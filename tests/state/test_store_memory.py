"""MemoryStore: the fake every other part tests against. Same semantics as MongoStore (contract §4.E)."""

import asyncio
from datetime import UTC, datetime, timedelta

import pytest

from api import settings
from api.protocols import Admission, Refusal
from api.state.store import MemoryStore, StoreUnavailable
from tests.state import cases
from tests.state.cases import T, event


@pytest.mark.anyio
@pytest.mark.parametrize("case", cases.ALL, ids=lambda c: c.__name__)
async def test_semantics(case):
    store = MemoryStore()
    await store.ensure_indexes()
    await case(store)


def test_both_stores_implement_every_method_of_the_protocol_with_its_exact_signature():
    import inspect
    from api.protocols import Store
    from api.state.store import MongoStore
    names = [n for n, v in vars(Store).items() if inspect.iscoroutinefunction(v)]
    assert {"read_month", "read_stops", "get_run_record", "admit", "record_spend", "live_status"} <= set(names)
    assert not {"reserve", "settle", "release", "open_reservations", "count_run_started"} & set(names)    # P4.21
    for cls in (MemoryStore, MongoStore):
        for gone in ("reserve", "settle", "release", "open_reservations", "count_run_started"):
            assert not hasattr(cls, gone), f"{cls.__name__}.{gone} should be gone (P4.21)"
        for n in names:
            impl = getattr(cls, n, None)
            assert inspect.iscoroutinefunction(impl), f"{cls.__name__}.{n} must be an async method"
            want = list(inspect.signature(getattr(Store, n)).parameters.values())[1:]
            got = list(inspect.signature(impl).parameters.values())[1:]
            assert [(p.name, p.kind, p.default) for p in got] == [(p.name, p.kind, p.default) for p in want], \
                f"{cls.__name__}.{n} does not match the protocol"


def test_the_cases_cover_every_store_method():
    # a guard against a case file that quietly stops exercising a method
    text = open(cases.__file__, encoding="utf-8").read()
    for m in ("ensure_indexes", "append_events", "read_events", "put_heartbeat", "latest_heartbeat", "upsert_run_record",
              "admit", "record_spend", "record_stop", "flag_until",
              "set_flag", "live_status", "read_month", "read_stops", "get_run_record"):
        assert f"store.{m}(" in text, m
    for gone in ("reserve", "settle", "release", "open_reservations", "count_run_started"):
        assert f"store.{gone}(" not in text, gone


@pytest.mark.anyio
async def test_ttl_is_simulated_by_expire():
    store = MemoryStore()
    await store.append_events("r1", [event("r1", 1), event("r1", 2)])
    await store.put_heartbeat("r1", 2, datetime.now(UTC))
    soon = datetime.now(UTC) + timedelta(seconds=int(settings.EVENTS_TTL_S.value) - 60)
    store.expire(soon)
    assert len(await store.read_events("r1", 0)) == 2                     # not yet
    store.expire(datetime.now(UTC) + timedelta(seconds=int(settings.EVENTS_TTL_S.value) + 60))
    assert await store.read_events("r1", 0) == []                         # events gone after 24 h
    # heartbeats expire on their own, much shorter, clock (T3.7)
    assert await store.latest_heartbeat("r1") is None


@pytest.mark.anyio
async def test_heartbeat_ttl_is_ten_minutes_from_its_at():
    store = MemoryStore()
    await store.put_heartbeat("r1", 2, T)
    store.expire(T + timedelta(seconds=int(settings.HEARTBEATS_TTL_S.value) - 1))
    assert await store.latest_heartbeat("r1") == T
    store.expire(T + timedelta(seconds=int(settings.HEARTBEATS_TTL_S.value) + 1))
    assert await store.latest_heartbeat("r1") is None


@pytest.mark.anyio
async def test_events_created_uses_the_injected_clock():
    t0 = datetime(2030, 1, 1, tzinfo=UTC)
    store = MemoryStore(clock=lambda: t0)
    await store.append_events("r1", [event("r1", 1)])
    store.expire(t0 + timedelta(seconds=int(settings.EVENTS_TTL_S.value) - 1))
    assert len(await store.read_events("r1", 0)) == 1
    store.expire(t0 + timedelta(seconds=int(settings.EVENTS_TTL_S.value) + 1))
    assert await store.read_events("r1", 0) == []


@pytest.mark.anyio
async def test_unreachable_atlas_refuses_admission_and_writes_nothing():
    store = MemoryStore()
    store.unreachable = True
    assert await store.admit("run-a", T) == Refusal("atlas_unreachable")
    store.unreachable = False
    # a dead Atlas could not have recorded the stop or created the month: neither is simulated
    assert await store.read_stops(day="2030-05-14") == []
    assert await store.read_month("2030-05") is None


@pytest.mark.anyio
async def test_a_zero_cost_never_touches_the_store_so_it_never_raises_when_unreachable():
    store = MemoryStore()
    store.unreachable = True
    await store.record_spend(Admission("r", "2030-05", "2030-05-14"), 0.0)
    with pytest.raises(ValueError):
        await store.record_spend(Admission("r", "2030-05", "2030-05-14"), -1.0)       # still validated
    store.unreachable = False
    assert await store.read_month("2030-05") is None


@pytest.mark.anyio
async def test_a_month_made_by_admit_has_the_shape_mongostore_makes():
    store = MemoryStore()
    await store.admit("run-a", T)
    assert await store.read_month("2030-05") == {"_id": "2030-05", "spent": 0.0,
                                                 "days": {"2030-05-14": {"spent": 0.0, "runs_started": 1}}}
    other = MemoryStore()
    await other.record_spend(Admission("g", "2030-05", "2030-05-14"), 0.25)
    assert set(await other.read_month("2030-05")) == {"_id", "spent", "days"}


@pytest.mark.anyio
async def test_a_null_spent_reads_as_zero_and_a_malformed_document_fails_closed():
    store = MemoryStore()
    store._spend["2030-05"] = {"_id": "2030-05", "spent": None, "days": {"2030-05-14": {"spent": None, "runs_started": 0}}}
    assert isinstance(await store.admit("run-a", T), Admission)
    assert (await store.live_status(T, 2.0))["live_research"] == "open"
    bad = MemoryStore()
    bad._spend["2030-05"] = {"_id": "2030-05", "spent": "lots", "days": {}}
    assert await bad.admit("run-b", T) == Refusal("atlas_unreachable")                 # no TypeError out of admit
    assert await bad.live_status(T, 2.0) == {"live_research": "unknown", "update_check": "unknown"}
    worse = MemoryStore()
    worse._spend["2030-05"] = {"_id": "2030-05", "spent": 1.0, "days": {"2030-05-14": {"spent": [1]}}}
    assert await worse.admit("run-c", T) == Refusal("atlas_unreachable")
    assert (await worse.live_status(T, 2.0))["live_research"] == "unknown"


@pytest.mark.anyio
async def test_other_operations_raise_store_unavailable_when_unreachable():
    store = MemoryStore()
    store.unreachable = True
    a = Admission("r", "2030-05", "2030-05-14")
    for call in (lambda: store.append_events("r1", [event("r1", 1)]), lambda: store.read_events("r1", 0),
                 lambda: store.put_heartbeat("r1", 1, T), lambda: store.latest_heartbeat("r1"),
                 lambda: store.upsert_run_record({"run": "r1"}), lambda: store.record_spend(a, 0.1),
                 lambda: store.flag_until("exa_out_of_credit", T), lambda: store.set_flag("exa_out_of_credit", T)):
        with pytest.raises(StoreUnavailable):
            await call()


@pytest.mark.anyio
async def test_live_status_is_unknown_when_unreachable_or_slower_than_the_timeout():
    unknown = {"live_research": "unknown", "update_check": "unknown"}
    store = MemoryStore()
    store.unreachable = True
    assert await store.live_status(T, 2.0) == unknown
    slow = MemoryStore(latency_s=0.2)
    assert await slow.live_status(T, 0.01) == unknown
    assert (await slow.live_status(T, 5.0))["live_research"] == "open"


@pytest.mark.anyio
async def test_latency_lets_racing_admissions_interleave_without_losing_a_start():
    # with I/O in every call, a read-then-write implementation would lose counts
    store = MemoryStore(latency_s=0.005)
    results = await asyncio.gather(*(store.admit(f"r{i}", T) for i in range(8)))
    assert all(isinstance(r, Admission) for r in results)
    assert (await store.read_month("2030-05"))["days"]["2030-05-14"]["runs_started"] == 8


@pytest.mark.anyio
async def test_returned_documents_are_copies():
    store = MemoryStore()
    await store.append_events("r1", [event("r1", 1, deep={"a": 1})])
    got = await store.read_events("r1", 0)
    got[0]["data"]["deep"]["a"] = 99
    assert (await store.read_events("r1", 0))[0]["data"]["deep"]["a"] == 1
    a = await store.admit("run-a", T)
    await store.record_spend(a, 0.5)
    m = await store.read_month("2030-05")
    m["spent"] = 0
    assert (await store.read_month("2030-05"))["spent"] == 0.5


@pytest.mark.anyio
async def test_a_record_stored_is_not_aliased_to_the_callers_dict():
    store = MemoryStore()
    rec = {"run": "r1", "state": "answered"}
    await store.upsert_run_record(rec)
    rec["state"] = "changed"
    assert (await store.get_run_record("r1"))["state"] == "answered"


# --- documents written before v2.0 (they hold `reserved` and `reservations`) -------------------------------------------

def old_month(spent=1.0, day_spent=1.0, reserved=9.0):
    """A month as the reservation design left it: reserved money is not spend."""
    return {"_id": "2030-05", "spent": spent, "reserved": reserved,
            "days": {"2030-05-14": {"spent": day_spent, "reserved": reserved, "runs_started": 3}},
            "reservations": {"old-run": {"day": "2030-05-14", "amount": reserved, "at": T}}}


@pytest.mark.anyio
async def test_old_reserved_money_is_never_counted_as_spend():
    store = MemoryStore()
    store._spend["2030-05"] = old_month()                         # $9 reserved on a $10 day, $1 spent
    assert isinstance(await store.admit("run-a", T), Admission)
    assert (await store.live_status(T, 2.0))["live_research"] == "open"
    store2 = MemoryStore()
    store2._spend["2030-05"] = old_month(spent=1.0, day_spent=10.0)         # $10 actually spent: at the cap
    assert await store2.admit("run-b", T) == Refusal("daily_cap")
    assert (await store2.live_status(T, 2.0))["live_research"] == "paused_day"


@pytest.mark.anyio
async def test_old_documents_are_read_written_to_in_spent_only_and_never_given_new_reservations():
    store = MemoryStore()
    store._spend["2030-05"] = old_month()
    a = await store.admit("run-a", T)
    await store.record_spend(a, 0.5)
    await store.record_stop("step_limit", "run-a", T, {})
    m = await store.read_month("2030-05")
    assert m["spent"] == pytest.approx(1.5) and m["days"]["2030-05-14"]["spent"] == pytest.approx(1.5)
    assert m["days"]["2030-05-14"]["runs_started"] == 4
    assert m["reserved"] == 9.0 and m["days"]["2030-05-14"]["reserved"] == 9.0 and "old-run" in m["reservations"]   # untouched
    [s] = await store.read_stops(day="2030-05-14")
    assert "month_reserved" not in s and "day_reserved" not in s


@pytest.mark.anyio
async def test_new_documents_have_no_reservation_fields():
    store = MemoryStore()
    a = await store.admit("run-a", T)
    await store.record_spend(a, 0.5)
    await store.record_spend(Admission("run-a", "2030-06", "2030-06-02"), 0.5)
    await store.record_stop("daily_cap", None, T, {})
    for month in ("2030-05", "2030-06"):
        m = await store.read_month(month)
        assert set(m) <= {"_id", "spent", "days"}
        assert all(set(d) <= {"spent", "runs_started", "stops"} for d in m["days"].values())
