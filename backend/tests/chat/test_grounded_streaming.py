import asyncio
import json
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.assistant.rendering import AcceptedReply
from app.chat import streaming
from app.chat.orchestrator import AssistantFailure, GroundingRejected


class Request:
    disconnected = False

    async def is_disconnected(self):
        return self.disconnected


class Connection:
    def __init__(self):
        self.calls = []

    def commit(self):
        self.calls.append("commit")

    def rollback(self):
        self.calls.append("rollback")


@pytest.fixture
def setup(monkeypatch):
    async def history(*args, **kwargs):
        return [
            {"role": "user", "content": "Trusted server history"},
            {"role": "assistant", "content": "Prior answer"},
        ]

    async def save(*args):
        args[0].calls.append("save")

    monkeypatch.setattr(streaming.chats, "recent_history", history)
    monkeypatch.setattr(streaming.chats, "save_turn", save)


def events(raw):
    return [json.loads(s[6:]) for s in raw if "[DONE]" not in s]


def test_progress_precedes_validated_text_and_citations_replay_without_paid_work(
    setup, monkeypatch
):
    cid = str(uuid4())
    reply = AcceptedReply(
        text="Supported [1]",
        parts=[
            {"type": "text", "text": "Supported [1]"},
            {"type": "data-citation", "id": "1", "data": {"chunk_id": cid}},
        ],
    )
    calls = []

    async def generate(question, history, user_id, thread_id, progress):
        assert history[0]["content"] == "Trusted server history"
        calls.append("generation")
        await progress("verifying")
        await asyncio.sleep(0.01)
        return SimpleNamespace(reply=reply)

    monkeypatch.setattr(streaming, "generate_reply", generate)

    async def consume():
        for existing in (None, reply):
            c = Connection()
            out = events(
                [
                    s
                    async for s in streaming.stream_turn(
                        Request(),
                        c,
                        uuid4(),
                        uuid4(),
                        uuid4(),
                        "Question",
                        existing,
                        user_id=uuid4(),
                    )
                ]
            )
            assert [e for e in out if e["type"] == "data-citation"] == reply.parts[1:]
            if existing is None:
                assert next(
                    i for i, e in enumerate(out) if e["type"] == "data-status"
                ) < next(i for i, e in enumerate(out) if e["type"] == "text-delta")
            assert c.calls == (["save", "commit"] if existing is None else ["commit"])
        assert calls == ["generation"]

    asyncio.run(consume())


@pytest.mark.parametrize(
    "failure",
    [
        GroundingRejected("private draft"),
        TimeoutError("secret"),
        RuntimeError("secret"),
        AssistantFailure("model_output_limit", {}),
    ],
)
def test_failed_generation_exposes_no_text_or_private_error(
    setup, monkeypatch, failure
):
    async def generate(*args):
        raise failure

    monkeypatch.setattr(streaming, "generate_reply", generate)
    c = Connection()

    async def consume():
        return [
            s
            async for s in streaming.stream_turn(
                Request(), c, uuid4(), uuid4(), uuid4(), "Q", None, user_id=uuid4()
            )
        ]

    raw = asyncio.run(consume())
    assert not any(e["type"] in ("text-delta", "finish") for e in events(raw))
    assert "secret" not in "".join(raw) and "private draft" not in "".join(raw)
    assert c.calls == ["rollback"]
    if isinstance(failure, AssistantFailure):
        assert "The model reached its response limit." in "".join(raw)


def test_disconnect_cancels_work_and_rolls_back(setup, monkeypatch):
    request = Request()
    closed = []

    async def generate(*args):
        try:
            request.disconnected = True
            await asyncio.Event().wait()
        finally:
            closed.append(True)

    monkeypatch.setattr(streaming, "generate_reply", generate)
    c = Connection()

    async def consume():
        return [
            s
            async for s in streaming.stream_turn(
                request, c, uuid4(), uuid4(), uuid4(), "Q", None, user_id=uuid4()
            )
        ]

    raw = asyncio.run(consume())
    assert not any(e["type"] in ("text-delta", "finish") for e in events(raw))
    assert closed == [True] and c.calls == ["rollback"]
