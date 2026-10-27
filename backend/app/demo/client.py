from contextvars import ContextVar
from dataclasses import dataclass
from uuid import UUID

import httpx

from app.demo.store import DemoStore
from app.demo.transport import MeteredTransport


@dataclass(frozen=True)
class DemoAttempt:
    store: DemoStore
    id: UUID


# Bound by the stream, inherited by its title and answer tasks, never user input.
current_attempt: ContextVar[DemoAttempt | None] = ContextVar(
    "demo_attempt", default=None
)


def demo_client_options() -> dict:
    attempt = current_attempt.get()
    if attempt is None:
        return {}
    return {
        "base_url": "https://api.openai.com/v1",
        "http_client": httpx.AsyncClient(
            transport=MeteredTransport(attempt.store, attempt.id)
        ),
    }
