"""Per-user answer limits for a single backend process.

The pilot runs one backend instance, so in-process counters are enough; with
more replicas these limits would apply per replica.
"""

from collections import defaultdict, deque
from time import monotonic
from uuid import UUID

from fastapi import HTTPException, status

HOUR = 3600.0
# A stream closed before it starts never runs its release, so an in-progress
# slot also expires after the answer deadline (120 s) plus a margin.
STALE = 180.0


class TurnLimiter:
    def __init__(self) -> None:
        self.active: dict[UUID, list[float]] = defaultdict(list)
        self.started: dict[UUID, deque[float]] = defaultdict(deque)

    def acquire(self, user_id: UUID, concurrent: int, per_hour: int) -> None:
        now = monotonic()
        recent = self.started[user_id]
        while recent and now - recent[0] >= HOUR:
            recent.popleft()
        running = [t for t in self.active[user_id] if now - t < STALE]
        if len(running) >= concurrent:
            raise HTTPException(
                status.HTTP_429_TOO_MANY_REQUESTS,
                "Too many answers in progress",
                headers={"Retry-After": "30"},
            )
        if len(recent) >= per_hour:
            raise HTTPException(
                status.HTTP_429_TOO_MANY_REQUESTS,
                "Hourly question limit reached",
                headers={"Retry-After": str(int(HOUR - (now - recent[0])) + 1)},
            )
        recent.append(now)
        self.active[user_id] = [*running, now]

    def release(self, user_id: UUID) -> None:
        running = self.active.get(user_id)
        if running:
            running.pop(0)
        if not running:
            self.active.pop(user_id, None)


limiter = TurnLimiter()
