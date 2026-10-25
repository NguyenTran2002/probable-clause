"""The update step and the composition run side by side (contract §4.G.1, v2.0), so `emit`, `record_usage` and
`before_paid_call` are called by two callers at once (§4.H). Each is tested here with two concurrent callers: event
numbers follow the order of the calls with no gap, spend and totals add up, and one pause emits one `paused` and one
`resumed` however many calls wait on it. The caps are never looked at: a run in progress always finishes (P4.21)."""

import asyncio

import pytest

from api import settings
from api.protocols import Admission
from api.state.prices import price
from api.state.store import MemoryStore
from api.types import RunStopped
from tests.server.support import (COMPOSITION_MODEL, UPDATE_MODEL, FakeClock, FlakyStore, claude_call, claude_usage,
                                  ended_data, lifespan, make_app, round_data, run_started_data)

pytestmark = pytest.mark.anyio
DEADLINE = float(settings.RUN_DEADLINE_S.value)
ABANDON = float(settings.ABANDON_AFTER_S.value)
DAILY = float(settings.DAILY_CAP_USD.value)
MONTHLY = float(settings.MONTHLY_CAP_USD.value)


async def begin(h):
    run_id = (await h.client.post("/runs", {"question": "Does a thermal imager need a warrant?"})).json()["run_id"]
    s = h.client.stream(f"/runs/{run_id}/events")
    await h.clock.settle()
    s.pump()
    return run_id, s


def kinds(s):
    s.pump()
    return [e["kind"] for e in s.events()]


def assert_no_gap(s):
    ns = [e["n"] for e in s.events()]
    assert ns == list(range(1, len(ns) + 1)), "numbers run on from 1 with no gap and no repeat"


# --- emit ------------------------------------------------------------------------------------------------------------------
async def test_emit_from_two_branches_numbers_in_the_order_of_the_calls():
    returned: list[tuple[str, int]] = []

    async def script(ctx, deps):
        await ctx.emit("run_started", run_started_data(ctx))

        async def branch(name, step, count):
            for i in range(count):
                n = await ctx.emit("round_started", round_data(i + 1, step))
                returned.append((name, n))
                await asyncio.sleep(0)               # the other branch gets a turn between events

        await asyncio.gather(branch("update", "update", 20), branch("composition", "research", 20))
        await ctx.emit("run_ended", ended_data(ctx, state="failed", answer_end="none", failure_reason="overloaded"))

    h = make_app(script)
    async with lifespan(h.app):
        run_id, s = await begin(h)
        evs = s.events()
        assert_no_gap(s)
        assert [n for _, n in returned] == list(range(2, 42)), "the number each caller was given follows the call order"
        by_step = [e["data"]["step"] for e in evs if e["kind"] == "round_started"]
        assert by_step.count("update") == 20 and by_step.count("research") == 20
        # a branch's own events stay in its own order
        for step in ("update", "research"):
            rounds = [e["data"]["round"] for e in evs if e["kind"] == "round_started" and e["data"]["step"] == step]
            assert rounds == sorted(rounds)
        stored = await h.store.read_events(run_id, 0)
        assert [e["n"] for e in stored] == [e["n"] for e in evs]
    assert h.schema_errors == []


async def test_emit_many_at_once_never_repeats_or_skips_a_number():
    async def script(ctx, deps):
        await ctx.emit("run_started", run_started_data(ctx))
        numbers = await asyncio.gather(*(ctx.emit("round_started", round_data(i + 1, "update")) for i in range(100)))
        assert numbers == list(range(2, 102))
        await ctx.emit("run_ended", ended_data(ctx, state="failed", answer_end="none", failure_reason="overloaded"))

    h = make_app(script)
    async with lifespan(h.app):
        run_id, s = await begin(h)
        s.pump()
        assert_no_gap(s)
        assert len(s.events()) == 102


# --- record_usage ----------------------------------------------------------------------------------------------------------
async def test_record_usage_from_two_branches_at_once():
    update_cost, composition_cost = [], []

    async def script(ctx, deps):
        await ctx.emit("run_started", run_started_data(ctx))
        await ctx.emit("round_started", round_data(1))

        async def update_branch():
            for i in range(5):
                update_cost.append(await claude_call(ctx, "update", call_no=10 + i, inp=7, w1=0, read=17000, out=300))

        async def composition_branch():
            for i in range(5):
                composition_cost.append(await claude_call(ctx, "composition", call_no=20 + i, inp=1892, w1=0, out=1875))

        await asyncio.gather(update_branch(), composition_branch())
        await ctx.emit("answer_block", {"index": 0, "text": "Done.", "citations": []})
        await ctx.emit("run_ended", ended_data(ctx, answer_chars=5))

    store = MemoryStore(latency_s=0)
    h = make_app(script, store=store)
    async with lifespan(h.app):
        run_id, s = await begin(h)
        evs = s.events()
        assert_no_gap(s)
        paid = [e["data"] for e in evs if e["kind"] == "paid_call"]
        assert len(paid) == 10
        assert [(p["purpose"], p["step"]) for p in paid if p["purpose"] == "update"] == [("update", "update")] * 5
        assert [(p["purpose"], p["step"]) for p in paid if p["purpose"] == "composition"] == [("composition", "composition")] * 5
        # each branch's own calls stay in order, whichever way the two interleave
        assert [p["call_no"] for p in paid if p["purpose"] == "update"] == [10, 11, 12, 13, 14]
        assert [p["call_no"] for p in paid if p["purpose"] == "composition"] == [20, 21, 22, 23, 24]
        t = evs[-1]["data"]["totals"]["claude"]
        assert t["calls"] == 10
        assert t["cost_usd"]["update"] == pytest.approx(5 * price(claude_usage(UPDATE_MODEL, inp=7, w1=0, read=17000, out=300)))
        assert t["cost_usd"]["composition"] == pytest.approx(
            5 * price(claude_usage(COMPOSITION_MODEL, inp=1892, w1=0, out=1875)))
        assert t["input_tokens"] == 5 * (7 + 17000) + 5 * 1892 and t["output_tokens"] == 5 * 300 + 5 * 1875
        # and Atlas holds exactly the sum, whichever order the writes landed in
        month = await store.read_month("2026-10")
        assert month["spent"] == pytest.approx(sum(update_cost) + sum(composition_cost), abs=1e-9)
        assert h.run(run_id).totals() == evs[-1]["data"]["totals"]
    assert h.schema_errors == []


async def test_one_branchs_failed_spend_write_keeps_both_branches_costs():
    """Atlas fails for one of two concurrent callers: from then on no more spend calls, every cost is kept, and the end
    records them as one sum (contract §4.H)."""
    store = FlakyStore()
    store.fail["record_spend"] = 1

    async def script(ctx, deps):
        await ctx.emit("run_started", run_started_data(ctx))
        await asyncio.gather(*(claude_call(ctx, p, call_no=i + 1, inp=5, w1=0, read=1000, out=50)
                               for i, p in enumerate(("update", "composition", "update", "composition"))))
        await ctx.emit("answer_block", {"index": 0, "text": "Done.", "citations": []})
        await ctx.emit("run_ended", ended_data(ctx, answer_chars=5))

    h = make_app(script, store=store)
    async with lifespan(h.app):
        run_id, s = await begin(h)
        await h.clock.settle()
        total = h.run(run_id).totals()["claude"]["cost_usd"]
        assert (await store.inner.read_month("2026-10"))["spent"] == pytest.approx(total["update"] + total["composition"])
        # the first write fails and nothing else goes to Atlas until the end, which records the other three and the first
        # as one sum: exactly two spend calls, however the four calls interleave
        assert store.calls["record_spend"] == 2


# --- before_paid_call ------------------------------------------------------------------------------------------------------
async def test_two_calls_due_together_while_unattended_pause_once_and_resume_once():
    clock = FakeClock()
    passed = []

    async def script(ctx, deps):
        await ctx.emit("run_started", run_started_data(ctx))
        await clock.sleep(30)

        async def one(service, purpose):
            await ctx.before_paid_call(service, purpose)
            passed.append(purpose)

        await asyncio.gather(one("anthropic", "update"), one("anthropic", "composition"), one("exa", "update_search"))
        await ctx.emit("run_ended", ended_data(ctx, state="failed", answer_end="none", failure_reason="overloaded"))

    h = make_app(script, clock=clock)
    async with lifespan(h.app):
        run_id, s = await begin(h)
        await clock.advance(35)
        assert passed == [] and kinds(s).count("paused") == 1
        r = await h.client.post(f"/runs/{run_id}/alive", {"last_event": 1})
        assert r.status == 204
        await clock.settle()
        assert sorted(passed) == ["composition", "update", "update_search"]
        assert kinds(s).count("paused") == 1 and kinds(s).count("resumed") == 1
        assert kinds(s) == ["run_started", "paused", "resumed", "run_ended"]
        assert_no_gap(s)
    assert h.schema_errors == []


async def test_two_calls_waiting_when_the_run_is_abandoned_both_stop_with_one_pause():
    clock = FakeClock()
    seen = []

    async def script(ctx, deps):
        await ctx.emit("run_started", run_started_data(ctx))
        await clock.sleep(30)

        async def one(purpose):
            try:
                await ctx.before_paid_call("anthropic", purpose)
                seen.append((purpose, "passed"))
            except RunStopped as e:
                seen.append((purpose, e.reason))

        await asyncio.gather(one("update"), one("composition"))
        await ctx.emit("run_ended", ended_data(ctx, state="abandoned", answer_end="none"))

    h = make_app(script, clock=clock)
    async with lifespan(h.app):
        run_id, s = await begin(h)
        await clock.advance(ABANDON + 5)
        assert sorted(seen) == [("composition", "abandoned"), ("update", "abandoned")]
        assert kinds(s) == ["run_started", "paused", "run_ended"]


async def test_a_second_pause_is_a_second_paused_and_resumed():
    clock = FakeClock()

    async def script(ctx, deps):
        await ctx.emit("run_started", run_started_data(ctx))
        for wait in (30, 40):
            await clock.sleep(wait)
            await asyncio.gather(ctx.before_paid_call("anthropic", "update"), ctx.before_paid_call("anthropic", "composition"))
        await ctx.emit("run_ended", ended_data(ctx, state="failed", answer_end="none", failure_reason="overloaded"))

    h = make_app(script, clock=clock)
    async with lifespan(h.app):
        run_id, s = await begin(h)
        await clock.advance(35)
        await h.client.post(f"/runs/{run_id}/alive", {"last_event": 1})
        await clock.settle()
        assert kinds(s) == ["run_started", "paused", "resumed"]
        await clock.advance(42)
        assert kinds(s)[-1] == "paused"
        await h.client.post(f"/runs/{run_id}/alive", {"last_event": 1})
        await clock.settle()
        assert kinds(s) == ["run_started", "paused", "resumed", "paused", "resumed", "run_ended"]


@pytest.mark.parametrize("purpose", ["loop", "update", "embed", "rerank", "update_search"])
async def test_past_the_deadline_every_purpose_but_composition_is_refused(purpose):
    clock = FakeClock()
    seen = {}

    async def script(ctx, deps):
        await ctx.emit("run_started", run_started_data(ctx))
        await clock.sleep(DEADLINE + 1)
        service = {"loop": "anthropic", "update": "anthropic", "embed": "voyage", "rerank": "voyage",
                   "update_search": "exa"}[purpose]
        for p, sv in ((purpose, service), ("composition", "anthropic")):
            try:
                await ctx.before_paid_call(sv, p)
                seen[p] = "passed"
            except RunStopped as e:
                seen[p] = e.reason
        await ctx.emit("run_ended", ended_data(ctx, state="time_limit", stop_kind="time_limit", answer_end="none"))

    h = make_app(script, clock=clock)
    async with lifespan(h.app):
        run_id, s = await begin(h)
        beat = asyncio.ensure_future(_keep_alive(h, run_id, DEADLINE + 5))
        await clock.advance(DEADLINE + 5)
        beat.cancel()
        assert seen == {purpose: "deadline", "composition": "passed"}


async def _keep_alive(h, run_id, until):
    while h.clock.t + 10 <= until:
        await h.clock.sleep(10)
        await h.client.post(f"/runs/{run_id}/alive", {"last_event": 1})


async def test_the_update_step_is_stopped_at_the_deadline_while_the_composition_proceeds_beside_it():
    clock = FakeClock()
    seen = {}

    async def script(ctx, deps):
        await ctx.emit("run_started", run_started_data(ctx))
        await clock.sleep(DEADLINE - 1)

        async def update():
            await clock.sleep(2)
            try:
                await ctx.before_paid_call("anthropic", "update")
                seen["update"] = "passed"
            except RunStopped as e:
                seen["update"] = e.reason

        async def composition():
            await clock.sleep(2)
            await ctx.before_paid_call("anthropic", "composition")
            seen["composition"] = "passed"
            await claude_call(ctx, "composition", 1)

        await asyncio.gather(update(), composition())
        await ctx.emit("run_ended", ended_data(ctx, state="time_limit", stop_kind="time_limit", answer_end="none"))

    h = make_app(script, clock=clock)
    async with lifespan(h.app):
        run_id, s = await begin(h)
        beat = asyncio.ensure_future(_keep_alive(h, run_id, DEADLINE + 5))
        await clock.advance(DEADLINE + 5)
        beat.cancel()
        assert seen == {"update": "deadline", "composition": "passed"}


# --- the caps are never looked at by a run in progress ---------------------------------------------------------------------
async def test_a_cap_reached_during_a_run_never_stops_it():
    """A run in progress always finishes (P4.21): the cap only refuses the next admission."""
    store = MemoryStore()
    passed = []

    async def script(ctx, deps):
        await ctx.emit("run_started", run_started_data(ctx))
        await claude_call(ctx, "loop", 1)
        # another run takes the day, then the month, past their caps while this one is in progress
        await store.record_spend(Admission("elsewhere", "2026-10", "2026-10-24"), DAILY)
        await store.record_spend(Admission("elsewhere", "2026-10", "2026-10-01"), MONTHLY)
        for purpose, service in (("loop", "anthropic"), ("embed", "voyage"), ("update", "anthropic"),
                                 ("update_search", "exa"), ("composition", "anthropic")):
            await ctx.before_paid_call(service, purpose)
            passed.append(purpose)
        await claude_call(ctx, "update", 2)
        await claude_call(ctx, "composition", 3)
        await ctx.emit("answer_block", {"index": 0, "text": "Done.", "citations": []})
        await ctx.emit("run_ended", ended_data(ctx, answer_chars=5))

    h = make_app(script, store=store)
    async with lifespan(h.app):
        run_id, s = await begin(h)
        await h.clock.settle()
        assert passed == ["loop", "embed", "update", "update_search", "composition"]
        assert s.events()[-1]["data"]["state"] == "answered"
        assert [s_["kind"] for s_ in await store.read_stops(day="2026-10-24")] == [], "no cap stop is recorded by H"
        r = await h.client.post("/runs", {"question": "And now another?"})
        assert r.status == 503 and r.json()["error"] == "paused_month", "the next admission is what the cap refuses"
