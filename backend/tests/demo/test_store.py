from contextlib import contextmanager
from datetime import date
from uuid import uuid4

import httpx
import pytest

from app.demo.errors import DemoUnavailable
from app.demo.pricing import request_bound
from app.demo.store import DemoStore


class Result:
    def __init__(self, row):
        self.row = row

    def fetchone(self):
        return self.row


class Connection:
    def __init__(self, rows):
        self.rows = iter(rows)
        self.calls = []

    def execute(self, sql, params=None):
        self.calls.append((sql, params))
        return Result(next(self.rows, None))


def test_finish_only_releases_its_own_lease():
    store = DemoStore()
    conn = Connection([None, None])
    attempt = uuid4()
    store._finish(conn, attempt)
    sql = " ".join(call[0] for call in conn.calls)
    assert "active_attempt = %s" in sql
    assert all("demo_budget_days" not in call[0] for call in conn.calls)
    assert all("attempts_started =" not in call[0] for call in conn.calls)


def test_status_never_exposes_ledger_or_other_users():
    store = DemoStore()
    status = store._status_row(
        {"attempts_started": 3, "busy": False},
        day(),
        enabled=True,
    )
    assert status.remaining_attempts == 0
    assert status.reason == "visitor_limit"
    assert not status.can_generate
    assert set(status.model_dump()) == {
        "remaining_attempts",
        "can_generate",
        "reset_at",
        "reason",
    }


def test_budget_and_accounting_block_status():
    store = DemoStore()
    visitor = {"attempts_started": 0, "busy": False}
    budget = day(charged=1, reserved=999999)
    assert store._status_row(visitor, budget, enabled=True).reason == "daily_budget"
    budget["blocked"] = True
    assert store._status_row(visitor, budget, enabled=True).reason == "unavailable"


def test_status_reset_uses_database_day_even_if_app_clock_differs():
    status = DemoStore()._status_row(
        {"attempts_started": 0, "busy": False}, day(day=date(2001, 1, 1)), enabled=True
    )
    assert status.reset_at.isoformat() == "2001-01-02T00:00:00+00:00"


def test_positive_but_insufficient_pool_is_unavailable_before_title_can_start(
    monkeypatch,
):
    from app.config import settings

    monkeypatch.setattr(settings, "demo_enabled", True)
    monkeypatch.setattr(settings, "openai_chat_model", "gpt-5.4-mini")
    budget = day(charged=980000)
    visitor = {"attempts_started": 0, "busy": False}
    status = DemoStore()._status_row(visitor, budget, enabled=True)
    assert status.reason == "daily_budget" and not status.can_generate
    assert status.remaining_attempts == 3
    conn = Connection([budget, visitor])
    with pytest.raises(DemoUnavailable) as error:
        DemoStore()._begin(conn, uuid4(), uuid4(), uuid4())
    assert error.value.reason == "daily_budget"
    assert len(conn.calls) == 2


def bound():
    return request_bound(
        httpx.Request(
            "POST",
            "https://api.openai.com/v1/chat/completions",
            json={"model": "gpt-5.4-mini", "max_tokens": 4000},
        )
    )


def day(**changes):
    return {
        "day": date(2026, 10, 27),
        "ceiling": 1000000,
        "charged": 0,
        "reserved": 0,
        "blocked": False,
        "admissions": 0,
        **changes,
    }


@pytest.mark.parametrize("already_started", [0, 1])
def test_reservation_consumes_attempt_once_and_commits_before_provider(already_started):
    attempt_id = uuid4()
    visitor = {
        "active_attempt": attempt_id,
        "busy": True,
        "attempts_started": 0,
        "user_id": uuid4(),
    }
    conn = Connection(
        [day(), visitor, {"state": "active", "provider_starts": already_started}]
    )
    DemoStore()._reserve(conn, attempt_id, bound())
    statements = [sql for sql, _ in conn.calls]
    assert "ON CONFLICT (day)" in statements[0]
    assert "FOR UPDATE OF v" in statements[1]
    assert "FOR UPDATE" in statements[2]
    assert sum(
        "attempts_started = attempts_started + 1" in sql for sql in statements
    ) == (not already_started)
    assert any(
        params == (318000, date(2026, 10, 27))
        for sql, params in conn.calls
        if "reserved = reserved +" in sql
    )
    assert all(str(attempt_id) not in sql for sql in statements)


@pytest.mark.parametrize(
    "kind", ["budget", "blocked", "expired", "replaced", "exhausted"]
)
def test_declined_reservation_makes_no_counter_write(kind):
    attempt_id = uuid4()
    visitor = {
        "active_attempt": attempt_id,
        "busy": True,
        "attempts_started": 0,
        "user_id": uuid4(),
    }
    budget = day()
    if kind == "budget":
        budget["reserved"] = 700000
    if kind == "blocked":
        budget["blocked"] = True
    if kind == "expired":
        visitor["busy"] = False
    if kind == "replaced":
        visitor["active_attempt"] = uuid4()
    if kind == "exhausted":
        visitor["attempts_started"] = 3
    conn = Connection([budget, visitor, {"state": "active", "provider_starts": 0}])
    with pytest.raises(DemoUnavailable):
        DemoStore()._reserve(conn, attempt_id, bound())
    assert len(conn.calls) == 3


def ledger_row(**changes):
    b = bound()
    return {
        "day": date(2026, 10, 26),
        "state": "reserved",
        "model": b.model,
        "endpoint": b.endpoint,
        "input_limit": b.input_limit,
        "output_limit": b.output_limit,
        "input_rate": b.input_rate,
        "output_rate": b.output_rate,
        "reservation": b.reservation,
        **changes,
    }


def test_settlement_uses_original_day_rates_and_rounds_once():
    row = ledger_row()
    conn = Connection([{"day": row["day"]}, None, row])
    assert DemoStore()._settle(
        conn, uuid4(), bound(), {"prompt_tokens": 1, "completion_tokens": 1}
    )
    update = next(
        params for sql, params in conn.calls if "reserved = reserved -" in sql
    )
    assert update == (318000, 6, date(2026, 10, 26))


def test_idempotent_settlement_cannot_charge_twice():
    row = ledger_row(state="settled")
    conn = Connection([{"day": row["day"]}, None, row])
    assert DemoStore()._settle(
        conn, uuid4(), bound(), {"prompt_tokens": 1, "completion_tokens": 1}
    )
    assert not any(sql.startswith("UPDATE") for sql, _ in conn.calls)


def test_unknown_usage_never_releases_reservation():
    row = ledger_row()
    conn = Connection([{"day": row["day"]}, None, row])
    assert DemoStore()._settle(conn, uuid4(), bound(), None)
    assert not any("reserved = reserved -" in sql for sql, _ in conn.calls)
    assert "state = 'unknown'" in conn.calls[-1][0]


def test_invalid_usage_blocks_further_dispatch_without_refund():
    row = ledger_row()
    conn = Connection([{"day": row["day"]}, None, row])
    assert not DemoStore()._settle(
        conn, uuid4(), bound(), {"prompt_tokens": 1, "completion_tokens": 5000}
    )
    assert "SET blocked = true" in conn.calls[-1][0]
    assert not any("reserved = reserved -" in sql for sql, _ in conn.calls)


def test_admission_is_idempotent_at_daily_limit():
    conn = Connection([day(admissions=100), {"is_demo": True}])
    DemoStore()._admit(conn, uuid4())
    assert len(conn.calls) == 2


def test_admission_limit_precedes_profile_write():
    conn = Connection([day(admissions=100), None])
    with pytest.raises(DemoUnavailable):
        DemoStore()._admit(conn, uuid4())
    assert len(conn.calls) == 2


def test_begin_only_leases_does_not_consume_allowance(monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "demo_enabled", True)
    visitor = {"attempts_started": 0, "busy": False}
    conn = Connection([day(), visitor])
    DemoStore()._begin(conn, uuid4(), uuid4(), uuid4())
    assert not any("attempts_started =" in sql for sql, _ in conn.calls)
    assert any("interval '180 seconds'" in sql for sql, _ in conn.calls)


@pytest.mark.anyio
async def test_database_failure_is_sanitized_and_connection_independent(monkeypatch):
    import psycopg

    import app.demo.store as module

    @contextmanager
    def broken(*args, **kwargs):
        assert kwargs["prepare_threshold"] is None
        assert kwargs["connect_timeout"] == 10
        raise psycopg.OperationalError("PRIVATE CONNECTION STRING")
        yield

    monkeypatch.setattr(module.psycopg, "connect", broken)
    with pytest.raises(DemoUnavailable) as error:
        await DemoStore().status(uuid4())
    assert str(error.value) == "unavailable"
