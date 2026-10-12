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
    assert database.calls[0][1] == (USER_ID, 10, 20)
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


def test_stream_saves_pair_and_finishes(thread_client):
    client, database = thread_client
    database.results.extend([{"user_id": USER_ID}, [], {"next": 0}])
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
                },
            ],
        ]
    )
    response = client.post("/chat/stream", json=stream_payload())
    assert response.status_code == 200
    assert "Saved reply" in response.text
    assert not any("INSERT" in query for query, _ in database.calls)


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
