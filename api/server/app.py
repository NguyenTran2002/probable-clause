"""The HTTP API (contract §5) and its start-up (T3.6).

- Everything loads in the lifespan, before the port opens (uvicorn accepts connections only once start-up is done),
  so `/health` answers only when the app is ready.
- Errors are `{"error": "<code>", "message": "<for logs>"}`; the page writes its own words from the codes (T5.4).
- Protections (T3.7): every body is capped at REQUEST_BODY_MAX_BYTES, control characters are stripped from the
  question, an empty question and one over QUESTION_MAX_CHARS are refused before any paid call. No cookie is set
  and no client address is read.
"""

import asyncio
import functools
import json
import logging
import re
import secrets
import time
import unicodedata
from collections.abc import Awaitable, Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, PlainTextResponse, Response, StreamingResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from api import settings
from api.protocols import Refusal, Reservation, Store
from api.server.clock import Clock, RealClock
from api.server.registry import RunRegistry
from api.server.run import Run, _kind
from api.server.sse import SSE_HEADERS, ascii_int, live_stream, parse_last_event_id, replay_stream, stored_frames
from api.state.budget import worst_case_usd
from api.state.records import RUN_ID
from api.types import CorpusLabel

log = logging.getLogger("api.server")

APP_NAME = "probable-clause"
LIVE_STATES = ("open", "paused_day", "paused_month", "unknown")
UPDATE_STATES = ("available", "unavailable", "unknown")

# The refusals of POST /runs (contract §5; T3.4). The spend-limit pause answers paused_month.
REFUSALS = {
    "daily_cap": ("paused_day", "The run's worst case would take today's spend past the daily cap."),
    "monthly_cap": ("paused_month", "The run's worst case would take this month's spend past the monthly cap."),
    "spend_limit_paused": ("paused_month", "Live research is paused until the 1st after the Anthropic spend limit was reached."),
    "atlas_unreachable": ("atlas_unreachable", "The spending records could not be reached, so no run was started."),
}
RUN_UNKNOWN = "No such run, or its events have expired."


@dataclass
class AppDeps:
    """What the app runs on. `api/main.py` builds the real ones; tests build fakes."""
    store: Store
    execute_run: Callable[[Any, Any], Awaitable[None]]     # api.loop.execute_run(ctx, deps)
    loop_deps: Any = None                                    # api.loop.LoopDeps
    corpus_label: CorpusLabel = "full"
    commit: str = "unknown"
    clock: Clock = field(default_factory=RealClock)
    event_validator: Callable[[dict], None] | None = None   # tests: every event checked against the schema
    aclose: Callable[[], Awaitable[None]] | None = None      # closes the store's client at shutdown


def _error(status: int, code: str, message: str) -> JSONResponse:
    return JSONResponse({"error": code, "message": message}, status_code=status)


def clean_question(raw: str) -> str:
    """Control characters stripped (T3.7): a whitespace control (tab, line break) becomes a space, so words stay
    apart; every other control character and any lone surrogate is removed. Then trimmed."""
    out = []
    for ch in raw:
        cat = unicodedata.category(ch)
        if cat == "Cc":
            if ch.isspace():
                out.append(" ")
        elif cat != "Cs":
            out.append(ch)
    return "".join(out).strip()


BAD_LENGTH = object()


async def read_capped_body(request: Request):
    """The body; None if it is larger than REQUEST_BODY_MAX_BYTES (read no further than the cap, T3.7); BAD_LENGTH
    if `Content-Length` is not a number in ASCII digits."""
    cap = int(settings.REQUEST_BODY_MAX_BYTES.value)
    declared = request.headers.get("content-length")
    if declared is not None:
        n = ascii_int(declared, 20)
        if n is None:
            return BAD_LENGTH
        if n > cap:
            return None
    buf = bytearray()
    async for chunk in request.stream():
        buf += chunk
        if len(buf) > cap:
            return None
    return bytes(buf)


def _too_large() -> JSONResponse:
    return _error(413, "body_too_large", f"The request body is larger than {int(settings.REQUEST_BODY_MAX_BYTES.value)} bytes.")


def _json_object(body: bytes) -> dict | None:
    try:
        obj = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, ValueError, RecursionError):
        return None
    return obj if isinstance(obj, dict) else None


def _guarded(fn):
    """An unexpected error answers 500 in our JSON shape and is logged by kind only (T3.7)."""
    @functools.wraps(fn)
    async def wrapper(*args, **kwargs):
        try:
            return await fn(*args, **kwargs)
        except Exception as e:
            log.error("%s failed (%s)", fn.__name__, _kind(e))
            return _error(500, "internal", "The server could not handle the request.")
    return wrapper


class _State:
    deps: AppDeps | None = None
    registry: RunRegistry | None = None
    ready: bool = False


def create_app(deps_factory: Callable[[], Awaitable[AppDeps]]) -> FastAPI:
    state = _State()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        t0 = time.monotonic()
        deps = await deps_factory()               # T3.6: everything loads before the port opens
        state.deps = deps
        state.registry = RunRegistry(deps.clock)
        state.ready = True
        log.info("ready in %.3f s (corpus %s, commit %s)", time.monotonic() - t0, deps.corpus_label, deps.commit)
        try:
            yield
        finally:
            state.ready = False
            await state.registry.shutdown()
            if deps.aclose is not None:
                try:
                    await deps.aclose()
                except Exception as e:
                    log.warning("closing the store failed (%s)", _kind(e))

    app = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)
    app.state.pc = state

    @app.exception_handler(StarletteHTTPException)
    async def http_error(request: Request, exc: StarletteHTTPException):
        if exc.status_code == 404:
            return _error(404, "not_found", "No such endpoint.")
        if exc.status_code == 405:
            return _error(405, "method_not_allowed", "This method is not allowed here.")
        return _error(exc.status_code, "http_error", "The request could not be handled.")

    # --- GET /health (contract §5, T3.4, T3.6) ----------------------------------------------------------------------
    @app.get("/health")
    @_guarded
    async def health():
        if not state.ready or state.deps is None:
            # not our JSON, so the page treats it as still starting (contract §5.1 rule 2)
            return PlainTextResponse("Service Unavailable", status_code=503)
        deps = state.deps
        try:
            s = await deps.store.live_status(deps.clock.now(), worst_case_usd(), float(settings.ATLAS_HEALTH_TIMEOUT_S.value))
        except Exception as e:
            log.warning("health: live status failed (%s)", _kind(e))
            s = {}
        live = s.get("live_research") if s.get("live_research") in LIVE_STATES else "unknown"
        update = s.get("update_check") if s.get("update_check") in UPDATE_STATES else "unknown"
        return JSONResponse({"app": APP_NAME, "ready": True, "live_research": live, "update_check": update,
                             "commit": deps.commit})

    # --- POST /runs (contract §5, T3.4, T3.7) -----------------------------------------------------------------------
    @app.post("/runs")
    @_guarded
    async def create_run(request: Request):
        deps, registry = state.deps, state.registry
        body = await read_capped_body(request)
        if body is None:
            return _too_large()
        if body is BAD_LENGTH:
            return _error(400, "bad_request", "Content-Length is not a number.")
        obj = _json_object(body)
        if obj is None or not isinstance(obj.get("question"), str):
            return _error(400, "bad_request", "The body must be a JSON object with a question string.")
        question = clean_question(obj["question"])
        if not question:
            return _error(400, "question_empty", "The question is empty after control characters were removed.")
        limit = int(settings.QUESTION_MAX_CHARS.value)
        if len(question) > limit:
            return _error(400, "question_too_long", f"The question is longer than {limit} characters.")

        run_id = secrets.token_urlsafe(16)
        while run_id in registry or not RUN_ID.match(run_id):
            run_id = secrets.token_urlsafe(16)
        now = deps.clock.now()
        try:
            got = await deps.store.reserve(run_id, worst_case_usd(), now)     # T3.4: atomic, authoritative
        except Exception as e:                    # fail closed
            log.error("run %s: the reservation failed (%s)", run_id, _kind(e))
            got = Refusal("atlas_unreachable")
        if isinstance(got, Refusal):
            code, message = REFUSALS.get(got.kind, REFUSALS["atlas_unreachable"])
            log.info("run refused: %s", got.kind)
            return _error(503, code, message)
        if not isinstance(got, Reservation):
            log.error("run %s: the store answered the reservation with something else", run_id)
            return _error(503, "atlas_unreachable", REFUSALS["atlas_unreachable"][1])

        try:
            try:
                exa_out = await deps.store.flag_until("exa_out_of_credit", now) is not None
            except Exception as e:            # D reads the flag again before each search (contract §4.D)
                log.warning("run %s: could not read the Exa credit flag (%s)", run_id, _kind(e))
                exa_out = False
            run = Run(run_id=run_id, question=question, update_check_available=not exa_out,
                      corpus_label=deps.corpus_label, store=deps.store, reservation=got, clock=deps.clock,
                      execute_run=deps.execute_run, loop_deps=deps.loop_deps, event_validator=deps.event_validator,
                      on_expired=registry.discard)
            if exa_out:
                run.flags.exa_unavailable = "no_credit"      # T2.4, P2.11: out of credit until the 1st
            registry.add(run)
            run.schedule_expiry()
        except BaseException as e:            # a cancellation included: the reservation is never left behind
            log.error("run %s: could not be created (%s); releasing its reservation", run_id, _kind(e))
            try:
                await asyncio.shield(deps.store.release(got))
            except BaseException as e2:
                log.error("run %s: the reservation could not be released (%s)", run_id, _kind(e2))
            if not isinstance(e, Exception):
                raise
            return _error(500, "internal", "The server could not handle the request.")
        log.info("run %s created: %.3f USD reserved, update check %s", run_id, got.amount_usd,
                 "available" if not exa_out else "unavailable")
        return JSONResponse({"run_id": run_id}, status_code=201)

    # --- GET /runs/{id}/events (contract §5, T3.1) ------------------------------------------------------------------
    @app.get("/runs/{run_id}/events")
    @_guarded
    async def events(run_id: str, request: Request):
        deps, registry = state.deps, state.registry
        if not RUN_ID.match(run_id):
            return _error(404, "run_unknown", RUN_UNKNOWN)
        last = parse_last_event_id(request.headers.get("last-event-id"))
        run = registry.get(run_id)
        if run is not None:
            token = run.attach(deps.clock.now())
            return StreamingResponse(live_stream(run, token, last, deps.clock, registry.closing),
                                     media_type="text/event-stream",
                                     headers=SSE_HEADERS)
        try:
            stored = await deps.store.read_events(run_id, 0)
        except Exception as e:
            log.warning("run %s: stored events could not be read (%s)", run_id, _kind(e))
            return _error(503, "atlas_unreachable", "The stored events could not be reached.")
        if not stored:
            return _error(404, "run_unknown", RUN_UNKNOWN)
        log.info("run %s: replayed from Atlas after event %d", run_id, last)
        return StreamingResponse(replay_stream(stored_frames(stored, last, deps.clock)),
                                 media_type="text/event-stream", headers=SSE_HEADERS)

    # --- POST /runs/{id}/alive (contract §5, T3.2) ------------------------------------------------------------------
    @app.post("/runs/{run_id}/alive")
    @_guarded
    async def alive(run_id: str, request: Request):
        deps, registry = state.deps, state.registry
        if not RUN_ID.match(run_id):
            return _error(404, "run_unknown", RUN_UNKNOWN)
        body = await read_capped_body(request)
        if body is None:
            return _too_large()
        if body is BAD_LENGTH:
            return _error(400, "bad_request", "Content-Length is not a number.")
        obj = _json_object(body)
        last_event = obj.get("last_event") if obj is not None else None
        if isinstance(last_event, bool) or not isinstance(last_event, int) or last_event < 0:
            return _error(400, "bad_request", "The body must be a JSON object with last_event, an integer.")
        now = deps.clock.now()
        run = registry.get(run_id)
        if run is not None:
            run.heartbeat(now)
            try:
                await deps.store.put_heartbeat(run_id, last_event, now)
            except Exception as e:            # this instance holds the run, so the heartbeat already counts
                log.warning("run %s: heartbeat not written to Atlas (%s)", run_id, _kind(e))
            return Response(status_code=204)
        # Another instance holds the run (or none does): write the heartbeat to Atlas if the run is stored (T3.2).
        try:
            after = max(0, last_event - 1)
            known = await deps.store.read_events(run_id, after)
            if not known and after > 0:
                known = await deps.store.read_events(run_id, 0)
            if not known:
                return _error(404, "run_unknown", RUN_UNKNOWN)
            await deps.store.put_heartbeat(run_id, last_event, now)
        except Exception as e:
            log.warning("run %s: heartbeat could not be written (%s)", run_id, _kind(e))
            return _error(503, "atlas_unreachable", "The heartbeat could not be stored.")
        return Response(status_code=204)

    return app
