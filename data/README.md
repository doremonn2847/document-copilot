# Data

Local data artifacts for development live here.

- `downloads/` holds raw source files fetched from SEC EDGAR, grouped by year.
- Downloaded payloads are gitignored because the corpus can get large.
- Fetch a sample corpus with `uv run data/download.py` 

## Convert HTML to Markdown

Docling is a development dependency of the backend's uv environment. From
`backend/`, run:

```powershell
uv run python ../data/convert.py
```

The script converts every `.htm` below `data/downloads/` into UTF-8 Markdown
under `data/markdown/`, preserving year folders and filenames. Existing outputs
are skipped; use `--overwrite` to regenerate them. Generated Markdown is ignored
by Git. Source metadata remains in `downloads/manifest.json`; filenames link
each conversion to its source filing.

This is extraction only: no embeddings or database writes. Review financial
tables and source citation locations before chunking. HTML conversion does not
guarantee original printed page numbers or preserve every HTML anchor.
The initial Apple table spot-check retained year labels, figures, and footnotes,
but expanded merged HTML cells into repeated Markdown columns. Table cleanup
and accuracy review remain separate ingestion tasks.

References: [Docling quickstart](https://docling-project.github.io/docling/getting_started/quickstart/)
and [supported formats](https://docling-project.github.io/docling/usage/supported_formats/).

## Preview chunks locally

From `backend/`, with development dependencies installed (`uv sync`):

```powershell
uv run python -m ingest.preview --file ../data/markdown/2025/aapl_10-k_2025-10-31_0000320193-25-000079.md
```

This writes `data/chunks/<accession>.jsonl` without embedding requests or database
writes. Each record includes raw text, contextualized embedding input, exact
token count, source metadata, and stable IDs. `INGESTION_CHUNK_TOKENS` defaults
to 1024, including heading context. Original page locations remain unverified.
The owner reviewed one prose chunk and accepted imperfect extraction for this
tutorial. Table cleanup and verified citation locations are deferred.

## Run the reviewed single-chunk trial

From `backend/`, after reviewing the local preview:

```powershell
uv run python -m ingest.trial --file ../data/markdown/2025/aapl_10-k_2025-10-31_0000320193-25-000079.md --chunk 11
```

This sends only the selected chunk to OpenAI and atomically stores its source
and vector in Supabase. It checks read-back content, full-text matching for
`international trade` in this reviewed sample, and vector self-search. Matching
reruns reuse the saved embedding; changed source/config/content is rejected.
The source remains incomplete (`ingested_at` null), with unverified fiscal year,
section and page left null. No full-filing or corpus ingestion is performed.

There are no automatic API retries. If embedding succeeds but saving fails,
that request can still be billed; a later manual retry may embed again. Durable
embedding progress is deferred to the full-filing stage. Errors print only their
type so driver/SDK messages cannot reveal credentials.

## Ingest a complete filing or the corpus

From `backend/`:

```powershell
uv run python -m ingest.filing --all --preview-only
uv run python -m ingest.filing --file ../data/markdown/2025/aapl_10-k_2025-10-31_0000320193-25-000079.md
uv run python -m ingest.filing --all
```

The preview command is free of API/database calls. Ingestion uses 32-chunk
batches, up to two SDK retries with backoff, and saves embeddings atomically to
ignored `data/chunks/*.embeddings.json` before committing each database batch.
Rerun the same command to reuse saved rows/cache after interruption. Changed
source, content, model, or chunk settings are rejected; automatic refresh or
deletion is deliberately unsupported. Keep these local caches until ingestion
is verified. A crash between API success and cache saving may still require a
paid retry; resumability is not an exactly-once billing guarantee.

`ingested_at` means all preview chunks passed storage checks, not that extraction
is perfect. Fiscal year and page remain null unless verified; corpus folder year
is retained separately in chunk metadata. Source URLs remain available.
The original single-chunk trial is superseded after completing its filing.
