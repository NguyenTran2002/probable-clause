"""Consistency tests for the frontend mock's fixtures (contract §12, P0.3).

tests/fixtures/make_fixtures.py writes tests/fixtures/events/*.json (one run's events each, contract §11.2) and
tests/fixtures/http/*.json (contract §5). The schema test (test_events_schema.py) validates each event's shape; these
tests check what a schema cannot: the order rules of contract §6, that every citation is the exact slice of its
passage, that the totals are the sum of the stream's paid calls, that the checks event is what `check_answer` makes
of the stream's own blocks, that no web page text is anywhere, and that the set as a whole covers every state,
stop kind and band outcome the contract defines.
"""

import json
import re
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from api import settings
from api.checks import check_answer
from api.corpus.store import Corpus
from api.state.prices import PRICE_TABLE, price, price_sources
from api.types import Usage

ROOT = Path(__file__).resolve().parents[2]
EVENT_FILES = sorted((ROOT / "tests" / "fixtures" / "events").glob("*.json"))
HTTP_FILES = sorted((ROOT / "tests" / "fixtures" / "http").glob("*.json"))
SCHEMA = json.loads((ROOT / "contracts" / "events.schema.json").read_text())
CHICAGO = ZoneInfo(str(settings.TIME_ZONE.value))
WITHHELD = "[statement withheld: it repeated a page's words]"
RUN_ID = re.compile(r"^[A-Za-z0-9_-]{1,128}$")
PLACEHOLDER = re.compile(r"^\[page text: \d+ characters, not stored\]$")
OPEN_BLOCK = re.compile(r"<web_page_text[^>]*>\n(.*?)\n</web_page_text>", re.S)
CORPORA: dict = {}


def corpus(label: str) -> Corpus:
    if label not in CORPORA:
        CORPORA[label] = Corpus.load(ROOT, exclude=("chatrie",) if label == "before_chatrie" else ())
    return CORPORA[label]


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


ALL = {p.name: load(p) for p in EVENT_FILES}


def ids_of(path):
    return [p.name for p in path]


# ---------------------------------------------------------------------------------------------------------------
# One stream
# ---------------------------------------------------------------------------------------------------------------
def test_fixtures_exist():
    assert len(EVENT_FILES) >= 25, "the generator has not been run"
    assert len(HTTP_FILES) >= 15


@pytest.mark.parametrize("path", EVENT_FILES, ids=ids_of(EVENT_FILES))
def test_top_level_fields(path):
    doc = load(path)
    keys = ["format", "slug", "question", "recorded_at", "commit", "models", "prices", "corpus_label"]
    assert [k for k in doc if k != "after"][:-1] == keys and list(doc)[-1] == "events"
    assert doc["format"] == 1 and doc["slug"] == path.stem and doc["commit"] == "fixture"
    assert doc["models"] == {"loop": settings.LOOP_MODEL.value, "composition": settings.COMPOSITION_MODEL.value}
    assert doc["prices"] == price_sources()
    assert doc["corpus_label"] in ("full", "before_chatrie")
    rec = datetime.fromisoformat(doc["recorded_at"])
    assert rec.utcoffset() == rec.astimezone(CHICAGO).utcoffset(), "recorded_at must carry Chicago's offset"
    assert doc["events"][0]["data"].get("corpus_label", doc["corpus_label"]) == doc["corpus_label"]


@pytest.mark.parametrize("path", EVENT_FILES, ids=ids_of(EVENT_FILES))
def test_envelopes_and_order_rules(path):
    doc = load(path)
    events = doc["events"]
    after = doc.get("after", 0)
    assert [e["n"] for e in events] == list(range(after + 1, after + len(events) + 1))
    run = events[0]["run"]
    assert RUN_ID.match(run) and len(run) >= 16
    rec = datetime.fromisoformat(doc["recorded_at"])
    last_t = 0
    for e in events:
        assert e["run"] == run and e["v"] == 1
        assert e["t_ms"] >= last_t, f"t_ms went back at n={e['n']}"
        last_t = e["t_ms"]
        at = datetime.fromisoformat(e["at"])
        assert at.utcoffset() == at.astimezone(CHICAGO).utcoffset(), "at must carry Chicago's offset for that instant"
        assert abs((at - (rec + timedelta(milliseconds=e["t_ms"]))).total_seconds()) < 0.002
    assert [e["kind"] for e in events].count("run_ended") == 1 and events[-1]["kind"] == "run_ended"
    if after == 0:
        assert events[0]["kind"] == "run_started"


@pytest.mark.parametrize("path", EVENT_FILES, ids=ids_of(EVENT_FILES))
def test_tool_calls_precede_their_results(path):
    calls = {}
    results = set()
    for e in load(path)["events"]:
        d = e["data"]
        if e["kind"] == "tool_call":
            assert d["tool_use_id"] not in calls
            calls[d["tool_use_id"]] = d["name"]
        elif e["kind"] == "tool_result":
            assert calls.get(d["tool_use_id"]) == d["name"], f"result without its call at n={e['n']}"
            assert d["tool_use_id"] not in results
            results.add(d["tool_use_id"])
    if load(path).get("after", 0) == 0:
        assert results == set(calls), "every tool call has a result"


def names_in(e):
    """The passage IDs an event names, for the passage-before-naming rule."""
    d = e["data"]
    if e["kind"] == "tool_result":
        out = list(d.get("found", [])) + list(d.get("matched_again", [])) + list(d.get("read", []))
        return out + [k["id"] for k in d.get("kept", [])]
    if e["kind"] == "composition_started":
        return list(d["documents"])
    if e["kind"] == "answer_block":
        return [c["passage_id"] for c in d["citations"]]
    if e["kind"] == "api_fragment":
        return [d["passage_id"]]
    return []


@pytest.mark.parametrize("path", EVENT_FILES, ids=ids_of(EVENT_FILES))
def test_passages_come_before_anything_naming_them(path):
    doc = load(path)
    if doc.get("after"):
        pytest.skip("the passages of a reconnect fixture came before its first event")
    seen = set()
    for e in doc["events"]:
        if e["kind"] == "passage":
            assert e["data"]["id"] not in seen, "one passage event per passage per run"
            seen.add(e["data"]["id"])
        for pid in names_in(e):
            assert pid in seen, f"{pid} named at n={e['n']} ({e['kind']}) before its passage event"


@pytest.mark.parametrize("path", EVENT_FILES, ids=ids_of(EVENT_FILES))
def test_fragments_and_paid_calls_are_ordered(path):
    events = load(path)["events"]
    paid = {}
    for i, e in enumerate(events):
        if e["kind"] == "paid_call" and "call_no" in e["data"]:
            paid.setdefault(e["data"]["call_no"], []).append(i)
    for i, e in enumerate(events):
        if e["kind"] != "api_fragment":
            continue
        d = e["data"]
        if d["call_no"] not in paid:
            continue            # a reconnect fixture may start after the call's paid_call
        if d["role"] == "request":
            assert i < min(paid[d["call_no"]]), f"request fragment after its call's paid_call, n={e['n']}"
        else:
            assert i > max(paid[d["call_no"]]), f"response fragment before its call's paid_call, n={e['n']}"
        assert re.fullmatch(r"(messages\[\d+\]\.)?content\[\d+\](\.content\[\d+\])?", d["path"]), d["path"]
        assert (d["role"] == "request") == d["path"].startswith("messages[")
    # Claude calls are numbered from 1 without gaps, and each call's attempts are numbered from 1
    nos = sorted(paid)
    if nos and not load(path).get("after"):
        assert nos == list(range(1, len(nos) + 1))
        for c, idxs in paid.items():
            assert [events[i]["data"]["attempt"] for i in idxs] == list(range(1, len(idxs) + 1))
            assert [events[i]["data"]["outcome"] for i in idxs][:-1] == ["retrying"] * (len(idxs) - 1)


@pytest.mark.parametrize("path", EVENT_FILES, ids=ids_of(EVENT_FILES))
def test_citations_are_exact_slices_of_their_passages(path):
    doc = load(path)
    if doc.get("after"):
        pytest.skip("needs the passages from before the reconnect point")
    passages = {e["data"]["id"]: e["data"] for e in doc["events"] if e["kind"] == "passage"}
    comp = next((e["data"] for e in doc["events"] if e["kind"] == "composition_started"), None)
    fragments = {}
    for e in doc["events"]:
        if e["kind"] == "api_fragment":
            d = e["data"]
            fragments[(d["passage_id"], d["call_no"], d["role"], d["path"])] = d["json"]
    for e in doc["events"]:
        if e["kind"] == "passage":
            p = e["data"]
            assert [x for a, b in p["sentences"] for x in range(a, b)] == list(range(len(p["text"]))), "sentences tile the text"
        if e["kind"] == "composition_started":
            for i, pid in enumerate(e["data"]["documents"]):
                frag = fragments[(pid, e["data"]["call_no"], "request", f"messages[0].content[{i}]")]
                p = passages[pid]
                assert frag["type"] == "document" and frag["source"]["type"] == "content" and frag["context"]
                assert [b["text"] for b in frag["source"]["content"]] == [p["text"][a:b] for a, b in p["sentences"]]
                assert frag["citations"] == {"enabled": True}
        if e["kind"] != "answer_block":
            continue
        d = e["data"]
        for c in d["citations"]:
            p = passages[c["passage_id"]]
            assert 0 <= c["first_sentence"] <= c["last_sentence"] < len(p["sentences"])
            a, z = p["sentences"][c["first_sentence"]][0], p["sentences"][c["last_sentence"]][1]
            assert c["cited_text"] == p["text"][a:z], f"cited_text is not the slice at n={e['n']}"
            # the response's content index: thinking blocks come first, so it is at or after the answer index (v1.3)
            k = re.fullmatch(r"content\[(\d+)\]", c["path"])
            assert c["call_no"] == comp["call_no"] and k and int(k.group(1)) >= d["index"]
            frag = fragments[(c["passage_id"], c["call_no"], "response", c["path"])]
            assert frag["text"] == d["text"]
            doc_index = comp["documents"].index(c["passage_id"])
            assert any(x["type"] == "content_block_location" and x["cited_text"] == c["cited_text"]
                       and x["document_index"] == doc_index and x["start_block_index"] == c["first_sentence"]
                       and x["end_block_index"] == c["last_sentence"] + 1 for x in frag["citations"])


@pytest.mark.parametrize("path", EVENT_FILES, ids=ids_of(EVENT_FILES))
def test_loop_fragments_point_at_what_was_sent_and_returned(path):
    """T4.3(7): a request fragment is a block of the previous round's tool result; a response fragment is that
    round's tool_use block, and the passage is one the tool returned, matched again or kept."""
    doc = load(path)
    if doc.get("after"):
        pytest.skip("needs the rounds before the reconnect point")
    events = doc["events"]
    rounds, current = {}, 0
    for e in events:
        if e["kind"] == "round_started":
            current = e["data"]["round"]
        elif e["kind"] == "tool_call":
            rounds.setdefault(current, {"calls": [], "results": {}})["calls"].append(e["data"])
        elif e["kind"] == "tool_result":
            rounds[current]["results"][e["data"]["tool_use_id"]] = e["data"]
    for e in events:
        if e["kind"] != "api_fragment":
            continue
        d = e["data"]
        if d["call_no"] not in rounds and d["role"] == "request":
            continue                                    # a composition document, checked elsewhere
        comp = next((x["data"]["call_no"] for x in events if x["kind"] == "composition_started"), None)
        if d["call_no"] == comp:
            continue
        if d["role"] == "request":
            m = re.fullmatch(r"messages\[(\d+)\]\.content\[(\d+)\]\.content\[(\d+)\]", d["path"])
            assert m and int(m.group(1)) == 2 * (d["call_no"] - 1), d["path"]
            prev = rounds[d["call_no"] - 1]
            call = prev["calls"][int(m.group(2))]
            assert d["json"]["type"] == "text" and d["json"]["text"] in prev["results"][call["tool_use_id"]]["content"]
            assert f"[{d['passage_id']}]" in d["json"]["text"]
        else:
            m = re.fullmatch(r"content\[(\d+)\]", d["path"])
            assert m
            block = d["json"]
            assert block["type"] == "tool_use"
            call = next(c for c in rounds[d["call_no"]]["calls"] if c["tool_use_id"] == block["id"])
            assert block["name"] == call["name"]
            res = rounds[d["call_no"]]["results"][block["id"]]
            ids = set(res.get("found", [])) | set(res.get("matched_again", [])) | set(res.get("read", [])) | {k["id"] for k in res.get("kept", [])}
            assert d["passage_id"] in ids
            if call["name"] != "submit_answer":
                assert block["input"] == call["input"], "the fragment is exactly what Claude sent"


@pytest.mark.parametrize("path", EVENT_FILES, ids=ids_of(EVENT_FILES))
def test_loop_usage_is_cold_then_cached(path):
    doc = load(path)
    if doc.get("after"):
        pytest.skip("needs the first call")
    loop = [e["data"] for e in doc["events"] if e["kind"] == "paid_call" and e["data"]["purpose"] == "loop" and e["data"]["outcome"] == "ok"]
    comp = [e["data"] for e in doc["events"] if e["kind"] == "paid_call" and e["data"]["purpose"] == "composition" and e["data"]["outcome"] == "ok"]
    if loop:
        first = loop[0]["usage"]
        assert first["cache_read_input_tokens"] == 0 and first["cache_creation"]["ephemeral_1h_input_tokens"] >= 10_000
        for p in loop[1:]:
            assert p["usage"]["cache_read_input_tokens"] > 10_000
    for p in comp:
        assert p["usage"]["cache_read_input_tokens"] == 0 and p["usage"]["cache_creation_input_tokens"] == 0     # composition is uncached (T1.11)


@pytest.mark.parametrize("path", EVENT_FILES, ids=ids_of(EVENT_FILES))
def test_answer_blocks_are_numbered_and_follow_composition(path):
    events = load(path)["events"]
    blocks = [e for e in events if e["kind"] == "answer_block"]
    assert [b["data"]["index"] for b in blocks] == list(range(len(blocks)))
    if blocks and not load(path).get("after"):
        kinds = [e["kind"] for e in events]
        assert kinds.index("composition_started") < events.index(blocks[0])
        assert kinds.count("composition_started") == 1


@pytest.mark.parametrize("path", EVENT_FILES, ids=ids_of(EVENT_FILES))
def test_totals_are_the_sum_of_the_paid_calls(path):
    doc = load(path)
    if doc.get("after"):
        pytest.skip("a reconnect fixture holds only part of the paid calls")
    paid = [e["data"] for e in doc["events"] if e["kind"] == "paid_call"]
    t = doc["events"][-1]["data"]["totals"]
    claude = [p for p in paid if p["service"] == "anthropic"]
    input_tokens = cache_read = cache_write = output = 0
    cost = {"loop": 0.0, "composition": 0.0}
    for p in claude:
        model = doc["models"]["loop" if p["purpose"] == "loop" else "composition"]
        if p["usage"] is None:       # an attempt that reported no usage: input estimated at the uncached price (T3.3)
            assert p["estimated"] is True and p["outcome"] in ("retrying", "failed")
            input_tokens += round(p["cost_usd"] * 1e6 / PRICE_TABLE["anthropic"]["models"][model]["input"])
        else:
            u = p["usage"]
            cc = u["cache_creation"]
            assert u["cache_creation_input_tokens"] == cc["ephemeral_5m_input_tokens"] + cc["ephemeral_1h_input_tokens"]
            input_tokens += u["input_tokens"] + u["cache_creation_input_tokens"] + u["cache_read_input_tokens"]
            cache_read += u["cache_read_input_tokens"]
            cache_write += u["cache_creation_input_tokens"]
            output += u["output_tokens"]
            expected = price(Usage(service="anthropic", model=model, input_tokens=u["input_tokens"],
                                   cache_write_5m_tokens=cc["ephemeral_5m_input_tokens"],
                                   cache_write_1h_tokens=cc["ephemeral_1h_input_tokens"],
                                   cache_read_tokens=u["cache_read_input_tokens"], output_tokens=u["output_tokens"]))
            assert p["cost_usd"] == pytest.approx(expected, rel=1e-9), "a paid call's cost is price(usage)"
        cost[p["purpose"]] += p["cost_usd"]
    c = t["claude"]
    assert c["calls"] == len(claude)
    assert (c["input_tokens"], c["cache_read_tokens"], c["cache_write_tokens"], c["output_tokens"]) == (
        input_tokens, cache_read, cache_write, output)
    assert c["cost_usd"]["loop"] == pytest.approx(cost["loop"], abs=1e-8)
    assert c["cost_usd"]["composition"] == pytest.approx(cost["composition"], abs=1e-8)
    for service, key, field in (("exa", "exa", "searches"), ("voyage", "voyage", "requests")):
        mine = [p for p in paid if p["service"] == service]
        assert t[key][field] == len(mine)
        assert t[key]["cost_usd"] == pytest.approx(sum(p["cost_usd"] for p in mine), abs=1e-8)
    assert t["prices"] == price_sources()
    for p in paid:
        assert p["max_attempts"] >= p["attempt"] >= 1
        assert (p["service"] == "anthropic") == ("call_no" in p)
        assert (p["outcome"] == "ok") == (p["error_kind"] is None)
        if p["service"] == "anthropic" and p["outcome"] == "ok":
            assert p["usage"] is not None and p["estimated"] is False
    # the run's end reports what was counted
    ended = doc["events"][-1]["data"]
    assert ended["rounds"] == sum(1 for e in doc["events"] if e["kind"] == "round_started")
    blocks = [e["data"]["text"] for e in doc["events"] if e["kind"] == "answer_block"]
    assert ended["answer_chars"] == sum(len(b) for b in blocks)


@pytest.mark.parametrize("path", EVENT_FILES, ids=ids_of(EVENT_FILES))
def test_checks_are_check_answer_run_on_the_streams_own_blocks(path):
    doc = load(path)
    if doc.get("after"):
        pytest.skip("needs the passages from before the reconnect point")
    events = doc["events"]
    blocks = [e["data"]["text"] for e in events if e["kind"] == "answer_block"]
    checks = [e["data"] for e in events if e["kind"] == "checks"]
    if not blocks:
        assert checks == []
        return
    assert len(checks) == 1
    passages = {e["data"]["id"]: e["data"]["text"] for e in events if e["kind"] == "passage"}
    comp = next(e["data"] for e in events if e["kind"] == "composition_started")
    c = corpus(doc["corpus_label"])
    r = check_answer(blocks, [passages[i] for i in comp["documents"]], c.manifest)
    expected = json.loads(json.dumps(r, default=lambda o: o.__dict__))
    assert checks[0] == expected
    kinds = [e["kind"] for e in events]
    assert kinds.index("answer_block") < kinds.index("checks") < kinds.index("update_band")


@pytest.mark.parametrize("path", EVENT_FILES, ids=ids_of(EVENT_FILES))
def test_web_pages_are_synthetic_and_carry_no_text(path):
    doc = load(path)
    events = doc["events"]
    returned = set()
    for e in events:
        d = e["data"]
        if e["kind"] == "tool_result" and d["name"] == "search_web_updates":
            for pg in d.get("web", []):
                returned.add(pg["id"])
            assert set(d.get("web_repeats", [])) <= returned if not doc.get("after") else True
            for body in OPEN_BLOCK.findall(d["content"]):
                assert PLACEHOLDER.match(body), "page text must be replaced by its placeholder"
            assert "</web_page_text>" not in OPEN_BLOCK.sub("", d["content"])
    pages = []
    for e in events:
        d = e["data"]
        if e["kind"] == "tool_result":
            pages += d.get("web", [])
        if e["kind"] == "update_band":
            pages += d["pages"]
            if not doc.get("after"):
                assert {p["id"] for p in d["pages"]} <= returned, "a band page no search returned"
                for f in d["findings"]:
                    assert set(f["sources"]) <= returned, "a finding names a page no search returned"
                assert len({p["id"] for p in d["pages"]}) == len(d["pages"])
    for pg in pages:
        assert pg["domain"].endswith("example.test") and pg["url"].startswith("https://" + pg["domain"] + "/")
        assert pg["title"].startswith("[Sample]")
        for k, v in pg.items():
            if isinstance(v, str):
                assert len(v) <= 200, f"{k} of a web page is {len(v)} characters long"
    for e in events:
        if e["kind"] == "update_band":
            for f in e["data"]["findings"]:
                assert len(f["statement"]) <= settings.UPDATE_STATEMENT_MAX_CHARS.value and f["sources"]
            if e["data"]["overview"]:
                assert len(e["data"]["overview"]) <= settings.UPDATE_OVERVIEW_MAX_CHARS.value


@pytest.mark.parametrize("path", EVENT_FILES, ids=ids_of(EVENT_FILES))
def test_the_band_matches_what_the_run_did(path):
    doc = load(path)
    if doc.get("after"):
        pytest.skip("needs the whole run")
    events = doc["events"]
    band = next((e["data"] for e in events if e["kind"] == "update_band"), None)
    ended = events[-1]["data"]
    if ended["state"] in ("failed", "interrupted"):
        assert band is None or ended["state"] == "failed"
        if ended["state"] == "interrupted":
            assert band is None
        return
    assert band is not None
    results = [e["data"] for e in events if e["kind"] == "tool_result" and e["data"]["name"] == "search_web_updates"]
    counted = [r for r in results if r["web_status"] in ("ok", "refused_by_exa", "failed")]
    assert [s["search_no"] for s in band["searches"]] == [r["search_no"] for r in results if "search_no" in r]
    submits = [e["data"] for e in events if e["kind"] == "tool_result" and e["data"]["name"] == "submit_answer"
               and e["data"]["submit"]["accepted"]]
    o = band["outcome"]
    if o == "found":
        assert band["findings"] and counted
    elif o == "nothing_relevant":
        assert counted and submits and not band["findings"]
    elif o == "not_summarised":
        assert counted and not submits
    elif o == "unavailable":
        assert band["reason"] in ("no_credit", "key_refused") and not counted
    elif o == "skipped":
        assert band["reason"] and not counted and submits
    elif o == "declined":
        assert band["reason"] is None and not counted and submits
    elif o == "not_run":
        assert not counted and not submits and not any(r["web_status"] == "unavailable" for r in results)
    assert band["reason"] is None or o in ("skipped", "unavailable")


# Which answer_end each state may carry (contract section 6, v1.1). A state that stops before or without a composition
# carries "none"; one that composes from what was kept carries how that composition ended.
ALLOWED_ANSWER_END = {
    "answered": {"complete", "cut_off", "incomplete"},
    "no_sources": {"none"},
    "step_limit": {"complete", "cut_off", "incomplete", "none"},
    "token_ceiling": {"complete", "cut_off", "incomplete", "none"},
    "time_limit": {"complete", "cut_off", "incomplete", "none"},
    "error_stopped": {"complete", "cut_off", "incomplete"},
    "abandoned": {"none"}, "interrupted": {"none"}, "failed": {"none"}, "refusal": {"none"}, "spend_limit": {"none"},
}


@pytest.mark.parametrize("path", EVENT_FILES, ids=ids_of(EVENT_FILES))
def test_run_ended_is_consistent(path):
    d = load(path)["events"][-1]["data"]
    state, kind, end = d["state"], d["stop_kind"], d["answer_end"]
    allowed = {"step_limit": {"step_limit"}, "token_ceiling": {"token_ceiling_input", "token_ceiling_output"},
               "time_limit": {"time_limit"}, "spend_limit": {"console_spend_limit", "tier_spend_cap"}}
    if state in allowed:
        assert kind in allowed[state]
    elif kind == "composition_max_tokens":
        assert end == "cut_off"
    else:
        assert kind is None
    # a loop limit keeps its own stop_kind when its composition is then cut off (v1.3)
    assert (end == "cut_off") == (kind == "composition_max_tokens" or (state in allowed and state != "spend_limit"
                                                                      and end == "cut_off"))
    if kind == "composition_max_tokens":
        assert end == "cut_off"
    if state == "no_sources":
        assert d["no_sources_reason"] in ("out_of_scope", "nothing_found") and d["note"] and end == "none"
    else:
        assert d["no_sources_reason"] is None and d["note"] is None
    if state in ("failed", "error_stopped", "refusal") or end == "incomplete":
        assert d["failure_reason"]
    if d["failure_reason"] is not None:
        assert d["failure_reason"] in SCHEMA["$defs"]["run_ended"]["properties"]["failure_reason"]["enum"]
    assert end in ALLOWED_ANSWER_END[state], f"{state} with answer_end {end} is not a pairing the contract allows"
    if end == "incomplete":                  # a composition that broke after its first block (v1.1, v1.3)
        assert state in ("answered", "step_limit", "token_ceiling", "time_limit", "error_stopped")
    if end in ("complete", "cut_off", "incomplete"):
        assert d["answer_chars"] > 0
    if end == "none" and state not in ("failed", "interrupted"):   # H's endings count what streamed (v1.2)
        assert d["answer_chars"] == 0


@pytest.mark.parametrize("path", EVENT_FILES, ids=ids_of(EVENT_FILES))
def test_refused_submits_withhold_flagged_statements(path):
    doc = load(path)
    events = doc["events"]
    calls = {e["data"]["tool_use_id"]: e["data"] for e in events if e["kind"] == "tool_call"}
    for e in events:
        d = e["data"]
        if e["kind"] == "tool_result" and d["name"] == "submit_answer":
            sub = d["submit"]
            if not sub["accepted"]:
                assert d["is_error"] and sub["rule"] in ("same_turn", "findings", "copy_guard", "no_search", "nothing_kept",
                                                         "no_update_check", "no_note", None)   # None: bad input (v1.3)
            inp = calls[d["tool_use_id"]]["input"]
            texts = [f["statement"] for f in inp.get("update_findings") or []] + [inp.get("update_overview") or ""]
            withheld = [t for t in texts if t == WITHHELD]
            if sub.get("rule") == "copy_guard":
                assert withheld, "a submit refused by the copy guard is stored with its flagged statements withheld (P4.3)"
                assert "page" in d["content"] and "Paraphrase" in d["content"] or "own words" in d["content"]
            elif sub["accepted"]:
                assert not withheld   # an accepted submit has nothing the guard flagged; a refused one may (v1.3)


@pytest.mark.parametrize("path", EVENT_FILES, ids=ids_of(EVENT_FILES))
def test_warnings_come_once_each(path):
    codes = [e["data"]["code"] for e in load(path)["events"] if e["kind"] == "warning"]
    assert len(codes) == len(set(codes))


def test_reconnect_fixture_is_the_tail_of_its_source():
    rc = [d for d in ALL.values() if "after" in d]
    assert len(rc) == 1
    d = rc[0]
    src = ALL[d["slug"].split("-after-")[0] + ".json"]
    assert d["after"] >= 1 and d["events"][0]["n"] == d["after"] + 1
    assert d["events"] == [e for e in src["events"] if e["n"] > d["after"]]
    assert {k: v for k, v in d.items() if k not in ("after", "events", "slug")} == {
        k: v for k, v in src.items() if k not in ("events", "slug")}


def test_interrupted_run_ends_with_h_event():
    d = ALL["interrupted-run.json"]
    last = d["events"][-1]["data"]
    assert last["state"] == "interrupted" and last["answer_end"] == "none"
    assert d["events"][-1]["n"] == d["events"][-2]["n"] + 1
    assert d["events"][-1]["t_ms"] - d["events"][-2]["t_ms"] > 5_000       # the page came back later


def test_the_set_covers_every_state_stop_kind_and_outcome():
    ends = [d["events"][-1]["data"] for d in ALL.values()]
    bands = [e["data"] for d in ALL.values() for e in d["events"] if e["kind"] == "update_band"]
    defs = SCHEMA["$defs"]
    states = set(defs["run_ended"]["properties"]["state"]["enum"])
    assert {e["state"] for e in ends} == states
    # the schema allows only the stop kinds a run can end with (daily_cap, monthly_cap and exa_no_credit are not among them)
    run_stop_kinds = set(defs["run_ended"]["properties"]["stop_kind"]["enum"]) - {None}
    assert not run_stop_kinds & {"daily_cap", "monthly_cap", "exa_no_credit"}
    assert {e["stop_kind"] for e in ends} - {None} == run_stop_kinds
    assert {e["answer_end"] for e in ends} == set(defs["run_ended"]["properties"]["answer_end"]["enum"])
    assert {(e["state"], e["answer_end"]) for e in ends} <= {(st, a) for st, ae in ALLOWED_ANSWER_END.items() for a in ae}
    assert ("answered", "incomplete") in {(e["state"], e["answer_end"]) for e in ends}
    assert {e["no_sources_reason"] for e in ends} - {None} == {"out_of_scope", "nothing_found"}
    assert {b["outcome"] for b in bands} == set(defs["update_band"]["properties"]["outcome"]["enum"])
    assert {s["status"] for b in bands for s in b["searches"]} == set(
        defs["update_band"]["properties"]["searches"]["items"]["properties"]["status"]["enum"])
    events = [e for d in ALL.values() for e in d["events"]]
    assert {e["kind"] for e in events} == set(SCHEMA["properties"]["kind"]["enum"])
    results = [e["data"] for e in events if e["kind"] == "tool_result"]
    assert {r["name"] for r in results} == set(defs["tool_result"]["properties"]["name"]["enum"])
    assert {r["web_status"] for r in results if "web_status" in r} == set(defs["tool_result"]["properties"]["web_status"]["enum"])
    assert {r["submit"]["rule"] for r in results if r.get("submit") and not r["submit"]["accepted"]} == {
        "same_turn", "findings", "copy_guard", "no_search", "nothing_kept", "no_update_check"}
    assert {e["data"]["code"] for e in events if e["kind"] == "warning"} == {"meaning_search_degraded", "meaning_search_unavailable"}
    paid = [e["data"] for e in events if e["kind"] == "paid_call"]
    assert {p["outcome"] for p in paid} == {"ok", "retrying", "failed"}
    assert {(p["service"], p["purpose"]) for p in paid} == {
        ("anthropic", "loop"), ("anthropic", "composition"), ("voyage", "embed"), ("voyage", "rerank"), ("exa", "update_search")}
    assert {p["service"] for p in paid if p["outcome"] == "retrying"} == {"anthropic", "voyage"}
    assert {p["error_kind"] for p in paid if p["service"] == "anthropic"} >= {
        "overloaded", "rate_limited", "server_error", "refusal", "spend_limit", "spend_cap", "stream_broken"}
    assert any(r["name"] == "keep_passages" and r.get("refused") for r in results)
    assert any(r["name"] == "keep_passages" and any(k["replaced"] for k in r.get("kept", [])) for r in results)
    assert any(r["name"] == "search_meaning" and r.get("not_reranked") for r in results)
    assert any(r["is_error"] for r in results if r["name"] in ("search_meaning", "search_exact", "read_passages"))
    ent = [e["data"] for d in ALL.values() for e in d["events"] if e["kind"] == "checks"]
    assert any(c["flags"] and any(f["kind"] == "quotation_not_found" for f in c["flags"]) for c in ent)
    assert any(any(f["kind"] == "not_in_corpus" for f in c["flags"]) for c in ent)
    assert any(d["corpus_label"] == "before_chatrie" for d in ALL.values())
    whole = [d for d in ALL.values() if "after" not in d]          # a reconnect fixture shares its source run's ID
    assert len({d["events"][0]["run"] for d in whole}) == len(whole), "run IDs are unique"
    assert sum(p.stat().st_size for p in EVENT_FILES) < 5_000_000


# ---------------------------------------------------------------------------------------------------------------
# HTTP fixtures (contract §5, §5.1)
# ---------------------------------------------------------------------------------------------------------------
def hdr(d, name):
    return {k.lower(): v for k, v in d["headers"].items()}[name]


@pytest.mark.parametrize("path", HTTP_FILES, ids=ids_of(HTTP_FILES))
def test_http_fixture_shape(path):
    d = load(path)
    assert list(d) == ["description", "method", "path", "status", "headers", "body"]
    assert d["method"] in ("GET", "POST") and d["path"].startswith("/") and isinstance(d["status"], int)
    assert isinstance(d["body"], str) and isinstance(d["description"], str) and d["description"]
    if d["status"] != 204:
        assert hdr(d, "content-type")


def http(name):
    return load(ROOT / "tests" / "fixtures" / "http" / name)


@pytest.mark.parametrize("name,live,update", [
    ("health-ready.json", "open", "available"), ("health-paused-day.json", "paused_day", "available"),
    ("health-paused-month.json", "paused_month", "available"), ("health-unknown.json", "unknown", "unknown")])
def test_health_bodies_have_contract_5s_shape(name, live, update):
    d = http(name)
    assert d["method"] == "GET" and d["path"] == "/health" and d["status"] == 200
    assert hdr(d, "content-type").startswith("application/json")
    body = json.loads(d["body"])
    assert body == {"app": "probable-clause", "ready": True, "live_research": live, "update_check": update, "commit": "fixture"}
    assert d["body"] == json.dumps(body, separators=(",", ":"))


ERRORS = [
    ("post-runs-400-question-empty.json", 400, "question_empty"), ("post-runs-400-question-too-long.json", 400, "question_too_long"),
    ("post-runs-413-body-too-large.json", 413, "body_too_large"), ("post-runs-503-paused-day.json", 503, "paused_day"),
    ("post-runs-503-paused-month.json", 503, "paused_month"), ("post-runs-503-atlas-unreachable.json", 503, "atlas_unreachable"),
    ("get-events-404-run-unknown.json", 404, "run_unknown"), ("post-alive-404-run-unknown.json", 404, "run_unknown"),
]


@pytest.mark.parametrize("name,status,code", ERRORS)
def test_error_bodies_are_error_and_message(name, status, code):
    d = http(name)
    assert d["status"] == status and hdr(d, "content-type").startswith("application/json")
    body = json.loads(d["body"])
    assert list(body) == ["error", "message"] and body["error"] == code and body["message"]


def test_run_creation_and_the_stream_headers():
    ok = http("post-runs-201.json")
    assert ok["method"] == "POST" and ok["path"] == "/runs" and ok["status"] == 201
    body = json.loads(ok["body"])
    assert list(body) == ["run_id"] and RUN_ID.match(body["run_id"]) and len(body["run_id"]) >= 16
    s = http("get-events-200-stream.json")
    assert s["status"] == 200 and hdr(s, "content-type").startswith("text/event-stream")
    assert hdr(s, "x-accel-buffering") == "no"
    frames = [f for f in s["body"].split("\n\n") if f]
    assert any(f.startswith(":") for f in frames), "a keep-alive comment line"
    data_frames = [f for f in frames if not f.startswith(":")]
    for f in data_frames:
        lines = f.split("\n")
        assert lines[0].startswith("id: ") and lines[1].startswith("event: ") and lines[2].startswith("data: ")
        env = json.loads(lines[2][len("data: "):])
        assert str(env["n"]) == lines[0][4:] and env["kind"] == lines[1][7:]
    alive = http("post-alive-204.json")
    assert alive["status"] == 204 and alive["body"] == "" and json.loads(http("post-alive-404-run-unknown.json")["body"])["error"] == "run_unknown"


@pytest.mark.parametrize("name,status", [("cloud-run-429.json", 429), ("cloud-run-500.json", 500), ("cloud-run-503.json", 503),
                                         ("gateway-502.json", 502)])
def test_wake_protocol_answers_are_not_our_json(name, status):
    d = http(name)
    assert d["status"] == status and "representative" in d["description"]
    with pytest.raises(ValueError):
        json.loads(d["body"])                 # the page treats any answer that is not our JSON as "still starting" (§5.1)
    if status == 502:
        assert hdr(d, "content-type").startswith("text/html") and "<html" in d["body"]
    else:
        assert hdr(d, "content-type").startswith("text/plain")
