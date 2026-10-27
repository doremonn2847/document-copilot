import importlib.util
from pathlib import Path

from sqlalchemy.dialects.postgresql import dialect
from sqlalchemy.schema import CreateTable

from app.database.models import Base, User


def test_money_survives_user_and_chat_deletion():
    attempt = Base.metadata.tables["demo_attempts"]
    assert next(iter(attempt.c.user_id.foreign_keys)).ondelete == "SET NULL"
    assert not attempt.c.thread_id.foreign_keys
    request = Base.metadata.tables["demo_model_requests"]
    assert all(fk.ondelete != "CASCADE" for fk in request.foreign_keys)
    assert User.__table__.c.email.nullable
    ddl = str(CreateTable(User.__table__).compile(dialect=dialect()))
    assert "NOT is_demo AND email IS NOT NULL" in ddl


def test_migration_revokes_clients_and_preserves_typed_corpus_approval(monkeypatch):
    path = Path(__file__).parents[2] / "alembic/versions/d90e7c5a2101_public_demo.py"
    spec = importlib.util.spec_from_file_location("demo_migration", path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    statements = []
    monkeypatch.setattr(migration.op, "execute", statements.append)
    migration.upgrade()
    for table in [
        "demo_visitors",
        "demo_budget_days",
        "demo_attempts",
        "demo_model_requests",
    ]:
        assert f"ALTER TABLE public.{table} ENABLE ROW LEVEL SECURITY" in statements
        assert (
            f"REVOKE ALL ON public.{table} FROM PUBLIC, anon, authenticated"
            in statements
        )
    assert not any("GRANT" in sql and "authenticated" in sql for sql in statements)
    assert sum("auth.jwt()->>'is_anonymous'" in sql for sql in statements) == 2
