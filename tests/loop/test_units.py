"""Units of part G: the citation mapping (honesty-critical), P4.3's withholding, the formats, the prompts and the
tool definitions."""

import json
import re

import pytest

from api import settings
from api.errors import ToolInputError
from api.loop import format as fmt
from api.loop import prompts
from api.loop.run import WITHHELD, map_citations, usage_from_raw, withhold_flagged
from api.loop.tools import STRICT_TOOLS, TOOL_NAMES, max_results, strict_optional_count, tools


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
    inp = {"out_of_scope": False, "update_findings": [{"statement": "a", "sources": ["web-1-1"]},
                                                      {"statement": "b", "sources": ["web-1-2"]}],
           "update_overview": "o"}
    shown = withhold_flagged(inp, {1}, False)
    assert shown["update_findings"][0]["statement"] == "a" and shown["update_findings"][1]["statement"] == WITHHELD
    assert shown["update_overview"] == "o" and inp["update_findings"][1]["statement"] == "b"   # input untouched
    assert withhold_flagged(inp, set(), True)["update_overview"] == WITHHELD
    assert WITHHELD == "[statement withheld: it repeated a page's words]"                       # P4.3


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


def test_status_lines_and_unavailable_line():
    assert prompts.status_line(3, 4, searches_counted=2, unavailable=False) == "Round 3 of 12 · 4 kept · update searches 2 of 3"
    assert prompts.status_line(1, 0, searches_counted=0, unavailable=True) == "Round 1 of 12 · 0 kept · update check unavailable"
    assert "Exa refused this site's key" in prompts.unavailable_line("key_refused")


def test_fill_fields_is_one_pass():
    assert prompts.fill_fields("Q: <question>", question="<question> and {{MAX_ROUNDS}}") == "Q: <question> and {{MAX_ROUNDS}}"
    with pytest.raises(KeyError):
        prompts.fill_settings("{{NOT_A_SETTING}}")


def test_tool_definitions():
    ts = tools()
    assert [t["name"] for t in ts] == list(TOOL_NAMES)
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
