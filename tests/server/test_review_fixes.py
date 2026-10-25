"""Part H's fixes after review, ruled in contract v1.2: a cancel mid-settle, estimated usage shown as null, a
reachable and bounded shutdown, the reservation on a cancelled POST /runs, ASCII-only numbers, `interrupted`
when the page is ahead or Atlas has a gap, the event tail before the record, `internal`, and the extra codes."""

import asyncio
import json

import pytest

from api import settings
from api.state.prices import failed_attempt_usage, price
from api.state.store import MemoryStore
from api.types import Usage
from tests.server.support import (QUESTION, START, VALIDATOR, FakeClock, FlakyStore, answered_script, ended_data,
                                  lifespan, loop_call, make_app, run_started_data)

pytestmark = pytest.mark.anyio
GRACE = float(settings.SHUTDOWN_GRACE_S.value)
OP = float(settings.ATLAS_OP_TIMEOUT_S.value)


async def begin(h, headers=None):
    run_id = (await h.client.post("/runs", {"question": QUESTION})).json()["run_id"]
    s = h.client.stream(f"/runs/{run_id}/events", headers)
    await h.clock.settle()
    s.pump()
    return run_id, s


# 1. a cancel during record_usage's settle keeps the cost --------------------------------------------------------------
async def test_a_cancel_mid_settle_keeps_the_billed_cost():
    store = FlakyStore()
    clock = FakeClock()

    async def script(ctx, deps):
        await ctx.emit("run_started", run_started_data(ctx))
        await loop_call(ctx)                         # its settle is held at the gate

    h = make_app(script, store=store, clock=clock)
    store.gates["settle"] = asyncio.Event()
    async with lifespan(h.app):
        run_id, s = await begin(h)
        run = h.run(run_id)
        assert store.calls.get("settle") == 1
        run.cancel()                                 # the shutdown cancel lands mid-settle
        await clock.settle()
        store.gates["settle"].set()
        await clock.settle()
        assert run.finished.is_set()
    m = await store.inner.read_month("2026-10")
    cost = price(Usage(service="anthropic", model="claude-sonnet-5-5", input_tokens=50, cache_write_1h_tokens=12000,
                       output_tokens=400))
    assert m["spent"] == pytest.approx(cost), "the billed cost is counted, settled at the end"
    assert run.totals()["claude"]["calls"] == 1


# 2. an estimated usage is never shown as the provider's --------------------------------------------------------------
async def test_an_estimated_usage_is_shown_as_null():
    async def script(ctx, deps):
        await ctx.emit("run_started", run_started_data(ctx))
        await ctx.before_paid_call("voyage", "rerank")
        await ctx.record_usage(failed_attempt_usage("voyage", "rerank-3", 22229), purpose="rerank", attempt=1,
                               max_attempts=3, outcome="retrying", error_kind="server_error", duration_ms=330)
        await ctx.before_paid_call("anthropic", "loop")
        await ctx.record_usage(failed_attempt_usage("anthropic", "claude-sonnet-5-5", 1000), purpose="loop",
                               attempt=1, max_attempts=3, outcome="retrying", error_kind="overloaded",
                               duration_ms=10, raw_usage={"input_tokens": 1000}, call_no=1)
        await ctx.before_paid_call("voyage", "embed")
        await ctx.record_usage(Usage(service="voyage", model="voyage-law-2", input_tokens=40), purpose="embed",
                               attempt=1, max_attempts=3, outcome="ok", error_kind=None, duration_ms=200)
        await ctx.emit("run_ended", ended_data(ctx, state="failed", answer_end="none", failure_reason="overloaded"))

    h = make_app(script)
    async with lifespan(h.app):
        _, s = await begin(h)
        p = [e["data"] for e in s.events() if e["kind"] == "paid_call"]
        assert [(x["usage"], x["estimated"]) for x in p] == [(None, True), (None, True), ({"total_tokens": 40}, False)]
        assert p[0]["cost_usd"] == pytest.approx(0.00111145)     # as the fixture prices the same failed rerank


# 3. a shutdown that closes the streams and fits in the grace --------------------------------------------------------
async def test_shutdown_closes_streams_and_releases_within_the_grace():
    store = FlakyStore()
    clock = FakeClock()

    async def script(ctx, deps):
        await ctx.emit("run_started", run_started_data(ctx))
        await loop_call(ctx)
        await clock.sleep(1000)                      # running: no paid call in flight

    h = make_app(script, store=store, clock=clock)
    cm = lifespan(h.app)
    await cm.__aenter__()
    run_id, s = await begin(h)
    unattached = (await h.client.post("/runs", {"question": QUESTION})).json()["run_id"]
    for slow in ("append_events", "upsert_run_record", "record_stop"):    # Atlas ops that never answer
        store.gates[slow] = asyncio.Event()
    leaving = asyncio.ensure_future(cm.__aexit__(None, None, None))
    await clock.settle()
    s.pump()
    assert s.closed, "every open stream ends when the shutdown begins"
    await clock.advance(GRACE - 0.01)
    m = await store.inner.read_month("2026-10")
    assert m["reservations"] == {}, "both reservations released inside the grace"
    await clock.advance(0.02)
    await leaving                                    # the lifespan shutdown returned within SHUTDOWN_GRACE_S
    assert clock.t <= GRACE + 0.02 and h.run(run_id).reservation_released
    assert unattached not in m["reservations"]


async def test_shutdown_releases_runs_at_once_not_one_after_another():
    """Each release waiting ATLAS_OP_TIMEOUT_S still fits: the runs end concurrently."""
    store = FlakyStore()
    clock = FakeClock()

    async def slow_release(r):
        await clock.sleep(OP * 0.9)
        await MemoryStore.release(store.inner, r)
    store.inner.release = slow_release

    async def script(ctx, deps):
        await ctx.emit("run_started", run_started_data(ctx))
        await clock.sleep(1000)

    h = make_app(script, store=store, clock=clock)
    cm = lifespan(h.app)
    await cm.__aenter__()
    for _ in range(4):
        await begin(h)
    leaving = asyncio.ensure_future(cm.__aexit__(None, None, None))
    try:
        await clock.advance(OP)
        assert (await store.inner.read_month("2026-10"))["reservations"] == {}
    finally:
        await clock.advance(100 * OP)
        await asyncio.wait_for(leaving, 5)


async def test_a_release_that_never_answers_cannot_hold_the_shutdown_past_the_grace():
    store = FlakyStore()
    clock = FakeClock()

    async def script(ctx, deps):
        await ctx.emit("run_started", run_started_data(ctx))
        await clock.sleep(1000)

    h = make_app(script, store=store, clock=clock)
    cm = lifespan(h.app)
    await cm.__aenter__()
    run_id, s = await begin(h)
    store.gates["release"] = asyncio.Event()          # Atlas never answers the release
    leaving = asyncio.ensure_future(cm.__aexit__(None, None, None))
    try:
        await clock.advance(GRACE + 0.01)
        assert leaving.done(), "the shutdown returns within SHUTDOWN_GRACE_S"
        assert run_id in (await store.inner.read_month("2026-10"))["reservations"], "left counted: the safe side"
    finally:
        store.gates["release"].set()
        await clock.advance(1)
        await asyncio.wait_for(leaving, 5)


async def test_shutdown_keeps_a_reservation_with_a_call_in_flight():
    clock = FakeClock()

    async def script(ctx, deps):
        await ctx.emit("run_started", run_started_data(ctx))
        await ctx.before_paid_call("anthropic", "loop")
        await clock.sleep(1000)                      # the call is running

    h = make_app(script, clock=clock)
    cm = lifespan(h.app)
    await cm.__aenter__()
    run_id, s = await begin(h)
    leaving = asyncio.ensure_future(cm.__aexit__(None, None, None))
    await clock.advance(GRACE)
    await leaving
    assert run_id in (await h.store.read_month("2026-10"))["reservations"]


# 4. a cancelled POST /runs never leaves its reservation --------------------------------------------------------------
async def test_a_cancelled_post_runs_releases_its_reservation():
    store = FlakyStore()
    store.gates["flag_until"] = asyncio.Event()      # held after the reservation succeeded
    h = make_app(store=store)
    async with lifespan(h.app):
        post = asyncio.ensure_future(h.client.post("/runs", {"question": QUESTION}))
        await h.clock.settle()
        assert len((await store.inner.read_month("2026-10"))["reservations"]) == 1
        post.cancel()
        with pytest.raises(asyncio.CancelledError):
            await post
        await h.clock.settle()
        m = await store.inner.read_month("2026-10")
        assert m["reservations"] == {} and m["reserved"] == pytest.approx(0)
        assert h.registry._runs == {}


# 5. ASCII digits only --------------------------------------------------------------------------------------------------
@pytest.mark.parametrize("header", ["²", "¹2", "3²", "9" * 13, " "])     # headers are latin-1
async def test_an_unreadable_last_event_id_counts_as_none(header):
    h = make_app()
    async with lifespan(h.app):
        run_id, _ = await begin(h)
        again = h.client.stream(f"/runs/{run_id}/events", {"Last-Event-ID": header})
        await h.clock.settle()
        again.pump()
        assert [e["n"] for e in again.events()] == [1, 2, 3, 4, 5]


@pytest.mark.parametrize("value", ["²", "¹2", "-1", "12a", ""])
async def test_a_bad_content_length_is_bad_request(value):
    h = make_app()
    async with lifespan(h.app):
        body = json.dumps({"question": QUESTION}).encode()
        r = await h.client.post("/runs", body, headers={"content-length": value})
        assert r.status == 400 and r.json()["error"] == "bad_request"
        r = await h.client.post("/runs/uSZPbMAkuQGfL7TAcGTjZu/alive", b'{"last_event": 1}',
                                headers={"content-length": value})
        assert r.status == 400 and r.json()["error"] == "bad_request"
        assert await h.store.read_month("2026-10") is None


# 6. interrupted: the page ahead, a gap, the tail before the record --------------------------------------------------
def stored_run(ns, run="FMqJmdYSKLYoRICY4MO1ER"):
    evs = []
    for n in ns:
        kind = "run_started" if n == 1 else "round_started"
        data = ({"question": QUESTION, "limits": {"rounds": 12, "input_tokens": 400000, "output_tokens": 20000,
                                                   "update_searches": 3, "deadline_s": 600},
                 "coverage": {"latest_decision_full_pull": "2026-06-29", "latest_decision_in_corpus": "2026-06-29",
                              "ingested": "2026-10-23"}, "update_check_available": True,
                 "models": {"loop": "claude-sonnet-5-5", "composition": "claude-opus-5-5"}, "corpus_label": "full"}
                if n == 1 else {"round": n, "status_line": f"Round {n} of 12"})
        evs.append({"v": 1, "run": run, "n": n, "t_ms": n * 100,
                    "at": (START.replace(microsecond=0)).isoformat(timespec="milliseconds"), "kind": kind, "data": data})
    store = MemoryStore()
    store._events[run] = {e["n"]: {**e, "created": START} for e in evs}
    return store, run


@pytest.mark.parametrize("ns,header,sent", [
    ([1, 2, 3], "7", [8]),                    # the page is ahead of Atlas: it still gets its end
    ([3, 5], "2", [3, 6]),                    # a gap: replay stops at 4; the end is past the last stored
    ([3, 5], "0", [6]),                       # 1 is missing: nothing replays across the gap
    ([1, 2, 3, 5], "3", [6]),
    ([1, 2, 3, 5], "4", [5, 6]),
])
async def test_interrupted_with_the_page_ahead_or_a_gap(ns, header, sent):
    store, run = stored_run(ns)
    h = make_app(store=store)
    async with lifespan(h.app):
        s = h.client.stream(f"/runs/{run}/events", {"Last-Event-ID": header})
        await h.clock.settle()
        s.pump()
        evs = s.events()
        assert [e["n"] for e in evs] == sent and s.closed
        assert evs[-1]["kind"] == "run_ended" and evs[-1]["data"]["state"] == "interrupted"
        assert evs[-1]["data"]["rounds"] == sum(1 for n in ns if n != 1)
        for e in evs:
            assert not list(VALIDATOR.iter_errors(e))


async def test_the_event_tail_reaches_atlas_before_the_stop_and_the_record():
    store = FlakyStore()
    store.fail["append_events"] = 1                  # the first batch fails and is carried in the tail

    async def script(ctx, deps):
        await ctx.emit("run_started", run_started_data(ctx))
        await loop_call(ctx)
        await ctx.emit("answer_block", {"index": 0, "text": "Text.", "citations": []})
        await ctx.emit("run_ended", ended_data(ctx, state="step_limit", stop_kind="step_limit",
                                               answer_end="complete", answer_chars=5))

    h = make_app(script, store=store)
    async with lifespan(h.app):
        store.gates["append_events"] = asyncio.Event()      # Atlas is slow to take the events
        run_id, s = await begin(h)
        await h.clock.settle()
        assert s.closed and "record_stop" not in store.order and "upsert_run_record" not in store.order
        store.gates["append_events"].set()
        await h.clock.settle()
        tail = [x for x in store.order if x in ("append_events", "record_stop", "upsert_run_record")]
        last_append = max(i for i, x in enumerate(tail) if x == "append_events")
        assert last_append < tail.index("record_stop") < tail.index("upsert_run_record")
        assert [e["n"] for e in await store.inner.read_events(run_id, 0)] == [1, 2, 3, 4]


# 7. failed: internal, and the characters that did arrive -------------------------------------------------------------
async def test_failed_after_blocks_keeps_answer_chars_and_says_internal():
    async def script(ctx, deps):
        await ctx.emit("run_started", run_started_data(ctx))
        await ctx.emit("answer_block", {"index": 0, "text": "Part of ", "citations": []})
        await ctx.emit("answer_block", {"index": 1, "text": "an answer", "citations": []})
        raise ValueError("a bug")

    h = make_app(script)
    async with lifespan(h.app):
        _, s = await begin(h)
        d = s.events()[-1]["data"]
        assert (d["state"], d["answer_end"], d["answer_chars"], d["failure_reason"]) == ("failed", "none", 17, "internal")
    assert h.schema_errors == []


async def test_returning_without_run_ended_is_failed_internal():
    async def script(ctx, deps):
        await ctx.emit("run_started", run_started_data(ctx))

    h = make_app(script)
    async with lifespan(h.app):
        _, s = await begin(h)
        assert s.events()[-1]["data"]["failure_reason"] == "internal"


# 8. the extra codes of §5 v1.2 ------------------------------------------------------------------------------------------
async def test_500_internal_in_our_shape(monkeypatch, caplog):
    import api.server.app as app_module

    def broken(*a):
        raise RuntimeError("a secret-looking message")
    monkeypatch.setattr(app_module, "clean_question", broken)
    h = make_app()
    async with lifespan(h.app):
        r = await h.client.post("/runs", {"question": QUESTION})
        assert r.status == 500 and r.json() == {"error": "internal", "message": "The server could not handle the request."}
        assert await h.store.read_month("2026-10") is None
    assert "secret-looking" not in caplog.text


@pytest.mark.parametrize("method,path,status,code", [
    ("POST", "/runs", 400, "bad_request"), ("GET", "/nowhere", 404, "not_found"),
    ("DELETE", "/runs", 405, "method_not_allowed"), ("PUT", "/health", 405, "method_not_allowed")])
async def test_the_other_codes(method, path, status, code):
    h = make_app()
    async with lifespan(h.app):
        r = await h.client.request(method, path, b"[]")
        assert r.status == status and list(r.json()) == ["error", "message"] and r.json()["error"] == code


async def test_atlas_unreachable_on_events_and_on_alive_for_a_run_held_elsewhere():
    store, run = stored_run([1, 2])
    h = make_app(store=store)
    async with lifespan(h.app):
        store.unreachable = True
        r = await h.client.get(f"/runs/{run}/events")
        assert r.status == 503 and r.json()["error"] == "atlas_unreachable"
        r = await h.client.post(f"/runs/{run}/alive", {"last_event": 2})
        assert r.status == 503 and r.json()["error"] == "atlas_unreachable"


async def test_a_page_holding_the_stored_end_gets_nothing_more():
    from tests.server.support import event_fixture
    doc = event_fixture("pause-and-resume.json")
    store = MemoryStore()
    run = doc["events"][0]["run"]
    store._events[run] = {e["n"]: {**e, "created": START} for e in doc["events"]}
    end = doc["events"][-1]["n"]
    h = make_app(store=store)
    async with lifespan(h.app):
        for header, ns in ((str(end), []), (str(end + 3), []), (str(end - 1), [end])):
            s = h.client.stream(f"/runs/{run}/events", {"Last-Event-ID": header})
            await h.clock.settle()
            s.pump()
            assert [e["n"] for e in s.events()] == ns and s.closed
