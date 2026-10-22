from __future__ import annotations

import uuid
from typing import Literal, get_args

from sqlalchemy import CheckConstraint, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base, TimestampMixin

FeedbackReason = Literal[
    "wrong_fact",
    "wrong_citation",
    "missing_information",
    "should_have_answered",
    "too_slow",
    "other",
]
FEEDBACK_REASONS = get_args(FeedbackReason)


class MessageFeedback(Base, TimestampMixin):
    """One rating per user and assistant reply, for the pilot's trust log."""

    __tablename__ = "message_feedback"
    __table_args__ = (
        UniqueConstraint(
            "message_id", "user_id", name="uq_message_feedback_message_user"
        ),
        CheckConstraint("rating IN ('up', 'down')", name="ck_message_feedback_rating"),
        CheckConstraint(
            "reason IS NULL OR (rating = 'down' AND reason IN ("
            + ", ".join(f"'{reason}'" for reason in FEEDBACK_REASONS)
            + "))",
            name="ck_message_feedback_reason",
        ),
        CheckConstraint(
            "char_length(comment) <= 500", name="ck_message_feedback_comment_length"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    message_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("chat_messages.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    rating: Mapped[str] = mapped_column(String(8), nullable=False)
    reason: Mapped[str | None] = mapped_column(String(32))
    comment: Mapped[str | None] = mapped_column(Text)
