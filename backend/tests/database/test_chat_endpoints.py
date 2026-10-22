"""Live SQL/API checks; Auth is overridden and all fixtures are rolled back."""

import asyncio
from unittest.mock import Mock
from uuid import uuid4

import httpx
import psycopg
import pytest
from psycopg.rows import dict_row


@pytest.mark.integration
def test_chat_endpoints_isolate_users_and_order_history(monkeypatch):
    asyncio.run(check_endpoints(monkeypatch))


async def check_endpoints(monkeypatch):
    from types import SimpleNamespace

    from app.assistant.rendering import AcceptedReply
    from app.chat import streaming

    async def generate(*_args):
        return SimpleNamespace(
            reply=AcceptedReply(
                text="Verified fixture",
                parts=[{"type": "text", "text": "Verified fixture"}],
            )
        )

    monkeypatch.setattr(streaming, "generate_reply", generate)
    from app.auth.dependencies import CurrentUser, get_current_user
    from app.config import Settings
    from app.database.connection import get_connection
    from app.main import app

    connection = psycopg.connect(
        str(Settings().database_url), connect_timeout=10, row_factory=dict_row
    )
    alice, bob = uuid4(), uuid4()
    current_id = alice
    database_fixture = Mock(wraps=connection)
    # Exercise stream persistence inside the fixture transaction without committing it.
    database_fixture.commit.return_value = None

    async def user():
        return CurrentUser(id=current_id, email=f"{current_id}@example.invalid")

    async def database():
        yield database_fixture

    app.dependency_overrides[get_current_user] = user
    app.dependency_overrides[get_connection] = database
    try:
        for user_id in (alice, bob):
            connection.execute(
                "INSERT INTO auth.users (id, email) VALUES (%s, %s)",
                (user_id, f"{user_id}@example.invalid"),
            )
            connection.execute(
                "INSERT INTO public.users (id, email) VALUES (%s, %s)",
                (user_id, f"{user_id}@example.invalid"),
            )
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post("/chat/threads", json={"title": "Alice chat"})
            assert response.status_code == 201
            alice_thread = response.json()["id"]
            response = await client.post(
                "/chat/threads", json={"id": alice_thread, "title": "Alice chat"}
            )
            assert response.status_code == 201
            assert response.json()["id"] == alice_thread
            assert (
                connection.execute(
                    "SELECT COUNT(*) AS count FROM public.chat_threads WHERE id = %s",
                    (alice_thread,),
                ).fetchone()["count"]
                == 1
            )
            current_id = bob
            assert (
                await client.post(
                    "/chat/threads", json={"id": alice_thread, "title": "Alice chat"}
                )
            ).status_code == 403
            response = await client.post("/chat/threads", json={})
            assert response.status_code == 201
            bob_thread = response.json()["id"]
            cursor = connection.execute(
                "SELECT user_id FROM public.chat_threads WHERE id = %s", (bob_thread,)
            )
            assert cursor.fetchone()["user_id"] == bob
            for sequence, role in ((1, "ASSISTANT"), (0, "USER")):
                connection.execute(
                    """INSERT INTO public.chat_messages
                    (id, thread_id, role, sequence, content)
                    VALUES (%s, %s, %s, %s, %s)""",
                    (uuid4(), alice_thread, role, sequence, f"Message {sequence}"),
                )
            for user_id, own_thread, other_thread in (
                (alice, alice_thread, bob_thread),
                (bob, bob_thread, alice_thread),
            ):
                current_id = user_id
                response = await client.get("/chat/threads")
                assert response.status_code == 200
                assert [item["id"] for item in response.json()] == [own_thread]
                response = await client.get(f"/chat/threads/{other_thread}/messages")
                assert response.status_code == 403
                response = await client.get(f"/chat/threads/{own_thread}/messages")
                assert response.status_code == 200
                assert [item["sequence"] for item in response.json()] == (
                    [0, 1] if user_id == alice else []
                )
            current_id = alice
            response = await client.get(
                f"/chat/threads/{alice_thread}/messages?limit=1&offset=1"
            )
            assert [item["sequence"] for item in response.json()] == [1]
            assert (
                await client.get(f"/chat/threads/{uuid4()}/messages")
            ).status_code == 404
            payload = {
                "threadId": alice_thread,
                "messages": [
                    {
                        "id": "live-stream-question",
                        "role": "user",
                        "parts": [{"type": "text", "text": "Show the streaming stub"}],
                    }
                ],
            }
            for _ in range(2):
                response = await client.post("/chat/stream", json=payload)
                assert response.status_code == 200
                assert '"type": "finish"' in response.text
                history = (
                    await client.get(f"/chat/threads/{alice_thread}/messages")
                ).json()
                assert [item["sequence"] for item in history] == [0, 1, 2, 3]
                assert history[-2]["content"] == "Show the streaming stub"
                assert history[-1]["role"] == "ASSISTANT"
            payload["messages"][0]["parts"][0]["text"] = (
                "Different question with reused ID"
            )
            assert (await client.post("/chat/stream", json=payload)).status_code == 409
            current_id = bob
            assert (await client.post("/chat/stream", json=payload)).status_code == 403
            # Deletion: owner only, and the cascade removes messages and their
            # citations while the cited filing chunk stays.
            assert (
                await client.delete(f"/chat/threads/{alice_thread}")
            ).status_code == 403
            chunk = connection.execute(
                "SELECT id FROM public.document_chunks LIMIT 1"
            ).fetchone()["id"]
            answer_id = history[-1]["id"]
            connection.execute(
                """INSERT INTO public.message_citations
                (id, message_id, chunk_id, citation_index, excerpt, ticker, form, filing_date)
                VALUES (%s, %s, %s, 1, 'Fixture excerpt', 'AAPL', '10-K', '2025-10-31')""",
                (uuid4(), answer_id, chunk),
            )
            current_id = alice
            response = await client.delete(f"/chat/threads/{alice_thread}")
            assert response.status_code == 204
            for table, column, value in (
                ("chat_threads", "id", alice_thread),
                ("chat_messages", "thread_id", alice_thread),
                ("message_citations", "message_id", answer_id),
            ):
                assert (
                    connection.execute(
                        f"SELECT COUNT(*) AS count FROM public.{table} WHERE {column} = %s",
                        (value,),
                    ).fetchone()["count"]
                    == 0
                )
            assert connection.execute(
                "SELECT 1 FROM public.document_chunks WHERE id = %s", (chunk,)
            ).fetchone()
            assert (
                await client.get(f"/chat/threads/{alice_thread}/messages")
            ).status_code == 404
            assert [t["id"] for t in (await client.get("/chat/threads")).json()] == []
            assert (
                await client.delete(f"/chat/threads/{alice_thread}")
            ).status_code == 404
    finally:
        app.dependency_overrides.clear()
        connection.rollback()
        connection.close()
