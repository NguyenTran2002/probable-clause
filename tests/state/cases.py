"""The semantic cases every Store must pass (contract §4.E, §8; T3.4).

Plain async functions taking a store. They run against MemoryStore, against MongoStore over the fake database
(tests/state/fakes.py), and, when PC_ATLAS_TEST=1, against MongoStore on Probable_Clause_test. The dates are in
2030 so no case touches a real month, and each case is written so that it starts from an empty store.
"""

from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

import anyio
import pytest

from api.protocols import BUDGET_STOPS, StopKind, Refusal, Reservation

CHI = ZoneInfo("America/Chicago")
W = 1.674                        # about a run's worst case (T3.4)
T = datetime(2030, 5, 14, 12, 0, tzinfo=CHI)
DAY, MONTH = "2030-05-14", "2030-05"


def at(month_day: str, hh=12, mm=0, ss=0) -> datetime:
    """A Chicago instant in 2030: at("05-14", 23, 59)."""
    m, d = (int(x) for x in month_day.split("-"))
    return datetime(2030, m, d, hh, mm, ss, tzinfo=CHI)


def close(a, b, tol=1e-9):
    return abs(a - b) <= tol


def figures(month_doc, day=DAY):
    """(month spent, month reserved, day spent, day reserved), missing fields read as zero."""
    d = (month_doc or {}).get("days", {}).get(day, {})
    return ((month_doc or {}).get("spent", 0.0), (month_doc or {}).get("reserved", 0.0),
            d.get("spent", 0.0), d.get("reserved", 0.0))


def event(run, n, kind="tool_call", **data):
    return {"v": 1, "run": run, "n": n, "t_ms": n * 100, "at": "2030-05-14T12:00:00.000-05:00", "kind": kind, "data": data}


# --- reserve ------------------------------------------------------------------------------------------------------

async def case_reserve_success(store):
    r = await store.reserve("run-a", W, T)
    assert r == Reservation("run-a", MONTH, DAY, W)
    m = await store.read_month(MONTH)
    ms, mr, ds, dr = figures(m)
    assert close(ms, 0) and close(mr, W) and close(ds, 0) and close(dr, W)
    assert m["days"][DAY]["runs_started"] == 1
    open_ = await store.open_reservations(T)
    assert [(o["run"], o["month"], o["day"]) for o in open_] == [("run-a", MONTH, DAY)]
    assert close(open_[0]["amount"], W)


async def case_five_runs_fit_a_day_and_the_sixth_is_refused_and_recorded(store):
    for i in range(5):
        assert isinstance(await store.reserve(f"run-{i}", W, T + timedelta(minutes=i)), Reservation)
    refusal = await store.reserve("run-6", W, T + timedelta(minutes=9))
    assert refusal == Refusal("daily_cap")
    m = await store.read_month(MONTH)
    assert close(figures(m)[1], 5 * W) and close(figures(m)[3], 5 * W)          # nothing was reserved for run-6
    assert m["days"][DAY]["runs_started"] == 5                                   # a refusal is not a start
    assert m["days"][DAY]["stops"] == {"daily_cap": 1}
    stops = await store.read_stops(day=DAY)
    assert len(stops) == 1
    s = stops[0]
    assert s["kind"] == "daily_cap" and s["run"] == "run-6" and s["budget"] is True
    assert s["date"] == DAY and s["time"] == "12:09:00"
    assert close(s["day_reserved"], 5 * W) and close(s["month_reserved"], 5 * W)
    assert close(s["day_spent"], 0) and close(s["month_spent"], 0)
    assert isinstance(s["at"], datetime)


async def case_the_cap_is_inclusive_and_float_noise_does_not_refuse(store):
    # 25 x 0.4 sums to 10.000000000000004 in floating point: exactly the cap, so all 25 must fit
    for i in range(25):
        r = await store.reserve(f"run-{i}", 0.4, T)
        assert isinstance(r, Reservation), f"reservation {i} refused"
    assert await store.reserve("run-26", 0.4, T) == Refusal("daily_cap")


async def case_four_at_two_and_a_half_fill_a_day_exactly(store):
    for i in range(4):
        assert isinstance(await store.reserve(f"run-{i}", 2.5, T), Reservation)
    assert await store.reserve("run-5", 0.01, T) == Refusal("daily_cap")


async def case_monthly_cap_refuses_when_the_month_is_full_and_is_recorded(store):
    # $5 a run: two fill a day ($10), twelve fill $60 across six days
    n = 0
    for d in range(1, 7):
        for _ in range(2):
            assert isinstance(await store.reserve(f"run-{n}", 5.0, at(f"05-{d:02d}")), Reservation)
            n += 1
    assert await store.reserve("run-next-day", 5.0, at("05-07")) == Refusal("monthly_cap")
    m = await store.read_month(MONTH)
    assert close(m["reserved"], 60.0)
    assert m["days"]["2030-05-07"]["stops"] == {"monthly_cap": 1}
    stops = await store.read_stops(month=MONTH)
    assert [(s["kind"], s["budget"], s["run"], s["date"]) for s in stops] == [("monthly_cap", True, "run-next-day", "2030-05-07")]
    assert close(stops[0]["month_reserved"], 60.0)


async def case_monthly_cap_wins_when_both_caps_are_exceeded(store):
    n = 0
    for d in range(1, 7):
        for _ in range(2):
            await store.reserve(f"run-{n}", 5.0, at(f"05-{d:02d}"))
            n += 1
    # day 6 is full ($10) and the month is full ($60): the longer pause is the one to report
    assert await store.reserve("late", 5.0, at("05-06", 23)) == Refusal("monthly_cap")
    m = await store.read_month(MONTH)
    assert m["days"]["2030-05-06"]["stops"] == {"monthly_cap": 1}


async def case_the_day_is_a_chicago_day_not_a_utc_day(store):
    evening = datetime(2030, 5, 14, 22, 0, tzinfo=CHI)          # 03:00 UTC on May 15
    assert evening.astimezone(UTC).day == 15
    r = await store.reserve("evening", W, evening.astimezone(UTC))
    assert r.day == "2030-05-14" and r.month == MONTH


async def case_a_new_chicago_day_has_a_fresh_daily_cap_in_the_same_month(store):
    for i in range(5):
        await store.reserve(f"a{i}", W, at("05-14", 23, 59, 0))
    assert await store.reserve("a-refused", W, at("05-14", 23, 59, 30)) == Refusal("daily_cap")
    r = await store.reserve("b0", W, at("05-15", 0, 0, 30))
    assert isinstance(r, Reservation) and r.day == "2030-05-15"
    m = await store.read_month(MONTH)
    assert close(m["reserved"], 6 * W)                              # the month keeps counting
    assert close(figures(m, "2030-05-15")[3], W)


async def case_a_new_month_starts_a_new_document(store):
    last = at("05-31", 23, 59, 59)
    first = at("06-01", 0, 0, 1)
    r1 = await store.reserve("may", 5.0, last)
    r2 = await store.reserve("june", 5.0, first)
    assert (r1.month, r2.month) == ("2030-05", "2030-06")
    assert close((await store.read_month("2030-05"))["reserved"], 5.0)
    assert close((await store.read_month("2030-06"))["reserved"], 5.0)


async def case_the_daylight_saving_day_is_one_chicago_day(store):
    # Nov 3 2030 is the fall-back Sunday; 01:30 happens twice. Both are the same Chicago day.
    first = datetime(2030, 11, 3, 1, 30, tzinfo=CHI, fold=0)
    second = datetime(2030, 11, 3, 1, 30, tzinfo=CHI, fold=1)
    r1 = await store.reserve("one", 2.5, first)
    r2 = await store.reserve("two", 2.5, second)
    assert r1.day == r2.day == "2030-11-03"
    assert close(figures(await store.read_month("2030-11"), "2030-11-03")[3], 5.0)


async def case_reserving_twice_for_one_run_is_a_bug(store):
    await store.reserve("run-a", W, T)
    with pytest.raises(ValueError):
        await store.reserve("run-a", W, T)
    assert close((await store.read_month(MONTH))["reserved"], W)    # not double-counted


async def case_bad_inputs_are_refused_before_anything_is_written(store):
    with pytest.raises(ValueError):
        await store.reserve("bad.id", W, T)
    with pytest.raises(ValueError):
        await store.reserve("$bad", W, T)
    with pytest.raises(ValueError):
        await store.reserve("ok", 0.0, T)
    with pytest.raises(ValueError):
        await store.reserve("ok", float("nan"), T)
    with pytest.raises(ValueError):
        await store.reserve("ok", W, datetime(2030, 5, 14, 12, 0))   # naive
    assert await store.read_month(MONTH) is None


# --- settle and release -------------------------------------------------------------------------------------------

async def case_settle_moves_cost_from_reserved_to_spent_and_release_frees_the_rest(store):
    r = await store.reserve("run-a", W, T)
    await store.settle(r, 0.5)
    ms, mr, ds, dr = figures(await store.read_month(MONTH))
    assert close(ms, 0.5) and close(mr, W - 0.5) and close(ds, 0.5) and close(dr, W - 0.5)
    await store.settle(r, 0.3)
    ms, mr, ds, dr = figures(await store.read_month(MONTH))
    assert close(ms, 0.8) and close(mr, W - 0.8)
    open_ = await store.open_reservations(T)
    assert close(open_[0]["amount"], W - 0.8)
    await store.release(r)
    m = await store.read_month(MONTH)
    ms, mr, ds, dr = figures(m)
    assert close(ms, 0.8) and close(mr, 0.0) and close(ds, 0.8) and close(dr, 0.0)
    assert await store.open_reservations(T) == []
    assert m["reservations"] == {}


async def case_settle_beyond_the_reservation_is_spent_in_full_and_reserved_never_goes_negative(store):
    r = await store.reserve("run-a", 1.0, T)
    await store.settle(r, 1.5)
    ms, mr, ds, dr = figures(await store.read_month(MONTH))
    assert close(ms, 1.5) and close(mr, 0.0) and close(ds, 1.5) and close(dr, 0.0)
    await store.settle(r, 0.25)           # nothing left to move: still counted as spent
    ms, mr, ds, dr = figures(await store.read_month(MONTH))
    assert close(ms, 1.75) and close(mr, 0.0)


async def case_settle_after_release_still_counts_the_spend(store):
    r = await store.reserve("run-a", W, T)
    await store.release(r)
    await store.settle(r, 0.4)
    ms, mr, ds, dr = figures(await store.read_month(MONTH))
    assert close(ms, 0.4) and close(mr, 0.0) and close(ds, 0.4)


async def case_release_twice_is_harmless(store):
    r = await store.reserve("run-a", W, T)
    await store.release(r)
    await store.release(r)
    assert close(figures(await store.read_month(MONTH))[1], 0.0)


async def case_an_unsettled_reservation_stays_counted_until_released(store):
    for i in range(5):
        await store.reserve(f"run-{i}", W, T)           # five instances "lost mid-run"
    assert await store.reserve("run-6", W, T) == Refusal("daily_cap")
    open_ = await store.open_reservations(T)
    assert sorted(o["run"] for o in open_) == [f"run-{i}" for i in range(5)]
    await store.release(Reservation("run-0", MONTH, DAY, W))
    assert isinstance(await store.reserve("run-7", W, T), Reservation)


async def case_spend_counts_toward_the_day_and_month_the_run_started_in(store):
    r = await store.reserve("late", W, at("05-31", 23, 59, 30))     # started just before midnight, May 31
    await store.settle(r, 0.9)                                      # settled after midnight: still May 31
    may = await store.read_month("2030-05")
    assert close(may["spent"], 0.9) and close(may["days"]["2030-05-31"]["spent"], 0.9)
    assert await store.read_month("2030-06") is None
    await store.release(r)
    assert close((await store.read_month("2030-05"))["reserved"], 0.0)


async def case_open_reservations_span_months_and_carry_their_age(store):
    await store.reserve("may", 1.0, at("05-31", 23, 0))
    await store.reserve("june", 2.0, at("06-01", 1, 0))
    now = at("06-01", 2, 0)
    open_ = await store.open_reservations(now)
    by_run = {o["run"]: o for o in open_}
    assert set(by_run) == {"may", "june"}
    assert by_run["may"]["month"] == "2030-05" and by_run["june"]["month"] == "2030-06"
    assert close(by_run["june"]["age_s"], 3600.0, 1.0) and close(by_run["may"]["age_s"], 3 * 3600.0, 1.0)
    assert [o["run"] for o in open_] == ["may", "june"]             # oldest first


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


async def case_the_spend_limit_flag_pauses_reservations_without_recording_a_stop(store):
    await store.set_flag("anthropic_spend_limit", T)
    assert await store.reserve("run-a", W, T) == Refusal("spend_limit_paused")
    m = await store.read_month(MONTH)
    assert m is None or (close(figures(m)[1], 0) and m["days"].get(DAY, {}).get("runs_started", 0) == 0)
    assert await store.read_stops(month=MONTH) == []
    # it lapses on the 1st of the next month
    r = await store.reserve("run-b", W, at("06-01", 0, 0, 5))
    assert isinstance(r, Reservation)


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
    assert {s["kind"] for s in stops if not s["budget"]} == {"atlas_unreachable", "time_limit"}
    assert stops[0]["run"] == "run-0" and stops[1]["run"] is None
    assert stops[3]["detail"] == {"rounds": 3}
    counts = (await store.read_month(MONTH))["days"][DAY]["stops"]
    assert counts == {k: 1 for k in kinds}


async def case_stop_counts_accumulate_per_day_and_records_show_spend_at_that_moment(store):
    r = await store.reserve("run-a", W, T)
    await store.settle(r, 0.5)
    await store.record_stop("step_limit", "run-a", T + timedelta(minutes=1), {})
    await store.record_stop("step_limit", "run-b", T + timedelta(minutes=2), {})
    await store.record_stop("step_limit", "run-c", at("05-15", 9, 0), {})
    m = await store.read_month(MONTH)
    assert m["days"][DAY]["stops"] == {"step_limit": 2}
    assert m["days"]["2030-05-15"]["stops"] == {"step_limit": 1}
    today = await store.read_stops(day=DAY)
    assert [s["run"] for s in today] == ["run-a", "run-b"]
    assert close(today[0]["day_spent"], 0.5) and close(today[0]["day_reserved"], W - 0.5)
    assert len(await store.read_stops(month=MONTH)) == 3
    assert len(await store.read_stops(day="2030-05-15")) == 1


async def case_record_stop_works_on_a_month_with_no_document_yet(store):
    await store.record_stop("atlas_unreachable", None, T, {})
    m = await store.read_month(MONTH)
    assert m["days"][DAY]["stops"] == {"atlas_unreachable": 1}
    assert close(m["spent"], 0) and close(m["reserved"], 0)
    # a reservation afterwards must still be checked against real totals, not a partial document
    for i in range(5):
        assert isinstance(await store.reserve(f"run-{i}", W, T), Reservation)
    assert await store.reserve("run-6", W, T) == Refusal("daily_cap")


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
    s = await store.live_status(T, W, 2.0)
    assert s == {"live_research": "open", "update_check": "available"}
    for i in range(5):
        await store.reserve(f"run-{i}", W, T)              # 8.37 reserved: one more would be 10.044
    s = await store.live_status(T, W, 2.0)
    assert s["live_research"] == "paused_day"
    assert (await store.live_status(at("05-15"), W, 2.0))["live_research"] == "open"   # the next day
    assert (await store.live_status(T, 1.0, 2.0))["live_research"] == "open"           # a smaller worst case still fits


async def case_live_status_paused_month_wins_over_paused_day(store):
    n = 0
    for d in range(1, 7):
        for _ in range(2):
            await store.reserve(f"run-{n}", 5.0, at(f"05-{d:02d}"))
            n += 1
    assert (await store.live_status(at("05-06", 20), W, 2.0))["live_research"] == "paused_month"
    assert (await store.live_status(at("05-07", 8), 5.0, 2.0))["live_research"] == "paused_month"
    assert (await store.live_status(at("06-01", 8), W, 2.0))["live_research"] == "open"


async def case_live_status_counts_settled_spend_too(store):
    r = await store.reserve("run-a", W, T)
    await store.settle(r, W)
    await store.release(r)
    for i in range(4):
        r = await store.reserve(f"run-{i}", W, T)
        await store.settle(r, W)
        await store.release(r)
    assert (await store.live_status(T, W, 2.0))["live_research"] == "paused_day"      # 5 x 1.674 spent


async def case_live_status_flags(store):
    await store.set_flag("anthropic_spend_limit", T)
    s = await store.live_status(T, W, 2.0)
    assert s["live_research"] == "paused_month" and s["update_check"] == "available"
    await store.set_flag("exa_out_of_credit", T)
    s = await store.live_status(T, W, 2.0)
    assert s == {"live_research": "paused_month", "update_check": "unavailable"}
    s = await store.live_status(at("06-01", 0, 0, 1), W, 2.0)                         # both lapse on the 1st
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

async def case_ten_runs_race_and_exactly_five_get_in(store):
    results: dict[int, object] = {}

    async def go(i):
        results[i] = await store.reserve(f"run-{i}", W, T)

    async with anyio.create_task_group() as tg:
        for i in range(10):
            tg.start_soon(go, i)
    ok = [r for r in results.values() if isinstance(r, Reservation)]
    refused = [r for r in results.values() if isinstance(r, Refusal)]
    assert len(ok) == 5 and len(refused) == 5 and all(r.kind == "daily_cap" for r in refused)
    m = await store.read_month(MONTH)
    assert close(m["reserved"], 5 * W) and m["days"][DAY]["runs_started"] == 5
    assert m["days"][DAY]["stops"] == {"daily_cap": 5}
    assert len(await store.open_reservations(T)) == 5


async def case_two_runs_racing_for_the_last_room_cannot_both_succeed(store):
    await store.reserve("base", 7.0, T)                    # $3 of room left in the day: one $2 run fits, not two
    results: dict[int, object] = {}

    async def go(i):
        results[i] = await store.reserve(f"racer-{i}", 2.0, T)

    async with anyio.create_task_group() as tg:
        for i in range(4):
            tg.start_soon(go, i)
    wins = [i for i, r in results.items() if isinstance(r, Reservation)]
    assert len(wins) == 1
    assert close((await store.read_month(MONTH))["reserved"], 9.0)


async def case_concurrent_settles_of_one_reservation_lose_nothing(store):
    r = await store.reserve("run-a", 2.0, T)

    async def go():
        await store.settle(r, 0.1)

    async with anyio.create_task_group() as tg:
        for _ in range(10):
            tg.start_soon(go)
    ms, mr, ds, dr = figures(await store.read_month(MONTH))
    assert close(ms, 1.0) and close(mr, 1.0) and close(ds, 1.0) and close(dr, 1.0)
    assert close((await store.open_reservations(T))[0]["amount"], 1.0)


ALL = [v for k, v in sorted(globals().items()) if k.startswith("case_") and callable(v)]
