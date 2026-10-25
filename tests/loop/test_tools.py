"""The search, read and keep tools as Claude and the events see them (T1.4, T1.6, T1.7, T3.3, T3.7)."""

import pytest

from api import settings
from api.errors import ServiceError
from api.loop.prompts import rejection
from api.search.voyage import FakeVoyageClient
from tests.loop.support import cite_block, composition, loop_usage, run_loop, tu, turn

pytestmark = pytest.mark.anyio

SKIP = "Not needed."


def finish(world, pid="katz-1-p6", first=0):
    return [turn(tu("keep_passages", keep=[{"id": pid, "reason": "r"}])),
            turn(tu("submit_answer", out_of_scope=False, update_skip_reason=SKIP)),
            composition(cite_block("Text. ", world.corpus, [pid], pid, first, first))]


async def test_matched_again_and_top_up(world):
    q = {"any_of": ['"telephone booth"'], "filters": {"cases": ["katz"]}, "max_results": 2}
    script = [turn(tu("search_exact", **q)), turn(tu("search_exact", **q)), *finish(world, "katz-1-p3")]
    ctx, fakes = await run_loop(world, script)
    first, second = ctx.results("search_exact")
    assert first["found"] == ["katz-1-n8", "katz-1-p3"] and first["matched_again"] == []
    assert second["matched_again"] == ["katz-1-n8", "katz-1-p3"] and len(second["found"]) == 2
    assert set(second["found"]).isdisjoint(first["found"])
    assert "Matched again (shown earlier in this run, not sent again): katz-1-n8, katz-1-p3." in second["content"]
    # the matched-again passages are not sent again
    assert second["content"].count("[katz-1-p3] Katz") == 0


async def test_attached_footnotes_are_shown_and_can_be_kept(world):
    script = [turn(tu("read_passages", target="katz-1-p5")),
              turn(tu("search_exact", any_of=["booth"], filters={"cases": ["katz"]}, max_results=1)),
              *finish(world, "katz-1-n4")]
    ctx, _ = await run_loop(world, script)
    read = ctx.results("read_passages")[0]
    assert read["read"] == ["katz-1-p5"]                          # attached footnotes are not "read" or "found"
    for n in (4, 5, 6, 7):
        assert f"[katz-1-n{n}] n. " in read["content"]
    assert ctx.results("keep_passages")[0]["kept"][0]["id"] == "katz-1-n4"


async def test_a_page_read_marks_the_passages_on_that_page(world):
    script = [turn(tu("read_passages", target="KATZ:351", before=0, after=0)),
              turn(tu("search_exact", any_of=["booth"], filters={"cases": ["katz"]}, max_results=1)), *finish(world)]
    ctx, _ = await run_loop(world, script)
    read = ctx.results("read_passages")[0]
    assert read["target"] == "katz:351" and read["read"] == ["katz-1-p5", "katz-1-p6", "katz-1-n7", "katz-1-n8", "katz-1-n9"]
    assert read["content"].count("(on the page you asked for)") == 5


async def test_no_match_repeats_the_filters(world):
    script = [turn(tu("search_exact", all_of=["zebra", "giraffe"], filters={"cases": ["katz"], "decided_from": "1960"})),
              turn(tu("read_passages", target="katz-1-p6")), *finish(world)]
    ctx, _ = await run_loop(world, script)
    res = ctx.results("search_exact")[0]
    assert not res["is_error"] and res["found"] == []
    assert res["content"] == "No passages matched this search. Filters set: cases katz; decided_from 1960."


@pytest.mark.parametrize("name,inp,fragment", [
    ("search_exact", {}, "at least one item"),
    ("search_exact", {"any_of": "booth"}, "list of strings"),
    ("search_exact", {"any_of": ["booth"], "filters": {"cases": ["nope"]}}, "Unknown case key"),
    ("search_exact", {"any_of": ["booth"], "max_results": "five"}, "max_results"),
    ("search_exact", {"any_of": ["booth"], "colour": "red"}, "Unknown field"),
    ("search_meaning", {"query": "  "}, "must not be empty"),
    ("search_meaning", {"query": "x", "filters": {"opinion_types": ["judgment"]}}, "Unknown opinion type"),
    ("read_passages", {"target": "katz-1-p999"}, "katz-1 has paragraphs"),
    ("read_passages", {"target": "katz-1-p6", "before": 11}, "from 0 to 10"),
    ("read_passages", {"target": "chatrie:12"}, "slip opinion"),
    ("keep_passages", {"keep": "katz-1-p6"}, "non-empty list"),
])
async def test_bad_input_is_an_error_result_saying_what_to_fix(world, name, inp, fragment):
    script = [turn(tu(name, **inp)), turn(tu("search_exact", any_of=["booth"], filters={"cases": ["katz"]}, max_results=1),
                                          tu("read_passages", target="katz-1-p6")), *finish(world)]
    ctx, fakes = await run_loop(world, script)
    res = ctx.results(name)[0]
    assert res["is_error"] and fragment in res["content"]
    # Claude got the same text as an error tool result
    sent = fakes["anthropic"].requests[1]["messages"][2]["content"][0]
    assert sent["is_error"] is True and fragment in sent["content"][0]["text"]
    assert not fakes["voyage"].calls                 # refused input never reaches Voyage


async def test_max_results_is_clamped(world):
    script = [turn(tu("search_exact", any_of=["booth"], max_results=50)),
              turn(tu("read_passages", target="katz-1-p6")), *finish(world)]
    ctx, _ = await run_loop(world, script)
    assert len(ctx.results("search_exact")[0]["found"]) == settings.MAX_RESULTS_CAP.value


async def test_keep_rules(world):
    long = "x" * (settings.KEEP_REASON_MAX_CHARS.value + 1)
    script = [turn(tu("read_passages", target="katz-1-p6"), tu("search_exact", any_of=["booth"], max_results=1)),
              turn(tu("keep_passages", keep=[{"id": "katz-1-p6", "reason": "first reason"},
                                             {"id": "katz-9-p1", "reason": "never shown"},
                                             {"id": "katz-1-n8", "reason": "   "},
                                             {"id": "katz-1-n9", "reason": long}])),
              turn(tu("keep_passages", keep=[{"id": "katz-1-p6", "reason": "corrected reason"}])),
              turn(tu("keep_passages", keep=[{"id": "katz-9-p1", "reason": "still never shown"}])),
              turn(tu("submit_answer", out_of_scope=False, update_skip_reason=SKIP)),
              composition(cite_block("Text. ", world.corpus, ["katz-1-p6"], "katz-1-p6", 0, 0))]
    ctx, fakes = await run_loop(world, script)
    k1, k2, k3 = ctx.results("keep_passages")
    assert k1["kept"] == [{"id": "katz-1-p6", "reason": "first reason", "replaced": False}] and k1["kept_count"] == 1
    assert [r["why"] for r in k1["refused"]] == [
        rejection("keep", "unseen_id", id="katz-9-p1"), rejection("keep", "reason_empty", id="katz-1-n8"),
        rejection("keep", "reason_too_long", id="katz-1-n9", length=len(long))]
    assert not k1["is_error"]
    assert k2["kept"] == [{"id": "katz-1-p6", "reason": "corrected reason", "replaced": True}]
    assert k3["is_error"] and k3["kept"] == [] and k3["content"].startswith("Nothing was kept:")
    # the composition gets the corrected reason (T1.7)
    doc = fakes["anthropic"].requests[-1]["messages"][0]["content"][0]
    assert "corrected reason" in doc["context"] and "first reason" not in doc["context"]


async def test_keep_cap(world, monkeypatch):
    monkeypatch.setattr("api.loop.run.KEEP_CAP", 2)
    script = [turn(tu("read_passages", target="katz-1-p5")),
              turn(tu("keep_passages", keep=[{"id": f"katz-1-n{i}", "reason": "r"} for i in (4, 5, 6)])),
              turn(tu("keep_passages", keep=[{"id": "katz-1-n4", "reason": "re-keep is not a new keep"}])),
              turn(tu("search_exact", any_of=["booth"], max_results=1)),
              turn(tu("submit_answer", out_of_scope=False, update_skip_reason=SKIP)),
              composition(cite_block("Text. ", world.corpus, ["katz-1-n4", "katz-1-n5"], "katz-1-n4", 0, 0))]
    ctx, _ = await run_loop(world, script)
    k1, k2 = ctx.results("keep_passages")
    assert [k["id"] for k in k1["kept"]] == ["katz-1-n4", "katz-1-n5"]
    assert k1["refused"] == [{"id": "katz-1-n6", "why": rejection("keep", "cap_reached", id="katz-1-n6", count=2)}]
    assert k2["kept"][0]["replaced"] is True and "refused" not in k2


def _err(kind):
    return ServiceError("voyage", kind, 503, kind)


async def test_meaning_search_not_reranked_warns_once(world):
    voyage = FakeVoyageClient(rerank_failures=[_err("server_error")] * 3 + [_err("server_error")] * 3)
    script = [turn(tu("search_meaning", query="listening to a booth", max_results=3)),
              turn(tu("search_meaning", query="eavesdropping device", max_results=3)),
              turn(tu("read_passages", target="katz-1-p6")), *finish(world)]
    ctx, _ = await run_loop(world, script, voyage=voyage)
    r1, r2 = ctx.results("search_meaning")
    assert r1["not_reranked"] is True and "not reranked" in r1["content"] and not r1["is_error"]
    assert [d["code"] for d in ctx.of("warning")] == ["meaning_search_degraded"]
    kinds = ctx.kinds()
    first_result = next(i for i, e in enumerate(ctx.events) if e["kind"] == "tool_result")
    assert kinds[first_result + 1] == "warning"            # right after the result that set the flag


async def test_meaning_search_unavailable_is_an_error_result(world):
    voyage = FakeVoyageClient(embed_failures=[_err("rate_limited")] * 3)
    script = [turn(tu("search_meaning", query="listening to a booth")),
              turn(tu("search_exact", any_of=["booth"], max_results=1), tu("read_passages", target="katz-1-p6")),
              *finish(world)]
    ctx, _ = await run_loop(world, script, voyage=voyage)
    res = ctx.results("search_meaning")[0]
    assert res["is_error"] and "Keyword search still works" in res["content"] and res["found"] == []
    assert [d["code"] for d in ctx.of("warning")] == ["meaning_search_unavailable"]
    voy = [p for p in ctx.of("paid_call") if p["service"] == "voyage"]
    assert [(p["purpose"], p["outcome"]) for p in voy] == [("embed", "retrying"), ("embed", "retrying"), ("embed", "failed")]


async def test_meaning_search_unavailable_does_not_count_as_a_search(world):
    voyage = FakeVoyageClient(embed_failures=[_err("rate_limited")] * 3)
    script = [turn(tu("search_meaning", query="booth")), turn(tu("read_passages", target="katz-1-p6")),
              turn(tu("keep_passages", keep=[{"id": "katz-1-p6", "reason": "r"}])),
              turn(tu("submit_answer", out_of_scope=False, update_skip_reason=SKIP)),
              turn(tu("search_exact", any_of=["booth"], max_results=1)),
              turn(tu("submit_answer", out_of_scope=False, update_skip_reason=SKIP)),
              composition(cite_block("Text. ", world.corpus, ["katz-1-p6"], "katz-1-p6", 0, 0))]
    ctx, _ = await run_loop(world, script, voyage=voyage)
    assert [d["submit"].get("rule") for d in ctx.results("submit_answer")] == ["no_search", None]


async def test_meaning_search_results_carry_headers(world):
    script = [turn(tu("search_meaning", query="a phone booth", filters={"cases": ["katz"], "opinion_types": ["majority"]},
                      max_results=4)), turn(tu("read_passages", target="katz-1-p6")), *finish(world)]
    ctx, fakes = await run_loop(world, script)
    res = ctx.results("search_meaning")[0]
    assert len(res["found"]) == 4 and all(pid.startswith("katz-1-") for pid in res["found"])
    assert res["not_reranked"] is False
    for pid in res["found"]:
        assert f"[{pid}] Katz v. United States, 389 U.S. 347, decided 1967-12-18\nopinion katz-1: majority · Stewart" in res["content"]
    embed = [c for c in fakes["voyage"].calls if c[0] == "embed"]
    assert embed == [("embed", ["a phone booth"], "query")]


async def test_per_curiam_header(world):
    script = [turn(tu("read_passages", target="clinton-1-p1")), turn(tu("read_passages", target="katz-1-p6"),
                                                                      tu("search_exact", any_of=["booth"], max_results=1)),
              *finish(world)]
    ctx, _ = await run_loop(world, script)
    assert "opinion clinton-1: majority · per curiam · " in ctx.results("read_passages")[0]["content"]


async def test_unknown_tool_gets_an_error_result_and_no_events(world):
    script = [turn({"type": "tool_use", "id": "toolu_x", "name": "search_corpus", "input": {"query": "x"}},
                   tu("read_passages", target="katz-1-p6")),
              turn(tu("search_exact", any_of=["booth"], max_results=1)), *finish(world)]
    ctx, fakes = await run_loop(world, script)
    assert "search_corpus" not in [d["name"] for d in ctx.of("tool_call")]
    sent = fakes["anthropic"].requests[1]["messages"][2]["content"]
    assert sent[0]["tool_use_id"] == "toolu_x" and sent[0]["is_error"] is True
    from api.loop import prompts
    from api.loop.tools import TOOL_NAMES
    assert sent[0]["content"][0]["text"] == prompts.message("unknown_tool", name="search_corpus", tools=", ".join(TOOL_NAMES))
    # the request fragments still point at the right tool_result index
    frag = next(d for d in ctx.of("api_fragment") if d["role"] == "request" and d["passage_id"] == "katz-1-p6")
    assert frag["path"] == "messages[2].content[1].content[0]"
