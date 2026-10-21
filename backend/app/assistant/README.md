# Grounded answers

From `backend/`:

```powershell
uv run uvicorn app.main:app --reload --port 8001
uv run python -m scripts.smoke_assistant --question "What services does Azure provide?" --output ../data/chunks/assistant/lookup.json
uv run python -m scripts.smoke_assistant --cases ../docs/evaluations/assistant-smoke-cases.json --output ../data/chunks/assistant/smoke.json
uv run python -m scripts.smoke_assistant --cases ../docs/evaluations/retrieval-cases.json --output ../data/chunks/assistant/client-questions.json
uv run pytest -m "not integration" --tb=no
uv run pytest tests/assistant/test_live_grounding.py tests/database/test_grounded_persistence.py tests/database/test_chat_endpoints.py -m integration --tb=no
uv run pytest tests/assistant/test_live_calculation.py::test_autonomous_guided_ratio_uses_verified_inputs -m integration --tb=no
```

The smoke command uses paid OpenAI calls and read-only retrieval; it never saves
chat messages. Run evaluations sequentially to avoid unnecessary provider-rate
pressure. Artifacts contain public filing excerpts and the evaluated questions,
but never credentials or raw provider/driver errors. Payloads under `data/` stay
ignored. `--only Q01 Q02` limits a worksheet run. Output is checkpointed after each
case, so failed cases remain visible.

## Flow and configuration

Explicit filing comparisons now use a guided handoff. `compare_filings` is a
typed planning output: the backend runs the existing per-target hybrid retrieval
once, exposes bounded full source context and returns the plan to orchestration.
A separate writer has no search/read tools. Its first draft and at most one
repair share the frozen evidence and cumulative usage. Schema/ID failures consume
the same repair as structural or semantic rejection; there is no nested writer
retry loop. The original planner retains its existing schema-validation retry.
Existing lookups and verified calculator routing remain separate.

Comparison facts select flat `evidence_ids`. Interpretations select
`evidence_by_company`: either one compared company's group or a nonempty group
for every compared company, with source choices restricted to each company's
observed IDs. The submission boundary checks those groups again, then resolves
only model-selected IDs into existing exact quote references. Interpretations
allow ten references total (facts five): up to ten for a single company, or an
equal share per company in a cross-company group, which the schema enforces in
one branch. Broader syntheses must split or narrow. Shared enum
definitions avoid doubling the existing source-enumeration budget. When a
compared company has no observed evidence, interpretations are hidden and the
writer can return facts and gaps. A single-company comparison requires one group.
Group membership does not establish meaning, period coverage or factual support;
all existing structural and semantic checks still apply. This contract has
offline SDK/regression verification; live confirmation remains pending.

Comparison gaps select server-generated `R1`, `R2`, ... question spans instead of
copying request text. IDs are enumerated in the writer schema; the server resolves
their actual text. The grounding judge checks the matching request ID and whether
the proposed limitation is requested and unresolved. A matching ID does not
establish relevance or factual support. Empty-target gaps remain server-generated.
The gap envelope allows 25 requested-aspect gaps plus 25 target-coverage gaps, so
all requested targets remain visible even when an additional aspect is unverified.
Provider output-token limits and the 120-second turn deadline are unchanged.

The compact comparison repair reuses the original bounded evidence messages and
bounded private output-validation feedback; that feedback is never added to
public/log diagnostics. It does not append every observed quote again or reopen
retrieval. Guided judging requires one verdict per server-owned claim/gap key;
the backend assigns decision indices. Offline tests
cover actual SDK planning/writer handoff, invalid plans/IDs, gap-only judging,
request provenance, coverage, shared repair and fail-closed behavior. Live
quality/latency confirmation is still required. The one approved diagnostic
failed; subsequent observer and contract fixes have only offline verification.

Cross-company interpretations are checked during final submission as well as
final structural validation. If their own citations omit a named company,
submission returns a bounded output-validation retry with observed candidate
IDs grouped by company/corpus year. The candidates establish provenance only;
the agent must choose supporting quotes or omit the synthesis. The server never
adds citations automatically. This uses the existing output-retry/request caps
and does not replace semantic grounding. Missing comparison-target coverage
continues to be derived from actual submitted citations.

Reasoning models (including `gpt-5-nano`) use
`ASSISTANT_REASONING_EFFORT=minimal` by default across answering, numeric
selection, numeric verification and final grounding. Nonreasoning models retain
temperature zero. Existing completion-token limits also include reasoning tokens;
raising them can increase cost without producing a usable answer.

A provider response ending at its token limit stops the turn immediately, before
tool/output retries or grounding repair. The browser reports the response limit
instead of encouraging repeated retries. Safe diagnostics record the failing role,
model, output tokens and reasoning tokens. Billed tokens remain in cumulative
usage even though PydanticAI's request counter excludes the aborted step.
These controls bound the failure; they do not establish nano's answer quality.

For the owner's GPT-5.4-mini trial, `backend/.env` uses:

```dotenv
OPENAI_CHAT_MODEL=gpt-5.4-mini
OPENAI_GROUNDING_MODEL=gpt-4.1-mini
ASSISTANT_REASONING_EFFORT=none
ASSISTANT_OUTPUT_TOKENS=4000
GROUNDING_OUTPUT_TOKENS=2000
```

[Official model documentation](https://developers.openai.com/api/docs/models/gpt-5.4-mini)
lists reasoning efforts none/low/medium/high/xhigh; minimal is unsupported.
However, the owner's approved Chat Completions diagnostic rejected the explicit
reasoning_effort parameter with HTTP 400. This integration therefore uses the
documented default (none) and omits that parameter entirely. Configuration requires
none for this model and its snapshots in the current adapter. Using explicit
reasoning needs separate endpoint/compatibility validation, not another blind retry.
The 4,000-token answering ceiling includes reasoning plus structured output;
it is not a target to consume. Existing request, tool, repair and time limits
remain in force. These settings apply to numeric selection too, which shares
the answering model. The nonreasoning grounding judge still uses temperature
zero. No paid quality evaluation is implied by configuring this trial.

Missing-evidence gaps for an already-cited target must name the unresolved
requested aspect in `missing_detail` (at most 400 characters). A blanket gap
fails structural validation and uses the existing single bounded repair before
any judge call. Genuine uncovered targets remain visible. Specific gaps render
as “Not established from the retrieved evidence” without claiming the filing
omits that information. Merely retrieving passages does not prove coverage.
The final judge also evaluates every gap against the actual question and the
supported answer in the same request used for prose verification. Internal
research suggestions, optional new topics and demands to confirm existing
citations are unwarranted. Missing, repeated or out-of-range gap verdicts fail
closed. Rejected gaps use the existing bounded repair; they are never silently
deleted. An already verified calculation needs no repeat numeric verification,
but any accompanying gaps still require a relevance verdict.

Model-written gaps now require `request_quote`, a verbatim span (up to 1,000
characters) of the current question identifying the unresolved request. Code
rejects missing, blank or fabricated spans before accepting final output. The
judge must independently return the same request quote for an approved
model-written gap; a missing or mismatched quote rejects its approval. Whitespace
is normalized, but wording is not paraphrased. Server-detected uncovered comparison
targets retain their fixed coverage warnings without needing a model-written quote.

Final verification supplies the proposed answer/evidence/gaps as an assistant
draft and the original question as the final user message. Its structured context
separates `actual_user_request` from `proposed_answer`. This prevents treating
gap prose as a user message. Literal anchors establish provenance, not semantic
correctness; the judge must still reject requirements added to a genuine quote.
No new model call or retry allowance is introduced. Saved replies are unchanged.

For SDK `UnexpectedModelBehavior` failures, safe turn diagnostics now retain
`model_failure.kind` (for example, `output_retries_exhausted`) and allowlisted
validation field/type pairs, without rejected values, raw exception text or
provider bodies. Semantic request-quote failures use the fixed
`request_anchor_invalid` reason. The browser's generic service message and all
retry/token budgets are unchanged. Older logs cannot recover these details.
Provider HTTP failures separately retain numeric HTTP status, allowlisted error
codes and parameter paths. Unknown values are redacted to `unclassified`; raw
provider messages/bodies are never logged. A successful model-metadata lookup
does not establish permission for inference or compatibility of a full request.

`assistant/agent.py` supplies bounded tools and typed claims. `deps.py` records
only source spans actually shown in the current turn. Displayed sentences/spans
receive short evidence IDs (`E1`, `E2`, case-insensitive). The model selects IDs;
the provider's strict schema enumerates the source and calculation IDs available
this turn. There are at most 900 selectable source spans, leaving room within
OpenAI's enum limit. Truncated sentences are previews without citation IDs;
read more before citing the complete statement.
`selection.py` attaches the original quote and source, derives answer status and
adds individual gaps for uncovered comparison targets. Unknown IDs are rejected.
Factual claims must cite one filing; this is checked during grounding so the agent
can repair a compound claim. Claims retain the existing 2,000-character bound. Supported cross-filing
inferences must be labeled interpretations. Calculation citations come directly
from the verified record. The model no longer transcribes UUID/quote pairs.
`grounding/validator.py`
checks provenance, quotes, numeric tokens, comparison coverage and calculator
records. The independent no-tool judge sees each claim's attached quotes and
authoritative metadata, not unrelated sentences elsewhere in a source chunk.
One repair is allowed; rejected drafts never reach the browser or chat tables.
Each quoted reference must be one contiguous observed source span. Nonadjacent
sentences need separate references, even within the same chunk. Stitched quotes
are rejected; repair receives the existing evidence-ID catalog.
Tools and typed outputs explicitly use OpenAI strict schemas; Python validation
still enforces local constraints and semantic source checks. The first retrieval
retains the full question alongside the agent's search focus; later queries can
refine it. Explicit arithmetic requests follow enforced steps: prepare numeric
facts, calculate from their IDs, then return the typed answer. Indirect requests
can also choose preparation; ordinary lookups retain their normal tool flow.

Numeric preparation checks proposed corpus-year filters against years named in
the current question. Unmentioned years are removed to widen retrieval; fiscal
years are never substituted as corpus filters. Explicit source-year requests,
bounded year ranges, undated follow-ups and references such as “that filing”
retain their source scope. This is a narrow defense against stale year filters,
not a general natural-language query planner or an authorization boundary.
The model sees a notice when its restriction was removed. Quote-based numeric
measure, unit and fiscal-period checks still decide whether inputs are usable.
Each numeric attempt records proposed/effective filters, returned chunk IDs and
corpus years, and its outcome/rejection stage in diagnostics and the safe turn
log. Query text, model assessments and raw provider errors are not added to logs.

`facts.py` enumerates narrative amounts from displayed source spans. Candidate
numbers, scales, explicit period headings and quotes come from code, not model
transcription. The no-tool selector chooses two candidate IDs and their supported
segment; mechanical checks and the independent judge must pass before IDs become
calculator inputs. `calculate(first_fact_id, second_fact_id)` accepts only the
ordered verified pair from this request. No arbitrary numbers or new operations
can be supplied by the chat agent. `ratio_percent` means `100 * first / second`,
including ratios of annual increases; it does not label the result a company's
reported gross margin. Ambiguous tables, missing explicit headings, and inputs
requiring chained arithmetic return gaps rather than guessed values.

`calculate` is now an output tool: after preparation succeeds it is the sole
available final output, with both argument schemas restricted to the ordered
verified fact IDs. Before verification it is unavailable. It computes the
Decimal record and builds the typed calculation claim and source references in
code, ending the agent run without another model call to submit a calculation
ID, claim kind or prose. Invalid/reordered IDs fail before creating a record.
The existing orchestration still validates the returned answer and recomputes
the stored calculation before backend rendering. Already verified input pairs
retain their existing semantic approval. Prose/lookup answers keep final_result;
failed preparation can still return controlled evidence gaps.

`calculations.py` uses Decimal arithmetic with checked cited inputs. The backend
rechecks source inputs and recomputes each calculation before accepting its record;
incorrect units, periods, signs, formulas, results or display values cannot be
authorized by an LLM verdict. Factual numeric checks also preserve accounting negatives.
The backend
renders calculations from the recorded operands and result, never the model's
computed prose. The judge checks the same canonical calculation text shown to
the user when inputs have not already passed semantic verification. For the guided
flow, the exact operands and operation must match the turn's verified fact pair;
the final calculation reuses that semantic verdict and passes fresh deterministic
input/arithmetic checks. It does not pay for a contradictory second assessment of
the same inputs. Other claims still require the independent judge. The numeric
input judge has dedicated instructions: source parsing and mechanical checks
establish exact narrative amounts, inline units and quoted headings; semantic
verification checks the requested measures and company/segment scope. It must
verify the meaning, scale and period of each
operand; finding a numeric token alone is insufficient.
Each semantic decision includes a bounded evidence assessment. The judge must
reject unsupported qualifiers, trend/urgency claims, causal leaps and assertions
that an entire filing omits a topic based only on excerpts. These checks remain
heuristic; calibration results distinguish application safeguards from raw judge
performance rather than claiming the judge is infallible.
The calculator also requires quoted explicit years and currency/scale or percentage
labels. Bare numeric rows cannot authorize calculations using inferred periods.
Before model judging, financial prose with recognized measures and numeric amounts
must state an explicit year present in its attached quotes, currency for
money, and matching scale words when supplied. Filing labels and 'prior column'
do not bind a financial period. Percentage-only figures do not require currency.
Cross-company interpretations naming the five pilot companies must attach sources
from each named company to that claim; other claims' sources cannot substitute.
These conservative English-language checks catch missing context, not semantic
entailment: the judge still verifies column binding, units and meaning. They do
not reconstruct flattened tables or guarantee complete comparison coverage.
Year wording is flexible ('in 2025', 'FY2025', or 'fiscal 2025'); this check does
not require a particular English phrase. The judge must still establish fiscal
meaning from the actual source and reject wrong periods or ambiguous columns.
After the existing repair limit, a comparison failing only those financial
context checks returns no claims and an explicit ambiguous-figures gap for every
registered target. This owner-approved fallback reports inability to verify,
not missing information in the filing. Other structural errors, judge rejections
and provider failures retain controlled failures. Safe turn logs include fixed
structural-error categories per attempt and whether this fallback was used;
rejected model text and raw validation errors are not logged. An uncited number
on a claim already rejected for financial context can also trigger this no-claims
fallback. Uncited numbers on other claims, invalid quotes and unknown sources
still block it. Logs associate each fixed error category with safe claim indices.
Unknown metadata fields are omitted from the judge payload; the citation UI
retains unverified fiscal-year/page labels. Explicit quoted fiscal headings can
establish periods independently of those index fields. Repair feedback includes
the judge's bounded explanation of the unsupported content.

Settings live in `app/config.py`; names/defaults are listed in `.env.example`.
Answering uses `OPENAI_CHAT_MODEL`, judging uses `OPENAI_GROUNDING_MODEL` (both default
to `gpt-4o-mini`). Existing actual environment files are never rewritten.
Defaults: 20 generator requests, 12 tools (4 retrievals), 50 unique exposed chunks,
48,000 cumulative source characters, 12,000 characters per tool response,
20 claims/5 references per claim, 3,000 generator/2,000 judge output tokens,
one output-schema retry per attempt, one grounding repair, 120 seconds per turn.
Numeric preparation shares the generator's cumulative request budget and permits
`grounding repairs + 1` attempts (default two). Each preparation uses up to three
retrieved passages and at most 40 bounded narrative candidates. Its fact-support
judge calls are counted separately from the at-most-two whole-answer judgments,
allowing at most four judge requests by default; all are included in usage totals.
Tools are disabled at the budget boundary. Retrieval still prepares embeddings
and keywords separately; those calls and judge usage are accounted separately.

## Chat behavior and limits

Excerpt scope is enforced before probabilistic judging: recognized assertions
that an entire filing never mentions a topic are rejected, including in gap
details. A disclosed negative fact ('we do not manufacture chips') and a scoped
retrieval limitation remain eligible for judging. These are conservative English
patterns, not exhaustive semantic classification. Cross-filing 'most/least
explicit' interpretations need cited alternative filings for each company.

Search/compare exposure uses the prepared lexical query (or question when lexical
preparation is unavailable) to choose a verbatim window at sentence boundaries.
Reads use the current question. Simple word-prefix overlap selects text, never
establishes support or changes RRF ranks, filters, document ownership or IDs.
Unrelated original table context no longer crowds out a relevant narrative.
Complete-span rules, exact quote verification and all output budgets remain.
Specific missing_detail text is rendered for every gap reason; an empty target
does not print an orphan colon. Wording/urgency gaps should use missing_evidence,
with a specific limitation, rather than a causal-relationship reason.

Original-table evidence is restored at read time from `source_documents.markdown_content`.
The indexed chunk text and embeddings remain unchanged. Hydration verifies the
chunk's recorded source SHA-256 (including ingestion's known Windows newline
translation), resolves its Docling table reference, and exposes bounded verbatim
Markdown headers/rows together. Matching explicit fiscal headings or the filing's
printed fiscal cover heading remain separate source spans; fiscal-year metadata
is never inferred or rewritten. A source hash mismatch fails the read.
The registry checks these spans against the verified source context and against
what the tool displayed. Unselected context is excluded from judge metadata.
Saved citations label original table context separately from indexed chunk text;
source snapshots survive reopening without a local Markdown-file dependency.
This is bounded source context, not comprehensive table cleanup or a new index.

Authentication and the owned-thread lock precede paid work. History comes from
the latest six complete server-side pairs within 12,000 characters. History is
context, never current evidence. Retrieval uses separate read-only connections.

Progress is transient SSE; answer text starts only after acceptance. Final text,
source snapshots and normalized citations are saved together. `finish` follows
commit. Completed-ID retries replay saved parts without model calls. Stop,
disconnect, timeout, invalid grounding or persistence failure rolls back the
unfinished turn. A provider can still bill work already accepted before Stop.

Source links use authoritative filing metadata. Corpus year, filing date and
fiscal year remain separate; unknown fiscal years/pages stay unknown. The corpus
is still the 25-filings pilot, not the full client-brief universe. Extraction
cleanup remains deferred. A heuristic judge is an additional check, not proof of
truth. Controlled insufficient evidence, grounding rejection, service failure,
timeout and budget exhaustion are distinct outcomes.

Token counters describe known returned usage; canceled/failed upstream work may
not return complete billing information. Broad table-heavy questions currently
need further quality review; see [answer evaluations](../../../docs/evaluations/assistant-results.md).
