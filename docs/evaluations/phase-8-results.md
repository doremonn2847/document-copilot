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

## Client example questions, after fixes

Reruns 01:52–02:03 with UTF-8 questions. Accuracy was checked claim by claim.

| Case | Result | Accuracy against quotes | Coverage |
|---|---|---|---|
| Q01 | **refused** (financial fallback) | Every drafted claim stated mix percentages the writer computed itself; derived numbers need the calculator, which the comparison writer cannot call. | None. Correct outcome, unhelpful answer. |
| Q02 | accepted, gaps only | No claim kept: AWS/North America/International amounts were now drafted from table rows but failed currency checks (Amazon prints $ only on some rows) and one claim derived "924". | "Figures could not be verified" per year: safe, unhelpful. |
| Q03 | accepted | Correct: three Data Center demand claims match their quotes; one claim withheld. | Partial: customer concentration and supply constraints reported as not established. |
| Q05 | accepted | Correct: Search & other, YouTube ads and Cloud revenue for 2021–2024 match Alphabet's reported figures and the current-year column. | Good: Network and subscriptions lines reported as not established. |
| Q06 | accepted | Run r2: two claims listed topics their quotes never named and the judge accepted them, which led to the quoted-wording check. Run r3: that check withheld the padded claim; the remaining Apple and Microsoft claims match their quotes. | Partial: "what changed" reported as not established. |
| Q07 | accepted | Correct: Apple single-source and prepayment claims, NVIDIA supplier dependence and Asia-Pacific concentration. | Partial: urgency trend reported as not established. |
| Q08 | accepted | Correct; an unsupported claim with a derived "30" was withheld. | No capex amounts. |
| Q09 | accepted | Correct but weak: Alphabet FX exposure, Microsoft segments. | Apple's regional segment table was not retrieved. |

## Negative cases (task 2), partial

| Case | Result |
|---|---|
| N1 Tesla 2028 10-K | Correct refusal: no claims, fixed "No indexed passage was retrieved for TSLA / 10-K / corpus years 2028" notice. It spent four searches (12 requests) on a company outside the corpus. |
| N2–N6, F1 | Not run: the batch was stopped at 02:03 when the machine ran critically low on memory (0.6 GB free of 13.8 GB). N2 was killed mid-run and is counted at its per-run cap (20 requests) in the ledger. |
