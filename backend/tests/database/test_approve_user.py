"""Live approval checks use temporary accounts and roll back all changes."""

from contextlib import nullcontext
from uuid import uuid4

import psycopg
import pytest


@pytest.mark.integration
def test_approval_requires_confirmed_active_account(monkeypatch):
    from app.config import settings
    from app.database import approve_user

    connection = psycopg.connect(str(settings.database_url), connect_timeout=10)
    monkeypatch.setattr(
        approve_user.psycopg, "connect", lambda *a, **kw: nullcontext(connection)
    )
    try:
        for confirmed, deleted in ((True, False), (False, False), (True, True)):
            user_id = uuid4()
            connection.execute(
                """INSERT INTO auth.users (id, email, email_confirmed_at, deleted_at)
                VALUES (%s, %s, CASE WHEN %s THEN now() END,
                    CASE WHEN %s THEN now() END)""",
                (user_id, f"{user_id}@example.invalid", confirmed, deleted),
            )
            monkeypatch.setattr("sys.argv", ["approve_user", str(user_id)])
            if confirmed and not deleted:
                approve_user.main()
                approve_user.main()  # Approval is safe to repeat.
            else:
                with pytest.raises(SystemExit, match="Approval failed"):
                    approve_user.main()
            exists = connection.execute(
                "SELECT EXISTS(SELECT 1 FROM public.users WHERE id = %s)", (user_id,)
            ).fetchone()[0]
            assert exists == (confirmed and not deleted)
    finally:
        connection.rollback()
        connection.close()
