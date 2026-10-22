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

> Status 2026-10-22: blocked by Railway's platform outage (builds paused for
> Hobby/Free/Trial workspaces after a security incident). Do not store
> secrets on Railway until the incident is closed.

1. `railway login`, then from the repo root `railway init -n document-copilot`.
2. Create the two services and public domains:
   `railway add --service backend`, `railway add --service frontend`,
   `railway domain --service backend`, `railway domain --service frontend`.
3. Copy configuration (owner runs it; prints key names only):
   `python deploy/push_railway_env.py --backend-url https://<backend domain> --frontend-url https://<frontend domain>`.
   It sends everything in `backend/.env` except `SUPABASE_SERVICE_ROLE_KEY`
   (admin scripts only) and sets `ALLOWED_ORIGINS` to the frontend URL.
4. Deploy: `railway up backend --path-as-root --service backend` and
   `railway up frontend --path-as-root --service frontend` from the repo root.
5. Supabase dashboard, **Authentication → URL Configuration**: set the Site
   URL to the frontend URL and add it to Redirect URLs.
6. Spending alerts: Railway workspace **Settings → Usage** (alert and hard
   limit); OpenAI **Settings → Limits** (monthly budget, alert at 80%).
7. Smoke test in the browser: sign in, ask an example question, open a
   citation, reload a `/chats/<id>` URL (SPA fallback), reopen history.

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

## 3a. Capacity (measured 2026-10-22)

Local machine, production models, each answer holding a database transaction
as the real endpoint does:

| Simultaneous answers | Session pooler (5432) | Transaction pooler (6543) |
|---:|---|---|
| 6 | 6 of 6 accepted, 17–36 s | — |
| 12 | **6 of 12 failed** ("max clients reached … pool_size: 15") | 12 of 12 accepted, 16–35 s |

Each answer holds one transaction for its whole duration (up to 120 s), so the
transaction pooler's 15 server connections cap simultaneous answers at about
15 across all users; with at most 2 per user this covers the 40-analyst pilot.
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

Cited chunks cannot be deleted: `message_citations.chunk_id` is
`ON DELETE RESTRICT`, so replacing a filing that analysts have cited needs a
migration plan (keep old chunks, or remap citations) before re-ingesting.

## 7. Backup and restore

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
- From git: `git revert <bad commit>`, then redeploy with `railway up` as in
  section 2.
- Database migrations: `uv run alembic downgrade -1` only after checking the
  migration's downgrade; data-dropping downgrades need a backup first.

## 9. Conversation history and restarts

History is durable by design: a turn is saved and committed before the
stream sends `finish`, and a failed or interrupted turn is rolled back.
Verified 2026-10-22: threads created on 2026-10-21 were intact after many
backend restarts that day, and turns stopped mid-answer left no rows.

## 10. Users

- Approve a signed-up user: `uv run python -m app.database.approve_user <user-uuid>`.
- Reset a password (admin, needs `SUPABASE_SERVICE_ROLE_KEY` in the local
  `.env` only): `uv run python scripts/set_user_password.py`.
- Revoking approval deletes the user's row and **cascade-deletes their chat
  history**; export what must be kept first.
