"""Read-only psycopg operations; every worker owns its connection."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING
from uuid import UUID

import psycopg
from psycopg.rows import dict_row
from starlette.concurrency import run_in_threadpool

from app.retrieval.table_context import original_table_context
from app.retrieval.types import RankedChunkHit, RetrievedPassage, SearchFilters

if TYPE_CHECKING:
    from app.config import Settings


PASSAGE_COLUMNS = """
    c.id AS chunk_id, c.document_id, c.chunk_index, c.text, c.page, c.section,
    d.ticker, d.form, d.accession_number, d.source_url, d.filing_date,
    d.report_date, d.fiscal_year, c.chunk_metadata->>'corpus_year' AS corpus_year,
    c.chunk_metadata,
    CASE WHEN c.chunk_metadata->'item_types' @> '["table"]'::jsonb
        THEN d.markdown_content END AS source_markdown
"""
FROM_CHUNKS = "FROM public.document_chunks c JOIN public.source_documents d ON d.id = c.document_id"


def hydrate_passages(rows: list[dict]) -> list[RetrievedPassage]:
    return [
        RetrievedPassage(
            **{
                key: value
                for key, value in row.items()
                if key not in {"chunk_metadata", "source_markdown", "source_context"}
            },
            source_context=original_table_context(
                row.get("source_markdown"), row.get("chunk_metadata", {}), row["text"]
            ),
        )
        for row in rows
    ]


def fetch_rows(settings: Settings, sql: str, params: dict) -> list[dict]:
    with psycopg.connect(
        str(settings.database_url), connect_timeout=10, row_factory=dict_row
    ) as connection:
        connection.execute("SET TRANSACTION READ ONLY")
        connection.execute("SET LOCAL statement_timeout = '10s'")
        return connection.execute(sql, params).fetchall()


def build_filters(
    settings: Settings, filters: SearchFilters | None
) -> tuple[str, dict]:
    clauses = [
        "d.ingested_at IS NOT NULL",
        "c.embedding IS NOT NULL",
        "c.chunk_metadata->>'model' = %(model)s",
        "c.chunk_metadata->>'dimensions' = %(dimensions)s",
        "vector_dims(c.embedding) = %(vector_dimensions)s",
    ]
    params = {
        "model": settings.openai_embedding_model,
        "dimensions": str(settings.openai_embedding_dimensions),
        "vector_dimensions": settings.openai_embedding_dimensions,
    }
    if filters:
        for field, clause in (
            ("ticker", "d.ticker = %(ticker)s"),
            ("form", "d.form = %(form)s"),
            ("fiscal_years", "d.fiscal_year = ANY(%(fiscal_years)s)"),
            (
                "corpus_years",
                "c.chunk_metadata->>'corpus_year' = ANY(%(corpus_years)s)",
            ),
        ):
            value = getattr(filters, field)
            if value is not None:
                clauses.append(clause)
                params[field] = (
                    [str(year) for year in value] if field == "corpus_years" else value
                )
    return " AND ".join(clauses), params


async def semantic_search(
    settings: Settings, vector: list[float], filters: SearchFilters | None, limit: int
) -> list[RankedChunkHit]:
    where, params = build_filters(settings, filters)
    sql = f"SELECT c.id AS chunk_id, 1 - (c.embedding <=> %(vector)s::vector) AS score {FROM_CHUNKS} WHERE {where} ORDER BY c.embedding <=> %(vector)s::vector, c.id LIMIT %(limit)s"
    rows = await run_in_threadpool(
        fetch_rows,
        settings,
        sql,
        {**params, "vector": json.dumps(vector), "limit": limit},
    )
    return [RankedChunkHit(**row, rank=rank) for rank, row in enumerate(rows, 1)]


async def full_text_search(
    settings: Settings, text: str, filters: SearchFilters | None, limit: int
) -> list[RankedChunkHit]:
    where, params = build_filters(settings, filters)
    # ANDing every keyword returned nothing when one word was absent ("AI" in
    # passages that say "artificial intelligence"). Match any two keywords and
    # rank by how many match, so full matches still come first.
    sql = (
        f"SELECT c.id AS chunk_id, ts_rank_cd(c.search_vector, q.query) AS score {FROM_CHUNKS} "
        "CROSS JOIN (SELECT array_agg(term) AS terms, string_agg('(' || term::text || ')', ' | ')::tsquery AS query "
        "FROM unnest(%(words)s::text[]) AS w, plainto_tsquery(%(config)s::regconfig, w) AS term WHERE numnode(term) > 0) AS q "
        "CROSS JOIN LATERAL (SELECT count(*) AS matched FROM unnest(q.terms) AS term WHERE c.search_vector @@ term) AS m "
        f"WHERE {where} AND c.search_vector @@ q.query AND m.matched >= least(2, cardinality(q.terms)) "
        "ORDER BY m.matched DESC, score DESC, c.id LIMIT %(limit)s"
    )
    rows = await run_in_threadpool(
        fetch_rows,
        settings,
        sql,
        {
            **params,
            "config": settings.retrieval_fts_config,
            "words": text.split(),
            "limit": limit,
        },
    )
    return [RankedChunkHit(**row, rank=rank) for rank, row in enumerate(rows, 1)]


async def get_chunks(
    settings: Settings, ids: list[UUID], filters: SearchFilters | None = None
) -> list[RetrievedPassage]:
    if not ids:
        return []
    where, params = build_filters(settings, filters)
    rows = await run_in_threadpool(
        fetch_rows,
        settings,
        f"SELECT {PASSAGE_COLUMNS} {FROM_CHUNKS} WHERE {where} AND c.id = ANY(%(ids)s::uuid[])",
        {**params, "ids": ids},
    )
    return await run_in_threadpool(hydrate_passages, rows)


async def get_neighbors(
    settings: Settings, anchors: list[RetrievedPassage], radius: int
) -> list[RetrievedPassage]:
    if not anchors or radius == 0:
        return []
    pairs = sorted(
        {
            (anchor.document_id, anchor.chunk_index + delta)
            for anchor in anchors
            for delta in range(-radius, radius + 1)
            if delta != 0 and anchor.chunk_index + delta >= 0
        }
    )
    where, params = build_filters(settings, None)
    sql = f"SELECT {PASSAGE_COLUMNS} {FROM_CHUNKS} JOIN unnest(%(documents)s::uuid[], %(indices)s::int[]) AS wanted(document_id, chunk_index) ON c.document_id = wanted.document_id AND c.chunk_index = wanted.chunk_index WHERE {where} ORDER BY c.document_id, c.chunk_index"
    rows = await run_in_threadpool(
        fetch_rows,
        settings,
        sql,
        {
            **params,
            "documents": [pair[0] for pair in pairs],
            "indices": [pair[1] for pair in pairs],
        },
    )
    return await run_in_threadpool(hydrate_passages, rows)
