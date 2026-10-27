# Public demo implementation plan

> **For agentic workers:** Use superpowers:executing-plans, inline, with one final independent review.

**Goal:** Isolated anonymous demo access with three attempts and a durable shared $1/day provider ceiling.

**Architecture:** Supabase verifies identities; privileged short Postgres transactions admit guests and account for attempts and provider reservations. One HTTP transport meters all OpenAI roles, including retries. Existing ownership and grounding remain unchanged.

**Tech stack:** Existing FastAPI, psycopg, Alembic, httpx/OpenAI, React and Supabase SDKs; no new dependencies.

**Spec:** `docs/superpowers/specs/2026-10-27-public-demo-design.md` (owner approved).

## Global constraints

- Demo disabled by default. No live migration, paid calls, account changes, deployment, commit or push in this implementation.
- Three attempts per identity, one active attempt, 100 admissions/day; UTC budget day, $1 = 1,000,000 microdollars.
- Reserve documented full input context plus explicit output maximum; unknown costs remain reserved. Short transactions independent of chat persistence.
- Continue the existing checkout, preserving delivery changes and unrelated retrieval reviews, as previously agreed.
- No frontend test runner; offline backend tests must not access network/database.

## Review focus

- Cancellation while a reservation commits must never refund uncertain spending.
- SDK wrapping/retries and lexical/triage fallbacks must not hide a denied reservation.
- Simultaneous title and answer calls must share the same attempt and daily pool.
- Expired concurrency leases must not erase attempt counts or financial liabilities.
- Normal approval, completed replay and retained history must keep working when demo is disabled.

### Task 1: Pricing and request boundary

Files: `backend/app/demo/pricing.py`, `errors.py`, `transport.py`; `backend/tests/demo/test_transport.py`.

Interfaces: `request_bound(request) -> RequestBound`, `charge(bound, usage) -> int`; `MeteredTransport(store, attempt_id, transport)` reserves before every HTTP dispatch and settles once. `demo_failure(error)` finds wrapped budget failures.

- [x] Write tests for supported/rejected shapes, upward rounding, retry accounting, missing/invalid usage, cancellation and pre-dispatch denial; watch fail.
- [x] Implement manifest (verified 2026-10-27), strict Chat Completions/embedding boundary and transport.
- [x] Run focused offline tests and lint.

### Task 2: Durable database ledger and guest admission

Files: `backend/app/demo/store.py`, `backend/app/database/models/demo.py`, `user.py`, model exports, additive Alembic revision, config and `.env.example`; `backend/tests/demo/test_store.py`.

Interfaces: `DemoStore.admit(user_id)`, `status(user_id)`, `begin(user_id, thread_id, question_id) -> UUID`, `finish(attempt_id)`, `reserve(attempt_id, bound) -> UUID`, `settle(request_id, bound, usage)`; each async operation offloads one independent transaction.

- [x] Write failing SQL/transaction tests for lock order, conditional counters, lease ownership, midnight, durable liabilities and isolation.
- [x] Implement additive schema, RLS/no client grants, nullable guest email check, positive settings and supported model validation.
- [x] Run tests, lint and offline migration SQL inspection; no migration application.

### Task 3: Auth and generation integration

Files: `auth/dependencies.py`, `api/auth.py`, `api/chat.py`, `chat/streaming.py`, `chat/orchestrator.py`, `chat/titles.py`, `retrieval/retriever.py`, `retrieval/keywords.py`, demo client/context; auth and stream regression tests.

Interfaces: verified `AuthIdentity` includes `is_anonymous`; `CurrentUser` includes server-owned `is_demo`. POST/GET `/auth/demo` returns remaining attempts, availability, reset time and safe reason. A context scoped to a streaming attempt creates metered clients for every role.

- [x] Write failing tests for admission/type mismatch, ordinary unapproved users, replay bypass, cleanup and wrapped exhaustion propagation.
- [x] Split identity verification/profile approval, guard new demo turns, bind provider context to both title/main tasks, preserve registered callers.
- [x] Run full offline backend tests and lint.

### Task 4: Demo entry and status

Files: `frontend/src/pages/AuthPage.tsx`, `components/AuthProvider.tsx`, `lib/auth.ts`, `components/chat/DemoBanner.tsx`, `pages/ChatLayout.tsx`, existing error formatting as needed.

- [x] Reuse anonymous sessions, never replace registered sessions; admit guests before access checks.
- [x] Add Try demo and honest limits; banner refreshes status after generation/focus and exposes retained-history/reset limitations.
- [x] Run pnpm typecheck, lint and build; document manual browser checks as pending.

### Task 5: Review and rollout record

Files: demo README/runbook and this plan's progress ledger.

- [x] Document configuration, conservative availability, retained unknown costs, anonymous retention and separately gated rollout/rollback.
- [x] Run final offline verification and one independent whole-change reviewer; fix blocking findings with regressions.
- [x] Report implemented versus unverified. Preserve all existing records and make no unrequested commits.
