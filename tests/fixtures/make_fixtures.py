#!/usr/bin/env python3
"""Deterministic generator for the frontend mock's fixtures (contract §12, P0.3).

    .venv/bin/python tests/fixtures/make_fixtures.py             # writes everything
    .venv/bin/python tests/fixtures/make_fixtures.py --summary   # also prints each run's tool results and end
    .venv/bin/python tests/fixtures/make_fixtures.py --only <slug>

Every event stream is the real backend's output: H's app (`api.server.create_app`) and its `Run` around G's
`execute_run`, with B's, C's, D's, E's and F's real parts, exactly as tests/contract/test_end_to_end.py runs them.
Only the outside services are faked, with their parts' own fakes: `FakeAnthropic` (G), `FakeVoyageClient` (C),
`FakeExaTransport` (D) and `MemoryStore` (E). The stream is read off `GET /runs/{id}/events` as the page would read
it, while a simulated page posts `POST /runs/{id}/alive` every HEARTBEAT_INTERVAL_S of virtual time.

What this script decides, and nothing else:
  - what Claude "says": each scripted turn's tool calls, the answer blocks and their citations;
  - what the fakes report: token counts (the loop's own estimator, the corpus's characters per token, applied to the
    request the fake received), latencies (virtual seconds on `FakeClock`), Exa's sample pages, the scripted
    failures;
  - meaning-search order: `FakeVoyageClient` embeds each scripted query as the committed vector of a stand-in passage
    and reranks by the same closeness, so the order is the real vectors file's nearest neighbours of that passage.

Seams patched at run time (restored after each stream; no source file is changed):
  - `api.server.app.secrets`: the run ID is a fixed hash of the slug, not a random token;
  - `time.monotonic` in `api.loop.run`, `api.search.meaning` and `api.web_updates.exa`: the virtual clock, so the
    `duration_ms` of every paid call is the fake's latency;
  - `api.loop.run.retry_sleep`: the virtual clock's sleep, so retry waits pass in virtual time;
  - `api.loop.run.anyio`: F's checks run inline instead of in a worker thread, so nothing waits on real time.

Running it twice writes byte-identical files: Python's string hashing is pinned (the script re-executes itself
with PYTHONHASHSEED=0), the clock is virtual and every random choice is seeded by the stream's slug.
"""

import os
import sys

if os.environ.get("PYTHONHASHSEED") != "0":            # set iteration order must not vary between runs
    os.environ["PYTHONHASHSEED"] = "0"
    os.execv(sys.executable, [sys.executable] + sys.argv)

import asyncio  # noqa: E402
import copy  # noqa: E402
import hashlib  # noqa: E402
import json  # noqa: E402
import logging  # noqa: E402
import math  # noqa: E402
import random  # noqa: E402
import re  # noqa: E402
from collections import deque  # noqa: E402
from collections.abc import Callable  # noqa: E402
from contextlib import contextmanager  # noqa: E402
from dataclasses import dataclass, field  # noqa: E402
from datetime import datetime, timedelta  # noqa: E402
from pathlib import Path  # noqa: E402
from types import SimpleNamespace  # noqa: E402
from zoneinfo import ZoneInfo  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import numpy as np  # noqa: E402

import api.loop.run as loop_run  # noqa: E402
import api.search.meaning as meaning_mod  # noqa: E402
import api.server.app as app_mod  # noqa: E402
import api.web_updates.exa as exa_mod  # noqa: E402
from api import settings  # noqa: E402
from api.corpus.keyword import KeywordIndex  # noqa: E402
from api.corpus.store import Corpus  # noqa: E402
from api.errors import ServiceError  # noqa: E402
from api.loop import LoopDeps, execute_run  # noqa: E402
from api.loop.streamer import FakeAnthropic, FakeTurn, StreamFailed, raw_usage  # noqa: E402
from api.search.meaning import MeaningIndex  # noqa: E402
from api.search.voyage import FakeVoyageClient  # noqa: E402
from api.server import AppDeps, create_app  # noqa: E402
from api.state.budget import worst_case_usd  # noqa: E402
from api.state.prices import price_sources  # noqa: E402
from api.state.store import MemoryStore  # noqa: E402
from api.web_updates.exa import FakeExaTransport, UpdateSearch, exa_response, exa_result  # noqa: E402
from tests.loop.support import check_stream  # noqa: E402
from tests.server.support import VALIDATOR, Client, FakeClock, lifespan  # noqa: E402

logging.disable(logging.CRITICAL)        # the parts log expected failures; this script reports its own

EVENTS_DIR = ROOT / "tests" / "fixtures" / "events"
HTTP_DIR = ROOT / "tests" / "fixtures" / "http"
CHICAGO = ZoneInfo(str(settings.TIME_ZONE.value))
# Synthetic recording times: the fixtures are not real runs. Each stream starts seven minutes after the last.
BASE = datetime(2026, 10, 24, 22, 0, 0, tzinfo=CHICAGO)

LOOP_MODEL = str(settings.LOOP_MODEL.value)
COMP_MODEL = str(settings.COMPOSITION_MODEL.value)
HEARTBEAT_S = float(settings.HEARTBEAT_INTERVAL_S.value)
EMBED_S, RERANK_S = 0.3, 0.6            # the fake Voyage's latencies (virtual seconds)
LOOP_TOKENS_PER_S, COMP_TOKENS_PER_S, COMP_THINKING_PER_S = 85, 55, 90

CORPORA = {"full": Corpus.load(ROOT), "before_chatrie": Corpus.load(ROOT, exclude=("chatrie",))}
KEYWORD = {k: KeywordIndex(c) for k, c in CORPORA.items()}
MEANING = {k: MeaningIndex.load(ROOT / "data" / "vectors", c.passages.values()) for k, c in CORPORA.items()}
# The fake Claude's token counts: characters over a fixed ratio, set so that the loop's fixed prefix (system prompt,
# catalog and tools) comes out at FIXED_PREFIX_TOKENS_ESTIMATE, the settings' own figure for it (T1.14, T3.4). The
# loop's estimator (the corpus's characters per token) is deliberately higher, so its checks err on the safe side.
_PREFIX_CHARS = len(loop_run.prompts.loop_system(CORPORA["full"])) + len(json.dumps(loop_run.build_tool_list(), ensure_ascii=False))
RATIO = _PREFIX_CHARS / int(settings.FIXED_PREFIX_TOKENS_ESTIMATE.value)


def est(text: str) -> int:
    return math.ceil(len(text) / RATIO) if text else 0


def est_json(obj) -> int:
    return est(json.dumps(obj, ensure_ascii=False))


def jdump(o) -> str:
    return json.dumps(o, ensure_ascii=False, separators=(",", ":"))


def stable_id(*parts, length=22, prefix="") -> str:
    h = hashlib.sha256("|".join(map(str, parts)).encode()).digest()
    alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789"
    return prefix + "".join(alphabet[b % 62] for b in h[:length])


# ---------------------------------------------------------------------------------------------------------------
# What a scenario scripts
# ---------------------------------------------------------------------------------------------------------------
@dataclass
class Web:
    """What Exa answers to one search that reaches it. kind: ok | refused | failed | no_credit | key_refused."""
    pages: list = field(default_factory=list)      # page(...) tuples; a page given again comes back as a repeat
    kind: str = "ok"
    seconds: float | None = None


@dataclass
class Call:
    name: str
    input: dict
    seed: str | None = None         # search_meaning: the stand-in passage whose committed vector the query embeds as
    web: Web | None = None          # search_web_updates: Exa's answer (None: our code refuses it, so Exa is never called)


@dataclass
class Round:
    calls: list
    text: str | None = None
    retries: list = field(default_factory=list)    # attempts that failed and were retried: [(error kind, seconds)]
    fail: tuple | None = None                      # the attempt after them failed too: (error kind, seconds)
    refusal: bool = False                          # the response ends with the refusal stop reason
    hang: bool = False                             # the call never answers (the instance goes away)
    think: int | None = None                       # thinking tokens in the output
    seconds: float | None = None                   # the successful attempt's latency


@dataclass
class Comp:
    spec: list
    retries: list = field(default_factory=list)    # [(error kind, seconds)] before the attempt that streams
    fail: tuple | None = None                      # every attempt failed before its first block
    break_after: int | None = None                 # the stream breaks after this many answer blocks
    cut: bool = False                              # stops at max_tokens; the last block is cut mid-word


@dataclass
class Scenario:
    slug: str
    question: str
    rounds: list
    comp: Comp | None = None
    label: str = "full"
    exa_flag: bool = False                         # the Atlas flag "Exa out of credit" is set before the run
    embed_failures: list = field(default_factory=list)
    rerank_failures: list = field(default_factory=list)
    heartbeat: Callable[[float], bool] = lambda t: True      # whether the page sends its heartbeat at time t
    interrupt: bool = False
    expect: dict = field(default_factory=dict)
    spare_rounds: bool = False                     # a limit ends the loop before every scripted round was used


def T(text):
    """An uncited block of the answer (the page marks it as Claude's synthesis)."""
    return {"text": text, "cites": []}


def C(text, *cites):
    """A block that cites sentences: C("text", ("katz-1-p6", 4, 4), ("katz-3-p2", 3, 3)), both ends inclusive."""
    return {"text": text, "cites": list(cites)}


def K(pid, reason):
    return {"id": pid, "reason": reason}


def page(title, domain, slug, published, chars, author=None, lead=""):
    return (f"[Sample] {title}", domain, slug, published, chars, author, lead)


def page_text(slug: str, n: int, lead: str = "") -> str:
    """Synthetic filler for a sample page. Only its length ever reaches an event (the copy guard reads it)."""
    s = f"Sample page {slug}. This is invented filler text standing in for a web page. "
    return ((lead + " " if lead else "") + s * (n // len(s) + 1))[:n]


def page_texts(sc: Scenario) -> list[str]:
    out = []
    for r in sc.rounds:
        for c in r.calls:
            if c.web:
                out += [page_text(p[2], p[4], p[6])[:80] for p in c.web.pages]
    return out


# ---------------------------------------------------------------------------------------------------------------
# The fakes, configured
# ---------------------------------------------------------------------------------------------------------------
class FixtureVoyage(FakeVoyageClient):
    """C's FakeVoyageClient with latencies on the virtual clock, each scripted query embedded as the committed vector
    of its stand-in passage, and the rerank scoring the same closeness (so it keeps the embedding order)."""

    def __init__(self, clock, index: MeaningIndex, seeds: dict, embed_failures, rerank_failures):
        rows = {p.id: i for i, p in enumerate(index.passages)}
        self.clock = clock
        self.qvec = {q: index.matrix[rows[pid]] for q, pid in seeds.items()}
        self.dvec = {t: index.matrix[i] for i, t in enumerate(index.texts)}
        super().__init__(embed_failures=embed_failures, rerank_failures=rerank_failures, rerank_score=self.closeness)

    def vector_for(self, text: str) -> list[float]:
        v = self.qvec.get(text)
        return [float(x) for x in v] if v is not None else super().vector_for(text)

    def closeness(self, query: str, document: str) -> float:
        q, d = self.qvec.get(query), self.dvec.get(document)
        return 0.0 if q is None or d is None else round(float(np.dot(q, d)), 6)

    async def embed(self, texts, input_type):
        await self.clock.sleep(EMBED_S)
        return await super().embed(texts, input_type)

    async def rerank(self, query, documents):
        await self.clock.sleep(RERANK_S)
        return await super().rerank(query, documents)


def voyage_error(kind: str) -> ServiceError:
    return ServiceError("voyage", kind, {"rate_limited": 429, "server_error": 503, "auth": 401}.get(kind),
                        f"Voyage returned a synthetic {kind}")


def exa_script(sc: Scenario, clock, rng: random.Random) -> list:
    """FakeExaTransport's script: one coroutine per search that reaches Exa, in order."""
    items = []
    for r in sc.rounds:
        for c in r.calls:
            if c.web is None:
                continue
            w = c.web

            def make(w=w, secs=w.seconds if w.seconds is not None else round(rng.uniform(2.2, 5.4), 3)):
                async def item(arguments):
                    await clock.sleep(secs)
                    if w.kind == "ok":
                        return exa_response([exa_result(url=f"https://{domain}/{slug}", title=title,
                                                        published=f"{pub}T00:00:00.000Z" if pub else None,
                                                        text=page_text(slug, chars, lead), author=author,
                                                        id=f"https://{domain}/{slug}")
                                             for title, domain, slug, pub, chars, author, lead in w.pages],
                                            cost_total=0.007 if arguments.get("type", "auto") == "auto" else 0.004)
                    raise FakeExaTransport.failure({"refused": "bad_request", "failed": "timeout"}.get(w.kind, w.kind))
                return item
            items.append(make())
    return items


class FixtureClaude:
    """G's FakeAnthropic behind a scripted conversation: each loop turn and the composition are built from the
    request the fake receives, so usage follows the request's size, and every call takes virtual time."""

    def __init__(self, sc: Scenario, clock: FakeClock, rng: random.Random):
        self.sc, self.clock, self.rng = sc, clock, rng
        self.fake = FakeAnthropic()
        self.loop: deque = deque()
        for r in sc.rounds:
            for kind, secs in r.retries:
                self.loop.append(("fail", kind, secs))
            if r.fail:
                self.loop.append(("fail", *r.fail))
            elif r.hang:
                self.loop.append(("hang",))
            else:
                self.loop.append(("turn", r))
        self.comp: deque = deque()
        if sc.comp:
            for kind, secs in sc.comp.retries:
                self.comp.append(("fail", kind, secs))
            if sc.comp.fail:
                kind, secs = sc.comp.fail
                for _ in range(int(settings.ANTHROPIC_RETRIES.value) + 1):
                    self.comp.append(("fail", kind, secs))
            else:
                self.comp.append(("answer", sc.comp))
        self.tool_n = 0
        self.ok_calls = 0
        self.cached_conv = 0
        self.hung: float | None = None

    @staticmethod
    def error(kind: str) -> StreamFailed:
        messages = {"spend_limit": "You have reached your specified API usage limits (synthetic)",
                    "spend_cap": "You have reached your API usage limits (synthetic)"}
        status = {"overloaded": 529, "rate_limited": 429, "server_error": 500, "spend_limit": 400,
                  "spend_cap": 429}.get(kind)
        return StreamFailed(kind, status, messages.get(kind, f"synthetic {kind}"))

    async def stream(self, request: dict, deadline_s: float, on_block):
        queue = self.comp if request["model"] == COMP_MODEL else self.loop
        if not queue:
            raise AssertionError(f"{self.sc.slug}: no scripted {'composition' if queue is self.comp else 'loop'} "
                                 f"call left")
        item = queue.popleft()
        if item[0] == "fail":
            await self.clock.sleep(item[2])
            raise self.error(item[1])
        if item[0] == "hang":
            self.hung = self.clock.t
            await asyncio.Event().wait()           # never answers: the instance goes away (T3.1)
        if item[0] == "answer":
            return await self.compose(request, deadline_s, on_block, item[1])
        return await self.turn(request, deadline_s, item[1])

    # -- the loop --
    def loop_usage(self, request: dict, out: int) -> dict:
        """The prefix (system prompt and tools) written to the 1-hour cache on the first call, then read; the
        conversation written to the 5-minute cache as it grows, the last status line left uncached."""
        prefix = est(request["system"][0]["text"]) + est_json(request["tools"])
        conv = sum(est_json(m["content"]) for m in request["messages"])
        if self.ok_calls == 0:
            usage = raw_usage(conv, w1=prefix, output=out)
        else:
            new = conv - self.cached_conv
            last = request["messages"][-1]["content"][-1]
            tail = est(last.get("text", "")) if isinstance(last, dict) else 0
            if new - tail >= 1024:
                usage = raw_usage(tail, w5=new - tail, read=prefix + self.cached_conv, output=out)
                self.cached_conv = conv - tail
            else:
                usage = raw_usage(new, read=prefix + self.cached_conv, output=out)
        self.ok_calls += 1
        return usage

    async def turn(self, request: dict, deadline_s: float, r: Round):
        content = [{"type": "thinking", "thinking": "", "signature": stable_id(self.sc.slug, "sig", self.tool_n)}]
        if r.text:
            content.append({"type": "text", "text": r.text})
        for c in r.calls:
            self.tool_n += 1
            content.append({"type": "tool_use", "id": stable_id(self.sc.slug, "tool", self.tool_n, length=24,
                                                                  prefix="toolu_01"),
                            "name": c.name, "input": copy.deepcopy(c.input)})
        think = r.think if r.think is not None else self.rng.randint(140, 620)
        out = think + sum(est_json(b["input"]) + 12 for b in content if b["type"] == "tool_use") + est(r.text or "")
        stop = "tool_use"
        if r.refusal:
            content, stop, out = [], "refusal", 30
        elif out > int(request["max_tokens"]):         # the loop's output budget runs out mid-turn (T3.3)
            content, stop, out = content[:1], "max_tokens", int(request["max_tokens"])
        usage = self.loop_usage(request, out)
        secs = r.seconds if r.seconds is not None else 0.9 + out / LOOP_TOKENS_PER_S + self.rng.uniform(-0.3, 0.6)
        await self.clock.sleep(round(secs, 3))
        self.fake.push(FakeTurn(content=content, stop_reason=stop, usage=usage))
        return await self.fake.stream(request, deadline_s, None)

    # -- the composition --
    async def compose(self, request: dict, deadline_s: float, on_block, comp: Comp):
        docs, titles = [], []
        for b in request["messages"][0]["content"]:
            if b.get("type") == "document":
                docs.append(re.match(r"ID (\S+) ·", b["context"]).group(1))
                titles.append(b["title"])
        corpus = CORPORA[self.sc.label]
        blocks = []
        for blk in comp.spec:
            b = {"type": "text", "text": blk["text"]}
            if blk["cites"]:
                b["citations"] = []
                for pid, first, last in blk["cites"]:
                    if pid not in docs:
                        raise AssertionError(f"{self.sc.slug}: the answer cites {pid}, which was not kept")
                    p = corpus.passages[pid]
                    di = docs.index(pid)
                    b["citations"].append({"type": "content_block_location",
                                           "cited_text": p.text[p.sentences[first][0]:p.sentences[last][1]],
                                           "document_index": di, "document_title": titles[di],
                                           "start_block_index": first, "end_block_index": last + 1})
            blocks.append(b)
        content = [{"type": "thinking", "thinking": "", "signature": stable_id(self.sc.slug, "sig-comp")}] + blocks
        inp = est(request["system"]) + est_json(request["messages"])
        think = self.rng.randint(1_800, 3_600)
        out = int(request["max_tokens"]) if comp.cut else think + sum(est(b["text"]) for b in blocks)
        await self.clock.sleep(round(think / COMP_THINKING_PER_S, 3))       # thinking before the first block

        async def slow_block(i, b):
            await self.clock.sleep(round(max(0.25, est(b["text"]) / COMP_TOKENS_PER_S), 3))
            await on_block(i, b)

        self.fake.push(FakeTurn(content=content, stop_reason="max_tokens" if comp.cut else "end_turn",
                                usage=raw_usage(inp, output=out), break_after=comp.break_after,
                                partial_usage=raw_usage(inp, output=1) if comp.break_after is not None else None))
        return await self.fake.stream(request, deadline_s, slow_block)


# ---------------------------------------------------------------------------------------------------------------
# Running one scenario through H's app
# ---------------------------------------------------------------------------------------------------------------
@contextmanager
def patched(clock: FakeClock, run_id: str):
    async def run_sync(fn, *args):
        return fn(*args)

    fake_time = SimpleNamespace(monotonic=clock.monotonic)
    saved = [(loop_run, "time"), (loop_run, "retry_sleep"), (loop_run, "anyio"), (meaning_mod, "time"),
             (exa_mod, "time"), (app_mod, "secrets")]
    old = [(m, a, getattr(m, a)) for m, a in saved]
    loop_run.time = fake_time
    loop_run.retry_sleep = clock.sleep
    loop_run.anyio = SimpleNamespace(to_thread=SimpleNamespace(run_sync=run_sync))
    meaning_mod.time = fake_time
    exa_mod.time = fake_time
    app_mod.secrets = SimpleNamespace(token_urlsafe=lambda n=16: run_id)
    try:
        yield
    finally:
        for m, a, v in old:
            setattr(m, a, v)


def next_due(clock: FakeClock) -> float | None:
    live = [w for w, _, f in clock._heap if not f.done()]
    return min(live) if live else None


async def drive(clock: FakeClock, client: Client, run_id: str, s, sc: Scenario, claude: FixtureClaude) -> None:
    """Advance virtual time to the next sleeper or heartbeat until the stream closes (or the call hangs)."""
    next_hb = HEARTBEAT_S
    while True:
        await clock.settle()
        s.pump()
        if s.closed:
            return
        if claude.hung is not None and clock.t >= claude.hung + 2:
            return
        if clock.t > 3_600:
            raise RuntimeError(f"{sc.slug}: the run did not end within an hour of virtual time")
        due = next_due(clock)
        target = next_hb if due is None else min(due, next_hb)
        if claude.hung is not None:
            target = min(target, claude.hung + 2)
        await clock.advance(max(0.0, target - clock.t))
        if clock.t >= next_hb - 1e-9:
            if sc.heartbeat(next_hb):
                evs = s.events()
                await client.post(f"/runs/{run_id}/alive", {"last_event": evs[-1]["n"] if evs else 0})
            next_hb += HEARTBEAT_S


@dataclass
class Recorded:
    sc: Scenario
    doc: dict
    raw: str                      # the stream's text as sent, keep-alive lines included


def document(sc: Scenario, start: datetime, events: list) -> dict:
    return {"format": 1, "slug": sc.slug, "question": events[0]["data"]["question"],
            "recorded_at": start.isoformat(timespec="seconds"), "commit": "fixture",
            "models": {"loop": LOOP_MODEL, "composition": COMP_MODEL}, "prices": price_sources(),
            "corpus_label": sc.label, "events": events}


async def record(sc: Scenario, order: int) -> Recorded:
    corpus = CORPORA[sc.label]
    start = BASE + timedelta(minutes=7 * order)
    clock = FakeClock(start)
    store = MemoryStore(clock=lambda: clock.now())
    run_id = stable_id(sc.slug, "run")
    rng = random.Random(sc.slug)
    claude = FixtureClaude(sc, clock, rng)
    seeds = {c.input["query"]: c.seed for r in sc.rounds for c in r.calls if c.seed}
    voyage = FixtureVoyage(clock, MEANING[sc.label], seeds, [voyage_error(k) for k in sc.embed_failures],
                           [voyage_error(k) for k in sc.rerank_failures])
    transport = FakeExaTransport(exa_script(sc, clock, rng), tool_schema={"inputSchema": {"properties": {}}})
    deps = LoopDeps(corpus=corpus, keyword=KEYWORD[sc.label], meaning=MEANING[sc.label], voyage=voyage,
                    updates=UpdateSearch(transport, store, now=clock.now), anthropic=claude)
    errors: list[str] = []

    def validate(env: dict) -> None:
        errors.extend(f"{env.get('kind')} n={env.get('n')}: {e.message}" for e in VALIDATOR.iter_errors(env))

    async def factory():
        return AppDeps(store=store, execute_run=execute_run, loop_deps=deps, corpus_label=sc.label,
                       commit="fixture", clock=clock, event_validator=validate)

    app = create_app(factory)
    client = Client(app)
    with patched(clock, run_id):
        async with lifespan(app):
            if sc.exa_flag:
                await store.set_flag("exa_out_of_credit", clock.now())
            resp = await client.post("/runs", {"question": sc.question})
            assert resp.status == 201 and resp.json()["run_id"] == run_id, resp.text
            s = client.stream(f"/runs/{run_id}/events")
            await drive(clock, client, run_id, s, sc, claude)
            events = s.events()
            if sc.interrupt:
                assert claude.hung is not None, f"{sc.slug}: the call never hung"
                stored = await store.read_events(run_id, 0)
                assert stored == events, f"{sc.slug}: Atlas's copy differs from the stream"
                hung_at = claude.hung

                async def tick():                  # the instance's shutdown waits on the virtual clock
                    while True:
                        await clock.advance(1)
                ticker = asyncio.ensure_future(tick())
            await clock.settle()
        if sc.interrupt:
            ticker.cancel()
    assert errors == [], f"{sc.slug}: schema errors {errors[:3]}"

    if sc.interrupt:
        # The instance that held the run is gone; the page comes back 41 s later to another instance, which finds
        # the stored events in Atlas and ends them with H's `interrupted` (T3.1, contract §4.H).
        clock2 = FakeClock(start + timedelta(seconds=math.floor(hung_at) + 41))

        async def factory2():
            return AppDeps(store=store, execute_run=execute_run, loop_deps=deps, corpus_label=sc.label,
                           commit="fixture", clock=clock2, event_validator=validate)

        app2 = create_app(factory2)
        async with lifespan(app2):
            s2 = Client(app2).stream(f"/runs/{run_id}/events")
            await clock2.settle()
            s2.pump()
            again = s2.events()
            assert s2.closed and again[:-1] == stored, f"{sc.slug}: the replay differs from the stored events"
        events = again
        raw = s.text + s2.text
    else:
        raw = s.text
        check_stream(events, corpus, page_texts=page_texts(sc))      # G's checker: the schema and contract §6's order rules
        if not sc.spare_rounds:
            assert not claude.loop, f"{sc.slug}: {len(claude.loop)} scripted loop calls were left unused"
        assert not claude.comp, f"{sc.slug}: scripted composition calls were left unused"
        assert not transport._script, f"{sc.slug}: scripted Exa answers were left unused"
    check_expectations(sc, events)
    return Recorded(sc, document(sc, start, events), raw)


def check_expectations(sc: Scenario, events: list) -> None:
    end = events[-1]["data"]
    band = next((e["data"] for e in events if e["kind"] == "update_band"), None)
    got = {"state": end["state"], "stop_kind": end["stop_kind"], "answer_end": end["answer_end"],
           "band": band["outcome"] if band else None, "failure_reason": end["failure_reason"],
           "no_sources_reason": end["no_sources_reason"]}
    for k, v in sc.expect.items():
        if k == "refused_keeps":
            continue
        assert got[k] == v, f"{sc.slug}: {k} is {got[k]!r}, expected {v!r}"
    refused = [r["id"] for e in events if e["kind"] == "tool_result" for r in e["data"].get("refused", [])]
    assert refused == sc.expect.get("refused_keeps", []), f"{sc.slug}: keeps refused {refused}"


# ===============================================================================================================
# Scenarios
# ===============================================================================================================
SCENARIOS: list[Callable[[], Scenario]] = []


def scenario(fn):
    SCENARIOS.append(fn)
    return fn


def answered(**kw):
    return {"state": "answered", "stop_kind": None, "answer_end": "complete", **kw}


# --- 1. An answered run: phone location records ------------------------------------------------------------------
LOC_KEEPS = {
    "carpenter-1-p25": "Majority (Roberts): the holding that getting historical cell-site records from a carrier was a search, and that Smith and Miller were not extended to it.",
    "carpenter-1-p28": "Majority: why cell-site records raise greater privacy concerns than the GPS tracking in Jones.",
    "carpenter-1-p33": "Majority: states the conclusion that accessing the records invaded a reasonable expectation of privacy in the whole of physical movements.",
    "carpenter-1-p41": "Majority: the warrant requirement; the Government must generally get a warrant supported by probable cause for such records.",
    "smith-1-p16": "Majority (Blackmun): the assumed-risk reasoning of the third-party rule that Carpenter declined to extend to location records.",
    "miller-1-p16": "Majority (Powell): the bank-records version of the third-party rule.",
    "katz-3-p2": "Concurrence (Harlan): the two-part expectation-of-privacy test later called the Katz test. A concurrence, not the Court's opinion.",
    "carpenter-4-p5": "Dissent (Alito): the opposing view, that the order was not a search. A dissent, not the holding.",
}
LOC_P40_FIRST = "Majority: says the decision is narrow."
LOC_P40 = "Majority: the decision is expressly narrow; real-time location data, tower dumps and conventional surveillance such as security cameras are left open."

LOC_ANSWER = [
    T("## What the Court has said\n\n"),
    C("In *Carpenter v. United States*, 585 U.S. 296 (2018), the majority held that the Government's acquisition of historical cell-site location records from wireless carriers was a search under the Fourth Amendment. ",
      ("carpenter-1-p25", 2, 2)),
    C("It reached that result by declining to extend the third-party cases *Smith v. Maryland* and *United States v. Miller* to these records. ",
      ("carpenter-1-p25", 0, 0)),
    C("It explained that historical cell-site records present even greater privacy concerns than the GPS monitoring of a vehicle considered in *United States v. Jones*, because tracking a phone achieves near perfect surveillance, \"as if it had attached an ankle monitor to the phone's user\". ",
      ("carpenter-1-p28", 0, 0), ("carpenter-1-p28", 5, 5)),
    T("\n\n## The cases it declined to extend\n\n"),
    C("In *Smith*, the Court held that a person who voluntarily conveys the numbers he dials to the phone company assumes the risk that the company will reveal them to the police. ",
      ("smith-1-p16", 1, 2)),
    C("*Miller* reasoned the same way about bank records: the depositor takes the risk, in revealing his affairs to another, that the information will be conveyed by that person to the Government. ",
      ("miller-1-p16", 0, 0)),
    C("Justice Harlan's concurrence in *Katz v. United States* set out a two-part test: a person must have exhibited an actual (subjective) expectation of privacy, and the expectation must be one that society is prepared to recognize as reasonable. It is a concurrence, not the Court's opinion.",
      ("katz-3-p2", 3, 3)),
    T("\n\n## Warrant, and how far the holding goes\n\n"),
    C("Having found a search, the majority concluded that the Government must generally obtain a warrant supported by probable cause before acquiring such records. ",
      ("carpenter-1-p41", 0, 0)),
    C("The Court called its decision narrow: it expressed no view on real-time location data or \"tower dumps\", said it did not disturb the application of *Smith* and *Miller*, and did not call into question conventional surveillance techniques and tools, such as security cameras. ",
      ("carpenter-1-p40", 0, 3)),
    C("Justice Alito dissented, describing the majority's holding as based on the premise that the order was an actual search, a premise he said was inconsistent with the original meaning of the Fourth Amendment and with more than a century of precedent. A dissent is not the Court's holding.",
      ("carpenter-4-p5", 3, 3)),
    T("\n\n## What this does not settle\n\nThese passages do not say how the rules apply to any particular person's records, and the Court expressly left some kinds of location data open. This is research, not legal advice. Developments after the corpus's coverage dates are not part of this answer; see the update check beside it."),
]

LOC_PAGE_1 = page("Appeals court weighs a tower-dump warrant", "news.example.test", "tower-dump-appeal", "2026-09-12", 3812, "Sample Staff")
WEB_LOC_1 = Web(pages=[
    LOC_PAGE_1,
    page("State bill would limit sales of location data to agencies", "capitol.example.test", "location-data-bill", "2026-08-03", 2905),
    page("Notes on location records and the third-party rule", "journal.example.test", "location-notes", None, 4000),
    page("Privacy law roundup, October", "digest.example.test", "privacy-roundup-oct", "2026-10-01", 3340, "Sample Editor"),
])
WEB_LOC_2 = Web(pages=[
    page("Petitions on location data wait at the Court", "news.example.test", "location-petitions", "2026-09-28", 3120),
    LOC_PAGE_1,                                     # returned again: a repeat of web-1-1
    page("Commentary: what remains open after the location-records decision", "review.example.test", "what-remains-open", "2026-07-20", 4000, "Sample Contributor"),
    page("Scholars react to a state high court's location ruling", "journal.example.test", "state-high-court", "2026-08-19", 2710),
])


@scenario
def answered_phone_location_records():
    return Scenario("answered-phone-location-records", "Do police need a warrant to get my cell phone location records from my carrier?", [
        Round([
            Call("search_meaning", {"query": "whether police need a warrant to obtain cell phone location records from a wireless carrier",
                                    "max_results": 6}, seed="carpenter-1-p41"),
            Call("search_meaning", {"query": "how the Court treated the Government's acquisition of historical cell-site records",
                                    "max_results": 6}, seed="carpenter-1-p33"),
            Call("search_exact", {"any_of": ["cell-site", "CSLI"], "filters": {"decided_from": "2012"}, "max_results": 6}),
        ]),
        Round([
            Call("search_meaning", {"query": "a person has no legitimate expectation of privacy in information voluntarily turned over to a third party",
                                    "filters": {"decided_to": "1990"}, "max_results": 5}, seed="smith-1-p16"),
            Call("search_exact", {"any_of": ["\"takes the risk\"", "\"assumed the risk\""],
                                  "filters": {"decided_to": "1990", "opinion_types": ["majority"]}, "max_results": 4}),
            Call("search_meaning", {"query": "tracking a person's movements through a phone compared with GPS monitoring of a car",
                                    "filters": {"decided_from": "2012"}, "max_results": 4}, seed="carpenter-1-p28"),
            Call("keep_passages", {"keep": [K(i, LOC_KEEPS[i]) for i in ("carpenter-1-p25", "carpenter-1-p33", "carpenter-1-p41")]}),
        ], text="Reading the third-party cases the Court discussed."),
        Round([
            Call("read_passages", {"target": "carpenter-1-p40", "before": 0, "after": 1}),
            Call("search_meaning", {"query": "actual expectation of privacy and an expectation society is prepared to recognize as reasonable",
                                    "filters": {"cases": ["katz"]}, "max_results": 3}, seed="katz-3-p2"),
            Call("search_exact", {"all_of": ["probable cause", "cell-site"], "filters": {"cases": ["carpenter"], "opinion_types": ["dissent"]}, "max_results": 3}),
            Call("keep_passages", {"keep": [K("carpenter-1-p28", LOC_KEEPS["carpenter-1-p28"]), K("smith-1-p16", LOC_KEEPS["smith-1-p16"]),
                                            K("miller-1-p16", LOC_KEEPS["miller-1-p16"])]}),
        ]),
        Round([
            Call("search_exact", {"any_of": ["\"585 U. S. 296\"", "\"585 U. S., at\""], "filters": {"decided_from": "2019"}, "max_results": 4}),
            Call("keep_passages", {"keep": [K("katz-3-p2", LOC_KEEPS["katz-3-p2"]), K("carpenter-4-p5", LOC_KEEPS["carpenter-4-p5"]),
                                            K("carpenter-1-p40", LOC_P40_FIRST)]}),
        ]),
        Round([
            Call("search_web_updates", {"query": "Supreme Court cell phone location records warrant decision", "start_published_date": "2026-06-30",
                                        "end_published_date": "2026-10-24", "category": "news", "num_results": 5}, web=WEB_LOC_1),
            Call("keep_passages", {"keep": [K("carpenter-1-p40", LOC_P40)]}),
        ], text="Checking for developments after the corpus's last decision."),
        Round([
            Call("search_web_updates", {"query": "pending petitions location data warrant third-party doctrine", "start_published_date": "2026-06-30",
                                        "category": "publication", "num_results": 5}, web=WEB_LOC_2),
        ]),
        Round([
            Call("submit_answer", {"out_of_scope": False, "update_findings": [
                {"statement": "A sample news page reports that a federal court of appeals took up a challenge to a tower-dump warrant in September 2026.",
                 "sources": ["web-1-1"]},
                {"statement": "Sample pages report that a state legislature was considering limits on sales of location data to government agencies, and that petitions on location data were waiting at the Court.",
                 "sources": ["web-1-2", "web-2-1"]}],
                "update_overview": "The sample pages describe lower-court and legislative activity on location data after the corpus's coverage dates. None of them reports a Supreme Court decision."}),
        ]),
    ], Comp(LOC_ANSWER), expect=answered(band="found"))


# --- Small topics reused by many streams ----------------------------------------------------------------------------
PHONE_Q = "Can police search my phone when they arrest me?"
PHONE_KEEPS = {
    "riley-1-p26": "Majority (Roberts): the holding. The Court declines to extend Robinson to cell phone data and says officers must generally get a warrant.",
    "riley-1-p25": "Majority: why the older search-incident-to-arrest rationales do not carry over to digital data.",
    "riley-1-p66": "Majority: the Court's own summary of what police must do before searching a phone seized at an arrest.",
}
PHONE_ANSWER = [
    T("## Short answer\n\n"),
    C("In *Riley v. California* the Court declined to extend the *Robinson* rule for searches incident to arrest to the data on cell phones, and held that officers must generally secure a warrant before conducting such a search. ",
      ("riley-1-p26", 0, 0)),
    C("The majority found no comparable risks to those behind the older rule when the search is of digital data, and noted that cell phones place vast quantities of personal information literally in the hands of individuals. ",
      ("riley-1-p25", 2, 2), ("riley-1-p25", 4, 4)),
    C("It summed up its answer to what police must do before searching a cell phone seized incident to an arrest as simple: get a warrant.",
      ("riley-1-p66", 3, 3)),
    T("\n\nThis states what the Court held and why. It does not say how the rule applies to any particular arrest, and it is research, not legal advice."),
]
RILEY_SKIP = "The question asks what the Court held in Riley, so a search for later developments was not needed."
KYLLO_SKIP = "The question asks what the Court held in Kyllo, so a search for later developments was not needed."
GPS_SKIP = "The question asks what the Court held about GPS trackers, so a search for later developments was not needed."


def phone_search_calls():
    return [
        Call("search_meaning", {"query": "searching the digital contents of a cell phone found on a person who has just been arrested",
                                "max_results": 6}, seed="riley-1-p25"),
        Call("search_exact", {"all_of": ["cell phone", "warrant"], "filters": {"cases": ["riley"], "opinion_types": ["majority"]},
                              "max_results": 4}),
    ]


def phone_keep(*ids):
    return Call("keep_passages", {"keep": [K(i, PHONE_KEEPS[i]) for i in ids]})


THERMAL_Q = "Can police use a thermal imager on my house from the street?"
THERMAL_KEEPS = {
    "kyllo-1-p1": "Majority (Scalia): states the question presented, a thermal imager aimed at a home from a public street.",
    "kyllo-1-p14": "Majority: the holding, that using a device not in general public use to explore the home is a search.",
    "kyllo-1-p7": "Majority: separates naked-eye observation from technological enhancement and refers back to Dow Chemical.",
}
THERMAL_ANSWER = [
    T("## Short answer\n\n"),
    C("In *Kyllo v. United States* the Court considered whether using a thermal-imaging device aimed at a private home from a public street, to detect relative amounts of heat within the home, is a search. ",
      ("kyllo-1-p1", 0, 0)),
    C("It held that where the Government uses a device that is not in general public use to explore details of the home that would previously have been unknowable without physical intrusion, the surveillance is a search and is presumptively unreasonable without a warrant. ",
      ("kyllo-1-p14", 5, 5)),
    C("The majority contrasted this with naked-eye observation from a public street, noting that it had reserved how much technological enhancement is too much and had upheld enhanced aerial photography of an industrial complex in *Dow Chemical*.",
      ("kyllo-1-p7", 0, 2)),
    T("\n\nThis is what the opinion says, not how it applies to any particular home. It is research, not legal advice."),
]


def thermal_search_calls(meaning_max=4, exact_max=3):
    return [
        Call("search_meaning", {"query": "using a thermal imaging device on a house from a public street", "max_results": meaning_max}, seed="kyllo-1-p5"),
        Call("search_exact", {"any_of": ["\"thermal imaging\"", "\"thermal-imaging\""], "filters": {"cases": ["kyllo"], "opinion_types": ["majority"]},
                              "max_results": exact_max}),
    ]


def thermal_keep(*ids):
    return Call("keep_passages", {"keep": [K(i, THERMAL_KEEPS[i]) for i in ids]})


def submit(**inp):
    return Call("submit_answer", {"out_of_scope": False, **inp})


# --- 2. A reply with no sources: out of scope ------------------------------------------------------------------------
OUT_OF_SCOPE_NOTE = ("This question is about landlord-tenant law, which falls outside what this corpus covers: Supreme Court opinions on the "
                     "Fourth Amendment and surveillance technology. A related question I can research is whether police may use technology such as "
                     "thermal imaging to look into a home from outside it.")


@scenario
def out_of_scope_reply():
    skip = "The question is outside the corpus's subject, so there is nothing to check for later developments."
    return Scenario("out-of-scope-reply", "Can my landlord raise my rent in the middle of a lease?", [
        Round([Call("submit_answer", {"out_of_scope": True, "note": OUT_OF_SCOPE_NOTE, "update_skip_reason": skip})], think=1_400),
    ], expect={"state": "no_sources", "no_sources_reason": "out_of_scope", "band": "skipped"})


# --- 3. A reply with no sources: nothing found ----------------------------------------------------------------------
@scenario
def nothing_found_reply():
    note = ("Claude found no passages in the corpus that bear on this question. The corpus holds Supreme Court opinions on the Fourth Amendment "
            "and surveillance technology, and none of them addresses searches by school officials. A related question it can answer is how the "
            "Court treats searches of the data on a cell phone.")
    return Scenario("nothing-found-reply", "Does the Fourth Amendment require a warrant before a public school searches a student's backpack?", [
        Round([
            Call("search_meaning", {"query": "a school official searching a student's belongings for contraband", "max_results": 5}, seed="grady-1-p9"),
            Call("search_exact", {"all_of": ["school", "student"], "max_results": 5}),
        ]),
        Round([
            Call("read_passages", {"target": "grady-1-p9", "before": 1, "after": 1}),
            Call("search_exact", {"any_of": ["\"school official\"", "\"public school\"", "schoolchildren"], "max_results": 5}),
        ], text="The only mention of schools is in passing; checking its context."),
        Round([
            Call("search_web_updates", {"query": "Supreme Court student backpack search Fourth Amendment school decision", "start_published_date": "2026-06-30",
                                        "category": "news", "num_results": 3},
                 web=Web(pages=[page("School district updates its locker search policy", "schools.example.test", "locker-policy", "2026-08-21", 2480),
                                page("A parent's guide to searches at school", "family.example.test", "parents-guide", None, 3160)])),
        ]),
        Round([submit(note=note, update_findings=[])]),
    ], expect={"state": "no_sources", "no_sources_reason": "nothing_found", "band": "nothing_relevant"})


# --- pause and resume (T3.2), with a scope note -----------------------------------------------------------------------
@scenario
def pause_and_resume():
    scope = ("Part of this question turns on a state constitution, which the corpus does not cover. The answer sets out only what the "
             "Supreme Court held under the Fourth Amendment.")
    return Scenario("pause-and-resume", "Can police search my phone when they arrest me, and does my state constitution add anything?", [
        # a long first call while the page sends no heartbeat (a phone's screen turned off)
        Round([Call("search_exact", {"all_of": ["cell phone", "warrant"], "filters": {"cases": ["riley"], "opinion_types": ["majority"]}, "max_results": 4}),
               Call("search_exact", {"any_of": ["\"search incident to arrest\"", "\"incident to the arrest\""], "filters": {"cases": ["riley"]}, "max_results": 4})],
              think=2_200),
        # paused before this call: no heartbeat for over ATTENDED_WINDOW_S; resumed when the page's heartbeat returns
        Round([Call("search_meaning", {"query": "searching the digital contents of a cell phone found on a person who has just been arrested",
                                       "max_results": 6}, seed="riley-1-p25"),
               Call("read_passages", {"target": "riley-1-p66"})]),
        Round([phone_keep("riley-1-p26", "riley-1-p25", "riley-1-p66")]),
        Round([submit(note=scope, update_skip_reason=RILEY_SKIP)]),
    ], Comp(PHONE_ANSWER), heartbeat=lambda t: not (0 < t < 40), expect=answered(band="skipped"))


# --- an abandoned run (T3.2) ---------------------------------------------------------------------------------------------
@scenario
def abandoned_run():
    return Scenario("abandoned-run", PHONE_Q, [
        Round(phone_search_calls()),
        Round([phone_keep("riley-1-p26", "riley-1-p25")], think=2_400),
        Round([Call("read_passages", {"target": "riley-1-p66"})]),      # never made: paused before it, then abandoned
    ], heartbeat=lambda t: t <= 10, spare_rounds=True,
        expect={"state": "abandoned", "stop_kind": None, "answer_end": "none", "band": "not_run"})


# --- an interrupted run (T3.1): the instance that held it is gone; the page reconnects to another one -------------
@scenario
def interrupted_run():
    return Scenario("interrupted-run", THERMAL_Q, [
        Round(thermal_search_calls()),
        Round([thermal_keep("kyllo-1-p14")]),
        Round([Call("search_exact", {"any_of": ["\"general public use\""], "max_results": 3})], hang=True),
    ], interrupt=True, expect={"state": "interrupted", "answer_end": "none", "band": None})


# --- The GPS topic -----------------------------------------------------------------------------------------------------
GPS_Q = "Can police attach a GPS tracker to a car without a warrant?"
GPS_KEEPS = {
    "jones-1-p8": "Majority (Scalia): the holding, that installing a GPS device on a vehicle and monitoring its movements is a search.",
    "jones-1-p9": "Majority: the reasoning from physical occupation of private property, tied to the Amendment's text and history.",
    "knotts-1-p15": "Majority (Rehnquist): the earlier beeper case; no reasonable expectation of privacy in movements on public roads.",
    "karo-1-p19": "Majority (White): why a beeper inside a house differs from Knotts.",
    "jones-2-p4": "Concurrence (Sotomayor): attributes of GPS monitoring. A concurrence, not the Court's opinion.",
    "jones-3-p29": "Concurrence in the judgment (Alito): reaches the result on the expectation-of-privacy test. Not the majority's reasoning.",
}
GPS_ANSWER = [
    T("## Short answer\n\n"),
    C("In *United States v. Jones*, the majority held that the Government's installation of a GPS device on a target's vehicle, and its use of that device to monitor the vehicle's movements, constitutes a search. ",
      ("jones-1-p8", 3, 3)),
    C("It reasoned that the Government had physically occupied private property for the purpose of obtaining information, which would have been considered a search when the Fourth Amendment was adopted. ",
      ("jones-1-p9", 0, 1)),
    T("\n\n## How the beeper cases fit\n\n"),
    C("Earlier, in *United States v. Knotts*, the Court had said that a person traveling in an automobile on public thoroughfares has no reasonable expectation of privacy in his movements from one place to another. ",
      ("knotts-1-p15", 0, 0)),
    C("In *United States v. Karo*, the Court distinguished that case: monitoring a beeper inside a private residence revealed a critical fact about the interior of the premises that the Government could not otherwise have obtained without a warrant. ",
      ("karo-1-p19", 0, 1)),
    T("\n\n## Separate opinions\n\n"),
    C("Justice Sotomayor, concurring, wrote that GPS monitoring generates a precise, comprehensive record of a person's public movements. ",
      ("jones-2-p4", 1, 1)),
    C("Justice Alito, concurring in the judgment, concluded that the lengthy monitoring in the case constituted a search under the Fourth Amendment. A concurrence in the judgment is not the majority's opinion.",
      ("jones-3-p29", 0, 0)),
    T("\n\nThese passages say what the Court held, not how it applies to any particular tracker. This is research, not legal advice."),
]


def gps_keep(*ids):
    return Call("keep_passages", {"keep": [K(i, GPS_KEEPS[i]) for i in ids]})


# --- 4. The step limit: twelve rounds, then the answer is built from what was kept (T1.11, T3.5) ----------------------
@scenario
def step_limit_stop():
    return Scenario("step-limit-stop", GPS_Q, [
        Round([
            Call("search_meaning", {"query": "attaching a GPS tracking device to a car and following its movements", "max_results": 4}, seed="jones-1-p8"),
            Call("search_exact", {"any_of": ["GPS", "\"Global-Positioning-System\""], "filters": {"decided_from": "2000"}, "max_results": 4}),
        ]),
        Round([
            Call("search_meaning", {"query": "movements on public roads are visible to anyone, so no reasonable expectation of privacy",
                                    "filters": {"decided_to": "1990"}, "max_results": 4}, seed="knotts-1-p15"),
            Call("search_exact", {"any_of": ["beeper"], "filters": {"cases": ["knotts"], "opinion_types": ["majority"]}, "max_results": 3}),
            Call("read_passages", {"target": "jones-1-p9"}),
            gps_keep("jones-1-p8"),
        ]),
        Round([gps_keep("jones-1-p9"), Call("read_passages", {"target": "knotts-1-p15", "before": 1, "after": 1}),
               Call("search_meaning", {"query": "monitoring an electronic tracking device inside a private home", "max_results": 4}, seed="karo-1-p19")]),
        Round([gps_keep("knotts-1-p15"),
               Call("search_exact", {"all_of": ["beeper", "warrant"], "filters": {"cases": ["karo"]}, "max_results": 3})]),
        Round([Call("read_passages", {"target": "karo-1-p19", "before": 0, "after": 2})]),
        Round([gps_keep("karo-1-p19"),
               Call("search_meaning", {"query": "GPS monitoring creates a precise, comprehensive record of a person's public movements",
                                       "filters": {"opinion_types": ["concurrence"]}, "max_results": 4}, seed="jones-2-p4")]),
        Round([Call("read_passages", {"target": "jones-2-p4", "before": 1, "after": 1}),
               Call("search_exact", {"all_of": ["long-term", "monitoring"], "filters": {"cases": ["jones"]}, "max_results": 3})]),
        Round([gps_keep("jones-2-p4"), Call("read_passages", {"target": "jones-3-p28", "before": 0, "after": 1})]),
        Round([gps_keep("jones-3-p29"),
               Call("search_exact", {"any_of": ["\"565 U. S. 400\"", "\"565 U. S., at\""], "filters": {"decided_from": "2013"}, "max_results": 4})]),
        Round([Call("search_meaning", {"query": "tracking a person through a phone compared with GPS monitoring of a car",
                                       "filters": {"decided_from": "2013"}, "max_results": 4}, seed="carpenter-1-p28")]),
        Round([Call("search_web_updates", {"query": "GPS tracker warrant court decision", "start_published_date": "2026-06-30", "category": "news",
                                           "num_results": 4},
                    web=Web(pages=[page("Police GPS trackers draw a new round of challenges", "news.example.test", "gps-challenges", "2026-09-03", 3010),
                                   page("Explainer: tracking devices and the warrant requirement", "explainer.example.test", "tracking-explainer", None, 3880)]))]),
        Round([Call("search_exact", {"any_of": ["\"Global-Positioning-System\"", "\"GPS\""], "filters": {"decided_from": "2013"}, "max_results": 4})]),
    ], Comp(GPS_ANSWER), expect={"state": "step_limit", "stop_kind": "step_limit", "answer_end": "complete", "band": "not_summarised"})


# --- the checks: a misquotation and a full case name that is not in the corpus (T1.12, T5.2) -----------------------
@scenario
def check_flags():
    spec = [
        T("## Short answer\n\n"),
        C("In *United States v. Jones*, the majority held that the Government's installation of a GPS device on a target's vehicle, and its use of that device to monitor the vehicle's movements, constitutes a search. ",
          ("jones-1-p8", 3, 3)),
        C("Its reasoning rested on physical intrusion on property, and it described *Entick v. Carrington*, 95 Eng. Rep. 807 (C. P. 1765), as a case familiar to every American statesman when the Constitution was adopted. ",
          ("jones-1-p9", 0, 2)),
        C("It set this against *United States v. Knotts*, where the Court said \"a person traveling in an automobile on public thoroughfares has no reasonable expectation of privacy in his journeys from one place to another\". ",
          ("knotts-1-p15", 0, 0)),
        C("In *Karo* the Court found that a beeper inside a house revealed a critical fact about the interior of the premises that the Government could not otherwise have obtained without a warrant.",
          ("karo-1-p19", 0, 0)),
        T("\n\nThis is research, not legal advice."),
    ]
    return Scenario("check-flags", GPS_Q, [
        Round([
            Call("search_meaning", {"query": "attaching a GPS tracking device to a car and following its movements", "max_results": 4}, seed="jones-1-p8"),
            Call("search_exact", {"any_of": ["beeper"], "filters": {"opinion_types": ["majority"]}, "max_results": 4}),
        ]),
        Round([
            Call("search_meaning", {"query": "movements on public roads are visible to anyone", "filters": {"decided_to": "1990"}, "max_results": 3}, seed="knotts-1-p15"),
            Call("search_meaning", {"query": "a beeper inside a private home", "max_results": 3}, seed="karo-1-p19"),
            Call("read_passages", {"target": "jones-1-p9"}),
        ]),
        Round([gps_keep("jones-1-p8", "jones-1-p9", "knotts-1-p15", "karo-1-p19")]),
        Round([submit(update_skip_reason=GPS_SKIP)]),
    ], Comp(spec), expect=answered(band="skipped"))


# --- 5. The per-run input ceiling (T3.3): the next call would cross 370,000 input tokens --------------------------------
HEAVY_POOL = [
    ("riley-1-p47", "what makes a cell phone different from other things an arrestee carries", "riley-1-p50", "the volume of private information in a phone", "riley-1-p43"),
    ("carpenter-1-p28", "cell-site records compared with GPS tracking", "carpenter-1-p16", "location data held by a third party", "carpenter-1-p41"),
    ("kyllo-1-p14", "technology that reveals the inside of a home", "kyllo-1-p7", "enhanced observation from a public street", "kyllo-1-p14"),
    ("jones-2-p4", "long-term monitoring of public movements", "jones-1-p9", "physical intrusion on property as a search", "jones-3-p25"),
    ("katz-3-p2", "an expectation of privacy society recognizes as reasonable", "katz-1-p6", "protecting people rather than places", "katz-1-p9"),
    ("smith-1-p16", "information a person voluntarily conveys to a company", "miller-1-p16", "records held by a bank", "smith-1-p11"),
    ("chatrie-1-p26", "how the Court applied Carpenter to a location history request", "chatrie-4-p1", "a dissent warning about Carpenter", "chatrie-1-p30"),
    ("ciraolo-1-p10", "observation from an aircraft over a backyard", "florida_v_riley-1-p5", "a helicopter flying at low altitude", "ciraolo-1-p10"),
    ("olmstead-1-p23", "wiretapping before Katz", "berger-1-p23", "electronic eavesdropping and particularity", "olmstead-1-p23"),
    ("dow-1-p10", "aerial photography of an industrial plant", "jardines-1-p6", "a drug-sniffing dog on a front porch", "dow-1-p10"),
    ("karo-1-p19", "a beeper carried into a private residence", "knotts-1-p15", "following a car on public highways", "karo-1-p19"),
]


@scenario
def token_ceiling_input():
    rounds = []
    for k, (sd1, q1, sd2, q2, rd) in enumerate(HEAVY_POOL):
        calls = [Call("search_meaning", {"query": q1, "max_results": 6}, seed=sd1),
                 Call("search_meaning", {"query": q2, "max_results": 6}, seed=sd2),
                 Call("read_passages", {"target": rd, "before": 3, "after": 3})]
        if k == 0:
            calls = phone_search_calls() + calls[2:]
        if k == 1:
            calls.insert(0, phone_keep("riley-1-p26", "riley-1-p25", "riley-1-p66"))
        # a busy day: calls that failed and were retried still count toward the ceiling (T3.3), so it comes sooner
        retries = {2: [("overloaded", 1.3), ("overloaded", 1.05)], 4: [("rate_limited", 0.9), ("overloaded", 1.2)]}.get(k, [])
        rounds.append(Round(calls, retries=retries))
    return Scenario("token-ceiling-input", PHONE_Q, rounds, Comp(PHONE_ANSWER), spare_rounds=True,
                    expect={"state": "token_ceiling", "stop_kind": "token_ceiling_input", "answer_end": "complete", "band": "not_run"})


# --- 6. The per-run output ceiling (T3.3): the last loop call is cut at max_tokens ------------------------------------------
@scenario
def token_ceiling_output():
    rounds = [
        thermal_search_calls(),
        [thermal_keep("kyllo-1-p1", "kyllo-1-p14"), Call("read_passages", {"target": "kyllo-1-p14", "before": 1, "after": 1})],
        [thermal_keep("kyllo-1-p7"), Call("search_meaning", {"query": "devices in general public use", "max_results": 3}, seed="kyllo-1-p14")],
        [Call("search_exact", {"any_of": ["\"general public use\""], "max_results": 3})],
        [Call("search_meaning", {"query": "enhanced aerial photography of an industrial complex", "max_results": 3}, seed="dow-1-p10")],
        [Call("search_exact", {"any_of": ["\"naked eye\""], "filters": {"cases": ["kyllo"]}, "max_results": 3})],
        [Call("search_meaning", {"query": "the line the Fourth Amendment draws at the entrance to the house", "max_results": 3}, seed="kyllo-1-p14")],
        [Call("read_passages", {"target": "kyllo-1-p5", "before": 0, "after": 2})],
        [Call("search_exact", {"any_of": ["home"], "filters": {"cases": ["kyllo"], "opinion_types": ["dissent"]}, "max_results": 3})],
        [Call("read_passages", {"target": "kyllo-2-p1", "before": 0, "after": 2})],
    ]
    rng = random.Random("token-ceiling-output thinking")
    return Scenario("token-ceiling-output", THERMAL_Q, [Round(c, think=rng.randint(780, 900)) for c in rounds],
                    Comp(THERMAL_ANSWER), spare_rounds=True,
                    expect={"state": "token_ceiling", "stop_kind": "token_ceiling_output", "answer_end": "complete", "band": "not_run"})


# --- 7. The time limit (T3.5): ten minutes, then the answer is built from what was kept ------------------------------------
@scenario
def time_limit_stop():
    secs = [88.4, 95.1, 84.7, 101.2, 92.6, 97.3, 90.8, 86.0]     # a slow day: each loop call takes a minute and a half
    rounds = [
        phone_search_calls(),
        [phone_keep("riley-1-p26", "riley-1-p25", "riley-1-p66"),
         Call("search_meaning", {"query": "why a phone is unlike a wallet or a cigarette pack", "max_results": 4}, seed="riley-1-p43")],
        [Call("read_passages", {"target": "riley-1-p26", "before": 1, "after": 1})],
        [Call("search_exact", {"any_of": ["\"search incident to arrest\""], "filters": {"cases": ["riley"]}, "max_results": 4})],
        [Call("search_meaning", {"query": "what officers may do to keep a phone from being wiped", "max_results": 4}, seed="riley-1-p32")],
        [Call("read_passages", {"target": "riley-1-p66", "before": 2, "after": 0})],
        [Call("search_exact", {"any_of": ["\"cloud computing\"", "\"remote wiping\""], "filters": {"cases": ["riley"]}, "max_results": 3})],
        [Call("search_meaning", {"query": "searches of phones at the border or in schools", "max_results": 3}, seed="riley-1-p62")],
    ]
    return Scenario("time-limit-stop", PHONE_Q, [Round(c, seconds=s) for c, s in zip(rounds, secs)], Comp(PHONE_ANSWER),
                    spare_rounds=True,
                    expect={"state": "time_limit", "stop_kind": "time_limit", "answer_end": "complete", "band": "not_run"})


# --- Refused submits (T1.10, T2.3, P4.3) -------------------------------------------------------------------------------------
COPY_LEAD = ("In a ruling this week the court of appeals held that police must obtain a warrant before using a thermal imaging "
             "device to scan the exterior of a home from a public street.")
COPIED = ("The court of appeals held that police must obtain a warrant before using a thermal imaging device to scan the "
          "exterior of a home from a public street.")


@scenario
def submit_refused_copy_guard():
    return Scenario("submit-refused-copy-guard", THERMAL_Q, [
        Round(thermal_search_calls()),
        Round([thermal_keep("kyllo-1-p1", "kyllo-1-p14", "kyllo-1-p7"),
               Call("search_web_updates", {"query": "thermal imaging warrant court of appeals ruling", "start_published_date": "2026-06-30",
                                           "category": "news", "num_results": 3},
                    web=Web(pages=[page("Appeals court rules on thermal scans of homes", "news.example.test", "thermal-ruling", "2026-09-17", 3600, "Sample Staff", COPY_LEAD),
                                   page("Thermal imaging: what officers may use", "explainer.example.test", "thermal-explainer", "2026-08-05", 2950)]))]),
        Round([submit(update_findings=[
            {"statement": "A sample news page reports an appeals court ruling on thermal scans of homes.", "sources": ["web-3-1"]},
            {"statement": "A second sample page lists the devices officers may use without a warrant.", "sources": []}])]),
        Round([submit(update_findings=[
            {"statement": COPIED, "sources": ["web-1-1"]},
            {"statement": "A second sample page discusses which devices officers use, without saying whether any ruling changed.", "sources": ["web-1-2"]}],
            update_overview="The sample pages describe a lower-court ruling and an explainer.")]),
        Round([submit(update_findings=[
            {"statement": "A sample news page reports that an appeals court addressed thermal scans of homes from the street and required a warrant for them.",
             "sources": ["web-1-1"]},
            {"statement": "A second sample page discusses which devices officers use, without saying whether any ruling changed.", "sources": ["web-1-2"]}],
            update_overview="The sample pages describe a lower-court ruling and an explainer.")]),
    ], Comp(THERMAL_ANSWER), expect=answered(band="found"))


@scenario
def submit_refused_basic_rules_then_declined():
    spec = [x for x in PHONE_ANSWER if all(pid != "riley-1-p66" for pid, _, _ in x["cites"])]
    return Scenario("submit-refused-basic-rules-then-declined", PHONE_Q, [
        Round([Call("read_passages", {"target": "riley-1-p1"}), Call("read_passages", {"target": "riley-1-p999"}),
               submit()]),                                                          # rule 1: in the same turn as a read
        Round([submit()]),                                                          # rule 2: a read alone is not a search
        Round([Call("submit_answer", {"out_of_scope": "no"})]),                     # bad input: rule null (v1.3)
        Round(phone_search_calls()),
        Round([Call("submit_answer", {"out_of_scope": True})]),                     # out of scope with no note: no_note (v1.3)
        Round([submit()]),                                                          # rule 3: nothing kept, no note
        Round([Call("keep_passages", {"keep": [K("riley-1-p26", PHONE_KEEPS["riley-1-p26"]), K("riley-1-p25", PHONE_KEEPS["riley-1-p25"]),
                                               K("riley-1-p67", "The last paragraph of the opinion.")]})]),   # one ID never shown
        Round([submit()]),                                                          # rule 4: no update check, no reason: refused once
        Round([submit()]),                                                          # accepted after the reminder: declined
    ], Comp(spec), expect=answered(band="declined", refused_keeps=["riley-1-p67"]))


# --- The update check unavailable (T2.4, P2.11) ------------------------------------------------------------------------------
def unavailable_run(slug, reason, *, at_start=False):
    calls = [thermal_keep("kyllo-1-p1", "kyllo-1-p14", "kyllo-1-p7")]
    if not at_start:
        calls.append(Call("search_web_updates", {"query": "thermal imaging warrant ruling", "start_published_date": "2026-06-30", "num_results": 5},
                          web=Web(kind=reason)))
    return Scenario(slug, THERMAL_Q, [
        Round(thermal_search_calls()),
        Round(calls),
        Round([submit()]),        # rule 4 is waived while the check is unavailable
    ], Comp(THERMAL_ANSWER), exa_flag=at_start, expect=answered(band="unavailable"))


@scenario
def band_unavailable_no_credit():
    return unavailable_run("band-unavailable-no-credit", "no_credit")


@scenario
def band_unavailable_key_refused():
    return unavailable_run("band-unavailable-key-refused", "key_refused")


@scenario
def band_unavailable_credit_flag_at_start():
    return unavailable_run("band-unavailable-credit-flag-at-start", "no_credit", at_start=True)


# --- Every way an update search can end (T2.1, T2.4) -------------------------------------------------------------------------
@scenario
def update_search_statuses():
    q = {"query": "cell phone search incident to arrest new decision", "start_published_date": "2026-06-30", "category": "news", "num_results": 4}
    return Scenario("update-search-statuses", PHONE_Q, [
        Round(phone_search_calls()),
        Round([phone_keep("riley-1-p26", "riley-1-p25", "riley-1-p66")]),
        Round([Call("search_web_updates", {"query": "cell phone search warrant arrest ruling", "start_published_date": "2026-6-30"})]),   # refused by our code
        Round([Call("search_web_updates", q, web=Web(kind="refused"))]),
        Round([Call("search_web_updates", {**q, "type": "lite"}, web=Web(kind="failed", seconds=30.0))]),
        Round([Call("search_web_updates", {"query": "phone search arrest court", "start_published_date": "2026-06-30", "num_results": 4},
                    web=Web(pages=[page("Court notes on digital searches at arrest", "news.example.test", "arrest-notes", "2026-08-11", 2800),
                                   page("Local police update their phone-search policy", "city.example.test", "police-policy", "2026-09-02", 2150, "Sample Desk")]))]),
        Round([Call("search_web_updates", {"query": "phone search arrest policy", "num_results": 3})]),       # the fourth: refused by our code
        Round([submit(update_findings=[
            {"statement": "A sample page reports that a local police department updated its policy on searching phones after an arrest.", "sources": ["web-3-2"]}])]),
    ], Comp(PHONE_ANSWER), expect=answered(band="found"))


# --- The Voyage warning, both codes (T3.3) -------------------------------------------------------------------------------------
@scenario
def voyage_warning_degraded():
    return Scenario("voyage-warning-degraded", THERMAL_Q, [
        Round([Call("search_meaning", {"query": "using a thermal imaging device on a house from a public street", "max_results": 6}, seed="kyllo-1-p5"),
               thermal_search_calls()[1]]),
        Round([thermal_keep("kyllo-1-p1", "kyllo-1-p14", "kyllo-1-p7")]),
        Round([submit(update_skip_reason=KYLLO_SKIP)]),
    ], Comp(THERMAL_ANSWER), rerank_failures=["server_error"] * 3, expect=answered(band="skipped"))


@scenario
def voyage_warning_unavailable():
    return Scenario("voyage-warning-unavailable", THERMAL_Q, [
        Round([Call("search_meaning", {"query": "using a thermal imaging device on a house from a public street", "max_results": 6}, seed="kyllo-1-p5"),
               thermal_search_calls()[1]]),
        Round([Call("search_meaning", {"query": "using a thermal imaging device on a house from a public street", "max_results": 6}, seed="kyllo-1-p5")],
              text="Meaning search failed; trying it again, and using keyword search meanwhile."),
        Round([thermal_keep("kyllo-1-p1", "kyllo-1-p14", "kyllo-1-p7")]),
        Round([submit(update_skip_reason=KYLLO_SKIP)]),
    ], Comp(THERMAL_ANSWER), embed_failures=["rate_limited"] * 3, expect=answered(band="skipped"))


# --- Retries that worked: Anthropic (loop and composition) and Voyage (embed and rerank) (T3.3) ---------------------------------
@scenario
def retries_recovered():
    return Scenario("retries-anthropic-and-voyage-recovered", PHONE_Q, [
        Round(phone_search_calls(), retries=[("rate_limited", 0.85)]),
        Round([phone_keep("riley-1-p26", "riley-1-p25", "riley-1-p66")]),
        Round([submit(update_skip_reason=RILEY_SKIP)]),
    ], Comp(PHONE_ANSWER, retries=[("overloaded", 1.3)]), embed_failures=["server_error"],
        rerank_failures=["rate_limited", "server_error"], expect=answered(band="skipped"))


# --- Loop and composition failures (T3.3, T1.11, T5.4) --------------------------------------------------------------------------
@scenario
def error_stopped_after_retries():
    return Scenario("error-stopped-loop-retries-exhausted", THERMAL_Q, [
        Round(thermal_search_calls()),
        Round([thermal_keep("kyllo-1-p1", "kyllo-1-p14", "kyllo-1-p7")]),
        Round([Call("search_exact", {"any_of": ["\"general public use\""], "max_results": 3})],
              retries=[("overloaded", 1.5), ("overloaded", 1.2)], fail=("overloaded", 1.4)),
    ], Comp(THERMAL_ANSWER), expect={"state": "error_stopped", "stop_kind": None, "answer_end": "complete",
                                     "failure_reason": "overloaded", "band": "not_run"})


@scenario
def composition_incomplete():
    return Scenario("composition-incomplete-stream-broken", THERMAL_Q, [
        Round(thermal_search_calls()),
        Round([thermal_keep("kyllo-1-p1", "kyllo-1-p14", "kyllo-1-p7")]),
        Round([submit(update_skip_reason=KYLLO_SKIP)]),
    ], Comp(THERMAL_ANSWER, break_after=3),
        expect={"state": "answered", "answer_end": "incomplete", "failure_reason": "stream_broken", "band": "skipped"})


@scenario
def composition_failed():
    return Scenario("composition-failed-before-first-block", PHONE_Q, [
        Round(phone_search_calls()),
        Round([phone_keep("riley-1-p26", "riley-1-p25", "riley-1-p66")]),
        Round([submit(update_skip_reason=RILEY_SKIP)]),
    ], Comp(PHONE_ANSWER, fail=("server_error", 0.75)),
        expect={"state": "failed", "answer_end": "none", "failure_reason": "server_error", "band": "skipped"})


def gps_compact_rounds():
    """Three short rounds and an accepted submit on the GPS topic (shared by the cut-off stream)."""
    return [
        Round([
            Call("search_meaning", {"query": "attaching a GPS tracking device to a car and following its movements", "max_results": 4}, seed="jones-1-p8"),
            Call("search_exact", {"any_of": ["beeper"], "filters": {"opinion_types": ["majority"]}, "max_results": 4}),
        ]),
        Round([
            Call("search_meaning", {"query": "movements on public roads are visible to anyone", "filters": {"decided_to": "1990"}, "max_results": 3}, seed="knotts-1-p15"),
            Call("search_meaning", {"query": "a beeper inside a private home", "max_results": 3}, seed="karo-1-p19"),
            Call("read_passages", {"target": "jones-1-p9"}),
            Call("search_meaning", {"query": "GPS monitoring creates a precise, comprehensive record of a person's public movements",
                                    "filters": {"opinion_types": ["concurrence"]}, "max_results": 3}, seed="jones-2-p4"),
        ]),
        Round([gps_keep("jones-1-p8", "jones-1-p9", "knotts-1-p15", "karo-1-p19", "jones-2-p4")]),
        Round([submit(update_skip_reason=GPS_SKIP)]),
    ]


@scenario
def answer_cut_off():
    spec = GPS_ANSWER[:5] + [T("Justice Sotomayor, concurring, wrote that GPS monitoring generates a precise, comprehensive record of a person's public movements that reflects a wealth of detail about her familial, political, profes")]
    return Scenario("answer-cut-off-length-limit", GPS_Q, gps_compact_rounds(), Comp(spec, cut=True),
                    expect={"state": "answered", "stop_kind": "composition_max_tokens", "answer_end": "cut_off", "band": "skipped"})


@scenario
def failed_nothing_kept():
    return Scenario("failed-nothing-kept", THERMAL_Q, [
        Round(thermal_search_calls()),
        Round([thermal_keep("kyllo-1-p14")], retries=[("server_error", 0.9), ("server_error", 1.1)], fail=("server_error", 1.0)),
    ], expect={"state": "failed", "answer_end": "none", "failure_reason": "server_error", "band": "not_run"})


@scenario
def refusal():
    return Scenario("refusal", "How can I avoid being tracked by police while committing a crime?", [
        Round([Call("search_meaning", {"query": "avoiding police tracking", "max_results": 4}, seed="jones-2-p4")], refusal=True),
    ], expect={"state": "refusal", "answer_end": "none", "failure_reason": "refusal", "band": "not_run"})


@scenario
def spend_limit_console():
    return Scenario("spend-limit-console", THERMAL_Q, [
        Round(thermal_search_calls()),
        Round([thermal_keep("kyllo-1-p1", "kyllo-1-p14")]),
        Round([Call("search_exact", {"any_of": ["\"general public use\""], "max_results": 3})], fail=("spend_limit", 0.6)),
    ], expect={"state": "spend_limit", "stop_kind": "console_spend_limit", "answer_end": "none", "band": "not_run"})


@scenario
def spend_limit_tier_cap():
    return Scenario("spend-limit-tier-cap", PHONE_Q, [
        Round(phone_search_calls()),
        Round([phone_keep("riley-1-p26", "riley-1-p25"),
               Call("search_web_updates", {"query": "cell phone search arrest court decision", "start_published_date": "2026-06-30", "num_results": 3},
                    web=Web(pages=[page("Notes on phone searches after arrest", "news.example.test", "phone-notes", "2026-07-30", 2600)]))]),
        Round([Call("search_exact", {"any_of": ["\"get a warrant\""], "filters": {"cases": ["riley"]}, "max_results": 3})], fail=("spend_cap", 0.45)),
    ], expect={"state": "spend_limit", "stop_kind": "tier_spend_cap", "answer_end": "none", "band": "not_summarised"})


# --- A replay: the geofence question recorded on the corpus that ends before Chatrie (T5.6) ---------------------------------
GEO_Q = "Is getting someone's location history from Google with a geofence warrant a Fourth Amendment search?"
GEO_KEEPS = {
    "carpenter-1-p25": "Majority (Roberts): the holding on historical cell-site records, and that Smith and Miller were not extended to them.",
    "carpenter-1-p40": "Majority: says the decision is narrow and names tower dumps and real-time location data as left open. Nearest passage to a geofence request.",
    "carpenter-1-p37": "Majority: the Court has shown special solicitude for location information even in the third-party context.",
    "smith-1-p16": "Majority (Blackmun): the third-party reasoning a Government would rely on for data a company holds.",
    "jones-2-p7": "Concurrence (Sotomayor): questions the premise that information handed to third parties has no protection. A concurrence, not the Court's opinion.",
}
GEO_ANSWER = [
    T("## What the corpus can and cannot say\n\nThe corpus ends with *Carpenter v. United States* (2018) and holds no opinion that decides whether a geofence warrant is a search. The closest passages concern historical cell-site records.\n\n"),
    C("In *Carpenter* the majority held that an individual maintains a legitimate expectation of privacy in the record of his physical movements as captured through cell-site records, and that the location information obtained from the wireless carriers was the product of a search. ",
      ("carpenter-1-p25", 2, 2)),
    C("The Court described its decision as narrow, expressing no view on real-time cell-site location information or \"tower dumps\", a download of information on all the devices that connected to a particular cell site during a particular interval. ",
      ("carpenter-1-p40", 0, 1)),
    C("It also said it did not disturb the application of *Smith* and *Miller*. ",
      ("carpenter-1-p40", 2, 2)),
    C("The third-party reasoning of *Smith v. Maryland* was that a person who voluntarily conveys information to a company assumes the risk that the company will reveal it to the police. ",
      ("smith-1-p16", 1, 2)),
    C("Justice Sotomayor, concurring in *United States v. Jones*, suggested that it may be necessary to reconsider the premise that an individual has no reasonable expectation of privacy in information voluntarily disclosed to third parties. ",
      ("jones-2-p7", 0, 0)),
    T("\n\nWhether the same reasoning reaches a request that names a place and a time rather than a person is not decided by these passages. This is research, not legal advice."),
]


@scenario
def replay_geofence_before_chatrie():
    return Scenario("replay-geofence-before-chatrie", GEO_Q, [
        Round([
            Call("search_meaning", {"query": "whether obtaining a person's location history from a company with a warrant is a search", "max_results": 6}, seed="carpenter-1-p40"),
            Call("search_exact", {"any_of": ["\"tower dumps\"", "\"tower dump\"", "geofence"], "max_results": 4}),
        ]),
        Round([
            Call("search_meaning", {"query": "information handed to a company is still protected when it reveals a person's whereabouts", "max_results": 5}, seed="carpenter-1-p37"),
            Call("search_meaning", {"query": "a person who conveys information to a third party assumes the risk it will be passed to the Government",
                                    "filters": {"decided_to": "1990"}, "max_results": 3}, seed="smith-1-p16"),
            Call("search_meaning", {"query": "reconsidering the rule that information shared with third parties is unprotected", "filters": {"opinion_types": ["concurrence"]},
                                    "max_results": 3}, seed="jones-2-p7"),
        ]),
        Round([Call("keep_passages", {"keep": [K(i, GEO_KEEPS[i]) for i in GEO_KEEPS]})]),
        Round([Call("search_web_updates", {"query": "Supreme Court geofence warrant decision", "start_published_date": "2018-06-23", "end_published_date": "2026-10-24",
                                           "category": "news", "num_results": 5},
                    web=Web(pages=[page("Court issues its decision in Chatrie v. United States", "news.example.test", "chatrie-decision", "2026-06-29", 3900, "Sample Staff"),
                                   page("What the geofence decision means for location history", "review.example.test", "geofence-meaning", "2026-07-01", 4000, "Sample Contributor"),
                                   page("Notes on a geofence ruling", "journal.example.test", "geofence-notes", None, 2700)]))],
              text="The corpus ends at 2018, so checking the web for later decisions."),
        Round([submit(update_findings=[
            {"statement": "A sample news page reports that the Supreme Court issued its decision in Chatrie v. United States, a case about a geofence warrant, on June 29, 2026.",
             "sources": ["web-1-1"]},
            {"statement": "A sample commentary page discusses what that decision means for requests for location history.", "sources": ["web-1-2"]}],
            update_overview="The sample pages report a Supreme Court decision on geofence warrants after the corpus's last case. The corpus does not contain it.")]),
    ], Comp(GEO_ANSWER), label="before_chatrie", expect=answered(band="found"))


# --- P4.7: an out-of-scope reply needs no update check -------------------------------------------------------------------------
@scenario
def out_of_scope_no_update_check():
    note = ("Hello! I research what the Supreme Court has said about the Fourth Amendment and surveillance technology, such as "
            "phone searches, location records and thermal imaging. Ask me a question on one of those and I will look through the opinions.")
    return Scenario("out-of-scope-no-update-check", "hello", [
        Round([Call("submit_answer", {"out_of_scope": True, "note": note})]),
    ], expect={"state": "no_sources", "no_sources_reason": "out_of_scope", "band": "not_run"})


# --- P4.8: the copy guard covers a no-sources reply's note once a page was returned -------------------------------------------
INFOTAINMENT_LEAD = ("Vehicle systems can store call logs, text messages, location history and the contacts of every phone that was ever "
                     "paired with the car, often for years after the phone itself is gone.")


@scenario
def note_refused_copy_guard():
    copied = ("The corpus has no Supreme Court opinion on searching a car's onboard computer. Be aware that vehicle systems can store call "
              "logs, text messages, location history and the contacts of every phone that was ever paired with the car.")
    reworded = ("The corpus has no Supreme Court opinion on searching a car's onboard computer, and the passages found are about phones "
                "and tracking devices rather than data kept in a vehicle. A related question it can answer is how the Court treats "
                "searches of the data on a cell phone seized at an arrest.")
    return Scenario("note-refused-copy-guard", "Do police need a warrant to download the data from my car's infotainment system?", [
        Round([
            Call("search_meaning", {"query": "police downloading stored data from a vehicle's onboard computer", "max_results": 5}, seed="riley-1-p47"),
            Call("search_exact", {"any_of": ["infotainment", "\"onboard computer\"", "\"vehicle data\""], "max_results": 5}),
        ]),
        Round([
            Call("search_web_updates", {"query": "warrant vehicle infotainment data download court", "start_published_date": "2026-06-30",
                                        "category": "news", "num_results": 3},
                 web=Web(pages=[page("What your car remembers about your phone", "explainer.example.test", "car-remembers", "2026-08-14", 3400, "Sample Desk", INFOTAINMENT_LEAD)])),
        ], text="Nothing in the corpus addresses vehicle data directly; checking for later developments."),
        Round([submit(note=copied, update_findings=[])]),            # the note repeats the page's words: refused, withheld (P4.8)
        Round([submit(note=reworded, update_findings=[])]),          # reworded: accepted
    ], expect={"state": "no_sources", "no_sources_reason": "nothing_found", "band": "nothing_relevant"})


# --- P4.6: the note is capped at NOTE_MAX_CHARS ---------------------------------------------------------------------------------
@scenario
def note_too_long():
    long_note = (
        "This question is about contesting a traffic ticket, which is a matter of state traffic law and local court procedure. "
        "The corpus this site researches holds Supreme Court opinions on the Fourth Amendment and surveillance technology: cases "
        "about wiretaps, beepers and GPS trackers, thermal imagers, aerial observation, cell phone searches at an arrest, "
        "historical cell-site location records and geofence warrants. None of those opinions sets out how a ticket from a traffic "
        "camera is contested, what deadlines apply, what evidence a court will accept, or whether a camera's operator must appear. "
        "Those rules differ from state to state and often from city to city, and they are written in statutes, ordinances and court "
        "rules rather than in Supreme Court opinions. The court or agency named on the ticket usually explains how to contest it, "
        "and a local legal aid office or a lawyer who handles traffic cases can say what applies where you live. If you are "
        "interested in the constitutional side of surveillance, a related question this site can research is whether police may "
        "use technology to track a car's movements without a warrant, which the Court addressed in its GPS tracking case."
    )
    short_note = ("This question is about contesting a traffic ticket, which is a matter of state traffic law and local court "
                  "procedure, not the Supreme Court opinions on the Fourth Amendment and surveillance technology that this corpus "
                  "holds. A related question it can research is whether police may track a car's movements without a warrant.")
    skip = "The question is outside the corpus's subject, so there is nothing to check for later developments."
    return Scenario("note-too-long", "How do I contest a speeding ticket from a traffic camera?", [
        Round([Call("submit_answer", {"out_of_scope": True, "note": long_note, "update_skip_reason": skip})]),
        Round([Call("submit_answer", {"out_of_scope": True, "note": short_note, "update_skip_reason": skip})]),
    ], expect={"state": "no_sources", "no_sources_reason": "out_of_scope", "band": "skipped"})


# ===============================================================================================================
# Writing
# ===============================================================================================================
def write_stream(doc: dict) -> Path:
    EVENTS_DIR.mkdir(parents=True, exist_ok=True)
    top = {k: v for k, v in doc.items() if k != "events"}
    head = ",\n".join(f"  {json.dumps(k)}: {jdump(v)}" for k, v in top.items())
    body = ",\n".join("    " + jdump(e) for e in doc["events"])
    path = EVENTS_DIR / f"{doc['slug']}.json"
    path.write_text("{\n" + head + ',\n  "events": [\n' + body + "\n  ]\n}\n", encoding="utf-8")
    return path


RECONNECT_AFTER = 185          # the frontend's reconnect fixture is named for this cut point


def reconnect_document(src: dict) -> dict:
    """The events after a Last-Event-ID: the answered run, picked up in its fifth round or later. The cut stays at
    n = 185 while that is a valid point (round 5 started by event 186, and no tool result separated from its call);
    otherwise it moves to the event before round 5 starts, and the file is renamed."""
    events = src["events"]
    r5 = next(e["n"] for e in events if e["kind"] == "round_started" and e["data"]["round"] == 5)

    def valid(after: int) -> bool:
        calls = {e["data"]["tool_use_id"] for e in events if e["kind"] == "tool_call" and e["n"] <= after}
        split = any(e["kind"] == "tool_result" and e["n"] > after and e["data"]["tool_use_id"] in calls for e in events)
        return r5 <= after + 1 and after < events[-1]["n"] - 1 and not split

    after = RECONNECT_AFTER if valid(RECONNECT_AFTER) else r5 - 1
    doc = {k: v for k, v in src.items() if k != "events"}
    doc["slug"] = f"{src['slug']}-after-n{after}"
    doc["after"] = after
    doc["events"] = [e for e in events if e["n"] > after]
    return doc


def summarise(doc: dict) -> None:
    for e in doc["events"]:
        d = e["data"]
        if e["kind"] == "tool_result":
            print(f"   n={e['n']} t={e['t_ms']} {d['name']} err={d['is_error']} found={d.get('found')} again={d.get('matched_again')} "
                  f"read={d.get('read')} kept={[k['id'] for k in d.get('kept', [])]} refused={[r['id'] for r in d.get('refused', [])]} "
                  f"submit={d.get('submit')} web={d.get('web_status')}")
        elif e["kind"] in ("run_ended", "checks", "update_band", "paused", "resumed", "warning"):
            print(f"   n={e['n']} {e['kind']} t={e['t_ms']} " + jdump({k: v for k, v in d.items() if k not in ("totals", "pages", "searches")})[:400])


# ===============================================================================================================
# HTTP fixtures (contract §5, §5.1): H's real answers, except the Cloud Run and gateway bodies
# ===============================================================================================================
KEEP_HEADERS = {"content-type": "Content-Type", "cache-control": "Cache-Control", "x-accel-buffering": "X-Accel-Buffering"}
HTTP_START = BASE


def write_http(name: str, description: str, method: str, path: str, status: int, headers: dict, body: str) -> None:
    HTTP_DIR.mkdir(parents=True, exist_ok=True)
    d = {"description": description, "method": method, "path": path, "status": status, "headers": headers, "body": body}
    (HTTP_DIR / f"{name}.json").write_text(json.dumps(d, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def shown_headers(h: dict) -> dict:
    return {KEEP_HEADERS[k]: v for k, v in h.items() if k in KEEP_HEADERS}


async def http_app(run_id: str, prepare=None):
    """A fresh app on a fresh MemoryStore at the fixtures' start time; `prepare(store)` fills the store first."""
    clock = FakeClock(HTTP_START)
    store = MemoryStore(clock=lambda: clock.now())
    if prepare is not None:
        await prepare(store, clock)

    async def never(ctx, deps):          # no HTTP fixture starts a run
        raise AssertionError("an HTTP fixture started a run")

    async def factory():
        return AppDeps(store=store, execute_run=never, loop_deps=None, commit="fixture", clock=clock)
    return create_app(factory), store, clock


async def write_all_http(oos: Recorded) -> None:
    run_id = oos.doc["events"][0]["run"]      # the HTTP samples and the stream sample describe the same run
    plain = {"Content-Type": "text/plain; charset=utf-8"}

    async def answer(name, description, method, path, body=None, prepare=None, during=None, keep_body=True):
        app, store, clock = await http_app(run_id, prepare)
        with patched(clock, run_id):
            async with lifespan(app):
                client = Client(app)
                if during is not None:
                    await during(store, client)
                r = await client.request(method, path, body)
        write_http(name, description, method, path, r.status, shown_headers(r.headers), r.text)
        return r

    async def fill_day(store, clock):
        await store.reserve("filler", float(settings.DAILY_CAP_USD.value) - worst_case_usd() + 0.5, clock.now())

    async def fill_month(store, clock):
        for day in range(1, 7):
            await store.reserve(f"filler-{day}", 9.9, datetime(2026, 10, day, 12, tzinfo=CHICAGO))

    async def atlas_down(store, client):
        store.unreachable = True

    await answer("health-ready", "GET /health when loading is complete and live research is open (contract section 5).", "GET", "/health")
    await answer("health-paused-day", "GET /health when today's cap would be exceeded: live research is paused until midnight, Chicago time.",
                 "GET", "/health", prepare=fill_day)
    await answer("health-paused-month", "GET /health when the month's cap would be exceeded, or after the Console spend limit ended a run.",
                 "GET", "/health", prepare=fill_month)
    await answer("health-unknown", "GET /health when Atlas did not answer within the short timeout: both fields are unknown.",
                 "GET", "/health", during=atlas_down)
    write_http("cloud-run-429", "A representative Cloud Run plain-text 429 (no instance free yet). Not a verbatim capture. Any answer that is not our JSON means the server is still starting (contract section 5.1).",
               "GET", "/health", 429, plain, "Rate exceeded.")
    write_http("cloud-run-500", "A representative Cloud Run plain-text 500. Not a verbatim capture.", "GET", "/health", 500, plain, "Internal Server Error")
    write_http("cloud-run-503", "A representative Cloud Run plain-text 503 while an instance starts or has stopped. Not a verbatim capture.",
               "GET", "/health", 503, plain, "Service Unavailable")
    html = ('<!DOCTYPE html>\n<html lang="en">\n<head><meta charset="utf-8"><title>502 Bad Gateway</title></head>\n<body>\n'
            '<h1>Bad Gateway</h1>\n<p>The gateway could not get a valid answer from the service behind it. Please try again in a moment.</p>\n'
            '</body>\n</html>\n')
    write_http("gateway-502", "A representative gateway HTML 502, written generically for this fixture; the real page will differ. The page treats it as still starting.",
               "GET", "/health", 502, {"Content-Type": "text/html; charset=utf-8"}, html)
    q = {"question": oos.doc["question"]}
    await answer("post-runs-201", "POST /runs accepted: a random, unguessable run ID (here the out-of-scope-reply stream's).", "POST", "/runs", q)
    await answer("post-runs-400-question-empty", "POST /runs with an empty or whitespace-only question (refused before any paid call).",
                 "POST", "/runs", {"question": " \t\n "})
    await answer("post-runs-400-question-too-long", "POST /runs with a question over QUESTION_MAX_CHARS.", "POST", "/runs",
                 {"question": "a" * (int(settings.QUESTION_MAX_CHARS.value) + 1)})
    await answer("post-runs-413-body-too-large", "POST /runs with a body over REQUEST_BODY_MAX_BYTES.", "POST", "/runs",
                 json.dumps({"question": "a" * int(settings.REQUEST_BODY_MAX_BYTES.value)}))
    await answer("post-runs-503-paused-day", "POST /runs when the Chicago day's cap would be exceeded (the daily cap). Authoritative over /health.",
                 "POST", "/runs", q, prepare=fill_day)
    await answer("post-runs-503-paused-month", "POST /runs when the month's cap would be exceeded, or while the Anthropic spend-limit flag is set.",
                 "POST", "/runs", q, prepare=fill_month)
    await answer("post-runs-503-atlas-unreachable", "POST /runs when Atlas cannot be reached: fail closed, no paid run.", "POST", "/runs", q,
                 during=atlas_down)
    # the first part of the out-of-scope-reply stream, as sent: through the fourth data frame after a keep-alive line
    frames = [f + "\n\n" for f in oos.raw.split("\n\n") if f]
    ka = next(i for i, f in enumerate(frames) if f.startswith(":"))
    data_seen, cut = 0, len(frames)
    for i, f in enumerate(frames):
        if not f.startswith(":"):
            data_seen += 1
        if i > ka and data_seen >= 4:
            cut = i + 1
            break
    write_http("get-events-200-stream", "GET /runs/{id}/events: the first part of a stream (a keep-alive comment line sits between frames), as H sent the out-of-scope-reply stream. X-Accel-Buffering: no keeps the gateway from buffering it.",
               "GET", f"/runs/{run_id}/events", 200,
               {"Content-Type": "text/event-stream; charset=utf-8", "Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
               "".join(frames[:cut]))
    await answer("get-events-404-run-unknown", "GET /runs/{id}/events for a run that never existed or has expired (the page says the run is no longer stored).",
                 "GET", f"/runs/{run_id}/events")

    async def created(store, client):
        r = await client.post("/runs", q)
        assert r.status == 201 and r.json()["run_id"] == run_id
    await answer("post-alive-204", "POST /runs/{id}/alive: the heartbeat was recorded. No body.", "POST", f"/runs/{run_id}/alive",
                 {"last_event": 0}, during=created)
    await answer("post-alive-404-run-unknown", "POST /runs/{id}/alive for an unknown or expired run.", "POST", f"/runs/{run_id}/alive",
                 {"last_event": 3})


# ===============================================================================================================
async def build(only: str | None) -> list[Recorded]:
    out = []
    for order, fn in enumerate(SCENARIOS):
        sc = fn()
        if only and sc.slug != only and not (only.startswith(sc.slug + "-after-")):
            continue
        try:
            out.append(await record(sc, order))
        except Exception:
            print(f"!! {sc.slug} failed", file=sys.stderr)
            raise
    return out


def main():
    only = sys.argv[sys.argv.index("--only") + 1] if "--only" in sys.argv else None
    recorded = asyncio.run(build(only))
    docs = [(r, r.doc) for r in recorded]
    src = next((r.doc for r in recorded if r.sc.slug == "answered-phone-location-records"), None)
    if src is not None:
        docs.append((None, reconnect_document(src)))
    wanted = {d["slug"] for _, d in docs}
    if not only:
        for f in EVENTS_DIR.glob("*.json"):            # a renamed or removed scenario leaves no stale file behind
            if f.stem not in wanted:
                f.unlink()
    for r, doc in docs:
        path = write_stream(doc)
        end = doc["events"][-1]["data"]
        cost = sum(e["data"]["cost_usd"] for e in doc["events"] if e["kind"] == "paid_call")
        print(f"{path.name}: {len(doc['events'])} events, {path.stat().st_size} bytes, {end['state']}, "
              f"{end['rounds']} rounds, {doc['events'][-1]['t_ms'] / 1000:.1f} s, ${cost:.4f}")
        if r is not None and "--summary" in sys.argv:
            summarise(doc)
    if not only:
        asyncio.run(write_all_http(next(r for r in recorded if r.sc.slug == "out-of-scope-reply")))
        total = sum(p.stat().st_size for p in EVENTS_DIR.glob("*.json"))
        print(f"{len(docs)} event files, {total} bytes; {len(list(HTTP_DIR.glob('*.json')))} http files")


if __name__ == "__main__":
    main()
