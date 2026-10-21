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
