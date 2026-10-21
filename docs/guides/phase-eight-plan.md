# Phase 8 plan: client-brief gaps and answer quality

Autopilot plan, continued from [phase 7](phase-seven-plan.md) on the night of
2026-10-22 after its tasks were complete. The checklist lives in
[todos](../todos.md#8-close-the-client-brief-gaps-and-validate-quality).
The owner raised the paid grant to 400 requests (cumulative) for this phase.

## Rules for each autopilot iteration

- Same rules as phase 7: first unchecked task, small changes, offline tests,
  local commits only, tick each task with a one-line result.
- Paid calls only through `data/chunks/assistant/capped_question.py` (it
  records searches, judge payloads, requests and latency per run). Stay inside
  the ledger's grant.
- An answer counts as correct only after reading every claim against its own
  quotes. Citation presence alone is not proof.
- Results go to [phase-8 results](../evaluations/phase-8-results.md).

## Tasks

1. [ ] **Client example questions.** Run the ten brief questions
   (`docs/evaluations/retrieval-cases.json`, Q01–Q10) once each. Record status,
   claims and gaps, claim-by-claim accuracy against quotes, citation location,
   latency and requests.
2. [ ] **Negative cases.** Unsupported company/period, missing figures, an
   ambiguous question and "AI caused margin improvement" causal claims
   (smoke cases S04, S05 plus new ones). The right result is a refusal or a
   truthful gap, never an invented fact.
3. [ ] **Financial comparisons.** Check units, fiscal calendars and segment
   names in the numeric answers from tasks 1–2 (Q02, Q05, Q08, the Microsoft
   ratio, Apple Services percent change S03).
4. [ ] **Fix and rerun.** Fix the failures found in tasks 1–3 where a
   deterministic or narrowly scoped fix exists; rerun only the affected cases.
5. [x] **Credential exposure check.** Done: production bundle and 150 local logs/artifacts hold no privileged keys, URLs or tokens; deployed logs wait for phase 9. Confirm the production frontend bundle
   and backend logs contain no privileged keys (search for key names and
   patterns without printing values).
6. [ ] **Owner/client decisions (not autopilot work).** Expanding the corpus
   to S&P 500 10-K and 10-Q filings for 2020–2025 changes scope and embedding
   spend and needs client agreement; the two-analyst confidentiality check
   needs two real accounts. Record what is needed in the morning summary.
