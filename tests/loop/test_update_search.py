"""The update search in the loop (T2.1 to T2.5): counting, search numbers, repeats, D's two formatters, the schema
check, and the band's outcome worked out by code (§6)."""

import pytest

from api.loop import run as run_mod
from api.loop.run import band_outcome
from api.loop.prompts import rejection
from api.state.store import MemoryStore
from api.web_updates.exa import FakeExaTransport
from tests.loop.support import cite_block, composition, run_loop, tu, turn, web_reply

pytestmark = pytest.mark.anyio

PAGE_A = "Synthetic sample page A text about a later ruling, written for this test only, never to be stored. " * 2
PAGE_B = "Synthetic sample page B text about a pending petition, written for this test only, never stored. " * 2


def research():
    return [turn(tu("search_exact", any_of=["booth"], filters={"cases": ["katz"]}, max_results=1),
                 tu("read_passages", target="katz-1-p6")),
            turn(tu("keep_passages", keep=[{"id": "katz-1-p6", "reason": "r"}]))]


def web(**inp):
    inp.setdefault("query", "phone surveillance ruling")
    return turn(tu("search_web_updates", **inp))


def end(world, **submit):
    inp = {"out_of_scope": False}
    inp.update(submit)
    return [turn(tu("submit_answer", **inp)),
            composition(cite_block("Text. ", world.corpus, ["katz-1-p6"], "katz-1-p6", 0, 0))]


async def test_every_way_a_search_ends(world):
    exa = [FakeExaTransport.failure("bad_request"), FakeExaTransport.failure("timeout"),
           web_reply(("a", "Page A", "2026-08-11T00:00:00Z", PAGE_A), ("b", "Page B", None, PAGE_B))]
    script = [*research(),
              web(start_published_date="2026-6-30"),                 # refused by our code: not counted
              web(start_published_date="2026-06-30"),                # refused by Exa: counted
              web(type="lite"),                                      # failed: counted
              web(num_results=4),                                    # ok
              web(),                                                 # a fourth: refused by our code
              *end(world, update_findings=[{"statement": "A sample page reports a ruling.", "sources": ["web-3-1"]}])]
    ctx, fakes = await run_loop(world, script, exa=exa, page_texts=[PAGE_A[:60], PAGE_B[:60]])
    res = ctx.results("search_web_updates")
    assert [r["web_status"] for r in res] == ["refused_by_us", "refused_by_exa", "failed", "ok", "refused_by_us"]
    assert [r.get("search_no") for r in res] == [None, 1, 2, 3, None]
    assert [r["is_error"] for r in res] == [True, True, True, False, True]
    assert res[4]["content"] == rejection("update_search", "fourth_search")
    ok = res[3]
    assert [p["id"] for p in ok["web"]] == ["web-3-1", "web-3-2"] and ok["web"][1]["published"] is None
    assert "[page text: " in ok["content"] and PAGE_A[:60] not in ok["content"]
    band = ctx.of("update_band")[0]
    assert [s["search_no"] for s in band["searches"]] == [1, 2, 3]
    assert [s["status"] for s in band["searches"]] == ["refused_by_exa", "failed", "ok"]
    assert band["searches"][2]["returned"] == 2 and band["searches"][2]["undated"] == 1
    assert band["searches"][1]["params"]["type"] == "lite" and band["searches"][0]["fixed"]["highlights"] is False
    assert band["outcome"] == "found"
    exa_paid = [p for p in ctx.of("paid_call") if p["service"] == "exa"]
    assert [(p["outcome"], p["cost_usd"]) for p in exa_paid] == [("failed", 0.0), ("failed", 0.004), ("ok", 0.007)]
    assert len(fakes["exa"].calls) == 3
    # the status line counts the searches that counted (T2.1)
    assert ctx.of("round_started")[-1]["status_line"].endswith("update searches 3 of 3")


async def test_repeats_listed_by_their_first_id(world):
    exa = [web_reply(("a", "Page A", "2026-08-11", PAGE_A)),
           web_reply(("a", "Page A", "2026-08-11", PAGE_A), ("b", "Page B", "2026-09-01", PAGE_B))]
    script = [*research(), web(), web(), *end(world, update_findings=[])]
    ctx, fakes = await run_loop(world, script, exa=exa, page_texts=[PAGE_A[:60], PAGE_B[:60]])
    second = ctx.results("search_web_updates")[1]
    assert second["web_repeats"] == ["web-1-1"] and [p["id"] for p in second["web"]] == ["web-2-1"]
    band = ctx.of("update_band")[0]
    assert band["searches"][1]["returned"] == 2
    assert [p["id"] for p in band["pages"]] == ["web-1-1", "web-2-1"]
    assert band["outcome"] == "nothing_relevant"
    # Claude got the page text, inside the markers
    sent = fakes["anthropic"].requests[3]["messages"][-1]["content"][0]["content"][0]["text"]
    assert PAGE_A[:60] in sent and "<web_page_text" in sent


@pytest.mark.parametrize("failure,reason", [("no_credit", "no_credit"), ("key_refused", "key_refused")])
async def test_unavailable_mid_run(world, failure, reason):
    store = MemoryStore()
    script = [*research(), web(), web(), *end(world)]
    ctx, fakes = await run_loop(world, script, exa=[FakeExaTransport.failure(failure)], store=store)
    res = ctx.results("search_web_updates")
    assert [r["web_status"] for r in res] == ["unavailable", "unavailable"]
    assert len(fakes["exa"].calls) == 1               # the second never reaches Exa
    assert ctx.flags.exa_unavailable == reason
    assert not [p for p in ctx.of("paid_call") if p["service"] == "exa"]     # not counted, no cost (T2.4)
    band = ctx.of("update_band")[0]
    assert band["outcome"] == "unavailable" and band["reason"] == reason
    assert [s["status"] for s in band["searches"]] == ["unavailable", "unavailable"]
    assert ctx.of("round_started")[-1]["status_line"].endswith("update check unavailable")
    assert [d["submit"].get("rule") for d in ctx.results("submit_answer")] == [None]     # rule 4 waived


async def test_not_summarised_when_the_run_stops_before_a_submit(world):
    from tests.loop.support import FakeCtx, stop_on
    script = [*research(), web()]
    ctx, _ = await run_loop(world, script, exa=[web_reply(("a", "Page A", "2026-08-11", PAGE_A))],
                            ctx=FakeCtx(stop=stop_on("loop", "abandoned", at=4)), page_texts=[PAGE_A[:60]])
    assert ctx.of("update_band")[0]["outcome"] == "not_summarised"
    assert ctx.of("update_band")[0]["pages"][0]["id"] == "web-1-1"


async def test_schema_check_once_per_instance(world, caplog):
    from api.loop import execute_run
    from tests.loop.support import FakeCtx, make_deps
    run_mod._SCHEMA_CHECKED.clear() if hasattr(run_mod._SCHEMA_CHECKED, "clear") else None
    listed = {"n": 0}

    class Transport(FakeExaTransport):
        async def list_tool_schema(self):
            listed["n"] += 1
            return {"inputSchema": {"properties": {"query": {"type": "string"}}}}

    deps, fakes = make_deps(world, [*research(), web(), web(), *end(world, update_findings=[])])
    transport = Transport([web_reply(("a", "Page A", "2026-08-11", PAGE_A)), web_reply(("b", "Page B", "2026-08-12", PAGE_B))])
    deps.updates.__init__(transport, MemoryStore())
    await execute_run(FakeCtx(), deps)
    deps.anthropic.push(*research(), web(), *end(world, update_findings=[]))
    transport.push(web_reply(("c", "Page C", "2026-08-13", PAGE_A)))
    await execute_run(FakeCtx(), deps)                       # the same instance: no second check
    import asyncio
    await asyncio.sleep(0)
    assert listed["n"] == 1


def test_band_outcome_rules():
    b = lambda **kw: band_outcome(**{**dict(searches_counted=0, submitted=False, findings=[], unavailable=False,  # noqa: E731
                                            skip_reason=None, declined=False), **kw})
    assert b(searches_counted=1, submitted=True, findings=[{"x": 1}]) == ("found", None)
    assert b(searches_counted=2, submitted=True) == ("nothing_relevant", None)
    assert b(searches_counted=1) == ("not_summarised", None)
    assert b(unavailable=True, submitted=True) == ("unavailable", None)
    assert b(submitted=True, skip_reason="why") == ("skipped", "why")
    assert b(submitted=True, declined=True) == ("declined", None)
    assert b() == ("not_run", None)
    assert b(searches_counted=1, submitted=True, unavailable=True) == ("nothing_relevant", None)   # a search ran
    assert b(submitted=True, skip_reason="why", declined=True) == ("skipped", "why")
