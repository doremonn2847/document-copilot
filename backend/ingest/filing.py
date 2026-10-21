"""Ingest one unchanged Markdown filing with bounded batches and resumable progress."""

import argparse
import hashlib
import json
from pathlib import Path

import psycopg
from openai import OpenAI, OpenAIError
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from ingest.preview import DATA, chunk_records, load_filing
from ingest.trial import require_match, validate_preview, validate_vector


def write_json(path: Path, value) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
    temporary.replace(path)


def fingerprint(row: dict) -> str:
    return hashlib.sha256(json.dumps(row, sort_keys=True).encode()).hexdigest()


def check_saved(saved: dict, row: dict) -> None:
    expected = {
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
    require_match(
        {**saved, "id": str(saved["id"]), "document_id": str(saved["document_id"])},
        expected,
    )
    require_match(saved["chunk_metadata"], row["metadata"])
    validate_vector(json.loads(saved["vector_text"]))


def response_vectors(response, size: int) -> list[list[float]]:
    if sorted(item.index for item in response.data) != list(range(size)):
        raise ValueError("Embedding response indices do not match batch")
    vectors = [item.embedding for item in sorted(response.data, key=lambda x: x.index)]
    for vector in vectors:
        validate_vector(vector)
    return vectors


def load_preview(path: Path, filing: dict, settings) -> list[dict]:
    target = DATA / "chunks" / f"{filing['accession_number']}.jsonl"
    if target.exists():
        rows = [
            json.loads(line) for line in target.read_text(encoding="utf-8").splitlines()
        ]
    else:
        from docling.datamodel.base_models import InputFormat
        from docling.document_converter import DocumentConverter

        document = (
            DocumentConverter(allowed_formats=[InputFormat.MD]).convert(path).document
        )
        rows = chunk_records(
            document,
            filing,
            settings.openai_embedding_model,
            settings.openai_embedding_dimensions,
            settings.ingestion_chunk_tokens,
        )
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_suffix(".jsonl.tmp")
        temporary.write_text(
            "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
            encoding="utf-8",
        )
        temporary.replace(target)
    if not rows or [r["chunk_index"] for r in rows] != list(range(len(rows))):
        raise ValueError("Preview must contain consecutive ordered chunks")
    for row in rows:
        validate_preview(row, filing, settings)
    return rows


def ingest_file(path: Path, settings) -> dict:
    filing = load_filing(path)
    rows = load_preview(path, filing, settings)
    print(
        json.dumps(
            {
                "filing": path.name,
                "chunks": len(rows),
                "tokens": sum(r["token_count"] for r in rows),
            }
        ),
        flush=True,
    )
    cache_path = DATA / "chunks" / f"{filing['accession_number']}.embeddings.json"
    cache = (
        json.loads(cache_path.read_text(encoding="utf-8"))
        if cache_path.exists()
        else {}
    )
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
        markdown_content=path.read_text(encoding="utf-8"),
        fiscal_year=None,
    )
    requests = tokens = 0
    with psycopg.connect(
        str(settings.database_url),
        connect_timeout=10,
        autocommit=True,
        row_factory=dict_row,
    ) as conn:
        conn.execute("SET statement_timeout = '30s'")
        if (
            conn.execute(
                "SELECT format_type(atttypid, atttypmod) AS type FROM pg_attribute WHERE attrelid = 'document_chunks'::regclass AND attname = 'embedding'"
            ).fetchone()["type"]
            != "vector(1536)"
        ):
            raise ValueError("Database vector dimensions differ")
        if not conn.execute(
            "SELECT pg_try_advisory_lock(hashtextextended(%s, 0)) AS locked",
            (source["accession_number"],),
        ).fetchone()["locked"]:
            raise ValueError("Another ingestion for this filing is running")
        saved_source = conn.execute(
            "SELECT * FROM source_documents WHERE accession_number = %s",
            (source["accession_number"],),
        ).fetchone()
        if saved_source:
            require_match(
                {
                    **saved_source,
                    "id": str(saved_source["id"]),
                    "filing_date": str(saved_source["filing_date"]),
                    "report_date": str(saved_source["report_date"]),
                },
                source,
            )
        existing = conn.execute(
            "SELECT *, embedding::text AS vector_text FROM document_chunks WHERE document_id = %s ORDER BY chunk_index",
            (source["id"],),
        ).fetchall()
        by_index = {row["chunk_index"]: row for row in existing}
        if set(by_index) - set(range(len(rows))):
            raise ValueError("Stored chunks exceed preview; explicit refresh required")
        for row in rows:
            if row["chunk_index"] in by_index:
                check_saved(by_index[row["chunk_index"]], row)
            if row["id"] in cache:
                require_match(cache[row["id"]], {"fingerprint": fingerprint(row)})
                validate_vector(cache[row["id"]]["vector"])
        if not saved_source:
            conn.execute(
                "INSERT INTO source_documents (id,ticker,cik,form,filing_date,report_date,fiscal_year,accession_number,primary_document,source_url,markdown_content) VALUES (%(id)s,%(ticker)s,%(cik)s,%(form)s,%(filing_date)s,%(report_date)s,%(fiscal_year)s,%(accession_number)s,%(primary_document)s,%(source_url)s,%(markdown_content)s)",
                source,
            )
        missing = [row for row in rows if row["chunk_index"] not in by_index]
        if missing:
            conn.execute(
                "UPDATE source_documents SET ingested_at = NULL WHERE id = %s",
                (source["id"],),
            )
        # At most 32 * 8191 tokens per request, below the aggregate input limit.
        with OpenAI(
            api_key=settings.openai_api_key.get_secret_value(),
            max_retries=2,
            timeout=60,
        ) as client:
            for start in range(0, len(missing), 32):
                batch = missing[start : start + 32]
                uncached = [r for r in batch if r["id"] not in cache]
                if uncached:
                    response = client.embeddings.create(
                        model=settings.openai_embedding_model,
                        dimensions=1536,
                        input=[r["embedding_text"] for r in uncached],
                        encoding_format="float",
                    )
                    vectors = response_vectors(response, len(uncached))
                    requests += 1
                    tokens += response.usage.total_tokens
                    for row, vector in zip(uncached, vectors, strict=True):
                        cache[row["id"]] = {
                            "fingerprint": fingerprint(row),
                            "vector": vector,
                            "batch_usage_tokens": response.usage.total_tokens,
                            "batch_id": uncached[0]["id"],
                        }
                    write_json(cache_path, cache)
                with conn.transaction():
                    for row in batch:
                        cached = cache[row["id"]]
                        conn.execute(
                            "INSERT INTO document_chunks (id,document_id,chunk_index,page,section,text,token_count,chunk_metadata,embedding) VALUES (%(id)s,%(document_id)s,%(chunk_index)s,%(page)s,%(section)s,%(text)s,%(token_count)s,%(chunk_metadata)s,%(embedding)s::vector)",
                            {
                                **row,
                                "chunk_metadata": Jsonb(
                                    {
                                        **row["metadata"],
                                        "trial": False,
                                        "embedding_batch_id": cached["batch_id"],
                                        "embedding_batch_usage_tokens": cached[
                                            "batch_usage_tokens"
                                        ],
                                    }
                                ),
                                "embedding": json.dumps(cached["vector"]),
                            },
                        )
                print(
                    f"Saved {min(start + 32, len(missing))}/{len(missing)} missing chunks",
                    flush=True,
                )
        stored = conn.execute(
            "SELECT *, embedding::text AS vector_text, search_vector::text AS search_text FROM document_chunks WHERE document_id = %s ORDER BY chunk_index",
            (source["id"],),
        ).fetchall()
        if len(stored) != len(rows):
            raise ValueError("Final chunk count mismatch")
        for saved, row in zip(stored, rows, strict=True):
            check_saved(saved, row)
            if saved["search_text"] is None:
                raise ValueError("Missing generated full-text vector")
        with conn.transaction():
            conn.execute(
                "UPDATE document_chunks SET chunk_metadata = chunk_metadata || '{\"trial\": false}'::jsonb WHERE document_id = %s AND chunk_metadata->>'trial' = 'true'",
                (source["id"],),
            )
            conn.execute(
                "UPDATE source_documents SET ingested_at = COALESCE(ingested_at, now()) WHERE id = %s",
                (source["id"],),
            )
    result = {
        "filing": path.name,
        "chunks": len(rows),
        "reused": len(existing),
        "embedding_batches": requests,
        "api_usage_tokens": tokens,
        "complete": True,
    }
    print(json.dumps(result), flush=True)
    return result


def main() -> None:
    from app.config import settings

    parser = argparse.ArgumentParser(description=__doc__)
    selection = parser.add_mutually_exclusive_group(required=True)
    selection.add_argument("--file", type=Path)
    selection.add_argument(
        "--all", action="store_true", help="Process all local Markdown filings"
    )
    parser.add_argument(
        "--preview-only",
        action="store_true",
        help="Validate all chunk previews without API or database calls",
    )
    args = parser.parse_args()
    paths = sorted((DATA / "markdown").glob("*/*.md")) if args.all else [args.file]
    if not paths:
        raise ValueError("No Markdown filings found")
    summaries = []
    for path in paths:
        if args.preview_only:
            rows = load_preview(path, load_filing(path), settings)
            result = {
                "filing": path.name,
                "chunks": len(rows),
                "tokens": sum(row["token_count"] for row in rows),
            }
            print(json.dumps(result), flush=True)
        else:
            result = ingest_file(path, settings)
        summaries.append(result)
    write_json(
        DATA
        / "chunks"
        / ("preview-summary.json" if args.preview_only else "ingestion-summary.json"),
        summaries,
    )


if __name__ == "__main__":
    try:
        main()
    except (
        psycopg.Error,
        OpenAIError,
        ValueError,
        OSError,
        KeyError,
        TypeError,
    ) as error:
        raise SystemExit(
            f"Ingestion failed ({type(error).__name__}); saved batches can be resumed. Raw error suppressed."
        ) from None
