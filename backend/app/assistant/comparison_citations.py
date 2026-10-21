"""Company-scoped citations for the frozen comparison writer."""

from itertools import combinations, pairwise
from typing import Annotated, Literal

from pydantic import Field
from pydantic_ai import ModelRetry

from app.assistant.deps import DocumentAgentDeps
from app.assistant.outputs import Contract
from app.assistant.selection import SelectedClaim


class ComparisonFact(SelectedClaim):
    kind: Literal["fact"] = "fact"
    calculation_id: None = None


class ComparisonInterpretation(Contract):
    text: str = Field(min_length=1, max_length=2000)
    kind: Literal["interpretation"] = "interpretation"
    evidence_by_company: dict[
        str, Annotated[list[str], Field(min_length=1, max_length=5)]
    ] = Field(min_length=1)


def compared_companies(deps: DocumentAgentDeps) -> list[str]:
    targets = deps.registry.comparison_targets
    companies = {target.ticker for target in targets if target.ticker}
    if not targets or any(target.ticker is None for target in targets):
        companies.update(
            deps.registry.passages[ref.chunk_id].ticker
            for ref in deps.registry.evidence_refs.values()
        )
    return sorted(companies)


def prepare_comparison_citations(schema: dict, deps: DocumentAgentDeps) -> None:
    """Scope wire choices and require every compared company's own sources."""
    definitions = schema["$defs"]
    refs_by_company = {}
    for key, ref in deps.registry.evidence_refs.items():
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
    if 1 <= len(companies) <= 5 and all(ticker in company_refs for ticker in companies):
        allocations = []
        # Each branch allocates the same five slots across all required companies.
        for cuts in combinations(range(1, 5), len(companies) - 1):
            boundaries = (0, *cuts, 5)
            limits = [right - left for left, right in pairwise(boundaries)]
            allocations.append(
                {
                    "type": "object",
                    "properties": {
                        ticker: {
                            "type": "array",
                            "minItems": 1,
                            "maxItems": limit,
                            "items": company_refs[ticker],
                        }
                        for ticker, limit in zip(companies, limits)
                    },
                    "required": companies,
                    "additionalProperties": False,
                }
            )
        groups = allocations[0] if len(allocations) == 1 else {"anyOf": allocations}
        groups["description"] = (
            "Select supporting passages for every compared company. Five references total; split or narrow broader interpretations."
        )
        definitions["ComparisonInterpretation"]["properties"]["evidence_by_company"] = (
            groups
        )
    else:
        # Missing-company evidence cannot support an all-company synthesis.
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
    if not companies or set(claim.evidence_by_company) != set(companies):
        raise ModelRetry(
            f"Company citation groups must include exactly: {', '.join(companies)}."
        )
    selected = []
    for ticker in companies:
        for key in claim.evidence_by_company[ticker]:
            ref = deps.registry.evidence_refs.get(key)
            if ref is None or deps.registry.passages[ref.chunk_id].ticker != ticker:
                raise ModelRetry(
                    f"Select only {ticker}'s observed evidence IDs in its citation group."
                )
            if key not in selected:
                selected.append(key)
    if len(selected) > 5:
        raise ModelRetry(
            "At most five references total per interpretation. Split or narrow the claim; do not drop a compared company's citations."
        )
    return SelectedClaim(text=claim.text, kind="interpretation", evidence_ids=selected)
