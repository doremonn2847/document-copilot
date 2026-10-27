"""Private accounting tables; never exposed through PostgREST grants."""

import sqlalchemy as sa

from app.database.base import Base

demo_visitors = sa.Table(
    "demo_visitors",
    Base.metadata,
    sa.Column(
        "user_id",
        sa.UUID,
        sa.ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    sa.Column("attempts_started", sa.Integer, nullable=False, server_default="0"),
    sa.Column("active_attempt", sa.UUID),
    sa.Column("lease_until", sa.DateTime(timezone=True)),
    sa.CheckConstraint("attempts_started >= 0", name="ck_demo_visitors_attempts"),
)
demo_budget_days = sa.Table(
    "demo_budget_days",
    Base.metadata,
    sa.Column("day", sa.Date, primary_key=True),
    sa.Column("ceiling", sa.BigInteger, nullable=False),
    sa.Column("charged", sa.BigInteger, nullable=False, server_default="0"),
    sa.Column("reserved", sa.BigInteger, nullable=False, server_default="0"),
    sa.Column("admissions", sa.Integer, nullable=False, server_default="0"),
    sa.Column("blocked", sa.Boolean, nullable=False, server_default=sa.text("false")),
    sa.CheckConstraint(
        "ceiling > 0 AND charged >= 0 AND reserved >= 0 AND admissions >= 0",
        name="ck_demo_budget_nonnegative",
    ),
)
demo_attempts = sa.Table(
    "demo_attempts",
    Base.metadata,
    sa.Column("id", sa.UUID, primary_key=True),
    sa.Column("user_id", sa.UUID, sa.ForeignKey("users.id", ondelete="SET NULL")),
    sa.Column("thread_id", sa.UUID, nullable=False),
    sa.Column("question_id", sa.UUID, nullable=False),
    sa.Column("state", sa.String(16), nullable=False, server_default="active"),
    sa.Column("provider_starts", sa.Integer, nullable=False, server_default="0"),
    sa.Column(
        "created_at",
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.text("now()"),
    ),
    sa.Column("finished_at", sa.DateTime(timezone=True)),
    sa.CheckConstraint(
        "state IN ('active', 'finished') AND provider_starts >= 0",
        name="ck_demo_attempt_state",
    ),
)
demo_model_requests = sa.Table(
    "demo_model_requests",
    Base.metadata,
    sa.Column("id", sa.UUID, primary_key=True),
    sa.Column("attempt_id", sa.UUID, sa.ForeignKey("demo_attempts.id"), nullable=False),
    sa.Column("day", sa.Date, sa.ForeignKey("demo_budget_days.day"), nullable=False),
    sa.Column("model", sa.String(64), nullable=False),
    sa.Column("endpoint", sa.String(32), nullable=False),
    sa.Column("rate_revision", sa.String(64), nullable=False),
    sa.Column("input_rate", sa.Numeric(12, 6), nullable=False),
    sa.Column("output_rate", sa.Numeric(12, 6), nullable=False),
    sa.Column("input_limit", sa.Integer, nullable=False),
    sa.Column("output_limit", sa.Integer, nullable=False),
    sa.Column("reservation", sa.BigInteger, nullable=False),
    sa.Column("charge", sa.BigInteger),
    sa.Column("input_tokens", sa.Integer),
    sa.Column("output_tokens", sa.Integer),
    sa.Column("state", sa.String(16), nullable=False, server_default="reserved"),
    sa.Column(
        "created_at",
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.text("now()"),
    ),
    sa.Column("settled_at", sa.DateTime(timezone=True)),
    sa.CheckConstraint(
        "state IN ('reserved', 'unknown', 'settled') AND reservation > 0 AND (charge IS NULL OR charge BETWEEN 0 AND reservation)",
        name="ck_demo_request_state",
    ),
)
