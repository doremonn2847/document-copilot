from typing import Annotated
from uuid import uuid5

import psycopg
from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse

from app.auth.dependencies import CurrentUser, get_current_user
from app.chat.messages import ChatRequest
from app.chat.streaming import stream_turn
from app.database import chats
from app.database.connection import get_connection

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
    return StreamingResponse(
        stream_turn(
            request,
            connection,
            payload.threadId,
            user_message_id,
            assistant_message_id,
            payload.question,
            existing,
            user_id=user.id,
        ),
        media_type="text/event-stream",
        headers={
            "x-vercel-ai-ui-message-stream": "v1",
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
