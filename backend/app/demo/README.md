# Public demo

Local implementation of the approved [design](../../../docs/superpowers/specs/2026-10-27-public-demo-design.md).
**Deployed with demo disabled on 2026-10-27.** Migration and private-ledger catalog
checks passed; real guest/concurrency/provider checks remain pending. See the
[release evidence](../../../docs/operations/release-2026-10-27.md).

Visitors use Supabase anonymous sessions and server-admitted `users.is_demo`
profiles. Email signup still requires administrator approval. Backend auth checks
that the verified anonymous identity matches the server profile; corpus RLS also
checks that identity type. No shared password or service-role key is needed.

`POST /auth/demo` admits a verified anonymous user idempotently. `GET /auth/demo`
returns only that visitor's remaining attempts, availability and UTC reset time.
`GET /auth/me` includes `is_demo` and a nullable guest email. Existing payloads
for chat, feedback and thread management are unchanged.

## Limits and accounting

Settings in `app/config.py` / `backend/.env.example`:

| Setting | Default | Meaning |
|---|---|---|
| `DEMO_ENABLED` | `false` | Admission / provider dispatch kill switch |
| `DEMO_DAILY_BUDGET_USD` | `1.00` | Shared anonymous OpenAI pool; may be reduced |
| `DEMO_ATTEMPTS_PER_VISITOR` | `3` | Lifetime allowance per anonymous identity |
| `DEMO_DAILY_ADMISSIONS` | `100` | New admitted profiles per UTC day |

Only anonymous demo traffic counts. Railway, Supabase and registered-account
OpenAI usage are outside this ceiling. Clearing browser data can create another
identity; this is not a per-person limit. Shared accounting remains authoritative.

`store.py` opens short independent psycopg transactions in worker threads.
The day row serializes reservations; visitor rows serialize the one-active-turn
lease and attempt count. The first committed provider reservation consumes the
attempt. No funds are refunded by chat rollback, Stop, failed generations or
deletion. Expired 180-second leases free only concurrency, never money/attempts.
Completed answer replay and non-generation operations remain free.

`current_attempt` is set for the streaming turn and inherited by its main/title
tasks. Every runtime client constructor uses `demo_client_options`; SDK copies
retain its HTTP transport. `transport.py` meters each HTTP attempt, including
SDK retries, before network dispatch. Triage and keyword fallback paths propagate
wrapped demo errors; optional title failures keep the existing fallback title.

`pricing.py` allows reviewed direct OpenAI nonstreaming text/tool Chat Completions
and single-text embeddings only. It forces Standard/default service tier and
reserves full context input plus explicit output cap at uncached rates. A
GPT-5.4-mini request capped at 4,000 output tokens reserves $0.318. This can reject
a request before actual spending reaches $1. Admission/status require enough
unreserved funds for the mandatory initial triage request; the banner is only a
snapshot, never a reservation or promise of three successful answers.

Known usage settles once using persisted rates, including completion/reasoning
tokens, rounded upward in integer microdollars. Missing usage, HTTP errors and
interruption retain full liability. Invalid usage bounds persist an accounting
block that carries into later days; investigate before clearing it. Never clear
unknown reservations on a timer or restart. Rates were reviewed 2026-10-27;
future price/model changes need a new review, not guessed rates.

The financial day is the UTC dispatch-transaction date (07:00 Bangkok reset).
Late responses settle against that original day. Financial records retain no
prompts or replies and survive guest/chat deletion. Anonymous Auth accounts and
ledger rows have no automatic retention/deletion job; review storage manually.

## Verification and rollout

Offline: `uv run pytest -m "not integration"`, `uv run ruff check .` from backend;
`pnpm exec tsc -b`, `pnpm lint`, `pnpm build` from frontend. Tests use fake
connections/transports; they do not prove Postgres concurrency or deployed RLS.

Before public enablement, separately authorize and record:

1. Backup/rollback review for the additive `d90e7c5a2101` migration. Previous
   free-plan backup deferral does not authorize this new schema change.
2. Apply to a disposable database; inspect schema parity, RLS/direct REST grants,
   concurrent admissions/reservations, idempotent settlement and restart/Stop
   behavior. Then review production application using a session/direct URL.
3. Deliberately enable Supabase anonymous sign-in; inspect IP/signup restrictions
   and bot protections without breaking existing email login.
4. Deploy both services with demo disabled; verify two guests, registered-user
   isolation, ordinary approval, retained history, feedback, completed replay,
   navigation, exhausted allowance and status/banner behavior.
5. Obtain a fresh bounded allowance for actual paid/provider checks, then enable
   `DEMO_ENABLED` only after the accounting and isolation checks pass.

Rollback: disable `DEMO_ENABLED` and restore the prior application release.
Keep the additive schema, guest rows and ledger. Migration downgrade intentionally
refuses to erase financial evidence or invalidate nullable guest rows. No automatic
account cleanup, public rollout or provider calls are performed by offline tests.
