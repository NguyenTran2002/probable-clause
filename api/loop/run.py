"""The research loop and the composition call (contract §4.G; T1.2 to T1.14, T2.1 to T2.5, T3.1 to T3.7,
P4.3 to P4.10).

`execute_run(ctx, deps)` emits run_started ... run_ended and returns normally for every expected end, RunStopped
included. H holds the run (RunContext): the gate before every paid call, the pricing and the one emitter of
`paid_call`. This module never touches the store, the reservation or Atlas.

Logs hold run IDs, rounds, call numbers, outcomes, error kinds, timings and counts, never the question, Claude's
queries, the answer or page text (T3.7).
"""

import asyncio
import copy
import json
import logging
import math
import time
import weakref
from dataclasses import asdict, dataclass, field

import anyio

from api import settings
from api.checks import CorpusWords, check_answer, check_update_findings, copy_guard_report, corpus_words, pages_named
from api.corpus.filters import excluded_by_none_of, matches, parse_filters
from api.corpus.keyword import KeywordIndex
from api.corpus.store import Corpus
from api.errors import ServiceError, ToolInputError
from api.loop import format as fmt
from api.loop import prompts
from api.loop.prompts import rejection
from api.loop.streamer import AnthropicStreamer, StreamResult
from api.loop.streamer import raw_usage as usage_object
from api.loop.tools import (STRICT_TOOLS, TOOL_NAMES, check_fields, max_results, string_list,
                            text_field, tools as build_tool_list, whole_number)
from api.retry import ANTHROPIC_POLICY, with_retries
from api.search.meaning import UNAVAILABLE_NOTE, MeaningIndex
from api.search.voyage import VoyageClient
from api.state.prices import failed_attempt_usage
from api.types import KeptPassage, RunContext, RunStopped, Usage, WebPage
from api.web_updates import UpdateSearch, fixed_settings, format_for_claude, format_for_events, params_as_dict, parse_params

log = logging.getLogger("probable_clause.loop")


def _v(s: settings.Setting):
    return s.value


LOOP_MODEL = str(_v(settings.LOOP_MODEL))
LOOP_EFFORT = str(_v(settings.LOOP_EFFORT))
COMPOSITION_MODEL = str(_v(settings.COMPOSITION_MODEL))
COMPOSITION_EFFORT = str(_v(settings.COMPOSITION_EFFORT))
MAX_ROUNDS = int(_v(settings.MAX_ROUNDS))
LOOP_INPUT_BUDGET = int(_v(settings.LOOP_INPUT_BUDGET))
LOOP_OUTPUT_BUDGET = int(_v(settings.LOOP_OUTPUT_BUDGET))
COMPOSITION_MAX_TOKENS = int(_v(settings.COMPOSITION_MAX_TOKENS))
COMPOSITION_RESERVE_INPUT = int(_v(settings.COMPOSITION_RESERVE_INPUT))
FIXED_PREFIX_TOKENS = int(_v(settings.FIXED_PREFIX_TOKENS_ESTIMATE))
LOOP_CALL_DEADLINE_S = float(_v(settings.LOOP_CALL_DEADLINE_S))
COMPOSITION_CALL_DEADLINE_S = float(_v(settings.COMPOSITION_CALL_DEADLINE_S))
UPDATE_SEARCHES = int(_v(settings.UPDATE_SEARCHES_PER_RUN))
KEEP_CAP = int(_v(settings.KEEP_CAP))
KEEP_REASON_MAX = int(_v(settings.KEEP_REASON_MAX_CHARS))
COPY_GUARD_WORDS = int(_v(settings.COPY_GUARD_WORDS))
NOTE_MAX = int(_v(settings.NOTE_MAX_CHARS))
MAX_ATTEMPTS = ANTHROPIC_POLICY.retries + 1

# P4.3: the stored and streamed tool_call of a refused submit carries this in place of each flagged statement.
WITHHELD = "[statement withheld: it repeated a page's words]"

# T3.3: errors after retries that are our fault or the account's end the run with no further calls; every other
# kind left after retries composes from what was kept.
# GAP: T3.3 lists 400, 401, 403, 404 and 413 as our fault or the account's; this set is those kinds and nothing more.
FATAL_KINDS = frozenset({"bad_request", "auth", "permission", "not_found", "too_large"})
SPEND_STOP = {"spend_limit": "console_spend_limit", "spend_cap": "tier_spend_cap"}      # §6, T3.4
LIMIT_STATE = {"step_limit": "step_limit", "token_ceiling_input": "token_ceiling",
               "token_ceiling_output": "token_ceiling", "time_limit": "time_limit"}
WARNINGS = (("meaning_degraded", "meaning_search_degraded"), ("meaning_unavailable_once", "meaning_search_unavailable"))


@dataclass
class LoopDeps:
    corpus: Corpus
    keyword: KeywordIndex
    meaning: MeaningIndex
    voyage: VoyageClient
    updates: UpdateSearch
    anthropic: AnthropicStreamer


async def execute_run(ctx: RunContext, deps: LoopDeps) -> None:
    """Emits run_started ... run_ended; returns normally for every expected end, RunStopped included (§4.G)."""
    await _Run(ctx, deps).execute()


# ---------- tokens (T3.3) ----------

_RATIO: "weakref.WeakKeyDictionary[Corpus, float]" = weakref.WeakKeyDictionary()


def chars_per_token(corpus: Corpus) -> float:
    """The corpus's own ratio: its paragraphs' characters over the manifest's token count (counted with the loop
    model's tokenizer). Paragraph characters only, so the ratio errs low and estimates err high."""
    if corpus not in _RATIO:
        chars = sum(len(p.text) for p in corpus.passages.values() if p.kind == "paragraph")
        _RATIO[corpus] = chars / max(1, int(corpus.manifest["core_tokens"]))
    return _RATIO[corpus]


_EXEMPT: "weakref.WeakKeyDictionary[Corpus, CorpusWords]" = weakref.WeakKeyDictionary()


def corpus_exemption(corpus: Corpus) -> CorpusWords:
    """The corpus's words for the copy guard (P4.9), built once per corpus from its passages' texts (about 2 MB,
    under a tenth of a second), on the first guarded submit: a run of words also found in one passage is the Court's,
    so a page quoting it is not copied by a text quoting it too."""
    if corpus not in _EXEMPT:
        _EXEMPT[corpus] = corpus_words(p.text for p in corpus.passages.values())
    return _EXEMPT[corpus]


def usage_from_raw(raw: dict, model: str, *, estimated: bool = False) -> Usage:
    """Claude's usage object as E prices it. Cache writes the API did not attribute to a TTL are counted at the
    1-hour rate, the dearer one (T3.4: the conservative figure)."""
    cc = raw.get("cache_creation") or {}
    w5 = int(cc.get("ephemeral_5m_input_tokens") or 0)
    w1 = int(cc.get("ephemeral_1h_input_tokens") or 0)
    writes = int(raw.get("cache_creation_input_tokens") or 0)
    if writes > w5 + w1:
        w1 += writes - (w5 + w1)
    return Usage(service="anthropic", model=model, input_tokens=int(raw.get("input_tokens") or 0),
                 cache_write_5m_tokens=w5, cache_write_1h_tokens=w1,
                 cache_read_tokens=int(raw.get("cache_read_input_tokens") or 0),
                 output_tokens=int(raw.get("output_tokens") or 0), estimated=estimated)


def total_input(u: Usage) -> int:
    """All input: uncached, cache writes and cache reads (T3.3, §6.2)."""
    return u.input_tokens + u.cache_write_5m_tokens + u.cache_write_1h_tokens + u.cache_read_tokens


# ---------- the citation mapping (T1.9, §6): honesty-critical ----------

def _spacing_aside(text) -> str:
    return " ".join(text.split()) if isinstance(text, str) else ""


def map_citations(block: dict, documents: list[str], corpus: Corpus, call_no: int,
                  content_index: int) -> tuple[list[dict], int, int]:
    """Each content_block_location citation of an answer block, mapped back to our passage and an inclusive range
    of its sentences. `document_index` indexes the composition request's documents (one per kept passage, in
    `documents`' order); the API's `end_block_index` is exclusive, so `last_sentence = end_block_index - 1`
    (https://platform.claude.com/docs/en/build-with-claude/citations: "Content block indices are 0-indexed with
    exclusive end indices", read Oct 24, 2026). A citation that does not point inside a document is dropped, never
    guessed; one whose `cited_text` disagrees with our slice of those sentences, spacing aside, is not attached
    either (v1.3), so the page never lights sentences Claude did not cite. Returns (citations, dropped, mismatched)."""
    out: list[dict] = []
    dropped = mismatched = 0
    for c in block.get("citations") or []:
        if not isinstance(c, dict) or c.get("type") != "content_block_location":
            dropped += 1
            continue
        di, s, e = c.get("document_index"), c.get("start_block_index"), c.get("end_block_index")
        if not all(isinstance(x, int) and not isinstance(x, bool) for x in (di, s, e)) or not 0 <= di < len(documents):
            dropped += 1
            continue
        p = corpus.passages[documents[di]]
        if not 0 <= s < e <= len(p.sentences):
            dropped += 1
            continue
        first, last = s, e - 1
        cited = p.text[p.sentences[first][0]:p.sentences[last][1]]
        if _spacing_aside(c.get("cited_text")) != _spacing_aside(cited):
            mismatched += 1
            log.error("composition call %d: mapping fault: a citation's cited_text disagrees with %s sentences %d-%d "
                      "(document %d); not attached", call_no, p.id, first, last, di)
            continue
        out.append({"passage_id": p.id, "first_sentence": first, "last_sentence": last, "cited_text": cited,
                    "call_no": call_no, "path": f"content[{content_index}]"})
    return out, dropped, mismatched


def band_outcome(*, searches_counted: int, submitted: bool, findings: list, unavailable: bool,
                 skip_reason: str | None, declined: bool) -> tuple[str, str | None]:
    """The update band's outcome, worked out by code (T2.3 item 4, §6). Returns (outcome, reason)."""
    if searches_counted > 0:
        if not submitted:
            return "not_summarised", None
        return ("found" if findings else "nothing_relevant"), None
    if unavailable:
        return "unavailable", None
    if submitted and skip_reason:
        return "skipped", skip_reason
    if submitted and declined:
        return "declined", None
    return "not_run", None


def sort_documents(ids, corpus: Corpus) -> list[str]:
    """T1.11: decision date, then opinion, then position: the corpus's reading order within a date (case, opinion,
    paragraphs, then footnotes)."""
    order = {pid: i for i, pid in enumerate(corpus.passages)}
    return sorted(ids, key=lambda pid: (corpus.passages[pid].decided, order[pid]))


def withhold_flagged(inp: dict, flagged: set[int], overview_flagged: bool, *, note_flagged: bool = False,
                     skip_reason_flagged: bool = False) -> dict:
    """P4.3: the input as stored, each flagged statement replaced; a flagged overview, a flagged note (P4.8) and a
    flagged update skip reason (P4.13) replaced by the same text."""
    shown = copy.deepcopy(inp)
    findings = shown.get("update_findings")
    for i in flagged:
        if isinstance(findings, list) and 0 <= i < len(findings) and isinstance(findings[i], dict):
            findings[i]["statement"] = WITHHELD
    if overview_flagged:
        shown["update_overview"] = WITHHELD
    if note_flagged:
        shown["note"] = WITHHELD
    if skip_reason_flagged:
        shown["update_skip_reason"] = WITHHELD
    return shown


# ---------- internals ----------

class _BudgetStop(Exception):
    """A retry would cross the run's token ceiling (T3.3, T3.4)."""
    def __init__(self, kind: str):
        super().__init__(kind)
        self.kind = kind


@dataclass
class _End:
    kind: str                       # submitted | step_limit | token_ceiling_* | time_limit | error_stopped | failed |
    failure_reason: str | None = None   # refusal | spend_limit | abandoned
    stop_kind: str | None = None


@dataclass
class _Out:
    blocks: list[str]
    is_error: bool = False
    extra: dict = field(default_factory=dict)
    event_content: str | None = None                       # what the event stores, where it differs (web)
    block_pids: list[tuple[str, int]] = field(default_factory=list)   # (passage, block) for request fragments
    resp_pids: list[str] = field(default_factory=list)                 # passages the tool_use block names


@dataclass
class _Broken:
    error: ServiceError


@dataclass
class _Comp:
    outcome: str                    # complete | cut_off | incomplete | failed | refused | spend | abandoned
    kind: str | None = None
    stop_kind: str | None = None


_SCHEMA_CHECKED: "weakref.WeakSet" = weakref.WeakSet()
_BACKGROUND: set = set()
_PROMPT_CACHE: "weakref.WeakKeyDictionary[Corpus, str]" = weakref.WeakKeyDictionary()


def _loop_system(corpus: Corpus) -> str:
    if corpus not in _PROMPT_CACHE:
        _PROMPT_CACHE[corpus] = prompts.loop_system(corpus)
    return _PROMPT_CACHE[corpus]


async def retry_sleep(seconds: float) -> None:
    """The wait between retries (a test seam; api/retry.py's waits, T3.3)."""
    await asyncio.sleep(seconds)


def _ms(t0: float) -> int:
    return max(0, int((time.monotonic() - t0) * 1000))


class _Attempts:
    """The attempts of one Claude call, each recorded once (T3.3). A failed attempt is recorded `retrying` only once
    the next attempt has passed the budget check and the gate; if either stops it, the failed attempt is recorded
    `failed`, so no record says `retrying` without an attempt after it."""

    def __init__(self, run: "_Run", purpose: str, model: str, call_no: int, est_input: int):
        self.run, self.purpose, self.model, self.call_no, self.est = run, purpose, model, call_no, est_input
        self.attempt = 1
        self.t0 = time.monotonic()
        self.ms, self.raw, self.chars = 0, None, 0
        self.pending: tuple | None = None          # (attempt, error kind, usage, usage object, duration)

    def failed_now(self, e: ServiceError) -> None:
        self.ms = _ms(self.t0)
        self.raw = getattr(e, "raw_usage", None)
        self.chars = getattr(e, "streamed_chars", 0) or 0

    async def on_retry(self, next_attempt: int, error: ServiceError, wait_s: float) -> None:
        usage, shown = self.run.failure_usage(self.model, self.raw, self.est, self.chars)
        self.pending = (next_attempt - 1, error.kind, usage, shown, self.ms)
        log.info("run %s: %s call %d attempt %d failed (%s); retrying in %.1f s", self.run.ctx.run_id, self.purpose,
                 self.call_no, next_attempt - 1, error.kind, wait_s)

    async def flush(self, outcome: str) -> None:
        if self.pending is not None:
            attempt, kind, usage, shown, ms = self.pending
            self.pending = None
            await self.run.record_usage(self.purpose, usage, shown, call_no=self.call_no, attempt=attempt,
                                        outcome=outcome, error_kind=kind, duration_ms=ms)

    async def gate(self, n: int, budget=None) -> None:
        self.attempt = n
        if self.pending is not None:
            try:
                if budget is not None:
                    budget(self.pending[2])
                await self.run.ctx.before_paid_call("anthropic", self.purpose)
            except (_BudgetStop, RunStopped):
                await self.flush("failed")
                raise
            await self.flush("retrying")
        else:
            await self.run.ctx.before_paid_call("anthropic", self.purpose)
        self.t0 = time.monotonic()

    async def completed(self, res: StreamResult, outcome: str, kind) -> Usage:
        return await self.run.record_usage(self.purpose, usage_from_raw(res.usage, self.model), res.usage,
                                           call_no=self.call_no, attempt=self.attempt, outcome=outcome,
                                           error_kind=kind, duration_ms=_ms(self.t0))

    async def failed_finally(self, e: ServiceError) -> None:
        await self.flush("failed")         # never left pending (with_retries raises without a further attempt)
        usage, shown = self.run.failure_usage(self.model, self.raw, self.est, self.chars)
        await self.run.record_usage(self.purpose, usage, shown, call_no=self.call_no, attempt=self.attempt,
                                    outcome="failed", error_kind=e.kind, duration_ms=self.ms)


class _Run:
    def __init__(self, ctx: RunContext, deps: LoopDeps):
        self.ctx, self.deps, self.corpus = ctx, deps, deps.corpus
        self.system_text = _loop_system(self.corpus)
        self.tool_list = build_tool_list()
        self.ratio = chars_per_token(self.corpus)
        self.messages: list[dict] = []
        self.call_no = 0
        self.round_no = 0
        self.status_for_round = ""
        self.seen: set[str] = set()                 # passages whose text Claude was sent (T1.7)
        self.seen_before_turn: frozenset[str] = frozenset()   # what Claude had seen when it wrote this turn's calls
        self.stops: list[str] = []                  # every budget or limit stop, in order (v1.4)
        self.emitted: set[str] = set()              # passages with a `passage` event
        self.kept: dict[str, KeptPassage] = {}
        self.pending: list[tuple[str, int, int, int, str]] = []
        self.pages: dict[str, WebPage] = {}         # every page returned in the run; text only for Claude and the guard
        self.band_searches: list[dict] = []
        self.counted = 0                            # update searches that count (T2.1)
        self.seen_urls: dict[str, str] = {}
        self.corpus_searched = False
        self.reminded_round: int | None = None
        self.declined = False
        self.accepted: dict | None = None
        self.warned: set[str] = set()
        self.answer_texts: list[str] = []
        self.loop_input_used = 0                    # every loop attempt, actual or estimated (T3.3, T3.4)
        self.loop_output_used = 0
        self.last_ok: tuple[int, int, int] | None = None   # (total input, output, messages in that request)

    # -- events --
    async def emit(self, kind: str, data: dict) -> int:
        return await self.ctx.emit(kind, data)

    async def ensure_passage(self, pid: str) -> None:
        if pid not in self.emitted:
            self.emitted.add(pid)
            await self.emit("passage", fmt.passage_event(self.corpus.passages[pid]))

    def unavailable(self) -> bool:
        return (not self.ctx.update_check_available) or self.ctx.flags.exa_unavailable is not None

    def status_line(self, round_no: int) -> str:
        return prompts.status_line(round_no, len(self.kept), searches_counted=self.counted,
                                   unavailable=self.unavailable())

    def est(self, text: str) -> int:
        return math.ceil(len(text) / self.ratio)

    def est_json(self, obj) -> int:
        return self.est(json.dumps(obj, ensure_ascii=False))

    # -- the run --
    async def execute(self) -> None:
        if self.ctx.corpus_label != self.corpus.label:
            raise ValueError("the run's corpus label and the loaded corpus disagree")
        if not self.ctx.update_check_available and self.ctx.flags.exa_unavailable is None:
            self.ctx.flags.exa_unavailable = "no_credit"     # T2.4: the Atlas flag; no search is attempted
        log.info("run %s: started; %d strict tools", self.ctx.run_id, len(STRICT_TOOLS))
        cov = self.corpus.coverage
        await self.emit("run_started", {
            "question": self.ctx.question,
            "limits": {"rounds": MAX_ROUNDS, "input_tokens": int(_v(settings.RUN_INPUT_TOKENS)),
                       "output_tokens": int(_v(settings.RUN_OUTPUT_TOKENS)), "update_searches": UPDATE_SEARCHES,
                       "deadline_s": int(_v(settings.RUN_DEADLINE_S))},
            "coverage": {k: cov[k] for k in ("latest_decision_full_pull", "latest_decision_in_corpus", "ingested")},
            "update_check_available": bool(self.ctx.update_check_available),
            "models": {"loop": LOOP_MODEL, "composition": COMPOSITION_MODEL},
            "corpus_label": self.ctx.corpus_label,
        })
        first = [{"type": "text", "text": prompts.message("first_message", question=self.ctx.question)}]
        if not self.ctx.update_check_available:
            first.append({"type": "text", "text": prompts.unavailable_line(self.ctx.flags.exa_unavailable or "no_credit")})
        self.status_for_round = self.status_line(1)
        first.append({"type": "text", "text": self.status_for_round})
        self.messages.append({"role": "user", "content": first})
        end = await self.research()
        log.info("run %s: loop ended (%s) after %d rounds", self.ctx.run_id, end.kind, self.round_no)
        await self.finish(end)

    # -- the loop --
    def next_input_estimate(self) -> int:
        """The next loop call's input, estimated before it is sent (T3.3)."""
        if self.last_ok is None:
            prefix = max(FIXED_PREFIX_TOKENS, self.est(self.system_text) + self.est_json(self.tool_list))
            return prefix + sum(self.est_json(m["content"]) for m in self.messages)
        total, output, n = self.last_ok
        return total + output + sum(self.est_json(m["content"]) for m in self.messages[n + 1:])

    def output_left(self) -> int:
        return LOOP_OUTPUT_BUDGET - self.loop_output_used

    async def research(self) -> _End:
        try:
            while True:
                # Limits are checked before a round starts (T1.11, T3.3, T3.5).
                if self.round_no >= MAX_ROUNDS:
                    return _End("step_limit")
                if self.ctx.seconds_left() <= 0:
                    return _End("time_limit")
                if self.output_left() <= 0:
                    return _End("token_ceiling_output")
                est = self.next_input_estimate()
                if self.loop_input_used + est > LOOP_INPUT_BUDGET:
                    return _End("token_ceiling_input")
                self.round_no += 1
                await self.emit("round_started", {"round": self.round_no, "status_line": self.status_for_round})
                self.call_no += 1
                call_no = self.call_no
                try:
                    res = await self.loop_call(call_no, est)
                except _BudgetStop as b:
                    return _End(b.kind)
                except ServiceError as e:
                    return self.end_for_error(e)
                if res.stop_reason == "refusal":
                    return _End("refusal", failure_reason="refusal")
                self.messages.append({"role": "assistant", "content": res.content})
                if res.stop_reason == "max_tokens":
                    return _End("token_ceiling_output")       # T3.3: a loop call stopped by max_tokens
                results, accepted = await self.run_tools(res, call_no)
                if accepted:
                    return _End("submitted")
                self.status_for_round = self.status_line(self.round_no + 1)
                self.messages.append({"role": "user", "content": results + [{"type": "text", "text": self.status_for_round}]})
        except RunStopped as e:
            return _End("abandoned") if e.reason == "abandoned" else _End("time_limit")

    def end_for_error(self, e: ServiceError) -> _End:
        log.warning("run %s: loop call failed (%s)", self.ctx.run_id, e.kind)
        if e.kind in SPEND_STOP:
            return _End("spend_limit", stop_kind=SPEND_STOP[e.kind])
        if e.kind in FATAL_KINDS:
            return _End("failed", failure_reason=e.kind)
        # GAP: T3.3 composes after "transient failures"; our deadline, an unreadable reply, a protocol error and a
        # timeout are not in its list either way, and are treated as transient: the kept passages are composed.
        return _End("error_stopped", failure_reason=e.kind)

    def loop_request(self, max_tokens: int) -> dict:
        """One loop call (P2.1, T1.14, T3.3). Sources, read Oct 24, 2026:
        - thinking: adaptive (https://platform.claude.com/docs/en/build-with-claude/adaptive-thinking); display left
          at its default, omitted (T3.1);
        - effort: `output_config.effort` (https://platform.claude.com/docs/en/build-with-claude/effort);
        - caching: a 1-hour breakpoint on the system prompt (tools, system prompt and catalog come before it in the
          prefix), plus top-level automatic caching (5 minutes) for the growing conversation; a 1-hour entry must
          come before 5-minute ones (https://platform.claude.com/docs/en/build-with-claude/prompt-caching);
        - tool_choice left at auto: forced tool use is a 400 on this model
          (https://platform.claude.com/docs/en/api/errors, "Forced tool use not supported")."""
        return {
            "model": LOOP_MODEL,
            "max_tokens": max_tokens,
            "system": [{"type": "text", "text": self.system_text, "cache_control": {"type": "ephemeral", "ttl": "1h"}}],
            "tools": self.tool_list,
            "messages": list(self.messages),
            "thinking": {"type": "adaptive"},
            "output_config": {"effort": LOOP_EFFORT},
            "cache_control": {"type": "ephemeral"},
        }

    def est_chars(self, chars: int) -> int:
        return math.ceil(chars / self.ratio) if chars > 0 else 0

    def failure_usage(self, model: str, raw: dict | None, est_input: int, chars: int) -> tuple[Usage, dict | None]:
        """A failed attempt's usage (T3.3): what its stream reported, with output at least the tokens it streamed
        (estimated from the characters of the text, thinking and tool input, erring high); an attempt that reported
        nothing and streamed nothing is its input estimate at the uncached price, with no usage object."""
        out = self.est_chars(chars)
        if raw is None and out == 0:
            return failed_attempt_usage("anthropic", model, est_input), None
        shown = copy.deepcopy(raw) if raw is not None else usage_object(est_input)
        if out > int(shown.get("output_tokens") or 0):
            shown["output_tokens"] = out
        return usage_from_raw(shown, model, estimated=True), shown

    async def record_usage(self, purpose: str, usage: Usage, shown: dict | None, *, call_no: int, attempt: int,
                           outcome: str, error_kind, duration_ms: int) -> Usage:
        """One attempt, through H's record_usage (the agreed convention): `usage` is what E prices; `raw_usage` is
        Claude's usage object (marked estimated on a failed attempt), or None when it reported none (§6)."""
        await self.ctx.record_usage(usage, purpose=purpose, attempt=attempt, max_attempts=MAX_ATTEMPTS,
                                    outcome=outcome, error_kind=error_kind, duration_ms=duration_ms,
                                    raw_usage=shown, call_no=call_no)
        if purpose == "loop":
            self.loop_input_used += total_input(usage)
            self.loop_output_used += usage.output_tokens
        return usage

    async def loop_call(self, call_no: int, est: int) -> StreamResult:
        att = _Attempts(self, "loop", LOOP_MODEL, call_no, est)
        flushed = {"done": False}

        def budget(pending: Usage) -> None:
            # T3.4: every attempt counts toward the ceiling, so a retry never crosses it
            if self.loop_input_used + total_input(pending) + est > LOOP_INPUT_BUDGET:
                raise _BudgetStop("token_ceiling_input")
            if self.output_left() - pending.output_tokens <= 0:
                raise _BudgetStop("token_ceiling_output")

        async def before(n: int) -> None:
            await att.gate(n, budget)

        async def attempt(n: int) -> StreamResult:
            if not flushed["done"]:        # only once the gate has let the request go (a fragment is what was sent)
                flushed["done"] = True
                await self.flush_request_fragments(call_no)
            try:
                res = await self.deps.anthropic.stream(self.loop_request(self.output_left()), LOOP_CALL_DEADLINE_S, None)
            except ServiceError as e:
                att.failed_now(e)
                raise
            refused = res.stop_reason == "refusal"     # billed, so its usage is real (T3.3)
            usage = await att.completed(res, "failed" if refused else "ok", "refusal" if refused else None)
            if not refused:
                self.last_ok = (total_input(usage), usage.output_tokens, len(self.messages))
            log.info("run %s: loop call %d attempt %d %s, stop %s", self.ctx.run_id, call_no, n,
                     "refused" if refused else "ok", res.stop_reason)
            return res

        try:
            return await with_retries(attempt, ANTHROPIC_POLICY, before, att.on_retry, retry_sleep)
        except ServiceError as e:
            await att.failed_finally(e)
            raise

    async def flush_request_fragments(self, call_no: int) -> None:
        """T4.3(7): each passage's block in the previous round's tool result, before this call's paid_call (§6)."""
        for pid, mi, ti, bi, text in self.pending:
            await self.emit("api_fragment", {"passage_id": pid, "call_no": call_no, "role": "request",
                                             "path": f"messages[{mi}].content[{ti}].content[{bi}]",
                                             "json": {"type": "text", "text": text}})
        self.pending = []

    # -- the tools --
    async def run_tools(self, res: StreamResult, call_no: int) -> tuple[list[dict], bool]:
        """The turn's tools in Claude's order (§4.G). submit_answer must be the turn's only call: with any other
        call, or a second submit, every submit is refused and the other calls run as usual (P4.16, amending T1.10
        rule 1). Every tool_use gets its tool_call and tool_result; the results go back to Claude in Claude's order."""
        uses = [(ti, ci, b) for ti, (ci, b) in enumerate((i, b) for i, b in enumerate(res.content)
                                                         if b.get("type") == "tool_use")]
        same_turn = len(uses) > 1                                                 # rule 1, P4.16
        # T1.7: a keep may name only passages shown before this turn; this turn's results are not yet seen by Claude
        self.seen_before_turn = frozenset(self.seen)
        user_index = len(self.messages)          # the index the tool results' user message will have
        results: list[dict | None] = [None] * len(uses)
        accepted_any = False
        for ti, ci, b in uses:
            name, tid, inp = b.get("name"), b.get("id"), b.get("input")
            if name not in TOOL_NAMES:
                log.warning("run %s: Claude called an unknown tool", self.ctx.run_id)
                results[ti] = _tool_result(tid, [prompts.message("unknown_tool", name=name,
                                                                 tools=", ".join(TOOL_NAMES))], True)
                continue
            if name == "submit_answer":
                out, shown, accepted = self.submit(inp, same_turn)       # before tool_call: P4.3 needs the guard's result
                accepted_any = accepted_any or accepted
                await self.emit("tool_call", {"round": self.round_no, "tool_use_id": tid, "name": name, "input": shown})
            else:
                await self.emit("tool_call", {"round": self.round_no, "tool_use_id": tid, "name": name, "input": inp})
                try:
                    out = await self.execute_tool(name, inp)
                except RunStopped:
                    # The run stopped before this tool could finish: nothing was sent to Claude for it.
                    await self.emit("tool_result", {"tool_use_id": tid, "name": name, "is_error": True, "content": "",
                                                    **_empty_extra(name)})
                    raise
            await self.emit("tool_result", {"tool_use_id": tid, "name": name, "is_error": out.is_error,
                                            "content": out.event_content if out.event_content is not None
                                            else "\n\n".join(out.blocks), **out.extra})
            await self.emit_warnings()           # right after the result that set the flag
            for pid in dict.fromkeys(out.resp_pids):
                await self.emit("api_fragment", {"passage_id": pid, "call_no": call_no, "role": "response",
                                                 "path": f"content[{ci}]", "json": b})
            for pid, bi in out.block_pids:
                self.pending.append((pid, user_index, ti, bi, out.blocks[bi]))
            results[ti] = _tool_result(tid, out.blocks, out.is_error)
        return [r for r in results if r is not None], accepted_any

    async def execute_tool(self, name: str, inp) -> _Out:
        if name == "search_meaning":
            return await self.search_meaning(inp)
        if name == "search_exact":
            return await self.search_exact(inp)
        if name == "read_passages":
            return await self.read_passages(inp)
        if name == "keep_passages":
            return self.keep_passages(inp)
        return await self.search_web_updates(inp)

    async def show(self, pid: str, blocks: list[str], block_pids: list, mark: str | None = None) -> None:
        """Send one passage's block, with its attached footnotes; every passage sent gets its event first (§6)."""
        await self.ensure_passage(pid)
        bi = len(blocks)
        blocks.append(fmt.passage_block(self.corpus, pid, mark))
        block_pids.append((pid, bi))
        self.seen.add(pid)
        for f in self.corpus.attached_footnotes(pid):
            await self.ensure_passage(f.id)
            self.seen.add(f.id)
            block_pids.append((f.id, bi))

    async def assemble(self, ranked: list[str], limit: int, f) -> _Out:
        """New passages up to `limit`, passages already shown as one "matched again" line (T1.6)."""
        new, again, blocks, block_pids = [], [], [], []
        shown_now: set[str] = set()
        for pid in ranked:
            if pid in shown_now:
                continue
            if pid in self.seen:
                if pid not in again:
                    again.append(pid)
                continue
            before = len(block_pids)
            await self.show(pid, blocks, block_pids)
            shown_now.update(p for p, _ in block_pids[before:])
            new.append(pid)
            if len(new) >= limit:
                break
        if again:
            blocks.append(fmt.matched_again_line(again))
        if not new and not again:
            blocks.append(fmt.no_match_text(f))
        return _Out(blocks, False, {"found": new, "matched_again": again}, None, block_pids, new + again)

    async def search_meaning(self, inp) -> _Out:
        try:
            check_fields("search_meaning", inp, ("query", "filters", "max_results"), ("query",))
            query = text_field(inp, "query", required=True)
            f = parse_filters(inp.get("filters"), self.corpus)
            limit = max_results(inp.get("max_results"))
        except ToolInputError as e:
            return _Out([e.message], True, {"found": [], "matched_again": []})
        res = await self.deps.meaning.search(query, lambda p: matches(p, f) and not excluded_by_none_of(p, f),
                                             self.ctx, self.deps.voyage, sleep=retry_sleep)
        if res.status == "unavailable":
            return _Out([res.message_for_claude or UNAVAILABLE_NOTE], True,
                        {"found": [], "matched_again": [], "not_reranked": False})
        self.corpus_searched = True
        out = await self.assemble([h.passage_id for h in res.hits], limit, f)
        if res.status == "not_reranked" and res.message_for_claude:
            out.blocks.append(res.message_for_claude)
        out.extra["not_reranked"] = res.status == "not_reranked"
        return out

    async def search_exact(self, inp) -> _Out:
        try:
            check_fields("search_exact", inp, ("all_of", "any_of", "none_of", "filters", "max_results"))
            lists = [string_list(inp, k) for k in ("all_of", "any_of", "none_of")]
            f = parse_filters(inp.get("filters"), self.corpus)
            limit = max_results(inp.get("max_results"))
            hits = self.deps.keyword.search(*lists, f, limit + len(self.seen))   # room to top up (§4.B)
        except ToolInputError as e:
            return _Out([e.message], True, {"found": [], "matched_again": []})
        self.corpus_searched = True
        return await self.assemble([h.passage_id for h in hits], limit, f)

    async def read_passages(self, inp) -> _Out:
        raw_target = inp.get("target") if isinstance(inp, dict) else None
        try:
            check_fields("read_passages", inp, ("target", "before", "after"), ("target",))
            ps = self.corpus.read(inp["target"], whole_number(inp, "before"), whole_number(inp, "after"))
        except ToolInputError as e:
            return _Out([e.message], True, {"target": "" if raw_target is None else str(raw_target), "read": []})
        target = inp["target"].strip().lower()
        page = int(target.partition(":")[2].strip()) if ":" in target else None
        blocks, block_pids = [], []
        for p in ps:
            if page is None:
                mark = "(the passage you asked for)" if p.id == target else None
            else:
                mark = "(on the page you asked for)" if p.page_start <= page <= p.page_end else None
            await self.show(p.id, blocks, block_pids, mark)
        ids = [p.id for p in ps]
        return _Out(blocks, False, {"target": target, "read": ids}, None, block_pids, ids)

    def keep_passages(self, inp) -> _Out:
        """T1.7: only IDs already shown, the reason cap, KEEP_CAP, a re-keep replacing the reason (history kept)."""
        try:
            check_fields("keep_passages", inp, ("keep",), ("keep",))
            items = inp["keep"]
            if not isinstance(items, list) or not items:
                raise ToolInputError("'keep' must be a non-empty list of {id, reason} objects.")
            for n, it in enumerate(items, 1):
                if (not isinstance(it, dict) or set(it) - {"id", "reason"} or not isinstance(it.get("id"), str)
                        or not isinstance(it.get("reason"), str)):
                    raise ToolInputError(f"Item {n} of 'keep' must be an object with a text 'id' and a text 'reason'.")
        except ToolInputError as e:
            return _Out([e.message], True, {"kept": [], "refused": [], "kept_count": len(self.kept)})
        applied, refused = [], []
        for it in items:
            pid, reason = it["id"], it["reason"]
            if pid not in self.seen_before_turn:
                why = rejection("keep", "unseen_id", id=pid)
            elif not reason.strip():
                why = rejection("keep", "reason_empty", id=pid)
            elif len(reason) > KEEP_REASON_MAX:
                why = rejection("keep", "reason_too_long", id=pid, length=len(reason))
            elif pid not in self.kept and len(self.kept) >= KEEP_CAP:
                why = rejection("keep", "cap_reached", id=pid, count=len(self.kept))
            else:
                why = None
            if why is not None:
                refused.append({"id": pid, "why": why})
                continue
            replaced = pid in self.kept
            if replaced:
                kp = self.kept[pid]
                kp.history.append(kp.reason)
                kp.reason = reason
            else:
                self.kept[pid] = KeptPassage(passage_id=pid, reason=reason, kept_at_round=self.round_no)
            applied.append({"id": pid, "reason": reason, "replaced": replaced})
        if not applied:
            text = rejection("keep", "nothing_applied", problems="\n".join(r["why"] for r in refused))
            return _Out([text], True, {"kept": [], "refused": refused, "kept_count": len(self.kept)})
        new = [a["id"] for a in applied if not a["replaced"]]
        again = [a["id"] for a in applied if a["replaced"]]
        parts = []
        if new:
            parts.append(f"Kept {len(new)} passage{'s' if len(new) != 1 else ''}: {', '.join(new)}.")
        if again:
            parts.append(f"Replaced the reason for {', '.join(again)}.")
        parts.append(f"{len(self.kept)} passage{'s are' if len(self.kept) != 1 else ' is'} kept in all.")
        text = " ".join(parts)
        if refused:
            text += "\nNot kept:\n" + "\n".join(r["why"] for r in refused)
        extra = {"kept": applied, "kept_count": len(self.kept)}
        if refused:
            extra["refused"] = refused
        return _Out([text], False, extra, None, [], [a["id"] for a in applied])

    async def search_web_updates(self, inp) -> _Out:
        """T2.1 to T2.5. Input refused by our code is not counted; Claude gets format_for_claude, the event gets
        format_for_events, so no page text is ever emitted (T2.2, P1.7)."""
        refused = {"web": [], "web_repeats": [], "web_status": "refused_by_us"}
        if self.counted >= UPDATE_SEARCHES:
            return _Out([rejection("update_search", "fourth_search")], True, dict(refused))
        try:
            params = parse_params(inp)
        except ToolInputError as e:
            return _Out([e.message], True, dict(refused))
        search_no = self.counted + 1
        self.start_schema_check()
        outcome = await self.deps.updates.search(params, search_no, self.seen_urls, self.ctx)
        if outcome.kind != "unavailable":
            self.counted += 1
        for pg in outcome.pages:
            self.pages[pg.id] = pg
        self.band_searches.append({"search_no": search_no, "params": params_as_dict(params), "fixed": fixed_settings(),
                                   "status": outcome.kind, "returned": len(outcome.pages) + len(outcome.repeats),
                                   "undated": outcome.undated})
        log.info("run %s: update search %d %s", self.ctx.run_id, search_no, outcome.kind)
        return _Out([format_for_claude(params, outcome)], outcome.kind != "ok",
                    {"web": [_page_detail(pg) for pg in outcome.pages], "web_repeats": list(outcome.repeats),
                     "web_status": outcome.kind, "search_no": search_no},
                    event_content=format_for_events(params, outcome))

    def start_schema_check(self) -> None:
        """T2.5: Exa's tool listing, compared once per instance on its first update search; warnings logged only."""
        updates = self.deps.updates
        try:
            if updates in _SCHEMA_CHECKED:
                return
            _SCHEMA_CHECKED.add(updates)
        except TypeError:
            return

        async def check() -> None:
            try:
                warnings = await updates.schema_check()
                log.info("exa schema check: %d warning(s)", len(warnings))
            except Exception as e:      # never blocks, never reaches Claude
                log.warning("exa schema check could not run (%s)", type(e).__name__)

        task = asyncio.ensure_future(check())
        _BACKGROUND.add(task)
        task.add_done_callback(_BACKGROUND.discard)

    # -- submitting (T1.10, T2.3, P4.3, P4.6 to P4.9) --
    def note_guarded(self, inp: dict) -> bool:
        """P4.8: the note of a no-sources reply (out of scope, or nothing kept) is guarded; the scope note of an
        answered run (in scope, something kept) is not. Kept passages are counted as the submit runs, after the
        turn's other tools (v1.3). An `out_of_scope` that is not a boolean (bad input, refused anyway) is guarded."""
        note = inp.get("note")
        return isinstance(note, str) and bool(note.strip()) and (inp.get("out_of_scope") is not False or not self.kept)

    def guard_report(self, inp):
        """The copy guard over the submit's statements and overview, one entry per finding so the indexes line up,
        over a no-sources reply's note (P4.8) and over the update skip reason on every submit (P4.13); runs of words
        that are also the corpus's are exempt (P4.9). None when no page was returned in the run, or there is nothing
        to guard."""
        if not isinstance(inp, dict) or not self.pages:
            return None
        findings = inp.get("update_findings")
        statements = []
        if isinstance(findings, list):
            statements = [f.get("statement") if isinstance(f, dict) and isinstance(f.get("statement"), str) else ""
                          for f in findings]
        overview = inp.get("update_overview") if isinstance(inp.get("update_overview"), str) else None
        note = inp["note"] if self.note_guarded(inp) else None
        skip = inp.get("update_skip_reason")
        skip = skip if isinstance(skip, str) and skip.strip() else None
        if not statements and not overview and not note and not skip:
            return None
        return copy_guard_report(statements, overview, {pid: pg.text for pid, pg in self.pages.items()},
                                 COPY_GUARD_WORDS, note=note, skip_reason=skip, exempt=corpus_exemption(self.corpus))

    def submit(self, inp, same_turn: bool) -> tuple[_Out, dict, bool]:
        """Rule 1, then the findings checks, the note cap (P4.6) and the copy guard, then rules 2 to 4, rule 4
        waived when out of scope (T1.10, T2.3, P4.7). Returns the result, the input as stored (P4.3, P4.8) and
        whether the submit was accepted."""
        guard = self.guard_report(inp)
        shown = inp
        if guard is not None and (guard.flagged_statements or guard.overview_flagged or guard.note_flagged
                                  or guard.skip_reason_flagged):
            # P4.3, P4.8, P4.13, and §1: no page's words are stored, whichever rule refuses the submit.
            shown = withhold_flagged(inp, guard.flagged_statements, guard.overview_flagged,
                                     note_flagged=guard.note_flagged, skip_reason_flagged=guard.skip_reason_flagged)

        def refuse(rule, text):
            log.info("run %s: submit refused (%s)", self.ctx.run_id, rule)
            return _Out([text], True, {"submit": {"accepted": False, "rule": rule}}), shown, False

        if same_turn:                                                                     # rule 1
            return refuse("same_turn", rejection("submit", "rule_1_same_turn"))
        try:
            check_fields("submit_answer", inp, ("out_of_scope", "note", "update_skip_reason", "update_findings",
                                                "update_overview"), ("out_of_scope",))
            if not isinstance(inp["out_of_scope"], bool):
                raise ToolInputError("'out_of_scope' must be true or false.")
            note = text_field(inp, "note")
            skip = text_field(inp, "update_skip_reason")
        except ToolInputError as e:
            return refuse(None, e.message)
        findings, overview = inp.get("update_findings"), inp.get("update_overview")
        if findings is not None or overview is not None:                                 # T2.3 item 2
            problems = check_update_findings(findings, overview, set(self.pages), self.counted)
            if problems:
                return refuse("findings", rejection("submit", "findings_problems", problems="\n".join(problems)))
        if note is not None and len(note) > NOTE_MAX:                                    # P4.6
            return refuse("note_too_long", rejection("submit", "note_too_long", length=len(note)))
        if guard is not None and guard.problems:                                          # T2.3 item 3, P4.8
            others = bool(guard.flagged_statements or guard.overview_flagged)
            if guard.note_flagged and not others and not guard.skip_reason_flagged:
                text = rejection("submit", "copy_guard_note", pages=pages_named(guard.note_pages))
            elif guard.skip_reason_flagged and not others and not guard.note_flagged:     # P4.13
                text = rejection("submit", "copy_guard_skip_reason", pages=pages_named(guard.skip_reason_pages))
            else:
                text = rejection("submit", "copy_guard", problems="\n".join(guard.problems))
            return refuse("copy_guard", text)
        out_of_scope = inp["out_of_scope"]
        if not out_of_scope:
            if not self.corpus_searched:                                                  # rule 2
                return refuse("no_search", rejection("submit", "rule_2_no_search"))
            if not self.kept and not note:                                                # rule 3
                return refuse("nothing_kept", rejection("submit", "rule_3_nothing_kept"))
        elif not note:                                                                    # T1.10, v1.3
            return refuse("no_note", rejection("submit", "out_of_scope_no_note"))
        # rule 4, refused once; waived while the check is unavailable (P2.11) and for an out-of-scope reply (P4.7)
        if not out_of_scope and self.counted == 0 and not self.unavailable() and not skip:
            if self.reminded_round is None or self.reminded_round >= self.round_no:
                self.reminded_round = self.round_no
                return refuse("no_update_check", rejection("submit", "rule_4_no_update_check"))
            self.declined = True
        self.accepted = {"out_of_scope": out_of_scope, "note": note, "skip": skip,
                         "findings": [{"statement": f["statement"], "sources": list(f["sources"])} for f in findings or []],
                         "overview": overview if isinstance(overview, str) and overview.strip() else None}
        n = len(self.kept)
        if out_of_scope or not n:
            text = prompts.message("submit_accepted_note")
        else:
            text = prompts.message("submit_accepted_answer",
                                   passages="1 kept passage" if n == 1 else f"{n} kept passages")
        log.info("run %s: submit accepted", self.ctx.run_id)
        return _Out([text], False, {"submit": {"accepted": True}}), shown, True

    async def emit_warnings(self) -> None:
        """The Voyage warning (T3.3), once each, from ctx.flags."""
        for flag, code in WARNINGS:
            if getattr(self.ctx.flags, flag) and code not in self.warned:
                self.warned.add(code)
                await self.emit("warning", {"code": code})

    # -- the end --
    def add_stop(self, kind: str | None) -> None:
        """A budget or limit stop, recorded once, in the order it happened (v1.4)."""
        if kind and kind not in self.stops:
            self.stops.append(kind)

    async def finish(self, end: _End) -> None:
        await self.emit_warnings()
        k = end.kind
        if k in LIMIT_STATE:
            self.add_stop(k)                 # before composing, so a failed composition still records it (v1.4)
        if k == "abandoned":
            return await self.close("abandoned")                 # T3.2: composes nothing
        if k == "spend_limit":
            return await self.close("spend_limit", stop_kind=end.stop_kind)
        if k == "refusal":
            return await self.close("refusal", failure_reason="refusal")
        if k == "failed":
            return await self.close("failed", failure_reason=end.failure_reason)
        base_failure = None
        scope = None
        if k == "submitted":
            sub = self.accepted
            if sub["out_of_scope"]:
                return await self.close("no_sources", no_sources_reason="out_of_scope", note=sub["note"])
            if not self.kept:
                return await self.close("no_sources", no_sources_reason="nothing_found", note=sub["note"])
            state, stop_kind, scope = "answered", None, sub["note"]
        elif k in LIMIT_STATE:
            state, stop_kind = LIMIT_STATE[k], k
            if not self.kept:
                return await self.close(state, stop_kind=stop_kind)       # T1.11: nothing kept, nothing composed
        elif k == "error_stopped":
            if not self.kept:
                return await self.close("failed", failure_reason=end.failure_reason)     # T3.3
            state, stop_kind, base_failure = "error_stopped", None, end.failure_reason
        else:
            raise AssertionError(f"unknown loop end {k}")
        comp = await self.compose(scope)
        if comp.outcome == "abandoned":
            return await self.close("abandoned")
        if comp.outcome == "spend":
            return await self.close("spend_limit", stop_kind=comp.stop_kind)
        if comp.outcome == "refused":
            return await self.close("refusal", failure_reason="refusal")
        if comp.outcome == "failed":
            return await self.close("failed", failure_reason=comp.kind)
        scope_note = scope if state == "answered" else None
        if comp.outcome == "complete":
            return await self.close(state, stop_kind=stop_kind, failure_reason=base_failure, answer_end="complete",
                                    scope_note=scope_note)
        if comp.outcome == "cut_off":
            return await self.close(state, stop_kind=stop_kind or "composition_max_tokens", failure_reason=base_failure,
                                    answer_end="cut_off", scope_note=scope_note)
        return await self.close(state, stop_kind=stop_kind, failure_reason=comp.kind, answer_end="incomplete",
                                scope_note=scope_note)

    async def close(self, state: str, *, stop_kind=None, failure_reason=None, no_sources_reason=None, note=None,
                    scope_note=None, answer_end: str = "none") -> None:
        self.add_stop(stop_kind)             # the end's own stop, last (a spend limit, or a limit's stop_kind)
        await self.emit("update_band", self.band())
        await self.emit("run_ended", {
            "state": state, "stop_kind": stop_kind, "stop_kinds": list(self.stops), "no_sources_reason": no_sources_reason, "note": note,
            "scope_note": scope_note, "answer_end": answer_end, "failure_reason": failure_reason,
            "rounds": self.round_no, "answer_chars": sum(len(t) for t in self.answer_texts),
            "totals": self.ctx.totals()})
        log.info("run %s: ended %s (%s), %d rounds", self.ctx.run_id, state, stop_kind or failure_reason or answer_end,
                 self.round_no)

    def band(self) -> dict:
        sub = self.accepted
        findings = sub["findings"] if sub else []
        outcome, reason = band_outcome(searches_counted=self.counted, submitted=sub is not None, findings=findings,
                                       unavailable=self.unavailable(), skip_reason=sub["skip"] if sub else None,
                                       declined=self.declined)
        if outcome == "unavailable":
            reason = self.ctx.flags.exa_unavailable or "no_credit"
        return {"outcome": outcome, "reason": reason, "searches": self.band_searches,
                "findings": findings if sub else [], "overview": sub["overview"] if sub else None,
                "pages": [_page_detail(pg) for pg in self.pages.values()]}

    # -- composition (T1.8, T1.9, T1.11) --
    def composition_ask(self, scope_note: str | None) -> str:
        """The question, a scope note if any, and the coverage dates (T1.11), from loop_messages.json."""
        cov = self.corpus.coverage
        parts = [prompts.message("first_message", question=self.ctx.question)]
        if scope_note:
            parts.append(prompts.message("composition_scope_note", scope_note=scope_note))
        parts.append(prompts.message("composition_coverage", **{k: cov[k] for k in (
            "latest_decision_full_pull", "latest_decision_in_corpus", "ingested")}))
        return "\n\n".join(parts)

    def composition_request(self, documents: list[dict], scope_note: str | None) -> dict:
        """Opus at high effort (T1.8), adaptive thinking (always on for this model), uncached (T1.11, T3.3),
        `max_tokens` 12,000 (T1.11), custom content documents with citations enabled (T1.9)."""
        return {
            "model": COMPOSITION_MODEL,
            "max_tokens": COMPOSITION_MAX_TOKENS,
            "system": prompts.composition_system(),
            "messages": [{"role": "user", "content": documents + [{"type": "text", "text": self.composition_ask(scope_note)}]}],
            "thinking": {"type": "adaptive"},
            "output_config": {"effort": COMPOSITION_EFFORT},
        }

    async def compose(self, scope_note: str | None) -> _Comp:
        docs = sort_documents(self.kept, self.corpus)
        documents = [fmt.document_block(self.corpus.passages[pid], self.kept[pid].reason) for pid in docs]
        request = self.composition_request(documents, scope_note)
        est = self.est(request["system"]) + self.est_json(request["messages"])
        if est > COMPOSITION_RESERVE_INPUT:
            # P4.6: the reserve is the worst case by this estimator, so plain text never reaches this; logged, and
            # the call still runs (P4.4: no tripwire)
            log.error("run %s: composition input estimated at %d tokens, above the %d held back (T1.11, P4.6)",
                      self.ctx.run_id, est, COMPOSITION_RESERVE_INPUT)
        self.call_no += 1
        call_no = self.call_no
        blocks: list[tuple[int, dict, list[dict]]] = []
        st = {"started": False, "dropped": 0, "mismatched": 0}
        att = _Attempts(self, "composition", COMPOSITION_MODEL, call_no, est)

        async def before(n: int) -> None:
            await att.gate(n)

        async def on_block(ci: int, block: dict) -> None:
            cits, dropped, mismatched = map_citations(block, docs, self.corpus, call_no, ci)
            st["dropped"] += dropped
            st["mismatched"] += mismatched
            for c in cits:
                await self.ensure_passage(c["passage_id"])
            await self.emit("answer_block", {"index": len(self.answer_texts), "text": block.get("text", ""),
                                             "citations": cits})
            self.answer_texts.append(block.get("text", ""))
            blocks.append((ci, block, cits))

        async def attempt(n: int):
            if not st["started"]:
                st["started"] = True
                await self.emit("composition_started", {"call_no": call_no, "documents": docs})
                for i, pid in enumerate(docs):
                    await self.emit("api_fragment", {"passage_id": pid, "call_no": call_no, "role": "request",
                                                     "path": f"messages[0].content[{i}]", "json": documents[i]})
            try:
                return await self.deps.anthropic.stream(request, COMPOSITION_CALL_DEADLINE_S, on_block)
            except ServiceError as e:
                att.failed_now(e)
                if blocks:
                    return _Broken(e)          # T3.3: never retried once a block was shown
                raise

        try:
            res = await with_retries(attempt, ANTHROPIC_POLICY, before, att.on_retry, retry_sleep)
        except RunStopped as e:
            if e.reason == "abandoned":
                return _Comp("abandoned")          # composes nothing (T3.2)
            log.error("run %s: the gate stopped a composition for its deadline, which §4.H never does", self.ctx.run_id)
            return _Comp("failed", kind="deadline")
        except ServiceError as e:
            await att.failed_finally(e)
            log.warning("run %s: composition failed (%s)", self.ctx.run_id, e.kind)
            if e.kind in SPEND_STOP:
                return _Comp("spend", stop_kind=SPEND_STOP[e.kind])
            return _Comp("failed", kind=e.kind)
        if st["dropped"] or st["mismatched"]:
            # v1.3: a mapping fault; nothing was attached for these, so the page lights no sentence Claude did not cite
            log.error("run %s: composition call %d: %d citation(s) pointed outside the documents and %d disagreed "
                      "with our sentences; none was attached", self.ctx.run_id, call_no, st["dropped"], st["mismatched"])
        if isinstance(res, _Broken):
            await att.failed_finally(res.error)
            self.add_stop(SPEND_STOP.get(res.error.kind))
            await self.response_fragments(blocks, call_no)
            await self.run_checks(docs)
            return _Comp("incomplete", kind=res.error.kind)
        refused = res.stop_reason == "refusal"
        await att.completed(res, "failed" if refused else "ok", "refusal" if refused else None)
        if res.stop_reason == "max_tokens":
            self.add_stop("composition_max_tokens")          # recorded even if nothing usable came of it (v1.4)
        await self.response_fragments(blocks, call_no)
        if not blocks:
            return _Comp("refused") if refused else _Comp("failed", kind="unreadable")
        await self.run_checks(docs)
        if refused:
            return _Comp("incomplete", kind="refusal")
        return _Comp("cut_off" if res.stop_reason == "max_tokens" else "complete")

    async def response_fragments(self, blocks: list[tuple[int, dict, list[dict]]], call_no: int) -> None:
        """The answer blocks that cite each passage, after the call's paid_call (§6, T4.3 item 7)."""
        for ci, block, cits in blocks:
            for pid in dict.fromkeys(c["passage_id"] for c in cits):
                await self.emit("api_fragment", {"passage_id": pid, "call_no": call_no, "role": "response",
                                                 "path": f"content[{ci}]", "json": block})

    async def run_checks(self, docs: list[str]) -> None:
        """F's checks, off the event loop (they are CPU-bound), on the text exactly as streamed (T1.12)."""
        kept_texts = [self.corpus.passages[pid].text for pid in docs]
        result = await anyio.to_thread.run_sync(check_answer, list(self.answer_texts), kept_texts, self.corpus.manifest)
        await self.emit("checks", asdict(result))


def _tool_result(tool_use_id: str, blocks: list[str], is_error: bool) -> dict:
    out = {"type": "tool_result", "tool_use_id": tool_use_id, "content": [{"type": "text", "text": t} for t in blocks]}
    if is_error:
        out["is_error"] = True
    return out


def _empty_extra(name: str) -> dict:
    if name in ("search_meaning", "search_exact"):
        return {"found": [], "matched_again": []}
    if name == "read_passages":
        return {"read": []}
    return {}


def _page_detail(pg: WebPage) -> dict:
    """A page's details for events and the band: never its text (T2.2, P1.7)."""
    return {"id": pg.id, "title": pg.title, "url": pg.url, "domain": pg.domain, "published": pg.published,
            "author": pg.author}
