"""The Atlas store, twice: MongoStore (pymongo's AsyncMongoClient) and MemoryStore (the fake) (contract §4.E, §8).

Both implement `api.protocols.Store` with the same meaning, which `tests/state/cases.py` states once and runs
against both (and against the real Atlas test database when PC_ATLAS_TEST=1).

Money (T3.4):
- `reserve` is one conditional update of the month's document: it succeeds only if, for the Chicago day and the
  month, spent + reserved + the run's worst case stays within the caps. It counts `runs_started` in the same update.
  A refusal is diagnosed afterwards from the document and recorded as a budget stop.
- `settle` moves a call's cost from the run's reservation to spent, never moving more than the reservation holds
  (spend beyond it is still counted); `release` frees what is left. A reservation never settled stays counted, and
  spend counts toward the Chicago day and month the run started in (the `Reservation` carries both).
- If Atlas cannot be reached the run is refused (fail closed) and that is recorded, where it can be, as not a
  budget stop.

Beyond the protocol, both classes offer what tests and scripts/spend_report.py read: `read_month`, `read_stops`,
`get_run_record`.

Records never hold the question or the answer text (T3.7): `upsert_run_record` and `record_stop` accept only the
shapes allowed in `api/state/records.py` (read its docstring for exactly what to send), and refuse the rest with a
ValueError that names key paths, never values.

Error messages and logs never carry the URI, a host, or Atlas's own error text. Every StoreUnavailable is raised
outside the `except` block that caught the driver's error, so no pymongo, bson or asyncio error is left in its
`__cause__` or `__context__`.

Known safe-side leak: an `update_one` that times out on our side but still lands after `_undo_reserve` has read the
document leaves a reservation counted until it is cleaned by hand. It cannot overspend (only reserved money is
over-counted, never spent money under-counted), and `scripts/spend_report.py --open-reservations` lists it with its age.
"""

import asyncio
import copy
import logging
from datetime import UTC, datetime, timedelta
from typing import Literal

from pymongo import AsyncMongoClient
from pymongo.errors import BulkWriteError, DuplicateKeyError, OperationFailure, PyMongoError

from api import settings
from api.protocols import Refusal, Reservation, StopKind
from api.state import mongo_docs as md
from api.state import rules
from api.state.clock import CHICAGO, chicago_day, chicago_month, next_month_start

log = logging.getLogger(__name__)

FlagName = Literal["exa_out_of_credit", "anthropic_spend_limit"]

class StoreUnavailable(Exception):
    """Atlas could not be reached, answered too slowly, or refused an operation. The message is ours: it never
    carries the URI, a host name, or Atlas's own error text."""


def db_name_for(env) -> str:
    """The database for PC_ENV (contract §8): "live" is Probable_Clause, "test" is Probable_Clause_test."""
    if env == "live":
        return str(settings.ATLAS_DB_LIVE.value)
    if env == "test":
        return str(settings.ATLAS_DB_TEST.value)
    raise ValueError("PC_ENV must be 'live' or 'test'")


def _aware(dt: datetime) -> datetime:
    """A date read back from BSON: always UTC, whether or not the driver marked it so."""
    return dt.replace(tzinfo=UTC) if dt.tzinfo is None else dt


def _keys(now: datetime) -> tuple[str, str]:
    return chicago_month(now), chicago_day(now)      # raises ValueError for a naive datetime


def _check_events(run_id: str, events: list[dict]) -> None:
    rules.check_run_id(run_id)
    for e in events:
        n = e.get("n") if isinstance(e, dict) else None
        if isinstance(n, bool) or not isinstance(n, int) or n < 1:
            raise ValueError("an event needs an integer n of 1 or more")
        if e.get("run", run_id) != run_id:
            raise ValueError("an event belongs to another run")


def _tries() -> int:
    """Compare-and-swap rounds, and upsert attempts, before Atlas counts as unreachable (api/settings.py)."""
    return int(settings.ATLAS_RESERVE_TRIES.value)


def _clean_stop(doc: dict) -> dict:
    doc = dict(doc)
    doc.pop("_id", None)
    doc["at"] = _aware(doc["at"]).astimezone(CHICAGO)
    return doc


def _stops_matching(docs: list[dict], day: str | None, month: str | None) -> list[dict]:
    if (day is None) == (month is None):
        raise ValueError("give exactly one of day and month")
    if day is not None:
        sel = [d for d in docs if d["date"] == day]
    else:
        sel = [d for d in docs if d["date"].startswith(month + "-")]
    return sorted((_clean_stop(d) for d in sel), key=lambda d: d["at"])


def _open_from(docs: list[dict], now: datetime) -> list[dict]:
    out = []
    for doc in docs:
        for run, entry in (doc.get("reservations") or {}).items():
            at = _aware(entry["at"]).astimezone(CHICAGO) if entry.get("at") else None
            out.append({"run": run, "month": doc["_id"], "day": entry["day"], "amount": entry["amount"], "at": at,
                        "age_s": (now - at).total_seconds() if at else None})
    out.sort(key=lambda o: (o["at"] is None, o["at"]))
    return out


# ======================================================================================================================
class MemoryStore:
    """The fake every other part tests against. Same semantics as MongoStore.

    No method awaits between reading and writing its state, so each is atomic the way one Atlas update is; every
    method first awaits `latency_s` (default: one trip round the event loop), so concurrent callers genuinely
    interleave. `unreachable = True` simulates a dead Atlas; `expire(now)` plays the part of its TTL monitor.
    """

    def __init__(self, *, latency_s: float = 0.0, clock=None):
        self.latency_s = latency_s
        self.unreachable = False
        self._clock = clock or (lambda: datetime.now(UTC))
        self._events: dict[str, dict[int, dict]] = {}
        self._heartbeats: dict[str, dict] = {}
        self._runs: dict[str, dict] = {}
        self._spend: dict[str, dict] = {}
        self._stops: list[dict] = []
        self._flags: dict[str, dict] = {}

    async def _io(self):
        await asyncio.sleep(self.latency_s)
        if self.unreachable:
            raise StoreUnavailable("the store is unreachable (simulated)")

    def expire(self, now: datetime) -> None:
        """What Atlas's TTL indexes do (T3.7): drop events 24 h after `created` and heartbeats 10 min after `at`."""
        ev = timedelta(seconds=int(settings.EVENTS_TTL_S.value))
        hb = timedelta(seconds=int(settings.HEARTBEATS_TTL_S.value))
        for run in list(self._events):
            self._events[run] = {n: d for n, d in self._events[run].items() if d["created"] + ev > now}
            if not self._events[run]:
                del self._events[run]
        self._heartbeats = {r: d for r, d in self._heartbeats.items() if d["at"] + hb > now}

    # --- internals ---------------------------------------------------------------------------------------------------
    def _month(self, month: str) -> dict:
        if month not in self._spend:
            self._spend[month] = {"_id": month, **rules.month_defaults(), "days": {}}
        return self._spend[month]

    @staticmethod
    def _day(doc: dict, day: str) -> dict:
        d = doc["days"].setdefault(day, rules.day_defaults())
        for k, v in rules.day_defaults().items():
            d.setdefault(k, v)
        return d

    def _flag_until(self, name: str, now: datetime) -> datetime | None:
        f = self._flags.get(name)
        return f["until"] if f and f["until"] > now else None

    def _write_stop(self, kind: str, run_id: str | None, now: datetime, totals, detail: dict) -> None:
        self._stops.append(rules.stop_document(kind, run_id, now.astimezone(UTC), totals, copy.deepcopy(detail)))
        day = self._day(self._month(chicago_month(now)), chicago_day(now))
        stops = day.setdefault("stops", {})
        stops[kind] = stops.get(kind, 0) + 1

    # --- events and heartbeats -----------------------------------------------------------------------------------------
    async def ensure_indexes(self) -> None:
        await self._io()

    async def append_events(self, run_id: str, events: list[dict]) -> None:
        _check_events(run_id, events)
        await self._io()
        store = self._events.setdefault(run_id, {})
        for e in events:
            if e["n"] not in store:       # a repeated batch is a no-op: the first write stands
                store[e["n"]] = {**copy.deepcopy(e), "run": run_id, "created": self._clock()}

    async def read_events(self, run_id: str, after: int) -> list[dict]:
        rules.check_run_id(run_id)
        await self._io()
        docs = self._events.get(run_id, {})
        out = []
        for n in sorted(docs):
            if n > after:
                d = copy.deepcopy(docs[n])
                d.pop("created", None)
                out.append(d)
        return out

    async def put_heartbeat(self, run_id: str, last_event: int, now: datetime) -> None:
        rules.check_run_id(run_id)
        _keys(now)
        await self._io()
        self._heartbeats[run_id] = {"run": run_id, "last_event": last_event, "at": now.astimezone(UTC)}

    async def latest_heartbeat(self, run_id: str) -> datetime | None:
        rules.check_run_id(run_id)
        await self._io()
        hb = self._heartbeats.get(run_id)
        return hb["at"].astimezone(CHICAGO) if hb else None

    async def upsert_run_record(self, record: dict) -> None:
        run = rules.check_run_record(record)
        await self._io()
        self._runs[run] = copy.deepcopy(record)

    async def get_run_record(self, run_id: str) -> dict | None:
        rules.check_run_id(run_id)
        await self._io()
        r = self._runs.get(run_id)
        return copy.deepcopy(r) if r else None

    # --- money ---------------------------------------------------------------------------------------------------------
    async def reserve(self, run_id: str, worst_case_usd: float, now: datetime) -> Reservation | Refusal:
        rules.check_run_id(run_id)
        worst = rules.check_worst(worst_case_usd)
        month, day = _keys(now)
        try:
            await self._io()
        except StoreUnavailable:
            self._write_stop("atlas_unreachable", run_id, now, None, {})
            return Refusal("atlas_unreachable")
        # nothing below awaits: like one conditional update, it cannot be interleaved
        if self._flag_until("anthropic_spend_limit", now):
            return Refusal("spend_limit_paused")
        doc = self._spend.get(month)
        if doc and run_id in doc["reservations"]:
            raise ValueError("this run already holds a reservation")
        verdict = rules.cap_verdict(doc, day, worst)
        if verdict:
            self._write_stop(verdict, run_id, now, rules.day_totals(doc, day), {})
            return Refusal(verdict)
        doc = self._month(month)
        d = self._day(doc, day)
        doc["reserved"] += worst
        d["reserved"] += worst
        d["runs_started"] += 1
        doc["reservations"][run_id] = {"day": day, "amount": worst, "at": now.astimezone(UTC)}
        return Reservation(run_id, month, day, worst)

    async def settle(self, r: Reservation, cost_usd: float) -> None:
        rules.check_run_id(r.run_id)
        cost = rules.check_cost(cost_usd)
        await self._io()
        if cost == 0:
            return
        doc = self._month(r.month)
        d = self._day(doc, r.day)
        entry = doc["reservations"].get(r.run_id)
        moved = min(cost, entry["amount"]) if entry else 0.0
        doc["spent"] += cost
        d["spent"] += cost
        if moved > 0:
            doc["reserved"] -= moved
            d["reserved"] -= moved
            entry["amount"] -= moved

    async def release(self, r: Reservation) -> None:
        rules.check_run_id(r.run_id)
        await self._io()
        doc = self._spend.get(r.month)
        entry = doc["reservations"].pop(r.run_id, None) if doc else None
        if entry:
            doc["reserved"] -= entry["amount"]
            self._day(doc, entry["day"])["reserved"] -= entry["amount"]

    async def open_reservations(self, now: datetime) -> list[dict]:
        _keys(now)
        await self._io()
        return _open_from(copy.deepcopy(list(self._spend.values())), now)

    async def record_stop(self, kind: StopKind, run_id: str | None, now: datetime, detail: dict) -> None:
        rules.check_stop_kind(kind)
        if run_id is not None:
            rules.check_run_id(run_id)
        rules.check_stop_detail(detail)
        month, day = _keys(now)
        await self._io()
        self._write_stop(kind, run_id, now, rules.day_totals(self._spend.get(month), day), detail)

    # --- flags and /health -----------------------------------------------------------------------------------------------
    async def flag_until(self, name: FlagName, now: datetime) -> datetime | None:
        rules.check_flag_name(name)
        _keys(now)
        await self._io()
        until = self._flag_until(name, now)
        return until.astimezone(CHICAGO) if until else None

    async def set_flag(self, name: FlagName, now: datetime) -> None:
        rules.check_flag_name(name)
        until = next_month_start(now)
        await self._io()
        self._flags[name] = {"until": until.astimezone(UTC), "set_at": now.astimezone(UTC)}

    async def live_status(self, now: datetime, worst_case_usd: float, timeout_s: float) -> dict:
        month, day = _keys(now)
        try:
            async with asyncio.timeout(timeout_s):
                await self._io()
                return rules.health_view(self._spend.get(month),
                                         self._flag_until("anthropic_spend_limit", now) is not None,
                                         self._flag_until("exa_out_of_credit", now) is not None, day, worst_case_usd)
        except (TimeoutError, StoreUnavailable):
            return dict(rules.UNKNOWN_HEALTH)

    # --- reads for reports and tests ---------------------------------------------------------------------------------------
    async def read_month(self, month: str) -> dict | None:
        await self._io()
        doc = self._spend.get(month)
        return copy.deepcopy(doc) if doc else None

    async def read_stops(self, *, day: str | None = None, month: str | None = None) -> list[dict]:
        await self._io()
        return _stops_matching(copy.deepcopy(self._stops), day, month)


# ======================================================================================================================
class MongoStore:
    """Atlas, through pymongo's AsyncMongoClient (T3.4, T3.5). The caller chooses the database by name
    (`db_name_for("live" | "test")`); every operation is cut off at `ATLAS_OP_TIMEOUT_S` (a placeholder in
    api/settings.py: pymongo's own default is 30 s).

    `db` and `prefix` are test seams: `db` replaces the client (tests/state/fakes.py), and `prefix` is put in
    front of every collection name so a test on the real test database touches only collections of its own.
    """

    def __init__(self, uri: str | None = None, db_name: str | None = None, *, db=None, prefix: str = "",
                 op_timeout_s: float | None = None, clock=None):
        self._timeout = float(op_timeout_s if op_timeout_s is not None else settings.ATLAS_OP_TIMEOUT_S.value)
        self._prefix = prefix
        self._clock = clock or (lambda: datetime.now(UTC))
        self._client = None
        if db is not None:
            self._db = db
            return
        if not uri or not db_name:
            raise ValueError("a MongoStore needs a URI and a database name")
        ms = int(self._timeout * 1000)
        try:
            self._client = AsyncMongoClient(uri, tz_aware=True, tzinfo=CHICAGO, serverSelectionTimeoutMS=ms,
                                            connectTimeoutMS=ms)
            self._db = self._client[db_name]
            malformed = False
        except Exception:        # the driver's message can quote parts of the URI: say nothing of it
            malformed = True
        if malformed:
            raise ValueError("the Atlas connection string could not be used")

    def __repr__(self) -> str:
        return f"<MongoStore db={getattr(self._db, 'name', '?')!r} prefix={self._prefix!r}>"

    async def close(self) -> None:
        if self._client is not None:
            await self._client.close()

    # --- plumbing ------------------------------------------------------------------------------------------------------
    def _c(self, name: str):
        return self._db[self._prefix + name]

    async def _op(self, aw, passthrough: tuple = ()):
        """Run one Atlas operation with the operation timeout. Every failure becomes StoreUnavailable, except
        the exception types in `passthrough`, which the caller handles itself.

        Any Exception counts, not only pymongo's: bson's errors quote the document that failed to encode (which can
        hold the question), and the driver can raise OverflowError or UnicodeError on data. StoreUnavailable is
        raised after the `except` block, so nothing the driver raised is left in its `__cause__` or `__context__`.
        """
        problem = None
        try:
            async with asyncio.timeout(self._timeout):
                return await aw
        except passthrough:
            raise
        except TimeoutError:
            problem = "an Atlas operation timed out"
        except Exception as e:
            problem = f"an Atlas operation failed ({type(e).__name__})"
        raise StoreUnavailable(problem)

    async def _upsert(self, coll, flt: dict, update: dict) -> None:
        """An upsert on a unique key can lose a race to another upsert of the same key: it is tried again, as the
        document now exists, up to the shared bound."""
        for _ in range(_tries()):
            try:
                await self._op(coll.update_one(flt, update, upsert=True), passthrough=(DuplicateKeyError,))
                return
            except DuplicateKeyError:
                continue
        raise StoreUnavailable("an Atlas upsert kept colliding")

    # --- indexes --------------------------------------------------------------------------------------------------------
    async def ensure_indexes(self) -> None:
        for spec in md.index_specs():
            coll = self._c(spec.collection)
            problem = None
            ttl_changed = False
            try:
                await self._op(coll.create_index(spec.keys, name=spec.name, **spec.options), passthrough=(OperationFailure,))
            except OperationFailure as e:
                # a TTL whose figure changed in api/settings.py: 85 and 86 are "index exists with other options";
                # collMod is the way to change a TTL in place (any other conflict is not ours to overwrite)
                if "expireAfterSeconds" in spec.options and e.code in (85, 86):
                    ttl_changed = True
                else:
                    problem = f"an Atlas operation failed ({type(e).__name__})"
            if problem:
                raise StoreUnavailable(problem)
            if ttl_changed:
                await self._op(self._db.command({"collMod": self._prefix + spec.collection,
                                                 "index": {"name": spec.name,
                                                           "expireAfterSeconds": spec.options["expireAfterSeconds"]}}))

    # --- events and heartbeats -------------------------------------------------------------------------------------------
    async def append_events(self, run_id: str, events: list[dict]) -> None:
        _check_events(run_id, events)
        if not events:
            return
        created = self._clock()
        docs = [{**copy.deepcopy(e), "run": run_id, "created": created} for e in events]    # `created`: a BSON date (TTL)
        failed = False
        try:
            # unordered, so one repeated event never blocks the rest of a retried batch
            await self._op(self._c("events").insert_many(docs, ordered=False), passthrough=(BulkWriteError,))
        except BulkWriteError as e:
            errors = (e.details or {}).get("writeErrors", [])
            failed = not errors or any(x.get("code") != 11000 for x in errors)     # 11000: already stored, which is fine
        if failed:
            raise StoreUnavailable("an Atlas event write failed")

    async def read_events(self, run_id: str, after: int) -> list[dict]:
        rules.check_run_id(run_id)
        cursor = self._c("events").find({"run": run_id, "n": {"$gt": after}}, {"_id": 0, "created": 0}).sort("n", 1)
        return await self._op(cursor.to_list(None))

    async def put_heartbeat(self, run_id: str, last_event: int, now: datetime) -> None:
        rules.check_run_id(run_id)
        _keys(now)
        await self._upsert(self._c("heartbeats"), {"_id": run_id}, md.heartbeat_update(run_id, last_event, now))

    async def latest_heartbeat(self, run_id: str) -> datetime | None:
        rules.check_run_id(run_id)
        doc = await self._op(self._c("heartbeats").find_one({"_id": run_id}))
        return _aware(doc["at"]).astimezone(CHICAGO) if doc else None

    async def upsert_run_record(self, record: dict) -> None:
        run = rules.check_run_record(record)
        for _ in range(_tries()):
            try:
                await self._op(self._c("runs").replace_one({"run": run}, copy.deepcopy(record), upsert=True),
                               passthrough=(DuplicateKeyError,))
                return
            except DuplicateKeyError:
                continue
        raise StoreUnavailable("an Atlas upsert kept colliding")

    async def get_run_record(self, run_id: str) -> dict | None:
        rules.check_run_id(run_id)
        return await self._op(self._c("runs").find_one({"run": run_id}, {"_id": 0}))

    # --- money ---------------------------------------------------------------------------------------------------------
    async def reserve(self, run_id: str, worst_case_usd: float, now: datetime) -> Reservation | Refusal:
        rules.check_run_id(run_id)
        worst = rules.check_worst(worst_case_usd)
        month, day = _keys(now)
        spend = self._c("spend")
        try:
            if await self._flag_active("anthropic_spend_limit", now):
                return Refusal("spend_limit_paused")
            await self._upsert(spend, {"_id": month}, md.ensure_month_update())
            for _ in range(_tries()):
                try:
                    res = await self._op(spend.update_one(md.reserve_filter(month, day, run_id, worst),
                                                          md.reserve_update(day, run_id, worst, now)))
                except StoreUnavailable:
                    # the update may have been applied with the reply lost: take it back if we can, so a run that
                    # is refused does not leave a reservation counted
                    await self._undo_reserve(month, day, run_id)
                    raise
                if res.matched_count == 1:
                    return Reservation(run_id, month, day, worst)
                doc = await self._op(spend.find_one({"_id": month}))
                if doc and run_id in (doc.get("reservations") or {}):
                    raise ValueError("this run already holds a reservation")
                verdict = rules.cap_verdict(doc, day, worst)
                if verdict:
                    await self._record_stop(verdict, run_id, now, rules.day_totals(doc, day), {}, may_fail=True)
                    return Refusal(verdict)
                # no cap is broken now, so the document changed between the update and the read: try again
            raise StoreUnavailable("no consistent answer from Atlas")
        except StoreUnavailable:
            await self._record_stop("atlas_unreachable", run_id, now, None, {}, may_fail=True)
            return Refusal("atlas_unreachable")

    async def _undo_reserve(self, month: str, day: str, run_id: str) -> None:
        try:
            await self._release_run(month, day, run_id, uncount_start=True)
        except StoreUnavailable:
            log.warning("could not take back a reservation after an unacknowledged update (run %s)", run_id)

    async def _release_run(self, month: str, day: str, run_id: str, uncount_start: bool = False) -> None:
        spend = self._c("spend")
        for _ in range(_tries()):
            doc = await self._op(spend.find_one({"_id": month}, {f"reservations.{run_id}": 1}))
            entry = ((doc or {}).get("reservations") or {}).get(run_id)
            if not entry:
                return                                    # nothing held, or already released
            remaining = entry["amount"]
            res = await self._op(spend.update_one(md.release_filter(month, run_id, remaining),
                                                  md.release_update(entry.get("day", day), run_id, remaining, uncount_start)))
            if res.matched_count == 1:
                return
        # still counted, which is the safe side; the caller is told
        raise StoreUnavailable("a reservation could not be released")

    async def settle(self, r: Reservation, cost_usd: float) -> None:
        rules.check_run_id(r.run_id)
        cost = rules.check_cost(cost_usd)
        if cost == 0:
            return
        spend = self._c("spend")
        # the usual case in one atomic update: the reservation still holds the whole cost
        res = await self._op(spend.update_one(md.settle_full_filter(r.month, r.run_id, cost),
                                              md.settle_full_update(r.day, r.run_id, cost)))
        if res.matched_count == 1:
            return
        # the cost exceeds what is left (or nothing is left): spend all of it, move only what the reservation holds
        for _ in range(_tries()):
            doc = await self._op(spend.find_one({"_id": r.month}, {f"reservations.{r.run_id}": 1}))
            if doc is None:
                break
            entry = (doc.get("reservations") or {}).get(r.run_id)
            remaining = entry["amount"] if entry else None
            moved = min(cost, remaining) if remaining is not None else 0.0
            res = await self._op(spend.update_one(md.settle_clamped_filter(r.month, r.run_id, remaining),
                                                  md.settle_clamped_update(r.day, r.run_id, cost, moved)))
            if res.matched_count == 1:
                return
        # no document, or the swap kept losing: the spend must not be lost; the reservation stays counted
        await self._upsert(spend, {"_id": r.month}, md.settle_spent_only_update(r.day, cost))

    async def release(self, r: Reservation) -> None:
        rules.check_run_id(r.run_id)
        await self._release_run(r.month, r.day, r.run_id)

    async def open_reservations(self, now: datetime) -> list[dict]:
        _keys(now)
        docs = await self._op(self._c("spend").find({}, {"reservations": 1}).to_list(None))
        return _open_from(docs, now)

    async def record_stop(self, kind: StopKind, run_id: str | None, now: datetime, detail: dict) -> None:
        rules.check_stop_kind(kind)
        if run_id is not None:
            rules.check_run_id(run_id)
        rules.check_stop_detail(detail)
        month, day = _keys(now)
        doc = await self._op(self._c("spend").find_one({"_id": month}))
        await self._record_stop(kind, run_id, now, rules.day_totals(doc, day), detail, may_fail=False)

    async def _record_stop(self, kind: str, run_id: str | None, now: datetime, totals, detail: dict, *, may_fail: bool) -> None:
        """One stop record and one count on the day. With may_fail, a failure is logged and swallowed: the caller
        has a refusal to return whatever happens ("where it can", T3.4)."""
        try:
            month, day = _keys(now)
            doc = rules.stop_document(kind, run_id, now.astimezone(UTC), totals, detail)
            await self._op(self._c("budget_stops").insert_one(doc))
            await self._upsert(self._c("spend"), {"_id": month}, md.stop_count_update(day, kind))
        except StoreUnavailable:
            if not may_fail:
                raise
            log.warning("could not record the %s stop (run %s)", kind, run_id)

    # --- flags and /health -------------------------------------------------------------------------------------------------
    async def flag_until(self, name: FlagName, now: datetime) -> datetime | None:
        rules.check_flag_name(name)
        _keys(now)
        doc = await self._op(self._c("flags").find_one({"_id": name}))
        if not doc:
            return None
        until = _aware(doc["until"]).astimezone(CHICAGO)
        return until if until > now else None

    async def _flag_active(self, name: str, now: datetime) -> bool:
        return await self.flag_until(name, now) is not None

    async def set_flag(self, name: FlagName, now: datetime) -> None:
        rules.check_flag_name(name)
        await self._upsert(self._c("flags"), {"_id": name}, md.flag_update(name, next_month_start(now), now))

    async def live_status(self, now: datetime, worst_case_usd: float, timeout_s: float) -> dict:
        month, day = _keys(now)
        try:
            async with asyncio.timeout(timeout_s):
                doc = await self._op(self._c("spend").find_one({"_id": month}))
                spend_limit = await self._flag_active("anthropic_spend_limit", now)
                exa = await self._flag_active("exa_out_of_credit", now)
            return rules.health_view(doc, spend_limit, exa, day, worst_case_usd)
        except (TimeoutError, StoreUnavailable):
            return dict(rules.UNKNOWN_HEALTH)

    # --- reads for reports and tests -----------------------------------------------------------------------------------------
    async def read_month(self, month: str) -> dict | None:
        return await self._op(self._c("spend").find_one({"_id": month}))

    async def read_stops(self, *, day: str | None = None, month: str | None = None) -> list[dict]:
        if (day is None) == (month is None):
            raise ValueError("give exactly one of day and month")
        flt = {"date": day} if day is not None else {"date": {"$gte": f"{month}-01", "$lte": f"{month}-31"}}
        docs = await self._op(self._c("budget_stops").find(flt).sort("at", 1).to_list(None))
        return _stops_matching(docs, day, month)
