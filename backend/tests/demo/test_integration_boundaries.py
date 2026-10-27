"""Offline component checks; no real Auth, database or model calls."""

import asyncio
from types import SimpleNamespace
from uuid import uuid4

import httpx
import pytest
from openai import AsyncOpenAI

from app.demo.client import DemoAttempt, current_attempt, demo_client_options
from app.demo.errors import DemoUnavailable, demo_failure
from app.demo.transport import MeteredTransport


class Meter:
    def __init__(self):
        self.reservations = []
        self.settlements = []

    async def reserve(self, attempt_id, bound):
        self.reservations.append((attempt_id, bound))
        return uuid4()

    async def settle(self, request_id, bound, usage):
        self.settlements.append((request_id, usage))


@pytest.mark.anyio
async def test_sdk_retry_is_metered_and_standard_tier_is_explicit():
    store = Meter()
    calls = []

    def provider(request):
        import json

        assert json.loads(request.content)["service_tier"] == "default"
        calls.append(request)
        if len(calls) == 1:
            return httpx.Response(500, json={"error": {"message": "fixture"}})
        return httpx.Response(
            200,
            json={
                "id": "chatcmpl-unit",
                "object": "chat.completion",
                "created": 0,
                "model": "gpt-4o-mini",
                "choices": [],
                "usage": {
                    "prompt_tokens": 4,
                    "completion_tokens": 3,
                    "total_tokens": 7,
                },
            },
        )

    async with AsyncOpenAI(
        api_key="unit-test",
        max_retries=1,
        http_client=httpx.AsyncClient(
            transport=MeteredTransport(store, uuid4(), httpx.MockTransport(provider))
        ),
    ) as client:
        await client.chat.completions.create(
            model="gpt-4o-mini",
            max_tokens=40,
            messages=[{"role": "user", "content": "Hello"}],
        )
    assert len(store.reservations) == 2
    assert len(store.settlements) == 1


@pytest.mark.anyio
async def test_wrapped_denial_does_not_fall_back_to_filings(monkeypatch):
    from app.chat import orchestrator

    async def denied(*args):
        try:
            raise DemoUnavailable("daily_budget")
        except DemoUnavailable as cause:
            raise RuntimeError("wrapped") from cause

    monkeypatch.setattr(orchestrator, "triage_turn", denied)
    monkeypatch.setattr(orchestrator, "build_triage_agent", lambda *a: None)
    with pytest.raises(DemoUnavailable):
        await orchestrator.safe_triage("Hello", [], None)


@pytest.mark.anyio
async def test_context_inherited_by_parallel_roles_but_not_other_requests():
    assert demo_client_options() == {}
    attempt = DemoAttempt(Meter(), uuid4())

    async def role():
        options = demo_client_options()
        assert options["base_url"] == "https://api.openai.com/v1"
        transport = options["http_client"]._transport
        assert transport.attempt_id == attempt.id
        await options["http_client"].aclose()

    token = current_attempt.set(attempt)
    try:
        await asyncio.gather(role(), role())
    finally:
        current_attempt.reset(token)
    assert demo_client_options() == {}


@pytest.mark.anyio
async def test_cancelled_provider_keeps_reservation():
    store = Meter()

    async def interrupted(_):
        raise asyncio.CancelledError

    transport = MeteredTransport(store, uuid4(), httpx.MockTransport(interrupted))
    request = httpx.Request(
        "POST",
        "https://api.openai.com/v1/chat/completions",
        json={"model": "gpt-4o-mini", "max_tokens": 40},
    )
    with pytest.raises(asyncio.CancelledError):
        await transport.handle_async_request(request)
    assert len(store.reservations) == 1
    assert not store.settlements


@pytest.mark.anyio
async def test_keyword_denial_is_visible_not_lexical_degradation():
    from app.config import settings
    from app.retrieval.keywords import extract_keywords

    class Agent:
        async def run(self, *a, **kw):
            from openai import APIConnectionError

            try:
                raise DemoUnavailable("daily_budget")
            except DemoUnavailable as cause:
                raise APIConnectionError(
                    request=httpx.Request("POST", "https://api.openai.com")
                ) from cause

    with pytest.raises(DemoUnavailable):
        await extract_keywords(
            "What services does Azure provide in this filing?", [], settings, Agent()
        )


@pytest.mark.anyio
async def test_pydanticai_wrapped_transport_denial_keeps_safe_reason():
    from app.chat.triage import build_triage_agent, triage_turn
    from app.config import settings

    class DenyingMeter(Meter):
        async def reserve(self, *args):
            raise DemoUnavailable("daily_budget")

    def must_not_dispatch(_):
        raise AssertionError("Budget refused before provider dispatch")

    transport = MeteredTransport(
        DenyingMeter(), uuid4(), httpx.MockTransport(must_not_dispatch)
    )
    async with AsyncOpenAI(
        api_key="unit-test",
        max_retries=0,
        http_client=httpx.AsyncClient(transport=transport),
    ) as client:
        with pytest.raises(Exception) as captured:
            await triage_turn("Hello", [], build_triage_agent(settings, client))
    assert demo_failure(captured.value).reason == "daily_budget"


def test_error_chain_handles_cycles():
    a = RuntimeError()
    b = RuntimeError()
    a.__cause__ = b
    b.__cause__ = a
    assert demo_failure(a) is None


@pytest.mark.anyio
async def test_stream_sets_context_for_both_tasks_and_releases_lease(monkeypatch):
    from app.assistant.rendering import AcceptedReply
    from app.chat import streaming

    meter = Meter()
    attempt = DemoAttempt(meter, uuid4())
    seen = []

    async def title(_):
        seen.append(("title", current_attempt.get()))

    async def reply(*args):
        seen.append(("reply", current_attempt.get()))
        return SimpleNamespace(reply=AcceptedReply(text="Hello", parts=[]))

    async def finish(attempt_id):
        seen.append(("finish", attempt_id))

    async def history(*a, **kw):
        return []

    async def save(*a):
        pass

    class Connection:
        def commit(self):
            pass

        def rollback(self):
            pass

    class Request:
        async def is_disconnected(self):
            return False

    meter.finish = finish
    monkeypatch.setattr(streaming, "summarize_title", title)
    monkeypatch.setattr(streaming, "generate_reply", reply)
    monkeypatch.setattr(streaming.chats, "recent_history", history)
    monkeypatch.setattr(streaming.chats, "save_turn", save)
    events = [
        part
        async for part in streaming.stream_turn(
            Request(),
            Connection(),
            uuid4(),
            uuid4(),
            uuid4(),
            "Hi",
            None,
            user_id=uuid4(),
            demo_attempt=attempt,
        )
    ]
    assert any("[DONE]" in part for part in events)
    assert ("title", attempt) in seen and ("reply", attempt) in seen
    assert ("finish", attempt.id) in seen
    assert current_attempt.get() is None
