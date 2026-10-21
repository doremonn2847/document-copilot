import asyncio
import json
from uuid import uuid4

import psycopg
import pytest

from app.chat.messages import ChatRequest


@pytest.fixture
def streaming_module(monkeypatch):
    for key, value in {
        "SUPABASE_URL": "https://example.supabase.co",
        "SUPABASE_ANON_KEY": "test-anon",
        "SUPABASE_SERVICE_ROLE_KEY": "test-service-secret",
        "DATABASE_URL": "postgresql://postgres:test-password@localhost:5432/postgres",
        "OPENAI_API_KEY": "test-openai-secret",
        "ALLOWED_ORIGINS": "http://localhost:5173, http://localhost:4173/",
    }.items():
        monkeypatch.setenv(key, value)
    from types import SimpleNamespace

    from app.assistant.rendering import AcceptedReply
    from app.chat import streaming

    async def no_delay(_seconds):
        pass

    monkeypatch.setattr(streaming.asyncio, "sleep", no_delay)

    async def history(*_args, **_kwargs):
        return []

    async def generate(*_args):
        return SimpleNamespace(
            reply=AcceptedReply(
                text="Verified reply",
                parts=[{"type": "text", "text": "Verified reply"}],
            )
        )

    monkeypatch.setattr(streaming.chats, "recent_history", history)
    monkeypatch.setattr(streaming, "generate_reply", generate)
    return streaming


class Request:
    def __init__(self, disconnect_after=100):
        self.checks = 0
        self.disconnect_after = disconnect_after

    async def is_disconnected(self):
        self.checks += 1
        return self.checks > self.disconnect_after


class Connection:
    def __init__(self, fail_commit=False):
        self.calls = []
        self.fail_commit = fail_commit

    def commit(self):
        self.calls.append("commit")
        if self.fail_commit:
            raise psycopg.OperationalError("synthetic-secret")

    def rollback(self):
        self.calls.append("rollback")


def chunks(events):
    return [json.loads(item[6:]) for item in events if "[DONE]" not in item]


def test_success_commits_before_finish(streaming_module, monkeypatch):
    connection = Connection()

    async def save(*_args):
        connection.calls.append("save")

    monkeypatch.setattr(streaming_module.chats, "save_turn", save)

    async def consume():
        events = []
        async for item in streaming_module.stream_turn(
            Request(),
            connection,
            uuid4(),
            uuid4(),
            uuid4(),
            "Revenue?",
            None,
            user_id=uuid4(),
        ):
            if '"type": "finish"' in item:
                assert connection.calls == ["save", "commit"]
            events.append(item)
        return events

    events = asyncio.run(consume())
    assert chunks(events)[-1] == {"type": "finish", "finishReason": "stop"}
    assert events[-1] == "data: [DONE]\n\n"
    assert connection.calls == ["save", "commit"]


@pytest.mark.parametrize("mode", ["disconnect", "cancel", "save-fails", "commit-fails"])
def test_interrupted_turn_never_finishes(streaming_module, monkeypatch, mode):
    connection = Connection(fail_commit=mode == "commit-fails")

    async def save(*_args):
        connection.calls.append("save")
        if mode == "save-fails":
            raise psycopg.OperationalError("synthetic-secret")

    monkeypatch.setattr(streaming_module.chats, "save_turn", save)

    async def consume():
        request = Request(disconnect_after=1 if mode == "disconnect" else 100)
        iterator = streaming_module.stream_turn(
            request,
            connection,
            uuid4(),
            uuid4(),
            uuid4(),
            "Revenue?",
            None,
            user_id=uuid4(),
        )
        events = []
        if mode == "cancel":
            events.append(await anext(iterator))
            await iterator.aclose()
        else:
            events = [item async for item in iterator]
        return events

    events = asyncio.run(consume())
    assert not any(item.get("type") == "finish" for item in chunks(events))
    assert connection.calls[-1] == "rollback"
    if mode in ("cancel", "disconnect"):
        assert "save" not in connection.calls
    else:
        assert any(item["type"] == "error" for item in chunks(events))
    assert "synthetic-secret" not in "".join(events)


def test_retry_replays_without_saving(streaming_module, monkeypatch):
    from app.assistant.rendering import AcceptedReply

    async def unexpected_save(*_args):
        pytest.fail("Completed retries must not create messages")

    monkeypatch.setattr(streaming_module.chats, "save_turn", unexpected_save)
    connection = Connection()

    async def consume():
        return [
            item
            async for item in streaming_module.stream_turn(
                Request(),
                connection,
                uuid4(),
                uuid4(),
                uuid4(),
                "Question",
                AcceptedReply(text="Saved reply", parts=[]),
                user_id=uuid4(),
            )
        ]

    events = chunks(asyncio.run(consume()))
    assert (
        "".join(item["delta"] for item in events if item["type"] == "text-delta")
        == "Saved reply"
    )
    assert connection.calls == ["commit"]


@pytest.mark.parametrize(
    "change",
    [
        {"user_id": "spoofed"},
        {"messages": []},
        {"trigger": "regenerate-message"},
        {
            "messages": [
                {
                    "id": "u1",
                    "role": "assistant",
                    "parts": [{"type": "text", "text": "x"}],
                }
            ]
        },
        {
            "messages": [
                {"id": "u1", "role": "user", "parts": [{"type": "text", "text": " "}]}
            ]
        },
        {
            "messages": [
                {"id": "u1", "role": "user", "parts": [{"type": "file", "url": "x"}]}
            ]
        },
        {"messageId": "another-message"},
    ],
)
def test_payload_boundary(change):
    from pydantic import ValidationError

    payload = {
        "threadId": str(uuid4()),
        "messages": [
            {
                "id": "u1",
                "role": "user",
                "parts": [{"type": "text", "text": "Revenue?"}],
            }
        ],
        **change,
    }
    with pytest.raises(ValidationError):
        ChatRequest.model_validate(payload)


def test_sdk_assistant_step_parts_are_accepted_in_history():
    payload = ChatRequest.model_validate(
        {
            "threadId": str(uuid4()),
            "messages": [
                {
                    "id": "a1",
                    "role": "assistant",
                    "parts": [
                        {"type": "step-start"},
                        {"type": "text", "text": "Prior reply", "state": "done"},
                    ],
                },
                {
                    "id": "u2",
                    "role": "user",
                    "parts": [{"type": "text", "text": "Follow-up?"}],
                },
            ],
        }
    )
    assert payload.question == "Follow-up?"
