"""Fact citations for the frozen comparison writer.

Comparisons publish cited per-filing facts and gaps only. Model-written trend
interpretations failed grounding in every live check and the judge did not
catch them (docs/guides/guided-comparisons.md), so trends, urgency and
cross-company assessments are reported as gaps instead.
"""

from typing import Literal

from app.assistant.deps import DocumentAgentDeps
from app.assistant.selection import SelectedClaim


class ComparisonFact(SelectedClaim):
    kind: Literal["fact"] = "fact"
    calculation_id: None = None


def prepare_comparison_citations(schema: dict, deps: DocumentAgentDeps) -> None:
    """Restrict fact citations to the evidence displayed to the writer."""
    refs = list(deps.registry.selectable_refs())
    fact = schema["$defs"]["ComparisonFact"]["properties"]
    if refs:
        fact["evidence_ids"]["items"]["enum"] = refs
    else:
        schema["properties"]["claims"]["maxItems"] = 0
    fact["calculation_id"]["enum"] = [None]
