import asyncio
from uuid import UUID

from app.retrieval import queries
from app.retrieval.types import SearchFilters


def test_both_searches_bind_identical_filters(config, monkeypatch):
    calls = []

    def fetch(settings, sql, params):
        calls.append((sql, params))
        return [{"chunk_id": UUID(int=1), "score": 0.5}]

    monkeypatch.setattr(queries, "fetch_rows", fetch)
    filters = SearchFilters(
        ticker="AAPL", corpus_years=[2025], fiscal_years=[2024], form="10-K"
    )

    async def run():
        semantic, lexical = await asyncio.gather(
            queries.semantic_search(config, [0.1] * 1536, filters, 50),
            queries.full_text_search(
                config, "revenue'; DROP TABLE users;--", filters, 50
            ),
        )
        assert semantic[0].rank == lexical[0].rank == 1

    asyncio.run(run())
    for sql, params in calls:
        assert "DROP TABLE" not in sql and "AAPL" not in sql
        assert "ingested_at IS NOT NULL" in sql
        assert (
            "chunk_metadata->>'model'" in sql and "chunk_metadata->>'dimensions'" in sql
        )
        assert params["ticker"] == "AAPL" and params["corpus_years"] == ["2025"]
        assert params["fiscal_years"] == [2024] and params["limit"] == 50
        assert "d.fiscal_year = ANY" in sql
    assert "<=>" in calls[0][0] or "<=>" in calls[1][0]
    assert any("plainto_tsquery" in sql and "ts_rank_cd" in sql for sql, _ in calls)
    # Keywords are bound as data, one array item per word, never spliced into SQL.
    assert [p["words"] for _, p in calls if "words" in p] == [
        ["revenue';", "DROP", "TABLE", "users;--"]
    ]


def test_each_fetch_owns_readonly_connection(config, monkeypatch):
    from unittest.mock import MagicMock

    connect = MagicMock()
    connection = connect.return_value.__enter__.return_value
    connection.execute.return_value.fetchall.return_value = []
    monkeypatch.setattr(queries.psycopg, "connect", connect)
    queries.fetch_rows(config, "SELECT 1", {})
    queries.fetch_rows(config, "SELECT 2", {})
    assert connect.call_count == 2
    assert connection.execute.call_args_list[0].args[0] == "SET TRANSACTION READ ONLY"


def test_neighbor_targets_use_document_and_position(config, monkeypatch):
    from test_contracts import passage

    calls = []
    monkeypatch.setattr(
        queries,
        "fetch_rows",
        lambda settings, sql, params: calls.append((sql, params)) or [],
    )
    asyncio.run(queries.get_neighbors(config, [passage()], 1))
    sql, params = calls[0]
    assert "c.document_id = wanted.document_id" in sql
    assert "c.chunk_index = wanted.chunk_index" in sql
    assert params["indices"] == [0, 2]
