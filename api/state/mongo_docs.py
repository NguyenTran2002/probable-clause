"""The filters and updates MongoStore sends, as pure functions (T3.4; contract §8).

Kept apart so they can be tested without a network: tests/state/test_mongo_docs.py applies them to documents with
a small matcher and compares the admit filter with `rules.cap_verdict` over a grid of states.

Days go into dotted paths ("days.<day>.spent"); `rules.check_admission` and the Chicago clock only make "YYYY-MM-DD".
"""

from dataclasses import dataclass
from datetime import UTC, datetime

from api import settings
from api.state import rules


def _utc(dt: datetime) -> datetime:
    return dt.astimezone(UTC)


# --- the spend document (one per Chicago month) -------------------------------------------------------------------------

def ensure_month_update() -> dict:
    """Create the month's document with zeroed totals and no days if it is not there; leave it alone if it is. The
    same shape MemoryStore makes. Used with upsert=True and the plain filter {"_id": month}: Atlas refuses $expr in an
    upsert's filter (code 224). (Not used with `stop_count_update`, whose $inc names paths under `days`.)"""
    return {"$setOnInsert": {**rules.month_defaults(), "days": {}}}


def admit_filter(month: str, day: str) -> dict:
    """The one condition of admission (P4.21): this month's document, its spent strictly under the monthly cap and the
    Chicago day's spent strictly under the daily cap. Every field read is guarded with $ifNull: a missing field
    (no day entry yet, no month yet) must count as zero, not slip under the cap by MongoDB's null ordering.

    NEVER used with upsert=True: Atlas refuses $expr in an upsert's filter (WriteError 224). It matches 0 documents when
    a cap is reached or when the month has no document yet; MongoStore reads the document once to tell which, and
    creates the month with `ensure_month_update` (a plain `_id` upsert) when there is none."""
    def read(path: str):
        return {"$ifNull": [path, 0]}

    return {
        "_id": month,
        "$expr": {"$and": [
            {"$lt": [read("$spent"), float(settings.MONTHLY_CAP_USD.value) - rules.EPS]},
            {"$lt": [read(f"$days.{day}.spent"), float(settings.DAILY_CAP_USD.value) - rules.EPS]},
        ]},
    }


def admit_update(day: str) -> dict:
    """Count the start on the day, in the same update (use without upsert). The zero increments create the day's
    fields, so a day created by an admission always has its whole shape (and no `reserved`, no `reservations`)."""
    return {"$inc": {"spent": 0.0, f"days.{day}.spent": 0.0, f"days.{day}.runs_started": 1}}


def spend_update(day: str, cost: float) -> dict:
    """One paid call's cost, added to the month's and the admitted day's spent (use with upsert)."""
    return {"$inc": {"spent": cost, f"days.{day}.spent": cost, f"days.{day}.runs_started": 0}}


def stop_count_update(day: str, kind: str) -> dict:
    """Count one stop on the day (use with upsert: it also creates the month and the day with their full shape)."""
    return {
        "$inc": {f"days.{day}.stops.{kind}": 1, f"days.{day}.spent": 0.0, f"days.{day}.runs_started": 0},
        "$setOnInsert": rules.month_defaults(),
    }


# --- flags and heartbeats -------------------------------------------------------------------------------------------------

def flag_update(name: str, until: datetime, now: datetime) -> dict:
    return {"$set": {"until": _utc(until), "set_at": _utc(now)}}


def heartbeat_update(run_id: str, last_event: int, now: datetime) -> dict:
    return {"$set": {"run": run_id, "last_event": last_event, "at": _utc(now)}}


# --- indexes (contract §8) ---------------------------------------------------------------------------------------------------

@dataclass(frozen=True)
class IndexSpec:
    collection: str
    name: str
    keys: list
    options: dict


def index_specs() -> list[IndexSpec]:
    """Every index of §8. `spend` and `flags` are looked up by _id, which Atlas indexes itself."""
    return [
        IndexSpec("events", "run_n_unique", [("run", 1), ("n", 1)], {"unique": True}),
        IndexSpec("events", "created_ttl", [("created", 1)], {"expireAfterSeconds": int(settings.EVENTS_TTL_S.value)}),
        IndexSpec("runs", "run_unique", [("run", 1)], {"unique": True}),
        IndexSpec("budget_stops", "at", [("at", 1)], {}),
        IndexSpec("heartbeats", "at_ttl", [("at", 1)], {"expireAfterSeconds": int(settings.HEARTBEATS_TTL_S.value)}),
    ]
