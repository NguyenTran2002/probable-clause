"""The run's token budget (T3.3, T3.4): the estimate before each loop call, every attempt counting toward the
ceiling, and a retry never crossing it."""

import json
import math

import pytest

from api import settings
from api.loop.run import _Run, chars_per_token
from api.loop.streamer import StreamFailed, raw_usage
from tests.loop.support import FakeCtx, cite_block, composition, loop_usage, make_deps, run_loop, tu, turn

pytestmark = pytest.mark.anyio


def read_keep():
    return turn(tu("read_passages", target="katz-1-p6"),
                tu("keep_passages", keep=[{"id": "katz-1-p6", "reason": "r"}]), usage=loop_usage(1, first=True))


def answer(world):
    return composition(cite_block("Text. ", world.corpus, ["katz-1-p6"], "katz-1-p6", 0, 0))


def test_ratio_errs_toward_more_tokens(world):
    r = chars_per_token(world.corpus)
    all_chars = sum(len(p.text) for p in world.corpus.passages.values())
    assert 2.0 < r < all_chars / world.corpus.manifest["core_tokens"]


def test_first_estimate_covers_the_fixed_prefix(world):
    deps, _ = make_deps(world, [])
    run = _Run(FakeCtx(), deps)
    run.messages.append({"role": "user", "content": [{"type": "text", "text": "x" * 4000}]})
    est = run.next_input_estimate()
    prefix = max(settings.FIXED_PREFIX_TOKENS_ESTIMATE.value,
                 math.ceil(len(run.system_text) / run.ratio) + math.ceil(len(json.dumps(run.tool_list)) / run.ratio))
    assert est >= prefix + 4000 / run.ratio and prefix >= settings.FIXED_PREFIX_TOKENS_ESTIMATE.value


def test_later_estimates_build_on_the_last_reported_usage(world):
    deps, _ = make_deps(world, [])
    run = _Run(FakeCtx(), deps)
    run.messages = [{"role": "user", "content": [{"type": "text", "text": "q"}]},
                    {"role": "assistant", "content": [{"type": "text", "text": "a"}]},
                    {"role": "user", "content": [{"type": "text", "text": "y" * 3000}]}]
    run.last_ok = (20_000, 700, 1)              # the request held one message; the reply and results came after
    assert run.next_input_estimate() == 20_000 + 700 + run.est_json(run.messages[2]["content"])


async def test_a_retry_that_would_cross_the_ceiling_is_not_made(world):
    partial = raw_usage(40, w5=1_000, read=360_000, output=10)       # the failed attempt reported its input
    ctx, fakes = await run_loop(world, [read_keep(), StreamFailed("overloaded", None, "x", raw_usage=partial,
                                                                  started=True), answer(world)])
    end = ctx.ended()
    assert end["state"] == "token_ceiling" and end["stop_kind"] == "token_ceiling_input"
    call2 = [p for p in ctx.of("paid_call") if p.get("call_no") == 2]
    assert [p["outcome"] for p in call2] == ["failed"]        # no retry followed it, so it never reads "retrying"
    assert len(fakes["anthropic"].requests) == 3       # loop call 1, the failed attempt, the composition


async def test_failed_attempts_count_their_estimate(world, monkeypatch):
    """With no usage reported, an attempt counts at its input estimate (T3.3), so retries reach the ceiling."""
    monkeypatch.setattr("api.loop.run.LOOP_INPUT_BUDGET", 20_000)
    ctx, fakes = await run_loop(world, [StreamFailed("overloaded", None, "x")])
    end = ctx.ended()
    assert end["state"] == "token_ceiling" and end["stop_kind"] == "token_ceiling_input" and end["answer_end"] == "none"
    p = ctx.of("paid_call")[0]
    assert p["usage"] is None and p["estimated"] and p["outcome"] == "failed" and p["cost_usd"] > 0
    model = settings.LOOP_MODEL.value
    from api.state.prices import PRICE_TABLE
    est_tokens = round(p["cost_usd"] * 1e6 / PRICE_TABLE["anthropic"]["models"][model]["input"])
    assert est_tokens >= settings.FIXED_PREFIX_TOKENS_ESTIMATE.value


async def test_output_budget_is_each_calls_max_tokens(world):
    script = [turn(tu("read_passages", target="katz-1-p6"), usage=raw_usage(50, w1=12_000, output=3_000)),
              turn(tu("keep_passages", keep=[{"id": "katz-1-p6", "reason": "r"}]),
                   usage=raw_usage(40, read=13_000, output=4_000)),
              turn(tu("search_exact", any_of=["booth"]), usage=raw_usage(40, read=14_000, output=1_000)),
              answer(world)]
    ctx, fakes = await run_loop(world, script)
    assert [r["max_tokens"] for r in fakes["anthropic"].requests[:3]] == [8_000, 5_000, 1_000]
    assert ctx.ended()["stop_kind"] == "token_ceiling_output"
