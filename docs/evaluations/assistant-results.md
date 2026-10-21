# Phase-six answer evaluation

Status as of 2026-10-20: implementation present; **browser/owner review COMPLETE; answer-quality gate OPEN**.
Latest bounded checks used `gpt-5.4-mini` answering and `gpt-4.1-mini` grounding. Earlier sections retain historical model configurations and failures.
An automatically accepted answer is not a human correctness judgment. Refusals may be incorrect when useful evidence exists.

## Owner supplier-comparison feedback and group-gap correction (2026-10-21)

### Grouped live check: company omission resolved in this run; total limit failed

The separately approved grouped-contract check failed with `GroundingRejected`
after **33.08 seconds**. Actual requests: **3 answering, 0 judging, 1 keyword,
1 embedding**; answering usage 13,131 input / 1,672 output tokens. No retries,
extra runs or chat/database writes occurred.

Both drafts cited Apple and NVIDIA. The first interpretation selected 4+3
references; the repair selected 3+3. Both exceeded the existing five-reference
total, despite repair feedback explicitly requiring a split or narrower claim.
Judging was never reached. This is observed progress on company selection, not
an accepted answer, semantic correctness verdict or phase-six pass.

The independently bounded group lists left a combined-budget violation possible
in the provider schema. Offline regression tests reproduced it. The schema now
offers only allocations totaling at most five across required companies, while
keeping independent runtime validation. Exhaustive count checks preserve all
valid allocations for one through five companies; actual SDK wire tests check
normalized branches and company ownership. This correction has no live proof
yet, and no further paid calls were made. Phase 6 remains OPEN.
Post-correction verification: **345 offline tests passed, 15 deselected**;
affected Python lint/format checks passed. FastAPI restarted healthy.

### Owner-approved grouped citations: implemented and verified offline

The repeated failure was reproduced from both saved drafts. The writer had all
35 selectable sources, including 19 NVIDIA sources, and the exact rejection
feedback. Its interpretation still selected five Apple IDs only. The flat
selection schema did not require per-company coverage and the interpretation
spanned more company/year targets than its five-reference budget could support.

After owner approval, comparison interpretations require `evidence_by_company`:
each compared company has a required nonempty field limited to its own observed
IDs. Submission independently checks membership and the five-reference total,
then resolves only those selected IDs through the existing citation path. Facts,
retrieval, the one-repair allowance and semantic judging retain their roles.
Unsupported or missing-company interpretations cannot be made acceptable by
automatically adding citations. Broad interpretations must split or narrow.

**340 offline tests passed, 15 integration tests deselected.** Real-SDK mock
regressions cover invalid and corrected submissions, fail-closed exhaustion and
semantic rejection despite valid source groups. Both actual failed
interpretations are rejected by the new typed contract in a separate offline
replay. Lint and formatting pass. No paid rerun or browser confirmation has
followed this contract change. These are contract/regression results, not a
human quality verdict or a successful live supplier comparison. Phase 6 is OPEN.

### Follow-up live check: writer repeats cross-company citation error

The owner approved one more capped check after the offline fixes. It failed
closed with `GroundingRejected` in **33.8 seconds**, before any judging:
**3 answering, 0 judging, 1 keyword, 1 embedding** requests; answering usage
13,145 input / 2,576 output tokens. Zero retries, extra runs or chat/database
writes occurred.

Both drafts included ten company/year facts and a broad Apple/NVIDIA
interpretation citing five Apple IDs only. Captured repair input contains the
specific missing-NVIDIA rejection and candidate NVIDIA IDs, plus the original
evidence. The model repeated the same invalid interpretation citations after
repair. No claim received semantic acceptance; fixed-key judging was not reached.
The observer and repair-feedback corrections are exercised, but the writer's
cross-company citation behavior remains unresolved. Phase 6 stays OPEN; do not
treat the ten draft facts as a passed answer or request routine frontend retries.

### Latest approved live check failed; follow-up fixes are offline only

The guided supplier-comparison diagnostic failed with `InvalidSupportReport` in
35.77 seconds. Actual requests: **3 answering, 1 judging, 1 keyword, 1 embedding**,
within the approved caps and with no chat/database writes. Answering used 8,313
input / 1,251 output tokens; judging used 2,572 / 727. The first draft's
cross-company synthesis cited only Apple and was correctly rejected.

An offline reproduction found that the diagnostic's nested SDK message capture
hid failed draft history from the outer repair handler. Its replacement HTTP
observer preserves history and captures judge replies without recording headers
or error bodies. This limits what the failed diagnostic says about production.

Guided judge verdicts now use required server-owned claim/gap keys rather than
model-generated decision indices. A separate real-SDK regression reproduced
missing output-validation feedback in the repair prompt; bounded private feedback
now accompanies the preserved evidence. Safe log categories are unchanged.
Observer parity passed with two mock requests and zero live requests.

**327 offline tests passed, 15 integration tests deselected**; affected Python
lint/format checks passed. There has been no paid rerun or browser confirmation
after these fixes. Phase-six reliability remains OPEN. Historical entries below
describe their respective earlier verification states.

### Approved guided comparison implemented offline

The owner approved replacing open-ended comparison research with a guided path.
The existing typed `compare_filings` call is now a planning output that returns
after backend-controlled comparison retrieval. A tool-free writer drafts from
bounded source exposure. Its invalid submissions and structural/semantic
rejections share one repair allowance and frozen evidence; no writer-stage
search/read loop or extra source-catalogue expansion occurs during repair.

The writer selects server-owned question-span IDs rather than transcribing
request quotes. The server resolves their text; the judge verifies the matching
ID and independently checks whether the specific gap is requested and unresolved.
Gap-only comparison outputs also receive semantic judging. Missing target
coverage remains server-owned; the bounded gap envelope now accommodates
25 aspect gaps plus 25 coverage gaps. Lookup and verified-calculator paths,
production model settings, provider limits, deadline, corpus and database schema remain
unchanged. No new dependency or paid request was introduced.

Offline SDK transport tests exercise planning, frozen retrieval, a writer with
only final_result available, valid and invalid E/R IDs, a shared repair across
submission/grounding errors, fail-closed exhaustion, empty target plans, budget
gates and explicit empty-target coverage. Request spans preserve actual text and
remain bounded for long questions. The focused review's two budget/target-count
findings were reproduced, fixed and rechecked. Implementation record:
[guided comparisons](../guides/guided-comparisons.md).

This is implementation/offline evidence only. No post-change live generation,
judge evaluation or browser confirmation has run. Prior failures and owner
verdicts are preserved; phase-six live reliability remains OPEN.

Final verification: **324 offline tests passed, 15 integration tests deselected**;
Ruff lint and formatting passed for all 12 changed Python files. The exact-span,
company-source, numeric/calculator, citation, persistence and normal-lookup
regressions remain passing. An additional gap-only orchestration regression
confirms that an unrequested limitation cannot bypass judging. No live requests
were made to obtain these results; the next evidence gate is an instrumented,
separately approved live run, before ordinary frontend retries.

### Two subsequent frontend failures: live reliability still open

The owner reported two failures after the submission change. Safe runtime logs
show different outcomes on the same conversation:

- First attempt: `TimeoutError` at 120.01 seconds, after 7 generator requests
  (92,389 input / 4,408 output tokens) and 1 grounding request (8,134 input /
  853 output tokens). Both recorded structural attempts had zero errors. This
  establishes that structural acceptance alone did not ensure timely completion;
  the logs do not retain the judge's rejected details or final repair draft.
- Second attempt: `UnexpectedModelBehavior`, `output_retries_exhausted`, with
  `request_anchor_invalid`, at 49.93 seconds; 6 generator requests (51,603 input /
  2,792 output tokens), no judge calls and no returned draft. The submission
  failed the exact user-request anchor check. The raw invalid anchor is not
  retained, so do not assume a particular punctuation mismatch or paraphrase.

Neither is recorded as a navigation cancellation. No additional model calls were
made while inspecting these logs. The earlier company-submission change remains
offline-verified but has not made the broad comparison reliable. Do not mark
phase 6 complete or ask the owner to continue ordinary frontend retries.

Proposed owner review: a guided comparison path with one typed target-planning
step, backend-controlled comparison retrieval/exposure, one bounded draft, and
at most one grounding repair; server-owned request-span IDs replace free-form
request quote copying. Preserve actual evidence checks and explicit target gaps.
This changes orchestration and needs the owner's architecture decision before
implementation. Production settings and validation rules remain unchanged here.

### Instrumented diagnostic: captured company-citation mismatch

The owner approved one additional run under the same caps. Actual requests:
**6 answering, 0 judging, 1 keyword, 1 embedding**, zero HTTP retries.
Known generator usage: 59,451 input / 1,527 output tokens; 66.81 seconds.
This run returned a draft with ten factual claims, one interpretation and six
gaps. Structural validation rejected the interpretation because it named both
Apple and NVIDIA but cited only Apple passages. The request cap then prevented
a repair. The recorded draft did not reproduce the earlier numeric-token error;
do not claim that original error has been resolved.

Factual blocks cite AAPL corpus 2021–2025 and NVDA 2021/2024/2025. The draft also
incorrectly proposes a missing-Apple-2022–2025 gap despite its own cited facts;
no judge ran to assess those gaps or the claims. This is not an accepted answer,
coverage-quality pass or owner verdict.

The cross-company citation rule now also runs at final submission, sharing the
existing company-coverage check. Invalid submissions receive the missing ticker
and a small catalogue of already-observed candidate IDs grouped by corpus year
within the existing output retry. The application does not attach or substitute
citations. Final structural and semantic validation remain in place. Instructions
now reserve missing-company/year coverage reporting for the server, while the
model reports specific unresolved aspects. Prompt compliance has not been rerun
live. Production request/token limits, models, database and corpus are unchanged.

Two regression tests first failed because invalid submissions returned instead
of requesting repair. They now pass. A network-free SDK transport test confirms
that a first Apple-only submission receives specific NVIDIA-ID feedback and a
second submission can explicitly select both companies' sources in one agent
run. This proves submission/retry mechanics, not future model quality.

The instrumented artifact is
`data/chunks/assistant/capped-supplier-comparison-result.json`; the prior run is
preserved separately as `capped-supplier-comparison-first-run.json`. No further
paid rerun was made. Live confirmation and the original numeric rejection remain
open; phase 6 is not closed.

Final offline verification: **306 tests passed, 15 integration tests deselected**;
Ruff lint and formatting passed for the three changed Python files. A separate
metadata-only replay of the actual captured final submission rejects claim 10
at submission and returns observed NVIDIA-ID candidates without altering its
selected citations. It makes no network/database calls and is not a semantic
or full-source verification. Artifact:
`data/chunks/assistant/supplier-submission-offline-replay.json`.

### Approved single diagnostic: request cap reached, original rejection unresolved

The owner approved one run capped at six answering calls (4,000 output tokens
each), two judging calls (2,000 each), three keyword calls (150 each) and one
embedding request, with zero HTTP retries and no chat/database writes. Actual
requests: **6 answering, 0 judging, 1 keyword, 1 embedding**. Known generator
usage: 52,240 input / 933 output tokens; elapsed 39.38 seconds. The run stopped
with `UsageLimitExceeded` after six tool calls, before returning a final draft.
It exposed 198 evidence spans but produced no structural-validation report.
Artifact (archived before the next run):
`data/chunks/assistant/capped-supplier-comparison-first-run.json`.

This did not reproduce the earlier `uncited_number` rejection and is not a
grounding or supplier-quality pass. The diagnostic cap is tighter than the
production limit of 20 answering requests; its exhaustion alone does not prove
a production loop or justify changing production limits. No automatic rerun was
made. The approved allowance is consumed.

The diagnostic wrapper previously captured only completed agent outputs. It now
also uses the installed SDK's `capture_run_messages` in a `finally` block so a
future interrupted run retains intermediate model/tool messages. An offline
FunctionModel probe deliberately exhausted a one-request limit and verified that
the partial tool messages were retained, with zero provider calls. This capture
change cannot recover the already-finished diagnostic's missing messages and
has not been rerun live. It changes only the ignored local diagnostic script,
not application behavior, prompts, production settings, models or source data.

### Browser failure and group-gap regression

The subsequent frontend attempt still failed. Its safe runtime diagnostics show
two structural rejections for `uncited_number` (claim indices 8, then 15), four
generator requests and zero grounding requests. This is not a judge rejection
and is separate from chat navigation. Neither rejected draft nor the unmatched
numeric tokens are retained in these production logs, so the exact source/claim
pair has not been reproduced. Do not infer a validator defect, remove numeric
checks, or repeat paid attempts based only on that category. Further diagnosis
needs the failed draft and its cited evidence from one explicitly bounded run.

The owner's new browser reply contains cited blocks for AAPL corpus 2022–2025
and NVDA corpus 2024–2025. This is an observed output, not an independent
verification of every claim or interpretation. AAPL 2021 and NVDA 2021–2023
have no factual blocks. The reply repeats limitations about missing earlier
years under years that already have cited blocks, then repeats them in different
words. The owner judged the answer unsatisfactory.

A regression reproduced the mechanical defect: `final_answer` expanded a
multi-year gap into individual periods and copied its specific explanation to
each. One group-level limitation appeared five times. Specific limitations now
retain their submitted group scope; blanket gaps without details still expand
into individual periods. Server-created gaps independently preserve every
uncited comparison target. Exact duplicates are still removed. The regression
passes with one group limitation and a separate uncited-year gap. Instructions
also prohibit paraphrasing the same limitation into multiple gaps; compliance
with that instruction has not been live-tested.

Phase 6 requires supported claims, traceable citations and accurately scoped
limitations, not exhaustive coverage or perfect prose for every client question.
Phase 7 covers presentation and analyst usability; broader retrieval/answer
quality evaluation belongs to phase 8. Incorrectly scoped gaps are a phase-6
defect. No new model calls, database changes or corpus changes were made here.
The claim-support gate remains open; do not treat this offline fix or the owner's
quality complaint as acceptance of the supplier answer.

Verification: **303 offline tests passed, 15 integration tests deselected**;
Ruff lint and format checks passed for the changed Python files. The targeted
regression failed before the fix (five copies instead of one) and passes after it.

## Nano response-budget compatibility (2026-10-19)

### Remaining scope and supplier-exposure defects fixed offline (2026-10-20)

The owner requested fixes after the bounded live checks failed. Implemented
application checks for recognized whole-filing absence assertions before model
judging, with the same rule applied to gap details. The judge boundary also
prechecks this class, so direct callers cannot accept the known false positive.
Source-disclosed negative facts and scoped excerpt limitations still reach the
judge. This enforces existing policy; it does not claim the raw judge improved
or that English-pattern checks detect every possible paraphrase.

The saved supplier superlative ('most explicit' across filings) lacked cited
alternatives for each company. That comparison now fails structural validation;
the agent must cite the compared filings or omit the ranking and report a gap.
The renderer now preserves specific missing_detail for every reason, so the
recorded urgency limitation is displayed instead of causal boilerplate. Empty
targets no longer print a stray colon. Instructions distinguish wording/urgency
comparisons from causal questions.

Read-only inspection found relevant supplier/manufacturing text in the actual
retrieved AAPL 2022, AAPL 2025 and NVDA 2025 chunks, roughly 1,300–2,800 characters
after their beginnings. Prefix-only excerpts and an unrelated stock table hid
those sentences. Exposure now chooses verbatim sentence-boundary windows using
the prepared lexical query/current question and suppresses unrelated table
context. Retrieval ranks, filters, source identities, embeddings and output caps
are unchanged; relevance is only an excerpt-selection heuristic, not proof of
claim support.

Eight regressions failed before implementation. The corrected application replay
of all eleven recorded raw judge verdicts now matches expected decisions: the
known absence acceptance is rejected by code, not recast as a successful raw
judge decision. Re-exposure of the three real saved source chunks recovers
relevant complete quotations. A ten-nonempty-group budget replay, with seven
synthetic budget placeholders, retains those real quotations within 10,943
characters. All displayed references pass source verification. The saved urgency
gap renders its correct detail without the causal sentence or empty prefix.

Artifacts: `data/chunks/assistant/remaining-errors-offline-replay.json` and
`data/chunks/assistant/supplier-ten-group-exposure-replay.json`. These are offline
replays, not new retrieval/model evaluations. No additional paid calls, model
changes, database writes, migrations, dependencies or corpus changes occurred.
Current supplier generation and current application live calibration still need
post-fix confirmation before closing the phase-six quality gate. Historical live
failures and owner review verdicts remain intact.

Final offline verification: **302 passed, 15 integration tests deselected**.
Ruff lint and formatting checks passed for all eight changed Python files;
`git diff --check` reported no whitespace errors.

### Approved remaining phase-six checks: NOT CLOSED (2026-10-20)

The owner approved the remaining live checks. The single run imposed shared HTTP
caps of ten answering calls (4,000 output tokens each), six judging calls (2,000
each), two query embeddings and six keyword calls (150 each). HTTP retries were
disabled. Actual totals: **9 answering, 5 judging, 2 embeddings, 2 keyword calls**.
No failed paid case was rerun, and no production code, settings, models, database
records or chat history were changed. Artifact:
`data/chunks/assistant/phase6-final-checks.json`.

| Check | Observed result | Verdict |
|---|---|---|
| Apple/NVIDIA 2021–2025 supplier comparison | Five claims, including a synthesis citing both companies; all ten targets represented by facts or gaps. Only Apple 2021/2024 and NVIDIA 2021 have factual coverage. | Partial; citation-company coverage passes, comparison quality not complete |
| Application calibration, 11 cases | Both supported controls accepted; eight of nine unsupported cases rejected. Whole-filing absence claim wrongly accepted. | FAIL: 10/11 |
| Numeric input measure/scope | Consolidated-revenue request rejected when evidence describes international-segment operating income. | PASS |
| Raw independent judge, same 11 cases | Forged calculation rejected without the application's mechanical precheck; the same whole-filing absence claim wrongly accepted. | FAIL: 10/11 |
| Direct calculator completion | 65.56%, three citations, one completed calculation; three generator requests including numeric selection, one input judge. | PASS live |

The supplier run returned a controlled partial answer, not a complete five-year
comparison. Its synthesis now cites both AAPL and NVDA, resolving the previous
missing-company citation defect. Manual inspection also found quality limits:
the urgency question received `unsupported_causality` even though its specific
missing detail correctly describes sparse evidence for an urgency trend. The
renderer drops that detail for this reason and prints an empty-target colon.
The phrase 'most explicit' compares wording using citations from only the 2021
filings; do not treat it as a verified ranking across the requested years.
Uncovered targets remain visible. Exposed AAPL 2022/2025 excerpts concern product
competition, and NVDA 2025 context includes a stock-performance chart, so those
refusals cannot establish that the underlying filings lack supplier disclosures.
The test's generator cap was six for this comparison; production's larger
default budget was not exercised. Supplier usage: 50,612 input / 977 output
generator tokens and 5,959 input / 875 output judge tokens; 43.24 seconds.

Both calibrations failed the known unsupported assertion 'The filing never
mentions Azure.' The judge reasoned that a supplied excerpt does not mention
Azure and therefore supports absence from the entire filing. This violates the
documented selected-excerpt scope policy. Wrong scale, unsupported prior period,
causal leap, fabricated compound fact, wrong accounting sign, unsupported urgency,
cloud-capacity inference and forged calculation were rejected; supported revenue
and AI-launch controls were accepted. The source contains instruction-like text;
it did not make the judge accept all claims. These are labeled fixture outcomes,
not a corpus-wide accuracy estimate. Expectations were not weakened.

Direct calculator usage: 9,373 input / 186 output generator tokens, 1,606 input /
208 output judge tokens; 11.33 seconds. This resolves the earlier uncertainty
about live direct-output completion: the registry recorded exactly one calculation
and no extra generator call after submission. The earlier Azure lookup and
Microsoft five-year comparison successes remain valid recorded results.

The remaining blockers are evidence-scope enforcement for file-wide absence
assertions and supplier comparison/limitation quality. **Do not close phase six.**
No additional inference calls or fixes occurred after this verification run.

### Owner-approved capped five-year Microsoft comparison: PASS (2026-10-20)

The owner authorized exactly one diagnostic of the original fiscal-2021–2025
question. An HTTP request hook enforced at most six answering requests (4,000
output tokens each), two judging requests (2,000 each), one embedding request
and three keyword requests (150 each), with zero automatic HTTP retries. The
test used the current app agent, retriever, registry, validator, judge and renderer,
an empty conversation history and no chat/database writes. The test-local
generator request limit was six and retrieval-preparation limit one; no cap was
hit and no production settings were changed.

**Result: answered**, five factual claims covering every requested year, no gaps,
no repair and no fallback. Each claim includes revenue, gross margin, currency
scale and fiscal year. Fifteen citations attach the source table plus period and
section context. Structural validation returned no errors, and the independent
judge accepted all five claims. Deterministic inspection confirms each citation
group uses the correct MSFT corpus-year source, includes the complete displayed
revenue/gross-margin rows and fiscal heading, and keeps unknown indexed fiscal
years and page labels null.

| Fiscal year | Revenue ($ millions) | Gross margin ($ millions) |
|---|---:|---:|
| 2021 | 168,088 | 115,856 |
| 2022 | 198,270 | 135,620 |
| 2023 | 211,915 | 146,052 |
| 2024 | 245,122 | 171,008 |
| 2025 | 281,724 | 193,893 |

Actual provider requests: two answering, one judging, one keyword and one query
embedding. Answering usage: 8,663 input / 479 output tokens; judging: 6,344 input /
430 output tokens. Total elapsed 32.83 seconds. This is a real end-to-end model
success for the selected question, not a developer-assembled fixture. It does
not establish reliability across repeated runs, prior conversation histories,
supplier synthesis or the rest of the client worksheet. The broader phase-six
quality gate remains open. No extra inference was performed after this run.
Artifact: `data/chunks/assistant/capped-msft-comparison-result.json`.

### False structural period rejection after table restoration (2026-10-20)

The next real frontend turn used the restored-context code but returned the
ambiguous-figures fallback. Both drafts had exactly two structural errors,
financial_period on claims 0 and 1. No currency/scale/uncited-number error was
recorded. Five generator requests used 51,628 input / 1,118 output tokens;
zero judge calls, 57.07 seconds. This proves structural rejection before judging,
not a judge refusal. The live draft text was not retained, so its wording and
selected evidence cannot be recovered from that log.

Offline reproduction exposed a validator bug: supported financial statements
using 'in 2025' were rejected unless they matched a prescribed fiscal-year prose
pattern. A second false rejection interpreted a heading 'Revenue (2025):' as
the negative numeric token -2025. Corrected the prose gate to require actual
quoted year evidence without prescribing wording, and treat parenthesized years
followed by a heading colon as year labels. Ordinary parenthesized monetary
amounts remain negative; the calculator parser is unchanged. Missing quoted
years still fail even when corpus metadata names the year. Semantic fiscal
meaning and column binding still require the judge; regressions cover both
acceptance and rejection after the structural check.

Three focused cases failed before these corrections. These explain confirmed
validator defects consistent with the live category, not the exact discarded
draft. Safe diagnostics now distinguish missing prose years from missing quoted
years. No paid inference or model changes occurred in this follow-up. End-to-end
live quality remains unverified; the phase-six gate stays open.
Verification: 283 offline tests passed, 15 integration deselected; Ruff passed.
Backend restarted after these corrections. A capped live diagnostic is proposed
to inspect the actual answering/judging path rather than request another blind
frontend retry; no additional paid request is authorized or executed yet.

### Root repair: restore original table evidence at read time (2026-10-20)

The owner requested an underlying repair, then approved attaching hash-verified
original table context while preserving indexed text and embeddings. Inspection
found that the first HTML-to-Markdown conversion retains the financial year
columns and units, while the later Markdown-to-Docling chunking pass flattens
them into cell fragments. The chat evidence splitter then exposes those fragments
separately. The figures are present; their usable row/header context was lost.

Read-only retrieval now restores bounded verbatim Markdown table context from
the original content already stored in Supabase, using each chunk's source hash
and Docling table reference. It also exposes matching explicit fiscal headings
or printed cover-year headings. Hash checking accounts for the known LF/CRLF
translation from ingestion; it does not allow changed content. Indexed text,
vectors, nullable fiscal metadata and database records are unchanged. Table
headers and rows are exposed together as citation choices. Registry checks still
require exact source spans actually displayed this turn, and context cannot leak
through judge metadata into unrelated claims. Citation snapshots label original
table context so the UI does not imply it is the literal indexed chunk text.

Four initial offline regressions failed before implementation, then passed.
Additional checks cover five-target tool bounds, unexposed-context isolation,
non-contiguous quote rejection and explicit cover headings. The real read-only
Supabase proof selected the five known MSFT summary-table chunks and passed them
through hydration, chat exposure, source selection, structural validation and
rendering. All five revenue/gross-margin row pairs were present within the chat
budget, with zero structural errors. Its claims were assembled deterministically
by the developer: no question embedding, keyword generation, answering or judge
inference was run. Artifact: `data/chunks/assistant/financial-table-context-proof.json`.

This proves restored evidence availability, not live model planning or semantic
judge acceptance. No database writes, re-embedding, migration, new dependency,
model changes or paid inference were performed. Live answer quality remains
unverified and phase-six quality remains open.
Final verification: 276 offline tests passed, 15 integration deselected; Ruff
check/format and frontend typecheck/lint/build passed. The local 25-filing audit
checked 4,511 cached table-bearing chunks: 4,364 supplied bounded context with
matching cells, with no source-hash or out-of-range-reference errors. The remaining
chunks supplied no matching bounded table context; this count is not an answer
accuracy measure. The final Supabase proof exposes all five table row pairs and
explicit fiscal headings within 11,133 tool characters. The 2021 source uses its
printed fiscal cover heading, not inferred fiscal metadata. Frontend build retains
its existing bundle-size advisory. Backend restarted after final changes.

### Uncited-number repair bypassed the comparison fallback (2026-10-20)

The next owner attempt failed at 08:46:00 UTC. Safe logs show seven structural
errors on the first draft (financial period/currency/scale), then eight on the
repair (financial period/currency plus uncited_number). Five generator requests
used 60,136 input / 1,596 output tokens; zero judge calls, 28.89 seconds. The
fallback flag was false: its original classifier excluded every uncited number.
The log did not retain claim indices, so the exact bad number and whether it
shared a claim with the financial-context errors cannot be recovered.

Completed the approved no-figures fallback for the narrowly related case: an
uncited number on a claim already rejected for financial context may be
discarded along with all other draft claims, returning explicit unverified-figure
gaps for every comparison target. Uncited numbers on other claims, unknown
sources, nonverbatim quotes and other failures still block the fallback. This
does not accept unsupported figures or broaden the conditions for factual
answers. Safe logs now include claim indices for fixed structural-error kinds.

Offline orchestration regression first failed on the financial-context plus
uncited-number repair, then passed after the classifier change. Both drafts'
figures stay hidden, all five targets remain, and no extra inference is required.
Negative cases retain failures for a separate uncited claim and an invented
source quote. The precise live draft is unavailable; this is coverage for the
observed error combination with explicit claim binding, not a claim of live
success. No paid requests were made. The financial comparison remains incomplete
and phase-six quality stays open.
Verification: 268 offline tests passed, 15 integration deselected; Ruff check
and format passed. Backend explicitly restarted after the final code changes.

### Comparison refusal after context hardening (2026-10-20)

The owner's next five-year MSFT frontend attempt failed with GroundingRejected:
six generator requests (82,033 input / 1,691 output tokens), zero grounding
requests and 33.35 seconds. This establishes rejection at structural validation
before judging; the exact failed checks were not retained in the old log and
cannot be reconstructed from those counters. Do not claim the model repaired
the units/periods correctly or that a particular recognizer caused this turn.

Safe turn logs now retain fixed structural-error categories/counts per attempt,
without raw rejected text, and a financial-context-fallback flag. The owner
approved returning explicit unverified-figure gaps for each requested comparison
target after the bounded repair, but only when all remaining errors are financial
period/currency/scale context checks. This path discards every draft claim and
does not assert the information is absent from the filings. Other structural
failures, unsupported synthesis, judge rejections and service errors still fail
closed. The fallback adds no model calls or retry budget. Offline regressions
first reproduced the exhausted-repair failure, then verified all five targets
survive without figures/citations; an additional uncited-number failure blocks
the fallback. The actual failed turn's precise causes remain unknown and live
fallback behavior remains unverified. Phase-six answer quality remains open.
Verification: 266 offline tests passed, 15 integration deselected; Ruff check
and formatting passed. No paid requests were made during this follow-up.

### Financial comparison context and synthesis citations (2026-10-20)

Owner-reported comparison answers exposed two accepted defects. Read-only
inspection of the saved replies confirms that the MSFT financial claims cite
flattened rows without fiscal-period/unit headings, and the Apple/NVIDIA
interpretation cites only Apple despite NVIDIA evidence attached to other claims.
All ten company/corpus-year targets in the supplier response are represented by
cited facts or explicit gaps; the defect is support for its final synthesis.

Added pre-judge checks for explicit financial periods in prose and source quotes,
currency and matching scale words for monetary figures, and each named pilot
company's citation coverage within a cross-company interpretation. Percentage
figures need periods but not currency. Descriptive filing lookups do not require
fiscal periods, ordinary facts may mention another company's role, and verified
calculator output retains its existing separate checks. Existing bounded repair
receives specific failures; unsupported drafts remain hidden. Instructions now
require headings or specific gaps for ambiguous table rows. Removed the stale
frontend 'Test replies only' footer.

Offline replay of the actual saved citations rejects all three MSFT financial
claims and precisely the unsupported supplier synthesis. The focused tests first
reproduced seven failures before the fix; subsequent regressions include accepted
unit/period context, valid two-company citations, descriptive Azure/revenue
lookups and percentage dates. These are conservative English-pattern checks, not
a semantic parser or a replacement for judge calibration. They prevent the
observed acceptance defects; they do not establish that a live model will repair
the answer successfully or retrieve missing financial headings. No inference
calls, re-ingestion, model changes or credit spending were performed. Live
comparison quality and the phase-six gate remain open.
Final verification: 263 offline tests passed, 15 integration tests deselected;
Ruff check/format, frontend typecheck, lint and production build passed. Vite
retains its bundle-size advisory. The first full test attempt encountered an
unrelated Windows temp-directory permission error; the passing run used a new
isolated test directory. No dependency or configuration changes were needed.

### Owner-approved direct calculator output (2026-10-20)

Owner-reported frontend result: **65.56%**, with three citations. This matches
the reported annual increases: USD 19.8 billion gross margin divided by USD
30.2 billion revenue, multiplied by 100. It is a ratio of increases, not the
company's gross-margin percentage.

The accepted live turn at 07:46:04 UTC recorded verified numeric inputs,
four generator requests, one grounding request and 14.33 seconds. It did not
include the new completed-calculation count. The worker restarted immediately
afterward and logged application startup at 07:46:13 UTC. Record this as a
successful calculation answer and numeric-source verification, not proof of
the new direct-output protocol. That protocol remains offline-verified and
awaits live confirmation during normal use. No additional paid calls were made
to investigate this result; the broader answer-quality gate stays open.

The owner approved making the calculator directly submit its verified result.
`calculate` is now a strict output tool, unavailable before a verified input pair
exists and the sole output after successful preparation. Its two arguments have
dynamic enums containing the ordered verified fact IDs. It calls the existing
Decimal calculator, creates a server-owned typed calculation claim with exact
input references, and terminates generation. There is no extra model round trip
to rewrite the result, choose a calculation kind, or resubmit a calculation ID.

The existing run_grounded structural checks, record recomputation, exact input
pair approval and citation rendering remain. Ordinary prose uses final_result;
failed numeric preparation can still return controlled gaps. Invalid or reversed
fact IDs cannot create a calculation record. No arbitrary arithmetic inputs or
new operations were added. Safe logs now include a completed-calculation count.

Offline SDK transport/orchestration tests assert exactly two main-agent model
requests (prepare_calculation, calculate), no request afterward, ordered ID enums,
strict schemas, the 65.56% result and retained citations, with and without prior
Azure-2025 history and a stale proposed 2025 filter. Numeric selection is mocked
separately and its existing source-verification checks remain covered. No paid
calls were made. Live confirmation and the broader phase-six quality gate remain
pending.
Verification: the full offline suite passed 247 tests (15 integration deselected)
before the two new invalid-ID cases were added. The final 51-test focused
selection/grounding/calculator suite passed, including those cases; the four
calculator protocol cases then passed with explicit assertions for three source
citations and one completed calculation. Ruff and formatting passed.

### Numeric retrieval guard verified live; submission failure remains (2026-10-20)

The next reported generic error now has a useful attempt trace. The model
proposed MSFT/10-K/corpus-2025 filters; the guard removed the year restriction.
Retrieval returned corpus-2025, the known corpus-2022 evidence chunk, and a
corpus-2023 chunk. The attempt outcome is verified_inputs. Thus the stale-filter
pattern occurred in this live turn, and the guard plus numeric grounding worked.

The turn then failed as UnexpectedModelBehavior/output_retries_exhausted with a
semantic_validation retry reason. Counts: five generator requests (21,430 input /
610 output tokens), one grounding request (1,608 input / 164 output tokens), two
tool calls, 20.33 seconds. The fixed diagnostic category does not retain the
specific final semantic rejection, and completed calculation records are not
logged, so do not assert its exact formatting/ID mistake from this log alone.

Proposed next change, pending owner contract review: make calculate an output
tool that accepts only the ordered verified fact IDs and returns a server-built
GroundedAnswer. This removes the redundant model round trip to resubmit a
calculation ID, kind and free-text claim. Existing source checks, Decimal
recomputation and citation rendering would remain; ordinary prose output would
keep its existing path. Owner involvement is opt in because the internal tool
contract changes. No implementation of this proposal or paid calls occurred
during this diagnostic follow-up.

### Numeric year-scope guard and attempt trace (2026-10-20)

Continued the false-refusal investigation without paid calls. Offline reproduction
demonstrated that a model-proposed MSFT corpus-2025 restriction on the current
fiscal-2022/2021 question excludes the parseable 2022 source and leads to an
ambiguous-input refusal. The old live call's actual filters remain unknown.

Numeric preparation now removes unmentioned proposed corpus years when the
current question explicitly names years, widening search rather than converting
fiscal periods into corpus filters. Explicit source years, bounded ranges,
undated follow-ups and explicit references to the same/that filing are preserved.
Ticker/form and verified fiscal filters are unchanged. This is a narrow lexical
guard, not automatic semantic query planning. A tool notice reports adjustments.

Each attempt retains proposed/effective filters, adjustment status, returned
chunk IDs/corpus years, and its outcome/rejection stage in safe diagnostics and
the turn log. No raw question/model-assessment/provider-body logging was added.
Existing extraction, source checks, calculator verification and budgets remain.

The offline SDK/tool/orchestrator regression includes preceding Azure-2025
history and an explicitly simulated stale 2025 tool filter; it retrieves the
2022 facts, verifies them and renders 65.56%. Other tests preserve a deliberately
requested 2025 filing, ranges and source follow-ups, trace candidate-extraction
rejection, and prevent fiscal/corpus substitution. This guards a proven failure
pattern; it does not prove the previous live call used that filter or establish
that the live ratio question now succeeds. No paid evaluation was run.
Final verification: 247 offline tests passed, 15 integration tests deselected;
Ruff and formatting passed. Backend health returned HTTP 200 after code reload.

### False refusal on Microsoft annual-increases ratio (2026-10-20)

After the successful Azure lookup in the same thread, the owner asked for the
ratio of Microsoft's reported gross-margin increase to revenue increase for
fiscal 2022 versus fiscal 2021. The app returned an ambiguous_figures refusal
labeled MSFT corpus 2025. The saved question confirms explicit 2022/2021 periods;
the preceding question concerned the 2025 Azure filing.

The accepted refusal log records three generator requests (10,539 input / 223
output tokens), one tool call, zero grounding requests and 10.36 seconds. The
numeric flow stopped before independent fact verification. Exact retrieval
filters, returned passage IDs and the numeric rejection reason were not retained,
so stale 2025 filtering is a plausible hypothesis, not a proven diagnosis.

Read-only corpus inspection confirms chunk dca204b5-c187-5dc8-8d88-62a09e01f8cd
in the MSFT corpus-2022 filing contains the explicit heading "Fiscal Year 2022
Compared with Fiscal Year 2021", revenue increase $30.2 billion and gross-margin
increase $19.8 billion. Ratio: 19.8 / 30.2 = 0.655629..., or 65.56%. An offline
probe through actual expose_groups/numeric_candidates preserves both amounts
with one primary source and with a three-group budget simulation. Thus the
evidence exists and is mechanically parseable if retrieved; the refusal is not
a demonstrated corpus gap. No paid calls or app changes were made during this
investigation. Numeric retrieval/selection reliability remains a failed live gate.

### Verified successful Azure lookup (2026-10-20)

The owner supplied the latest three-claim Azure reply and asked whether judging
had been skipped. Read-only inspection confirms the saved question/reply exactly
match the supplied example. The corresponding accepted turn log records:

- Answering: gpt-5.4-mini, 2 requests, 10,548 input / 245 output tokens.
- Grounding: gpt-4.1-mini, 1 request, 2,349 input / 265 output tokens.
- Duration: 15.14 seconds; accepted, no recorded failure.

The grounding judge DID run. The current acceptance path requires exact verdict
coverage and supported decisions for all ordinary factual claims before rendering.
Read-only inspection of the saved citations independently confirms each claim
matches its attached excerpt: Azure's cloud-platform definition, the listed
datacenter-backed services, and IaaS/PaaS consumption affecting revenue. All three
sources identify the same MSFT 10-K corpus-2025 filing dated 2025-07-30; no fiscal
period is inferred. The invented fiscal-heading gap is absent.

This lookup passes the observed live source-support check. One successful example
does not establish broad grounding reliability or close the full phase-six quality
gate. No additional inference calls were made for this investigation and no app
behavior was changed. A judge verdict is a backend step, not a separate visible
chat message; saved-answer replay also does not invoke a new judge.

### Approved single GPT-5.4-mini HTTP probe (2026-10-20)

The owner approved one direct diagnostic request using the captured first-call
app schema, capped at 128 completion tokens with no retries or tool execution.
It returned HTTP 400 naming `reasoning_effort`; the code was not among the safe
allowlist and was recorded as unclassified. No success/usage payload was returned.
The retained error does not distinguish an unsupported parameter from an
unsupported value, nor prove all subsequent request parameters are valid.

The narrow compatibility adjustment uses the documented default reasoning mode
(none) and OMITS reasoning_effort entirely for this model in the current Chat
Completions integration. The answering cap remains 4000 and grounding remains
gpt-4.1-mini/2000. Configuration explicitly requires this default for GPT-5.4-mini
and its snapshots; it also rejects disabling reasoning for nano. No endpoint,
retry budget or prompt contract was changed. Offline HTTP capture verifies that
both reasoning_effort and temperature are absent. No further inference request
was made after the approved probe; live acceptance remains unverified.
The prior low-reasoning trial settings recorded below are superseded.
Verification: 238 offline tests passed, 15 integration tests deselected; Ruff
and formatting passed. FastAPI restarted with none/4000 answering settings,
gpt-4.1-mini grounding, and health HTTP 200. Only the one approved inference
request was attempted in this follow-up.

### GPT-5.4-mini HTTP rejection (2026-10-20)

The first reported failure after the trial configuration is DIFFERENT from the
nano output-validation failure: `ModelHTTPError`, zero reported generator and
judge usage, 1.8 seconds. The previous log did not retain HTTP status/body codes,
so its exact provider rejection cannot be recovered retrospectively. A free
GET model-metadata lookup recognized gpt-5.4-mini (HTTP 200); that is not proof
of inference authorization. An offline transport capture confirmed low reasoning,
no temperature, and seven tool definitions including final output.

Safe diagnostics now retain HTTP status, allowlisted error codes and parameter
paths, without provider messages, bodies or unknown values. Both nested and flat
error-body fixtures plus redaction checks pass. No model settings or inference
behavior changed in this follow-up. A single direct diagnostic request using
the captured schema, capped at 128 output tokens with no retries or tool
execution was subsequently approved and run; results and the compatibility
adjustment are recorded above.

### Owner-requested GPT-5.4-mini trial preparation (2026-10-20)

The owner selected gpt-5.4-mini for answering and authorized related setting
adjustments. The actual environment already contained that model choice;
grounding remains gpt-4.1-mini. Official model documentation lists reasoning
none/low/medium/high/xhigh, not minimal. The installed SDK profile incorrectly
advertises minimal support for this model, so central configuration now rejects
minimal for the alias and its snapshots before making requests.

The local environment was adjusted only for ASSISTANT_REASONING_EFFORT=low and
ASSISTANT_OUTPUT_TOKENS=4000 (from 3000), providing bounded space for reasoning
and typed output. Grounding stays capped at 2000, the overall deadline stays
120 seconds, and tool/request/retry limits are unchanged. Offline transport
fixtures check supported reasoning, omission of temperature, a 4000-token
completion limit, and immediate stopping on truncated responses across all
four agent roles. No paid model evaluation was run and live quality remains
unverified.

Trial setup verification: 235 offline tests passed, 15 integration tests
deselected; Ruff and formatting passed. FastAPI restarted and health returned
HTTP 200. Effective settings were verified without printing secrets.

### Generic service failure diagnosis (2026-10-20)

The latest live generic-service event records `UnexpectedModelBehavior`, nano
answering, eight generator requests (31,018 input / 733 output tokens), zero
grounding requests, and 27.64 seconds. Two preceding attempts instead reached
grounding and ended as `GroundingRejected`. The generic event therefore failed
in answering before the independent grounding judge, not as the same source
verification rejection. Its original exception reason/cause was discarded by
the existing sanitization boundary; the exact live subreason is unavailable.

Offline reproduction uses the real answering agent/SDK and TestModel, then the
real `generate_reply` exception boundary. Missing and fabricated request_quote
outputs exhaust the bounded output retry and produce UnexpectedModelBehavior,
the same service category observed live. This makes output-contract rejection
a plausible explanation, not a proven reconstruction of the live response.

Safe diagnostics now preserve fixed SDK failure categories and allowlisted
validation field/error codes from exception causes. They never log rejected
values, request quotes, raw exception messages or provider bodies. Semantic
request-anchor failures have a fixed reason. A red/green regression demonstrates
that these details were previously lost; an adversarial fixture verifies redaction.
No model, retry budget, browser behavior or answer policy was changed. No paid
API calls were made; live semantic correctness remains unresolved.
Verification: 223 offline tests passed, 15 integration tests deselected; Ruff and
formatting passed. The reloaded backend health endpoint returned HTTP 200.

### Request provenance implementation (2026-10-20; live confirmation pending)

Following the owner's instruction to fix the issue, model-written gaps now use
the `RequestedGap` output contract with required `request_quote`. Final-output
validation checks a nonblank, literal span of the actual question (whitespace
normalized). Fabricated fiscal-heading requests and missing anchors are rejected
before an answer is accepted, even when its factual claims have valid citations.
Server-generated uncovered comparison targets retain their code-owned gaps;
they cannot be supplied as an unanchored gap through the model's output schema.

Final judging now places proposed claims/evidence/gaps in an assistant-role
message and the exact actual question in the final user-role message. Structured
context separates `actual_user_request.text` from `proposed_answer`; instructions
forbid treating proposed gap text as the user's request. A warranted model gap
must independently return the same literal request quote; missing, fabricated
or mismatched judge anchors invalidate that approval. An anchor proves provenance
only; semantic relevance is still probabilistic and must be reviewed live.

Verification: 220 offline tests passed, 15 integration tests deselected. Ruff and
formatting passed. Tests cover invalid/missing/blank quotes, genuine requested
pricing, retained missing target coverage, exact judge anchor matching and real
SDK HTTP message serialization with the actual user request last. The final
selection regression was strengthened to include supported Azure claims.
No paid calls were made for this implementation, no model/config change or new
dependency was added, and existing output/repair budgets remain unchanged.
Saved replies are unchanged. The live answer-quality gate remains OPEN.

### Approved two-call real-source replay (2026-10-20)

The owner approved exactly two further judge-only calls on the saved real-source
reply, with no retrieval, generation or retries and 2,000 output tokens per call.
Two claims were reconstructed from saved rendered paragraphs and their four
actual citation excerpts/metadata; the saved record does not retain the original
typed claims or judge verdict. This replay therefore approximates that request
without claiming byte-for-byte identity.

| GPT-4.1-mini variant | Observed result | Input tokens | Output tokens |
|---|---|---:|---:|
| Current combined claim/gap judge | Supported both claims; incorrectly accepted fiscal-heading gap | 2,267 | 290 |
| Focused gap-only instructions | InvalidSupportReport; no valid comparison verdict | 1,448 | 241 |

The combined judge's gap assessment explicitly says: "The user requested an
explicit quoted fiscal-period heading stating what Azure provides for fiscal
year 2025." That requirement exists only in the proposed gap, not in the actual
question. This supplies direct evidence of source-of-request confusion in this
sample, rather than merely insufficient retrieval. Increasing model capability
alone has not solved it. The focused variant did not pass output coverage
validation; its generated report was unfortunately not retained before validation
raised. The probe now retains reports before validation for any future explicitly
approved run; neither call was repeated.

Total: 3,715 input / 531 output tokens, exactly two calls. No app behavior or
configured model was changed. Focused verification is NOT a proven fix. Next
design work should keep proposed limitations distinct from actual user requests
and verify an exact request anchor before accepting invented requirements.
Ignored probe/artifact: `data/chunks/assistant/azure_real_gap_probe.py` and
`data/chunks/assistant/azure-real-gap-probe.json`.

### Live failure after grounding-model switch (2026-10-20)

The owner repeated the original Azure lookup after switching grounding to
gpt-4.1-mini. The reply retained an invented requirement for an explicit
fiscal-period heading. The latest saved question is exactly the original
lookup. The matching accepted live log records nano answering (11 requests,
139,027 input / 739 output tokens) and gpt-4.1-mini grounding (one request,
2,279 input / 247 output tokens). Current code checks exact gap-verdict
coverage before accepting. The detailed verdict was not retained in that log;
its rationale cannot be recovered. This is a failed live check, not evidence
that switching models solved gap relevance.

Read-only inspection captured the actual saved question, answer and four
citations in ignored `data/chunks/assistant/azure-live-accepted-replay.json`.
All four citations identify MSFT 10-K corpus 2025 with nullable fiscal-year
metadata. No paid calls were made during this follow-up investigation. The
previous three-call allowance had been used. The owner subsequently approved
two real-fixture judge-only checks; results are recorded above. No further
production behavior has been changed.

### Approved three-call judge-only comparison

The owner explicitly approved at most three judge-only calls, no retrieval,
answer generation or retries, with 2,000 output tokens per call. The fixed
synthetic fixture uses the owner's pasted Azure description as both claim and
evidence, synthetic MSFT/corpus-2025 source identity, the exact original question,
and the latest invented fiscal-period gap. It tests the distinction between
source selection and a fiscal assertion, not retrieval accuracy or full-chat
quality. No configured model was changed.

| Judge / reasoning | Observed result | Input tokens | Output tokens (includes reasoning) |
|---|---|---:|---:|
| gpt-5-nano / minimal | UnexpectedModelBehavior; no usable structured verdict | 1,648 | 277 |
| gpt-5-nano / low | Incorrectly marked the fiscal gap warranted; claim supported | 1,648 | 628 (448 reasoning) |
| gpt-4.1-mini / nonreasoning | Correctly supported the descriptive claim and rejected the unrequested fiscal gap | 1,564 | 198 |

Total reported usage: 4,860 input and 1,103 output tokens. Exactly three calls
were attempted. The minimal failure's detailed response was not retained, so its
specific malformed-output cause is unknown. Nano/low's assessment explicitly
demanded fiscal binding despite the question selecting a filing. GPT-4.1-mini
explicitly distinguished those cases. One fixture/one sample per setting does
not prove general reliability, but supports testing gpt-4.1-mini as grounding
judge while keeping nano as the answering model. Broader quality gates remain
open. Ignored reproducible probe/results: `data/chunks/assistant/azure_gap_judge_probe.py`
and `data/chunks/assistant/azure-gap-judge-probe.json`.

Third owner observation: the Azure lookup still rendered a gap demanding fiscal
2025-versus-2024 support, despite the question selecting the 2025 filing rather
than requesting that comparison. This is a LIVE FAILURE of gap relevance;
prior mocked verdict tests did not establish nano judgment quality. Inspection
found an unconditional judge instruction requiring fiscal-period binding and a
general per-period answering instruction. Both are now conditional on actual
fiscal assertions/comparisons. Descriptive source selection is explicitly
distinguished from fiscal-period claims in answering and judging instructions.

Focused offline verification: 44 tests passed; Ruff passed. The exact fiscal-gap
text was added to the orchestration contract fixtures, which exercise a supplied
rejection rather than predict nano's decision. No paid evaluation was run and
live resolution remains UNVERIFIED. The owner should not treat this prompt change
as proof that the nano/nano stack reliably rejects invented gaps.

Second gap follow-up: the owner observed an Azure answer followed by
`missing_detail` asking to confirm E1/E2 and explore optional Foundry nuances.
The previous structural fix was insufficient: nonempty text is not proof of a
genuine unanswered request. The final judge now receives the actual gaps and
returns a separate indexed relevance verdict for each, alongside existing claim
verdicts. It must reject internal research instructions, citation confirmation,
and unrequested elaborations while preserving genuinely unresolved requested
aspects. Gap verdict coverage is validated exactly; failures cannot silently
accept or discard gaps. The existing single repair handles rejected gaps.

Offline verification: 210 passed, 15 integration tests deselected; Ruff and
formatting checks passed. The exact owner-provided gap is replayed through the
orchestrator with a rejecting judge fixture and yields only the supported Azure
answer after repair. A requested pricing gap is preserved with one combined
judge call. These are contract tests, not evidence of live nano judgment quality.
No paid calls were made; existing saved replies are unchanged.

Follow-up: the owner observed correct Azure citations accompanied by a blanket
missing-evidence warning for MSFT corpus 2025. Structural validation now rejects
blanket `missing_evidence` gaps overlapping cited targets (including untargeted
gaps when claims exist). A genuinely unresolved aspect uses bounded
`missing_detail` and renders as a retrieval limitation, not an assertion that
the filing omits it. Uncovered company/year targets and unverified fiscal-year
coverage remain distinct. No gap is silently removed and no citation is upgraded
to proof of complete coverage. The existing single bounded repair handles the
contradiction before invoking the judge.

Verification: 201 offline tests passed, 15 integration tests deselected. After
adding three detail-input boundary cases, all 15 focused contract/orchestration
tests passed. Ruff and formatting checks passed. No paid calls were made.
The offline Azure orchestration fixture confirms the repaired answer renders
its citation without the blanket warning; live model behavior remains to be
reviewed. Existing saved replies are unchanged.

Owner-selected answering and grounding models: `gpt-5-nano`. Three failed browser
turns included one timeout and two service failures. Both service failures recorded
exactly 2,000 judge output tokens. This strongly suggests exhaustion of the judge's
completion allowance by reasoning; the old logs did not capture finish reasons,
so the exact live cause is not yet proven.

Offline HTTP fixtures reproduce blank reasoning-only and partial-tool responses
with `finish_reason=length` across all four agent roles. Requests now explicitly
use minimal reasoning, preserve existing token caps, and stop immediately on
truncation without output retries or grounding repair. Safe logs capture failure
type and role/model/token-limit details; the browser shows a distinct limit error.
Tokens from aborted responses remain accounted for; the SDK's request count only
includes committed steps.

Verification: the final full offline suite passed (196 tests, 15 integration
tests deselected). Ruff, frontend type checking and lint passed. Backend and
frontend returned HTTP 200 after the backend restart; effective settings remain
nano/nano with minimal reasoning. No paid API calls
were made for this investigation. Nano end-to-end reliability remains unverified;
the answer-quality gate remains open. Owner review verdicts are unchanged.

## Latest reliability corrections and verification (2026-10-19)

The source contract now uses short, request-scoped evidence IDs. The provider's
strict output schema enumerates the available evidence and completed calculation
IDs; code attaches the immutable quotes and source identity. Unknown IDs cannot
authorize citations. Complete displayed sentences/lines receive IDs; truncated
sentences remain previews without IDs. At most 900 selectable spans keep the
request inside provider enum limits. No source text was cleaned or re-embedded.

Factual comparisons are checked per filing. The backend labels each block from
source metadata and expands grouped missing periods into explicit gaps. It does
not infer fiscal years from corpus labels. Repair now includes the judge's
bounded explanation plus the evidence-ID catalog and filing identity.

Calculation safeguards now recompute stored results/formulas/displays and preserve
accounting negatives in factual checks. Numeric-input verification uses a dedicated
scope/measure judge, distinct from final prose validation. Parsing and mechanical
checks bind narrative amounts to inline units and quoted fiscal headings. Final
arithmetic can reuse semantic approval only for the exact registered pair and
operation, after fresh deterministic checks. Unknown metadata is omitted from
judge requests; citations still show unverified fiscal-year/page fields.

**Final offline verification: 185 passed, 15 integration tests deselected.** Ruff
check and formatting passed. Five marked live tests passed together:

| Check | Latest outcome |
|---|---|
| Eleven-case application support calibration | Passed: two supported facts accepted, nine unsupported cases rejected |
| Numeric input with wrong requested measure/company scope | Rejected as expected |
| Answering agent facing source-injected instructions | Passed |
| Developer-assembled calculation over real source quotes | Passed; not an autonomous-answer score |
| Autonomous Microsoft ratio of reported increases | Answered 65.56%, exact 19.8 / 30.2 USD-billion inputs, three citations |

The autonomous run took about 12 seconds: four generator requests, one numeric
input-verification request, two tools, no repair. Raw evidence is retained in
`final-retrieval-agent-live.txt` and `autonomous-ratio-latest.json` under ignored
`data/chunks/assistant/`. The application calibration includes a deterministic
rejection of the forged record; it does **not** claim the raw LLM judge became
reliable at validating forged arithmetic records.

Final answer checks and remaining limitations:

- Azure lookup S01 returned an answered reply; Tesla 2028 S04 returned an explicit
  empty-target refusal (`evidence-task-smoke.json`). The later preview restriction
  passed the marked source-injection/lookup path; no new authenticated browser
  acceptance is claimed or requested for the unchanged citation wire format.
- S02 initially returned an accepted partial answer after the improved repair
  feedback, but review found its third claim used only the cut-off quote
  “Restrictions on international trade can increase the…”. **That claim is not
  accepted evidence.** The preview-only fix prevents selecting that incomplete
  span. The final S02 run failed grounding safely
  (`final-supplier-preview-check.json`); this remains an unresolved quality case.
- A paired Q04 trial used the current default `gpt-4o-mini` and an evaluation-only
  `gpt-4.1-mini` answering model with the same default judge. **Both failed
  grounding**, so this trial does not justify changing production models
  (`answer-model-comparison.json`). The default draft still overstated Azure
  support; the alternative still misattributed a period. No answer was saved.
- A saved supplier-urgency draft also exposed a raw judge false positive despite
  more explicit instructions (`supplier-judgment-replay.json`). Its multi-filing
  factual claims are now rejected structurally. Modest, labeled interpretations
  still require semantic evaluation; no mathematical guarantee is claimed.

The additional full sweep during development (`client-questions-evidence-final.json`)
is an **intermediate run before the ID-enum and repair corrections**, not a final
quality result: Q01/Q04–Q10 were service/output-contract failures, Q03 failed
grounding, and Q02 returned insufficient evidence. A shorter interrupted sweep
and targeted diagnostics are retained separately. Subsequent targeted Q04/Q07
runs reached controlled grounding rejection rather than those contract failures.
Do not compare these mixed-version artifacts as an answer-quality score.

The final code has not passed a fresh ten-question quality review. Further broad
paid sweeps were stopped once the remaining comparison failure was reproduced
and the paired model trial did not solve it. **The claim-support quality gate
remains open; owner/browser review is complete.** Models, actual environment,
database schema, dependencies and corpus remain unchanged.

## Verification after owner acceptance (2026-10-19)

All five manual browser reviews passed according to the owner. The current
offline suite passed **169 tests, 14 integration tests deselected**, using a fresh
local pytest temporary directory after Windows denied access to its default
temporary directory. Assistant/grounding Ruff checks and formatting passed.
Earlier pending-browser statements below are historical.

The original five-case independent-judge calibration passed once. The expanded
seven-case calibration failed: it accepted the forged calculation record again,
while correctly rejecting wrong factual scale, unsupported causality/prior year,
partially supported compound content and a positive claim about an accounting
negative. Artifacts: `judge-calibration-20261019T055944571901Z.json` and
`judge-calibration-20261019T060106149029Z.json` under `data/chunks/assistant/`.
The forged record bypasses the calculator boundary and cannot be created through
the current guided calculator. This still fails the independent-judge expectation;
no expectation was weakened and no repeated paid retries were used to select a pass.

## Current ten-question sweep: guided implementation (2026-10-19)

Command, from `backend/`:

```powershell
.venv/Scripts/python scripts/smoke_assistant.py --cases ../docs/evaluations/retrieval-cases.json --output ../data/chunks/assistant/client-questions-guided-review.json
```

All ten cases completed without chat writes or changes to application code during
the run. **Eight controlled grounding failures, one automatically accepted partial
answer and one insufficient-evidence reply; no service errors.** This is not a
quality pass, and the prior sweep is retained below for history.

| Case | Automatic outcome | Accepted claims / gaps | Generator / judge calls | Seconds |
|---|---|---:|---:|---:|
| Q01 | controlled grounding | 0 / 0 | 7 / 0 | 49.18 |
| Q02 | controlled grounding | 0 / 0 | 6 / 0 | 57.82 |
| Q03 | controlled grounding | 0 / 0 | 14 / 0 | 53.86 |
| Q04 | partial | 2 / 1 | 5 / 1 | 30.73 |
| Q05 | controlled grounding | 0 / 0 | 6 / 0 | 36.98 |
| Q06 | controlled grounding | 0 / 0 | 8 / 0 | 82.31 |
| Q07 | controlled grounding | 0 / 0 | 7 / 0 | 37.95 |
| Q08 | controlled grounding | 0 / 0 | 6 / 1 | 39.01 |
| Q09 | controlled grounding | 0 / 0 | 14 / 0 | 45.93 |
| Q10 | insufficient evidence | 0 / 2 | 13 / 0 | 31.22 |

Evidence review of this run:

- Q01/Q02: narrative-only numeric preparation correctly declined to infer table
  columns. Subsequent factual drafts still used nonverbatim quotes; these failed
  validation. No computed result was accepted.
- Q03/Q07: quotes were attached to incorrect chunk IDs, including an incorrectly
  copied ID during repair; uncited numbers/periods also remained. Q07 therefore
  does not pass the supplier-comparison check.
- Q05/Q06/Q09: quotation and/or explicit target-coverage checks rejected the
  drafts. Requested company/year coverage is not demonstrated by a rejected draft.
- Q08: repair passed structural validation, but the judge rejected two of four
  claims as unsupported. No partial draft was displayed or persisted.
- Q04: the accepted partial answer has six source references, but its first claim
  combines general company/product descriptions into an Azure/AI evolution story.
  Several quotes do not explicitly establish Azure-specific changes; a single
  datacenter expansion statement also does not establish an increasing trend.
  One broad gap groups all five years rather than explaining each missing period.
  This automatic acceptance is **not accepted evidence of a correct comparison**.
- Q10: refusing to assert that generative AI caused improved margins is cautious,
  but this reply contains no cited evidence and identifies only GOOGL/MSFT 2023
  gaps. It does not answer what evidence exists across the requested companies.
  The refusal is not a complete or verified corpus-wide answer; no semantic judge
  ran because it contained no claims.

Known returned usage: generator **86 requests, 1,043,712 input / 25,720 output
tokens**; grounding **2 requests, 4,593 input / 254 output tokens**. Retrieval
embedding/keyword usage is recorded separately per case. No billed-cost estimate
or ranking/quality improvement is inferred from these counts.

Next technical work should address reliable quote/source selection, explicit
comparison coverage and semantic-support calibration. Preserve exact-quote and
period/unit checks; do not resolve these failures by accepting unsupported drafts.
No additional paid full sweeps, model changes or corpus rewriting were performed.

## Guided calculation implemented (2026-10-19)

The owner chose the guided numeric-fact flow. The backend now enumerates narrative
amount candidates directly from observed source text, with exact quotes, currency
or percentage units and explicit period headings. A no-tool model selects two
candidate IDs and supported scope. Mechanical checks and the independent judge
must accept them before request-scoped fact IDs are issued. The calculator accepts
only the ordered verified pair; it cannot accept new amounts or metadata.

For explicit arithmetic requests, provider tool choice enforces preparation,
calculation, then final output. Missing inputs allow a bounded retry or an explicit
gap. Candidate enumeration does not infer table columns or fiscal years, and the
selector cannot mentally derive additional inputs. The internal ratio operation
is now named `ratio_percent`, avoiding confusion between a ratio of changes and
a company's reported margin. The judge evaluates the same canonical calculation
text rendered by the backend, with the immutable record and actual cited quotes.

The original reported-increases question now passed **two autonomous live checks**:
the CLI artifact `data/chunks/assistant/calculation-guided-canonical.json` and
`test_autonomous_guided_ratio_uses_verified_inputs`. Both returned an answered
65.56% from $19.8 billion / $30.2 billion, consolidated Microsoft, explicitly
fiscal 2022 compared with fiscal 2021. Three citations cover the comparison
heading and the two reported increases. The recorded CLI run used two tools,
four generator requests (including the selector), two judge requests and about
14 seconds, with no repair. These are autonomous results, unlike the earlier
developer-assembled fixture. Neither evaluation wrote chat history.

The Azure lookup also passed after the guided implementation; local artifact:
`azure-after-guided-calculation.json`. Earlier failed guided trials remain in
`calculation-guided-first.json`, `calculation-guided-enforced.json`,
`calculation-guided-candidates.json` and `calculation-guided-ratio.json`. Some
returned incorrect insufficient-evidence replies; they are not counted as quality
passes. The final autonomous success does not erase them or establish general
answer reliability.

The owner accepted the earlier calculation fixture's evidence after verification
and subsequently confirmed all five browser reviews, including the new guided
calculation, source/history restoration and interruption recovery. No additional
manual review is outstanding for those cases.
Final offline verification: **169 passed, 14 integration tests deselected**;
Ruff check and formatting passed. The separately selected autonomous live test
passed. Backend health returned `status: ok`.
No model configuration, corpus, database schema or dependencies changed. The
broad client-question quality and independent-judge calibration gates remain open.

## Targeted Azure quote fix (2026-10-19)

The owner reported a grounding rejection for: “What does Microsoft’s 2025 filing
say Azure provides? Cite the supporting passages.” A repeat set reproduced it
(2/3 accepted), and a traced failure showed that the draft joined real sentences
while omitting an intervening revenue sentence. The same invalid quotation was
repeated during repair. This was a non-contiguous quote, not missing Azure evidence.

The output-field description and agent instructions now require a single
contiguous source span per reference. For stitched sentences, validation still
rejects the quote but supplies individually verified, already-observed sentences
as separate-reference repair suggestions. It never accepts a stitched quote or
supplies hidden/reworded text. The independent judge and configured models remain
unchanged.

After the fix, **3/3 consecutive live runs** of that exact question passed both
structural validation and the judge, taking about 11–12 seconds. **151 offline
tests passed, 13 integration tests deselected**, and Ruff passed. The live runs
were read-only and wrote no chats. Local artifacts: `azure-debug-repeat.json`,
`azure-quote-trace.json`, and `azure-debug-after.json` under
`data/chunks/assistant/`. This small targeted check does not establish general
reliability; the broad client-question sweep below has not been rerun or passed.

The frontend also preserves specific SSE error messages through the SDK's
subsequent finish callback, instead of replacing them with “Reply interrupted.”
An SDK-based temporary harness verified service errors, interruption fallback,
and preservation of Stop messages; TypeScript and lint passed. Authenticated
browser confirmation remains pending.

## Calculation frontend blocker (2026-10-19)

Historical investigation record; the guided calculation section above supersedes
the pending implementation decision and this specific numerical blocker.

The owner reported two service failures for the calculation review question.
The prior real-source calculation fixture was assembled by code, not by an
autonomous answering agent; it is not evidence that the browser question works.

Read-only traces identified repeated rejected calculations (11 attempts in the
first trace), unquoted currency/period assumptions, malformed one-operand calls,
and confusion between segment percentages and consolidated reported increases.
The first model query also reduced the question to “gross margin revenue.” A
separate retrieval probe using the complete question ranked the passage containing
the reported $19.8 billion and $30.2 billion increases first.

Corrections now preserve the complete question alongside the first search focus,
retain later query refinement, require two operands in the tool schema, and
disable calculation after rejection until genuinely new evidence is exposed.
Provider requests now explicitly enforce strict tool/output schemas for the
answering agent and judge. An offline HTTP-level regression verifies strict
schemas and required nested fields in the actual OpenAI request body; local
Pydantic bounds and all source checks remain enforced.

**These corrections have not solved the autonomous numerical question.** The
latest configured-model run still failed grounding. An isolated evaluation-only
gpt-4.1-mini answering-model run also failed, omitting required calculator fields
before strict schemas were enabled. It does not establish whether a stronger
model with the corrected protocol would pass. Actual model configuration is
unchanged. No production model switch was made based on those results.

Latest offline run: **156 passed, 13 integration tests deselected**. The Azure
lookup also passed a live regression after preserving the initial question,
before strict schemas were enabled; no authenticated browser regression has been
claimed for the final protocol changes. Traces are retained locally under
`data/chunks/assistant/calculation-debug-*.json` and
`calculation-full-question-retrieval.json`; no evaluation wrote chat history.

Owner decision pending: a guided verified-facts-to-calculator flow (recommended),
or a controlled stronger-model evaluation before redesign. The manual calculation
gate and overall phase-six quality gate remain open. The original source corpus
and fiscal-year/page limitations are unchanged.

## Historical client-question sweep (before guided calculations)

Recorded 10/10 cases after exact-ID repair feedback, numeric diagnostics, comparison-year and calculator-unit hardening. Raw local artifact: `data/chunks/assistant/client-questions-repaired.json`.
**All ten cases failed safely: eight grounding rejections and two service/output-schema failures. The broad answer-quality gate has not passed.**
No answer model was allowed to write chat history during these evaluations.

| Case | Automatic outcome | Claims / gaps | Generator / judge calls | Seconds |
|---|---|---:|---:|---:|
| Q01 | controlled grounding | 0 / 0 | 14 / 0 | 69.34 |
| Q02 | controlled service | 0 / 0 | 14 / 0 | 65.52 |
| Q03 | controlled grounding | 0 / 0 | 6 / 0 | 29.36 |
| Q04 | controlled grounding | 0 / 0 | 8 / 0 | 53.37 |
| Q05 | controlled grounding | 0 / 0 | 8 / 0 | 55.22 |
| Q06 | controlled grounding | 0 / 0 | 7 / 0 | 52.45 |
| Q07 | controlled grounding | 0 / 0 | 14 / 0 | 53.65 |
| Q08 | controlled service | 0 / 0 | 13 / 0 | 58.41 |
| Q09 | controlled grounding | 0 / 0 | 14 / 0 | 52.05 |
| Q10 | controlled grounding | 0 / 0 | 4 / 0 | 43.16 |

Questions and intended coverage: [ten-question worksheet](retrieval-cases.json).

### Q01

Across Apple's 2021–2025 10-Ks, how did the revenue mix between iPhone, Services, Mac, iPad, and Wearables change, and which category appears to have contributed most to any mix shift?

**Controlled failure:** grounding; GroundingRejected. No rejected draft was displayed or saved.

Validation failures: claim 0: uncited numeric tokens 2021. Cite exact supporting source numbers/periods; derived results require calculation kind and a recorded calculation ID; claim 1: uncited numeric tokens 2021, 191973. Cite exact supporting source numbers/periods; derived results require calculation kind and a recorded calculation ID; Preserve comparison target with a cited claim or explicit gap: {"ticker":"AAPL","form":"10-K","corpus_years":[2021]}; Preserve comparison target with a cited claim or explicit gap: {"ticker":"AAPL","form":"10-K","corpus_years":[2022]}; Preserve comparison target with a cited claim or explicit gap: {"ticker":"AAPL","form":"10-K","corpus_years":[2024]}

Validation failures: claim 0: uncited numeric tokens 2021. Cite exact supporting source numbers/periods; derived results require calculation kind and a recorded calculation ID; claim 1: uncited numeric tokens 2021. Cite exact supporting source numbers/periods; derived results require calculation kind and a recorded calculation ID; Preserve comparison target with a cited claim or explicit gap: {"ticker":"AAPL","form":"10-K","corpus_years":[2021]}

### Q02

For Amazon, compare AWS operating income and margin against North America and International from 2021–2025. In which years did AWS appear to fund losses or weaker profitability elsewhere?

**Controlled failure:** service; UnexpectedModelBehavior. No rejected draft was displayed or saved.

### Q03

How did NVIDIA describe demand drivers, customer concentration, and supply constraints for its Data Center business from fiscal 2021 through fiscal 2025?

**Controlled failure:** grounding; GroundingRejected. No rejected draft was displayed or saved.

Validation failures: claim 0: uncited numeric tokens 4, 7, 52. Cite exact supporting source numbers/periods; derived results require calculation kind and a recorded calculation ID; claim 0: Quote is not verbatim source text for chunk 4c415db4-7bcb-52ba-a1cd-4d3deaba615a; claim 1: uncited numeric tokens 5, 83, 58566. Cite exact supporting source numbers/periods; derived results require calculation kind and a recorded calculation ID; claim 1: Quote is not verbatim source text for chunk 58566daa-83bb-5ebd-a660-e6e11d80abc4; claim 2: uncited numeric tokens 5, 107, 1148. Cite exact supporting source numbers/periods; derived results require calculation kind and a recorded calculation ID; Preserve comparison target with a cited claim or explicit gap: {"ticker":"NVDA","form":"10-K","corpus_years":[2021]}; Preserve comparison target with a cited claim or explicit gap: {"ticker":"NVDA","form":"10-K","corpus_years":[2022]}; Preserve comparison target with a cited claim or explicit gap: {"ticker":"NVDA","form":"10-K","corpus_years":[2025]}

Validation failures: claim 0: uncited numeric tokens 4, 7, 52. Cite exact supporting source numbers/periods; derived results require calculation kind and a recorded calculation ID; claim 0: Quote is not verbatim source text for chunk 4c415db4-7bcb-52ba-a1cd-4d3deaba615a; claim 1: uncited numeric tokens 5, 83, 58566. Cite exact supporting source numbers/periods; derived results require calculation kind and a recorded calculation ID; claim 1: Quote is not verbatim source text for chunk 58566daa-83bb-5ebd-a660-e6e11d80abc4; claim 2: uncited numeric tokens 5, 107, 1148. Cite exact supporting source numbers/periods; derived results require calculation kind and a recorded calculation ID; Preserve comparison target with a cited claim or explicit gap: {"ticker":"NVDA","form":"10-K","corpus_years":[2021]}; Preserve comparison target with a cited claim or explicit gap: {"ticker":"NVDA","form":"10-K","corpus_years":[2022]}; Preserve comparison target with a cited claim or explicit gap: {"ticker":"NVDA","form":"10-K","corpus_years":[2025]}

### Q04

Across Microsoft's 2021–2025 filings, what changed in the way the company describes Azure, AI infrastructure, and cloud capacity constraints?

**Controlled failure:** grounding; GroundingRejected. No rejected draft was displayed or saved.

Validation failures: claim 0: uncited numeric tokens 5, 8, 5764, 581122. Cite exact supporting source numbers/periods; derived results require calculation kind and a recorded calculation ID; claim 1: uncited numeric tokens 3, 391, 5098. Cite exact supporting source numbers/periods; derived results require calculation kind and a recorded calculation ID; claim 2: uncited numeric tokens 1, 90, 660, 2024, 2762, 5629. Cite exact supporting source numbers/periods; derived results require calculation kind and a recorded calculation ID; claim 3: uncited numeric tokens 5, 9, 5436, 8466. Cite exact supporting source numbers/periods; derived results require calculation kind and a recorded calculation ID; claim 3: Quote is not verbatim source text for chunk d3a4a724-5e36-5436-8466-9fa53dabcffa; Preserve comparison target with a cited claim or explicit gap: {"ticker":"MSFT","form":"10-K","corpus_years":[2023]}; Preserve comparison target with a cited claim or explicit gap: {"ticker":"MSFT","form":"10-K","corpus_years":[2024]}

Validation failures: claim 0: uncited numeric tokens 5, 8, 5764, 581122. Cite exact supporting source numbers/periods; derived results require calculation kind and a recorded calculation ID; claim 1: uncited numeric tokens 3, 391, 5098. Cite exact supporting source numbers/periods; derived results require calculation kind and a recorded calculation ID; claim 2: uncited numeric tokens 1, 90, 660, 2024, 2762, 5629. Cite exact supporting source numbers/periods; derived results require calculation kind and a recorded calculation ID; claim 3: uncited numeric tokens 5, 9, 5436, 8466. Cite exact supporting source numbers/periods; derived results require calculation kind and a recorded calculation ID; claim 3: Quote is not verbatim source text for chunk d3a4a724-5e36-5436-8466-9fa53dabcffa; Preserve comparison target with a cited claim or explicit gap: {"ticker":"MSFT","form":"10-K","corpus_years":[2023]}; Preserve comparison target with a cited claim or explicit gap: {"ticker":"MSFT","form":"10-K","corpus_years":[2024]}

### Q05

For Alphabet, how did Google Search, YouTube ads, Google Network, subscriptions/platforms/devices, and Google Cloud revenue trends differ across the available 10-Ks?

**Controlled failure:** grounding; GroundingRejected. No rejected draft was displayed or saved.

Validation failures: claim 0: uncited numeric tokens 2021. Cite exact supporting source numbers/periods; derived results require calculation kind and a recorded calculation ID; claim 0: Quote is not verbatim source text for chunk 7f048dc5-208b-5c4e-9016-7e5cafa77d50; claim 1: uncited numeric tokens 2021. Cite exact supporting source numbers/periods; derived results require calculation kind and a recorded calculation ID; claim 1: Quote is not verbatim source text for chunk 7f048dc5-208b-5c4e-9016-7e5cafa77d50; claim 2: uncited numeric tokens 2021. Cite exact supporting source numbers/periods; derived results require calculation kind and a recorded calculation ID; claim 2: Quote is not verbatim source text for chunk 7f048dc5-208b-5c4e-9016-7e5cafa77d50; claim 3: uncited numeric tokens 2022. Cite exact supporting source numbers/periods; derived results require calculation kind and a recorded calculation ID; claim 3: Quote is not verbatim source text for chunk cdda3db2-c14f-5600-92b6-46553451c0be; claim 4: uncited numeric tokens 2021. Cite exact supporting source numbers/periods; derived results require calculation kind and a recorded calculation ID; claim 4: Quote is not verbatim source text for chunk 7e9efd22-4fa5-5f10-a14d-b5030c8e9121; Preserve comparison target with a cited claim or explicit gap: {"ticker":"GOOGL","form":"10-K","corpus_years":[2021]}; Preserve comparison target with a cited claim or explicit gap: {"ticker":"GOOGL","form":"10-K","corpus_years":[2024]}; Preserve comparison target with a cited claim or explicit gap: {"ticker":"GOOGL","form":"10-K","corpus_years":[2025]}

Validation failures: claim 0: uncited numeric tokens 2021. Cite exact supporting source numbers/periods; derived results require calculation kind and a recorded calculation ID; claim 0: Quote is not verbatim source text for chunk 7f048dc5-208b-5c4e-9016-7e5cafa77d50; claim 1: uncited numeric tokens 2021. Cite exact supporting source numbers/periods; derived results require calculation kind and a recorded calculation ID; claim 1: Quote is not verbatim source text for chunk 7f048dc5-208b-5c4e-9016-7e5cafa77d50; claim 2: uncited numeric tokens 2021. Cite exact supporting source numbers/periods; derived results require calculation kind and a recorded calculation ID; claim 2: Quote is not verbatim source text for chunk 7f048dc5-208b-5c4e-9016-7e5cafa77d50; claim 3: uncited numeric tokens 2022. Cite exact supporting source numbers/periods; derived results require calculation kind and a recorded calculation ID; claim 3: Quote is not verbatim source text for chunk cdda3db2-c14f-5600-92b6-46553451c0be; claim 4: uncited numeric tokens 2021. Cite exact supporting source numbers/periods; derived results require calculation kind and a recorded calculation ID; claim 4: Quote is not verbatim source text for chunk 7e9efd22-4fa5-5f10-a14d-b5030c8e9121; Preserve comparison target with a cited claim or explicit gap: {"ticker":"GOOGL","form":"10-K","corpus_years":[2021]}; Preserve comparison target with a cited claim or explicit gap: {"ticker":"GOOGL","form":"10-K","corpus_years":[2024]}; Preserve comparison target with a cited claim or explicit gap: {"ticker":"GOOGL","form":"10-K","corpus_years":[2025]}

### Q06

Which of the five companies added, removed, or materially changed risk-factor language related to AI, cloud infrastructure, export controls, supply chain concentration, or regulation between 2021 and 2025?

**Controlled failure:** grounding; GroundingRejected. No rejected draft was displayed or saved.

Validation failures: claim 0: uncited numeric tokens 2021. Cite exact supporting source numbers/periods; derived results require calculation kind and a recorded calculation ID; claim 0: Quote is not verbatim source text for chunk 1fc5706b-0efa-532f-9cd1-8554af579189; Preserve comparison target with a cited claim or explicit gap: {"ticker":"AAPL","form":"10-K","corpus_years":[2021]}; Preserve comparison target with a cited claim or explicit gap: {"ticker":"AMZN","form":"10-K","corpus_years":[2021]}; Preserve comparison target with a cited claim or explicit gap: {"ticker":"AMZN","form":"10-K","corpus_years":[2022]}; Preserve comparison target with a cited claim or explicit gap: {"ticker":"AMZN","form":"10-K","corpus_years":[2023]}; Preserve comparison target with a cited claim or explicit gap: {"ticker":"AMZN","form":"10-K","corpus_years":[2024]}; Preserve comparison target with a cited claim or explicit gap: {"ticker":"AMZN","form":"10-K","corpus_years":[2025]}; Preserve comparison target with a cited claim or explicit gap: {"ticker":"MSFT","form":"10-K","corpus_years":[2021]}; Preserve comparison target with a cited claim or explicit gap: {"ticker":"MSFT","form":"10-K","corpus_years":[2022]}; Preserve comparison target with a cited claim or explicit gap: {"ticker":"MSFT","form":"10-K","corpus_years":[2023]}; Preserve comparison target with a cited claim or explicit gap: {"ticker":"MSFT","form":"10-K","corpus_years":[2024]}; Preserve comparison target with a cited claim or explicit gap: {"ticker":"MSFT","form":"10-K","corpus_years":[2025]}; Preserve comparison target with a cited claim or explicit gap: {"ticker":"NVDA","form":"10-K","corpus_years":[2021]}; Preserve comparison target with a cited claim or explicit gap: {"ticker":"NVDA","form":"10-K","corpus_years":[2022]}; Preserve comparison target with a cited claim or explicit gap: {"ticker":"NVDA","form":"10-K","corpus_years":[2023]}; Preserve comparison target with a cited claim or explicit gap: {"ticker":"NVDA","form":"10-K","corpus_years":[2024]}; Preserve comparison target with a cited claim or explicit gap: {"ticker":"NVDA","form":"10-K","corpus_years":[2025]}; Preserve comparison target with a cited claim or explicit gap: {"ticker":"GOOGL","form":"10-K","corpus_years":[2021]}; Preserve comparison target with a cited claim or explicit gap: {"ticker":"GOOGL","form":"10-K","corpus_years":[2022]}; Preserve comparison target with a cited claim or explicit gap: {"ticker":"GOOGL","form":"10-K","corpus_years":[2023]}; Preserve comparison target with a cited claim or explicit gap: {"ticker":"GOOGL","form":"10-K","corpus_years":[2024]}; Preserve comparison target with a cited claim or explicit gap: {"ticker":"GOOGL","form":"10-K","corpus_years":[2025]}

Validation failures: claim 0: uncited numeric tokens 2021, 2025. Cite exact supporting source numbers/periods; derived results require calculation kind and a recorded calculation ID; claim 0: Quote is not verbatim source text for chunk 1fc5706b-0efa-532f-9cd1-8554af579189; claim 0: Quote belongs to these already-observed chunk IDs: 557a8085-2084-57dd-8f0c-b44e6b0063c0; replace the incorrect ID 5997af8d-9048-59bd-9d27-40da34fae837 or remove the unsupported claim; Preserve comparison target with a cited claim or explicit gap: {"ticker":"AAPL","form":"10-K","corpus_years":[2025]}; Preserve comparison target with a cited claim or explicit gap: {"ticker":"AMZN","form":"10-K","corpus_years":[2021]}; Preserve comparison target with a cited claim or explicit gap: {"ticker":"AMZN","form":"10-K","corpus_years":[2022]}; Preserve comparison target with a cited claim or explicit gap: {"ticker":"AMZN","form":"10-K","corpus_years":[2023]}; Preserve comparison target with a cited claim or explicit gap: {"ticker":"AMZN","form":"10-K","corpus_years":[2024]}; Preserve comparison target with a cited claim or explicit gap: {"ticker":"AMZN","form":"10-K","corpus_years":[2025]}; Preserve comparison target with a cited claim or explicit gap: {"ticker":"MSFT","form":"10-K","corpus_years":[2021]}; Preserve comparison target with a cited claim or explicit gap: {"ticker":"MSFT","form":"10-K","corpus_years":[2022]}; Preserve comparison target with a cited claim or explicit gap: {"ticker":"MSFT","form":"10-K","corpus_years":[2023]}; Preserve comparison target with a cited claim or explicit gap: {"ticker":"MSFT","form":"10-K","corpus_years":[2024]}; Preserve comparison target with a cited claim or explicit gap: {"ticker":"MSFT","form":"10-K","corpus_years":[2025]}; Preserve comparison target with a cited claim or explicit gap: {"ticker":"NVDA","form":"10-K","corpus_years":[2021]}; Preserve comparison target with a cited claim or explicit gap: {"ticker":"NVDA","form":"10-K","corpus_years":[2022]}; Preserve comparison target with a cited claim or explicit gap: {"ticker":"NVDA","form":"10-K","corpus_years":[2023]}; Preserve comparison target with a cited claim or explicit gap: {"ticker":"NVDA","form":"10-K","corpus_years":[2024]}; Preserve comparison target with a cited claim or explicit gap: {"ticker":"NVDA","form":"10-K","corpus_years":[2025]}; Preserve comparison target with a cited claim or explicit gap: {"ticker":"GOOGL","form":"10-K","corpus_years":[2021]}; Preserve comparison target with a cited claim or explicit gap: {"ticker":"GOOGL","form":"10-K","corpus_years":[2022]}; Preserve comparison target with a cited claim or explicit gap: {"ticker":"GOOGL","form":"10-K","corpus_years":[2023]}; Preserve comparison target with a cited claim or explicit gap: {"ticker":"GOOGL","form":"10-K","corpus_years":[2024]}; Preserve comparison target with a cited claim or explicit gap: {"ticker":"GOOGL","form":"10-K","corpus_years":[2025]}

### Q07

For Apple and NVIDIA, what do the filings say about supplier concentration or dependence on third-party manufacturing, and did the wording become more or less urgent over time?

**Controlled failure:** grounding; GroundingRejected. No rejected draft was displayed or saved.

Validation failures: claim 0: uncited numeric tokens 1, 2, 5, 8, 93, 546, 572, 5982, 9504. Cite exact supporting source numbers/periods; derived results require calculation kind and a recorded calculation ID; claim 0: Quote is not verbatim source text for chunk 8c65847a-e19c-5982-b695-93e15fea70c5; claim 1: uncited numeric tokens 4, 5, 9, 21, 87, 90, 5570, 31607. Cite exact supporting source numbers/periods; derived results require calculation kind and a recorded calculation ID; claim 1: Quote is not verbatim source text for chunk e59ecf43-9f01-5570-90e3-4b17a8ac47df; claim 1: Quote is not verbatim source text for chunk 31607fbb-4d43-5b74-87e4-b51497c3056e; Preserve comparison target with a cited claim or explicit gap: {"ticker":"AAPL","form":"10-K","corpus_years":[2024]}; Preserve comparison target with a cited claim or explicit gap: {"ticker":"AAPL","form":"10-K","corpus_years":[2025]}; Preserve comparison target with a cited claim or explicit gap: {"ticker":"NVDA","form":"10-K","corpus_years":[2022]}; Preserve comparison target with a cited claim or explicit gap: {"ticker":"NVDA","form":"10-K","corpus_years":[2024]}

Validation failures: claim 0: uncited numeric tokens 1, 2, 5, 8, 93, 546, 572, 2024, 2025, 5982, 9504. Cite exact supporting source numbers/periods; derived results require calculation kind and a recorded calculation ID; Preserve comparison target with a cited claim or explicit gap: {"ticker":"NVDA","form":"10-K","corpus_years":[2021]}; Preserve comparison target with a cited claim or explicit gap: {"ticker":"NVDA","form":"10-K","corpus_years":[2023]}; Preserve comparison target with a cited claim or explicit gap: {"ticker":"NVDA","form":"10-K","corpus_years":[2025]}

### Q08

Compare capital expenditures and purchase commitments for Microsoft, Alphabet, Amazon, and NVIDIA. What do the filings imply about the scale and timing of AI/cloud infrastructure investment?

**Controlled failure:** service; UnexpectedModelBehavior. No rejected draft was displayed or saved.

### Q09

For each company, summarize the most important geographic revenue exposures disclosed in the latest 10-K, then identify any year-over-year changes that could matter to an analyst.

**Controlled failure:** grounding; GroundingRejected. No rejected draft was displayed or saved.

Validation failures: claim 0: Quote belongs to these already-observed chunk IDs: bbae2181-21c6-5e6b-b62b-1068c914c23f; replace the incorrect ID 93b647fc-8c77-5239-b51b-1b0e2a67d508 or remove the unsupported claim; claim 1: Quote belongs to these already-observed chunk IDs: 49c8f381-f2ce-561a-bab2-2be985361987; replace the incorrect ID 0c9751e8-0e37-5dae-afb3-8b7a1021941a or remove the unsupported claim; claim 1: Quote is not verbatim source text for chunk 165bf45a-21c4-5602-90ad-41783c329bef; claim 2: Quote belongs to these already-observed chunk IDs: c438038d-19c1-5cb7-9e55-369c27688305; replace the incorrect ID 552c884d-541d-5d27-9768-392b479df8a9 or remove the unsupported claim; claim 3: Quote belongs to these already-observed chunk IDs: 49c8f381-f2ce-561a-bab2-2be985361987; replace the incorrect ID 590cc067-473d-5b72-b919-8a9516610f4e or remove the unsupported claim; claim 3: Quote is not verbatim source text for chunk 49c8f381-f2ce-561a-bab2-2be985361987; claim 4: Quote belongs to these already-observed chunk IDs: d01c1281-2a78-5c25-b013-cf4a8a5a3592; replace the incorrect ID e00de649-21c1-5524-a24b-77d4757c1a75 or remove the unsupported claim

Validation failures: claim 0: uncited numeric tokens 2024. Cite exact supporting source numbers/periods; derived results require calculation kind and a recorded calculation ID; claim 1: Quote belongs to these already-observed chunk IDs: 49c8f381-f2ce-561a-bab2-2be985361987; replace the incorrect ID 0c9751e8-0e37-5dae-afb3-8b7a1021941a or remove the unsupported claim; claim 2: Quote belongs to these already-observed chunk IDs: c438038d-19c1-5cb7-9e55-369c27688305; replace the incorrect ID 552c884d-541d-5d27-9768-392b479df8a9 or remove the unsupported claim; claim 3: Quote belongs to these already-observed chunk IDs: 49c8f381-f2ce-561a-bab2-2be985361987; replace the incorrect ID 590cc067-473d-5b72-b919-8a9516610f4e or remove the unsupported claim; claim 3: Quote is not verbatim source text for chunk 49c8f381-f2ce-561a-bab2-2be985361987; claim 4: Quote belongs to these already-observed chunk IDs: d01c1281-2a78-5c25-b013-cf4a8a5a3592; replace the incorrect ID e00de649-21c1-5524-a24b-77d4757c1a75 or remove the unsupported claim

### Q10

If an analyst asks whether the filings prove that generative AI improved margins for any of these companies, what evidence exists in the corpus, and where should the bot refuse to infer beyond the filings?

**Controlled failure:** grounding; GroundingRejected. No rejected draft was displayed or saved.

Validation failures: claim 2: Quote is not verbatim source text for chunk 84ec8c5c-3778-55a7-b086-5248fe0dcd42; Preserve comparison target with a cited claim or explicit gap: {"ticker":"AAPL","form":"10-K","corpus_years":[2021]}; Preserve comparison target with a cited claim or explicit gap: {"ticker":"AAPL","form":"10-K","corpus_years":[2022]}; Preserve comparison target with a cited claim or explicit gap: {"ticker":"AAPL","form":"10-K","corpus_years":[2023]}; Preserve comparison target with a cited claim or explicit gap: {"ticker":"AAPL","form":"10-K","corpus_years":[2024]}; Preserve comparison target with a cited claim or explicit gap: {"ticker":"AAPL","form":"10-K","corpus_years":[2025]}; Preserve comparison target with a cited claim or explicit gap: {"ticker":"AMZN","form":"10-K","corpus_years":[2021]}; Preserve comparison target with a cited claim or explicit gap: {"ticker":"AMZN","form":"10-K","corpus_years":[2022]}; Preserve comparison target with a cited claim or explicit gap: {"ticker":"AMZN","form":"10-K","corpus_years":[2023]}; Preserve comparison target with a cited claim or explicit gap: {"ticker":"AMZN","form":"10-K","corpus_years":[2024]}; Preserve comparison target with a cited claim or explicit gap: {"ticker":"AMZN","form":"10-K","corpus_years":[2025]}; Preserve comparison target with a cited claim or explicit gap: {"ticker":"MSFT","form":"10-K","corpus_years":[2021]}; Preserve comparison target with a cited claim or explicit gap: {"ticker":"MSFT","form":"10-K","corpus_years":[2022]}; Preserve comparison target with a cited claim or explicit gap: {"ticker":"MSFT","form":"10-K","corpus_years":[2024]}; Preserve comparison target with a cited claim or explicit gap: {"ticker":"MSFT","form":"10-K","corpus_years":[2025]}; Preserve comparison target with a cited claim or explicit gap: {"ticker":"NVDA","form":"10-K","corpus_years":[2021]}; Preserve comparison target with a cited claim or explicit gap: {"ticker":"NVDA","form":"10-K","corpus_years":[2022]}; Preserve comparison target with a cited claim or explicit gap: {"ticker":"NVDA","form":"10-K","corpus_years":[2023]}; Preserve comparison target with a cited claim or explicit gap: {"ticker":"NVDA","form":"10-K","corpus_years":[2025]}; Preserve comparison target with a cited claim or explicit gap: {"ticker":"GOOGL","form":"10-K","corpus_years":[2021]}; Preserve comparison target with a cited claim or explicit gap: {"ticker":"GOOGL","form":"10-K","corpus_years":[2024]}; Preserve comparison target with a cited claim or explicit gap: {"ticker":"GOOGL","form":"10-K","corpus_years":[2025]}

Validation failures: Preserve comparison target with a cited claim or explicit gap: {"ticker":"AAPL","form":"10-K","corpus_years":[2021]}; Preserve comparison target with a cited claim or explicit gap: {"ticker":"AAPL","form":"10-K","corpus_years":[2022]}; Preserve comparison target with a cited claim or explicit gap: {"ticker":"AAPL","form":"10-K","corpus_years":[2023]}; Preserve comparison target with a cited claim or explicit gap: {"ticker":"AAPL","form":"10-K","corpus_years":[2024]}; Preserve comparison target with a cited claim or explicit gap: {"ticker":"AAPL","form":"10-K","corpus_years":[2025]}; Preserve comparison target with a cited claim or explicit gap: {"ticker":"AMZN","form":"10-K","corpus_years":[2021]}; Preserve comparison target with a cited claim or explicit gap: {"ticker":"AMZN","form":"10-K","corpus_years":[2022]}; Preserve comparison target with a cited claim or explicit gap: {"ticker":"AMZN","form":"10-K","corpus_years":[2023]}; Preserve comparison target with a cited claim or explicit gap: {"ticker":"AMZN","form":"10-K","corpus_years":[2024]}; Preserve comparison target with a cited claim or explicit gap: {"ticker":"AMZN","form":"10-K","corpus_years":[2025]}; Preserve comparison target with a cited claim or explicit gap: {"ticker":"MSFT","form":"10-K","corpus_years":[2021]}; Preserve comparison target with a cited claim or explicit gap: {"ticker":"MSFT","form":"10-K","corpus_years":[2022]}; Preserve comparison target with a cited claim or explicit gap: {"ticker":"MSFT","form":"10-K","corpus_years":[2024]}; Preserve comparison target with a cited claim or explicit gap: {"ticker":"MSFT","form":"10-K","corpus_years":[2025]}; Preserve comparison target with a cited claim or explicit gap: {"ticker":"NVDA","form":"10-K","corpus_years":[2021]}; Preserve comparison target with a cited claim or explicit gap: {"ticker":"NVDA","form":"10-K","corpus_years":[2022]}; Preserve comparison target with a cited claim or explicit gap: {"ticker":"NVDA","form":"10-K","corpus_years":[2023]}; Preserve comparison target with a cited claim or explicit gap: {"ticker":"NVDA","form":"10-K","corpus_years":[2025]}; Preserve comparison target with a cited claim or explicit gap: {"ticker":"GOOGL","form":"10-K","corpus_years":[2021]}; Preserve comparison target with a cited claim or explicit gap: {"ticker":"GOOGL","form":"10-K","corpus_years":[2024]}; Preserve comparison target with a cited claim or explicit gap: {"ticker":"GOOGL","form":"10-K","corpus_years":[2025]}

## Known findings and technical checks

- Offline verification: 149 passed, 13 integration tests deselected. The selected live suite had four passes and one failed judge-calibration test. Frontend TypeScript, lint and production build passed; authenticated browser checks remain pending.
- Exact-ID repair feedback suggests only matching source IDs already observed by the agent; it never accepts a quote attached to the wrong chunk. A targeted Apple supplier comparison subsequently produced a validated partial answer (`supplier-diagnostic-repair.json`); human correctness review remains pending and this does not override the full sweep.
- Missing or duplicate judge coverage is a service failure, not an evidence-gap refusal. Calculator token checks preserve negative signs, including spaced parentheses, and reject missing quoted year/scale bindings.
- Evaluation-only gpt-4.1-mini trials passed one five-case judge calibration, but supplier-comparison trials were mixed, including wrong-chunk quote failures. These limited trials do not establish reliability. Production model configuration was not changed; no further paid trials were run for this report.
- All ten questions were also run before the last hardening changes. The earlier bounded-tools run accepted only Q02 as insufficient evidence and Q06 as partial; eight turns failed safely. Those results are not a successful quality gate or a retrieval relevance score.
- Table-heavy revenue/margin questions frequently produced invalid quotes, unverified input mappings or missing periods. Extraction remains unchanged as requested; do not interpret these failures as permission to clean/re-embed the corpus.
- Exact-quote validation caught claims whose numerical values were absent from the displayed quotes. The judge now receives claim-specific quotes, not unrelated source paragraphs.
- A Services-growth result of 13.51% was once automatically accepted with bare numeric rows but no quoted year/scale bindings. **That result is not accepted evidence.** The calculator now rejects such inputs; the affected smoke recheck returned controlled insufficient evidence.
- The small judge inconsistently accepted a deliberately forged calculation record with missing periods and the wrong dollar scale. The current calculator cannot create that tested record, but this remains an independent-judge calibration failure. The marked test keeps the expected rejection; do not hide it by accepting the false positive.
- A narrative Microsoft ratio fixture uses real quoted fiscal-period headings and USD-billion inputs; it passed calculator, structural and live-judge checks. It is developer-assembled integration evidence, **not** an autonomous-agent-quality success.
- Live database tests verified atomic citation/message writes, rollback on an invalid citation foreign key, completed replay, owner isolation and ordered history. Fixtures were rolled back.
- A live answering-agent test ignored instruction-like text in a labeled synthetic source. The judge rejected wrong-scale factual claims, unsupported prior periods and causal leaps in the calibration fixture.
- Final browser login/question/source/reload/Stop/retry checks remain owner work. TypeScript, lint and production build are technical checks, not browser acceptance.

## Historical sweep usage (before guided calculations)

```json
{
  "generator": {
    "requests": 102,
    "input_tokens": 1290698,
    "output_tokens": 24036
  },
  "grounding": {
    "requests": 0,
    "input_tokens": 0,
    "output_tokens": 0
  }
}
```

Retrieval embedding/keyword usage is recorded separately in each raw case. Counters include known returned usage only; cancellations/provider failures may be billed without returning all usage. No dollar-cost estimate is asserted here.

## Owner review

See [three concrete review cases](assistant-owner-review.md). These are new phase-six judgments; phase-five retrieval acceptance does not approve generated answers.
