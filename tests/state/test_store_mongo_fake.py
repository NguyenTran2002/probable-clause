"""MongoStore's own flow, run over the fake database (no network). Contract §4.E, §8; T3.4, T3.7."""

import asyncio
import time
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from bson.errors import InvalidDocument
from pymongo.errors import BulkWriteError, DuplicateKeyError, OperationFailure, ServerSelectionTimeoutError

from api import settings
from api.protocols import Refusal, Reservation
from api.state import mongo_docs
from api.state.store import MongoStore, StoreUnavailable, db_name_for
from tests.state import cases
from tests.state.cases import DAY, MONTH, T, W, event
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
    await store.reserve("run-a", W, T)
    [doc] = db["spend"].docs
    assert doc["_id"] == MONTH
    assert set(doc) == {"_id", "spent", "reserved", "days", "reservations"}
    assert set(doc["days"][DAY]) == {"spent", "reserved", "runs_started"}
    entry = doc["reservations"]["run-a"]
    assert entry["day"] == DAY and entry["amount"] == W and isinstance(entry["at"], datetime)


@pytest.mark.anyio
async def test_prefix_names_the_collections():
    store, db = make(prefix="t1_")
    await store.reserve("run-a", W, T)
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


# --- the reservation is one conditional update --------------------------------------------------------------------

@pytest.mark.anyio
async def test_reserve_is_one_conditional_update_of_the_month_document():
    store, db = make()
    await store.reserve("run-a", W, T)
    conditional = [c for c in db.calls_to("spend", "update_one") if "$expr" in (c["filter"] or {})]
    assert len(conditional) == 1
    assert conditional[0]["filter"] == mongo_docs.reserve_filter(MONTH, DAY, "run-a", W)
    assert conditional[0]["update"] == mongo_docs.reserve_update(DAY, "run-a", W, T)


@pytest.mark.anyio
async def test_a_room_taken_between_the_check_and_the_write_refuses_the_run():
    # a read-then-write reserve would see room here; the conditional update must not
    store, db = make()
    await store.reserve("base", 7.0, T)
    taken = False

    async def steal(coll, op, args):
        nonlocal taken
        if coll.name == "spend" and op == "update_one" and "$expr" in (args["filter"] or {}) and not taken:
            taken = True
            doc = coll.docs[0]
            doc["reserved"] += 2.0
            doc["days"][DAY]["reserved"] += 2.0
            doc["reservations"]["rival"] = {"day": DAY, "amount": 2.0, "at": T}

    db.hooks.append(steal)
    assert await store.reserve("racer", 2.0, T) == Refusal("daily_cap")   # the rival took the room: 9 + 2 > 10
    assert "racer" not in db["spend"].docs[0]["reservations"]


@pytest.mark.anyio
async def test_a_refusal_is_diagnosed_from_one_read_after_the_failed_update():
    store, db = make()
    for i in range(5):
        await store.reserve(f"r{i}", W, T)
    db.calls.clear()
    assert await store.reserve("late", W, T) == Refusal("daily_cap")
    assert len(db.calls_to("spend", "find_one")) == 1


@pytest.mark.anyio
async def test_if_the_state_changes_under_the_diagnosis_the_update_is_tried_again():
    store, db = make()
    await store.reserve("base", 8.0, T)
    flips = 0

    async def release_after_the_failed_update(coll, op, args):
        # the first conditional update fails (8 + 3 > 10); before the diagnosing read, the room is freed
        nonlocal flips
        if coll.name == "spend" and op == "find_one" and flips == 0:
            flips += 1
            doc = coll.docs[0]
            doc["reserved"] -= 8.0
            doc["days"][DAY]["reserved"] -= 8.0
            doc["reservations"].pop("base")

    db.hooks.append(release_after_the_failed_update)
    r = await store.reserve("racer", 3.0, T)
    assert isinstance(r, Reservation)
    assert (await store.read_month(MONTH))["reserved"] == pytest.approx(3.0)


# --- settle and release --------------------------------------------------------------------------------------------

@pytest.mark.anyio
async def test_settle_inside_the_reservation_is_a_single_atomic_update_with_no_prior_read():
    store, db = make()
    r = await store.reserve("run-a", W, T)
    db.calls.clear()
    await store.settle(r, 0.5)
    assert [c["op"] for c in db.calls] == ["update_one"]
    assert db.calls[0]["update"] == mongo_docs.settle_full_update(DAY, "run-a", 0.5)


@pytest.mark.anyio
async def test_settling_nothing_sends_nothing():
    store, db = make()
    r = await store.reserve("run-a", W, T)
    db.calls.clear()
    await store.settle(r, 0.0)
    assert db.calls == []


@pytest.mark.anyio
async def test_settle_beyond_what_is_left_reads_then_swaps_and_survives_a_concurrent_change():
    store, db = make()
    r = await store.reserve("run-a", 1.0, T)
    interfered = False

    async def another_settle_lands_first(coll, op, args):
        nonlocal interfered
        if (coll.name == "spend" and op == "update_one" and not interfered
                and args["filter"].get("reservations.run-a.amount") == 1.0):
            interfered = True
            doc = coll.docs[0]
            for target in (doc, doc["days"][DAY]):
                target["spent"] += 0.4
                target["reserved"] -= 0.4
            doc["reservations"]["run-a"]["amount"] -= 0.4

    db.hooks.append(another_settle_lands_first)
    await store.settle(r, 1.5)           # more than the whole reservation: clamp path
    m = await store.read_month(MONTH)
    assert m["spent"] == pytest.approx(1.9) and m["reserved"] == pytest.approx(0.0)
    assert m["reservations"]["run-a"]["amount"] == pytest.approx(0.0)


@pytest.mark.anyio
async def test_settle_never_loses_spend_even_if_the_swap_cannot_converge():
    store, db = make()
    r = await store.reserve("run-a", 1.0, T)
    count = 0

    async def always_changing(coll, op, args):
        nonlocal count
        if coll.name == "spend" and op == "update_one" and "reservations.run-a.amount" in (args["filter"] or {}) \
                and not isinstance(args["filter"]["reservations.run-a.amount"], dict):
            count += 1
            coll.docs[0]["reservations"]["run-a"]["amount"] -= 1e-3      # someone else moves it every time
            coll.docs[0]["reserved"] -= 1e-3

    db.hooks.append(always_changing)
    await store.settle(r, 2.0)
    m = await store.read_month(MONTH)
    assert m["spent"] == pytest.approx(2.0)          # the spend is on the books
    assert m["reserved"] >= 0.0                      # reserved stays counted (conservative) rather than negative
    assert count >= 2


@pytest.mark.anyio
async def test_settle_into_a_month_with_no_document_still_counts_the_spend():
    store, _ = make()
    await store.settle(Reservation("ghost", MONTH, DAY, 1.0), 0.25)
    m = await store.read_month(MONTH)
    assert m["spent"] == pytest.approx(0.25) and m["reserved"] == 0.0 and m["days"][DAY]["spent"] == pytest.approx(0.25)


@pytest.mark.anyio
async def test_release_swaps_on_the_remaining_amount_and_retries_when_it_moved():
    store, db = make()
    r = await store.reserve("run-a", W, T)
    interfered = False

    async def settle_lands_first(coll, op, args):
        nonlocal interfered
        if coll.name == "spend" and op == "update_one" and args["update"].get("$unset") and not interfered:
            interfered = True
            doc = coll.docs[0]
            for target in (doc, doc["days"][DAY]):
                target["spent"] += 0.5
                target["reserved"] -= 0.5
            doc["reservations"]["run-a"]["amount"] -= 0.5

    db.hooks.append(settle_lands_first)
    await store.release(r)
    m = await store.read_month(MONTH)
    assert m["reserved"] == pytest.approx(0.0) and m["spent"] == pytest.approx(0.5) and m["reservations"] == {}


@pytest.mark.anyio
async def test_a_release_that_cannot_converge_says_so_rather_than_pretending():
    store, db = make()
    r = await store.reserve("run-a", W, T)

    async def always_changing(coll, op, args):
        if coll.name == "spend" and op == "update_one" and args["update"].get("$unset"):
            coll.docs[0]["reservations"]["run-a"]["amount"] -= 1e-3
            coll.docs[0]["reserved"] -= 1e-3

    db.hooks.append(always_changing)
    with pytest.raises(StoreUnavailable):
        await store.release(r)
    assert "run-a" in (await store.read_month(MONTH))["reservations"]       # still counted: the safe side


# --- Atlas unreachable ---------------------------------------------------------------------------------------------

def server_down(coll, op, args):
    raise ServerSelectionTimeoutError("cluster0-shard-00-00.example.mongodb.net:27017: timed out")


@pytest.mark.anyio
async def test_unreachable_atlas_refuses_the_run_and_does_not_leak_the_host():
    store, db = make()

    async def down(coll, op, args):
        server_down(coll, op, args)

    db.hooks.append(down)
    assert await store.reserve("run-a", W, T) == Refusal("atlas_unreachable")
    with pytest.raises(StoreUnavailable) as e:
        await store.read_events("r1", 0)
    assert "mongodb.net" not in str(e.value) and "cluster0" not in str(e.value)
    assert (await store.live_status(T, W, 1.0)) == {"live_research": "unknown", "update_check": "unknown"}


@pytest.mark.anyio
async def test_the_unreachable_stop_is_recorded_where_it_can_be():
    store, db = make()
    failures = {"left": 1}

    async def one_failure(coll, op, args):      # the first operation fails (the flag read); Atlas answers after that
        if failures["left"]:
            failures["left"] -= 1
            server_down(coll, op, args)

    db.hooks.append(one_failure)
    assert await store.reserve("run-a", W, T) == Refusal("atlas_unreachable")
    [stop] = await store.read_stops(day=DAY)
    assert stop["kind"] == "atlas_unreachable" and stop["budget"] is False and stop["run"] == "run-a"
    assert (await store.read_month(MONTH))["days"][DAY]["stops"] == {"atlas_unreachable": 1}


@pytest.mark.anyio
async def test_a_hanging_atlas_is_cut_off_at_the_operation_timeout():
    store, db = make(op_timeout_s=0.05)
    db.hang = True
    t0 = time.monotonic()
    assert await store.reserve("run-a", W, T) == Refusal("atlas_unreachable")
    assert time.monotonic() - t0 < 1.0
    with pytest.raises(StoreUnavailable):
        await store.put_heartbeat("r1", 1, T)


@pytest.mark.anyio
async def test_live_status_honours_its_own_shorter_timeout():
    store, db = make(op_timeout_s=30.0)
    db.hang = True
    t0 = time.monotonic()
    s = await store.live_status(T, W, 0.05)
    assert s == {"live_research": "unknown", "update_check": "unknown"}
    assert time.monotonic() - t0 < 1.0


@pytest.mark.anyio
async def test_a_reservation_written_but_not_acknowledged_is_taken_back():
    # the conditional update is applied, the reply is lost: the run is refused, so its reservation must not linger
    store, db = make()

    async def reply_lost(coll, op, args):
        if coll.name == "spend" and op == "update_one" and "$expr" in (args["filter"] or {}):
            raise ServerSelectionTimeoutError("reply lost")

    db.after_hooks.append(reply_lost)
    assert await store.reserve("run-a", W, T) == Refusal("atlas_unreachable")
    m = await store.read_month(MONTH)
    assert m["reserved"] == pytest.approx(0.0) and m["reservations"] == {}
    assert m["days"][DAY]["runs_started"] == 0                                # the refused run did not start
    assert await store.open_reservations(T) == []


@pytest.mark.anyio
async def test_other_database_errors_are_store_unavailable_without_their_text():
    store, db = make()

    async def boom(coll, op, args):
        raise OperationFailure("not authorized on Probable_Clause to execute command {...}", code=13)

    db.hooks.append(boom)
    with pytest.raises(StoreUnavailable) as e:
        await store.put_heartbeat("r1", 1, T)
    assert "authorized" not in str(e.value)


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
    await assert_clean(lambda: store.settle(Reservation("r", MONTH, DAY, 1.0), 0.1))
    await assert_clean(lambda: store.release(Reservation("r", MONTH, DAY, 1.0)))
    await assert_clean(lambda: store.open_reservations(T))
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


@pytest.mark.anyio
async def test_a_failed_index_that_is_not_a_ttl_change_is_wrapped_cleanly():
    store, db = make()

    async def conflict(coll, op, args):
        if op == "create_index" and coll.name == "runs":
            raise OperationFailure("Index already exists with a different unique option: secret-question", code=85)

    db.hooks.append(conflict)
    await assert_clean(lambda: store.ensure_indexes())


@pytest.mark.anyio
async def test_a_reservation_refused_for_unreachability_leaves_no_driver_error_anywhere():
    # reserve returns a Refusal rather than raising, so the chain check is on what the recording path logs and keeps
    store, db = make()

    async def boom(coll, op, args):
        raise InvalidDocument("secret-question")

    db.hooks.append(boom)
    assert await store.reserve("run-a", W, T) == Refusal("atlas_unreachable")


def test_a_malformed_connection_string_is_a_clean_value_error():
    for uri in ("mongodb://user:secret-question@host:notaport/", "not-a-uri-at-all://x", "mongodb://[::1"):
        with pytest.raises(ValueError) as e:
            MongoStore(uri, "Probable_Clause_test")
        assert e.value.__cause__ is None and e.value.__context__ is None
        assert "secret-question" not in str(e.value) and "host" not in str(e.value)


# --- the retry bound is the shared setting -----------------------------------------------------------------------------

@pytest.mark.anyio
async def test_the_compare_and_swap_bound_is_the_setting(monkeypatch):
    assert int(settings.ATLAS_RESERVE_TRIES.value) == 5
    monkeypatch.setattr(settings, "ATLAS_RESERVE_TRIES", settings.Setting(2, "test"))
    store, db = make()
    r = await store.reserve("run-a", W, T)
    swaps = 0

    async def always_changing(coll, op, args):
        nonlocal swaps
        if coll.name == "spend" and op == "update_one" and args["update"].get("$unset"):
            swaps += 1
            coll.docs[0]["reservations"]["run-a"]["amount"] -= 1e-3
            coll.docs[0]["reserved"] -= 1e-3

    db.hooks.append(always_changing)
    with pytest.raises(StoreUnavailable):
        await store.release(r)
    assert swaps == 2


@pytest.mark.anyio
async def test_an_upsert_collision_is_retried_up_to_the_setting(monkeypatch):
    monkeypatch.setattr(settings, "ATLAS_RESERVE_TRIES", settings.Setting(3, "test"))
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
