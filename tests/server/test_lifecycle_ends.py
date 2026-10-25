"""The ends of a run that the review found (contract §4.H, v2.0): the event before the write, a run cancelled before it
first ran, the watchdog, a cost that arrives after the end, and the record of an update step that never ended."""

import asyncio
import logging

import pytest

from api import settings
from api.settings import Setting
from api.state.prices import price
from tests.server.support import (QUESTION, FakeClock, FlakyStore, claude_call, claude_usage, lifespan,
                                  loop_call, make_app, round_data, run_started_data, update_ended_data)

pytestmark = pytest.mark.anyio


async def begin(h):
    run_id = (await h.client.post("/runs", {"question": QUESTION})).json()["run_id"]
    s = h.client.stream(f"/runs/{run_id}/events")
    await h.clock.settle()
    s.pump()
    return run_id, s


# 1. the event before the write ---------------------------------------------------------------------------------------------
async def test_a_cancel_mid_write_loses_neither_the_event_nor_the_cost():
    store = FlakyStore()
    clock = FakeClock()

    async def script(ctx, deps):
        await ctx.emit("run_started", run_started_data(ctx))
        await loop_call(ctx, call_no=1)              # its record_spend is held at the gate

    h = make_app(script, store=store, clock=clock)
    store.gates["record_spend"] = asyncio.Event()
    async with lifespan(h.app):
        run_id, s = await begin(h)
        run = h.run(run_id)
        s.pump()
        assert [e["kind"] for e in s.events()] == ["run_started", "paid_call"], "the event is out before the write ends"
        cost = s.events()[-1]["data"]["cost_usd"]
        run.cancel()
        await clock.settle()
        assert [e["kind"] for e in run.events][:2] == ["run_started", "paid_call"]
        store.gates["record_spend"].set()
        await clock.settle()
        assert run.finished.is_set()
    assert (await store.inner.read_month("2026-10"))["spent"] == pytest.approx(cost)
    assert [e["n"] for e in await store.inner.read_events(run_id, 0)][:2] == [1, 2]


# 2. cancelled before its first step ----------------------------------------------------------------------------------------
async def test_a_run_cancelled_before_its_task_first_runs_still_ends_and_frees_its_slot():
    h = make_app()
    async with lifespan(h.app):
        run_id = (await h.client.post("/runs", {"question": QUESTION})).json()["run_id"]
        run = h.run(run_id)
        assert h.registry.in_progress == 1
        run.attach(h.clock.now())                    # starts the task, which has not had a turn yet
        run.cancel()
        await h.clock.settle()
        assert run.finished.is_set() and run.state == "finished"
        assert h.registry.in_progress == 0
        assert h.contexts == [], "execute_run never ran"
        assert (await h.store.get_run_record(run_id))["state"] == "interrupted"


# 3. the watchdog -----------------------------------------------------------------------------------------------------------
async def test_the_watchdog_ends_a_hung_run_failed_internal_and_frees_its_slot(monkeypatch):
    monkeypatch.setattr(settings, "RUN_WATCHDOG_S", Setting(50, "test"))
    clock = FakeClock()

    async def hung(ctx, deps):
        await ctx.emit("run_started", run_started_data(ctx))
        await loop_call(ctx)
        await asyncio.Event().wait()

    h = make_app(hung, clock=clock)
    async with lifespan(h.app):
        run_id, s = await begin(h)
        beat = asyncio.ensure_future(_keep_alive(h, run_id, 60))
        await clock.advance(49)
        assert not h.run(run_id).ended and h.registry.in_progress == 1
        await clock.advance(2)
        beat.cancel()
        s.pump()
        end = s.events()[-1]
        assert end["kind"] == "run_ended" and s.closed
        assert (end["data"]["state"], end["data"]["failure_reason"], end["data"]["answer_end"]) == (
            "failed", "internal", "none")
        assert end["data"]["totals"]["claude"]["calls"] == 1
        assert h.registry.in_progress == 0 and h.run(run_id).finished.is_set()
        rec = await h.store.get_run_record(run_id)
        assert rec["state"] == "failed"
        assert (await h.store.read_month("2026-10"))["spent"] > 0, "what was spent is recorded"
    assert h.schema_errors == []


async def _keep_alive(h, run_id, until):
    while h.clock.t + 10 <= until:
        await h.clock.sleep(10)
        await h.client.post(f"/runs/{run_id}/alive", {"last_event": 1})


async def test_the_watchdog_leaves_a_run_that_ends_in_time_alone(monkeypatch, caplog):
    monkeypatch.setattr(settings, "RUN_WATCHDOG_S", Setting(50, "test"))
    caplog.set_level(logging.INFO)
    h = make_app()
    async with lifespan(h.app):
        run_id, s = await begin(h)
        await h.clock.advance(100)
        s.pump()
        assert s.events()[-1]["data"]["state"] == "answered"
    assert "cancelling it" not in caplog.text


# 4. a cost after the end -----------------------------------------------------------------------------------------------------
async def test_a_cost_after_the_end_is_recorded_on_its_own_and_logged(caplog):
    caplog.set_level(logging.INFO)
    h = make_app()
    async with lifespan(h.app):
        run_id, s = await begin(h)
        await h.clock.settle()
        ctx = h.contexts[0]
        before = (await h.store.read_month("2026-10"))["spent"]
        with pytest.raises(RuntimeError):            # what emit raises after run_ended; the caller is told, not silenced
            await claude_call(ctx, "update", 9, inp=10, w1=0, read=15000, out=200)
        late = claude_usage(str(settings.UPDATE_MODEL.value), inp=10, w1=0, read=15000, out=200)
        spent = (await h.store.read_month("2026-10"))["spent"]
        assert spent - before == pytest.approx(price(late)), "the late cost is in Atlas, not silently dropped"
    assert "after the run's end" in caplog.text and f"{price(late):.6f}" in caplog.text
    assert [e["kind"] for e in h.run(run_id).events].count("paid_call") == 1, "and it has no event"


async def test_a_cost_after_the_end_that_atlas_cannot_take_is_logged_as_lost(caplog):
    store = FlakyStore()
    caplog.set_level(logging.INFO)
    h = make_app(store=store)
    async with lifespan(h.app):
        run_id, s = await begin(h)
        await h.clock.settle()
        store.fail["record_spend"] = -1
        with pytest.raises(RuntimeError):
            await claude_call(h.contexts[0], "update", 9)
    assert "of spend is lost" in caplog.text


# 6. an update step that never ended ----------------------------------------------------------------------------------------
async def test_the_record_of_an_update_step_that_never_ended_has_a_null_end():
    async def script(ctx, deps):
        await ctx.emit("run_started", run_started_data(ctx))
        await ctx.emit("round_started", round_data(1))
        await ctx.emit("update_started", {"kept": []})
        await ctx.emit("round_started", round_data(1, "update"))
        await ctx.emit("round_started", round_data(2, "update"))
        raise RuntimeError("a bug in the composition")

    h = make_app(script)
    async with lifespan(h.app):
        run_id, s = await begin(h)
        await h.clock.settle()
        rec = await h.store.get_run_record(run_id)
        assert rec["state"] == "failed" and rec["rounds"] == 1
        assert rec["update_end"] is None and rec["update_rounds"] == 2


async def test_no_update_fields_when_the_update_step_never_started():
    h = make_app()
    async with lifespan(h.app):
        run_id, s = await begin(h)
        await h.clock.settle()
        rec = await h.store.get_run_record(run_id)
        assert "update_end" not in rec and "update_rounds" not in rec
