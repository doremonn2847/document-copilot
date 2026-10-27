from collections import deque
from datetime import UTC, datetime
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

USER_ID = UUID("00000000-0000-0000-0000-000000000001")
THREAD_ID = UUID("00000000-0000-0000-0000-000000000010")
NOW = datetime.now(UTC)
THREAD = {"id": THREAD_ID, "title": "New chat", "created_at": NOW, "updated_at": NOW}


class FakeConnection:
    def __init__(self):
        self.results = deque()
        self.calls = []
        self.commits = 0
        self.rollbacks = 0

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1

    def execute(self, query, params=None):
        self.calls.append((query, params))
        return self

    def fetchone(self):
        return self.results.popleft()

    def fetchall(self):
        return self.results.popleft()


@pytest.fixture
def thread_client(monkeypatch):
    for name, value in {
        "SUPABASE_URL": "https://example.supabase.co",
        "SUPABASE_ANON_KEY": "test-anon",
        "SUPABASE_SERVICE_ROLE_KEY": "test-service-secret",
        "DATABASE_URL": "postgresql://postgres:test-password@localhost:5432/postgres",
        "OPENAI_API_KEY": "test-openai-secret",
        "ALLOWED_ORIGINS": "http://localhost:5173, http://localhost:4173/",
    }.items():
        monkeypatch.setenv(name, value)
    from app.auth.dependencies import CurrentUser, get_current_user
    from app.database.connection import get_connection
    from app.main import app

    connection = FakeConnection()

    async def user():
        return CurrentUser(id=USER_ID, email="analyst@example.test")

    async def database():
        yield connection

    app.dependency_overrides[get_current_user] = user
    app.dependency_overrides[get_connection] = database
    try:
        yield TestClient(app), connection
    finally:
        app.dependency_overrides.clear()


def test_create_uses_verified_owner(thread_client):
    client, database = thread_client
    database.results.append(THREAD)
    response = client.post("/chat/threads", json={"title": "  Revenue  "})
    assert response.status_code == 201
    assert database.calls[0][1][1:] == (USER_ID, "Revenue")
    assert response.json()["id"] == str(THREAD_ID)


def test_creation_accepts_stable_id(thread_client):
    client, database = thread_client
    database.results.append(THREAD)
    response = client.post("/chat/threads", json={"id": str(THREAD_ID)})
    assert response.status_code == 201
    assert database.calls[0][1][0] == THREAD_ID


@pytest.mark.parametrize(
    "owner,title,status",
    [
        (USER_ID, "New chat", 201),
        (UUID(int=2), "New chat", 403),
        (USER_ID, "Changed", 409),
    ],
)
def test_creation_retry_checks_owner_and_title(thread_client, owner, title, status):
    client, database = thread_client
    database.results.extend([None, {**THREAD, "user_id": owner, "title": title}])
    response = client.post("/chat/threads", json={"id": str(THREAD_ID)})
    assert response.status_code == status
    assert "ON CONFLICT" in database.calls[0][0]


@pytest.mark.parametrize(
    "payload", [{"user_id": str(USER_ID)}, {"title": " "}, {"title": "a" * 256}]
)
def test_invalid_creation_is_rejected(thread_client, payload):
    client, database = thread_client
    assert client.post("/chat/threads", json=payload).status_code == 422
    assert database.calls == []


def test_list_applies_owner_and_pagination(thread_client):
    client, database = thread_client
    database.results.append([THREAD])
    response = client.get("/chat/threads?limit=10&offset=20")
    assert response.status_code == 200
    assert database.calls[0][1] == (USER_ID, None, None, 10, 20)
    assert len(response.json()) == 1


@pytest.mark.parametrize("owner,status", [(None, 404), (UUID(int=2), 403)])
def test_history_denied_before_reading_messages(thread_client, owner, status):
    client, database = thread_client
    database.results.append(None if owner is None else {"user_id": owner})
    response = client.get(f"/chat/threads/{THREAD_ID}/messages")
    assert response.status_code == status
    assert len(database.calls) == 1


def test_empty_history(thread_client):
    client, database = thread_client
    database.results.extend([{"user_id": USER_ID}, []])
    response = client.get(f"/chat/threads/{THREAD_ID}/messages")
    assert response.status_code == 200
    assert response.json() == []
    assert database.calls[1][1][:2] == (THREAD_ID, USER_ID)


@pytest.mark.parametrize(
    "path",
    [
        "/chat/threads?limit=201",
        "/chat/threads?offset=-1",
        "/chat/threads/invalid/messages",
    ],
)
def test_invalid_query_and_id(thread_client, path):
    client, database = thread_client
    assert client.get(path).status_code == 422
    assert database.calls == []


def test_missing_token_does_not_query_database(thread_client):
    from app.auth.dependencies import get_current_user
    from app.main import app

    client, database = thread_client
    app.dependency_overrides.pop(get_current_user)
    assert client.get("/chat/threads").status_code == 401
    assert database.calls == []


@pytest.mark.parametrize("commit_fails", [False, True])
def test_transaction_finishes_before_success(thread_client, monkeypatch, commit_fails):
    import psycopg

    from app.database.connection import get_connection
    from app.main import app

    client, database = thread_client
    app.dependency_overrides.pop(get_connection)
    database.results.append(THREAD)
    finished = []

    def commit():
        finished.append("commit")
        if commit_fails:
            raise psycopg.OperationalError("synthetic-private-connection-details")

    monkeypatch.setattr(psycopg, "connect", lambda *args, **kwargs: database)
    monkeypatch.setattr(database, "commit", commit, raising=False)
    monkeypatch.setattr(
        database, "close", lambda: finished.append("close"), raising=False
    )
    response = client.post("/chat/threads", json={})
    assert response.status_code == (503 if commit_fails else 201)
    assert finished == ["commit", "close"]
    assert "synthetic-private-connection-details" not in response.text


def stream_payload():
    return {
        "threadId": str(THREAD_ID),
        "messages": [
            {
                "id": "question-1",
                "role": "user",
                "parts": [{"type": "text", "text": "Revenue?"}],
            }
        ],
    }


def test_stream_saves_pair_and_finishes(thread_client, monkeypatch):
    from types import SimpleNamespace

    from app.assistant.rendering import AcceptedReply
    from app.chat import streaming

    async def generate(*_args):
        return SimpleNamespace(
            reply=AcceptedReply(
                text="Verified reply",
                parts=[{"type": "text", "text": "Verified reply"}],
            )
        )

    monkeypatch.setattr(streaming, "generate_reply", generate)
    client, database = thread_client
    database.results.extend([{"user_id": USER_ID}, [], [], {"next": 0}])
    response = client.post("/chat/stream", json=stream_payload())
    assert response.status_code == 200
    assert response.headers["x-vercel-ai-ui-message-stream"] == "v1"
    assert '"type": "finish"' in response.text
    assert response.text.endswith("data: [DONE]\n\n")
    assert database.commits == 1
    assert database.rollbacks == 0
    inserts = [
        params
        for query, params in database.calls
        if "INSERT INTO public.chat_messages" in query
    ]
    assert len(inserts) == 1
    assert inserts[0][3] == "Revenue?"
    assert inserts[0][2] == 0 and inserts[0][7] == 1


@pytest.mark.parametrize("owner,status", [(None, 404), (UUID(int=2), 403)])
def test_stream_checks_owner_before_sse(thread_client, owner, status):
    client, database = thread_client
    database.results.append(None if owner is None else {"user_id": owner})
    response = client.post("/chat/stream", json=stream_payload())
    assert response.status_code == status
    assert "text-delta" not in response.text
    assert len(database.calls) == 1


def test_completed_stream_retry_does_not_duplicate(thread_client):
    from uuid import uuid5

    client, database = thread_client
    database.results.extend(
        [
            {"user_id": USER_ID},
            [
                {"id": uuid5(THREAD_ID, "user:question-1"), "content": "Revenue?"},
                {
                    "id": uuid5(THREAD_ID, "assistant:question-1"),
                    "content": "Saved reply",
                    "parts": [{"type": "text", "text": "Saved reply"}],
                },
            ],
        ]
    )
    response = client.post("/chat/stream", json=stream_payload())
    assert response.status_code == 200
    assert "Saved reply" in response.text
    assert not any("INSERT" in query for query, _ in database.calls)


def demo_user_override():
    from app.auth.dependencies import CurrentUser

    return CurrentUser(id=USER_ID, email=None, is_demo=True)


def test_demo_denial_is_before_sse_and_after_ownership(thread_client, monkeypatch):
    from app.auth.dependencies import get_current_user
    from app.demo.errors import DemoUnavailable
    from app.demo.store import DemoStore
    from app.main import app

    async def deny(*args):
        raise DemoUnavailable("visitor_limit")

    app.dependency_overrides[get_current_user] = demo_user_override
    monkeypatch.setattr(DemoStore, "begin", deny)
    client, database = thread_client
    database.results.extend([{"user_id": USER_ID}, []])
    response = client.post("/chat/stream", json=stream_payload())
    assert response.status_code == 429
    assert response.json()["detail"] == {
        "code": "demo_limit",
        "reason": "visitor_limit",
    }
    assert "text-delta" not in response.text


def test_demo_completed_replay_bypasses_disabled_admission(thread_client, monkeypatch):
    from uuid import uuid5

    from app.auth.dependencies import get_current_user
    from app.demo.store import DemoStore
    from app.main import app

    async def must_not_begin(*args):
        raise AssertionError("Replaying is free")

    app.dependency_overrides[get_current_user] = demo_user_override
    monkeypatch.setattr(DemoStore, "begin", must_not_begin)
    client, database = thread_client
    database.results.extend(
        [
            {"user_id": USER_ID},
            [
                {"id": uuid5(THREAD_ID, "user:question-1"), "content": "Revenue?"},
                {
                    "id": uuid5(THREAD_ID, "assistant:question-1"),
                    "content": "Saved reply",
                    "parts": [],
                },
            ],
        ]
    )
    response = client.post("/chat/stream", json=stream_payload())
    assert response.status_code == 200 and "Saved reply" in response.text
    assert not any("INSERT" in sql for sql, _ in database.calls)


def test_stream_lock_conflict(thread_client, monkeypatch):
    import psycopg

    client, database = thread_client

    def locked(*_args):
        raise psycopg.errors.LockNotAvailable("synthetic-lock-details")

    monkeypatch.setattr(database, "execute", locked)
    response = client.post("/chat/stream", json=stream_payload())
    assert response.status_code == 409
    assert "synthetic-lock-details" not in response.text


def test_stream_requires_token(thread_client):
    from app.auth.dependencies import get_current_user
    from app.main import app

    client, database = thread_client
    app.dependency_overrides.pop(get_current_user)
    assert client.post("/chat/stream", json=stream_payload()).status_code == 401
    assert database.calls == []


def test_new_answers_are_rate_limited_but_replays_are_not(thread_client, monkeypatch):
    from types import SimpleNamespace

    from app.api import chat
    from app.assistant.rendering import AcceptedReply
    from app.chat import streaming
    from app.chat.limits import TurnLimiter

    async def generate(*_args):
        return SimpleNamespace(
            reply=AcceptedReply(
                text="Verified reply",
                parts=[{"type": "text", "text": "Verified reply"}],
            )
        )

    monkeypatch.setattr(streaming, "generate_reply", generate)
    monkeypatch.setattr(chat, "limiter", TurnLimiter())
    monkeypatch.setattr(chat.settings, "assistant_user_turns_per_hour", 1)
    client, database = thread_client
    database.results.extend([{"user_id": USER_ID}, [], [], {"next": 0}])
    assert client.post("/chat/stream", json=stream_payload()).status_code == 200
    # The finished answer released its concurrency slot.
    assert chat.limiter.active == {}
    database.results.extend([{"user_id": USER_ID}, []])
    limited = client.post("/chat/stream", json=stream_payload())
    assert limited.status_code == 429 and "Retry-After" in limited.headers


def test_delete_removes_own_thread_after_locking_it(thread_client):
    client, database = thread_client
    database.results.append({"user_id": USER_ID})
    response = client.delete(f"/chat/threads/{THREAD_ID}")
    assert response.status_code == 204 and response.content == b""
    lock, delete = database.calls
    assert "FOR UPDATE NOWAIT" in lock[0]
    assert delete[0].startswith("DELETE FROM public.chat_threads")
    assert delete[1] == (THREAD_ID, USER_ID)


@pytest.mark.parametrize(
    "owner,status",
    [(UUID("00000000-0000-0000-0000-000000000002"), 403), (None, 404)],
)
def test_delete_refuses_other_users_and_missing_threads(thread_client, owner, status):
    client, database = thread_client
    database.results.append(None if owner is None else {"user_id": owner})
    response = client.delete(f"/chat/threads/{THREAD_ID}")
    assert response.status_code == status
    # Only the ownership check ran; nothing was deleted.
    assert len(database.calls) == 1


def test_delete_waits_for_a_reply_in_progress(thread_client, monkeypatch):
    import psycopg

    client, database = thread_client

    def locked(*_args):
        raise psycopg.errors.LockNotAvailable("synthetic-lock-details")

    monkeypatch.setattr(database, "execute", locked)
    response = client.delete(f"/chat/threads/{THREAD_ID}")
    assert response.status_code == 409


def test_delete_requires_token(thread_client):
    from app.auth.dependencies import get_current_user
    from app.main import app

    client, database = thread_client
    app.dependency_overrides.pop(get_current_user)
    assert client.delete(f"/chat/threads/{THREAD_ID}").status_code == 401
    assert database.calls == []


def test_first_turn_saves_a_generated_title_with_the_answer(thread_client, monkeypatch):
    from types import SimpleNamespace

    from app.assistant.rendering import AcceptedReply
    from app.chat import streaming

    async def generate(*_args):
        return SimpleNamespace(
            reply=AcceptedReply(
                text="Verified", parts=[{"type": "text", "text": "Verified"}]
            )
        )

    async def title(question):
        assert question == "Revenue?"
        return "Revenue question"

    monkeypatch.setattr(streaming, "generate_reply", generate)
    monkeypatch.setattr(streaming, "summarize_title", title)
    client, database = thread_client
    database.results.extend([{"user_id": USER_ID}, [], [], {"next": 0}])
    assert client.post("/chat/stream", json=stream_payload()).status_code == 200
    updates = [
        p
        for q, p in database.calls
        if q.lstrip().startswith("UPDATE public.chat_threads SET title")
    ]
    # Only the default title (the first question or "New chat") is replaced.
    assert updates == [("Revenue question", THREAD_ID, "Revenue?")]


def test_later_turns_keep_the_title(thread_client, monkeypatch):
    from types import SimpleNamespace

    from app.assistant.rendering import AcceptedReply
    from app.chat import streaming

    async def generate(*_args):
        return SimpleNamespace(
            reply=AcceptedReply(
                text="Verified", parts=[{"type": "text", "text": "Verified"}]
            )
        )

    async def title(_question):
        raise AssertionError("a later turn must not be retitled")

    monkeypatch.setattr(streaming, "generate_reply", generate)
    monkeypatch.setattr(streaming, "summarize_title", title)
    client, database = thread_client
    earlier = [
        {"role": "USER", "content": "Revenue?", "sequence": 0},
        {"role": "ASSISTANT", "content": "Verified", "sequence": 1},
    ]
    database.results.extend(
        [{"user_id": USER_ID}, [], list(reversed(earlier)), {"next": 2}]
    )
    response = client.post("/chat/stream", json=stream_payload())
    assert response.status_code == 200 and '"type": "finish"' in response.text
    assert not [q for q, _ in database.calls if "SET title" in q]


MESSAGE_ID = UUID("00000000-0000-0000-0000-000000000020")
REPLY = {"user_id": USER_ID, "role": "ASSISTANT"}


def test_feedback_is_saved_for_own_reply(thread_client):
    client, database = thread_client
    saved = {"rating": "down", "reason": "wrong_citation", "comment": "Page 26"}
    database.results.extend([REPLY, saved])
    response = client.put(
        f"/chat/messages/{MESSAGE_ID}/feedback",
        json={"rating": "down", "reason": "wrong_citation", "comment": " Page 26 "},
    )
    assert response.status_code == 200
    assert response.json() == saved
    assert database.calls[0][1] == (MESSAGE_ID,)
    assert "ON CONFLICT (message_id, user_id)" in database.calls[1][0]
    assert database.calls[1][1][1:] == (
        MESSAGE_ID,
        USER_ID,
        "down",
        "wrong_citation",
        "Page 26",
    )


@pytest.mark.parametrize(
    "found,status",
    [
        (None, 404),
        ({"user_id": UUID(int=2), "role": "ASSISTANT"}, 403),
        ({"user_id": USER_ID, "role": "USER"}, 422),
    ],
)
def test_feedback_only_on_own_assistant_replies(thread_client, found, status):
    client, database = thread_client
    database.results.append(found)
    response = client.put(
        f"/chat/messages/{MESSAGE_ID}/feedback", json={"rating": "up"}
    )
    assert response.status_code == status
    assert len(database.calls) == 1


@pytest.mark.parametrize(
    "payload",
    [
        {"rating": "meh"},
        {"rating": "up", "reason": "wrong_fact"},
        {"rating": "down", "reason": "rude"},
        {"rating": "down", "comment": "x" * 501},
        {"rating": "up", "user_id": str(USER_ID)},
    ],
)
def test_invalid_feedback_is_rejected_before_the_database(thread_client, payload):
    client, database = thread_client
    response = client.put(f"/chat/messages/{MESSAGE_ID}/feedback", json=payload)
    assert response.status_code == 422
    assert database.calls == []


def test_blank_comment_is_stored_as_none(thread_client):
    client, database = thread_client
    database.results.extend([REPLY, {"rating": "up", "reason": None, "comment": None}])
    response = client.put(
        f"/chat/messages/{MESSAGE_ID}/feedback", json={"rating": "up", "comment": "  "}
    )
    assert response.status_code == 200
    assert database.calls[1][1][-1] is None


def test_feedback_can_be_cleared(thread_client):
    client, database = thread_client
    database.results.append(REPLY)
    response = client.delete(f"/chat/messages/{MESSAGE_ID}/feedback")
    assert response.status_code == 204
    assert database.calls[1][1] == (MESSAGE_ID, USER_ID)


def test_feedback_requires_token(thread_client):
    client, database = thread_client
    from app.auth.dependencies import get_current_user
    from app.main import app

    del app.dependency_overrides[get_current_user]
    response = client.put(
        f"/chat/messages/{MESSAGE_ID}/feedback", json={"rating": "up"}
    )
    assert response.status_code == 401
    assert database.calls == []


def test_history_returns_the_users_feedback(thread_client):
    client, database = thread_client
    message = {
        "id": MESSAGE_ID,
        "thread_id": THREAD_ID,
        "role": "ASSISTANT",
        "content": "Answer",
        "parts": None,
        "sequence": 2,
        "created_at": NOW,
        "feedback": {"rating": "up", "reason": None, "comment": None},
    }
    database.results.extend([{"user_id": USER_ID}, [message]])
    response = client.get(f"/chat/threads/{THREAD_ID}/messages")
    assert response.json()[0]["feedback"] == message["feedback"]
    assert "f.user_id = t.user_id" in database.calls[1][0]


def test_rename_checks_owner_then_updates_title(thread_client):
    client, database = thread_client
    database.results.extend([{"user_id": USER_ID}, {**THREAD, "title": "AWS margins"}])
    response = client.patch(
        f"/chat/threads/{THREAD_ID}", json={"title": " AWS margins "}
    )
    assert response.status_code == 200
    assert response.json()["title"] == "AWS margins"
    assert database.calls[1][1] == ("AWS margins", THREAD_ID, USER_ID)


@pytest.mark.parametrize("owner,status", [(None, 404), (UUID(int=2), 403)])
def test_rename_refuses_other_users_and_missing_threads(thread_client, owner, status):
    client, database = thread_client
    database.results.append(None if owner is None else {"user_id": owner})
    response = client.patch(f"/chat/threads/{THREAD_ID}", json={"title": "Mine"})
    assert response.status_code == status
    assert len(database.calls) == 1


@pytest.mark.parametrize(
    "payload", [{"title": "  "}, {"title": "a" * 256}, {"title": "x", "user_id": "y"}]
)
def test_invalid_rename_is_rejected(thread_client, payload):
    client, database = thread_client
    assert client.patch(f"/chat/threads/{THREAD_ID}", json=payload).status_code == 422
    assert database.calls == []


@pytest.mark.parametrize(
    "query,pattern",
    [("", None), ("  ", None), (" AWS ", "%AWS%"), ("50%_x", r"%50\%\_x%")],
)
def test_search_matches_titles_literally(thread_client, query, pattern):
    client, database = thread_client
    database.results.append([THREAD])
    response = client.get("/chat/threads", params={"q": query})
    assert response.status_code == 200
    assert database.calls[0][1] == (USER_ID, pattern, pattern, 50, 0)


def test_search_text_is_bounded(thread_client):
    client, database = thread_client
    assert client.get("/chat/threads", params={"q": "a" * 101}).status_code == 422
    assert database.calls == []
