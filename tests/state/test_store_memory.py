"""MemoryStore: the fake every other part tests against. Same semantics as MongoStore (contract §4.E)."""

import asyncio
from datetime import UTC, datetime, timedelta

import pytest

from api import settings
from api.protocols import Refusal, Reservation
from api.state.store import MemoryStore, StoreUnavailable
from tests.state import cases
from tests.state.cases import T, W, event


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
    assert {"read_month", "read_stops", "get_run_record", "reserve", "settle", "release"} <= set(names)
    assert "count_run_started" not in names                   # reserve counts the start (8492353)
    for cls in (MemoryStore, MongoStore):
        assert not hasattr(cls, "count_run_started")
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
              "reserve", "settle", "release", "open_reservations", "record_stop", "flag_until",
              "set_flag", "live_status", "read_month", "read_stops", "get_run_record"):
        assert f"store.{m}(" in text, m
    assert "count_run_started" not in text


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
async def test_unreachable_atlas_refuses_reservations_and_records_it_as_not_a_budget_stop():
    store = MemoryStore()
    store.unreachable = True
    assert await store.reserve("run-a", W, T) == Refusal("atlas_unreachable")
    store.unreachable = False
    stops = await store.read_stops(day="2030-05-14")
    assert [(s["kind"], s["budget"], s["run"]) for s in stops] == [("atlas_unreachable", False, "run-a")]
    assert stops[0]["month_spent"] is None                                # unknown, not zero
    assert (await store.read_month("2030-05"))["days"]["2030-05-14"]["stops"] == {"atlas_unreachable": 1}
    assert await store.open_reservations(T) == []                         # nothing was reserved


@pytest.mark.anyio
async def test_other_operations_raise_store_unavailable_when_unreachable():
    store = MemoryStore()
    store.unreachable = True
    for call in (lambda: store.append_events("r1", [event("r1", 1)]), lambda: store.read_events("r1", 0),
                 lambda: store.put_heartbeat("r1", 1, T), lambda: store.latest_heartbeat("r1"),
                 lambda: store.upsert_run_record({"run": "r1"}), lambda: store.settle(Reservation("r", "2030-05", "2030-05-14", 1), 0.1),
                 lambda: store.release(Reservation("r", "2030-05", "2030-05-14", 1)), lambda: store.open_reservations(T),
                 lambda: store.flag_until("exa_out_of_credit", T), lambda: store.set_flag("exa_out_of_credit", T)):
        with pytest.raises(StoreUnavailable):
            await call()


@pytest.mark.anyio
async def test_live_status_is_unknown_when_unreachable_or_slower_than_the_timeout():
    unknown = {"live_research": "unknown", "update_check": "unknown"}
    store = MemoryStore()
    store.unreachable = True
    assert await store.live_status(T, W, 2.0) == unknown
    slow = MemoryStore(latency_s=0.2)
    assert await slow.live_status(T, W, 0.01) == unknown
    assert (await slow.live_status(T, W, 5.0))["live_research"] == "open"


@pytest.mark.anyio
async def test_latency_lets_racing_reservations_interleave():
    # with I/O in every call, a read-then-write implementation would let two runs take the last room
    store = MemoryStore(latency_s=0.005)
    await store.reserve("base", 7.0, T)
    results = await asyncio.gather(*(store.reserve(f"r{i}", 2.0, T) for i in range(4)))
    assert sum(isinstance(r, Reservation) for r in results) == 1


@pytest.mark.anyio
async def test_returned_documents_are_copies():
    store = MemoryStore()
    await store.append_events("r1", [event("r1", 1, deep={"a": 1})])
    got = await store.read_events("r1", 0)
    got[0]["data"]["deep"]["a"] = 99
    assert (await store.read_events("r1", 0))[0]["data"]["deep"]["a"] == 1
    await store.reserve("run-a", W, T)
    m = await store.read_month("2030-05")
    m["reserved"] = 0
    assert (await store.read_month("2030-05"))["reserved"] == W


@pytest.mark.anyio
async def test_a_record_stored_is_not_aliased_to_the_callers_dict():
    store = MemoryStore()
    rec = {"run": "r1", "state": "answered"}
    await store.upsert_run_record(rec)
    rec["state"] = "changed"
    assert (await store.get_run_record("r1"))["state"] == "answered"
