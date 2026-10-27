import json
from uuid import uuid4

import httpx
import pytest

from app.demo.errors import DemoUnavailable
from app.demo.pricing import charge, request_bound
from app.demo.transport import MeteredTransport


def request(body, path="/v1/chat/completions"):
    return httpx.Request("POST", "https://api.openai.com" + path, json=body)


def test_conservative_bound_and_upward_rounding():
    bound = request_bound(
        request({"model": "gpt-5.4-mini", "max_completion_tokens": 4000})
    )
    assert bound.reservation == 318000
    assert charge(bound, {"prompt_tokens": 1, "completion_tokens": 1}) == 6


@pytest.mark.parametrize(
    "change",
    [
        {"model": "unknown"},
        {"stream": True},
        {"service_tier": "flex"},
        {"max_tokens": 0},
        {"max_tokens": 40, "max_completion_tokens": 1},
        {"n": 2},
        {"tools": [{"type": "web_search"}]},
        {"messages": [{"role": "user", "content": [{"type": "image_url"}]}]},
    ],
)
def test_unsupported_requests_are_rejected(change):
    with pytest.raises(DemoUnavailable):
        request_bound(request({"model": "gpt-4o-mini", "max_tokens": 40, **change}))


def test_embeddings_single_text_only():
    bound = request_bound(
        request({"model": "text-embedding-3-small", "input": "hello"}, "/v1/embeddings")
    )
    assert bound.reservation == 164
    assert charge(bound, {"prompt_tokens": 2, "total_tokens": 2}) == 1
    for value in [["hello"], [1, 2], "x" * 8192]:
        with pytest.raises(DemoUnavailable):
            request_bound(
                request(
                    {"model": "text-embedding-3-small", "input": value},
                    "/v1/embeddings",
                )
            )


class Store:
    def __init__(self, deny=False):
        self.calls = []
        self.deny = deny

    async def reserve(self, attempt_id, bound):
        self.calls.append("reserve")
        if self.deny:
            raise DemoUnavailable("daily_budget")
        return uuid4()

    async def settle(self, request_id, bound, usage):
        self.calls.append(("settle", usage))


@pytest.mark.anyio
async def test_denial_precedes_dispatch_and_missing_usage_stays_reserved():
    store = Store(deny=True)
    dispatched = []

    async def provider(req):
        dispatched.append(req)
        return httpx.Response(200, json={"choices": []})

    async with httpx.AsyncClient(
        transport=MeteredTransport(store, uuid4(), httpx.MockTransport(provider))
    ) as client:
        with pytest.raises(DemoUnavailable):
            await client.send(request({"model": "gpt-4o-mini", "max_tokens": 40}))
        assert dispatched == []
        store.deny = False
        await client.send(request({"model": "gpt-4o-mini", "max_tokens": 40}))
    assert store.calls == ["reserve", "reserve", ("settle", None)]


@pytest.mark.anyio
async def test_each_http_attempt_is_reserved_and_usage_settled():
    store = Store()
    responses = iter(
        [
            httpx.Response(500),
            httpx.Response(
                200, json={"usage": {"prompt_tokens": 4, "completion_tokens": 3}}
            ),
        ]
    )
    async with httpx.AsyncClient(
        transport=MeteredTransport(
            store, uuid4(), httpx.MockTransport(lambda _: next(responses))
        )
    ) as client:
        for _ in range(2):
            await client.send(request({"model": "gpt-4o-mini", "max_tokens": 40}))
    assert store.calls == [
        "reserve",
        "reserve",
        ("settle", {"prompt_tokens": 4, "completion_tokens": 3}),
    ]


def test_usage_cannot_exceed_reserved_bounds():
    bound = request_bound(request({"model": "gpt-4o-mini", "max_tokens": 40}))
    for usage in [
        {"prompt_tokens": 1, "completion_tokens": 41},
        {"prompt_tokens": -1, "completion_tokens": 2},
        {"prompt_tokens": True, "completion_tokens": 1},
    ]:
        with pytest.raises(DemoUnavailable):
            charge(bound, usage)


def test_request_origin_cannot_be_overridden():
    req = httpx.Request(
        "POST",
        "https://elsewhere.example/v1/chat/completions",
        content=json.dumps({"model": "gpt-4o-mini", "max_tokens": 40}),
    )
    with pytest.raises(DemoUnavailable):
        request_bound(req)
