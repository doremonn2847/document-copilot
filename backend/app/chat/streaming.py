import asyncio
import json
from collections.abc import AsyncIterator
from uuid import UUID

import psycopg
import structlog
from anyio import CancelScope
from fastapi import Request
from starlette.concurrency import run_in_threadpool

from app.database import chats

logger = structlog.get_logger()


def event(payload: dict[str, object]) -> str:
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


async def stream_turn(
    request: Request,
    connection: psycopg.Connection,
    thread_id: UUID,
    user_message_id: UUID,
    assistant_message_id: UUID,
    question: str,
    existing_answer: str | None,
) -> AsyncIterator[str]:
    answer = (
        existing_answer
        if existing_answer is not None
        else (
            "This is a test reply from Document Copilot. Streaming and private chat history "
            "are connected. Document retrieval and AI answers are not enabled yet."
        )
    )
    committed = False
    try:
        yield event({"type": "start", "messageId": str(assistant_message_id)})
        yield event({"type": "start-step"})
        yield event({"type": "text-start", "id": "reply"})
        for offset in range(0, len(answer), 20):
            if await request.is_disconnected():
                return
            yield event(
                {
                    "type": "text-delta",
                    "id": "reply",
                    "delta": answer[offset : offset + 20],
                }
            )
            await asyncio.sleep(0.04)
        if await request.is_disconnected():
            return
        yield event({"type": "text-end", "id": "reply"})
        if existing_answer is None:
            await chats.save_turn(
                connection,
                thread_id,
                user_message_id,
                assistant_message_id,
                question,
                answer,
            )
        if await request.is_disconnected():
            return
        # Finish means the pair is durable, not merely that text generation stopped.
        await run_in_threadpool(connection.commit)
        committed = True
        yield event({"type": "finish-step"})
        yield event({"type": "finish", "finishReason": "stop"})
        yield "data: [DONE]\n\n"
    except psycopg.Error:
        logger.warning("chat_persistence_failed", thread_id=str(thread_id))
        yield event(
            {
                "type": "error",
                "errorText": "The reply could not be saved. Retry your question.",
            }
        )
        yield "data: [DONE]\n\n"
    finally:
        if not committed:
            with CancelScope(shield=True):
                await run_in_threadpool(connection.rollback)
