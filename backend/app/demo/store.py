"""Short, independent transactions: chat rollback can never refund paid work."""

from datetime import UTC, datetime, timedelta
from decimal import ROUND_FLOOR, Decimal
from typing import Literal
from uuid import UUID, uuid4

import psycopg
from psycopg.rows import dict_row
from pydantic import BaseModel
from starlette.concurrency import run_in_threadpool

from app.config import settings
from app.demo.errors import DemoUnavailable
from app.demo.pricing import REVISION, RequestBound, charge, chat_bound


class DemoStatus(BaseModel):
    remaining_attempts: int
    can_generate: bool
    reset_at: datetime
    reason: Literal["visitor_limit", "daily_budget", "busy", "unavailable"] | None


class DemoStore:
    async def _run(self, operation, *args):
        return await run_in_threadpool(self._transaction, operation, *args)

    def _transaction(self, operation, *args):
        try:
            with psycopg.connect(
                str(settings.database_url),
                connect_timeout=10,
                row_factory=dict_row,
                prepare_threshold=None,
            ) as conn:
                conn.execute("SET LOCAL statement_timeout = '10s'")
                return operation(conn, *args)
        except psycopg.Error:
            raise DemoUnavailable() from None

    def _day(self, conn):
        ceiling = int(
            (settings.demo_daily_budget_usd * 1000000).to_integral_value(
                rounding=ROUND_FLOOR
            )
        )
        return conn.execute(
            """INSERT INTO demo_budget_days (day, ceiling, blocked)
            VALUES ((now() AT TIME ZONE 'UTC')::date, %s, (SELECT COALESCE(bool_or(blocked), false) FROM demo_budget_days))
            ON CONFLICT (day) DO UPDATE SET ceiling = LEAST(demo_budget_days.ceiling, EXCLUDED.ceiling),
                blocked = demo_budget_days.blocked OR EXCLUDED.blocked
            RETURNING *""",
            (ceiling,),
        ).fetchone()

    def _enabled(self):
        if not settings.demo_enabled:
            raise DemoUnavailable()

    async def admit(self, user_id: UUID) -> DemoStatus:
        self._enabled()
        await self._run(self._admit, user_id)
        return await self.status(user_id)

    def _admit(self, conn, user_id):
        day = self._day(conn)
        existing = conn.execute(
            "SELECT is_demo FROM users WHERE id = %s", (user_id,)
        ).fetchone()
        if existing:
            if not existing["is_demo"]:
                raise DemoUnavailable()
            return
        if day["blocked"] or day["admissions"] >= settings.demo_daily_admissions:
            raise DemoUnavailable()
        conn.execute(
            "INSERT INTO users (id, email, is_demo) VALUES (%s, NULL, true)", (user_id,)
        )
        conn.execute("INSERT INTO demo_visitors (user_id) VALUES (%s)", (user_id,))
        conn.execute(
            "UPDATE demo_budget_days SET admissions = admissions + 1 WHERE day = %s",
            (day["day"],),
        )

    async def status(self, user_id: UUID) -> DemoStatus:
        return await self._run(self._status, user_id)

    def _status(self, conn, user_id):
        day = self._day(conn)
        visitor = conn.execute(
            "SELECT attempts_started, lease_until > now() AS busy FROM demo_visitors WHERE user_id = %s",
            (user_id,),
        ).fetchone()
        if visitor is None:
            raise DemoUnavailable()
        return self._status_row(visitor, day, enabled=settings.demo_enabled)

    def _status_row(self, visitor, day, *, enabled):
        from app.chat.triage import TRIAGE_OUTPUT_TOKENS

        required = (
            chat_bound(settings.openai_chat_model, TRIAGE_OUTPUT_TOKENS).reservation
            if enabled
            else 0
        )
        remaining = max(
            0, settings.demo_attempts_per_visitor - visitor["attempts_started"]
        )
        reason = (
            "unavailable"
            if not enabled or day["blocked"]
            else "visitor_limit"
            if not remaining
            else "busy"
            if visitor["busy"]
            else "daily_budget"
            if day["charged"] + day["reserved"] + required > day["ceiling"]
            else None
        )
        reset = datetime.combine(
            day["day"] + timedelta(days=1), datetime.min.time(), UTC
        )
        return DemoStatus(
            remaining_attempts=remaining,
            can_generate=reason is None,
            reset_at=reset,
            reason=reason,
        )

    async def begin(self, user_id: UUID, thread_id: UUID, question_id: UUID) -> UUID:
        self._enabled()
        return await self._run(self._begin, user_id, thread_id, question_id)

    def _begin(self, conn, user_id, thread_id, question_id):
        day = self._day(conn)
        visitor = conn.execute(
            "SELECT *, lease_until > now() AS busy FROM demo_visitors WHERE user_id = %s FOR UPDATE",
            (user_id,),
        ).fetchone()
        if visitor is None:
            raise DemoUnavailable()
        status = self._status_row(visitor, day, enabled=settings.demo_enabled)
        if not status.can_generate:
            raise DemoUnavailable(status.reason)
        attempt_id = uuid4()
        conn.execute(
            "INSERT INTO demo_attempts (id, user_id, thread_id, question_id) VALUES (%s, %s, %s, %s)",
            (attempt_id, user_id, thread_id, question_id),
        )
        conn.execute(
            "UPDATE demo_visitors SET active_attempt = %s, lease_until = now() + interval '180 seconds' WHERE user_id = %s",
            (attempt_id, user_id),
        )
        return attempt_id

    async def finish(self, attempt_id: UUID) -> None:
        await self._run(self._finish, attempt_id)

    def _finish(self, conn, attempt_id):
        conn.execute(
            "UPDATE demo_visitors SET active_attempt = NULL, lease_until = NULL WHERE active_attempt = %s",
            (attempt_id,),
        )
        conn.execute(
            "UPDATE demo_attempts SET state = 'finished', finished_at = now() WHERE id = %s",
            (attempt_id,),
        )

    async def reserve(self, attempt_id: UUID, bound: RequestBound) -> UUID:
        self._enabled()
        return await self._run(self._reserve, attempt_id, bound)

    def _reserve(self, conn, attempt_id, bound):
        # Consistent day -> visitor -> attempt lock order serializes all spend.
        day = self._day(conn)
        visitor = conn.execute(
            "SELECT v.*, v.lease_until > now() AS busy FROM demo_visitors v JOIN demo_attempts a ON a.user_id = v.user_id WHERE a.id = %s FOR UPDATE OF v",
            (attempt_id,),
        ).fetchone()
        attempt = conn.execute(
            "SELECT * FROM demo_attempts WHERE id = %s FOR UPDATE", (attempt_id,)
        ).fetchone()
        if (
            not visitor
            or not attempt
            or visitor["active_attempt"] != attempt_id
            or not visitor["busy"]
            or attempt["state"] != "active"
        ):
            raise DemoUnavailable()
        if day["blocked"]:
            raise DemoUnavailable()
        if day["charged"] + day["reserved"] + bound.reservation > day["ceiling"]:
            raise DemoUnavailable("daily_budget")
        if attempt["provider_starts"] == 0:
            if visitor["attempts_started"] >= settings.demo_attempts_per_visitor:
                raise DemoUnavailable("visitor_limit")
            conn.execute(
                "UPDATE demo_visitors SET attempts_started = attempts_started + 1 WHERE user_id = %s",
                (visitor["user_id"],),
            )
        request_id = uuid4()
        conn.execute(
            "UPDATE demo_attempts SET provider_starts = provider_starts + 1 WHERE id = %s",
            (attempt_id,),
        )
        conn.execute(
            "UPDATE demo_budget_days SET reserved = reserved + %s WHERE day = %s",
            (bound.reservation, day["day"]),
        )
        conn.execute(
            """INSERT INTO demo_model_requests (id, attempt_id, day, model, endpoint, rate_revision, input_rate, output_rate, input_limit, output_limit, reservation)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
            (
                request_id,
                attempt_id,
                day["day"],
                bound.model,
                bound.endpoint,
                REVISION,
                bound.input_rate,
                bound.output_rate,
                bound.input_limit,
                bound.output_limit,
                bound.reservation,
            ),
        )
        return request_id

    async def settle(
        self, request_id: UUID, bound: RequestBound, usage: dict | None
    ) -> None:
        valid = await self._run(self._settle, request_id, bound, usage)
        if not valid:
            raise DemoUnavailable()

    def _settle(self, conn, request_id, bound, usage):
        # Charge the original dispatch day, even if the response crosses midnight.
        row = conn.execute(
            "SELECT day FROM demo_model_requests WHERE id = %s", (request_id,)
        ).fetchone()
        if not row:
            raise DemoUnavailable()
        conn.execute(
            "SELECT day FROM demo_budget_days WHERE day = %s FOR UPDATE", (row["day"],)
        )
        row = conn.execute(
            "SELECT * FROM demo_model_requests WHERE id = %s FOR UPDATE", (request_id,)
        ).fetchone()
        if row["state"] == "settled":
            return True
        if not isinstance(usage, dict):
            conn.execute(
                "UPDATE demo_model_requests SET state = 'unknown' WHERE id = %s",
                (request_id,),
            )
            return True
        try:
            # Persisted prices, rather than today's manifest, govern settlement.
            stored = RequestBound(
                row["model"],
                row["endpoint"],
                row["input_limit"],
                row["output_limit"],
                Decimal(row["input_rate"]),
                Decimal(row["output_rate"]),
            )
            cost = charge(stored, usage)
            if cost > row["reservation"]:
                raise DemoUnavailable()
        except DemoUnavailable:
            conn.execute(
                "UPDATE demo_budget_days SET blocked = true WHERE day = %s",
                (row["day"],),
            )
            return False
        conn.execute(
            "UPDATE demo_budget_days SET reserved = reserved - %s, charged = charged + %s WHERE day = %s",
            (row["reservation"], cost, row["day"]),
        )
        conn.execute(
            "UPDATE demo_model_requests SET state = 'settled', charge = %s, input_tokens = %s, output_tokens = %s, settled_at = now() WHERE id = %s",
            (
                cost,
                usage["prompt_tokens"],
                usage.get("completion_tokens", 0),
                request_id,
            ),
        )
        return True
