# Phase six execution record

Plan: [grounded answers](phase-six-grounded-answers-plan.md).

## Current gate status (2026-10-20)

**OPEN — recorded failures fixed offline; post-fix live confirmation pending.**
Application excerpt-scope checks now reject the recorded whole-filing absence
false positive, and its eleven-case recorded-verdict replay passes. Supplier
exposure now shows relevant text buried behind off-topic chunk prefixes; specific
urgency-gap details are preserved and unsupported cross-filing superlatives are
rejected. No additional paid calls were run. See the
[fix evidence and limitations](../evaluations/assistant-results.md).

The Microsoft five-year
financial comparison passes with original table context. Direct calculator
completion now passes live (65.56%, three citations, one calculation). The owner
browser review remains complete.

The final Apple/NVIDIA run cites both companies and preserves all ten requested
targets, but returns incomplete factual coverage and mislabels the urgency gap
as causality. Application and raw-judge calibrations both wrongly accept a
whole-filing absence assertion from a selected excerpt (10/11 cases correct).
Numeric input measure/scope rejection passes. Do not close the claim-support gate.
Details, source inspections and actual request counts are in the
[latest evaluation record](../evaluations/assistant-results.md). No repeated
paid runs, settings changes or product-code fixes occurred in this verification.

## Earlier checkpoint (2026-10-19)

Latest correction work: source selection now uses server-issued, provider-enumerated
evidence IDs; quotes and source metadata are attached by code. Incomplete sentences
remain uncitable previews. Comparison labels come from filing metadata and missing
period groups expand into individual gaps. Repair receives specific support
assessments and source identity, rather than only a rejection category.

Numeric checks preserve accounting negatives and recompute calculation records.
Guided inputs use a dedicated scope/measure verifier; source parsing checks their
amounts, units and period headings. Final arithmetic reuses only the exact verified
pair and is recomputed before rendering. Unknown metadata fields are omitted from
judge requests without changing the citation UI's unknown-year/page labels.

Final verification: **185 offline tests passed, 15 integration tests deselected**;
Ruff check and formatting passed. **Five marked live checks passed**: eleven-case
application grounding calibration, wrong input measure/scope, source injection,
real-source arithmetic fixture and the autonomous Microsoft ratio (65.56%, four
generator requests and one input-verification request). This supersedes the
intermediate regressions recorded in local artifacts, not their historical record.

The hard five-year Microsoft question still failed with both the default answering
model and an isolated `gpt-4.1-mini` candidate (same default judge). No production
model change is justified by that paired result. The final supplier comparison
also failed grounding safely. Broad answer quality remains open; see the
[latest evaluation record](../evaluations/assistant-results.md). The owner's manual
review is complete. Earlier verification results below describe prior checkpoints.

The owner confirmed all five proposed browser reviews work as expected. The
manual gate is complete, including the guided calculation, source/history
restoration, Stop/retry, F5/retry, network recovery and unsupported-target refusal.
Historical pending-browser statements below describe earlier checkpoints.

After this confirmation, the offline suite passed **169 tests, 14 integration
tests deselected**. The default Windows pytest temporary directory was inaccessible;
the complete rerun used a fresh directory below ignored `data/chunks/assistant/`.
Ruff check and formatting passed for assistant/grounding modules and assistant tests.

Earlier independent-judge calibration was inconsistent. A five-case run rejected all
four unsupported cases, but an expanded seven-case run accepted the deliberately
forged calculation record again. It rejected the added partially supported
compound claim and wrong accounting sign. The fixture deliberately bypasses the
calculator boundary; the real calculator's mechanical protections remain in place.
Expectations are unchanged and timestamped artifacts preserve both outcomes.
This is a failed calibration gate, not a passing retry. No further paid calibration
retries or model/prompt changes were made during this verification.

The completed ten-question evaluation returned eight grounding failures, one
automatically accepted partial answer and one insufficient-evidence reply, with
no service errors. The partial answer and refusal do not establish complete
supported comparisons; details and usage are recorded in the
[answer worksheet](../evaluations/assistant-results.md). The overall claim-support
quality gate remains open independently of the completed manual review.

Implementation authorized on the current checkout. No commits, pushes, migrations,
dependency additions, corpus changes, or actual environment edits.

Shared interfaces: tools expose source spans to the registry; validation consumes
only those spans; rendering supplies citation snapshots to persistence and UI.
Replay consumes those saved snapshots without invoking the assistant.

## Implementation and verification

- Tasks 1–3 implemented: frozen typed claims/references, per-turn observed spans,
  bounded retrieval tools, explicit company/year coverage, Decimal calculator,
  structural checks, independent no-tool judge and one repair.
- Task 4 implemented: bounded server history, authenticated ownership before paid
  work, transient progress, cancellation, accepted-only text, atomic citations and
  completed-turn replay. Existing deterministic IDs and NOWAIT lock remain.
- Task 5 implemented: typed source/status parts, safe SEC links, expandable exact
  quotes, citation restoration and allowlisted safe failure messages.
- Task 6 implementation present: smoke CLI, checkpointed JSON results, evaluation
  worksheet and concrete owner-review cases. Quality acceptance remains OPEN.

Tests were written and observed failing before the corresponding contracts,
calculator, tool bounds, grounding and orchestration implementations. Later
regressions were reproduced before fixes: hidden/unquoted numeric support,
parenthesized negatives, lost comparison warnings, multi-year target grouping and
calculation output tampering. New runtime dependencies: none.

Final offline run: **149 passed, 13 integration tests deselected**. Frontend
TypeScript, lint and production build passed. Vite reports the existing large
bundle warning; no bundle-splitting scope was added.

The final rerun uses `--basetemp=.pytest_cache/phase6-final-20261019b` because the
default Windows `pytest-of-Lenovo` temporary directory denied access during three
ingestion fixture setups. This is a local test-directory workaround; no app or
corpus configuration changed. Three test-file import-order issues were also fixed.

Live database checks: **2 passed**, all fixtures rolled back. Live source-injection
answering-agent check passed. The real-source calculator/judge fixture passed.
The expanded independent-judge calibration is **not consistently passing**: the
small judge has accepted a forged calculation record lacking year/scale evidence.
That forged record bypasses the calculator boundary; the actual calculator now
rejects those inputs mechanically. This remains a recorded judge limitation,
not a reason to delete or weaken the calibration expectation.

The selected live suite finished with **4 passed, 1 failed**. The latest complete
client-question sweep (`client-questions-repaired.json`) failed all ten cases
safely: eight grounding rejections and two service/output-schema failures. Exact-ID
repair feedback helped one targeted supplier comparison produce a validated partial
answer, but that does not establish broad answer quality or owner acceptance.

Malformed judge coverage now fails as a service error. Numeric-token validation
also preserves spaced parenthesized negatives. Evaluation-only `gpt-4.1-mini`
trials passed one calibration but had mixed comparison outcomes; production model
configuration remains unchanged. No further paid tuning is justified by this record.

## Review and decisions

An independent read-only reviewer identified four findings. All were fixed:

1. Support must come from each claim's attached quotes, not other source paragraphs.
   Added a regression proving the judge never receives unrelated sentences.
2. `(100)` cannot supply a positive `100` operand. Negative-token regression passed.
3. Comparison results retain lexical status and bounded warnings per target.
4. The browser preserves only allowlisted backend grounding/budget/timeout errors.

Ruling: calculate records, rather than model calculation prose, supply the final
calculation label/operands/value. This prevents a fabricated model result reaching
the user even if a heuristic judge errs; tests demonstrate the rendered value
comes from the immutable Decimal record.

Ruling: multi-year agent comparison filters expand into individual year targets
(still at most 25, same phase-five concurrency). Otherwise three hits for a broad
five-year filter could conceal missing periods. Completed retrievals are counted
separately from failed attempts when enforcing the in-scope retrieval requirement.

Ruling: the current source format and configured models remain unchanged. Quality
failures are reported, not hidden through weaker quote checks, an unapproved model
change or corpus rewriting. The cost is a still-open answer-quality gate.

No commits/pushes were made. Owner verdicts and browser recovery/source checks are
pending in [the review sheet](../evaluations/assistant-owner-review.md). The
[evaluation worksheet](../evaluations/assistant-results.md) records actual outcomes
and known refusals/rejections; phase-five acceptance is not reused as answer
acceptance.

## Follow-up: Azure lookup failure (2026-10-19)

Reproduced the owner's exact question failing because the model stitched
nonadjacent source sentences into one quotation and repeated it during repair.
Clarified the typed quote field and instructions; added precise repair feedback
that offers separate sentences only when each is already-observed exact text.
The original invalid reference remains rejected. Regression coverage also proves
that hidden and reworded sentences are never suggested.

Latest verification: **151 offline tests passed, 13 integration tests deselected**;
Ruff passed. Three consecutive live runs of the exact question passed structural
checks and judging (about 11–12 seconds), without chat writes. The frontend error
overwrite was fixed separately and checked using the actual SDK callback order,
TypeScript and lint. Models, actual environment, corpus and schemas are unchanged.
Browser confirmation and the broad answer-quality gate remain open.

## Follow-up: numerical browser question remains blocked (2026-10-19)

The owner reported two service failures for the Microsoft reported-increases
ratio. Investigation reproduced repeated invalid calculations, missing quoted
units/periods, one-operand requests and incorrect segment/percentage selection.
The full original question retrieves the correct narrative passage, whereas the
agent's shortened query lost the reported-increase intent.

Added first-query preservation, model-facing two-operand cardinality, and a
calculator pause until new evidence is observed after a rejected calculation.
Enabled explicit strict provider schemas for tools, the typed answer and the
judge; an HTTP mock verifies the actual request contract without network calls.
Latest offline suite: **156 passed, 13 integration tests deselected**.

The latest configured-model numerical run still failed grounding. A prior
evaluation-only stronger-model trial also failed before strict schemas were
enabled; it is not evidence to change production configuration. No configured
models, actual environment, corpus or database schemas were changed. Further prompt tuning and blind
paid retries are stopped. A guided numeric-fact verification flow versus a
controlled stronger-model evaluation is an owner decision. The review sheet now
records the failed browser case without overwriting the owner's verdicts.

## Guided calculation implementation (2026-10-19)

The owner selected this direction. Added `assistant/facts.py`: source-derived
narrative candidates, a typed no-tool selector, mechanical input checks and an
independent support check before fact registration. Calculator calls now carry
only two request-scoped ordered fact IDs. Removed the obsolete raw-operand tool
contract and evidence-revision retry gate. The unchanged Decimal math uses the
clearer internal name `ratio_percent` for ratios expressed as percentages.

Provider tool choice enforces the sequence for explicit arithmetic; ordinary
lookups keep their normal flow. The candidate enumerator requires explicit
period headings and recognized units, preserves signed source tokens and never
infers table columns. The first full question is preserved, with resolved query
context retained for short follow-ups. Preparation is capped at two attempts;
selector requests share the generator budget, and input/final judge requests are
counted cumulatively. No new settings or dependencies were introduced.

The independent judge now checks the same canonical calculation text the backend
renders, rather than discarded model prose. Source quote/input checks remain
strict. Offline tests cover atomic fact registration, bad/foreign/reversed IDs,
semantic rejection, period/scale/token extraction, routing states and actual
OpenAI wire-level prepare → calculate → final-output behavior without network.

Two autonomous live checks returned the correct supported 65.56% and three
citations for the reported-increases question. The Azure regression also passed.
Final offline verification: **169 passed, 14 integration tests deselected**;
Ruff and formatting passed. The separately selected autonomous live test passed,
and the backend health check returned `status: ok`.
Evidence is in the [worksheet](../evaluations/assistant-results.md); the owner
review retains existing verdicts and now requests a browser recheck of the guided
path. Broad client-question quality and judge calibration were not rerun or
declared resolved. No actual environment, corpus, database schema, commits or
pushes changed.
