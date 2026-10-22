"""message feedback

Revision ID: 3ff92ab46eb9
Revises: ab55919814e7
Create Date: 2026-10-23 01:40:17.197663

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "3ff92ab46eb9"
down_revision: str | Sequence[str] | None = "ab55919814e7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "message_feedback",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("message_id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("rating", sa.String(length=8), nullable=False),
        sa.Column("reason", sa.String(length=32), nullable=True),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "rating IN ('up', 'down')", name="ck_message_feedback_rating"
        ),
        sa.CheckConstraint(
            "reason IS NULL OR (rating = 'down' AND reason IN ('wrong_fact', 'wrong_citation', 'missing_information', 'should_have_answered', 'too_slow', 'other'))",
            name="ck_message_feedback_reason",
        ),
        sa.CheckConstraint(
            "char_length(comment) <= 500", name="ck_message_feedback_comment_length"
        ),
        sa.ForeignKeyConstraint(
            ["message_id"], ["chat_messages.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "message_id", "user_id", name="uq_message_feedback_message_user"
        ),
    )
    # Same access model as the chat tables: the backend writes through its
    # privileged connection; signed-in users may only read their own rows.
    op.execute("ALTER TABLE public.message_feedback ENABLE ROW LEVEL SECURITY")
    op.execute("REVOKE ALL ON public.message_feedback FROM anon, authenticated")
    op.execute("GRANT SELECT ON public.message_feedback TO authenticated")
    op.execute("GRANT ALL ON public.message_feedback TO service_role")
    op.execute(
        "CREATE POLICY feedback_read_own ON public.message_feedback FOR SELECT TO authenticated USING (user_id = (SELECT auth.uid()))"
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("message_feedback")
