# Document Copilot: AI agent handoff

Snapshot: **2026-10-24**. Implementation baseline: `3172020`. This is an
onboarding map; [AGENTS.md](../AGENTS.md), [backend instructions](../backend/AGENTS.md)
and [frontend instructions](../frontend/AGENTS.md) remain authoritative.
[CLAUDE.md](../CLAUDE.md) imports the shared instructions. Do not restore old
architecture or citation rules from the historical evaluation notes.

## 1. Product, agreed scope and accepted milestones

Document Copilot is an internal SEC-filings research assistant for the fictional
Driftwood Capital. Analysts ask questions, inspect exact cited passages, and
revisit their private conversations. See [client brief](client-brief.md).

The owner is learning while building this tutorial project. Follow the owner
involvement rules: automate routine work; obtain decisions on consequential
architecture, authorization, retrieval, grounding and deployment changes.

**Current scope:** the owner accepted a pilot on the existing 25 10-Ks for AAPL,
AMZN, GOOGL, MSFT and NVDA, corpus years 2021–2025. Full S&P 500 10-K/10-Q
coverage is deferred, not implemented; [scope decision](guides/corpus-scope-options.md).
The stand-in pilot uses the owner as one analyst. Its results cannot satisfy the
original brief's five-senior-analyst client acceptance requirement.

Recorded gates:

- Phase 5 retrieval: owner accepted lookup/comparison evidence on 2026-10-18.
- Phases 6–7: owner accepted grounded replies and analyst UI on 2026-10-22,
  with the limitations below. Comparisons now publish per-filing facts and gaps.
- Phase 8: closed 2026-10-23, including two approved accounts and one unapproved
  account in the browser confidentiality check. The latest 17-case evaluation
  completed; completion is distinct from comprehensive evidence coverage.
- Phase 9: provisionally closed by owner on 2026-10-24 for the one-person pilot.
  Both Railway services deployed; public health/auth-rejection/SPA/CORS
  checks passed on 2026-10-24. The owner also reports hosted question/citations,
  reload persistence, two-account isolation, unapproved refusal and restart/history
  recovery passed. The owner also confirms remaining feature checks and spending
  controls pass. Backup/restore and hosted capacity are explicitly deferred;
  rollback verification remains untested. Full evidence and limitations are in
  [delivery status](operations/delivery-status.md).
- Phase 10: stand-in scheme prepared in [pilot plan](pilot/pilot-plan.md);
  real owner timings and results are pending. Do not invent pilot outcomes.

Evidence labels: **implemented** means code exists; **recorded** means a dated
check or owner verdict; **pending** means no adequate confirmation yet. A green
unit suite or an accepted model response is not an independent accuracy verdict.

Onboarding baseline rechecked 2026-10-23: **473 offline tests passed, 15 integration
tests deselected**; backend lint and frontend type/lint/build passed. The frontend
build has a non-blocking chunk-size warning. These are not hosted checks.
Delivery verification: **477 offline tests passed, 15 integration tests deselected**;
four deployment-helper regressions were added. Backend lint passed.
At the baseline the working tree was clean and Claude's features were committed.
Inspect `git status` before editing; delivery documentation may now be uncommitted.

## 2. Architecture and request lifecycle

Locked stack: React 19/Vite 8/TypeScript SPA, FastAPI/Python, Supabase Auth and
Postgres, pgvector + English full-text search, OpenAI and PydanticAI. Railway
runs a static Caddy frontend and one backend process/replica. SQLAlchemy models
and Alembic own schema definitions; request-path SQL primarily uses psycopg.

Browser entry: `frontend/src/main.tsx` → `App.tsx` → `AuthProvider`/`AccessGate`.
Supabase manages email signup/sign-in. Confirmation alone does not admit a user:
an approved `public.users` profile is required. Approval remains an admin CLI.
A separate reviewer demo account was created by the owner and approved on
2026-10-26 using the existing CLI; its hosted sign-in remains an owner check.
Credentials are shared privately, and all reviewers on that identity share its
history and quota. This adds no guest mode or authentication bypass; see
[runbook](operations/runbook.md#11-reviewer-demo-account).

Backend auth verifies bearer tokens with Supabase; privileged database operations
explicitly enforce thread ownership. Approved users share the SEC corpus; chat
history is private. Departmental authorization/multi-tenancy is not implemented.

Turn lifecycle:

1. Authenticated `/chat/stream` checks ownership and locks the thread. Stable IDs
   derive from thread ID plus client question ID; completed retries replay saved
   content/citations without repeat model generation.
2. A small conversational front door answers safe small talk/help directly or
   rewrites a follow-up into a standalone filings question. The latter is shown
   as “Answered as”. Doubtful factual requests use the filings pipeline.
3. Request-scoped dependencies hold bounded server history, exposed evidence,
   usage, tools and calculations. Source text/history are untrusted data.
4. Retrieval/tools provide observed E evidence IDs. Typed facts and requested
   gaps undergo structural validation and a no-tool semantic judge. A bounded
   repair may correct errors; unverified claims can be withheld with a notice.
5. Backend rendering assigns citation numbers and structured `data-answer` /
   `data-citation` parts. Progress precedes validation; accepted text is then
   transmitted using the AI SDK 7 SSE UI-message protocol, not raw model tokens.
6. Messages, parts and citation snapshots commit together before successful
   `finish`. Interrupted work is not saved as a successful turn. A disconnect
   after commit can be recovered by replay. Generated titles run alongside a
   new answer and never overwrite a manually renamed title.

The workspace keeps active/retryable views mounted while switching chats.
Page unload can still cancel work: there is no durable background-job system.
Account-scoped tab session storage preserves questions/IDs for explicit retry.
New chats are drafts until first send; thread management includes title search,
rename and permanent deletion, with active-thread deletion refused. Feedback
is per assistant reply, ownership checked, and restored with history.

## 3. Retrieval, ingestion and trust decisions

Offline ingestion: `data/download.py` → `data/convert.py` (Docling) →
`backend/ingest/{preview,trial,filing}.py` → documents/chunks/vectors. Payloads,
Markdown and caches live under ignored `data/` directories. Ingestion reuses
matching progress and rejects changed source/config/content; cited-chunk refresh
needs an explicit migration strategy. Do not re-download/re-embed for deployment.

`DocumentRetriever` supports `search`, `compare`, `read_chunk` and
`read_surrounding_chunks`. Full-question embedding and typed keyword extraction
run concurrently. Semantic cosine search and FTS use separate read-only worker
connections and identical completed-document/model/filter restrictions. Defaults:
50 candidates/branch, RRF constant 60, 10 primary hits and one neighboring chunk
per side. Comparisons prepare once, keep up to 25 targets including empty ones,
return three primary hits per target, and run two target searches concurrently.
Keyword failure visibly degrades to semantic-only; DB/embedding failures fail.

The corpus/query embedding pair is enforced as `text-embedding-3-small` / 1536
dimensions. Changing an env value alone is not a provider/index migration.
RRF is a ranking score, not a confidence probability. No external reranker exists.
Original hash-verified Markdown table context supplements indexed chunks without
rewriting their text/vectors. Table rows and narrative evidence remain distinct.

Important decisions superseding the older phase-6 implementation:

- **Comparisons are facts-only.** Trend/urgency/cross-company interpretations are
  reported as gaps. Do not resurrect the earlier grouped-interpretation writer.
- **Up to eight references per claim**, matching current settings/output types.
  The previous five-total allocation workaround is historical.
- **Grounding is fallible.** Provenance, numeric/unit/period checks and the judge
  remain; fixed notices cover advice/causation, and unsupported facts are withheld.
- **Calculator inputs are verified narrative facts**, with measure, scope, units
  and fiscal periods checked before Decimal arithmetic. Table-column calculations
  remain unsupported. Verified calculation output completes directly.
- **Page/fiscal mapping is implemented.** `ingest.pages` maps printed original-HTML
  page ranges; `ingest.fiscal_years` verifies XBRL year focus against report date.
  Corpus year, filing date and fiscal year remain different labels. Unmapped
  passages and borrowed headings must keep unknown page metadata.

Approved read-only inventory 2026-10-23: migration head `3ff92ab46eb9`, 25/25
completed documents, 5,396 chunks, no missing vectors/FTS vectors or embedding
model/dimension mismatches, 25 verified fiscal years, 5,260 chunks with page
labels (97.48%). This does not certify every extraction/section assignment.

## 4. Implemented features and remaining limitations

Implemented extensions: structured answer/citation UI with exact-source opening
and copy, feedback with reason/comment, rename/delete/title search, safe generated
titles, small talk/help/unrelated routing, standalone follow-ups, per-user answer
limits, transaction-pooler support, printed page ranges and fiscal-year metadata.
The feedback migration is `3ff92ab46eb9_message_feedback.py`; it follows the
initial `ab55919814e7` schema migration.

Accepted quality backlog (delivery-first decision, 2026-10-23):

- Q09 regional revenue tables remain hard to retrieve.
- Q08 can include an off-topic but source-supported claim.
- Q04 period coverage is uneven; section labels outside Item 1A need care.
- Table-backed calculations are not implemented; judge calibration still misses
  subtle relationships. Refusals/gaps and fact-only comparisons are deliberate.
- The five-company 10-K corpus is not full client coverage.

Public hosted SPA/CORS/cache checks and the served-bundle/bounded-log scan passed
on 2026-10-24. The owner reports hosted sign-in, question/citations, reload
persistence, account isolation/unapproved refusal and restart/history recovery
passed. Feedback add/change/remove and manual rename/search/reload also passed
per owner report, as have chat switching during generation, Stop, Retry and reload
without duplicates. The owner subsequently reports final feature checks
(follow-ups, generated-title/manual-rename protection, disposable-chat deletion)
and spending controls pass. Phase 9 is provisionally closed for the one-person
pilot: backup/restore and hosted capacity testing are explicitly deferred, and
rollback verification remains untested. Exact spending thresholds were not
independently read back. No database-loss recovery or broader capacity is proven.
Future logs still need normal operational review. Local 12-turn success is not
proof of capacity for 40 users.
The latest rollout checklist is [todos](todos.md); its older dated records are
history, not instructions to reopen accepted milestones.

## 5. Setup, configuration and checks

Use service-local environments and existing lockfiles. Python >=3.12; current
backend image uses Python 3.14.7. Vite requires Node ^20.19.0 or >=22.12.0; the
frontend image uses Node 24.18.0. uv and pnpm enforce seven-day release age.
Do not overwrite existing `.env` files. Never print credentials or raw DB/SDK
errors; live checks use sanitized output and `--tb=no`, never `--showlocals`.

From `backend/`:

```powershell
uv sync --locked
uv run --locked python -m uvicorn app.main:app --reload --port 8001
uv run --locked python -m pytest -m "not integration" -q --tb=no
uv run --locked ruff check app tests ingest scripts ../deploy
```

Health `/health`; Swagger `/docs`. Select `backend/.venv/Scripts/python.exe`
for editor/Jupyter kernels. Do not use Conda/root environments accidentally.
`pyproject.toml` now excludes integration tests by default; explicitly selecting
`-m integration` can use live credentials and spend money.

From `frontend/`, in another terminal:

```powershell
pnpm install --frozen-lockfile
pnpm dev
pnpm exec tsc -b
pnpm lint
pnpm build
```

Use localhost:5173 with API port 8001 for development. Restart services after env
changes. Frontend tests/test runners are prohibited by its AGENTS; verify manually
plus type/lint/build. Central env modules are `backend/app/config.py` and
`frontend/src/lib/env.ts`. Required backend names: `SUPABASE_URL`,
`SUPABASE_ANON_KEY`, `DATABASE_URL`, `OPENAI_API_KEY`, `ALLOWED_ORIGINS`.
`SUPABASE_SERVICE_ROLE_KEY` is optional/admin-only and stays off hosted services.
Only `VITE_API_BASE_URL`, `VITE_SUPABASE_URL`, `VITE_SUPABASE_ANON_KEY` enter the
browser. Model settings in examples are not proof of active private env values.

Production runtime uses the transaction pooler (6543, prepared statements
disabled); migrations/ingestion use session/direct (5432). Reuse the existing
Supabase project. One backend process/replica is required for in-memory limits:
2 new turns concurrently per user, 60/hour, 120-second answer deadline; completed
replays are exempt. Limits reset on restart and are not distributed quotas.

Live/database batches, paid smoke runs and capacity tests require explicit
scoped approval. Deployment authorization does not authorize unlimited model
calls. Include triage/title/keyword/embedding/answer/judge calls in budgets.
Never invent human timings or count CSV example rows as pilot observations.

## 6. Where to continue

1. Read [delivery status](operations/delivery-status.md) and
   [operations runbook](operations/runbook.md); finish recorded deployment gates.
2. Run only separately approved hosted checks; retain exact evidence and failures.
3. Conduct the [stand-in scheme](pilot/pilot-plan.md) with the owner performing
   human tasks. Report observed savings and risks, not real client acceptance.
4. Keep the accepted quality backlog deferred unless a blocking trust failure
   requires a narrowly reviewed correction. No provider/corpus/architecture
   changes, CI expansion or bundle optimization are part of this delivery.

## 7. File map

| Need | Start with |
| --- | --- |
| Shared rules / product | root and service AGENTS, CLAUDE.md, client-brief.md, todos.md |
| Backend entry / identity | app/main.py, config.py, api/auth.py, auth/dependencies.py |
| Threads / feedback / storage | api/{threads,chat,feedback}.py, database/chats.py, database/models/, alembic/versions/ |
| Turn lifecycle / front door / titles / limits | chat/{orchestrator,streaming,messages,triage,titles,limits}.py |
| Tools and evidence | assistant/{agent,deps,tools,selection,outputs,excerpts}.py |
| Fact-only comparisons / numeric flow | assistant/{comparisons,comparison_citations,facts,calculations}.py |
| Grounding / safe failures | grounding/{validator,claim_context,judge}.py, assistant/{failure_diagnostics,model_settings}.py |
| Source metadata / hybrid search | retrieval/{retriever,queries,table_context,types,embeddings,keywords,fusion}.py |
| Ingestion and mapping | backend/ingest/{preview,trial,filing,pages,fiscal_years}.py; data/{download,convert}.py |
| Browser routing / access | frontend/src/App.tsx, components/{AuthProvider,AccessGate}.tsx |
| UI and recovery | components/chat/, pages/{ChatLayout,ChatThreadPage,NewChatPage}.tsx, lib/{chats,chat-parts,pending-chat}.ts |
| Deployment | service Dockerfile/.dockerignore/railway.json, frontend/Caddyfile, deploy/push_railway_env.py |
| Verification | backend/tests/, scripts/smoke_{retrieval,assistant}.py; live markers require approval |

Latest quality evidence: [phase-8 results](evaluations/phase-8-results.md).
Historical rationale: [guided comparisons](guides/guided-comparisons.md),
[phase-six record](guides/phase-six-progress.md), [owner review](evaluations/assistant-owner-review.md).
Later dated decisions supersede the original phase-6 failures. Ignored diagnostics
under `data/chunks/assistant/` are local evidence, not a portable runtime dependency.

## Public demo extension — local work, 2026-10-27

The owner approved isolated Supabase anonymous identities, up to three generated
attempts per identity, one active attempt, 100 admissions/day and a shared $1/day
anonymous OpenAI pool. Implementation is local/uncommitted and disabled by
default; it has not been deployed, migrated or exercised with real guests.

See [approved design](superpowers/specs/2026-10-27-public-demo-design.md),
[implementation plan](superpowers/plans/2026-10-27-public-demo.md), and
[accounting/rollout notes](../backend/app/demo/README.md). The new migration is
`d90e7c5a2101`, after `3ff92ab46eb9`; apply/review the additive schema before
releasing the changed backend because normal auth also reads `users.is_demo`.

All runtime OpenAI client constructors use a turn-scoped demo HTTP meter. Durable
independent transactions reserve conservative request bounds before dispatch and
retain uncertain costs; chat rollback/deletion cannot refund them. Demo status
and admission require enough available funds for the mandatory first triage call.
The budget covers anonymous traffic only; existing regular/shared-reviewer
accounts remain outside it. Normal registration still requires approval.

Remaining gates: reviewed backup/rollback decision for this new schema,
disposable-DB migration/concurrency/RLS checks, Supabase anonymous Auth settings,
two-guest isolation/manual browser checks, separately approved paid smoke checks,
and rollout with demo disabled before public enablement. No real-user pilot or
accuracy/time-saving claim follows from the local feature tests.
