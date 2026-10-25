"""The endpoints of contract §5, answer for answer against tests/fixtures/http/ (status, the relevant headers, body)."""

import asyncio
import json
import re
from datetime import datetime, timedelta

import pytest

from api import settings
from api.state.budget import worst_case_usd
from api.state.clock import CHICAGO
from api.state.store import MemoryStore

from tests.server.support import QUESTION, START, http_fixture, lifespan, make_app

pytestmark = pytest.mark.anyio
RUN_ID = re.compile(r"^[A-Za-z0-9_-]{1,128}$")
CAP = int(settings.REQUEST_BODY_MAX_BYTES.value)
MAX_Q = int(settings.QUESTION_MAX_CHARS.value)


def assert_matches(resp, name: str, *, body=True):
    fx = http_fixture(name)
    assert resp.status == fx["status"]
    for k, v in fx["headers"].items():
        assert resp.headers.get(k.lower()) == v, k
    if body:
        assert resp.text == fx["body"]
    assert "set-cookie" not in resp.headers          # T3.7: no cookies


def fill_day(store: MemoryStore, now=START):
    """Leave less than one worst case of room today."""
    return store.reserve("filler", float(settings.DAILY_CAP_USD.value) - worst_case_usd() + 0.5, now)


async def fill_month(store: MemoryStore):
    """Leave less than one worst case of room this month, with today still open."""
    for day in range(1, 7):
        await store.reserve(f"filler-{day}", 9.9, datetime(2026, 10, day, 12, tzinfo=CHICAGO))


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
        assert month["reservations"][body["run_id"]]["amount"] == pytest.approx(worst_case_usd())
        assert month["days"]["2026-10-24"]["runs_started"] == 1


async def test_run_ids_are_distinct_and_unguessable():
    h = make_app()
    async with lifespan(h.app):
        # four open reservations: well within the $15 day at P4.6's $2.106 (P4.11)
        ids = {(await h.client.post("/runs", {"question": f"{QUESTION} {i}"})).json()["run_id"] for i in range(4)}
        assert len(ids) == 4 and all(len(i) == 22 for i in ids)


@pytest.mark.parametrize("question", ["", "   ", "\n\t \r", "\x00\x01\x07\x7f", "\u0085\u009f"])
async def test_post_runs_400_question_empty(question):
    h = make_app()
    async with lifespan(h.app):
        assert_matches(await h.client.post("/runs", {"question": question}), "post-runs-400-question-empty.json")
        assert await h.store.read_month("2026-10") is None        # refused before any reservation


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


async def test_post_runs_503_paused_day():
    h = make_app()
    await fill_day(h.store)
    async with lifespan(h.app):
        assert_matches(await h.client.post("/runs", {"question": QUESTION}), "post-runs-503-paused-day.json")
    assert [s["kind"] for s in await h.store.read_stops(day="2026-10-24")] == ["daily_cap"]   # recorded by reserve


async def test_post_runs_503_paused_month():
    h = make_app()
    await fill_month(h.store)
    async with lifespan(h.app):
        assert_matches(await h.client.post("/runs", {"question": QUESTION}), "post-runs-503-paused-month.json")


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


async def test_post_runs_fails_closed_when_reserve_raises():
    from tests.server.support import FlakyStore
    store = FlakyStore()
    store.fail["reserve"] = -1
    h = make_app(store=store)
    async with lifespan(h.app):
        r = await h.client.post("/runs", {"question": QUESTION})
        assert r.status == 503 and r.json()["error"] == "atlas_unreachable"


@pytest.mark.parametrize("body", [b"not json", b"[1, 2]", b'{"q": "x"}', b'{"question": 7}', b"\xff\xfe",
                                  b'{"question": null}'])
async def test_post_runs_400_bad_request(body):
    h = make_app()
    async with lifespan(h.app):
        r = await h.client.post("/runs", body)
        assert r.status == 400 and r.json()["error"] == "bad_request" and list(r.json()) == ["error", "message"]


async def test_two_runs_racing_for_the_last_room_do_not_both_start():
    h = make_app()
    room = float(settings.DAILY_CAP_USD.value) - 1.5 * worst_case_usd()      # room for one worst case, not two
    await h.store.reserve("filler", room, START)
    async with lifespan(h.app):
        a, b = await asyncio.gather(h.client.post("/runs", {"question": QUESTION}),
                                    h.client.post("/runs", {"question": QUESTION + " again"}))
        assert sorted([a.status, b.status]) == [201, 503]
        refused = a if a.status == 503 else b
        assert refused.json()["error"] == "paused_day"
        month = await h.store.read_month("2026-10")
        assert month["reserved"] <= float(settings.DAILY_CAP_USD.value) + 1e-9


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
