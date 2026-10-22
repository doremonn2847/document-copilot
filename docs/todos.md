# Document Copilot implementation checklist

Build order: backend foundation → database and identity → a thin frontend with
working chat plumbing → ingestion → retrieval → grounded answers → polished
citations → deployment → analyst pilot.

Build both sides in small connected steps. Do not finish the entire backend before
trying it from the browser. Each milestone below has an observable completion gate.
Mark a task complete only after checking its result.

References: [client brief](client-brief.md), [architecture](architecture.md),
[backend setup](guides/backend-setup.md), [frontend setup](guides/frontend-setup.md).

## 0. Starting point

- [x] Install and verify Python, uv, Node.js, and pnpm.
- [x] Copy the tutorial's `Document Copilot Setup` snapshot, including all `AGENTS.md` files.
- [x] Initialize Git and push the setup commit to our GitHub repository.
- [x] Download the initial SEC sample files and manifest into ignored `data/downloads/`.
- [x] Check the manifest and downloaded files cover the expected 25 filings: AAPL, AMZN, GOOGL, MSFT, and NVDA, fiscal years 2021–2025.
- [x] Turn the ten example questions in the client brief into an evaluation worksheet: expected companies/years, source passages, figures, and appropriate refusals. Start with a few simple questions and expand as ingestion becomes available.
- [x] Resolve page citations before choosing the extraction format: preserve actual filing page labels and source locations. HTML line numbers or invented page numbers are not valid substitutes. If reliable pages are unavailable, obtain client agreement on section/anchor citations before considering this requirement satisfied.

**Gate:** The starting scope and evidence needed to demonstrate success are clear.

## 1. Backend foundation

- [x] Set up the backend environment with uv and add the declared backend dependencies as needed; add pytest and Ruff for development.
- [x] Verify dependency pinning and release-age configuration uses valid uv settings and is actually enforced; commit the generated lockfile.
- [x] Create the FastAPI entry point and a health endpoint; run it locally with Uvicorn.
- [x] Add the central Pydantic settings module, a safe `.env.example`, and ignored local environment files. Validate required configuration at startup.
- [x] Configure explicit development CORS origins and structured logs without credentials or bearer tokens.
- [x] Add a small backend test foundation and verify the health endpoint and configuration failures.

**Gate:** The backend starts reproducibly, serves a health response, and reports missing configuration clearly.

## 2. Database, migrations, and identity

- [x] Create the Supabase project and configure email authentication for the internal application.
- [x] Decide admission policy: public registration, email confirmation, then manual approval via the administrator CLI. Only approved profiles gain app access; email verification alone does not admit outsiders.
- [x] Configure the backend Supabase clients and direct/session Postgres connection for Alembic.
- [x] Define SQLAlchemy models for profiles/users, chat threads, messages, citations, source documents, and document chunks, with foreign keys and ownership fields.
- [x] Add reviewed Alembic migrations for tables, `pgvector`, embedding dimensions, generated full-text vectors, and HNSW/GIN indexes.
- [x] Add RLS policies and grants; restrict private conversations to their owners and corpus access to approved authenticated users. Enforce approval on protected routes; future privileged resource operations must also check ownership.
- [x] Apply migrations to a fresh development database and verify they reproduce the expected schema.
- [x] Verify Supabase bearer tokens in FastAPI and derive identity from the verified session.
- [x] Test missing/expired/invalid tokens and unapproved users with mocked Auth responses; verify cross-user isolation and database permissions against live Supabase with two temporary database identities (all fixtures rolled back).
- [ ] Verify real invited-user sign-in and `/auth/me` with two actual Supabase sessions; confirm an account without an approved profile receives 403. This remains necessary before declaring the milestone gate complete.

**Gate:** An approved user can authenticate; another user cannot read or modify their conversations.

## 3. Connect the frontend and prove chat plumbing

- [x] Scaffold Vite + React + TypeScript while preserving the existing `.npmrc` and agent instructions; configure React Router, Tailwind, shadcn/ui, and the import alias.
- [x] Add central frontend environment validation and the shared Supabase browser client. Only public configuration belongs in the browser.
- [x] Build public sign-up, email confirmation guidance, login, logout, pending-approval screens, protected routes, session restoration, and handling for rejected/expired sessions.
- [x] Verify public registration/sign-in → pending approval → manual approval → Check again → approved workspace with an actual browser account (confirmed by the developer).
- [x] Verify the approved session survives page reload, logout returns to login, and protected routes reject access after logout (confirmed by the developer).
- [ ] Verify email-confirmation and expired-session behavior explicitly with actual browser sessions.
- [x] Build the shared native-fetch API client with automatic bearer-token injection and clear HTTP/network error handling.
- [x] Add backend endpoints to create/list threads and read ordered message history; enforce verified-user ownership on every operation. Verified with unit tests and live SQL/API checks using temporary identities (fixtures rolled back).
- [x] Add `POST /chat/stream` with a deterministic test response in the installed AI SDK 7 UI-message protocol; verify using its actual transport/parser. Save completed turns atomically, roll back interrupted turns, and replay completed retries without duplication.
- [x] Connect a minimal chat screen, input, message list, and thread sidebar to FastAPI using the AI SDK React primitives. TypeScript, lint, and production build pass; actual browser flow remains part of the gate below.
- [ ] Persist completed test turns and restore them after page reload. Define failure/cancellation behavior so partial answers are never stored as successful turns.
- [x] Implemented backend atomic persistence and frontend history/Stop/Retry with stable question IDs. Browser send → reload → Stop → Retry verification remains pending.
- [ ] Verify invalid payloads, unknown threads, forbidden threads, upstream failures, and interrupted streams are handled clearly.

**Gate:** Log in → create a chat → see a streamed test answer → reload and recover history → log out. This milestone does not yet use the LLM.

## 4. Prepare documents for retrieval

Owner scope decision: keep existing converted text for the tutorial. Heading/table
cleanup, original-page mapping, and verified fiscal-year labels are deferred;
they do not block pipeline ingestion. Do not present them as verified.

- [ ] Review the SEC downloader's identifying user-agent, request pacing, and error handling before additional downloads.
- [x] Convert all 25 existing filings into Markdown and retain source URL/accession metadata; use the extracted text as-is for the tutorial.
- [ ] Deferred: normalize financial tables and verify headings, units, fiscal periods, footnotes, and original citation locations against the filing.
- [x] Store documents and metadata in Supabase; use a stable identifier so rerunning ingestion does not create duplicates.
- [x] Implement token-aware chunking with contextualized inputs and an exact token limit; preserve available Docling context without inventing missing headings.
  - Local preview verified on Apple 2025: 164 chunks, max 1,017 tokens. Owner approved `data/chunks/selected-chunk.md` and later accepted extraction limitations for the tutorial.
- [x] Store chunk text, ordering, source URL/hashes, company/corpus-year/filing-type metadata, and available sections; leave unverified pages/fiscal years empty. Original offsets/page mapping are deferred.
- [x] Generate embeddings with the configured model and dimensions; batch requests, handle transient failures, and record enough progress to resume.
  - [x] Single-chunk trial passed, then Apple 2025 completed with 164 chunks. Full-filing rerun reused all chunks with zero API tokens. Three real-question vector searches found relevant passages.
- [x] Make refresh/re-chunk behavior explicit so outdated chunks cannot remain mixed with new ones: reject changed source/config/content; require an explicit future refresh workflow instead of silently replacing cited chunks.
- [x] Test chunking limits, lossless overflow splitting, cache reload, conflicting reruns, response ordering, and invalid vectors; verify the Apple pilot before all 25 filings. Backend offline suite: 69 passed.
- [x] Verify corpus storage: 25 complete filings, 5,396 chunks, no missing embeddings/full-text vectors/required metadata, no ordering gaps or duplicates, all vectors 1536 dimensions. Full rerun reused all chunks with paid API calls blocked and never attempted.
- [x] Smoke-test semantic retrieval on Apple tariffs, Microsoft Azure, and NVIDIA CUDA; retain detailed results under `data/chunks/`. Full retrieval evaluation belongs to batch 5.

**Tutorial gate passed (2026-10-18):** Every sample filing is stored as searchable
data; chunks retain filing URLs and content hashes. Exact source-page locations
and extraction fidelity remain explicitly deferred by the owner.

## 5. Prove retrieval before generating answers

- [x] Embed questions using the indexed `text-embedding-3-small` model and 1536 dimensions; validate responses and question limits.
- [x] Implement bounded pgvector cosine search and English Postgres full-text search with identical completed-filing/model/company/year/form restrictions.
- [x] Fuse ranked IDs with RRF (k=60, 50 candidates per branch, top 10), deterministic ties, and deduplicated same-document neighbors.
- [x] Support company, corpus-year, verified fiscal-year, and filing-type constraints. Never infer fiscal year from filing date or corpus year; current fiscal years remain unverified.
- [x] Retrieve three primary passages per explicit comparison target (up to 25), prepare the question once, preserve empty targets, and limit target concurrency to two.
- [x] Add `scripts.smoke_retrieval` with formatted/JSON output, explicit targets, branch rankings, usage, timings, and warnings; no answering model call.
- [x] Test ranking, SQL parameters/filters, metadata labels, keyword schema/retries, degradation, output limits, and comparison behavior offline; add marked live checks. Offline backend suite: 89 passed.
- [x] Marked live retrieval suite: 6 passed. All ten worksheet questions ran over 110 explicit targets; all keyword extractions succeeded. FTS returned candidates for 44 targets; empty lexical branches and evidence-quality caveats are recorded in the worksheet. This is not a relevance score.
- [x] Owner accepted [the Azure lookup and Apple comparison](evaluations/retrieval-evidence-review.md) on 2026-10-18, completing the phase-5 sample evidence review.
- [x] Owner accepted [the complete ten-question retrieval worksheet](evaluations/retrieval-results.md) on 2026-10-18. Phase-5 evidence review is complete; answer accuracy and grounding remain phase-6/broader quality-evaluation work.

**Gate passed (2026-10-18):** Implementation and technical checks are complete;
the owner accepted the lookup, multi-year comparison, and complete retrieval
worksheet. Lexical gaps and source-quality limitations remain recorded.

Implementation, settings, commands, and phase-6 handoff:
[retrieval README](../backend/app/retrieval/README.md).

## 6. Generate and validate grounded answers

- [x] Add the PydanticAI agent with explicit request dependencies and typed answer, citation, and source-passage outputs.
- [x] Expose bounded tools for searching filings and reading retrieved/neighboring chunks; keep database queries under application control.
- [x] Instruct the agent to answer only from evidence, cite each factual claim, explain evidence gaps, and avoid stock recommendations or outside knowledge.
- [x] Treat retrieved document text as evidence, not instructions; live answering-agent injection check passed over a labeled synthetic source.
- [x] Validate that every citation references an actual passage retrieved for this turn and has accurate filing/location metadata; quotes must have been exposed this turn and unknown locations remain unknown.
- [x] Check claim support, not only citation existence. Validate numerical units, periods, and any computed margins or comparisons against cited inputs; clearly label calculations and interpretations. Closed with known limitations (2026-10-22): a semantic judge checks every claim and model-written gap, but it misses subtle errors such as reversed relationships; guided comparisons therefore publish facts and gaps only.
- [x] Return an explicit insufficient-evidence answer when appropriate, and controlled failures for invalid/unsupported citations. Correctness of individual refusals remains review work.
- [x] Decide how validation interacts with streaming: progress first, accepted text after validation, successful finish after commit. Rejected drafts are never displayed or saved.
- [x] Connect retrieval, generation, validation, streaming, and persistence in the chat orchestrator; support bounded server-owned follow-up context and replay saved citations without repeat model calls.
- [x] Record model usage, latency, and safe failure categories; bound context size, tool calls, output size, and timeouts.
- [x] Add offline citation/refusal/orchestration/persistence tests, marked live source-injection and judge checks, live database atomicity checks, and a checkpointed CLI evaluation of all ten client questions. A recorded evaluation run is not a quality pass.

Implementation and evidence: [execution record](guides/phase-six-progress.md),
[answer worksheet](evaluations/assistant-results.md), and
[owner review cases](evaluations/assistant-owner-review.md).

**Owner browser review complete (2026-10-19):** The owner confirmed all five
proposed reviews work as expected, including the guided calculation, source
inspection/history, reload, Stop/retry, connection recovery and unsupported-target
refusal. Verdicts are recorded in the review sheet's
[final manual-review gate](evaluations/assistant-owner-review.md#final-manual-review-gate).

**Guided calculation update (2026-10-19):** The owner-approved verified-fact flow
now passes two autonomous live checks of the Microsoft reported-increases ratio,
returning 65.56% with three source citations. The owner also confirmed the new
flow in the frontend; existing evidence verdicts are preserved. This does not close the broad
claim-support or independent-judge calibration gate.

**Gate remains open (2026-10-20):** The Microsoft five-year comparison and direct
calculator output now pass live. The final bounded supplier comparison cites both
companies and retains all targets, but its coverage and urgency-gap presentation
remain incomplete. Application and raw-judge calibrations both accepted an
unsupported whole-filing absence assertion from a selected excerpt (10/11 correct).
Claim-support quality remains open; owner/browser review is complete. See the
[latest verification results](evaluations/assistant-results.md).

**Post-verification fixes (2026-10-20):** Application scope enforcement, supplier
excerpt selection, comparison-superlative checks and specific gap rendering are
fixed and covered by offline regressions/recorded-data replays. Fresh live
supplier and application calibration checks have not been run; no further API
credits were spent. Keep the claim-support checkbox open until that confirmation.

**Earlier corrections (2026-10-19):** Provider-enumerated evidence IDs replace model
transcription of quotes/UUIDs; incomplete sentences are uncitable previews. Input
verification is separate from final prose judging, arithmetic is recomputed, and
repairs receive specific support explanations. Verification: 185 offline tests and
five marked live checks passed, including the autonomous 65.56% ratio. A paired
answer-model check did not resolve the hard five-year comparison, and the final
supplier comparison still failed grounding. Keep the claim-support quality item
open; no additional owner review is currently required.

**Gate:** A real browser question produces a supported answer with verifiable sources, or clearly states that the available evidence is insufficient.

**Owner supplier review (2026-10-21):** The new browser answer has more cited
company/year blocks but repeats group limitations under already-supported years.
Specific gaps now preserve their group scope instead of expanding into misleading
yearly copies; uncited targets retain separate coverage gaps. This is an offline
correction, not owner acceptance or a live claim-support pass. Phase 6 requires
trustworthy claims and gaps; phase 7 improves presentation, and phase 8 evaluates
broader answer quality. See the [recorded feedback](evaluations/assistant-results.md).

**Instrumented supplier diagnostic (2026-10-21):** The second owner-capped run
captured a synthesis naming both companies with only Apple citations. The existing
rule now also rejects that mismatch at final submission and provides observed
company/year citation candidates within the existing output retry. Offline SDK
and recorded-metadata replays pass; 306 offline tests pass. No paid post-fix rerun
was made. The earlier numeric-token rejection remains unreproduced; keep the
claim-support gate open.

**Approved guided comparison (2026-10-21):** Typed planning now hands backend
retrieval to a tool-free comparison writer; invalid submissions and grounding
share one repair on frozen evidence. Gaps use server-owned request IDs, with
semantic relevance checks preserved. Implementation and focused offline SDK
checks are present. The one approved live check failed with an invalid judge
report; diagnostic capture interference and two contract issues were then fixed
offline (327 tests passed, 15 deselected). Browser confirmation remains pending.
The subsequently approved capped live check also failed (33.8 seconds): the
writer repeated an Apple/NVIDIA interpretation citing Apple only despite the
specific repair feedback. Three answering calls, no judging; no accepted answer.
See the implementation record for captured evidence. Phase 6 remains open.
The owner then approved grouped company citations for interpretations. Required
company fields now constrain source choices, with independent membership and
five-reference-total checks; 340 offline tests pass (15 deselected). Both saved
flat-citation drafts fail the new contract. No paid post-contract check has run;
the live quality gate stays open.
The approved grouped-contract live run then cited both companies, but selected
seven references and six on repair, failing the five-total limit before judging.
The schema's independent per-company maxima were corrected offline to enforce
the combined budget while preserving valid allocations. No live rerun has
followed that correction; no accepted supplier-comparison answer yet.
Offline verification after the combined-budget fix: 345 passed, 15 deselected;
affected Python lint/format checks pass. The claim-support quality gate stays open.
See [the implementation record](guides/guided-comparisons.md). The claim-support
quality gate remains open.

**Gate passed (2026-10-22):** In the owner's browser review, the Apple/NVIDIA
supplier comparison returned verified per-year facts and honest gaps, Tesla 2028
invented nothing, "Should I buy NVIDIA?" declined advice with cited facts, and
the Apple AI question returned supported facts with an honest gap. The owner
accepted the gate. Known limitations carried forward: the judge misses subtle
errors (comparisons are facts-only as a result), the writer can omit facts it
had evidence for, search planning missed Apple's AI-risk passages, and page
citations are unavailable. Details: [comparison record](guides/guided-comparisons.md).

## 7. Finish the analyst experience

Navigation update (2026-10-21): the owner approved continuing replies while
switching chats. Workspace-owned views now retain running/retryable conversations
across navigation and release completed background views. Stop and page-unload
recovery retain their existing behavior. TypeScript/lint/build checks pass;
manual navigation/Stop/logout confirmation remains pending.

- [x] Render readable Markdown, comparison tables, streaming status, and distinct provisional/completed/failed states. (2026-10-22: structured `data-answer` blocks; comparison facts grouped by company with year chips instead of Markdown tables; gaps under "Not established"; notices as banners.)
- [x] Make each claim's citation open the exact underlying passage in one click, showing company, filing, fiscal year, page/approved location, and original source link. (Page and fiscal year still read "unverified"; see phase 4.)
- [x] Restore citations and source passages correctly when reopening old conversations. (Malformed stored parts are skipped instead of hiding the thread.)
- [x] Add useful empty states and example questions drawn from the supported corpus. (Five examples, each answered live and checked against its quotes.)
- [x] Show clear messages for no evidence, unavailable sources, authentication expiry, network failures, and interrupted answers; avoid duplicate turns on retry. (Transient re-check failures keep approved users in the workspace.)
- [x] Manually verify keyboard use, long answers/tables, scrolling, and common browser sizes. (Owner browser check 2026-10-22: new-chat page, one-click citations, seven test questions, history after reload, keyboard, narrow window and stream interruptions passed.)
- [x] Run frontend TypeScript checks, lint, and production build; use manual browser verification per frontend agent instructions. (Checks pass; the manual check is the item above.)

**Gate:** An analyst can ask, verify, and revisit answers without developer assistance.

**Gate passed (owner, 2026-10-22).** One finding moved to phase 8: the Amazon
segment question sometimes fell back to "figures could not be verified"
(fixed in bcdbe6f; live confirmation pending).

## 8. Close the client-brief gaps and validate quality

- [x] Run all ten client example questions and record evidence coverage, factual accuracy, claim-level citations, location accuracy, latency, and cost. (2026-10-22: [phase-8 results](evaluations/phase-8-results.md); all ten answer truthfully, Q03/Q06/Q09 thin for retrieval reasons; locations are section/table, pages still unverified.)
- [x] Include negative cases: unsupported companies/periods, missing figures, ambiguous questions, and claims that the filings cannot establish (especially AI causing margin improvements). (Seven cases pass; causal and advice questions get fixed server notices.)
- [x] Verify financial comparisons respect units, fiscal calendars, segment changes, and restated figures; surface limitations rather than silently comparing incompatible values. (Amazon segments, Apple categories, Alphabet revenue lines and the Microsoft ratio verified against quoted rows and columns; scale, currency and period checks tightened. Table-backed calculations remain unsupported.)
- [x] Review failed cases and rerun the affected evaluations after fixes. Citation presence alone is not proof of correctness. (Every accepted claim was read against its quotes.)
- [ ] Extend ingestion to the brief's curated 10-K and 10-Q scope for S&P 500 companies across 2020–2025; define the company universe, inventory required filings, and report missing coverage.
- [ ] Process the broader corpus in resumable batches and verify retrieval/index performance and ingestion cost at that size. Any reduced pilot scope needs explicit client agreement.
- [ ] Recheck confidentiality with two analyst accounts and ensure the deployed bundle/logs do not expose privileged credentials.

**Gate:** The evaluation results demonstrate supported behavior and known gaps; the sample corpus is not mistaken for full client coverage.

## 9. Deploy and prepare operations

- [ ] Create Railway frontend and backend services; configure production build/start commands, health checks, and HTTPS URLs.
- [ ] Configure production secrets, exact CORS origins, and Supabase email confirmation/redirect URLs.
- [ ] Apply reviewed migrations using the correct connection mode and ingest the agreed corpus into the production database.
- [ ] Verify SPA route fallback and streamed responses through the deployed hosting stack.
- [ ] Add practical per-user request/concurrency limits, upstream timeouts, and provider spending alerts for the expected roughly 40 analysts plus partners.
- [ ] Measure concurrent usage on the chosen small/medium hosting footprint and agree acceptable answer latency before rollout.
- [ ] Document logs, troubleshooting, corpus updates, backup/restore, and application rollback; verify conversation history survives a backend restart.
- [ ] Run backend unit tests and relevant integration checks, frontend checks/build, and the full deployed login → question → citation → history flow.

**Gate:** Approved analysts can use the hosted app reliably, and one developer can maintain it using the runbook.

## 10. Pilot and definition of done

- [ ] Recruit five senior analysts and capture their baseline time spent on comparable document-intake tasks.
- [ ] Run the pilot for one week; record usage, time saved, incorrect/unsupported answers, citation problems, and feedback.
- [ ] Confirm the pilot reports at least three hours saved per analyst per week, as required by the brief.
- [ ] Resolve blocking trust/usability issues and repeat affected checks before the rollout decision.
- [ ] Obtain the pilot group's acceptance and roll out to the remaining approved analysts with a short usage guide and feedback channel.

**Done means:** The architecture works, evidence can be checked, private history remains private, and the analyst pilot meets the client's time-saving target.

## Later extensions — outside this delivery checklist

- Optional Ollama/Qwen answer generation for local development; verify tool calling, structured outputs, streaming, and quality with the selected model. Keep embeddings unchanged initially.
- Changing embedding models requires a planned re-embedding/index migration and matched query embeddings.
- Multi-organization tenancy, billing, external data, and trading recommendations remain outside the current client brief.
