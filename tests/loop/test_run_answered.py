"""A whole answered run on the real corpus (contract v2.0 §4.G, §6): research, then the update step and the
composition side by side; every event checked against the schema and the order rules, the requests Claude gets,
the composition documents and the citation mapping."""

import pytest

from api import settings
from api.loop import prompts
from api.loop.run import sort_documents
from tests.loop.support import cite_block, composition, loop_usage, run_loop, tu, turn, update_usage, web_reply

pytestmark = pytest.mark.anyio

PAGE_TEXT = ("Synthetic filler for a sample page about a later ruling on telephone surveillance, invented for this "
             "test and long enough to be seen if it ever leaked into an event. ") * 3
STATEMENT = "A sample page reports a later lower-court ruling on surveillance."
DOCS = ["katz-1-p6", "katz-1-n8"]


def research():
    return [
        turn(tu("search_exact", any_of=['"telephone booth"'], filters={"cases": ["katz"]}, max_results=3),
             tu("read_passages", target="katz-1-p6"), usage=loop_usage(1, first=True)),
        turn(tu("keep_passages", keep=[
                {"id": "katz-1-p6", "reason": "Majority (Stewart): the Amendment protects people, not places."},
                {"id": "katz-1-n8", "reason": "Majority footnote on the parties' formulation."}]),
             usage=loop_usage(2)),
        turn(tu("submit_answer", out_of_scope=False), usage=loop_usage(3)),
    ]


def update():
    return [
        turn(tu("search_web_updates", query="phone booth eavesdropping ruling", start_published_date="2026-06-30"),
             usage=update_usage(0)),
        turn(tu("submit_update", update_findings=[{"statement": STATEMENT, "sources": ["web-1-1"]}],
                update_overview="One sample page describes lower-court activity."), usage=update_usage(1)),
    ]


def answer(world):
    return [composition(
        {"type": "text", "text": "## Short answer\n\n"},
        cite_block("The majority said the Amendment protects people, not places. ", world.corpus, DOCS,
                   "katz-1-p6", 2, 3),
        cite_block("A footnote addresses the formulation. ", world.corpus, DOCS, "katz-1-n8", 0, 0),
    )]


def scripts(world):
    """The answered run's three scripts, for other tests to reuse."""
    return {"script": research(), "update": update(), "comp": answer(world)}


def exa():
    return [web_reply(("later", "Later ruling", "2026-09-12T00:00:00Z", PAGE_TEXT))]


async def run_answered(world):
    return await run_loop(world, **scripts(world), exa=exa(), page_texts=[PAGE_TEXT[:80]])


async def test_answered_run_events_and_end(world):
    ctx, fakes = await run_answered(world)
    end = ctx.ended()
    assert end["state"] == "answered" and end["answer_end"] == "complete" and end["stop_kind"] is None
    assert end["rounds"] == 3 and end["no_sources_reason"] is None and end["note"] is None and end["stop_kinds"] == []
    started = ctx.of("run_started")[0]
    assert started["limits"] == {"rounds": 12, "loop_input_tokens": 2_000_000, "loop_output_tokens": 16_000,
                                 "update_rounds": 8, "update_input_tokens": 2_000_000, "update_output_tokens": 6_000,
                                 "update_searches": 5, "composition_max_tokens": 16_000, "deadline_s": 600}
    assert started["models"] == {"loop": "claude-sonnet-5-5", "update": "claude-sonnet-5-5",
                                 "composition": "claude-sonnet-5-5"}
    assert started["coverage"] == world.corpus.coverage and started["corpus_label"] == "full"
    research_lines = [d["status_line"] for d in ctx.of("round_started") if d["step"] == "research"]
    assert research_lines == ["Round 1 of 12 · 0 kept", "Round 2 of 12 · 0 kept", "Round 3 of 12 · 2 kept"]
    update_lines = [d["status_line"] for d in ctx.of("round_started") if d["step"] == "update"]
    assert update_lines == ["Update step · round 1 of 8 · update check not yet run",
                            "Update step · round 2 of 8 · update searches 1 of 5"]
    assert ctx.of("update_started") == [{"kept": ["katz-1-p6", "katz-1-n8"]}]
    assert ctx.of("update_ended") == [{"end": "submitted", "stop_kind": None, "failure_reason": None, "rounds": 2,
                                       "searches": 1}]
    band = ctx.of("update_band")[0]
    assert band["outcome"] == "found" and band["reason"] is None
    assert band["findings"] == [{"statement": STATEMENT, "sources": ["web-1-1"]}]
    assert band["overview"] == "One sample page describes lower-court activity."
    assert band["searches"][0]["status"] == "ok" and band["searches"][0]["returned"] == 1
    assert band["searches"][0]["params"]["query"] == "phone booth eavesdropping ruling"
    assert band["pages"][0]["id"] == "web-1-1" and "text" not in band["pages"][0]
    # research's calls are 1 to 3; the update task is created first, so it takes 4 and the composition 5
    comp = ctx.of("composition_started")[0]
    assert comp["documents"] == ["katz-1-p6", "katz-1-n8"] and comp["call_no"] == 5
    by_call = {p["call_no"]: p["purpose"] for p in ctx.of("paid_call") if "call_no" in p}
    assert by_call == {1: "loop", 2: "loop", 3: "loop", 4: "update", 5: "composition", 6: "update"}
    blocks = ctx.of("answer_block")
    assert blocks[1]["citations"][0]["first_sentence"] == 2 and blocks[1]["citations"][0]["last_sentence"] == 3
    assert blocks[1]["citations"][0]["path"] == "content[2]"      # the thinking block is content[0]
    assert ctx.of("checks")[0]["quotations_checked"] == 0
    # the accepted submit_answer's result is the update_start text Claude is sent; submit_update's is never sent
    sub = ctx.results("submit_answer")[0]
    assert sub["step"] == "research" and sub["content"] == prompts.message("update_start", passages="2 kept passages")
    assert ctx.results("submit_update")[0]["content"] == prompts.message("submit_update_accepted")
    totals = end["totals"]["claude"]["cost_usd"]
    assert totals["loop"] > 0 and totals["update"] > 0 and totals["composition"] > 0


async def test_requests_claude_gets(world):
    ctx, fakes = await run_answered(world)
    research_reqs = fakes["anthropic"].requests_for("research")
    update_reqs = fakes["anthropic"].requests_for("update")
    (comp,) = fakes["anthropic"].requests_for("composition")
    first, second, third = research_reqs
    assert first["model"] == "claude-sonnet-5-5" and first["thinking"] == {"type": "adaptive"}
    assert first["output_config"] == {"effort": "high"} and first["cache_control"] == {"type": "ephemeral"}
    assert first["system"][0]["cache_control"] == {"type": "ephemeral", "ttl": "1h"}
    assert "{{" not in first["system"][0]["text"] and world.corpus.catalog_text in first["system"][0]["text"]
    assert first["max_tokens"] == settings.LOOP_OUTPUT_BUDGET.value
    assert second["max_tokens"] == settings.LOOP_OUTPUT_BUDGET.value - 400      # what remains of the 16,000
    assert [t["name"] for t in first["tools"]] == ["search_meaning", "search_exact", "read_passages", "keep_passages",
                                                    "submit_answer", "search_web_updates", "submit_update"]
    assert "tool_choice" not in first
    # the first user message: the question, then the status line, and nothing else (§4.G.3)
    m0 = first["messages"][0]
    assert m0["role"] == "user" and len(m0["content"]) == 2
    assert m0["content"][0]["text"] == prompts.message("first_message", question=ctx.question)
    assert m0["content"][1]["text"] == "Round 1 of 12 · 0 kept"
    # history is append-only: each request extends the previous one exactly (thinking blocks passed back unchanged)
    assert second["messages"][:1] == first["messages"]
    assert third["messages"][:3] == second["messages"]
    results = second["messages"][2]["content"]
    assert [b["type"] for b in results] == ["tool_result", "tool_result", "text"]
    assert results[-1]["text"] == "Round 2 of 12 · 0 kept"
    # the update step continues the conversation: the accepted submit's result, then its own status line
    u1, u2 = update_reqs
    assert u1["messages"][:5] == third["messages"] and len(u1["messages"]) == 7
    assert u1["messages"][5]["role"] == "assistant" and u1["messages"][5]["content"][-1]["name"] == "submit_answer"
    opening = u1["messages"][-1]["content"]
    assert opening[0]["type"] == "tool_result" and "is_error" not in opening[0]
    assert opening[0]["content"][0]["text"] == prompts.message("update_start", passages="2 kept passages")
    assert opening[1] == {"type": "text", "text": "Update step · round 1 of 8 · update check not yet run"}
    assert u1["max_tokens"] == settings.UPDATE_OUTPUT_BUDGET.value
    assert u2["max_tokens"] == settings.UPDATE_OUTPUT_BUDGET.value - 300
    # the page text reached Claude, inside its data markers, and nowhere in the events
    web_result = u2["messages"][-1]["content"][0]["content"][0]["text"]
    assert PAGE_TEXT[:80] in web_result and "<web_page_text" in web_result
    # composition: Sonnet (P4.20), uncached, the documents of our sentences, then the question and coverage
    assert comp["model"] == "claude-sonnet-5-5" and comp["max_tokens"] == 16_000
    assert comp["output_config"] == {"effort": "high"} and "cache_control" not in comp and "tools" not in comp
    docs = comp["messages"][0]["content"]
    p = world.corpus.passages["katz-1-p6"]
    assert docs[0]["source"]["content"] == [{"type": "text", "text": p.text[a:b]} for a, b in p.sentences]
    assert docs[0]["citations"] == {"enabled": True}
    assert "Keep reason" in docs[0]["context"] and "katz-1-p6" in docs[0]["context"]
    assert "[n. " not in "".join(b["text"] for b in docs[0]["source"]["content"])   # no markers in composition text
    assert docs[-1]["type"] == "text" and "Coverage:" in docs[-1]["text"]
    # deadlines: research and the update step the loop's call deadline, the composition its own
    assert fakes["anthropic"].deadlines.count(settings.COMPOSITION_CALL_DEADLINE_S.value) == 1


async def test_loop_text_has_markers_and_attached_footnotes(world):
    ctx, fakes = await run_answered(world)
    read = next(d for d in ctx.results("read_passages"))
    assert read["read"] == ["katz-1-p6"] and read["target"] == "katz-1-p6"
    assert "[n. " in read["content"] and "[katz-1-n9] n. " in read["content"]
    assert "(the passage you asked for)" in read["content"]
    # every passage sent gets an event, attached footnotes included
    sent = {e["data"]["id"] for e in ctx.events if e["kind"] == "passage"}
    assert {"katz-1-p6", "katz-1-n8", "katz-1-n9"} <= sent


def test_documents_in_decision_then_reading_order(world):
    ids = ["carpenter-1-n3", "katz-3-p2", "carpenter-1-p25", "katz-1-p6", "smith-1-p16"]
    assert sort_documents(ids, world.corpus) == ["katz-1-p6", "katz-3-p2", "smith-1-p16", "carpenter-1-p25",
                                                  "carpenter-1-n3"]
