"""Read-only spend reports from Atlas (T3.4, T3.5; contract §4.E): a day or a month.

    uv run --env-file .env python scripts/spend_report.py --day 2026-10-24
    uv run --env-file .env python scripts/spend_report.py --month 2026-10

`--env live|test` chooses the database (default: PC_ENV, else test); `--json` prints one JSON object instead of
text. Dates are America/Chicago. The URI is read from MONGODB_URI in the environment, in-process, and is never
printed; the script says which database it read, never which server.

Exit codes: 0 when it read the store and built the report; 2 when it could not read or build the report for any
reason (bad arguments, no URI, an unusable URI, Atlas unreachable, a document of an unexpected shape), so a failure to
look is never taken for "nothing recorded". (Exit 1 and `--open-reservations` are gone with the reservation, v2.0:
there is nothing held to look for.) A failure prints one fixed sentence: no traceback, no exception text, no URI, no
host, and nothing of a half-built report. deploy/deploy.sh reads the live month with it (contract §4.I).

Figures are shown as stored. A negative `spent` (below -1e-9, beyond float noise) is not clamped: it is shown and
listed as an ANOMALY, since it means the books are wrong. Old months written before v2.0 may hold `reserved` and
`reservations` fields; they are not spend and are not shown.

It only reads: it calls no method of the store that writes.
"""

import argparse
import asyncio
import io
import json
import os
import re
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from api.state.store import MongoStore, StoreUnavailable, db_name_for  # noqa: E402

# Below this, a figure that should not be negative is an anomaly; between it and zero it is float noise.
ANOMALY_BELOW = -1e-9

UNAVAILABLE = ("Could not read from the store: Atlas is unreachable or timed out. "
               "This is not an answer to the question asked.")
FAILED = ("The report could not be produced: the connection string was not usable, or the store returned something "
          "unexpected. Details are not printed, because they could include connection details.")

STOP_FIELDS = ("date", "time", "run", "kind", "budget", "month_spent", "day_spent", "detail")

DAY = re.compile(r"^\d{4}-\d{2}-\d{2}$")
MONTH = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")


def _day(text: str) -> str:
    try:
        if not DAY.match(text):
            raise ValueError
        date.fromisoformat(text)
    except ValueError:
        raise argparse.ArgumentTypeError("a day is YYYY-MM-DD") from None
    return text


def _month(text: str) -> str:
    if not MONTH.match(text):
        raise argparse.ArgumentTypeError("a month is YYYY-MM")
    return text


def _usd(x) -> str:
    """Dollars as stored, signed. Float noise that would print as "-$0.0000" prints as "$0.0000"."""
    if x is None:
        return "unknown"
    text = f"{x:,.4f}"
    if text == "-0.0000":
        text = "0.0000"
    return f"-${text[1:]}" if text.startswith("-") else f"${text}"


def _clean(x: float) -> float:
    return 0.0 if abs(x) <= 1e-9 else round(x, 6)


def _stop_json(s: dict) -> dict:
    out = {k: s[k] for k in STOP_FIELDS}
    out["at"] = s["at"].isoformat(timespec="seconds")
    return out


def _counts(stops: dict) -> str:
    return ", ".join(f"{k} {n}" for k, n in sorted(stops.items())) or "none"


def _day_figures(doc: dict | None, day: str) -> dict | None:
    d = ((doc or {}).get("days") or {}).get(day)
    if d is None:
        return None
    return {"spent": _clean(d.get("spent", 0.0)), "runs_started": d.get("runs_started", 0),
            "stops": dict(d.get("stops") or {})}


def _anomalies(label: str, f: dict) -> list[str]:
    out = []
    if f["spent"] < ANOMALY_BELOW:
        out.append(f"{label}: spent is negative ({_usd(f['spent'])})")
    return out


async def report_day(store, day: str, db: str, as_json: bool, out) -> int:
    month = day[:7]
    figures = _day_figures(await store.read_month(month), day)
    stops = await store.read_stops(day=day)
    anomalies = _anomalies(f"day {day}", figures) if figures else []
    if as_json:
        print(json.dumps({"database": db, "day": day, "recorded": figures is not None or bool(stops),
                          "figures": figures, "stops": [_stop_json(s) for s in stops], "anomalies": anomalies}, indent=2), file=out)
        return 0
    print(f"Database: {db}", file=out)
    if figures is None and not stops:
        print(f"Day {day}: no spend recorded", file=out)
        return 0
    f = figures or {"spent": 0.0, "runs_started": 0, "stops": {}}
    print(f"Day {day} (America/Chicago)", file=out)
    print(f"  spent          {_usd(f['spent'])}", file=out)
    print(f"  runs started   {f['runs_started']}", file=out)
    print(f"  stops          {_counts(f['stops'])}", file=out)
    for a_ in anomalies:
        print(f"ANOMALY: {a_}", file=out)
    if stops:
        print("Stop records (Chicago time, kind, run, budget stop):", file=out)
        for s in stops:
            print(f"  {s['time']}  {s['kind']:<24} {s['run'] or '-':<30} {'budget' if s['budget'] else 'not a budget stop'}"
                  f"   day {_usd(s['day_spent'])}  month {_usd(s['month_spent'])} spent", file=out)
    return 0


async def report_month(store, month: str, db: str, as_json: bool, out) -> int:
    doc = await store.read_month(month)
    stops = await store.read_stops(month=month)
    days = {d: _day_figures(doc, d) for d in sorted((doc or {}).get("days") or {})}
    total = {"spent": _clean((doc or {}).get("spent", 0.0))}
    anomalies = _anomalies(f"month {month}", total)
    for d, f in days.items():
        anomalies += _anomalies(f"day {d}", f)
    if as_json:
        print(json.dumps({"database": db, "month": month, "recorded": doc is not None, **total, "days": days,
                          "stops": [_stop_json(s) for s in stops], "anomalies": anomalies}, indent=2), file=out)
        return 0
    print(f"Database: {db}", file=out)
    if doc is None and not stops:
        print(f"Month {month}: no spend recorded", file=out)
        return 0
    print(f"Month {month} (America/Chicago)", file=out)
    print(f"  spent          {_usd(total['spent'])}", file=out)
    print("  days:", file=out)
    for d, f in days.items():
        print(f"    {d}  spent {_usd(f['spent'])}  runs started {f['runs_started']}"
              f"  stops: {_counts(f['stops'])}", file=out)
    print(f"  stop records   {len(stops)}", file=out)
    for a_ in anomalies:
        print(f"ANOMALY: {a_}", file=out)
    return 0


def main(argv=None, *, store_factory=None, out=None, err=None, env=None) -> int:
    out = out or sys.stdout
    err = err or sys.stderr
    env = os.environ if env is None else env
    p = argparse.ArgumentParser(description="Read-only spend report from Atlas (T3.4).")
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--day", type=_day, metavar="YYYY-MM-DD")
    g.add_argument("--month", type=_month, metavar="YYYY-MM")
    p.add_argument("--env", choices=("live", "test"), help="database (default: PC_ENV, else test)")
    p.add_argument("--json", action="store_true", dest="as_json")
    args = p.parse_args(argv)

    uri = env.get("MONGODB_URI")
    if not uri:
        print("MONGODB_URI is not set in the environment", file=err)
        return 2
    try:
        db = db_name_for(args.env or env.get("PC_ENV") or "test")
    except ValueError:
        print("PC_ENV must be 'live' or 'test'", file=err)
        return 2

    buf = io.StringIO()      # nothing reaches `out` unless the whole report was built

    async def go() -> int:
        store = (store_factory or MongoStore)(uri, db)
        try:
            if args.day:
                return await report_day(store, args.day, db, args.as_json, buf)
            return await report_month(store, args.month, db, args.as_json, buf)
        finally:
            close = getattr(store, "close", None)
            if close:
                await close()

    try:
        code = asyncio.run(go())
    except StoreUnavailable:
        print(UNAVAILABLE, file=err)
        return 2
    except Exception:           # whatever it was, its text could hold the URI or a host: say one fixed sentence
        print(FAILED, file=err)
        return 2
    out.write(buf.getvalue())
    return code


if __name__ == "__main__":
    sys.exit(main())
