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
uv run python -m pytest                # Tests
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
uv run python -m pytest tests/database/test_rls.py -q
uv run python scripts/check_sign_in.py
```

The sign-in check prompts for an existing account's email/password, keeps tokens
in memory, and calls the actual backend authentication dependency. No running
Uvicorn server is needed. Run for each approved account; an unapproved account
can be checked with `--expected-status 403`. The account must already have a password.

The RLS test uses temporary database identities and rolls back every fixture.
Token rejection cases use mocked Auth responses; real invited-user sign-in still
needs testing with actual sessions. No tokens or passwords belong in committed files.
