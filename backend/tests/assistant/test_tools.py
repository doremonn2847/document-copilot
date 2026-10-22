from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.assistant.deps import BudgetExceeded, DocumentAgentDeps
from app.assistant.tools import expose_groups
from tests.assistant.test_contracts import passage


def deps():
    return DocumentAgentDeps(
        uuid4(),
        uuid4(),
        None,
        SimpleNamespace(
            assistant_tool_chars=12000,
            assistant_comparison_target_chars=1500,
            assistant_reasoning_effort="minimal",
            assistant_evidence_chars=48000,
            assistant_max_chunks=50,
            assistant_tool_calls=12,
            assistant_search_calls=4,
        ),
    )


def test_comparison_preserves_all_targets_and_registry_matches_emitted_text():
    d = deps()
    groups = [(f"Target {i}", [passage("evidence " * 2000)]) for i in range(25)]
    result = expose_groups(d, groups)
    assert len(result) <= 12000
    for label, items in groups:
        assert label in result
        for span in d.registry.observed.get(items[0].chunk_id, []):
            assert span in result
    assert len(d.registry.passages) == 25


def test_cumulative_exposure_and_unique_chunk_limits():
    d = deps()
    d.settings.assistant_max_chunks = 1
    d.settings.assistant_evidence_chars = 15
    result = expose_groups(d, [("many", [passage("x" * 100), passage("y" * 100)])])
    assert len(d.registry.passages) == 1
    assert d.registry.exposed_characters == 15
    assert "truncated" in result


def test_tool_budget_counts_failures():
    import asyncio

    d = deps()
    d.settings.assistant_tool_calls = 1
    asyncio.run(d.begin("reading"))
    with pytest.raises(BudgetExceeded):
        asyncio.run(d.begin("reading"))


def test_budget_exhaustion_executes_no_retrieval():
    import asyncio

    from app.assistant.tools import search_filings

    d = deps()
    d.tool_calls = d.settings.assistant_tool_calls
    # No retriever is installed; the budget response must precede any I/O.
    result = asyncio.run(search_filings(SimpleNamespace(deps=d), "Revenue"))
    assert "budget exhausted" in result


def test_comparison_retains_lexical_degradation_and_target_warnings():
    import asyncio

    from app.assistant.tools import compare_filings
    from app.retrieval.types import (
        ComparisonResult,
        ComparisonTargetResult,
        RetrievalResult,
        RetrievalUsage,
        SearchFilters,
    )

    d = deps()
    target = SearchFilters(ticker="AAPL", corpus_years=[2025])

    async def compare(*args, **kwargs):
        return ComparisonResult(
            targets=[
                ComparisonTargetResult(
                    target=target,
                    result=RetrievalResult(
                        passages=[passage()],
                        lexical_available=False,
                        warnings=["Lexical unavailable: keyword service failed."],
                    ),
                )
            ],
            usage=RetrievalUsage(),
        )

    d.retriever = SimpleNamespace(compare=compare)
    output = asyncio.run(
        compare_filings(SimpleNamespace(deps=d), "Supply risk", [target])
    )
    assert "lexical_available=False" in output
    assert "keyword service failed" in output
    assert len(output) <= 12000


def test_multiyear_comparison_expands_years_before_searching():
    import asyncio

    from app.assistant.tools import compare_filings
    from app.retrieval.types import (
        ComparisonResult,
        ComparisonTargetResult,
        RetrievalResult,
        RetrievalUsage,
        SearchFilters,
    )

    d = deps()
    requested = SearchFilters(ticker="AAPL", corpus_years=[2021, 2022, 2023])

    async def compare(query, *, targets):
        assert [t.corpus_years for t in targets] == [[2021], [2022], [2023]]
        return ComparisonResult(
            targets=[
                ComparisonTargetResult(target=t, result=RetrievalResult())
                for t in targets
            ],
            usage=RetrievalUsage(),
        )

    d.retriever = SimpleNamespace(compare=compare)
    output = asyncio.run(
        compare_filings(SimpleNamespace(deps=d), "Compare risk", [requested])
    )
    assert len(d.registry.comparison_targets) == 3
    assert output.count("NO EVIDENCE") == 3


@pytest.mark.parametrize("operation", ["search", "compare"])
def test_initial_retrieval_retains_question_and_later_refinement(operation):
    import asyncio

    from app.assistant.tools import compare_filings, search_filings
    from app.retrieval.types import ComparisonResult, RetrievalResult, SearchFilters

    d = deps()
    d.question = "What is the ratio of the reported annual increases?"
    seen = []

    async def retrieve(query, **kwargs):
        seen.append(query)
        return (
            RetrievalResult()
            if operation == "search"
            else ComparisonResult(targets=[], usage={})
        )

    d.retriever = SimpleNamespace(search=retrieve, compare=retrieve)
    ctx = SimpleNamespace(deps=d)

    async def call(query):
        if operation == "search":
            return await search_filings(ctx, query)
        return await compare_filings(ctx, query, [SearchFilters(ticker="MSFT")])

    asyncio.run(call("gross margin revenue"))
    asyncio.run(call("fiscal period heading and USD billions"))
    assert d.question in seen[0]
    assert "gross margin revenue" in seen[0]
    assert seen[1] == "fiscal period heading and USD billions"


@pytest.mark.parametrize(
    "question",
    ["What about 2021?", "What is the ratio of the reported annual increases?"],
)
def test_numeric_preparation_preserves_resolved_short_followups(question):
    import asyncio

    from app.assistant.tools import prepare_calculation
    from app.retrieval.types import RetrievalResult

    d = deps()
    d.question = question
    d.settings.assistant_grounding_repairs = 1
    seen = []

    async def search(query, **kwargs):
        seen.append(query)
        return RetrievalResult()

    d.retriever = SimpleNamespace(search=search)
    focus = "MSFT reported gross-margin and revenue increases in fiscal 2021"
    asyncio.run(prepare_calculation(SimpleNamespace(deps=d), focus))
    assert question in seen[0]
    if len(question.split()) <= 5:
        assert focus in seen[0]
    else:
        assert seen[0] == question


def test_filters_with_no_retrieved_passages_are_reported_to_the_analyst():
    import asyncio

    from app.assistant.outputs import EvidenceGap, GroundedAnswer
    from app.assistant.rendering import render_answer
    from app.assistant.tools import compare_filings, search_filings
    from app.retrieval.types import (
        ComparisonResult,
        ComparisonTargetResult,
        RetrievalResult,
        RetrievalUsage,
        SearchFilters,
    )

    d = deps()
    d.question = "What did Tesla report about vehicle revenue in its 2028 10-K?"
    tesla = SearchFilters(ticker="TSLA", form="10-K", corpus_years=[2028])
    apple = SearchFilters(ticker="AAPL", corpus_years=[2025])

    class Retriever:
        async def search(self, query, *, filters=None):
            return RetrievalResult(passages=[])

        async def compare(self, query, *, targets):
            return ComparisonResult(
                targets=[
                    ComparisonTargetResult(
                        target=t,
                        result=RetrievalResult(
                            passages=[passage()] if t.ticker == "AAPL" else []
                        ),
                    )
                    for t in targets
                ],
                usage=RetrievalUsage(),
            )

    d.retriever = Retriever()
    ctx = SimpleNamespace(deps=d)
    asyncio.run(search_filings.__wrapped__(ctx, "Tesla vehicle revenue", tesla))
    asyncio.run(compare_filings.__wrapped__(ctx, "compare", [tesla, apple]))
    # Searched twice, recorded once; the AAPL target returned a passage.
    assert d.registry.unmatched_filters == [tesla]

    answer = GroundedAnswer(
        status="insufficient_evidence",
        gaps=[EvidenceGap(target=tesla, reason="missing_evidence")],
    )
    text = render_answer(answer, d.registry).text
    assert text.endswith(
        "No indexed passage was retrieved for TSLA / 10-K / corpus years 2028."
    )


# Filing sentences run to hundreds of characters; short ones hide starvation.
FILING_SENTENCE = (
    "The Company depends on component and product manufacturing and logistical "
    "services provided by outsourcing partners, many of which are located outside "
    "of the U.S., and substantially all of its hardware products are manufactured "
    "by partners located primarily in Asia. "
)


def test_scaled_comparison_budget_gives_every_target_citable_spans():
    # Live: a 25-target comparison exposed one citable span in 12,000 characters.
    def cited_targets(limit):
        d = deps()
        # Live-sized headers: target JSON plus three passage IDs per target.
        label = '{"ticker":"NVDA","form":"10-K","corpus_years":[2025]} lexical_available=True'
        groups = [
            (
                label.replace("2025", str(2000 + i)),
                [passage(FILING_SENTENCE * 12) for _ in range(3)],
            )
            for i in range(25)
        ]
        expose_groups(d, groups, full=True, limit=limit)
        cited = {ref.chunk_id for ref in d.registry.evidence_refs.values()}
        return sum(any(p.chunk_id in cited for p in items) for _, items in groups)

    assert cited_targets(None) < 25
    assert cited_targets(25 * 1500) == 25


def test_table_context_longer_than_a_quote_is_exposed_by_rows():
    # Live: a whole 5,000+ character table fit the room but not one quote,
    # and the search tool failed on EvidenceRef validation.
    from app.assistant.outputs import MAX_QUOTE_CHARS

    pad = " " * 80
    table = "\n".join(
        [f"|{pad}| 2024 |{pad}| 2025 |"]
        + [f"| Revenue line {i} |{pad}| {i},000 |{pad}| {i},500 |" for i in range(40)]
    )
    assert len(table) > MAX_QUOTE_CHARS
    p = passage("Revenue increased in 2025.").model_copy(
        update={"source_context": [table]}
    )
    d = deps()
    expose_groups(d, [("Search", [p])], focus="revenue line")
    quotes = [ref.exact_quote for ref in d.registry.evidence_refs.values()]
    assert quotes and all(len(q) <= MAX_QUOTE_CHARS for q in quotes)
    assert any("Revenue line" in q for q in quotes)


def test_question_words_pick_table_rows_the_search_keywords_missed():
    # Live Q02: keywords named only AWS, so North America and International
    # rows were never citable and drafts fell back to flattened text.
    pad = " " * 400
    table = "\n".join(
        [f"|{pad}| 2023 |{pad}| 2024 |"]
        + [
            f"| {label} |{pad}| {a} |{pad}| {b} |"
            for label, a, b in [
                ("Operating expenses", "1,000", "2,000"),
                ("North America", "$ 14,877", "$ 24,967"),
                ("International", "(2,656)", "3,792"),
                ("AWS", "24,631", "39,834"),
                ("Other", "5", "6"),
            ]
        ]
    )
    p = passage("Segment results.").model_copy(update={"source_context": [table]})
    d = deps()
    d.question = "Compare AWS against North America and International."
    expose_groups(d, [("Search", [p])], focus="AWS operating income", limit=6000)
    rows = [
        r.exact_quote.split("|")[1].strip()
        for r in d.registry.evidence_refs.values()
        if r.exact_quote.startswith("|")
    ]
    assert {"North America", "International", "AWS"} <= set(rows)
    assert "Other" not in rows
