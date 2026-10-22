from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.chat.limits import TurnLimiter


def test_concurrent_answers_are_capped_and_released():
    limiter, user = TurnLimiter(), uuid4()
    limiter.acquire(user, concurrent=2, per_hour=60)
    limiter.acquire(user, concurrent=2, per_hour=60)
    with pytest.raises(HTTPException) as error:
        limiter.acquire(user, concurrent=2, per_hour=60)
    assert error.value.status_code == 429
    limiter.release(user)
    limiter.acquire(user, concurrent=2, per_hour=60)
    # Another analyst is unaffected.
    limiter.acquire(uuid4(), concurrent=2, per_hour=60)


def test_hourly_limit_reports_when_to_retry(monkeypatch):
    from app.chat import limits

    clock = [1000.0]
    monkeypatch.setattr(limits, "monotonic", lambda: clock[0])
    limiter, user = TurnLimiter(), uuid4()
    for _ in range(3):
        limiter.acquire(user, concurrent=5, per_hour=3)
        limiter.release(user)
    with pytest.raises(HTTPException) as error:
        limiter.acquire(user, concurrent=5, per_hour=3)
    assert error.value.headers["Retry-After"] == "3601"
    clock[0] += 3600
    limiter.acquire(user, concurrent=5, per_hour=3)


def test_a_slot_that_was_never_released_expires(monkeypatch):
    # A stream closed before it starts never runs its release.
    from app.chat import limits

    clock = [1000.0]
    monkeypatch.setattr(limits, "monotonic", lambda: clock[0])
    limiter, user = TurnLimiter(), uuid4()
    limiter.acquire(user, concurrent=1, per_hour=60)
    with pytest.raises(HTTPException):
        limiter.acquire(user, concurrent=1, per_hour=60)
    clock[0] += limits.STALE
    limiter.acquire(user, concurrent=1, per_hour=60)
