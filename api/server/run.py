"""One run on this instance (contract §4.H): its state, event buffer, Atlas copy, heartbeat, deadline, admission, slot
and totals. `Run` is the `RunContext` the loop (G) and the search parts (C, D) are given.

The honesty-critical rules live here:
- `before_paid_call` checks, in this order: abandoned, past the deadline (never for composition), unattended (T3.2).
  Nothing is spent while nobody is watching: an unattended run pauses before the call and resumes only on a
  heartbeat that came after the pause began; with none it is abandoned ABANDON_AFTER_S after the last heartbeat.
  It never looks at the caps: a run in progress always finishes (P4.21). One lock serialises the check, so the update
  step and the composition calling together make one `paused` and one `resumed`, not two.
- `record_usage` is the one place spend is priced (E's `price`), recorded in Atlas call by call (`record_spend`),
  totalled, and emitted as `paid_call` (T3.4). Atlas failing once stops the run's spend calls: every later cost, and the
  one that failed, is kept and recorded once as a sum when the run ends, then logged as lost if that fails too (P4.21).
- The run's slot (the registry's count of runs in progress, `busy` at MAX_CONCURRENT_RUNS) is freed once the run has
  ended: on every path, in a `finally`, and on expiry of a run nothing attached to (P4.21).
- Events are numbered from 1 with no gaps, kept in memory for the stream and copied to Atlas in order by one
  background writer, so a slow or failed Atlas write never holds up the stream or stops the run (T3.1). `emit` never
  awaits, so two branches calling it at once are numbered in the order of the calls.

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
from api.protocols import Admission, Store
from api.server.clock import Clock, wait_event
from api.server.summary import answer_chars_of, rounds_of, run_record, update_stop_kind_of
from api.server.totals import COST_DIGITS, SERVICE_OF_PURPOSE, Totals, model_for
from api.state.clock import CHICAGO
from api.state.prices import failed_attempt_usage, price
from api.types import STEP_OF_PURPOSE, CallOutcome, CorpusLabel, Purpose, RunFlags, RunStopped, Service, Usage

log = logging.getLogger("api.server.run")

ERROR_KINDS = frozenset(get_args(ErrorKind))
# Stops recorded by someone else (contract §8): the cap refusals by `admit`, the Exa credit stop by D.
RECORDED_ELSEWHERE = frozenset({"daily_cap", "monthly_cap", "exa_no_credit", "atlas_unreachable"})
_STOP = object()


def _f(name: str) -> float:
    """A figure from api/settings.py, read when used."""
    return float(getattr(settings, name).value)


def _kind(e: BaseException) -> str:
    """What a log may say about an error: its kind, never its message (T3.7; E's errors can name hosts)."""
    return e.kind if isinstance(e, ServiceError) else type(e).__name__


# The two spend kinds of api/protocols.StopKind (the same pair as api/loop/run.py SPEND_STOP's values).
SPEND_STOP_KINDS = frozenset({"console_spend_limit", "tier_spend_cap"})


def estimated_usage(priced: Usage) -> dict | None:
    """v1.6: the tokens an estimated Claude attempt was priced at, ours and never shown as Claude's `usage`, so the
    totals can be summed again from the stored events (the `interrupted` ending)."""
    if not priced.estimated:
        return None
    return {"input_tokens": priced.input_tokens,
            "cache_creation_input_tokens": priced.cache_write_5m_tokens + priced.cache_write_1h_tokens,
            "cache_read_input_tokens": priced.cache_read_tokens, "output_tokens": priced.output_tokens}

class Run:
    """A run held by this instance. States: created (admitted, nothing attached), running, finished; or expired
    (nothing ever attached, T3.1)."""

    def __init__(self, *, run_id: str, question: str, update_check_available: bool, corpus_label: CorpusLabel,
                 store: Store, admission: Admission, clock: Clock,
                 execute_run: Callable[[Any, Any], Awaitable[None]], loop_deps: Any,
                 event_validator: Callable[[dict], None] | None = None,
                 on_expired: Callable[["Run"], None] | None = None,
                 release_slot: Callable[[], None] | None = None):
        # RunContext (api/types.py)
        self.run_id = run_id
        self.question = question
        self.update_check_available = update_check_available
        self.corpus_label = corpus_label
        self.flags = RunFlags()

        self.store = store
        self.admission = admission
        self.clock = clock
        self._execute_run = execute_run
        self._loop_deps = loop_deps
        self._validator = event_validator
        self._on_expired = on_expired
        self._release_slot = release_slot

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
        self._kept = 0.0             # costs Atlas did not take (P4.21): recorded once, as one sum, when the run ends
        self._spend_dead = False     # Atlas failed a spend write: no more spend calls for this run (contract §4.H)
        self._money_closed = False   # the kept costs were recorded at the end: a later cost is written on its own
        self._entered = False        # the run task reached the first line of `_main`
        self._watchdog: asyncio.Task | None = None
        self._watchdog_fired = False
        self._ended: dict | None = None

        self._queue: asyncio.Queue = asyncio.Queue()
        self._task: asyncio.Task | None = None
        self._writer: asyncio.Task | None = None
        self._expiry: asyncio.Task | None = None
        self._closing: asyncio.Future | None = None
        self.finished = asyncio.Event()

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
        self._watchdog = asyncio.create_task(self._watch())
        log.info("run %s started", self.run_id)

    async def _watch(self) -> None:
        """A run still in progress RUN_WATCHDOG_S after its task started is cancelled, and `_main` ends it `failed`
        (`internal`) through the normal end, freeing its slot (contract §4.H, v2.0)."""
        await self.clock.sleep(_f("RUN_WATCHDOG_S"))
        if self._task is not None and not self._task.done() and self._ended is None:
            self._watchdog_fired = True
            log.error("run %s: still in progress %.0f s after it started; cancelling it", self.run_id,
                      _f("RUN_WATCHDOG_S"))
            self._task.cancel()

    async def _expire_after_wait(self) -> None:
        await self.clock.sleep(_f("UNATTACHED_RUN_EXPIRY_S"))
        await self.expire("unattached")

    async def expire(self, why: str) -> None:
        """A run nothing attached to: no spend, its slot freed (T3.1)."""
        if self.state != "created":
            return
        self.state = "expired"
        if self._expiry is not None and self._expiry is not asyncio.current_task():
            self._expiry.cancel()
        self._closing = asyncio.ensure_future(self._expire_inner(why))
        await asyncio.shield(self._closing)

    async def _expire_inner(self, why: str) -> None:
        try:
            log.info("run %s expired (%s): nothing spent, slot freed", self.run_id, why)
        finally:
            self.free_slot()
            self.finished_mono = self.clock.monotonic()
            self.finished.set()
            self._notify()
            if self._on_expired is not None:
                self._on_expired(self)

    def free_slot(self) -> None:
        """Give the run's place among the runs in progress back; safe to call twice (contract §4.H)."""
        if self._release_slot is not None:
            try:
                self._release_slot()
            except Exception as e:                      # a count must never stop an end
                log.error("run %s: the slot could not be freed (%s)", self.run_id, _kind(e))

    def cancel(self) -> None:
        """Shutdown: a running run is cancelled; its `finally` still records its kept costs and frees its slot. A task
        cancelled before it first ran never reaches that `finally`, so the end is run directly for it (v2.0)."""
        if self._task is not None and not self._task.done():
            self._task.cancel()
            if not self._entered and self._closing is None:
                self._closing = asyncio.ensure_future(self._finish("cancelled"))

    # --- RunContext: events ----------------------------------------------------------------------------------------
    async def emit(self, kind: str, data: dict) -> int:
        """Number, time-stamp, buffer and queue one event (contract §6). Never waits on Atlas, and never awaits at all:
        the update step and the composition may call it together, and the numbers follow the order of the calls."""
        if self._t0 is None:
            raise RuntimeError("the run has not started")
        if self._ended is not None:
            raise RuntimeError("the run has already ended")
        n = len(self._events) + 1
        env = {"v": 2, "run": self.run_id, "n": n,
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
        # One lock: the update step and the composition may call together, and one pause emits one `paused` and one
        # `resumed` however many calls wait on it (contract v2.0). The caps are never looked at (P4.21).
        async with self._gate:
            while True:
                if self.abandoned:                                                   # 1
                    raise RunStopped("abandoned")
                if purpose != "composition" and self.seconds_left() <= 0:            # 2 (T3.5): every other purpose
                    raise RunStopped("deadline")
                if await self._attended():                                           # 3
                    break
                await self._pause()       # returns on a heartbeat, then the checks run again; raises when abandoned

    async def call_not_billed(self, service: Service, purpose: Purpose) -> None:
        """A call the gate cleared that was never made or billed (Exa's 402 or 401, contract v1.4). Nothing is
        recorded; with no reservation there is nothing to undo (v2.0)."""

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

    # --- RunContext: money (T3.3, T3.4, P4.21) -------------------------------------------------------------------
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
        self._totals.add(service, purpose, priced, cost)      # held before any await: a cancellation keeps the call
        if priced.estimated:
            shown = None                   # an estimate is ours, never shown as the provider's usage (v1.2)
        elif raw_usage is None and service == "voyage":
            shown = {"total_tokens": usage.input_tokens}
        else:
            shown = raw_usage
        data: dict = {"step": STEP_OF_PURPOSE[purpose]}
        if call_no is not None:
            data["call_no"] = call_no
        data.update({"service": service, "purpose": purpose, "attempt": attempt, "max_attempts": max_attempts,
                     "outcome": outcome, "error_kind": error_kind, "duration_ms": max(0, int(duration_ms)),
                     "usage": shown, "estimated_usage": estimated_usage(priced) if service == "anthropic" else None,
                     "cost_usd": cost, "estimated": bool(priced.estimated)})
        # The event first (it never awaits), then the write to Atlas: a cancellation during the write cannot lose the
        # event, and the write keeps the cost (v2.0). A call after the run's end cannot be emitted; its cost is still
        # recorded, and the error `emit` raises goes on to the caller, as for any event after `run_ended`.
        emit_error: Exception | None = None
        try:
            await self.emit("paid_call", data)
        except Exception as e:
            emit_error = e
            log.error("run %s: a paid call of %.6f USD came after the run's end and has no event (%s)", self.run_id,
                      cost, _kind(e))
        await self._record_spend(cost)
        if emit_error is not None:
            raise emit_error
        log.info("run %s paid call: %s %s attempt %d %s, %.6f USD, %d ms", self.run_id, service, purpose, attempt,
                 outcome, cost, max(0, int(duration_ms)))
        return cost

    async def _record_spend(self, cost: float) -> None:
        """One paid call's cost to Atlas. A failure is logged by kind and the cost kept; from then on this run makes no
        more spend calls to Atlas, so a dead Atlas costs the run no 5 s timeouts, and every later cost is kept too
        (contract §4.H). The kept costs are recorded at the end, once, as one sum."""
        if cost <= 0:
            return
        if self._money_closed:
            await self._record_late(cost)
            return
        if self._spend_dead:
            self._kept += cost
            return
        recorded = False
        try:
            await self.store.record_spend(self.admission, cost)
            recorded = True
        except Exception as e:
            self._spend_dead = True
            log.warning("run %s: a cost of %.6f could not be recorded (%s); kept, and no more spend calls for this run",
                        self.run_id, cost, _kind(e))
        finally:
            if not recorded:               # a failure, or a cancellation mid-write: the cost is kept, never dropped
                self._kept += cost

    async def _record_late(self, cost: float) -> None:
        """A cost that arrives after the end already recorded the kept costs (a branch still running, a call in flight
        when the run was cancelled): written on its own, once, and logged as lost if Atlas cannot take it."""
        log.error("run %s: a cost of %.6f arrived after the run's end; recording it on its own", self.run_id, cost)
        try:
            await self.store.record_spend(self.admission, cost)
        except Exception as e:
            log.error("run %s: %.6f of spend is lost; Atlas could not take it (%s)", self.run_id, cost, _kind(e))

    async def _record_kept(self) -> None:
        """The costs Atlas did not take, as one sum, once; logged as lost if that fails too (P4.21 accepts it)."""
        if self._kept <= 0:
            return
        amount = round(self._kept, COST_DIGITS)
        try:
            await self.store.record_spend(self.admission, amount)
            self._kept = max(0.0, self._kept - amount)       # a cost kept meanwhile stays kept
            log.info("run %s: %.6f of kept spend recorded at the end", self.run_id, amount)
        except Exception as e:
            log.error("run %s: %.6f of spend is lost; Atlas could not take it (%s)", self.run_id, amount, _kind(e))

    def totals(self) -> dict:
        return self._totals.as_dict()

    # --- the run task and its end ----------------------------------------------------------------------------------
    async def _main(self) -> None:
        self._entered = True
        outcome = "normal"
        try:
            await self._execute_run(self, self._loop_deps)
            if self._ended is None:
                log.error("run %s: the loop returned without run_ended", self.run_id)
                await self._emit_failed("internal")
        except asyncio.CancelledError:
            if not self._watchdog_fired or self._ended is not None:
                outcome = "cancelled"
                raise
            # the watchdog's cancel: the run ends failed (internal) through the normal end, and the task finishes
            outcome = "error"
            try:
                await self._emit_failed("internal")
            except Exception as e2:
                log.error("run %s: could not emit run_ended (%s)", self.run_id, _kind(e2))
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
            if self._closing is None:
                self._closing = asyncio.ensure_future(self._finish(outcome))
            await asyncio.shield(self._closing)

    async def _emit_failed(self, failure_reason: str | None) -> None:
        """H's `run_ended` with state `failed` (contract §4.H)."""
        await self.emit("run_ended", {
            "state": "failed", "stop_kind": None, "stop_kinds": [], "no_sources_reason": None, "note": None,
            "scope_note": None,
            "answer_end": "none", "failure_reason": failure_reason, "rounds": rounds_of(self._events),
            "answer_chars": answer_chars_of(self._events), "totals": self.totals()})

    @staticmethod
    def _stops_to_record(ended: dict, update_stop: str | None = None) -> list[str]:
        """Each kind in `run_ended.stop_kinds`, once, in order; `stop_kind` when the list is absent (v1.4); then the
        update step's own stop (its `update_ended.stop_kind`) if the list lacks it (v2.0). The cap refusals (`admit`)
        and `exa_no_credit` (D) are recorded elsewhere."""
        kinds = ended.get("stop_kinds")
        if not isinstance(kinds, list):
            kinds = [ended.get("stop_kind")]
        kinds = list(kinds) + [update_stop]
        out: list[str] = []
        for k in kinds:
            if isinstance(k, str) and k and k not in RECORDED_ELSEWHERE and k not in out:
                out.append(k)
        return out

    async def _finish(self, outcome: str) -> None:
        """Every end: the spend-limit pause, the kept costs, the slot, the last events to Atlas, the stops, the run
        record."""
        try:
            ended = self._ended or {}
            state = ended.get("state") or ("interrupted" if outcome == "cancelled" else "failed")
            stop_kind = ended.get("stop_kind")
            now = self.clock.now()
            stops = self._stops_to_record(ended, update_stop_kind_of(self._events))
            if state == "spend_limit" or SPEND_STOP_KINDS & set(stops):
                # T3.3, T5.4: a spend limit pauses live research until the 1st; set before the slot is freed, so no new
                # run can be admitted in between. Whichever step met it: research, the composition (after its first
                # block the run is answered, v1.4) or the update step beside it (v2.0).
                try:
                    await self.store.set_flag("anthropic_spend_limit", now)
                except Exception as e:
                    log.error("run %s: could not set the spend-limit flag (%s)", self.run_id, _kind(e))
            await self._record_kept()
            self._money_closed = True
            self.free_slot()
            # the last events reach Atlas before the stops and the record (v1.2)
            self._queue.put_nowait(_STOP)
            if self._writer is not None:
                try:
                    await self._writer
                except Exception as e:
                    log.error("run %s: the event copy ended badly (%s)", self.run_id, _kind(e))
            for kind in stops:
                try:
                    await self.store.record_stop(kind, self.run_id, now, {
                        "state": state, "rounds": rounds_of(self._events),
                        "cost_usd": self._totals.total_cost()})
                except Exception as e:
                    log.error("run %s: could not record the %s stop (%s)", self.run_id, kind, _kind(e))
            await self._write_record(state, stop_kind)
            elapsed = self.clock.monotonic() - (self._t0 or self.created_mono)
            log.info("run %s ended: state=%s stop_kind=%s cost=%.6f USD, %.1f s", self.run_id, state,
                     stop_kind, self._totals.total_cost(), elapsed)
        finally:
            if self._watchdog is not None and self._watchdog is not asyncio.current_task():
                self._watchdog.cancel()
            self._money_closed = True
            self.free_slot()                  # on every path, a failure of the bookkeeping above included
            self.state = "finished"
            self.finished_mono = self.clock.monotonic()
            self.finished.set()
            self._notify()

    async def _write_record(self, state: str, stop_kind: str | None) -> None:
        record = run_record(self.run_id, self.started_at, state, stop_kind, self._events, self._totals,
                            self.corpus_label)
        try:
            await self.store.upsert_run_record(record)
        except Exception as e:
            log.error("run %s: could not write the run record (%s)", self.run_id, _kind(e))
