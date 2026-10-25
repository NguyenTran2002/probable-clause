"""api/state/rules.py: the money rules both stores share (T3.4, T3.7)."""

import math
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from api import settings
from api.protocols import BUDGET_STOPS
from api.state import rules

CHI = ZoneInfo("America/Chicago")
NOW = datetime(2030, 5, 14, 12, 0, tzinfo=CHI)


def month_doc(ms=0.0, ds=0.0, day="2030-05-14"):
    return {"_id": "2030-05", "spent": ms, "days": {day: {"spent": ds, "runs_started": 0}}}


# --- the cap rule (P4.21): spend so far, strictly under ---------------------------------------------------------------
# The caps in tests/state are conftest's: $10 a day, $60 a month.

def test_no_document_means_an_empty_month():
    assert rules.cap_verdict(None, "2030-05-14") is None
    assert rules.day_totals(None, "2030-05-14") == rules.Totals(0.0, 0.0)


def test_under_both_caps_is_admitted():
    assert rules.cap_verdict(month_doc(ms=10, ds=3), "2030-05-14") is None
    assert rules.cap_verdict(month_doc(ms=59.99, ds=9.99), "2030-05-14") is None


def test_the_daily_cap_is_strict_at_or_over_refuses():
    assert rules.cap_verdict(month_doc(ds=10.0), "2030-05-14") == "daily_cap"
    assert rules.cap_verdict(month_doc(ds=10.01), "2030-05-14") == "daily_cap"
    assert rules.cap_verdict(month_doc(ds=9.99), "2030-05-14") is None


def test_the_monthly_cap_is_strict_at_or_over_refuses():
    assert rules.cap_verdict(month_doc(ms=60.0), "2030-05-14") == "monthly_cap"
    assert rules.cap_verdict(month_doc(ms=60.5), "2030-05-14") == "monthly_cap"
    assert rules.cap_verdict(month_doc(ms=59.99), "2030-05-14") is None


def test_the_rule_looks_at_spend_so_far_never_at_what_a_run_might_spend():
    import inspect
    assert list(inspect.signature(rules.cap_verdict).parameters) == ["doc", "day"]
    assert rules.cap_verdict(month_doc(ds=9.999), "2030-05-14") is None       # a run that might spend $10 is still admitted


def test_float_noise_below_the_cap_counts_as_at_the_cap():
    assert rules.cap_verdict(month_doc(ds=10.0 - 1e-12), "2030-05-14") == "daily_cap"
    assert rules.cap_verdict(month_doc(ds=sum([0.1] * 100)), "2030-05-14") == "daily_cap"      # 9.99999999999998
    assert rules.under_cap(9.9, 10.0) and not rules.under_cap(10.0, 10.0) and not rules.under_cap(10.5, 10.0)


def test_monthly_cap_is_reported_first_when_both_are_reached():
    assert rules.cap_verdict(month_doc(ms=60.0, ds=10.0), "2030-05-14") == "monthly_cap"


def test_a_day_with_no_entry_is_empty():
    assert rules.cap_verdict(month_doc(ms=1), "2030-05-15") is None


def test_a_partial_document_never_passes_by_accident():
    # missing fields read as zero, never as "less than any cap"; a missing spent is below the cap only because it is zero
    doc = {"_id": "2030-05", "days": {"2030-05-14": {"stops": {"atlas_unreachable": 1}}}}
    assert rules.cap_verdict(doc, "2030-05-14") is None
    assert rules.day_totals(doc, "2030-05-14") == rules.Totals(0.0, 0.0)
    assert rules.cap_verdict({"_id": "2030-05", "days": {"2030-05-14": {"spent": 10.0}}}, "2030-05-14") == "daily_cap"


def test_a_null_spent_reads_as_zero_like_ifnull():
    doc = {"_id": "2030-05", "spent": None, "days": {"2030-05-14": {"spent": None}}}
    assert rules.day_totals(doc, "2030-05-14") == rules.Totals(0.0, 0.0)
    assert rules.cap_verdict(doc, "2030-05-14") is None
    assert rules.day_totals({"_id": "m", "days": {"2030-05-14": None}}, "2030-05-14") == rules.Totals(0.0, 0.0)


@pytest.mark.parametrize("doc", [
    {"spent": "1"}, {"spent": True}, {"spent": float("nan")}, {"spent": [1.0]}, {"days": "x"},
    {"days": {"2030-05-14": "x"}}, {"days": {"2030-05-14": {"spent": "x"}}}, {"days": {"2030-05-14": {"spent": float("inf")}}},
])
def test_a_malformed_document_raises_malformed_document_not_a_type_error(doc):
    with pytest.raises(rules.MalformedDocument):
        rules.cap_verdict(doc, "2030-05-14")
    with pytest.raises(rules.MalformedDocument):
        rules.day_totals(doc, "2030-05-14")
    assert issubclass(rules.MalformedDocument, ValueError)


def test_old_reserved_fields_are_not_spend():
    old = {"_id": "2030-05", "spent": 1.0, "reserved": 59.0,
           "days": {"2030-05-14": {"spent": 1.0, "reserved": 9.5, "runs_started": 4}}, "reservations": {"r": {"amount": 59.0}}}
    assert rules.day_totals(old, "2030-05-14") == rules.Totals(1.0, 1.0)
    assert rules.cap_verdict(old, "2030-05-14") is None


def test_caps_come_from_settings_at_call_time(monkeypatch):
    monkeypatch.setattr(settings, "DAILY_CAP_USD", settings.Setting(1.0, "test"))
    assert rules.cap_verdict(month_doc(ds=1.0), "2030-05-14") == "daily_cap"
    assert rules.cap_verdict(month_doc(ds=0.99), "2030-05-14") is None
    monkeypatch.setattr(settings, "MONTHLY_CAP_USD", settings.Setting(5.0, "test"))
    assert rules.cap_verdict(month_doc(ms=5.0), "2030-05-14") == "monthly_cap"


# --- validation ------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("run_id", ["a", "run-1", "AbC_123-xyz", "x" * 128])
def test_good_run_ids(run_id):
    assert rules.check_run_id(run_id) == run_id


@pytest.mark.parametrize("run_id", ["", "a.b", "$x", "a b", "a/b", "x" * 129, None, 5, "a\x00"])
def test_bad_run_ids(run_id):
    with pytest.raises(ValueError):
        rules.check_run_id(run_id)


def test_there_is_no_worst_case_check_any_more():
    assert not hasattr(rules, "check_worst")


def test_cost_may_be_zero_but_not_negative_or_not_a_number():
    assert rules.check_cost(0.0) == 0.0 and rules.check_cost(3) == 3.0
    for bad in (-0.01, -1, float("nan"), float("inf"), float("-inf"), None, "1", True, False, [1.0]):
        with pytest.raises(ValueError):
            rules.check_cost(bad)


def test_an_admission_is_checked_before_its_day_goes_into_a_path():
    from api.protocols import Admission
    rules.check_admission(Admission("run-a", "2030-05", "2030-05-14"))
    for bad in (Admission("run-a", "2030-5", "2030-05-14"), Admission("run-a", "2030-05", "2030-05-1"),
                Admission("run-a", "2030-05", "2030-06-14"), Admission("run-a", "2030-05", "2030-05-14.x"),
                Admission("run-a", "2030-13", "2030-13-01"), Admission("a.b", "2030-05", "2030-05-14"),
                Admission("run-a", None, "2030-05-14")):
        with pytest.raises(ValueError):
            rules.check_admission(bad)


def test_stop_kinds_are_the_closed_vocabulary():
    for k in BUDGET_STOPS | {"atlas_unreachable", "time_limit", "update_time_limit"}:
        assert rules.check_stop_kind(k) == k
    with pytest.raises(ValueError):
        rules.check_stop_kind("coffee_break")


def test_flag_names():
    assert rules.check_flag_name("exa_out_of_credit") == "exa_out_of_credit"
    with pytest.raises(ValueError):
        rules.check_flag_name("other")


# --- T3.7: records never hold the question or the answer ---------------------------------------------------------------

def test_forbidden_keys_are_found_at_any_depth():
    assert rules.find_forbidden_keys({"run": "r", "rounds": 3, "answer_chars": 10}) == []
    assert rules.find_forbidden_keys({"question": "q"}) == ["question"]
    assert rules.find_forbidden_keys({"a": {"b": [{"answer": "x"}, {"ok": 1}]}}) == ["a.b[0].answer"]
    assert set(rules.find_forbidden_keys({"note": "n", "scope_note": "s", "text": "t", "queries": [], "answer_text": "x"})) == {
        "note", "scope_note", "text", "queries", "answer_text"}


def test_check_no_text_raises_naming_the_key_not_the_value():
    with pytest.raises(ValueError) as e:
        rules.check_no_text({"question": "my secret question"}, "run record")
    assert "question" in str(e.value) and "my secret question" not in str(e.value)


# --- the stop record ---------------------------------------------------------------------------------------------------

def test_stop_document_has_chicago_date_and_time_and_budget_flag():
    t = rules.Totals(1.0, 3.0)
    d = rules.stop_document("daily_cap", "run-a", datetime(2030, 5, 15, 3, 4, 5, tzinfo=ZoneInfo("UTC")), t, {"x": 1})
    assert d["date"] == "2030-05-14" and d["time"] == "22:04:05"
    assert d["kind"] == "daily_cap" and d["run"] == "run-a" and d["budget"] is True
    assert (d["month_spent"], d["day_spent"]) == (1.0, 3.0)
    assert "month_reserved" not in d and "day_reserved" not in d
    assert d["detail"] == {"x": 1}
    assert d["at"] == datetime(2030, 5, 15, 3, 4, 5, tzinfo=ZoneInfo("UTC"))


def test_stop_document_for_a_non_budget_stop_and_unknown_totals():
    d = rules.stop_document("atlas_unreachable", None, NOW, None, {})
    assert d["budget"] is False and d["run"] is None
    assert d["month_spent"] is None and d["day_spent"] is None         # unknown, not zero


# --- /health -----------------------------------------------------------------------------------------------------------

def test_health_view():
    assert rules.health_view(None, False, False, "2030-05-14") == {"live_research": "open", "update_check": "available"}
    assert rules.health_view(month_doc(ds=9.99), False, False, "2030-05-14")["live_research"] == "open"
    assert rules.health_view(month_doc(ds=10.0), False, False, "2030-05-14")["live_research"] == "paused_day"
    assert rules.health_view(month_doc(ms=60.0), False, False, "2030-05-14")["live_research"] == "paused_month"
    assert rules.health_view(month_doc(ms=60.0, ds=10.0), False, False, "2030-05-14")["live_research"] == "paused_month"
    assert rules.health_view(None, True, False, "2030-05-14")["live_research"] == "paused_month"
    assert rules.health_view(None, False, True, "2030-05-14") == {"live_research": "open", "update_check": "unavailable"}


def test_unknown_view():
    assert rules.UNKNOWN_HEALTH == {"live_research": "unknown", "update_check": "unknown"}


def test_eps_is_tiny_and_documented():
    assert 0 < rules.EPS < 1e-6 and math.isfinite(rules.EPS)


# --- the denylist is a second check, now case-insensitive and wider ---------------------------------------------------

def test_the_denylist_catches_the_reviewers_probe_in_any_case():
    probe = {"q": 1, "prompt": 1, "Question": 1, "content": 1, "summary": 1, "reason": 1, "title": 1, "statement": 1,
             "message": 1}
    found = rules.find_forbidden_keys(probe)
    assert {f.lower() for f in found} >= {"prompt", "question", "content", "summary", "reason", "title", "statement", "message"}
    assert rules.find_forbidden_keys({"a": {"Query": 1}}) == ["a.Query"]
