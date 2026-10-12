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
