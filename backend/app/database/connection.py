from collections.abc import AsyncIterator

import psycopg
from anyio import CancelScope
from fastapi import HTTPException
from psycopg.rows import dict_row
from starlette.concurrency import run_in_threadpool

from app.config import settings


async def get_connection() -> AsyncIterator[psycopg.Connection]:
    connection = None
    try:
        # Offload blocking I/O; psycopg async rejects Windows' default event loop.
        connection = await run_in_threadpool(
            psycopg.connect,
            str(settings.database_url),
            connect_timeout=10,
            row_factory=dict_row,
            # Supabase's transaction-mode pooler (port 6543) cannot keep
            # server-side prepared statements; harmless in session mode.
            prepare_threshold=None,
        )
        await run_in_threadpool(
            connection.execute, "SET LOCAL statement_timeout = '10s'"
        )
        yield connection
        await run_in_threadpool(connection.commit)
    except psycopg.Error as error:
        raise HTTPException(503, "Database service unavailable") from error
    finally:
        if connection is not None:
            with CancelScope(shield=True):
                await run_in_threadpool(connection.close)
