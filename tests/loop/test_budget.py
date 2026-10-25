"""Each step's token budgets (T3.3, T3.4 amended by P4.18): the estimate before each call, every attempt counting
toward its own step's budgets, and a retry never crossing them."""

import json
import math

import pytest

from api import settings
from api.loop.run import _Research, _Run, chars_per_token
from api.loop.streamer import StreamFailed, raw_usage
from tests.loop.support import (FakeCtx, cite_block, composition, loop_usage, make_deps, run_loop, skip_update, tu,
                                turn)

pytestmark = pytest.mark.anyio


def read_keep():
    """Two rounds: shown, then kept (T1.7)."""
    return [turn(tu("read_passages", target="katz-1-p6"), usage=loop_usage(1, first=True)),
            turn(tu("keep_passages", keep=[{"id": "katz-1-p6", "reason": "r"}]), usage=loop_usage(2))]


def answer(world):
    return [composition(cite_block("Text. ", world.corpus, ["katz-1-p6"], "katz-1-p6", 0, 0))]


def research_of(world) -> tuple[_Run, _Research]:
    deps, _ = make_deps(world, [])
    run = _Run(FakeCtx(), deps)
    return run, _Research(run)


def test_ratio_errs_toward_more_tokens(world):
    r = chars_per_token(world.corpus)
    all_chars = sum(len(p.text) for p in world.corpus.passages.values())
    assert 2.0 < r < all_chars / world.corpus.manifest["core_tokens"]


def test_the_first_estimate_is_the_prompt_tools_and_messages_with_no_floor(world):
    """P4.18: FIXED_PREFIX_TOKENS_ESTIMATE is gone; the first call's estimate is what it sends, at the corpus's ratio."""
    assert not hasattr(settings, "FIXED_PREFIX_TOKENS_ESTIMATE")
    run, research = research_of(world)
    run.messages.append({"role": "user", "content": [{"type": "text", "text": "x" * 4000}]})
    est = research.next_input_estimate()
    assert est == (math.ceil(len(run.system_text) / run.ratio) + run.est_json(run.tool_list)
                   + run.est_json(run.messages[0]["content"]))
    assert est > 4000 / run.ratio


def test_later_estimates_build_on_the_last_reported_usage(world):
    run, research = research_of(world)
    run.messages = [{"role": "user", "content": [{"type": "text", "text": "q"}]},
                    {"role": "assistant", "content": [{"type": "text", "text": "a"}]},
                    {"role": "user", "content": [{"type": "text", "text": "y" * 3000}]}]
    run.last_ok = (20_000, 700, 1)              # the request held one message; the reply and results came after
    assert research.next_input_estimate() == 20_000 + 700 + run.est_json(run.messages[2]["content"])


async def test_a_retry_that_would_cross_the_ceiling_is_not_made(world, monkeypatch):
    monkeypatch.setattr("api.loop.run.LOOP_INPUT_BUDGET", 370_000)
    partial = raw_usage(40, w5=1_000, read=360_000, output=10)       # the failed attempt reported its input
    ctx, fakes = await run_loop(world, [*read_keep(), StreamFailed("overloaded", None, "x", raw_usage=partial,
                                                                  started=True)], comp=answer(world))
    end = ctx.ended()
    assert end["state"] == "token_ceiling" and end["stop_kind"] == "token_ceiling_input"
    call3 = [p for p in ctx.of("paid_call") if p.get("call_no") == 3]
    assert [p["outcome"] for p in call3] == ["failed"]        # no retry followed it, so it never reads "retrying"
    assert len(fakes["anthropic"].requests) == 4       # loop calls 1 and 2, the failed attempt, the composition


async def test_failed_attempts_count_their_estimate(world, monkeypatch):
    """With no usage reported, an attempt counts at its input estimate (T3.3), so retries reach the ceiling."""
    run, research = research_of(world)
    first = run.est(run.system_text) + run.est_json(run.tool_list)
    monkeypatch.setattr("api.loop.run.LOOP_INPUT_BUDGET", first + 5_000)   # room for one failed attempt only
    ctx, fakes = await run_loop(world, [StreamFailed("overloaded", None, "x")])
    end = ctx.ended()
    assert end["state"] == "token_ceiling" and end["stop_kind"] == "token_ceiling_input" and end["answer_end"] == "none"
    p = ctx.of("paid_call")[0]
    assert p["usage"] is None and p["estimated"] and p["outcome"] == "failed" and p["cost_usd"] > 0
    assert p["estimated_usage"]["input_tokens"] >= first
    model = settings.LOOP_MODEL.value
    from api.state.prices import PRICE_TABLE
    est_tokens = round(p["cost_usd"] * 1e6 / PRICE_TABLE["anthropic"]["models"][model]["input"])
    assert est_tokens == p["estimated_usage"]["input_tokens"]


async def test_output_budget_is_each_calls_max_tokens(world, monkeypatch):
    monkeypatch.setattr("api.loop.run.LOOP_OUTPUT_BUDGET", 8_000)
    script = [turn(tu("read_passages", target="katz-1-p6"), usage=raw_usage(50, w1=12_000, output=3_000)),
              turn(tu("keep_passages", keep=[{"id": "katz-1-p6", "reason": "r"}]),
                   usage=raw_usage(40, read=13_000, output=4_000)),
              turn(tu("search_exact", any_of=["booth"]), usage=raw_usage(40, read=14_000, output=1_000))]
    ctx, fakes = await run_loop(world, script, comp=answer(world))
    assert [r["max_tokens"] for r in fakes["anthropic"].requests[:3]] == [8_000, 5_000, 1_000]
    assert ctx.ended()["stop_kind"] == "token_ceiling_output"


async def test_each_step_counts_only_its_own_attempts(world, monkeypatch):
    """§4.G.4: every update attempt counts toward the update budgets, and only toward them; research's leave them
    whole, so the update step's first max_tokens is its whole output budget."""
    heavy = raw_usage(40, w5=2_000, read=13_000, output=settings.LOOP_OUTPUT_BUDGET.value - 1_000)
    script = [turn(tu("read_passages", target="katz-1-p6"), tu("search_exact", any_of=["booth"], max_results=1),
                   usage=loop_usage(1, first=True)),
              turn(tu("keep_passages", keep=[{"id": "katz-1-p6", "reason": "r"}]), usage=heavy),
              turn(tu("submit_answer", out_of_scope=False), usage=raw_usage(40, read=14_000, output=500))]
    ctx, fakes = await run_loop(world, script, update=[skip_update()], comp=answer(world))
    (u,) = fakes["anthropic"].requests_for("update")
    assert u["max_tokens"] == settings.UPDATE_OUTPUT_BUDGET.value
    assert fakes["anthropic"].requests_for("composition")[0]["max_tokens"] == settings.COMPOSITION_MAX_TOKENS.value
    assert ctx.ended()["state"] == "answered" and ctx.ended()["stop_kinds"] == []


def test_the_documented_worst_case_composition_input_fits(world):
    """P4.21's documented worst case only (never a gate): the composition's largest input by this estimator fits in
    WORST_CASE_COMPOSITION_INPUT (as tests/contract/test_composition_worst_case.py recomputes it)."""
    from api.loop import format as fmt
    from api.loop.run import sort_documents
    reason = "r" * int(settings.KEEP_REASON_MAX_CHARS.value)
    deps, _ = make_deps(world, [])
    run = _Run(FakeCtx(question="q" * int(settings.QUESTION_MAX_CHARS.value)), deps)
    size = {pid: run.est_json(fmt.document_block(p, reason)) for pid, p in world.corpus.passages.items()}
    largest = sorted(size, key=lambda pid: (-size[pid], pid))[:int(settings.KEEP_CAP.value)]
    documents = [fmt.document_block(world.corpus.passages[pid], reason) for pid in sort_documents(largest, world.corpus)]
    request = run.composition_request(documents, "n" * int(settings.NOTE_MAX_CHARS.value))
    est = run.est(request["system"]) + run.est(json.dumps(request["messages"], ensure_ascii=False))
    assert 0.95 * settings.WORST_CASE_COMPOSITION_INPUT.value < est <= settings.WORST_CASE_COMPOSITION_INPUT.value
