"""Live schema proof with a fully rolled-back fixture and no model calls."""

import asyncio
from uuid import uuid4

import psycopg
import pytest
from psycopg.rows import dict_row


@pytest.mark.integration
def test_citations_replay_and_failed_citation_roll_back_pair():
    asyncio.run(check_atomicity())


async def check_atomicity():
    from app.assistant.rendering import AcceptedReply
    from app.config import Settings
    from app.database.chats import completed_turn, save_turn

    connection = psycopg.connect(
        str(Settings().database_url), connect_timeout=10, row_factory=dict_row
    )
    user_id, thread_id = uuid4(), uuid4()
    try:
        row = connection.execute("""SELECT c.id, d.ticker, d.form, d.filing_date
            FROM public.document_chunks c JOIN public.source_documents d ON d.id=c.document_id LIMIT 1""").fetchone()
        assert row is not None
        connection.execute(
            "INSERT INTO auth.users (id, email) VALUES (%s, %s)",
            (user_id, f"{user_id}@example.invalid"),
        )
        connection.execute(
            "INSERT INTO public.users (id, email) VALUES (%s, %s)",
            (user_id, f"{user_id}@example.invalid"),
        )
        connection.execute(
            "INSERT INTO public.chat_threads (id, user_id, title) VALUES (%s, %s, %s)",
            (thread_id, user_id, "Atomic citation fixture"),
        )
        citation = {
            "type": "data-citation",
            "id": "1",
            "data": {
                "chunk_id": str(row["id"]),
                "index": 1,
                "excerpt": "Fixture excerpt",
                "ticker": row["ticker"],
                "form": row["form"],
                "filing_date": str(row["filing_date"]),
                "page": None,
                "section": None,
            },
        }
        reply = AcceptedReply(
            text="Fixture [1]",
            parts=[{"type": "text", "text": "Fixture [1]"}, citation],
        )
        uid, aid = uuid4(), uuid4()
        await save_turn(connection, thread_id, uid, aid, "Q", reply)
        assert await completed_turn(connection, thread_id, uid, aid, "Q") == reply
        assert (
            connection.execute(
                "SELECT count(*) AS n FROM public.message_citations WHERE message_id=%s",
                (aid,),
            ).fetchone()["n"]
            == 1
        )
        connection.execute("SAVEPOINT before_failure")
        bad = reply.model_copy(deep=True)
        bad.parts[1]["data"]["chunk_id"] = str(uuid4())
        failed_uid, failed_aid = uuid4(), uuid4()
        with pytest.raises(psycopg.errors.ForeignKeyViolation):
            await save_turn(
                connection, thread_id, failed_uid, failed_aid, "Bad fixture", bad
            )
        connection.execute("ROLLBACK TO SAVEPOINT before_failure")
        assert (
            await completed_turn(
                connection, thread_id, failed_uid, failed_aid, "Bad fixture"
            )
            is None
        )
        assert (
            connection.execute(
                "SELECT count(*) AS n FROM public.message_citations WHERE message_id=%s",
                (failed_aid,),
            ).fetchone()["n"]
            == 0
        )
    finally:
        connection.rollback()
        connection.close()
