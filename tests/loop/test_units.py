"""Units of part G: the citation mapping (honesty-critical), P4.3's withholding and the guard's string walk, the
formats, the prompts, the tool definitions and the fake's per-step scripts (contract v2.0 §12)."""

import json
import re

import pytest

from api import settings
from api.errors import ToolInputError
from api.loop import format as fmt
from api.loop import prompts
from api.loop.run import WITHHELD, map_citations, texts_in, usage_from_raw, withhold_flagged, withhold_texts
from api.loop.tools import RESEARCH_TOOLS, STRICT_TOOLS, TOOL_NAMES, UPDATE_TOOLS, max_results, strict_optional_count, tools


def cite(di, s, e, text="", kind="content_block_location"):
    return {"type": kind, "cited_text": text, "document_index": di, "document_title": "t",
            "start_block_index": s, "end_block_index": e}


def sl(world, pid, first, last):
    p = world.corpus.passages[pid]
    return p.text[p.sentences[first][0]:p.sentences[last][1]]


def test_citation_end_index_is_exclusive_and_ours_inclusive(world):
    docs = ["katz-1-p6", "katz-1-n8"]
    exact = sl(world, "katz-1-p6", 2, 4)
    out, dropped, mismatched = map_citations({"text": "x", "citations": [cite(0, 2, 5, exact)]}, docs, world.corpus, 7, 3)
    assert (dropped, mismatched) == (0, 0)
    assert out == [{"passage_id": "katz-1-p6", "first_sentence": 2, "last_sentence": 4, "cited_text": exact,
                    "call_no": 7, "path": "content[3]"}]


def test_single_sentence_citation(world):
    out, _, _ = map_citations({"citations": [cite(0, 0, 1, sl(world, "katz-1-p6", 0, 0))]}, ["katz-1-p6"],
                              world.corpus, 1, 0)
    assert (out[0]["first_sentence"], out[0]["last_sentence"]) == (0, 0)


def test_document_index_maps_to_the_documents_order(world):
    docs = ["katz-1-p6", "katz-1-n8", "smith-1-p16"]
    cits = [cite(2, 0, 1, sl(world, "smith-1-p16", 0, 0)), cite(1, 0, 1, sl(world, "katz-1-n8", 0, 0)),
            cite(0, 0, 1, sl(world, "katz-1-p6", 0, 0))]
    out, dropped, mismatched = map_citations({"citations": cits}, docs, world.corpus, 1, 0)
    assert [c["passage_id"] for c in out] == ["smith-1-p16", "katz-1-n8", "katz-1-p6"] and not dropped + mismatched


def test_a_citation_whose_text_disagrees_is_not_attached(world, caplog):
    """v1.3: compared with spacing collapsed; a disagreement is a mapping fault, logged with kind and IDs only."""
    import logging
    caplog.set_level(logging.ERROR)
    docs = ["katz-1-p6"]
    other = sl(world, "katz-1-p6", 2, 2)
    out, dropped, mismatched = map_citations({"citations": [cite(0, 1, 2, other)]}, docs, world.corpus, 1, 0)
    assert out == [] and (dropped, mismatched) == (0, 1)
    msg = "\n".join(r.getMessage() for r in caplog.records if r.levelno >= logging.ERROR)
    assert "mapping fault" in msg and "katz-1-p6" in msg and other[:30] not in msg
    # spacing aside, the same text is a match
    spaced = "  " + sl(world, "katz-1-p6", 1, 1).replace(" ", "\n ", 3) + " "
    out, _, mismatched = map_citations({"citations": [cite(0, 1, 2, spaced)]}, docs, world.corpus, 1, 0)
    assert mismatched == 0 and out[0]["cited_text"] == sl(world, "katz-1-p6", 1, 1)


@pytest.mark.parametrize("c", [
    cite(2, 0, 1),                         # no such document
    cite(-1, 0, 1),
    cite(0, 0, 0),                         # an empty range
    cite(0, 3, 2),
    cite(0, 0, 99),                        # past the last sentence
    cite(0, -1, 1),
    cite(0, 0, 1, kind="char_location"),   # not a custom-content citation
    {"type": "content_block_location", "document_index": "0", "start_block_index": 0, "end_block_index": 1},
    {"type": "content_block_location", "document_index": True, "start_block_index": 0, "end_block_index": 1},
])
def test_citations_that_do_not_point_inside_a_document_are_dropped(world, c):
    out, dropped, mismatched = map_citations({"citations": [c]}, ["katz-1-p6", "katz-1-n8"], world.corpus, 1, 0)
    assert out == [] and dropped == 1 and mismatched == 0


def test_last_sentence_citation(world):
    p = world.corpus.passages["katz-1-p6"]
    n = len(p.sentences)
    out, dropped, _ = map_citations({"citations": [cite(0, n - 1, n, sl(world, "katz-1-p6", n - 1, n - 1))]},
                                    ["katz-1-p6"], world.corpus, 1, 0)
    assert dropped == 0 and out[0]["last_sentence"] == n - 1 and out[0]["cited_text"].endswith(p.text[-10:])


def test_withholding_replaces_only_flagged_statements():
    inp = {"update_findings": [{"statement": "a", "sources": ["web-1-1"]}, {"statement": "b", "sources": ["web-1-2"]}],
           "update_overview": "o", "update_skip_reason": "s"}
    shown = withhold_flagged(inp, {1}, False)
    assert shown["update_findings"][0]["statement"] == "a" and shown["update_findings"][1]["statement"] == WITHHELD
    assert shown["update_overview"] == "o" and inp["update_findings"][1]["statement"] == "b"   # input untouched
    assert withhold_flagged(inp, set(), True)["update_overview"] == WITHHELD
    assert withhold_flagged(inp, set(), False, skip_reason_flagged=True)["update_skip_reason"] == WITHHELD
    assert inp["update_skip_reason"] == "s"
    assert WITHHELD == "[statement withheld: it repeated a page's words]"                       # P4.3


def test_the_guard_walks_every_text_at_any_depth_keys_included():
    inp = {"keep": [{"id": "katz-1-p6", "reason": "r"}], "n": 3, "flag": True, "filters": {"none_of": ["x", "y"]},
           "note": None}
    assert texts_in(inp) == ["keep", "id", "katz-1-p6", "reason", "r", "n", "flag", "filters", "none_of", "x", "y",
                             "note"]
    shown = withhold_texts(inp, {4, 10})
    assert shown == {"keep": [{"id": "katz-1-p6", "reason": WITHHELD}], "n": 3, "flag": True,
                     "filters": {"none_of": ["x", WITHHELD]}, "note": None}
    assert inp["keep"][0]["reason"] == "r" and list(shown) == list(inp)                   # a copy, keys in order
    assert texts_in("a lone string") == ["a lone string"] and withhold_texts("t", {0}) == WITHHELD
    # a flagged key is numbered within the input, and never collides with a key Claude sent
    assert withhold_texts({"[field withheld 1]": 1, "k": 2}, {1}) == {"[field withheld 1]": 1, "[field withheld 2]": 2}


def test_usage_from_raw():
    u = usage_from_raw({"input_tokens": 10, "cache_creation_input_tokens": 300, "cache_read_input_tokens": 7,
                        "cache_creation": {"ephemeral_5m_input_tokens": 100, "ephemeral_1h_input_tokens": 200},
                        "output_tokens": 5}, "claude-sonnet-5-5")
    assert (u.input_tokens, u.cache_write_5m_tokens, u.cache_write_1h_tokens, u.cache_read_tokens, u.output_tokens) == \
        (10, 100, 200, 7, 5) and not u.estimated
    # writes the API did not attribute to a TTL are counted at the dearer 1-hour rate
    u = usage_from_raw({"input_tokens": 1, "cache_creation_input_tokens": 50, "output_tokens": 0}, "claude-sonnet-5-5")
    assert u.cache_write_1h_tokens == 50


def test_header_per_curiam_and_unknown_joiners(world):
    pc = world.corpus.passages["clinton-1-p1"]
    assert fmt.authors_text(pc) == "per curiam" and fmt.joiners_text(pc) == "per curiam"
    katz = world.corpus.passages["katz-1-p6"]                  # joined_by_source "not printed", none listed
    assert katz.joined_by == () and katz.joined_by_source == "not printed"
    assert "unknown" in fmt.joiners_text(katz) and "no one" not in fmt.joiners_text(katz)
    assert fmt.joiners_text(world.corpus.passages["katz-3-p1"]) == "joined by no one"            # heading, none
    assert fmt.joiners_text(world.corpus.passages["carpenter-1-p1"]).startswith("joined by Ginsburg")
    assert fmt.authors_text(world.corpus.passages["goldman-2-p1"]) == "Stone and Frankfurter"


def test_slip_pages_and_section_in_headers(world):
    c = world.corpus.passages["chatrie-1-p26"]
    assert "slip page" in fmt.header(c)
    k = world.corpus.passages["carpenter-1-p25"]
    assert "section III" in fmt.header(k) and "paragraph 25 of 52" in fmt.header(k)
    n = world.corpus.passages["carpenter-1-n3"]
    assert "footnote 3 (footnote 3 of 5 in this opinion), cited in carpenter-1-p25" in fmt.header(n)


def test_document_block_and_context(world):
    p = world.corpus.passages["katz-3-p2"]
    d = fmt.document_block(p, "Harlan's test.")
    assert d["title"] == "Katz v. United States (1967), Harlan, concurrence"
    assert "".join(b["text"] for b in d["source"]["content"]) == p.text
    assert len(d["source"]["content"]) == len(p.sentences)
    for needle in ("ID katz-3-p2", "389 U.S. 347", "decided 1967-12-18", "concurrence", "Harlan", "joined by no one",
                   "Keep reason", "Harlan's test."):
        assert needle in d["context"]


def test_loop_system_prompt_is_filled(world):
    s = prompts.loop_system(world.corpus)
    assert not re.search(r"\{\{\w+\}\}", s)
    assert "The corpus holds 32 Supreme Court cases" in s
    assert "the latest decision in the full pull is 2026-06-29" in s
    assert s.endswith(world.corpus.catalog_text)
    assert f"Round 5 of {settings.MAX_ROUNDS.value}" in s


def test_status_lines():
    """Contract v2.0 §4.G.3 and §4.G.4: research's line has no update count; the update step has its own."""
    assert prompts.status_line(3, 4) == "Round 3 of 12 · 4 kept"
    assert prompts.status_line_update(1, searches_counted=0, unavailable=False) == \
        "Update step · round 1 of 8 · update check not yet run"
    assert prompts.status_line_update(2, searches_counted=2, unavailable=False) == \
        "Update step · round 2 of 8 · update searches 2 of 5"
    assert prompts.status_line_update(3, searches_counted=1, unavailable=True) == \
        "Update step · round 3 of 8 · update check unavailable"
    assert prompts.kept_passages_text(1) == "1 kept passage" and prompts.kept_passages_text(0) == "0 kept passages"


def test_fill_fields_is_one_pass():
    assert prompts.fill_fields("Q: <question>", question="<question> and {{MAX_ROUNDS}}") == "Q: <question> and {{MAX_ROUNDS}}"
    with pytest.raises(KeyError):
        prompts.fill_settings("{{NOT_A_SETTING}}")


def test_tool_definitions():
    ts = tools()
    assert [t["name"] for t in ts] == list(TOOL_NAMES) == ["search_meaning", "search_exact", "read_passages",
                                                           "keep_passages", "submit_answer", "search_web_updates",
                                                           "submit_update"]
    assert RESEARCH_TOOLS | UPDATE_TOOLS == set(TOOL_NAMES) and not RESEARCH_TOOLS & UPDATE_TOOLS
    assert ts == tools() and ts is not tools()               # one list, the same every time, never shared
    submit = next(t for t in ts if t["name"] == "submit_answer")["input_schema"]
    assert set(submit["properties"]) == {"out_of_scope", "note"} and submit["required"] == ["out_of_scope"]
    upd = next(t for t in ts if t["name"] == "submit_update")["input_schema"]
    assert list(upd["properties"]) == ["update_findings", "update_overview", "update_skip_reason"]
    assert "required" not in upd
    text = json.dumps(ts)
    assert "{{" not in text and "<" not in text.replace("<n>", "").replace("<search>", "")
    descriptions = json.loads((prompts.PROMPTS_DIR / "tools.json").read_text())
    for t in ts:
        assert t["description"] == prompts.fill_settings(descriptions[t["name"]]["description"])
        assert t["input_schema"]["additionalProperties"] is False
    assert {t["name"] for t in ts if t.get("strict")} == set(STRICT_TOOLS)
    assert strict_optional_count(ts) <= 24
    # strict schemas carry no numeric or length constraints (T3.7)
    banned = {"minimum", "maximum", "minLength", "maxLength", "maxItems", "multipleOf", "pattern"}

    def keys(o):
        if isinstance(o, dict):
            for k, v in o.items():
                yield k
                yield from keys(v)
        elif isinstance(o, list):
            for v in o:
                yield from keys(v)
    for t in ts:
        if t.get("strict"):
            assert not banned & set(keys(t["input_schema"]))
    filters = ts[0]["input_schema"]["properties"]["filters"]
    assert filters["properties"]["opinion_types"]["items"]["enum"] == ["majority", "plurality", "concurrence", "dissent"]
    assert ts[0]["input_schema"]["required"] == ["query"] and "required" not in ts[1]["input_schema"]


def test_max_results_clamp():
    assert max_results(None) == 8 and max_results(0) == 1 and max_results(99) == 10 and max_results(5.0) == 5
    for bad in ("5", 5.5, True, float("nan")):
        with pytest.raises(ToolInputError):
            max_results(bad)


def test_per_curiam_only_where_the_manifest_says_so(world):
    """P1.18: an empty author list is "per curiam" only when joined_by_source says so; otherwise not guessed."""
    from dataclasses import replace
    p = replace(world.corpus.passages["katz-1-p6"], authors=(), joined_by_source="heading")
    assert fmt.authors_text(p) == "author not given"
    assert "per curiam" not in fmt.header(p) and "per curiam" not in fmt.document_title(p)
    pc = world.corpus.passages["clinton-1-p1"]
    assert fmt.document_title(pc) == "Clinton v. Virginia (1964), per curiam, majority"


# ---------- the fake's per-step scripts (contract v2.0 §12) ----------

async def _drain(fake, step, on_block=None):
    return await fake.stream({"model": "m", "max_tokens": 10, "messages": []}, 1.0, on_block, step=step)


@pytest.mark.anyio
async def test_the_fake_keeps_one_script_per_step_and_records_each_request_s_step():
    from api.loop.streamer import FakeAnthropic, FakeTurn
    fake = FakeAnthropic([FakeTurn(content=[{"type": "text", "text": "r"}])])
    fake.push(FakeTurn(content=[{"type": "text", "text": "u"}]), step="update")
    fake.push(FakeTurn(content=[{"type": "text", "text": "c"}]), step="composition")
    fake.push(FakeTurn(content=[{"type": "text", "text": "r2"}]))                 # no step: research
    assert fake.left() == {"research": 2, "update": 1, "composition": 1}
    assert (await _drain(fake, "composition")).content[0]["text"] == "c"
    assert (await _drain(fake, "update")).content[0]["text"] == "u"
    assert (await _drain(fake, "research")).content[0]["text"] == "r"
    assert [r.step for r in fake.requests] == ["composition", "update", "research"]
    assert fake.requests[0] == {"model": "m", "max_tokens": 10, "messages": []}      # the request as sent, a dict
    assert len(fake.requests_for("update")) == 1 and fake.left() == {"research": 1}
    with pytest.raises(AssertionError):
        await _drain(fake, "update")
    with pytest.raises(ValueError):
        fake.push(FakeTurn(content=[]), step="nowhere")


@pytest.mark.anyio
async def test_the_fake_yields_before_each_block(monkeypatch):
    import asyncio

    from api.loop.streamer import FakeAnthropic, FakeTurn
    yields = []
    real = asyncio.sleep

    async def counting(t, *a):
        yields.append(t)
        await real(t, *a)

    monkeypatch.setattr("api.loop.streamer.asyncio.sleep", counting)
    fake = FakeAnthropic([FakeTurn(content=[{"type": "thinking", "thinking": "", "signature": "s"},
                                            {"type": "text", "text": "a"}, {"type": "text", "text": "b"}])])
    seen = []
    await _drain(fake, "research", lambda i, b: seen.append(i))
    assert yields == [0, 0, 0] and seen == [1, 2]


@pytest.mark.anyio
async def test_a_cancelled_fake_stream_carries_what_it_streamed():
    import asyncio

    from api.loop.streamer import FakeAnthropic, FakeTurn, partial_of, raw_usage
    hold = asyncio.Event()
    fake = FakeAnthropic(composition=[FakeTurn(content=[{"type": "text", "text": "x" * 40}, {"type": "text", "text": "y"}],
                                               partial_usage=raw_usage(900, output=1))])

    async def on_block(i, b):
        if i == 1:
            await hold.wait()

    task = asyncio.create_task(_drain(fake, "composition", on_block))
    for _ in range(10):
        await asyncio.sleep(0)
    task.cancel()
    with pytest.raises(asyncio.CancelledError) as e:
        await task
    raw, chars, started = partial_of(e.value)
    assert raw["input_tokens"] == 900 and chars == 41 and started is True
    assert partial_of(asyncio.CancelledError()) == (None, 0, False)
