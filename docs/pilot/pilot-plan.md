# Analyst pilot plan

## Status and agreed scope (updated 2026-10-24)

The owner approved a **single-person stand-in pilot**, using the existing
five-company, 25-filing 10-K corpus and the existing Supabase project. This is
an owner estimate for a tutorial project, not client acceptance. Phases 6–8
were accepted with recorded limitations. Phase 9 is provisionally closed by owner
decision for this one-person pilot: backup/restore and hosted capacity tests are
deferred; rollback verification remains untested. Final feature checks and
spending controls pass per owner report. These limitations and evidence remain
in [delivery status](../operations/delivery-status.md).

The original client brief remains a separate criterion: five senior analysts
use the app for a week and each saves at least three hours. Recruiting those
analysts, claiming their acceptance or rolling out firm-wide is not part of
this stand-in run. Full S&P 500/10-Q coverage is deferred by owner decision.

## Deployed rehearsal (2026-10-26)

The agent completed an owner-approved eight-question [deployed rehearsal](deployed-rehearsal-2026-10-26.md): six C tasks plus two trust checks, one attempt each.
Research-task coverage was uneven (two full passes, one numeric answer with a
citation-context limitation, three incomplete); both trust checks passed.
This does not start or complete the human pilot, establish time savings, or count
as owner timing observations. Rehearsed answers may make those tasks familiar.

## Start gate and schedule

Activate a seven-consecutive-day pilot only after all of these are recorded:

- [x] Phase-9 hosted auth, confidentiality, source, history and recovery checks pass
      (owner-reported five-check acceptance, 2026-10-24). Recovery here means backend
      restart/history persistence; database-loss backup/restore is deferred.
- [x] Owner reports Railway/OpenAI spending-control checks pass (2026-10-24); exact
      thresholds were not independently read back.
- [ ] Owner confirms the start date and has the [usage guide](usage-guide.md),
      [time log](time-log.csv), and [issue log](answer-issues.csv).
- [x] Reduced corpus and one-person method agreed (2026-10-22/23).
- [x] Local two-approved-account/one-unapproved-account check recorded (2026-10-23).
      Hosted repeat also passed per owner report on 2026-10-24.

Provisional week: **2026-10-26 through 2026-11-01**, Asia/Bangkok. These dates
are a proposal, not a booked calendar event or a claim the pilot has started.
If deployment/start confirmation is later, shift the entire seven-day window.
No automatic model calls, reminders or background evaluations are scheduled.

| Day | Owner activity | Agent/developer activity |
| --- | --- | --- |
| D1 | Read instructions; mark familiar tasks; run pairs P1 and P2 in listed order. | Confirm logging; review issues on request. |
| D2 | Run pairs P3 and P4. | Check feedback and source issues. |
| D3 | Run pairs P5 and P6. | Verify arithmetic/period binding and log completeness. |
| D4–D6 | Use the app for genuine new in-scope research; record all attempts. | Triage issues and failures; investigate blockers before spending more. |
| D7 | Finish logs and give a short keep/stop/change-scope verdict. | Compute the stand-in report and unresolved-risk list. |

The owner times and performs human tasks. An agent must not generate manual
timings, simulate an analyst, fill observations from example CSV rows, or infer
weekly volume from the six task pairs. Daily review occurs when the owner brings
results; this document creates no unattended monitoring promise.

## Controlled task pairs

Each pair has one **M** question answered manually from original filings and one
**C** question answered with Copilot. They have the same evidence/verification
burden but different content. Order is counterbalanced. Do not ask Copilot the
manual question or open the counterpart's answer before its timed task.

Start each timer when opening the question. Stop only after recording the result,
checking every used source/period/unit and copying enough source location detail
to re-find it. Copilot time includes waiting, source checking, retries, corrections
and any manual fallback needed to finish. Record failures even when no result is
obtained. The manual task may use find-in-page and a basic calculator but no LLM.

Before timing, mark a pair **familiar** and exclude it from savings if either answer
or its source location is already memorized. In particular, the Azure-2025 demo,
Microsoft-2022 65.56% ratio and broad Apple/NVIDIA supplier demo are not benchmarks.
Do not select only the fastest successful attempts after seeing results.

### P1 — Business descriptions (M first, then C)

- **M:** In Microsoft's **2024 corpus 10-K**, what does Xbox Game Pass offer
  subscribers? Record two source-supported offerings and the source locations.
- **C:** In Microsoft's **2023 corpus 10-K**, what does Microsoft 365 Consumer
  offer subscribers? Cite two source-supported offerings.
- **Required evidence:** the named filing's product/business prose. Two distinct
  offerings, correct attribution, exact supporting text and an original source
  location; no claim about superiority, growth or a different period.

### P2 — Narrative risks (C first, then M)

- **M:** In Amazon's **2023 corpus 10-K**, identify two disclosed risks affecting
  fulfillment/delivery operations. Record the supporting passages and locations.
- **C:** In Amazon's **2024 corpus 10-K**, identify two disclosed risks affecting
  fulfillment/delivery operations. Cite the supporting passages.
- **Required evidence:** two actual disclosed operational risks from each named
  filing. A Business-section description must not be presented as an Item 1A quote.
  Do not infer that a risk occurred or intensified because the filing describes it.

### P3 — Quoted financial figures (M first, then C)

- **M:** What International-segment **net sales** does Amazon's **2022 corpus
  10-K** report for 2022 and 2021? Record the scale, currency and column labels.
- **C:** What International-segment **net sales** does Amazon's **2024 corpus
  10-K** report for 2024 and 2023? Cite the scale, currency and column labels.
- **Required evidence:** the net-sales row, segment identity, table units and the
  exact year headers. Do not substitute operating income, totals or another column.
  No new ratio is requested. A missing binding is a gap, not permission to guess.

### P4 — Multi-year factual comparison (C first, then M)

- **M:** What do Microsoft's **2021 and 2023 corpus 10-Ks** say LinkedIn provides?
  Record one supported statement and location from each filing.
- **C:** What do Microsoft's **2022 and 2024 corpus 10-Ks** say LinkedIn provides?
  Cite one supported statement from each filing.
- **Required evidence:** at least one attributable statement per named filing,
  preserving company and corpus labels. State a gap for any unsupported period.
  The task asks for per-filing facts, not an unsupported change or urgency trend.

### P5 — Cross-company factual comparison (M first, then C)

- **M:** In the **2023 corpus 10-Ks**, what cloud services do Amazon AWS and
  Google Cloud describe? Record one supported fact and location per company.
- **C:** In the **2024 corpus 10-Ks**, what cloud services do Amazon AWS and
  Google Cloud describe? Cite one supported fact per company.
- **Required evidence:** both companies' own filings; correct company attribution
  and at least one exact supporting passage each. No cross-company ranking,
  invented equivalence or implication that one company's quote supports the other.

### P6 — Verified narrative-input calculation (C first, then M)

- **M:** What is the ratio of Microsoft's **reported gross-margin increase to
  reported revenue increase**, as a percentage, for **fiscal 2023 compared with
  fiscal 2022**? Use the consolidated narrative increases, not gross-margin rate.
- **C:** What is the ratio of Microsoft's **reported gross-margin increase to
  reported revenue increase**, as a percentage, for **fiscal 2024 compared with
  fiscal 2023**? Use the consolidated narrative increases, not gross-margin rate.
- **Required evidence:** the exact fiscal-comparison heading, both stated amounts,
  currency/scale, consolidated scope, numerator/denominator order and the operation
  `(gross-margin increase / revenue increase) × 100`. Quote both inputs; use
  Decimal/basic-calculator arithmetic and report rounding. Local source inspection
  confirmed both narrative sections exist; no answer-generation check was run for
  these new questions. Segment figures or table-only inference do not qualify.

The cards specify evidence requirements, not predicted model success. If a period,
figure or passage is unavailable, record the incomplete task and its actual time;
accepted phase-8 limitations still apply. A claim that contradicts its own quoted
source is a blocker; a truthful gap is an incomplete task, not fabricated success.

## Separate trust checks (not savings observations)

After hosted smoke approval, ask these only within an approved paid batch:

1. “What revenue does Tesla's 2028 filing report?” — explicit unsupported-corpus
   response, no invented Tesla figures or silently substituted filing.
2. “Do these filings prove generative AI caused higher margins?” — preserve the
   causal limitation; any facts still require their own source support.

Also check that each source's printed page/range is plausible; unknown and
borrowed-heading locations stay unknown. Familiar demonstration questions may be
used for smoke tests only, never as time-saving evidence.

## Logs and calculation rules

Use the existing CSV columns without a new database or API contract. Existing
`example-analyst` rows are demonstrations, including their future dates. Leave them
intact and exclude them from all calculations. Real rows use `analyst=owner-stand-in`.

- M rows: `phase=baseline`, `used_copilot=no`, actual minutes, no estimated manual
  value. Notes include `pair=P1; variant=M; order=1; status=complete|incomplete`.
- C rows: `phase=pilot`, `used_copilot=yes`, total actual minutes including fallback.
  After both tasks are finished, use the matched M task's observed duration as
  `estimated_manual_minutes` only if the evidence burden was comparable. Otherwise
  leave it blank and record why the pair is non-comparable.
- Notes additionally record familiarity, whether every required evidence item was
  found, source-checking effort, attempts, actual answer latency and any fallback.
  Add the conversation URL for traceability; use the issue log for detailed faults.
- Out-of-scope work uses `out_of_scope=yes` and is excluded from the savings total.
  Include incomplete/failed in-scope attempts in the report and total actual-time
  burden. Do not drop slow/refused attempts to inflate savings.
- Every real pilot C task is counted once. A controlled pair and the same task
  appearing later in routine work are not two independent observations.

For each eligible real C row, estimated savings in minutes are
`estimated_manual_minutes - actual_minutes`. Include negative savings. Sum them
and divide by 60; do not multiply by imagined analysts, repeated tasks or weeks.
If fallback completed an otherwise incomplete C task, its entire time is included.
If no comparable baseline exists or the task never completes, no positive savings
is credited: report its actual cost and the unresolved measurement separately.

The matched questions are similar, not identical, so their deltas remain estimates.
Report order/familiarity effects, task mix and the small sample size; no statistical
claim or extrapolated weekly benefit is justified. D4–D6 work contributes only when
its own baseline estimate is anchored and documented, not assumed from a category.

## Trust triage, stop rule and final report

Use the existing thumbs-up/down controls and reason/comment fields. Copy real
thumbs-down issues into `answer-issues.csv`, with severity, status and fix note.
Keep logged conversations: deletion permanently breaks their evidence links.

**Stop rule:** any accepted claim contradicted by its cited passage is blocking.
Pause, preserve the example, investigate offline and obtain a separate live-check
budget before validating a fix. Quality improvements already accepted as deferred
are not automatically reopened by this delivery task.

At D7, produce a dated **stand-in estimate** containing:

- Active dates, actual task counts, completed/incomplete/familiar exclusions and
  baseline matching method; excluded example rows must not appear as observations.
- Observed baseline and Copilot time, source-checking/fallback overhead, negative
  savings, total estimated observed-week savings and unmeasurable task burden.
- Latency range, failures/refusals, issue counts by type/severity and unresolved
  risks; retained 120-second backend deadline, no stronger invented service target.
- Three-hour result: **met** only when sufficiently documented observed-week savings
  reach 180 minutes; **unmet** when adequate logs fall short; **insufficient evidence**
  when logs/baselines cannot support the judgment. A completed short pilot need
  not meet the target. More use cannot be invented to manufacture a pass.
- Owner verdict: continue, extend measurement, or stop/change scope. This never
  constitutes the original five-analyst client acceptance or a firm-wide rollout.

Until actual owner observations exist, report **not started / no result**. The
agent prepares and computes from supplied logs; it does not impersonate the owner.
