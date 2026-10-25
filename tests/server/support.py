"""Test seams for part H: a virtual clock, a minimal ASGI driver, an app factory and store wrappers.

No test waits real seconds: every sleep in the lifecycle goes through the injected clock, and `FakeClock.advance`
releases the sleepers in time order. Every event the app emits is validated against contracts/events.schema.json.
"""

import asyncio
import heapq
import json
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path

from jsonschema import Draft202012Validator

from api.server import AppDeps, create_app
from api.state.clock import CHICAGO
from api.state.store import MemoryStore, StoreUnavailable

ROOT = Path(__file__).resolve().parents[2]
SCHEMA = json.loads((ROOT / "contracts" / "events.schema.json").read_text())
VALIDATOR = Draft202012Validator(SCHEMA)
HTTP_FIXTURES = ROOT / "tests" / "fixtures" / "http"
EVENT_FIXTURES = ROOT / "tests" / "fixtures" / "events"
START = datetime(2026, 10, 24, 22, 0, 0, tzinfo=CHICAGO)


def http_fixture(name: str) -> dict:
    return json.loads((HTTP_FIXTURES / name).read_text(encoding="utf-8"))


def event_fixture(name: str) -> dict:
    return json.loads((EVENT_FIXTURES / name).read_text(encoding="utf-8"))


# --- the clock -------------------------------------------------------------------------------------------------------
class FakeClock:
    def __init__(self, start: datetime = START):
        self.start = start
        self.t = 0.0
        self._heap: list = []
        self._seq = 0

    def now(self) -> datetime:
        return self.start + timedelta(seconds=self.t)

    def monotonic(self) -> float:
        return self.t

    async def sleep(self, seconds: float) -> None:
        if seconds <= 0:
            await asyncio.sleep(0)
            return
        fut = asyncio.get_running_loop().create_future()
        self._seq += 1
        heapq.heappush(self._heap, (self.t + seconds, self._seq, fut))
        await fut

    @staticmethod
    async def settle(rounds: int = 200) -> None:
        for _ in range(rounds):
            await asyncio.sleep(0)

    async def advance(self, seconds: float) -> None:
        target = self.t + seconds
        await self.settle()
        while True:
            while self._heap and self._heap[0][2].done():
                heapq.heappop(self._heap)
            if not self._heap or self._heap[0][0] > target + 1e-9:
                break
            when, _, fut = heapq.heappop(self._heap)
            self.t = max(self.t, when)
            fut.set_result(None)
            await self.settle()
        self.t = target
        await self.settle()


# --- the ASGI driver -------------------------------------------------------------------------------------------------
@dataclass
class Resp:
    status: int
    headers: dict
    body: bytes

    @property
    def text(self) -> str:
        return self.body.decode("utf-8")

    def json(self):
        return json.loads(self.body)


def _scope(method: str, path: str, headers: dict | None) -> dict:
    hs = [(k.lower().encode("latin-1"), str(v).encode("latin-1")) for k, v in (headers or {}).items()]
    return {"type": "http", "asgi": {"version": "3.0", "spec_version": "2.3"}, "http_version": "1.1",
            "method": method, "scheme": "http", "path": path, "raw_path": path.encode(), "query_string": b"",
            "root_path": "", "headers": hs, "client": ("203.0.113.9", 50000), "server": ("testserver", 80)}


def _headers(raw) -> dict:
    out: dict = {}
    for k, v in raw:
        out.setdefault(k.decode("latin-1").lower(), []).append(v.decode("latin-1"))
    return {k: v[0] if len(v) == 1 else v for k, v in out.items()}


class Stream:
    """A streamed response being read. `pump()` takes what has been sent so far without waiting."""

    def __init__(self, app, path: str, headers: dict | None):
        self.sent: asyncio.Queue = asyncio.Queue()
        self.inbox: asyncio.Queue = asyncio.Queue()
        self.inbox.put_nowait({"type": "http.request", "body": b"", "more_body": False})
        self.status: int | None = None
        self.headers: dict = {}
        self.text = ""
        self.closed = False

        async def receive():
            return await self.inbox.get()

        async def send(msg):
            await self.sent.put(msg)

        self.task = asyncio.ensure_future(app(_scope("GET", path, headers), receive, send))

    def pump(self) -> str:
        new = ""
        while not self.sent.empty():
            msg = self.sent.get_nowait()
            if msg["type"] == "http.response.start":
                self.status = msg["status"]
                self.headers = _headers(msg["headers"])
            elif msg["type"] == "http.response.body":
                chunk = msg.get("body", b"").decode("utf-8")
                new += chunk
                if not msg.get("more_body", False):
                    self.closed = True
        self.text += new
        if self.task.done() and not self.task.cancelled() and self.task.exception():
            raise self.task.exception()
        return new

    def frames(self) -> list[str]:
        return [f for f in self.text.split("\n\n") if f]

    def events(self) -> list[dict]:
        out = []
        for f in self.frames():
            if f.startswith(":"):
                continue
            lines = f.split("\n")
            assert lines[0].startswith("id: ") and lines[1].startswith("event: ") and lines[2].startswith("data: "), f
            env = json.loads(lines[2][len("data: "):])
            assert str(env["n"]) == lines[0][4:] and env["kind"] == lines[1][7:]
            out.append(env)
        return out

    async def disconnect(self) -> None:
        await self.inbox.put({"type": "http.disconnect"})
        await asyncio.sleep(0)


class Client:
    def __init__(self, app):
        self.app = app

    async def request(self, method: str, path: str, body: bytes | str | dict | None = None,
                      headers: dict | None = None, chunks: list[bytes] | None = None) -> Resp:
        if isinstance(body, dict):
            body = json.dumps(body)
        if isinstance(body, str):
            body = body.encode("utf-8")
        headers = dict(headers or {})
        if chunks is None:
            chunks = [body or b""]
            headers.setdefault("content-type", "application/json")
            headers.setdefault("content-length", str(len(body or b"")))
        msgs = [{"type": "http.request", "body": c, "more_body": i < len(chunks) - 1} for i, c in enumerate(chunks)]
        sent: list = []

        async def receive():
            if msgs:
                return msgs.pop(0)
            await asyncio.Event().wait()          # never: a request answered without its whole body

        async def send(msg):
            sent.append(msg)

        await self.app(_scope(method, path, headers), receive, send)
        start = next(m for m in sent if m["type"] == "http.response.start")
        body_out = b"".join(m.get("body", b"") for m in sent if m["type"] == "http.response.body")
        return Resp(start["status"], _headers(start["headers"]), body_out)

    async def post(self, path, body=None, **kw) -> Resp:
        return await self.request("POST", path, body, **kw)

    async def get(self, path, **kw) -> Resp:
        return await self.request("GET", path, None, **kw)

    def stream(self, path: str, headers: dict | None = None) -> Stream:
        return Stream(self.app, path, headers)


@asynccontextmanager
async def lifespan(app):
    inbox: asyncio.Queue = asyncio.Queue()
    outbox: asyncio.Queue = asyncio.Queue()

    async def receive():
        return await inbox.get()

    async def send(msg):
        await outbox.put(msg)

    task = asyncio.ensure_future(app({"type": "lifespan", "asgi": {"version": "3.0", "spec_version": "2.3"}}, receive, send))
    await inbox.put({"type": "lifespan.startup"})
    msg = await outbox.get()
    if msg["type"] != "lifespan.startup.complete":
        await task
        raise RuntimeError(msg.get("message", "start-up failed"))
    try:
        yield
    finally:
        await inbox.put({"type": "lifespan.shutdown"})
        async with asyncio.timeout(10):        # a shutdown that never finishes fails the test instead of hanging it
            await outbox.get()
            await task


# --- stores ----------------------------------------------------------------------------------------------------------
class FlakyStore:
    """A MemoryStore whose chosen methods fail (as StoreUnavailable) or wait on a gate."""

    def __init__(self, inner: MemoryStore | None = None):
        self.inner = inner or MemoryStore()
        self.fail: dict[str, int] = {}          # method -> how many more calls fail (-1: always)
        self.gates: dict[str, asyncio.Event] = {}
        self.calls: dict[str, int] = {}
        self.order: list[str] = []              # every call, in the order made

    def __getattr__(self, name):
        target = getattr(self.inner, name)
        if not callable(target):
            return target

        async def wrapped(*a, **kw):
            self.calls[name] = self.calls.get(name, 0) + 1
            self.order.append(name)
            gate = self.gates.get(name)
            if gate is not None:
                await gate.wait()
            left = self.fail.get(name, 0)
            if left:
                if left > 0:
                    self.fail[name] = left - 1
                raise StoreUnavailable("simulated: an Atlas operation failed (host db.example.internal)")
            return await target(*a, **kw)
        return wrapped


# --- the app under test ----------------------------------------------------------------------------------------------
@dataclass
class Harness:
    app: object
    client: Client
    clock: FakeClock
    store: object
    schema_errors: list = field(default_factory=list)
    contexts: list = field(default_factory=list)       # every RunContext execute_run was given

    @property
    def registry(self):
        return self.app.state.pc.registry

    def run(self, run_id: str):
        return self.registry._runs.get(run_id)


def make_app(script=None, *, store=None, clock=None, commit="fixture", corpus_label="full"):
    """An app whose execute_run is `script(ctx, deps)` (default: start and answer at once)."""
    clock = clock or FakeClock()
    store = store if store is not None else MemoryStore(clock=lambda: clock.now())
    errors: list = []
    contexts: list = []

    def validate(env: dict) -> None:
        errors.extend(f"{env.get('kind')} n={env.get('n')}: {e.message}" for e in VALIDATOR.iter_errors(env))

    async def execute_run(ctx, deps):
        contexts.append(ctx)
        await (script or answered_script)(ctx, deps)

    async def factory():
        return AppDeps(store=store, execute_run=execute_run, loop_deps=object(), corpus_label=corpus_label,
                       commit=commit, clock=clock, event_validator=validate)

    app = create_app(factory)
    h = Harness(app=app, client=Client(app), clock=clock, store=store, schema_errors=errors, contexts=contexts)
    return h


# --- scripted runs (stand-ins for G's execute_run) -------------------------------------------------------------------
QUESTION = "Can police use a thermal imager on my house from the street?"
COVERAGE = {"latest_decision_full_pull": "2026-06-29", "latest_decision_in_corpus": "2026-06-29", "ingested": "2026-10-23"}


def run_started_data(ctx) -> dict:
    return {"question": ctx.question,
            "limits": {"rounds": 12, "input_tokens": 400000, "output_tokens": 20000, "update_searches": 3,
                       "deadline_s": 600},
            "coverage": COVERAGE, "update_check_available": ctx.update_check_available,
            "models": {"loop": "claude-sonnet-5-5", "composition": "claude-opus-5-5"}, "corpus_label": ctx.corpus_label}


def ended_data(ctx, state="answered", *, stop_kind=None, answer_end="complete", rounds=1, answer_chars=0,
               failure_reason=None) -> dict:
    return {"state": state, "stop_kind": stop_kind, "no_sources_reason": None, "note": None, "scope_note": None,
            "answer_end": answer_end, "failure_reason": failure_reason, "rounds": rounds,
            "answer_chars": answer_chars, "totals": ctx.totals()}


def raw_claude(inp=50, w5=0, w1=12000, read=0, out=400) -> dict:
    return {"input_tokens": inp, "cache_creation_input_tokens": w5 + w1, "cache_read_input_tokens": read,
            "cache_creation": {"ephemeral_5m_input_tokens": w5, "ephemeral_1h_input_tokens": w1},
            "output_tokens": out, "service_tier": "standard"}


def claude_usage(model="claude-sonnet-5-5", inp=50, w5=0, w1=12000, read=0, out=400):
    from api.types import Usage
    return Usage(service="anthropic", model=model, input_tokens=inp, cache_write_5m_tokens=w5,
                 cache_write_1h_tokens=w1, cache_read_tokens=read, output_tokens=out)


async def loop_call(ctx, call_no=1, *, outcome="ok", **tokens) -> float:
    await ctx.before_paid_call("anthropic", "loop")
    return await ctx.record_usage(claude_usage(**tokens), purpose="loop", attempt=1, max_attempts=3, outcome=outcome,
                                  error_kind=None if outcome == "ok" else "overloaded", duration_ms=1500,
                                  raw_usage=raw_claude(**tokens), call_no=call_no)


async def answered_script(ctx, deps) -> None:
    await ctx.emit("run_started", run_started_data(ctx))
    await ctx.emit("round_started", {"round": 1, "status_line": "Round 1 of 12 · 0 kept · update check not yet run"})
    await loop_call(ctx)
    await ctx.emit("answer_block", {"index": 0, "text": "An answer.", "citations": []})
    await ctx.emit("run_ended", ended_data(ctx, rounds=1, answer_chars=len("An answer.")))
