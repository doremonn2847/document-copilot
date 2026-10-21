import json
import re
from decimal import Decimal

from app.assistant.calculations import SOURCE_NUMBER, parse_number, validate_record
from app.assistant.deps import TurnRegistry, normalized
from app.assistant.outputs import GroundedAnswer
from app.assistant.selection import matches_target
from app.grounding.claim_context import claim_context_errors, unsupported_absence_claim


def numeric_tokens(text: str) -> set[Decimal]:
    # A parenthesized year used as a heading is not an accounting negative.
    # Ordinary '(2025) dollars' must retain its negative-value interpretation.
    text = re.sub(r"\(((?:19|20)\d{2})\)(?=\s*:)", r"\1", text)
    return {parse_number(token.group()) for token in SOURCE_NUMBER.finditer(text)}


def uncited_year_hint(claim, numbers: set[Decimal], registry: TurnRegistry) -> str:
    """Make the repair actionable: name same-company sources for each uncited year."""
    years = sorted(
        int(n) for n in numbers if n == n.to_integral_value() and 1990 <= n <= 2100
    )
    if not years:
        return ""
    tickers = {
        registry.passages[ref.chunk_id].ticker
        for ref in claim.evidence
        if ref.chunk_id in registry.passages
    }
    candidates = {}
    for key, ref in registry.selectable_refs().items():
        p = registry.passages[ref.chunk_id]
        if p.ticker in tickers and p.corpus_year in years:
            ids = candidates.setdefault(f"{p.ticker} {p.corpus_year}", [])
            if len(ids) < 4:
                ids.append(key)
    return (
        f". Uncited years {years}: cite a displayed source of that company and year"
        + (
            f" (candidate IDs; check their quotes support the claim: {json.dumps(candidates)})"
            if candidates
            else ""
        )
        + ", or remove the year from the claim and state that limitation as a gap instead"
    )


def structural_errors(
    answer: GroundedAnswer,
    registry: TurnRegistry,
    *,
    searches: int,
    max_claims: int = 20,
    max_refs: int = 5,
) -> list[str]:
    errors = []
    bypass = not answer.claims and all(
        g.reason in ("outside_scope", "ambiguous_question") for g in answer.gaps
    )
    if searches < 1 and not bypass:
        errors.append(
            "Retrieve evidence before answering or reporting missing evidence"
        )
    if len(answer.claims) > max_claims:
        errors.append("Claim limit exceeded")
    for i, claim in enumerate(answer.claims):
        errors.extend(
            f"claim {i}: {error}"
            for error in claim_context_errors(
                claim,
                [
                    registry.passages[ref.chunk_id]
                    for ref in claim.evidence
                    if ref.chunk_id in registry.passages
                ],
            )
        )
        documents = {
            registry.passages[ref.chunk_id].document_id
            for ref in claim.evidence
            if ref.chunk_id in registry.passages
        }
        if claim.kind == "fact" and len(documents) > 1:
            errors.append(
                f"claim {i}: factual claims must cite one filing. Split facts by filing; label a supported cross-filing inference as interpretation."
            )
        quoted_numbers = set().union(
            *(numeric_tokens(ref.exact_quote) for ref in claim.evidence)
        )
        record = (
            registry.calculations.get(claim.calculation_id)
            if claim.calculation_id
            else None
        )
        if record is not None:
            quoted_numbers.update(numeric_tokens(record.display))
        for ref in claim.evidence:
            p = registry.passages.get(ref.chunk_id)
            if p:
                quoted_numbers.update(
                    numeric_tokens(
                        f"{p.form} {p.corpus_year} {p.fiscal_year} {p.filing_date} {p.report_date} {p.page}"
                    )
                )
        missing_numbers = numeric_tokens(claim.text) - quoted_numbers
        if claim.kind != "calculation" and missing_numbers:
            errors.append(
                f"claim {i}: uncited numeric tokens {', '.join(str(n) for n in sorted(missing_numbers))}. Cite exact supporting source numbers/periods; derived results require calculation kind and a recorded calculation ID"
                + uncited_year_hint(claim, missing_numbers, registry)
            )
        if len(claim.evidence) > max_refs:
            errors.append(f"claim {i}: evidence limit exceeded")
        for ref in claim.evidence:
            try:
                registry.verify(ref)
            except ValueError as error:
                errors.append(f"claim {i}: {error}")
        if claim.calculation_id is not None:
            record = registry.calculations.get(claim.calculation_id)
            if record is None:
                errors.append(f"claim {i}: unknown calculation")
                continue
            try:
                validate_record(record, registry)
            except ValueError as error:
                errors.append(f"claim {i}: {error}")
            cited = {(r.chunk_id, normalized(r.exact_quote)) for r in claim.evidence}
            required = {
                (r.chunk_id, normalized(r.exact_quote))
                for o in record.operands
                for r in o.evidence
            }
            if not required <= cited:
                errors.append(f"claim {i}: cite every calculation input quote")
    cited_passages = [
        registry.passages[ref.chunk_id]
        for claim in answer.claims
        for ref in claim.evidence
        if ref.chunk_id in registry.passages
    ]
    for i, gap in enumerate(answer.gaps):
        if gap.missing_detail and unsupported_absence_claim(gap.missing_detail):
            errors.append(
                f"gap {i}: selected excerpts cannot establish absence from the entire filing. Describe the retrieved evidence limitation instead."
            )
        if (
            gap.reason == "missing_evidence"
            and not gap.missing_detail
            and any(
                gap.target is None or matches_target(p, gap.target)
                for p in cited_passages
            )
        ):
            errors.append(
                f"gap {i}: claims already cite this target. Remove a spurious gap, or supply missing_detail naming the specific requested information still unverified; do not report blanket missing evidence."
            )
    for target in registry.comparison_targets:
        covered = any(matches_target(p, target) for p in cited_passages)
        if not covered and not any(gap.target == target for gap in answer.gaps):
            errors.append(
                "Preserve comparison target with a cited claim or explicit gap: "
                + target.model_dump_json(exclude_none=True)
            )
    return errors
