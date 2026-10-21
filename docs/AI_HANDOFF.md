# Document Copilot: AI agent handoff

Snapshot: **2026-10-21**, current local working tree on `main`. This document is
an onboarding map, not a replacement for project instructions.

## 1. Start here: instructions, purpose and status

Read [root AGENTS.md](../AGENTS.md), then [backend instructions](../backend/AGENTS.md)
or [frontend instructions](../frontend/AGENTS.md) before editing that service.
Those files remain the shared source of coding conventions for Claude Code and
other agents. This task did not create a separate `CLAUDE.md` instruction set.

The owner is solo-developing while following the tutorial. Act as a teacher and
technical guide. Apply the owner-involvement check in `AGENTS.md`: automate
routine work; involve the owner in consequential architecture, authorization,
retrieval, grounding, streaming and schema decisions. Keep existing unrelated
changes intact. The checkout contains extensive modified **and untracked** work,
including the assistant, retrieval, ingestion and evaluation modules. A clone of
the last commit does not contain everything described here. Inspect `git status`
before changing, staging, resetting or moving work; no commit/push is requested
by this handoff.

### Product requirements and scope

The [client brief](client-brief.md) describes a fictional internal research
assistant for Driftwood Capital, roughly 40 analysts plus partners. Analysts ask
plain-English questions about a curated SEC corpus, inspect cited passages and
return to their private conversations. Trust requires supported claims, visible
evidence gaps, source links and accurate source locations. The brief requests
filing **page** citations; that requirement is not fulfilled by invented pages
or by labeling chunk indices as pages.

Intended client coverage is S&P 500 10-K/10-Q filings for 2020–2025. The current
sample is much narrower: 25 10-Ks for AAPL, AMZN, GOOGL, MSFT and NVDA in corpus
year folders 2021–2025. Previously recorded database checks found **5,396 chunks**;
this handoff did not recount the live database. Corpus folder year is not a
verified fiscal-year label.

Out of scope: stock picks/trading recommendations, external news or market
data, billing, mobile apps and multi-organization tenancy. Department-specific
document access was discussed as a possible future direction; no department
authorization model is implemented. Approved analysts currently share the SEC
corpus, while conversations are private to their individual owners.

The actual definition of done is a week-long pilot with five senior analysts
reporting at least three hours saved per analyst per week. No such pilot has
been established by the current evidence.

### Evidence labels used in this handoff

- **Implemented:** visible in the current code; not automatically production-ready.
- **Recorded verification:** earlier tests or owner/live checks documented in this
  session and repository; not rerun as part of this documentation task.
- **Intended / pending:** requirements or behavior without sufficient confirmation.

**Current milestone:** phase/batch 5 retrieval was accepted by the owner;
phase 6 grounded-answer implementation exists but its quality gate is **OPEN**.
Phase 7 is analyst UX polish, not permission to defer phase-6 citation correctness.
Latest recorded backend verification: **345 offline tests passed, 15 integration
tests deselected**, affected-file Ruff checks passed, and FastAPI restarted with
health HTTP 200. These are historical results, not a live service guarantee.

## 2. Architecture, entry points and data flows

The locked stack is a Vite/React/TypeScript SPA, FastAPI/Python, hosted Supabase
Auth/Postgres, pgvector plus Postgres full-text search, and OpenAI. SQLAlchemy
models and Alembic own schema definitions; request-path database work primarily
uses parameterized psycopg SQL. PydanticAI coordinates typed model/tool outputs.
Railway frontend/backend services are the intended hosting shape, not a verified
deployment. See [architecture](architecture.md).

### Browser request and identity

`frontend/src/main.tsx` → `src/App.tsx` → `AuthProvider` / `AccessGate` → pages.
Email signup/sign-in uses the shared Supabase browser client. Confirmation and
manual admission are separate: an authenticated account without a corresponding
approved `public.users` profile receives 403 from protected backend routes.
`app.database.approve_user` is the administrative approval CLI.

Ordinary JSON requests use `src/lib/api.ts` / `http.ts`; chat uses the AI SDK
transport in `ChatConversation.tsx`. Both attach the Supabase bearer token.
`backend/app/main.py` registers health, auth and chat routers. Authentication in
`app/auth/dependencies.py` asks Supabase Auth to verify the token and checks the
approved profile. Thread ownership derives from that identity, never a submitted
user ID. Explicit ownership checks are necessary because the backend connection
is privileged; RLS also protects user-scoped database access.

Current routes: public `GET /health`; protected `GET /auth/me`,
`POST /chat/threads`, `GET /chat/threads`,
`GET /chat/threads/{thread_id}/messages`, and `POST /chat/stream`.

### Chat generation, streaming and persistence

1. `/chat/stream` validates the request, checks/locks the owned thread and derives
   stable user/assistant UUIDs from the thread and client question ID. Existing
   completed turns replay their saved text/citations without model calls.
2. `chat/streaming.py` loads bounded server-owned history and calls
   `chat/orchestrator.py::generate_reply`. History is context, not source evidence.
3. The assistant retrieves passages, registers exposed verbatim spans and emits
   typed claims/gaps or a guided comparison/calculation handoff.
4. Structural validation checks provenance, quotes, numbers, periods and other
   contracts; a separate no-tool judge checks semantic support and gap relevance.
   Guided comparisons share at most one repair across invalid submissions and
   grounding rejection. Failed drafts are not displayed or stored as answers.
5. The backend renders accepted typed blocks and assigns citation numbers.
   Progress events precede validation; accepted text is then sent in chunks using
   the installed AI SDK 7 UI-message SSE protocol. This is not raw token streaming.
6. User message, assistant message, parts and citation rows are persisted together.
   A successful stream `finish` acknowledges commit. Cancellation before commit
   rolls back; disconnect just after commit may leave a durable turn that retry
   recovers. Same question ID/text replays; conflicting reuse or concurrent turns
   receive controlled conflicts.

There is no durable background-job system. Page unload/disconnect can cancel work.
Account-scoped tab `sessionStorage` retains pending questions/IDs for explicit
retry. New chat creates no database thread until first send; failed first sends
can leave empty threads. Workspace-owned views in `ChatLayout.tsx` now keep
running/retryable conversations mounted while switching chats; that latest
navigation change still needs the pending manual confirmation.

### Ingestion and retrieval

`data/download.py` → ignored `data/downloads/` + manifest → `data/convert.py`
(Docling) → ignored `data/markdown/` → `backend/ingest/preview.py` →
`ingest/trial.py` or `ingest/filing.py` → Supabase documents/chunks/vectors.
Token-aware chunking includes context in the configured 1,024-token input budget.
Full ingestion batches embeddings, caches progress under ignored `data/chunks/`,
reuses matching rows/cache and rejects source/config/content conflicts. It is
resumable, not an exactly-once billing guarantee. Changed-source refresh/delete
is intentionally not implemented.

`retrieval/retriever.py::DocumentRetriever` exposes async `search`, `compare`,
`read_chunk` and `read_surrounding_chunks`. Query embedding and typed keyword
extraction run concurrently. Semantic cosine search and English
`plainto_tsquery` / `ts_rank_cd` FTS run on separate read-only psycopg connections
in worker threads, with shared restrictions on completed filings, model,
dimensions and explicit filters. Defaults: 50 candidates per branch, RRF constant
60, 10 primary results and one same-document neighbor on either side. Comparisons
prepare once, preserve up to 25 explicit targets (including empty targets),
return three primary passages per target and run at most two target searches
concurrently. RRF scores are ranking values, not confidence probabilities.

The indexed/query embedding pair is currently enforced as
`text-embedding-3-small` / **1536 dimensions**. Changing an env value alone cannot
switch this corpus to another embedding model. Keyword failure visibly degrades
to semantic-only search; embedding/database failures fail clearly. Healthy FTS
with zero hits is not a service failure.

For table chunks, `retrieval/table_context.py` can attach excerpts from the
database's original stored Markdown after hash and table-reference checks. This
preserves indexed text/vectors; it does not repair extraction or certify periods.

## 3. Key decisions and their rationale

| Decision | Reason / consequence |
| --- | --- |
| Backend owns auth, retrieval, grounding and writes | Browser IDs, history and source text are untrusted; no browser OpenAI/service-role credentials. |
| Public email registration, confirmation, then manual approval | Registration alone must not grant internal-app access. No SSO is currently required. |
| Private chats, shared approved-user SEC corpus | Matches current single-firm scope; search filters are not authorization boundaries. |
| pgvector + FTS + Python RRF | Reuses Postgres, avoids a separate search service/BM25 dependency; no reranker is currently implemented. |
| Keep converted text as-is for the tutorial | Owner prioritized architecture/pipeline over extensive data cleanup; page/fiscal/table limitations remain explicit. |
| Server-issued E evidence IDs resolve exact quotes | Model selects observed evidence instead of copying/assembling quotes or inventing source metadata. |
| Validate first, then stream accepted text | Rejected drafts never become provisional factual output; commit still determines successful completion. |
| Guided comparison writer with frozen evidence and no read/search tools | Limits research loops, repeated context and spend; server-owned R request-span IDs replace copied question anchors. |
| Grouped company citations for interpretations | Require each compared company's own observed sources; grouping establishes provenance, not semantic support. |
| Five references total per claim, one shared comparison repair | Broad syntheses must split/narrow; increasing budget or auto-attaching sources is not an approved correctness fix. |
| Guided numeric facts and Decimal calculator | Verify measure, scope, units and periods before deterministic arithmetic; submit a verified calculation directly rather than require another model completion. |
| Central settings and fail-fast validation | Avoid hidden environment reads/fallbacks and incompatible model/config combinations. |

For exact rules, read the shared instructions rather than treating this table as
a competing policy. Important conventions include small functions, no speculative
abstractions/dependencies, async I/O boundaries, no `load_dotenv`, uv for Python,
pnpm only for frontend, and no frontend test runner. Frontend configuration
actually lives at `frontend/src/lib/env.ts` (the root instructions abbreviate it).

## 4. Implemented versus incomplete

| Area | Implemented / recorded evidence | Still incomplete or unverified |
| --- | --- | --- |
| Identity and ownership | Supabase auth verification, approval CLI/UI, RLS, private-thread APIs; owner reported working approval/access flows | Some early checklist items still request two real sessions, email-confirmation/expiry checks; reconcile exact evidence before checking them off. |
| Chat | Browser send/history, stable retry IDs, atomic persistence, replay, Stop, progress, citation snapshots | Latest cross-chat navigation/Stop/logout behavior has implementation/build checks, but pending manual confirmation. No durable background execution or empty-thread cleanup. |
| Corpus | Recorded 25 completed filings / 5,396 chunks, cached embeddings and immutable rerun checks | Full intended 10-K/10-Q universe, verified fiscal metadata, original page mapping, table cleanup and refresh workflow. |
| Retrieval (phase 5) | Offline/live checks and owner-accepted lookup/comparison evidence on 2026-10-18 | Retrieval coverage is not proof of answering quality; no automatic query planner or cross-encoder reranking. |
| Answers (phase 6) | Typed claims, structural checks, judge, guided calculations/comparisons, failure/usage diagnostics; earlier Azure, Microsoft ratio and five-year financial checks recorded | Broad supplier/manufacturing comparison reliability and overall claim-support gate remain open. Latest combined citation-budget schema fix has no live pass. |
| UX (phase 7) | Basic source expanders, excerpts, SEC links and explicit unknown-location labels | Rich Markdown/tables, claim-to-source interaction, complete usability/accessibility checks and example questions. |
| Delivery | Local app and run commands | Railway deployment, production operations/load/spending controls, full ten-question quality acceptance and analyst pilot. |

The owner confirmed the earlier five phase-6 browser reviews on 2026-10-19.
That acceptance does not cover later comparison/navigation changes or declare
the independent answer-quality gate complete. See
[owner review](evaluations/assistant-owner-review.md),
[retrieval review](evaluations/retrieval-evidence-review.md) and [checklist](todos.md).

## 5. Environment, dependencies and commands

Run from the correct service directory. Python **3.12+** is declared; the latest
local backend verification used a newer interpreter. For Vite 8, use a supported
Node version such as **22.12+**; the installed Vite package declares
`^20.19.0 || >=22.12.0`, stricter than the root README's generic “20+”.
Use uv and pnpm with their existing lockfiles. Backend versions are pinned in
`pyproject.toml`; uv and `frontend/.npmrc` enforce a seven-day release-age policy.
Docling, tiktoken, pytest, Ruff and ipykernel are backend development dependencies.

Create local `.env` files from each service's `.env.example` **only if absent**;
do not overwrite the owner's configured files. Populate credentials privately.

| Service | Configuration names / meaning |
| --- | --- |
| Backend required | `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_ROLE_KEY`, `DATABASE_URL`, `OPENAI_API_KEY`, `ALLOWED_ORIGINS`. Read defaults/validation in `app/config.py`. |
| Browser public only | `VITE_API_BASE_URL`, `VITE_SUPABASE_URL`, `VITE_SUPABASE_ANON_KEY`. No database URL, service-role key or OpenAI key. |
| Model/retrieval knobs | `OPENAI_CHAT_MODEL`, `OPENAI_GROUNDING_MODEL`, embedding settings, `RETRIEVAL_*`, `ASSISTANT_*`, `GROUNDING_OUTPUT_TOKENS`. Examples are not proof of active local values. |

Latest recorded diagnostics used `gpt-5.4-mini` answering, `gpt-4.1-mini` judging
and `gpt-4o-mini` keywords. Do not infer the current `.env` from that history.
The present Chat Completions integration requires `ASSISTANT_REASONING_EFFORT=none`
when selecting `gpt-5.4-mini`; configuration rejects incompatible settings.
See `assistant/model_settings.py` before changing reasoning/token controls.
Ollama/Qwen and the previously discussed hosted BGE/DeepSeek development stack
are not the current implementation or a supported provider-switching feature.

From `backend/`:

```powershell
uv sync --locked
uv run --locked python -m uvicorn app.main:app --reload --port 8001
```

Health: `http://localhost:8001/health`; API docs: `http://localhost:8001/docs`.
Port 8000 previously hit Windows socket restrictions; 8001 is the established
local port. Use `backend/.venv/Scripts/python.exe` for editor/Jupyter kernels,
not the root environment or Conda's Python. Ctrl+C stops a foreground server.
Restart backend after environment changes; restart Vite after frontend env edits.

From `frontend/`, in a separate terminal:

```powershell
pnpm install --frozen-lockfile
pnpm dev
pnpm exec tsc -b
pnpm lint
pnpm build
```

Use `http://localhost:5173` to match configured CORS/auth redirects. Supabase
confirmation redirects need `/auth/callback`; approval is a separate step.
`pnpm preview` is a local build preview, not a production deployment.

Offline backend verification, from `backend/`:

```powershell
uv run --locked python -m pytest -m "not integration" -q
uv run --locked ruff check .
uv run --locked ruff format --check .
```

The recorded passing lint checks were for affected Python files, not a fresh
whole-repository lint audit. If Windows' default pytest temp location is denied,
use a new ignored path with `--basetemp ../data/chunks/assistant/pytest-handoff-run`.
Use a fresh disposable directory: pytest manages that path. Frontend verification
is type/lint/build plus manual browser checks; do not add frontend tests.

Database/admin operations, from `backend/` (not part of routine offline checks):

```powershell
uv run --locked alembic current
uv run --locked alembic upgrade head
uv run --locked python -m app.database.approve_user <auth-user-uuid>
```

Use a direct or **session pooler** `DATABASE_URL`, not the transaction pooler.
Session pooling was chosen locally because direct-host name resolution failed.
URL-encode password punctuation; never print connection strings. Migrations are
the schema source of truth; review autogeneration/explicit RLS operations. An
initial downgrade is destructive, not a routine reset command.

Read-only local chunk preview (no model/database calls), from `backend/`:

```powershell
uv run --locked python -m ingest.filing --all --preview-only
```

Paid/live commands below are **reference only, not authorization to run them**:

```powershell
uv run --locked python -m scripts.smoke_retrieval --question "What services does Azure provide?" --ticker MSFT --corpus-years 2025 --output ../data/chunks/retrieval/azure.json
uv run --locked python -m scripts.smoke_assistant --question "What does Microsoft's 2025 filing say Azure provides? Cite the supporting passages." --output ../data/chunks/assistant/azure.json
uv run --locked python -m pytest tests/assistant/test_live_grounding.py -m integration -q
```

Retrieval smoke spends embedding/keyword credits; assistant smoke also spends
answer/judge credits. Neither smoke CLI writes chat history. Integration tests
can call services or use temporary database fixtures; do not run bare `pytest`
assuming it is offline. Full ingestion writes the database and may spend credits.
See [data operations](../data/README.md) for preview, conversion and ingestion.

## 6. Known failures, limitations and verification caveats

**Immediate blocker: broad comparison citations/grounding.** Read the latest
sections of [guided comparisons](guides/guided-comparisons.md) and
[answer results](evaluations/assistant-results.md) before changing prompts or
asking for another frontend retry:

1. Earlier drafts repeatedly cited only Apple in an Apple/NVIDIA interpretation.
   Replay confirmed that NVIDIA evidence and explicit repair feedback were present.
2. Owner-approved grouped citations now require each compared company's own
   observed IDs. The most recent live run did cite both companies.
3. That run still failed: interpretations selected **4+3**, then **3+3** references,
   exceeding five total. It took **33.08 seconds**, with **3 answering, 0 judging,
   1 keyword and 1 embedding** requests. No answer was accepted or semantically judged.
4. The schema previously limited lists independently, leaving a combined overflow
   representable. The latest offline fix encodes allowed allocations of five
   slots across required company groups. For two companies these have maxima
   1+4, 2+3, 3+2 or 4+1. Runtime ownership/total checks and semantic judging remain.
5. Exhaustive allocation tests and SDK wire tests pass; **there is no post-fix
   live success yet**. Do not claim that the entire citation/answering problem
   is solved, increase limits silently, or auto-attach sources to pass validation.

Diagnostic history also matters: an older wrapper nested SDK message capture and
hid repair history; it was replaced with a non-interfering HTTP observer. Missing
private rejection feedback and invalid judge decision coverage were separately
fixed offline. Guided judge verdicts now use required server-owned C/G keys.
The latest supplier run never reached judging, so it did not verify that judge
contract live. Logged failures must remain sanitized; private model feedback
does not belong in public diagnostics.

Additional limitations / debt:

- Fiscal year, filing date and corpus year remain distinct; original page mapping
  and many fiscal labels are unverified. Stored table context cannot certify them.
- The owner accepted imperfect extraction for this tutorial, not factual errors
  in generated answers. Financial units/periods still need source-backed checks.
- A selected excerpt cannot prove a whole filing lacks a topic. Earlier judge
  calibration had false positives; retain negative cases and refusal review.
- All-company interpretation groups are conservative: missing evidence for one
  compared company hides interpretations; facts and explicit gaps remain possible.
- No HTTP ingestion UI, automatic corpus refresh, departmental tenancy, durable
  job execution, global per-user cost/concurrency controls or deployed runbook is
  established by the inspected implementation. Per-thread locking is not a
  complete rate-limit strategy for the eventual analyst population.
- Basic UI has source expanders but text rendering is still plain/preformatted;
  duplicate-looking source citations and rich table/Markdown UX need review.
- Large generated inputs/caches/diagnostic artifacts are gitignored. Fresh clones
  may lack local corpus, cached embeddings and one-off diagnostic scripts even
  after application code is transferred. Do not rerun paid ingestion to recreate
  them without checking existing storage and obtaining the needed authorization.
- Root/backend/frontend READMEs and some setup/phase records contain historical
  stub-flow or navigation descriptions. Code and newer dated evidence take
  precedence. Some old unchecked manual items remain alongside later owner
  acceptance; reconcile their precise scope instead of blindly checking them off.

## 7. Priorities for the next agent

1. Read the instruction files, inspect the dirty tree, and read the latest
   comparison/evaluation records. Preserve owner verdicts and historical failures.
2. Validate the **latest total-budget schema correction** live only after fresh
   owner approval with explicit request/token/retry caps. All previous one-run
   approvals in this conversation have been consumed. The latest approved caps
   were 4 answering calls × 4,000 output tokens, 2 judge calls × 2,000, 2 keyword
   calls × 150, and 1 embedding, zero HTTP retries/extra runs, no chat/database
   writes. Those are diagnostic caps, not an unspent allowance or proof of normal
   application request limits.
3. Inspect source selection, total references, periods, claim support, requested
   gaps and judge output. A successful request or schema acceptance alone is not
   a correct answer. Reproduce remaining failures offline before further spending.
4. Once the backend produces a supported result, review the original broad
   supplier question in the browser and confirm navigation during an active turn,
   Stop, logout and recovery. Do not close phase 6 on mock tests alone.
5. Then proceed to phase-7 UX, full ten-question/negative-case evaluation,
   production confidentiality/operations checks, Railway deployment and the pilot.

Do not turn this onboarding task into a provider migration, data cleanup,
dependency refresh, architecture rewrite or unrequested commit.

## 8. File map and source records

| Need | Start with |
| --- | --- |
| Instructions and product scope | [AGENTS.md](../AGENTS.md), service AGENTS, [client brief](client-brief.md), [todos](todos.md) |
| App startup / config | `backend/app/main.py`, `backend/app/config.py`, `frontend/src/main.tsx`, `frontend/src/lib/env.ts`, service `.env.example` files |
| Auth / admission | `backend/app/auth/dependencies.py`, `app/api/auth.py`, `app/database/approve_user.py`; `frontend/src/components/AuthProvider.tsx`, `AccessGate.tsx`, auth pages |
| Thread APIs / storage | `backend/app/api/threads.py`, `app/api/chat.py`, `app/database/chats.py`, `app/database/connection.py` |
| Schema / RLS | `backend/app/database/models/` (users, threads, messages, citations, documents, chunks), `backend/alembic/versions/ab55919814e7_initial_schema.py` |
| Stream protocol / lifecycle | `backend/app/chat/messages.py`, `streaming.py`, `orchestrator.py`; `frontend/src/components/chat/ChatConversation.tsx`, `src/pages/ChatLayout.tsx` |
| Retrieval / table evidence | `backend/app/retrieval/{retriever,queries,embeddings,keywords,fusion,types,table_context}.py` |
| Model tools / citations | `backend/app/assistant/{agent,deps,tools,selection,outputs,rendering,excerpts}.py`, `instructions.md` |
| Guided comparison blocker | `backend/app/assistant/{comparisons,comparison_citations}.py`, `comparison-instructions.md`, `tests/assistant/test_comparison_citations.py`, `test_guided_comparisons.py` |
| Numeric path / limits / diagnostics | `backend/app/assistant/{facts,calculations,model_settings,failure_diagnostics}.py` |
| Grounding | `backend/app/grounding/{validator,claim_context,judge}.py`; assistant grounding/model-contract tests |
| UI sources / recovery | `frontend/src/components/chat/MessageList.tsx`, `src/lib/{chat-parts,pending-chat,chats}.ts`, `src/pages/{NewChatPage,ChatThreadPage}.tsx` |
| Ingestion | `data/{download,convert}.py`, `backend/ingest/{preview,trial,filing}.py`, [data README](../data/README.md) |
| Offline / integration checks | `backend/tests/{assistant,retrieval,ingest,chat,api,database}/`; integration markers distinguish live checks |
| Evaluations / operations | `backend/scripts/{smoke_retrieval,smoke_assistant,check_sign_in,set_user_password}.py`; admin scripts are not routine onboarding commands |

Read [guided comparison decisions and failure history](guides/guided-comparisons.md),
[answer results](evaluations/assistant-results.md),
[owner answer review](evaluations/assistant-owner-review.md),
[retrieval results](evaluations/retrieval-results.md), and
[phase-six plan](guides/phase-six-grounded-answers-plan.md) for detailed evidence.
The [phase-six progress record](guides/phase-six-progress.md) contains older
checkpoints; use the newer comparison record for the current blocker.
Repository-local diagnostic JSON/logs live under ignored
`data/chunks/assistant/`; inspect carefully and never publish credentials,
authorization headers, passwords, database URLs or raw provider error bodies.

This documentation task inspected source/manifests/instruction files and existing
records. It did not read private `.env` files, rerun application tests, call live
services, or change application code, tests, dependencies, architecture or AGENTS.
