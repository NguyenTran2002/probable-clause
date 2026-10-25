"""Chicago days and months (brief §10.7; contract §1).

Every date the money code keys on is a America/Chicago date, converted explicitly with zoneinfo from an aware
datetime. A naive datetime is refused: its zone would have to be guessed, and a guessed UTC date is the stumble
brief §10.7 records.
"""

from datetime import datetime
from zoneinfo import ZoneInfo

from api import settings

CHICAGO = ZoneInfo(str(settings.TIME_ZONE.value))


def _chicago(dt: datetime) -> datetime:
    if dt.tzinfo is None or dt.utcoffset() is None:
        raise ValueError("a timezone-aware datetime is required: a naive one has no Chicago date")
    return dt.astimezone(CHICAGO)


def chicago_now() -> datetime:
    return datetime.now(CHICAGO)


def chicago_day(dt: datetime) -> str:
    """"2026-10-24": the Chicago calendar date of `dt`."""
    c = _chicago(dt)
    return f"{c.year:04d}-{c.month:02d}-{c.day:02d}"


def chicago_month(dt: datetime) -> str:
    """"2026-10": the Chicago month of `dt`."""
    c = _chicago(dt)
    return f"{c.year:04d}-{c.month:02d}"


def chicago_time(dt: datetime) -> str:
    """"20:31:05": the Chicago wall-clock time of `dt`."""
    c = _chicago(dt)
    return f"{c.hour:02d}:{c.minute:02d}:{c.second:02d}"


def next_month_start(dt: datetime) -> datetime:
    """Midnight on the 1st of the next Chicago month, in Chicago time (when a flag lapses, T2.4, T3.4)."""
    c = _chicago(dt)
    year, month = (c.year + 1, 1) if c.month == 12 else (c.year, c.month + 1)
    return datetime(year, month, 1, tzinfo=CHICAGO)   # 00:00 never falls in a DST gap (changes are at 02:00)
