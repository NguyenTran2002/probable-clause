"""Every end of research and the composition (contract v2.0 §4.G.6, §6; T1.10, T1.11, T3.2, T3.3, T3.5): each run is
checked whole by check_stream (schema, order rules, citations, totals), and here for its end state."""

import pytest

from api import settings
from api.loop.streamer import FakeTurn, StreamFailed, raw_usage
from tests.loop.support import (FakeCtx, cite_block, composition, loop_usage, run_loop, skip_update, stop_on, tu,
                                turn)

pytestmark = pytest.mark.anyio

NOTE_OOS = "This question is about landlord-tenant law, which the corpus does not cover."
NOTE_NONE = "Claude found no passages in the corpus that bear on this question."


def read_and_search():
    return turn(tu("search_exact", any_of=['"telephone booth"'], filters={"cases": ["katz"]}, max_results=2),
                tu("read_passages", target="katz-1-p6"), usage=loop_usage(1, first=True))


def keep(*ids, usage=None):
    return turn(tu("keep_passages", keep=[{"id": i, "reason": f"Majority passage {i}."} for i in ids]),
                usage=usage or loop_usage(2))


def submit(**kw):
    inp = {"out_of_scope": False}
    inp.update(kw)
    return turn(tu("submit_answer", **inp), usage=loop_usage(3))


def answer(world, docs=("katz-1-p6",), **kw):
    return composition(cite_block("The Court said the Amendment protects people. ", world.corpus, list(docs),
                                  "katz-1-p6", 4, 4), **kw)


def err(kind, **kw):
    return StreamFailed(kind, None, kind, **kw)


async def test_out_of_scope_reply(world):
    ctx, fakes = await run_loop(world, [turn(tu("submit_answer", out_of_scope=True, note=NOTE_OOS),
                                             usage=loop_usage(1, first=True))])
    end = ctx.ended()
    assert (end["state"], end["no_sources_reason"], end["note"], end["answer_end"]) == \
        ("no_sources", "out_of_scope", NOTE_OOS, "none")
    assert "composition_started" not in ctx.kinds() and "update_started" not in ctx.kinds()
    assert ctx.of("update_band")[0]["outcome"] == "not_run"
    assert fakes["anthropic"].requests_for("update") == []


async def test_nothing_found_reply(world):
    ctx, fakes = await run_loop(world, [read_and_search(), submit(note=NOTE_NONE)], update=[skip_update()])
    end = ctx.ended()
    assert (end["state"], end["no_sources_reason"], end["note"]) == ("no_sources", "nothing_found", NOTE_NONE)
    assert "composition_started" not in ctx.kinds()
    assert ctx.of("update_started") == [{"kept": []}]


async def test_step_limit_composes_from_what_was_kept(world):
    targets = [f"katz-1-p{i}" for i in range(2, 14)]
    script = [turn(tu("read_passages", target=t), usage=loop_usage(i, first=i == 0)) for i, t in enumerate(targets)]
    script[1] = turn(tu("read_passages", target=targets[1]), tu("keep_passages", keep=[{"id": "katz-1-p2", "reason": "r"}]),
                     usage=loop_usage(1))
    ctx, _ = await run_loop(world, script, comp=[composition(cite_block("Text. ", world.corpus, ["katz-1-p2"],
                                                                         "katz-1-p2", 0, 0))])
    end = ctx.ended()
    assert end["state"] == "step_limit" and end["stop_kind"] == "step_limit" and end["answer_end"] == "complete"
    assert end["rounds"] == settings.MAX_ROUNDS.value == len(ctx.of("round_started"))
    assert ctx.of("update_band")[0]["outcome"] == "not_run" and "update_started" not in ctx.kinds()


async def test_step_limit_with_nothing_kept_composes_nothing(world):
    script = [turn(tu("read_passages", target=f"katz-1-p{i}"), usage=loop_usage(i, first=i == 2)) for i in range(2, 14)]
    ctx, _ = await run_loop(world, script)
    end = ctx.ended()
    assert end["state"] == "step_limit" and end["answer_end"] == "none" and end["answer_chars"] == 0
    assert "composition_started" not in ctx.kinds()


async def test_token_ceiling_input_stops_before_the_call(world, monkeypatch):
    monkeypatch.setattr("api.loop.run.LOOP_INPUT_BUDGET", 370_000)
    huge = raw_usage(40, w5=2_000, read=360_000, output=500)      # 362,040 used after call 2: call 3 would cross 370,000
    ctx, fakes = await run_loop(world, [read_and_search(), keep("katz-1-p6", usage=huge)], comp=[answer(world)])
    end = ctx.ended()
    assert end["state"] == "token_ceiling" and end["stop_kind"] == "token_ceiling_input" and end["answer_end"] == "complete"
    assert end["rounds"] == 2                     # checked before a round: no round_started for the call not made
    assert len(fakes["anthropic"].requests) == 3  # two loop calls and the composition


async def test_token_ceiling_output_at_max_tokens(world):
    cut = FakeTurn(content=[{"type": "thinking", "thinking": "", "signature": "s"},
                            tu("search_exact", any_of=["booth"])], stop_reason="max_tokens")
    ctx, fakes = await run_loop(world, [read_and_search(), keep("katz-1-p6"), cut], comp=[answer(world)])
    end = ctx.ended()
    assert end["state"] == "token_ceiling" and end["stop_kind"] == "token_ceiling_output"
    assert len(ctx.of("tool_call")) == 3          # the cut call's tool use never runs
    assert fakes["anthropic"].requests[2]["max_tokens"] == settings.LOOP_OUTPUT_BUDGET.value - 400 - 500
    assert sum(p["usage"]["output_tokens"] for p in ctx.of("paid_call") if p["purpose"] == "loop") == \
        settings.LOOP_OUTPUT_BUDGET.value


async def test_token_ceiling_output_when_budget_spent(world):
    spent = raw_usage(40, w5=2_000, read=13_000, output=settings.LOOP_OUTPUT_BUDGET.value - 400)
    ctx, _ = await run_loop(world, [read_and_search(), keep("katz-1-p6", usage=spent)], comp=[answer(world)])
    assert ctx.ended()["stop_kind"] == "token_ceiling_output" and ctx.ended()["rounds"] == 2


async def test_time_limit_before_a_round(world):
    left = iter([600.0, 300.0, 0.0])
    ctx = FakeCtx(seconds_left=lambda: next(left, 0.0))
    ctx, _ = await run_loop(world, [read_and_search(), keep("katz-1-p6")], comp=[answer(world)], ctx=ctx)
    end = ctx.ended()
    assert end["state"] == "time_limit" and end["stop_kind"] == "time_limit" and end["answer_end"] == "complete"
    assert end["rounds"] == 2


async def test_deadline_from_the_gate_mid_tool_composes(world):
    """RunStopped("deadline") from a Voyage gate inside a search: the tool's result is an empty error (nothing went
    to Claude), the round's other calls do not run, and the answer is composed from what was kept (T3.5)."""
    script = [read_and_search(), keep("katz-1-p6"),
              turn(tu("search_meaning", query="listening devices on a booth"), tu("keep_passages", keep=[
                  {"id": "katz-1-n9", "reason": "never applied"}]))]
    ctx, _ = await run_loop(world, script, comp=[answer(world)], ctx=FakeCtx(stop=stop_on("embed", "deadline")))
    end = ctx.ended()
    assert end["state"] == "time_limit" and end["answer_end"] == "complete"
    stopped = ctx.results("search_meaning")[-1]
    assert stopped["is_error"] and stopped["content"] == ""
    assert [d["name"] for d in ctx.of("tool_call")].count("keep_passages") == 1


async def test_deadline_with_nothing_kept(world):
    ctx, _ = await run_loop(world, [read_and_search()], ctx=FakeCtx(stop=stop_on("loop", "deadline", at=2)))
    end = ctx.ended()
    assert end["state"] == "time_limit" and end["answer_end"] == "none"


async def test_a_deadline_at_the_gate_then_a_composition_leaves_no_gap_in_call_numbers(world):
    """The call stopped at its gate takes no number (§4.G.4: numbers come from the one counter when a call is sent)."""
    ctx, _ = await run_loop(world, [read_and_search(), keep("katz-1-p6")], comp=[answer(world)],
                            ctx=FakeCtx(stop=stop_on("loop", "deadline", at=3)))
    assert ctx.ended()["state"] == "time_limit" and ctx.of("composition_started")[0]["call_no"] == 3


async def test_abandoned_at_the_loop_gate(world):
    ctx, fakes = await run_loop(world, [read_and_search(), keep("katz-1-p6")],
                                ctx=FakeCtx(stop=stop_on("loop", "abandoned", at=3)))
    end = ctx.ended()
    assert end["state"] == "abandoned" and end["answer_end"] == "none" and end["rounds"] == 3
    assert "composition_started" not in ctx.kinds()
    assert ctx.of("update_band")[0]["outcome"] == "not_run"
    # no request fragment for the call that was never sent
    assert not [d for d in ctx.of("api_fragment") if d["call_no"] == 3]


async def test_abandoned_at_the_composition_gate(world):
    ctx, _ = await run_loop(world, [read_and_search(), keep("katz-1-p6"), submit()], update=[skip_update()],
                            ctx=FakeCtx(stop=stop_on("composition", "abandoned")))
    assert ctx.ended()["state"] == "abandoned" and "composition_started" not in ctx.kinds()
    assert ctx.of("update_band")[0]["outcome"] == "skipped"          # the update step ran its course


@pytest.mark.parametrize("kind,stop_kind", [("spend_limit", "console_spend_limit"), ("spend_cap", "tier_spend_cap")])
async def test_spend_limits_end_the_run_without_retry(world, kind, stop_kind):
    ctx, fakes = await run_loop(world, [read_and_search(), keep("katz-1-p6"), err(kind)])
    end = ctx.ended()
    assert end["state"] == "spend_limit" and end["stop_kind"] == stop_kind and end["failure_reason"] is None
    assert end["stop_kinds"] == [stop_kind]
    failed = [p for p in ctx.of("paid_call") if p["call_no"] == 3]
    assert [(p["attempt"], p["outcome"], p["error_kind"]) for p in failed] == [(1, "failed", kind)]
    assert "composition_started" not in ctx.kinds()


async def test_spend_limit_during_composition(world):
    ctx, _ = await run_loop(world, [read_and_search(), keep("katz-1-p6"), submit()], update=[skip_update()],
                            comp=[err("spend_limit")])
    assert ctx.ended()["state"] == "spend_limit" and ctx.ended()["stop_kind"] == "console_spend_limit"
    assert ctx.ended()["stop_kinds"] == ["console_spend_limit"]


async def test_refusal_in_the_loop_is_billed_and_ends_the_run(world):
    refused = FakeTurn(content=[], stop_reason="refusal", usage=raw_usage(50, w1=12_000, output=30))
    ctx, _ = await run_loop(world, [refused])
    end = ctx.ended()
    assert end["state"] == "refusal" and end["failure_reason"] == "refusal" and end["answer_end"] == "none"
    p = ctx.of("paid_call")[0]
    assert (p["outcome"], p["error_kind"], p["estimated"]) == ("failed", "refusal", False) and p["usage"]["output_tokens"] == 30


async def test_error_after_retries_composes_from_kept(world, no_real_waits):
    over = [err("overloaded"), err("overloaded"), err("overloaded")]
    ctx, _ = await run_loop(world, [read_and_search(), keep("katz-1-p6"), *over], comp=[answer(world)])
    end = ctx.ended()
    assert end["state"] == "error_stopped" and end["failure_reason"] == "overloaded" and end["answer_end"] == "complete"
    attempts = [(p["attempt"], p["outcome"], p["usage"], p["estimated"]) for p in ctx.of("paid_call") if p.get("call_no") == 3]
    assert attempts == [(1, "retrying", None, True), (2, "retrying", None, True), (3, "failed", None, True)]
    assert no_real_waits == [2.0, 8.0]
    # each failed attempt is priced from our input estimate at the uncached price (T3.3)
    costs = [p["cost_usd"] for p in ctx.of("paid_call") if p.get("call_no") == 3]
    assert all(c > 0 for c in costs)


async def test_error_after_retries_with_nothing_kept_fails(world):
    ctx, _ = await run_loop(world, [read_and_search(), err("server_error"), err("server_error"), err("server_error")])
    end = ctx.ended()
    assert end["state"] == "failed" and end["failure_reason"] == "server_error" and end["answer_end"] == "none"


async def test_our_fault_ends_the_run_with_no_further_calls(world):
    ctx, fakes = await run_loop(world, [read_and_search(), keep("katz-1-p6"), err("bad_request")])
    assert ctx.ended()["state"] == "failed" and ctx.ended()["failure_reason"] == "bad_request"
    assert len(fakes["anthropic"].requests) == 3


async def test_our_deadline_is_never_retried(world):
    ctx, fakes = await run_loop(world, [read_and_search(), keep("katz-1-p6"), err("deadline")], comp=[answer(world)])
    end = ctx.ended()
    assert end["state"] == "error_stopped" and end["failure_reason"] == "deadline"
    assert [p["outcome"] for p in ctx.of("paid_call") if p.get("call_no") == 3] == ["failed"]


async def test_loop_retry_recovers(world, no_real_waits):
    ctx, _ = await run_loop(world, [read_and_search(), err("rate_limited", retry_after_s=3.0), keep("katz-1-p6"),
                                    submit()], update=[skip_update()], comp=[answer(world)])
    assert ctx.ended()["state"] == "answered"
    assert [p["outcome"] for p in ctx.of("paid_call") if p.get("call_no") == 2] == ["retrying", "ok"]
    assert no_real_waits == [3.0]                 # retry-after wins over our wait


async def test_failed_attempt_that_reported_usage_is_priced_from_it(world):
    partial = raw_usage(40, w5=1_000, read=12_500, output=20)
    ctx, _ = await run_loop(world, [read_and_search(), err("stream_broken", raw_usage=partial, started=True),
                                    keep("katz-1-p6"), submit()], update=[skip_update()], comp=[answer(world)])
    p = next(p for p in ctx.of("paid_call") if p.get("call_no") == 2)
    assert p["outcome"] == "retrying" and p["usage"] is None and p["estimated"] is True
    assert p["estimated_usage"] == {"input_tokens": 40, "cache_creation_input_tokens": 1_000,
                                    "cache_read_input_tokens": 12_500, "output_tokens": 20}


async def test_composition_incomplete_after_a_block(world):
    docs = ["katz-1-p6"]
    broken = composition(cite_block("First. ", world.corpus, docs, "katz-1-p6", 0, 0),
                         cite_block("Second. ", world.corpus, docs, "katz-1-p6", 1, 1), break_after=1)
    ctx, fakes = await run_loop(world, [read_and_search(), keep("katz-1-p6"), submit()], update=[skip_update()],
                                comp=[broken])
    end = ctx.ended()
    assert end["state"] == "answered" and end["answer_end"] == "incomplete" and end["failure_reason"] == "stream_broken"
    assert len(ctx.of("answer_block")) == 1 and len(ctx.of("checks")) == 1
    comp = [p for p in ctx.of("paid_call") if p["purpose"] == "composition"]
    assert [(p["attempt"], p["outcome"]) for p in comp] == [(1, "failed")]     # never retried after a block


async def test_composition_failed_before_first_block_is_retried_then_fails(world, no_real_waits):
    ctx, _ = await run_loop(world, [read_and_search(), keep("katz-1-p6"), submit()], update=[skip_update()],
                            comp=[err("server_error"), err("server_error"), err("server_error")])
    end = ctx.ended()
    assert end["state"] == "failed" and end["failure_reason"] == "server_error" and end["answer_end"] == "none"
    assert ctx.of("checks") == [] and ctx.of("answer_block") == []
    assert len(ctx.of("composition_started")) == 1


async def test_composition_retry_recovers(world):
    ctx, _ = await run_loop(world, [read_and_search(), keep("katz-1-p6"), submit()], update=[skip_update()],
                            comp=[err("overloaded"), answer(world)])
    assert ctx.ended()["state"] == "answered"
    assert [p["outcome"] for p in ctx.of("paid_call") if p["purpose"] == "composition"] == ["retrying", "ok"]


async def test_composition_cut_off(world):
    ctx, _ = await run_loop(world, [read_and_search(), keep("katz-1-p6"), submit()], update=[skip_update()],
                            comp=[answer(world, stop_reason="max_tokens", usage=raw_usage(9_000, output=16_000))])
    end = ctx.ended()
    assert (end["state"], end["stop_kind"], end["answer_end"]) == ("answered", "composition_max_tokens", "cut_off")


async def test_composition_refusal_before_any_block(world):
    refused = FakeTurn(content=[], stop_reason="refusal", usage=raw_usage(9_000, output=10))
    ctx, _ = await run_loop(world, [read_and_search(), keep("katz-1-p6"), submit()], update=[skip_update()],
                            comp=[refused])
    assert ctx.ended()["state"] == "refusal" and ctx.ended()["answer_end"] == "none"


async def test_composition_refusal_after_a_block_is_incomplete(world):
    refused = composition(cite_block("First. ", world.corpus, ["katz-1-p6"], "katz-1-p6", 0, 0), stop_reason="refusal")
    ctx, _ = await run_loop(world, [read_and_search(), keep("katz-1-p6"), submit()], update=[skip_update()],
                            comp=[refused])
    end = ctx.ended()
    assert (end["state"], end["answer_end"], end["failure_reason"]) == ("answered", "incomplete", "refusal")


async def test_scope_note_goes_to_composition_and_run_ended(world):
    scope = "Part of this question turns on state law, which the corpus does not cover."
    ctx, fakes = await run_loop(world, [read_and_search(), keep("katz-1-p6"), submit(note=scope)],
                                update=[skip_update()], comp=[answer(world)])
    assert ctx.ended()["scope_note"] == scope and ctx.ended()["note"] is None
    ask = fakes["anthropic"].requests_for("composition")[0]["messages"][0]["content"][-1]["text"]
    assert scope in ask


async def test_text_only_response_continues_with_the_status_line(world):
    talk = turn(text="Thinking about where to look.", stop_reason="end_turn")
    ctx, fakes = await run_loop(world, [read_and_search(), talk, keep("katz-1-p6"), submit()], update=[skip_update()],
                                comp=[answer(world)])
    assert ctx.ended()["state"] == "answered"
    msg = fakes["anthropic"].requests[2]["messages"][-1]
    assert msg["role"] == "user" and [b["type"] for b in msg["content"]] == ["text"]
    assert msg["content"][0]["text"] == "Round 3 of 12 · 0 kept"


async def test_run_on_the_corpus_before_chatrie(world_before_chatrie):
    ctx = FakeCtx(corpus_label="before_chatrie")
    ctx, fakes = await run_loop(world_before_chatrie, [read_and_search(), keep("katz-1-p6"), submit()],
                                update=[skip_update()], comp=[answer(world_before_chatrie)], ctx=ctx)
    started = ctx.of("run_started")[0]
    assert started["corpus_label"] == "before_chatrie"
    assert started["coverage"]["latest_decision_in_corpus"] == "2018-06-22"
    assert "chatrie" not in fakes["anthropic"].requests[0]["system"][0]["text"].split("## The corpus catalog")[1]


async def test_a_label_mismatch_is_refused_before_any_event(world):
    from api.loop import execute_run
    from tests.loop.support import make_deps
    deps, _ = make_deps(world, [])
    ctx = FakeCtx(corpus_label="before_chatrie")
    with pytest.raises(ValueError):
        await execute_run(ctx, deps)
    assert ctx.events == []
