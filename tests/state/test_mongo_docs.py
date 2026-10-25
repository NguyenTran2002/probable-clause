"""api/state/mongo_docs.py: the filters and updates MongoStore sends, built by pure functions (no network).

The admit filter is also checked against the shared rule (`rules.cap_verdict`) over a grid of states, using
the fake database's matcher, which follows MongoDB's null ordering.
"""

import itertools
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

import pytest

from api import settings
from api.state import mongo_docs as md
from api.state import rules
from tests.state.fakes import matches

CHI = ZoneInfo("America/Chicago")
NOW = datetime(2030, 5, 14, 12, 0, tzinfo=CHI)
DAY, MONTH = "2030-05-14", "2030-05"


# --- admit ---------------------------------------------------------------------------------------------------

def test_admit_filter_is_one_document_that_names_the_month():
    f = md.admit_filter(MONTH, DAY)
    assert set(f) == {"_id", "$expr"} and f["_id"] == MONTH            # no run id in it, no reservation to look for


def test_admit_filter_guards_every_field_read_with_ifnull():
    import json
    text = json.dumps(md.admit_filter(MONTH, DAY)["$expr"])
    # two reads: the month's spent and the day's spent; each wrapped
    assert text.count('"$ifNull"') == 2
    for path in ("$spent", f"$days.{DAY}.spent"):
        assert f'["{path}", 0]' in text
    assert "reserved" not in text


def test_admit_filter_is_strictly_under_each_cap():
    # tests/state/conftest.py pins the daily cap at $10; the filter reads the settings when it is built
    f = md.admit_filter(MONTH, DAY)["$expr"]["$and"]
    assert [list(c) for c in f] == [["$lt"], ["$lt"]]                   # $lt, never $lte
    assert f[0]["$lt"][1] == pytest.approx(float(settings.MONTHLY_CAP_USD.value), abs=1e-6)
    assert f[1]["$lt"][1] == pytest.approx(float(settings.DAILY_CAP_USD.value), abs=1e-6)
    assert f[0]["$lt"][1] < float(settings.MONTHLY_CAP_USD.value) and f[1]["$lt"][1] < float(settings.DAILY_CAP_USD.value)


def test_admit_update_counts_the_start_and_creates_the_whole_shape():
    u = md.admit_update(DAY)
    assert u == {"$inc": {"spent": 0.0, f"days.{DAY}.spent": 0.0, f"days.{DAY}.runs_started": 1}}
    assert set(u) == {"$inc"}                                           # no $set of a reservation


def test_ensure_month_only_sets_defaults_on_insert():
    assert rules.month_defaults() == {"spent": 0.0} and rules.day_defaults() == {"spent": 0.0, "runs_started": 0}
    u = md.ensure_month_update()
    assert u == {"$setOnInsert": {"spent": 0.0, "days": {}}}              # the shape MemoryStore makes, days included


@pytest.mark.parametrize("ms,ds,has_day", list(itertools.product(
    [0.0, 20.0, 59.99, 59.9999999999, 60.0, 61.0], [0.0, 3.0, 9.99, 9.9999999999, 10.0, 16.0], [True, False])))
def test_admit_filter_agrees_with_the_shared_rule(ms, ds, has_day):
    doc = {"_id": MONTH, "spent": ms}
    doc["days"] = {DAY: {"spent": ds, "runs_started": 0}} if has_day else {}
    ok = matches(doc, md.admit_filter(MONTH, DAY))
    assert ok == (rules.cap_verdict(doc, DAY) is None)


def test_admit_filter_ignores_old_reserved_fields():
    doc = {"_id": MONTH, "spent": 1.0, "reserved": 59.0, "days": {DAY: {"spent": 1.0, "reserved": 14.0, "runs_started": 1}},
           "reservations": {"old": {"day": DAY, "amount": 59.0}}}
    assert matches(doc, md.admit_filter(MONTH, DAY))


def test_admit_filter_on_a_partial_document_is_still_checked():
    doc = {"_id": MONTH, "days": {DAY: {"stops": {"atlas_unreachable": 1}}}}
    assert matches(doc, md.admit_filter(MONTH, DAY))                   # a missing spent counts as zero
    assert not matches({"_id": MONTH, "spent": 60.0, "days": {}}, md.admit_filter(MONTH, DAY))
    assert not matches({"_id": MONTH, "days": {DAY: {"spent": 10.0}}}, md.admit_filter(MONTH, DAY))


def test_the_filter_for_another_month_never_matches():
    doc = {"_id": "2030-06", "spent": 0, "days": {}}
    assert not matches(doc, md.admit_filter(MONTH, DAY))


# --- record_spend --------------------------------------------------------------------------------------------------

def test_spend_update_is_one_increment_of_both_totals_that_also_fills_the_day_shape():
    u = md.spend_update(DAY, 0.5)
    assert u == {"$inc": {"spent": 0.5, f"days.{DAY}.spent": 0.5, f"days.{DAY}.runs_started": 0}}


def test_no_update_names_a_path_and_its_parent():
    # MongoDB refuses conflicting paths; the fake does too, so build each and apply it to a document
    from tests.state.fakes import _apply
    doc = {"_id": MONTH, "spent": 0.0, "days": {DAY: {"spent": 0.0, "runs_started": 1}}}
    for u in (md.admit_update(DAY), md.spend_update(DAY, 0.5), md.stop_count_update(DAY, "daily_cap")):
        _apply(doc, u, inserting=False)
        _apply({}, u, inserting=True)


def test_an_upsert_through_the_updates_makes_a_whole_month():
    from tests.state.fakes import _apply
    for u in (md.admit_update(DAY), md.spend_update(DAY, 0.5), md.stop_count_update(DAY, "daily_cap")):
        doc = {"_id": MONTH}
        _apply(doc, u, inserting=True)
        assert set(doc) == {"_id", "spent", "days"} and {"spent", "runs_started"} <= set(doc["days"][DAY])


# --- stop counts, flags, heartbeats ------------------------------------------------------------------------------------

def test_stop_count_update_counts_the_kind_on_the_day_and_defaults_the_month():
    u = md.stop_count_update(DAY, "daily_cap")
    assert u["$inc"][f"days.{DAY}.stops.daily_cap"] == 1
    assert u["$inc"][f"days.{DAY}.spent"] == 0.0 and f"days.{DAY}.reserved" not in u["$inc"]
    assert u["$inc"][f"days.{DAY}.runs_started"] == 0
    assert u["$setOnInsert"] == {"spent": 0.0}


def test_flag_update_stores_the_lapse_time_as_a_bson_date():
    u = md.flag_update("exa_out_of_credit", datetime(2030, 6, 1, tzinfo=CHI), NOW)
    assert u["$set"]["until"] == datetime(2030, 6, 1, tzinfo=CHI).astimezone(UTC)
    assert u["$set"]["set_at"] == NOW.astimezone(UTC)


def test_heartbeat_update_stores_at_as_a_bson_date_keyed_by_run():
    u = md.heartbeat_update("run-a", 12, NOW)
    assert u["$set"] == {"run": "run-a", "last_event": 12, "at": NOW.astimezone(UTC)}


# --- indexes -----------------------------------------------------------------------------------------------------------

def test_index_specs_cover_section_8():
    specs = {(s.collection, s.name): s for s in md.index_specs()}
    ev = specs[("events", "run_n_unique")]
    assert ev.keys == [("run", 1), ("n", 1)] and ev.options == {"unique": True}
    ttl = specs[("events", "created_ttl")]
    assert ttl.keys == [("created", 1)] and ttl.options == {"expireAfterSeconds": int(settings.EVENTS_TTL_S.value)}
    assert specs[("runs", "run_unique")].options == {"unique": True}
    assert specs[("budget_stops", "at")].keys == [("at", 1)]
    hb = specs[("heartbeats", "at_ttl")]
    assert hb.options == {"expireAfterSeconds": int(settings.HEARTBEATS_TTL_S.value)}
    assert {s.collection for s in md.index_specs()} == {"events", "runs", "budget_stops", "heartbeats"}   # spend and flags use _id


def test_ttl_specs_are_marked_for_collmod():
    ttl = [s for s in md.index_specs() if "expireAfterSeconds" in s.options]
    assert {s.name for s in ttl} == {"created_ttl", "at_ttl"}
