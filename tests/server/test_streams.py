"""Events and streams (contract §4.H, §5, §6; T3.1): the envelope, the SSE frames, the keep-alive, the Atlas copy,
reconnects from memory and from Atlas, one stream per run, and the `interrupted` ending."""

import asyncio
import logging
import re
from datetime import datetime, timedelta

import pytest

from api import settings
from api.state.clock import CHICAGO
from api.state.store import MemoryStore
from tests.server.support import (EVENT_FIXTURES, QUESTION, START, VALIDATOR, FakeClock, FlakyStore, answered_script,
                                  ended_data, event_fixture, lifespan, loop_call, make_app, run_started_data)

pytestmark = pytest.mark.anyio
KEEPALIVE_S = float(settings.KEEPALIVE_S.value)
AT = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}-05:00$")


async def start(h, question=QUESTION, headers=None):
    run_id = (await h.client.post("/runs", {"question": question})).json()["run_id"]
    s = h.client.stream(f"/runs/{run_id}/events", headers)
    await h.clock.settle()
    s.pump()
    return run_id, s


def gated_script(gate: asyncio.Event, clock):
    """run_started, round_started, a paid call; wait on `gate`; then an answer block and run_ended."""
    async def script(ctx, deps):
        await ctx.emit("run_started", run_started_data(ctx))
        await ctx.emit("round_started", {"round": 1, "status_line": "Round 1 of 12 · 0 kept · update check not yet run"})
        await loop_call(ctx)
        await gate.wait()
        await ctx.emit("answer_block", {"index": 0, "text": "Done.", "citations": []})
        await ctx.emit("run_ended", ended_data(ctx, answer_chars=5))
    return script


# --- frames, envelope, keep-alive --------------------------------------------------------------------------------------
async def test_stream_frames_headers_and_close_after_run_ended():
    h = make_app()
    async with lifespan(h.app):
        run_id, s = await start(h)
        assert s.status == 200
        assert s.headers["content-type"] == "text/event-stream; charset=utf-8"
        assert s.headers["cache-control"] == "no-cache" and s.headers["x-accel-buffering"] == "no"
        assert "set-cookie" not in s.headers
        evs = s.events()
        assert [e["kind"] for e in evs] == ["run_started", "round_started", "paid_call", "answer_block", "run_ended"]
        assert s.closed, "the stream closes after run_ended"
        await h.clock.settle()
        assert s.task.done()
    assert h.schema_errors == []


async def test_envelope_numbering_time_and_offset():
    clock = FakeClock()

    async def script(ctx, deps):
        await ctx.emit("run_started", run_started_data(ctx))
        for i in range(1, 4):
            await clock.sleep(1.2345)
            await ctx.emit("round_started", {"round": i, "status_line": f"Round {i} of 12"})
        await ctx.emit("run_ended", ended_data(ctx, state="no_sources", answer_end="none", rounds=3)
                       | {"no_sources_reason": "out_of_scope", "note": "Outside the corpus."})

    h = make_app(script, clock=clock)
    async with lifespan(h.app):
        run_id, s = await start(h)
        await clock.advance(10)
        s.pump()
        evs = s.events()
        assert [e["n"] for e in evs] == [1, 2, 3, 4, 5]
        assert all(e["v"] == 1 and e["run"] == run_id for e in evs)
        assert [e["t_ms"] for e in evs] == [0, 1234, 2469, 3703, 3703]
        for e in evs:
            assert AT.match(e["at"])
            assert datetime.fromisoformat(e["at"]) == START + timedelta(milliseconds=e["t_ms"])
            assert not list(VALIDATOR.iter_errors(e))
    assert h.schema_errors == []


async def test_keep_alive_comment_every_keepalive_s_while_idle():
    clock = FakeClock()

    async def script(ctx, deps):
        await ctx.emit("run_started", run_started_data(ctx))
        await clock.sleep(2.5 * KEEPALIVE_S)
        await ctx.emit("run_ended", ended_data(ctx, state="failed", answer_end="none", rounds=0,
                                               failure_reason="overloaded"))

    h = make_app(script, clock=clock)
    async with lifespan(h.app):
        _, s = await start(h)
        assert s.text.count(": keep-alive") == 0
        await clock.advance(KEEPALIVE_S - 0.01)
        s.pump()
        assert s.text.count(": keep-alive") == 0
        await clock.advance(0.02)
        s.pump()
        assert s.text.count(": keep-alive\n\n") == 1
        await clock.advance(KEEPALIVE_S)
        s.pump()
        assert s.text.count(": keep-alive\n\n") == 2
        await clock.advance(KEEPALIVE_S)
        s.pump()
        assert s.closed and s.events()[-1]["kind"] == "run_ended"


# --- the Atlas copy ------------------------------------------------------------------------------------------------------
async def test_events_are_copied_to_atlas_in_order_with_bson_dates():
    h = make_app()
    async with lifespan(h.app):
        run_id, s = await start(h)
        await h.clock.settle()
        stored = await h.store.read_events(run_id, 0)
        assert stored == s.events()
        for n, doc in h.store._events[run_id].items():
            assert isinstance(doc["created"], datetime) and doc["created"].tzinfo is not None


async def test_a_slow_atlas_never_holds_up_the_stream():
    store = FlakyStore()
    store.gates["append_events"] = asyncio.Event()           # every event write waits
    h = make_app(store=store)
    async with lifespan(h.app):
        run_id, s = await start(h)
        assert s.closed and s.events()[-1]["kind"] == "run_ended"
        assert await store.inner.read_events(run_id, 0) == []          # nothing copied yet
        assert await store.inner.open_reservations(h.clock.now()) == []   # the money did not wait on the copy
        store.gates["append_events"].set()
        await h.clock.settle()
        assert [e["n"] for e in await store.inner.read_events(run_id, 0)] == [1, 2, 3, 4, 5]


async def test_a_failed_atlas_copy_never_stops_the_run_and_is_logged_by_kind(caplog):
    store = FlakyStore()
    store.fail["append_events"] = 2
    h = make_app(store=store)
    caplog.set_level(logging.INFO)
    async with lifespan(h.app):
        run_id, s = await start(h)
        await h.clock.settle()
        assert s.events()[-1]["data"]["state"] == "answered"
        assert [e["n"] for e in await store.inner.read_events(run_id, 0)] == [1, 2, 3, 4, 5]
    assert "StoreUnavailable" in caplog.text
    assert "db.example.internal" not in caplog.text and QUESTION not in caplog.text


async def test_atlas_down_for_the_whole_run(caplog):
    store = FlakyStore()
    store.fail["append_events"] = -1
    h = make_app(store=store)
    caplog.set_level(logging.INFO)
    async with lifespan(h.app):
        run_id, s = await start(h)
        await h.clock.settle()
        assert s.closed and s.events()[-1]["data"]["state"] == "answered"
        assert await store.inner.get_run_record(run_id) is not None
        assert await store.inner.open_reservations(h.clock.now()) == []
    assert "never copied" in caplog.text and "db.example.internal" not in caplog.text


# --- reconnects from memory, one stream per run --------------------------------------------------------------------------
@pytest.mark.parametrize("header,first", [("2", 3), ("0", 1), ("4", 5), ("junk", 1), ("-3", 1)])
async def test_reconnect_from_memory_honours_last_event_id(header, first):
    h = make_app()
    async with lifespan(h.app):
        run_id, s = await start(h)
        assert [e["n"] for e in s.events()] == [1, 2, 3, 4, 5]
        again = h.client.stream(f"/runs/{run_id}/events", {"Last-Event-ID": header})
        await h.clock.settle()
        again.pump()
        assert [e["n"] for e in again.events()] == list(range(first, 6))
        assert again.closed


async def test_reconnect_after_run_ended_sends_nothing_and_closes():
    h = make_app()
    async with lifespan(h.app):
        run_id, s = await start(h)
        again = h.client.stream(f"/runs/{run_id}/events", {"Last-Event-ID": "5"})
        await h.clock.settle()
        again.pump()
        assert again.status == 200 and again.events() == [] and again.closed


async def test_a_second_stream_replaces_the_first():
    gate = asyncio.Event()
    clock = FakeClock()
    h = make_app(gated_script(gate, clock), clock=clock)
    async with lifespan(h.app):
        run_id, first = await start(h)
        assert [e["n"] for e in first.events()] == [1, 2, 3]
        second = h.client.stream(f"/runs/{run_id}/events", {"Last-Event-ID": "2"})
        await clock.settle()
        first.pump()
        second.pump()
        assert first.closed, "the earlier stream is closed when a new one attaches (T3.1)"
        assert [e["n"] for e in second.events()] == [3]
        gate.set()
        await clock.settle()
        first.pump()
        second.pump()
        assert [e["n"] for e in first.events()] == [1, 2, 3]
        assert [e["n"] for e in second.events()] == [3, 4, 5] and second.closed
        assert len(h.contexts) == 1, "attaching again never starts a second run"


async def test_the_run_starts_on_the_first_attach_only():
    h = make_app()
    async with lifespan(h.app):
        run_id = (await h.client.post("/runs", {"question": QUESTION})).json()["run_id"]
        await h.clock.advance(5)
        assert h.contexts == [] and h.run(run_id).state == "created"
        s = h.client.stream(f"/runs/{run_id}/events")
        await h.clock.settle()
        s.pump()
        assert len(h.contexts) == 1 and s.events()[0]["kind"] == "run_started"


# --- a run this instance does not hold -------------------------------------------------------------------------------------
async def test_another_instance_replays_a_finished_run_from_atlas():
    store = MemoryStore()
    h1 = make_app(store=store)
    h2 = make_app(store=store, clock=h1.clock)
    async with lifespan(h1.app), lifespan(h2.app):
        run_id, s = await start(h1)
        await h1.clock.settle()
        other = h2.client.stream(f"/runs/{run_id}/events", {"Last-Event-ID": "2"})
        await h1.clock.settle()
        other.pump()
        assert other.status == 200 and other.headers["x-accel-buffering"] == "no"
        assert other.events() == s.events()[2:] and other.closed
        assert h2.contexts == [], "a replay from Atlas never starts a run"


def _store_with(events: list[dict]) -> MemoryStore:
    store = MemoryStore()
    store._events[events[0]["run"]] = {e["n"]: {**e, "created": START} for e in events}
    return store


async def test_interrupted_matches_the_fixture_exactly():
    doc = event_fixture("interrupted-run.json")
    stored, expected = doc["events"][:-1], doc["events"][-1]
    store = _store_with(stored)
    clock = FakeClock(datetime.fromisoformat(expected["at"]))
    h = make_app(store=store, clock=clock)
    run_id = stored[0]["run"]
    async with lifespan(h.app):
        s = h.client.stream(f"/runs/{run_id}/events")
        await clock.settle()
        s.pump()
        evs = s.events()
        assert evs[:-1] == stored
        assert evs[-1] == expected, "n is the last stored + 1; totals are summed from the stored paid calls"
        assert s.closed
        assert not list(VALIDATOR.iter_errors(evs[-1]))
        assert [e["n"] for e in await store.read_events(run_id, 0)] == [e["n"] for e in stored], "never stored"
        assert await store.get_run_record(run_id) is None


# v1.2: the page always receives an end, numbered past whichever is larger, the last stored event or its own
@pytest.mark.parametrize("header,ns", [("42", [43]), ("43", [44]), ("50", [51]), ("10", list(range(11, 44)))])
async def test_interrupted_honours_last_event_id(header, ns):
    doc = event_fixture("interrupted-run.json")
    stored = doc["events"][:-1]
    h = make_app(store=_store_with(stored))
    async with lifespan(h.app):
        s = h.client.stream(f"/runs/{stored[0]['run']}/events", {"Last-Event-ID": header})
        await h.clock.settle()
        s.pump()
        assert [e["n"] for e in s.events()] == ns and s.closed


FIXTURES = sorted(p.name for p in EVENT_FIXTURES.glob("*.json") if "-after-" not in p.name)


@pytest.mark.parametrize("name", FIXTURES)
async def test_interrupted_totals_are_the_stored_paid_calls(name):
    """Every fixture stream, cut before its run_ended: H's interrupted ending reports the totals, rounds and answer
    length the stream's own run_ended reported."""
    doc = event_fixture(name)
    stored, end = doc["events"][:-1], doc["events"][-1]
    h = make_app(store=_store_with(stored))
    async with lifespan(h.app):
        s = h.client.stream(f"/runs/{stored[0]['run']}/events", {"Last-Event-ID": str(stored[-1]["n"])})
        await h.clock.settle()
        s.pump()
        [ev] = s.events()
        assert ev["n"] == end["n"] and ev["data"]["state"] == "interrupted"
        assert ev["data"]["totals"] == end["data"]["totals"]
        assert ev["data"]["rounds"] == end["data"]["rounds"]
        assert ev["data"]["answer_chars"] == end["data"]["answer_chars"]
        assert not list(VALIDATOR.iter_errors(ev))


async def test_alive_on_another_instance_writes_the_heartbeat_to_atlas():
    doc = event_fixture("interrupted-run.json")
    stored = doc["events"][:-1]
    store = _store_with(stored)
    h = make_app(store=store)
    run_id = stored[0]["run"]
    async with lifespan(h.app):
        r = await h.client.post(f"/runs/{run_id}/alive", {"last_event": 42})
        assert r.status == 204 and await store.latest_heartbeat(run_id) == START
        r = await h.client.post(f"/runs/{run_id}/alive", {"last_event": 0})
        assert r.status == 204
        r = await h.client.post(f"/runs/{run_id}/alive", {"last_event": 900})     # a bogus number still finds the run
        assert r.status == 204
        store.unreachable = True
        r = await h.client.post(f"/runs/{run_id}/alive", {"last_event": 42})
        assert r.status == 503 and r.json()["error"] == "atlas_unreachable"


async def test_events_from_atlas_unreachable_is_503():
    h = make_app()
    async with lifespan(h.app):
        h.store.unreachable = True
        r = await h.client.get("/runs/uSZPbMAkuQGfL7TAcGTjZu/events")
        assert r.status == 503 and r.json()["error"] == "atlas_unreachable"
