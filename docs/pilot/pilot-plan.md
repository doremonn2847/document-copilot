# Analyst pilot plan

Definition of done (client brief): five senior analysts use Document Copilot
for one week and report that it saves **at least 3 hours per analyst per
week**; if so, Driftwood rolls it out firm-wide.

## Stand-in pilot (owner decision, 2026-10-22)

This is a tutorial project with no real Driftwood analysts, so the owner runs
the pilot as a **single stand-in analyst** (an agent prepares the detailed
scheme). The method below still applies, scaled to one person:

- Corpus: the current five-company 10-K corpus (owner decision; see
  [corpus scope options](../guides/corpus-scope-options.md)).
- Baseline: time a few representative filing tasks by hand first, then do
  comparable tasks with Document Copilot and log both in the time log.
- Target: the brief's 3 hours saved per analyst per week, judged from the
  stand-in's own logs; record the result as a stand-in estimate, not as
  client acceptance.
- Trust log and stop rule unchanged.

Sections that assume five analysts (recruitment, approvals, interviews,
client rollout decision) do not apply to the stand-in run.

## Before the pilot (owner)

- [ ] Hosted app live and the phase-9 smoke test passed (runbook section 2).
- [ ] Corpus scope agreed in writing with the client: the five-company 10-K
      corpus for the pilot, or the brief's S&P 500 10-K/10-Q scope first.
- [ ] Five senior analysts named; each signs up with a Driftwood email and is
      approved (`uv run python -m app.database.approve_user <user-uuid>`).
- [ ] Two-account confidentiality check done (phase 8): analyst A cannot open
      analyst B's conversation URL.
- [ ] Spending alerts set on Railway and OpenAI (runbook section 2).
- [ ] Each analyst has the [usage guide](usage-guide.md) and the two logs below.

## Measuring time saved

Self-reported weekly totals tend to be optimistic. The pilot uses per-task
logs against a baseline instead.

1. **Baseline week (before access).** Each analyst logs every document-intake
   task: what they needed from which filings, and how long it took by hand.
   Use [time-log.csv](time-log.csv) with `phase` = `baseline`.
2. **Pilot week.** For every task done with Document Copilot, log the actual
   time (including checking citations) and an estimate of how long it would
   have taken by hand, with `phase` = `pilot`. Comparable baseline tasks
   anchor those estimates.
3. **Result per analyst:** sum of (estimated manual minutes − actual minutes)
   over pilot-week tasks, in hours. The target is met when **all five** reach
   3 hours, or the client accepts a stated alternative (for example the
   median) before the pilot starts.

Only time on tasks the corpus covers counts. Tasks outside it (other
companies, 10-Qs, news) are logged as `out_of_scope` so the corpus decision
can be revisited with numbers.

## Measuring trust

Every wrong or doubtful answer goes into [answer-issues.csv](answer-issues.csv)
with `issue_type` one of `wrong_fact`, `wrong_citation`, `missing_information`,
`wrong_refusal` or `slow_or_failed`, and `severity` `blocking` or `minor`. The conversation link lets the
developer trace it (backend logs: `assistant_turn_finished`).

**Stop rule:** any accepted claim that is false according to its own cited
passage is a blocking issue. Pause the pilot and fix it before continuing (the
phase-8 evaluation found none across 17 cases).

## During the week (developer)

- Daily: read the issue log and backend logs; answer analysts' questions.
- Watch per-user limits (429s), answer failures and spend.
- Fix blocking issues, rerun the affected phase-8 cases, note fixes in the log.

## End of the week

- Compute hours saved per analyst from the time logs.
- Summarise issues by type and what was fixed.
- Short interview per analyst: would they keep using it, what is missing.
- Decision with the client: roll out, extend the pilot, or change scope.
  Rollout uses the same usage guide, per-user limits and runbook.
