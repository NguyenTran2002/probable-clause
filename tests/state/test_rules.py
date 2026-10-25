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


def month_doc(ms=0.0, mr=0.0, ds=0.0, dr=0.0, day="2030-05-14"):
    return {"_id": "2030-05", "spent": ms, "reserved": mr, "days": {day: {"spent": ds, "reserved": dr, "runs_started": 0}},
            "reservations": {}}


# --- the cap rule ---------------------------------------------------------------------------------------------------
# 1.674 is an example worst case (T3.4's before P4.6, now $2.106); the rule takes the amount it is given.

def test_no_document_means_an_empty_month():
    assert rules.cap_verdict(None, "2030-05-14", 1.674) is None
    assert rules.day_totals(None, "2030-05-14") == rules.Totals(0.0, 0.0, 0.0, 0.0)


def test_fits_within_both_caps():
    assert rules.cap_verdict(month_doc(ms=10, mr=5, ds=3, dr=2), "2030-05-14", 1.674) is None


def test_daily_cap_counts_day_spent_plus_day_reserved_plus_the_worst_case():
    assert rules.cap_verdict(month_doc(ms=0, mr=0, ds=4, dr=4.4), "2030-05-14", 1.674) == "daily_cap"   # 10.074
    assert rules.cap_verdict(month_doc(ms=0, mr=0, ds=4, dr=4.3), "2030-05-14", 1.674) is None          # 9.974


def test_monthly_cap_counts_month_spent_plus_month_reserved_plus_the_worst_case():
    assert rules.cap_verdict(month_doc(ms=50, mr=8.4), "2030-05-14", 1.674) == "monthly_cap"            # 60.074
    assert rules.cap_verdict(month_doc(ms=50, mr=8.3), "2030-05-14", 1.674) is None                     # 59.974


def test_caps_are_inclusive_with_a_tolerance_for_float_noise():
    assert rules.cap_verdict(month_doc(ds=7.5), "2030-05-14", 2.5) is None                  # exactly $10.00
    assert rules.cap_verdict(month_doc(ds=10.000000000000004 - 0.4), "2030-05-14", 0.4) is None
    assert rules.cap_verdict(month_doc(ds=7.5), "2030-05-14", 2.51) == "daily_cap"


def test_monthly_cap_is_reported_first_when_both_fail():
    assert rules.cap_verdict(month_doc(ms=59, mr=0, ds=9.5), "2030-05-14", 1.674) == "monthly_cap"


def test_a_day_with_no_entry_is_empty():
    assert rules.cap_verdict(month_doc(ms=1), "2030-05-15", 1.674) is None


def test_a_partial_document_never_passes_by_accident():
    # missing fields read as zero, never as "less than any cap"
    doc = {"_id": "2030-05", "days": {"2030-05-14": {"stops": {"atlas_unreachable": 1}}}}
    assert rules.cap_verdict(doc, "2030-05-14", 1.674) is None
    assert rules.cap_verdict(doc, "2030-05-14", 11.0) == "daily_cap"
    assert rules.cap_verdict(doc, "2030-05-14", 61.0) == "monthly_cap"


def test_caps_come_from_settings_at_call_time(monkeypatch):
    monkeypatch.setattr(settings, "DAILY_CAP_USD", settings.Setting(1.0, "test"))
    assert rules.cap_verdict(None, "2030-05-14", 1.674) == "daily_cap"


# --- validation ------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("run_id", ["a", "run-1", "AbC_123-xyz", "x" * 128])
def test_good_run_ids(run_id):
    assert rules.check_run_id(run_id) == run_id


@pytest.mark.parametrize("run_id", ["", "a.b", "$x", "a b", "a/b", "x" * 129, None, 5, "a\x00"])
def test_bad_run_ids(run_id):
    with pytest.raises(ValueError):
        rules.check_run_id(run_id)


@pytest.mark.parametrize("bad", [0, 0.0, -1.0, float("nan"), float("inf"), None, "1"])
def test_worst_case_must_be_positive_and_finite(bad):
    with pytest.raises(ValueError):
        rules.check_worst(bad)


def test_cost_may_be_zero_but_not_negative_or_nan():
    assert rules.check_cost(0.0) == 0.0
    for bad in (-0.01, float("nan"), float("inf"), None):
        with pytest.raises(ValueError):
            rules.check_cost(bad)


def test_stop_kinds_are_the_closed_vocabulary():
    for k in BUDGET_STOPS | {"atlas_unreachable", "time_limit"}:
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
    t = rules.Totals(1.0, 2.0, 3.0, 4.0)
    d = rules.stop_document("daily_cap", "run-a", datetime(2030, 5, 15, 3, 4, 5, tzinfo=ZoneInfo("UTC")), t, {"x": 1})
    assert d["date"] == "2030-05-14" and d["time"] == "22:04:05"
    assert d["kind"] == "daily_cap" and d["run"] == "run-a" and d["budget"] is True
    assert (d["month_spent"], d["month_reserved"], d["day_spent"], d["day_reserved"]) == (1.0, 2.0, 3.0, 4.0)
    assert d["detail"] == {"x": 1}
    assert d["at"] == datetime(2030, 5, 15, 3, 4, 5, tzinfo=ZoneInfo("UTC"))


def test_stop_document_for_a_non_budget_stop_and_unknown_totals():
    d = rules.stop_document("atlas_unreachable", None, NOW, None, {})
    assert d["budget"] is False and d["run"] is None
    assert d["month_spent"] is None and d["day_reserved"] is None      # unknown, not zero


# --- /health -----------------------------------------------------------------------------------------------------------

def test_health_view():
    assert rules.health_view(None, False, False, "2030-05-14", 1.674) == {"live_research": "open", "update_check": "available"}
    full_day = month_doc(ds=8.4)
    assert rules.health_view(full_day, False, False, "2030-05-14", 1.674)["live_research"] == "paused_day"
    full_month = month_doc(ms=58.4)
    assert rules.health_view(full_month, False, False, "2030-05-14", 1.674)["live_research"] == "paused_month"
    assert rules.health_view(None, True, False, "2030-05-14", 1.674)["live_research"] == "paused_month"
    assert rules.health_view(None, False, True, "2030-05-14", 1.674) == {"live_research": "open", "update_check": "unavailable"}


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
