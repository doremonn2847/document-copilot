from uuid import UUID, uuid4

import psycopg
from fastapi import HTTPException
from psycopg.types.json import Jsonb
from starlette.concurrency import run_in_threadpool


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
) -> str | None:
    cursor = await run_in_threadpool(
        connection.execute,
        """SELECT id, content FROM public.chat_messages
        WHERE thread_id = %s AND id = ANY(%s)""",
        (thread_id, [user_message_id, assistant_message_id]),
    )
    messages = {row["id"]: row["content"] for row in cursor.fetchall()}
    if not messages:
        return None
    if len(messages) != 2 or messages.get(user_message_id) != question:
        raise HTTPException(409, "This message ID was already used for another turn")
    return messages[assistant_message_id]


async def save_turn(
    connection: psycopg.Connection,
    thread_id: UUID,
    user_message_id: UUID,
    assistant_message_id: UUID,
    question: str,
    answer: str,
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
            answer,
            Jsonb([{"type": "text", "text": answer}]),
        ),
    )
    await run_in_threadpool(
        connection.execute,
        "UPDATE public.chat_threads SET updated_at = now() WHERE id = %s",
        (thread_id,),
    )
