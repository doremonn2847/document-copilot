from uuid import UUID, uuid4

import psycopg
from fastapi import HTTPException
from psycopg.types.json import Jsonb
from starlette.concurrency import run_in_threadpool

from app.assistant.rendering import AcceptedReply


async def create_thread(
    connection: psycopg.Connection,
    user_id: UUID,
    title: str,
    thread_id: UUID | None = None,
) -> dict[str, object]:
    cursor = await run_in_threadpool(
        connection.execute,
        """INSERT INTO public.chat_threads (id, user_id, title)
        VALUES (%s, %s, %s)
        ON CONFLICT (id) DO NOTHING
        RETURNING id, title, created_at, updated_at""",
        (thread_id or uuid4(), user_id, title),
    )
    created = cursor.fetchone()
    if created is not None:
        return created
    cursor = await run_in_threadpool(
        connection.execute,
        "SELECT id, user_id, title, created_at, updated_at FROM public.chat_threads WHERE id = %s",
        (thread_id,),
    )
    existing = cursor.fetchone()
    if existing["user_id"] != user_id:
        raise HTTPException(403, "You do not own this chat thread")
    if existing["title"] != title:
        raise HTTPException(409, "This thread ID was already used with another title")
    return existing


async def list_threads(
    connection: psycopg.Connection, user_id: UUID, limit: int, offset: int
) -> list[dict[str, object]]:
    cursor = await run_in_threadpool(
        connection.execute,
        """SELECT id, title, created_at, updated_at FROM public.chat_threads
        WHERE user_id = %s ORDER BY updated_at DESC, id DESC
        LIMIT %s OFFSET %s""",
        (user_id, limit, offset),
    )
    return cursor.fetchall()


async def list_messages(
    connection: psycopg.Connection,
    user_id: UUID,
    thread_id: UUID,
    limit: int,
    offset: int,
) -> list[dict[str, object]]:
    await require_thread_owner(connection, user_id, thread_id)
    cursor = await run_in_threadpool(
        connection.execute,
        """SELECT m.id, m.thread_id, m.role, m.content, m.parts,
            m.sequence, m.created_at
        FROM public.chat_messages m
        JOIN public.chat_threads t ON t.id = m.thread_id
        WHERE m.thread_id = %s AND t.user_id = %s
        ORDER BY m.sequence ASC LIMIT %s OFFSET %s""",
        (thread_id, user_id, limit, offset),
    )
    return cursor.fetchall()


async def require_thread_owner(
    connection: psycopg.Connection,
    user_id: UUID,
    thread_id: UUID,
    *,
    lock: bool = False,
) -> None:
    # This privileged DB connection bypasses RLS, so check ownership first.
    query = "SELECT user_id FROM public.chat_threads WHERE id = %s"
    if lock:
        query += " FOR UPDATE NOWAIT"
    try:
        cursor = await run_in_threadpool(connection.execute, query, (thread_id,))
    except psycopg.errors.LockNotAvailable as error:
        raise HTTPException(
            409, "A reply is already in progress for this thread"
        ) from error
    thread = cursor.fetchone()
    if thread is None:
        raise HTTPException(404, "Chat thread not found")
    if thread["user_id"] != user_id:
        raise HTTPException(403, "You do not own this chat thread")


async def completed_turn(
    connection: psycopg.Connection,
    thread_id: UUID,
    user_message_id: UUID,
    assistant_message_id: UUID,
    question: str,
) -> AcceptedReply | None:
    cursor = await run_in_threadpool(
        connection.execute,
        """SELECT id, content, parts FROM public.chat_messages
        WHERE thread_id = %s AND id = ANY(%s)""",
        (thread_id, [user_message_id, assistant_message_id]),
    )
    messages = {row["id"]: row for row in cursor.fetchall()}
    if not messages:
        return None
    if len(messages) != 2 or messages[user_message_id]["content"] != question:
        raise HTTPException(409, "This message ID was already used for another turn")
    saved = messages[assistant_message_id]
    return AcceptedReply(text=saved["content"], parts=saved["parts"])


async def recent_history(
    connection: psycopg.Connection, thread_id: UUID, *, pairs: int, characters: int
) -> list[dict]:
    cursor = await run_in_threadpool(
        connection.execute,
        """SELECT role, content, sequence FROM public.chat_messages
        WHERE thread_id = %s ORDER BY sequence DESC LIMIT %s""",
        (thread_id, pairs * 2),
    )
    rows = list(reversed(cursor.fetchall()))
    history = []
    for i in range(0, len(rows) - 1, 2):
        a, b = rows[i : i + 2]
        if (
            a["role"] != "USER"
            or b["role"] != "ASSISTANT"
            or b["sequence"] != a["sequence"] + 1
        ):
            continue
        history.extend(
            [
                {"role": "user", "content": a["content"]},
                {"role": "assistant", "content": b["content"]},
            ]
        )
    while sum(len(m["content"]) for m in history) > characters:
        del history[:2]
    return history


async def save_turn(
    connection: psycopg.Connection,
    thread_id: UUID,
    user_message_id: UUID,
    assistant_message_id: UUID,
    question: str,
    answer: AcceptedReply,
) -> None:
    cursor = await run_in_threadpool(
        connection.execute,
        "SELECT COALESCE(MAX(sequence), -1) + 1 AS next FROM public.chat_messages WHERE thread_id = %s",
        (thread_id,),
    )
    sequence = cursor.fetchone()["next"]
    await run_in_threadpool(
        connection.execute,
        """INSERT INTO public.chat_messages (id, thread_id, role, sequence, content, parts)
        VALUES (%s, %s, 'USER', %s, %s, %s), (%s, %s, 'ASSISTANT', %s, %s, %s)""",
        (
            user_message_id,
            thread_id,
            sequence,
            question,
            Jsonb([{"type": "text", "text": question}]),
            assistant_message_id,
            thread_id,
            sequence + 1,
            answer.text,
            Jsonb(answer.parts),
        ),
    )
    for part in answer.parts:
        if part["type"] != "data-citation":
            continue
        c = part["data"]
        await run_in_threadpool(
            connection.execute,
            """INSERT INTO public.message_citations
            (id, message_id, chunk_id, citation_index, excerpt, ticker, form, filing_date, page, section)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
            (
                uuid4(),
                assistant_message_id,
                c["chunk_id"],
                c["index"],
                c["excerpt"],
                c["ticker"],
                c["form"],
                c["filing_date"],
                c["page"],
                c["section"],
            ),
        )
    await run_in_threadpool(
        connection.execute,
        "UPDATE public.chat_threads SET updated_at = now() WHERE id = %s",
        (thread_id,),
    )
