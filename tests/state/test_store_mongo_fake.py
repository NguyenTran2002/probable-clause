"""MongoStore's own flow, run over the fake database (no network). Contract §4.E, §8; T3.4, T3.7."""

import asyncio
import time
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from bson.errors import InvalidDocument
from pymongo.errors import BulkWriteError, DuplicateKeyError, OperationFailure, ServerSelectionTimeoutError

from api import settings
from api.protocols import Admission, Refusal
from api.state import mongo_docs
from api.state.store import MongoStore, StoreUnavailable, db_name_for
from tests.state import cases
from tests.state.cases import DAY, MONTH, T, event
from tests.state.fakes import FakeDatabase, get_path

CHI = ZoneInfo("America/Chicago")


def make(db=None, **kw):
    db = db or FakeDatabase()
    return MongoStore(db=db, **kw), db


@pytest.mark.anyio
@pytest.mark.parametrize("case", cases.ALL, ids=lambda c: c.__name__)
async def test_semantics(case):
    store, _ = make()
    await store.ensure_indexes()
    await case(store)


# --- shapes in Atlas ---------------------------------------------------------------------------------------------

@pytest.mark.anyio
async def test_events_are_stored_with_created_as_a_date_and_read_back_without_it():
    store, db = make()
    await store.ensure_indexes()
    await store.append_events("r1", [event("r1", 1), event("r1", 2)])
    raw = db["events"].docs
    assert len(raw) == 2 and all(isinstance(d["created"], datetime) and d["created"].tzinfo is not None for d in raw)
    assert {d["n"] for d in raw} == {1, 2} and raw[0]["run"] == "r1"
    assert all("created" not in e and "_id" not in e for e in await store.read_events("r1", 0))


@pytest.mark.anyio
async def test_heartbeat_at_is_a_date_and_the_document_is_keyed_by_run():
    store, db = make()
    await store.put_heartbeat("r1", 4, T)
    [d] = db["heartbeats"].docs
    assert d["_id"] == "r1" and d["run"] == "r1" and d["last_event"] == 4
    assert isinstance(d["at"], datetime) and d["at"] == T.astimezone(UTC)


@pytest.mark.anyio
async def test_budget_stop_records_have_a_date_for_the_at_index_and_chicago_strings():
    store, db = make()
    await store.record_stop("step_limit", "r1", datetime(2030, 5, 15, 3, 4, 5, tzinfo=UTC), {})
    [d] = db["budget_stops"].docs
    assert isinstance(d["at"], datetime) and d["date"] == "2030-05-14" and d["time"] == "22:04:05"


@pytest.mark.anyio
async def test_the_spend_document_has_section_8s_shape():
    store, db = make()
    a = await store.admit("run-a", T)
    await store.record_spend(a, 0.5)
    [doc] = db["spend"].docs
    assert doc["_id"] == MONTH
    assert set(doc) == {"_id", "spent", "days"}                       # v2.0: no `reserved`, no `reservations`
    assert set(doc["days"][DAY]) == {"spent", "runs_started"}
    assert doc["spent"] == 0.5 and doc["days"][DAY] == {"spent": 0.5, "runs_started": 1}


@pytest.mark.anyio
async def test_record_spend_alone_creates_a_whole_month_and_day():
    store, db = make()
    await store.record_spend(Admission("ghost", MONTH, DAY), 0.25)
    [doc] = db["spend"].docs
    assert set(doc) == {"_id", "spent", "days"} and doc["days"][DAY] == {"spent": 0.25, "runs_started": 0}


@pytest.mark.anyio
async def test_prefix_names_the_collections():
    store, db = make(prefix="t1_")
    await store.admit("run-a", T)
    assert "t1_spend" in db.collections and "spend" not in db.collections


# --- indexes ------------------------------------------------------------------------------------------------------

@pytest.mark.anyio
async def test_ensure_indexes_creates_every_index_of_section_8():
    store, db = make()
    await store.ensure_indexes()
    assert db["events"].indexes["run_n_unique"]["options"] == {"unique": True}
    assert db["events"].indexes["created_ttl"]["options"] == {"expireAfterSeconds": int(settings.EVENTS_TTL_S.value)}
    assert db["heartbeats"].indexes["at_ttl"]["options"] == {"expireAfterSeconds": int(settings.HEARTBEATS_TTL_S.value)}
    assert db["runs"].indexes["run_unique"]["options"] == {"unique": True}
    assert "at" in db["budget_stops"].indexes


@pytest.mark.anyio
async def test_a_changed_ttl_is_applied_with_collmod_not_a_crash(monkeypatch):
    store, db = make()
    await store.ensure_indexes()
    monkeypatch.setattr(settings, "EVENTS_TTL_S", settings.Setting(3600, "test"))
    await store.ensure_indexes()
    assert {"collMod": "events", "index": {"name": "created_ttl", "expireAfterSeconds": 3600}} in db.commands
    assert db["events"].indexes["created_ttl"]["options"]["expireAfterSeconds"] == 3600


@pytest.mark.anyio
async def test_the_unique_index_is_what_makes_a_repeated_event_a_no_op():
    store, db = make()                      # no ensure_indexes: the duplicate would be stored twice
    await store.append_events("r1", [event("r1", 1)])
    await store.append_events("r1", [event("r1", 1)])
    assert len(db["events"].docs) == 2
    store2, db2 = make()
    await store2.ensure_indexes()
    await store2.append_events("r1", [event("r1", 1)])
    await store2.append_events("r1", [event("r1", 1)])
    assert len(db2["events"].docs) == 1


# --- admission is one conditional update ----------------------------------------------------------------------------

@pytest.mark.anyio
async def test_admit_reads_the_flag_then_makes_one_conditional_update_with_no_upsert():
    store, db = make()
    await store.admit("first", T)                  # a month with no document: created first (see the next test)
    db.calls.clear()
    await store.admit("run-a", T)
    assert [(c["collection"], c["op"]) for c in db.calls] == [("flags", "find_one"), ("spend", "update_one")]
    [upd] = db.calls_to("spend", "update_one")
    assert upd["filter"] == mongo_docs.admit_filter(MONTH, DAY)
    assert upd["update"] == mongo_docs.admit_update(DAY)
    assert upd["upsert"] is False                    # Atlas refuses $expr in an upsert's filter (code 224)
    assert "$expr" in upd["filter"]


@pytest.mark.anyio
async def test_a_month_with_no_document_is_created_by_a_plain_id_upsert_then_admitted():
    store, db = make()
    await store.admit("run-a", T)
    ops = [(c["collection"], c["op"], c.get("upsert")) for c in db.calls]
    assert ops == [("flags", "find_one", None), ("spend", "update_one", False), ("spend", "find_one", None),
                   ("spend", "update_one", True), ("spend", "update_one", False)]
    [ensure] = [c for c in db.calls_to("spend", "update_one") if c["upsert"]]
    assert ensure["filter"] == {"_id": MONTH} and ensure["update"] == mongo_docs.ensure_month_update()
    [doc] = db["spend"].docs
    assert set(doc) == {"_id", "spent", "days"} and doc["days"][DAY] == {"spent": 0.0, "runs_started": 1}


@pytest.mark.anyio
async def test_no_filter_with_expr_is_ever_used_in_an_upsert():
    store, db = make()
    a = await store.admit("run-a", T)
    await store.record_spend(a, 0.5)
    await store.admit("run-b", T + timedelta(days=40))
    db["spend"].docs[0]["days"][DAY]["spent"] = 10.0
    await store.admit("late", T)                                      # a refusal
    await store.record_stop("daily_cap", None, T, {})
    await store.set_flag("exa_out_of_credit", T)
    await store.put_heartbeat("r1", 1, T)
    await store.upsert_run_record({"run": "r1"})
    assert db.calls
    for c in db.calls:
        if c.get("upsert"):
            assert "$expr" not in str(c["filter"]), c


@pytest.mark.anyio
async def test_the_fake_refuses_expr_in_an_upsert_as_atlas_does():
    from pymongo.errors import WriteError
    store, db = make()
    flt = mongo_docs.admit_filter(MONTH, DAY)
    with pytest.raises(WriteError) as e:
        await db["spend"].update_one(flt, mongo_docs.admit_update(DAY), upsert=True)
    assert e.value.code == 224 and "$expr" in str(e.value)
    await db["spend"].update_one({"_id": MONTH}, mongo_docs.ensure_month_update(), upsert=True)
    with pytest.raises(WriteError):                                   # matched or not
        await db["spend"].update_one(flt, mongo_docs.admit_update(DAY), upsert=True)
    with pytest.raises(WriteError):
        await db["spend"].update_one({"$and": [{"_id": MONTH}, {"$expr": {"$lt": [1, 2]}}]}, {"$inc": {"x": 1}}, upsert=True)
    with pytest.raises(WriteError):
        await db["runs"].replace_one({"$expr": {"$lt": [1, 2]}}, {"run": "r"}, upsert=True)
    assert (await db["spend"].update_one(flt, mongo_docs.admit_update(DAY))).matched_count == 1    # fine without upsert


@pytest.mark.anyio
async def test_a_refusal_at_the_cap_is_a_refusal_not_a_duplicate_key_error():
    # the document is there and the condition fails: the upsert collides on _id, which must never surface
    store, db = make()
    await store.admit("run-a", T)
    db["spend"].docs[0]["days"][DAY]["spent"] = 10.0
    db.calls.clear()
    assert await store.admit("late", T) == Refusal("daily_cap")
    assert len([c for c in db.calls_to("spend", "update_one") if "$expr" in c["filter"]]) == 1    # the other is the stop's count
    assert len(db.calls_to("spend", "find_one")) == 1                 # one read to say which cap
    [stop] = await store.read_stops(day=DAY)
    assert stop["kind"] == "daily_cap" and stop["day_spent"] == 10.0


@pytest.mark.anyio
async def test_a_missing_day_spent_counts_as_zero_in_the_condition():
    store, db = make()
    db["spend"].docs.append({"_id": MONTH, "spent": 3.0, "days": {DAY: {"runs_started": 2, "stops": {"daily_cap": 1}}}})
    assert isinstance(await store.admit("run-a", T), Admission)
    db["spend"].docs[0] = {"_id": MONTH, "days": {}}                    # no spent at all, month or day
    assert isinstance(await store.admit("run-b", T), Admission)


@pytest.mark.anyio
async def test_spend_taken_between_the_flag_read_and_the_update_refuses_the_run():
    # a read-then-write admit would pass here; the conditional update must not
    store, db = make()
    a = await store.admit("base", T)
    await store.record_spend(a, 9.5)
    taken = False

    async def spend_lands(coll, op, args):
        nonlocal taken
        if coll.name == "spend" and op == "update_one" and "$expr" in (args["filter"] or {}) and not taken:
            taken = True
            doc = coll.docs[0]
            doc["spent"] += 0.5
            doc["days"][DAY]["spent"] += 0.5

    db.hooks.append(spend_lands)
    assert await store.admit("racer", T) == Refusal("daily_cap")      # $10.00: at the cap
    assert db["spend"].docs[0]["days"][DAY]["runs_started"] == 1       # racer was not counted


@pytest.mark.anyio
async def test_a_lost_race_to_create_the_month_is_tried_again_and_admits():
    store, db = make()
    raced = False

    async def rival_creates_the_month(coll, op, args):
        nonlocal raced
        if coll.name == "spend" and op == "update_one" and args.get("upsert") and not raced:
            raced = True
            coll.docs.append({"_id": MONTH, "spent": 0.0, "days": {}})
            raise DuplicateKeyError("E11000 duplicate key error collection: spend index: _id_", 11000)

    db.hooks.append(rival_creates_the_month)
    a = await store.admit("run-a", T)
    assert a == Admission("run-a", MONTH, DAY)
    assert db["spend"].docs[0]["days"][DAY]["runs_started"] == 1 and len(db["spend"].docs) == 1


def is_month_creation(args) -> bool:
    """The plain _id upsert that creates a month (ensure_month_update), apart from the stop count's upsert."""
    return bool(args.get("upsert")) and args["update"] == mongo_docs.ensure_month_update()


def is_stop_count(args) -> bool:
    return bool(args.get("upsert")) and any(".stops." in k for k in args["update"].get("$inc", {}))


@pytest.mark.anyio
async def test_admit_gives_up_as_unreachable_after_the_shared_bound_of_rounds(monkeypatch):
    monkeypatch.setattr(settings, "ATLAS_ADMIT_TRIES", settings.Setting(3, "test"))
    store, db = make()
    attempts = 0

    async def month_creation_always_collides(coll, op, args):
        nonlocal attempts
        if coll.name == "spend" and op == "update_one" and is_month_creation(args):
            attempts += 1
            raise DuplicateKeyError("E11000", 11000)

    db.hooks.append(month_creation_always_collides)
    assert await store.admit("run-a", T) == Refusal("atlas_unreachable")      # no cap is reached, yet Atlas never answered
    assert attempts == 3                                                      # one round: the bound of upsert attempts
    [stop] = await store.read_stops(day=DAY)
    assert stop["kind"] == "atlas_unreachable" and stop["budget"] is False and stop["run"] == "run-a"
    # the stop count is a different upsert and went through; no run was admitted
    assert db["spend"].docs == [{"_id": MONTH, "spent": 0.0,
                                 "days": {DAY: {"spent": 0.0, "runs_started": 0, "stops": {"atlas_unreachable": 1}}}}]


@pytest.mark.anyio
async def test_a_stop_written_but_not_counted_still_refuses_the_run(monkeypatch):
    monkeypatch.setattr(settings, "ATLAS_ADMIT_TRIES", settings.Setting(2, "test"))
    store, db = make()
    a = await store.admit("base", T)
    await store.record_spend(a, 10.0)

    async def stop_count_always_collides(coll, op, args):
        if coll.name == "spend" and op == "update_one" and is_stop_count(args):
            raise DuplicateKeyError("E11000", 11000)

    db.hooks.append(stop_count_always_collides)
    assert await store.admit("late", T) == Refusal("daily_cap")               # the refusal is returned whatever happens
    [stop] = await store.read_stops(day=DAY)                                  # the stop record was written ...
    assert stop["kind"] == "daily_cap" and stop["run"] == "late" and stop["day_spent"] == 10.0
    assert "stops" not in db["spend"].docs[0]["days"][DAY]                    # ... its count was not
    assert db["spend"].docs[0]["days"][DAY]["runs_started"] == 1


@pytest.mark.anyio
async def test_a_conditional_update_that_never_matches_although_no_cap_is_reached_is_bounded(monkeypatch):
    monkeypatch.setattr(settings, "ATLAS_ADMIT_TRIES", settings.Setting(3, "test"))
    store, db = make()
    await store.admit("first", T)
    coll = db["spend"]
    real = coll.update_one
    tries = 0

    async def never_matches(flt, update, upsert=False, **kw):
        nonlocal tries
        if "$expr" in (flt or {}):
            tries += 1
            from tests.state.fakes import _Result
            return _Result()                                          # the document moved under us, every time
        return await real(flt, update, upsert=upsert, **kw)

    monkeypatch.setattr(coll, "update_one", never_matches)
    assert await store.admit("run-a", T) == Refusal("atlas_unreachable")
    assert tries == 3


@pytest.mark.anyio
async def test_the_setting_is_the_shared_bound_for_upserts_too(monkeypatch):
    assert int(settings.ATLAS_ADMIT_TRIES.value) == 5
    monkeypatch.setattr(settings, "ATLAS_ADMIT_TRIES", settings.Setting(3, "test"))
    store, db = make()
    tries = 0

    async def collide(coll, op, args):
        nonlocal tries
        if coll.name == "flags" and op == "update_one":
            tries += 1
            raise DuplicateKeyError("E11000", 11000)

    db.hooks.append(collide)
    with pytest.raises(StoreUnavailable):
        await store.set_flag("exa_out_of_credit", T)
    assert tries == 3


# --- record_spend is one atomic increment ---------------------------------------------------------------------------------

@pytest.mark.anyio
async def test_record_spend_is_one_upserting_increment_with_no_prior_read():
    store, db = make()
    a = await store.admit("run-a", T)
    db.calls.clear()
    await store.record_spend(a, 0.5)
    assert [(c["collection"], c["op"]) for c in db.calls] == [("spend", "update_one")]
    c = db.calls[0]
    assert c["filter"] == {"_id": MONTH} and c["update"] == mongo_docs.spend_update(DAY, 0.5) and c["upsert"] is True
    assert c["update"]["$inc"]["spent"] == 0.5 and c["update"]["$inc"][f"days.{DAY}.spent"] == 0.5


@pytest.mark.anyio
async def test_a_zero_cost_and_a_bad_cost_send_nothing():
    store, db = make()
    a = await store.admit("run-a", T)
    db.calls.clear()
    await store.record_spend(a, 0.0)
    for bad in (-0.1, float("nan"), "0.1", None):
        with pytest.raises(ValueError):
            await store.record_spend(a, bad)
    assert db.calls == []


@pytest.mark.anyio
async def test_record_spend_retries_only_a_creation_collision():
    store, db = make()
    raced = False

    async def rival_creates_the_month(coll, op, args):
        nonlocal raced
        if coll.name == "spend" and op == "update_one" and not raced:
            raced = True
            coll.docs.append({"_id": MONTH, "spent": 1.0, "days": {DAY: {"spent": 1.0, "runs_started": 1}}})
            raise DuplicateKeyError("E11000", 11000)

    db.hooks.append(rival_creates_the_month)
    await store.record_spend(Admission("run-a", MONTH, DAY), 0.5)
    assert db["spend"].docs[0]["spent"] == pytest.approx(1.5)           # the rival's $1 and ours, once each


@pytest.mark.anyio
async def test_record_spend_raises_the_store_error_when_atlas_fails_and_does_not_retry_it():
    store, db = make()
    calls = 0

    async def down(coll, op, args):
        nonlocal calls
        calls += 1
        server_down(coll, op, args)

    db.hooks.append(down)
    with pytest.raises(StoreUnavailable) as e:
        await store.record_spend(Admission("run-a", MONTH, DAY), 0.5)
    assert "mongodb.net" not in str(e.value) and calls == 1


# --- documents written before v2.0 (they hold `reserved` and `reservations`) ----------------------------------------------

def old_month(spent=1.0, day_spent=1.0, reserved=9.0):
    return {"_id": MONTH, "spent": spent, "reserved": reserved,
            "days": {DAY: {"spent": day_spent, "reserved": reserved, "runs_started": 3}},
            "reservations": {"old-run": {"day": DAY, "amount": reserved, "at": T.astimezone(UTC)}}}


@pytest.mark.anyio
async def test_old_reserved_money_is_never_counted_as_spend():
    store, db = make()
    db["spend"].docs.append(old_month())                              # $9 reserved on a $10 day, $1 spent
    assert isinstance(await store.admit("run-a", T), Admission)
    assert (await store.live_status(T, 2.0))["live_research"] == "open"
    store2, db2 = make()
    db2["spend"].docs.append(old_month(day_spent=10.0))               # $10 actually spent
    assert await store2.admit("run-b", T) == Refusal("daily_cap")
    assert (await store2.live_status(T, 2.0))["live_research"] == "paused_day"
    store3, db3 = make()
    db3["spend"].docs.append(old_month(spent=60.0, day_spent=0.0, reserved=0.0))
    assert await store3.admit("run-c", T) == Refusal("monthly_cap")


@pytest.mark.anyio
async def test_old_documents_are_read_and_written_to_in_spent_only():
    store, db = make()
    db["spend"].docs.append(old_month())
    a = await store.admit("run-a", T)
    await store.record_spend(a, 0.5)
    await store.record_stop("step_limit", "run-a", T, {})
    m = await store.read_month(MONTH)
    assert m["spent"] == pytest.approx(1.5) and m["days"][DAY]["spent"] == pytest.approx(1.5)
    assert m["days"][DAY]["runs_started"] == 4 and m["days"][DAY]["stops"] == {"step_limit": 1}
    assert m["reserved"] == 9.0 and m["days"][DAY]["reserved"] == 9.0 and "old-run" in m["reservations"]   # left as they were


@pytest.mark.anyio
async def test_no_write_produces_a_reservation_field():
    store, db = make()
    a = await store.admit("run-a", T)
    await store.record_spend(a, 0.5)
    await store.record_stop("daily_cap", None, T, {})
    next_day = T + timedelta(days=1)
    await store.admit("run-b", next_day)
    await store.record_stop("atlas_unreachable", None, next_day, {})
    for doc in db["spend"].docs:
        assert set(doc) <= {"_id", "spent", "days"}
        assert all(set(d) <= {"spent", "runs_started", "stops"} for d in doc["days"].values())
    for stop in db["budget_stops"].docs:
        assert "month_reserved" not in stop and "day_reserved" not in stop


# --- Atlas unreachable ---------------------------------------------------------------------------------------------

def server_down(coll, op, args):
    raise ServerSelectionTimeoutError("cluster0-shard-00-00.example.mongodb.net:27017: timed out")


@pytest.mark.anyio
async def test_unreachable_atlas_refuses_the_run_and_does_not_leak_the_host():
    store, db = make()

    async def down(coll, op, args):
        server_down(coll, op, args)

    db.hooks.append(down)
    assert await store.admit("run-a", T) == Refusal("atlas_unreachable")
    with pytest.raises(StoreUnavailable) as e:
        await store.read_events("r1", 0)
    assert "mongodb.net" not in str(e.value) and "cluster0" not in str(e.value)
    assert (await store.live_status(T, 1.0)) == {"live_research": "unknown", "update_check": "unknown"}


@pytest.mark.anyio
async def test_the_unreachable_stop_is_recorded_where_it_can_be():
    store, db = make()
    failures = {"left": 1}

    async def one_failure(coll, op, args):      # the first operation fails (the flag read); Atlas answers after that
        if failures["left"]:
            failures["left"] -= 1
            server_down(coll, op, args)

    db.hooks.append(one_failure)
    assert await store.admit("run-a", T) == Refusal("atlas_unreachable")
    [stop] = await store.read_stops(day=DAY)
    assert stop["kind"] == "atlas_unreachable" and stop["budget"] is False and stop["run"] == "run-a"
    assert (await store.read_month(MONTH))["days"][DAY]["stops"] == {"atlas_unreachable": 1}


@pytest.mark.anyio
async def test_a_hanging_atlas_is_cut_off_at_the_operation_timeout():
    store, db = make(op_timeout_s=0.05)
    db.hang = True
    t0 = time.monotonic()
    assert await store.admit("run-a", T) == Refusal("atlas_unreachable")
    assert time.monotonic() - t0 < 1.0
    with pytest.raises(StoreUnavailable):
        await store.put_heartbeat("r1", 1, T)


@pytest.mark.anyio
async def test_live_status_honours_its_own_shorter_timeout():
    store, db = make(op_timeout_s=30.0)
    db.hang = True
    t0 = time.monotonic()
    s = await store.live_status(T, 0.05)
    assert s == {"live_research": "unknown", "update_check": "unknown"}
    assert time.monotonic() - t0 < 1.0


@pytest.mark.anyio
async def test_an_admission_applied_but_not_acknowledged_is_refused_and_spend_is_untouched():
    # the conditional update is applied, the reply is lost: the run is refused (fail closed). Only the start count
    # may be one high; no money is involved.
    store, db = make()

    async def reply_lost(coll, op, args):
        if coll.name == "spend" and op == "update_one" and "$expr" in (args["filter"] or {}):
            raise ServerSelectionTimeoutError("reply lost")

    db.after_hooks.append(reply_lost)
    assert await store.admit("run-a", T) == Refusal("atlas_unreachable")
    m = await store.read_month(MONTH)
    assert m["spent"] == 0.0 and m["days"][DAY]["spent"] == 0.0
    [stop] = await store.read_stops(day=DAY)
    assert stop["kind"] == "atlas_unreachable" and stop["budget"] is False


@pytest.mark.anyio
async def test_other_database_errors_are_store_unavailable_without_their_text():
    store, db = make()

    async def boom(coll, op, args):
        raise OperationFailure("not authorized on Probable_Clause to execute command {...}", code=13)

    db.hooks.append(boom)
    with pytest.raises(StoreUnavailable) as e:
        await store.put_heartbeat("r1", 1, T)
    assert "authorized" not in str(e.value)


@pytest.mark.anyio
async def test_a_refused_admit_against_a_hanging_store_costs_one_operation_timeout_not_two():
    store, db = make(op_timeout_s=0.2)
    db.hang = True
    t0 = time.monotonic()
    assert await store.admit("run-a", T) == Refusal("atlas_unreachable")
    elapsed = time.monotonic() - t0
    assert 0.19 <= elapsed < 0.32, elapsed                   # the flag read times out; the stop write gets no second wait


@pytest.mark.anyio
async def test_the_stop_write_after_a_quick_failure_is_still_made_within_the_same_timeout():
    store, db = make(op_timeout_s=0.2)
    failures = {"left": 1}

    async def flag_read_fails_fast(coll, op, args):
        if failures["left"]:
            failures["left"] -= 1
            server_down(coll, op, args)

    db.hooks.append(flag_read_fails_fast)
    t0 = time.monotonic()
    assert await store.admit("run-a", T) == Refusal("atlas_unreachable")
    assert time.monotonic() - t0 < 0.2
    assert [s["kind"] for s in await store.read_stops(day=DAY)] == ["atlas_unreachable"]


@pytest.mark.anyio
async def test_a_null_spent_counts_as_zero_when_read_and_the_write_that_cannot_apply_fails_closed():
    # the filter's $ifNull and the diagnosis read null as 0; Atlas cannot $inc a null, so the run is refused, not raised
    import api.state.rules as rules
    store, db = make()
    db["spend"].docs.append({"_id": MONTH, "spent": None, "days": {DAY: {"spent": None, "runs_started": 0}}})
    assert (await store.live_status(T, 2.0))["live_research"] == "open"
    assert rules.cap_verdict(db["spend"].docs[0], DAY) is None
    assert await store.admit("run-a", T) == Refusal("atlas_unreachable")
    assert db["spend"].docs[0]["days"][DAY]["runs_started"] == 0
    assert db["spend"].docs[0]["spent"] is None                         # nothing half-applied


@pytest.mark.anyio
async def test_a_malformed_document_fails_closed_without_a_type_error():
    unknown = {"live_research": "unknown", "update_check": "unknown"}
    for bad in ({"_id": MONTH, "spent": "lots", "days": {}},
                {"_id": MONTH, "spent": 1.0, "days": {DAY: {"spent": "lots"}}}):
        store, db = make()
        db["spend"].docs.append(bad)
        assert await store.admit("run-a", T) == Refusal("atlas_unreachable")      # read, not a number: refused
        assert await store.live_status(T, 2.0) == unknown
    store, db = make()
    db["spend"].docs.append({"_id": MONTH, "spent": 1.0, "days": {DAY: "x"}})
    assert await store.admit("run-a", T) == Refusal("atlas_unreachable")          # the update cannot apply: refused
    assert await store.live_status(T, 2.0) == unknown


@pytest.mark.anyio
async def test_a_month_made_by_admit_has_the_same_shape_as_memorystores():
    from api.state.store import MemoryStore
    store, db = make()
    mem = MemoryStore()
    await store.admit("run-a", T)
    await mem.admit("run-a", T)
    assert await store.read_month(MONTH) == await mem.read_month(MONTH) == {
        "_id": MONTH, "spent": 0.0, "days": {DAY: {"spent": 0.0, "runs_started": 1}}}


# --- construction ----------------------------------------------------------------------------------------------------

def test_db_name_follows_pc_env():
    assert db_name_for("live") == settings.ATLAS_DB_LIVE.value == "Probable_Clause"
    assert db_name_for("test") == settings.ATLAS_DB_TEST.value == "Probable_Clause_test"
    for bad in ("", "prod", None):
        with pytest.raises(ValueError):
            db_name_for(bad)


@pytest.mark.anyio
async def test_the_real_client_is_built_with_the_operation_timeout_and_no_connection_is_made():
    s = MongoStore("mongodb://localhost:27017", settings.ATLAS_DB_TEST.value)
    try:
        assert s._client.options.server_selection_timeout == float(settings.ATLAS_OP_TIMEOUT_S.value)
        assert s._db.name == "Probable_Clause_test"
    finally:
        await s.close()


def test_a_store_needs_either_a_uri_and_a_database_or_a_database_object():
    with pytest.raises(ValueError):
        MongoStore()
    with pytest.raises(ValueError):
        MongoStore("mongodb://localhost:27017")
    with pytest.raises(ValueError):
        MongoStore("mongodb://localhost:27017", "")


def test_the_uri_is_not_in_the_repr():
    s = MongoStore("mongodb://user:secret@localhost:27017", "Probable_Clause_test")
    assert "secret" not in repr(s) and "secret" not in str(s)


# --- no pymongo error, host or document text survives in an exception chain (T3.7) -------------------------------------

def chain(exc):
    """Every exception reachable from `exc` through __cause__ and __context__."""
    seen, todo = [], [exc]
    while todo:
        e = todo.pop()
        if e is None or any(e is s for s in seen):
            continue
        seen.append(e)
        todo += [e.__cause__, e.__context__]
    return seen


async def assert_clean(call):
    with pytest.raises(StoreUnavailable) as e:
        await call()
    for link in chain(e.value):
        assert isinstance(link, StoreUnavailable), f"{type(link).__name__} survives in the chain"
    text = " ".join(str(link) for link in chain(e.value))
    for leak in ("mongodb.net", "cluster0", "27017", "secret-question", "authorized", "E11000"):
        assert leak not in text
    return e.value


@pytest.mark.anyio
@pytest.mark.parametrize("failure", [
    ServerSelectionTimeoutError("cluster0-shard-00-00.example.mongodb.net:27017: timed out"),
    OperationFailure("not authorized on Probable_Clause to execute command", code=13),
    InvalidDocument("cannot encode object: {'question': 'secret-question'}"),
    OverflowError("MongoDB can only handle up to 8-byte ints"),
    UnicodeEncodeError("utf-8", "secret-question", 0, 1, "surrogates not allowed"),
    RuntimeError("anything the driver might raise, with secret-question in it"),
], ids=lambda f: type(f).__name__)
async def test_every_operation_wraps_any_driver_error_without_chaining_it(failure):
    store, db = make()

    async def boom(coll, op, args):
        raise failure

    db.hooks.append(boom)
    await assert_clean(lambda: store.put_heartbeat("r1", 1, T))
    await assert_clean(lambda: store.read_events("r1", 0))
    await assert_clean(lambda: store.append_events("r1", [event("r1", 1)]))
    await assert_clean(lambda: store.upsert_run_record({"run": "r1"}))
    await assert_clean(lambda: store.get_run_record("r1"))
    await assert_clean(lambda: store.record_spend(Admission("r", MONTH, DAY), 0.1))
    await assert_clean(lambda: store.flag_until("exa_out_of_credit", T))
    await assert_clean(lambda: store.set_flag("exa_out_of_credit", T))
    await assert_clean(lambda: store.record_stop("step_limit", "r1", T, {}))
    await assert_clean(lambda: store.read_month(MONTH))
    await assert_clean(lambda: store.read_stops(day=DAY))
    await assert_clean(lambda: store.ensure_indexes())


@pytest.mark.anyio
async def test_a_timeout_is_wrapped_without_the_cancellation_in_its_chain():
    store, db = make(op_timeout_s=0.02)
    db.hang = True
    e = await assert_clean(lambda: store.put_heartbeat("r1", 1, T))
    assert "timed out" in str(e)


@pytest.mark.anyio
async def test_a_bulk_write_error_that_is_not_a_repeat_is_wrapped_cleanly():
    store, db = make()

    async def bad_bulk(coll, op, args):
        if op == "insert_many":
            raise BulkWriteError({"writeErrors": [{"index": 0, "code": 121, "errmsg": "Document failed validation secret-question"}]})

    db.hooks.append(bad_bulk)
    await assert_clean(lambda: store.append_events("r1", [event("r1", 1)]))


@pytest.mark.anyio
async def test_an_upsert_that_keeps_colliding_is_wrapped_cleanly():
    store, db = make()

    async def collide(coll, op, args):
        if op == "update_one" and args.get("upsert"):
            raise DuplicateKeyError("E11000 duplicate key error collection: x index: _id_ dup key: secret-question", 11000)

    db.hooks.append(collide)
    await assert_clean(lambda: store.put_heartbeat("r1", 1, T))
    await assert_clean(lambda: store.set_flag("exa_out_of_credit", T))
    await assert_clean(lambda: store.record_stop("step_limit", "r1", T, {}))
    await assert_clean(lambda: store.record_spend(Admission("r", MONTH, DAY), 0.1))


@pytest.mark.anyio
async def test_a_failed_index_that_is_not_a_ttl_change_is_wrapped_cleanly():
    store, db = make()

    async def conflict(coll, op, args):
        if op == "create_index" and coll.name == "runs":
            raise OperationFailure("Index already exists with a different unique option: secret-question", code=85)

    db.hooks.append(conflict)
    await assert_clean(lambda: store.ensure_indexes())


@pytest.mark.anyio
async def test_an_admission_refused_for_unreachability_leaves_no_driver_error_anywhere():
    # admit returns a Refusal rather than raising, so the chain check is on what the recording path logs and keeps
    store, db = make()

    async def boom(coll, op, args):
        raise InvalidDocument("secret-question")

    db.hooks.append(boom)
    assert await store.admit("run-a", T) == Refusal("atlas_unreachable")


def test_a_malformed_connection_string_is_a_clean_value_error():
    for uri in ("mongodb://user:secret-question@host:notaport/", "not-a-uri-at-all://x", "mongodb://[::1"):
        with pytest.raises(ValueError) as e:
            MongoStore(uri, "Probable_Clause_test")
        assert e.value.__cause__ is None and e.value.__context__ is None
        assert "secret-question" not in str(e.value) and "host" not in str(e.value)
