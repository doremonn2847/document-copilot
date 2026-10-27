# Document Copilot operations runbook

For the one developer who maintains the hosted pilot. Commands run from
`backend/` unless stated otherwise. Never paste secrets into chat tools,
commits or logs; `.env` files stay local.

## 1. What runs where

| Part | Where | Notes |
|---|---|---|
| Frontend (React SPA) | Railway service `frontend` | `frontend/Dockerfile`: pnpm build, served by Caddy with SPA fallback. `VITE_*` values are public and baked in at build time. |
| Backend (FastAPI) | Railway service `backend` | `backend/Dockerfile`, health check `GET /health`, **one replica** (per-user answer limits are in-process). |
| Database and sign-in | Supabase (Postgres + Auth) | Chats, approvals, filings and chunks. The hosted backend uses the **transaction pooler (port 6543)**; migrations and ingestion use the session pooler (5432). |
| Answers and embeddings | OpenAI | Models are set by `OPENAI_*` variables; see `backend/.env.example`. |

## 2. First deployment (Railway)

> Historical status 2026-10-22: builds were paused after a security incident.
> Rechecked 2026-10-23: the official status page reports builds/deployments for
> all plans proceeding, while the incident remains Identified. The owner
> explicitly authorized deployment after that distinction was reported. This
> does not mean the security incident is resolved. Current resources, build
> results and remaining gates: [delivery status](delivery-status.md).

The current project is already created and linked. Do not repeat `railway init`
or create duplicate services. Backend: https://backend-production-927f.up.railway.app;
frontend: https://frontend-production-e3f9.up.railway.app. The following is a
first-setup reference; inspect existing state before any mutation.

1. `railway login`, then from the repo root `railway init -n document-copilot`.
2. Create the two services and public domains:
   `railway add --service backend`, `railway add --service frontend`,
   `railway domain --service backend`, `railway domain --service frontend`.
3. Copy configuration (owner runs it; prints key names only):
   `python deploy/push_railway_env.py --backend-url https://<backend domain> --frontend-url https://<frontend domain>`.
   It excludes `SUPABASE_SERVICE_ROLE_KEY` (admin scripts only) and standalone
   `DATABASE_PASSWORD` (already inside `DATABASE_URL`), and sets `ALLOWED_ORIGINS`
   to the frontend URL. Windows command shims are resolved explicitly; secret
   values stay on stdin and raw CLI error text is withheld.
4. Deploy from a clean tracked-files staging directory as shown in section 2b.
   Current Railway rejects the legacy JSON configuration format; keep the
   existing service settings in Railway and omit `railway.json` from uploads.
5. Supabase dashboard, **Authentication → URL Configuration**: set the Site
   URL to the frontend URL and allow the exact
   `https://frontend-production-e3f9.up.railway.app/auth/callback` redirect.
   Retain `http://localhost:5173` and `http://localhost:5173/auth/callback` for
   development. These four URL settings were saved and verified in the dashboard
   on 2026-10-24; actual confirmation-email/callback behavior remains untested.
6. Spending alerts: Railway workspace **Settings → Usage** (alert and hard
   limit); OpenAI **Settings → Limits** (monthly budget, alert at 80%).
7. Smoke test in the browser: sign in, ask an example question, open a
   citation, reload a `/chats/<id>` URL (SPA fallback), reopen history.

## 2a. Recorded hosted checks (2026-10-24)

Both services deployed successfully. Public `/health` returns 200; unauthenticated
chat access returns 401. Root/deep chat routes serve the same SPA; caching and
exact-origin CORS pass. The served bundle references the correct services and,
along with a bounded hosted-log sample, has no detected privileged credential
values. These checks make no database or paid model calls. Full evidence and
remaining gates are in [delivery status](delivery-status.md).

The initial effective Railway manifest omitted health checks despite the local
JSON files. The existing settings were explicitly applied to service configuration;
when redeploying, inspect the effective manifest for `/health` (backend), `/`
(frontend), timeout 60, one replica and five ON_FAILURE retries. Do not assume
CLI-uploaded local JSON was applied merely because the Docker build succeeded.
Railway rejected setting `railwayConfigFile` with BAD_USER_INPUT on 2026-10-24: it
now requires its newer IaC format. Migrating configuration ownership is deferred;
existing service settings and the clean upload procedure below suffice.

The owner confirmed hosted sign-in, answer progress/citations, reload persistence,
two-approved-account isolation, unapproved-account refusal and history/citations
surviving a backend restart on 2026-10-24. The owner also reports feedback
add/change/remove and manual rename/search/reload passed. Remaining hosted checks
exclude generation controls, which the owner also reports passed (chat switching,
Stop, Retry and reload without duplicates). The owner subsequently reports final follow-up,
generated-title/manual-rename protection, disposable-chat deletion and spending
controls pass. Phase 9 is provisionally closed for the one-person pilot. Backup/
restore and hosted capacity testing are owner-deferred; rollback verification is
untested. Exact spending thresholds were not independently read back. Detailed
evidence distinguishes direct agent checks from owner-reported browser results.

## 2b. Repeatable manual upload

From the linked repository root, save this snippet to a temporary Python file
outside the repository and run it with the backend Python interpreter. It copies
current contents of tracked files, including saved uncommitted edits; new files
must be tracked first if needed by the app. It does not add/commit/push files.
It omits local env files and the rejected legacy JSON, retaining Dockerfiles and
lockfiles. Uploads are manual snapshots, not GitHub autodeploys.

```python
import shutil
import subprocess
import tempfile
from pathlib import Path

root = Path.cwd()
railway = shutil.which("railway")
assert railway, "Install/login/link the Railway CLI first"
for service in ("backend", "frontend"):
    files = subprocess.check_output(["git", "ls-files", service], text=True).splitlines()
    with tempfile.TemporaryDirectory(prefix="dc-railway-") as directory:
        stage = Path(directory)
        for name in files:
            relative = Path(name).relative_to(service)
            if relative.name == "railway.json" or relative.name.startswith(".env"):
                continue
            target = stage / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(root / name, target)
        assert (stage / "Dockerfile").is_file()
        subprocess.run([railway, "up", str(stage), "--path-as-root",
                        "--service", service, "--detach"], check=True)
```

Before the upload, service **Settings → Deploy** must retain health checks
`/health` and `/` respectively, timeout 60, one replica and ON_FAILURE with five
retries; those settings were also applied via `serviceInstanceUpdate` on
2026-10-24. After upload, `railway deployment list --service <name> --json` and
public health checks must confirm success; detached upload alone is not a pass.
Use the sanitized delivery record for the latest known good deployment IDs.

## 3. Configuration reference

Required: `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `DATABASE_URL`,
`OPENAI_API_KEY`, `ALLOWED_ORIGINS` (exact origins, comma-separated, no
paths). `SUPABASE_SERVICE_ROLE_KEY` is optional and should stay off the
hosted backend.

Limits worth knowing (defaults in `backend/app/config.py`):

| Setting | Default | Effect |
|---|---:|---|
| `ASSISTANT_USER_CONCURRENT_TURNS` | 2 | Answers in progress per user; more returns 429. |
| `ASSISTANT_USER_TURNS_PER_HOUR` | 60 | New questions per user per hour; replays are free. |
| `ASSISTANT_DEADLINE_SECONDS` | 120 | Whole-answer timeout. |
| `ASSISTANT_COMPARISON_TARGET_CHARS` | 3000 | Evidence per company/year in a comparison. |
| `ASSISTANT_CLAIM_REFS` | 8 | Quotes per claim. |

Frontend build variables: `VITE_API_BASE_URL` (backend URL),
`VITE_SUPABASE_URL`, `VITE_SUPABASE_ANON_KEY` (public key only; the build
rejects secret or legacy service keys).

## 3a. Capacity (measured locally 2026-10-22)

Owner decision 2026-10-24: defer hosted six/twelve-turn capacity testing for the
one-person pilot. This is a documented limitation, not a hosted capacity pass.

Local machine, production models, each answer holding a database transaction
as the real endpoint does:

| Simultaneous answers | Session pooler (5432) | Transaction pooler (6543) |
|---:|---|---|
| 6 | 6 of 6 accepted, 17–36 s | — |
| 12 | **6 of 12 failed** ("max clients reached … pool_size: 15") | 12 of 12 accepted, 16–35 s |

Each answer holds one transaction for its whole duration (up to 120 s). The
measured pool has 15 server connections, shared with retrieval and other database
work. Twelve local successes do not establish a safe global ceiling or capacity
for 40 analysts. Repeat hosted six/twelve-turn probes only in separately approved
paid batches. The current stand-in pilot has one analyst; retain the 120-second
deadline and report actual latency rather than asserting a stronger target.
`deploy/push_railway_env.py` switches a Supabase pooler `DATABASE_URL` to port
6543 for Railway. A larger Supabase compute size raises the pool; releasing
the transaction during generation would remove the cap (future work).

## 4. Logs

`railway logs --service backend` (or the service's Logs tab). Backend logs are
JSON lines (structlog). Useful events:

- `application_started` / `application_stopped`: process lifecycle.
- `assistant_turn_finished`: one per answer. Fields include `status`,
  `failure_type`, model request and token counts, `structural_validation`
  (check names, claim numbers), `withheld` and `judge_rejections` (indices
  only). Answer and source text are deliberately not logged.
- `chat_turn_failed`: `thread_id` and a failure `category` (no user text).
- `assistant_turn_routed`: the front door's decision per turn: `route`
  (`conversation` skips the filings pipeline, `filings` runs it) and
  `rewritten` (a follow-up was turned into a standalone question).
- `assistant_triage_failed`: the front door errored and the turn fell back to
  the filings pipeline (answers still work; check the `failure_type`).
- `answer_feedback_saved`: an analyst rated a reply: `message_id`, `rating`,
  `reason`, `has_comment` (the comment itself is only in the database).

Pilot feedback review (Supabase SQL editor, read-only):

```sql
SELECT f.updated_at, u.email, f.rating, f.reason, f.comment,
       m.thread_id, m.content
FROM public.message_feedback f
JOIN public.users u ON u.id = f.user_id
JOIN public.chat_messages m ON m.id = f.message_id
ORDER BY f.updated_at DESC;
```

The conversation link is `https://<frontend domain>/chats/<thread_id>`.

## 5. Troubleshooting

| Symptom | Likely cause | Check |
|---|---|---|
| App loads, chats never load ("request timed out") | Database ports 5432/6543 unreachable from the backend's network | From the backend host: TCP to the pooler host on 5432. On 2026-10-22 a local network blocked both ports while 443 worked. |
| Sign-in works, every chat request 401/403 | Session expired (401) or user not approved (403) | Approve: `uv run python -m app.database.approve_user <user-uuid>` (needs `DATABASE_URL`). |
| "You have reached the question limit" | Per-user limits (429) | Wait, or raise the two `ASSISTANT_USER_*` variables. |
| "The answer could not be verified against its sources" | Every drafted claim failed grounding | `assistant_turn_finished` → `structural_validation` / `judge_rejections`. Rephrase narrower; report repeated cases. |
| Frontend 404 on reload of `/chats/<id>` | SPA fallback missing | `frontend/Caddyfile` must keep `try_files {path} /index.html`. |
| CORS errors in the browser console | `ALLOWED_ORIGINS` lacks the exact frontend origin | Set it to `https://<frontend domain>` (no trailing path). |
| Backend crash at start | Missing or invalid required variable (fails fast by design) | Deploy logs show the failing setting name. |

## 6. Corpus updates

The corpus is ingested offline from a developer machine, never from the
hosted backend.

1. Download and convert: `uv run data/download.py` (from the repo root;
   **deletes and refetches the local corpus**), then
   `uv run python ../data/convert.py`.
2. Preview (free, no API or database calls):
   `uv run python -m ingest.filing --all --preview-only`.
3. Ingest (embedding cost; writes to the database):
   `uv run python -m ingest.filing --all` or `--file <markdown path>`.
4. Page numbers (free; from the original SEC HTML in `data/downloads/`):
   `uv run python -m ingest.pages` reports coverage per filing (about 97% of
   chunks), and `--write` updates `document_chunks.page`. Run it after every
   ingest; a chunk without a page shows "page unverified".
5. Fiscal years (free; from each filing's own XBRL tag):
   `uv run python -m ingest.fiscal_years`, then `--write`. A filing whose
   tagged year differs from the year its period ended stays NULL and shows
   "fiscal year unverified".

Cited chunks cannot be deleted: `message_citations.chunk_id` is
`ON DELETE RESTRICT`, so replacing a filing that analysts have cited needs a
migration plan (keep old chunks, or remap citations) before re-ingesting.

## 7. Backup and restore

Owner decision 2026-10-24: defer backup/restore readiness and the restore drill
for the free-plan one-person pilot. No managed or manual backup/restore result
is verified. The reference procedure below remains future work; database-loss
recovery is not covered by the passed backend-restart check. Revisit before
consequential data changes or broader rollout.

- Supabase takes daily backups on paid plans; point-in-time recovery is an
  add-on. Check **Database → Backups** for the project's plan before the
  pilot.
- Manual logical backup (any plan), from a machine that can reach the pooler:
  `pg_dump "$DATABASE_URL" --schema=public --no-owner --format=custom -f copilot-YYYYMMDD.dump`.
- Restore into a fresh project: apply migrations (`uv run alembic upgrade head`),
  then `pg_restore --data-only --no-owner -d "$DATABASE_URL" copilot-YYYYMMDD.dump`.
  Auth users live in Supabase's `auth` schema; restoring a project's auth
  users is done through Supabase backups, not this dump.

## 8. Rollback

- Railway keeps previous deployments: service → **Deployments** → choose the
  last good one → **Redeploy**.
- From git: `git revert <bad commit>`, then upload the reviewed snapshot using
  section 2b. This requires approval for shared-branch writes if performed by an agent.
- Database migrations: `uv run alembic downgrade -1` only after checking the
  migration's downgrade; data-dropping downgrades need a backup first.

## 9. Conversation history and restarts

History is durable by design: a turn is saved and committed before the
stream sends `finish`, and a failed or interrupted turn is rolled back.
Verified 2026-10-22: threads created on 2026-10-21 were intact after many
backend restarts that day, and turns stopped mid-answer left no rows.
Hosted owner check 2026-10-24: saved conversation and citations survived a backend
restart after generation completed; this does not test a restart during generation.

## 10. Users

- Approve a signed-up user: `uv run python -m app.database.approve_user <user-uuid>`.
- Reset a password (admin, needs `SUPABASE_SERVICE_ROLE_KEY` in the local
  `.env` only): `uv run python scripts/set_user_password.py`.
- Revoking approval deletes the user's row and **cascade-deletes their chat
  history**; export what must be kept first.

## 11. Reviewer demo account

Provisioned 2026-10-26: the owner created a separate email/password Auth account
and set its password privately in Supabase. Its exact Auth UUID was matched to
the requested demo email in the dashboard, then approved with the existing
`app.database.approve_user` command. The command succeeded and requires an active,
email-confirmed Auth user. No other profile, credential or Auth policy was changed.

This account has normal approved-analyst access to the shared SEC corpus and its
own conversations. Reviewers using it share the same chat history, modification/
deletion permissions and user quota; it is not isolated guest access. Keep its
content disposable, and share the login privately with reviewers. No password is
stored in repository files or reports. No automatic login or public auth bypass
was implemented.

The account inherits the existing hosted per-user limits (2 concurrent answers,
60 new turns/hour, 120-second answer deadline); no stricter demo-specific limit
or new spending ceiling was added. Model calls consume the owner's API credits.

Backend approval is verified; hosted sign-in as this new account remains an owner
check because the password was not supplied to the agent. Verify in a separate
private browser session that sign-in succeeds and existing owner conversations
are absent. Account provisioning made no paid model calls.

## Public Try demo — live, 2026-10-27

The owner approved isolated Supabase anonymous visitors, three generated attempts
per identity and a shared $1/day demo OpenAI pool on 2026-10-27. Implementation,
configuration, retained-cost policy and the exact rollout checklist are in
[backend/app/demo/README.md](../../backend/app/demo/README.md).

This is a new schema/auth change, separate from phase 9's provisional acceptance.
Migration `d90e7c5a2101` was applied before the owner-authorized release; both
services report SUCCESS. [Release evidence](release-2026-10-27.md) records the
commit, deployment IDs and initial hosted checks. Later
[launch evidence](public-demo-launch-2026-10-27.md) records enabled Supabase
anonymous sign-in, hosted `DEMO_ENABLED=true`, two-guest/direct-REST isolation,
disposable-schema concurrent ledger checks and two successful capped paid questions.
The source remains unchanged; the configuration-only backend deployment is
`297dc311-6b3d-4024-abf9-bb5529c0c860`. Set `DEMO_ENABLED=false` and redeploy the
backend to halt new public generation while preserving history and normal users.

The existing shared reviewer account remains a regular account outside the demo
pool. No credentials are exposed by the new button. A private affected-profile
and policy snapshot preceded migration; this does not establish full database/Auth
backup or restore readiness. Roll back application code with demo disabled and
retain the additive schema. Do not automatically downgrade or delete the ledger.
