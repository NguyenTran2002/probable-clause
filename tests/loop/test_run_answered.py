"""A whole answered run on the real corpus (contract §4.G, §6): every event checked against the schema and the
order rules, the request Claude gets, the composition documents and the citation mapping."""

import pytest

from api import settings
from api.loop.run import sort_documents
from tests.loop.support import cite_block, composition, loop_usage, run_loop, tu, turn, web_reply

pytestmark = pytest.mark.anyio

PAGE_TEXT = ("Synthetic filler for a sample page about a later ruling on telephone surveillance, invented for this "
             "test and long enough to be seen if it ever leaked into an event. ") * 3


def script(world, documents=None):
    docs = documents or ["katz-1-p6", "katz-1-n8"]
    return [
        turn(tu("search_exact", any_of=['"telephone booth"'], filters={"cases": ["katz"]}, max_results=3),
             tu("read_passages", target="katz-1-p6"), usage=loop_usage(1, first=True)),
        turn(tu("keep_passages", keep=[
                {"id": "katz-1-p6", "reason": "Majority (Stewart): the Amendment protects people, not places."},
                {"id": "katz-1-n8", "reason": "Majority footnote on the parties' formulation."}]),
             tu("search_web_updates", query="phone booth eavesdropping ruling", start_published_date="2026-06-30"),
             usage=loop_usage(2)),
        turn(tu("submit_answer", out_of_scope=False,
                update_findings=[{"statement": "A sample page reports a later lower-court ruling on surveillance.",
                                  "sources": ["web-1-1"]}],
                update_overview="One sample page describes lower-court activity."), usage=loop_usage(3)),
        composition(
            {"type": "text", "text": "## Short answer\n\n"},
            cite_block("The majority said the Amendment protects people, not places. ", world.corpus, docs,
                       "katz-1-p6", 2, 3),
            cite_block("A footnote addresses the formulation. ", world.corpus, docs, "katz-1-n8", 0, 0),
        ),
    ]


async def test_answered_run_events_and_end(world):
    ctx, fakes = await run_loop(world, script(world), exa=[web_reply(("later", "Later ruling", "2026-09-12T00:00:00Z", PAGE_TEXT))],
                                page_texts=[PAGE_TEXT[:80]])
    end = ctx.ended()
    assert end["state"] == "answered" and end["answer_end"] == "complete" and end["stop_kind"] is None
    assert end["rounds"] == 3 and end["no_sources_reason"] is None and end["note"] is None
    started = ctx.of("run_started")[0]
    assert started["limits"] == {"rounds": 12, "input_tokens": 400_000, "output_tokens": 20_000, "update_searches": 3,
                                 "deadline_s": 600}
    assert started["models"] == {"loop": "claude-sonnet-5-5", "composition": "claude-opus-5-5"}
    assert started["coverage"] == world.corpus.coverage and started["corpus_label"] == "full"
    statuses = [d["status_line"] for d in ctx.of("round_started")]
    assert statuses == ["Round 1 of 12 · 0 kept · update check not yet run",
                        "Round 2 of 12 · 0 kept · update check not yet run",
                        "Round 3 of 12 · 2 kept · update searches 1 of 3"]
    band = ctx.of("update_band")[0]
    assert band["outcome"] == "found" and band["reason"] is None
    assert band["findings"] == [{"statement": "A sample page reports a later lower-court ruling on surveillance.",
                                 "sources": ["web-1-1"]}]
    assert band["searches"][0]["status"] == "ok" and band["searches"][0]["returned"] == 1
    assert band["searches"][0]["params"]["query"] == "phone booth eavesdropping ruling"
    assert band["pages"][0]["id"] == "web-1-1" and "text" not in band["pages"][0]
    comp = ctx.of("composition_started")[0]
    assert comp["documents"] == ["katz-1-p6", "katz-1-n8"] and comp["call_no"] == 4
    blocks = ctx.of("answer_block")
    assert blocks[1]["citations"][0]["first_sentence"] == 2 and blocks[1]["citations"][0]["last_sentence"] == 3
    assert blocks[1]["citations"][0]["path"] == "content[2]"      # the thinking block is content[0]
    assert ctx.of("checks")[0]["quotations_checked"] == 0


async def test_requests_claude_gets(world):
    ctx, fakes = await run_loop(world, script(world), exa=[web_reply(("later", "Later ruling", "2026-09-12", PAGE_TEXT))],
                                page_texts=[PAGE_TEXT[:80]])
    reqs = fakes["anthropic"].requests
    first, second, third, comp = reqs
    assert first["model"] == "claude-sonnet-5-5" and first["thinking"] == {"type": "adaptive"}
    assert first["output_config"] == {"effort": "high"} and first["cache_control"] == {"type": "ephemeral"}
    assert first["system"][0]["cache_control"] == {"type": "ephemeral", "ttl": "1h"}
    assert "{{" not in first["system"][0]["text"] and world.corpus.catalog_text in first["system"][0]["text"]
    assert first["max_tokens"] == settings.LOOP_OUTPUT_BUDGET.value
    assert second["max_tokens"] == settings.LOOP_OUTPUT_BUDGET.value - 400      # what remains of the 8,000
    assert [t["name"] for t in first["tools"]] == ["search_meaning", "search_exact", "read_passages", "keep_passages",
                                                    "search_web_updates", "submit_answer"]
    assert "tool_choice" not in first
    # the first user message: the question, then the status line
    m0 = first["messages"][0]
    assert m0["role"] == "user" and m0["content"][0]["text"].startswith("The visitor's question:\n\n")
    assert m0["content"][-1]["text"] == "Round 1 of 12 · 0 kept · update check not yet run"
    # history is append-only: each request extends the previous one exactly (thinking blocks passed back unchanged)
    assert second["messages"][:1] == first["messages"]
    assert third["messages"][:3] == second["messages"]
    assert second["messages"][1]["content"][0] == {"type": "thinking", "thinking": "", "signature": "sig-2"} or \
        second["messages"][1]["content"][0]["type"] == "thinking"
    results = second["messages"][2]["content"]
    assert [b["type"] for b in results] == ["tool_result", "tool_result", "text"]
    assert results[-1]["text"] == "Round 2 of 12 · 0 kept · update check not yet run"
    # the page text reached Claude, inside its data markers, and nowhere in the events
    web_result = third["messages"][4]["content"][1]["content"][0]["text"]
    assert PAGE_TEXT[:80] in web_result and "<web_page_text" in web_result
    # composition: Opus, uncached, the documents of our sentences, then the question and coverage
    assert comp["model"] == "claude-opus-5-5" and comp["max_tokens"] == 12_000
    assert comp["output_config"] == {"effort": "high"} and "cache_control" not in comp
    docs = comp["messages"][0]["content"]
    p = world.corpus.passages["katz-1-p6"]
    assert docs[0]["source"]["content"] == [{"type": "text", "text": p.text[a:b]} for a, b in p.sentences]
    assert docs[0]["citations"] == {"enabled": True}
    assert "Keep reason" in docs[0]["context"] and "katz-1-p6" in docs[0]["context"]
    assert "[n. " not in "".join(b["text"] for b in docs[0]["source"]["content"])   # no markers in composition text
    assert docs[-1]["type"] == "text" and "Coverage:" in docs[-1]["text"]


async def test_loop_text_has_markers_and_attached_footnotes(world):
    ctx, fakes = await run_loop(world, script(world), exa=[web_reply(("later", "Later ruling", "2026-09-12", PAGE_TEXT))],
                                page_texts=[PAGE_TEXT[:80]])
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
