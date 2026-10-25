"""The filters and updates MongoStore sends, as pure functions (T3.4; contract §8).

Kept apart so they can be tested without a network: tests/state/test_mongo_docs.py applies them to documents with
a small matcher and compares the reserve filter with `rules.cap_verdict` over a grid of states.

Run IDs go into dotted paths ("reservations.<run>"); `rules.check_run_id` has already refused any with a "." or "$".
"""

from dataclasses import dataclass
from datetime import UTC, datetime

from api import settings
from api.state import rules


def _utc(dt: datetime) -> datetime:
    return dt.astimezone(UTC)


# --- the spend document (one per Chicago month) -------------------------------------------------------------------------

def ensure_month_update() -> dict:
    """Create the month's document with zeroed totals if it is not there; leave it alone if it is."""
    return {"$setOnInsert": rules.month_defaults()}


def reserve_filter(month: str, day: str, run_id: str, worst: float) -> dict:
    """The one condition of a reservation (T3.4, B1): this month's document, this run holding nothing yet, and
    spent + reserved + the worst case within the monthly cap and within the Chicago day's cap. Every field read is
    guarded with $ifNull: a missing field must count as zero, not slip under the cap."""
    def read(path: str):
        return {"$ifNull": [path, 0]}

    return {
        "_id": month,
        f"reservations.{run_id}": {"$exists": False},
        "$expr": {"$and": [
            {"$lte": [{"$add": [read("$spent"), read("$reserved"), worst]},
                      float(settings.MONTHLY_CAP_USD.value) + rules.EPS]},
            {"$lte": [{"$add": [read(f"$days.{day}.spent"), read(f"$days.{day}.reserved"), worst]},
                      float(settings.DAILY_CAP_USD.value) + rules.EPS]},
        ]},
    }


def reserve_update(day: str, run_id: str, worst: float, at: datetime) -> dict:
    return {
        "$inc": {
            "reserved": worst,
            f"days.{day}.reserved": worst,
            f"days.{day}.spent": 0.0,          # creates the field, so a day always has its whole shape
            f"days.{day}.runs_started": 1,
        },
        "$set": {f"reservations.{run_id}": {"day": day, "amount": worst, "at": _utc(at)}},
    }


def settle_full_filter(month: str, run_id: str, cost: float) -> dict:
    """The common case: the reservation still holds at least this much, so the whole cost moves."""
    return {"_id": month, f"reservations.{run_id}.amount": {"$gte": cost}}


def settle_full_update(day: str, run_id: str, cost: float) -> dict:
    return {"$inc": {"spent": cost, f"days.{day}.spent": cost, "reserved": -cost, f"days.{day}.reserved": -cost,
                     f"reservations.{run_id}.amount": -cost}}


def settle_clamped_filter(month: str, run_id: str, remaining: float | None) -> dict:
    """Compare-and-swap on what was read: `remaining` is the reservation's amount, None if it holds none."""
    if remaining is None:
        return {"_id": month, f"reservations.{run_id}": {"$exists": False}}
    return {"_id": month, f"reservations.{run_id}.amount": remaining}


def settle_clamped_update(day: str, run_id: str, cost: float, moved: float) -> dict:
    """The whole cost is spent; only `moved` (at most what the reservation still holds) leaves reserved, so
    reserved never goes negative and spend beyond a reservation is still counted."""
    inc = {"spent": cost, f"days.{day}.spent": cost}
    if moved > 0:
        inc.update({"reserved": -moved, f"days.{day}.reserved": -moved, f"reservations.{run_id}.amount": -moved})
    return {"$inc": inc}


def settle_spent_only_update(day: str, cost: float) -> dict:
    """Last resort (use with upsert): record the spend and leave the reservation counted."""
    return {"$inc": {"spent": cost, f"days.{day}.spent": cost}, "$setOnInsert": {"reserved": 0.0, "reservations": {}}}


def release_filter(month: str, run_id: str, remaining: float) -> dict:
    return {"_id": month, f"reservations.{run_id}.amount": remaining}


def release_update(day: str, run_id: str, remaining: float, uncount_start: bool = False) -> dict:
    inc = {"reserved": -remaining, f"days.{day}.reserved": -remaining}
    if uncount_start:       # taking back a reservation whose reply was lost: the run did not start
        inc[f"days.{day}.runs_started"] = -1
    return {"$inc": inc, "$unset": {f"reservations.{run_id}": ""}}


def stop_count_update(day: str, kind: str) -> dict:
    """Count one stop on the day (use with upsert: it also creates the month and the day with their full shape)."""
    return {
        "$inc": {f"days.{day}.stops.{kind}": 1, f"days.{day}.spent": 0.0, f"days.{day}.reserved": 0.0,
                 f"days.{day}.runs_started": 0},
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
