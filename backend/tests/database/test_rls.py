"""Opt-in live database checks; all fixtures are rolled back."""

import json
from uuid import uuid4

import psycopg
import pytest


@pytest.mark.integration
def test_two_database_identities_and_unapproved_user():
    from app.config import Settings

    settings = Settings()
    (
        alice,
        bob,
        outsider,
        alice_thread,
        bob_thread,
        document,
        chunk,
        message,
        citation,
    ) = [uuid4() for _ in range(9)]
    connection = psycopg.connect(str(settings.database_url), connect_timeout=10)
    try:
        for user_id in (alice, bob, outsider):
            connection.execute(
                "INSERT INTO auth.users (id, email) VALUES (%s, %s)",
                (user_id, f"{user_id}@example.invalid"),
            )
        for user_id in (alice, bob):
            connection.execute(
                "INSERT INTO public.users (id, email) VALUES (%s, %s)",
                (user_id, f"{user_id}@example.invalid"),
            )
        for thread_id, user_id in ((alice_thread, alice), (bob_thread, bob)):
            connection.execute(
                "INSERT INTO public.chat_threads (id,user_id,title) VALUES (%s,%s,'RLS test')",
                (thread_id, user_id),
            )
        connection.execute(
            """INSERT INTO public.source_documents
            (id,ticker,cik,form,filing_date,accession_number,primary_document,source_url)
            VALUES (%s,'TEST','0000000000','10-K','2025-01-01',%s,'test.htm','https://example.invalid')""",
            (document, document.hex),
        )
        connection.execute(
            "INSERT INTO public.document_chunks (id,document_id,chunk_index,text) VALUES (%s,%s,0,'Test evidence')",
            (chunk, document),
        )
        connection.execute(
            "INSERT INTO public.chat_messages (id,thread_id,role,sequence,content) VALUES (%s,%s,'ASSISTANT',0,'Test answer')",
            (message, alice_thread),
        )
        connection.execute(
            """INSERT INTO public.message_citations
            (id,message_id,chunk_id,citation_index,excerpt,ticker,form,filing_date)
            VALUES (%s,%s,%s,1,'Test evidence','TEST','10-K','2025-01-01')""",
            (citation, message, chunk),
        )
        connection.execute("SET LOCAL ROLE authenticated")
        for user_id, thread_id in (
            (alice, alice_thread),
            (bob, bob_thread),
            (outsider, None),
        ):
            connection.execute(
                "SELECT set_config('request.jwt.claims', %s, true)",
                (json.dumps({"sub": str(user_id), "role": "authenticated"}),),
            )
            rows = connection.execute(
                "SELECT id FROM public.chat_threads WHERE id = ANY(%s)",
                ([alice_thread, bob_thread],),
            ).fetchall()
            assert rows == ([(thread_id,)] if thread_id else [])
            for table, row_id in (
                ("source_documents", document),
                ("document_chunks", chunk),
            ):
                assert len(
                    connection.execute(
                        f"SELECT id FROM public.{table} WHERE id=%s", (row_id,)
                    ).fetchall()
                ) == (0 if user_id == outsider else 1)
            for table, row_id in (
                ("chat_messages", message),
                ("message_citations", citation),
            ):
                assert len(
                    connection.execute(
                        f"SELECT id FROM public.{table} WHERE id=%s", (row_id,)
                    ).fetchall()
                ) == (1 if user_id == alice else 0)
            if user_id != alice:
                assert (
                    connection.execute(
                        "UPDATE public.chat_threads SET title='Forbidden' WHERE id=%s",
                        (alice_thread,),
                    ).rowcount
                    == 0
                )
                assert (
                    connection.execute(
                        "DELETE FROM public.chat_threads WHERE id=%s", (alice_thread,)
                    ).rowcount
                    == 0
                )
                with pytest.raises(psycopg.errors.InsufficientPrivilege), connection.transaction():
                    connection.execute(
                        "INSERT INTO public.chat_threads (id,user_id,title) VALUES (%s,%s,'Forbidden')",
                        (uuid4(), alice),
                    )
        connection.execute("SET LOCAL ROLE anon")
        with pytest.raises(psycopg.errors.InsufficientPrivilege), connection.transaction():
            connection.execute("SELECT id FROM public.chat_threads")
    finally:
        connection.rollback()
        connection.close()
