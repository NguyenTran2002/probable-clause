"""MongoStore against Atlas's Probable_Clause_test (T3.4, T3.5). Skipped unless PC_ATLAS_TEST=1.

The main session runs this with the URI in MONGODB_URI. Every collection used here is prefixed with a random
name and dropped afterwards, so no real data in the test database is read or changed, and the dates are all in
2030. Nothing here runs in the offline suite.
"""

import os
import uuid

import pytest

from api import settings
from api.state.store import MongoStore
from tests.state import cases

pytestmark = pytest.mark.skipif(os.environ.get("PC_ATLAS_TEST") != "1",
                                reason="set PC_ATLAS_TEST=1 and MONGODB_URI to run against Probable_Clause_test")

COLLECTIONS = ("events", "runs", "spend", "budget_stops", "heartbeats", "flags")


@pytest.fixture
async def atlas_store():
    prefix = f"t{uuid.uuid4().hex[:10]}_"
    store = MongoStore(os.environ["MONGODB_URI"], settings.ATLAS_DB_TEST.value, prefix=prefix)
    try:
        await store.ensure_indexes()
        yield store
    finally:
        for name in COLLECTIONS:
            await store._db[prefix + name].drop()
        await store.close()


@pytest.mark.anyio
@pytest.mark.parametrize("case", cases.ALL, ids=lambda c: c.__name__)
async def test_semantics_on_atlas(case, atlas_store):
    await case(atlas_store)


@pytest.mark.anyio
async def test_documents_have_the_bson_types_the_ttl_indexes_need(atlas_store):
    from datetime import datetime
    await atlas_store.append_events("r1", [cases.event("r1", 1)])
    await atlas_store.put_heartbeat("r1", 1, cases.T)
    raw_event = await atlas_store._db[atlas_store._prefix + "events"].find_one({"run": "r1"})
    raw_hb = await atlas_store._db[atlas_store._prefix + "heartbeats"].find_one({"run": "r1"})
    assert isinstance(raw_event["created"], datetime) and isinstance(raw_hb["at"], datetime)
    infos = await atlas_store._db[atlas_store._prefix + "events"].index_information()
    assert any(i.get("expireAfterSeconds") == int(settings.EVENTS_TTL_S.value) for i in infos.values())
