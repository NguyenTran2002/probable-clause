"""The endpoints of contract §5, answer for answer against tests/fixtures/http/ (status, the relevant headers, body)."""

import asyncio
import json
import re

import pytest

from api import settings
from api.protocols import Admission
from api.state.store import MemoryStore

from tests.server.support import QUESTION, START, FakeClock, FlakyStore, http_fixture, lifespan, make_app

pytestmark = pytest.mark.anyio
RUN_ID = re.compile(r"^[A-Za-z0-9_-]{1,128}$")
CAP = int(settings.REQUEST_BODY_MAX_BYTES.value)
MAX_Q = int(settings.QUESTION_MAX_CHARS.value)
SLOTS = int(settings.MAX_CONCURRENT_RUNS.value)
EXPIRY = float(settings.UNATTACHED_RUN_EXPIRY_S.value)
DAILY = float(settings.DAILY_CAP_USD.value)
MONTHLY = float(settings.MONTHLY_CAP_USD.value)

# contract §5 (v2.0): the texts of the refusals, which go in `message` for logs
MSG_DAILY = "Today's spending has reached the daily cap, so no new question can start until midnight, Central Time."
MSG_MONTHLY = "This month's spending has reached the monthly cap, so no new question can start until the 1st."
MSG_BUSY = ("Five questions are being researched right now, the most this site handles at once. "
            "Please try again in a minute.")


def assert_matches(resp, name: str, *, body=True):
    fx = http_fixture(name)
    assert resp.status == fx["status"]
    for k, v in fx["headers"].items():
        assert resp.headers.get(k.lower()) == v, k
    if body:
        assert resp.text == fx["body"]
    assert "set-cookie" not in resp.headers          # T3.7: no cookies


async def fill_day(store: MemoryStore, now=START):
    """Today's spend at the daily cap: the next admission is refused (strictly under the cap admits)."""
    await store.record_spend(Admission("filler", "2026-10", "2026-10-24"), DAILY)


async def fill_month(store: MemoryStore):
    """This month's spend at the monthly cap, on an earlier day, with today still open."""
    await store.record_spend(Admission("filler", "2026-10", "2026-10-01"), MONTHLY)


# --- /health ---------------------------------------------------------------------------------------------------------
async def test_health_ready():
    h = make_app()
    async with lifespan(h.app):
        assert_matches(await h.client.get("/health"), "health-ready.json")


async def test_health_paused_day():
    h = make_app()
    await fill_day(h.store)
    async with lifespan(h.app):
        assert_matches(await h.client.get("/health"), "health-paused-day.json")


async def test_health_paused_month_by_cap_and_by_flag():
    h = make_app()
    await fill_month(h.store)
    async with lifespan(h.app):
        assert_matches(await h.client.get("/health"), "health-paused-month.json")
    h2 = make_app()
    await h2.store.set_flag("anthropic_spend_limit", START)
    async with lifespan(h2.app):
        assert_matches(await h2.client.get("/health"), "health-paused-month.json")


async def test_health_unknown_when_atlas_is_down():
    h = make_app()
    async with lifespan(h.app):
        h.store.unreachable = True
        assert_matches(await h.client.get("/health"), "health-unknown.json")


async def test_health_reports_the_exa_flag_and_the_commit():
    h = make_app(commit="ab12cd3")
    await h.store.set_flag("exa_out_of_credit", START)
    async with lifespan(h.app):
        body = (await h.client.get("/health")).json()
        assert body == {"app": "probable-clause", "ready": True, "live_research": "open",
                        "update_check": "unavailable", "commit": "ab12cd3"}


async def test_health_before_loading_completes_is_not_our_json():
    h = make_app()
    r = await h.client.get("/health")        # no lifespan run: still loading
    assert r.status == 503
    with pytest.raises(ValueError):
        json.loads(r.body)


async def test_start_up_waits_for_the_deps_factory():
    """T3.6: nothing answers until everything has loaded; the lifespan awaits the factory."""
    gate = asyncio.Event()
    from api.server import AppDeps, create_app

    async def factory():
        await gate.wait()
        return AppDeps(store=MemoryStore(), execute_run=None)

    app = create_app(factory)
    cm = lifespan(app)
    entering = asyncio.ensure_future(cm.__aenter__())
    await asyncio.sleep(0.01)
    assert not entering.done()
    assert app.state.pc.ready is False
    gate.set()
    await entering
    assert app.state.pc.ready is True
    await cm.__aexit__(None, None, None)


# --- POST /runs ------------------------------------------------------------------------------------------------------
async def test_post_runs_201():
    h = make_app()
    async with lifespan(h.app):
        r = await h.client.post("/runs", {"question": QUESTION})
        assert_matches(r, "post-runs-201.json", body=False)
        body = r.json()
        assert list(body) == ["run_id"] and RUN_ID.match(body["run_id"]) and len(body["run_id"]) >= 16
        month = await h.store.read_month("2026-10")
        assert month["days"]["2026-10-24"]["runs_started"] == 1
        assert "reservations" not in month and "reserved" not in month, "nothing is reserved (P4.21)"
        assert month["spent"] == 0 and h.registry.in_progress == 1


async def test_run_ids_are_distinct_and_unguessable():
    h = make_app()
    async with lifespan(h.app):
        # four runs in progress: under the limit of MAX_CONCURRENT_RUNS
        ids = {(await h.client.post("/runs", {"question": f"{QUESTION} {i}"})).json()["run_id"] for i in range(4)}
        assert len(ids) == 4 and all(len(i) == 22 for i in ids)


@pytest.mark.parametrize("question", ["", "   ", "\n\t \r", "\x00\x01\x07\x7f", "\u0085\u009f"])
async def test_post_runs_400_question_empty(question):
    h = make_app()
    async with lifespan(h.app):
        assert_matches(await h.client.post("/runs", {"question": question}), "post-runs-400-question-empty.json")
        assert await h.store.read_month("2026-10") is None        # refused before any admission
        assert h.registry.in_progress == 0


async def test_post_runs_400_question_too_long():
    h = make_app()
    async with lifespan(h.app):
        assert_matches(await h.client.post("/runs", {"question": "a" * (MAX_Q + 1)}),
                       "post-runs-400-question-too-long.json")
        assert (await h.client.post("/runs", {"question": "a" * MAX_Q})).status == 201
        # control characters do not count toward the cap: they are stripped first
        assert (await h.client.post("/runs", {"question": "a" * MAX_Q + "\x00\x01"})).status == 201
        assert await h.store.read_month("2026-10") is not None


async def test_post_runs_413_by_declared_length_and_by_streamed_body():
    h = make_app()
    async with lifespan(h.app):
        big = json.dumps({"question": "a" * CAP}).encode()
        assert_matches(await h.client.post("/runs", big), "post-runs-413-body-too-large.json")
        chunks = [big[i:i + 1000] for i in range(0, len(big), 1000)]
        assert_matches(await h.client.post("/runs", chunks=chunks), "post-runs-413-body-too-large.json")
        exact = json.dumps({"question": "a"}).encode().ljust(CAP)    # whitespace padding: valid JSON, at the cap
        assert len(exact) == CAP
        assert (await h.client.post("/runs", exact)).status == 201
        assert (await h.client.post("/runs", exact + b" ")).status == 413


def assert_refusal(resp, name: str, message: str):
    """Status and headers from the fixture, the code from the fixture's body, the message from contract §5 v2.0."""
    fx = http_fixture(name)
    assert resp.status == fx["status"]
    for k, v in fx["headers"].items():
        assert resp.headers.get(k.lower()) == v, k
    assert resp.json() == {"error": json.loads(fx["body"])["error"], "message": message}
    assert "set-cookie" not in resp.headers


async def test_post_runs_503_paused_day():
    h = make_app()
    await fill_day(h.store)
    async with lifespan(h.app):
        assert_refusal(await h.client.post("/runs", {"question": QUESTION}), "post-runs-503-paused-day.json", MSG_DAILY)
        assert h.registry.in_progress == 0, "the slot is freed on a refusal"
    assert [s["kind"] for s in await h.store.read_stops(day="2026-10-24")] == ["daily_cap"]   # recorded by admit


async def test_post_runs_503_paused_month():
    h = make_app()
    await fill_month(h.store)
    async with lifespan(h.app):
        assert_refusal(await h.client.post("/runs", {"question": QUESTION}), "post-runs-503-paused-month.json",
                       MSG_MONTHLY)
        assert h.registry.in_progress == 0
    assert [s["kind"] for s in await h.store.read_stops(day="2026-10-24")] == ["monthly_cap"]


async def test_a_cap_is_strict_just_under_admits_at_the_cap_refuses():
    h = make_app()
    await h.store.record_spend(Admission("filler", "2026-10", "2026-10-24"), DAILY - 0.01)
    async with lifespan(h.app):
        assert (await h.client.post("/runs", {"question": QUESTION})).status == 201
        await h.store.record_spend(Admission("filler", "2026-10", "2026-10-24"), 0.01)
        r = await h.client.post("/runs", {"question": QUESTION})
        assert r.status == 503 and r.json()["error"] == "paused_day"


async def test_post_runs_spend_limit_pause_answers_paused_month():
    h = make_app()
    await h.store.set_flag("anthropic_spend_limit", START)
    async with lifespan(h.app):
        r = await h.client.post("/runs", {"question": QUESTION})
        assert r.status == 503 and r.json()["error"] == "paused_month"
        assert list(r.json()) == ["error", "message"]


async def test_post_runs_503_atlas_unreachable():
    h = make_app()
    async with lifespan(h.app):
        h.store.unreachable = True
        assert_matches(await h.client.post("/runs", {"question": QUESTION}), "post-runs-503-atlas-unreachable.json")


async def test_post_runs_fails_closed_when_admit_raises():
    store = FlakyStore()
    store.fail["admit"] = -1
    h = make_app(store=store)
    async with lifespan(h.app):
        r = await h.client.post("/runs", {"question": QUESTION})
        assert r.status == 503 and r.json()["error"] == "atlas_unreachable"
        assert h.registry.in_progress == 0, "the slot is freed when Atlas fails"


@pytest.mark.parametrize("body", [b"not json", b"[1, 2]", b'{"q": "x"}', b'{"question": 7}', b"\xff\xfe",
                                  b'{"question": null}'])
async def test_post_runs_400_bad_request(body):
    h = make_app()
    async with lifespan(h.app):
        r = await h.client.post("/runs", body)
        assert r.status == 400 and r.json()["error"] == "bad_request" and list(r.json()) == ["error", "message"]


async def test_busy_at_the_limit_with_no_atlas_call():
    store = FlakyStore()
    h = make_app(store=store)
    async with lifespan(h.app):
        ids = [(await h.client.post("/runs", {"question": f"{QUESTION} {i}"})).json()["run_id"] for i in range(SLOTS)]
        assert store.calls["admit"] == SLOTS and h.registry.in_progress == SLOTS
        before = dict(store.calls)
        r = await h.client.post("/runs", {"question": QUESTION})
        assert r.status == 503 and r.json() == {"error": "busy", "message": MSG_BUSY}
        assert store.calls == before, "busy answers with no Atlas call"
        assert await store.inner.read_stops(day="2026-10-24") == [], "busy is not recorded: it is not a budget stop"
        assert len(ids) == len(set(ids))


async def test_the_count_holds_under_concurrent_requests():
    """Slots are taken before Atlas is awaited, so a burst never overshoots, however slow Atlas is."""
    clock = FakeClock()
    inner = MemoryStore(clock=lambda: clock.now(), latency_s=0)
    store = FlakyStore(inner)
    store.gates["admit"] = asyncio.Event()                 # every admission waits on Atlas
    h = make_app(store=store, clock=clock)
    async with lifespan(h.app):
        burst = [asyncio.ensure_future(h.client.post("/runs", {"question": f"{QUESTION} {i}"})) for i in range(3 * SLOTS)]
        await clock.settle()
        assert h.registry.in_progress == SLOTS, "the slots were taken before Atlas answered"
        assert store.calls["admit"] == SLOTS, "only the runs that got a slot reached Atlas"
        refused = [t.result() for t in burst if t.done()]
        assert len(refused) == 2 * SLOTS and all(r.status == 503 and r.json()["error"] == "busy" for r in refused)
        store.gates["admit"].set()
        results = await asyncio.gather(*burst)
        assert sorted(r.status for r in results) == [201] * SLOTS + [503] * (2 * SLOTS)
        assert h.registry.in_progress == SLOTS
        month = await inner.read_month("2026-10")
        assert month["days"]["2026-10-24"]["runs_started"] == SLOTS


async def test_the_slot_is_freed_on_a_refusal_and_on_expiry():
    store = FlakyStore()
    h = make_app(store=store)
    async with lifespan(h.app):
        store.fail["admit"] = SLOTS                         # Atlas fails for the first SLOTS requests
        for _ in range(SLOTS):
            assert (await h.client.post("/runs", {"question": QUESTION})).json()["error"] == "atlas_unreachable"
        assert h.registry.in_progress == 0
        ids = [(await h.client.post("/runs", {"question": QUESTION})).json()["run_id"] for _ in range(SLOTS)]
        assert (await h.client.post("/runs", {"question": QUESTION})).json()["error"] == "busy"
        await h.clock.advance(EXPIRY + 1)                   # nothing attached to any of them
        assert h.registry.in_progress == 0 and h.contexts == []
        r = await h.client.post("/runs", {"question": QUESTION})
        assert r.status == 201 and r.json()["run_id"] not in ids


async def test_the_slot_is_freed_after_run_ended():
    h = make_app()
    async with lifespan(h.app):
        for _ in range(SLOTS):
            run_id = (await h.client.post("/runs", {"question": QUESTION})).json()["run_id"]
            assert h.registry.in_progress == 1
            s = h.client.stream(f"/runs/{run_id}/events")
            await h.clock.settle()
            s.pump()
            assert s.closed and s.events()[-1]["kind"] == "run_ended"
            assert h.registry.in_progress == 0, "freed once the run has ended"
        # more runs than slots over the day, one after another: never busy
        assert (await h.client.post("/runs", {"question": QUESTION})).status == 201


async def test_five_broken_runs_cannot_lock_the_site():
    async def broken(ctx, deps):
        raise RuntimeError("a bug before anything")

    h = make_app(broken)
    async with lifespan(h.app):
        for _ in range(2 * SLOTS):
            r = await h.client.post("/runs", {"question": QUESTION})
            assert r.status == 201, "the slot of a failed run was freed"
            s = h.client.stream(f"/runs/{r.json()['run_id']}/events")
            await h.clock.settle()
            s.pump()
            assert s.events()[-1]["data"]["state"] == "failed"
        assert h.registry.in_progress == 0


async def test_the_caps_look_at_what_was_spent_never_at_a_worst_case():
    h = make_app()
    await h.store.record_spend(Admission("filler", "2026-10", "2026-10-24"), DAILY - 0.5)
    async with lifespan(h.app):
        # fifty cents of room is enough: nothing is reserved, so no run needs a worst case to fit (P4.21)
        for _ in range(3):
            assert (await h.client.post("/runs", {"question": QUESTION})).status == 201


async def test_control_characters_are_stripped_from_the_question():
    seen = []

    async def script(ctx, deps):
        seen.append(ctx.question)
        from tests.server.support import answered_script
        await answered_script(ctx, deps)

    h = make_app(script)
    async with lifespan(h.app):
        r = await h.client.post("/runs", {"question": "  Can\tpolice\nsearch\x00 my\x1b phone​?\ud800 \x7f "})
        s = h.client.stream(f"/runs/{r.json()['run_id']}/events")
        await h.clock.settle()
        s.pump()
        assert seen == ["Can police search my phone​?"]
        assert not any(ord(c) < 32 or 127 <= ord(c) < 160 for c in seen[0])


async def test_update_check_available_follows_the_exa_flag():
    h = make_app()
    async with lifespan(h.app):
        r = await h.client.post("/runs", {"question": QUESTION})
        assert h.run(r.json()["run_id"]).update_check_available is True
        await h.store.set_flag("exa_out_of_credit", START)
        r = await h.client.post("/runs", {"question": QUESTION})
        run = h.run(r.json()["run_id"])
        assert run.update_check_available is False and run.flags.exa_unavailable == "no_credit"


# --- GET /runs/{id}/events and POST /runs/{id}/alive -----------------------------------------------------------------
async def test_get_events_404_run_unknown():
    h = make_app()
    async with lifespan(h.app):
        assert_matches(await h.client.get("/runs/uSZPbMAkuQGfL7TAcGTjZu/events"), "get-events-404-run-unknown.json")
        r = await h.client.get("/runs/not.a$valid.id/events")
        assert r.status == 404 and r.json()["error"] == "run_unknown"


async def test_post_alive_204_and_404():
    h = make_app()
    async with lifespan(h.app):
        run_id = (await h.client.post("/runs", {"question": QUESTION})).json()["run_id"]
        r = await h.client.post(f"/runs/{run_id}/alive", {"last_event": 0})
        assert_matches(r, "post-alive-204.json")
        assert await h.store.latest_heartbeat(run_id) == START
        assert_matches(await h.client.post("/runs/uSZPbMAkuQGfL7TAcGTjZu/alive", {"last_event": 3}),
                       "post-alive-404-run-unknown.json")


@pytest.mark.parametrize("body", [b"{}", b'{"last_event": -1}', b'{"last_event": "3"}', b'{"last_event": true}', b"x"])
async def test_post_alive_400(body):
    h = make_app()
    async with lifespan(h.app):
        run_id = (await h.client.post("/runs", {"question": QUESTION})).json()["run_id"]
        r = await h.client.post(f"/runs/{run_id}/alive", body)
        assert r.status == 400 and r.json()["error"] == "bad_request"


async def test_post_alive_413():
    h = make_app()
    async with lifespan(h.app):
        run_id = (await h.client.post("/runs", {"question": QUESTION})).json()["run_id"]
        r = await h.client.post(f"/runs/{run_id}/alive", b'{"last_event": 1}' + b" " * CAP)
        assert r.status == 413 and r.json()["error"] == "body_too_large"


async def test_unknown_paths_and_methods_answer_in_our_error_shape():
    h = make_app()
    async with lifespan(h.app):
        r = await h.client.get("/nowhere")
        assert r.status == 404 and r.json()["error"] == "not_found"
        r = await h.client.get("/runs")
        assert r.status == 405 and r.json()["error"] == "method_not_allowed"
        for path in ("/docs", "/openapi.json", "/redoc"):
            assert (await h.client.get(path)).status == 404
