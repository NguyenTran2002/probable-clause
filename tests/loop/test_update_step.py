"""The update step (contract v2.0 §4.G.2, §4.G.4; P4.19): one conversation and one cache with research, each step's
tools refused in the other, submit_update's rules in order with P4.3's withholding, the copy guard on every refused
call once a page was returned, and every way the step ends, none of which touches the answer. Every web page here is
synthetic, on example.test."""

import copy
import json

import pytest

from api import settings
from api.checks import copy_guard_report
from api.loop import prompts
from api.loop.prompts import rejection
from api.loop.streamer import FakeTurn, StreamFailed, raw_usage
from api.state.store import MemoryStore
from tests.loop.support import (WITHHELD, FakeCtx, cite_block, composition, loop_usage, run_loop, skip_update,
                                stop_on, tu, turn, update_usage, web_reply)

pytestmark = pytest.mark.anyio

COPY_LEAD = ("In a ruling this week the court of appeals held that police must obtain a warrant before using a "
             "thermal imaging device to scan the exterior of a home from a public street.")
PAGE = COPY_LEAD + " Synthetic filler that stands in for the rest of a sample page, invented for this test."
COPIED = ("The court of appeals held that police must obtain a warrant before using a thermal imaging device to scan "
          "the exterior of a home from a public street.")
CLEAN = "A sample page reports an appeals ruling on thermal scans of homes."
SKIP = "A later development could not change what Katz held about the booth."
COPIED_SKIP = "No update check was needed here. " + COPIED
# P4.9: a sentence of Katz (katz-1-p6, the real corpus), which the synthetic page below quotes too
KATZ_Q = ("What a person knowingly exposes to the public, even in his own home or office, is not a subject of Fourth "
          "Amendment protection.")
PAGE_OWN = "Synthetic commentary follows it here, written for this test and found on no real page anywhere at all."
COURT_PAGE = "Commentators keep returning to the 1967 opinion, which said: " + KATZ_Q + " " + PAGE_OWN
N = int(settings.COPY_GUARD_WORDS.value)


def research():
    return [turn(tu("search_exact", any_of=['"telephone booth"'], filters={"cases": ["katz"]}, max_results=2),
                 tu("read_passages", target="katz-1-p6"), usage=loop_usage(1, first=True)),
            turn(tu("keep_passages", keep=[{"id": "katz-1-p6", "reason": "Majority: people, not places."}]),
                 usage=loop_usage(2)),
            turn(tu("submit_answer", out_of_scope=False), usage=loop_usage(3))]


def answer(world):
    return [composition(cite_block("The Court said the Amendment protects people. ", world.corpus, ["katz-1-p6"],
                                   "katz-1-p6", 4, 4))]


def web(n=0, **inp):
    inp.setdefault("query", "thermal imaging ruling")
    inp.setdefault("start_published_date", "2026-06-30")
    return turn(tu("search_web_updates", **inp), usage=update_usage(n))


def sub(n=1, **inp):
    return turn(tu("submit_update", **inp), usage=update_usage(n))


def page(text=PAGE):
    return web_reply(("tr", "Thermal ruling", "2026-09-17", text))


def rules(ctx):
    return [d["submit"].get("rule") for d in ctx.results("submit_update")]


def calls(ctx, name):
    return [d["input"] for d in ctx.of("tool_call") if d["name"] == name]


def answer_end(ctx) -> dict:
    """What the update step must never change (§4.G.1 item 5, §4.G.6)."""
    end = ctx.ended()
    return {k: end[k] for k in ("state", "stop_kind", "answer_end", "failure_reason", "rounds", "no_sources_reason",
                                "note", "scope_note", "answer_chars")} | {
        "blocks": [b["text"] for b in ctx.of("answer_block")], "checks": ctx.of("checks")}


@pytest.fixture
async def baseline(world):
    ctx, _ = await run_loop(world, research(), update=[skip_update()], comp=answer(world))
    return answer_end(ctx)


# ---------- one conversation, one cache (§4.G.2) ----------

async def test_the_update_step_continues_research_s_conversation_byte_for_byte(world):
    script = research()
    response = copy.deepcopy(script[-1].content)           # the accepted submit_answer's turn, as the API sent it
    ctx, fakes = await run_loop(world, script, update=[web(0), sub(1, update_findings=[{"statement": CLEAN,
                                                                                         "sources": ["web-1-1"]}])],
                                comp=answer(world), exa=[page()], page_texts=[COPY_LEAD])
    last = fakes["anthropic"].requests_for("research")[-1]
    first, second = fakes["anthropic"].requests_for("update")
    # one builder: the same fields in the same order; every field but max_tokens and messages identical, key order
    # included (tools are rendered into the prompt), and with keys sorted as well
    assert list(last) == list(first)
    for k in last:
        if k in ("max_tokens", "messages"):
            continue
        assert json.dumps(first[k], ensure_ascii=False) == json.dumps(last[k], ensure_ascii=False), k
        assert json.dumps(first[k], sort_keys=True) == json.dumps(last[k], sort_keys=True), k
    assert first["max_tokens"] == settings.UPDATE_OUTPUT_BUDGET.value != last["max_tokens"]
    # the messages: research's last request's, then that call's response unchanged, then one user turn
    n = len(last["messages"])
    assert json.dumps(first["messages"][:n], ensure_ascii=False) == json.dumps(last["messages"], ensure_ascii=False)
    assert json.dumps(first["messages"][:n], sort_keys=True) == json.dumps(last["messages"], sort_keys=True)
    assert json.dumps(first["messages"][n], sort_keys=True) == \
        json.dumps({"role": "assistant", "content": response}, sort_keys=True)
    assert len(first["messages"]) == n + 2
    tool_result, status = first["messages"][n + 1]["content"]
    assert first["messages"][n + 1]["role"] == "user"
    assert tool_result == {"type": "tool_result", "tool_use_id": response[-1]["id"],
                           "content": [{"type": "text", "text": prompts.message("update_start",
                                                                                passages="1 kept passage")}]}
    assert status == {"type": "text", "text": "Update step · round 1 of 8 · update check not yet run"}
    # every later update call appends to the same list
    assert json.dumps(second["messages"][:len(first["messages"])], sort_keys=True) == \
        json.dumps(first["messages"], sort_keys=True)
    # the model and effort are the loop's (asserted at import), the 1-hour breakpoint on the system block stays
    assert first["model"] == settings.LOOP_MODEL.value and first["output_config"] == {"effort": settings.LOOP_EFFORT.value}
    assert first["system"][0]["cache_control"] == {"type": "ephemeral", "ttl": "1h"}
    assert first["cache_control"] == {"type": "ephemeral"}


@pytest.mark.parametrize("name,value", [("UPDATE_EFFORT", "low"), ("UPDATE_MODEL", "claude-other")])
def test_the_update_model_and_effort_must_equal_the_loop_s(name, value):
    """Asserted at import (§4.G.2), in a fresh interpreter so this process's module is left alone."""
    import subprocess
    import sys

    from tests.loop.support import ROOT
    code = (f"import api.settings as s; s.{name} = s.Setting({value!r}, 'test')\n"
            "try:\n    import api.loop.run\nexcept RuntimeError as e:\n    print('refused:', e)\n")
    out = subprocess.run([sys.executable, "-c", code], cwd=ROOT, capture_output=True, text=True, timeout=120)
    assert out.returncode == 0 and out.stdout.startswith("refused: UPDATE_MODEL and UPDATE_EFFORT must equal"), \
        out.stdout + out.stderr


async def test_the_update_estimate_carries_on_from_research_s_last_call(world, monkeypatch):
    """§4.G.4: the update input budget is checked by research's estimator, from research's last call."""
    last = raw_usage(40, w5=2_000, read=15_000, output=500)          # 17,040 in, 500 out
    script = research()
    script[-1].usage = last
    monkeypatch.setattr("api.loop.run.UPDATE_INPUT_BUDGET", 17_040 + 500)   # no room for the new turn
    ctx, fakes = await run_loop(world, script, comp=answer(world))
    assert ctx.of("update_ended")[0] == {"end": "stopped", "stop_kind": "update_token_ceiling_input",
                                         "failure_reason": None, "rounds": 0, "searches": 0}
    assert fakes["anthropic"].requests_for("update") == []


# ---------- each step's tools refused in the other (§4.G.2) ----------

async def test_the_update_tools_are_refused_in_research(world):
    script = [research()[0],
              turn(tu("search_web_updates", query="later rulings")),
              turn(tu("submit_update", update_skip_reason=SKIP)),
              *research()[1:]]
    ctx, fakes = await run_loop(world, script, update=[skip_update()], comp=answer(world))
    web_res, = ctx.results("search_web_updates")
    upd_res = [r for r in ctx.results("submit_update") if r["step"] == "research"][0]
    assert web_res == {"step": "research", "tool_use_id": web_res["tool_use_id"], "name": "search_web_updates",
                       "is_error": True, "content": rejection("wrong_step", "update_tool", name="search_web_updates"),
                       "web": [], "web_repeats": [], "web_status": "refused_by_us", "wrong_step": True}
    assert upd_res["submit"] == {"accepted": False, "rule": "wrong_step"} and upd_res["wrong_step"] is True
    assert upd_res["content"] == rejection("wrong_step", "update_tool", name="submit_update")
    # never counted: no Exa call, no band search, no search number, and the update step starts at 0
    assert fakes["exa"].calls == [] and ctx.of("update_band")[0]["searches"] == []
    assert ctx.of("update_ended")[0]["searches"] == 0
    assert ctx.of("update_band")[0]["outcome"] == "skipped"


async def test_the_research_tools_are_refused_in_the_update_step(world):
    update = [turn(tu("search_meaning", query="booths")),
              turn(tu("search_exact", any_of=["booth"])),
              turn(tu("read_passages", target="katz-1-p7")),
              turn(tu("keep_passages", keep=[{"id": "katz-1-n9", "reason": "late"}])),
              turn(tu("submit_answer", out_of_scope=True, note="Changed my mind.")),
              turn(tu("search_exact", any_of=["booth"]), tu("submit_update", update_skip_reason=SKIP)),
              skip_update(SKIP)]
    ctx, fakes = await run_loop(world, research(), update=update, comp=answer(world))
    res = [r for r in ctx.results() if r["step"] == "update"]
    text = lambda name: rejection("wrong_step", "research_tool", name=name)     # noqa: E731
    assert [(r["name"], r["is_error"], r.get("wrong_step")) for r in res] == [
        ("search_meaning", True, True), ("search_exact", True, True), ("read_passages", True, True),
        ("keep_passages", True, True), ("submit_answer", True, True), ("search_exact", True, True),
        ("submit_update", True, None), ("submit_update", False, None)]
    assert [r["content"] for r in res[:6]] == [text("search_meaning"), text("search_exact"), text("read_passages"),
                                               text("keep_passages"), text("submit_answer"), text("search_exact")]
    assert res[0]["found"] == [] and res[0]["matched_again"] == [] and "not_reranked" not in res[0]
    assert res[2]["read"] == [] and res[2]["target"] == "katz-1-p7"
    assert res[3]["kept"] == [] and res[3]["kept_count"] == 1 and "refused" not in res[3]
    assert res[4]["submit"] == {"accepted": False, "rule": "wrong_step"}
    # rule 1 counts every tool_use, a refused one too
    assert rules(ctx) == ["same_turn", None]
    # never counted: nothing searched, read or kept; no Voyage call; the run's end is research's
    assert not fakes["voyage"].calls
    assert ctx.of("composition_started")[0]["documents"] == ["katz-1-p6"]
    assert "katz-1-p7" not in {d["id"] for d in ctx.of("passage")}
    assert ctx.ended()["state"] == "answered" and ctx.ended()["no_sources_reason"] is None
    # the tool_call holds the input as sent (no page was returned, so nothing to guard)
    assert calls(ctx, "keep_passages")[-1] == {"keep": [{"id": "katz-1-n9", "reason": "late"}]}


async def test_an_unknown_tool_in_the_update_step(world):
    update = [turn({"type": "tool_use", "id": "toolu_upd_x", "name": "browse", "input": {}},
                   tu("submit_update", update_skip_reason=SKIP)), skip_update(SKIP)]
    ctx, fakes = await run_loop(world, research(), update=update, comp=answer(world))
    sent = fakes["anthropic"].requests_for("update")[1]["messages"][-1]["content"]
    from api.loop.tools import TOOL_NAMES
    assert sent[0]["content"][0]["text"] == prompts.message("unknown_tool", name="browse", tools=", ".join(TOOL_NAMES))
    assert len(TOOL_NAMES) == 7 and "browse" not in [d["name"] for d in ctx.of("tool_call")]
    assert rules(ctx) == ["same_turn", None]


# ---------- submit_update's rules, in order (§4.G.4) ----------

async def test_submit_update_rules_each_in_turn(world):
    update = [
        # rule 1: the search runs (and returns the page), the submit is refused; its copied statement withheld
        turn(tu("search_web_updates", query="thermal imaging ruling", start_published_date="2026-06-30"),
             tu("submit_update", update_findings=[{"statement": COPIED, "sources": ["web-1-1"]}])),
        # the input check, rule null; a copied statement still withheld
        sub(update_findings=[{"statement": COPIED, "sources": ["web-1-1"]}], colour="red"),
        sub(update_skip_reason=5),
        # the findings checks, before the copy guard
        sub(update_findings=[{"statement": COPIED, "sources": ["web-9-9"]}, {"statement": CLEAN, "sources": []}]),
        # the copy guard: a statement; the skip reason alone; the overview
        sub(update_findings=[{"statement": COPIED, "sources": ["web-1-1"]}, {"statement": CLEAN, "sources": ["web-1-1"]}]),
        sub(update_findings=[{"statement": CLEAN, "sources": ["web-1-1"]}], update_skip_reason=COPIED_SKIP),
        sub(update_findings=[{"statement": CLEAN, "sources": ["web-1-1"]}], update_overview=COPIED),
        sub(update_findings=[{"statement": CLEAN, "sources": ["web-1-1"]}], update_overview="One sample page."),
    ]
    ctx, fakes = await run_loop(world, research(), update=update, comp=answer(world), exa=[page()],
                                page_texts=[COPY_LEAD, COPIED])
    assert rules(ctx) == ["same_turn", None, None, "findings", "copy_guard", "copy_guard", "copy_guard", None]
    res = ctx.results("submit_update")
    assert res[0]["content"] == rejection("submit_update", "rule_1_same_turn")
    assert "colour" in res[1]["content"] and "update_skip_reason" in res[2]["content"]
    assert res[3]["content"].startswith("Not accepted: the update findings have these problems:")
    pages = {"web-1-1": PAGE}
    report = copy_guard_report([COPIED, CLEAN], None, pages, N)
    assert res[4]["content"] == rejection("submit_update", "copy_guard", problems="\n".join(report.problems))
    assert res[5]["content"] == rejection("submit_update", "copy_guard_skip_reason", pages="page web-1-1")
    assert "The overview" in res[6]["content"]
    assert all(COPIED not in r["content"] for r in res)
    shown = calls(ctx, "submit_update")
    assert shown[0]["update_findings"][0]["statement"] == WITHHELD                       # whichever rule refuses it
    assert shown[1] == {"update_findings": [{"statement": WITHHELD, "sources": ["web-1-1"]}], "colour": "red"}
    assert shown[3]["update_findings"] == [{"statement": WITHHELD, "sources": ["web-9-9"]},
                                           {"statement": CLEAN, "sources": []}]
    assert [f["statement"] for f in shown[4]["update_findings"]] == [WITHHELD, CLEAN]
    assert shown[5]["update_skip_reason"] == WITHHELD and shown[5]["update_findings"][0]["statement"] == CLEAN
    assert shown[6]["update_overview"] == WITHHELD
    assert shown[7]["update_overview"] == "One sample page."                            # accepted: as sent
    # Claude's own conversation keeps its input (P4.3); only the events are withheld
    later = fakes["anthropic"].requests_for("update")[-1]["messages"]
    sent = [b for m in later if m["role"] == "assistant" for b in m["content"] if b.get("name") == "submit_update"]
    assert sent[0]["input"]["update_findings"][0]["statement"] == COPIED
    band = ctx.of("update_band")[0]
    assert band["outcome"] == "found" and band["findings"] == [{"statement": CLEAN, "sources": ["web-1-1"]}]
    assert band["overview"] == "One sample page."
    assert COPIED not in json.dumps(ctx.events) and COPY_LEAD not in json.dumps(ctx.events)


async def test_no_check_is_refused_every_time(world):
    update = [sub(), sub(update_findings=[]), sub(), sub(update_overview="  "), skip_update(SKIP)]
    ctx, _ = await run_loop(world, research(), update=update, comp=answer(world))
    assert rules(ctx) == ["no_check", "no_check", "no_check", "no_check", None]
    assert ctx.results("submit_update")[0]["content"] == rejection("submit_update", "no_check")
    band = ctx.of("update_band")[0]
    assert (band["outcome"], band["reason"]) == ("skipped", SKIP)


async def test_findings_with_no_search_are_refused_before_no_check(world):
    update = [sub(update_findings=[{"statement": CLEAN, "sources": ["web-1-1"]}]), sub(update_overview="An overview."),
              skip_update(SKIP)]
    ctx, _ = await run_loop(world, research(), update=update, comp=answer(world))
    assert rules(ctx) == ["findings", "findings", None]


async def test_no_check_is_waived_once_the_check_became_unavailable(world):
    """Exa's credit flag is set in the store before the step's search: D marks the run, nothing is called, and a bare
    submit_update is accepted; the band says why (§6: unavailable first, even with a skip reason)."""
    store = MemoryStore()
    from datetime import datetime
    from zoneinfo import ZoneInfo
    await store.set_flag("exa_out_of_credit", datetime.now(ZoneInfo("America/Chicago")))
    ctx, fakes = await run_loop(world, research(), update=[web(), sub(update_skip_reason=SKIP)], comp=answer(world),
                                store=store)
    assert ctx.flags.exa_unavailable == "no_credit" and fakes["exa"].calls == []
    assert rules(ctx) == [None]
    band = ctx.of("update_band")[0]
    assert (band["outcome"], band["reason"]) == ("unavailable", "no_credit")


async def test_the_copy_guard_exempts_words_that_are_also_the_court_s(world):
    quoting = 'A sample page discusses Katz and its line that "' + KATZ_Q + '"'
    copying = 'A sample page says: "' + KATZ_Q + '" ' + PAGE_OWN
    skip_quoting = 'Not needed: Katz\'s line that "' + KATZ_Q + '" is not in question.'
    assert copy_guard_report([quoting, copying], None, {"web-1-1": COURT_PAGE}, N).flagged_statements == {0, 1}
    update = [web(), sub(update_findings=[{"statement": copying, "sources": ["web-1-1"]}]),
              sub(update_findings=[{"statement": quoting, "sources": ["web-1-1"]}], update_skip_reason=skip_quoting)]
    ctx, _ = await run_loop(world, research(), update=update, comp=answer(world), exa=[page(COURT_PAGE)],
                            page_texts=[PAGE_OWN])
    assert rules(ctx) == ["copy_guard", None]
    assert calls(ctx, "submit_update")[0]["update_findings"][0]["statement"] == WITHHELD
    band = ctx.of("update_band")[0]
    assert band["outcome"] == "found" and band["findings"][0]["statement"] == quoting


async def test_nothing_is_guarded_before_any_page_was_returned(world):
    ctx, _ = await run_loop(world, research(), update=[sub(update_skip_reason=COPIED_SKIP)], comp=answer(world))
    assert rules(ctx) == [None] and calls(ctx, "submit_update")[0]["update_skip_reason"] == COPIED_SKIP


# ---------- no page's words in any refused call (§4.G.2) ----------

async def test_every_refused_call_in_the_update_step_is_guarded(world):
    update = [web(),
              turn(tu("keep_passages", keep=[{"id": "katz-1-p6", "reason": COPIED}])),
              turn(tu("submit_answer", out_of_scope=True, note="Changed: " + COPIED)),
              turn(tu("read_passages", target=COPIED)),
              turn(tu("search_meaning", query=COPIED, filters={"none_of": [COPIED, "booth"]})),
              turn(tu("search_web_updates", query=COPIED, start_published_date="2026-6-30")),
              sub(update_findings=[{"statement": CLEAN, "sources": ["web-1-1"]}])]
    ctx, fakes = await run_loop(world, research(), update=update, comp=answer(world), exa=[page()],
                                page_texts=[COPY_LEAD, COPIED])
    upd = [d for d in ctx.of("tool_call") if d["step"] == "update"]
    assert upd[1]["input"] == {"keep": [{"id": "katz-1-p6", "reason": WITHHELD}]}
    assert upd[2]["input"] == {"out_of_scope": True, "note": WITHHELD}
    assert upd[3]["input"] == {"target": WITHHELD}
    assert upd[4]["input"] == {"query": WITHHELD, "filters": {"none_of": [WITHHELD, "booth"]}}
    assert upd[5]["input"] == {"query": WITHHELD, "start_published_date": "2026-6-30"}
    read = [r for r in ctx.results("read_passages") if r["step"] == "update"][0]
    assert read["target"] == WITHHELD
    # accepted calls are stored as Claude sent them
    assert upd[0]["input"]["query"] == "thermal imaging ruling" and upd[6]["input"]["update_findings"][0]["statement"] == CLEAN
    # Claude's conversation keeps every input as written
    later = fakes["anthropic"].requests_for("update")[-1]["messages"]
    assert any(b.get("input") == {"target": COPIED} for m in later if m["role"] == "assistant" for b in m["content"])
    assert COPIED not in json.dumps(ctx.events) and COPY_LEAD not in json.dumps(ctx.events)


# ---------- every way the step ends; none touches the answer (§4.G.1 item 5, §4.G.4) ----------

def text_turn(n=0, **kw):
    return turn(text="Considering whether later developments matter.", stop_reason="end_turn",
                usage=kw.pop("usage", None) or update_usage(n), **kw)


async def test_the_update_step_limit(world, baseline, monkeypatch):
    monkeypatch.setattr("api.loop.run.UPDATE_MAX_ROUNDS", 2)
    ctx, _ = await run_loop(world, research(), update=[text_turn(0), text_turn(1)], comp=answer(world))
    assert ctx.of("update_ended")[0] == {"end": "stopped", "stop_kind": "update_step_limit", "failure_reason": None,
                                         "rounds": 2, "searches": 0}
    band = ctx.of("update_band")[0]
    assert (band["outcome"], band["reason"]) == ("unavailable", "update_step_limit")
    assert answer_end(ctx) == baseline and ctx.ended()["stop_kinds"] == ["update_step_limit"]


async def test_the_update_step_limit_after_a_search_is_not_summarised(world, baseline, monkeypatch):
    monkeypatch.setattr("api.loop.run.UPDATE_MAX_ROUNDS", 2)
    ctx, _ = await run_loop(world, research(), update=[web(0), text_turn(1)], comp=answer(world), exa=[page()],
                            page_texts=[COPY_LEAD])
    assert ctx.of("update_band")[0]["outcome"] == "not_summarised" and answer_end(ctx) == baseline


async def test_the_update_time_limit_before_a_round(world, baseline):
    checks = {"n": 0}

    def left():
        checks["n"] += 1
        return 600.0 if checks["n"] <= 4 else 0.0                # research's three rounds, then the update's first

    ctx, _ = await run_loop(world, research(), update=[text_turn()], comp=answer(world),
                            ctx=FakeCtx(seconds_left=left))
    assert ctx.of("update_ended")[0]["stop_kind"] == "update_time_limit" and ctx.of("update_ended")[0]["rounds"] == 1
    assert answer_end(ctx) == baseline and ctx.ended()["stop_kinds"] == ["update_time_limit"]


@pytest.mark.parametrize("purpose,rounds", [("update", 1), ("update_search", 1)])
async def test_the_run_deadline_from_the_gate_ends_the_update_step(world, baseline, purpose, rounds):
    ctx, _ = await run_loop(world, research(), update=[web()] if purpose == "update_search" else [],
                            comp=answer(world), exa=[], ctx=FakeCtx(stop=stop_on(purpose, "deadline")))
    ended = ctx.of("update_ended")[0]
    assert (ended["end"], ended["stop_kind"], ended["rounds"]) == ("stopped", "update_time_limit", rounds)
    assert answer_end(ctx) == baseline
    if purpose == "update_search":
        stopped = ctx.results("search_web_updates")[0]
        assert stopped["is_error"] and stopped["content"] == "" and ctx.of("update_band")[0]["searches"] == []


async def test_the_update_output_ceiling(world, baseline):
    cut = FakeTurn(content=[{"type": "thinking", "thinking": "", "signature": "s"}, tu("submit_update",
                                                                                         update_skip_reason=SKIP)],
                   stop_reason="max_tokens")
    ctx, fakes = await run_loop(world, research(), update=[cut], comp=answer(world))
    assert ctx.of("update_ended")[0]["stop_kind"] == "update_token_ceiling_output"
    assert not ctx.results("submit_update")                      # the cut call's tool use never runs
    assert answer_end(ctx) == baseline
    spent = text_turn(usage=raw_usage(30, read=20_000, output=settings.UPDATE_OUTPUT_BUDGET.value))
    ctx, _ = await run_loop(world, research(), update=[spent], comp=answer(world))
    assert ctx.of("update_ended")[0]["stop_kind"] == "update_token_ceiling_output"
    assert ctx.of("update_ended")[0]["rounds"] == 1 and answer_end(ctx) == baseline


async def test_the_update_input_ceiling_counts_only_update_attempts(world, baseline, monkeypatch):
    monkeypatch.setattr("api.loop.run.UPDATE_INPUT_BUDGET", 60_000)
    heavy = text_turn(usage=raw_usage(30, w5=1_000, read=40_000, output=300))     # 41,030 of 60,000
    ctx, _ = await run_loop(world, research(), update=[heavy], comp=answer(world))
    ended = ctx.of("update_ended")[0]
    assert (ended["stop_kind"], ended["rounds"]) == ("update_token_ceiling_input", 1)
    assert answer_end(ctx) == baseline and ctx.ended()["stop_kinds"] == ["update_token_ceiling_input"]


async def test_an_abandoned_update_step(world, baseline):
    ctx, _ = await run_loop(world, research(), comp=answer(world), ctx=FakeCtx(stop=stop_on("update", "abandoned")))
    assert ctx.of("update_ended")[0] == {"end": "abandoned", "stop_kind": None, "failure_reason": None, "rounds": 1,
                                         "searches": 0}
    assert ctx.of("update_band")[0]["outcome"] == "not_run"
    assert answer_end(ctx) == baseline and ctx.ended()["stop_kinds"] == []


@pytest.mark.parametrize("kind,stop_kind", [("spend_limit", "console_spend_limit"), ("spend_cap", "tier_spend_cap")])
async def test_a_spend_limit_in_the_update_step(world, baseline, kind, stop_kind):
    ctx, _ = await run_loop(world, research(), update=[StreamFailed(kind, None, kind)], comp=answer(world))
    assert ctx.of("update_ended")[0] == {"end": "stopped", "stop_kind": stop_kind, "failure_reason": kind,
                                         "rounds": 1, "searches": 0}
    band = ctx.of("update_band")[0]
    assert (band["outcome"], band["reason"]) == ("unavailable", stop_kind)
    # in stop_kinds, so H pauses live research; the run itself stays answered with no stop_kind (§4.G.6)
    assert ctx.ended()["stop_kinds"] == [stop_kind] and answer_end(ctx) == baseline
    failed = [p for p in ctx.of("paid_call") if p["purpose"] == "update"]
    assert [(p["attempt"], p["outcome"], p["error_kind"], p["step"]) for p in failed] == [(1, "failed", kind, "update")]


async def test_a_service_error_in_the_update_step(world, baseline, no_real_waits):
    over = [StreamFailed("overloaded", 529, "x")] * 3
    ctx, _ = await run_loop(world, research(), update=over, comp=answer(world))
    assert ctx.of("update_ended")[0] == {"end": "failed", "stop_kind": None, "failure_reason": "overloaded",
                                         "rounds": 1, "searches": 0}
    band = ctx.of("update_band")[0]
    assert (band["outcome"], band["reason"]) == ("unavailable", "overloaded")
    attempts = [(p["attempt"], p["outcome"]) for p in ctx.of("paid_call") if p["purpose"] == "update"]
    assert attempts == [(1, "retrying"), (2, "retrying"), (3, "failed")] and no_real_waits == [2.0, 8.0]
    assert answer_end(ctx) == baseline and ctx.ended()["stop_kinds"] == []


async def test_a_retry_in_the_update_step_recovers(world, baseline):
    ctx, _ = await run_loop(world, research(), update=[StreamFailed("overloaded", 529, "x"), skip_update(SKIP)],
                            comp=answer(world))
    assert [p["outcome"] for p in ctx.of("paid_call") if p["purpose"] == "update"] == ["retrying", "ok"]
    assert ctx.of("update_band")[0]["outcome"] == "skipped" and answer_end(ctx) == baseline


async def test_a_refusal_in_the_update_step(world, baseline):
    refused = FakeTurn(content=[], stop_reason="refusal", usage=raw_usage(30, read=20_000, output=10))
    ctx, _ = await run_loop(world, research(), update=[refused], comp=answer(world))
    assert ctx.of("update_ended")[0]["end"] == "failed" and ctx.of("update_ended")[0]["failure_reason"] == "refusal"
    assert answer_end(ctx) == baseline


async def test_an_unexpected_exception_in_the_update_step_ends_it_internal(world, baseline, caplog):
    import logging
    caplog.set_level(logging.ERROR)

    def boom(request):
        raise KeyError("a bug in our own code")

    ctx, _ = await run_loop(world, research(), update=[boom], comp=answer(world))
    assert ctx.of("update_ended")[0] == {"end": "failed", "stop_kind": None, "failure_reason": "internal",
                                         "rounds": 1, "searches": 0}
    band = ctx.of("update_band")[0]
    assert (band["outcome"], band["reason"]) == ("unavailable", "internal")
    assert answer_end(ctx) == baseline
    # the attempt that raised is recorded, so the call numbers keep no gap
    p = [p for p in ctx.of("paid_call") if p["purpose"] == "update"]
    assert [(x["outcome"], x["error_kind"]) for x in p] == [("failed", "internal")]
    assert "KeyError" in caplog.text


async def test_an_update_step_abandoned_after_the_composition_finished_leaves_the_run_answered(world, baseline):
    hold = __import__("asyncio").Event()

    async def late(request):
        hold.set()
        return FakeTurn(content=[], stop_reason="end_turn", usage=update_usage())

    ctx = FakeCtx()
    gates = {"n": 0}

    def stop(service, purpose, n):
        if purpose == "update":
            gates["n"] += 1
            if gates["n"] == 2:
                from api.types import RunStopped
                return RunStopped("abandoned")
        return None

    ctx.stop = stop
    ctx, _ = await run_loop(world, research(), update=[late], comp=answer(world), ctx=ctx)
    assert ctx.of("update_ended")[0]["end"] == "abandoned"
    assert answer_end(ctx) == baseline and ctx.ended()["state"] == "answered"


async def test_an_unexpected_exception_inside_a_search_still_closes_the_call(world, baseline, monkeypatch):
    """The call that was running gets an empty error result, so every tool_call has its tool_result, and the step
    ends `failed` with `internal` while the answer stands."""
    async def broken(self, params, search_no, seen_urls, ctx):
        raise KeyError("a bug in our own code")

    monkeypatch.setattr("api.web_updates.exa.UpdateSearch.search", broken)
    ctx, _ = await run_loop(world, research(), update=[web()], comp=answer(world))
    (res,) = ctx.results("search_web_updates")
    assert res["is_error"] and res["content"] == "" and res["step"] == "update"
    assert ctx.of("update_ended")[0]["failure_reason"] == "internal" and answer_end(ctx) == baseline



# ---------- contract v2.0 §4.G.2 as revised: every stored update-step call, keys included ----------

async def test_a_finding_with_an_extra_key_is_refused_at_the_input_check(world):
    """F's checks read only statement and sources, so an extra key would pass unchecked and reach the events."""
    update = [web(), sub(update_findings=[{"statement": CLEAN, "sources": ["web-1-1"], "quote": COPIED}]),
              sub(update_findings=[{"statement": CLEAN}]),
              sub(update_findings=["not an object"]),
              sub(update_findings=[{"statement": CLEAN, "sources": ["web-1-1"]}])]
    ctx, _ = await run_loop(world, research(), update=update, comp=answer(world), exa=[page()])
    assert rules(ctx) == [None, None, None, None]
    res = ctx.results("submit_update")
    assert [r["submit"]["accepted"] for r in res] == [False, False, False, True]
    assert all("exactly" in r["content"] and "quote" not in r["content"] for r in res[:3])
    assert calls(ctx, "submit_update")[0]["update_findings"][0] == {"statement": CLEAN, "sources": ["web-1-1"],
                                                                     "quote": WITHHELD}
    assert ctx.of("update_band")[0]["findings"] == [{"statement": CLEAN, "sources": ["web-1-1"]}]


async def test_a_key_that_repeats_a_page_is_withheld(world):
    update = [web(),
              turn(tu("keep_passages", **{COPIED: "x", "keep": [{"id": "katz-1-p6", "reason": "r"}]})),
              sub(**{COPIED: [CLEAN], "update_skip_reason": SKIP}),
              sub(update_findings=[{"statement": CLEAN, "sources": ["web-1-1"]}])]
    ctx, fakes = await run_loop(world, research(), update=update, comp=answer(world), exa=[page()])
    upd = [d for d in ctx.of("tool_call") if d["step"] == "update"]
    assert upd[1]["input"] == {"[field withheld 1]": "x", "keep": [{"id": "katz-1-p6", "reason": "r"}]}
    assert upd[2]["input"] == {"[field withheld 1]": [CLEAN], "update_skip_reason": SKIP}
    refused = ctx.results("submit_update")[0]
    assert refused["submit"] == {"accepted": False, "rule": None} and refused["content"] == WITHHELD
    # Claude got its own input back, and its error text naming the field
    later = fakes["anthropic"].requests_for("update")[-1]["messages"]
    assert any(COPIED in b.get("input", {}) for m in later if m["role"] == "assistant" for b in m["content"])
    sent = [b for m in later if m["role"] == "user" for b in m["content"] if b.get("type") == "tool_result"]
    assert any(COPIED in b["content"][0]["text"] for b in sent)


def test_keys_are_numbered_within_the_input():
    from api.loop.run import texts_in, withhold_texts
    inp = {"a": {"b": "x", "c": ["y", {"d": "z"}]}}
    assert texts_in(inp) == ["a", "b", "x", "c", "y", "d", "z"]
    assert withhold_texts(inp, {0, 2, 5}) == {"[field withheld 1]": {"b": WITHHELD, "c": ["y", {"[field withheld 2]": "z"}]}}
    assert inp == {"a": {"b": "x", "c": ["y", {"d": "z"}]}}


async def test_an_accepted_call_that_quotes_a_page_is_withheld_too(world):
    """A later search whose query quotes a page: the stored tool_call, the band's params and the event's copy of the
    result show the withheld text; Claude and Exa get the query as written."""
    update = [web(), web(1, query=COPIED), sub(update_findings=[{"statement": CLEAN, "sources": ["web-1-1"]}])]
    ctx, fakes = await run_loop(world, research(), update=update, comp=answer(world),
                                exa=[page(), web_reply(("tr2", "Second ruling", "2026-09-20", "Another synthetic page, "
                                                        "written for this test, about something else entirely."))])
    upd = [d for d in ctx.of("tool_call") if d["name"] == "search_web_updates"]
    assert upd[0]["input"]["query"] == "thermal imaging ruling"           # before any page: nothing to guard
    assert upd[1]["input"] == {"query": WITHHELD, "start_published_date": "2026-06-30"}
    band = ctx.of("update_band")[0]
    assert [s["params"]["query"] for s in band["searches"]] == ["thermal imaging ruling", WITHHELD]
    second = ctx.results("search_web_updates")[1]
    assert second["web_status"] == "ok" and WITHHELD in second["content"] and second["search_no"] == 2
    assert fakes["exa"].calls[1][0]["query"] == COPIED
    later = fakes["anthropic"].requests_for("update")[-1]["messages"]
    assert any(b.get("input", {}).get("query") == COPIED for m in later if m["role"] == "assistant"
               for b in m["content"])


async def test_an_exa_refusal_echoing_a_page_is_guarded_in_the_event(world):
    """Exa's own message is part of a refused search's event content; once a page was returned, a message that
    repeats one is withheld there, as a refused result's content is (§4.G.2). Claude still gets Exa's message."""
    from api.errors import ServiceError
    echo = ServiceError("exa", "bad_request", 400, "Invalid query: " + COPIED)
    update = [web(), web(1, query="thermal imaging appeal"), sub(update_findings=[{"statement": CLEAN,
                                                                                 "sources": ["web-1-1"]}])]
    ctx, fakes = await run_loop(world, research(), update=update, comp=answer(world), exa=[page(), echo])
    refused = ctx.results("search_web_updates")[1]
    assert refused["web_status"] == "refused_by_exa" and refused["search_no"] == 2
    assert refused["content"] == WITHHELD
    sent = fakes["anthropic"].requests_for("update")[2]["messages"][-1]["content"][0]["content"][0]["text"]
    assert COPIED in sent and "Exa refused" in sent
    assert ctx.of("update_band")[0]["searches"][1]["status"] == "refused_by_exa"


@pytest.mark.parametrize("reason", ["max_tokens", "model_context_window_exceeded"])
async def test_a_call_cut_by_the_context_window_ends_the_update_step_at_its_output_ceiling(world, baseline, reason,
                                                                                            caplog):
    import logging
    caplog.set_level(logging.WARNING)
    cut = FakeTurn(content=[{"type": "thinking", "thinking": "", "signature": "s"},
                            tu("search_web_updates", query="never run")], stop_reason=reason,
                   usage=update_usage())
    ctx, fakes = await run_loop(world, research(), update=[cut], comp=answer(world))
    assert ctx.of("update_ended")[0] == {"end": "stopped", "stop_kind": "update_token_ceiling_output",
                                         "failure_reason": None, "rounds": 1, "searches": 0}
    assert not ctx.results("search_web_updates") and fakes["exa"].calls == []
    assert answer_end(ctx) == baseline and ctx.ended()["stop_kinds"] == ["update_token_ceiling_output"]
    assert reason in caplog.text
