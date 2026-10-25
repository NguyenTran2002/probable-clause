"""The money rules MemoryStore and MongoStore share (T3.4, T3.7; contract §4.E, §8).

Pure functions on the shape of the month document, so both stores answer the same way:

    {"_id": "2026-10", "spent": 0.0, "reserved": 0.0,
     "days": {"2026-10-24": {"spent", "reserved", "runs_started", "stops": {<kind>: n}}},
     "reservations": {<run>: {"day", "amount", "at"}}}

A missing field reads as zero. MongoDB sorts a missing (null) number below every number, so a comparison that
forgot this would pass any cap; `mongo_docs.reserve_filter` guards each read with $ifNull for the same reason.
"""

import math
from collections import namedtuple
from datetime import datetime
from typing import Literal

from api import settings
from api.protocols import BUDGET_STOPS
from api.state.clock import chicago_day, chicago_time
from api.state.records import (  # noqa: F401  (re-exported: both stores and the tests reach them here)
    FORBIDDEN_KEYS, RUN_ID, STOP_KINDS, check_no_text, check_run_record, check_stop_detail, find_forbidden_keys,
)

# Tolerance when comparing a sum of floats with a cap, so that 25 x $0.40 (10.000000000000004 in floating point)
# is still "exactly $10". It is float noise, not a money figure.
EPS = 1e-9

FLAG_NAMES = ("exa_out_of_credit", "anthropic_spend_limit")

UNKNOWN_HEALTH = {"live_research": "unknown", "update_check": "unknown"}

Totals = namedtuple("Totals", "month_spent month_reserved day_spent day_reserved")


def month_defaults() -> dict:
    return {"spent": 0.0, "reserved": 0.0, "reservations": {}}


def day_defaults() -> dict:
    return {"spent": 0.0, "reserved": 0.0, "runs_started": 0}


# --- validation -------------------------------------------------------------------------------------------------------

def check_run_id(run_id) -> str:
    if not isinstance(run_id, str) or not RUN_ID.match(run_id):
        raise ValueError("a run id is 1 to 128 characters from A-Z a-z 0-9 _ -")
    return run_id


def _number(x, what: str) -> float:
    if isinstance(x, bool) or not isinstance(x, (int, float)) or not math.isfinite(x):
        raise ValueError(f"{what} must be a finite number")
    return float(x)


def check_worst(x) -> float:
    x = _number(x, "the worst case")
    if x <= 0:
        raise ValueError("the worst case must be positive")
    return x


def check_cost(x) -> float:
    x = _number(x, "a cost")
    if x < 0:
        raise ValueError("a cost cannot be negative")
    return x


def check_stop_kind(kind) -> str:
    if kind not in STOP_KINDS:
        raise ValueError(f"unknown stop kind {kind!r}")
    return kind


def check_flag_name(name) -> str:
    if name not in FLAG_NAMES:
        raise ValueError(f"unknown flag {name!r}")
    return name


# --- the caps ---------------------------------------------------------------------------------------------------------

def day_totals(doc: dict | None, day: str) -> Totals:
    doc = doc or {}
    d = (doc.get("days") or {}).get(day) or {}
    return Totals(doc.get("spent", 0.0), doc.get("reserved", 0.0), d.get("spent", 0.0), d.get("reserved", 0.0))


def cap_verdict(doc: dict | None, day: str, worst: float) -> Literal["monthly_cap", "daily_cap"] | None:
    """Which cap a run of this worst case would break, if any (T3.4; P2.7).

    spent + reserved + worst must stay within the cap for the Chicago day and for the month. The month is named
    first: when both are broken the longer pause is the true one.
    """
    t = day_totals(doc, day)
    if t.month_spent + t.month_reserved + worst > float(settings.MONTHLY_CAP_USD.value) + EPS:
        return "monthly_cap"
    if t.day_spent + t.day_reserved + worst > float(settings.DAILY_CAP_USD.value) + EPS:
        return "daily_cap"
    return None


def health_view(doc: dict | None, spend_limit_active: bool, exa_flag_active: bool, day: str, worst: float) -> dict:
    """The two /health fields the store knows (contract §5, §4.E)."""
    if spend_limit_active:
        live = "paused_month"
    else:
        verdict = cap_verdict(doc, day, worst)
        live = {"monthly_cap": "paused_month", "daily_cap": "paused_day", None: "open"}[verdict]
    return {"live_research": live, "update_check": "unavailable" if exa_flag_active else "available"}


# --- the stop record --------------------------------------------------------------------------------------------------

def stop_document(kind: str, run_id: str | None, now: datetime, totals: Totals | None, detail: dict) -> dict:
    """One small record per refusal or stop (T3.4): Chicago date and time, run ID or null, which limit, spent and
    reserved at that moment, and whether it was a budget stop. `totals` None means unknown (Atlas unreachable)."""
    check_stop_kind(kind)
    if run_id is not None:
        check_run_id(run_id)
    check_stop_detail(detail)
    t = totals if totals is not None else Totals(None, None, None, None)
    return {
        "at": now,
        "date": chicago_day(now),
        "time": chicago_time(now),
        "run": run_id,
        "kind": kind,
        "budget": kind in BUDGET_STOPS,
        "month_spent": t.month_spent,
        "month_reserved": t.month_reserved,
        "day_spent": t.day_spent,
        "day_reserved": t.day_reserved,
        "detail": dict(detail),
    }
