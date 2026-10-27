"""Private public-demo ledger and anonymous profiles.

Revision ID: d90e7c5a2101
Revises: 3ff92ab46eb9
"""

from alembic import op

revision = "d90e7c5a2101"
down_revision = "3ff92ab46eb9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE public.users ADD COLUMN is_demo boolean NOT NULL DEFAULT false"
    )
    op.execute("ALTER TABLE public.users ALTER COLUMN email DROP NOT NULL")
    op.execute(
        "ALTER TABLE public.users ADD CONSTRAINT ck_users_demo_email CHECK ((is_demo AND email IS NULL) OR (NOT is_demo AND email IS NOT NULL))"
    )
    op.execute("""CREATE TABLE public.demo_visitors (
        user_id uuid PRIMARY KEY REFERENCES public.users(id) ON DELETE CASCADE,
        attempts_started integer NOT NULL DEFAULT 0,
        active_attempt uuid, lease_until timestamptz,
        CONSTRAINT ck_demo_visitors_attempts CHECK (attempts_started >= 0))""")
    op.execute("""CREATE TABLE public.demo_budget_days (
        day date PRIMARY KEY, ceiling bigint NOT NULL,
        charged bigint NOT NULL DEFAULT 0, reserved bigint NOT NULL DEFAULT 0,
        admissions integer NOT NULL DEFAULT 0, blocked boolean NOT NULL DEFAULT false,
        CONSTRAINT ck_demo_budget_nonnegative CHECK (ceiling > 0 AND charged >= 0 AND reserved >= 0 AND admissions >= 0))""")
    op.execute("""CREATE TABLE public.demo_attempts (
        id uuid PRIMARY KEY, user_id uuid REFERENCES public.users(id) ON DELETE SET NULL,
        thread_id uuid NOT NULL, question_id uuid NOT NULL,
        state varchar(16) NOT NULL DEFAULT 'active', provider_starts integer NOT NULL DEFAULT 0,
        created_at timestamptz NOT NULL DEFAULT now(), finished_at timestamptz,
        CONSTRAINT ck_demo_attempt_state CHECK (state IN ('active', 'finished') AND provider_starts >= 0))""")
    op.execute("""CREATE TABLE public.demo_model_requests (
        id uuid PRIMARY KEY, attempt_id uuid NOT NULL REFERENCES public.demo_attempts(id),
        day date NOT NULL REFERENCES public.demo_budget_days(day),
        model varchar(64) NOT NULL, endpoint varchar(32) NOT NULL, rate_revision varchar(64) NOT NULL,
        input_rate numeric(12,6) NOT NULL, output_rate numeric(12,6) NOT NULL,
        input_limit integer NOT NULL, output_limit integer NOT NULL,
        reservation bigint NOT NULL, charge bigint, input_tokens integer, output_tokens integer,
        state varchar(16) NOT NULL DEFAULT 'reserved', created_at timestamptz NOT NULL DEFAULT now(), settled_at timestamptz,
        CONSTRAINT ck_demo_request_state CHECK (state IN ('reserved', 'unknown', 'settled') AND reservation > 0 AND (charge IS NULL OR charge BETWEEN 0 AND reservation)))""")
    for table in (
        "demo_visitors",
        "demo_budget_days",
        "demo_attempts",
        "demo_model_requests",
    ):
        op.execute(f"ALTER TABLE public.{table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"REVOKE ALL ON public.{table} FROM PUBLIC, anon, authenticated")
        op.execute(f"GRANT ALL ON public.{table} TO service_role")
    # Converted anonymous identities must not bypass ordinary approval via REST.
    for table in ("source_documents", "document_chunks"):
        op.execute(f"DROP POLICY {table}_read_approved ON public.{table}")
        op.execute(
            f"CREATE POLICY {table}_read_approved ON public.{table} FOR SELECT TO authenticated USING (EXISTS (SELECT 1 FROM public.users u WHERE u.id = (SELECT auth.uid()) AND u.is_demo = COALESCE((SELECT auth.jwt()->>'is_anonymous')::boolean, false)))"
        )


def downgrade() -> None:
    # Financial evidence and nullable guest rows cannot safely be erased by rollback.
    raise RuntimeError(
        "Disable DEMO_ENABLED and roll back application code; retain the demo ledger. Destructive schema downgrade requires a separate reviewed retention plan."
    )
