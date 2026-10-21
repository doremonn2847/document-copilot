import asyncio
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID

import pytest
from test_contracts import passage

from app.retrieval import retriever as module
from app.retrieval.types import KeywordResult, RankedChunkHit, SearchFilters


@pytest.fixture
def service(config, monkeypatch):
    monkeypatch.setattr(
        module, "embed_query", AsyncMock(return_value=([0.1] * 1536, 8))
    )
    monkeypatch.setattr(
        module,
        "extract_keywords",
        AsyncMock(return_value=KeywordResult(text="revenue services growth")),
    )
    monkeypatch.setattr(module, "build_keyword_agent", lambda *args: MagicMock())
    monkeypatch.setattr(
        module.queries,
        "semantic_search",
        AsyncMock(
            return_value=[
                RankedChunkHit(chunk_id=UUID(int=1), rank=1, score=0.9),
                RankedChunkHit(chunk_id=UUID(int=2), rank=2, score=0.8),
            ]
        ),
    )
    monkeypatch.setattr(
        module.queries,
        "full_text_search",
        AsyncMock(
            return_value=[RankedChunkHit(chunk_id=UUID(int=2), rank=1, score=1.0)]
        ),
    )
    monkeypatch.setattr(
        module.queries, "get_chunks", AsyncMock(return_value=[passage(1), passage(2)])
    )
    monkeypatch.setattr(
        module.queries,
        "get_neighbors",
        AsyncMock(
            return_value=[
                passage(1),
                passage(3),
                passage(3),
                passage(4, document_id=UUID(int=200)),
            ]
        ),
    )
    return module.DocumentRetriever(config, client=MagicMock())


def test_hydration_ranking_and_neighbor_dedup(service):
    result = asyncio.run(
        service.search("Which products drove Apple's services growth?")
    )
    assert [p.chunk_id.int for p in result.passages] == [2, 1]
    assert [n.chunk_id.int for p in result.passages for n in p.neighbors] == [3]
    assert result.lexical_available and len(result.semantic_hits) == 2
    assert result.usage.embedding_tokens == 8
    assert any("fiscal" in w.lower() for w in result.warnings)


def test_keyword_failure_degrades_visibly(service, monkeypatch):
    monkeypatch.setattr(
        module,
        "extract_keywords",
        AsyncMock(
            return_value=KeywordResult(warning="Lexical search unavailable: timeout")
        ),
    )
    result = asyncio.run(
        service.search("How did the company describe its supply chain?")
    )
    assert not result.lexical_available and not result.lexical_hits
    assert any("timeout" in w for w in result.warnings)
    module.queries.full_text_search.assert_not_called()


def test_empty_fts_is_healthy(service, monkeypatch):
    monkeypatch.setattr(module.queries, "full_text_search", AsyncMock(return_value=[]))
    assert asyncio.run(service.search("revenue growth")).lexical_available


def test_failures_propagate_and_input_checked_before_paid_call(service, monkeypatch):
    for query in ("   ", "x" * 8192):
        with pytest.raises(ValueError):
            asyncio.run(service.search(query))
    module.embed_query.assert_not_called()
    monkeypatch.setattr(
        module.queries,
        "semantic_search",
        AsyncMock(side_effect=RuntimeError("DB unavailable")),
    )
    with pytest.raises(RuntimeError):
        asyncio.run(service.search("revenue growth"))


def test_comparison_prepares_once_and_limits_concurrency(service, monkeypatch):
    active = maximum = 0

    async def target_search(*args, **kwargs):
        nonlocal active, maximum
        active += 1
        maximum = max(maximum, active)
        await asyncio.sleep(0.01)
        active -= 1
        return module.RetrievalResult()

    monkeypatch.setattr(service, "_search_prepared", target_search)
    targets = [
        SearchFilters(ticker="AAPL", corpus_years=[year]) for year in range(2021, 2026)
    ]
    result = asyncio.run(
        service.compare(
            "Compare Apple's revenue across these five years", targets=targets
        )
    )
    assert [r.target for r in result.targets] == targets
    assert all(not r.result.passages for r in result.targets)
    assert maximum == 2 and result.usage.embedding_tokens == 8
    assert module.embed_query.await_count == module.extract_keywords.await_count == 1


def test_read_chunk_and_radius_bound(service, monkeypatch):
    monkeypatch.setattr(module.queries, "get_chunks", AsyncMock(return_value=[]))
    assert asyncio.run(service.read_chunk(UUID(int=999))) is None
    with pytest.raises(ValueError):
        asyncio.run(service.read_surrounding_chunks(UUID(int=1), radius=100))
