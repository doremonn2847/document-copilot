from pydantic import Field

from app.assistant.calculations import CalculationRecord
from app.assistant.deps import TurnRegistry, normalized
from app.assistant.outputs import Contract, GroundedAnswer


class AcceptedReply(Contract):
    text: str
    parts: list[dict] = Field(default_factory=list)


GAPS = {
    # The server knows only that no accepted claim covers the target, not that
    # the filings lack the information; a live answer said otherwise wrongly.
    "missing_evidence": "This answer contains no verified statement for this target; check the cited filings directly.",
    "ambiguous_figures": "The figures or their units and periods could not be verified reliably.",
    "unsupported_causality": "The filings do not establish the requested causal relationship.",
    "ambiguous_question": "Please clarify the company, period, or measure you want to examine.",
    "outside_scope": "I can help analyze the available SEC filings; this request is outside that scope.",
}


def calculation_text(record: CalculationRecord) -> str:
    a, b = record.operands
    label = {
        "ratio_percent": "ratio (as a percentage)",
        "percent_change": "percentage change",
        "difference": "difference",
    }[record.operation]
    return (
        f"{label}: {a.entity} / {a.segment}; "
        f"{a.measure.strip()} ({a.period}, {a.unit}) and {b.measure.strip()} ({b.period}, {b.unit}) "
        f"= {record.display}"
    )


WITHHELD_NOTICE = "Some drafted statements were omitted because they could not be verified against the cited filings."


def render_answer(
    answer: GroundedAnswer, registry: TurnRegistry, *, withheld: int = 0
) -> AcceptedReply:
    indices = {}
    citations = []
    lines = []
    for claim in answer.claims:
        labels = []
        for ref in claim.evidence:
            key = (ref.chunk_id, normalized(ref.exact_quote))
            if key not in indices:
                index = len(indices) + 1
                indices[key] = index
                p = registry.passages[ref.chunk_id]
                citations.append(
                    {
                        "type": "data-citation",
                        "id": str(index),
                        "data": {
                            **p.model_dump(
                                mode="json",
                                exclude={
                                    "text",
                                    "neighbors",
                                    "fusion_score",
                                    "accession_number",
                                    "source_context",
                                },
                            ),
                            "index": index,
                            "excerpt": ref.exact_quote,
                            "source_kind": "original_table_context"
                            if any(ref.exact_quote in span for span in p.source_context)
                            else "indexed_chunk",
                        },
                    }
                )
            labels.append(f"[{indices[key]}]")
        prefix = (
            "Interpretation: "
            if claim.kind == "interpretation"
            else "Calculation: "
            if claim.kind == "calculation"
            else ""
        )
        text = claim.text
        if claim.kind == "fact" and registry.comparison_targets:
            p = registry.passages[claim.evidence[0].chunk_id]
            text = f"{p.ticker} / {p.form} / corpus {p.corpus_year if p.corpus_year is not None else 'unverified'}: {text}"
        if claim.calculation_id:
            text = calculation_text(registry.calculations[claim.calculation_id])
        lines.append(prefix + text + " " + " ".join(dict.fromkeys(labels)))
    for gap in answer.gaps:
        target = ""
        if gap.target and any(gap.target.model_dump(exclude_none=True).values()):
            f = gap.target
            target = (
                " / ".join(
                    filter(
                        None,
                        [
                            f.ticker,
                            f.form,
                            "corpus years " + ", ".join(map(str, f.corpus_years))
                            if f.corpus_years
                            else None,
                            "verified fiscal years "
                            + ", ".join(map(str, f.fiscal_years))
                            if f.fiscal_years
                            else None,
                        ],
                    )
                )
                + ": "
            )
        message = (
            "Not established from the retrieved evidence: " + gap.missing_detail
            if gap.missing_detail
            else GAPS[gap.reason]
        )
        lines.append(target + message)
    if withheld:
        # Fixed server text: an answer that lost claims must not read as complete.
        lines.append(WITHHELD_NOTICE)
    text = "\n\n".join(lines)
    return AcceptedReply(text=text, parts=[{"type": "text", "text": text}, *citations])
