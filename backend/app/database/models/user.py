from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, CheckConstraint, String, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.database.models.chat_thread import ChatThread


class User(Base, TimestampMixin):
    """One row per Supabase Auth user (`auth.users.id`)."""

    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint(
            "(is_demo AND email IS NULL) OR (NOT is_demo AND email IS NOT NULL)",
            name="ck_users_demo_email",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    is_demo: Mapped[bool] = mapped_column(
        Boolean, server_default=text("false"), nullable=False
    )
    display_name: Mapped[str | None] = mapped_column(String(255))

    chat_threads: Mapped[list[ChatThread]] = relationship(back_populates="owner")
