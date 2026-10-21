"""Explicit live checks: use --tb=no so provider/driver payloads stay private."""

import asyncio

import pytest

from app.retrieval.retriever import DocumentRetriever
from app.retrieval.types import SearchFilters


@pytest.mark.integration
def test_live_known_lexical_term():
    from app.config import Settings
    from app.retrieval.queries import full_text_search

    hits = asyncio.run(
        full_text_search(
            Settings(), "tariffs", SearchFilters(ticker="AAPL", corpus_years=[2025]), 50
        )
    )
    assert hits and all(hit.score > 0 for hit in hits)


@pytest.mark.integration
@pytest.mark.parametrize(
    "ticker,question,expected",
    [
        (
            "AAPL",
            "How do tariffs affect Apple manufacturing and supply chains?",
            "tariff",
        ),
        ("AAPL", "What were Apple's total net sales in 2025 and 2024?", "416,161"),
        (
            "MSFT",
            "What cloud services does Microsoft Azure offer to customers?",
            "azure",
        ),
        ("NVDA", "How does NVIDIA use CUDA for accelerated computing?", "cuda"),
    ],
)
def test_live_hybrid_lookup(ticker, question, expected):
    from app.config import Settings

    async def run():
        async with DocumentRetriever(Settings()) as retriever:
            result = await retriever.search(
                question,
                filters=SearchFilters(ticker=ticker, corpus_years=[2025], form="10-K"),
            )
            assert result.semantic_hits and result.lexical_available
            # A healthy AND query can match no rows; its execution/status is still verified.
            assert result.lexical_query
            assert expected in " ".join(p.text for p in result.passages).lower()
            assert all(
                p.ticker == ticker and p.corpus_year == 2025 for p in result.passages
            )
            assert all(p.source_url and p.fiscal_year is None for p in result.passages)
            first = result.passages[0]
            assert (await retriever.read_chunk(first.chunk_id)).text == first.text
            neighbors = await retriever.read_surrounding_chunks(first.chunk_id)
            assert all(
                p.document_id == first.document_id
                and abs(p.chunk_index - first.chunk_index) == 1
                for p in neighbors
            )

    asyncio.run(run())


@pytest.mark.integration
def test_live_comparison_and_empty_targets():
    from app.config import Settings

    async def run():
        async with DocumentRetriever(Settings()) as retriever:
            targets = [
                SearchFilters(ticker="AAPL", corpus_years=[year])
                for year in range(2021, 2026)
            ]
            targets += [
                SearchFilters(ticker="NVDA", corpus_years=[2025]),
                SearchFilters(ticker="ORCL", corpus_years=[2025]),
                SearchFilters(ticker="AAPL", corpus_years=[2099]),
            ]
            result = await retriever.compare(
                "Compare the companies' supply chain dependence and manufacturing risks",
                targets=targets,
            )
            assert len(result.targets) == 8
            assert all(len(t.result.passages) == 3 for t in result.targets[:6])
            assert all(
                not t.result.passages and t.result.warnings for t in result.targets[6:]
            )
            assert result.usage.embedding_tokens > 0

    asyncio.run(run())
