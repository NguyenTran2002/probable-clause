"""`record_usage`, the spend recorded per call, and the end of a run (contract §4.H, §6.2, §8; T3.3, T3.4, T3.7, P4.21).

There is no reservation (v2.0): each paid call's cost goes to Atlas as it happens (`record_spend`), and a run is
admitted under the caps (`admit`). The slot among the runs in progress is freed once the run has ended.
"""

import asyncio
import json
import logging

import pytest

from api import settings
from api.errors import ServiceError
from api.state.prices import failed_attempt_usage, price, price_sources
from api.types import RunStopped, Usage
from tests.server.support import (COMPOSITION_MODEL, LOOP_MODEL, QUESTION, UPDATE_MODEL, FakeClock, FlakyStore,
                                  claude_call, claude_usage, ended_data, lifespan, loop_call, make_app, raw_claude,
                                  round_data, run_started_data, update_ended_data)

pytestmark = pytest.mark.anyio
ABANDON = float(settings.ABANDON_AFTER_S.value)
EXPIRY = float(settings.UNATTACHED_RUN_EXPIRY_S.value)
DEADLINE = float(settings.RUN_DEADLINE_S.value)


async def begin(h, question=QUESTION):
    run_id = (await h.client.post("/runs", {"question": question})).json()["run_id"]
    s = h.client.stream(f"/runs/{run_id}/events")
    await h.clock.settle()
    s.pump()
    return run_id, s


async def month(store):
    return await store.read_month("2026-10")


def paid(s):
    s.pump()
    return [e["data"] for e in s.events() if e["kind"] == "paid_call"]


async def assert_spent(store, costs):
    m = await month(store)
    assert m["spent"] == pytest.approx(sum(costs), abs=1e-12)
    assert m["days"]["2026-10-24"]["spent"] == pytest.approx(sum(costs), abs=1e-12)
    assert "reservations" not in m and "reserved" not in m


# --- pricing and recording ---------------------------------------------------------------------------------------------
async def test_record_usage_prices_records_and_emits():
    seen = {}

    async def script(ctx, deps):
        await ctx.emit("run_started", run_started_data(ctx))
        seen["cost"] = await loop_call(ctx, call_no=1, inp=51, w1=12000, out=406)
        seen["month"] = await month(h.store)                     # recorded as the call completes, not at the end
        await ctx.emit("run_ended", ended_data(ctx, state="failed", answer_end="none", failure_reason="overloaded"))

    h = make_app(script)
    async with lifespan(h.app):
        run_id, s = await begin(h)
        expected = price(claude_usage(inp=51, w1=12000, out=406))
        assert seen["cost"] == pytest.approx(expected, rel=1e-12)
        assert seen["month"]["spent"] == pytest.approx(expected)
        [p] = paid(s)
        assert p == {"step": "research", "call_no": 1, "service": "anthropic", "purpose": "loop", "attempt": 1,
                     "max_attempts": 3, "outcome": "ok", "error_kind": None, "duration_ms": 1500,
                     "usage": raw_claude(inp=51, w1=12000, out=406), "estimated_usage": None,
                     "cost_usd": round(expected, 10), "estimated": False}
        await assert_spent(h.store, [expected])
    assert h.schema_errors == []


async def test_paid_call_carries_the_step_of_its_purpose():
    """STEP_OF_PURPOSE: loop, embed, rerank are research; update and update_search the update step; composition its own."""
    costs = []

    async def script(ctx, deps):
        await ctx.emit("run_started", run_started_data(ctx))
        rec = ctx.record_usage
        await ctx.before_paid_call("voyage", "embed")
        costs.append(await rec(Usage(service="voyage", model="voyage-law-2", input_tokens=28), purpose="embed",
                               attempt=1, max_attempts=3, outcome="ok", error_kind=None, duration_ms=200))
        await ctx.before_paid_call("voyage", "rerank")
        costs.append(await rec(None, purpose="rerank", attempt=1, max_attempts=3, outcome="retrying",
                               error_kind="server_error", duration_ms=330))
        costs.append(await loop_call(ctx, call_no=1))
        costs.append(await claude_call(ctx, "update", 2, inp=19, w5=5027, w1=0, read=12052, out=491))
        await ctx.before_paid_call("exa", "update_search")
        costs.append(await rec(Usage(service="exa", model="auto", exa_cost_usd=0.007), purpose="update_search",
                               attempt=1, max_attempts=1, outcome="ok", error_kind=None, duration_ms=2100))
        costs.append(await claude_call(ctx, "composition", 3, inp=1892, w1=0, out=1875))
        await ctx.emit("run_ended", ended_data(ctx, state="failed", answer_end="none", failure_reason="overloaded"))

    h = make_app(script)
    async with lifespan(h.app):
        run_id, s = await begin(h)
        p = paid(s)
        assert [(x["purpose"], x["step"]) for x in p] == [
            ("embed", "research"), ("rerank", "research"), ("loop", "research"), ("update", "update"),
            ("update_search", "update"), ("composition", "composition")]
        assert ["call_no" in x for x in p] == [False, False, True, True, False, True]
        await assert_spent(h.store, costs)
    assert h.schema_errors == []


async def test_voyage_exa_and_unreported_usage():
    costs = []

    async def script(ctx, deps):
        await ctx.emit("run_started", run_started_data(ctx))
        rec = ctx.record_usage
        await ctx.before_paid_call("voyage", "embed")
        costs.append(await rec(Usage(service="voyage", model="voyage-law-2", input_tokens=28), purpose="embed",
                               attempt=1, max_attempts=3, outcome="ok", error_kind=None, duration_ms=200))
        await ctx.before_paid_call("voyage", "rerank")
        costs.append(await rec(None, purpose="rerank", attempt=1, max_attempts=3, outcome="retrying",
                               error_kind="server_error", duration_ms=330))
        await ctx.before_paid_call("exa", "update_search")
        costs.append(await rec(Usage(service="exa", model="auto", exa_cost_usd=0.0), purpose="update_search",
                               attempt=1, max_attempts=1, outcome="failed", error_kind="bad_request", duration_ms=2000))
        await ctx.before_paid_call("exa", "update_search")
        costs.append(await rec(Usage(service="exa", model="lite", estimated=True), purpose="update_search",
                               attempt=1, max_attempts=1, outcome="failed", error_kind="timeout", duration_ms=30000))
        await ctx.before_paid_call("anthropic", "composition")
        costs.append(await rec(failed_attempt_usage("anthropic", COMPOSITION_MODEL, 1803), purpose="composition",
                               attempt=1, max_attempts=3, outcome="retrying", error_kind="overloaded",
                               duration_ms=1300, raw_usage=None, call_no=4))
        await ctx.before_paid_call("anthropic", "update")
        costs.append(await rec(None, purpose="update", attempt=1, max_attempts=3, outcome="failed",
                               error_kind="overloaded", duration_ms=10, call_no=5))
        await ctx.emit("run_ended", ended_data(ctx, state="failed", answer_end="none", failure_reason="overloaded"))

    h = make_app(script)
    async with lifespan(h.app):
        run_id, s = await begin(h)
        p = paid(s)
        assert [x["usage"] for x in p] == [{"total_tokens": 28}, None, None, None, None, None]
        assert [x["estimated"] for x in p] == [False, True, False, True, True, True]
        composition_cost = price(failed_attempt_usage("anthropic", COMPOSITION_MODEL, 1803))
        assert costs == [pytest.approx(28 * 0.12 / 1e6), 0.0, 0.0, 0.004, pytest.approx(composition_cost), 0.0]
        assert [x["cost_usd"] for x in p] == [pytest.approx(c) for c in costs]
        t = s.events()[-1]["data"]["totals"]
        assert t["claude"]["calls"] == 2 and t["claude"]["input_tokens"] == 1803
        assert t["claude"]["cost_usd"] == {"loop": 0, "update": 0, "composition": pytest.approx(composition_cost)}
        assert t["exa"] == {"searches": 2, "cost_usd": pytest.approx(0.004)}
        assert t["voyage"] == {"requests": 2, "cost_usd": pytest.approx(3.36e-06)}
        assert t["prices"] == price_sources()
        await assert_spent(h.store, costs)
    assert h.schema_errors == []


async def test_an_attempt_with_no_usage_is_priced_at_its_steps_model():
    """contract §4.H: `loop` at LOOP_MODEL, `update` at UPDATE_MODEL, `composition` at COMPOSITION_MODEL."""
    from api.server.totals import model_for
    assert (model_for("loop"), model_for("update"), model_for("composition")) == (LOOP_MODEL, UPDATE_MODEL,
                                                                                 COMPOSITION_MODEL)
    assert model_for("update_search") == "auto"


async def test_totals_count_attempts_all_input_and_the_update_steps_cost():
    async def script(ctx, deps):
        await ctx.emit("run_started", run_started_data(ctx))
        await ctx.before_paid_call("anthropic", "loop")
        await ctx.record_usage(failed_attempt_usage("anthropic", LOOP_MODEL, 12046), purpose="loop",
                               attempt=1, max_attempts=3, outcome="retrying", error_kind="rate_limited",
                               duration_ms=850, call_no=1)
        await loop_call(ctx, call_no=1, inp=51, w1=12000, out=406)
        await loop_call(ctx, call_no=2, inp=19, w5=5027, w1=0, read=12052, out=491)
        await claude_call(ctx, "update", 3, inp=7, w1=0, read=17000, out=300)
        await claude_call(ctx, "composition", 4, inp=1892, w1=0, out=1875)
        await ctx.emit("answer_block", {"index": 0, "text": "Answer.", "citations": []})
        await ctx.emit("run_ended", ended_data(ctx, rounds=0, answer_chars=7))

    h = make_app(script)
    async with lifespan(h.app):
        run_id, s = await begin(h)
        t = s.events()[-1]["data"]["totals"]
        c = t["claude"]
        assert c["calls"] == 5, "attempts, each billed"
        assert c["input_tokens"] == 12046 + (51 + 12000) + (19 + 5027 + 12052) + (7 + 17000) + 1892
        assert (c["cache_read_tokens"], c["cache_write_tokens"], c["output_tokens"]) == (
            12052 + 17000, 17027, 406 + 491 + 300 + 1875)
        loop = sum(price(u) for u in (failed_attempt_usage("anthropic", LOOP_MODEL, 12046),
                                      claude_usage(inp=51, w1=12000, out=406),
                                      claude_usage(inp=19, w5=5027, w1=0, read=12052, out=491)))
        assert c["cost_usd"]["loop"] == pytest.approx(loop)
        assert c["cost_usd"]["update"] == pytest.approx(price(claude_usage(UPDATE_MODEL, inp=7, w1=0, read=17000, out=300)))
        assert c["cost_usd"]["composition"] == pytest.approx(price(claude_usage(COMPOSITION_MODEL, inp=1892, w1=0, out=1875)))
        assert h.run(run_id).totals() == t
        assert set(c["cost_usd"]) == {"loop", "update", "composition"}


async def test_an_unpriceable_call_fails_the_run_and_records_nothing():
    async def script(ctx, deps):
        await ctx.emit("run_started", run_started_data(ctx))
        await ctx.before_paid_call("anthropic", "loop")
        await ctx.record_usage(Usage(service="anthropic", model="claude-unknown"), purpose="loop", attempt=1,
                               max_attempts=3, outcome="ok", error_kind=None, duration_ms=1, call_no=1)

    h = make_app(script)
    async with lifespan(h.app):
        run_id, s = await begin(h)
        s.pump()
        assert s.events()[-1]["data"]["state"] == "failed"
        assert h.registry.in_progress == 0
        assert (await month(h.store))["spent"] == 0


async def test_a_zero_cost_call_makes_no_atlas_call():
    store = FlakyStore()

    async def script(ctx, deps):
        await ctx.emit("run_started", run_started_data(ctx))
        await ctx.before_paid_call("exa", "update_search")
        await ctx.record_usage(Usage(service="exa", model="auto", exa_cost_usd=0.0), purpose="update_search",
                               attempt=1, max_attempts=1, outcome="failed", error_kind="bad_request", duration_ms=5)
        await ctx.emit("run_ended", ended_data(ctx, state="failed", answer_end="none", failure_reason="overloaded"))

    h = make_app(script, store=store)
    async with lifespan(h.app):
        await begin(h)
        assert "record_spend" not in store.calls


# --- the spend recorded when Atlas fails (P4.21) --------------------------------------------------------------------------
def three_calls(ctx_calls):
    async def script(ctx, deps):
        await ctx.emit("run_started", run_started_data(ctx))
        for i in range(ctx_calls):
            await loop_call(ctx, call_no=i + 1)
        await ctx.emit("answer_block", {"index": 0, "text": "Text.", "citations": []})
        await ctx.emit("run_ended", ended_data(ctx, answer_chars=5))
    return script


async def test_a_failed_spend_write_is_kept_and_recorded_once_at_the_end(caplog):
    store = FlakyStore()
    store.fail["record_spend"] = 1               # the first call's write fails; Atlas is back by the end
    caplog.set_level(logging.INFO)
    h = make_app(three_calls(3), store=store)
    async with lifespan(h.app):
        run_id, s = await begin(h)
        await h.clock.settle()
        costs = [p["cost_usd"] for p in paid(s)]
        assert len(costs) == 3 and s.events()[-1]["data"]["state"] == "answered"
        # one failed write, then no more spend calls for this run until the end, which records the sum once
        assert store.calls["record_spend"] == 2
        await assert_spent(store.inner, costs)
    assert "could not be recorded" in caplog.text and "kept" in caplog.text
    assert "db.example.internal" not in caplog.text and "StoreUnavailable" in caplog.text
    assert "lost" not in caplog.text


async def test_after_a_failure_the_run_makes_no_more_spend_calls_so_a_dead_atlas_costs_no_timeouts():
    store = FlakyStore()
    store.fail["record_spend"] = -1
    h = make_app(three_calls(5), store=store)
    async with lifespan(h.app):
        run_id, s = await begin(h)
        await h.clock.settle()
        assert store.calls["record_spend"] == 1 + 1, "the first call's write, and the one sum at the end"
        assert s.events()[-1]["data"]["state"] == "answered"
        assert h.run(run_id).totals()["claude"]["calls"] == 5, "the costs are kept in the totals"


async def test_kept_spend_that_cannot_be_recorded_at_the_end_is_logged_as_lost(caplog):
    store = FlakyStore()
    store.fail["record_spend"] = -1
    caplog.set_level(logging.INFO)
    h = make_app(three_calls(2), store=store)
    async with lifespan(h.app):
        run_id, s = await begin(h)
        await h.clock.settle()
        total = h.run(run_id).totals()["claude"]["cost_usd"]["loop"]
        assert (await month(store.inner)) is None or (await month(store.inner))["spent"] == 0
        assert h.registry.in_progress == 0 and h.run(run_id).finished.is_set()
    assert f"{total:.6f} of spend is lost" in caplog.text
    assert "db.example.internal" not in caplog.text


async def test_the_end_survives_a_second_cancellation():
    """The end runs in a shielded task: a second cancellation while the kept costs are being recorded cannot skip it."""
    store = FlakyStore()
    clock = FakeClock()

    async def script(ctx, deps):
        await ctx.emit("run_started", run_started_data(ctx))
        await loop_call(ctx)
        await clock.sleep(1000)

    store.fail["record_spend"] = 1
    h = make_app(script, store=store, clock=clock)
    async with lifespan(h.app):
        run_id, s = await begin(h)
        run = h.run(run_id)
        cost = run.totals()["claude"]["cost_usd"]["loop"]
        store.gates["record_spend"] = asyncio.Event()
        run.cancel()
        await clock.settle()
        assert store.calls.get("record_spend") == 2 and not run.finished.is_set()    # the end waits on Atlas
        assert h.registry.in_progress == 1
        run.cancel()
        await clock.settle()
        store.gates["record_spend"].set()
        await clock.settle()
        assert run.finished.is_set() and h.registry.in_progress == 0
    assert (await store.inner.read_month("2026-10"))["spent"] == pytest.approx(cost)


# --- the slot freed on every end path -----------------------------------------------------------------------------------
def ending(state, *, stop_kind=None, answer_end="none", extra=None):
    async def script(ctx, deps):
        await ctx.emit("run_started", run_started_data(ctx))
        await loop_call(ctx)
        if answer_end != "none":
            await ctx.emit("answer_block", {"index": 0, "text": "Text.", "citations": []})
        data = ended_data(ctx, state=state, stop_kind=stop_kind, answer_end=answer_end,
                          answer_chars=5 if answer_end != "none" else 0) | (extra or {})
        await ctx.emit("run_ended", data)
    return script


async def raises(ctx, deps):
    await ctx.emit("run_started", run_started_data(ctx))
    await loop_call(ctx)
    raise RuntimeError("a bug in the loop")


async def returns_silently(ctx, deps):
    await ctx.emit("run_started", run_started_data(ctx))
    await loop_call(ctx)


ENDINGS = {
    "answered": ending("answered", answer_end="complete"),
    "no_sources": ending("no_sources", extra={"no_sources_reason": "out_of_scope", "note": "Outside."}),
    "step_limit": ending("step_limit", stop_kind="step_limit", answer_end="complete"),
    "token_ceiling": ending("token_ceiling", stop_kind="token_ceiling_input", answer_end="complete"),
    "cut_off": ending("answered", stop_kind="composition_max_tokens", answer_end="cut_off"),
    "time_limit": ending("time_limit", stop_kind="time_limit", answer_end="complete"),
    "spend_limit": ending("spend_limit", stop_kind="console_spend_limit"),
    "refusal": ending("refusal", extra={"failure_reason": "refusal"}),
    "raises": raises,
    "returns_without_run_ended": returns_silently,
}


@pytest.mark.parametrize("name", list(ENDINGS))
async def test_the_slot_is_freed_and_the_spend_recorded_on_every_end(name):
    h = make_app(ENDINGS[name])
    async with lifespan(h.app):
        run_id, s = await begin(h)
        await h.clock.settle()
        assert s.closed and s.events()[-1]["kind"] == "run_ended"
        assert h.registry.in_progress == 0
        await assert_spent(h.store, [p["cost_usd"] for p in paid(s)])
    assert h.schema_errors == []


async def test_the_slot_is_freed_after_run_ended_not_before():
    gate = asyncio.Event()

    async def script(ctx, deps):
        await ctx.emit("run_started", run_started_data(ctx))
        await gate.wait()
        await ctx.emit("run_ended", ended_data(ctx, state="no_sources", answer_end="none", rounds=0)
                       | {"no_sources_reason": "nothing_found", "note": "n"})

    h = make_app(script)
    async with lifespan(h.app):
        run_id, s = await begin(h)
        assert h.registry.in_progress == 1
        gate.set()
        await h.clock.settle()
        s.pump()
        assert s.events()[-1]["kind"] == "run_ended" and h.registry.in_progress == 0


async def test_released_when_abandoned():
    clock = FakeClock()

    async def script(ctx, deps):
        await ctx.emit("run_started", run_started_data(ctx))
        await loop_call(ctx)
        await clock.sleep(30)
        try:
            await loop_call(ctx, call_no=2)
        except RunStopped:
            await ctx.emit("run_ended", ended_data(ctx, state="abandoned", answer_end="none"))

    h = make_app(script, clock=clock)
    async with lifespan(h.app):
        run_id, s = await begin(h)
        await clock.advance(ABANDON + 1)
        s.pump()
        assert s.events()[-1]["data"]["state"] == "abandoned"
        await assert_spent(h.store, [p["cost_usd"] for p in paid(s)])
        assert len(paid(s)) == 1 and h.registry.in_progress == 0


async def test_nothing_ever_attaches_frees_the_slot_with_no_spend():
    h = make_app()
    async with lifespan(h.app):
        run_id = (await h.client.post("/runs", {"question": QUESTION})).json()["run_id"]
        await h.clock.advance(EXPIRY - 0.1)
        assert h.registry.in_progress == 1
        await h.clock.advance(0.2)
        assert h.registry.in_progress == 0
        assert (await month(h.store))["spent"] == 0
        assert h.contexts == [], "an expired run never ran: no spend"
        r = await h.client.get(f"/runs/{run_id}/events")
        assert r.status == 404 and r.json()["error"] == "run_unknown"
        r = await h.client.post(f"/runs/{run_id}/alive", {"last_event": 0})
        assert r.status == 404


async def test_attaching_before_the_expiry_keeps_the_run():
    h = make_app()
    async with lifespan(h.app):
        run_id = (await h.client.post("/runs", {"question": QUESTION})).json()["run_id"]
        await h.clock.advance(EXPIRY - 1)
        s = h.client.stream(f"/runs/{run_id}/events")
        await h.clock.advance(10)
        s.pump()
        assert s.events()[-1]["data"]["state"] == "answered"
        assert (await month(h.store))["spent"] > 0


async def test_shutdown_for_a_paused_run_and_an_unattached_one():
    clock = FakeClock()

    async def script(ctx, deps):
        await ctx.emit("run_started", run_started_data(ctx))
        await loop_call(ctx)
        await clock.sleep(30)
        await loop_call(ctx, call_no=2)                   # paused here when the instance shuts down

    h = make_app(script, clock=clock)
    async with lifespan(h.app):
        run_id, s = await begin(h)
        other = (await h.client.post("/runs", {"question": QUESTION})).json()["run_id"]
        await clock.advance(35)
        s.pump()
        assert [e["kind"] for e in s.events()][-1] == "paused"
    assert h.registry.in_progress == 0
    rec = await h.store.get_run_record(run_id)
    assert rec["state"] == "interrupted"                  # no run_ended: a reconnect elsewhere says interrupted
    assert other not in h.registry


# --- H's failed ending ---------------------------------------------------------------------------------------------------
@pytest.mark.parametrize("exc,reason", [(ServiceError("anthropic", "overloaded", 529), "overloaded"),
                                        (RuntimeError("boom"), "internal"), (KeyError("x"), "internal")])
async def test_failed_when_execute_run_raises(exc, reason, caplog):
    async def script(ctx, deps):
        await ctx.emit("run_started", run_started_data(ctx))
        await ctx.emit("round_started", round_data(1))
        await ctx.emit("round_started", round_data(1, "update"))
        raise exc

    h = make_app(script)
    async with lifespan(h.app):
        run_id, s = await begin(h)
        end = s.events()[-1]
        assert end["kind"] == "run_ended" and s.closed
        d = end["data"]
        assert (d["state"], d["failure_reason"], d["answer_end"], d["rounds"], d["stop_kind"]) == (
            "failed", reason, "none", 1, None), "rounds are research's: the update round is not counted"
        assert d["totals"] == h.run(run_id).totals()
        rec = await h.store.get_run_record(run_id)
        assert rec["state"] == "failed" and rec["rounds"] == 1
    assert h.schema_errors == []
    assert "boom" not in caplog.text


async def test_an_event_after_run_ended_is_refused():
    errors = []

    async def script(ctx, deps):
        await ctx.emit("run_started", run_started_data(ctx))
        await ctx.emit("run_ended", ended_data(ctx, state="failed", answer_end="none", failure_reason="overloaded"))
        try:
            await ctx.emit("round_started", round_data(2))
        except RuntimeError as e:
            errors.append(str(e))

    h = make_app(script)
    async with lifespan(h.app):
        run_id, s = await begin(h)
        assert errors and [e["kind"] for e in s.events()] == ["run_started", "run_ended"]


# --- stops and the spend-limit flag ------------------------------------------------------------------------------------
@pytest.mark.parametrize("name,kind", [("step_limit", "step_limit"), ("token_ceiling", "token_ceiling_input"),
                                       ("cut_off", "composition_max_tokens"), ("time_limit", "time_limit"),
                                       ("spend_limit", "console_spend_limit"), ("answered", None),
                                       ("raises", None)])
async def test_the_stop_named_by_run_ended_is_recorded_once(name, kind):
    h = make_app(ENDINGS[name])
    async with lifespan(h.app):
        run_id, s = await begin(h)
        await h.clock.settle()
        stops = await h.store.read_stops(day="2026-10-24")
        assert [x["kind"] for x in stops] == ([kind] if kind else [])
        if kind:
            assert stops[0]["run"] == run_id
            assert stops[0]["budget"] is (kind != "time_limit")
            assert (await month(h.store))["days"]["2026-10-24"]["stops"] == {kind: 1}


@pytest.mark.parametrize("kind", ["console_spend_limit", "tier_spend_cap"])
async def test_a_spend_limit_pauses_live_research_until_the_1st(kind):
    h = make_app(ending("spend_limit", stop_kind=kind))
    async with lifespan(h.app):
        run_id, s = await begin(h)
        await h.clock.settle()
        until = await h.store.flag_until("anthropic_spend_limit", h.clock.now())
        assert until is not None and until.isoformat() == "2026-11-01T00:00:00-05:00"
        r = await h.client.post("/runs", {"question": QUESTION})
        assert r.status == 503 and r.json()["error"] == "paused_month"
        assert (await h.client.get("/health")).json()["live_research"] == "paused_month"


@pytest.mark.parametrize("kind", ["console_spend_limit", "tier_spend_cap"])
async def test_a_spend_limit_met_by_the_composition_pauses_research_too(kind):
    # the composition broke after its first block on the spend limit, so the run is answered and incomplete with the
    # stop in stop_kinds; research still pauses until the 1st (T3.3, T5.4)
    h = make_app(ending("answered", answer_end="incomplete",
                        extra={"failure_reason": "spend_limit", "stop_kinds": [kind]}))
    async with lifespan(h.app):
        await begin(h)
        await h.clock.settle()
        until = await h.store.flag_until("anthropic_spend_limit", h.clock.now())
        assert until is not None and until.isoformat() == "2026-11-01T00:00:00-05:00"


def answered_with_update(update_end, stop_kinds, *, state="answered"):
    """An answered run whose update step ended as given (G's stop_kinds lists every stop of either step)."""
    async def script(ctx, deps):
        await ctx.emit("run_started", run_started_data(ctx))
        await ctx.emit("round_started", round_data(1))
        await loop_call(ctx)
        await ctx.emit("update_started", {"kept": []})
        await ctx.emit("round_started", round_data(1, "update"))
        await claude_call(ctx, "update", 2, inp=10, w1=0, read=15000, out=200)
        await claude_call(ctx, "composition", 3, inp=1000, w1=0, out=900)
        await ctx.emit("answer_block", {"index": 0, "text": "Text.", "citations": []})
        await ctx.emit("update_ended", update_end)
        await ctx.emit("run_ended", ended_data(ctx, state=state, answer_chars=5) | {"stop_kinds": stop_kinds})
    return script


@pytest.mark.parametrize("kind", ["console_spend_limit", "tier_spend_cap"])
async def test_a_spend_limit_met_by_the_update_step_sets_the_flag_in_an_answered_run(kind):
    end = update_ended_data("stopped", stop_kind=kind, failure_reason="spend_limit" if kind == "console_spend_limit"
                            else "spend_cap", rounds=1, searches=0)
    h = make_app(answered_with_update(end, [kind]))
    async with lifespan(h.app):
        run_id, s = await begin(h)
        await h.clock.settle()
        assert s.events()[-1]["data"]["state"] == "answered"
        until = await h.store.flag_until("anthropic_spend_limit", h.clock.now())
        assert until is not None and until.isoformat() == "2026-11-01T00:00:00-05:00"
        assert [x["kind"] for x in await h.store.read_stops(day="2026-10-24")] == [kind]
    assert h.schema_errors == []


async def test_the_update_steps_own_stop_is_recorded_even_if_the_list_lacks_it():
    end = update_ended_data("stopped", stop_kind="tier_spend_cap", failure_reason="spend_cap", rounds=1, searches=0)
    h = make_app(answered_with_update(end, []))
    async with lifespan(h.app):
        await begin(h)
        await h.clock.settle()
        assert [x["kind"] for x in await h.store.read_stops(day="2026-10-24")] == ["tier_spend_cap"]
        assert await h.store.flag_until("anthropic_spend_limit", h.clock.now()) is not None


@pytest.mark.parametrize("kind,budget", [("update_step_limit", True), ("update_token_ceiling_input", True),
                                         ("update_token_ceiling_output", True), ("update_time_limit", False)])
async def test_each_update_stop_in_stop_kinds_is_recorded_without_the_flag(kind, budget):
    end = update_ended_data("stopped", stop_kind=kind, rounds=8, searches=2)
    h = make_app(answered_with_update(end, [kind]))
    async with lifespan(h.app):
        run_id, s = await begin(h)
        await h.clock.settle()
        [stop] = await h.store.read_stops(day="2026-10-24")
        assert (stop["kind"], stop["run"], stop["budget"]) == (kind, run_id, budget)
        assert s.events()[-1]["data"]["state"] == "answered"
        assert await h.store.flag_until("anthropic_spend_limit", h.clock.now()) is None
    assert h.schema_errors == []


async def test_a_run_with_no_spend_stop_sets_no_flag():
    h = make_app(ending("step_limit", stop_kind="step_limit", answer_end="complete",
                        extra={"stop_kinds": ["step_limit"]}))
    async with lifespan(h.app):
        await begin(h)
        await h.clock.settle()
        assert await h.store.flag_until("anthropic_spend_limit", h.clock.now()) is None


async def test_the_flag_is_set_before_the_slot_is_freed():
    order = []
    store = FlakyStore()
    real_set = store.inner.set_flag

    async def set_flag(*a, **kw):
        order.append(("flag", h.registry.in_progress))
        return await real_set(*a, **kw)

    store.inner.set_flag = set_flag
    h = make_app(ending("spend_limit", stop_kind="tier_spend_cap"), store=store)
    async with lifespan(h.app):
        await begin(h)
        await h.clock.settle()
        assert h.registry.in_progress == 0
    assert order == [("flag", 1)], "no new run is admitted between the stop and the flag"


async def test_other_ends_do_not_set_the_flag():
    for name in ("answered", "raises", "refusal", "time_limit"):
        h = make_app(ENDINGS[name])
        async with lifespan(h.app):
            await begin(h)
            await h.clock.settle()
            assert await h.store.flag_until("anthropic_spend_limit", h.clock.now()) is None, name


# --- the run record (T3.7) ---------------------------------------------------------------------------------------------
class RecordingStore(FlakyStore):
    """Remembers every record the run sent, whether the allowlist took it or not."""

    def __init__(self):
        super().__init__()
        self.sent: list[dict] = []
        real = self.inner.upsert_run_record

        async def upsert(record):
            self.sent.append(json.loads(json.dumps(record)))
            await real(record)
        self.inner.upsert_run_record = upsert


async def test_the_run_record_is_the_allowlisted_shape_with_no_text():
    secret_query = "thermal imaging of the home interior"
    answer = "The Court held that using a thermal imager is a search."

    async def script(ctx, deps):
        await ctx.emit("run_started", run_started_data(ctx))
        await ctx.emit("round_started", round_data(1))
        await ctx.before_paid_call("anthropic", "loop")
        await ctx.record_usage(failed_attempt_usage("anthropic", LOOP_MODEL, 1000), purpose="loop",
                               attempt=1, max_attempts=3, outcome="retrying", error_kind="overloaded",
                               duration_ms=10, call_no=1)
        await loop_call(ctx, call_no=1)
        for i, (name, inp) in enumerate((("search_meaning", {"query": secret_query}), ("search_exact", {"all_of": ["thermal"]}),
                                         ("search_meaning", {"query": "heat"}))):
            await ctx.emit("tool_call", {"step": "research", "round": 1, "tool_use_id": f"t{i}", "name": name,
                                         "input": inp})
        await ctx.emit("tool_call", {"step": "research", "round": 1, "tool_use_id": "w0", "name": "search_web_updates",
                                     "input": {"query": secret_query}})      # the wrong step's tool: never counted
        await ctx.emit("tool_result", {"step": "research", "tool_use_id": "w0", "name": "search_web_updates",
                                       "is_error": True, "content": "x", "wrong_step": True})
        await ctx.before_paid_call("voyage", "rerank")
        await ctx.record_usage(None, purpose="rerank", attempt=1, max_attempts=3, outcome="retrying",
                               error_kind="server_error", duration_ms=5)
        await ctx.emit("warning", {"code": "meaning_search_degraded"})
        await ctx.emit("tool_result", {"step": "research", "tool_use_id": "t-k", "name": "keep_passages",
                                       "is_error": False, "content": "kept", "kept": [], "refused": [],
                                       "kept_count": 3})
        await ctx.emit("update_started", {"kept": []})
        await ctx.emit("round_started", round_data(1, "update"))
        await ctx.emit("tool_call", {"step": "update", "round": 1, "tool_use_id": "u1", "name": "search_web_updates",
                                     "input": {"query": secret_query}})
        await ctx.emit("tool_result", {"step": "update", "tool_use_id": "u1", "name": "search_web_updates",
                                       "is_error": False, "content": "pages", "search_no": 1, "web": [],
                                       "web_status": "ok"})
        await claude_call(ctx, "update", 2, inp=10, w1=0, read=15000, out=200)
        await ctx.emit("round_started", round_data(2, "update"))
        await ctx.emit("answer_block", {"index": 0, "text": answer, "citations": []})
        await ctx.emit("checks", {"quotations_checked": 2, "quotations_found": 1, "citations_checked": 3,
                                  "citations_found": 2, "not_in_corpus": ["Entick v. Carrington"],
                                  "flags": [{"block": 0, "start": 0, "end_block": 0, "end": 5,
                                             "kind": "not_in_corpus", "text": "Entick"}]})
        await ctx.emit("update_ended", update_ended_data("submitted", rounds=2, searches=1))
        await ctx.emit("run_ended", ended_data(ctx, stop_kind="composition_max_tokens", answer_end="cut_off",
                                               rounds=1, answer_chars=len(answer))
                       | {"scope_note": "A scope note with words in it."})

    store = RecordingStore()
    h = make_app(script, store=store)
    async with lifespan(h.app):
        run_id, s = await begin(h)
        await h.clock.settle()
        stored = await store.inner.get_run_record(run_id)
        t = s.events()[-1]["data"]["totals"]
    full = store.sent[0]
    assert full == {
        "run": run_id, "state": "answered", "stop_kind": "composition_max_tokens", "rounds": 1,
        "answer_chars": len(answer), "searches": {"meaning": 2, "exact": 1, "web": 1}, "keeps": 3,
        "tokens": {"input": t["claude"]["input_tokens"], "cache_read": 15000, "cache_write": 12000, "output": 600},
        "cost_usd": {"claude_loop": t["claude"]["cost_usd"]["loop"], "claude_update": t["claude"]["cost_usd"]["update"],
                     "claude_composition": 0, "exa": 0, "voyage": 0},
        "calls": {"claude": 3, "exa": 0, "voyage": 1}, "retries": {"claude": 1, "voyage": 1},
        "update_rounds": 2, "update_end": "submitted",
        "voyage_warning": "degraded", "corpus_label": "full",
        "started_date": "2026-10-24", "started_time": "22:00:00",
        "checks": {"quotations_checked": 2, "quotations_found": 1, "citations_checked": 3, "citations_found": 2,
                   "not_in_corpus": 1, "flags": 1}}
    assert full["cost_usd"]["claude_update"] > 0
    assert stored == full, "the store's allowlist takes the update-step fields"
    text = json.dumps(full)
    for words in (QUESTION, secret_query, answer, "Entick", "scope note"):
        assert words not in text


async def test_the_record_with_the_update_fields_is_written_once_and_accepted():
    store = RecordingStore()
    h = make_app(answered_with_update(update_ended_data("submitted", rounds=2, searches=1), []), store=store)
    async with lifespan(h.app):
        run_id, s = await begin(h)
        await h.clock.settle()
        assert len(store.sent) == 1, "one write, no fallback"
        stored = await store.inner.get_run_record(run_id)
        assert stored == store.sent[0]
        assert stored["update_rounds"] == 2 and stored["update_end"] == "submitted"
        assert stored["cost_usd"]["claude_update"] > 0


async def test_the_record_carries_the_corpus_label_and_unavailable_warning():
    async def script(ctx, deps):
        await ctx.emit("run_started", run_started_data(ctx))
        await ctx.emit("warning", {"code": "meaning_search_degraded"})
        await ctx.emit("warning", {"code": "meaning_search_unavailable"})
        await ctx.emit("run_ended", ended_data(ctx, state="no_sources", answer_end="none", rounds=0)
                       | {"no_sources_reason": "nothing_found", "note": "n"})

    h = make_app(script, corpus_label="before_chatrie")
    async with lifespan(h.app):
        run_id, s = await begin(h)
        await h.clock.settle()
        rec = await h.store.get_run_record(run_id)
        assert rec["corpus_label"] == "before_chatrie" and rec["voyage_warning"] == "unavailable"
        assert "update_end" not in rec, "no update_ended was emitted"
        assert h.contexts[0].corpus_label == "before_chatrie"


def test_counting_by_step_from_events():
    """contract §4.H: research's rounds are round_started with step research; the update step's come from update_ended;
    update searches from tool_results carrying search_no; a wrong-step call is never counted."""
    from api.server.summary import rounds_of, update_ended_of, update_searches_of, _tool_calls

    def ev(kind, **data):
        return {"kind": kind, "data": data}
    events = [
        ev("round_started", step="research", round=1), ev("round_started", step="research", round=2),
        ev("round_started", step="update", round=1), ev("round_started", step="update", round=2),
        ev("round_started", step="update", round=3),
        ev("tool_call", step="research", tool_use_id="a", name="search_meaning"),
        ev("tool_call", step="update", tool_use_id="b", name="search_meaning"),      # refused: the other step's tool
        ev("tool_result", step="update", tool_use_id="b", name="search_meaning", wrong_step=True),
        ev("tool_call", step="update", tool_use_id="c", name="search_web_updates"),
        ev("tool_result", step="update", tool_use_id="c", name="search_web_updates", search_no=1),
        ev("tool_call", step="update", tool_use_id="d", name="search_web_updates"),
        ev("tool_result", step="update", tool_use_id="d", name="search_web_updates", search_no=2),
        ev("tool_call", step="research", tool_use_id="e", name="search_web_updates"),
        ev("tool_result", step="research", tool_use_id="e", name="search_web_updates", wrong_step=True),
        ev("update_ended", end="submitted", stop_kind=None, failure_reason=None, rounds=3, searches=2)]
    assert rounds_of(events) == 2
    assert update_searches_of(events) == 2
    assert _tool_calls(events, "search_meaning") == 1 and _tool_calls(events, "search_web_updates") == 2
    assert update_ended_of(events)["rounds"] == 3
    assert update_ended_of(events[:-1]) is None


async def test_logs_hold_no_question_or_answer(caplog):
    caplog.set_level(logging.DEBUG)
    h = make_app()
    async with lifespan(h.app):
        await begin(h, question="What did Kyllo hold about heat?")
        await h.clock.settle()
    assert "Kyllo" not in caplog.text and "An answer." not in caplog.text
    assert "paid call" in caplog.text and "ended: state=answered" in caplog.text


@pytest.mark.parametrize("state,kind", [("step_limit", "step_limit"), ("token_ceiling", "token_ceiling_output"),
                                        ("time_limit", "time_limit")])
async def test_a_loop_limit_cut_off_in_composition_records_its_stop_kind(state, kind):
    """v1.3: a loop limit keeps its stop_kind when its composition is then cut off; H records that kind."""
    h = make_app(ending(state, stop_kind=kind, answer_end="cut_off"))
    async with lifespan(h.app):
        run_id, s = await begin(h)
        await h.clock.settle()
        assert [x["kind"] for x in await h.store.read_stops(day="2026-10-24")] == [kind]
        assert (await h.store.get_run_record(run_id))["stop_kind"] == kind
        assert h.registry.in_progress == 0
    assert h.schema_errors == []
