"""One run on this instance (contract §4.H): its state, event buffer, Atlas copy, heartbeat, deadline, reservation
and totals. `Run` is the `RunContext` the loop (G) and the search parts (C, D) are given.

The honesty-critical rules live here:
- `before_paid_call` checks, in this order: abandoned, past the deadline (never for composition), unattended (T3.2).
  Nothing is spent while nobody is watching: an unattended run pauses before the call and resumes only on a
  heartbeat that came after the pause began; with none it is abandoned ABANDON_AFTER_S after the last heartbeat.
- `record_usage` is the one place spend is priced (E's `price`), settled against the reservation and totalled,
  and the one emitter of `paid_call` (T3.4).
- The reservation is released when the run ends, on every path, in a `finally` that cancellation cannot skip (T3.4).
  Two cases leave it counted, which is the safe side ("a reservation that is never settled stays counted"): a cost
  that could not be settled in Atlas, and a run that ended abnormally (an exception or a cancellation) while a paid
  call it had cleared was not yet recorded, since that call may have been billed.
- Events are numbered from 1 with no gaps, kept in memory for the stream and copied to Atlas in order by one
  background writer, so a slow or failed Atlas write never holds up the stream or stops the run (T3.1).

Logs carry the run ID, states, timings, costs and error kinds only (T3.7): never the question, a query, the answer,
page text, or a store exception's message or chain (E's errors can carry host names).
"""

import asyncio
import json
import logging
from collections.abc import Awaitable, Callable
from datetime import datetime
from typing import Any, get_args

from api import settings
from api.errors import ErrorKind, ServiceError
from api.protocols import Reservation, Store
from api.server.clock import Clock, wait_event
from api.server.summary import answer_chars_of, rounds_of, run_record
from api.server.totals import COST_DIGITS, SERVICE_OF_PURPOSE, Totals, model_for
from api.state.clock import CHICAGO
from api.state.prices import failed_attempt_usage, price
from api.types import CallOutcome, CorpusLabel, Purpose, RunFlags, RunStopped, Service, Usage

log = logging.getLogger("api.server.run")

ERROR_KINDS = frozenset(get_args(ErrorKind))
# Stops recorded by someone else (contract §8): the cap refusals by `reserve`, the Exa credit stop by D.
RECORDED_ELSEWHERE = frozenset({"daily_cap", "monthly_cap", "exa_no_credit", "atlas_unreachable"})
_STOP = object()


def _f(name: str) -> float:
    """A figure from api/settings.py, read when used."""
    return float(getattr(settings, name).value)


def _kind(e: BaseException) -> str:
    """What a log may say about an error: its kind, never its message (T3.7; E's errors can name hosts)."""
    return e.kind if isinstance(e, ServiceError) else type(e).__name__


class Run:
    """A run held by this instance. States: created (reserved, nothing attached), running, finished; or expired
    (nothing ever attached, T3.1)."""

    def __init__(self, *, run_id: str, question: str, update_check_available: bool, corpus_label: CorpusLabel,
                 store: Store, reservation: Reservation, clock: Clock,
                 execute_run: Callable[[Any, Any], Awaitable[None]], loop_deps: Any,
                 event_validator: Callable[[dict], None] | None = None,
                 on_expired: Callable[["Run"], None] | None = None):
        # RunContext (api/types.py)
        self.run_id = run_id
        self.question = question
        self.update_check_available = update_check_available
        self.corpus_label = corpus_label
        self.flags = RunFlags()

        self.store = store
        self.reservation = reservation
        self.clock = clock
        self._execute_run = execute_run
        self._loop_deps = loop_deps
        self._validator = event_validator
        self._on_expired = on_expired

        self.state = "created"
        self.created_mono = clock.monotonic()
        self.finished_mono: float | None = None
        self.started_at: datetime | None = None
        self._t0: float | None = None

        self._events: list[dict] = []
        self._frames: list[str] = []
        self._changed = asyncio.Event()
        self._stream_token = 0

        self._last_hb: datetime | None = None
        self._hb_event = asyncio.Event()
        self.abandoned = False
        self._gate = asyncio.Lock()

        self._totals = Totals()
        self._in_flight = 0          # paid calls cleared by before_paid_call and not yet recorded
        self._unsettled = 0.0        # costs Atlas did not take; settled again at the end
        self._ended: dict | None = None

        self._queue: asyncio.Queue = asyncio.Queue()
        self._task: asyncio.Task | None = None
        self._writer: asyncio.Task | None = None
        self._expiry: asyncio.Task | None = None
        self._closing: asyncio.Future | None = None
        self.finished = asyncio.Event()
        self.money_done = asyncio.Event()      # the reservation is released, or deliberately left counted
        self.reservation_released = False

    # --- what the streams read ----------------------------------------------------------------------------------
    @property
    def frames(self) -> list[str]:
        return self._frames

    @property
    def changed(self) -> asyncio.Event:
        return self._changed

    @property
    def ended(self) -> bool:
        return self._ended is not None

    @property
    def events(self) -> list[dict]:
        return self._events

    def wake_streams(self) -> None:
        """Wake every stream of this run so it can see the instance is shutting down."""
        self._notify()

    def _notify(self) -> None:
        ev, self._changed = self._changed, asyncio.Event()
        ev.set()

    def is_current_stream(self, token: int) -> bool:
        return token == self._stream_token

    # --- attaching, heartbeats, expiry (T3.1, T3.2) --------------------------------------------------------------
    def schedule_expiry(self) -> None:
        self._expiry = asyncio.create_task(self._expire_after_wait())

    def attach(self, now: datetime) -> int:
        """A stream attaches: it counts as a heartbeat, replaces any earlier stream (one stream per run, T3.1), and
        the first one starts the run. Returns the stream's token."""
        if self.state == "expired":
            raise RuntimeError("an expired run cannot be attached")
        self.heartbeat(now)
        self._stream_token += 1
        self._notify()                                   # an earlier stream sees it is replaced and closes
        if self.state == "created":
            self._start()
        return self._stream_token

    def heartbeat(self, now: datetime) -> None:
        if self._last_hb is None or now > self._last_hb:
            self._last_hb = now
        self._hb_event.set()

    def _start(self) -> None:
        self.state = "running"
        self._t0 = self.clock.monotonic()
        self.started_at = self.clock.now()
        if self._expiry is not None:
            self._expiry.cancel()
        self._writer = asyncio.create_task(self._copy_events())
        self._task = asyncio.create_task(self._main())
        log.info("run %s started", self.run_id)

    async def _expire_after_wait(self) -> None:
        await self.clock.sleep(_f("UNATTACHED_RUN_EXPIRY_S"))
        await self.expire("unattached")

    async def expire(self, why: str) -> None:
        """A run nothing attached to: no spend, its reservation released (T3.1)."""
        if self.state != "created":
            return
        self.state = "expired"
        if self._expiry is not None and self._expiry is not asyncio.current_task():
            self._expiry.cancel()
        self._closing = asyncio.ensure_future(self._expire_inner(why))
        await asyncio.shield(self._closing)

    async def _expire_inner(self, why: str) -> None:
        try:
            try:
                await self._release()
            finally:
                self.money_done.set()
            log.info("run %s expired (%s): nothing spent, reservation released=%s", self.run_id, why,
                     self.reservation_released)
        finally:
            self.finished_mono = self.clock.monotonic()
            self.finished.set()
            self._notify()
            if self._on_expired is not None:
                self._on_expired(self)

    def cancel(self) -> None:
        """Shutdown: a running run is cancelled; its `finally` still settles, releases and records."""
        if self._task is not None and not self._task.done():
            self._task.cancel()

    # --- RunContext: events ----------------------------------------------------------------------------------------
    async def emit(self, kind: str, data: dict) -> int:
        """Number, time-stamp, buffer and queue one event (contract §6). Never waits on Atlas."""
        if self._t0 is None:
            raise RuntimeError("the run has not started")
        if self._ended is not None:
            raise RuntimeError("the run has already ended")
        n = len(self._events) + 1
        env = {"v": 1, "run": self.run_id, "n": n,
               "t_ms": max(0, int((self.clock.monotonic() - self._t0) * 1000)),
               "at": self.clock.now().astimezone(CHICAGO).isoformat(timespec="milliseconds"),
               "kind": kind, "data": data}
        text = json.dumps(env, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
        stored = json.loads(text)        # a copy: later changes to `data` by the caller reach nothing
        if self._validator is not None:
            self._validator(stored)
        self._events.append(stored)
        self._frames.append(f"id: {n}\nevent: {kind}\ndata: {text}\n\n")
        if kind == "run_ended":
            self._ended = stored["data"]
        self._queue.put_nowait(stored)
        self._notify()
        return n

    async def _copy_events(self) -> None:
        """Copy events to Atlas in order, one batch at a time; a failed batch is kept and sent with the next (the
        write is idempotent on (run, n)). A failure is logged by kind and never stops the run (T3.1)."""
        pending: list[dict] = []
        stopping = False
        while not stopping:
            item = await self._queue.get()
            items = [item]
            while not self._queue.empty():
                items.append(self._queue.get_nowait())
            for it in items:
                if it is _STOP:
                    stopping = True
                else:
                    pending.append(it)
            if not pending:
                continue
            try:
                await self.store.append_events(self.run_id, pending)
                pending = []
            except Exception as e:
                log.warning("run %s: %d events not yet copied to Atlas (%s)", self.run_id, len(pending), _kind(e))
        if pending:
            log.error("run %s: %d events were never copied to Atlas", self.run_id, len(pending))

    # --- RunContext: the gate before every paid call (contract §4.H, T3.2) ---------------------------------------
    def seconds_left(self) -> float:
        if self._t0 is None:
            return _f("RUN_DEADLINE_S")
        return self._t0 + _f("RUN_DEADLINE_S") - self.clock.monotonic()

    async def before_paid_call(self, service: Service, purpose: Purpose) -> None:
        async with self._gate:            # one pause at a time, however many calls are due together
            while True:
                if self.abandoned:                                                   # 1
                    raise RunStopped("abandoned")
                if purpose != "composition" and self.seconds_left() <= 0:            # 2 (T3.5)
                    raise RunStopped("deadline")
                if await self._attended():                                           # 3
                    break
                await self._pause()       # returns on a heartbeat, then the checks run again; raises when abandoned
        self._in_flight += 1

    async def call_not_billed(self, service: Service, purpose: Purpose) -> None:
        """A call the gate cleared that was never made or billed (Exa's 402 or 401, contract v1.4): undo its
        in-flight count, never below zero. Nothing is recorded."""
        self._in_flight = max(0, self._in_flight - 1)

    def _fresh(self, now: datetime) -> bool:
        return self._last_hb is not None and (now - self._last_hb).total_seconds() < _f("ATTENDED_WINDOW_S")

    async def _attended(self) -> bool:
        if self._fresh(self.clock.now()):
            return True
        await self._read_atlas_heartbeat()     # a heartbeat sent to another instance (T3.2)
        return self._fresh(self.clock.now())

    async def _read_atlas_heartbeat(self) -> None:
        try:
            at = await self.store.latest_heartbeat(self.run_id)
        except Exception as e:                 # no heartbeat read is no heartbeat: the safe side
            log.warning("run %s: could not read the heartbeat from Atlas (%s)", self.run_id, _kind(e))
            return
        if at is not None and (self._last_hb is None or at > self._last_hb):
            self._last_hb = at

    async def _pause(self) -> None:
        last = self._last_hb
        assert last is not None                # attaching set one
        since_s = (self.clock.now() - last).total_seconds()
        await self.emit("paused", {"since_ms": max(0, int(since_s * 1000))})
        paused_at = self.clock.monotonic()
        log.info("run %s paused: %.1f s since the last heartbeat", self.run_id, since_s)
        while True:
            self._hb_event.clear()
            await self._read_atlas_heartbeat()
            if self._last_hb > last:           # a heartbeat that came after the pause began
                await self.emit("resumed", {"since_ms": max(0, int((self.clock.monotonic() - paused_at) * 1000))})
                log.info("run %s resumed after %.1f s", self.run_id, self.clock.monotonic() - paused_at)
                return
            remaining = _f("ABANDON_AFTER_S") - (self.clock.now() - self._last_hb).total_seconds()
            if remaining <= 0:
                self.abandoned = True
                log.info("run %s abandoned: no heartbeat for %.0f s", self.run_id, _f("ABANDON_AFTER_S"))
                raise RunStopped("abandoned")
            await wait_event(self._hb_event, min(_f("HEARTBEAT_POLL_S"), remaining), self.clock)

    # --- RunContext: money (T3.3, T3.4) --------------------------------------------------------------------------
    async def record_usage(self, usage: Usage | None, *, purpose: Purpose, attempt: int, max_attempts: int,
                           outcome: CallOutcome, error_kind: str | None, duration_ms: int,
                           raw_usage: dict | None = None, call_no: int | None = None) -> float:
        if purpose not in SERVICE_OF_PURPOSE:
            raise ValueError(f"unknown purpose {purpose!r}")
        service = SERVICE_OF_PURPOSE[purpose]
        if usage is not None and usage.service != service:
            raise ValueError(f"a {usage.service} usage recorded for purpose {purpose!r}")
        # No usage reported: priced as T3.3 says, with no input estimate from the caller ($0 for Claude and Voyage,
        # Exa's list price for the dearer type).
        priced = usage if usage is not None else failed_attempt_usage(service, model_for(purpose), 0)
        cost = round(price(priced), COST_DIGITS)
        settled = False
        try:
            await self.store.settle(self.reservation, cost)
            settled = True
        except Exception as e:
            log.warning("run %s: a cost of %.6f could not be settled (%s); tried again at the end", self.run_id,
                        cost, _kind(e))
        finally:
            # Any failure or cancellation mid-settle: the cost is kept, so the end settles it or stays counted.
            # The call counts as recorded only once its cost is held (T3.4).
            if not settled:
                self._unsettled += cost
            self._totals.add(service, purpose, priced, cost)
            self._in_flight = max(0, self._in_flight - 1)
        if priced.estimated:
            shown = None                   # an estimate is ours, never shown as the provider's usage (v1.2)
        elif raw_usage is None and service == "voyage":
            shown = {"total_tokens": usage.input_tokens}
        else:
            shown = raw_usage
        data: dict = {}
        if call_no is not None:
            data["call_no"] = call_no
        data.update({"service": service, "purpose": purpose, "attempt": attempt, "max_attempts": max_attempts,
                     "outcome": outcome, "error_kind": error_kind, "duration_ms": max(0, int(duration_ms)),
                     "usage": shown, "cost_usd": cost, "estimated": bool(priced.estimated)})
        await self.emit("paid_call", data)
        log.info("run %s paid call: %s %s attempt %d %s, %.6f USD, %d ms", self.run_id, service, purpose, attempt,
                 outcome, cost, max(0, int(duration_ms)))
        return cost

    def totals(self) -> dict:
        return self._totals.as_dict()

    # --- the run task and its end ----------------------------------------------------------------------------------
    async def _main(self) -> None:
        outcome = "normal"
        try:
            await self._execute_run(self, self._loop_deps)
            if self._ended is None:
                log.error("run %s: the loop returned without run_ended", self.run_id)
                await self._emit_failed("internal")
        except asyncio.CancelledError:
            outcome = "cancelled"
            raise
        except Exception as e:
            outcome = "error"
            log.error("run %s: the loop raised (%s)", self.run_id, _kind(e))
            if self._ended is None:
                # an unexpected exception in our own code is `internal` (contract v1.2)
                kind = e.kind if isinstance(e, ServiceError) and e.kind in ERROR_KINDS else "internal"
                try:
                    await self._emit_failed(kind)
                except Exception as e2:
                    log.error("run %s: could not emit run_ended (%s)", self.run_id, _kind(e2))
        finally:
            self._closing = asyncio.ensure_future(self._finish(outcome))
            await asyncio.shield(self._closing)

    async def _emit_failed(self, failure_reason: str | None) -> None:
        """H's `run_ended` with state `failed` (contract §4.H)."""
        await self.emit("run_ended", {
            "state": "failed", "stop_kind": None, "stop_kinds": [], "no_sources_reason": None, "note": None,
            "scope_note": None,
            "answer_end": "none", "failure_reason": failure_reason, "rounds": rounds_of(self._events),
            "answer_chars": answer_chars_of(self._events), "totals": self.totals()})

    async def _release(self) -> None:
        try:
            await self.store.release(self.reservation)
            self.reservation_released = True
        except Exception as e:                 # it stays counted: the safe side; spend_report lists it
            log.error("run %s: the reservation could not be released (%s)", self.run_id, _kind(e))

    async def _settle_and_release(self, abnormal: bool) -> None:
        try:
            await self._settle_and_release_inner(abnormal)
        finally:
            self.money_done.set()

    async def _settle_and_release_inner(self, abnormal: bool) -> None:
        if self._unsettled > 0:
            try:
                await self.store.settle(self.reservation, round(self._unsettled, COST_DIGITS))
                self._unsettled = 0.0
            except Exception as e:
                log.error("run %s: %.6f of spend could not be settled (%s); the reservation stays counted",
                          self.run_id, self._unsettled, _kind(e))
                return
        if abnormal and self._in_flight > 0:
            log.error("run %s: ended with a paid call cleared but not recorded; the reservation stays counted",
                      self.run_id)
            return
        await self._release()

    @staticmethod
    def _stops_to_record(ended: dict) -> list[str]:
        """Each kind in `run_ended.stop_kinds`, once, in order; `stop_kind` when the list is absent (v1.4). The cap
        refusals (`reserve`) and `exa_no_credit` (D) are recorded elsewhere."""
        kinds = ended.get("stop_kinds")
        if not isinstance(kinds, list):
            kinds = [ended.get("stop_kind")]
        out: list[str] = []
        for k in kinds:
            if isinstance(k, str) and k and k not in RECORDED_ELSEWHERE and k not in out:
                out.append(k)
        return out

    async def _finish(self, outcome: str) -> None:
        """Every end: the spend-limit pause, the money, the last events to Atlas, the stop, the run record."""
        try:
            ended = self._ended or {}
            state = ended.get("state") or ("interrupted" if outcome == "cancelled" else "failed")
            stop_kind = ended.get("stop_kind")
            now = self.clock.now()
            if state == "spend_limit":
                # T3.3, T5.4: a spend limit pauses live research until the 1st; set before the release, so no new
                # run can reserve in between. Both stop kinds of the state (console_spend_limit, tier_spend_cap).
                try:
                    await self.store.set_flag("anthropic_spend_limit", now)
                except Exception as e:
                    log.error("run %s: could not set the spend-limit flag (%s)", self.run_id, _kind(e))
            await self._settle_and_release(abnormal=outcome != "normal")
            # the last events reach Atlas before the stop and the record (v1.2)
            self._queue.put_nowait(_STOP)
            if self._writer is not None:
                try:
                    await self._writer
                except Exception as e:
                    log.error("run %s: the event copy ended badly (%s)", self.run_id, _kind(e))
            for kind in self._stops_to_record(ended):
                try:
                    await self.store.record_stop(kind, self.run_id, now, {
                        "state": state, "rounds": rounds_of(self._events),
                        "cost_usd": self._totals.total_cost()})
                except Exception as e:
                    log.error("run %s: could not record the %s stop (%s)", self.run_id, kind, _kind(e))
            try:
                await self.store.upsert_run_record(run_record(
                    self.run_id, self.started_at, state, stop_kind, self._events, self._totals, self.corpus_label))
            except Exception as e:
                log.error("run %s: could not write the run record (%s)", self.run_id, _kind(e))
            elapsed = self.clock.monotonic() - (self._t0 or self.created_mono)
            log.info("run %s ended: state=%s stop_kind=%s cost=%.6f USD, %.1f s, released=%s", self.run_id, state,
                     stop_kind, self._totals.total_cost(), elapsed, self.reservation_released)
        finally:
            self.money_done.set()
            self.state = "finished"
            self.finished_mono = self.clock.monotonic()
            self.finished.set()
            self._notify()
