"""api/state/clock.py: Chicago days and months from zoneinfo, never from a UTC date (brief §10.7)."""

from datetime import UTC, datetime
from zoneinfo import ZoneInfo

import pytest

from api.state.clock import chicago_day, chicago_month, chicago_now, chicago_time, next_month_start

CHI = ZoneInfo("America/Chicago")


def utc(*a):
    return datetime(*a, tzinfo=UTC)


def test_chicago_now_is_aware_and_in_chicago():
    n = chicago_now()
    assert n.tzinfo is not None
    assert n.utcoffset() in (CHI.utcoffset(datetime(2026, 1, 1)), CHI.utcoffset(datetime(2026, 7, 1)))


def test_evening_chicago_is_not_the_next_utc_day():
    # the previous build stamped evening Chicago runs with the next day's UTC date (brief §10.7)
    t = utc(2026, 10, 25, 1, 31)  # 20:31 CDT on Oct 24
    assert chicago_day(t) == "2026-10-24"
    assert chicago_month(t) == "2026-10"
    assert chicago_time(t) == "20:31:00"


def test_accepts_any_zone_and_converts_explicitly():
    t = datetime(2026, 10, 24, 23, 59, 59, tzinfo=CHI)
    assert chicago_day(t.astimezone(UTC)) == "2026-10-24"
    assert chicago_day(datetime(2026, 10, 25, 0, 0, 0, tzinfo=CHI)) == "2026-10-25"


def test_naive_datetime_is_refused():
    with pytest.raises(ValueError):
        chicago_day(datetime(2026, 10, 24, 12, 0))
    with pytest.raises(ValueError):
        chicago_month(datetime(2026, 10, 24, 12, 0))
    with pytest.raises(ValueError):
        next_month_start(datetime(2026, 10, 24, 12, 0))


def test_month_edge_between_oct_and_nov_2026():
    # DST ends Nov 1 2026 at 2:00 CDT (07:00 UTC); midnight Nov 1 is still CDT (05:00 UTC)
    assert chicago_month(utc(2026, 11, 1, 4, 59, 59)) == "2026-10"
    assert chicago_day(utc(2026, 11, 1, 4, 59, 59)) == "2026-10-31"
    assert chicago_month(utc(2026, 11, 1, 5, 0, 0)) == "2026-11"
    assert chicago_day(utc(2026, 11, 1, 5, 0, 0)) == "2026-11-01"


def test_year_edge():
    # Jan 1 2027 00:00 CST is 06:00 UTC
    assert chicago_day(utc(2027, 1, 1, 5, 59, 59)) == "2026-12-31"
    assert chicago_month(utc(2027, 1, 1, 5, 59, 59)) == "2026-12"
    assert chicago_day(utc(2027, 1, 1, 6, 0, 0)) == "2027-01-01"
    assert chicago_month(utc(2027, 1, 1, 6, 0, 0)) == "2027-01"


def test_fall_back_day_has_25_hours_and_one_date():
    # Nov 1 2026: midnight CDT is 05:00 UTC; midnight Nov 2 is CST, 06:00 UTC
    assert chicago_day(utc(2026, 11, 1, 5, 0)) == "2026-11-01"
    assert chicago_day(utc(2026, 11, 2, 5, 59, 59)) == "2026-11-01"  # 24 h + later, same Chicago day
    assert chicago_day(utc(2026, 11, 2, 6, 0)) == "2026-11-02"
    # the repeated hour: 01:30 CDT and 01:30 CST are the same day
    first = datetime(2026, 11, 1, 1, 30, tzinfo=CHI, fold=0)
    second = datetime(2026, 11, 1, 1, 30, tzinfo=CHI, fold=1)
    assert first.utcoffset() != second.utcoffset()
    assert chicago_day(first) == chicago_day(second) == "2026-11-01"


def test_spring_forward_day_has_23_hours_and_one_date():
    # Mar 14 2027: midnight CST is 06:00 UTC; 2:00 CST jumps to 3:00 CDT; midnight Mar 15 is CDT, 05:00 UTC
    assert chicago_day(utc(2027, 3, 14, 5, 59)) == "2027-03-13"
    assert chicago_day(utc(2027, 3, 14, 6, 0)) == "2027-03-14"
    assert chicago_day(utc(2027, 3, 15, 4, 59, 59)) == "2027-03-14"
    assert chicago_day(utc(2027, 3, 15, 5, 0)) == "2027-03-15"


def test_next_month_start_is_chicago_midnight_on_the_first():
    nm = next_month_start(utc(2026, 10, 25, 1, 31))  # Oct 24 evening, Chicago
    assert nm == datetime(2026, 11, 1, 0, 0, tzinfo=CHI)
    assert nm.utcoffset().total_seconds() == -5 * 3600  # still CDT at midnight Nov 1
    assert nm.astimezone(UTC) == utc(2026, 11, 1, 5, 0)


def test_next_month_start_from_the_last_instant_and_the_first_instant():
    last = datetime(2026, 10, 31, 23, 59, 59, 999999, tzinfo=CHI)
    assert next_month_start(last) == datetime(2026, 11, 1, 0, 0, tzinfo=CHI)
    first = datetime(2026, 11, 1, 0, 0, tzinfo=CHI)
    assert next_month_start(first) == datetime(2026, 12, 1, 0, 0, tzinfo=CHI)
    # December 1 is CST: six hours behind UTC
    assert next_month_start(first).astimezone(UTC) == utc(2026, 12, 1, 6, 0)


def test_next_month_start_december_to_january():
    n = next_month_start(datetime(2026, 12, 15, 12, 0, tzinfo=CHI))
    assert n == datetime(2027, 1, 1, 0, 0, tzinfo=CHI)
    assert n.astimezone(UTC) == utc(2027, 1, 1, 6, 0)


def test_next_month_start_across_daylight_saving_changes():
    # February to March 1 2027 is CST; March to April 1 2027 is CDT (spring forward was Mar 14)
    assert next_month_start(datetime(2027, 2, 10, 9, 0, tzinfo=CHI)).astimezone(UTC) == utc(2027, 3, 1, 6, 0)
    assert next_month_start(datetime(2027, 3, 20, 9, 0, tzinfo=CHI)).astimezone(UTC) == utc(2027, 4, 1, 5, 0)


def test_next_month_start_uses_chicago_month_not_utc_month():
    # 20:00 CDT on Oct 31 is Nov 1 01:00 UTC; the Chicago month is still October
    t = utc(2026, 11, 1, 1, 0)
    assert chicago_month(t) == "2026-10"
    assert next_month_start(t) == datetime(2026, 11, 1, 0, 0, tzinfo=CHI)


def test_leap_day():
    assert chicago_day(utc(2028, 3, 1, 5, 59)) == "2028-02-29"
    assert next_month_start(datetime(2028, 2, 29, 12, 0, tzinfo=CHI)) == datetime(2028, 3, 1, 0, 0, tzinfo=CHI)
