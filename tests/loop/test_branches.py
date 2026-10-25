"""execute_run's branches (contract v2.0 §4.G.1, §6): which branches run, the update step and the composition side by
side as two tasks (the update task first), both awaited before run_ended, the band placed as §6 says, the stream
interleaved and deterministic, and what an unexpected exception or a cancellation does. Every web page here is
synthetic, on example.test."""

import asyncio
import copy
import json
from types import SimpleNamespace

import pytest

from api.loop import execute_run
from api.loop.streamer import FakeTurn, StreamFailed, raw_usage
from tests.loop.support import (FakeCtx, check_stream, cite_block, composition, loop_usage, make_deps, run_loop,
                                skip_update, tu, turn, update_usage, web_reply)

pytestmark = pytest.mark.anyio

PAGE = ("Synthetic sample page text about a later thermal-imaging ruling, invented for this test and never to be "
        "stored anywhere. ") * 2
NOTE = "This question is about landlord-tenant law, which the corpus does not cover."


def research(*, keep=True):
    out = [turn(tu("search_exact", any_of=['"telephone booth"'], filters={"cases": ["katz"]}, max_results=2),
                tu("read_passages", target="katz-1-p6"), usage=loop_usage(1, first=True))]
    if keep:
        out.append(turn(tu("keep_passages", keep=[{"id": "katz-1-p6", "reason": "Majority: people, not places."},
                                                  {"id": "katz-1-n9", "reason": "Majority footnote."}]),
                        usage=loop_usage(2)))
    out.append(turn(tu("submit_answer", out_of_scope=False, **({} if keep else {"note": "Nothing bears on it."})),
                    usage=loop_usage(3)))
    return out


def update():
    return [turn(tu("search_web_updates", query="thermal imaging ruling", start_published_date="2026-06-30"),
                 usage=update_usage(0)),
            turn(tu("submit_update", update_findings=[{"statement": "A sample page reports a later ruling.",
                                                       "sources": ["web-1-1"]}]), usage=update_usage(1))]


def answer(world, **kw):
    docs = ["katz-1-p6", "katz-1-n9"]
    return [composition({"type": "text", "text": "## Short answer\n\n"},
                        cite_block("The Court said the Amendment protects people. ", world.corpus, docs,
                                   "katz-1-p6", 4, 4),
                        cite_block("A footnote adds a point. ", world.corpus, docs, "katz-1-n9", 0, 0),
                        {"type": "text", "text": "That is the holding."}, **kw)]


def exa():
    return [web_reply(("tr", "Thermal ruling", "2026-09-17", PAGE))]


def hang(started: asyncio.Event | None = None):
    """A scripted call that never answers, so a test holds it in flight."""
    async def wait(request):
        if started is not None:
            started.set()
        await asyncio.Event().wait()
    return wait


# ---------- which branches run (§4.G.1 item 3) ----------

async def test_out_of_scope_makes_no_update_call_and_the_band_is_not_run(world):
    script = [turn(tu("search_exact", any_of=["lease"], max_results=1), usage=loop_usage(1, first=True)),
              turn(tu("submit_answer", out_of_scope=True, note=NOTE), usage=loop_usage(2))]
    ctx, fakes = await run_loop(world, script)
    assert fakes["anthropic"].requests_for("update") == [] and fakes["exa"].calls == []
    assert ctx.kinds()[-2:] == ["update_band", "run_ended"]
    assert ctx.of("update_band")[0]["outcome"] == "not_run" and "update_started" not in ctx.kinds()
    assert ctx.ended()["no_sources_reason"] == "out_of_scope"


async def test_a_reply_that_never_searched_the_corpus_starts_no_update_step(world, monkeypatch):
    """The user's rule (P4.19), enforced by code apart from rule 2: here rule 2 is made to let a submit through after
    a search was undone, and the update step still does not start."""
    from api.loop.run import _Research
    real = _Research.submit

    def submit(self, inp, same_turn):
        out = real(self, inp, same_turn)
        self.run.corpus_searched = False
        return out

    monkeypatch.setattr(_Research, "submit", submit)
    ctx, fakes = await run_loop(world, research(), comp=answer(world))
    assert fakes["anthropic"].requests_for("update") == []
    band = ctx.of("update_band")[0]
    assert (band["outcome"], band["reason"]) == ("not_run", None)
    assert ctx.kinds().index("update_band") < ctx.kinds().index("composition_started")
    assert ctx.ended()["state"] == "answered"


@pytest.mark.parametrize("ctx_kw,reason", [({"update_check_available": False}, "no_credit"),
                                           ({"exa_unavailable": "key_refused"}, "key_refused")])
async def test_exa_unavailable_at_the_start_makes_no_update_call(world, ctx_kw, reason):
    ctx, fakes = await run_loop(world, research(), comp=answer(world), ctx=FakeCtx(**ctx_kw))
    assert fakes["anthropic"].requests_for("update") == [] and fakes["exa"].calls == []
    band = ctx.of("update_band")[0]
    assert (band["outcome"], band["reason"], band["searches"]) == ("unavailable", reason, [])
    kinds = ctx.kinds()
    assert kinds.index("update_band") < kinds.index("composition_started")       # at once (§6)
    assert ctx.ended()["state"] == "answered" and ctx.ended()["answer_end"] == "complete"


async def test_nothing_found_runs_the_update_step_and_no_composition(world):
    ctx, fakes = await run_loop(world, research(keep=False), update=update(), exa=exa(), page_texts=[PAGE[:60]])
    assert "composition_started" not in ctx.kinds() and fakes["anthropic"].requests_for("composition") == []
    assert ctx.of("update_started") == [{"kept": []}]
    assert ctx.of("update_band")[0]["outcome"] == "found"
    end = ctx.ended()
    assert (end["state"], end["no_sources_reason"], end["answer_end"]) == ("no_sources", "nothing_found", "none")
    assert ctx.kinds()[-3:] == ["update_ended", "update_band", "run_ended"]


async def test_a_research_limit_with_kept_passages_composes_and_runs_no_update_step(world, monkeypatch):
    monkeypatch.setattr("api.loop.run.MAX_ROUNDS", 2)
    ctx, fakes = await run_loop(world, research()[:2], comp=answer(world))
    assert fakes["anthropic"].requests_for("update") == []
    assert ctx.of("update_band")[0]["outcome"] == "not_run"
    kinds = ctx.kinds()
    assert kinds.index("update_band") < kinds.index("composition_started")
    end = ctx.ended()
    assert (end["state"], end["stop_kind"], end["answer_end"]) == ("step_limit", "step_limit", "complete")


@pytest.mark.parametrize("end_kind", ["abandoned", "spend_limit", "refusal", "failed", "error_stopped"])
async def test_research_ending_without_a_submit_starts_no_update_step(world, end_kind):
    from tests.loop.support import stop_on
    ctx_kw, script, comp = {}, research()[:2], []
    if end_kind == "abandoned":
        ctx_kw = {"stop": stop_on("loop", "abandoned", at=3)}
    elif end_kind == "spend_limit":
        script.append(StreamFailed("spend_limit", 400, "x"))
    elif end_kind == "refusal":
        script.append(FakeTurn(content=[], stop_reason="refusal", usage=raw_usage(10, output=5)))
    elif end_kind == "failed":
        script.append(StreamFailed("bad_request", 400, "x"))
    else:
        script.extend([StreamFailed("overloaded", 529, "x")] * 3)
        comp = answer(world)
    ctx, fakes = await run_loop(world, script, comp=comp, ctx=FakeCtx(**ctx_kw))
    assert fakes["anthropic"].requests_for("update") == [] and "update_started" not in ctx.kinds()
    assert ctx.of("update_band")[0]["outcome"] == "not_run"


# ---------- side by side (§4.G.1 item 4, §6) ----------

async def test_both_branches_interleave_in_one_valid_stream(world):
    ctx, fakes = await run_loop(world, research(), update=update(), comp=answer(world), exa=exa(),
                                page_texts=[PAGE[:60]])
    kinds = ctx.kinds()
    start, end = kinds.index("update_started"), kinds.index("update_ended")
    comp_events = [i for i, e in enumerate(ctx.events) if e["kind"] in ("composition_started", "answer_block")
                   or (e["kind"] == "paid_call" and e["data"]["purpose"] == "composition")]
    assert any(start < i < end for i in comp_events), "the composition ran while the update step did"
    update_events = [i for i, e in enumerate(ctx.events) if e["kind"] == "round_started" and e["data"]["step"] == "update"]
    assert any(i > kinds.index("composition_started") for i in update_events)
    # the update task was created first, so its first call has the lower number
    nos = {p["call_no"]: p["purpose"] for p in ctx.of("paid_call") if "call_no" in p}
    assert [nos[k] for k in sorted(nos)] == ["loop", "loop", "loop", "update", "composition", "update"]
    assert kinds[end + 1] == "update_band" and kinds[-1] == "run_ended"
    assert ctx.ended()["state"] == "answered" and ctx.of("update_band")[0]["outcome"] == "found"


def _deterministic(monkeypatch):
    """The fixtures' seams: no wall clock in durations, and F's checks inline instead of in a worker thread."""
    import api.loop.run as run_mod
    import api.search.meaning as meaning_mod
    import api.web_updates.exa as exa_mod
    still = SimpleNamespace(monotonic=lambda: 1000.0)
    for mod in (run_mod, meaning_mod, exa_mod):
        monkeypatch.setattr(mod, "time", still)

    async def run_sync(fn, *args):
        return fn(*args)

    monkeypatch.setattr(run_mod, "anyio", SimpleNamespace(to_thread=SimpleNamespace(run_sync=run_sync)))


async def test_the_stream_is_deterministic(world, monkeypatch):
    _deterministic(monkeypatch)
    scripts = {"script": research(), "update": update(), "comp": answer(world)}
    streams = []
    for _ in range(2):
        s = copy.deepcopy(scripts)
        ctx, _ = await run_loop(world, s["script"], update=s["update"], comp=s["comp"], exa=exa(),
                                page_texts=[PAGE[:60]])
        streams.append(json.dumps(ctx.events, sort_keys=True))
    assert streams[0] == streams[1]


async def test_stop_kinds_hold_every_step_s_stops_once_in_the_order_they_happened(world, monkeypatch):
    # the update step stops before its first round, then the composition is cut off
    monkeypatch.setattr("api.loop.run.UPDATE_INPUT_BUDGET", 1)
    ctx, _ = await run_loop(world, research(), comp=answer(world, stop_reason="max_tokens",
                                                             usage=raw_usage(9_000, output=16_000)))
    end = ctx.ended()
    assert end["stop_kinds"] == ["update_token_ceiling_input", "composition_max_tokens"]
    assert end["stop_kind"] == "composition_max_tokens" and end["state"] == "answered"
    # a spend limit met by both branches is listed once; the run's own stop is the composition's
    monkeypatch.undo()
    ctx, _ = await run_loop(world, research(), update=[StreamFailed("spend_limit", 400, "x")],
                            comp=[StreamFailed("spend_limit", 400, "x")])
    end = ctx.ended()
    assert end["stop_kinds"] == ["console_spend_limit"] and end["state"] == "spend_limit"
    assert end["stop_kind"] == "console_spend_limit"


# ---------- unexpected exceptions and cancellation (§4.G.1 items 5 to 7) ----------

async def test_an_unexpected_exception_in_the_composition_cancels_the_update_step_and_propagates(world):
    started = asyncio.Event()

    def boom(request):
        raise KeyError("a bug in our own code")

    ctx = FakeCtx()
    deps, fakes = make_deps(world, research(), update=[hang(started)], comp=[boom])
    with pytest.raises(KeyError):                 # the original exception, never an ExceptionGroup
        await execute_run(ctx, deps)
    assert started.is_set()
    kinds = ctx.kinds()
    assert "update_started" in kinds
    assert "update_ended" not in kinds and "update_band" not in kinds and "run_ended" not in kinds
    paid = {p["purpose"]: p for p in ctx.of("paid_call") if p["service"] == "anthropic" and p["purpose"] != "loop"}
    # the update attempt in flight is recorded before the cancellation goes on; the composition's that raised too
    assert (paid["update"]["outcome"], paid["update"]["estimated"]) == ("failed", True)
    assert paid["update"]["error_kind"] in ("stream_broken", "connection")
    assert (paid["composition"]["outcome"], paid["composition"]["error_kind"]) == ("failed", "internal")
    assert sorted(p["call_no"] for p in ctx.of("paid_call") if "call_no" in p) == [1, 2, 3, 4, 5]


async def test_an_unexpected_exception_in_research_propagates_before_any_branch(world):
    def boom(request):
        raise ZeroDivisionError("a bug")

    ctx = FakeCtx()
    deps, _ = make_deps(world, [research()[0], boom], update=[skip_update()], comp=answer(world))
    with pytest.raises(ZeroDivisionError):
        await execute_run(ctx, deps)
    kinds = ctx.kinds()
    assert "update_started" not in kinds and "update_band" not in kinds and "run_ended" not in kinds
    assert [(p["call_no"], p["outcome"], p["error_kind"]) for p in ctx.of("paid_call") if "call_no" in p][-1] == \
        (2, "failed", "internal")


async def test_a_cancelled_run_records_both_attempts_in_flight_and_emits_nothing_more(world):
    """H's shutdown cancels the run task: each branch's attempt in flight is recorded, priced from what it reported,
    then the cancellation goes on (§4.G.1 item 7)."""
    upd, comp = asyncio.Event(), asyncio.Event()
    ctx = FakeCtx()
    deps, fakes = make_deps(world, research(), update=[hang(upd)], comp=[hang(comp)])
    task = asyncio.create_task(execute_run(ctx, deps))
    await upd.wait()
    await comp.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    kinds = ctx.kinds()
    assert "run_ended" not in kinds and "update_ended" not in kinds and "update_band" not in kinds
    branch = {p["purpose"]: p for p in ctx.of("paid_call") if p["purpose"] in ("update", "composition")}
    assert set(branch) == {"update", "composition"}
    assert all(p["outcome"] == "failed" and p["estimated"] for p in branch.values())
    assert sorted(p["call_no"] for p in ctx.of("paid_call") if "call_no" in p) == [1, 2, 3, 4, 5]


async def test_a_cancelled_attempt_is_priced_from_what_it_streamed(world):
    """The fake leaves what it streamed on the CancelledError, as the real streamer does; the attempt is priced from
    the usage its stream reported, with output at least what it streamed."""
    reached = asyncio.Event()
    partial = raw_usage(9_000, output=1)
    blocks = [cite_block(f"Block {i} of a long answer that streams for a while. ", world.corpus,
                         ["katz-1-p6", "katz-1-n9"], "katz-1-p6", i, i) for i in range(3)]
    turn_ = composition(*blocks, partial_usage=partial)

    async def on_second_block_hold(request):
        return turn_

    ctx = FakeCtx()
    deps, fakes = make_deps(world, research(), update=[skip_update()], comp=[on_second_block_hold])
    real_emit = ctx.emit

    async def emit(kind, data):
        n = await real_emit(kind, data)
        if kind == "answer_block" and data["index"] == 1:
            reached.set()
            await asyncio.Event().wait()          # hold the composition inside its second block
        return n

    ctx.emit = emit
    task = asyncio.create_task(execute_run(ctx, deps))
    await reached.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    p = [x for x in ctx.paid if x["purpose"] == "composition"][-1]
    assert p["outcome"] == "failed" and p["error_kind"] == "stream_broken" and p["estimated"] is True
    assert p["_raw"]["input_tokens"] == 9_000 and p["_usage"].output_tokens > 1
    assert "run_ended" not in ctx.kinds()


async def test_the_update_task_is_awaited_before_run_ended(world):
    """The composition ends first; run_ended waits for the update step."""
    release = asyncio.Event()

    async def late(request):
        await release.wait()
        return skip_update()

    ctx = FakeCtx()
    deps, fakes = make_deps(world, research(), update=[late], comp=answer(world))
    task = asyncio.create_task(execute_run(ctx, deps))
    for _ in range(500):                          # F's checks run in a worker thread: wait for them in real time
        if "checks" in ctx.kinds():
            break
        await asyncio.sleep(0.01)
    for _ in range(10):
        await asyncio.sleep(0)
    assert "checks" in ctx.kinds() and "run_ended" not in ctx.kinds() and not task.done()
    release.set()
    await task
    kinds = ctx.kinds()
    assert kinds[-3:] == ["update_ended", "update_band", "run_ended"]
    check_stream(ctx.events, world.corpus)


async def test_an_exception_inside_on_block_is_priced_from_what_was_streamed(world, monkeypatch):
    """A bug in our own block handling (here the citation mapping) is re-raised, and the composition attempt is
    recorded from the usage its stream reported and the output it streamed, not from the input estimate alone."""
    import api.loop.run as run_mod
    real, seen = run_mod.map_citations, {"n": 0}

    def flaky(*a, **kw):
        seen["n"] += 1
        if seen["n"] == 2:
            raise KeyError("a bug in our own code")
        return real(*a, **kw)

    monkeypatch.setattr(run_mod, "map_citations", flaky)
    partial = raw_usage(9_000, output=1)
    comp = answer(world)[0]
    comp.partial_usage = partial
    ctx = FakeCtx()
    deps, _ = make_deps(world, research(), update=[skip_update()], comp=[comp])
    with pytest.raises(KeyError):
        await execute_run(ctx, deps)
    (p,) = [x for x in ctx.paid if x["purpose"] == "composition"]
    assert (p["outcome"], p["error_kind"], p["estimated"]) == ("failed", "internal", True)
    assert p["_raw"]["input_tokens"] == 9_000 and p["_usage"].input_tokens == 9_000
    assert p["_usage"].output_tokens > 1                    # thinking and two blocks streamed
    assert "run_ended" not in ctx.kinds()


async def test_any_exception_at_the_gate_still_records_the_earlier_failed_attempt(world):
    from api.loop.streamer import StreamFailed as SF

    def stop(service, purpose, n):
        return KeyError("a bug in the gate") if (purpose, n) == ("loop", 3) else None

    ctx = FakeCtx(stop=stop)
    deps, _ = make_deps(world, [research()[0], SF("overloaded", 529, "x")])
    with pytest.raises(KeyError):
        await execute_run(ctx, deps)
    assert [(p["call_no"], p["attempt"], p["outcome"], p["error_kind"]) for p in ctx.of("paid_call")
            if p.get("call_no") == 2] == [(2, 1, "failed", "overloaded")]


@pytest.mark.parametrize("kind", ["composition_started", "api_fragment"])
async def test_a_failure_before_the_request_is_handed_over_records_no_attempt(world, kind):
    """Only an attempt handed to the streamer is recorded: an event that fails before it (composition_started, or
    research's request fragments) leaves no paid_call for a call that was never sent."""
    ctx = FakeCtx()
    real_emit = ctx.emit

    async def emit(k, data):
        if k == kind and (kind == "composition_started" or data["role"] == "request"):
            raise KeyError(f"cannot emit {k}")
        return await real_emit(k, data)

    ctx.emit = emit
    script = research() if kind == "composition_started" else [research()[0], research()[1]]
    deps, fakes = make_deps(world, script, update=[skip_update()], comp=answer(world))
    with pytest.raises(KeyError):
        await execute_run(ctx, deps)
    purpose = "composition" if kind == "composition_started" else "loop"
    sent = fakes["anthropic"].requests_for("composition" if purpose == "composition" else "research")
    recorded = [p for p in ctx.of("paid_call") if p["purpose"] == purpose]
    assert len(recorded) == len(sent)                        # one record per request actually sent, no more
