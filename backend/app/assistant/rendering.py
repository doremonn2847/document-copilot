import re

from pydantic import Field

from app.assistant.calculations import CalculationRecord
from app.assistant.deps import TurnRegistry, normalized
from app.assistant.outputs import Contract, EvidenceGap, GroundedAnswer
from app.retrieval.types import SearchFilters


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


BORROWED_HEADING = re.compile(
    r"\s*(?:For the Fiscal Year Ended|Fiscal Year \d{4} Compared)", re.IGNORECASE
)
WITHHELD_NOTICE = "Some drafted statements were omitted because they could not be verified against the cited filings."
ADVICE_NOTICE = "I can't give investment recommendations. The following reports only what the cited filings say."
CAUSAL_NOTICE = "The cited filings report facts and the companies' own explanations; they do not prove causes beyond what the filings themselves state."


def target_label(f: SearchFilters) -> str:
    return " / ".join(
        filter(
            None,
            [
                f.ticker,
                f.form,
                "corpus years " + ", ".join(map(str, f.corpus_years))
                if f.corpus_years
                else None,
                "verified fiscal years " + ", ".join(map(str, f.fiscal_years))
                if f.fiscal_years
                else None,
            ],
        )
    )


def merged_coverage_gaps(gaps: list[EvidenceGap]) -> list[EvidenceGap]:
    """One "no verified statement" line per company instead of per year.

    A live four-company, five-year answer listed 20 such lines in a row.
    """
    merged: dict[tuple, EvidenceGap] = {}
    result = []
    for gap in gaps:
        t = gap.target
        if not (
            gap.reason == "missing_evidence"
            and gap.missing_detail is None
            and t
            and t.ticker
            and t.corpus_years
            and not t.fiscal_years
        ):
            result.append(gap)
            continue
        key = (t.ticker, t.form)
        if key in merged:
            years = sorted({*merged[key].target.corpus_years, *t.corpus_years})
            merged[key].target.corpus_years = years
        else:
            merged[key] = gap.model_copy(deep=True)
            result.append(merged[key])
    return result


def render_answer(
    answer: GroundedAnswer,
    registry: TurnRegistry,
    *,
    withheld: int = 0,
    advice: bool = False,
    causal: bool = False,
    uncovered: list[str] | None = None,
    interpreted: str | None = None,
    years: set[int] | None = None,
) -> AcceptedReply:
    indices = {}
    citations = []
    blocks = []
    for claim in answer.claims:
        numbers = []
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
                            # The chunk's page range covers its text, table
                            # rows and the caption above the table; a fiscal
                            # heading found elsewhere in the filing (cover page,
                            # a later "Compared with" heading) shows none.
                            "page": None
                            if ref.exact_quote not in p.text
                            and BORROWED_HEADING.match(ref.exact_quote)
                            else p.page,
                            "excerpt": ref.exact_quote,
                            "source_kind": "original_table_context"
                            if any(ref.exact_quote in span for span in p.source_context)
                            else "indexed_chunk",
                        },
                    }
                )
            numbers.append(indices[key])
        label = None
        cited = [registry.passages[ref.chunk_id] for ref in claim.evidence]
        # A claim from a filing outside the years the question names is
        # labelled with that filing: a live "Microsoft's 2019 10-K" answer
        # showed 2021 statements whose text never said 2021.
        off_year = bool(years) and not any(
            p.corpus_year in years or p.fiscal_year in years for p in cited
        )
        if claim.kind == "fact" and (registry.comparison_targets or off_year):
            p = cited[0]
            label = f"{p.ticker} / {p.form} / corpus {p.corpus_year if p.corpus_year is not None else 'unverified'}"
        blocks.append(
            {
                "kind": "claim",
                "claim_kind": claim.kind,
                "label": label,
                "text": calculation_text(registry.calculations[claim.calculation_id])
                if claim.calculation_id
                else claim.text,
                "citations": list(dict.fromkeys(numbers)),
            }
        )
    for gap in merged_coverage_gaps(answer.gaps):
        blocks.append(
            {
                "kind": "gap",
                "label": target_label(gap.target) if gap.target else None,
                # A reply with no claims that asks for clarification or declines the
                # scope uses fixed text ("not established" misreads "which
                # company?"). In a partial answer the specific limitation is kept:
                # live answers otherwise read "this request is outside that scope"
                # or "Please clarify..." under verified Apple and Microsoft facts.
                "text": "Not established from the retrieved evidence: "
                + gap.missing_detail
                if gap.missing_detail
                and not (
                    gap.reason in ("ambiguous_question", "outside_scope")
                    and not answer.claims
                )
                else GAPS[gap.reason],
            }
        )
    # Fixed server text below states only what the server observed this turn.
    blocks += [
        {"kind": "notice", "text": f"No indexed passage was retrieved for {label}."}
        for label in dict.fromkeys(target_label(f) for f in registry.unmatched_filters)
        if label
    ]
    if withheld:
        # An answer that lost claims must not read as complete.
        blocks.append({"kind": "notice", "text": WITHHELD_NOTICE})
    if uncovered:
        blocks.append(
            {
                "kind": "notice",
                "text": f"No statement in this answer covers {', '.join(uncovered)}; ask about them separately.",
            }
        )
    if causal:
        blocks.insert(0, {"kind": "notice", "text": CAUSAL_NOTICE})
    if interpreted:
        # A follow-up was rewritten as a standalone question; show how it was read.
        blocks.insert(0, {"kind": "notice", "text": f"Answered as: {interpreted}"})
    if advice:
        blocks.insert(0, {"kind": "notice", "text": ADVICE_NOTICE})
    text = "\n\n".join(block_text(block) for block in blocks)
    return AcceptedReply(
        text=text,
        parts=[
            {"type": "text", "text": text},
            # Structured blocks let the browser lay out claims, gaps and notices.
            {"type": "data-answer", "id": "answer", "data": {"blocks": blocks}},
            *citations,
        ],
    )


def block_text(block: dict) -> str:
    """The plain-text form kept for history, replay and older clients."""
    if block["kind"] != "claim":
        return (
            f"{block['label']}: {block['text']}"
            if block.get("label")
            else block["text"]
        )
    prefix = {"interpretation": "Interpretation: ", "calculation": "Calculation: "}
    label = f"{block['label']}: " if block["label"] else ""
    return (
        prefix.get(block["claim_kind"], "")
        + label
        + block["text"]
        + " "
        + " ".join(f"[{number}]" for number in block["citations"])
    )
