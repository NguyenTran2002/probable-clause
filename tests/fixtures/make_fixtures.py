#!/usr/bin/env python3
"""Deterministic generator for the frontend mock's fixtures (contract §12, P0.3).

    .venv/bin/python tests/fixtures/make_fixtures.py

Writes tests/fixtures/events/*.json (one run's events each, in the replay format of contract §11.2) and
tests/fixtures/http/*.json (contract §5). Re-running it writes identical files. It uses no network and no keys.

Wherever the merged code can produce a value, this script calls it: passages, sentence offsets and loop text from
`Corpus`; keyword results from `KeywordIndex`; meaning-search order from the committed vectors file; the checks
event from `check_answer`; the update band's lines from `format_for_events`, `params_as_dict` and `fixed_settings`;
every price from `price`; the prices object from `price_sources`; every figure from `api/settings.py`.

What is NOT real, and the README says so:
  - the loop's tool-result text follows T1.6's shape (a header, the text, attached footnotes, a "matched again"
    line) but builder G will write the real format;
  - meaning-search order is the nearest neighbours of a stand-in passage in the real vectors file, not a live
    Voyage query;
  - web pages are synthetic samples on example.test;
  - token counts are estimates (the corpus's own characters-per-token ratio); latencies are invented;
  - the answers are written by hand for each question, with citations checked against the passages' sentences.
"""

import hashlib
import json
import random
import re
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import numpy as np  # noqa: E402

from api import settings  # noqa: E402
from api.checks import check_answer, check_update_findings, copy_guard_report  # noqa: E402
from api.corpus.filters import excluded_by_none_of, matches, parse_filters  # noqa: E402
from api.corpus.keyword import KeywordIndex  # noqa: E402
from api.corpus.store import Corpus  # noqa: E402
from api.errors import ToolInputError  # noqa: E402
from api.search.meaning import NOT_RERANKED_NOTE, UNAVAILABLE_NOTE, MeaningIndex  # noqa: E402
from api.state.prices import failed_attempt_usage, price, price_sources  # noqa: E402
from api.types import Usage, WebPage  # noqa: E402
from api.web_updates import (  # noqa: E402
    WebSearchOutcome,
    fixed_settings,
    format_for_events,
    params_as_dict,
    parse_params,
)

EVENTS_DIR = ROOT / "tests" / "fixtures" / "events"
HTTP_DIR = ROOT / "tests" / "fixtures" / "http"
CHICAGO = ZoneInfo(str(settings.TIME_ZONE.value))
# Synthetic recording times: the fixtures are not real runs. Each stream starts a few minutes after the last.
BASE = datetime(2026, 10, 24, 22, 0, 0, tzinfo=CHICAGO)

LOOP_MODEL = str(settings.LOOP_MODEL.value)
COMP_MODEL = str(settings.COMPOSITION_MODEL.value)
MAX_ROUNDS = int(settings.MAX_ROUNDS.value)
UPDATE_SEARCHES = int(settings.UPDATE_SEARCHES_PER_RUN.value)
LOOP_ATTEMPTS = int(settings.ANTHROPIC_RETRIES.value) + 1
VOYAGE_ATTEMPTS = int(settings.VOYAGE_RETRIES.value) + 1
PREFIX_TOKENS = int(settings.FIXED_PREFIX_TOKENS_ESTIMATE.value)
VOYAGE_WAITS = settings.waits(settings.VOYAGE_RETRY_WAITS_S)
ANTHROPIC_WAITS = settings.waits(settings.ANTHROPIC_RETRY_WAITS_S)
WITHHELD = "[statement withheld: it repeated a page's words]"

REJ = json.loads((ROOT / "api" / "prompts" / "rejections.json").read_text(encoding="utf-8"))
LMSG = json.loads((ROOT / "api" / "prompts" / "loop_messages.json").read_text(encoding="utf-8"))

# ---------------------------------------------------------------------------------------------------------------
# The corpora (full, and the recording-only one that ends before Chatrie, T5.6) and their indexes
# ---------------------------------------------------------------------------------------------------------------
CORPORA = {"full": Corpus.load(ROOT), "before_chatrie": Corpus.load(ROOT, exclude=("chatrie",))}
KEYWORD = {k: KeywordIndex(c) for k, c in CORPORA.items()}
MEANING = {k: MeaningIndex.load(ROOT / "data" / "vectors", c.passages.values()) for k, c in CORPORA.items()}
MEANING_ROW = {k: {p.id: i for i, p in enumerate(m.passages)} for k, m in MEANING.items()}

# Tokens: the manifest's own token count (claude-sonnet-5-5's tokenizer) over the paragraphs' characters.
_FULL = CORPORA["full"]
CHARS_PER_TOKEN = sum(len(p.text) for p in _FULL.passages.values() if p.kind == "paragraph") / _FULL.manifest["core_tokens"]


def tok(s: str) -> int:
    return max(1, round(len(s) / CHARS_PER_TOKEN))


def fill(template: str, **fields) -> str:
    """`{{NAME}}` from api/settings.py, then `<field>` from the call."""
    out = re.sub(r"\{\{([A-Z_]+)\}\}", lambda m: str(getattr(settings, m.group(1)).value), template)
    for k, v in fields.items():
        out = out.replace(f"<{k}>", str(v))
    return out


def jdump(o) -> str:
    return json.dumps(o, ensure_ascii=False, separators=(",", ":"))


def stable_id(*parts, length=22, prefix="") -> str:
    h = hashlib.sha256("|".join(map(str, parts)).encode()).digest()
    alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789"
    return prefix + "".join(alphabet[b % 62] for b in h[:length])


def passage_data(p) -> dict:
    """The §6.1 passage event, from the real `Passage`."""
    return {
        "id": p.id, "kind": p.kind, "case_key": p.case_key, "case_name": p.case_name, "citation": p.citation,
        "decided": p.decided, "slip_opinion": p.slip_opinion, "opinion_id": p.opinion_id, "opinion_type": p.opinion_type,
        "authors": list(p.authors), "joined_by": list(p.joined_by), "joined_by_source": p.joined_by_source,
        "section": p.section, "page_start": p.page_start, "page_end": p.page_end, "paragraph_kind": p.paragraph_kind,
        "footnote_label": p.footnote_label, "footnotes": list(p.footnotes), "cited_by": list(p.cited_by),
        "text": p.text, "sentences": [[a, b] for a, b in p.sentences],
    }


def passage_block(corpus: Corpus, pid: str, requested: bool = False) -> str:
    """One passage as the loop's tool result shows it: header, loop text, attached footnotes (T1.6).
    Approximate: builder G writes the real format."""
    p = corpus.passages[pid]
    who = ", ".join(p.authors) if p.authors else "per curiam"
    pages = str(p.page_start) if p.page_start == p.page_end else f"{p.page_start}-{p.page_end}"
    where = f"slip page {pages}" if p.slip_opinion else f"page {pages}"
    section = f"section {p.section}" if p.section else "no section label"
    if p.kind == "paragraph":
        pos = f"paragraph {p.position} of {p.of}"
    else:
        pos = f"footnote {p.footnote_label} (number {p.position} of {p.of}), cited in {p.cited_by[0]}"
    lines = [f"[{p.id}] {p.case_name}, {p.citation}, decided {p.decided}",
             f"{p.opinion_type} · {who} · {where} · {section} · {pos}"]
    if requested:
        lines.append("(the passage you asked for)")
    lines += ["", corpus.loop_text(pid)]
    notes = corpus.attached_footnotes(pid)
    if notes:
        lines += ["", "Footnotes cited in this passage:"]
        lines += [f"[{f.id}] n. {f.footnote_label}: {f.text}" for f in notes]
    return "\n".join(lines)


def doc_title(p) -> str:
    who = ", ".join(p.authors) if p.authors else "per curiam"
    return f"{p.case_name} ({p.decided[:4]}), {who}, {p.opinion_type}"


def doc_context(p, reason: str) -> str:
    who = ", ".join(p.authors) if p.authors else "per curiam"
    joined = ", ".join(p.joined_by) if p.joined_by else ("not printed" if p.joined_by_source == "not printed" else "no one")
    pages = str(p.page_start) if p.page_start == p.page_end else f"{p.page_start}-{p.page_end}"
    sec = p.section or "none"
    return (f"ID {p.id} · {p.case_name}, {p.citation} · decided {p.decided} · {p.opinion_type} · {who} · "
            f"joined by: {joined} · section: {sec} · pages {pages} · Why it was kept: {reason}")


def doc_block(p, reason: str) -> dict:
    return {"type": "document",
            "source": {"type": "content", "content": [{"type": "text", "text": p.text[a:b]} for a, b in p.sentences]},
            "title": doc_title(p), "context": doc_context(p, reason), "citations": {"enabled": True}}


def tool_id(slug: str, n: int) -> str:
    return stable_id(slug, "tool", n, length=24, prefix="toolu_01")


# ---------------------------------------------------------------------------------------------------------------
# One loop call, one tool, one web page: small records the scenarios fill in
# ---------------------------------------------------------------------------------------------------------------
@dataclass
class Call:
    name: str
    input: dict
    seed: str | None = None         # search_meaning: the stand-in passage whose vector plays the query
    voyage: dict | None = None      # scripted Voyage failures: {"embed": [kinds...], "rerank": [kinds...]}; [] = ok first time
    web: "Web | None" = None
    id: str = ""
    index: int = 0                  # position in the assistant message's content


@dataclass
class Web:
    kind: str = "ok"                # ok | refused_by_exa | failed | unavailable
    pages: list = field(default_factory=list)      # dicts: title, domain, slug, published, author, chars, truncated
    repeats: list = field(default_factory=list)    # IDs of pages an earlier search returned
    exa_message: str | None = None
    reason: str | None = None       # unavailable: no_credit | key_refused
    ms: int | None = None


@dataclass
class Result:
    blocks: list
    is_error: bool = False
    extra: dict = field(default_factory=dict)
    block_pids: list = field(default_factory=list)   # (passage id, index into blocks) for request fragments
    resp_pids: list = field(default_factory=list)    # passages the tool_use block gets a response fragment for


def page_text(slug: str, n: int, lead: str = "") -> str:
    """Synthetic filler for a sample page. Only its length ever reaches an event (and the copy guard reads it)."""
    s = f"Sample page {slug}. This is invented filler text standing in for a web page. "
    return (lead + " " + s * (n // len(s) + 1))[:n]


# ---------------------------------------------------------------------------------------------------------------
# A simulated run
# ---------------------------------------------------------------------------------------------------------------
class Sim:
    def __init__(self, slug: str, question: str, order: int, *, label: str = "full", update_available: bool = True,
                 update_unavailable_reason: str = "no_credit"):
        self.slug, self.question, self.label = slug, question, label
        self.corpus = CORPORA[label]
        self.kw, self.mi, self.row = KEYWORD[label], MEANING[label], MEANING_ROW[label]
        self.rng = random.Random(slug)
        self.run = stable_id(slug, "run")
        self.start = BASE + timedelta(minutes=7 * order)
        self.events: list[dict] = []
        self.t = 0
        self.call_no = 0
        self.round_no = 0
        self.tool_seq = 0
        self.messages: list[dict] = []
        self.prev_conv = 0
        self.seen: set[str] = set()
        self.emitted: set[str] = set()
        self.kept: dict[str, dict] = {}          # id -> {"reason", "round"} in first-kept order
        self.log: list[dict] = []                # every paid call: service, purpose, usage, cost
        self.pending: list[tuple] = []           # (pid, user message index, tool_result index, block index, block)
        self.pages: dict[str, WebPage] = {}      # every page returned in the run
        self.page_order: list[str] = []
        self.band_searches: list[dict] = []
        self.counted = 0                         # update searches that count toward the limit
        self.unavailable = None if update_available else update_unavailable_reason
        self.update_available = update_available
        self.corpus_searched = False
        self.reminded = False
        self.warned: set[str] = set()
        self.submit: dict | None = None          # the accepted submit's input
        self.declined = False
        self.answer_texts: list[str] = []
        self.kept_at_compose: list[str] = []
        self.ended = False
        self.n_voyage = 0

    # -- events ----------------------------------------------------------------------------------------------
    def wait(self, ms: float) -> None:
        self.t += int(round(ms))

    def emit(self, kind: str, data: dict, adv: int = 1) -> dict:
        self.t += adv
        at = (self.start + timedelta(milliseconds=self.t)).isoformat(timespec="milliseconds")
        e = {"v": 1, "run": self.run, "n": len(self.events) + 1, "t_ms": self.t, "at": at, "kind": kind, "data": data}
        self.events.append(e)
        return e

    def ensure_passage(self, pid: str) -> None:
        if pid not in self.emitted:
            self.emitted.add(pid)
            self.emit("passage", passage_data(self.corpus.passages[pid]), adv=self.rng.choice((1, 2, 2, 3)))

    # -- the run's top and bottom ------------------------------------------------------------------------------
    def run_started(self) -> None:
        cov = self.corpus.coverage
        self.emit("run_started", {
            "question": self.question,
            "limits": {"rounds": MAX_ROUNDS, "input_tokens": int(settings.RUN_INPUT_TOKENS.value),
                       "output_tokens": int(settings.RUN_OUTPUT_TOKENS.value), "update_searches": UPDATE_SEARCHES,
                       "deadline_s": int(settings.RUN_DEADLINE_S.value)},
            "coverage": {k: cov[k] for k in ("latest_decision_full_pull", "latest_decision_in_corpus", "ingested")},
            "update_check_available": self.update_available,
            "models": {"loop": LOOP_MODEL, "composition": COMP_MODEL},
            "corpus_label": self.label})

    def status_line(self, round_no: int) -> str:
        if self.unavailable:
            upd = LMSG["status_update"]["unavailable"]
        elif self.counted:
            upd = fill(LMSG["status_update"]["some_run"], n=self.counted)
        else:
            upd = LMSG["status_update"]["not_run"]
        return fill(LMSG["status_line"], round=round_no, kept=len(self.kept), update_status=upd)

    def first_message(self) -> dict:
        blocks = [{"type": "text", "text": fill(LMSG["first_message"], question=self.question)}]
        if not self.update_available:
            why = fill(LMSG["update_unavailable_reason"][self.unavailable or "no_credit"])
            blocks.append({"type": "text", "text": fill(LMSG["update_check_unavailable"], reason=why)})
        blocks.append({"type": "text", "text": self.status_line(1)})
        return {"role": "user", "content": blocks}

    # -- tokens ------------------------------------------------------------------------------------------------
    @staticmethod
    def msg_tokens(m: dict) -> int:
        n = 0
        for b in m["content"]:
            if b["type"] == "text":
                n += tok(b["text"])
            elif b["type"] == "tool_use":
                n += tok(jdump(b["input"])) + 12
            elif b["type"] == "tool_result":
                n += sum(tok(x["text"]) for x in b["content"]) + 8
        return n

    def conv_tokens(self) -> int:
        return sum(self.msg_tokens(m) for m in self.messages)

    # -- money -------------------------------------------------------------------------------------------------
    def paid(self, service: str, purpose: str, *, attempt: int, max_attempts: int, outcome: str, error_kind,
             duration_ms: int, usage: Usage, raw, call_no: int | None = None, adv: int = 1) -> float:
        cost = round(price(usage), 10)
        data = {}
        if call_no is not None:
            data["call_no"] = call_no
        data.update({"service": service, "purpose": purpose, "attempt": attempt, "max_attempts": max_attempts,
                     "outcome": outcome, "error_kind": error_kind, "duration_ms": int(duration_ms), "usage": raw,
                     "cost_usd": cost, "estimated": bool(usage.estimated)})
        self.emit("paid_call", data, adv=adv)
        self.log.append({"service": service, "purpose": purpose, "usage": usage, "cost": cost, "outcome": outcome})
        return cost

    def claude_usage(self, model: str, raw: dict) -> Usage:
        cc = raw.get("cache_creation", {})
        return Usage(service="anthropic", model=model, input_tokens=raw["input_tokens"],
                     cache_write_5m_tokens=cc.get("ephemeral_5m_input_tokens", 0),
                     cache_write_1h_tokens=cc.get("ephemeral_1h_input_tokens", 0),
                     cache_read_tokens=raw.get("cache_read_input_tokens", 0), output_tokens=raw["output_tokens"])

    @staticmethod
    def raw_usage(input_tokens: int, w5: int, w1: int, read: int, out: int) -> dict:
        return {"input_tokens": input_tokens, "cache_creation_input_tokens": w5 + w1, "cache_read_input_tokens": read,
                "cache_creation": {"ephemeral_5m_input_tokens": w5, "ephemeral_1h_input_tokens": w1},
                "output_tokens": out, "service_tier": "standard"}

    def totals(self) -> dict:
        a = [x for x in self.log if x["service"] == "anthropic"]
        u = lambda x: x["usage"]  # noqa: E731
        return {
            "claude": {
                "calls": len(a),
                "input_tokens": sum(u(x).input_tokens + u(x).cache_write_5m_tokens + u(x).cache_write_1h_tokens
                                    + u(x).cache_read_tokens for x in a),
                "cache_read_tokens": sum(u(x).cache_read_tokens for x in a),
                "cache_write_tokens": sum(u(x).cache_write_5m_tokens + u(x).cache_write_1h_tokens for x in a),
                "output_tokens": sum(u(x).output_tokens for x in a),
                "cost_usd": {p: round(sum(x["cost"] for x in a if x["purpose"] == p), 10) for p in ("loop", "composition")},
            },
            "exa": {"searches": sum(1 for x in self.log if x["service"] == "exa"),
                    "cost_usd": round(sum(x["cost"] for x in self.log if x["service"] == "exa"), 10)},
            "voyage": {"requests": sum(1 for x in self.log if x["service"] == "voyage"),
                       "cost_usd": round(sum(x["cost"] for x in self.log if x["service"] == "voyage"), 10)},
            "prices": price_sources(),
        }

    # -- the per-run budgets (T3.3) ----------------------------------------------------------------------------
    def loop_input_used(self) -> int:
        """Every attempt counts toward the run's ceiling, a retried one at its estimated input (T3.3, T3.4)."""
        return sum(x["usage"].input_tokens + x["usage"].cache_write_5m_tokens + x["usage"].cache_write_1h_tokens
                   + x["usage"].cache_read_tokens for x in self.log
                   if x["service"] == "anthropic" and x["purpose"] == "loop")

    def loop_output_used(self) -> int:
        return sum(x["usage"].output_tokens for x in self.log
                   if x["service"] == "anthropic" and x["purpose"] == "loop" and x["outcome"] == "ok")

    def next_call_would_cross_input(self) -> bool:
        """Before each loop call our code estimates its input and, if the run would cross the budget, goes to composition."""
        return self.loop_input_used() + PREFIX_TOKENS + self.conv_tokens() > int(settings.LOOP_INPUT_BUDGET.value)

    # -- fragments ---------------------------------------------------------------------------------------------
    def flush_request_fragments(self, call_no: int) -> None:
        for pid, mi, ti, bi, block in self.pending:
            self.emit("api_fragment", {"passage_id": pid, "call_no": call_no, "role": "request",
                                       "path": f"messages[{mi}].content[{ti}].content[{bi}]",
                                       "json": {"type": "text", "text": block}})
        self.pending = []

    # -- pause / resume ----------------------------------------------------------------------------------------
    def pause(self, quiet_ms: int = 26_000, resume_after_ms: int | None = 17_000) -> None:
        """`paused.since_ms`: how long since the last heartbeat when the run paused; `resumed.since_ms`: how long
        the run was paused (an assumption, raised as a question in the README)."""
        self.wait(quiet_ms)
        self.emit("paused", {"since_ms": quiet_ms})
        if resume_after_ms is not None:
            self.wait(resume_after_ms)
            self.emit("resumed", {"since_ms": resume_after_ms})

    # -- one loop round ----------------------------------------------------------------------------------------
    def round(self, calls: list, text: str | None = None, *, retries: list | None = None, fail: tuple | None = None,
              think: int | None = None, pause: tuple | None = None, cut_output: int | None = None,
              latency_scale: float = 1.0, refusal: bool = False) -> bool:
        """One round: round_started, the Claude call (with any retries), then each tool call and its result.

        retries: failures that were retried, [(error_kind, duration_ms), ...]. fail=(error_kind, duration_ms): the
        attempt after them also failed, so the call has failed and nothing more happens in this round (returns False).
        cut_output=n: the call stopped at max_tokens after n output tokens: no tool calls (T3.3). pause=(quiet_ms,
        resume_after_ms or None): the run pauses before the call."""
        if not self.messages:
            self.messages.append(self.first_message())
        self.round_no += 1
        self.emit("round_started", {"round": self.round_no, "status_line": self.status_line(self.round_no)}, adv=3)
        self.call_no += 1
        call_no = self.call_no
        self.flush_request_fragments(call_no)
        if pause:
            self.pause(*pause)
            if pause[1] is None:          # never resumed: no call is made (the run goes on to be abandoned)
                self.call_no -= 1
                return False

        content = []
        if text:
            content.append({"type": "text", "text": text})
        for c in calls:
            self.tool_seq += 1
            c.id = tool_id(self.slug, self.tool_seq)
            c.index = len(content)
            content.append({"type": "tool_use", "id": c.id, "name": c.name, "input": c.input})
        think = think if think is not None else self.rng.randint(140, 620)
        out_tokens = cut_output if cut_output is not None else (
            sum(tok(jdump(b["input"])) + 14 if b["type"] == "tool_use" else tok(b["text"]) for b in content) + think)

        conv = self.conv_tokens()
        tail = tok(self.messages[-1]["content"][-1].get("text", "")) if self.messages[-1]["role"] == "user" else 0
        if call_no == 1:
            raw = self.raw_usage(conv, 0, PREFIX_TOKENS, 0, out_tokens)
        else:
            new = conv - self.prev_conv
            w5 = new - tail if new - tail >= 1024 else 0
            raw = self.raw_usage(new - w5, w5, 0, PREFIX_TOKENS + self.prev_conv, out_tokens)
        est_in = PREFIX_TOKENS + conv
        latency = lambda out: int((700 + out * 4.0 + self.rng.randint(-150, 250)) * latency_scale)  # noqa: E731

        # attempts that failed and were retried, then the last one
        for k, (kind, dur) in enumerate(retries or [], start=1):
            self.wait(dur)
            self.paid("anthropic", "loop", attempt=k, max_attempts=LOOP_ATTEMPTS, outcome="retrying", error_kind=kind,
                      duration_ms=dur, usage=failed_attempt_usage("anthropic", LOOP_MODEL, est_in), raw=None, call_no=call_no)
            self.wait(ANTHROPIC_WAITS[min(k - 1, len(ANTHROPIC_WAITS) - 1)] * 1000)
        attempt = len(retries or []) + 1
        if fail:
            kind, dur = fail
            self.wait(dur)
            self.paid("anthropic", "loop", attempt=attempt, max_attempts=LOOP_ATTEMPTS, outcome="failed", error_kind=kind,
                      duration_ms=dur, usage=failed_attempt_usage("anthropic", LOOP_MODEL, est_in), raw=None, call_no=call_no)
            return False
        dur = latency(out_tokens)
        self.wait(dur)
        if refusal:             # the response finished with the refusal stop reason: billed, so its usage is real (T3.3)
            self.paid("anthropic", "loop", attempt=attempt, max_attempts=LOOP_ATTEMPTS, outcome="failed", error_kind="refusal",
                      duration_ms=dur, usage=self.claude_usage(LOOP_MODEL, raw), raw=raw, call_no=call_no)
            return False
        self.paid("anthropic", "loop", attempt=attempt, max_attempts=LOOP_ATTEMPTS, outcome="ok", error_kind=None,
                  duration_ms=dur, usage=self.claude_usage(LOOP_MODEL, raw), raw=raw, call_no=call_no)
        self.prev_conv = conv
        if cut_output is not None:
            return True
        self.messages.append({"role": "assistant", "content": content})

        results = []
        same_turn_reads = any(c.name in ("search_meaning", "search_exact", "read_passages", "search_web_updates") for c in calls)
        for ti, c in enumerate(calls):
            res = self.execute(c, same_turn_reads, call_no)
            results.append(res)
            # the response-side fragments name the tool_use block that returned or kept each passage
            for pid in res.resp_pids:
                self.emit("api_fragment", {"passage_id": pid, "call_no": call_no, "role": "response",
                                           "path": f"content[{c.index}]", "json": content[c.index]})
            for pid, bi in res.block_pids:
                self.pending.append((pid, len(self.messages), ti, bi, res.blocks[bi]))
        user = []
        for c, res in zip(calls, results):
            b = {"type": "tool_result", "tool_use_id": c.id, "content": [{"type": "text", "text": t} for t in res.blocks]}
            if res.is_error:
                b["is_error"] = True
            user.append(b)
        user.append({"type": "text", "text": self.status_line(self.round_no + 1)})
        self.messages.append({"role": "user", "content": user})
        return True

    # -- tools -------------------------------------------------------------------------------------------------
    def execute(self, c: Call, same_turn: bool, call_no: int) -> Result:
        shown = c.input
        if c.name == "submit_answer":
            res, shown = self.do_submit(c, same_turn)
        else:
            res = None
        self.emit("tool_call", {"round": self.round_no, "tool_use_id": c.id, "name": c.name, "input": shown}, adv=2)
        if res is None:
            res = {"search_meaning": self.do_meaning, "search_exact": self.do_exact, "read_passages": self.do_read,
                   "keep_passages": self.do_keep, "search_web_updates": self.do_web}[c.name](c)
        warn = res.extra.pop("_warn", None)
        data = {"tool_use_id": c.id, "name": c.name, "is_error": res.is_error, "content": "\n\n".join(res.blocks)}
        data.update(res.extra)
        self.emit("tool_result", data, adv=2)
        if warn:
            self._warn(warn)          # once each, right after the result that set the flag (T3.3)
        return res

    def _warn(self, code: str) -> None:
        if code not in self.warned:
            self.warned.add(code)
            self.emit("warning", {"code": code}, adv=2)

    # search results: new passages up to max_results, "matched again" for the ones already shown (T1.6)
    def assemble(self, ranked: list, max_results: int, extra_blocks: list | None = None) -> Result:
        new, again = [], []
        for pid in ranked:
            if pid in self.seen:
                again.append(pid)
            else:
                new.append(pid)
                if len(new) >= max_results:
                    break
        blocks, block_pids = [], []
        for pid in new:
            self.ensure_passage(pid)
            block_pids.append((pid, len(blocks)))
            blocks.append(passage_block(self.corpus, pid))
            self.seen.add(pid)
            for f in self.corpus.attached_footnotes(pid):
                self.ensure_passage(f.id)
                self.seen.add(f.id)
                block_pids.append((f.id, len(blocks) - 1))
        if again:
            blocks.append("Matched again (shown earlier in this run, not sent again): " + ", ".join(again) + ".")
        if not new and not again:
            blocks.append("No passages matched this search.")
        blocks += extra_blocks or []
        return Result(blocks=blocks, extra={"found": list(new), "matched_again": list(again)},
                      block_pids=block_pids, resp_pids=list(new) + list(again))

    def max_results(self, inp: dict) -> int:
        n = inp.get("max_results", int(settings.MAX_RESULTS_DEFAULT.value))
        return max(1, min(int(settings.MAX_RESULTS_CAP.value), int(n)))

    def do_exact(self, c: Call) -> Result:
        inp = c.input
        try:
            f = parse_filters(inp.get("filters"), self.corpus)
            mr = self.max_results(inp)
            hits = self.kw.search(inp.get("all_of", []), inp.get("any_of", []), inp.get("none_of", []), f, mr + len(self.seen))
        except ToolInputError as e:
            return Result(blocks=[e.message], is_error=True, extra={"found": [], "matched_again": []})
        self.corpus_searched = True
        return self.assemble([h.passage_id for h in hits], mr)

    def do_meaning(self, c: Call) -> Result:
        inp = c.input
        try:
            f = parse_filters(inp.get("filters"), self.corpus)
        except ToolInputError as e:
            return Result(blocks=[e.message], is_error=True, extra={"found": [], "matched_again": []})
        mr = self.max_results(inp)
        script = c.voyage or {}
        # the embed request, then the rerank request, each through our retries (T3.3)
        qtok = tok(inp["query"]) + 4
        embed_ok = self.voyage_request("embed", script.get("embed", []), qtok, f"{self.slug}-e{c.id}", ms=190)
        if not embed_ok:
            return Result(blocks=[UNAVAILABLE_NOTE], is_error=True,
                          extra={"found": [], "matched_again": [], "not_reranked": False,
                                 "_warn": "meaning_search_unavailable"})
        q = self.mi.matrix[self.row[c.seed]]
        sims = self.mi.matrix @ q
        order = np.argsort(-sims, kind="stable")
        cand = [self.mi.passages[j].id for j in order
                if matches(self.mi.passages[j], f) and not excluded_by_none_of(self.mi.passages[j], f)]
        cand = cand[: int(settings.SEMANTIC_CANDIDATES.value)]
        doc_tokens = sum(tok(self.corpus.passages[p].text) for p in cand) + qtok * len(cand)
        rerank_ok = self.voyage_request("rerank", script.get("rerank", []), doc_tokens, f"{self.slug}-r{c.id}", ms=640)
        extra_blocks = []
        if not rerank_ok:
            extra_blocks.append(NOT_RERANKED_NOTE)
        self.corpus_searched = True
        res = self.assemble(cand, mr, extra_blocks)
        res.extra["not_reranked"] = not rerank_ok
        if not rerank_ok:
            res.extra["_warn"] = "meaning_search_degraded"
        return res

    def voyage_request(self, purpose: str, failures: list, tokens: int, salt: str, ms: int) -> bool:
        """A Voyage request with `failures` (error kinds) before it works, each a paid_call attempt (T3.3).
        More failures than the retries allow means it failed for good. Returns whether it worked."""
        self.n_voyage += 1
        model = str(settings.EMBED_MODEL.value if purpose == "embed" else settings.RERANK_MODEL.value)
        for k, kind in enumerate(failures, start=1):
            dur = int(settings.VOYAGE_TIMEOUT_S.value) * 1000 if kind == "timeout" else self.rng.randint(120, 400)
            self.wait(dur)
            last = k >= VOYAGE_ATTEMPTS
            self.paid("voyage", purpose, attempt=k, max_attempts=VOYAGE_ATTEMPTS, outcome="failed" if last else "retrying",
                      error_kind=kind, duration_ms=dur, usage=failed_attempt_usage("voyage", model, tokens), raw=None)
            if last:
                return False
            self.wait(VOYAGE_WAITS[min(k - 1, len(VOYAGE_WAITS) - 1)] * 1000)
        dur = ms + self.rng.randint(-40, 90)
        self.wait(dur)
        self.paid("voyage", purpose, attempt=len(failures) + 1, max_attempts=VOYAGE_ATTEMPTS, outcome="ok", error_kind=None,
                  duration_ms=dur, usage=Usage(service="voyage", model=model, input_tokens=tokens),
                  raw={"total_tokens": tokens})
        return True

    def do_read(self, c: Call) -> Result:
        inp = c.input
        try:
            ps = self.corpus.read(inp.get("target", ""), int(inp.get("before", 0)), int(inp.get("after", 0)))
        except ToolInputError as e:
            return Result(blocks=[e.message], is_error=True, extra={"target": str(inp.get("target", "")), "read": []})
        target = str(inp["target"]).strip().lower()
        blocks, block_pids = [], []
        for p in ps:
            self.ensure_passage(p.id)
            req = p.id == target or ":" in target
            block_pids.append((p.id, len(blocks)))
            blocks.append(passage_block(self.corpus, p.id, requested=req))
            self.seen.add(p.id)
            for f in self.corpus.attached_footnotes(p.id):
                self.ensure_passage(f.id)
                self.seen.add(f.id)
                block_pids.append((f.id, len(blocks) - 1))
        ids = [p.id for p in ps]
        return Result(blocks=blocks, extra={"target": target, "read": ids}, block_pids=block_pids, resp_pids=ids)

    def do_keep(self, c: Call) -> Result:
        items = c.input.get("keep", [])
        cap, rmax = int(settings.KEEP_CAP.value), int(settings.KEEP_REASON_MAX_CHARS.value)
        applied, refused, lines = [], [], []
        for it in items:
            pid, reason = it.get("id"), it.get("reason", "")
            if pid not in self.seen:
                why = fill(REJ["keep"]["unseen_id"], id=pid)
            elif not reason.strip():
                why = fill(REJ["keep"]["reason_empty"], id=pid)
            elif len(reason) > rmax:
                why = fill(REJ["keep"]["reason_too_long"], id=pid, length=len(reason))
            elif pid not in self.kept and len(self.kept) >= cap:
                why = fill(REJ["keep"]["cap_reached"], id=pid, count=len(self.kept))
            else:
                why = None
            if why:
                refused.append({"id": pid, "why": why})
                continue
            replaced = pid in self.kept
            self.kept[pid] = {"reason": reason, "round": self.round_no}
            applied.append({"id": pid, "reason": reason, "replaced": replaced})
        if not applied:
            text = fill(REJ["keep"]["nothing_applied"], problems="\n".join(r["why"] for r in refused))
            return Result(blocks=[text], is_error=True, extra={"kept": [], "refused": refused, "kept_count": len(self.kept)})
        new = [a["id"] for a in applied if not a["replaced"]]
        again = [a["id"] for a in applied if a["replaced"]]
        parts = []
        if new:
            parts.append(f"Kept {len(new)} passage{'s' if len(new) != 1 else ''}: {', '.join(new)}.")
        if again:
            parts.append(f"Replaced the reason for {', '.join(again)}.")
        parts.append(f"{len(self.kept)} passages are kept in all.")
        text = " ".join(parts)
        if refused:
            text += "\nNot kept:\n" + "\n".join(r["why"] for r in refused)
        extra = {"kept": applied, "kept_count": len(self.kept)}
        if refused:
            extra["refused"] = refused
        return Result(blocks=[text], extra=extra, resp_pids=[a["id"] for a in applied])

    # -- the update check --------------------------------------------------------------------------------------
    def do_web(self, c: Call) -> Result:
        w = c.web or Web()
        raw = c.input
        try:
            params = parse_params(raw)
        except ToolInputError as e:
            return Result(blocks=[e.message], is_error=True, extra={"web": [], "web_repeats": [], "web_status": "refused_by_us"})
        if self.counted >= UPDATE_SEARCHES:
            return Result(blocks=[fill(REJ["update_search"]["fourth_search"])], is_error=True,
                          extra={"web": [], "web_repeats": [], "web_status": "refused_by_us"})
        kind = "unavailable" if self.unavailable else w.kind
        search_no = self.counted + 1
        pages = []
        if kind == "ok":
            for i, spec in enumerate(w.pages, start=1):
                pid = f"web-{search_no}-{i}"
                domain = spec["domain"]
                pg = WebPage(id=pid, title=spec["title"], url=f"https://{domain}/sample/{spec['slug']}", domain=domain,
                             published=spec.get("published"), author=spec.get("author"),
                             text=page_text(spec["slug"], spec["chars"], spec.get("text", "")), truncated=spec["chars"] >= int(settings.EXA_TEXT_CHARS.value))
                pages.append(pg)
        outcome = WebSearchOutcome(kind=kind, unavailable_reason=(self.unavailable or w.reason) if kind == "unavailable" else None,
                                   pages=pages, repeats=list(w.repeats) if kind == "ok" else [],
                                   undated=sum(1 for p in pages if p.published is None), exa_message=w.exa_message,
                                   cost_usd=0.0)
        if kind == "unavailable":
            self.unavailable = outcome.unavailable_reason
        else:
            self.counted += 1
            dur = w.ms or (30_000 if kind == "failed" else self.rng.randint(1100, 2300))
            self.wait(dur)
            if kind == "ok":
                usage = Usage(service="exa", model=params.type, exa_cost_usd=0.004 if params.type == "lite" else 0.007)
                self.paid("exa", "update_search", attempt=1, max_attempts=1, outcome="ok", error_kind=None, duration_ms=dur,
                          usage=usage, raw=None)
            elif kind == "refused_by_exa":
                self.paid("exa", "update_search", attempt=1, max_attempts=1, outcome="failed", error_kind="bad_request",
                          duration_ms=dur, usage=Usage(service="exa", model=params.type, exa_cost_usd=0.0), raw=None)
            else:
                self.paid("exa", "update_search", attempt=1, max_attempts=1, outcome="failed", error_kind="timeout",
                          duration_ms=dur, usage=failed_attempt_usage("exa", params.type), raw=None)
        for pg in pages:
            self.pages[pg.id] = pg
            self.page_order.append(pg.id)
        self.band_searches.append({
            "search_no": search_no, "params": params_as_dict(params), "fixed": fixed_settings(),
            "status": {"ok": "ok", "refused_by_exa": "refused_by_exa", "failed": "failed", "unavailable": "unavailable"}[kind],
            "returned": len(pages) + len(outcome.repeats), "undated": outcome.undated})
        details = [{"id": p.id, "title": p.title, "url": p.url, "domain": p.domain, "published": p.published, "author": p.author}
                   for p in pages]
        text = format_for_events(params, outcome)
        return Result(blocks=[text], is_error=kind != "ok",
                      extra={"web": details, "web_repeats": list(outcome.repeats), "web_status": kind, "search_no": search_no})

    # -- the submit and its rules (T1.10, T2.3) ----------------------------------------------------------------
    def do_submit(self, c: Call, same_turn: bool):
        inp = c.input
        shown = inp
        findings = inp.get("update_findings")
        overview = inp.get("update_overview")

        def refuse(rule: str, text: str, shown_input=None):
            res = Result(blocks=[text], is_error=True, extra={"submit": {"accepted": False, "rule": rule}})
            return res, (shown_input if shown_input is not None else inp)

        if same_turn:
            return refuse("same_turn", fill(REJ["submit"]["rule_1_same_turn"]))
        if findings is not None or overview:
            problems = check_update_findings(findings or [], overview, set(self.pages), self.counted)
            if problems:
                return refuse("findings", fill(REJ["submit"]["findings_problems"], problems="\n".join(problems)))
            texts = {pid: p.text for pid, p in self.pages.items()}
            rep = copy_guard_report([f["statement"] for f in findings or []], overview, texts, int(settings.COPY_GUARD_WORDS.value))
            if rep.problems:
                red = json.loads(jdump(inp))
                for i in rep.flagged_statements:
                    red["update_findings"][i]["statement"] = WITHHELD
                if rep.overview_flagged:
                    red["update_overview"] = WITHHELD
                return refuse("copy_guard", fill(REJ["submit"]["copy_guard"], problems="\n".join(rep.problems)), red)
        if not inp.get("out_of_scope"):
            if not self.corpus_searched:
                return refuse("no_search", fill(REJ["submit"]["rule_2_no_search"]))
            if not self.kept and not inp.get("note"):
                return refuse("nothing_kept", fill(REJ["submit"]["rule_3_nothing_kept"]))
        searched = self.counted > 0
        if not searched and not self.unavailable and not inp.get("update_skip_reason"):
            if not self.reminded:
                self.reminded = True
                return refuse("no_update_check", fill(REJ["submit"]["rule_4_no_update_check"]))
            self.declined = True
        self.submit = inp
        n = len(self.kept)
        msg = ("Submission accepted. " + (f"The answer is being written from the {n} kept passage{'s' if n != 1 else ''}."
                                          if n and not inp.get("out_of_scope") else "No answer will be written."))
        return Result(blocks=[msg], extra={"submit": {"accepted": True}}), shown

    # -- composition and the ends --------------------------------------------------------------------------------
    def sorted_kept(self) -> list:
        def key(pid):
            p = self.corpus.passages[pid]
            return (p.decided, int(p.opinion_id.rsplit("-", 1)[1]), p.kind == "footnote", p.position)
        return sorted(self.kept, key=key)

    def compose(self, spec: list, *, scope_note: str | None = None, retries: list | None = None, fail: tuple | None = None,
                incomplete_after: int | None = None, cut_off: bool = False, think: int | None = None,
                fail_after: tuple | None = None) -> bool:
        """The composition call (T1.11): started, request fragments, answer blocks as they stream, the paid call, response
        fragments, then the checks. `spec`: [{"text", "cites": [(passage_id, first, last), ...]}, ...].
        retries/fail: attempts that failed before the first block (T3.3); incomplete_after=k: the stream broke after k
        blocks; cut_off: the call stopped at max_tokens. Returns whether any block arrived."""
        self.call_no += 1
        call_no = self.call_no
        docs = self.sorted_kept()
        self.kept_at_compose = list(docs)
        self.emit("composition_started", {"call_no": call_no, "documents": docs}, adv=4)
        content = [doc_block(self.corpus.passages[pid], self.kept[pid]["reason"]) for pid in docs]
        ask = [f"Question: {self.question}"]
        if scope_note:
            ask.append(f"Scope note: {scope_note}")
        cov = self.corpus.coverage
        ask.append(f"The corpus ends at these dates: latest decision in the full pull {cov['latest_decision_full_pull']}; "
                   f"latest in the corpus {cov['latest_decision_in_corpus']}; ingested {cov['ingested']}.")
        ask_text = "\n\n".join(ask)
        content.append({"type": "text", "text": ask_text})
        req_tokens = 640 + sum(sum(tok(b["text"]) for b in d["source"]["content"]) + tok(d["context"]) + tok(d["title"]) + 20
                               for d in content[:-1]) + tok(ask_text)
        for i, pid in enumerate(docs):
            self.emit("api_fragment", {"passage_id": pid, "call_no": call_no, "role": "request",
                                       "path": f"messages[0].content[{i}]", "json": content[i]}, adv=1)
        doc_index = {pid: i for i, pid in enumerate(docs)}

        for k, (kind, dur) in enumerate(retries or [], start=1):
            self.wait(dur)
            self.paid("anthropic", "composition", attempt=k, max_attempts=LOOP_ATTEMPTS, outcome="retrying", error_kind=kind,
                      duration_ms=dur, usage=failed_attempt_usage("anthropic", COMP_MODEL, req_tokens), raw=None, call_no=call_no)
            self.wait(ANTHROPIC_WAITS[min(k - 1, len(ANTHROPIC_WAITS) - 1)] * 1000)
        attempt = len(retries or []) + 1
        if fail:
            kind, dur = fail
            self.wait(dur)
            self.paid("anthropic", "composition", attempt=attempt, max_attempts=LOOP_ATTEMPTS, outcome="failed", error_kind=kind,
                      duration_ms=dur, usage=failed_attempt_usage("anthropic", COMP_MODEL, req_tokens), raw=None, call_no=call_no)
            return False

        blocks = []
        for i, b in enumerate(spec):
            cites = []
            for pid, a, z in b.get("cites", []):
                if pid not in doc_index:
                    raise AssertionError(f"{self.slug}: block {i} cites {pid}, which is not kept")
                p = self.corpus.passages[pid]
                cites.append({"passage_id": pid, "first_sentence": a, "last_sentence": z,
                              "cited_text": p.text[p.sentences[a][0]: p.sentences[z][1]], "call_no": call_no,
                              "path": f"content[{i}]"})
            api = {"type": "text", "text": b["text"]}
            if cites:
                api["citations"] = [{"type": "content_block_location", "cited_text": x["cited_text"],
                                     "document_index": doc_index[x["passage_id"]],
                                     "document_title": doc_title(self.corpus.passages[x["passage_id"]]),
                                     "start_block_index": x["first_sentence"], "end_block_index": x["last_sentence"] + 1}
                                    for x in cites]
            blocks.append((b, cites, api))
        shown = blocks if incomplete_after is None else blocks[:incomplete_after]
        text_tokens = sum(tok(b["text"]) + 6 * len(cs) for b, cs, _ in shown)
        think = think if think is not None else self.rng.randint(900, 2100)
        out_tokens = int(settings.COMPOSITION_MAX_TOKENS.value) if cut_off else text_tokens + think
        total_ms = int((900 + out_tokens * 4.6) + self.rng.randint(-200, 300))
        step = total_ms // (len(shown) + 1)
        self.wait(step)
        for b, cites, _ in shown:
            self.emit("answer_block", {"index": len(self.answer_texts), "text": b["text"], "citations": cites}, adv=1)
            self.answer_texts.append(b["text"])
            self.wait(step)
        if incomplete_after is not None:
            kind, dur = fail_after or ("stream_broken", 900)
            self.wait(dur)
            self.paid("anthropic", "composition", attempt=attempt, max_attempts=LOOP_ATTEMPTS, outcome="failed", error_kind=kind,
                      duration_ms=total_ms, usage=failed_attempt_usage("anthropic", COMP_MODEL, req_tokens), raw=None, call_no=call_no)
        else:
            raw = self.raw_usage(req_tokens, 0, 0, 0, out_tokens)
            self.paid("anthropic", "composition", attempt=attempt, max_attempts=LOOP_ATTEMPTS, outcome="ok", error_kind=None,
                      duration_ms=total_ms, usage=self.claude_usage(COMP_MODEL, raw), raw=raw, call_no=call_no)
        for b, cites, api in shown:
            for cite in cites:
                self.emit("api_fragment", {"passage_id": cite["passage_id"], "call_no": call_no, "role": "response",
                                           "path": cite["path"], "json": api}, adv=1)
        self.run_checks()
        return True

    def run_checks(self) -> None:
        kept_texts = [self.corpus.passages[pid].text for pid in self.kept_at_compose]
        r = check_answer(list(self.answer_texts), kept_texts, self.corpus.manifest)
        self.emit("checks", asdict(r), adv=3)
        self.checks = r

    def band(self) -> dict:
        """The update band's outcome, worked out by code (T2.3 item 4, contract §6)."""
        findings, overview = [], None
        if self.submit:
            findings = [{"statement": f["statement"], "sources": list(f["sources"])} for f in (self.submit.get("update_findings") or [])]
            overview = self.submit.get("update_overview") or None
        reason = None
        if self.counted > 0:
            outcome = ("found" if findings else "nothing_relevant") if self.submit else "not_summarised"
        elif self.unavailable:
            outcome, reason = "unavailable", self.unavailable
        elif self.submit and self.submit.get("update_skip_reason"):
            outcome, reason = "skipped", self.submit["update_skip_reason"]
        elif self.submit and self.declined:
            outcome = "declined"
        else:
            outcome = "not_run"
        return {"outcome": outcome, "reason": reason, "searches": self.band_searches, "findings": findings,
                "overview": overview, "pages": [self.page_detail(i) for i in self.page_order]}

    def page_detail(self, pid: str) -> dict:
        p = self.pages[pid]
        return {"id": p.id, "title": p.title, "url": p.url, "domain": p.domain, "published": p.published, "author": p.author}

    def emit_band(self) -> dict:
        b = self.band()
        self.emit("update_band", b, adv=3)
        return b

    def end(self, state: str, *, stop_kind=None, no_sources_reason=None, note=None, scope_note=None, answer_end="none",
            failure_reason=None, wait_ms: int = 300) -> None:
        assert not self.ended
        self.wait(wait_ms)
        self.emit("run_ended", {
            "state": state, "stop_kind": stop_kind, "no_sources_reason": no_sources_reason, "note": note,
            "scope_note": scope_note, "answer_end": answer_end, "failure_reason": failure_reason,
            "rounds": self.round_no, "answer_chars": sum(len(t) for t in self.answer_texts), "totals": self.totals()})
        self.ended = True

    # -- the file ------------------------------------------------------------------------------------------------
    def document(self, extra_top: dict | None = None, events: list | None = None) -> dict:
        d = {"format": 1, "slug": self.slug, "question": self.question,
             "recorded_at": self.start.isoformat(timespec="seconds"), "commit": "fixture",
             "models": {"loop": LOOP_MODEL, "composition": COMP_MODEL}, "prices": price_sources(),
             "corpus_label": self.label}
        if extra_top:
            d.update(extra_top)
        d["events"] = self.events if events is None else events
        return d


def write_stream(doc: dict) -> Path:
    EVENTS_DIR.mkdir(parents=True, exist_ok=True)
    top = {k: v for k, v in doc.items() if k != "events"}
    head = ",\n".join(f"  {json.dumps(k)}: {jdump(v)}" for k, v in top.items())
    body = ",\n".join("    " + jdump(e) for e in doc["events"])
    path = EVENTS_DIR / f"{doc['slug']}.json"
    path.write_text("{\n" + head + ',\n  "events": [\n' + body + "\n  ]\n}\n", encoding="utf-8")
    return path


# ===============================================================================================================
# Scenarios
# ===============================================================================================================
SCENARIOS = []


def scenario(fn):
    SCENARIOS.append(fn)
    return fn


def T(text):
    """An uncited block of the answer (the page marks it as Claude's synthesis)."""
    return {"text": text, "cites": []}


def C(text, *cites):
    """A block that cites sentences: C("text", ("katz-1-p6", 4, 4), ("katz-3-p2", 3, 3))."""
    return {"text": text, "cites": list(cites)}


def K(pid, reason):
    return {"id": pid, "reason": reason}


def page(title, domain, slug, published, chars, author=None):
    return {"title": f"[Sample] {title}", "domain": domain, "slug": slug, "published": published,
            "author": author, "chars": chars}


def must_keep_ok(sim: Sim) -> None:
    for e in sim.events:
        if e["kind"] == "tool_result" and e["data"].get("refused"):
            summarise(sim)
            raise AssertionError(f"{sim.slug}: a keep was refused: {e['data']['refused']}")


def finish_answered(sim: Sim, spec: list, *, scope_note=None, answer_end="complete", stop_kind=None, state="answered", **kw) -> None:
    """After an accepted submit: composition, the checks, the band, the end."""
    sim.compose(spec, scope_note=scope_note, **kw)
    sim.emit_band()
    sim.end(state, stop_kind=stop_kind, scope_note=scope_note, answer_end=answer_end)


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


WEB_LOC_1 = Web(pages=[
    page("Appeals court weighs a tower-dump warrant", "news.example.test", "tower-dump-appeal", "2026-09-12", 3812, "Sample Staff"),
    page("State bill would limit sales of location data to agencies", "capitol.example.test", "location-data-bill", "2026-08-03", 2905),
    page("Notes on location records and the third-party rule", "journal.example.test", "location-notes", None, 4000),
    page("Privacy law roundup, October", "digest.example.test", "privacy-roundup-oct", "2026-10-01", 3340, "Sample Editor"),
])
WEB_LOC_2 = Web(pages=[
    page("Petitions on location data wait at the Court", "news.example.test", "location-petitions", "2026-09-28", 3120),
    page("Commentary: what remains open after the location-records decision", "review.example.test", "what-remains-open", "2026-07-20", 4000, "Sample Contributor"),
    page("Scholars react to a state high court's location ruling", "journal.example.test", "state-high-court", "2026-08-19", 2710),
], repeats=["web-1-1"])


@scenario
def answered_phone_location_records(order):
    s = Sim("answered-phone-location-records", "Do police need a warrant to get my cell phone location records from my carrier?", order)
    s.run_started()
    s.round([
        Call("search_meaning", {"query": "whether police need a warrant to obtain cell phone location records from a wireless carrier",
                                "max_results": 6}, seed="carpenter-1-p41"),
        Call("search_meaning", {"query": "how the Court treated the Government's acquisition of historical cell-site records",
                                "max_results": 6}, seed="carpenter-1-p33"),
        Call("search_exact", {"any_of": ["cell-site", "CSLI"], "filters": {"decided_from": "2012"}, "max_results": 6}),
    ])
    s.round([
        Call("search_meaning", {"query": "a person has no legitimate expectation of privacy in information voluntarily turned over to a third party",
                                "filters": {"decided_to": "1990"}, "max_results": 5}, seed="smith-1-p16"),
        Call("search_exact", {"any_of": ["\"takes the risk\"", "\"assumed the risk\""],
                              "filters": {"decided_to": "1990", "opinion_types": ["majority"]}, "max_results": 4}),
        Call("search_meaning", {"query": "tracking a person's movements through a phone compared with GPS monitoring of a car",
                                "filters": {"decided_from": "2012"}, "max_results": 4}, seed="carpenter-1-p28"),
        Call("keep_passages", {"keep": [K(i, LOC_KEEPS[i]) for i in ("carpenter-1-p25", "carpenter-1-p33", "carpenter-1-p41")]}),
    ], text="Reading the third-party cases the Court discussed.")
    s.round([
        Call("read_passages", {"target": "carpenter-1-p40", "before": 0, "after": 1}),
        Call("search_meaning", {"query": "actual expectation of privacy and an expectation society is prepared to recognize as reasonable",
                                "filters": {"cases": ["katz"]}, "max_results": 3}, seed="katz-3-p2"),
        Call("search_exact", {"all_of": ["probable cause", "cell-site"], "filters": {"cases": ["carpenter"], "opinion_types": ["dissent"]}, "max_results": 3}),
        Call("keep_passages", {"keep": [K("carpenter-1-p28", LOC_KEEPS["carpenter-1-p28"]), K("smith-1-p16", LOC_KEEPS["smith-1-p16"]),
                                        K("miller-1-p16", LOC_KEEPS["miller-1-p16"])]}),
    ])
    s.round([
        Call("search_exact", {"any_of": ["\"585 U. S. 296\"", "\"585 U. S., at\""], "filters": {"decided_from": "2019"}, "max_results": 4}),
        Call("keep_passages", {"keep": [K("katz-3-p2", LOC_KEEPS["katz-3-p2"]), K("carpenter-4-p5", LOC_KEEPS["carpenter-4-p5"]),
                                        K("carpenter-1-p40", LOC_P40_FIRST)]}),
    ])
    s.round([
        Call("search_web_updates", {"query": "Supreme Court cell phone location records warrant decision", "start_published_date": "2026-06-30",
                                    "end_published_date": "2026-10-24", "category": "news", "num_results": 5}, web=WEB_LOC_1),
        Call("keep_passages", {"keep": [K("carpenter-1-p40", LOC_P40)]}),
    ], text="Checking for developments after the corpus's last decision.")
    s.round([
        Call("search_web_updates", {"query": "pending petitions location data warrant third-party doctrine", "start_published_date": "2026-06-30",
                                    "category": "publication", "num_results": 5}, web=WEB_LOC_2),
    ])
    s.round([
        Call("submit_answer", {"out_of_scope": False, "update_findings": [
            {"statement": "A sample news page reports that a federal court of appeals took up a challenge to a tower-dump warrant in September 2026.",
             "sources": ["web-1-1"]},
            {"statement": "Sample pages report that a state legislature was considering limits on sales of location data to government agencies, and that petitions on location data were waiting at the Court.",
             "sources": ["web-1-2", "web-2-1"]}],
            "update_overview": "The sample pages describe lower-court and legislative activity on location data after the corpus's coverage dates. None of them reports a Supreme Court decision."}),
    ])
    must_keep_ok(s)
    finish_answered(s, LOC_ANSWER)
    return s




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


def thermal_search_calls():
    return [
        Call("search_meaning", {"query": "using a thermal imaging device on a house from a public street", "max_results": 4}, seed="kyllo-1-p5"),
        Call("search_exact", {"any_of": ["\"thermal imaging\"", "\"thermal-imaging\""], "filters": {"cases": ["kyllo"], "opinion_types": ["majority"]},
                              "max_results": 3}),
    ]


def thermal_keep(*ids):
    return Call("keep_passages", {"keep": [K(i, THERMAL_KEEPS[i]) for i in ids]})


# --- 2. A reply with no sources: out of scope ------------------------------------------------------------------------
@scenario
def out_of_scope_reply(order):
    s = Sim("out-of-scope-reply", "Can my landlord raise my rent in the middle of a lease?", order)
    s.run_started()
    note = ("This question is about landlord-tenant law, which falls outside what this corpus covers: Supreme Court opinions on the "
            "Fourth Amendment and surveillance technology. A related question I can research is whether police may use technology such as "
            "thermal imaging to look into a home from outside it.")
    skip = "The question is outside the corpus's subject, so there is nothing to check for later developments."
    s.round([Call("submit_answer", {"out_of_scope": True, "note": note, "update_skip_reason": skip})])
    s.emit_band()
    s.end("no_sources", no_sources_reason="out_of_scope", note=note)
    return s


# --- 3. A reply with no sources: nothing found ----------------------------------------------------------------------
@scenario
def nothing_found_reply(order):
    s = Sim("nothing-found-reply", "Does the Fourth Amendment require a warrant before a public school searches a student's backpack?", order)
    s.run_started()
    s.round([
        Call("search_meaning", {"query": "a school official searching a student's belongings for contraband", "max_results": 5}, seed="grady-1-p9"),
        Call("search_exact", {"all_of": ["school", "student"], "max_results": 5}),
    ])
    s.round([
        Call("read_passages", {"target": "grady-1-p9", "before": 1, "after": 1}),
        Call("search_exact", {"any_of": ["\"school official\"", "\"public school\"", "schoolchildren"], "max_results": 5}),
    ], text="The only mention of schools is in passing; checking its context.")
    s.round([
        Call("search_web_updates", {"query": "Supreme Court student backpack search Fourth Amendment school decision", "start_published_date": "2026-06-30",
                                    "category": "news", "num_results": 3},
             web=Web(pages=[page("School district updates its locker search policy", "schools.example.test", "locker-policy", "2026-08-21", 2480),
                            page("A parent's guide to searches at school", "family.example.test", "parents-guide", None, 3160)])),
    ])
    note = ("Claude found no passages in the corpus that bear on this question. The corpus holds Supreme Court opinions on the Fourth Amendment "
            "and surveillance technology, and none of them addresses searches by school officials. A related question it can answer is how the "
            "Court treats searches of the data on a cell phone.")
    s.round([Call("submit_answer", {"out_of_scope": False, "note": note, "update_findings": []})])
    must_keep_ok(s)
    s.emit_band()
    s.end("no_sources", no_sources_reason="nothing_found", note=note)
    return s


# --- pause and resume (T3.2), with a scope note -----------------------------------------------------------------------
@scenario
def pause_and_resume(order):
    s = Sim("pause-and-resume", "Can police search my phone when they arrest me, and does my state constitution add anything?", order)
    s.run_started()
    s.round(phone_search_calls())
    s.round([phone_keep("riley-1-p26", "riley-1-p25", "riley-1-p66")], pause=(26_000, 17_000))
    scope = ("Part of this question turns on a state constitution, which the corpus does not cover. The answer sets out only what the "
             "Supreme Court held under the Fourth Amendment.")
    s.round([Call("submit_answer", {"out_of_scope": False, "note": scope,
                                    "update_skip_reason": "The question asks what the Court held in Riley, so a search for later developments was not needed."})])
    must_keep_ok(s)
    finish_answered(s, PHONE_ANSWER, scope_note=scope)
    return s


# --- an abandoned run (T3.2) ---------------------------------------------------------------------------------------------
@scenario
def abandoned_run(order):
    s = Sim("abandoned-run", PHONE_Q, order)
    s.run_started()
    s.round(phone_search_calls())
    s.round([phone_keep("riley-1-p26", "riley-1-p25")])
    s.round([], pause=(26_000, None))          # no heartbeat ever comes back
    s.wait(int(settings.ABANDON_AFTER_S.value) * 1000 - 26_000)
    s.emit_band()
    s.end("abandoned", wait_ms=200)
    return s


# --- an interrupted run (T3.1): the instance that held it is gone; the page reconnects to another one -------------
@scenario
def interrupted_run(order):
    s = Sim("interrupted-run", THERMAL_Q, order)
    s.run_started()
    s.round(thermal_search_calls())
    s.round([thermal_keep("kyllo-1-p1", "kyllo-1-p14")])
    s.end("interrupted", wait_ms=41_000)       # H's event: sent on the stream only, never stored
    return s


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
def step_limit_stop(order):
    s = Sim("step-limit-stop", GPS_Q, order)
    s.run_started()
    s.round([
        Call("search_meaning", {"query": "attaching a GPS tracking device to a car and following its movements", "max_results": 4}, seed="jones-1-p8"),
        Call("search_exact", {"any_of": ["GPS", "\"Global-Positioning-System\""], "filters": {"decided_from": "2000"}, "max_results": 4}),
    ])
    s.round([
        Call("search_meaning", {"query": "movements on public roads are visible to anyone, so no reasonable expectation of privacy",
                                "filters": {"decided_to": "1990"}, "max_results": 4}, seed="knotts-1-p15"),
        Call("search_exact", {"any_of": ["beeper"], "filters": {"cases": ["knotts"], "opinion_types": ["majority"]}, "max_results": 3}),
        Call("read_passages", {"target": "jones-1-p9"}),
        gps_keep("jones-1-p8"),
    ])
    s.round([gps_keep("jones-1-p9"), Call("read_passages", {"target": "knotts-1-p15", "before": 1, "after": 1}),
             Call("search_meaning", {"query": "monitoring an electronic tracking device inside a private home", "max_results": 4}, seed="karo-1-p19")])
    s.round([gps_keep("knotts-1-p15"),
             Call("search_exact", {"all_of": ["beeper", "warrant"], "filters": {"cases": ["karo"]}, "max_results": 3})])
    s.round([Call("read_passages", {"target": "karo-1-p19", "before": 0, "after": 2})])
    s.round([gps_keep("karo-1-p19"),
             Call("search_meaning", {"query": "GPS monitoring creates a precise, comprehensive record of a person's public movements",
                                     "filters": {"opinion_types": ["concurrence"]}, "max_results": 4}, seed="jones-2-p4")])
    s.round([Call("read_passages", {"target": "jones-2-p4", "before": 1, "after": 1}),
             Call("search_exact", {"all_of": ["long-term", "monitoring"], "filters": {"cases": ["jones"]}, "max_results": 3})])
    s.round([gps_keep("jones-2-p4"), Call("read_passages", {"target": "jones-3-p28", "before": 0, "after": 1})])
    s.round([gps_keep("jones-3-p29"),
             Call("search_exact", {"any_of": ["\"565 U. S. 400\"", "\"565 U. S., at\""], "filters": {"decided_from": "2013"}, "max_results": 4})])
    s.round([Call("search_meaning", {"query": "tracking a person through a phone compared with GPS monitoring of a car",
                                     "filters": {"decided_from": "2013"}, "max_results": 4}, seed="carpenter-1-p28")])
    s.round([Call("search_web_updates", {"query": "GPS tracker warrant court decision", "start_published_date": "2026-06-30", "category": "news",
                                         "num_results": 4},
                  web=Web(pages=[page("Police GPS trackers draw a new round of challenges", "news.example.test", "gps-challenges", "2026-09-03", 3010),
                                 page("Explainer: tracking devices and the warrant requirement", "explainer.example.test", "tracking-explainer", None, 3880)]))])
    s.round([Call("search_exact", {"any_of": ["\"Global-Positioning-System\"", "\"GPS\""], "filters": {"decided_from": "2013"}, "max_results": 4})])
    must_keep_ok(s)
    finish_answered(s, GPS_ANSWER, state="step_limit", stop_kind="step_limit")
    return s


# --- the checks: a misquotation and a full case name that is not in the corpus (T1.12, T5.2) -----------------------
@scenario
def check_flags(order):
    s = Sim("check-flags", GPS_Q, order)
    s.run_started()
    s.round([
        Call("search_meaning", {"query": "attaching a GPS tracking device to a car and following its movements", "max_results": 4}, seed="jones-1-p8"),
        Call("search_exact", {"any_of": ["beeper"], "filters": {"opinion_types": ["majority"]}, "max_results": 4}),
    ])
    s.round([
        Call("search_meaning", {"query": "movements on public roads are visible to anyone", "filters": {"decided_to": "1990"}, "max_results": 3}, seed="knotts-1-p15"),
        Call("search_meaning", {"query": "a beeper inside a private home", "max_results": 3}, seed="karo-1-p19"),
        Call("read_passages", {"target": "jones-1-p9"}),
    ])
    s.round([gps_keep("jones-1-p8", "jones-1-p9", "knotts-1-p15", "karo-1-p19")])
    s.round([Call("submit_answer", {"out_of_scope": False,
                                    "update_skip_reason": "The question asks what the Court held about GPS trackers, so a search for later developments was not needed."})])
    must_keep_ok(s)
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
    finish_answered(s, spec)
    return s


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
]


@scenario
def token_ceiling_input(order):
    s = Sim("token-ceiling-input", PHONE_Q, order)
    s.run_started()
    for k, (sd1, q1, sd2, q2, rd) in enumerate(HEAVY_POOL):
        if s.next_call_would_cross_input():
            break
        calls = [Call("search_meaning", {"query": q1, "max_results": 6}, seed=sd1),
                 Call("search_meaning", {"query": q2, "max_results": 6}, seed=sd2),
                 Call("read_passages", {"target": rd, "before": 3, "after": 3})]
        if k == 1:
            calls.insert(0, phone_keep("riley-1-p26", "riley-1-p25", "riley-1-p66"))
        if k == 0:
            calls = phone_search_calls() + calls[2:]
        # a busy day: calls that failed and were retried still count toward the ceiling (T3.3), so the run reaches it sooner
        retries = {2: [("overloaded", 1_300), ("overloaded", 1_050)], 4: [("rate_limited", 900), ("overloaded", 1_200)]}.get(k)
        s.round(calls, retries=retries)
    assert s.next_call_would_cross_input(), "the pool ran out before the ceiling"
    must_keep_ok(s)
    finish_answered(s, PHONE_ANSWER, state="token_ceiling", stop_kind="token_ceiling_input")
    return s


# --- 6. The per-run output ceiling (T3.3): the last loop call is cut at max_tokens ------------------------------------------
@scenario
def token_ceiling_output(order):
    s = Sim("token-ceiling-output", THERMAL_Q, order)
    s.run_started()
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
    ]
    budget = int(settings.LOOP_OUTPUT_BUDGET.value)
    for calls in rounds:
        remaining = budget - s.loop_output_used()
        if remaining < 1_150:
            s.round([], cut_output=remaining)        # stopped by max_tokens: the call is paid for, nothing comes of it
            break
        s.round(calls, think=s.rng.randint(780, 900))
    assert s.loop_output_used() == budget
    must_keep_ok(s)
    finish_answered(s, THERMAL_ANSWER, state="token_ceiling", stop_kind="token_ceiling_output")
    return s


# --- 7. The time limit (T3.5): ten minutes, then the answer is built from what was kept ------------------------------------
@scenario
def time_limit_stop(order):
    s = Sim("time-limit-stop", PHONE_Q, order)
    s.run_started()
    slow = 34.0                                     # a slow day: each loop call takes a minute or two (below the 120 s deadline)
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
    for calls in rounds:
        if s.t / 1000 >= int(settings.RUN_DEADLINE_S.value):     # checked before each loop call (T3.5)
            break
        s.round(calls, latency_scale=slow)
    assert s.t / 1000 >= int(settings.RUN_DEADLINE_S.value), s.t
    must_keep_ok(s)
    finish_answered(s, PHONE_ANSWER, state="time_limit", stop_kind="time_limit")
    return s


# --- Refused submits (T1.10, T2.3, P4.3) -------------------------------------------------------------------------------------
COPY_LEAD = ("In a ruling this week the court of appeals held that police must obtain a warrant before using a thermal imaging "
             "device to scan the exterior of a home from a public street.")
COPIED = ("The court of appeals held that police must obtain a warrant before using a thermal imaging device to scan the "
          "exterior of a home from a public street.")


@scenario
def submit_refused_copy_guard(order):
    s = Sim("submit-refused-copy-guard", THERMAL_Q, order)
    s.run_started()
    s.round(thermal_search_calls())
    s.round([thermal_keep("kyllo-1-p1", "kyllo-1-p14", "kyllo-1-p7"),
             Call("search_web_updates", {"query": "thermal imaging warrant court of appeals ruling", "start_published_date": "2026-06-30",
                                         "category": "news", "num_results": 3},
                  web=Web(pages=[page("Appeals court rules on thermal scans of homes", "news.example.test", "thermal-ruling", "2026-09-17", 3600, "Sample Staff"),
                                 page("Thermal imaging: what officers may use", "explainer.example.test", "thermal-explainer", "2026-08-05", 2950)]))])
    # the page text is synthetic; the first page's text is what a copied statement would repeat
    s.pages["web-1-1"] = WebPage(**{**asdict(s.pages["web-1-1"]), "text": page_text("thermal-ruling", 3600, COPY_LEAD)})
    s.round([Call("submit_answer", {"out_of_scope": False, "update_findings": [
        {"statement": "A sample news page reports an appeals court ruling on thermal scans of homes.", "sources": ["web-3-1"]},
        {"statement": "A second sample page lists the devices officers may use without a warrant.", "sources": []}]})])
    s.round([Call("submit_answer", {"out_of_scope": False, "update_findings": [
        {"statement": COPIED, "sources": ["web-1-1"]},
        {"statement": "A second sample page discusses which devices officers use, without saying whether any ruling changed.", "sources": ["web-1-2"]}],
        "update_overview": "The sample pages describe a lower-court ruling and an explainer."})])
    s.round([Call("submit_answer", {"out_of_scope": False, "update_findings": [
        {"statement": "A sample news page reports that an appeals court addressed thermal scans of homes from the street and required a warrant for them.",
         "sources": ["web-1-1"]},
        {"statement": "A second sample page discusses which devices officers use, without saying whether any ruling changed.", "sources": ["web-1-2"]}],
        "update_overview": "The sample pages describe a lower-court ruling and an explainer."})])
    must_keep_ok(s)
    finish_answered(s, THERMAL_ANSWER)
    return s


@scenario
def submit_refused_basic_rules_then_declined(order):
    s = Sim("submit-refused-basic-rules-then-declined", PHONE_Q, order)
    s.run_started()
    s.round([Call("read_passages", {"target": "riley-1-p1"}), Call("read_passages", {"target": "riley-1-p999"}),
             Call("submit_answer", {"out_of_scope": False})])                       # rule 1: in the same turn as a read
    s.round([Call("submit_answer", {"out_of_scope": False})])                       # rule 2: a read alone is not a search
    s.round(phone_search_calls())
    s.round([Call("submit_answer", {"out_of_scope": False})])                       # rule 3: nothing kept, no note
    s.round([Call("keep_passages", {"keep": [K("riley-1-p26", PHONE_KEEPS["riley-1-p26"]), K("riley-1-p25", PHONE_KEEPS["riley-1-p25"]),
                                             K("riley-1-p67", "The last paragraph of the opinion.")]})])      # one id never shown
    s.round([Call("submit_answer", {"out_of_scope": False})])                       # rule 4: no update check, no reason: refused once
    s.round([Call("submit_answer", {"out_of_scope": False})])                       # accepted after the reminder: declined
    spec = [x for x in PHONE_ANSWER if all(pid != "riley-1-p66" for pid, _, _ in x["cites"])]
    finish_answered(s, spec)
    return s


# --- The update check unavailable (T2.4, P2.11) ------------------------------------------------------------------------------
def unavailable_run(slug, order, reason, *, at_start=False):
    s = Sim(slug, THERMAL_Q, order, update_available=not at_start, update_unavailable_reason=reason)
    s.run_started()
    s.round(thermal_search_calls())
    calls = [thermal_keep("kyllo-1-p1", "kyllo-1-p14", "kyllo-1-p7")]
    if not at_start:
        calls.append(Call("search_web_updates", {"query": "thermal imaging warrant ruling", "start_published_date": "2026-06-30", "num_results": 5},
                          web=Web(kind="unavailable", reason=reason)))
    s.round(calls)
    s.round([Call("submit_answer", {"out_of_scope": False})])        # rule 4 is waived while the check is unavailable
    must_keep_ok(s)
    finish_answered(s, THERMAL_ANSWER)
    return s


@scenario
def band_unavailable_no_credit(order):
    return unavailable_run("band-unavailable-no-credit", order, "no_credit")


@scenario
def band_unavailable_key_refused(order):
    return unavailable_run("band-unavailable-key-refused", order, "key_refused")


@scenario
def band_unavailable_credit_flag_at_start(order):
    return unavailable_run("band-unavailable-credit-flag-at-start", order, "no_credit", at_start=True)


# --- Every way an update search can end (T2.1, T2.4) -------------------------------------------------------------------------
@scenario
def update_search_statuses(order):
    s = Sim("update-search-statuses", PHONE_Q, order)
    s.run_started()
    s.round(phone_search_calls())
    s.round([phone_keep("riley-1-p26", "riley-1-p25", "riley-1-p66")])
    s.round([Call("search_web_updates", {"query": "cell phone search warrant arrest ruling", "start_published_date": "2026-6-30"})])    # refused by our code
    q = {"query": "cell phone search incident to arrest new decision", "start_published_date": "2026-06-30", "category": "news", "num_results": 4}
    s.round([Call("search_web_updates", q, web=Web(kind="refused_by_exa", exa_message="Invalid request: the combination of search type and category is not supported for this plan."))])
    s.round([Call("search_web_updates", {**q, "type": "lite"}, web=Web(kind="failed"))])
    s.round([Call("search_web_updates", {"query": "phone search arrest court", "start_published_date": "2026-06-30", "num_results": 4},
                  web=Web(pages=[page("Court notes on digital searches at arrest", "news.example.test", "arrest-notes", "2026-08-11", 2800),
                                 page("Local police update their phone-search policy", "city.example.test", "police-policy", "2026-09-02", 2150, "Sample Desk")]))])
    s.round([Call("search_web_updates", {"query": "phone search arrest policy", "num_results": 3})])       # the fourth: refused by our code
    s.round([Call("submit_answer", {"out_of_scope": False, "update_findings": [
        {"statement": "A sample page reports that a local police department updated its policy on searching phones after an arrest.", "sources": ["web-3-2"]}]})])
    must_keep_ok(s)
    finish_answered(s, PHONE_ANSWER)
    return s


# --- The Voyage warning, both codes (T3.3) -------------------------------------------------------------------------------------
@scenario
def voyage_warning_degraded(order):
    s = Sim("voyage-warning-degraded", THERMAL_Q, order)
    s.run_started()
    s.round([Call("search_meaning", {"query": "using a thermal imaging device on a house from a public street", "max_results": 6},
                  seed="kyllo-1-p5", voyage={"rerank": ["server_error", "server_error", "server_error"]}),
             thermal_search_calls()[1]])
    s.round([thermal_keep("kyllo-1-p1", "kyllo-1-p14", "kyllo-1-p7")])
    s.round([Call("submit_answer", {"out_of_scope": False, "update_skip_reason": "The question asks what the Court held in Kyllo, so a search for later developments was not needed."})])
    must_keep_ok(s)
    finish_answered(s, THERMAL_ANSWER)
    return s


@scenario
def voyage_warning_unavailable(order):
    s = Sim("voyage-warning-unavailable", THERMAL_Q, order)
    s.run_started()
    s.round([Call("search_meaning", {"query": "using a thermal imaging device on a house from a public street", "max_results": 6},
                  seed="kyllo-1-p5", voyage={"embed": ["rate_limited", "rate_limited", "rate_limited"]}),
             thermal_search_calls()[1]])
    s.round([Call("search_meaning", {"query": "using a thermal imaging device on a house from a public street", "max_results": 6}, seed="kyllo-1-p5")],
            text="Meaning search failed; trying it again, and using keyword search meanwhile.")
    s.round([thermal_keep("kyllo-1-p1", "kyllo-1-p14", "kyllo-1-p7")])
    s.round([Call("submit_answer", {"out_of_scope": False, "update_skip_reason": "The question asks what the Court held in Kyllo, so a search for later developments was not needed."})])
    must_keep_ok(s)
    finish_answered(s, THERMAL_ANSWER)
    return s


# --- Retries that worked: Anthropic (loop and composition) and Voyage (embed and rerank) (T3.3) ---------------------------------
@scenario
def retries_recovered(order):
    s = Sim("retries-anthropic-and-voyage-recovered", PHONE_Q, order)
    s.run_started()
    first = phone_search_calls()
    first[0].voyage = {"embed": ["server_error"], "rerank": ["rate_limited", "server_error"]}
    s.round(first, retries=[("rate_limited", 850)])
    s.round([phone_keep("riley-1-p26", "riley-1-p25", "riley-1-p66")])
    s.round([Call("submit_answer", {"out_of_scope": False, "update_skip_reason": "The question asks what the Court held in Riley, so a search for later developments was not needed."})])
    must_keep_ok(s)
    finish_answered(s, PHONE_ANSWER, retries=[("overloaded", 1_300)])
    return s


# --- Loop and composition failures (T3.3, T1.11, T5.4) --------------------------------------------------------------------------
@scenario
def error_stopped_after_retries(order):
    s = Sim("error-stopped-loop-retries-exhausted", THERMAL_Q, order)
    s.run_started()
    s.round(thermal_search_calls())
    s.round([thermal_keep("kyllo-1-p1", "kyllo-1-p14", "kyllo-1-p7")])
    ok = s.round([Call("search_exact", {"any_of": ["\"general public use\""], "max_results": 3})],
                 retries=[("overloaded", 1_500), ("overloaded", 1_200)], fail=("overloaded", 1_400))
    assert not ok
    must_keep_ok(s)
    s.compose(THERMAL_ANSWER)
    s.emit_band()
    s.end("error_stopped", answer_end="complete", failure_reason="overloaded")
    return s


@scenario
def composition_incomplete(order):
    s = Sim("composition-incomplete-stream-broken", THERMAL_Q, order)
    s.run_started()
    s.round(thermal_search_calls())
    s.round([thermal_keep("kyllo-1-p1", "kyllo-1-p14", "kyllo-1-p7")])
    s.round([Call("submit_answer", {"out_of_scope": False, "update_skip_reason": "The question asks what the Court held in Kyllo, so a search for later developments was not needed."})])
    must_keep_ok(s)
    s.compose(THERMAL_ANSWER, incomplete_after=3)
    s.emit_band()
    s.end("answered", answer_end="incomplete", failure_reason="stream_broken")     # the loop finished; the composition broke (contract section 6, v1.1)
    return s


@scenario
def composition_failed(order):
    s = Sim("composition-failed-before-first-block", PHONE_Q, order)
    s.run_started()
    s.round(phone_search_calls())
    s.round([phone_keep("riley-1-p26", "riley-1-p25", "riley-1-p66")])
    s.round([Call("submit_answer", {"out_of_scope": False, "update_skip_reason": "The question asks what the Court held in Riley, so a search for later developments was not needed."})])
    must_keep_ok(s)
    got = s.compose(PHONE_ANSWER, retries=[("server_error", 700), ("server_error", 650)], fail=("server_error", 800))
    assert not got
    s.emit_band()
    s.end("failed", answer_end="none", failure_reason="server_error")
    return s


@scenario
def answer_cut_off(order):
    s = Sim("answer-cut-off-length-limit", GPS_Q, order)
    s.run_started()
    gps_compact_rounds(s)
    spec = GPS_ANSWER[:5] + [T("Justice Sotomayor, concurring, wrote that GPS monitoring generates a precise, comprehensive record of a person's public movements that reflects a wealth of detail about her familial, political, profes")]
    finish_answered(s, spec, answer_end="cut_off", stop_kind="composition_max_tokens", cut_off=True)
    return s


@scenario
def failed_nothing_kept(order):
    s = Sim("failed-nothing-kept", THERMAL_Q, order)
    s.run_started()
    s.round(thermal_search_calls())
    ok = s.round([thermal_keep("kyllo-1-p14")], retries=[("server_error", 900), ("server_error", 1_100)], fail=("server_error", 1_000))
    assert not ok
    s.emit_band()
    s.end("failed", answer_end="none", failure_reason="server_error")
    return s


@scenario
def refusal(order):
    s = Sim("refusal", "How can I avoid being tracked by police while committing a crime?", order)
    s.run_started()
    ok = s.round([Call("search_meaning", {"query": "avoiding police tracking", "max_results": 4}, seed="jones-2-p4")], refusal=True)
    assert not ok
    s.emit_band()
    s.end("refusal", answer_end="none", failure_reason="refusal")
    return s


@scenario
def spend_limit_console(order):
    s = Sim("spend-limit-console", THERMAL_Q, order)
    s.run_started()
    s.round(thermal_search_calls())
    s.round([thermal_keep("kyllo-1-p1", "kyllo-1-p14")])
    ok = s.round([Call("search_exact", {"any_of": ["\"general public use\""], "max_results": 3})], fail=("spend_limit", 600))
    assert not ok
    s.emit_band()
    s.end("spend_limit", stop_kind="console_spend_limit", answer_end="none")
    return s


@scenario
def spend_limit_tier_cap(order):
    s = Sim("spend-limit-tier-cap", PHONE_Q, order)
    s.run_started()
    s.round(phone_search_calls())
    s.round([phone_keep("riley-1-p26", "riley-1-p25"),
             Call("search_web_updates", {"query": "cell phone search arrest court decision", "start_published_date": "2026-06-30", "num_results": 3},
                  web=Web(pages=[page("Notes on phone searches after arrest", "news.example.test", "phone-notes", "2026-07-30", 2600)]))])
    ok = s.round([Call("search_exact", {"any_of": ["\"get a warrant\""], "filters": {"cases": ["riley"]}, "max_results": 3})], fail=("spend_cap", 450))
    assert not ok
    s.emit_band()
    s.end("spend_limit", stop_kind="tier_spend_cap", answer_end="none")
    return s


def gps_compact_rounds(s):
    """Three short rounds and an accepted submit on the GPS topic (shared by the cut-off stream)."""
    s.round([
        Call("search_meaning", {"query": "attaching a GPS tracking device to a car and following its movements", "max_results": 4}, seed="jones-1-p8"),
        Call("search_exact", {"any_of": ["beeper"], "filters": {"opinion_types": ["majority"]}, "max_results": 4}),
    ])
    s.round([
        Call("search_meaning", {"query": "movements on public roads are visible to anyone", "filters": {"decided_to": "1990"}, "max_results": 3}, seed="knotts-1-p15"),
        Call("search_meaning", {"query": "a beeper inside a private home", "max_results": 3}, seed="karo-1-p19"),
        Call("read_passages", {"target": "jones-1-p9"}),
        Call("search_meaning", {"query": "GPS monitoring creates a precise, comprehensive record of a person's public movements",
                                "filters": {"opinion_types": ["concurrence"]}, "max_results": 3}, seed="jones-2-p4"),
    ])
    s.round([gps_keep("jones-1-p8", "jones-1-p9", "knotts-1-p15", "karo-1-p19", "jones-2-p4")])
    s.round([Call("submit_answer", {"out_of_scope": False,
                                    "update_skip_reason": "The question asks what the Court held about GPS trackers, so a search for later developments was not needed."})])
    must_keep_ok(s)


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
def replay_geofence_before_chatrie(order):
    s = Sim("replay-geofence-before-chatrie", GEO_Q, order, label="before_chatrie")
    s.run_started()
    s.round([
        Call("search_meaning", {"query": "whether obtaining a person's location history from a company with a warrant is a search", "max_results": 6}, seed="carpenter-1-p40"),
        Call("search_exact", {"any_of": ["\"tower dumps\"", "\"tower dump\"", "geofence"], "max_results": 4}),
    ])
    s.round([
        Call("search_meaning", {"query": "information handed to a company is still protected when it reveals a person's whereabouts", "max_results": 5}, seed="carpenter-1-p37"),
        Call("search_meaning", {"query": "a person who conveys information to a third party assumes the risk it will be passed to the Government",
                                "filters": {"decided_to": "1990"}, "max_results": 3}, seed="smith-1-p16"),
        Call("search_meaning", {"query": "reconsidering the rule that information shared with third parties is unprotected", "filters": {"opinion_types": ["concurrence"]},
                                "max_results": 3}, seed="jones-2-p7"),
    ])
    s.round([Call("keep_passages", {"keep": [K(i, GEO_KEEPS[i]) for i in GEO_KEEPS]})])
    s.round([Call("search_web_updates", {"query": "Supreme Court geofence warrant decision", "start_published_date": "2018-06-23", "end_published_date": "2026-10-24",
                                         "category": "news", "num_results": 5},
                  web=Web(pages=[page("Court issues its decision in Chatrie v. United States", "news.example.test", "chatrie-decision", "2026-06-29", 3900, "Sample Staff"),
                                 page("What the geofence decision means for location history", "review.example.test", "geofence-meaning", "2026-07-01", 4000, "Sample Contributor"),
                                 page("Notes on a geofence ruling", "journal.example.test", "geofence-notes", None, 2700)]))],
            text="The corpus ends at 2018, so checking the web for later decisions.")
    s.round([Call("submit_answer", {"out_of_scope": False, "update_findings": [
        {"statement": "A sample news page reports that the Supreme Court issued its decision in Chatrie v. United States, a case about a geofence warrant, on June 29, 2026.",
         "sources": ["web-1-1"]},
        {"statement": "A sample commentary page discusses what that decision means for requests for location history.", "sources": ["web-1-2"]}],
        "update_overview": "The sample pages report a Supreme Court decision on geofence warrants after the corpus's last case. The corpus does not contain it."})])
    must_keep_ok(s)
    finish_answered(s, GEO_ANSWER)
    return s


def build_all():
    out = []
    for i, fn in enumerate(SCENARIOS):
        out.append(fn(i))
    return out
def summarise(s):
    for e in s.events:
        d = e["data"]
        if e["kind"] == "tool_result":
            print(f"   n={e['n']} {d['name']} err={d['is_error']} found={d.get('found')} again={d.get('matched_again')} read={d.get('read')} "
                  f"kept={[k['id'] for k in d.get('kept', [])]} refused={[r['id'] for r in d.get('refused', [])]} submit={d.get('submit')} web={d.get('web_status')}")
        elif e["kind"] in ("run_ended", "checks", "update_band", "paused", "resumed", "warning"):
            print(f"   n={e['n']} {e['kind']} t={e['t_ms']} " + jdump({k: v for k, v in d.items() if k not in ("totals", "pages", "searches")})[:500])
            if e["kind"] == "run_ended":
                t = d["totals"]
                print("   totals", jdump({k: t[k] for k in ("claude", "exa", "voyage")}))


# ===============================================================================================================
# HTTP fixtures (contract §5, §5.1)
# ===============================================================================================================
JSON_H = {"Content-Type": "application/json"}


def write_http(name: str, description: str, method: str, path: str, status: int, headers: dict, body: str) -> None:
    HTTP_DIR.mkdir(parents=True, exist_ok=True)
    d = {"description": description, "method": method, "path": path, "status": status, "headers": headers, "body": body}
    (HTTP_DIR / f"{name}.json").write_text(json.dumps(d, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def error_body(code: str, message: str) -> str:
    return json.dumps({"error": code, "message": message}, separators=(",", ":"))


def health(live: str, update: str) -> str:
    return json.dumps({"app": "probable-clause", "ready": True, "live_research": live, "update_check": update, "commit": "fixture"},
                      separators=(",", ":"))


def sse_frame(e: dict) -> str:
    return f"id: {e['n']}\nevent: {e['kind']}\ndata: {jdump(e)}\n\n"


def write_all_http(sims: list) -> None:
    first_sim = next(x for x in sims if x.slug == "out-of-scope-reply")
    run_id = first_sim.run                      # the HTTP samples and the stream sample describe the same run
    write_http("health-ready", "GET /health when loading is complete and live research is open (contract section 5).", "GET", "/health", 200,
               JSON_H, health("open", "available"))
    write_http("health-paused-day", "GET /health when today's cap would be exceeded: live research is paused until midnight, Chicago time.",
               "GET", "/health", 200, JSON_H, health("paused_day", "available"))
    write_http("health-paused-month", "GET /health when the month's cap would be exceeded, or after the Console spend limit ended a run.",
               "GET", "/health", 200, JSON_H, health("paused_month", "available"))
    write_http("health-unknown", "GET /health when Atlas did not answer within the short timeout: both fields are unknown.",
               "GET", "/health", 200, JSON_H, health("unknown", "unknown"))
    plain = {"Content-Type": "text/plain; charset=utf-8"}
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
    write_http("post-runs-201", "POST /runs accepted: a random, unguessable run ID.", "POST", "/runs", 201, JSON_H, json.dumps({"run_id": run_id}, separators=(",", ":")))
    write_http("post-runs-400-question-empty", "POST /runs with an empty or whitespace-only question (refused before any paid call).", "POST", "/runs", 400, JSON_H,
               error_body("question_empty", "The question is empty after control characters were removed."))
    write_http("post-runs-400-question-too-long", "POST /runs with a question over QUESTION_MAX_CHARS.", "POST", "/runs", 400, JSON_H,
               error_body("question_too_long", f"The question is longer than {int(settings.QUESTION_MAX_CHARS.value)} characters."))
    write_http("post-runs-413-body-too-large", "POST /runs with a body over REQUEST_BODY_MAX_BYTES.", "POST", "/runs", 413, JSON_H,
               error_body("body_too_large", f"The request body is larger than {int(settings.REQUEST_BODY_MAX_BYTES.value)} bytes."))
    write_http("post-runs-503-paused-day", "POST /runs when the Chicago day's cap would be exceeded (the daily cap). Authoritative over /health.", "POST", "/runs", 503, JSON_H,
               error_body("paused_day", "The run's worst case would take today's spend past the daily cap."))
    write_http("post-runs-503-paused-month", "POST /runs when the month's cap would be exceeded, or while the Anthropic spend-limit flag is set.", "POST", "/runs", 503, JSON_H,
               error_body("paused_month", "The run's worst case would take this month's spend past the monthly cap."))
    write_http("post-runs-503-atlas-unreachable", "POST /runs when Atlas cannot be reached: fail closed, no paid run.", "POST", "/runs", 503, JSON_H,
               error_body("atlas_unreachable", "The spending records could not be reached, so no run was started."))
    first = first_sim.events
    body = sse_frame(first[0]) + ": keep-alive\n\n" + "".join(sse_frame(e) for e in first[1:4])
    write_http("get-events-200-stream", "GET /runs/{id}/events: the first part of a stream (a keep-alive comment line sits between frames). X-Accel-Buffering: no keeps the gateway from buffering it.",
               "GET", f"/runs/{run_id}/events", 200,
               {"Content-Type": "text/event-stream; charset=utf-8", "Cache-Control": "no-cache", "X-Accel-Buffering": "no"}, body)
    write_http("get-events-404-run-unknown", "GET /runs/{id}/events for a run that never existed or has expired (the page says the run is no longer stored).",
               "GET", f"/runs/{run_id}/events", 404, JSON_H, error_body("run_unknown", "No such run, or its events have expired."))
    write_http("post-alive-204", "POST /runs/{id}/alive: the heartbeat was recorded. No body.", "POST", f"/runs/{run_id}/alive", 204, {}, "")
    write_http("post-alive-404-run-unknown", "POST /runs/{id}/alive for an unknown or expired run.", "POST", f"/runs/{run_id}/alive", 404, JSON_H,
               error_body("run_unknown", "No such run, or its events have expired."))


def reconnect_document(src: "Sim") -> dict:
    """The events after a Last-Event-ID: the answered run, picked up when its fifth round begins."""
    idx = next(i for i, e in enumerate(src.events) if e["kind"] == "round_started" and e["data"]["round"] == 5)
    after = src.events[idx - 1]["n"]
    doc = src.document(extra_top={"after": after}, events=[e for e in src.events if e["n"] > after])
    doc["slug"] = f"{src.slug}-after-n{after}"
    return doc


def main():
    only = sys.argv[sys.argv.index("--only") + 1] if "--only" in sys.argv else None
    sims = build_all()
    docs = [(s, s.document()) for s in sims]
    docs.append((None, reconnect_document(next(s for s in sims if s.slug == "answered-phone-location-records"))))
    wanted = {d["slug"] for _, d in docs}
    for f in EVENTS_DIR.glob("*.json"):            # a renamed or removed scenario leaves no stale file behind
        if f.stem not in wanted and not only:
            f.unlink()
    for s, doc in docs:
        if only and doc["slug"] != only:
            continue
        path = write_stream(doc)
        print(f"{path.name}: {len(doc['events'])} events, {path.stat().st_size} bytes")
        if s is not None and "--summary" in sys.argv:
            summarise(s)
    if not only:
        write_all_http(sims)
        total = sum(p.stat().st_size for p in EVENTS_DIR.glob("*.json"))
        print(f"{len(docs)} event files, {total} bytes; {len(list(HTTP_DIR.glob('*.json')))} http files")


if __name__ == "__main__":
    main()
