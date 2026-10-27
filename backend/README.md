# Backend

Run these commands from `D:\document-copilot\backend`.

```powershell
uv sync --locked                      # Create/update .venv from the lockfile
uv run python -m uvicorn app.main:app --reload --port 8001
```

Configure credentials in `.env` using `.env.example` as the template.
The app validates configuration when it starts.

- Health: http://localhost:8001/health
- API docs: http://localhost:8001/docs
- Stop: **Ctrl+C**. Development mode reloads after code changes.

```powershell
uv run python -m pytest                # Offline tests (live ones need -m integration)
uv run ruff check .                    # Lint
uv add <package>                       # Add a runtime dependency
uv add --dev <package>                 # Add a development dependency
```

Commit `pyproject.toml` and `uv.lock` after dependency changes. Keep `.env` private.
For Jupyter, select `backend/.venv/Scripts/python.exe` as the kernel.

## Database migrations

Use the direct/session connection in `DATABASE_URL`, not the transaction pooler.

```powershell
uv run alembic upgrade head            # Apply migrations
uv run alembic current                 # Show database revision
uv run alembic check                   # Check models match the database
uv run alembic revision --autogenerate -m "describe change"
```

Review generated migrations before applying. RLS, grants, and Supabase-specific
operations need explicit review. The initial downgrade drops all six app tables
and their data; it keeps Supabase Auth and the shared vector extension.

## Authentication

Users may register publicly and confirm their email, but app access requires
manual approval. Review the account's eligibility, then approve it using its
Auth user UUID (from Authentication → Users). Invited accounts also work after
email confirmation:

```powershell
uv run python -m app.database.approve_user <user-uuid>
```

`GET /auth/me` requires `Authorization: Bearer <access-token>` and returns the
verified user ID/email. Supabase Auth verifies the token; a matching `public.users`
profile grants app access. Keep future private routes behind `get_current_user`
and check resource ownership before using privileged clients. Health stays public.

```powershell
uv run python -m pytest -m "not integration" -q
uv run python -m pytest tests/database/test_rls.py -m integration -q
uv run python scripts/check_sign_in.py
```

The sign-in check prompts for an existing account's email/password, keeps tokens
in memory, and calls the actual backend authentication dependency. No running
Uvicorn server is needed. Run for each approved account; an unapproved account
can be checked with `--expected-status 403`. The account must already have a password.

The RLS test uses temporary database identities and rolls back every fixture.
Token rejection cases use mocked Auth responses. The owner verified two approved
browser accounts and one unapproved account locally on 2026-10-23; hosted-session
checks remain part of phase 9. No tokens or passwords belong in committed files.

## Chat thread endpoints

All endpoints require an approved user's bearer token:

| Method | Path | Result |
| --- | --- | --- |
| POST | `/chat/threads` | Create a thread with `{"title": "New chat"}` (or `{}`); returns 201 |
| GET | `/chat/threads` | List only the current user's threads, newest updated first |
| GET | `/chat/threads/{thread_id}/messages` | Read owned-thread messages in sequence order |

List endpoints accept `limit` (1–200) and `offset` (0 or greater). Defaults are
50 threads or 100 messages. Fetch subsequent pages when needed. Unknown threads
return 404; another user's thread returns 403. Ownership comes from the verified
session, and a submitted `user_id` is rejected. Invalid inputs return 422;
database failures return a generic 503.

Async handlers run psycopg database I/O in FastAPI's worker pool, supporting the
default Windows event loop without blocking requests. They use the existing
database connection setting. This
privileged connection requires explicit ownership checks; Supabase's RLS remains
in place for browser/user-scoped database access. Writes commit before success
is sent. No schema migration or new dependency is required.

```powershell
uv run python -m pytest tests/api/test_threads.py -q
uv run python -m pytest tests/database/test_chat_endpoints.py -m integration -q
```

The live endpoint test overrides authentication with temporary identities,
executes real SQL, and rolls back all fixtures. The chat UI and grounded stream
are implemented; phases 6–8 have recorded owner acceptance. See the
[delivery status](../docs/operations/delivery-status.md) for remaining hosted checks.

## Chat stream

`POST /chat/stream` requires the same approved-user bearer token. Send:

```json
{
  "threadId": "the-created-thread-uuid",
  "messages": [{"id": "unique-question-id", "role": "user", "parts": [{"type": "text", "text": "What is Apple's revenue?"}]}]
}
```

It returns SSE using the installed AI SDK 7 UI-message protocol, with
`x-vercel-ai-ui-message-stream: v1`. The reply comes from the grounded assistant
(`app/chat/orchestrator.py`): progress parts while it works, then the verified
answer text, structured `data-answer` blocks and `data-citation` parts. New
answers are limited per user (2 in progress, 60 per hour; 429 with Retry-After).
The final message must be a user question. Text and SDK step-start parts are
supported; attachments, tool parts, and regeneration are not implemented yet.
Earlier client messages do not determine database ownership or stored history.

The question and reply are inserted together in one transaction. `finish` is
sent only after commit. Cancellation observed before commit rolls back the
turn; persistence failures emit a safe `error` event without `finish`.
The UI marks missing completion as interrupted, even if all text
arrived. A disconnect just after commit may leave a saved turn; reload history
to recover it. Retrying the same question ID replays that saved answer rather
than inserting another pair. Reusing an ID for different text returns 409.

Thread-row locking serializes turns; a concurrent stream gets 409. The stream
keeps its transaction until completion, while regular thread operations commit
before responding. Interrupted-stream cleanup releases the connection/lock.

```powershell
uv run python -m pytest tests/chat tests/api -q --tb=no
uv run python -m pytest tests/database/test_chat_endpoints.py -m integration -q --tb=no
```

The live test keeps stream commits inside a rollback-only fixture transaction.
Durability ordering and commit failure behavior are covered by unit tests.

## Public demo implementation

Anonymous Try demo access is live on Railway (the local default remains disabled). Read
[the demo setup and rollout notes](app/demo/README.md) before enabling it or
applying migration `d90e7c5a2101`. Registered-account approval remains required.
