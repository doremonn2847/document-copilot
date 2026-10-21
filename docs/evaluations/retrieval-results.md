# Retrieval evaluation worksheet

Run: 2026-10-18. Query embeddings and typed keywords only; no answer generation.

Offline suite: **89 passed**. Marked live retrieval checks: **6 passed**. Independent code review: no important findings.

This is a diagnostic worksheet, not labeled ground truth. Candidate coverage does not prove relevance or answer sufficiency. Semantic-only and FTS-only top IDs, fused scores, full passages, neighbors, warnings, usage and timings are in the ignored `data/chunks/retrieval/client-questions.json` report. No NDCG/recall improvement is claimed.

Owner review (2026-10-18): the owner accepted this complete ten-question
retrieval worksheet, in addition to the Azure lookup and Apple comparison in
[the evidence review](retrieval-evidence-review.md). Phase-5 evidence review is
complete. Individual relevance labels were not separately annotated, so this
acceptance does not create labeled benchmark data or establish answer accuracy.

| Case | Company/corpus-year targets | Targets with candidates | Targets with FTS hits | Keyword status | First candidate ID (not a relevance label) |
|---|---:|---:|---:|---|---|
| Q01 | 5 | 5 | 0 | available | `e07394d9-91c8-56c8-a052-04e872148029` |
| Q02 | 5 | 5 | 5 | available | `5d03afc4-dd75-57d2-b274-e29c4d247535` |
| Q03 | 5 | 5 | 0 | available | `651f0018-b0c9-5cca-83d5-ed2de106503b` |
| Q04 | 5 | 5 | 3 | available | `d3a4a724-5e36-5436-8466-9fa53dabcffa` |
| Q05 | 5 | 5 | 5 | available | `618f878e-f4a5-51b1-95a3-06b95a6b33ef` |
| Q06 | 25 | 25 | 6 | available | `51e88006-f965-516a-9ead-09be67844319` |
| Q07 | 10 | 10 | 8 | available | `a1bf6952-b82f-5072-99d7-c839a42d3ef6` |
| Q08 | 20 | 20 | 17 | available | `e6c900da-c437-5b57-9299-7c4861d2bc20` |
| Q09 | 5 | 5 | 0 | available | `2f11a8dd-73d2-5551-a514-990f5a437d3a` |
| Q10 | 25 | 25 | 0 | available | `91b34bcd-769c-5c70-bc86-c607e7881577` |

## Observations and known limitations

- Matching passages were returned for every requested target. This confirms filter/group plumbing, not that every question facet is covered.
- Broad AND-based lexical queries still have zero hits for some targets. A successful empty lexical branch is distinct from failed keyword extraction; both are visible in the report.
- Existing tables contain repeated labels and values; the owner accepted these extraction limits. Units and periods still require checking before a financial answer can be trusted.
- Three primary passages per target can miss facets of complex questions (for example AWS income, North America losses, and calculated margins). This phase exposes candidates; it does not invent the missing comparison.
- AI-risk and causal-margin questions require careful evidence judgments; vector similarity alone cannot establish an effect on margins. Refusal/claim validation remains phase 6.
- Fiscal years and original page locations remain unverified. Corpus-year filters are explicitly labeled and are not fiscal-year substitutes.

Recorded usage for this final ten-case run: `{"embedding_tokens": 349, "keyword_input_tokens": 5712, "keyword_output_tokens": 419, "keyword_requests": 10}`. It excludes separate integration checks and earlier diagnostic runs.

## Questions and relevance judgments

### Q01

Across Apple's 2021–2025 10-Ks, how did the revenue mix between iPhone, Services, Mac, iPad, and Wearables change, and which category appears to have contributed most to any mix shift?

Explicit targets: AAPL:2021, AAPL:2022, AAPL:2023, AAPL:2024, AAPL:2025.

- Relevant chunk IDs: not separately annotated; candidate IDs are retained in the JSON report.
- Missing evidence / noise: inspect the separate branch rankings and the full passage text; do not judge solely from clipped excerpts.
- Owner acceptance: accepted.

### Q02

For Amazon, compare AWS operating income and margin against North America and International from 2021–2025. In which years did AWS appear to fund losses or weaker profitability elsewhere?

Explicit targets: AMZN:2021, AMZN:2022, AMZN:2023, AMZN:2024, AMZN:2025.

- Relevant chunk IDs: not separately annotated; candidate IDs are retained in the JSON report.
- Missing evidence / noise: inspect the separate branch rankings and the full passage text; do not judge solely from clipped excerpts.
- Owner acceptance: accepted.

### Q03

How did NVIDIA describe demand drivers, customer concentration, and supply constraints for its Data Center business from fiscal 2021 through fiscal 2025?

Explicit targets: NVDA:2021, NVDA:2022, NVDA:2023, NVDA:2024, NVDA:2025.

- Relevant chunk IDs: not separately annotated; candidate IDs are retained in the JSON report.
- Missing evidence / noise: inspect the separate branch rankings and the full passage text; do not judge solely from clipped excerpts.
- Owner acceptance: accepted.

### Q04

Across Microsoft's 2021–2025 filings, what changed in the way the company describes Azure, AI infrastructure, and cloud capacity constraints?

Explicit targets: MSFT:2021, MSFT:2022, MSFT:2023, MSFT:2024, MSFT:2025.

- Relevant chunk IDs: not separately annotated; candidate IDs are retained in the JSON report.
- Missing evidence / noise: inspect the separate branch rankings and the full passage text; do not judge solely from clipped excerpts.
- Owner acceptance: accepted.

### Q05

For Alphabet, how did Google Search, YouTube ads, Google Network, subscriptions/platforms/devices, and Google Cloud revenue trends differ across the available 10-Ks?

Explicit targets: GOOGL:2021, GOOGL:2022, GOOGL:2023, GOOGL:2024, GOOGL:2025.

- Relevant chunk IDs: not separately annotated; candidate IDs are retained in the JSON report.
- Missing evidence / noise: inspect the separate branch rankings and the full passage text; do not judge solely from clipped excerpts.
- Owner acceptance: accepted.

### Q06

Which of the five companies added, removed, or materially changed risk-factor language related to AI, cloud infrastructure, export controls, supply chain concentration, or regulation between 2021 and 2025?

Explicit targets: AAPL:2021, AAPL:2022, AAPL:2023, AAPL:2024, AAPL:2025, AMZN:2021, AMZN:2022, AMZN:2023, AMZN:2024, AMZN:2025, NVDA:2021, NVDA:2022, NVDA:2023, NVDA:2024, NVDA:2025, MSFT:2021, MSFT:2022, MSFT:2023, MSFT:2024, MSFT:2025, GOOGL:2021, GOOGL:2022, GOOGL:2023, GOOGL:2024, GOOGL:2025.

- Relevant chunk IDs: not separately annotated; candidate IDs are retained in the JSON report.
- Missing evidence / noise: inspect the separate branch rankings and the full passage text; do not judge solely from clipped excerpts.
- Owner acceptance: accepted.

### Q07

For Apple and NVIDIA, what do the filings say about supplier concentration or dependence on third-party manufacturing, and did the wording become more or less urgent over time?

Explicit targets: AAPL:2021, AAPL:2022, AAPL:2023, AAPL:2024, AAPL:2025, NVDA:2021, NVDA:2022, NVDA:2023, NVDA:2024, NVDA:2025.

- Relevant chunk IDs: not separately annotated; candidate IDs are retained in the JSON report.
- Missing evidence / noise: inspect the separate branch rankings and the full passage text; do not judge solely from clipped excerpts.
- Owner acceptance: accepted.

### Q08

Compare capital expenditures and purchase commitments for Microsoft, Alphabet, Amazon, and NVIDIA. What do the filings imply about the scale and timing of AI/cloud infrastructure investment?

Explicit targets: MSFT:2021, MSFT:2022, MSFT:2023, MSFT:2024, MSFT:2025, GOOGL:2021, GOOGL:2022, GOOGL:2023, GOOGL:2024, GOOGL:2025, AMZN:2021, AMZN:2022, AMZN:2023, AMZN:2024, AMZN:2025, NVDA:2021, NVDA:2022, NVDA:2023, NVDA:2024, NVDA:2025.

- Relevant chunk IDs: not separately annotated; candidate IDs are retained in the JSON report.
- Missing evidence / noise: inspect the separate branch rankings and the full passage text; do not judge solely from clipped excerpts.
- Owner acceptance: accepted.

### Q09

For each company, summarize the most important geographic revenue exposures disclosed in the latest 10-K, then identify any year-over-year changes that could matter to an analyst.

Explicit targets: AAPL:2025, AMZN:2025, NVDA:2025, MSFT:2025, GOOGL:2025.

- Relevant chunk IDs: not separately annotated; candidate IDs are retained in the JSON report.
- Missing evidence / noise: inspect the separate branch rankings and the full passage text; do not judge solely from clipped excerpts.
- Owner acceptance: accepted.

### Q10

If an analyst asks whether the filings prove that generative AI improved margins for any of these companies, what evidence exists in the corpus, and where should the bot refuse to infer beyond the filings?

Explicit targets: AAPL:2021, AAPL:2022, AAPL:2023, AAPL:2024, AAPL:2025, AMZN:2021, AMZN:2022, AMZN:2023, AMZN:2024, AMZN:2025, NVDA:2021, NVDA:2022, NVDA:2023, NVDA:2024, NVDA:2025, MSFT:2021, MSFT:2022, MSFT:2023, MSFT:2024, MSFT:2025, GOOGL:2021, GOOGL:2022, GOOGL:2023, GOOGL:2024, GOOGL:2025.

- Relevant chunk IDs: not separately annotated; candidate IDs are retained in the JSON report.
- Missing evidence / noise: inspect the separate branch rankings and the full passage text; do not judge solely from clipped excerpts.
- Owner acceptance: accepted.
