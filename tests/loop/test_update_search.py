"""The update search in the update step (T2.1 to T2.5, contract v2.0 §4.G.4): counting, search numbers, repeats,
D's two formatters, the schema check, and the band's outcome worked out by code (§6)."""

import pytest

from api.loop import run as run_mod
from api.loop.prompts import rejection
from api.loop.run import band_outcome, update_decision
from api.state.store import MemoryStore
from api.web_updates.exa import FakeExaTransport
from tests.loop.support import cite_block, composition, run_loop, tu, turn, web_reply

pytestmark = pytest.mark.anyio

PAGE_A = "Synthetic sample page A text about a later ruling, written for this test only, never to be stored. " * 2
PAGE_B = "Synthetic sample page B text about a pending petition, written for this test only, never stored. " * 2


def research():
    return [turn(tu("search_exact", any_of=["booth"], filters={"cases": ["katz"]}, max_results=1),
                 tu("read_passages", target="katz-1-p6")),
            turn(tu("keep_passages", keep=[{"id": "katz-1-p6", "reason": "r"}])),
            turn(tu("submit_answer", out_of_scope=False))]


def web(**inp):
    inp.setdefault("query", "phone surveillance ruling")
    return turn(tu("search_web_updates", **inp))


def submit_update(**inp):
    return turn(tu("submit_update", **inp))


def answer(world):
    return [composition(cite_block("Text. ", world.corpus, ["katz-1-p6"], "katz-1-p6", 0, 0))]


async def test_every_way_a_search_ends(world):
    exa = [FakeExaTransport.failure("bad_request"), FakeExaTransport.failure("timeout"),
           web_reply(("a", "Page A", "2026-08-11T00:00:00Z", PAGE_A), ("b", "Page B", None, PAGE_B)),
           web_reply(("c", "Page C", "2026-08-12", PAGE_A)), web_reply(("d", "Page D", "2026-08-13", PAGE_B))]
    update = [web(start_published_date="2026-6-30"),                 # refused by our code: not counted
              web(start_published_date="2026-06-30"),                # refused by Exa: counted
              web(type="lite"),                                      # failed: counted
              web(num_results=4),                                    # ok
              web(query="second"), web(query="third"),               # ok, ok: five counted
              web(),                                                 # a sixth: refused by our code
              submit_update(update_findings=[{"statement": "A sample page reports a ruling.", "sources": ["web-3-1"]}])]
    ctx, fakes = await run_loop(world, research(), update=update, comp=answer(world), exa=exa,
                                page_texts=[PAGE_A[:60], PAGE_B[:60]])
    res = ctx.results("search_web_updates")
    assert [r["web_status"] for r in res] == ["refused_by_us", "refused_by_exa", "failed", "ok", "ok", "ok",
                                              "refused_by_us"]
    assert [r.get("search_no") for r in res] == [None, 1, 2, 3, 4, 5, None]
    assert [r["is_error"] for r in res] == [True, True, True, False, False, False, True]
    assert all(r["step"] == "update" and "wrong_step" not in r for r in res)
    assert res[6]["content"] == rejection("update_search", "fourth_search")
    ok = res[3]
    assert [p["id"] for p in ok["web"]] == ["web-3-1", "web-3-2"] and ok["web"][1]["published"] is None
    assert "[page text: " in ok["content"] and PAGE_A[:60] not in ok["content"]
    band = ctx.of("update_band")[0]
    assert [s["search_no"] for s in band["searches"]] == [1, 2, 3, 4, 5]
    assert [s["status"] for s in band["searches"]] == ["refused_by_exa", "failed", "ok", "ok", "ok"]
    assert band["searches"][2]["returned"] == 2 and band["searches"][2]["undated"] == 1
    assert band["searches"][1]["params"]["type"] == "lite" and band["searches"][0]["fixed"]["highlights"] is False
    assert band["outcome"] == "found"
    exa_paid = [p for p in ctx.of("paid_call") if p["service"] == "exa"]
    assert [(p["outcome"], p["cost_usd"], p["step"]) for p in exa_paid][:3] == \
        [("failed", 0.0, "update"), ("failed", 0.004, "update"), ("ok", 0.007, "update")]
    assert len(fakes["exa"].calls) == 5
    # the update step's status line counts the searches that counted (T2.1)
    lines = [d["status_line"] for d in ctx.of("round_started") if d["step"] == "update"]
    assert lines[-1] == "Update step · round 8 of 8 · update searches 5 of 5"
    assert ctx.of("update_ended")[0]["searches"] == 5


async def test_repeats_listed_by_their_first_id(world):
    exa = [web_reply(("a", "Page A", "2026-08-11", PAGE_A)),
           web_reply(("a", "Page A", "2026-08-11", PAGE_A), ("b", "Page B", "2026-09-01", PAGE_B))]
    ctx, fakes = await run_loop(world, research(), update=[web(), web(), submit_update(update_findings=[])],
                                comp=answer(world), exa=exa, page_texts=[PAGE_A[:60], PAGE_B[:60]])
    second = ctx.results("search_web_updates")[1]
    assert second["web_repeats"] == ["web-1-1"] and [p["id"] for p in second["web"]] == ["web-2-1"]
    band = ctx.of("update_band")[0]
    assert band["searches"][1]["returned"] == 2
    assert [p["id"] for p in band["pages"]] == ["web-1-1", "web-2-1"]
    assert band["outcome"] == "nothing_relevant"
    # Claude got the page text, inside the markers
    sent = fakes["anthropic"].requests_for("update")[1]["messages"][-1]["content"][0]["content"][0]["text"]
    assert PAGE_A[:60] in sent and "<web_page_text" in sent


@pytest.mark.parametrize("failure,reason", [("no_credit", "no_credit"), ("key_refused", "key_refused")])
async def test_unavailable_during_the_step(world, failure, reason):
    """Exa became unavailable during the step: no search counted, no_check waived, the band `unavailable` (§6)."""
    store = MemoryStore()
    ctx, fakes = await run_loop(world, research(), update=[web(), web(), submit_update()], comp=answer(world),
                                exa=[FakeExaTransport.failure(failure)], store=store)
    res = ctx.results("search_web_updates")
    assert [r["web_status"] for r in res] == ["unavailable", "unavailable"]
    assert [r.get("search_no") for r in res] == [None, None]           # not counted (T2.4), so no number
    assert len(fakes["exa"].calls) == 1               # the second never reaches Exa
    assert ctx.flags.exa_unavailable == reason
    assert not [p for p in ctx.of("paid_call") if p["service"] == "exa"]     # not counted, no cost (T2.4)
    assert ctx.not_billed == [("exa", "update_search")]                          # D tells H the call cost nothing (v1.4)
    band = ctx.of("update_band")[0]
    assert band["outcome"] == "unavailable" and band["reason"] == reason
    assert [s["status"] for s in band["searches"]] == ["unavailable", "unavailable"]
    lines = [d["status_line"] for d in ctx.of("round_started") if d["step"] == "update"]
    assert lines[-1] == "Update step · round 3 of 8 · update check unavailable"
    assert [d["submit"].get("rule") for d in ctx.results("submit_update")] == [None]     # no_check waived
    assert ctx.of("update_ended")[0]["searches"] == 0 and ctx.ended()["state"] == "answered"


async def test_not_summarised_when_the_step_stops_before_a_submit(world):
    from tests.loop.support import FakeCtx, stop_on
    ctx, _ = await run_loop(world, research(), update=[web()], comp=answer(world),
                            exa=[web_reply(("a", "Page A", "2026-08-11", PAGE_A))],
                            ctx=FakeCtx(stop=stop_on("update", "abandoned", at=2)), page_texts=[PAGE_A[:60]])
    band = ctx.of("update_band")[0]
    assert band["outcome"] == "not_summarised" and band["pages"][0]["id"] == "web-1-1"
    assert ctx.of("update_ended")[0]["end"] == "abandoned"
    assert ctx.ended()["state"] == "answered"                 # the update step's end never changes the run's


async def test_schema_check_once_per_instance(world, caplog):
    from api.loop import execute_run
    from tests.loop.support import FakeCtx, make_deps
    run_mod._SCHEMA_CHECKED.clear() if hasattr(run_mod._SCHEMA_CHECKED, "clear") else None
    listed = {"n": 0}

    class Transport(FakeExaTransport):
        async def list_tool_schema(self):
            listed["n"] += 1
            return {"inputSchema": {"properties": {"query": {"type": "string"}}}}

    deps, fakes = make_deps(world, research(), update=[web(), web(), submit_update(update_findings=[])],
                            comp=answer(world))
    transport = Transport([web_reply(("a", "Page A", "2026-08-11", PAGE_A)), web_reply(("b", "Page B", "2026-08-12", PAGE_B))])
    deps.updates.__init__(transport, MemoryStore())
    await execute_run(FakeCtx(), deps)
    deps.anthropic.push(*research())
    deps.anthropic.push(web(), submit_update(update_findings=[]), step="update")
    deps.anthropic.push(*answer(world), step="composition")
    transport.push(web_reply(("c", "Page C", "2026-08-13", PAGE_A)))
    await execute_run(FakeCtx(), deps)                       # the same instance: no second check
    import asyncio
    await asyncio.sleep(0)
    assert listed["n"] == 1 and not deps.anthropic.left()


def test_band_outcome_rules():
    """§6's order of precedence, the first rule that applies winning."""
    b = lambda **kw: band_outcome(**{"started": True, **kw})     # noqa: E731
    # 1. a counted search ran
    assert b(searches_counted=1, submitted=True, findings=[{"x": 1}]) == ("found", None)
    assert b(searches_counted=2, submitted=True) == ("nothing_relevant", None)
    assert b(searches_counted=1) == ("not_summarised", None)
    assert b(searches_counted=1, end="failed", failure_reason="overloaded") == ("not_summarised", None)
    assert b(searches_counted=1, submitted=True, unavailable="no_credit") == ("nothing_relevant", None)
    # 2. never started for research's reasons
    assert band_outcome(started=False) == ("not_run", None)
    # 3. unavailable: at the start, or during the step (even with a skip reason), then a stop or a failure
    assert band_outcome(started=False, unavailable="key_refused") == ("unavailable", "key_refused")
    assert b(unavailable="no_credit", submitted=True, skip_reason="why") == ("unavailable", "no_credit")
    assert b(end="stopped", stop_kind="update_step_limit") == ("unavailable", "update_step_limit")
    assert b(end="stopped", stop_kind="console_spend_limit", failure_reason="spend_limit") == \
        ("unavailable", "console_spend_limit")
    assert b(end="failed", failure_reason="internal") == ("unavailable", "internal")
    # 4. skipped
    assert b(submitted=True, skip_reason="why", end="submitted") == ("skipped", "why")
    # 5. otherwise
    assert b(end="abandoned") == ("not_run", None)
    assert b(submitted=True, end="submitted") == ("not_run", None)


def test_the_update_decision():
    """§4.G.1 item 3, the corpus search enforced by code as the user's backstop to rule 2 (P4.19)."""
    d = lambda **kw: update_decision(**{"submitted": True, "out_of_scope": False, "corpus_searched": True,   # noqa: E731
                                        "unavailable": None, **kw})
    assert d() == ("start", None)
    assert d(submitted=False) == ("not_run", None)
    assert d(out_of_scope=True) == ("not_run", None)
    assert d(corpus_searched=False) == ("not_run", None)
    assert d(unavailable="no_credit") == ("unavailable", "no_credit")
    assert d(corpus_searched=False, unavailable="no_credit") == ("not_run", None)   # research's reasons come first
    assert d(submitted=False, unavailable="key_refused") == ("not_run", None)
