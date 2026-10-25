"""The whole backend on fakes: H's app and Run around G's real execute_run, with B's, C's, D's, E's and F's real
parts, and only the outside services faked (contract §12). One answered run, start to finish, checked at the seams:
the stream, Atlas's copy of it, the money and the run record."""

import json

import pytest

from api.corpus.keyword import KeywordIndex
from api.corpus.store import Corpus
from api.loop import execute_run
from api.search.meaning import MeaningIndex
from api.server import AppDeps, create_app
from api.state.budget import worst_case_usd
from api.state.store import MemoryStore
from tests.loop.support import (ROOT, World, check_stream, cite_block, composition, loop_usage, make_deps, tu, turn,
                                web_reply)
from tests.server.support import VALIDATOR, Client, FakeClock, lifespan

pytestmark = pytest.mark.anyio

QUESTION = "Is listening to a phone booth call with a device on the outside a search?"
PAGE_TEXT = ("Synthetic page text for the end-to-end test, invented here and distinctive enough to be found if it "
             "ever reached an event, the store or a run record. ") * 3
DOCS = ["katz-1-p6", "katz-1-n8"]


@pytest.fixture(scope="module")
def world() -> World:
    corpus = Corpus.load(ROOT)
    return World(corpus, KeywordIndex(corpus), MeaningIndex.load(ROOT / "data" / "vectors", corpus.passages.values()))


def script(world):
    return [
        turn(tu("search_meaning", query="eavesdropping on a telephone booth", filters={"cases": ["katz"]}),
             tu("read_passages", target="katz-1-p6"), usage=loop_usage(1, first=True)),
        turn(tu("search_web_updates", query="phone booth eavesdropping ruling", start_published_date="2026-06-30"),
             tu("keep_passages", keep=[
                 {"id": "katz-1-p6", "reason": "Majority: the Amendment protects people, not places."},
                 {"id": "katz-1-n8", "reason": "Majority footnote on the parties' formulation."}]),
             usage=loop_usage(2)),
        turn(tu("submit_answer", out_of_scope=False,
                update_findings=[{"statement": "A sample page reports a later lower-court ruling.",
                                  "sources": ["web-1-1"]}]),
             usage=loop_usage(3)),
        composition(
            {"type": "text", "text": "## Short answer\n\n"},
            cite_block("The majority said the Amendment protects people, not places. ", world.corpus, DOCS,
                       "katz-1-p6", 2, 3),
            cite_block("A footnote addresses the formulation. ", world.corpus, DOCS, "katz-1-n8", 0, 0),
        ),
    ]


async def test_an_answered_run_through_the_whole_backend(world):
    clock = FakeClock()
    store = MemoryStore(clock=lambda: clock.now())
    deps, fakes = make_deps(world, script(world), store=store,
                            exa=[web_reply(("later", "Later ruling", "2026-09-12T00:00:00Z", PAGE_TEXT))])
    errors: list[str] = []

    def validate(env: dict) -> None:
        errors.extend(f"{env.get('kind')} n={env.get('n')}: {e.message}" for e in VALIDATOR.iter_errors(env))

    async def factory():
        return AppDeps(store=store, execute_run=execute_run, loop_deps=deps, commit="e2e", clock=clock,
                       event_validator=validate)

    app = create_app(factory)
    client = Client(app)
    async with lifespan(app):
        resp = await client.post("/runs", {"question": QUESTION})
        assert resp.status == 201
        run_id = resp.json()["run_id"]
        s = client.stream(f"/runs/{run_id}/events")
        for _ in range(50):
            await clock.settle()
            s.pump()
            if s.closed:
                break
        assert s.closed, "the run did not end"
        events = s.events()
        await clock.settle()

        # the stream: valid, in order, ended as answered, no page text anywhere
        assert errors == []
        check_stream(events, world.corpus, page_texts=[PAGE_TEXT[:80]])
        end = events[-1]["data"]
        assert end["state"] == "answered" and end["answer_end"] == "complete" and end["stop_kind"] is None
        assert not fakes["anthropic"].script, "scripted Claude turns were left unused"
        blocks = [e["data"] for e in events if e["kind"] == "answer_block"]
        cited = [(c["passage_id"], c["first_sentence"], c["last_sentence"]) for b in blocks for c in b["citations"]]
        assert cited == [("katz-1-p6", 2, 3), ("katz-1-n8", 0, 0)]
        assert end["answer_chars"] == sum(len(b["text"]) for b in blocks)
        assert next(e for e in events if e["kind"] == "update_band")["data"]["outcome"] == "found"

        # Atlas holds the same envelopes, in order
        stored = await store.read_events(run_id, 0)
        assert [{k: v for k, v in e.items() if k != "created"} for e in stored] == events

        # the money: every paid call priced once, the totals add up, the spend settled and the reservation released
        paid = [e["data"] for e in events if e["kind"] == "paid_call"]
        assert [p["service"] for p in paid].count("anthropic") == 4          # three loop calls and the composition
        assert [p["service"] for p in paid].count("exa") == 1
        assert [p["service"] for p in paid].count("voyage") == 2             # the query's embed and its rerank
        total = sum(p["cost_usd"] for p in paid)
        t = end["totals"]
        assert t["claude"]["calls"] == 4 and t["exa"]["searches"] == 1 and t["voyage"]["requests"] == 2
        assert abs(t["claude"]["cost_usd"]["loop"] + t["claude"]["cost_usd"]["composition"] + t["exa"]["cost_usd"]
                   + t["voyage"]["cost_usd"] - total) < 1e-6
        assert 0 < total < worst_case_usd()
        assert await store.open_reservations(clock.now()) == []
        month = await store.read_month(clock.now().strftime("%Y-%m"))
        assert abs(month["spent"] - total) < 1e-6 and month["reserved"] == pytest.approx(0, abs=1e-9)

        # the run record: the allowlisted shape, the right figures, nothing of the question, answer or pages
        record = await store.get_run_record(run_id)
        assert record["state"] == "answered" and record["rounds"] == end["rounds"]
        assert record["corpus_label"] == "full"
        dumped = json.dumps(record) + json.dumps(stored, default=str)
        assert QUESTION not in json.dumps(record) and PAGE_TEXT[:80] not in dumped
        assert "protects people, not places" not in json.dumps(record)
