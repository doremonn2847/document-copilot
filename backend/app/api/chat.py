from collections.abc import AsyncIterator
from typing import Annotated
from uuid import UUID, uuid5

import psycopg
from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse

from app.api.auth import demo_http_error
from app.auth.dependencies import CurrentUser, get_current_user
from app.chat.limits import limiter
from app.chat.messages import ChatRequest
from app.chat.streaming import stream_turn
from app.config import settings
from app.database import chats
from app.database.connection import get_connection
from app.demo.client import DemoAttempt
from app.demo.errors import DemoUnavailable
from app.demo.store import DemoStore

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("/stream")
async def chat_stream(
    payload: ChatRequest,
    request: Request,
    user: Annotated[CurrentUser, Depends(get_current_user)],
    connection: Annotated[psycopg.Connection, Depends(get_connection)],
) -> StreamingResponse:
    await chats.require_thread_owner(connection, user.id, payload.threadId, lock=True)
    message_id = payload.messages[-1].id
    user_message_id = uuid5(payload.threadId, f"user:{message_id}")
    assistant_message_id = uuid5(payload.threadId, f"assistant:{message_id}")
    existing = await chats.completed_turn(
        connection,
        payload.threadId,
        user_message_id,
        assistant_message_id,
        payload.question,
    )
    attempt = None
    if user.is_demo and existing is None:
        store = DemoStore()
        try:
            attempt = DemoAttempt(
                store, await store.begin(user.id, payload.threadId, user_message_id)
            )
        except DemoUnavailable as error:
            raise demo_http_error(error) from None
    turn = stream_turn(
        request,
        connection,
        payload.threadId,
        user_message_id,
        assistant_message_id,
        payload.question,
        existing,
        user_id=user.id,
        **({"demo_attempt": attempt} if attempt else {}),
    )
    if existing is None and not user.is_demo:
        # Replays of finished turns cost nothing and are not limited.
        limiter.acquire(
            user.id,
            settings.assistant_user_concurrent_turns,
            settings.assistant_user_turns_per_hour,
        )
        turn = released(turn, user.id)
    return StreamingResponse(
        turn,
        media_type="text/event-stream",
        headers={
            "x-vercel-ai-ui-message-stream": "v1",
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


async def released(turn: AsyncIterator[str], user_id: UUID) -> AsyncIterator[str]:
    try:
        async for chunk in turn:
            yield chunk
    finally:
        limiter.release(user_id)
