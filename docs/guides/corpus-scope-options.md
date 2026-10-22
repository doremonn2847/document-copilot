# Corpus scope options for the pilot

The brief's corpus is SEC 10-K and 10-Q filings for S&P 500 companies,
2020–2025. Today's corpus is 25 10-Ks: Apple, Amazon, Alphabet, Microsoft
and NVIDIA, corpus years 2021–2025. Phase 8 requires either the full scope
or explicit client agreement to a reduced pilot scope. This note sizes the
options so the owner and client can decide.

## Measured on the current corpus (2026-10-22)

| Measure | Value |
|---|---:|
| Filings | 25 10-Ks |
| Chunks per filing (median) | 220 (mean 216; 5,396 total) |
| Embedded tokens per filing (median) | 194,076 (4.75M total) |
| Database: chunk table | 103 MB (≈4.1 MB per filing, vectors and indexes included) |
| Database: whole project | 119 MB |
| Docling conversion time per filing | not recorded in phase 4; measure on a sample before committing |

## Full brief scope, estimated

Assumptions, stated so they can be corrected: about 500 companies; six annual
reports each (2020–2025) and three 10-Qs per year (18 each); a 10-Q is about
40% of a 10-K's text.

| Item | 10-Ks | 10-Qs | Total |
|---|---:|---:|---:|
| Filings | 3,000 | 9,000 | ~12,000 |
| Embedded tokens | ~570M | ~690M | **~1.3B** |
| Chunks | ~660k | ~790k | **~1.45M** |
| Chunk table (at 4.1 MB per 10-K equivalent) | ~12 GB | ~15 GB | **~27 GB** |

What that means:

- **Embedding spend is small:** ~1.3B tokens at text-embedding-3-small's list
  price ($0.02 per 1M tokens at the time of writing) is roughly **$25–30**.
- **The database is the real cost.** ~27 GB of vectors and text, plus an HNSW
  index that should fit in memory, is far beyond a free or entry Supabase
  project (the current project is 119 MB). Expect a paid plan with a larger
  compute size and disk; check Supabase's current pricing for ~30 GB and the
  RAM the index needs.
- **Conversion time is unknown and probably the longest step.** Docling turns
  each HTML filing into Markdown on the local machine; at 12,000 filings even
  one minute each is ~200 hours of compute. Measure five filings first.
- **SEC access:** EDGAR asks for an identifying User-Agent with a real contact
  (the downloader still has a placeholder) and at most 10 requests per second.
- **Retrieval quality at scale is untested.** Company and year filters keep
  searches scoped, but table-heavy facts (regional revenue, segment tables)
  are already hard to retrieve because Docling dropped most section headings.

## Options

| Option | Scope | Cost and effort | Fit for the pilot |
|---|---|---|---|
| **A. Pilot on the current corpus** | 5 companies, 10-K, 2021–2025 | None; ready now | Good if the five pilot analysts' work is mostly about these companies. Needs the client's written agreement (brief: "any reduced pilot scope needs explicit client agreement"). |
| **B. Pilot coverage list** | The ~20–50 companies the five analysts actually cover, 10-K and 10-Q | Days of conversion; ~1–3 GB database; embeddings a few dollars | Best evidence for the 3-hours-saved target: analysts test it on their real work. |
| **C. Full brief scope** | ~500 companies, 10-K and 10-Q, 2020–2025 | Weeks of conversion, ~27 GB database on a paid plan, ingestion and retrieval tuning at scale | Needed for firm-wide rollout, not for a one-week pilot. |

## Recommendation

**B, with A as the fallback.** Ask the pilot analysts for their coverage list
and pilot on those companies' 10-Ks and 10-Qs; the time-saved measurement then
reflects their real work. If the list cannot be ready in time, run the pilot
on A with the client's written agreement, and use the pilot's `out_of_scope`
time-log entries to size B or C for rollout.

Before any expansion: set a real SEC User-Agent in `data/download.py`, time
Docling on five filings, and decide whether section-heading recovery should be
fixed first (it limits table-heavy answers today).
