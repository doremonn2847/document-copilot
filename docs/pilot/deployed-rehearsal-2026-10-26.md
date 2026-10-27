# Deployed pilot rehearsal — 2026-10-26

Status: **complete — eight questions, one attempt each, concurrency 1**.
Executed 2026-10-26 after fresh owner approval; no manual retries or extra
questions were submitted. No application or deployment settings were changed.
Target: https://frontend-production-e3f9.up.railway.app.

This is an agent-run functional/evidence rehearsal of the Copilot tasks in
[pilot-plan.md](pilot-plan.md), not the human baseline or one-week stand-in pilot.
No manual timings, weekly savings, human acceptance or phase-10 completion may be
inferred. Preserve the time-log/issue-log example rows. Agent observations belong
here, separate from owner timing data. Owner baseline questions are not submitted.

## Preconditions and authorization

- Owner signed in; the hosted app shows the authenticated new-chat screen.
- Fresh bounded authorization granted for all eight questions under the limits
  below. Previous allowances remain separate and consumed.
- Use new rehearsal chats under the signed-in approved account. Successful turns
  write chat history/citations and may generate titles; keep them for traceability.
- No direct SQL checks, account changes, production configuration changes, load
  tests, backup/restore, deployments, dependencies or application edits.
- Existing modified `docs/evaluations/retrieval-results.md` is outside this task.

## Proposed batch and deployed limits

At most **8 questions**, submitted sequentially once each, concurrency **1**,
with no manual Retry/resubmission or additional follow-ups. The questions below
are the six C variants and two separate trust checks; M variants are excluded.

Read-only Railway configuration inspection and the current code show these
per-question upper bounds (not expected consumption or a dollar-price guarantee):

| Role | Maximum logical calls per question | Output cap per call |
| --- | ---: | ---: |
| Answering/planning/numeric selection, shared budget | 20 | 4,000 tokens |
| Grounding/numeric verification, conservative upper bound | 6 | 2,000 tokens |
| Keyword extraction, up to four retrieval preparations | 8 | 150 tokens |
| Query embeddings | 4 | One bounded question per request, 1,536 dimensions |
| Conversational routing | 2 | 1,500 tokens |
| Title generation for a new chat | 1 | 40 tokens |

Answer deadline: 120 seconds per question; title timeout: 15 seconds. The running
service retains one automatic HTTP retry for retrieval requests (keywords and
embeddings); other model clients have zero HTTP retries. Built-in typed-output
validation and at most one grounding repair remain inside the limits above.
The rehearsal does not change deployed behavior just to lower its request caps.

For all eight questions, the maxima are 160 answer/selection calls, 48 judge
calls, 64 keyword calls, 32 embedding requests, 16 routing calls and 8 title calls,
before the existing one-HTTP-retry allowance on retrieval. Actual calls are
expected to be fewer but must be reported as observed or unavailable, never
invented. A smaller two-question first batch can be authorized instead.

## Questions and acceptance

| ID | Exact question | Required evidence / expected behavior | Status |
| --- | --- | --- | --- |
| P1-C | In Microsoft's 2023 corpus 10-K, what does Microsoft 365 Consumer offer subscribers? Cite two source-supported offerings. | Two distinct offerings, exact quotes, correct company/filing and source locations. | incomplete |
| P2-C | In Amazon's 2024 corpus 10-K, identify two disclosed risks affecting fulfillment/delivery operations. Cite the supporting passages. | Two actual disclosed risks; preserve section/period attribution; no invented occurrence or trend. | pass |
| P3-C | What International-segment net sales does Amazon's 2024 corpus 10-K report for 2024 and 2023? Cite the scale, currency and column labels. | Correct segment/row/amounts/units/year headers, or explicit gaps. Gaps are incomplete task coverage, not a full task pass. | pass_with_citation_limitation |
| P4-C | What do Microsoft's 2022 and 2024 corpus 10-Ks say LinkedIn provides? Cite one supported statement from each filing. | Separate attributable statements per filing, or visible period gaps; no unsupported trend. | incomplete |
| P5-C | In the 2024 corpus 10-Ks, what cloud services do Amazon AWS and Google Cloud describe? Cite one supported fact per company. | Both companies' own evidence with correct attribution; no unsupported ranking. | incomplete |
| P6-C | What is the ratio of Microsoft's reported gross-margin increase to reported revenue increase, as a percentage, for fiscal 2024 compared with fiscal 2023? Use the consolidated narrative increases, not gross-margin rate. | Exact comparison heading and both narrative amounts/units/scope; verify 100 * numerator / denominator with Decimal and stated rounding. | pass |
| T1 | What revenue does Tesla's 2028 filing report? | Explicit unsupported-corpus response without invented figures or substituted company/year. | pass |
| T2 | Do these filings prove generative AI caused higher margins? | Preserve causal limitation; any included facts require their own sources. | pass |

## Execution and evidence recording

For each authorized question, record the chat URL, submission/completion timestamps,
observed latency, displayed answer/status, cited company/filing/period/page/chunk,
exact quote support, original source URL and gaps. Preserve screenshots. Inspect
only rehearsal chats; do not export unrelated conversation history or credentials.
Use the existing local source corpus where useful to check quotes and arithmetic;
no extra paid evaluation model is required. Model usage may be read from bounded,
sanely sanitized service logs; if unavailable, report it unavailable.

Record UI progress and persistence for rehearsal turns without re-generating.
An accepted claim contradicted by its own source stops the batch immediately:
preserve it and report the blocker; no prompt/code fix or paid rerun is authorized.
A truthful missing-evidence response is recorded as incomplete. Stop after two
service failures rather than consume the rest of the allowance on a broken path.

Once outputs are shown to the owner, treat these rehearsed tasks as familiar when
considering later human timing comparisons. Agent latency is not a human baseline
or complete analyst task time. No current human pilot start date is assumed.

## Results

Owner sign-in and paid-batch approval confirmed. Completed observations follow.

### Completion summary

The six research tasks yielded **two full passes** (P2, P6), **one correct numeric
answer with a citation-context limitation** (P3), and **three incomplete tasks**
(P1, P4, P5). Both separate trust checks passed. All eight turns completed without
a service failure; no accepted claim contradicting its cited source was observed
in this review. These are agent judgments on this small sample, not an accuracy
percentage for the corpus or a hallucination-free guarantee.

| Task | Review outcome | Backend turn time (s) | Generator / judge calls | Saved chat |
| --- | --- | ---: | ---: | --- |
| P1-C | incomplete | 31.13 | 4 / 1 | [Open](https://frontend-production-e3f9.up.railway.app/chats/8f92db55-4ff9-4184-97a0-203cb6d996ad) |
| P2-C | pass | 62.94 | 4 / 1 | [Open](https://frontend-production-e3f9.up.railway.app/chats/1d16f77f-f00e-4eaa-9881-c8764da1b9d7) |
| P3-C | pass_with_citation_limitation | 18.94 | 3 / 1 | [Open](https://frontend-production-e3f9.up.railway.app/chats/bdf52f1f-49cf-4a3a-b549-9acbc7ecc274) |
| P4-C | incomplete | 20.02 | 3 / 2 | [Open](https://frontend-production-e3f9.up.railway.app/chats/90a3eec8-ebc5-492d-bbf3-ed61ea39481f) |
| P5-C | incomplete | 22 | 3 / 2 | [Open](https://frontend-production-e3f9.up.railway.app/chats/d53d7491-237c-4138-81f3-d654890c6651) |
| P6-C | pass | 38.11 | 6 / 1 | [Open](https://frontend-production-e3f9.up.railway.app/chats/d0abd51b-640a-4fbd-a9cc-29ae405092d4) |
| T1 | pass | 7.41 | 2 / 0 | [Open](https://frontend-production-e3f9.up.railway.app/chats/6b27c758-a882-4870-95dc-f4e36a999ea5) |
| T2 | pass | 41.12 | 4 / 4 | [Open](https://frontend-production-e3f9.up.railway.app/chats/23dbc2dc-9c02-42cc-8212-1b133b37e7f8) |

### Evidence reviews

- **P1-C:** Both claims match the cited Office Consumer category description, but neither establishes two Microsoft 365 Consumer subscriber offerings.
- **P2-C:** Two disclosed risks are supported: constrained labor affects fulfillment staffing/costs; shipping/transportation difficulties can harm operating results and customer experience. Third reliance statement is also directly quoted.
- **P3-C:** 2023 $131,200 million and 2024 $142,906 million match the original International net-sales row and year headers. Displayed citation excerpts omit the International section label and the full Year Ended December 31 heading; original source context supplies them.
- **P4-C:** 2024 monetized-solutions claim is supported. No verified statement for 2022; original 2022 Markdown contains a LinkedIn product paragraph, so this is retrieval/selection coverage loss rather than corpus absence. One gap label spans both years despite its text addressing 2022.
- **P5-C:** Company/year attribution and quotes are correct, but the reply reports revenue-table line items instead of describing either company’s cloud services. It does not complete the requested comparison or declare that aspect missing.
- **P6-C:** Citations establish FY2024-vs-FY2023 consolidated gross-margin increase of $25.0 billion and revenue increase of $33.2 billion. Independent Decimal calculation gives 75.30% to two decimals, matching the displayed result. Raw inputs are in source cards rather than repeated inline.
- **T1:** Explicitly reports no indexed TSLA/2028 passage and unverified revenue, with no invented figure, replacement company/year, or fabricated citation.
- **T2:** Preserves the causal limitation: forward-looking AI monetization/margin language is not presented as proof AI caused higher margins. Two factual paraphrases match their GOOGL 2025 quotes; a third quote notes lower margins for channels/newer products, without being recast as causal proof.

Local original Markdown confirms the P2 risk passages are in Item 1A, the P3
International net-sales row is $131,200 million (2023) and $142,906 million (2024),
and P6 uses $25.0 billion / $33.2 billion * 100 = **75.30%** to two decimals.
P4's 2022 LinkedIn product description and P5's AWS/Google Cloud service prose
exist in the original Markdown despite incomplete replies; this is evidence of
retrieval/selection coverage loss, not absence of documents. No fix was attempted.

Original SEC URLs, exact displayed excerpts, filing/corpus/fiscal labels and
page/chunk metadata were inspected in the source cards. External SEC pages were
not independently fetched in this rehearsal. P3's excerpts omit the International
section label and full table period heading; local table context establishes
those labels, making it a citation-completeness/usability limitation.

### History, artifacts and measured-usage limits

A direct route reload of P1 confirmed its saved question, both claims and source
card. The other seven chats were not individually reloaded. All eight displayed
completed answers and have retained chat links; successful backend completion is
separate from task relevance. No chats were deleted or unrelated history exported.
Screenshots are cropped to the answer area, excluding the unrelated sidebar.

Ignored local evidence under `data/chunks/assistant/`:

- `pilot-rehearsal-runs-20261026.json`: questions, UI-observed answers/excerpts,
  timestamps, reviews and the representative history check.
- `pilot-rehearsal-usage-20261026.json`: sanitized per-turn server metadata.
- `pilot-P1-C-20261026.png` through `pilot-P6-C-20261026.png`,
  `pilot-T1-20261026.png`, `pilot-T2-20261026.png`: answer/source evidence.

Server logs cover **8/8** rehearsal turns; observed elapsed times range from **7.41 to 62.94 seconds**. These are backend turn durations, not complete analyst task time or a service-level guarantee.

- generator: 29 calls; 205,539 input tokens; 2,915 output tokens.
- grounding: 12 calls; 35,916 input tokens; 1,809 output tokens.

Routing, title generation, keywords, embeddings and retrieval HTTP-retry usage
are not separately exposed in these turn logs. They remain **unavailable**, not
zero. Reported token totals therefore exclude those roles; no exact dollar cost
is claimed. All observed generator/judge request counts are within the approved
limits. There were exactly eight question submissions and no paid rerun.

### Pilot interpretation

This is a completed **agent-run deployed rehearsal**, not the one-week human
stand-in pilot. No baseline or pilot time-log rows were added and example CSV
rows remain examples. No weekly time saving or three-hour target result can be
computed. Human pilot status remains **not started / no result** until the owner
confirms dates and supplies actual timed tasks. Treat rehearsed answers as
familiar for later timing comparisons; do not count agent runs as human use.

Recommended follow-up is narrowly scoped relevance/coverage work on P1/P4/P5
and citation context on P3, after owner prioritization. Preserve the accepted
phase-9 provisional closure and deferred backups/capacity; this test does not
authorize prompt, retrieval, grounding, architecture or application changes.
