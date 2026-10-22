from typing import Annotated, Literal
from uuid import UUID

import psycopg
import structlog
from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.api.threads import FeedbackResponse
from app.auth.dependencies import CurrentUser, get_current_user
from app.database import chats
from app.database.connection import get_connection
from app.database.models.message_feedback import FeedbackReason

router = APIRouter(prefix="/chat/messages", tags=["answer feedback"])
User = Annotated[CurrentUser, Depends(get_current_user)]
Connection = Annotated[psycopg.Connection, Depends(get_connection, scope="function")]
logger = structlog.get_logger()


class FeedbackRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    rating: Literal["up", "down"]
    reason: FeedbackReason | None = None
    comment: str | None = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def reason_only_with_thumbs_down(self) -> "FeedbackRequest":
        if self.rating == "up" and self.reason is not None:
            raise ValueError("A reason applies only to a thumbs-down rating")
        return self


@router.put("/{message_id}/feedback", response_model=FeedbackResponse)
async def save_feedback(
    message_id: UUID, payload: FeedbackRequest, user: User, connection: Connection
) -> dict[str, object]:
    saved = await chats.save_feedback(
        connection,
        user.id,
        message_id,
        payload.rating,
        payload.reason,
        payload.comment or None,
    )
    # The comment stays in the database; logs carry only the category.
    logger.info(
        "answer_feedback_saved",
        message_id=str(message_id),
        rating=payload.rating,
        reason=payload.reason,
        has_comment=bool(payload.comment),
    )
    return saved


@router.delete("/{message_id}/feedback", status_code=204)
async def clear_feedback(
    message_id: UUID, user: User, connection: Connection
) -> Response:
    await chats.clear_feedback(connection, user.id, message_id)
    return Response(status_code=204)
