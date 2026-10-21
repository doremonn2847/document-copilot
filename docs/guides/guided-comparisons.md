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

## Combined-budget live check and single-company interpretations (2026-10-21)

**Writer scope.** With the default four-search budget, the planner can search
before handing off to the writer. The writer schema previously offered every
evidence ID from the turn, including spans absent from its frozen prompt. The
registry now records the IDs displayed by the comparison retrieval, and only
those are selectable or resolvable by the writer. A wire test also confirms
that pydantic-ai's OpenAI strict-mode transformer leaves the hand-built
writer schema unchanged for one through six companies (commit `bbcb262`).

**Owner-approved capped run.** Same supplier question and caps as before
(4 answering × 4,000, 2 judging × 2,000, 2 keyword × 150, 1 embedding; zero
retries; no chat/database writes). It failed closed with `GroundingRejected`
in **35.5 seconds**: **3 answering, 0 judging, 1 keyword, 1 embedding**.
Answering usage was 14,397 input / 1,915 output tokens; 29 evidence IDs.

The combined five-reference budget held: interpretations selected 5 and 4
references, each covering both companies. Both drafts instead failed the
structural check on claim 7, an Apple-only trend statement saying the 2024
language "adds" prepayments and equipment. Because every interpretation had to
cite every compared company, it cited Apple 2021 twice, 2022, 2023 and one
NVIDIA passage, leaving no 2024 source, so `2024` was an uncited numeric token.
The statement was also unsupported: the cited Apple 2022 passage already
mentions prepayments. The repair resubmitted the same citations. The NVIDIA
trend interpretation likewise carried an unrelated Apple citation. The judge
was not reached.

**Owner decision.** Interpretations may now cite exactly one compared company
(up to five of its references) or every compared company (the existing
allocation). For two companies the schema offers two single-company branches
plus the four shared allocations; beyond five companies only single-company
interpretations remain. An interpretation naming several companies must still
cite each of them (`missing_company_evidence` at final submission). There is no
budget increase or automatic source attachment. Offline: **353 passed, 15
integration deselected**. Live confirmation is pending; phase 6 remains open.

**Owner decision: ten references per interpretation.** A two-company, five-year
comparison needs ten company-year sources, which a five-reference total could
never cite. Interpretations now allow ten references in total (facts remain at
five via `ASSISTANT_CLAIM_REFS`): up to ten for a single company, or an equal
share per company in a cross-company group (five each for two companies, three
for three, two for four or five). The equal share keeps the total enforced in
one schema branch instead of enumerating every uneven split (126 branches for
five companies at ten). Uneven cross-company splits such as 6+4 are therefore
not representable. Offline: **355 passed, 15 integration deselected**.

**Ten-reference live check.** One more approved run with unchanged caps was
**accepted** in 35.5 seconds: **3 answering, 1 judging, 1 keyword, 1 embedding**
(answering 14,313 input / 2,006 output tokens; judge 5,587 / 749; 37 evidence
IDs). This was the first live pass through the guided judge, but the accepted
answer was not correct:

- The first draft used the new contract well: 8 per-year facts, an Apple-only
  interpretation (4 sources), an NVIDIA-only one (7) and a 4+5 cross-company
  one. It failed with `evidence_ids too_long` because resolution rebuilt each
  interpretation as a `SelectedClaim`, which kept the five-ID fact limit. The
  repair then dropped all interpretations.
- The accepted repair reported Apple 2023 and 2024 as lacking supplier-risk
  wording, although the writer had been shown Apple 2023 (supplier facilities
  outside the U.S.) and 2024 (concentrated supply chains, supplier accidents)
  quotes. The judge marked both gaps warranted because it saw only cited
  evidence, never the evidence displayed for a gap's target.

Fixes: resolved interpretations keep the ten-reference limit
(`ResolvedInterpretation`), and in guided mode each targeted gap now carries
`displayed_target_evidence` (up to 12 shown quotes for that company/year, plus
an omitted count). The judge is told that such a gap is unwarranted when any
shown quote addresses the requested aspect. Offline: **357 passed, 15
integration deselected**. Live confirmation is pending; phase 6 remains open.

**Gap-evidence live check.** One more approved run with unchanged caps failed
closed in 31.9 seconds: **3 answering, 0 judging, 1 keyword, 1 embedding**
(answering 14,222 input / 2,504 output tokens; 29 evidence IDs). Both drafts
were substantively strong: per-year facts for both companies plus single-company
trend interpretations citing up to ten sources. Both failed structurally:
interpretations mentioned uncited years as caveats ("the 2025 excerpt does
not…", NVIDIA 2022/2023), and the repair returned the same text after generic
"cite exact numbers/periods" feedback (the second ineffective repair in a row).
One interpretation also said "both companies" while citing only Apple; the
company-name check cannot see unnamed groups, so it passed structurally.

Fixes: uncited-year feedback now names displayed same-company source IDs for
each missing year, or directs the limitation into a gap; a single-company
group rejects wording about several companies ("both/neither/the two
companies"); writer instructions state both rules. Offline: **362 passed, 15
integration deselected**. Live confirmation is pending; phase 6 remains open.

**Year-feedback live check.** One more approved run with unchanged caps failed
closed in 27.7 seconds: **3 answering, 0 judging, 1 keyword, 1 embedding**
(answering 14,042 input / 2,199 output tokens; 27 evidence IDs). The draft had
eight per-year facts, an NVIDIA trend interpretation and reasonable gaps. One
interpretation discussed both companies ("Apple's wording … while NVIDIA's …")
with an Apple-only group, and `missing_company_evidence` rejected it. The repair
feedback listed NVIDIA candidate IDs, yet the writer resubmitted the same group.
This was the third consecutive run in which the single repair did not correct
one claim, so the whole answer was discarded for one sentence.

**Design decision: withhold failed claims on the final guided attempt.** After
the single repair (or on a comparison first planned on the final attempt), the
writer's submission and the orchestrator drop only claims that fail submission,
structural or judge checks, plus model-written gaps the judge rejects. No check
is weakened. It still fails closed when every claim fails, when an error is not
tied to one claim (for example the claim limit), when the judge rejects a
server-owned coverage gap, or when judge-stage pruning would leave a covered
company/year without claims. Coverage gaps created by submission- or
structural-stage withholding are judged with the target's shown evidence. A
fixed server notice tells the analyst that statements were omitted. Withheld
reports (indices only) are recorded only for accepted answers. The financial
context fallback still applies to the pre-withholding structural errors.

An adversarial review (three lenses, one skeptic per finding) refuted two
findings and confirmed the rest, all addressed above: silent omission, the
financial fallback regression, a narrow gap masking a lost target, diagnostics
for rejected turns, and missing tests. Mutation checks confirm the new tests
fail when each guard is removed. Offline: **375 passed, 15 integration
deselected**. Live confirmation is pending; phase 6 remains open.

**Withholding live check: first accepted guided answer.** One more approved
run with unchanged caps was **accepted on its first draft** in 34.2 seconds:
**2 answering, 1 judging, 1 keyword, 1 embedding** (answering 7,999 input /
1,156 output tokens; judge 9,794 / 1,031; 29 evidence IDs). No repair or
withholding was needed. Manual verification against the shown evidence:
- All seven per-year facts (Apple 2021–2024, NVIDIA 2021/2024/2025) and the
  Apple-versus-NVIDIA emphasis interpretation are supported.
- Gaps for Apple 2025 and NVIDIA 2022/2023 are warranted: retrieval showed
  only unrelated text (a competitor list, patent boilerplate) for those years,
  a retrieval limitation reported honestly. Two further gaps are redundant.
- **The Apple trend interpretation is unsupported.** It calls the 2024
  disclosure "supplier-financed equipment/prepayment exposures" although the
  quote says Apple invested in equipment at partners and prepaid suppliers,
  and it infers "heavier dependence" from excerpts on different topics in
  different years. The NVIDIA "moves from … to" interpretation has the same
  excerpt-trend weakness. The judge accepted all ten claims.

Judge and writer instructions now require exact relationship direction and
forbid inferring shifts from differently selected excerpts. An approved
single-call replay of the recorded judge payload with these instructions
(`gpt-4.1-mini`; 9,912 input / 1,074 output tokens) **still accepted the
reversed claim**, restating it in its own assessment. (A first replay call
completed but its output was lost to a script bookkeeping bug; it was fixed
and verified offline with a mocked response before the approved retry.)
Instructions alone do not fix the judge; the judge model is the weak link.
Phase 6 remains open pending a judge decision.
