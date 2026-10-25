"""The money rules MemoryStore and MongoStore share (T3.4, T3.7; contract §4.E, §8).

Pure functions on the shape of the month document, so both stores answer the same way:

    {"_id": "2026-10", "spent": 0.0,
     "days": {"2026-10-24": {"spent", "runs_started", "stops": {<kind>: n}}}}

A missing field reads as zero. MongoDB sorts a missing (null) number below every number, so a comparison that
forgot this would pass any cap; `mongo_docs.admit_filter` guards each read with $ifNull for the same reason.

No reservation (P4.21, contract v2.0): a run is admitted while the month's and the day's spend are strictly under
the caps. Documents written before v2.0 may still hold `reserved` and `reservations` fields: nothing here reads
them as spend, and nothing here writes them.
"""

import math
import re
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

Totals = namedtuple("Totals", "month_spent day_spent")


def month_defaults() -> dict:
    return {"spent": 0.0}


def day_defaults() -> dict:
    return {"spent": 0.0, "runs_started": 0}


# --- validation -------------------------------------------------------------------------------------------------------

def check_run_id(run_id) -> str:
    if not isinstance(run_id, str) or not RUN_ID.match(run_id):
        raise ValueError("a run id is 1 to 128 characters from A-Z a-z 0-9 _ -")
    return run_id


def _number(x, what: str) -> float:
    if isinstance(x, bool) or not isinstance(x, (int, float)) or not math.isfinite(x):
        raise ValueError(f"{what} must be a finite number")
    return float(x)


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


MONTH_KEY = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")
DAY_KEY = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def check_admission(a) -> None:
    """An Admission's month and day go into a dotted path (`days.<day>.spent`): refuse any other shape."""
    check_run_id(a.run_id)
    if not isinstance(a.month, str) or not MONTH_KEY.match(a.month):
        raise ValueError("an admission's month is YYYY-MM")
    if not isinstance(a.day, str) or not DAY_KEY.match(a.day) or not a.day.startswith(a.month + "-"):
        raise ValueError("an admission's day is YYYY-MM-DD, in its month")


# --- the caps ---------------------------------------------------------------------------------------------------------

class MalformedDocument(ValueError):
    """A spend document whose figures cannot be read (a string where a number belongs). The stores fail closed on it:
    admit refuses as atlas_unreachable and live_status says unknown. The message never carries a value."""


def _spent(x) -> float:
    """A stored `spent`: missing or null reads as zero, as `$ifNull` does in the Atlas filter; anything else that is
    not a finite number is malformed."""
    if x is None:
        return 0.0
    if isinstance(x, bool) or not isinstance(x, (int, float)) or not math.isfinite(x):
        raise MalformedDocument("a spend document holds a figure that is not a number")
    return float(x)


def day_totals(doc: dict | None, day: str) -> Totals:
    """Spent so far, this month and this Chicago day; a missing document, day or field (or a null one) reads as zero.
    Old `reserved` fields are not read. Raises MalformedDocument for a figure that is not a number."""
    doc = doc or {}
    days = doc.get("days")
    if days is not None and not isinstance(days, dict):
        raise MalformedDocument("a spend document's days are not a mapping")
    d = (days or {}).get(day)
    if d is not None and not isinstance(d, dict):
        raise MalformedDocument("a spend document's day is not a mapping")
    return Totals(_spent(doc.get("spent")), _spent((d or {}).get("spent")))


def under_cap(spent: float, cap: float) -> bool:
    """Strictly under (P4.21): at or over the cap is not. EPS keeps float noise from deciding it: a sum that
    reaches the cap but for rounding error (25 x $0.60 against $15) counts as at the cap."""
    return spent < cap - EPS


def cap_verdict(doc: dict | None, day: str) -> Literal["monthly_cap", "daily_cap"] | None:
    """Which cap the spend so far has reached, if any (P4.21; P2.7). It looks at what has been spent, never at what a
    run might spend. The month is named first: when both are reached the longer pause is the true one."""
    t = day_totals(doc, day)
    if not under_cap(t.month_spent, float(settings.MONTHLY_CAP_USD.value)):
        return "monthly_cap"
    if not under_cap(t.day_spent, float(settings.DAILY_CAP_USD.value)):
        return "daily_cap"
    return None


def health_view(doc: dict | None, spend_limit_active: bool, exa_flag_active: bool, day: str) -> dict:
    """The two /health fields the store knows (contract §5, §4.E)."""
    if spend_limit_active:
        live = "paused_month"
    else:
        verdict = cap_verdict(doc, day)
        live = {"monthly_cap": "paused_month", "daily_cap": "paused_day", None: "open"}[verdict]
    return {"live_research": live, "update_check": "unavailable" if exa_flag_active else "available"}


# --- the stop record --------------------------------------------------------------------------------------------------

def stop_document(kind: str, run_id: str | None, now: datetime, totals: Totals | None, detail: dict) -> dict:
    """One small record per refusal or stop (T3.4): Chicago date and time, run ID or null, which limit, spent and
    at that moment (the month's and the day's), and whether it was a budget stop. `totals` None means unknown (Atlas
    unreachable)."""
    check_stop_kind(kind)
    if run_id is not None:
        check_run_id(run_id)
    check_stop_detail(detail)
    t = totals if totals is not None else Totals(None, None)
    return {
        "at": now,
        "date": chicago_day(now),
        "time": chicago_time(now),
        "run": run_id,
        "kind": kind,
        "budget": kind in BUDGET_STOPS,
        "month_spent": t.month_spent,
        "day_spent": t.day_spent,
        "detail": dict(detail),
    }
