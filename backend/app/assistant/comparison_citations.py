"""Company-scoped citations for the frozen comparison writer."""

from typing import Annotated, Literal

from pydantic import Field
from pydantic_ai import ModelRetry

from app.assistant.deps import DocumentAgentDeps
from app.assistant.outputs import INTERPRETATION_REFS, Contract
from app.assistant.selection import SelectedClaim


class ComparisonFact(SelectedClaim):
    kind: Literal["fact"] = "fact"
    calculation_id: None = None


class ComparisonInterpretation(Contract):
    text: str = Field(min_length=1, max_length=2000)
    kind: Literal["interpretation"] = "interpretation"
    evidence_by_company: dict[
        str, Annotated[list[str], Field(min_length=1, max_length=INTERPRETATION_REFS)]
    ] = Field(min_length=1)


class ResolvedInterpretation(SelectedClaim):
    # Flattened company groups keep the interpretation limit, not the fact limit.
    evidence_ids: list[str] = Field(max_length=INTERPRETATION_REFS)


def compared_companies(deps: DocumentAgentDeps) -> list[str]:
    targets = deps.registry.comparison_targets
    companies = {target.ticker for target in targets if target.ticker}
    if not targets or any(target.ticker is None for target in targets):
        companies.update(
            deps.registry.passages[ref.chunk_id].ticker
            for ref in deps.registry.selectable_refs().values()
        )
    return sorted(companies)


def allocation(company_refs: dict[str, dict], limits: dict[str, int]) -> dict:
    return {
        "type": "object",
        "properties": {
            ticker: {
                "type": "array",
                "minItems": 1,
                "maxItems": limit,
                "items": company_refs[ticker],
            }
            for ticker, limit in limits.items()
        },
        "required": list(limits),
        "additionalProperties": False,
    }


def prepare_comparison_citations(schema: dict, deps: DocumentAgentDeps) -> None:
    """Scope wire choices to one compared company's or every compared company's sources."""
    definitions = schema["$defs"]
    refs_by_company = {}
    for key, ref in deps.registry.selectable_refs().items():
        ticker = deps.registry.passages[ref.chunk_id].ticker
        refs_by_company.setdefault(ticker, []).append(key)
    company_refs = {}
    for index, (ticker, keys) in enumerate(sorted(refs_by_company.items())):
        name = f"CompanyEvidence{index}"
        definitions[name] = {"type": "string", "enum": keys, "description": ticker}
        company_refs[ticker] = {"$ref": f"#/$defs/{name}"}

    # Reuse definitions so each evidence ID counts once toward provider enum limits.
    fact = definitions["ComparisonFact"]["properties"]
    if company_refs:
        fact["evidence_ids"]["items"] = {"anyOf": list(company_refs.values())}
    fact["calculation_id"]["enum"] = [None]

    companies = compared_companies(deps)
    observed = [ticker for ticker in companies if ticker in company_refs]
    branches = []
    if len(companies) > 1:
        # A one-company trend should not spend slots on companies it does not discuss.
        branches += [
            allocation(company_refs, {ticker: INTERPRETATION_REFS})
            for ticker in observed
        ]
    share = INTERPRETATION_REFS // len(companies) if companies else 0
    if share and observed == companies:
        # An equal share bounds the cross-company total in one branch instead of
        # enumerating every allocation; two companies get one source per year each.
        branches.append(allocation(company_refs, dict.fromkeys(companies, share)))
    if branches:
        groups = branches[0] if len(branches) == 1 else {"anyOf": branches}
        groups["description"] = (
            f"Cite one compared company's passages for a single-company interpretation, or every compared company's passages for a cross-company one. {INTERPRETATION_REFS} references total; split or narrow broader interpretations."
        )
        definitions["ComparisonInterpretation"]["properties"]["evidence_by_company"] = (
            groups
        )
    else:
        # Without observed evidence no interpretation can be supported.
        schema["properties"]["claims"]["items"] = {"$ref": "#/$defs/ComparisonFact"}
        del definitions["ComparisonInterpretation"]
    if not company_refs:
        schema["properties"]["claims"]["maxItems"] = 0


def resolve_comparison_claim(
    claim: ComparisonFact | ComparisonInterpretation, deps: DocumentAgentDeps
) -> SelectedClaim:
    if not isinstance(claim, ComparisonInterpretation):
        if claim.kind != "fact":
            raise ModelRetry(
                "Interpretations require evidence_by_company, not a flat evidence_ids list."
            )
        return SelectedClaim.model_validate(claim.model_dump())
    companies = compared_companies(deps)
    groups = set(claim.evidence_by_company)
    if not companies or not (
        groups == set(companies) or len(groups) == 1 and groups <= set(companies)
    ):
        raise ModelRetry(
            f"Company citation groups must name one compared company or exactly: {', '.join(companies)}."
        )
    refs = deps.registry.selectable_refs()
    selected = []
    for ticker in [ticker for ticker in companies if ticker in groups]:
        for key in claim.evidence_by_company[ticker]:
            ref = refs.get(key)
            if ref is None or deps.registry.passages[ref.chunk_id].ticker != ticker:
                raise ModelRetry(
                    f"Select only {ticker}'s observed evidence IDs in its citation group."
                )
            if key not in selected:
                selected.append(key)
    if len(selected) > INTERPRETATION_REFS:
        raise ModelRetry(
            f"At most {INTERPRETATION_REFS} references total per interpretation. Split or narrow the claim; do not drop a compared company's citations."
        )
    return ResolvedInterpretation(
        text=claim.text, kind="interpretation", evidence_ids=selected
    )
