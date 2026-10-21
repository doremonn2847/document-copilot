# Hybrid retrieval

This implements local checklist batch 5 / reference phase 5. It does not generate
answers or change the existing stubbed chat flow. No migration, re-embedding, or
additional dependency is required.

## Flow

1. Embed the full question and prepare keywords concurrently. Questions longer
   than five whitespace-separated words use a typed PydanticAI agent with
   `gpt-4o-mini`. It returns 3–5 words with one validation retry and at most two
   model requests. Filtered company aliases and years are removed deterministically;
   product names remain. Short queries go directly to Postgres parsing.
2. Search pgvector cosine distance and English full-text search in parallel.
   Each worker owns a read-only psycopg connection with a 10-second statement
   timeout. Both searches enforce identical filters and require completed filings,
   matching embedding model/dimensions, and non-null vectors.
3. Fuse the two ranked ID lists with RRF: sum `1 / (60 + rank)`. Retrieve 50
   candidates per branch, return 10 primary passages, resolve ties by UUID, and
   count each ID once per branch. RRF scores are not confidence probabilities.
4. Hydrate passages and attach up to one adjacent chunk on either side, within
   the same document. Neighbors are deduplicated against primary passages and
   one another. Source URLs, accession numbers, dates, and chunk IDs stay intact.

`DocumentRetriever(settings)` is an async context manager. Its async methods are
`search(query, filters=..., top_k=..., include_neighbors=...)`,
`compare(query, targets=...)`, `read_chunk(chunk_id)`, and
`read_surrounding_chunks(chunk_id, radius=1)`. An injected `AsyncOpenAI` client
remains owned by the caller; otherwise the retriever closes its own client.

Comparisons prepare the question once and retrieve three primary passages for
each of up to 25 explicit targets, with two target searches active at a time.
Results preserve input target order and empty targets. Target passage counts are
coverage diagnostics, not proof that the evidence answers the question.

## Settings and failures

All configuration comes from `app.config.Settings`; see `backend/.env.example`.
The indexed model is `text-embedding-3-small` with 1536 dimensions. Retrieval
rejects a different configuration before making API calls. Questions must be
nonempty and at most 8191 UTF-8 bytes, a conservative embedding-token guard.
The FTS language stays `english`, matching the generated database vectors.

Keyword extraction failure returns semantic results with `lexical_available=false`
and an explicit warning. Known keyword usage is retained even on validation
failure. A healthy FTS query with zero matches keeps `lexical_available=true`.
Embedding and database failures propagate; CLI errors print only the exception
type, never raw provider/connection payloads.

FTS matches passages containing at least two keywords (all of them when fewer
than two are searchable) and ranks by how many keywords match, then
`ts_rank_cd`. ANDing every word returned nothing for questions such as "AI"
when passages say "artificial intelligence". Inspect branch rankings before
changing prompts or adding query planning.
There is no arbitrary relevance threshold; grounding belongs to phase 6.

`corpus_years` filters use stored folder-year metadata. `fiscal_years` filters
use only the source's fiscal-year column. The current corpus has unverified
fiscal years, so those filters return no matches with a warning. Filing dates
and corpus years are never relabeled as fiscal years. Original pages and
extraction quality remain deferred per the owner's tutorial scope decision.

Formatted passages have 800-character excerpts and a 12,000-character total
limit with truncation labels. Structured JSON retains full source text and all
branch IDs so evidence can be inspected without relying on truncated excerpts.

## Run from backend/

```powershell
uv run python -m scripts.smoke_retrieval --question "What cloud services does Microsoft Azure offer to customers?" --ticker MSFT --corpus-years 2025 --output ../data/chunks/retrieval/azure-lookup.json
uv run python -m scripts.smoke_retrieval --question "Compare Apple's revenue mix across the available filings" --target AAPL:2021 --target AAPL:2022 --target AAPL:2023 --target AAPL:2024 --target AAPL:2025 --output ../data/chunks/retrieval/apple-comparison.json
uv run python -m scripts.smoke_retrieval --cases ../docs/evaluations/retrieval-cases.json --json --output ../data/chunks/retrieval/client-questions.json
uv run pytest -m "not integration" --tb=no
uv run pytest tests/retrieval/test_integration.py -m integration --tb=no
```

Live commands incur query-embedding/keyword-generation usage, but never call an
answering model or write corpus data. JSON exposes semantic-only, FTS-only, and
fused rankings for the same prepared question; comparison-level usage is counted
once, rather than once per target. Do not publish private prompts or credentials
in evaluation artifacts. The current source filings are public SEC documents.

## References and phase 6 handoff

- [Cookbook hybrid retrieval](https://github.com/daveebbelaar/ai-cookbook/tree/84748d7a076c2ef3ab751435e80bf419b1c9ca61/knowledge/hybrid-retrieval): complementary search branches, RRF, inspectable evaluation.
- [Reference Postgres retrieval](https://github.com/daveebbelaar/document-copilot/tree/d41888da21e03fec2dbb17b9961bef9b67622588/backend/app/retrieval): keyword preparation, bounded ranked passages, neighbors.
- [PydanticAI dependencies](https://ai.pydantic.dev/dependencies/) and [typed output](https://ai.pydantic.dev/output/); installed 2.54 uses `retries={"output": 1, "tools": 0}` and `result.usage`.

Phase 6 will put this retriever in request-scoped agent dependencies, register
bounded search/read tools, track the passages actually supplied to the agent,
validate grounding/citations, and connect generation to chat streaming. That
work and cross-encoder reranking are intentionally not part of this phase.
