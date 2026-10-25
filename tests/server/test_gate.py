"""`before_paid_call` (contract §4.H, T3.2, T3.5): abandoned, then past the deadline (never for composition), then
unattended. Nothing is spent while nobody is watching."""

import asyncio

import pytest

from api import settings
from api.types import RunStopped
from tests.server.support import (QUESTION, FakeClock, ended_data, lifespan, loop_call, make_app, run_started_data)

pytestmark = pytest.mark.anyio
WINDOW = float(settings.ATTENDED_WINDOW_S.value)
ABANDON = float(settings.ABANDON_AFTER_S.value)
POLL = float(settings.HEARTBEAT_POLL_S.value)
DEADLINE = float(settings.RUN_DEADLINE_S.value)


class Probe:
    """A G-like script: each step waits `before` seconds of virtual time, then clears the gate for its purpose and,
    for a paid step, records a call. RunStopped ends the run the way G does."""

    def __init__(self, clock: FakeClock, steps):
        self.clock = clock
        self.steps = steps                      # [(wait_s, purpose)]
        self.passed: list[tuple[float, str]] = []
        self.stopped: list[tuple[float, str]] = []

    async def __call__(self, ctx, deps):
        await ctx.emit("run_started", run_started_data(ctx))
        try:
            for wait_s, purpose in self.steps:
                await self.clock.sleep(wait_s)
                await ctx.before_paid_call("anthropic" if purpose in ("loop", "composition") else "voyage", purpose)
                self.passed.append((self.clock.t, purpose))
        except RunStopped as e:
            self.stopped.append((self.clock.t, e.reason))
            if e.reason == "deadline":
                await ctx.before_paid_call("anthropic", "composition")
                self.passed.append((self.clock.t, "composition"))
                await ctx.emit("run_ended", ended_data(ctx, state="time_limit", stop_kind="time_limit",
                                                       answer_end="none"))
                return
            await ctx.emit("update_band", {"outcome": "not_run", "reason": None, "searches": [], "findings": [],
                                           "overview": None, "pages": []})
            await ctx.emit("run_ended", ended_data(ctx, state="abandoned", answer_end="none"))
            return
        await ctx.emit("run_ended", ended_data(ctx, state="no_sources", answer_end="none")
                       | {"no_sources_reason": "nothing_found", "note": "Nothing bears on it."})


async def begin(h):
    run_id = (await h.client.post("/runs", {"question": QUESTION})).json()["run_id"]
    s = h.client.stream(f"/runs/{run_id}/events")             # attaching at t = 0 is a heartbeat
    await h.clock.settle()
    s.pump()
    return run_id, s


def kinds(s):
    s.pump()
    return [(e["kind"], e["data"]) for e in s.events() if e["kind"] in ("paused", "resumed", "run_ended")]


async def alive(h, run_id, n=1):
    r = await h.client.post(f"/runs/{run_id}/alive", {"last_event": n})
    assert r.status == 204


async def keep_alive(h, run_id, until: float):
    while h.clock.t + 10 <= until:
        await h.clock.sleep(10)
        await alive(h, run_id)


async def test_attended_calls_pass_at_once():
    clock = FakeClock()
    p = Probe(clock, [(5, "loop"), (10, "embed")])
    h = make_app(p, clock=clock)
    async with lifespan(h.app):
        run_id, s = await begin(h)
        await clock.advance(20)
        assert p.passed == [(5, "loop"), (15, "embed")]
        assert [k for k, _ in kinds(s)] == ["run_ended"]
    assert h.schema_errors == []


async def test_unattended_pauses_until_a_heartbeat_then_resumes():
    clock = FakeClock()
    p = Probe(clock, [(30, "loop")])
    h = make_app(p, clock=clock)
    async with lifespan(h.app):
        run_id, s = await begin(h)
        await clock.advance(39.5)
        assert p.passed == [], "no paid call while nobody is watching"
        assert kinds(s) == [("paused", {"since_ms": 30000})]
        clock.t = 40.0
        await alive(h, run_id)
        await clock.settle()
        assert p.passed == [(40, "loop")]
        assert kinds(s)[:2] == [("paused", {"since_ms": 30000}), ("resumed", {"since_ms": 10000})]
    assert h.schema_errors == []


async def test_a_heartbeat_before_the_pause_does_not_resume_it():
    """Only a heartbeat that came after the pause began resumes the run."""
    clock = FakeClock()
    p = Probe(clock, [(30, "loop")])
    h = make_app(p, clock=clock)
    async with lifespan(h.app):
        run_id, s = await begin(h)
        clock.t = 3.0
        await alive(h, run_id)                   # last heartbeat at t = 3; the call comes at 30
        await clock.advance(36)                  # t = 39
        assert p.passed == [] and [k for k, _ in kinds(s)] == ["paused"]
        assert kinds(s)[0][1] == {"since_ms": 27000}


async def test_a_heartbeat_sent_to_another_instance_resumes_through_atlas():
    clock = FakeClock()
    p = Probe(clock, [(30, "loop")])
    h = make_app(p, clock=clock)
    async with lifespan(h.app):
        run_id, s = await begin(h)
        await clock.advance(41)
        await h.store.put_heartbeat(run_id, 3, clock.now())     # written by another instance at t = 41
        await clock.advance(POLL)
        assert len(p.passed) == 1 and 41 < p.passed[0][0] <= 41 + POLL
        assert [k for k, _ in kinds(s)] == ["paused", "resumed", "run_ended"]


async def test_an_atlas_heartbeat_read_before_pausing_avoids_the_pause():
    clock = FakeClock()
    p = Probe(clock, [(30, "loop")])
    h = make_app(p, clock=clock)
    async with lifespan(h.app):
        run_id, s = await begin(h)
        await clock.advance(20)
        await h.store.put_heartbeat(run_id, 3, clock.now())     # another instance got a heartbeat at t = 20
        await clock.advance(15)
        assert p.passed == [(30, "loop")]
        assert [k for k, _ in kinds(s)] == ["run_ended"]


@pytest.mark.parametrize("due", [30, 31, 33.7])     # polls that do not land on ABANDON_AFTER_S exactly
async def test_abandoned_exactly_abandon_after_s_after_the_last_heartbeat(due):
    clock = FakeClock()
    p = Probe(clock, [(due, "loop")])
    h = make_app(p, clock=clock)
    async with lifespan(h.app):
        run_id, s = await begin(h)
        await clock.advance(ABANDON - 0.1)
        assert p.stopped == [] and [k for k, _ in kinds(s)] == ["paused"]
        await clock.advance(0.1)
        assert p.stopped == [(ABANDON, "abandoned")] and p.passed == []
        assert [k for k, _ in kinds(s)] == ["paused", "run_ended"] and s.closed
        assert not [e for e in s.events() if e["kind"] == "paid_call"]
        assert h.run(run_id).abandoned


async def test_abandonment_counts_from_the_last_heartbeat_not_from_the_pause():
    clock = FakeClock()
    p = Probe(clock, [(50, "loop")])
    h = make_app(p, clock=clock)
    async with lifespan(h.app):
        run_id, s = await begin(h)
        clock.t = 20.0
        await alive(h, run_id)
        await clock.advance(20 + ABANDON - 20.1)            # t = 79.9
        assert p.stopped == [] and kinds(s)[0] == ("paused", {"since_ms": 30000})
        await clock.advance(0.1)                             # t = 80
        assert p.stopped == [(20 + ABANDON, "abandoned")]


async def test_after_abandonment_every_call_is_refused_without_pausing_again():
    clock = FakeClock()
    seen = []

    async def script(ctx, deps):
        await ctx.emit("run_started", run_started_data(ctx))
        await clock.sleep(30)
        for purpose in ("loop", "composition", "embed"):
            try:
                await ctx.before_paid_call("anthropic", purpose)
                seen.append((purpose, "passed"))
            except RunStopped as e:
                seen.append((purpose, e.reason))
        await ctx.emit("run_ended", ended_data(ctx, state="abandoned", answer_end="none"))

    h = make_app(script, clock=clock)
    async with lifespan(h.app):
        run_id, s = await begin(h)
        await clock.advance(ABANDON + 5)
        assert seen == [("loop", "abandoned"), ("composition", "abandoned"), ("embed", "abandoned")]
        assert [k for k, _ in kinds(s)] == ["paused", "run_ended"]


async def test_abandoned_comes_before_the_deadline():
    clock = FakeClock()
    seen = []

    async def script(ctx, deps):
        await ctx.emit("run_started", run_started_data(ctx))
        await clock.sleep(30)
        try:
            await ctx.before_paid_call("anthropic", "loop")
        except RunStopped as e:
            seen.append(e.reason)
        await clock.sleep(DEADLINE)                          # now past the deadline too
        for purpose in ("loop", "composition"):
            try:
                await ctx.before_paid_call("anthropic", purpose)
            except RunStopped as e:
                seen.append(e.reason)
        await ctx.emit("run_ended", ended_data(ctx, state="abandoned", answer_end="none"))

    h = make_app(script, clock=clock)
    async with lifespan(h.app):
        await begin(h)
        await clock.advance(DEADLINE + 200)
        assert seen == ["abandoned", "abandoned", "abandoned"]


async def test_past_the_deadline_only_composition_proceeds():
    clock = FakeClock()
    p = Probe(clock, [(DEADLINE - 1, "loop"), (2, "loop")])
    h = make_app(p, clock=clock)
    async with lifespan(h.app):
        run_id, s = await begin(h)
        beat = asyncio.ensure_future(keep_alive(h, run_id, DEADLINE + 10))
        await clock.advance(DEADLINE + 5)
        beat.cancel()
        assert p.passed == [(DEADLINE - 1, "loop"), (DEADLINE + 1, "composition")]
        assert p.stopped == [(DEADLINE + 1, "deadline")]
        assert kinds(s)[-1][1]["state"] == "time_limit"
        assert h.run(run_id).seconds_left() < 0


async def test_composition_also_waits_for_a_heartbeat():
    clock = FakeClock()
    p = Probe(clock, [(40, "composition")])
    h = make_app(p, clock=clock)
    async with lifespan(h.app):
        run_id, s = await begin(h)
        await clock.advance(45)
        assert p.passed == [] and [k for k, _ in kinds(s)] == ["paused"]
        await alive(h, run_id)
        await clock.settle()
        assert p.passed == [(45, "composition")]


async def test_the_deadline_is_checked_again_after_a_resume():
    clock = FakeClock()
    p = Probe(clock, [(DEADLINE - 5, "loop")])
    h = make_app(p, clock=clock)
    async with lifespan(h.app):
        run_id, s = await begin(h)
        beat = asyncio.ensure_future(keep_alive(h, run_id, DEADLINE - 30))   # last heartbeat at DEADLINE - 30
        await clock.advance(DEADLINE + 4)
        beat.cancel()
        assert [k for k, _ in kinds(s)] == ["paused"] and p.passed == []
        await alive(h, run_id)                                   # resumed past the deadline
        await clock.settle()
        assert p.stopped == [(DEADLINE + 4, "deadline")]
        assert p.passed == [(DEADLINE + 4, "composition")]
        assert [k for k, _ in kinds(s)][:2] == ["paused", "resumed"]


async def test_calls_due_together_while_unattended_pause_once():
    clock = FakeClock()
    passed = []

    async def script(ctx, deps):
        await ctx.emit("run_started", run_started_data(ctx))
        await clock.sleep(30)

        async def one(purpose):
            await ctx.before_paid_call("voyage", purpose)
            passed.append(purpose)
        await asyncio.gather(one("embed"), one("rerank"), one("loop"))
        await ctx.emit("run_ended", ended_data(ctx, state="no_sources", answer_end="none")
                       | {"no_sources_reason": "nothing_found", "note": "n"})

    h = make_app(script, clock=clock)
    async with lifespan(h.app):
        run_id, s = await begin(h)
        await clock.advance(35)
        assert passed == [] and [k for k, _ in kinds(s)] == ["paused"]
        await alive(h, run_id)
        await clock.settle()
        assert sorted(passed) == ["embed", "loop", "rerank"]
        assert [k for k, _ in kinds(s)] == ["paused", "resumed", "run_ended"]


async def test_no_paid_call_ever_passes_while_unattended():
    """Every call that passes the gate does so within ATTENDED_WINDOW_S of a heartbeat (T3.2)."""
    clock = FakeClock()
    p = Probe(clock, [(3, "loop"), (24, "embed"), (2, "rerank"), (30, "loop"), (1, "composition")])
    h = make_app(p, clock=clock)
    beats = [0.0]
    async with lifespan(h.app):
        run_id, s = await begin(h)
        for t in (10, 20, 70):
            await clock.advance(t - clock.t)
            await alive(h, run_id)
            beats.append(clock.t)
        await clock.advance(30)
        assert [x for x, _ in p.passed] == [3, 27, 29, 70, 71]
        for at, _ in p.passed:
            last = max(b for b in beats if b <= at)
            assert at - last < WINDOW
        assert [k for k, _ in kinds(s)] == ["paused", "resumed", "run_ended"]


async def test_record_usage_runs_after_the_gate(monkeypatch):
    """A loop call's paid_call is emitted only after the gate opened (the call happens after the check)."""
    clock = FakeClock()

    async def script(ctx, deps):
        await ctx.emit("run_started", run_started_data(ctx))
        await clock.sleep(30)
        await loop_call(ctx)
        await ctx.emit("run_ended", ended_data(ctx, state="no_sources", answer_end="none")
                       | {"no_sources_reason": "nothing_found", "note": "n"})

    h = make_app(script, clock=clock)
    async with lifespan(h.app):
        run_id, s = await begin(h)
        await clock.advance(40)
        s.pump()
        assert [e["kind"] for e in s.events()] == ["run_started", "paused"]
        await alive(h, run_id)
        await clock.settle()
        s.pump()
        assert [e["kind"] for e in s.events()] == ["run_started", "paused", "resumed", "paid_call", "run_ended"]
