"""submit_answer's rules in order (contract v2.0 §4.G.3; T1.10 amended by P4.16 and P4.19): rule 1 (alone in its
turn, once), the input check, the note cap, rule 2, rule 3, then `no_note`; no rule 4, no findings check and no copy
guard; the accepted texts, by whether the update step starts."""

import pytest

from api.loop import prompts
from api.loop.prompts import rejection
from tests.loop.support import FakeCtx, cite_block, composition, loop_usage, run_loop, skip_update, tu, turn

pytestmark = pytest.mark.anyio

NOTE = "The corpus holds the Supreme Court's Fourth Amendment opinions, and nothing in it bears on this question."


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


def answer(world, docs=("katz-1-p6",)):
    return composition(cite_block("Text. ", world.corpus, list(docs), docs[0], 0, 0))


def rules(ctx):
    return [d["submit"].get("rule") for d in ctx.results("submit_answer")]


async def test_rule_1_same_turn_as_a_search(world):
    script = [turn(tu("read_passages", target="katz-1-p6"), tu("search_exact", any_of=["booth"]),
                   tu("submit_answer", out_of_scope=False)), keep(), submit()]
    ctx, _ = await run_loop(world, script, update=[skip_update()], comp=[answer(world)])
    assert rules(ctx) == ["same_turn", None]
    refused = ctx.results("submit_answer")[0]
    assert refused["is_error"] and refused["content"] == rejection("submit", "rule_1_same_turn")


async def test_rule_1_comes_before_the_input_check(world):
    script = [turn(tu("read_passages", target="katz-1-p6"),
                   tu("submit_answer", out_of_scope=False, update_findings=[{"statement": "x", "sources": ["web-9-9"]}])),
              search(), keep(), submit()]
    ctx, _ = await run_loop(world, script, update=[skip_update()], comp=[answer(world)])
    assert rules(ctx)[0] == "same_turn"


async def test_a_wrong_step_call_counts_toward_rule_1(world):
    """§4.G.2: a wrong-step call is refused, never counted, but it is a call in the turn, so the submit is refused."""
    script = [search(), keep(), turn(tu("search_web_updates", query="later rulings"),
                                     tu("submit_answer", out_of_scope=False)), submit()]
    ctx, fakes = await run_loop(world, script, update=[skip_update()], comp=[answer(world)])
    assert rules(ctx) == ["same_turn", None]
    web = ctx.results("search_web_updates")[0]
    assert web["wrong_step"] is True and web["web_status"] == "refused_by_us" and "search_no" not in web
    assert fakes["exa"].calls == [] and ctx.of("update_band")[0]["searches"] == []


async def test_a_keep_in_the_same_turn_refuses_the_submit(world):
    """P4.16: a submit must be the turn's only call. The keep runs and counts; the submit is refused."""
    script = [search(), turn(tu("keep_passages", keep=[{"id": "katz-1-p6", "reason": "r"}]),
                             tu("submit_answer", out_of_scope=False)), submit()]
    ctx, fakes = await run_loop(world, script, update=[skip_update()], comp=[answer(world)])
    assert rules(ctx) == ["same_turn", None] and ctx.ended()["state"] == "answered"
    assert ctx.results("keep_passages")[0]["is_error"] is False
    assert ctx.of("composition_started")[0]["documents"] == ["katz-1-p6"]


async def test_rule_2_a_read_alone_is_not_a_search(world):
    script = [turn(tu("read_passages", target="katz-1-p6")), keep(), submit(), search(), submit()]
    ctx, _ = await run_loop(world, script, update=[skip_update()], comp=[answer(world)])
    assert rules(ctx) == ["no_search", None]


async def test_rule_3_nothing_kept_and_no_note(world):
    script = [search(), submit(), keep(), submit()]
    ctx, _ = await run_loop(world, script, update=[skip_update()], comp=[answer(world)])
    assert rules(ctx) == ["nothing_kept", None]


async def test_there_is_no_rule_4(world):
    """P4.19: a submit with no update check is accepted at once; the update step that follows decides."""
    ctx, _ = await run_loop(world, [search(), keep(), submit()], update=[skip_update()], comp=[answer(world)])
    assert rules(ctx) == [None]


async def test_two_submits_in_one_turn_are_both_refused(world):
    """P4.16: two submits alone in a turn are both refused by rule 1, before any other rule runs."""
    script = [search(), keep(), turn(tu("submit_answer", out_of_scope=False), tu("submit_answer", out_of_scope=False)),
              submit()]
    ctx, _ = await run_loop(world, script, update=[skip_update()], comp=[answer(world)])
    assert rules(ctx) == ["same_turn", "same_turn", None]
    assert all(r["content"] == rejection("submit", "rule_1_same_turn") for r in ctx.results("submit_answer")[:2])


async def test_a_submit_with_an_unknown_tool_is_refused(world):
    """P4.16: an unknown tool counts as another call; Claude gets an error for it and the submit is refused."""
    script = [search(), keep(), turn(tu("submit_answer", out_of_scope=False), tu("no_such_tool", x=1)), submit()]
    ctx, fakes = await run_loop(world, script, update=[skip_update()], comp=[answer(world)])
    assert rules(ctx) == ["same_turn", None] and ctx.ended()["state"] == "answered"
    sent = fakes["anthropic"].requests[3]["messages"][-1]["content"]
    assert [b["is_error"] for b in sent if b["type"] == "tool_result"] == [True, True]


async def test_a_split_submit_loses_nothing(world):
    """The paid build tests (Oct 25, test 4): a scope note in one submit and a bare submit in the same turn. Both
    are refused, so neither replaces the other; the single resubmit's note reaches the end."""
    scope = "The corpus holds Supreme Court opinions only; state law is not covered."
    script = [search(), keep(),
              turn(tu("submit_answer", out_of_scope=False, note=scope), tu("submit_answer", out_of_scope=False)),
              submit(note=scope)]
    ctx, _ = await run_loop(world, script, update=[skip_update()], comp=[answer(world)])
    assert rules(ctx) == ["same_turn", "same_turn", None]
    end = ctx.ended()
    assert end["state"] == "answered" and end["scope_note"] == scope


async def test_bad_input_is_an_error_result_with_no_rule(world):
    script = [search(), keep(), turn(tu("submit_answer", out_of_scope="no")),
              turn(tu("submit_answer", out_of_scope=True)),           # out of scope needs a note to the visitor
              turn(tu("submit_answer", out_of_scope=False, unknown=1)),
              # the update fields left submit_answer in v2.0: refused at the input check (§4.G.3)
              turn(tu("submit_answer", out_of_scope=False, update_skip_reason="Not needed.")),
              turn(tu("submit_answer", out_of_scope=False, update_findings=[])),
              submit()]
    ctx, _ = await run_loop(world, script, update=[skip_update()], comp=[answer(world)])
    res = ctx.results("submit_answer")
    assert [r["submit"] for r in res[:5]] == [{"accepted": False, "rule": None}, {"accepted": False, "rule": "no_note"},
                                              {"accepted": False, "rule": None}, {"accepted": False, "rule": None},
                                              {"accepted": False, "rule": None}]
    assert all(r["is_error"] for r in res[:5])
    assert res[1]["content"] == rejection("submit", "out_of_scope_no_note")     # v1.3
    assert "update_skip_reason" in res[3]["content"] and "update_findings" in res[4]["content"]


async def test_the_input_check_comes_before_the_note_cap_and_the_cap_before_rule_2(world):
    long = "n" * 1_001
    script = [turn(tu("submit_answer", out_of_scope="yes", note=long), usage=loop_usage(1, first=True)),
              turn(tu("submit_answer", out_of_scope=False, note=long)), search(), keep(), submit()]
    ctx, _ = await run_loop(world, script, update=[skip_update()], comp=[answer(world)])
    assert rules(ctx) == [None, "note_too_long", None]


async def test_a_keep_after_a_submit_runs_and_the_submit_is_refused(world):
    """P4.16: the turn's tools run in Claude's order; the keep counts, the submit is refused, every tool_use gets
    its tool_call and tool_result."""
    script = [search(), keep(), turn(tu("submit_answer", out_of_scope=False),
                                     tu("keep_passages", keep=[{"id": "katz-1-n9", "reason": "late"}])), submit()]
    ctx, _ = await run_loop(world, script, update=[skip_update()], comp=[answer(world, ("katz-1-p6", "katz-1-n9"))])
    assert [d["name"] for d in ctx.of("tool_call") if d["step"] == "research"][-3:] == \
        ["submit_answer", "keep_passages", "submit_answer"]
    assert [d["name"] for d in ctx.results() if d["step"] == "research"][-3:] == \
        ["submit_answer", "keep_passages", "submit_answer"]
    assert rules(ctx) == ["same_turn", None]
    assert ctx.of("composition_started")[0]["documents"] == ["katz-1-p6", "katz-1-n9"]
    assert ctx.results("submit_answer")[-1]["content"] == prompts.message("update_start", passages="2 kept passages")


async def test_the_results_go_back_in_claudes_order(world):
    """A refused submit before a keep: the results return in the order Claude called them."""
    script = [search(), turn(tu("submit_answer", out_of_scope=False),
                             tu("keep_passages", keep=[{"id": "katz-1-p6", "reason": "r"}])), submit()]
    ctx, fakes = await run_loop(world, script, update=[skip_update()], comp=[answer(world)])
    assert rules(ctx) == ["same_turn", None]                 # P4.16: not alone in its turn
    sent = fakes["anthropic"].requests[2]["messages"][4]["content"]
    asked = fakes["anthropic"].requests[2]["messages"][3]["content"]
    ids = [b["id"] for b in asked if b["type"] == "tool_use"]
    assert [b["tool_use_id"] for b in sent if b["type"] == "tool_result"] == ids


async def test_the_stored_call_is_exactly_what_claude_sent(world):
    """P4.19: research never sees a web page, so its calls are stored as sent, refused or accepted."""
    scope = "Part of this turns on state law."
    script = [search(), keep(), turn(tu("submit_answer", out_of_scope=False, note=scope), tu("search_exact", any_of=["x"])),
              submit(note=scope)]
    ctx, _ = await run_loop(world, script, update=[skip_update()], comp=[answer(world)])
    calls = [d["input"] for d in ctx.of("tool_call") if d["name"] == "submit_answer"]
    assert calls == [{"out_of_scope": False, "note": scope}, {"out_of_scope": False, "note": scope}]


# ---------- the accepted texts (§4.G.3) ----------

async def test_an_accepted_answer_opens_the_update_step(world):
    ctx, fakes = await run_loop(world, [search(), keep(), submit()], update=[skip_update()], comp=[answer(world)])
    text = prompts.message("update_start", passages="1 kept passage")
    assert ctx.results("submit_answer")[0]["content"] == text
    opening = fakes["anthropic"].requests_for("update")[0]["messages"][-1]["content"][0]
    assert opening["content"] == [{"type": "text", "text": text}]


async def test_nothing_found_opens_the_update_step_with_the_note_text(world):
    ctx, fakes = await run_loop(world, [search(), submit(note=NOTE)], update=[skip_update()])
    text = prompts.message("update_start_note")
    assert ctx.results("submit_answer")[0]["content"] == text
    assert fakes["anthropic"].requests_for("update")[0]["messages"][-1]["content"][0]["content"][0]["text"] == text
    assert ctx.ended()["no_sources_reason"] == "nothing_found" and "composition_started" not in ctx.kinds()


async def test_out_of_scope_accepted_text(world):
    ctx, _ = await run_loop(world, [turn(tu("submit_answer", out_of_scope=True, note="Outside."))])
    assert ctx.results("submit_answer")[0]["content"] == prompts.message("submit_accepted_note")


@pytest.mark.parametrize("ctx_kw", [{"update_check_available": False}, {"exa_unavailable": "key_refused"}])
async def test_with_the_update_check_unavailable_the_accepted_texts_are_never_sent(world, ctx_kw):
    ctx, fakes = await run_loop(world, [search(), keep(), submit()], comp=[answer(world)], ctx=FakeCtx(**ctx_kw))
    assert ctx.results("submit_answer")[0]["content"] == prompts.message("submit_accepted_answer",
                                                                         passages="1 kept passage")
    first = fakes["anthropic"].requests[0]["messages"][0]["content"]
    assert len(first) == 2 and first[-1]["text"] == "Round 1 of 12 · 0 kept"     # no unavailable line (§4.G.3)
    ctx2, _ = await run_loop(world, [search(), submit(note=NOTE)], ctx=FakeCtx(**ctx_kw))
    assert ctx2.results("submit_answer")[0]["content"] == prompts.message("submit_accepted_note")
