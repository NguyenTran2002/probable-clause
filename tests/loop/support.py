"""Test support for part G: a fake RunContext, the dependencies on the real corpus, and a checker that holds every
emitted stream to the event schema (envelope `v: 2` included) and to contract v2.0 §6's order rules: research first,
then the update step and the composition interleaved, each placed by its step. Every web page here is synthetic, on
example.test."""

import copy
import json
import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from jsonschema import Draft202012Validator

from api import settings
from api.checks import check_answer, copy_guard_report
from api.loop import LoopDeps
from api.loop.run import corpus_exemption
from api.loop.streamer import FakeAnthropic, FakeTurn, raw_usage
from api.server.run import estimated_usage   # v1.6: as H emits it
from api.state.prices import failed_attempt_usage, price, price_sources
from api.state.store import MemoryStore
from api.types import STEP_OF_PURPOSE, RunFlags, RunStopped, Usage
from api.web_updates.exa import FakeExaTransport, UpdateSearch, exa_response, exa_result

ROOT = Path(__file__).resolve().parents[2]
SCHEMA = json.loads((ROOT / "contracts" / "events.schema.json").read_text())
VALIDATOR = Draft202012Validator(SCHEMA)
CHICAGO = ZoneInfo(str(settings.TIME_ZONE.value))
SERVICE_OF = {"loop": "anthropic", "update": "anthropic", "composition": "anthropic", "embed": "voyage",
              "rerank": "voyage", "update_search": "exa"}
MODEL_OF = {"loop": str(settings.LOOP_MODEL.value), "update": str(settings.UPDATE_MODEL.value),
            "composition": str(settings.COMPOSITION_MODEL.value), "embed": str(settings.EMBED_MODEL.value),
            "rerank": str(settings.RERANK_MODEL.value), "update_search": "auto"}
PURPOSES = ("loop", "update", "composition")
WITHHELD = "[statement withheld: it repeated a page's words]"
WITHHELD_KEY = re.compile(r"\[field withheld \d+\]")
GUARD_WORDS = int(settings.COPY_GUARD_WORDS.value)


class FakeCtx:
    """A RunContext of our own: numbers events (envelope `v: 2`), prices with E's price(), emits `paid_call` the way H
    does (with the `step` of its purpose, `usage` null for an estimated attempt and its priced tokens in
    `estimated_usage`), keeps §6.2's totals, and its gate can be scripted to raise RunStopped (`stop(service, purpose,
    gate_number)` returns an exception or None)."""

    def __init__(self, *, question="Can police listen to a phone booth call without a warrant?",
                 update_check_available=True, corpus_label="full", stop=None, seconds_left=600.0,
                 run_id="run-loop-test-000001", exa_unavailable=None):
        self.run_id = run_id
        self.question = question
        self.update_check_available = update_check_available
        self.corpus_label = corpus_label
        self.flags = RunFlags(exa_unavailable=exa_unavailable)
        self.events: list[dict] = []
        self.gates: list[tuple[str, str]] = []
        self.paid: list[dict] = []
        self.not_billed: list[tuple[str, str]] = []
        self.stop = stop
        self._seconds_left = seconds_left
        self._t = 0
        self._start = datetime(2026, 10, 24, 22, 0, tzinfo=CHICAGO)
        self._log: list[tuple[str, str, Usage, float]] = []

    async def emit(self, kind: str, data: dict) -> int:
        self._t += 1
        n = len(self.events) + 1
        at = (self._start + timedelta(milliseconds=self._t)).isoformat(timespec="milliseconds")
        self.events.append({"v": 2, "run": self.run_id, "n": n, "t_ms": self._t, "at": at, "kind": kind,
                            "data": copy.deepcopy(data)})
        return n

    async def before_paid_call(self, service, purpose) -> None:
        self.gates.append((service, purpose))
        if self.stop is not None:
            err = self.stop(service, purpose, len(self.gates))
            if err is not None:
                raise err

    async def call_not_billed(self, service, purpose) -> None:
        """Contract v1.4: a call the gate let through that cost nothing (Exa's 402 and 401). Recorded only."""
        self.not_billed.append((service, purpose))

    async def record_usage(self, usage, *, purpose, attempt, max_attempts, outcome, error_kind, duration_ms,
                           raw_usage=None, call_no=None) -> float:
        service = SERVICE_OF[purpose]
        assert usage is None or usage.service == service
        priced = usage if usage is not None else failed_attempt_usage(service, MODEL_OF[purpose], 0)
        cost = round(price(priced), 10)
        if priced.estimated:
            shown = None                    # an estimate is ours, never shown as the provider's usage (H, v1.2)
        elif raw_usage is None and service == "voyage":
            shown = {"total_tokens": usage.input_tokens}
        else:
            shown = raw_usage
        data = {"step": STEP_OF_PURPOSE[purpose]}
        if call_no is not None:
            data["call_no"] = call_no
        data.update({"service": service, "purpose": purpose, "attempt": attempt, "max_attempts": max_attempts,
                     "outcome": outcome, "error_kind": error_kind, "duration_ms": max(0, int(duration_ms)),
                     "usage": shown, "estimated_usage": estimated_usage(priced) if service == "anthropic" else None,
                     "cost_usd": cost, "estimated": bool(priced.estimated)})
        self.paid.append({**data, "_usage": priced, "_raw": copy.deepcopy(raw_usage)})
        self._log.append((service, purpose, priced, cost))
        await self.emit("paid_call", data)
        return cost

    def totals(self) -> dict:
        a = [x for x in self._log if x[0] == "anthropic"]
        return {
            "claude": {
                "calls": len(a),
                "input_tokens": sum(u.input_tokens + u.cache_write_5m_tokens + u.cache_write_1h_tokens
                                    + u.cache_read_tokens for _, _, u, _ in a),
                "cache_read_tokens": sum(u.cache_read_tokens for _, _, u, _ in a),
                "cache_write_tokens": sum(u.cache_write_5m_tokens + u.cache_write_1h_tokens for _, _, u, _ in a),
                "output_tokens": sum(u.output_tokens for _, _, u, _ in a),
                "cost_usd": {p: round(sum(c for _, pp, _, c in a if pp == p), 10) for p in PURPOSES},
            },
            "exa": {"searches": sum(1 for x in self._log if x[0] == "exa"),
                    "cost_usd": round(sum(x[3] for x in self._log if x[0] == "exa"), 10)},
            "voyage": {"requests": sum(1 for x in self._log if x[0] == "voyage"),
                       "cost_usd": round(sum(x[3] for x in self._log if x[0] == "voyage"), 10)},
            "prices": price_sources(),
        }

    def seconds_left(self) -> float:
        return self._seconds_left() if callable(self._seconds_left) else self._seconds_left

    # helpers for assertions
    def kinds(self) -> list[str]:
        return [e["kind"] for e in self.events]

    def of(self, kind: str) -> list[dict]:
        return [e["data"] for e in self.events if e["kind"] == kind]

    def ended(self) -> dict:
        assert self.events[-1]["kind"] == "run_ended"
        return self.events[-1]["data"]

    def results(self, name: str | None = None) -> list[dict]:
        return [d for d in self.of("tool_result") if name is None or d["name"] == name]


def stop_on(purpose: str, reason: str, at: int = 1):
    """A gate that raises RunStopped(reason) at the `at`-th gate for `purpose`."""
    seen = {"n": 0}

    def stop(service, p, n):
        if p == purpose:
            seen["n"] += 1
            if seen["n"] == at:
                return RunStopped(reason)
        return None
    return stop


@dataclass
class World:
    corpus: object
    keyword: object
    meaning: object


def make_deps(world: World, script=(), *, update=(), comp=(), exa=(), voyage=None, store=None,
              tool_schema=None) -> tuple[LoopDeps, dict]:
    """The dependencies on the real corpus, with one Claude script per step (contract v2.0 §12): `script` for
    research, `update` for the update step, `comp` for the composition."""
    from api.search.voyage import FakeVoyageClient
    anthropic = FakeAnthropic(list(script), update=list(update), composition=list(comp))
    transport = FakeExaTransport(list(exa), tool_schema=tool_schema if tool_schema is not None else
                                 {"inputSchema": {"properties": {}}})
    store = store or MemoryStore()
    updates = UpdateSearch(transport, store)
    voyage = voyage or FakeVoyageClient()
    deps = LoopDeps(corpus=world.corpus, keyword=world.keyword, meaning=world.meaning, voyage=voyage,
                    updates=updates, anthropic=anthropic)
    return deps, {"anthropic": anthropic, "exa": transport, "store": store, "voyage": voyage}


# ---------- scripted turns ----------

_ids = {"n": 0}


def tu(name: str, **inp) -> dict:
    _ids["n"] += 1
    return {"type": "tool_use", "id": f"toolu_test_{_ids['n']:05d}", "name": name, "input": inp}


def turn(*uses, text: str | None = None, thinking: bool = True, stop_reason: str = "tool_use", usage=None,
         **kw) -> FakeTurn:
    content = []
    if thinking:
        content.append({"type": "thinking", "thinking": "", "signature": f"sig-{_ids['n']}"})
    if text:
        content.append({"type": "text", "text": text})
    content.extend(uses)
    return FakeTurn(content=content, stop_reason=stop_reason, usage=usage, **kw)


def loop_usage(n: int, *, first: bool = False) -> dict:
    """A plausible loop usage: a 1-hour write on the first call, cache reads after."""
    return raw_usage(50, w1=12_000, output=400) if first else raw_usage(40, w5=2_000, read=12_000 + 1_000 * n, output=500)


def cite_block(text: str, corpus, documents: list[str], pid: str, first: int, last: int) -> dict:
    """An answer block citing sentences first..last (inclusive) of pid, as the API would send it (end exclusive)."""
    p = corpus.passages[pid]
    cited = p.text[p.sentences[first][0]:p.sentences[last][1]]
    return {"type": "text", "text": text, "citations": [{
        "type": "content_block_location", "cited_text": cited, "document_index": documents.index(pid),
        "document_title": "t", "start_block_index": first, "end_block_index": last + 1}]}


def composition(*blocks, stop_reason="end_turn", usage=None, **kw) -> FakeTurn:
    content = [{"type": "thinking", "thinking": "", "signature": "sig-comp"}] + list(blocks)
    return FakeTurn(content=content, stop_reason=stop_reason,
                    usage=usage or raw_usage(9_000, output=1_500), **kw)


def web_reply(*pages, cost=0.007) -> dict:
    """pages: (slug, title, published, text)."""
    return exa_response([exa_result(url=f"https://news.example.test/{slug}", title=f"[Sample] {title}",
                                    published=published, text=text) for slug, title, published, text in pages],
                        cost_total=cost)


def update_usage(n: int = 0) -> dict:
    """A plausible update-step usage: research's conversation read from the cache, the new turn written."""
    return raw_usage(30, w5=1_500 + 500 * n, read=20_000 + 2_000 * n, output=300)


def skip_update(reason: str = "No later development could bear on what this question asks.", *, usage=None,
                **kw) -> FakeTurn:
    """An update turn that skips the check."""
    return turn(tu("submit_update", update_skip_reason=reason), usage=usage or update_usage(), **kw)


# ---------- the stream checker ----------

STEPPED = ("round_started", "tool_call", "tool_result", "paid_call", "api_fragment")


def names_in(e: dict) -> list[str]:
    d = e["data"]
    if e["kind"] == "tool_result":
        return list(d.get("found", [])) + list(d.get("matched_again", [])) + list(d.get("read", [])) + \
            [k["id"] for k in d.get("kept", [])]
    if e["kind"] in ("composition_started",):
        return list(d["documents"])
    if e["kind"] == "update_started":
        return list(d["kept"])
    if e["kind"] == "answer_block":
        return [c["passage_id"] for c in d["citations"]]
    if e["kind"] == "api_fragment":
        return [d["passage_id"]]
    return []


def step_of(e: dict) -> str | None:
    """The step an event belongs to (§6): its `step` field, or the step it opens or summarises."""
    if e["kind"] in STEPPED:
        return e["data"]["step"]
    if e["kind"] in ("update_started", "update_ended"):
        return "update"
    if e["kind"] in ("composition_started", "answer_block", "checks"):
        return "composition"
    return None


def check_stream(events: list[dict], corpus, *, page_texts: list[str] = ()) -> None:
    """Every event validates (P0.3), envelope `v: 2` included, and contract v2.0 §6's order rules hold."""
    for e in events:
        VALIDATOR.validate(e)
    assert [e["n"] for e in events] == list(range(1, len(events) + 1))
    assert events[0]["kind"] == "run_started"
    kinds = [e["kind"] for e in events]
    assert kinds.count("run_ended") == 1 and kinds[-1] == "run_ended"

    # tool_call before tool_result, one result per call, in the same step
    calls, results = {}, set()
    for e in events:
        d = e["data"]
        if e["kind"] == "tool_call":
            assert d["tool_use_id"] not in calls
            calls[d["tool_use_id"]] = (d["name"], d["step"])
        elif e["kind"] == "tool_result":
            assert calls.get(d["tool_use_id"]) == (d["name"], d["step"]), f"result without its call at n={e['n']}"
            assert d["tool_use_id"] not in results
            results.add(d["tool_use_id"])
            if d.get("wrong_step"):
                assert d["is_error"] is True and "search_no" not in d
    assert results == set(calls), "every tool call has a result"

    # a passage's event before anything naming it
    seen = set()
    for e in events:
        if e["kind"] == "passage":
            assert e["data"]["id"] not in seen
            seen.add(e["data"]["id"])
            p = corpus.passages[e["data"]["id"]]
            assert e["data"]["text"] == p.text and e["data"]["sentences"] == [[a, b] for a, b in p.sentences]
        for pid in names_in(e):
            assert pid in seen, f"{pid} named at n={e['n']} ({e['kind']}) before its passage event"

    # paid calls carry the step of their purpose (§2's STEP_OF_PURPOSE)
    for e in events:
        if e["kind"] == "paid_call":
            assert e["data"]["step"] == STEP_OF_PURPOSE[e["data"]["purpose"]]

    # fragments and paid calls (§6); the update step emits none
    paid = {}
    for i, e in enumerate(events):
        if e["kind"] == "paid_call" and "call_no" in e["data"]:
            paid.setdefault(e["data"]["call_no"], []).append(i)
    for i, e in enumerate(events):
        if e["kind"] != "api_fragment":
            continue
        d = e["data"]
        assert d["step"] in ("research", "composition")
        assert d["call_no"] in paid, f"a fragment for call {d['call_no']}, which made no paid call"
        assert events[paid[d["call_no"]][0]]["data"]["step"] == d["step"]
        if d["role"] == "request":
            assert i < min(paid[d["call_no"]]), f"request fragment after its paid_call, n={e['n']}"
        else:
            assert i > max(paid[d["call_no"]]), f"response fragment before its paid_call, n={e['n']}"
        assert re.fullmatch(r"(messages\[\d+\]\.)?content\[\d+\](\.content\[\d+\])?", d["path"]), d["path"]
        assert (d["role"] == "request") == d["path"].startswith("messages[")
    nos = sorted(paid)
    assert nos == list(range(1, len(nos) + 1)), "Claude calls numbered from 1 without gaps"
    for c, idxs in paid.items():
        attempts = [events[i]["data"] for i in idxs]
        assert len({(a["step"], a["purpose"]) for a in attempts}) == 1, f"call {c} spans steps"
        assert [a["attempt"] for a in attempts] == list(range(1, len(attempts) + 1))
        assert [a["outcome"] for a in attempts][:-1] == ["retrying"] * (len(attempts) - 1)

    # research's fragments point at what was sent and returned (T4.3 item 7); research's call k is its round k
    comp = next((e["data"] for e in events if e["kind"] == "composition_started"), None)
    rounds, current = {}, 0
    for e in events:
        if e["kind"] in ("round_started", "tool_call", "tool_result") and e["data"]["step"] != "research":
            continue
        if e["kind"] == "round_started":
            current = e["data"]["round"]
        elif e["kind"] == "tool_call":
            rounds.setdefault(current, {"calls": [], "results": {}})["calls"].append(e["data"])
        elif e["kind"] == "tool_result":
            rounds[current]["results"][e["data"]["tool_use_id"]] = e["data"]
    for e in events:
        d = e["data"]
        if e["kind"] != "api_fragment" or d["step"] != "research":
            continue
        if d["role"] == "request":
            m = re.fullmatch(r"messages\[(\d+)\]\.content\[(\d+)\]\.content\[(\d+)\]", d["path"])
            assert m and int(m.group(1)) == 2 * (d["call_no"] - 1), d["path"]
            prev = rounds[d["call_no"] - 1]
            # the tool_result index is the tool_use's place in the response; a call to an unknown tool has no events,
            # so fall back to finding the block among the round's results
            ti = int(m.group(2))
            call = prev["calls"][ti] if ti < len(prev["calls"]) else None
            texts = [prev["results"][call["tool_use_id"]]["content"]] if call else []
            if not any(d["json"]["text"] in t for t in texts):
                texts = [r["content"] for r in prev["results"].values()]
            assert d["json"]["type"] == "text" and any(d["json"]["text"] in t for t in texts)
            assert f"[{d['passage_id']}]" in d["json"]["text"]
        else:
            block = d["json"]
            assert block["type"] == "tool_use"
            call = next(c for c in rounds[d["call_no"]]["calls"] if c["tool_use_id"] == block["id"])
            res = rounds[d["call_no"]]["results"][block["id"]]
            ids = set(res.get("found", [])) | set(res.get("matched_again", [])) | set(res.get("read", [])) | \
                {k["id"] for k in res.get("kept", [])}
            assert d["passage_id"] in ids
            assert block["input"] == call["input"]

    # composition documents and citations are exact slices of our passages
    passages = {e["data"]["id"]: e["data"] for e in events if e["kind"] == "passage"}
    frags = {(e["data"]["passage_id"], e["data"]["call_no"], e["data"]["role"], e["data"]["path"]): e["data"]["json"]
             for e in events if e["kind"] == "api_fragment"}
    if comp:
        assert events[paid[comp["call_no"]][0]]["data"]["purpose"] == "composition"
        for i, pid in enumerate(comp["documents"]):
            doc = frags[(pid, comp["call_no"], "request", f"messages[0].content[{i}]")]
            p = passages[pid]
            assert doc["type"] == "document" and doc["source"]["type"] == "content" and doc["context"]
            assert [b["text"] for b in doc["source"]["content"]] == [p["text"][a:b] for a, b in p["sentences"]]
            assert doc["citations"] == {"enabled": True}
    blocks = [e["data"] for e in events if e["kind"] == "answer_block"]
    assert [b["index"] for b in blocks] == list(range(len(blocks)))
    for b in blocks:
        for c in b["citations"]:
            p = passages[c["passage_id"]]
            assert 0 <= c["first_sentence"] <= c["last_sentence"] < len(p["sentences"])
            a, z = p["sentences"][c["first_sentence"]][0], p["sentences"][c["last_sentence"]][1]
            assert c["cited_text"] == p["text"][a:z]
            assert c["call_no"] == comp["call_no"]
            frag = frags[(c["passage_id"], c["call_no"], "response", c["path"])]
            assert frag["text"] == b["text"]
            di = comp["documents"].index(c["passage_id"])
            assert any(x["type"] == "content_block_location" and x["document_index"] == di
                       and x["start_block_index"] == c["first_sentence"]
                       and x["end_block_index"] == c["last_sentence"] + 1 for x in frag["citations"])

    # the steps: research first, then the update step and the composition, each placed by its step (§6)
    research_last = max((i for i, e in enumerate(events) if step_of(e) == "research"), default=0)
    for i, e in enumerate(events):
        if step_of(e) in ("update", "composition"):
            assert i > research_last, f"{e['kind']} at n={e['n']} before research ended"
    bands = [i for i, k in enumerate(kinds) if k == "update_band"]
    assert len(bands) == 1, "one update_band"
    band = bands[0]
    if "update_started" in kinds:
        start, end = kinds.index("update_started"), kinds.index("update_ended")
        assert kinds.count("update_started") == kinds.count("update_ended") == 1
        assert band == end + 1, "update_band right after update_ended"
        for i, e in enumerate(events):
            if step_of(e) == "update" and e["kind"] not in ("update_started", "update_ended"):
                assert start < i < end, f"update-step {e['kind']} at n={e['n']} outside update_started..update_ended"
        ended = events[end]["data"]
        assert ended["rounds"] == sum(1 for e in events if e["kind"] == "round_started"
                                      and e["data"]["step"] == "update")
        assert ended["searches"] == sum(1 for e in events if e["kind"] == "tool_result" and "search_no" in e["data"])
    else:
        assert "update_ended" not in kinds
        assert not [e for e in events if step_of(e) == "update"], "update-step events with no update step"
        assert band > research_last and ("composition_started" not in kinds or band < kinds.index("composition_started"))

    # totals are the sum of the paid calls
    ended = events[-1]["data"]
    assert isinstance(ended["stop_kinds"], list)                       # v1.4: on every run_ended
    assert ended["stop_kind"] is None or ended["stop_kind"] in ended["stop_kinds"]
    t = ended["totals"]
    claude = [e["data"] for e in events if e["kind"] == "paid_call" and e["data"]["service"] == "anthropic"]
    assert t["claude"]["calls"] == len(claude)
    cost = {p: 0.0 for p in PURPOSES}
    for p in claude:
        cost[p["purpose"]] += p["cost_usd"]
        assert (p["outcome"] == "ok") == (p["error_kind"] is None)
        if p["usage"] is None:
            assert p["estimated"] is True and p["outcome"] in ("retrying", "failed") and p["estimated_usage"]
        if p["outcome"] == "ok":
            assert p["usage"] is not None and p["estimated"] is False
    for purpose in PURPOSES:
        assert abs(t["claude"]["cost_usd"][purpose] - cost[purpose]) < 1e-8
    assert t["prices"] == price_sources()
    assert ended["rounds"] == sum(1 for e in events if e["kind"] == "round_started" and e["data"]["step"] == "research")
    assert ended["answer_chars"] == sum(len(b["text"]) for b in blocks)

    # the checks event is F's check of the stream's own blocks
    checks = [e["data"] for e in events if e["kind"] == "checks"]
    if blocks:
        assert len(checks) == 1
        r = check_answer([b["text"] for b in blocks], [passages[i]["text"] for i in comp["documents"]], corpus.manifest)
        assert checks[0] == json.loads(json.dumps(r, default=lambda o: o.__dict__))
        assert kinds.index("checks") > max(i for i, k in enumerate(kinds) if k == "answer_block")
    else:
        assert checks == []

    # warnings once each
    codes = [e["data"]["code"] for e in events if e["kind"] == "warning"]
    assert len(codes) == len(set(codes))

    # no web page text anywhere (T2.2, P1.7): no given text as a substring, and no string of any event, keys
    # included, repeating COPY_GUARD_WORDS or more consecutive words of a page, by F's own guard and its corpus
    # exemption (§4.G.2); the withheld markers are ours
    whole = json.dumps(events, ensure_ascii=False)
    for text in page_texts:
        assert text not in whole, "a web page's text reached an event"
    if page_texts:
        texts = [t for e in events for t in all_texts(e) if t != WITHHELD and not WITHHELD_KEY.fullmatch(t)]
        report = copy_guard_report(texts, None, {f"page-{i}": t for i, t in enumerate(page_texts)}, GUARD_WORDS,
                                   exempt=corpus_exemption(corpus))
        assert not report.flagged_statements, \
            f"{len(report.flagged_statements)} event string(s) repeat a page's words: " + \
            "; ".join(repr(texts[i][:60]) for i in sorted(report.flagged_statements))


def all_texts(obj) -> list[str]:
    """Every string in an event, dict keys included."""
    out: list[str] = []

    def walk(o) -> None:
        if isinstance(o, str):
            out.append(o)
        elif isinstance(o, dict):
            for k, v in o.items():
                walk(k)
                walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)
    walk(obj)
    return out


def exa_page_texts(exa) -> list[str]:
    """The full texts of the pages a test scripts for Exa (dict replies only)."""
    return [r["text"] for item in exa if isinstance(item, dict) for r in item.get("results", [])
            if isinstance(r, dict) and isinstance(r.get("text"), str)]


async def run_loop(world: World, script=(), *, update=(), comp=(), ctx: FakeCtx | None = None, exa=(), page_texts=(),
                   check=True, **kw):
    """One full run against the fakes, a Claude script per step; the stream is checked unless `check=False`, against
    the given texts and every page scripted for Exa."""
    from api.loop import execute_run
    ctx = ctx or FakeCtx()
    exa = list(exa)
    deps, fakes = make_deps(world, script, update=update, comp=comp, exa=exa, **kw)
    await execute_run(ctx, deps)
    if check:
        check_stream(ctx.events, world.corpus, page_texts=[*page_texts, *exa_page_texts(exa)])
    assert not fakes["anthropic"].left(), f"scripted Claude turns were left unused: {fakes['anthropic'].left()}"
    return ctx, fakes
