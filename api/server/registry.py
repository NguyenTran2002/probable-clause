"""The runs this instance holds (contract §4.H). One stream per run is the `Run`'s own rule (T3.1)."""

import asyncio
import logging

from api import settings
from api.server.clock import Clock, wait_all
from api.server.run import Run

log = logging.getLogger("api.server.registry")


class RunRegistry:
    """Runs held here. An expired run leaves at once; a finished run stays readable from memory until its events
    would expire from Atlas (EVENTS_TTL_S, T3.2: "stays readable on reconnect until its events expire")."""

    def __init__(self, clock: Clock):
        self._clock = clock
        self._runs: dict[str, Run] = {}
        self.closing = asyncio.Event()           # set when the lifespan shutdown begins

    def __contains__(self, run_id: str) -> bool:
        return run_id in self._runs

    def add(self, run: Run) -> None:
        self._prune()
        if run.run_id in self._runs:
            raise ValueError("a run with this ID is already held")
        self._runs[run.run_id] = run

    def get(self, run_id: str) -> Run | None:
        self._prune()
        run = self._runs.get(run_id)
        return run if run is not None and run.state != "expired" else None

    def discard(self, run: Run) -> None:
        if self._runs.get(run.run_id) is run:
            del self._runs[run.run_id]

    def _prune(self) -> None:
        keep_s = float(settings.EVENTS_TTL_S.value)
        now = self._clock.monotonic()
        for rid, run in list(self._runs.items()):
            if run.state == "finished" and run.finished_mono is not None and now - run.finished_mono > keep_s:
                del self._runs[rid]

    async def shutdown(self) -> None:
        """Close every stream, expire what never started and cancel what runs, all at once (contract v1.2). Waits at
        most SHUTDOWN_GRACE_S: first for every reservation to be released (or kept counted, a paid call being in
        flight), then for the rest of each run's end. What does not finish in time stays counted: the safe side."""
        self.closing.set()
        runs = list(self._runs.values())
        for run in runs:
            run.wake_streams()                    # each live stream sees `closing` and ends
            if run.state == "created":
                asyncio.ensure_future(run.expire("shutdown"))
            elif run.state == "running":
                run.cancel()
        grace = float(settings.SHUTDOWN_GRACE_S.value)
        t0 = self._clock.monotonic()
        money = await wait_all([r.money_done for r in runs], grace, self._clock)
        rest = await wait_all([r.finished for r in runs], grace - (self._clock.monotonic() - t0), self._clock)
        open_ = sum(1 for r in runs if not r.reservation_released)
        if not (money and rest):
            log.error("shutdown: grace of %.0f s ran out (reservations settled: %s, runs ended: %s)", grace, money, rest)
        log.info("shutdown: %d runs closed, %d reservations left counted", len(runs), open_)
