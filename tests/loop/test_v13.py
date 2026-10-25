"""The rulings of contract v1.3 and the review's fixes: the end pairings after a loop limit, a failed attempt's
output estimate, no `retrying` record without an attempt after it, a citation whose text disagrees, no empty text
block, and the SDK's other error classes."""

import logging
import math

import httpx2
import pytest

from api import settings
from api.loop.streamer import StreamFailed, raw_usage
from api.search.meaning import UNAVAILABLE_NOTE, MeaningResult
from api.types import RunStopped
from tests.loop.support import FakeCtx, cite_block, composition, loop_usage, run_loop, stop_on, tu, turn

pytestmark = pytest.mark.anyio

SKIP = "Not needed."


def read_keep(usage=None):
    """Two rounds: the passage is shown, then kept (a keep may name only what an earlier turn showed, T1.7)."""
    return [turn(tu("read_passages", target="katz-1-p6"), tu("search_exact", any_of=["booth"], max_results=1),
                 usage=loop_usage(1, first=True)),
            turn(tu("keep_passages", keep=[{"id": "katz-1-p6", "reason": "r"}]), usage=usage or loop_usage(2))]


def blocks(world, n):
    return [cite_block(f"Sentence {i} of the answer, citing the passage. ", world.corpus, ["katz-1-p6"], "katz-1-p6", i, i)
            for i in range(n)]


def cut_off(world):
    return composition(*blocks(world, 2), stop_reason="max_tokens", usage=raw_usage(9_000, output=12_000))


def broken(world):
    return composition(*blocks(world, 3), break_after=2)


def _clock(values):
    it = iter(values)
    return lambda: next(it, 0.0)


def limit_scripts(world):
    """Each loop limit and the error stop, with something kept, reached after one round."""
    huge = raw_usage(40, w5=2_000, read=360_000, output=500)
    spent = raw_usage(40, w5=2_000, read=13_000, output=settings.LOOP_OUTPUT_BUDGET.value)
    return {
        ("token_ceiling", "token_ceiling_input"): ([*read_keep(usage=huge)], {}),
        ("token_ceiling", "token_ceiling_output"): ([*read_keep(usage=spent)], {}),
        ("time_limit", "time_limit"): ([*read_keep()], {"seconds_left": _clock([600.0, 600.0])}),
        ("step_limit", "step_limit"): ([*read_keep()] + [turn(tu("read_passages", target=f"katz-1-p{i}"),
                                                             usage=loop_usage(i)) for i in range(2, 12)], {}),
        ("error_stopped", None): ([*read_keep()] + [StreamFailed("overloaded", 529, "x")] * 3, {}),
    }


KEYS = [("token_ceiling", "token_ceiling_input"), ("token_ceiling", "token_ceiling_output"),
        ("time_limit", "time_limit"), ("step_limit", "step_limit"), ("error_stopped", None)]


@pytest.mark.parametrize("key", KEYS)
async def test_a_loop_limit_then_a_cut_off_composition(world, key):
    script, ctx_kw = limit_scripts(world)[key]
    ctx, _ = await run_loop(world, script + [cut_off(world)], ctx=FakeCtx(**ctx_kw))
    end = ctx.ended()
    state, stop_kind = key
    assert end["state"] == state and end["answer_end"] == "cut_off"
    # v1.3: the three limits keep their own stop_kind; error_stopped's cut-off is the composition's
    assert end["stop_kind"] == (stop_kind or "composition_max_tokens")


@pytest.mark.parametrize("key", KEYS)
async def test_a_loop_limit_then_a_composition_that_breaks(world, key):
    script, ctx_kw = limit_scripts(world)[key]
    ctx, _ = await run_loop(world, script + [broken(world)], ctx=FakeCtx(**ctx_kw))
    end = ctx.ended()
    assert end["state"] == key[0] and end["answer_end"] == "incomplete" and end["failure_reason"] == "stream_broken"
    assert end["stop_kind"] == key[1]
    assert len(ctx.of("answer_block")) == 2 and len(ctx.of("checks")) == 1


async def test_a_composition_that_breaks_after_several_blocks_counts_what_it_streamed(world):
    partial = raw_usage(9_000, output=1)            # message_start's usage: output not yet known
    comp = composition(*blocks(world, 4), break_after=3, partial_usage=partial)
    ctx, fakes = await run_loop(world, [*read_keep(), turn(tu("submit_answer", out_of_scope=False,
                                                             update_skip_reason=SKIP)), comp])
    p = [x for x in ctx.paid if x["purpose"] == "composition"][-1]
    streamed = sum(len(b.get("text") or b.get("thinking") or "") for b in comp.content[:4])   # thinking + 3 texts
    ratio = __import__("api.loop.run", fromlist=["chars_per_token"]).chars_per_token(world.corpus)
    assert p["outcome"] == "failed" and p["estimated"] is True
    assert p["usage"]["output_tokens"] == math.ceil(streamed / ratio) > 1
    assert p["usage"]["input_tokens"] == 9_000
    assert p["_usage"].output_tokens == p["usage"]["output_tokens"]      # priced on it, as the event shows


async def test_a_loop_call_cut_by_its_deadline_counts_its_output(world):
    partial = raw_usage(40, w5=1_000, read=12_500, output=1)
    cut = StreamFailed("deadline", None, "deadline", raw_usage=partial, started=True, streamed_chars=40_000)
    ctx, fakes = await run_loop(world, [*read_keep(), cut, composition(*blocks(world, 1))])
    p = next(x for x in ctx.paid if x.get("call_no") == 3)
    ratio = __import__("api.loop.run", fromlist=["chars_per_token"]).chars_per_token(world.corpus)
    est = math.ceil(40_000 / ratio)
    assert p["outcome"] == "failed" and p["error_kind"] == "deadline" and p["usage"]["output_tokens"] == est
    # counted against the output ceiling: the output used is the first call's and the estimate
    loop_out = sum(x["_usage"].output_tokens for x in ctx.paid if x["purpose"] == "loop")
    assert loop_out == 400 + 500 + est
    assert ctx.ended()["state"] == "error_stopped" and ctx.ended()["failure_reason"] == "deadline"


async def test_a_reported_output_larger_than_the_estimate_stands(world):
    partial = raw_usage(40, read=12_500, output=5_000)
    cut = StreamFailed("deadline", None, "deadline", raw_usage=partial, started=True, streamed_chars=10)
    ctx, _ = await run_loop(world, [*read_keep(), cut, composition(*blocks(world, 1))])
    assert next(x for x in ctx.paid if x.get("call_no") == 3)["usage"]["output_tokens"] == 5_000


async def test_an_attempt_that_reported_nothing_but_streamed_is_estimated(world):
    cut = StreamFailed("stream_broken", None, "x", started=True, streamed_chars=2_000)
    ctx, _ = await run_loop(world, [*read_keep(), cut, turn(tu("submit_answer", out_of_scope=False,
                                                              update_skip_reason=SKIP)), composition(*blocks(world, 1))])
    p = next(x for x in ctx.paid if x.get("call_no") == 3)
    assert p["outcome"] == "retrying" and p["estimated"] and p["usage"]["output_tokens"] > 0
    assert p["usage"]["input_tokens"] >= settings.FIXED_PREFIX_TOKENS_ESTIMATE.value


async def test_no_retrying_record_without_an_attempt_after_it(world):
    """The gate stops the retry: the failed attempt is recorded `failed`, not `retrying` (T3.3)."""
    ctx, _ = await run_loop(world, [*read_keep(), StreamFailed("overloaded", 529, "x"), composition(*blocks(world, 1))],
                            ctx=FakeCtx(stop=stop_on("loop", "deadline", at=4)))
    call2 = [x for x in ctx.paid if x.get("call_no") == 3]
    assert [(x["attempt"], x["outcome"]) for x in call2] == [(1, "failed")]
    assert ctx.ended()["state"] == "time_limit"


async def test_a_composition_retry_stopped_at_the_gate(world):
    ctx, _ = await run_loop(world, [*read_keep(), turn(tu("submit_answer", out_of_scope=False, update_skip_reason=SKIP)),
                                    StreamFailed("overloaded", 529, "x")],
                            ctx=FakeCtx(stop=stop_on("composition", "abandoned", at=2)))
    comp = [x for x in ctx.paid if x["purpose"] == "composition"]
    assert [(x["attempt"], x["outcome"]) for x in comp] == [(1, "failed")]
    assert ctx.ended()["state"] == "abandoned"


async def test_a_retry_that_runs_is_recorded_retrying_before_it(world):
    ctx, _ = await run_loop(world, [*read_keep(), StreamFailed("overloaded", 529, "x"),
                                    turn(tu("submit_answer", out_of_scope=False, update_skip_reason=SKIP)),
                                    composition(*blocks(world, 1))])
    call2 = [x for x in ctx.paid if x.get("call_no") == 3]
    assert [(x["attempt"], x["outcome"]) for x in call2] == [(1, "retrying"), (2, "ok")]


async def test_a_citation_that_disagrees_is_not_attached_in_a_run(world, caplog):
    caplog.set_level(logging.ERROR)
    good = cite_block("Good. ", world.corpus, ["katz-1-p6"], "katz-1-p6", 0, 0)
    bad = cite_block("Bad. ", world.corpus, ["katz-1-p6"], "katz-1-p6", 1, 1)
    bad["citations"][0]["cited_text"] = "Words the passage does not have at these sentences."
    ctx, _ = await run_loop(world, [*read_keep(), turn(tu("submit_answer", out_of_scope=False, update_skip_reason=SKIP)),
                                    composition(good, bad)])
    b = ctx.of("answer_block")
    assert len(b[0]["citations"]) == 1 and b[1]["citations"] == []
    comp_no = ctx.of("composition_started")[0]["call_no"]
    assert not [d for d in ctx.of("api_fragment") if d["call_no"] == comp_no and d["path"] == "content[2]"]
    logs = "\n".join(r.getMessage() for r in caplog.records)
    assert "mapping fault" in logs and "1 disagreed" in logs and "Words the passage" not in logs


async def test_no_empty_text_block_is_sent(world, monkeypatch):
    async def unavailable(self, query, keep, ctx, voyage, **kw):
        return MeaningResult([], "unavailable", None)

    monkeypatch.setattr("api.search.meaning.MeaningIndex.search", unavailable)
    script = [turn(tu("search_meaning", query="x")), *read_keep(), turn(tu("search_exact", any_of=["booth"], max_results=1)),
              turn(tu("submit_answer", out_of_scope=False, update_skip_reason=SKIP)), composition(*blocks(world, 1))]
    ctx, fakes = await run_loop(world, script)
    sent = fakes["anthropic"].requests[1]["messages"][2]["content"][0]["content"][0]["text"]
    assert sent == UNAVAILABLE_NOTE
    for req in fakes["anthropic"].requests:
        for m in req["messages"]:
            for blk in m["content"]:
                for inner in blk.get("content", []) if isinstance(blk.get("content"), list) else []:
                    assert inner.get("text", "x").strip()


async def test_a_reply_with_no_message_is_unreadable(world):
    from api.loop.run import _Run
    from api.loop.streamer import SdkAnthropicStreamer
    from tests.loop.support import make_deps

    deps, _ = make_deps(world, [])
    run = _Run(FakeCtx(), deps)
    run.messages.append({"role": "user", "content": [{"type": "text", "text": "q"}]})

    async def not_json(request):
        return httpx2.Response(200, headers={"content-type": "application/json"}, content=b"{\"type\": \"message\"}")

    s = SdkAnthropicStreamer("test-key-not-real", http_client=httpx2.AsyncClient(transport=httpx2.MockTransport(not_json)))
    with pytest.raises(StreamFailed) as e:
        await s.stream(run.loop_request(10), 30.0, None)
    assert e.value.kind == "unreadable"


@pytest.mark.parametrize("make,kind", [
    (lambda req: __import__("anthropic").APIResponseValidationError(httpx2.Response(200, request=req), None), "unreadable"),
    (lambda req: __import__("anthropic").APIError("odd", req, body=None), "protocol"),
])
async def test_sdk_validation_and_other_api_errors(make, kind):
    from api.loop.streamer import SdkAnthropicStreamer
    s = SdkAnthropicStreamer("test-key-not-real")
    req = httpx2.Request("POST", "https://api.anthropic.com/v1/messages")

    class Manager:
        async def __aenter__(self):
            raise make(req)

        async def __aexit__(self, *a):
            return False

    s._client.messages.stream = lambda **kw: Manager()
    with pytest.raises(StreamFailed) as e:
        await s.stream({"model": "m", "max_tokens": 1, "messages": []}, 5.0, None)
    assert e.value.kind == kind


# ---------- v1.4 ----------

async def test_a_keep_of_a_passage_shown_in_the_same_turn_is_refused(world):
    """T1.7: Claude wrote the keep before it saw the text, whichever order the calls came in."""
    from api.loop.prompts import rejection
    script = [turn(tu("read_passages", target="katz-1-p9"), tu("keep_passages", keep=[{"id": "katz-1-p9", "reason": "guess"}]),
                   tu("search_exact", any_of=["booth"], max_results=1)),
              turn(tu("keep_passages", keep=[{"id": "katz-1-p8", "reason": "guess"}]), tu("read_passages", target="katz-1-p8")),
              turn(tu("keep_passages", keep=[{"id": "katz-1-p9", "reason": "seen in an earlier turn"}])),
              turn(tu("submit_answer", out_of_scope=False, update_skip_reason=SKIP)),
              composition(cite_block("Text. ", world.corpus, ["katz-1-p9"], "katz-1-p9", 0, 0))]
    ctx, _ = await run_loop(world, script)
    k1, k2, k3 = ctx.results("keep_passages")
    assert k1["is_error"] and k1["refused"] == [{"id": "katz-1-p9", "why": rejection("keep", "unseen_id", id="katz-1-p9")}]
    assert k2["is_error"] and k2["refused"][0]["id"] == "katz-1-p8"
    assert k3["kept"] == [{"id": "katz-1-p9", "reason": "seen in an earlier turn", "replaced": False}]
    assert ctx.of("composition_started")[0]["documents"] == ["katz-1-p9"]


async def test_stop_kinds_on_every_end(world):
    spent = raw_usage(40, w5=2_000, read=13_000, output=settings.LOOP_OUTPUT_BUDGET.value)
    # a loop limit, then a composition that fails: the limit is still recorded
    ctx, _ = await run_loop(world, [*read_keep(usage=spent), *[StreamFailed("overloaded", 529, "x")] * 3])
    assert (ctx.ended()["state"], ctx.ended()["stop_kind"], ctx.ended()["stop_kinds"]) == \
        ("failed", None, ["token_ceiling_output"])
    # a loop limit, then a cut-off composition: both, in order
    script, kw = limit_scripts(world)[("step_limit", "step_limit")]
    ctx, _ = await run_loop(world, script + [cut_off(world)], ctx=FakeCtx(**kw))
    assert ctx.ended()["stop_kind"] == "step_limit"
    assert ctx.ended()["stop_kinds"] == ["step_limit", "composition_max_tokens"]
    # max_tokens with only thinking: failed (unreadable), the cut-off still listed
    thinking_only = composition(stop_reason="max_tokens", usage=raw_usage(9_000, output=12_000))
    ctx, _ = await run_loop(world, [*read_keep(), turn(tu("submit_answer", out_of_scope=False, update_skip_reason=SKIP)),
                                    thinking_only])
    end = ctx.ended()
    assert (end["state"], end["failure_reason"], end["stop_kind"], end["stop_kinds"]) == \
        ("failed", "unreadable", None, ["composition_max_tokens"])
    # a spend limit
    ctx, _ = await run_loop(world, [*read_keep(), StreamFailed("spend_cap", 429, "x")])
    assert ctx.ended()["stop_kinds"] == ["tier_spend_cap"] == [ctx.ended()["stop_kind"]]
    # no stop at all
    ctx, _ = await run_loop(world, [*read_keep(), turn(tu("submit_answer", out_of_scope=False, update_skip_reason=SKIP)),
                                    composition(*blocks(world, 1))])
    assert ctx.ended()["stop_kinds"] == [] and ctx.ended()["stop_kind"] is None
