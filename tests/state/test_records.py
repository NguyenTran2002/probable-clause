"""api/state/records.py: what a run record and a stop detail may hold (T3.7). Allowlists, not a denylist."""

import pytest

from api.protocols import BUDGET_STOPS
from api.state import records

GOOD = {
    "run": "AbC_123-xyz", "started_date": "2030-05-14", "started_time": "12:00:00", "state": "answered", "stop_kind": None,
    "rounds": 4, "answer_chars": 812, "searches": {"meaning": 2, "exact": 1, "web": 1}, "keeps": 5,
    "tokens": {"input": 1000, "cache_read": 800, "cache_write": 200, "output": 300},
    "cost_usd": {"claude_loop": 0.1, "claude_composition": 0.1, "exa": 0.007, "voyage": 0.001},
    "calls": {"claude": 6, "exa": 1, "voyage": 4}, "retries": {"claude": 0, "voyage": 1},
    "checks": {"quotations_checked": 3, "quotations_found": 3, "citations_checked": 2, "citations_found": 2,
               "not_in_corpus": 0, "flags": 0},
    "voyage_warning": "degraded", "corpus_label": "full",
}

# the reviewer's probe, plus the obvious: names that could carry the question, a query or the answer
PROBE_KEYS = ["q", "prompt", "Question", "question", "content", "summary", "reason", "title", "statement", "message",
              "Query", "query", "answer", "text", "note", "scope_note", "queries", "body", "input", "output_text"]


def refused(rec):
    with pytest.raises(ValueError) as e:
        records.check_run_record(rec)
    return str(e.value)


# --- run records ---------------------------------------------------------------------------------------------------

def test_a_full_good_record_passes_and_returns_the_run_id():
    assert records.check_run_record(GOOD) == "AbC_123-xyz"


def test_a_record_may_be_just_a_run_id():
    assert records.check_run_record({"run": "r1"}) == "r1"


def test_every_documented_key_is_accepted_alone_with_a_run_id():
    for k, v in GOOD.items():
        if k != "run":
            records.check_run_record({"run": "r1", k: v})


def test_the_run_id_is_required_and_must_be_an_id():
    refused({})
    refused({"state": "answered"})
    for bad in ("", "a.b", "a b", "$x", "x" * 129, "What is the rule on thermal imaging of homes?", None, 5, ["r1"]):
        refused({"run": bad})


@pytest.mark.parametrize("key", PROBE_KEYS)
def test_unknown_keys_are_refused_at_the_top_level(key):
    msg = refused({"run": "r1", key: "what is the rule on thermal imaging of a home?"})
    assert "thermal" not in msg
    refused({"run": "r1", key: 5})                       # a number under an unknown key is refused too


@pytest.mark.parametrize("key", PROBE_KEYS)
def test_unknown_keys_are_refused_at_every_depth(key):
    for parent in ("searches", "tokens", "cost_usd", "calls", "retries", "checks"):
        rec = {"run": "r1", parent: {key: "what is the rule on thermal imaging of a home?"}}
        assert "thermal" not in refused(rec)
    refused({"run": "r1", "searches": {"meaning": {"Query": "x"}}})
    refused({"run": "r1", "searches": [{"Query": "x"}]})


def test_keys_are_case_sensitive():
    refused({"run": "r1", "State": "answered"})
    refused({"run": "r1", "Run": "r1", "state": "answered"})


def test_long_free_text_under_an_allowed_key_is_refused():
    text = "Does the Fourth Amendment forbid police from using a thermal camera on my house without a warrant? " * 5
    for key in ("state", "stop_kind", "started_date", "started_time", "voyage_warning", "corpus_label", "run"):
        msg = refused({"run": "r1", key: text} if key != "run" else {"run": text})
        assert "Fourth Amendment" not in msg and "thermal" not in msg
    for key in ("rounds", "answer_chars", "keeps"):
        refused({"run": "r1", key: text})
    for parent, sub in (("searches", "meaning"), ("tokens", "input"), ("cost_usd", "exa"), ("calls", "claude"),
                        ("retries", "voyage"), ("checks", "flags")):
        refused({"run": "r1", parent: {sub: text}})
    refused({"run": "r1", "searches": text})


def test_strings_are_allowed_only_as_the_run_id_dates_times_and_enum_values():
    refused({"run": "r1", "state": "all done"})
    refused({"run": "r1", "state": "ANSWERED"})
    refused({"run": "r1", "stop_kind": "coffee_break"})
    refused({"run": "r1", "corpus_label": "partial"})
    refused({"run": "r1", "voyage_warning": "meaning search was degraded"})
    refused({"run": "r1", "started_date": "2030-5-14"})
    refused({"run": "r1", "started_date": "2030-02-30"})
    refused({"run": "r1", "started_date": "14 May 2030"})
    refused({"run": "r1", "started_time": "25:00:00"})
    refused({"run": "r1", "started_time": "noon"})
    refused({"run": "r1", "started_time": "12:00"})


def test_enums_cover_the_states_the_page_and_the_events_know():
    for st in ("answered", "no_sources", "step_limit", "token_ceiling", "time_limit", "error_stopped", "abandoned",
               "interrupted", "failed", "refusal", "spend_limit"):
        records.check_run_record({"run": "r1", "state": st})
    for k in BUDGET_STOPS | {"time_limit", "atlas_unreachable"}:
        records.check_run_record({"run": "r1", "stop_kind": k})
    for w in (None, "degraded", "unavailable"):
        records.check_run_record({"run": "r1", "voyage_warning": w})
    for c in ("full", "before_chatrie"):
        records.check_run_record({"run": "r1", "corpus_label": c})
    assert records.RUN_STATES == ("answered", "no_sources", "step_limit", "token_ceiling", "time_limit", "error_stopped",
                                  "abandoned", "interrupted", "failed", "refusal", "spend_limit")


def test_numbers_are_checked_by_type_and_range():
    for key in ("rounds", "answer_chars", "keeps"):
        for bad in (-1, 1.5, "3", True, None, float("nan"), [3]):
            refused({"run": "r1", key: bad})
    for bad in (-0.01, float("nan"), float("inf"), "0.1", True, None):
        refused({"run": "r1", "cost_usd": {"exa": bad}})
    refused({"run": "r1", "tokens": {"input": 1.5}})
    refused({"run": "r1", "calls": {"claude": True}})
    records.check_run_record({"run": "r1", "cost_usd": {"exa": 0}})            # an int zero is a number
    records.check_run_record({"run": "r1", "cost_usd": {"exa": 0.0}})


def test_nested_values_must_be_objects_of_the_documented_keys():
    refused({"run": "r1", "searches": 3})
    refused({"run": "r1", "searches": None})
    refused({"run": "r1", "searches": {"meaning": 1, "carrier_pigeon": 1}})
    refused({"run": "r1", "tokens": {"input": 1, "context": 1}})
    refused([("run", "r1")])
    refused("run r1")


def test_a_record_is_not_modified_by_checking_it():
    import copy
    rec = copy.deepcopy(GOOD)
    records.check_run_record(rec)
    assert rec == GOOD


def test_the_allowed_shape_is_documented_for_the_builder_of_h():
    doc = records.check_run_record.__doc__ + (records.__doc__ or "")
    for key in GOOD:
        assert f"`{key}`" in doc, key


# --- stop details --------------------------------------------------------------------------------------------------

def good_detail(**kw):
    records.check_stop_detail(kw)
    return kw


def bad_detail(d):
    with pytest.raises(ValueError) as e:
        records.check_stop_detail(d)
    return str(e.value)


def test_a_detail_may_hold_numbers_booleans_and_enum_strings():
    good_detail()
    good_detail(rounds=12, input_tokens=370_000, cost_usd=1.5, negative=-1, after_retry=True, stop_state="step_limit",
                purpose="composition", service="exa", corpus_label="before_chatrie", kind="daily_cap")


def test_free_text_in_a_detail_is_refused_whatever_the_key():
    text = "What does the Fourth Amendment say about drones?"
    for key in ("q", "prompt", "Question", "content", "summary", "reason", "title", "statement", "message", "Query",
                "rounds", "stop_state", "kind", "anything_at_all"):
        msg = bad_detail({key: text})
        assert "drones" not in msg


def test_enum_strings_come_from_one_small_fixed_set():
    assert len(records.DETAIL_STRINGS) < 60
    assert bad_detail({"x": "step_limit "}) and bad_detail({"x": "Step_Limit"}) and bad_detail({"x": ""})
    for kind in BUDGET_STOPS:
        good_detail(k=kind)


def test_structures_are_refused():
    bad_detail({"x": {"y": 1}})
    bad_detail({"x": [1, 2]})
    bad_detail({"x": (1, 2)})
    bad_detail({"x": None})
    bad_detail({"x": b"bytes"})
    bad_detail({"Query": {"nested": "text"}})


def test_numbers_must_be_finite():
    bad_detail({"x": float("nan")})
    bad_detail({"x": float("inf")})


def test_keys_must_look_like_names_not_sentences():
    for key in ("what is the rule", "x" * 41, "", "1abc", "has-dash", "UPPER", "dotted.key", "$op", 5, None):
        bad_detail({key: 1})


def test_not_too_many_keys_and_not_a_dict():
    good_detail(**{f"k{i}": i for i in range(20)})
    bad_detail({f"k{i}": i for i in range(21)})
    for bad in (None, [], "text", 5):
        with pytest.raises(ValueError):
            records.check_stop_detail(bad)


def test_the_denylist_still_applies_as_a_second_check_to_numbers_under_telling_names():
    for key in ("question", "query", "prompt", "answer", "note", "text"):
        bad_detail({key: 1})
