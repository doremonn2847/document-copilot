# Guided comparisons: approved implementation

Owner approved on 2026-10-21. Initial verification was offline; the subsequently
approved single paid diagnostic failed, as recorded below. No model/config
changes, corpus rewrites, database writes or commits were made.

Flow: typed `compare_filings` output plans targets and runs existing backend
comparison retrieval, then a tool-free writer submits source-backed claims and
specific gaps. Server-owned question-span IDs resolve gap provenance. Both
structural and semantic checks remain; at most one repair shares the same frozen
evidence. Missing target coverage stays server-generated. Existing lookups and
the verified calculator retain their paths.

Implementation sequence:

1. Request span catalog and typed comparison-gap resolution.
2. End comparison planning after retrieval; tool-free drafting and shared repair.
3. Judge request-ID provenance; preserve semantic gap checks.
4. Offline SDK, orchestration, regression and full-suite verification; docs.

Ruling: reuse the existing typed comparison call instead of adding another
planning-model call. Its target filters already provide the needed contract.

Ruling: retain the existing 120-second deadline and provider token/request caps.
Bound the stages rather than raising budgets. Invalid comparison output consumes
the same single repair allowance as a failed grounding check.

Ruling: keep the existing dirty workspace and prior owner-authorized main-branch
workflow; do not move, commit or overwrite unrelated work.

Ruling: a comparison begins when the existing answering agent selects the typed
comparison output; no separate routing-model call or keyword-based router is
introduced. Once that plan is selected, search/read tools cannot be used by the
writer or repair. Planning keeps its existing schema retry; drafting and judging
share at most one repair. Existing arithmetic routing takes precedence.

Ruling: the gap envelope allows 25 model aspect gaps plus 25 server coverage gaps
(50 total) so all requested targets survive even when a trend is unverified.
Model aspect submissions remain bounded at 25; provider output caps are unchanged.

Focused review: two budget/target-validation issues were found, reproduced with
failing tests and fixed. Recheck found no remaining important defect within this
scope. No live services were called by the review.

Latest verification: **327 tests passed, 15 integration tests deselected**;
lint and formatting checks passed for the affected Python files. Focused
review/recheck passed. Live reliability remains open.

## Authorized live diagnostic and offline corrections

The one approved check failed with `InvalidSupportReport` after 35.77 seconds:
3 answering requests (8,313 input / 1,251 output tokens), 1 judge request
(2,572 input / 727 output), 1 keyword request and 1 embedding. It stayed within
the approved caps and made no chat/database writes. The initial draft's
cross-company interpretation cited only Apple and was correctly rejected.

The diagnostic wrapper nested the SDK message capture, hiding failed writer
history from orchestration. A mock reproduction confirmed the interference.
The observer now captures bounded request/response JSON through HTTP hooks
without nesting SDK capture; it excludes headers and provider error bodies.
The failed run therefore does not establish production repair context loss.

Two production contract repairs are offline-verified: guided judging requires
one fixed `C0`/`G0` verdict field per submitted claim/gap, with server-assigned
indices; invalid writer submissions pass bounded specific validation feedback
privately to their one repair. Safe public/log diagnostics remain unchanged.
A real-SDK mock regression first failed on missing rejection feedback, then
passed. The observer parity check retained both evidence and `int_parsing`
feedback across two mock requests, with zero live requests.

These corrections were offline proof at that point. The separately approved
follow-up below did not produce an accepted supplier comparison.

## Follow-up capped live check: citation repair still fails

The owner approved one follow-up with the same hard caps. It failed closed with
`GroundingRejected` after **33.8 seconds**: **3 answering, 0 judge, 1 keyword,
1 embedding** requests. Answering used 13,145 input / 2,576 output tokens.
There were zero HTTP retries, extra reruns or chat/database writes.

Both captured writer submissions contained ten company/year factual blocks and
one broad Apple/NVIDIA interpretation. That interpretation selected five Apple
IDs and no NVIDIA IDs. The repair request retained the original evidence and
explicitly named the missing company, offered observed NVIDIA IDs and instructed
the writer to correct or omit the synthesis. The second submission repeated the
same invalid interpretation citations. Submission validation rejected it again;
no judge was called and none of the factual blocks were semantically accepted.

This run confirms the repaired observer and private feedback reach the wire.
It does not verify the fixed-key judge because judging was never reached.
The remaining demonstrated failure is the writer not correcting its own
cross-company citation selection. The current five-reference claim limit also
means a ten-period synthesis must be split or narrowed, not cite every period
in one block. Do not weaken grounding or auto-attach citations to make it pass.

The artifact is `data/chunks/assistant/guided-supplier-comparison-result.json`;
the previous failed artifact was preserved separately. No additional paid calls
were made. Phase 6 and frontend confirmation remain open.

## Approved company-grouped citation contract (offline verification)

The owner approved requiring separate company-scoped source selections for
comparison interpretations. Diagnosis replayed both failed live drafts and
inspected the actual writer schema: all 35 evidence IDs were available, including
19 NVIDIA IDs, and repair feedback reached the request. No backend ID removal or
mapping error was demonstrated. Both failed interpretations used all five slots
for Apple despite naming Apple and NVIDIA and spanning multiple periods.

Facts retain their flat `evidence_ids` path. Interpretations now use a required
`evidence_by_company` object with a nonempty field for every compared company.
Each field's schema enumerates only that company's observed IDs; the submission
boundary independently verifies keys and source ownership. It resolves only
model-selected IDs into the existing exact quote references. It does not add
missing sources or infer support. Shared enum definitions preserve the existing
900-source budget without duplicating enum values across facts and groups.

The total remains five references per claim, not five per company. Instructions
require splitting or narrowing broad company/year interpretations to fit this
limit. Single-company multi-year requests use one required group. If any
compared company has no observed evidence, interpretations are unavailable;
supported factual claims and explicit gaps remain possible. This conservative
contract requires all requested companies in an interpretation, rather than an
arbitrary subset of a larger comparison. It does not establish period coverage
or semantic support: existing structural and judge checks still apply.

Offline verification: **340 passed, 15 integration tests deselected**, with
affected-file lint and formatting checks passing. The regression first failed
because the writer schema had no company groups. Real-SDK mock tests now prove
scoped required groups, rejection of the captured flat-selection pattern, one
shared repair, acceptance of a corrected selection only after judging, and
rejection when judging finds no support. Boundary checks reject foreign/unknown
IDs, missing/extra groups and totals above five. Empty evidence and the maximum
enum budget are covered. Both actual captured interpretations also fail the new
typed contract in an offline replay.

No paid calls, model/config changes, corpus/database writes, dependencies or
commits were made for this change. The model has not yet run against the new
contract live. Phase 6 remains open pending separately authorized live proof.

## Grouped-citation live check and total-budget correction

The owner authorized one capped grouped-contract run. It failed closed with
`GroundingRejected` in **33.08 seconds**: **3 answering, 0 judging, 1 keyword,
1 embedding** requests. Answering usage was 13,131 input / 1,672 output tokens.
Zero HTTP retries, additional runs or chat/database writes occurred.

Both interpretations selected sources for Apple and NVIDIA, so this run did not
repeat the missing-company citation error. The first selected four Apple plus
three NVIDIA references; repair selected three plus three. Both exceeded the
five-reference total and were rejected before judging. The repair input contained
the explicit total-budget error. Correct company membership does not mean the
drafts were grounded; none of their claims received semantic acceptance.

The wire schema had bounded each company list independently at five, while
runtime validation enforced five combined. This left an over-budget submission
representable. An offline regression reproduced that mismatch for two through
five companies. The schema now offers bounded allocations of the existing five
slots across all required companies. For two companies it permits 1+4, 2+3,
3+2 or 4+1 maxima, with at least one reference from each; every valid smaller
allocation also fits. There is no budget increase, omitted-company allowance,
automatic source attachment or extra repair. Shared enum definitions remain.

Offline exhaustive count checks cover every 0–5 selection count for one through
five companies: allocations are representable exactly when every company has
at least one and the sum is at most five. Real-SDK mock tests inspect the
allocation branches after schema normalization. Live confirmation of this
combined-limit correction is still pending; no second paid run was made.

Post-correction verification: **345 offline tests passed, 15 integration tests
deselected**; affected Python lint/format checks passed. FastAPI was restarted
and health returned HTTP 200. Phase 6 remains open.
