import asyncio
import json
from types import SimpleNamespace

import pytest

from app.assistant.tools import numeric_filters_for_question, prepare_calculation
from app.retrieval.types import RetrievalResult, SearchFilters
from tests.assistant.test_contracts import passage
from tests.assistant.test_numeric_facts import prepared_context


def test_numeric_preparation_does_not_reuse_unmentioned_2025_filter():
    d, _, source = prepared_context()
    source = source.model_copy(update={"corpus_year": 2022})
    wrong_source = passage("Azure provides cloud services.").model_copy(
        update={"ticker": "MSFT", "corpus_year": 2025}
    )
    filters_seen = []

    async def search(query, *, filters, top_k):
        filters_seen.append(filters)
        return RetrievalResult(
            passages=[wrong_source if filters and filters.corpus_years else source]
        )

    d.retriever = SimpleNamespace(search=search)
    proposed = SearchFilters(ticker="MSFT", form="10-K", corpus_years=[2025])
    result = asyncio.run(
        prepare_calculation.__wrapped__(SimpleNamespace(deps=d), d.question, proposed)
    )
    assert d.registry.calculation_pairs, result
    assert filters_seen[0].ticker == "MSFT"
    assert filters_seen[0].form == "10-K"
    assert filters_seen[0].corpus_years is None
    assert filters_seen[0].fiscal_years is None
    assert proposed.corpus_years == [2025]
    assert json.loads(result)["operation"] == "ratio_percent"
    assert d.numeric_attempts[0]["outcome"] == "verified_inputs"
    assert d.numeric_attempts[0]["passages"][0]["corpus_year"] == 2022


def test_explicit_2025_source_is_preserved_and_rejection_is_traceable():
    d, _, _ = prepared_context()
    d.question = "Use Microsoft's 2025 filing to find reported fiscal 2022 increases."
    source = passage("Azure provides cloud services.").model_copy(
        update={"ticker": "MSFT", "corpus_year": 2025}
    )

    async def search(query, *, filters, top_k):
        assert filters.corpus_years == [2025]
        return RetrievalResult(passages=[source])

    d.retriever = SimpleNamespace(search=search)
    result = asyncio.run(
        prepare_calculation.__wrapped__(
            SimpleNamespace(deps=d),
            d.question,
            SearchFilters(ticker="MSFT", corpus_years=[2025]),
        )
    )
    assert "rejected" in result
    assert d.numeric_attempts[0]["outcome"] == "rejected"
    assert d.numeric_attempts[0]["rejection_stage"] == "candidate_extraction"
    assert d.fact_judge.calls == []


@pytest.mark.parametrize(
    "question, years",
    [
        ("Use the 2025 filing for fiscal 2022 changes", [2025]),
        ("Fiscal 2022 compared with fiscal 2021", None),
        ("Compare 2021 through 2025 filings", [2022, 2023, 2025]),
        ("What about revenue?", [2025]),
        ("In that filing, calculate fiscal 2022 increases", [2025]),
    ],
)
def test_scope_guard_preserves_explicit_sources_ranges_and_undated_followups(
    question, years
):
    original = [2022, 2023, 2025] if "through" in question else [2025]
    filters = SearchFilters(ticker="MSFT", form="10-K", corpus_years=original)
    result = numeric_filters_for_question(question, filters)
    assert result.corpus_years == years
    assert result.fiscal_years is None
    assert filters.corpus_years == original


def test_fiscal_years_are_not_converted_to_corpus_filters():
    filters = SearchFilters(ticker="MSFT", fiscal_years=[2022])
    result = numeric_filters_for_question("Fiscal 2022 versus 2021", filters)
    assert result is filters
    assert result.corpus_years is None
