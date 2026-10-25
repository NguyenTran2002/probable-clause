"""The semantic cases every Store must pass (contract §4.E, §8; T3.4 amended by P4.21).

Plain async functions taking a store. They run against MemoryStore, against MongoStore over the fake database
(tests/state/fakes.py), and, when PC_ATLAS_TEST=1, against MongoStore on Probable_Clause_test. The dates are in
2030 so no case touches a real month, and each case is written so that it starts from an empty store.

The caps in these cases are tests/state/conftest.py's: $10 a day and $60 a month.
"""

from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

import anyio
import pytest

from api.protocols import BUDGET_STOPS, Admission, StopKind, Refusal

CHI = ZoneInfo("America/Chicago")
T = datetime(2030, 5, 14, 12, 0, tzinfo=CHI)
DAY, MONTH = "2030-05-14", "2030-05"


def at(month_day: str, hh=12, mm=0, ss=0) -> datetime:
    """A Chicago instant in 2030: at("05-14", 23, 59)."""
    m, d = (int(x) for x in month_day.split("-"))
    return datetime(2030, m, d, hh, mm, ss, tzinfo=CHI)


def close(a, b, tol=1e-9):
    return abs(a - b) <= tol


def figures(month_doc, day=DAY):
    """(month spent, day spent), missing fields read as zero."""
    d = (month_doc or {}).get("days", {}).get(day, {})
    return (month_doc or {}).get("spent", 0.0), d.get("spent", 0.0)


def event(run, n, kind="tool_call", **data):
    return {"v": 1, "run": run, "n": n, "t_ms": n * 100, "at": "2030-05-14T12:00:00.000-05:00", "kind": kind, "data": data}


async def spend(store, run_id, amount, now=T):
    """Admit a run and record one call's cost for it: what H does. The admission is returned."""
    a = await store.admit(run_id, now)
    assert isinstance(a, Admission), f"{run_id} was refused: {a}"
    await store.record_spend(a, amount)
    return a


# --- admit and record_spend ----------------------------------------------------------------------------------------

async def case_admit_success(store):
    a = await store.admit("run-a", T)
    assert a == Admission("run-a", MONTH, DAY)
    m = await store.read_month(MONTH)
    assert figures(m) == (0.0, 0.0)
    assert m["days"][DAY]["runs_started"] == 1
    assert "reserved" not in m and "reservations" not in m and "reserved" not in m["days"][DAY]     # P4.21: none written


async def case_admissions_count_starts_and_do_not_reserve_anything(store):
    for i in range(12):                                   # no worst case to fit: twelve admissions, none spent yet
        assert isinstance(await store.admit(f"run-{i}", T + timedelta(minutes=i)), Admission)
    m = await store.read_month(MONTH)
    assert m["days"][DAY]["runs_started"] == 12 and figures(m) == (0.0, 0.0)
    assert await store.read_stops(day=DAY) == []


async def case_record_spend_adds_to_the_month_and_the_day(store):
    a = await store.admit("run-a", T)
    await store.record_spend(a, 0.5)
    await store.record_spend(a, 0.25)
    await store.record_spend(a, 0.0)
    m = await store.read_month(MONTH)
    ms, ds = figures(m)
    assert close(ms, 0.75) and close(ds, 0.75)
    assert m["days"][DAY]["runs_started"] == 1
    await spend(store, "run-b", 0.5, at("05-15"))                      # another day, same month
    m = await store.read_month(MONTH)
    assert close(m["spent"], 1.25) and close(figures(m, "2030-05-15")[1], 0.5) and close(figures(m)[1], 0.75)


async def case_the_cap_is_a_threshold_on_spend_so_far_strictly_under(store):
    await spend(store, "run-a", 9.99)
    assert isinstance(await store.admit("run-b", T), Admission)            # $9.99 is under $10, whatever run-b may spend
    await store.record_spend(Admission("run-a", MONTH, DAY), 0.01)         # exactly $10.00
    refusal = await store.admit("run-c", T + timedelta(minutes=9))
    assert refusal == Refusal("daily_cap")
    m = await store.read_month(MONTH)
    assert m["days"][DAY]["runs_started"] == 2                            # a refusal is not a start
    assert m["days"][DAY]["stops"] == {"daily_cap": 1}
    [s] = await store.read_stops(day=DAY)
    assert s["kind"] == "daily_cap" and s["run"] == "run-c" and s["budget"] is True
    assert s["date"] == DAY and s["time"] == "12:09:00" and isinstance(s["at"], datetime)
    assert close(s["day_spent"], 10.0) and close(s["month_spent"], 10.0)    # the spend at that moment
    assert "day_reserved" not in s and "month_reserved" not in s


async def case_float_noise_below_the_cap_still_counts_as_at_the_cap(store):
    a = await store.admit("run-a", T)
    for _ in range(100):
        await store.record_spend(a, 0.1)               # 100 x 0.1 is 9.99999999999998 in floating point: $10
    assert await store.admit("run-b", T) == Refusal("daily_cap")


async def case_runs_in_progress_finish_and_may_take_spend_past_the_cap(store):
    a = await store.admit("run-a", T)
    b = await store.admit("run-b", T)
    await store.record_spend(a, 9.0)
    await store.record_spend(b, 9.0)                    # $18 on a $10 day: nothing refuses a call of an admitted run
    await store.record_spend(a, 1.0)
    m = await store.read_month(MONTH)
    assert close(m["spent"], 19.0) and close(figures(m)[1], 19.0)
    assert await store.admit("run-c", T) == Refusal("daily_cap")           # only the next admission is refused


async def case_the_monthly_cap_refuses_and_is_recorded(store):
    # $10 a day fills a day; six days fill $60
    for d in range(1, 7):
        await spend(store, f"run-{d}", 10.0, at(f"05-{d:02d}"))
    assert await store.admit("run-next-day", at("05-07")) == Refusal("monthly_cap")     # day 7 is empty, the month is full
    m = await store.read_month(MONTH)
    assert close(m["spent"], 60.0)
    assert m["days"]["2030-05-07"]["stops"] == {"monthly_cap": 1}
    stops = await store.read_stops(month=MONTH)
    assert [(s["kind"], s["budget"], s["run"], s["date"]) for s in stops] == [("monthly_cap", True, "run-next-day", "2030-05-07")]
    assert close(stops[0]["month_spent"], 60.0) and close(stops[0]["day_spent"], 0.0)


async def case_just_under_the_monthly_cap_is_admitted(store):
    for d in range(1, 6):
        await spend(store, f"run-{d}", 10.0, at(f"05-{d:02d}"))
    await spend(store, "run-6", 9.99, at("05-06"))
    assert isinstance(await store.admit("run-7", at("05-07")), Admission)         # $59.99 is under $60


async def case_monthly_cap_wins_when_both_caps_are_reached(store):
    for d in range(1, 7):
        await spend(store, f"run-{d}", 10.0, at(f"05-{d:02d}"))
    # day 6 is full ($10) and the month is full ($60): the longer pause is the one to report
    assert await store.admit("late", at("05-06", 23)) == Refusal("monthly_cap")
    assert (await store.read_month(MONTH))["days"]["2030-05-06"]["stops"] == {"monthly_cap": 1}


async def case_a_month_or_day_with_no_document_counts_as_zero_spent(store):
    assert await store.read_month(MONTH) is None
    assert isinstance(await store.admit("run-a", T), Admission)
    await spend(store, "run-b", 10.0, at("05-20"))                  # a day with an entry for spend only
    assert isinstance(await store.admit("run-c", at("05-21")), Admission)     # a day with no entry yet


async def case_the_day_is_a_chicago_day_not_a_utc_day(store):
    evening = datetime(2030, 5, 14, 22, 0, tzinfo=CHI)          # 03:00 UTC on May 15
    assert evening.astimezone(UTC).day == 15
    a = await store.admit("evening", evening.astimezone(UTC))
    assert a.day == "2030-05-14" and a.month == MONTH


async def case_a_new_chicago_day_has_a_fresh_daily_cap_in_the_same_month(store):
    await spend(store, "a0", 10.0, at("05-14", 23, 59, 0))
    assert await store.admit("a-refused", at("05-14", 23, 59, 30)) == Refusal("daily_cap")
    b = await store.admit("b0", at("05-15", 0, 0, 30))
    assert isinstance(b, Admission) and b.day == "2030-05-15"
    await store.record_spend(b, 1.0)
    m = await store.read_month(MONTH)
    assert close(m["spent"], 11.0)                                  # the month keeps counting
    assert close(figures(m, "2030-05-15")[1], 1.0)


async def case_a_new_month_starts_a_new_document(store):
    a1 = await spend(store, "may", 5.0, at("05-31", 23, 59, 59))
    a2 = await spend(store, "june", 5.0, at("06-01", 0, 0, 1))
    assert (a1.month, a2.month) == ("2030-05", "2030-06")
    assert close((await store.read_month("2030-05"))["spent"], 5.0)
    assert close((await store.read_month("2030-06"))["spent"], 5.0)


async def case_the_daylight_saving_day_is_one_chicago_day(store):
    # Nov 3 2030 is the fall-back Sunday; 01:30 happens twice. Both are the same Chicago day.
    first = datetime(2030, 11, 3, 1, 30, tzinfo=CHI, fold=0)
    second = datetime(2030, 11, 3, 1, 30, tzinfo=CHI, fold=1)
    a1 = await spend(store, "one", 2.5, first)
    a2 = await spend(store, "two", 2.5, second)
    assert a1.day == a2.day == "2030-11-03"
    assert close(figures(await store.read_month("2030-11"), "2030-11-03")[1], 5.0)


async def case_spend_counts_toward_the_day_and_month_the_run_was_admitted_in(store):
    a = await store.admit("late", at("05-31", 23, 59, 30))          # admitted just before midnight, May 31
    await store.record_spend(a, 0.9)                                # recorded after midnight: still May 31
    may = await store.read_month("2030-05")
    assert close(may["spent"], 0.9) and close(may["days"]["2030-05-31"]["spent"], 0.9)
    assert await store.read_month("2030-06") is None


async def case_bad_inputs_are_refused_before_anything_is_written(store):
    with pytest.raises(ValueError):
        await store.admit("bad.id", T)
    with pytest.raises(ValueError):
        await store.admit("$bad", T)
    with pytest.raises(ValueError):
        await store.admit("ok", datetime(2030, 5, 14, 12, 0))   # naive
    assert await store.read_month(MONTH) is None


async def case_record_spend_refuses_a_bad_cost_or_admission_and_writes_nothing(store):
    a = await store.admit("run-a", T)
    for bad in (-0.01, -1, float("nan"), float("inf"), float("-inf"), None, "1", True, [0.5]):
        with pytest.raises(ValueError):
            await store.record_spend(a, bad)
    for bad_a in (Admission("run-a", "2030-5", DAY), Admission("run-a", MONTH, "2030-05-1"),
                  Admission("run-a", MONTH, "2030-06-14"), Admission("run-a", MONTH, "2030-05-14.x"),
                  Admission("bad.id", MONTH, DAY)):
        with pytest.raises(ValueError):
            await store.record_spend(bad_a, 0.1)
    assert figures(await store.read_month(MONTH)) == (0.0, 0.0)


async def case_record_spend_into_a_month_with_no_document_creates_it_whole(store):
    await store.record_spend(Admission("ghost", MONTH, DAY), 0.25)
    m = await store.read_month(MONTH)
    assert close(m["spent"], 0.25) and close(m["days"][DAY]["spent"], 0.25) and m["days"][DAY]["runs_started"] == 0
    assert "reserved" not in m and "reservations" not in m


# --- the Anthropic spend-limit flag, the Exa flag -------------------------------------------------------------------

async def case_flags_last_until_the_first_of_the_next_chicago_month(store):
    assert await store.flag_until("exa_out_of_credit", T) is None
    await store.set_flag("exa_out_of_credit", T)
    until = await store.flag_until("exa_out_of_credit", T)
    assert until == datetime(2030, 6, 1, 0, 0, tzinfo=CHI)
    assert await store.flag_until("anthropic_spend_limit", T) is None            # flags are independent
    assert await store.flag_until("exa_out_of_credit", at("05-31", 23, 59, 59)) == until
    assert await store.flag_until("exa_out_of_credit", datetime(2030, 6, 1, 0, 0, tzinfo=CHI)) is None   # lapsed on the 1st
    assert await store.flag_until("exa_out_of_credit", at("06-02")) is None
    with pytest.raises(ValueError):
        await store.set_flag("nope", T)


async def case_a_flag_set_in_december_lapses_on_january_first(store):
    dec = datetime(2030, 12, 20, 9, 0, tzinfo=CHI)
    await store.set_flag("anthropic_spend_limit", dec)
    assert await store.flag_until("anthropic_spend_limit", dec) == datetime(2031, 1, 1, 0, 0, tzinfo=CHI)


async def case_the_spend_limit_flag_pauses_admissions_without_recording_a_stop(store):
    await store.set_flag("anthropic_spend_limit", T)
    assert await store.admit("run-a", T) == Refusal("spend_limit_paused")
    m = await store.read_month(MONTH)
    assert m is None or m["days"].get(DAY, {}).get("runs_started", 0) == 0
    assert await store.read_stops(month=MONTH) == []
    # it lapses on the 1st of the next month
    assert isinstance(await store.admit("run-b", at("06-01", 0, 0, 5)), Admission)


async def case_the_flag_is_checked_before_the_caps(store):
    await spend(store, "run-a", 10.0)
    await store.set_flag("anthropic_spend_limit", T)
    assert await store.admit("run-b", T) == Refusal("spend_limit_paused")      # not daily_cap, and no stop recorded
    assert await store.read_stops(day=DAY) == []


async def case_a_flag_does_not_stop_spend_being_recorded(store):
    a = await store.admit("run-a", T)
    await store.set_flag("anthropic_spend_limit", T)
    await store.record_spend(a, 0.5)                    # a run in progress finishes and its spend is kept
    assert close((await store.read_month(MONTH))["spent"], 0.5)


# --- record_stop --------------------------------------------------------------------------------------------------

async def case_budget_is_true_exactly_for_the_budget_stops(store):
    kinds = list(StopKind.__args__)
    for i, kind in enumerate(kinds):
        await store.record_stop(kind, f"run-{i}" if i % 2 == 0 else None, T + timedelta(seconds=i), {"rounds": i})
    stops = await store.read_stops(day=DAY)
    assert len(stops) == len(kinds)
    for s, kind in zip(stops, kinds):
        assert s["kind"] == kind
        assert s["budget"] is (kind in BUDGET_STOPS)
    assert {s["kind"] for s in stops if not s["budget"]} == {"atlas_unreachable", "time_limit", "update_time_limit"}
    assert stops[0]["run"] == "run-0" and stops[1]["run"] is None
    assert stops[3]["detail"] == {"rounds": 3}
    counts = (await store.read_month(MONTH))["days"][DAY]["stops"]
    assert counts == {k: 1 for k in kinds}


async def case_stop_counts_accumulate_per_day_and_records_show_spend_at_that_moment(store):
    await spend(store, "run-a", 0.5)
    await store.record_stop("step_limit", "run-a", T + timedelta(minutes=1), {})
    await store.record_stop("step_limit", "run-b", T + timedelta(minutes=2), {})
    await store.record_stop("step_limit", "run-c", at("05-15", 9, 0), {})
    m = await store.read_month(MONTH)
    assert m["days"][DAY]["stops"] == {"step_limit": 2}
    assert m["days"]["2030-05-15"]["stops"] == {"step_limit": 1}
    today = await store.read_stops(day=DAY)
    assert [s["run"] for s in today] == ["run-a", "run-b"]
    assert close(today[0]["day_spent"], 0.5) and close(today[0]["month_spent"], 0.5)
    assert len(await store.read_stops(month=MONTH)) == 3
    assert len(await store.read_stops(day="2030-05-15")) == 1


async def case_record_stop_works_on_a_month_with_no_document_yet(store):
    await store.record_stop("atlas_unreachable", None, T, {})
    m = await store.read_month(MONTH)
    assert m["days"][DAY]["stops"] == {"atlas_unreachable": 1}
    assert close(m["spent"], 0)
    # an admission afterwards must still be checked against real totals, not a partial document
    a = await store.admit("run-a", T)
    assert isinstance(a, Admission)
    await store.record_spend(a, 10.0)
    assert await store.admit("run-b", T) == Refusal("daily_cap")


async def case_record_stop_refuses_unknown_kinds_and_question_text_in_detail(store):
    with pytest.raises(ValueError):
        await store.record_stop("coffee_break", None, T, {})
    with pytest.raises(ValueError):
        await store.record_stop("step_limit", None, T, {"question": "what is the rule?"})
    with pytest.raises(ValueError):
        await store.record_stop("step_limit", None, T, {"reason": "free text"})
    assert await store.read_stops(month=MONTH) == []


# --- /health ------------------------------------------------------------------------------------------------------

async def case_live_status_open_paused_day_paused_month(store):
    s = await store.live_status(T, 2.0)
    assert s == {"live_research": "open", "update_check": "available"}
    await spend(store, "run-a", 9.99)
    assert (await store.live_status(T, 2.0))["live_research"] == "open"           # under the cap: open
    await store.record_spend(Admission("run-a", MONTH, DAY), 0.01)               # exactly $10
    assert (await store.live_status(T, 2.0))["live_research"] == "paused_day"
    assert (await store.live_status(at("05-15"), 2.0))["live_research"] == "open"   # the next day


async def case_live_status_paused_month_wins_over_paused_day(store):
    for d in range(1, 7):
        await spend(store, f"run-{d}", 10.0, at(f"05-{d:02d}"))
    assert (await store.live_status(at("05-06", 20), 2.0))["live_research"] == "paused_month"
    assert (await store.live_status(at("05-07", 8), 2.0))["live_research"] == "paused_month"
    assert (await store.live_status(at("06-01", 8), 2.0))["live_research"] == "open"


async def case_live_status_agrees_with_admit(store):
    await spend(store, "run-a", 10.0)
    assert (await store.live_status(T, 2.0))["live_research"] == "paused_day"
    assert await store.admit("run-b", T) == Refusal("daily_cap")


async def case_live_status_flags(store):
    await store.set_flag("anthropic_spend_limit", T)
    s = await store.live_status(T, 2.0)
    assert s["live_research"] == "paused_month" and s["update_check"] == "available"
    await store.set_flag("exa_out_of_credit", T)
    s = await store.live_status(T, 2.0)
    assert s == {"live_research": "paused_month", "update_check": "unavailable"}
    s = await store.live_status(at("06-01", 0, 0, 1), 2.0)                            # both lapse on the 1st
    assert s == {"live_research": "open", "update_check": "available"}


# --- events, heartbeats, run records --------------------------------------------------------------------------------

async def case_events_are_read_back_in_order_after_a_given_n(store):
    assert await store.read_events("r1", 0) == []
    await store.append_events("r1", [event("r1", 1, "run_started"), event("r1", 2)])
    await store.append_events("r1", [event("r1", 4, x=[1, 2, {"y": 3}]), event("r1", 3, "passage")])
    await store.append_events("r2", [event("r2", 1)])
    got = await store.read_events("r1", 0)
    assert [e["n"] for e in got] == [1, 2, 3, 4]
    assert got[0] == event("r1", 1, "run_started") and got[3]["data"] == {"x": [1, 2, {"y": 3}]}
    assert "_id" not in got[0] and "created" not in got[0]
    assert [e["n"] for e in await store.read_events("r1", 2)] == [3, 4]
    assert await store.read_events("r1", 4) == []
    assert [e["run"] for e in await store.read_events("r2", 0)] == ["r2"]


async def case_a_repeated_event_is_stored_once(store):
    await store.append_events("r1", [event("r1", 1), event("r1", 2)])
    await store.append_events("r1", [event("r1", 2, changed=True), event("r1", 3)])     # a retried batch
    got = await store.read_events("r1", 0)
    assert [e["n"] for e in got] == [1, 2, 3]
    assert got[1]["data"] == {}                                                         # the first write stands


async def case_events_for_another_run_or_without_n_are_refused(store):
    with pytest.raises(ValueError):
        await store.append_events("r1", [event("r2", 1)])
    bad = event("r1", 1)
    del bad["n"]
    with pytest.raises(ValueError):
        await store.append_events("r1", [bad])
    assert await store.read_events("r1", 0) == []


async def case_heartbeats(store):
    assert await store.latest_heartbeat("r1") is None
    await store.put_heartbeat("r1", 5, T)
    assert await store.latest_heartbeat("r1") == T
    later = T + timedelta(seconds=10)
    await store.put_heartbeat("r1", 9, later)
    assert await store.latest_heartbeat("r1") == later
    assert await store.latest_heartbeat("r2") is None
    assert (await store.latest_heartbeat("r1")).utcoffset() is not None        # aware


async def case_run_records_are_replaced_by_run_and_hold_only_the_allowed_shape(store):
    rec = {"run": "r1", "started_date": "2030-05-14", "started_time": "12:00:00", "state": "answered", "stop_kind": None,
           "rounds": 4, "answer_chars": 812, "searches": {"meaning": 2, "exact": 1, "web": 1}, "keeps": 5,
           "tokens": {"input": 1000, "cache_read": 800, "cache_write": 200, "output": 300},
           "cost_usd": {"claude_loop": 0.1, "claude_composition": 0.1, "exa": 0.007, "voyage": 0.001},
           "retries": {"claude": 0, "voyage": 1}, "voyage_warning": "degraded", "corpus_label": "full"}
    await store.upsert_run_record(rec)
    assert await store.get_run_record("r1") == rec
    await store.upsert_run_record({**rec, "state": "step_limit", "stop_kind": "step_limit", "rounds": 12})
    got = await store.get_run_record("r1")
    assert got["state"] == "step_limit" and got["stop_kind"] == "step_limit" and got["rounds"] == 12
    assert await store.get_run_record("r2") is None
    for bad in ({"run": "r1", "question": "q"}, {"run": "r1", "searches": {"Query": "x"}}, {"run": "r1", "note": "n"},
                {"run": "r1", "state": "x" * 500}, {"run": "r1", "rounds": "12"}, {"run": "r1", "extra": 1}):
        with pytest.raises(ValueError):
            await store.upsert_run_record(bad)
    with pytest.raises(ValueError):
        await store.upsert_run_record({"state": "answered"})                     # no run id
    assert (await store.get_run_record("r1"))["state"] == "step_limit"


async def case_ensure_indexes_can_run_twice(store):
    await store.ensure_indexes()
    await store.ensure_indexes()


# --- concurrency (anyio) --------------------------------------------------------------------------------------------

async def case_racing_admissions_under_the_cap_all_pass_and_no_start_is_lost(store):
    results: dict[int, object] = {}

    async def go(i):
        results[i] = await store.admit(f"run-{i}", T)

    async with anyio.create_task_group() as tg:
        for i in range(10):
            tg.start_soon(go, i)
    assert all(isinstance(r, Admission) for r in results.values())          # spend is $0: under the cap
    m = await store.read_month(MONTH)
    assert m["days"][DAY]["runs_started"] == 10                              # the atomic count lost none
    assert await store.read_stops(day=DAY) == []


async def case_racing_admissions_at_the_cap_are_all_refused_and_all_recorded(store):
    await spend(store, "base", 10.0)
    results: dict[int, object] = {}

    async def go(i):
        results[i] = await store.admit(f"racer-{i}", T)

    async with anyio.create_task_group() as tg:
        for i in range(6):
            tg.start_soon(go, i)
    assert all(r == Refusal("daily_cap") for r in results.values())
    m = await store.read_month(MONTH)
    assert m["days"][DAY]["runs_started"] == 1 and m["days"][DAY]["stops"] == {"daily_cap": 6}
    assert len(await store.read_stops(day=DAY)) == 6


async def case_racing_admissions_on_a_new_month_create_it_once_and_count_every_start(store):
    results: dict[int, object] = {}

    async def go(i):
        results[i] = await store.admit(f"new-{i}", at("07-01", 0, 0, 1))

    async with anyio.create_task_group() as tg:
        for i in range(8):
            tg.start_soon(go, i)
    assert all(isinstance(r, Admission) for r in results.values())
    assert (await store.read_month("2030-07"))["days"]["2030-07-01"]["runs_started"] == 8


async def case_admissions_and_spend_racing_across_a_cap_that_spend_is_just_under(store):
    base = await spend(store, "base", 9.99)                  # $0.01 under the $10 day
    admitted: list = []
    refused: list = []

    async def reach_the_cap():
        await store.record_spend(base, 0.01)                 # spend reaches exactly $10.00

    async def go(i):
        r = await store.admit(f"racer-{i}", T)
        (admitted if isinstance(r, Admission) else refused).append(r)

    async with anyio.create_task_group() as tg:
        for i in range(3):
            tg.start_soon(go, i)
        tg.start_soon(reach_the_cap)
        for i in range(3, 6):
            tg.start_soon(go, i)
    # which racers saw the spend before it reached the cap is up to the interleaving; both outcomes are right, but
    # every racer got exactly one, each admission was counted once, and every refusal is the daily cap
    assert len(admitted) + len(refused) == 6
    assert all(r == Refusal("daily_cap") for r in refused)
    m = await store.read_month(MONTH)
    assert m["days"][DAY]["runs_started"] == 1 + len(admitted)               # none lost, none doubled
    assert m["days"][DAY].get("stops", {}).get("daily_cap", 0) == len(refused)
    assert close(figures(m)[1], 10.0)
    # once spend has reached the cap, no admission passes
    assert await store.admit("after", T) == Refusal("daily_cap")
    assert await store.admit("after-2", T) == Refusal("daily_cap")


async def case_concurrent_record_spend_loses_nothing(store):
    a = await store.admit("run-a", T)

    async def go():
        await store.record_spend(a, 0.1)

    async with anyio.create_task_group() as tg:
        for _ in range(10):
            tg.start_soon(go)
    ms, ds = figures(await store.read_month(MONTH))
    assert close(ms, 1.0) and close(ds, 1.0)


async def case_concurrent_record_spend_creating_the_month_loses_nothing(store):
    async def go():
        await store.record_spend(Admission("ghost", "2030-08", "2030-08-02"), 0.1)

    async with anyio.create_task_group() as tg:
        for _ in range(6):
            tg.start_soon(go)
    m = await store.read_month("2030-08")
    assert close(m["spent"], 0.6) and close(m["days"]["2030-08-02"]["spent"], 0.6)


ALL = [v for k, v in sorted(globals().items()) if k.startswith("case_") and callable(v)]
