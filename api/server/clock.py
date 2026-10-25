"""Time for the run lifecycle (contract §4.H): wall-clock Chicago time, a monotonic clock and sleeps, injected.

Tests pass a virtual clock (tests/server/support.py) so no test waits the real ATTENDED_WINDOW_S, ABANDON_AFTER_S
or UNATTACHED_RUN_EXPIRY_S.
"""

import asyncio
import time
from datetime import datetime
from typing import Protocol

from api.state.clock import CHICAGO


class Clock(Protocol):
    def now(self) -> datetime: ...              # aware, America/Chicago (brief §10.7)
    def monotonic(self) -> float: ...           # seconds, for t_ms and the run deadline
    async def sleep(self, seconds: float) -> None: ...


class RealClock:
    def now(self) -> datetime:
        return datetime.now(CHICAGO)

    def monotonic(self) -> float:
        return time.monotonic()

    async def sleep(self, seconds: float) -> None:
        await asyncio.sleep(seconds)


async def wait_event(event: asyncio.Event, timeout_s: float, clock: Clock) -> bool:
    """Wait until `event` is set or `timeout_s` passes on `clock`. True if the event was set."""
    if event.is_set():
        return True
    ev = asyncio.ensure_future(event.wait())
    timer = asyncio.ensure_future(clock.sleep(timeout_s))
    try:
        done, _ = await asyncio.wait({ev, timer}, return_when=asyncio.FIRST_COMPLETED)
        return ev in done
    finally:
        for t in (ev, timer):
            if not t.done():
                t.cancel()


async def wait_all(events: list[asyncio.Event], timeout_s: float, clock: Clock) -> bool:
    """Wait until every event is set or `timeout_s` passes on `clock`. True if all were set."""
    pending = [e for e in events if not e.is_set()]
    if not pending:
        return True
    if timeout_s <= 0:
        return False
    together = asyncio.ensure_future(asyncio.gather(*(e.wait() for e in pending)))
    timer = asyncio.ensure_future(clock.sleep(timeout_s))
    try:
        done, _ = await asyncio.wait({together, timer}, return_when=asyncio.FIRST_COMPLETED)
        return together in done
    finally:
        for t in (together, timer):
            if not t.done():
                t.cancel()
