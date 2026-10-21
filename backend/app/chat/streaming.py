import asyncio
import json
from collections.abc import AsyncIterator
from uuid import UUID

import psycopg
import structlog
from anyio import CancelScope
from fastapi import Request
from starlette.concurrency import run_in_threadpool

from app.assistant.deps import BudgetExceeded
from app.assistant.rendering import AcceptedReply
from app.chat.orchestrator import AssistantFailure, GroundingRejected, generate_reply
from app.config import settings
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
    existing_answer: AcceptedReply | None,
    *,
    user_id: UUID,
) -> AsyncIterator[str]:
    committed = False
    task = None
    try:
        yield event({"type": "start", "messageId": str(assistant_message_id)})
        yield event({"type": "start-step"})
        answer = existing_answer
        if answer is None:
            history = await chats.recent_history(
                connection,
                thread_id,
                pairs=settings.assistant_history_pairs,
                characters=settings.assistant_history_chars,
            )
            statuses = asyncio.Queue()

            async def progress(stage):
                statuses.put_nowait(stage)

            task = asyncio.create_task(
                generate_reply(question, history, user_id, thread_id, progress)
            )
            while not task.done():
                if await request.is_disconnected():
                    return
                while not statuses.empty():
                    yield event(
                        {
                            "type": "data-status",
                            "transient": True,
                            "data": {"stage": statuses.get_nowait()},
                        }
                    )
                await asyncio.wait({task}, timeout=0.1)
            while not statuses.empty():
                yield event(
                    {
                        "type": "data-status",
                        "transient": True,
                        "data": {"stage": statuses.get_nowait()},
                    }
                )
            answer = (await task).reply
        yield event({"type": "text-start", "id": "reply"})
        for offset in range(0, len(answer.text), 200):
            if await request.is_disconnected():
                return
            yield event(
                {
                    "type": "text-delta",
                    "id": "reply",
                    "delta": answer.text[offset : offset + 200],
                }
            )
        yield event({"type": "text-end", "id": "reply"})
        for part in answer.parts:
            if part["type"].startswith("data-"):
                yield event(part)
        if await request.is_disconnected():
            return
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
        # Finish acknowledges durability, including citation rows.
        await run_in_threadpool(connection.commit)
        committed = True
        yield event({"type": "finish-step"})
        yield event({"type": "finish", "finishReason": "stop"})
        yield "data: [DONE]\n\n"
    except Exception as error:  # noqa: BLE001 -- sanitize the SSE boundary
        # Raw provider/driver messages may contain secrets; this is the SSE error boundary.
        category = (
            error.category
            if isinstance(error, AssistantFailure)
            else (
                "persistence"
                if isinstance(error, psycopg.Error)
                else "grounding"
                if isinstance(error, GroundingRejected)
                else "budget"
                if isinstance(error, BudgetExceeded)
                else "timeout"
                if isinstance(error, TimeoutError)
                else "service"
            )
        )
        logger.warning("chat_turn_failed", thread_id=str(thread_id), category=category)
        messages = {
            "persistence": "The reply could not be saved. Retry your question.",
            "grounding": "The answer could not be verified against its sources. Try a narrower question.",
            "budget": "The evidence budget was exhausted. Try a narrower question.",
            "timeout": "The reply exceeded its time limit. Retry or narrow your question.",
            "service": "The answering service could not complete this reply. Retry your question.",
            "model_output_limit": "The model reached its response limit. Please report this error before retrying.",
        }
        yield event({"type": "error", "errorText": messages[category]})
        yield "data: [DONE]\n\n"
    finally:
        if task is not None:
            if not task.done():
                task.cancel()
            with CancelScope(shield=True):
                await asyncio.gather(task, return_exceptions=True)
        if not committed:
            with CancelScope(shield=True):
                await run_in_threadpool(connection.rollback)
