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
        self._slots: set[str] = set()            # runs in progress: slot taken at POST /runs, freed after the end (P4.21)
        self.closing = asyncio.Event()           # set when the lifespan shutdown begins

    def __contains__(self, run_id: str) -> bool:
        return run_id in self._runs

    # --- the count of runs in progress (contract §4.H, P4.21) -------------------------------------------------------------
    @property
    def in_progress(self) -> int:
        return len(self._slots)

    def take_slot(self, run_id: str) -> bool:
        """Take a place among the runs in progress, or False when MAX_CONCURRENT_RUNS are already in progress. There is
        no await between the count and the take, so two requests at once can never both pass a count of 4."""
        if run_id in self._slots:
            return True
        if len(self._slots) >= int(settings.MAX_CONCURRENT_RUNS.value):
            return False
        self._slots.add(run_id)
        return True

    def free_slot(self, run_id: str) -> None:
        """Give a place back. Safe to call twice: a slot is freed on a refusal, on expiry, and after `run_ended`."""
        self._slots.discard(run_id)

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
        """Close every stream, expire what never started and cancel what runs, all at once (contract v1.2, v2.0). Waits
        at most SHUTDOWN_GRACE_S for each run's end, which records its kept costs and frees its slot. A paid call in
        flight that the grace does not cover is lost, as P4.21 accepts."""
        self.closing.set()
        runs = list(self._runs.values())
        for run in runs:
            run.wake_streams()                    # each live stream sees `closing` and ends
            if run.state == "created":
                asyncio.ensure_future(run.expire("shutdown"))
            elif run.state == "running":
                run.cancel()
        grace = float(settings.SHUTDOWN_GRACE_S.value)
        ended = await wait_all([r.finished for r in runs], grace, self._clock)
        if not ended:
            log.error("shutdown: grace of %.0f s ran out before every run had ended", grace)
        log.info("shutdown: %d runs closed, %d still in progress", len(runs), self.in_progress)
