"""`record_usage`, the reservation and the end of a run (contract §4.H, §6.2, §8; T3.3, T3.4, T3.7)."""

import asyncio
import json

import pytest

from api import settings
from api.errors import ServiceError
from api.state.budget import worst_case_usd
from api.state.prices import failed_attempt_usage, price, price_sources
from api.types import RunStopped, Usage
from tests.server.support import (QUESTION, START, FakeClock, FlakyStore, claude_usage, ended_data, lifespan,
                                  loop_call, make_app, raw_claude, run_started_data)

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


async def assert_released(store, costs):
    m = await month(store)
    assert m["reservations"] == {}, "the reservation was released"
    assert m["reserved"] == pytest.approx(0, abs=1e-9)
    assert m["days"]["2026-10-24"]["reserved"] == pytest.approx(0, abs=1e-9)
    assert m["spent"] == pytest.approx(sum(costs), abs=1e-12)


# --- pricing and settling ------------------------------------------------------------------------------------------------
async def test_record_usage_prices_settles_and_emits():
    seen = {}

    async def script(ctx, deps):
        await ctx.emit("run_started", run_started_data(ctx))
        seen["cost"] = await loop_call(ctx, call_no=1, inp=51, w1=12000, out=406)
        seen["month"] = await month(h.store)                     # settled as the call completes, not at the end
        await ctx.emit("run_ended", ended_data(ctx, state="failed", answer_end="none", failure_reason="overloaded"))

    h = make_app(script)
    async with lifespan(h.app):
        run_id, s = await begin(h)
        expected = price(claude_usage(inp=51, w1=12000, out=406))
        assert seen["cost"] == pytest.approx(expected, rel=1e-12) and seen["cost"] == pytest.approx(0.052162)
        m = seen["month"]
        assert m["spent"] == pytest.approx(expected)
        assert m["reservations"][run_id]["amount"] == pytest.approx(worst_case_usd() - expected)
        assert m["reserved"] == pytest.approx(worst_case_usd() - expected)
        [p] = paid(s)
        assert p == {"call_no": 1, "service": "anthropic", "purpose": "loop", "attempt": 1, "max_attempts": 3,
                     "outcome": "ok", "error_kind": None, "duration_ms": 1500,
                     "usage": raw_claude(inp=51, w1=12000, out=406), "estimated_usage": None,
                     "cost_usd": round(expected, 10), "estimated": False}
        await assert_released(h.store, [expected])
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
        costs.append(await rec(failed_attempt_usage("anthropic", "claude-opus-5-5", 1803), purpose="composition",
                               attempt=1, max_attempts=3, outcome="retrying", error_kind="overloaded",
                               duration_ms=1300, raw_usage=None, call_no=4))
        await ctx.emit("run_ended", ended_data(ctx, state="failed", answer_end="none", failure_reason="overloaded"))

    h = make_app(script)
    async with lifespan(h.app):
        run_id, s = await begin(h)
        p = paid(s)
        assert [x["usage"] for x in p] == [{"total_tokens": 28}, None, None, None, None]
        assert [x["estimated"] for x in p] == [False, True, False, True, True]
        assert costs == [pytest.approx(28 * 0.12 / 1e6), 0.0, 0.0, 0.004, pytest.approx(1803 * 4 / 1e6)]
        assert [x["cost_usd"] for x in p] == [pytest.approx(c) for c in costs]
        assert ["call_no" in x for x in p] == [False, False, False, False, True]
        t = s.events()[-1]["data"]["totals"]
        assert t["claude"] == {"calls": 1, "input_tokens": 1803, "cache_read_tokens": 0, "cache_write_tokens": 0,
                               "output_tokens": 0, "cost_usd": {"loop": 0, "composition": pytest.approx(0.007212)}}
        assert t["exa"] == {"searches": 2, "cost_usd": pytest.approx(0.004)}
        assert t["voyage"] == {"requests": 2, "cost_usd": pytest.approx(3.36e-06)}
        assert t["prices"] == price_sources()
        await assert_released(h.store, costs)
    assert h.schema_errors == []


async def test_totals_count_attempts_and_all_input():
    async def script(ctx, deps):
        await ctx.emit("run_started", run_started_data(ctx))
        await ctx.before_paid_call("anthropic", "loop")
        await ctx.record_usage(failed_attempt_usage("anthropic", "claude-sonnet-5-5", 12046), purpose="loop",
                               attempt=1, max_attempts=3, outcome="retrying", error_kind="rate_limited",
                               duration_ms=850, call_no=1)
        await loop_call(ctx, call_no=1, inp=51, w1=12000, out=406)
        await loop_call(ctx, call_no=2, inp=19, w5=5027, w1=0, read=12052, out=491)
        await ctx.before_paid_call("anthropic", "composition")
        await ctx.record_usage(claude_usage("claude-opus-5-5", inp=1892, w1=0, out=1875), purpose="composition",
                               attempt=1, max_attempts=3, outcome="ok", error_kind=None, duration_ms=9589,
                               raw_usage=raw_claude(inp=1892, w1=0, out=1875), call_no=3)
        await ctx.emit("answer_block", {"index": 0, "text": "Answer.", "citations": []})
        await ctx.emit("run_ended", ended_data(ctx, rounds=0, answer_chars=7))

    h = make_app(script)
    async with lifespan(h.app):
        run_id, s = await begin(h)
        t = s.events()[-1]["data"]["totals"]
        c = t["claude"]
        assert c["calls"] == 4, "attempts, each billed"
        assert c["input_tokens"] == 12046 + (51 + 12000) + (19 + 5027 + 12052) + 1892
        assert (c["cache_read_tokens"], c["cache_write_tokens"], c["output_tokens"]) == (12052, 17027, 406 + 491 + 1875)
        loop = sum(price(u) for u in (failed_attempt_usage("anthropic", "claude-sonnet-5-5", 12046),
                                      claude_usage(inp=51, w1=12000, out=406),
                                      claude_usage(inp=19, w5=5027, w1=0, read=12052, out=491)))
        assert c["cost_usd"]["loop"] == pytest.approx(loop)
        assert c["cost_usd"]["composition"] == pytest.approx(price(claude_usage("claude-opus-5-5", inp=1892, w1=0, out=1875)))
        assert h.run(run_id).totals() == t


async def test_an_unpriceable_call_fails_the_run_and_keeps_the_reservation():
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
        m = await month(h.store)
        assert run_id in m["reservations"], "a call that was made but could not be priced may have been billed"


# --- the reservation released on every end path ---------------------------------------------------------------------------
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
async def test_the_reservation_is_released_on_every_end(name):
    h = make_app(ENDINGS[name])
    async with lifespan(h.app):
        run_id, s = await begin(h)
        await h.clock.settle()
        assert s.closed and s.events()[-1]["kind"] == "run_ended"
        assert h.run(run_id).reservation_released
        await assert_released(h.store, [p["cost_usd"] for p in paid(s)])
        assert await h.store.open_reservations(h.clock.now()) == []
    assert h.schema_errors == []


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
        await assert_released(h.store, [p["cost_usd"] for p in paid(s)])
        assert len(paid(s)) == 1


async def test_released_when_nothing_ever_attaches():
    h = make_app()
    async with lifespan(h.app):
        run_id = (await h.client.post("/runs", {"question": QUESTION})).json()["run_id"]
        await h.clock.advance(EXPIRY - 0.1)
        assert run_id in (await month(h.store))["reservations"]
        await h.clock.advance(0.2)
        m = await month(h.store)
        assert m["reservations"] == {} and m["reserved"] == pytest.approx(0) and m["spent"] == 0
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


async def test_released_at_shutdown_for_a_paused_run_and_an_unattached_one():
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
    m = await month(h.store)
    assert m["reservations"] == {} and m["reserved"] == pytest.approx(0)
    rec = await h.store.get_run_record(run_id)
    assert rec["state"] == "interrupted"                  # no run_ended: a reconnect elsewhere says interrupted
    assert other not in m["reservations"]


async def test_kept_counted_when_cancelled_with_a_paid_call_in_flight():
    clock = FakeClock()

    async def script(ctx, deps):
        await ctx.emit("run_started", run_started_data(ctx))
        await ctx.before_paid_call("anthropic", "loop")
        await clock.sleep(100)                            # the call is running when the instance stops
        await ctx.record_usage(claude_usage(), purpose="loop", attempt=1, max_attempts=3, outcome="ok",
                               error_kind=None, duration_ms=100000, raw_usage=raw_claude(), call_no=1)

    h = make_app(script, clock=clock)
    async with lifespan(h.app):
        run_id, s = await begin(h)
        await clock.advance(5)
    m = await month(h.store)
    assert run_id in m["reservations"], "the call may have been billed: the reservation stays counted (T3.4)"


async def test_unsettled_spend_is_settled_at_the_end_or_the_reservation_stays():
    store = FlakyStore()
    store.fail["settle"] = 1                               # the call's own settle fails; the end's succeeds
    h = make_app(store=store)
    async with lifespan(h.app):
        run_id, s = await begin(h)
        await h.clock.settle()
        await assert_released(store.inner, [p["cost_usd"] for p in paid(s)])

    store = FlakyStore()
    store.fail["settle"] = -1
    h = make_app(store=store)
    async with lifespan(h.app):
        run_id, s = await begin(h)
        await h.clock.settle()
        assert s.events()[-1]["data"]["state"] == "answered"
        m = await store.inner.read_month("2026-10")
        assert run_id in m["reservations"], "spend Atlas never took is not released away"


# --- H's failed ending ---------------------------------------------------------------------------------------------------
@pytest.mark.parametrize("exc,reason", [(ServiceError("anthropic", "overloaded", 529), "overloaded"),
                                        (RuntimeError("boom"), "internal"), (KeyError("x"), "internal")])
async def test_failed_when_execute_run_raises(exc, reason, caplog):
    async def script(ctx, deps):
        await ctx.emit("run_started", run_started_data(ctx))
        await ctx.emit("round_started", {"round": 1, "status_line": "Round 1 of 12"})
        raise exc

    h = make_app(script)
    async with lifespan(h.app):
        run_id, s = await begin(h)
        end = s.events()[-1]
        assert end["kind"] == "run_ended" and s.closed
        d = end["data"]
        assert (d["state"], d["failure_reason"], d["answer_end"], d["rounds"], d["stop_kind"]) == (
            "failed", reason, "none", 1, None)
        assert d["totals"] == h.run(run_id).totals()
        rec = await h.store.get_run_record(run_id)
        assert rec["state"] == "failed"
    assert h.schema_errors == []
    assert "boom" not in caplog.text


async def test_an_event_after_run_ended_is_refused():
    errors = []

    async def script(ctx, deps):
        await ctx.emit("run_started", run_started_data(ctx))
        await ctx.emit("run_ended", ended_data(ctx, state="failed", answer_end="none", failure_reason="overloaded"))
        try:
            await ctx.emit("round_started", {"round": 2, "status_line": "x"})
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


async def test_the_flag_is_set_before_the_reservation_is_released():
    order = []
    store = FlakyStore()
    real_set, real_release = store.inner.set_flag, store.inner.release

    async def set_flag(*a, **kw):
        order.append("flag")
        return await real_set(*a, **kw)

    async def release(*a, **kw):
        order.append("release")
        return await real_release(*a, **kw)

    store.inner.set_flag, store.inner.release = set_flag, release
    h = make_app(ending("spend_limit", stop_kind="tier_spend_cap"), store=store)
    async with lifespan(h.app):
        await begin(h)
        await h.clock.settle()
    assert order == ["flag", "release"]


async def test_other_ends_do_not_set_the_flag():
    for name in ("answered", "raises", "refusal", "time_limit"):
        h = make_app(ENDINGS[name])
        async with lifespan(h.app):
            await begin(h)
            await h.clock.settle()
            assert await h.store.flag_until("anthropic_spend_limit", h.clock.now()) is None, name


# --- the run record (T3.7) ---------------------------------------------------------------------------------------------
async def test_the_run_record_is_the_allowlisted_shape_with_no_text():
    secret_query = "thermal imaging of the home interior"
    answer = "The Court held that using a thermal imager is a search."

    async def script(ctx, deps):
        await ctx.emit("run_started", run_started_data(ctx))
        await ctx.emit("round_started", {"round": 1, "status_line": "Round 1 of 12"})
        await ctx.before_paid_call("anthropic", "loop")
        await ctx.record_usage(failed_attempt_usage("anthropic", "claude-sonnet-5-5", 1000), purpose="loop",
                               attempt=1, max_attempts=3, outcome="retrying", error_kind="overloaded",
                               duration_ms=10, call_no=1)
        await loop_call(ctx, call_no=1)
        for name, inp in (("search_meaning", {"query": secret_query}), ("search_exact", {"all_of": ["thermal"]}),
                          ("search_meaning", {"query": "heat"}), ("search_web_updates", {"query": secret_query})):
            await ctx.emit("tool_call", {"round": 1, "tool_use_id": f"t-{name}", "name": name, "input": inp})
        await ctx.before_paid_call("voyage", "rerank")
        await ctx.record_usage(None, purpose="rerank", attempt=1, max_attempts=3, outcome="retrying",
                               error_kind="server_error", duration_ms=5)
        await ctx.emit("warning", {"code": "meaning_search_degraded"})
        await ctx.emit("tool_result", {"tool_use_id": "t-k", "name": "keep_passages", "is_error": False,
                                       "content": "kept", "kept": [], "refused": [], "kept_count": 3})
        await ctx.emit("answer_block", {"index": 0, "text": answer, "citations": []})
        await ctx.emit("checks", {"quotations_checked": 2, "quotations_found": 1, "citations_checked": 3,
                                  "citations_found": 2, "not_in_corpus": ["Entick v. Carrington"],
                                  "flags": [{"block": 0, "start": 0, "end_block": 0, "end": 5,
                                             "kind": "not_in_corpus", "text": "Entick"}]})
        await ctx.emit("run_ended", ended_data(ctx, stop_kind="composition_max_tokens", answer_end="cut_off",
                                               rounds=1, answer_chars=len(answer))
                       | {"scope_note": "A scope note with words in it."})

    h = make_app(script)
    async with lifespan(h.app):
        run_id, s = await begin(h)
        await h.clock.settle()
        rec = await h.store.get_run_record(run_id)
        t = s.events()[-1]["data"]["totals"]
    assert rec == {
        "run": run_id, "state": "answered", "stop_kind": "composition_max_tokens", "rounds": 1,
        "answer_chars": len(answer), "searches": {"meaning": 2, "exact": 1, "web": 1}, "keeps": 3,
        "tokens": {"input": t["claude"]["input_tokens"], "cache_read": 0, "cache_write": 12000, "output": 400},
        "cost_usd": {"claude_loop": t["claude"]["cost_usd"]["loop"], "claude_composition": 0, "exa": 0,
                     "voyage": 0},
        "calls": {"claude": 2, "exa": 0, "voyage": 1}, "retries": {"claude": 1, "voyage": 1},
        "voyage_warning": "degraded", "corpus_label": "full",
        "started_date": "2026-10-24", "started_time": "22:00:00",
        "checks": {"quotations_checked": 2, "quotations_found": 1, "citations_checked": 3, "citations_found": 2,
                   "not_in_corpus": 1, "flags": 1}}
    text = json.dumps(rec)
    for words in (QUESTION, secret_query, answer, "Entick", "scope note"):
        assert words not in text


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
        assert h.contexts[0].corpus_label == "before_chatrie"


async def test_logs_hold_no_question_or_answer(caplog):
    import logging
    caplog.set_level(logging.DEBUG)
    h = make_app()
    async with lifespan(h.app):
        await begin(h, question="What did Kyllo hold about heat?")
        await h.clock.settle()
    assert "Kyllo" not in caplog.text and "An answer." not in caplog.text
    assert "paid call" in caplog.text and "ended: state=answered" in caplog.text


async def test_the_end_survives_a_second_cancellation():
    """The release runs in a shielded `finally`: a second cancellation while the end is under way cannot skip it."""
    store = FlakyStore()
    clock = FakeClock()

    async def script(ctx, deps):
        await ctx.emit("run_started", run_started_data(ctx))
        await loop_call(ctx)
        await clock.sleep(1000)

    h = make_app(script, store=store, clock=clock)
    async with lifespan(h.app):
        run_id, s = await begin(h)
        run = h.run(run_id)
        store.gates["release"] = asyncio.Event()
        run.cancel()
        await clock.settle()
        assert store.calls.get("release") == 1 and not run.reservation_released    # the end waits on Atlas
        run.cancel()
        await clock.settle()
        store.gates["release"].set()
        await clock.settle()
        assert run.reservation_released and run.finished.is_set()
    m = await store.inner.read_month("2026-10")
    assert m["reservations"] == {}


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
        assert h.run(run_id).reservation_released
    assert h.schema_errors == []
