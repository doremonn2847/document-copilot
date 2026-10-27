import json
from uuid import UUID

import httpx
from anyio import CancelScope

from app.demo.pricing import request_bound


class MeteredTransport(httpx.AsyncBaseTransport):
    def __init__(self, store, attempt_id: UUID, transport=None):
        self.store = store
        self.attempt_id = attempt_id
        self.transport = transport or httpx.AsyncHTTPTransport()

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        if request.url.path == "/v1/chat/completions":
            # The project default can change; demo dispatch always requests Standard.
            try:
                body = json.loads(request.content)
                if isinstance(body, dict) and "service_tier" not in body:
                    body["service_tier"] = "default"
                    request = httpx.Request(
                        request.method,
                        request.url,
                        headers={
                            key: value
                            for key, value in request.headers.items()
                            if key != "content-length"
                        },
                        json=body,
                        extensions=request.extensions,
                    )
            except ValueError:
                pass  # request_bound rejects malformed JSON before any reservation.
        bound = request_bound(request)
        # A cancelled worker may still commit. Never refund an uncertain dispatch.
        request_id = await self.store.reserve(self.attempt_id, bound)
        response = await self.transport.handle_async_request(request)
        if response.is_success:
            try:
                await response.aread()
                body = response.json()
                usage = body.get("usage") if isinstance(body, dict) else None
            except (ValueError, json.JSONDecodeError):
                usage = None
            with CancelScope(shield=True):
                await self.store.settle(request_id, bound, usage)
        return response

    async def aclose(self) -> None:
        await self.transport.aclose()
