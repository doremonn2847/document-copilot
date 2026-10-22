from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

import psycopg
from fastapi import APIRouter, Depends, Query, Response
from pydantic import BaseModel, ConfigDict, Field, JsonValue

from app.auth.dependencies import CurrentUser, get_current_user
from app.database import chats
from app.database.connection import get_connection
from app.database.models.message_feedback import FeedbackReason

router = APIRouter(prefix="/chat/threads", tags=["chat threads"])
User = Annotated[CurrentUser, Depends(get_current_user)]
Connection = Annotated[psycopg.Connection, Depends(get_connection, scope="function")]
PageSize = Annotated[int, Query(ge=1, le=200)]
PageOffset = Annotated[int, Query(ge=0)]


class ThreadCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    id: UUID | None = None
    title: str = Field(default="New chat", min_length=1, max_length=255)


class ThreadResponse(BaseModel):
    id: UUID
    title: str
    created_at: datetime
    updated_at: datetime


class FeedbackResponse(BaseModel):
    rating: Literal["up", "down"]
    reason: FeedbackReason | None
    comment: str | None


class MessageResponse(BaseModel):
    id: UUID
    thread_id: UUID
    role: Literal["USER", "ASSISTANT", "SYSTEM"]
    content: str | None
    parts: list[dict[str, JsonValue]] | None
    sequence: int
    created_at: datetime
    feedback: FeedbackResponse | None = None


@router.post("", response_model=ThreadResponse, status_code=201)
async def create_thread(
    payload: ThreadCreate, user: User, connection: Connection
) -> dict[str, object]:
    return await chats.create_thread(connection, user.id, payload.title, payload.id)


@router.get("", response_model=list[ThreadResponse])
async def list_threads(
    user: User, connection: Connection, limit: PageSize = 50, offset: PageOffset = 0
) -> list[dict[str, object]]:
    return await chats.list_threads(connection, user.id, limit, offset)


@router.get("/{thread_id}/messages", response_model=list[MessageResponse])
async def list_messages(
    thread_id: UUID,
    user: User,
    connection: Connection,
    limit: PageSize = 100,
    offset: PageOffset = 0,
) -> list[dict[str, object]]:
    return await chats.list_messages(connection, user.id, thread_id, limit, offset)


@router.delete("/{thread_id}", status_code=204)
async def delete_thread(
    thread_id: UUID, user: User, connection: Connection
) -> Response:
    await chats.delete_thread(connection, user.id, thread_id)
    return Response(status_code=204)
