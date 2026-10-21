"""Embed and persist exactly one reviewed preview chunk; reruns reuse matching data."""

import argparse
import hashlib
import json
import math
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

import psycopg
import tiktoken
from openai import OpenAI, OpenAIError
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from ingest.preview import DATA, load_filing


def validate_preview(row: dict, filing: dict, settings) -> None:
    meta = row["metadata"]
    expected = {
        "source_sha256": filing["source_sha256"],
        "accession_number": filing["accession_number"],
        "source_url": filing["source_url"],
        "ticker": filing["ticker"],
        "form": filing["form"],
        "corpus_year": filing["corpus_year"],
        "model": settings.openai_embedding_model,
        "dimensions": settings.openai_embedding_dimensions,
        "max_tokens": settings.ingestion_chunk_tokens,
        "tokenizer": "cl100k_base",
        "embedding_input_sha256": hashlib.sha256(
            row["embedding_text"].encode()
        ).hexdigest(),
    }
    if any(meta.get(k) != v for k, v in expected.items()):
        raise ValueError(
            "Preview no longer matches source or settings; regenerate and review"
        )
    count = len(
        tiktoken.get_encoding("cl100k_base").encode(
            row["embedding_text"], disallowed_special=()
        )
    )
    if (
        not row["text"].strip()
        or not 0 < count <= settings.ingestion_chunk_tokens
        or count != row["token_count"]
    ):
        raise ValueError("Invalid preview text or token count")
    if row["document_id"] != filing["document_id"] or row["id"] != str(
        uuid5(NAMESPACE_URL, filing["document_id"] + f":chunk:{row['chunk_index']}")
    ):
        raise ValueError("Invalid preview IDs")
    if meta["model"] != "text-embedding-3-small" or meta["dimensions"] != 1536:
        raise ValueError("Trial requires text-embedding-3-small and 1536 dimensions")


def validate_vector(vector: list[float]) -> None:
    if (
        len(vector) != 1536
        or not all(math.isfinite(x) for x in vector)
        or not any(vector)
    ):
        raise ValueError("Embedding must contain 1536 finite values and be nonzero")


def require_match(actual: dict, expected: dict) -> None:
    if any(actual.get(key) != value for key, value in expected.items()):
        raise ValueError(
            "Persisted trial differs from preview; refusing overwrite or paid retry"
        )


def embed(row: dict, settings) -> tuple[list[float], int]:
    with OpenAI(
        api_key=settings.openai_api_key.get_secret_value(), max_retries=0, timeout=30
    ) as client:
        response = client.embeddings.create(
            model=settings.openai_embedding_model,
            dimensions=1536,
            input=[row["embedding_text"]],
            encoding_format="float",
        )
    if len(response.data) != 1 or response.data[0].index != 0:
        raise ValueError("Unexpected embedding response")
    vector = response.data[0].embedding
    validate_vector(vector)
    return vector, response.usage.total_tokens


def persist_trial(conn, source: dict, chunk: dict, row: dict, settings) -> dict:
    # Session lock spans the paid call without holding a database transaction open.
    locked = conn.execute(
        "SELECT pg_try_advisory_lock(hashtextextended(%s, 0)) AS locked",
        (source["accession_number"],),
    ).fetchone()["locked"]
    if not locked:
        raise ValueError("Another trial for this filing is running")
    existing_source = conn.execute(
        "SELECT * FROM source_documents WHERE accession_number = %s",
        (source["accession_number"],),
    ).fetchone()
    existing_chunk = conn.execute(
        "SELECT *, embedding::text AS vector_text FROM document_chunks WHERE document_id = %s AND chunk_index = %s",
        (source["id"], chunk["chunk_index"]),
    ).fetchone()
    if existing_source:
        comparable = {
            **existing_source,
            "id": str(existing_source["id"]),
            "filing_date": str(existing_source["filing_date"]),
            "report_date": str(existing_source["report_date"]),
        }
        require_match(comparable, source)
    if existing_chunk:
        comparable = {
            **existing_chunk,
            "id": str(existing_chunk["id"]),
            "document_id": str(existing_chunk["document_id"]),
        }
        require_match(
            comparable, {k: v for k, v in chunk.items() if k != "chunk_metadata"}
        )
        require_match(existing_chunk["chunk_metadata"], chunk["chunk_metadata"])
        validate_vector(json.loads(existing_chunk["vector_text"]))
        return {"reused": True, "embedding_requests": 0, "billed_tokens_this_run": 0}
    if existing_source:
        raise ValueError(
            "Existing source has no matching trial chunk; refusing partial overwrite"
        )

    vector, usage = embed(row, settings)
    metadata = {**chunk["chunk_metadata"], "embedding_usage_tokens": usage}
    with conn.transaction():
        conn.execute(
            "INSERT INTO source_documents (id,ticker,cik,form,filing_date,report_date,fiscal_year,accession_number,primary_document,source_url,markdown_content,ingested_at) VALUES (%(id)s,%(ticker)s,%(cik)s,%(form)s,%(filing_date)s,%(report_date)s,%(fiscal_year)s,%(accession_number)s,%(primary_document)s,%(source_url)s,%(markdown_content)s,%(ingested_at)s)",
            source,
        )
        conn.execute(
            "INSERT INTO document_chunks (id,document_id,chunk_index,page,section,text,token_count,chunk_metadata,embedding) VALUES (%(id)s,%(document_id)s,%(chunk_index)s,%(page)s,%(section)s,%(text)s,%(token_count)s,%(chunk_metadata)s,%(embedding)s::vector)",
            {
                **chunk,
                "chunk_metadata": Jsonb(metadata),
                "embedding": json.dumps(vector),
            },
        )
    return {"reused": False, "embedding_requests": 1, "billed_tokens_this_run": usage}


def verify_trial(conn, source: dict, chunk: dict) -> dict:
    stored_source = conn.execute(
        "SELECT * FROM source_documents WHERE id = %s", (source["id"],)
    ).fetchone()
    require_match(
        {
            **stored_source,
            "id": str(stored_source["id"]),
            "filing_date": str(stored_source["filing_date"]),
            "report_date": str(stored_source["report_date"]),
        },
        source,
    )
    saved = conn.execute(
        "SELECT *, embedding::text AS vector_text, vector_dims(embedding) AS dimensions, search_vector @@ plainto_tsquery('english', 'international trade') AS text_match FROM document_chunks WHERE id = %s",
        (chunk["id"],),
    ).fetchone()
    require_match(
        {**saved, "id": str(saved["id"]), "document_id": str(saved["document_id"])},
        {k: v for k, v in chunk.items() if k != "chunk_metadata"},
    )
    require_match(saved["chunk_metadata"], chunk["chunk_metadata"])
    validate_vector(json.loads(saved["vector_text"]))
    nearest = conn.execute(
        "SELECT id, embedding <=> %s::vector AS distance FROM document_chunks WHERE embedding IS NOT NULL ORDER BY embedding <=> %s::vector LIMIT 1",
        (saved["vector_text"], saved["vector_text"]),
    ).fetchone()
    counts = conn.execute(
        "SELECT (SELECT count(*) FROM source_documents WHERE id = %s) AS sources, (SELECT count(*) FROM document_chunks WHERE document_id = %s) AS chunks, (SELECT ingested_at IS NULL FROM source_documents WHERE id = %s) AS incomplete",
        (source["id"], source["id"], source["id"]),
    ).fetchone()
    if (
        saved["dimensions"] != 1536
        or not saved["text_match"]
        or str(nearest["id"]) != chunk["id"]
        or abs(nearest["distance"]) > 1e-5
        or counts != {"sources": 1, "chunks": 1, "incomplete": True}
    ):
        raise ValueError("Trial search/count verification failed")
    return {
        **counts,
        "dimensions": saved["dimensions"],
        "full_text_match": True,
        "self_cosine_distance": nearest["distance"],
    }


def main() -> None:
    from app.config import settings

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--file", type=Path, required=True)
    parser.add_argument("--chunk", type=int, required=True)
    args = parser.parse_args()
    filing = load_filing(args.file)
    rows = [
        json.loads(line)
        for line in (DATA / "chunks" / f"{filing['accession_number']}.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    ]
    matches = [r for r in rows if r["chunk_index"] == args.chunk]
    if len(matches) != 1:
        raise ValueError("Select exactly one existing preview chunk")
    row = matches[0]
    validate_preview(row, filing, settings)
    source = {
        k: filing[k]
        for k in (
            "ticker",
            "cik",
            "form",
            "filing_date",
            "report_date",
            "accession_number",
            "primary_document",
            "source_url",
        )
    }
    source.update(
        id=filing["document_id"],
        markdown_content=args.file.read_text(encoding="utf-8"),
        fiscal_year=None,
        ingested_at=None,
    )
    chunk = {
        k: row[k]
        for k in (
            "id",
            "document_id",
            "chunk_index",
            "page",
            "section",
            "text",
            "token_count",
        )
    }
    chunk["chunk_metadata"] = {**row["metadata"], "trial": True}
    with psycopg.connect(
        str(settings.database_url),
        connect_timeout=10,
        autocommit=True,
        row_factory=dict_row,
    ) as conn:
        conn.execute("SET statement_timeout = '15s'")
        column = conn.execute(
            "SELECT format_type(atttypid, atttypmod) AS type FROM pg_attribute WHERE attrelid = 'document_chunks'::regclass AND attname = 'embedding'"
        ).fetchone()
        if column["type"] != "vector(1536)":
            raise ValueError("Database embedding dimensions do not match")
        result = persist_trial(conn, source, chunk, row, settings)
        verification = verify_trial(conn, source, chunk)
    print(json.dumps({"chunk_index": args.chunk, **result, **verification}))


if __name__ == "__main__":
    try:
        main()
    except (psycopg.Error, OpenAIError, ValueError, OSError, KeyError, TypeError) as error:
        # Driver and SDK errors can contain connection secrets; never print their payload.
        raise SystemExit(
            f"Trial failed ({type(error).__name__}); no automatic paid retry. Inspect safely."
        ) from None
