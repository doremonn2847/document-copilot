# Public Try demo: proposed design

Date: 2026-10-27 (Asia/Bangkok). Status: **owner approved; migrated and deployed disabled; public enablement checks pending**.
The owner requested anonymous full-function demo access and selected a **$1/day
shared OpenAI ceiling**. Three generated attempts per visitor is the proposed
starting allowance, now approved. The later owner-authorized release applied the
additive migration and deployed both services with demo disabled; see
[release evidence](../../operations/release-2026-10-27.md).

## Purpose and scope

A reviewer follows the CV link, selects **Try demo**, and uses the existing SEC
copilot without supplying an email/password or waiting for approval. Each browser
identity owns its conversations; no shared account credentials enter the bundle.
The regular approved-user application and its existing data remain available.

Reuse Supabase anonymous Auth identities, the existing chat UI, retrieval,
grounding, calculation, citation, feedback, title and history paths. Full function
means access to those existing functions within demo quotas, not guaranteed answer
quality, new corpus coverage, account administration or unlimited generation.

The chosen design changes authorization, `/auth/me`, database models, and provider
request accounting. It does not change grounding rules, answer models, the
1536-dimension embedding index, the corpus or provider. No new runtime dependency
is planned. This is separate from the provisionally closed phase-9 delivery work.

## Verified starting point

- `frontend/src/pages/AuthPage.tsx` only signs in/up with email and password.
- `frontend/src/components/AuthProvider.tsx` requires an email string from
  `/auth/me`; `CurrentUser` and `public.users.email` also require email.
- Backend auth verifies the token using Supabase, then requires a matching
  `public.users` approval row. Ordinary registration must keep that approval gate.
- Existing chat ownership uses user UUIDs in both server SQL and RLS. Anonymous
  Supabase identities also use the `authenticated` database role; they must be
  distinguished by verified `is_anonymous` identity and server-owned profile type.
- Current per-user answer limits are in memory and reset with a backend restart.
  They are not adequate for a daily financial ceiling or permanent guest quota.
- Provider clients exist in `chat/orchestrator.py`, `chat/titles.py`, and the
  retriever. `.with_options(max_retries=1)` enables retrieval HTTP retries.
  Generator/judge usage logs omit title/routing/retrieval usage, so logs alone
  cannot enforce the requested ceiling.
- The main chat transaction is held during generation and rolled back on Stop or
  failure. Financial reservations must commit independently of this transaction.

## Alternatives considered

1. **Supabase anonymous identities — chosen proposal.** Reuses signed sessions and
   UUID ownership. Requires nullable guest email, controlled guest admission and
   durable quotas, but no secret demo password or parallel session protocol.
2. **Automatic login to the shared demo account.** Smaller UI change but all
   visitors share chat ownership and quota. Does not meet isolated visitor access.
3. **A custom guest-cookie authentication system.** Avoids anonymous Auth users but
   introduces a second authentication protocol and duplicate ownership handling.

## Visitor flow and limits

1. Login page offers **Try demo** and states “3 generated attempts; private to this
   browser; shared daily demo availability applies.” Do not overwrite an existing
   registered-user session; signed-in users continue in their own account.
2. On first use, `supabase.auth.signInAnonymously()` creates a session. Reuse an
   existing anonymous session after reload; do not create identities per click.
3. The frontend calls `POST /auth/demo` with the bearer token. The backend verifies
   the Auth user, admits only a verified anonymous identity, and idempotently
   creates its demo profile and quota record. A client-supplied email, demo flag,
   user ID or remaining-quota number cannot authorize admission.
   Split verified-identity lookup from approved-profile lookup so admission does
   not circularly require the profile it is creating. Regular protected endpoints
   still require a profile, with `is_demo` matching the verified anonymous type.
4. `/auth/me` reports the verified user type. The frontend enters the existing
   workspace and fetches `GET /auth/demo` for the guest's remaining allowance and
   next global reset time. Regular unapproved email accounts still receive 403.
5. Each guest receives **3 new generation attempts per anonymous identity**, with
   **1 active attempt**. Follow-ups, small talk and retries that generate again
   consume attempts. Replaying a committed answer, reading history/citations,
   feedback, rename/search/delete, and starting an unsent chat do not.
6. Validation/ownership/concurrency rejection or a declined first reservation does
   not consume an attempt. The first provider reservation committed for dispatch
   consumes the attempt, including an uncertain crash between reservation and
   network dispatch. Stop, timeout, service failure or an unsupported-target reply
   then still consumes the attempt. This avoids refunding uncertain paid work.
7. Keep the existing 120-second deadline and bounded tool/model behavior. Normal
   registered-user limits retain their current behavior.
8. Signing out or clearing browser data can lose access to guest history and
   create a fresh identity. A visitor limit is not a per-person guarantee. The
   shared financial ceiling remains authoritative across fresh identities.

The financial day is the **UTC request-start date**, resetting at 07:00 Bangkok.
An in-flight request remains charged to its original day after midnight. UI
displays the reset time in the visitor's locale. Three attempts are an upper
allowance, not a promise that all three will be available after the global pool
has been used by others.

## Budget enforcement: $1/day, all demo provider requests

Use integer microdollars for counters (`$1 = 1,000,000`) and Decimal rates. Apply
the ceiling only to anonymous **Try demo** traffic. Registered accounts, including
the earlier shared reviewer account, keep their current behavior and are outside
this pool; do not imply this caps the whole OpenAI account or hosting costs. Do
not disable the existing reviewer account or delete its chats in this change.

Every paid attempt passes through one demo-aware OpenAI HTTP transport. It must
cover routing, answering/planning/numeric selection, judging/numeric verification,
query embeddings, keyword extraction, title generation, output-validation retries
and each SDK HTTP retry. It must also cover small-talk routes, which may return
without constructing the document agent.

Budget exhaustion must propagate through triage, keyword and tool fallback paths
as a demo limit. Those helpers cannot turn it into an unmetered retry, generic
grounding error, silent lexical fallback or a new client outside the meter.

Before dispatch, atomically reserve a conservative maximum for that request in
Postgres. Admit only if `charged + reserved + new_reservation <= daily_limit`.
No database lock or budget transaction remains open during provider I/O. Stop
new provider calls when a reservation is declined; do not merely check cost after
the answer or rely on frontend counters/provider budget alerts.

### Conservative request bounds

For the first implementation, avoid approximate prompt-token counts. Reserve
input at the model's full documented context-window bound and output at the
request's explicit maximum, both at uncached Standard prices. This deliberately
overestimates input and ignores possible cache discounts. Embeddings accept one
text query bounded by the existing 8191 UTF-8-byte validation; use 8192 input
tokens as the conservative reservation bound. Reject token-array/batched inputs.

Official references inspected on 2026-10-27:

| Allowed model | Input context bound | Input / output USD per 1M tokens |
| --- | ---: | --- |
| `gpt-5.4-mini` | 400,000 | 0.75 / 4.50 |
| `gpt-4o-mini` | 128,000 | 0.15 / 0.60 |
| `text-embedding-3-small` | Existing single-query boundary above | 0.02 / none |

Sources: [Standard pricing](https://developers.openai.com/api/docs/pricing),
[GPT-5.4 mini](https://developers.openai.com/api/docs/models/gpt-5.4-mini),
[GPT-4o mini](https://developers.openai.com/api/docs/models/gpt-4o-mini).

For example, a 4,000-output-token GPT-5.4-mini call reserves **$0.318**. Once
reported usage is settled, unused reservation becomes available again. Near the
end of the day, a call can be refused even if its eventual actual cost would have
fit. This conservative loss of availability is preferable to claiming a hard
dollar ceiling from approximate token counts. Do not silently replace this with
a character estimate. A tighter proven upper bound can be a later improvement.

The guest transport supports only non-streaming, text/tool Chat Completions and
single-query Embeddings against the direct OpenAI API. The current backend
already streams accepted rendered text, rather than provider tokens. Require an
explicit Standard/default processing tier, explicit output maximum and a known
pricing entry. Reject unknown models, changed endpoints, image/audio inputs,
paid provider-hosted tools, processing tiers or pricing shapes before dispatch.
Do not silently switch the normal user's provider/model configuration.

### Settlement and interruptions

- Parse non-streaming provider usage, charge uncached input and all completion
  tokens (including reasoning), rounding each request charge upward to a
  microdollar. Settle idempotently against that request's reservation.
- Store the pricing revision/rates used at reservation; a new rate config cannot
  reinterpret old requests. Pricing must be reviewed before changing demo models
  or processing tiers. This is an application ceiling under the verified rate
  schedule, not a guarantee against future provider price changes or unrelated
  API usage.
- Missing/malformed usage, provider errors, interrupted transport and process
  crashes retain the full reservation as unavailable. Never assume a cancelled
  request was free or release unknown liability on a timer/restart.
- Validate actual usage against reserved bounds. An accounting invariant failure
  disables further demo dispatch and is logged without prompts, quotes or tokens
  containing secrets; do not continue spending after a bound mismatch.
- Title generation may run in parallel, but it uses the same budget meter. A
  budget refusal for the optional title leaves the fallback title; an answer or
  mandatory judge budget refusal produces a controlled demo-limit response, not
  an unverified answer. No title request bypasses a failed admission.
- Keep existing atomic answer/citation persistence and completed-turn replay.
  Money and attempt accounting remain durable even when a chat transaction rolls
  back. A failed generation can consume allowance without saving a successful turn.

## Database changes and access policy

Use an additive Alembic migration plus the narrowly necessary nullable-email
change; no corpus rewrite or re-embedding.

- `public.users`: add `is_demo BOOLEAN NOT NULL DEFAULT false`; permit NULL email
  for demo profiles only. Enforce real email for normal profiles and NULL email
  for admitted anonymous profiles. Existing rows remain normal approved users.
- `demo_visitors`: user UUID, attempts started, active-attempt lease. This controls
  the lifetime three-attempt allowance across chats and backend restarts.
- `demo_budget_days`: UTC date, charged/reserved microdollars, configured daily
  ceiling, admission count and accounting-blocked state. Limit admitted new demo
  profiles to 100/day; idempotent reuse does not consume another admission.
- `demo_attempts`: attempt UUID, guest identity, original thread/question IDs,
  state/timestamps and provider-request-start count. A new paid retry gets a new
  attempt; a committed replay creates none. An expiring active lease can release
  a concurrency slot but not reset the attempt count or release money liability.
- `demo_model_requests`: attempt/day, request UUID, model/endpoint, rate revision,
  reservation, settled charge/usage and state. Provider metadata only, no raw
  prompts or outputs. Guest/thread deletion must not erase financial records;
  user references may become NULL, and monetary ledger rows are retained.

Budget tables have RLS enabled and no direct `anon`/`authenticated` grants or
client-write policies. Backend SQL is parameterized. Status endpoints return only
the current guest's allowance and demo availability, not other identities, IPs or
private spending records. Use short independent psycopg connections in worker
threads, preserving the transaction-pooler conventions.

Preserve the existing ownership policies and require server-owned admitted
profiles for corpus access. Never infer approval from user-editable metadata.
Verify two guests, guest-versus-registered-user isolation and direct REST access
before enabling public demo traffic. The backend continues without a service-role
key; admission uses its existing trusted database connection.

## API and UI contracts

- `POST /auth/demo`: admit/resume a verified anonymous user. Idempotent; never
  accepts a normal unapproved account as a demo. Returns a typed demo status.
- `GET /auth/demo`: read the authenticated demo visitor's status. Return
  `remaining_attempts`, `can_generate`, `reset_at`, and a safe reason such as
  `visitor_limit`, `daily_budget`, `busy` or `unavailable`.
  Availability is a snapshot, not a reservation; all dispatches recheck it
  atomically. A frontend status response never authorizes provider spending.
- `/auth/me`: keep `id`; allow nullable `email`; add server-owned `is_demo`.
  Frontend validation must distinguish a normal approved user from a guest.
- Existing chat/feedback/thread endpoints retain their payloads and ownership
  checks. Add demo admission/attempt guards before any paid work. Stable question
  IDs and completed-retry replay retain their existing meaning.
- HTTP 429 rejects exhausted/busy attempts before streaming. A budget exhausted
  during generation yields a specific SSE demo-limit error. A database/accounting
  outage fails closed with 503. Do not present demo admission as pending approval.
- Demo banner shows guest status, remaining attempts, browser-history limitation,
  and the reset time when the shared pool is unavailable. Reading saved history,
  citations and feedback remains available after generation quota is exhausted.
- Registered signup/login and normal approval flow remain available. Do not
  replace a registered session when Try demo is clicked.

## Configuration and operational boundaries

All configuration remains in the existing service settings modules. Proposed
settings are `DEMO_ENABLED` (false until validated), `DEMO_DAILY_BUDGET_USD=1.00`,
`DEMO_ATTEMPTS_PER_VISITOR=3`, and `DEMO_DAILY_ADMISSIONS=100`. The supported-model
pricing manifest carries an explicit verified date and known context bounds;
unsupported demo model configuration fails validation rather than guessing a rate.
`DEMO_ENABLED` is an intentional admission/dispatch kill switch for this public
entry point. Turning it off stops new demo work while preserving normal users.

Supabase anonymous sign-in must be enabled deliberately in the dashboard. Its
documented IP signup limits help, but do not make visitor identity abuse-proof.
Verify existing rate/bot-protection behavior before public enablement. Do not
enable a global CAPTCHA requirement that breaks the existing email forms.
Anonymous Auth users are not automatically cleaned up by Supabase; first release
documents manual retention/review and creates no scheduled deletion job. Do not
promise automatic expiry or deletion. Account cleanup is separate destructive work.

The $1 cap excludes Supabase/Railway resources, normal-user model calls and work
performed outside this application's guarded clients. Keeping a public endpoint
available indefinitely on trial credit is not guaranteed. Existing shared-account
credentials are not published, rotated or revoked by this feature.

## Verification and rollout

Offline backend tests must prove:

- Verified anonymous identity can be admitted once; normal unapproved accounts,
  forged demo flags and missing/invalid tokens cannot gain access.
- Guest email is nullable without weakening normal-user profile validation.
  RLS/client-write boundaries preserve isolation and prevent quota edits.
- Concurrent reservations/attempts obey daily financial and per-guest limits;
  state survives restart and chat deletion. Replays cost no attempt/model call.
- Every outgoing endpoint/model/tier/request shape is checked before dispatch;
  title, routing, selection, judge, keywords, embeddings and SDK retries use the
  same meter. No unmetered fallback client exists for a demo attempt.
- Settlement is idempotent, rounded up and includes reasoning. Unknown usage,
  crashes, Stop, timeouts, midnight boundaries and failed optional titles do not
  refund potentially billed work or leak active slots permanently.
- Exhaustion returns controlled HTTP/SSE behavior while history/citation/feedback
  access works. Existing grounding, retries and persistence regressions stay green.

Normal tests use fake transports/connections, no network or model calls. Run the
full offline backend suite/lint and frontend type/lint/build. Preserve the manual
frontend verification policy; add no frontend runner or test files.

Rollout order: reviewed migration/config, migration on a disposable database,
budgeted integration proof, Supabase settings, backend/frontend deployment with
demo disabled, two-guest isolation and small separately authorized paid checks,
then enable Try demo. No live database write or paid test is authorized by this
design document alone. Owner review is needed before applying the new migration:
the previous free-plan backup deferral did not waive the requirement to review
backup/rollback readiness for a new consequential schema change.

Rollback disables guest admission/generation and returns the application to a
known-good snapshot, retaining the additive schema/ledger. Do not automatically
downgrade nullable email or delete guest profiles/ledger rows to roll back code.

## Owner review

Approve or amend the proposed defaults: anonymous isolated guests; 3 generated
attempts per identity; 1 active attempt; $1/day shared demo provider budget;
07:00 Bangkok daily reset; conservative reservations and retained unknown costs.
The public demo can become unavailable before the exact measured spend reaches
$1, and an interrupted attempt may consume allowance. These are deliberate
budget-safety tradeoffs. Registered accounts remain outside the demo pool.

After approval, write the implementation plan against this spec before editing
application code. No unrequested commit/push, deployment, model call, migration,
account deletion or Supabase setting change occurs during design review.

## References

- [Supabase anonymous sign-ins](https://supabase.com/docs/guides/auth/auth-anonymous)
  (verified anonymous identity, authenticated RLS role, signup limits and lack of
  automatic cleanup).
- [OpenAI Standard pricing](https://developers.openai.com/api/docs/pricing).
- [GPT-5.4 mini context and output limits](https://developers.openai.com/api/docs/models/gpt-5.4-mini).
- [GPT-4o mini context and output limits](https://developers.openai.com/api/docs/models/gpt-4o-mini).
