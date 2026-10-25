"""The event schema (contract §6) is valid, accepts well-formed events and refuses malformed ones.

Every fixture under tests/fixtures/events/ is validated too, so the frontend
session's mock and the backend agree (P0.3).
"""

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[2]
SCHEMA = json.loads((ROOT / "contracts" / "events.schema.json").read_text())
VALIDATOR = Draft202012Validator(SCHEMA)
FIXTURES = sorted((ROOT / "tests" / "fixtures" / "events").glob("*.json"))


def envelope(n, kind, data):
    return {"v": 1, "run": "r" * 22, "n": n, "t_ms": n * 100, "at": "2026-10-24T20:31:05.123-05:00", "kind": kind, "data": data}


PASSAGE = {
    "id": "katz-1-p3", "kind": "paragraph", "case_key": "katz", "case_name": "Katz v. United States",
    "citation": "389 U.S. 347", "decided": "1967-12-18", "opinion_id": "katz-1", "opinion_type": "majority",
    "authors": ["Stewart"], "joined_by": [], "section": None, "page_start": 351, "page_end": 352,
    "paragraph_kind": "text", "footnote_label": None, "footnotes": ["katz-1-n8"], "cited_by": [],
    "text": "For the Fourth Amendment protects people, not places. What a person knowingly exposes...",
    "sentences": [[0, 55], [55, 87]],
}

GOOD = [
    envelope(1, "round_started", {"round": 1, "status_line": "Round 1 of 12 · 0 kept · update check not yet run"}),
    envelope(2, "passage", PASSAGE),
    envelope(3, "tool_result", {"tool_use_id": "toolu_1", "name": "search_exact", "is_error": False,
                                "content": "...", "found": ["katz-1-p3"], "matched_again": []}),
    envelope(4, "answer_block", {"index": 0, "text": "The Court held that the Amendment protects people.",
                                 "citations": [{"passage_id": "katz-1-p3", "first_sentence": 0, "last_sentence": 0,
                                                "cited_text": "For the Fourth Amendment protects people, not places. ",
                                                "call_no": 6, "path": "content[1]"}]}),
    envelope(5, "warning", {"code": "meaning_search_degraded"}),
]

BAD = [
    envelope(1, "passage", {**PASSAGE, "id": "Katz 1 p3"}),               # malformed passage ID
    envelope(1, "warning", {"code": "quality_affected"}),                # not a warning code
    envelope(1, "tool_result", {"tool_use_id": "t", "name": "search_corpus", "is_error": False, "content": ""}),
    {**envelope(1, "paused", {"since_ms": 0}), "at": "2026-10-24T20:31:05Z"},  # no offset (brief §10.7)
    {**envelope(1, "paused", {"since_ms": 0}), "extra": True},
]


def test_schema_is_valid():
    Draft202012Validator.check_schema(SCHEMA)


@pytest.mark.parametrize("event", GOOD)
def test_good_events_pass(event):
    VALIDATOR.validate(event)


@pytest.mark.parametrize("event", BAD)
def test_bad_events_fail(event):
    assert list(VALIDATOR.iter_errors(event))


@pytest.mark.parametrize("path", FIXTURES, ids=[p.name for p in FIXTURES])
def test_fixture_streams_validate(path):
    events = json.loads(path.read_text())["events"]
    for e in events:
        VALIDATOR.validate(e)
    assert [e["n"] for e in events] == list(range(1, len(events) + 1))
