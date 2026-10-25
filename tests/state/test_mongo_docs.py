"""api/state/mongo_docs.py: the filters and updates MongoStore sends, built by pure functions (no network).

The reserve filter is also checked against the shared rule (`rules.cap_verdict`) over a grid of states, using
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
W = 1.674


# --- reserve ---------------------------------------------------------------------------------------------------

def test_reserve_filter_is_one_document_that_names_the_month_and_the_run():
    f = md.reserve_filter(MONTH, DAY, "run-a", W)
    assert f["_id"] == MONTH
    assert f["reservations.run-a"] == {"$exists": False}
    assert "$expr" in f


def test_reserve_filter_guards_every_field_read_with_ifnull():
    import json
    text = json.dumps(md.reserve_filter(MONTH, DAY, "run-a", W)["$expr"])
    # four reads: month spent and reserved, day spent and reserved; each wrapped
    assert text.count('"$ifNull"') == 4
    for path in ("$spent", "$reserved", f"$days.{DAY}.spent", f"$days.{DAY}.reserved"):
        assert f'["{path}", 0]' in text


def test_reserve_update_moves_the_worst_case_into_reserved_and_counts_the_start():
    u = md.reserve_update(DAY, "run-a", W, NOW)
    assert u["$inc"]["reserved"] == W and u["$inc"][f"days.{DAY}.reserved"] == W
    assert u["$inc"][f"days.{DAY}.runs_started"] == 1
    assert u["$inc"][f"days.{DAY}.spent"] == 0.0            # creates the field so the day always has its full shape
    entry = u["$set"]["reservations.run-a"]
    assert entry["day"] == DAY and entry["amount"] == W and entry["at"] == NOW.astimezone(UTC)
    assert entry["at"].tzinfo is not None


def test_ensure_month_only_sets_defaults_on_insert():
    u = md.ensure_month_update()
    assert set(u) == {"$setOnInsert"}
    assert u["$setOnInsert"] == {"spent": 0.0, "reserved": 0.0, "reservations": {}}


@pytest.mark.parametrize("ms,mr,ds,dr,has_day,worst", list(itertools.product(
    [0.0, 20.0, 50.0, 58.3, 58.4, 60.0], [0.0, 5.0, 8.4], [0.0, 3.0, 8.3, 8.4], [0.0, 1.0], [True, False], [0.4, W, 11.0])))
def test_reserve_filter_agrees_with_the_shared_rule(ms, mr, ds, dr, has_day, worst):
    doc = {"_id": MONTH, "spent": ms, "reserved": mr, "reservations": {}}
    doc["days"] = {DAY: {"spent": ds, "reserved": dr, "runs_started": 0}} if has_day else {}
    ok = matches(doc, md.reserve_filter(MONTH, DAY, "run-a", worst))
    assert ok == (rules.cap_verdict(doc, DAY, worst) is None)


def test_reserve_filter_refuses_a_run_that_already_holds_a_reservation():
    doc = {"_id": MONTH, "spent": 0, "reserved": 1.0, "days": {}, "reservations": {"run-a": {"day": DAY, "amount": 1.0}}}
    assert not matches(doc, md.reserve_filter(MONTH, DAY, "run-a", 0.5))
    assert matches(doc, md.reserve_filter(MONTH, DAY, "run-b", 0.5))


def test_reserve_filter_on_a_partial_document_is_still_checked():
    doc = {"_id": MONTH, "days": {DAY: {"stops": {"atlas_unreachable": 1}}}}
    assert matches(doc, md.reserve_filter(MONTH, DAY, "run-a", W))
    assert not matches(doc, md.reserve_filter(MONTH, DAY, "run-a", 11.0))
    assert not matches(doc, md.reserve_filter(MONTH, DAY, "run-a", 61.0))


def test_the_filter_for_another_month_never_matches():
    doc = {"_id": "2030-06", "spent": 0, "reserved": 0, "days": {}, "reservations": {}}
    assert not matches(doc, md.reserve_filter(MONTH, DAY, "run-a", W))


# --- settle and release ----------------------------------------------------------------------------------------------

def test_settle_full_move_is_one_conditional_update_on_what_is_left_of_the_reservation():
    f = md.settle_full_filter(MONTH, "run-a", 0.5)
    assert f == {"_id": MONTH, "reservations.run-a.amount": {"$gte": 0.5}}
    u = md.settle_full_update(DAY, "run-a", 0.5)
    assert u == {"$inc": {"spent": 0.5, f"days.{DAY}.spent": 0.5, "reserved": -0.5, f"days.{DAY}.reserved": -0.5,
                          "reservations.run-a.amount": -0.5}}


def test_settle_clamped_moves_only_what_the_reservation_still_holds():
    f = md.settle_clamped_filter(MONTH, "run-a", 0.3)
    assert f == {"_id": MONTH, "reservations.run-a.amount": 0.3}
    u = md.settle_clamped_update(DAY, "run-a", cost=0.5, moved=0.3)
    assert u["$inc"] == {"spent": 0.5, f"days.{DAY}.spent": 0.5, "reserved": -0.3, f"days.{DAY}.reserved": -0.3,
                         "reservations.run-a.amount": -0.3}


def test_settle_with_no_reservation_left_counts_spend_only():
    f = md.settle_clamped_filter(MONTH, "run-a", None)
    assert f == {"_id": MONTH, "reservations.run-a": {"$exists": False}}
    u = md.settle_clamped_update(DAY, "run-a", cost=0.5, moved=0.0)
    assert u["$inc"] == {"spent": 0.5, f"days.{DAY}.spent": 0.5}


def test_settle_spent_only_upsert_creates_the_month_with_defaults():
    u = md.settle_spent_only_update(DAY, 0.5)
    assert u["$inc"] == {"spent": 0.5, f"days.{DAY}.spent": 0.5}
    assert u["$setOnInsert"] == {"reserved": 0.0, "reservations": {}}


def test_release_is_a_compare_and_swap_on_the_remaining_amount():
    assert md.release_filter(MONTH, "run-a", 1.174) == {"_id": MONTH, "reservations.run-a.amount": 1.174}
    u = md.release_update(DAY, "run-a", 1.174)
    assert u == {"$inc": {"reserved": -1.174, f"days.{DAY}.reserved": -1.174}, "$unset": {"reservations.run-a": ""}}


def test_undoing_a_reservation_also_uncounts_the_start():
    u = md.release_update(DAY, "run-a", 1.674, uncount_start=True)
    assert u["$inc"][f"days.{DAY}.runs_started"] == -1


def test_no_update_names_a_path_and_its_parent():
    # MongoDB refuses conflicting paths; the fake does too, so build each and apply it to a document
    from tests.state.fakes import _apply
    doc = {"_id": MONTH, "spent": 0.0, "reserved": 5.0, "days": {DAY: {"spent": 0.0, "reserved": 5.0, "runs_started": 1}},
           "reservations": {"run-a": {"day": DAY, "amount": 5.0}}}
    for u in (md.reserve_update(DAY, "run-b", W, NOW), md.settle_full_update(DAY, "run-a", 0.5),
              md.settle_clamped_update(DAY, "run-a", 0.5, 0.3), md.release_update(DAY, "run-a", 5.0, uncount_start=True),
              md.stop_count_update(DAY, "daily_cap"), md.settle_spent_only_update(DAY, 0.5)):
        _apply(doc, u, inserting=False)


# --- stop counts, flags, heartbeats ------------------------------------------------------------------------------------

def test_stop_count_update_counts_the_kind_on_the_day_and_defaults_the_month():
    u = md.stop_count_update(DAY, "daily_cap")
    assert u["$inc"][f"days.{DAY}.stops.daily_cap"] == 1
    assert u["$inc"][f"days.{DAY}.spent"] == 0.0 and u["$inc"][f"days.{DAY}.reserved"] == 0.0
    assert u["$inc"][f"days.{DAY}.runs_started"] == 0
    assert u["$setOnInsert"] == {"spent": 0.0, "reserved": 0.0, "reservations": {}}


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
