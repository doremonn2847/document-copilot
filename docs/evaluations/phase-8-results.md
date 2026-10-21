# Phase 8 results: answer quality on the client brief

Runs: night of 2026-10-22, production settings (gpt-5.4-mini answering,
gpt-4.1-mini judging, gpt-4o-mini keywords, text-embedding-3-small) through the
capped driver `data/chunks/assistant/capped_question.py`. Per-run artifacts
(`autopilot-p8-*.json`, gitignored) hold searches, judge payloads, requests and
timings. An answer is marked correct only after each claim was read against its
own quotes.

## Credential exposure (task 5)

- Production frontend build (`vite build` to a scratch directory): no OpenAI
  keys, Supabase secret keys, Postgres URLs, service-role JWTs or server
  variable names. The only Supabase key is the public publishable key, which
  `src/lib/env.ts` already rejects if it is a secret or legacy service key.
- 150 local backend logs and run artifacts: no OpenAI keys, Supabase secrets,
  Postgres URLs, bearer tokens or JWTs. Backend code does not log request
  headers, keys or connection strings.
- Not covered: logs of the deployed Railway services (phase 9).

## Client example questions (task 1), first pass

Questions Q01–Q10 from `retrieval-cases.json`, one run each (01:32–01:39).
The batch runner passed "2021–2025" through a cp1252 pipe, so the model saw a
stray control character instead of the dash in Q01, Q02, Q04 and Q06; reruns
use UTF-8. Requests are per run (answering / judging / keywords / embedding).

| Case | Result | Requests | Seconds | Accuracy against quotes | Coverage |
|---|---|---|---:|---|---|
| Q01 Apple revenue mix | accepted | 3/1/1/1 | 29 | Correct: iPhone and Mac figures match the first (current-year) table column; narrative drivers match. | Thin: iPhone/Mac for 2023–2025 only; mix shift reported as not established. |
| Q02 AWS vs segments | accepted | 3/2/1/1 | 33 | Correct but trivial: claims only say each filing has a segment table. | None of the requested amounts. Table rows were never citable (see below). |
| Q03 NVIDIA Data Center | **failed** | 8/0/2/2 | 34 | — | Two claims kept failing structural checks; the whole answer was refused. |
| Q04 Microsoft Azure/AI | accepted | 2/1/1/1 | 22 | Correct: four claims match their quotes word for word. | Partial: nothing on capacity constraints; 2022 uncovered; change over time reported as not established. |
| Q05 Alphabet revenue lines | accepted | 3/1/1/1 | 23 | One claim names YouTube ads but its five quotes cover only the Search bullet (judge accepted). | Thin: the revenue-table claim was withheld for missing units; trends not established. |
| Q06 risk-factor changes | **failed** | 3/1/1/1 | 62 | — | 25-target comparison exposed one citable span; the only claim was judged unsupported. |
| Q07 Apple/NVIDIA suppliers | **failed** | 7/1/2/2 | 37 | — | 15 claims; the judge returned too few verdicts (`InvalidSupportReport`). |
| Q08 capex and commitments | accepted | 3/1/1/1 | 21 | Correct; an off-topic NVIDIA buyback claim was withheld. | No capex amounts; NVIDIA uncovered; implication reported as not established. |
| Q09 geographic exposure | **failed** | 8/0/4/4 | 45 | — | Per-company searches exhausted the four-search budget (a single comparison was needed). |
| Q10 AI and margins | accepted | 4/1/1/1 | 20 | Correct refusal: AI statements and margin drivers quoted; Microsoft gross margin $171,008M vs $146,052M matches its table; causal inference refused. | One claim labels the corpus-2022 Alphabet filing (filed 2023) "2023 filing". |

**Pattern.** Every accepted answer was truthful, but financial trend questions
(Q01, Q02, Q05, Q08) came back thin: table rows rarely become citable. The
stored table context keeps only the first 1,600 characters, and Docling's
padded Markdown rows run to about 300 characters, so a table's context often
holds only its header rows. The segment amounts appear only in the flattened
chunk text ("AWS, = 24,631."), which has no column years.

Fixes after the first pass (all offline-tested): withholding on the final
attempt of every answer (Q03), fixed-key judge verdicts for all answers (Q07),
a comparison evidence budget scaled by target count (Q06), and an instruction
that multi-company and multi-year questions are comparisons (Q03, Q09).
