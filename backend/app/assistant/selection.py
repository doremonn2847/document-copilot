"""Resolve model-selected evidence IDs into immutable source references."""

import json
from itertools import product
from typing import Literal
from uuid import UUID

from pydantic import Field, ValidationError, field_validator
from pydantic_ai import ModelRetry, RunContext

from app.assistant.deps import DocumentAgentDeps, normalized
from app.assistant.outputs import AnswerClaim, Contract, EvidenceGap, GroundedAnswer
from app.grounding.claim_context import missing_company_evidence
from app.retrieval.types import RetrievedPassage, SearchFilters


class SelectedClaim(Contract):
    text: str = Field(
        min_length=1,
        max_length=2000,
        description="One small factual statement from one filing; cross-filing inferences must be labeled interpretation and directly supported.",
    )
    kind: Literal["fact", "calculation", "interpretation"] = "fact"
    evidence_ids: list[str] = Field(default_factory=list, max_length=5)
    calculation_id: UUID | None = None

    @field_validator("evidence_ids")
    @classmethod
    def canonical_ids(cls, values: list[str]) -> list[str]:
        return [value.upper() for value in values]


def matches_target(passage: RetrievedPassage, target: SearchFilters) -> bool:
    return (
        (not target.ticker or passage.ticker == target.ticker)
        and (not target.form or passage.form == target.form)
        and (not target.corpus_years or passage.corpus_year in target.corpus_years)
        and (not target.fiscal_years or passage.fiscal_year in target.fiscal_years)
    )


class RequestedGap(EvidenceGap):
    request_quote: str = Field(
        min_length=1,
        max_length=1000,
        description="Copy the exact part of the user's question that remains unanswered. Proposed gaps and internal verification requirements are not user requests.",
    )


def final_answer(
    ctx: RunContext[DocumentAgentDeps],
    claims: list[SelectedClaim],
    gaps: list[RequestedGap],
) -> GroundedAnswer:
    """Submit atomic claims citing displayed E IDs. The server attaches exact quotes.

    Calculation claims need only their calculation_id, with evidence_ids empty.
    Uncovered comparison targets become explicit missing-evidence gaps.
    """
    registry = ctx.deps.registry
    resolved = []
    try:
        if len(gaps) > 25:
            raise ModelRetry("At most 25 requested-aspect gaps are supported.")
        for gap in gaps:
            if (
                not gap.request_quote
                or not normalized(gap.request_quote)
                or normalized(gap.request_quote) not in normalized(ctx.deps.question)
            ):
                raise ModelRetry(
                    "Each model-written gap requires request_quote copied verbatim from the actual question. Do not quote an invented requirement, the proposed gap or verification policy. Remove unrequested gaps."
                )
        for claim in claims:
            if claim.kind == "calculation":
                record = registry.calculations.get(claim.calculation_id)
                if record is None:
                    raise ModelRetry(
                        "Unknown calculation ID; use a completed calculation"
                    )
                evidence = list(
                    {
                        (ref.chunk_id, ref.exact_quote): ref
                        for operand in record.operands
                        for ref in operand.evidence
                    }.values()
                )
            else:
                missing = [
                    key
                    for key in claim.evidence_ids
                    if key not in registry.evidence_refs
                ]
                if missing:
                    raise ModelRetry(
                        f"Unknown evidence IDs: {missing}. Select displayed E IDs only."
                    )
                evidence = [
                    registry.evidence_refs[key]
                    for key in dict.fromkeys(claim.evidence_ids)
                ]
            resolved.append(
                AnswerClaim(
                    text=claim.text,
                    kind=claim.kind,
                    calculation_id=claim.calculation_id,
                    evidence=evidence,
                )
            )
        for index, claim in enumerate(resolved):
            missing = missing_company_evidence(
                claim, [registry.passages[ref.chunk_id] for ref in claim.evidence]
            )
            if missing:
                candidates = {}
                for key, ref in registry.evidence_refs.items():
                    passage = registry.passages[ref.chunk_id]
                    if passage.ticker in missing:
                        label = f"{passage.ticker} / corpus {passage.corpus_year}"
                        ids = candidates.setdefault(label, [])
                        if len(ids) < 3:
                            ids.append(key)
                raise ModelRetry(
                    f"claim {index}: cite this claim's own evidence for every named company: {', '.join(sorted(missing))}. "
                    "Other claims' citations do not carry over. Omit the synthesis or select supporting IDs from each named company. "
                    "Observed candidate IDs (provenance only; check their displayed quotes for support): "
                    + json.dumps(candidates)
                )
        expanded = []
        for gap in gaps:
            # A specific comparison limitation belongs to the group as a whole;
            # copying it to each year mislabels years already supported by claims.
            if gap.target is None or gap.missing_detail:
                expanded.append(gap)
                continue
            for corpus_year, fiscal_year in product(
                gap.target.corpus_years or [None], gap.target.fiscal_years or [None]
            ):
                expanded.append(
                    gap.model_copy(
                        update={
                            "target": gap.target.model_copy(
                                update={
                                    "corpus_years": [corpus_year]
                                    if corpus_year is not None
                                    else None,
                                    "fiscal_years": [fiscal_year]
                                    if fiscal_year is not None
                                    else None,
                                }
                            )
                        }
                    )
                )
                if len(expanded) > 25:
                    raise ModelRetry(
                        "At most 25 individual evidence gaps are supported; narrow the targets."
                    )
        gaps = list({gap.model_dump_json(): gap for gap in expanded}.values())
        cited = [
            registry.passages[ref.chunk_id] for c in resolved for ref in c.evidence
        ]
        for target in registry.comparison_targets:
            if not any(matches_target(p, target) for p in cited) and not any(
                g.target == target for g in gaps
            ):
                gaps.append(EvidenceGap(target=target, reason="missing_evidence"))
        return GroundedAnswer(
            status="partial"
            if resolved and gaps
            else "answered"
            if resolved
            else "insufficient_evidence",
            claims=resolved,
            gaps=gaps,
        )
    except ValidationError as error:
        raise ModelRetry(str(error)) from None
