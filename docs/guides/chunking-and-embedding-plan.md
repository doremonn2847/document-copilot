# Chunking and embedding plan

Status (2026-10-18): tutorial corpus ingestion completed and verified. All 25
filings are complete, containing 5,396 chunks and 4,754,092 embedding input
tokens. This includes the original 840-token trial and Apple pilot. At the
previously checked $0.02 per million embedding tokens, estimated corpus cost is
$0.095; this is an estimate, not a billing-dashboard reconciliation.

Database audit: zero missing embeddings, wrong vector dimensions, missing
full-text vectors, missing required metadata, duplicate positions, or ordering
gaps. Maximum contextualized input: 1,017 tokens. A full corpus rerun reused all
5,396 chunks with paid API calls blocked and never attempted. Original trial
chunk 11 was reused and its trial marker cleared when Apple completed.

Three additional semantic-search questions returned relevant Apple tariff,
Microsoft Azure, and NVIDIA CUDA passages, filtered by company and corpus
folder year. Query embeddings used 28 tokens; the earlier Apple smoke used 33.
These checks do not implement the application retrieval layer or prove answer
quality. Local evidence: `data/chunks/corpus-audit.json`,
`ingestion-first-run-summary.json`, `ingestion-summary.json`, and
`corpus-retrieval-smoke.json` (all under ignored `data/chunks/`).

Apple 2025 preview: 164 chunks, 143,077 contextualized tokens, maximum 1,017
tokens. The converter recovered no recognized headings; section/page remain
null. Financial tables retain duplicated columns. The owner explicitly deferred
extraction cleanup to focus on the tutorial pipeline; these are documented
limitations, not ingestion blockers. Selected review artifact:
`data/chunks/selected-chunk.md` (chunk index 11, 840 tokens).

Offline verification: 69 tests passed, including conflict rejection before a
paid call, matching-rerun reuse, single-input requests, and invalid vectors.
The exact final-input token guard remains enforced. Full-filing ingestion now
uses batches of 32, atomic local embedding caches, per-batch database commits,
and up to two SDK retries for transient API failures. Apple 2025 completed with
164 chunks; a repeat used zero API tokens. Three question-based vector searches
returned relevant tariff, net-sales, and service passages. This is a smoke check,
not a comprehensive retrieval evaluation.

## Scope and decisions

Start with one local Markdown filing, preview its chunks, then embed and upload
exactly one reviewed chunk. Prove the database round trip and rerun behavior
before processing one complete filing or all 25 filings.

- Input: existing `data/markdown/<year>/*.md`, linked by filename to
  `data/downloads/manifest.json`. Do not repeat the HTML-to-Markdown batch.
- Code: a one-off CLI under `backend/ingest/`, using the backend uv environment
  and central `app.config.settings`.
- Generated artifacts: `data/chunks/`, ignored by Git. No generated corpus data
  under `backend/`.
- Embedding model: the configured `openai_embedding_model`, currently defaulting
  to `text-embedding-3-small`; dimensions default to 1536, matching the migrated
  `vector(1536)` column. Validate actual settings before any paid request.
- Initial retrieval chunk budget: **1024 tokens**, including the contextualized
  text sent for embedding. This is a starting choice to evaluate, not a claim
  that 1024 is optimal for financial tables.
- OpenAI documents an 8192-token input ceiling for this model. Use a conservative
  8191-token hard guard and the smaller 1024-token chunk budget. Count tokens,
  not characters; reject empty or oversized embedding inputs before requesting.
- Use `tiktoken` with the documented `cl100k_base` encoding via Docling's
  `OpenAITokenizer`. Check the installed dependency first; explicitly declare
  the tokenizer dependency if our ingestion code imports it directly.

## Docling approach

Native Docling chunkers accept a `DoclingDocument`, not a plain Markdown string.
Parse the selected existing Markdown through `DocumentConverter` restricted to
`InputFormat.MD`. Inspect the resulting headings and tables before chunking.

`HierarchicalChunker` groups document elements with their headings and captions.
`HybridChunker` builds on that hierarchical approach, splits oversized chunks,
and optionally merges adjacent chunks sharing headings/captions. Use
`HybridChunker` for production output with an OpenAI tokenizer and
`merge_peers=True`; use the hierarchical output only for inspection/comparison.
Do not independently chunk both outputs and upload both sets.

Use `chunker.contextualize(chunk)` for embedding input and recount that exact
string after serialization. Keep table header repetition enabled; do not
silently drop headers or truncate values to resolve overflow.
For Docling fragments that remain oversized, recursively split raw text near
whitespace, repeat contextual headings, and enforce the exact token limit. A
test verifies that concatenating the raw pieces reproduces the original text.
Do not add arbitrary overlap in the first trial: preserve structural context
and repeated table headers, then evaluate whether overlap is actually needed.

Markdown re-import cannot recover original HTML anchors, page labels, or layout
provenance lost during export. Never treat a synthetic Docling page as an actual
filing page. Leave `page` null unless mapped to a verified original page label.
For the pilot, retain Markdown item references, headings, source URL, and source
checksum. These support debugging but do not satisfy the final page-citation
requirement. Source-location mapping is deferred by the owner for this tutorial.

The converted Apple tables contain repeated columns from merged HTML cells.
The owner accepts embedding these as-is for the tutorial. Passing ingestion
checks does not establish extraction accuracy or reliable financial answers.

## Implementation order

1. **Preflight and CLI.** Add preview and explicit single-chunk upload modes,
   requiring one selected Markdown file. Confirm its manifest entry, settings,
   embedding dimensions, and backend development dependencies. Output only safe
   identifiers and counts; never log credentials or raw driver exceptions.
   Preview mode must work without contacting OpenAI or the database.
2. **Metadata mapping.** Map ticker, CIK, form, report/filing dates, accession,
   primary document, and SEC URL from the manifest. Derive fiscal year from the
   corpus's validated fiscal-year mapping, not the filing date: January-ending
   fiscal years and filings submitted the following year need special care.
3. **Local preview of one filing.** Parse Markdown into a DoclingDocument;
   inspect hierarchical structure and generate hybrid chunks. Save a JSONL
   preview under `data/chunks/` with raw text, contextualized embedding text,
   exact token count, index, headings, item references, and source metadata.
   Inspect a short prose chunk first and a known revenue table separately.
4. **Offline tests.** Cover manifest mapping, fiscal-year handling, token limits
   including contextual prefixes, empty input rejection, preserved table
   headers/units, deterministic IDs, and conflicting reruns. Mock OpenAI and DB
   at the service boundary. Use a small Docling fixture, not the entire corpus.
5. **Review one chunk.** Show its source, raw text, embedding input, token count,
   model, dimensions, and expected database fields. The owner reviews this
   concrete preview before the one-chunk paid/upload trial.
6. **Embed exactly one chunk.** Make one embeddings request with the configured
   model and explicit dimensions. Check the returned vector has 1536 finite
   values; record actual usage. Do not embed all chunks to obtain a sample.
7. **Upload and verify.** Use the existing backend database connection settings
   and SQL driver to write the source row and selected chunk atomically, then
   read them back. Keep paid calls outside the database transaction.
8. **Rerun the same trial.** Check existing persisted content/config before
   calling OpenAI. Unchanged trial rows should be reused without another paid
   embedding request or duplicate rows.
9. **One full filing.** Only after the trial passes, preview the filing's complete
   chunk count and total embedding tokens, then embed in bounded batches with
   retry/backoff and durable progress. Check tables and citation mapping again.
10. **Full corpus.** After reviewing the one-filing result and token estimate,
    explicitly expand to all 25 filings. Verify per-filing counts, missing
    embeddings, metadata, full-text vectors, and selected source passages.

## Existing database mapping

No new tables are needed for the trial.

| Table/field | Value |
| --- | --- |
| `source_documents.id` | Stable UUID derived from accession number |
| `source_documents` filing fields | Validated manifest metadata |
| `source_documents.markdown_content` | Selected filing's existing Markdown |
| `source_documents.ingested_at` | Null during a partial one-chunk trial; set only after complete filing ingestion |
| `document_chunks.id` | Stable UUID derived from document ID and chunk index |
| `document_chunks.document_id` | Source document foreign key |
| `document_chunks.chunk_index` | Deterministic index in the selected chunking output |
| `document_chunks.text` | Raw chunk passage, without added contextual headings |
| `document_chunks.section` | Verified heading path from the parsed document |
| `document_chunks.page` | Verified original page label, otherwise null |
| `document_chunks.embedding` | Vector for the contextualized embedding input |
| `document_chunks.token_count` | Token count of the exact embedding input |
| `document_chunks.chunk_metadata` | Source/input hash, contextualized input hash, model/dimensions, tokenizer, chunk budget, Docling version, headings/item references, corpus year/ticker/form, and trial status |
| `document_chunks.search_vector` | Generated automatically from `text`; never supplied manually |

The unique accession and `(document_id, chunk_index)` constraints support
idempotency. Stable IDs alone are insufficient: compare source hashes and
chunking/model settings before reusing an embedding. Fail clearly on changed
inputs/config for this initial version. Do not silently overwrite old chunks,
mix embedding models, delete cited chunks, or mark a partial filing complete.
Design an explicit refresh path before the later re-chunking milestone.

## One-chunk acceptance gate

- Exactly one source row and one selected chunk are persisted for the trial.
- Read-back content, document link, section, token count, and metadata match the
  reviewed preview; the vector has 1536 finite values.
- Postgres `vector_dims(embedding)` returns 1536.
- Generated `search_vector` is populated, and a known phrase from this chunk
  matches an English full-text query.
- A cosine-distance query using the saved vector returns the saved chunk near
  itself, proving storage/search plumbing. This is not a retrieval-quality test.
- Repeating unchanged input/config produces no duplicate rows and no extra
  embedding call.
- The source remains visibly incomplete, and no other filings are processed.

## Cost and execution gates

Parsing and chunking here are local CPU work; OpenAI embeddings are paid per
input token. Estimate from the exact contextualized inputs, using current
official pricing at execution time, and record actual API usage. Later batches
must obey both per-input and aggregate request limits. Never interpret a local
preview as permission to run the full corpus.

The owner approved the single-chunk trial and then authorized proceeding with
one filing, retrieval checks, and the remaining corpus using unchanged text.
No extraction cleanup or invented page/fiscal-year labels are required.

## Sources

- [Docling chunking concepts](https://docling-project.github.io/docling/concepts/chunking/):
  native document input, hierarchical structure, hybrid splitting/merging,
  contextualization, and table-header handling.
- Installed Docling Core's `transforms/chunker/tokenizer/openai.py` and
  `hybrid_chunker.py`: verified the OpenAI tokenizer adapter and current API.
- [Official OpenAI embeddings guide](https://platform.openai.com/docs/guides/embeddings):
  model dimensions, input limits, and `cl100k_base` tokenization.
- Repo models: `backend/app/database/models/source_document.py` and
  `document_chunk.py`; configuration: `backend/app/config.py`.
