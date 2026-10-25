"""submit_answer's rules in order (T1.10, T2.3): rule 1 (alone in its turn, once, P4.16), then the findings checks and the copy guard, then rules 2
to 4; P4.3's withholding of flagged statements in the stored tool_call."""

import json

import pytest

from api.loop import prompts
from api.loop.prompts import rejection
from tests.loop.support import FakeCtx, WITHHELD, cite_block, composition, loop_usage, run_loop, tu, turn, web_reply

pytestmark = pytest.mark.anyio

SKIP = "Not needed: the question asks what Katz held."
COPY_LEAD = ("In a ruling this week the court of appeals held that police must obtain a warrant before using a "
             "thermal imaging device to scan the exterior of a home from a public street.")
PAGE = COPY_LEAD + " Synthetic filler that stands in for the rest of a sample page, invented for this test."
COPIED = ("The court of appeals held that police must obtain a warrant before using a thermal imaging device to scan "
          "the exterior of a home from a public street.")


def search():
    return turn(tu("search_exact", any_of=['"telephone booth"'], filters={"cases": ["katz"]}, max_results=2),
                tu("read_passages", target="katz-1-p6"), usage=loop_usage(1, first=True))


def keep():
    return turn(tu("keep_passages", keep=[{"id": "katz-1-p6", "reason": "Majority: people, not places."}]),
                usage=loop_usage(2))


def submit(**kw):
    inp = {"out_of_scope": False}
    inp.update(kw)
    return turn(tu("submit_answer", **inp), usage=loop_usage(3))


def answer(world):
    return composition(cite_block("Text. ", world.corpus, ["katz-1-p6"], "katz-1-p6", 0, 0))


def rules(ctx):
    return [d["submit"].get("rule") for d in ctx.results("submit_answer")]


async def test_rule_1_same_turn_as_a_search(world):
    script = [turn(tu("read_passages", target="katz-1-p6"), tu("search_exact", any_of=["booth"]),
                   tu("submit_answer", out_of_scope=False, update_skip_reason=SKIP)),
              keep(), submit(update_skip_reason=SKIP), answer(world)]
    ctx, _ = await run_loop(world, script)
    assert rules(ctx) == ["same_turn", None]
    refused = ctx.results("submit_answer")[0]
    assert refused["is_error"] and refused["content"] == rejection("submit", "rule_1_same_turn")


async def test_rule_1_comes_before_the_findings_checks(world):
    script = [turn(tu("read_passages", target="katz-1-p6"),
                   tu("submit_answer", out_of_scope=False, update_findings=[{"statement": "x", "sources": ["web-9-9"]}])),
              search(), keep(), submit(update_skip_reason=SKIP), answer(world)]
    ctx, _ = await run_loop(world, script)
    assert rules(ctx)[0] == "same_turn"


async def test_a_keep_in_the_same_turn_refuses_the_submit(world):
    """P4.16: a submit must be the turn's only call. The keep runs and counts; the submit is refused."""
    script = [search(), turn(tu("keep_passages", keep=[{"id": "katz-1-p6", "reason": "r"}]),
                             tu("submit_answer", out_of_scope=False, update_skip_reason=SKIP)),
              submit(update_skip_reason=SKIP), answer(world)]
    ctx, fakes = await run_loop(world, script)
    assert rules(ctx) == ["same_turn", None] and ctx.ended()["state"] == "answered"
    assert ctx.results("keep_passages")[0]["is_error"] is False
    assert ctx.of("composition_started")[0]["documents"] == ["katz-1-p6"]
    assert fakes["anthropic"].requests[-1]["model"] == "claude-opus-5-5"


async def test_rule_2_a_read_alone_is_not_a_search(world):
    script = [turn(tu("read_passages", target="katz-1-p6")), keep(), submit(update_skip_reason=SKIP),
              search(), submit(update_skip_reason=SKIP), answer(world)]
    ctx, _ = await run_loop(world, script)
    assert rules(ctx) == ["no_search", None]


async def test_rule_3_nothing_kept_and_no_note(world):
    script = [search(), submit(update_skip_reason=SKIP), keep(), submit(update_skip_reason=SKIP), answer(world)]
    ctx, _ = await run_loop(world, script)
    assert rules(ctx) == ["nothing_kept", None]


async def test_rule_4_refused_once_then_declined(world):
    script = [search(), keep(), submit(), submit(), answer(world)]
    ctx, _ = await run_loop(world, script)
    assert rules(ctx) == ["no_update_check", None]
    band = ctx.of("update_band")[0]
    assert band["outcome"] == "declined" and band["reason"] is None


async def test_two_submits_in_one_turn_are_both_refused(world):
    """P4.16: two submits alone in a turn are both refused by rule 1, before any other rule runs."""
    script = [search(), keep(), turn(tu("submit_answer", out_of_scope=False), tu("submit_answer", out_of_scope=False)),
              submit(), submit(), answer(world)]
    ctx, _ = await run_loop(world, script)
    assert rules(ctx) == ["same_turn", "same_turn", "no_update_check", None]
    assert all(r["content"] == rejection("submit", "rule_1_same_turn") for r in ctx.results("submit_answer")[:2])


async def test_a_submit_with_an_unknown_tool_is_refused(world):
    """P4.16: an unknown tool counts as another call; Claude gets an error for it and the submit is refused."""
    script = [search(), keep(), turn(tu("submit_answer", out_of_scope=False, update_skip_reason=SKIP),
                                     tu("no_such_tool", x=1)),
              submit(update_skip_reason=SKIP), answer(world)]
    ctx, fakes = await run_loop(world, script)
    assert rules(ctx) == ["same_turn", None] and ctx.ended()["state"] == "answered"
    sent = fakes["anthropic"].requests[3]["messages"][-1]["content"]
    assert [b["is_error"] for b in sent if b["type"] == "tool_result"] == [True, True]


async def test_a_split_submit_loses_nothing(world):
    """The paid build tests (Oct 25, test 4): a scope note in one submit and a bare submit in the same turn. Both
    are refused, so neither replaces the other; the single resubmit's note reaches the end."""
    scope = "The corpus holds Supreme Court opinions only; state law is not covered."
    script = [search(), keep(),
              turn(tu("submit_answer", out_of_scope=False, note=scope, update_skip_reason=SKIP),
                   tu("submit_answer", out_of_scope=False)),
              submit(note=scope, update_skip_reason=SKIP), answer(world)]
    ctx, _ = await run_loop(world, script)
    assert rules(ctx) == ["same_turn", "same_turn", None]
    end = ctx.ended()
    assert end["state"] == "answered" and end["scope_note"] == scope
    assert ctx.of("update_band")[0]["outcome"] == "skipped"


async def test_rule_4_waived_while_the_update_check_is_unavailable(world):
    ctx = FakeCtx(update_check_available=False)
    ctx, fakes = await run_loop(world, [search(), keep(), submit(), answer(world)], ctx=ctx)
    assert rules(ctx) == [None]
    band = ctx.of("update_band")[0]
    assert band["outcome"] == "unavailable" and band["reason"] == "no_credit" and band["searches"] == []
    first = fakes["anthropic"].requests[0]["messages"][0]["content"]
    assert "update check is unavailable for this run" in first[1]["text"]
    assert first[-1]["text"].endswith("update check unavailable")


async def test_findings_problems_before_the_copy_guard(world):
    page = ("tr", "Thermal ruling", "2026-09-17", PAGE)
    script = [search(), keep(),
              turn(tu("search_web_updates", query="thermal imaging ruling", start_published_date="2026-06-30")),
              submit(update_findings=[{"statement": COPIED, "sources": ["web-1-1"]},
                                      {"statement": "A statement with no source.", "sources": []}]),
              submit(update_findings=[{"statement": COPIED, "sources": ["web-1-1"]}],
                     update_overview="A sample page describes a ruling."),
              submit(update_findings=[{"statement": "A sample page reports an appeals ruling on thermal scans.",
                                       "sources": ["web-1-1"]}]),
              answer(world)]
    ctx, _ = await run_loop(world, script, exa=[web_reply(page)], page_texts=[COPY_LEAD])
    assert rules(ctx) == ["findings", "copy_guard", None]
    guard = ctx.results("submit_answer")[1]
    assert "own words" in guard["content"] and "web-1-1" in guard["content"] and COPIED not in guard["content"]
    calls = [d for d in ctx.of("tool_call") if d["name"] == "submit_answer"]
    # P4.3: the flagged statement is withheld in the stored and streamed call, the rest exact
    assert calls[1]["input"]["update_findings"][0]["statement"] == WITHHELD
    assert calls[1]["input"]["update_overview"] == "A sample page describes a ruling."
    # and in the findings refusal too, since no page's words are ever stored (contract §1)
    assert calls[0]["input"]["update_findings"][0]["statement"] == WITHHELD
    assert calls[0]["input"]["update_findings"][1]["statement"] == "A statement with no source."
    assert calls[2]["input"]["update_findings"][0]["statement"].startswith("A sample page reports")
    assert ctx.of("update_band")[0]["outcome"] == "found"


async def test_claude_keeps_its_own_input_unchanged(world):
    page = ("tr", "Thermal ruling", "2026-09-17", PAGE)
    script = [search(), keep(), turn(tu("search_web_updates", query="thermal", start_published_date="2026-06-30")),
              submit(update_findings=[{"statement": COPIED, "sources": ["web-1-1"]}]),
              submit(update_findings=[], update_skip_reason=SKIP), answer(world)]
    ctx, fakes = await run_loop(world, script, exa=[web_reply(page)], page_texts=[COPY_LEAD])
    later = fakes["anthropic"].requests[4]["messages"]
    sent = [b for m in later if m["role"] == "assistant" for b in m["content"] if b.get("name") == "submit_answer"]
    assert sent[0]["input"]["update_findings"][0]["statement"] == COPIED      # only events are withheld (P4.3)
    assert ctx.of("update_band")[0]["outcome"] == "nothing_relevant"


async def test_overview_flagged_is_withheld(world):
    page = ("tr", "Thermal ruling", "2026-09-17", PAGE)
    script = [search(), keep(), turn(tu("search_web_updates", query="thermal", start_published_date="2026-06-30")),
              submit(update_findings=[{"statement": "A sample page reports a ruling.", "sources": ["web-1-1"]}],
                     update_overview=COPIED),
              submit(update_findings=[{"statement": "A sample page reports a ruling.", "sources": ["web-1-1"]}]),
              answer(world)]
    ctx, _ = await run_loop(world, script, exa=[web_reply(page)], page_texts=[COPY_LEAD])
    call = [d for d in ctx.of("tool_call") if d["name"] == "submit_answer"][0]
    assert rules(ctx) == ["copy_guard", None]
    assert call["input"]["update_overview"] == WITHHELD
    assert call["input"]["update_findings"][0]["statement"] == "A sample page reports a ruling."


async def test_findings_with_no_search_run(world):
    script = [search(), keep(), submit(update_findings=[{"statement": "x", "sources": ["web-1-1"]}]),
              submit(update_skip_reason=SKIP), answer(world)]
    ctx, _ = await run_loop(world, script)
    assert rules(ctx) == ["findings", None]


async def test_bad_input_is_an_error_result_with_no_rule(world):
    script = [search(), keep(), turn(tu("submit_answer", out_of_scope="no")),
              turn(tu("submit_answer", out_of_scope=True)),           # out of scope needs a note to the visitor
              turn(tu("submit_answer", out_of_scope=False, unknown=1)),
              submit(update_skip_reason=SKIP), answer(world)]
    ctx, _ = await run_loop(world, script)
    res = ctx.results("submit_answer")
    assert [r["submit"] for r in res[:3]] == [{"accepted": False, "rule": None}, {"accepted": False, "rule": "no_note"},
                                              {"accepted": False, "rule": None}]
    assert all(r["is_error"] for r in res[:3])
    assert res[1]["content"] == rejection("submit", "out_of_scope_no_note")     # v1.3


async def test_a_keep_after_a_submit_runs_and_the_submit_is_refused(world):
    """P4.16: the turn's tools run in Claude's order; the keep counts, the submit is refused, every tool_use gets
    its tool_call and tool_result."""
    script = [search(), keep(), turn(tu("submit_answer", out_of_scope=False, update_skip_reason=SKIP),
                                     tu("keep_passages", keep=[{"id": "katz-1-n9", "reason": "late"}])),
              submit(update_skip_reason=SKIP), answer(world)]
    ctx, _ = await run_loop(world, script)
    assert [d["name"] for d in ctx.of("tool_call")][-3:] == ["submit_answer", "keep_passages", "submit_answer"]
    assert [d["name"] for d in ctx.results()][-3:] == ["submit_answer", "keep_passages", "submit_answer"]
    assert rules(ctx) == ["same_turn", None]
    assert ctx.of("composition_started")[0]["documents"] == ["katz-1-p6", "katz-1-n9"]
    assert ctx.results("submit_answer")[-1]["content"] == prompts.message("submit_accepted_answer",
                                                                          passages="2 kept passages")


async def test_the_results_go_back_in_claudes_order(world):
    """A refused submit before a keep: the results return in the order Claude called them."""
    script = [search(), turn(tu("submit_answer", out_of_scope=False),
                             tu("keep_passages", keep=[{"id": "katz-1-p6", "reason": "r"}])),
              submit(update_skip_reason=SKIP), answer(world)]
    ctx, fakes = await run_loop(world, script)
    assert rules(ctx) == ["same_turn", None]                 # P4.16: not alone in its turn
    sent = fakes["anthropic"].requests[2]["messages"][4]["content"]
    asked = fakes["anthropic"].requests[2]["messages"][3]["content"]
    ids = [b["id"] for b in asked if b["type"] == "tool_use"]
    assert [b["tool_use_id"] for b in sent if b["type"] == "tool_result"] == ids


async def test_one_kept_passage_text(world):
    ctx, _ = await run_loop(world, [search(), keep(), submit(update_skip_reason=SKIP), answer(world)])
    assert ctx.results("submit_answer")[0]["content"] == prompts.message("submit_accepted_answer",
                                                                         passages="1 kept passage")


async def test_out_of_scope_accepted_text(world):
    ctx, _ = await run_loop(world, [turn(tu("submit_answer", out_of_scope=True, note="Outside.", update_skip_reason=SKIP))])
    assert ctx.results("submit_answer")[0]["content"] == prompts.message("submit_accepted_note")


async def test_withheld_text_never_reaches_any_event(world):
    page = ("tr", "Thermal ruling", "2026-09-17", PAGE)
    script = [search(), keep(), turn(tu("search_web_updates", query="thermal", start_published_date="2026-06-30")),
              submit(update_findings=[{"statement": COPIED, "sources": ["web-1-1"]}]),
              submit(update_skip_reason=SKIP, update_findings=[]), answer(world)]
    ctx, _ = await run_loop(world, script, exa=[web_reply(page)])
    assert COPIED not in json.dumps(ctx.events) and COPY_LEAD not in json.dumps(ctx.events)
