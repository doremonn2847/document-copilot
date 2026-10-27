# Delivery execution record

Updated: **2026-10-24** (Asia/Bangkok); preparation began 2026-10-23. Baseline: `3172020`. Binding scope is the
owner-approved delivery-first plan in this conversation. This record separates
implementation, historical acceptance and outstanding live/human evidence.

**Current status — provisionally closed for the one-person pilot, 2026-10-24.**
The owner accepted temporary phase-9 closure with limitations. Final hosted
feature checks and spending controls are owner-confirmed passes. Backup/restore
and hosted capacity testing are explicitly deferred, not passed. Rollback
verification remains untested. This is not full multi-user production acceptance.
Earlier open-gate statements below describe checkpoints before this owner decision.

## Decisions and authorization

- Preserve Claude's accepted phases 6–8 and facts-only comparison architecture.
- Reuse the current Supabase project, accounts, history and 25-filing corpus.
- Keep the 120-second answer deadline; no stronger hosted latency promise.
- Owner performs the single-person stand-in pilot; no invented observations.
- Read-only inventory approved separately on 2026-10-23: one connection,
  10-second connection and statement timeouts, no account/chat content, no writes.
- Owner then explicitly authorized Railway deployment. Earlier model-call budgets
  are exhausted; no paid generation, capacity batch or extra DB checks are
  authorized by deployment alone.

Ruling: continue in the approved current checkout, preserve existing code and
do not introduce a worktree/branch migration or unrequested commit/push. There
were no unrelated tracked modifications at the baseline.

Ruling: the October 22 Railway outage note is historical. On October 23 the
official status page reported builds/deployments proceeding for all plans while
the security incident remained Identified. The owner explicitly instructed us
to proceed with deployment after this distinction was reported. This is not a
claim that the incident has been resolved. Reference: https://status.railway.com.

## Verified preparation

| Check | Evidence / result |
| --- | --- |
| Final offline backend | 477 passed, 15 integration tests deselected; four deployment-helper regressions added |
| Baseline source checks | Backend lint; frontend type/lint/production build passed |
| Shared database migration | `3ff92ab46eb9` (feedback), already at committed head; no migration applied |
| Corpus | 25 completed filings; 5,396 chunks; no missing embeddings/FTS vectors; correct model/dimensions |
| Source metadata | 25 verified fiscal years; 5,260 chunks with page labels (97.48%); not a guarantee of perfect extraction |
| Backend image | Production Docker build passed; health 200; missing-auth request 401 |
| Backend image boundaries | No `.env` files, ingestion/admin scripts or Docling dev dependency in `/app` |
| Frontend image | Production Docker build passed with public placeholders, no private build values |
| Caddy behavior | Root 200; deep chat route returns the same app shell; shell no-cache; assets immutable |
| Build warnings | Frontend bundle-size warning; Docker flags the public anon-key ARG by name. Neither is proof of a secret leak or a new optimization task. |

Local Docker bridge DNS initially failed on npm/PyPI. Host-network builds passed
without modifying Dockerfiles, dependencies, lockfiles or global Docker settings.
Local container checks used dummy config, no model calls and no DB connections.
Artifacts under ignored `data/chunks/assistant/` include `delivery-inventory-20261023.json`,
`delivery-container-smoke-20261023.json` and the build logs.

## Narrow deployment-helper correction

The existing Python helper failed on Windows because subprocess could not locate
the bare Railway command. Resolve the installed executable with `shutil.which`,
keep values only on stdin, fail clearly when missing, and withhold raw service
error output. A failing regression reproduced the launcher defect before the fix.

The helper also copied a standalone local `DATABASE_PASSWORD` which the backend
does not consume; the password already travels inside `DATABASE_URL`. That
unnecessary hosted variable was removed and future uploads skip it along with
the service-role key. A boundary test reproduced the exclusion failure first.
No actual password/value was printed. Application code and public APIs are unchanged.

## Railway resources and rollout state

- Project: `document-copilot`, ID `228f9616-88f0-49be-af6f-01c62be37aae`.
- Environment: `production`; services `backend` and `frontend`.
- Backend: https://backend-production-927f.up.railway.app (port 8001).
- Frontend: https://frontend-production-e3f9.up.railway.app (port 8080).
- Runtime configuration uploaded via stdin. Service-role and standalone password
  are excluded; the app uses the transaction pooler. No local `.env` was edited.
- Backend initial deployment: `c303565b-8560-4f3b-96f6-c9b2b13fc9e8`.
- Frontend initial deployment: `7d8bd54c-fdf4-4a3b-8a18-0a9ea2560bcf`.

Both initial deployments reached **SUCCESS**. On 2026-10-24, public HTTPS
checks verified:

| Hosted check | Result |
| --- | --- |
| Backend `/health` | 200, `{"status":"ok"}`; this is process health, not an authenticated database/model check |
| `/chat/threads` without bearer token | 401 |
| Frontend root and direct `/chats/<uuid>` route | 200, identical app shell |
| Cache policy | Shell `no-cache`; hashed JS/CSS immutable, one year |
| CORS preflight | Hosted frontend allowed; unlisted origin rejected (400, no allow-origin header) |
| Served JS configuration | Correct backend and Supabase URLs |
| Served bundle scan | No matches for local privileged values or secret-key patterns |
| Hosted log sample | Latest 200 requested per service (10 backend / 14 frontend lines returned); no matching privileged values, secret-key patterns or traceback marker |
| Hosted variable readback | No service-role key or standalone database password; transaction port 6543; exact frontend CORS origin |

The scan covers the observed bundle/log sample, not every possible future log.
Sanitized evidence: ignored `data/chunks/assistant/delivery-hosted-*-20261024.json`.

The effective initial Railway deployment manifest had no health-check paths,
despite the repository JSON settings. The existing paths, 60-second health timeout,
one replica per service, and five ON_FAILURE restart retries were explicitly
applied through the Railway API, followed by redeployments. Final rollout evidence
is recorded below; do not infer those settings from a local file alone.

The first backend snapshot redeploy failed while the prior healthy deployment
remained active. Railway rejected an explicit legacy config-file path with
BAD_USER_INPUT: JSON/TOML config-as-code is deprecated in favor of newer IaC.
Fresh uploads stage tracked service files without `railway.json` or `.env*`,
using the existing API-applied service settings. The repeatable procedure is in
[runbook section 2b](runbook.md#2b-repeatable-manual-upload). No application code,
configuration ownership migration, new dependency or provider change was needed.

Final review: a fresh read-only reviewer found no helper correctness/security
findings. The stale handoff outstanding-check sentence was reconciled to public
hosted evidence; authenticated checks remain open. No paid checks were run.

## Final configured rollout (2026-10-24)

| Service | Deployment | State | Effective health check |
| --- | --- | --- | --- |
| Backend | `aa6aba75-1f09-4140-a04b-a52d78e7dd76` | SUCCESS | `/health`, timeout 60 s |
| Frontend | `0c784d4f-e9d0-401a-b1f3-bcb7813a1c8f` | SUCCESS | `/`, timeout 60 s |

Both effective manifests show one replica in one region and ON_FAILURE with five
restart retries. Public backend health and frontend root were rechecked at 200
after rollout. The initial backend deployment remains a known-good rollback
candidate, but lacks the corrected health-check manifest: preserve service
settings and prefer re-uploading the last good reviewed application snapshot.
At this initial rollout checkpoint, no rollback drill or authenticated history/
restart check had been performed. Later owner-reported restart acceptance is
recorded below; rollback remains outstanding.

Final routine checks: 477 backend offline tests pass (15 integration tests
excluded); backend lint and changed-Python formatting pass. Frontend type/lint/build
passed during preparation, with no frontend source changes afterward. Markdown
links/fences/UTF-8 and `git diff --check` pass. The independent reviewer found no
helper correctness/security issues; its stale documentation finding was corrected.

## Outstanding gates

- [x] Both hosted services healthy and served over HTTPS (public checks 2026-10-24).
- [x] Supabase Site URL and exact hosted callback configured and visibly saved
  on 2026-10-24, with both localhost redirects in the allowlist (details below).
- [x] Owner reports spending controls pass (2026-10-24), responding to the listed Railway/OpenAI controls; exact account thresholds were not independently read back.
- [x] Owner confirms an approved account signs in and chats load on the hosted app (2026-10-24; owner-reported browser result).
- [x] Owner reports hosted two-approved/one-unapproved confidentiality checks passed (2026-10-24): private sidebars, refused foreign chat URL, unapproved account held pending.
- [x] Owner reports one hosted Azure question passed progress, completed answer, source inspection and reload persistence without duplicates (2026-10-24).
- [x] Owner reports feedback add/change/remove and manual chat rename, title search and reload persistence passed (2026-10-24).
- [x] Owner reports chat switching during generation, Stop, Retry, completion and reload without duplicate exchanges passed (2026-10-24).
- [x] Owner reports the final feature checks pass (2026-10-24): contextual follow-ups, generated titles/manual-rename protection, and disposable-test-chat deletion. No additional agent-run paid calls were made.
- [x] Hosted bundle/log sample credential checks; no raw sensitive diagnostics published (2026-10-24; scope above).
- **Deferred by owner (2026-10-24):** hosted six-turn/twelve-turn capacity batches for the one-person pilot. No verified multi-user capacity or 40-user guarantee.
- [x] Owner reports saved conversation and citations survived a hosted backend restart (2026-10-24).
- **Untested limitation at provisional closure:** hosted rollback drill. Procedure and known-good deployment references are documented; successful restart is not rollback proof.
- **Deferred by owner (2026-10-24):** database backup/restore readiness and drill for the free-plan one-person pilot. No manual backup or restore was performed. Future migrations still require review and a backup.
- [ ] Owner confirms pilot start week and performs real timed tasks; no pilot
  observations or time-saving results exist yet.

The detailed [pilot scheme](../pilot/pilot-plan.md) is ready independently of
hosting. Phase 9 is provisionally closed by owner decision with the limitations
above; phase 10's stand-in outcome remains separate from the original five-analyst
definition of done.

## Execution rulings

- Continue the existing authorized checkout without an unrequested branch or
  commit. Cost if wrong: delivery edits remain pending review in the working tree.
- Apply existing Railway settings and omit the deprecated legacy JSON in upload
  staging, rather than introduce a new IaC architecture in this delivery task.
  Cost if wrong: future uploads could drift unless effective settings are checked;
  the runbook explicitly requires that check.
- Treat the review's stale pending-check summary as a documentation correctness
  issue and reconcile it with recorded evidence. No application behavior changed.

## Supabase dashboard setup (2026-10-24)

After the owner signed in, the dashboard showed the old default Site URL
`http://localhost:3000` and no redirect allowlist. Saved and verified:

- Site URL: `https://frontend-production-e3f9.up.railway.app`.
- Redirect: `https://frontend-production-e3f9.up.railway.app/auth/callback`.
- Redirect: `http://localhost:5173`.
- Redirect: `http://localhost:5173/auth/callback`.

The saved page lists three redirects; the Site URL save button is disabled with
the new value displayed. Screenshot evidence is local and ignored:
`data/chunks/assistant/supabase-url-configuration-20261024.png`. No passwords,
keys, accounts, approval rules or database records were changed. This confirms
configuration only; no confirmation email or end-to-end callback was exercised.

The owner reports Railway has 29 trial days or $4.97 credit remaining. This is
owner-reported trial availability, not a newly configured monthly usage cap.
The earlier CLI readback found no custom workspace limit; none was set here.
OpenAI alerts and ongoing hosting funding remain unconfirmed.

## Hosted owner check (2026-10-24)

After configuring the URLs, the owner reported that chats load on the deployed
app after being asked to sign in with an approved account. This is recorded as
owner-reported approved-account access and history loading, not an independently
observed two-account isolation, new-turn persistence, restart recovery, or
confirmation-email/callback test. No model call was made by the agent.

## Hosted five-check acceptance (2026-10-24)

The owner replied **“all works”** to the five explicit hosted checks supplied in
this conversation. Recorded as owner-reported passes:

1. Azure-2025 question: visible progress, completed reply, supporting citation
   text and original SEC filing link.
2. Reload after completion: same question, answer and citations, no duplicates.
3. Second approved account: private sidebar; the first account's direct chat URL
   refused without exposing messages or citations.
4. Existing unapproved account: pending approval and no chat access.
5. Backend restart after generation finished: saved conversation/citations intact.

No agent-side paid call, new database inspection or repeated generation was run
to reconfirm these reports. They do not cover retry replay, Stop/navigation during
generation, feedback/title controls, conversational follow-ups, rollback, capacity
or confirmation-email delivery. Phase 9 remains open for those and the spending
and operational gates; the stand-in pilot has not started.

## Hosted feedback and manual title controls (2026-10-24)

The owner replied **“pass”** to both checks requested on the same saved chat:
feedback add/change/remove, and manual rename followed by title search and reload
persistence. Recorded as owner-reported passes. This does not establish automatic
title generation, protection against a late generated-title overwrite, or chat
deletion. No model calls or database inspections were run by the agent.

## Hosted generation controls and phase-9 closure (2026-10-24)

The owner reports the three requested control steps passed: switching chats did
not cancel generation; Stop made the interrupted reply retryable; Retry completed
and reload showed one completed exchange. Recorded as owner-reported acceptance,
without an additional agent-run generation or database check.

The remaining closure work is limited to the approved delivery plan:

1. Remaining hosted feature smoke: contextual follow-up, generated title with
   manual-rename protection, and deletion of an explicitly disposable test chat.
2. Cost readiness: confirm the trial/funding boundary and spending controls, plus
   OpenAI budget alerts. Reported trial credit is not proof alerts are configured.
3. Operational readiness: confirm a usable backup/restore route and record rollback
   readiness/verification; no destructive restore or migration is authorized here.
4. Capacity: separately approved hosted six-turn and twelve-turn batches, record
   failures/latency under the 120-second deadline. No broader capacity promise.

Pilot start-date confirmation and human timings belong to phase 10, not an extra
phase-9 completion gate. This was the closure list before the later owner decision
below; capacity and backup/restore were subsequently deferred, not passed.

## Owner provisional closure decision (2026-10-24)

The owner explicitly deferred database backups/restoration because this project
uses Supabase Free, and deferred hosted capacity testing for the one-person pilot.
Manual logical exports remain technically possible; this decision does not claim
that all backup options require a paid plan. The owner then requested temporary
phase-9 closure with limitations and reported **“final feature checks and spending
controls passes.”**

Recorded as owner-reported passes for the previously listed contextual follow-up,
generated-title/manual-rename protection, disposable-chat deletion, and Railway/
OpenAI spending-control checks. No threshold values or screenshots were supplied;
those account settings were not independently re-read. The earlier trial-credit
report remains historical, not a prediction of future funding.

Phase 9 is **provisionally closed for the one-person stand-in pilot**. Limitations:

- No verified backup/restore route or disaster-recovery result. Database loss may
  lose account profiles, conversations and citations; restarting the backend does
  not establish recovery from database loss. Supabase Auth recovery is unverified.
- No hosted capacity measurements; local six/twelve-turn results do not establish
  hosted or 40-user capacity. Preserve one backend process/replica and the
  120-second deadline.
- Application rollback is documented but no hosted rollback drill was performed.
- Exact spending thresholds and confirmation-email delivery/callback behavior were
  not independently verified. Approved-account sign-in was owner-tested.

Revisit the deferred operational work before a broader rollout or consequential
data changes. No corpus expansion, new database operation, migration, paid batch,
plan upgrade or application-code change was authorized or run by this closure.
Phase 10 still needs an owner-confirmed start date and real timed observations.
