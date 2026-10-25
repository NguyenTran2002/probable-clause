"""Research, the update step and the composition (contract v2.0 §4.G; T1.2 to T1.14, T2.1 to T2.5, T3.1 to T3.7,
P4.3 to P4.10, P4.16 to P4.20).

`execute_run(ctx, deps)` emits run_started ... run_ended and returns normally for every expected end, RunStopped
included. A run is research (§4.G.3), then two branches side by side as asyncio tasks (§4.G.1): the update step
(§4.G.4), which continues research's conversation so it reads research's cache (§4.G.2), and the composition
(§4.G.5). H holds the run (RunContext): the gate before every paid call, the pricing and the one emitter of
`paid_call`. This module never touches the store or Atlas.

The conversation machinery (`_Conversation`) is shared by research and the update step, each with its own limits,
status line, allowed tools and `step`: the request builder (one for both, so their requests differ only in
`max_tokens` and `messages`), the attempts and retries (`_Attempts`), the budget checks and the estimate, the tool
dispatch in Claude's order with rule 1, and the round_started / tool_call / tool_result events.

Logs hold run IDs, rounds, call numbers, outcomes, error kinds, timings and counts, never the question, Claude's
queries, the answer or page text (T3.7).
"""

import asyncio
import copy
import dataclasses
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
from api.loop.streamer import AnthropicStreamer, StreamResult, partial_of
from api.loop.streamer import raw_usage as usage_object
from api.loop.tools import (RESEARCH_TOOLS, STRICT_TOOLS, TOOL_NAMES, UPDATE_TOOLS, check_fields, max_results,
                            string_list, text_field, tools as build_tool_list, whole_number)
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
UPDATE_MODEL = str(_v(settings.UPDATE_MODEL))
UPDATE_EFFORT = str(_v(settings.UPDATE_EFFORT))
# P4.19, contract v2.0 §4.G.2: the update step continues research's conversation, so it reads research's cache only
# if every field before the messages is identical. Checked at import, never stripped like an assert.
if UPDATE_MODEL != LOOP_MODEL or UPDATE_EFFORT != LOOP_EFFORT:
    raise RuntimeError("UPDATE_MODEL and UPDATE_EFFORT must equal LOOP_MODEL and LOOP_EFFORT (P4.19, contract §4.G.2)")
COMPOSITION_MODEL = str(_v(settings.COMPOSITION_MODEL))
COMPOSITION_EFFORT = str(_v(settings.COMPOSITION_EFFORT))
MAX_ROUNDS = int(_v(settings.MAX_ROUNDS))
LOOP_INPUT_BUDGET = int(_v(settings.LOOP_INPUT_BUDGET))
LOOP_OUTPUT_BUDGET = int(_v(settings.LOOP_OUTPUT_BUDGET))
UPDATE_MAX_ROUNDS = int(_v(settings.UPDATE_MAX_ROUNDS))
UPDATE_INPUT_BUDGET = int(_v(settings.UPDATE_INPUT_BUDGET))
UPDATE_OUTPUT_BUDGET = int(_v(settings.UPDATE_OUTPUT_BUDGET))
COMPOSITION_MAX_TOKENS = int(_v(settings.COMPOSITION_MAX_TOKENS))
RUN_DEADLINE_S = int(_v(settings.RUN_DEADLINE_S))
LOOP_CALL_DEADLINE_S = float(_v(settings.LOOP_CALL_DEADLINE_S))
COMPOSITION_CALL_DEADLINE_S = float(_v(settings.COMPOSITION_CALL_DEADLINE_S))
UPDATE_SEARCHES = int(_v(settings.UPDATE_SEARCHES_PER_RUN))
KEEP_CAP = int(_v(settings.KEEP_CAP))
KEEP_REASON_MAX = int(_v(settings.KEEP_REASON_MAX_CHARS))
COPY_GUARD_WORDS = int(_v(settings.COPY_GUARD_WORDS))
NOTE_MAX = int(_v(settings.NOTE_MAX_CHARS))
MAX_ATTEMPTS = ANTHROPIC_POLICY.retries + 1

# P4.3, contract v2.0 §4.G.2: a stored and streamed update-step call carries this in place of each flagged string,
# and the second in place of each flagged key, k counting from 1 within the input.
WITHHELD = "[statement withheld: it repeated a page's words]"
WITHHELD_KEY = "[field withheld {k}]"

# T3.3: errors after retries that are our fault or the account's end research with no further calls; every other
# kind left after retries composes from what was kept.
# GAP: T3.3 lists 400, 401, 403, 404 and 413 as our fault or the account's; this set is those kinds and nothing more.
FATAL_KINDS = frozenset({"bad_request", "auth", "permission", "not_found", "too_large"})
SPEND_STOP = {"spend_limit": "console_spend_limit", "spend_cap": "tier_spend_cap"}      # §6, T3.4
LIMIT_STATE = {"step_limit": "step_limit", "token_ceiling_input": "token_ceiling",
               "token_ceiling_output": "token_ceiling", "time_limit": "time_limit"}
UPDATE_STOPS = frozenset({"update_step_limit", "update_time_limit", "update_token_ceiling_output",
                          "update_token_ceiling_input"})                                   # §4.G.4
# Stop reasons that end a step at its output ceiling, as T3.3 says of `max_tokens`. `model_context_window_exceeded` is
# named by the installed SDK (`anthropic` 2.3.0, `types/stop_reason.py` and the `stop_reason` docstring in
# `types/message.py`: "we exceeded the model's context window"); treating it like `max_tokens` is the cross-part
# review's ruling (Oct 25, 2026): the turn is cut, so its tool calls never run and the step stops rather than loop.
OUTPUT_STOP_REASONS = ("max_tokens", "model_context_window_exceeded")
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
    """Emits run_started ... run_ended; returns normally for every expected end, RunStopped included (§4.G). An
    unexpected exception in research or the composition cancels the update step and is re-raised as it is, so H ends
    the run `failed` (§4.G.1 item 6)."""
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
    under a tenth of a second), on the first guarded check: a run of words also found in one passage is the Court's,
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


# ---------- the band (§6) ----------

def band_outcome(*, started: bool, unavailable: str | None = None, searches_counted: int = 0, submitted: bool = False,
                 findings=(), skip_reason: str | None = None, end: str | None = None, stop_kind: str | None = None,
                 failure_reason: str | None = None) -> tuple[str, str | None]:
    """The update band's outcome, worked out by code (T2.3 item 4 amended by P4.19, contract v2.0 §6), the first
    rule that applies winning. `started` is whether the update step ran; when it did not, `unavailable` is set only
    when the update check's unavailability was the only reason, so a step never started for research's reasons is
    `not_run`. When it did run, `unavailable` is set when the check became unavailable during it. `end`, `stop_kind`
    and `failure_reason` are its update_ended's. Returns (outcome, reason)."""
    if searches_counted > 0:                                            # 1. a counted search ran
        if not submitted:
            return "not_summarised", None
        return ("found" if findings else "nothing_relevant"), None
    if not started:                                                     # 2. research's reasons; 3. unavailable at start
        return ("unavailable", unavailable) if unavailable else ("not_run", None)
    if unavailable:                                                     # 3. became unavailable during the step
        return "unavailable", unavailable
    if end in ("stopped", "failed"):                                    # 3. a stop or failure, no counted search
        return "unavailable", stop_kind or failure_reason
    if submitted and skip_reason:                                       # 4.
        return "skipped", skip_reason
    return "not_run", None                                              # 5. e.g. abandoned before any search


def update_decision(*, submitted: bool, out_of_scope: bool, corpus_searched: bool,
                    unavailable: str | None) -> tuple[str, str | None]:
    """§4.G.1 item 3: whether the update step starts. ("start", None); ("not_run", None) when research's reasons stop
    it (no accepted submit, out of scope, or no corpus search: the user's rule, P4.19, enforced here as a backstop to
    rule 2); ("unavailable", reason) when the update check's unavailability is the only reason."""
    if not submitted or out_of_scope or not corpus_searched:
        return "not_run", None
    if unavailable is not None:
        return "unavailable", unavailable
    return "start", None


def sort_documents(ids, corpus: Corpus) -> list[str]:
    """T1.11: decision date, then opinion, then position: the corpus's reading order within a date (case, opinion,
    paragraphs, then footnotes)."""
    order = {pid: i for i, pid in enumerate(corpus.passages)}
    return sorted(ids, key=lambda pid: (corpus.passages[pid].decided, order[pid]))


def withhold_flagged(inp: dict, flagged: set[int], overview_flagged: bool, *, skip_reason_flagged: bool = False) -> dict:
    """P4.3, P4.13: a submit_update's input as stored, each flagged statement replaced; a flagged overview and a
    flagged update skip reason replaced by the same text. Claude's own input is never changed."""
    shown = copy.deepcopy(inp)
    findings = shown.get("update_findings")
    for i in flagged:
        if isinstance(findings, list) and 0 <= i < len(findings) and isinstance(findings[i], dict):
            findings[i]["statement"] = WITHHELD
    if overview_flagged:
        shown["update_overview"] = WITHHELD
    if skip_reason_flagged:
        shown["update_skip_reason"] = WITHHELD
    return shown


def texts_in(obj) -> list[str]:
    """Every text of a tool input, at any depth, in order, dict keys included: each key, then its value (contract
    v2.0 §4.G.2: a key can carry a page's words as well as a value can)."""
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


def withhold_texts(obj, flagged: set[int]):
    """A copy of `obj` with the texts `texts_in` numbers in `flagged` withheld: a value by WITHHELD, a key by
    "[field withheld <k>]", k counting from 1 within the input (§4.G.2)."""
    n = {"i": -1, "k": 0}

    def walk(o):
        if isinstance(o, str):
            n["i"] += 1
            return WITHHELD if n["i"] in flagged else o
        if isinstance(o, dict):
            out = {}
            for key, v in o.items():
                if isinstance(key, str):
                    n["i"] += 1
                    if n["i"] in flagged:
                        n["k"] += 1
                        key = WITHHELD_KEY.format(k=n["k"])
                        while key in o or key in out:         # never collide with a key Claude sent
                            n["k"] += 1
                            key = WITHHELD_KEY.format(k=n["k"])
                out[key] = walk(v)
            return out
        if isinstance(o, list):
            return [walk(v) for v in o]
        return copy.deepcopy(o)
    return walk(obj)


# ---------- internals ----------

class _BudgetStop(Exception):
    """A retry would cross the step's token budget (T3.3, T3.4)."""
    def __init__(self, kind: str):
        super().__init__(kind)
        self.kind = kind


@dataclass
class _End:
    """How a step ended. Research: submitted | step_limit | token_ceiling_* | time_limit | error_stopped | failed |
    refusal | spend_limit | abandoned. The update step: submitted | update_* | failed | refusal | spend_limit |
    abandoned. `failure_reason` is the error's kind (for a spend stop too); `stop_kind` a spend stop's kind."""
    kind: str
    failure_reason: str | None = None
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


@dataclass
class _Plan:
    """What research's end means for the run (§4.G.6): `final` is run_ended's fields when nothing is composed;
    otherwise the composition runs and these fields complete them."""
    final: dict | None = None
    state: str = ""
    stop_kind: str | None = None
    base_failure: str | None = None
    scope: str | None = None


@dataclass(frozen=True)
class _Limits:
    """One step's limits and the stop kind each ends it with (§4.G.3, §4.G.4)."""
    step: str                      # research | update
    purpose: str                   # loop | update
    model: str
    effort: str
    max_rounds: int
    input_budget: int
    output_budget: int
    stop_rounds: str
    stop_time: str
    stop_output: str
    stop_input: str


def _research_limits() -> _Limits:
    """Read at the start of each run, so a test may change a figure for one run."""
    return _Limits("research", "loop", LOOP_MODEL, LOOP_EFFORT, MAX_ROUNDS, LOOP_INPUT_BUDGET, LOOP_OUTPUT_BUDGET,
                   "step_limit", "time_limit", "token_ceiling_output", "token_ceiling_input")


def _update_limits() -> _Limits:
    return _Limits("update", "update", UPDATE_MODEL, UPDATE_EFFORT, UPDATE_MAX_ROUNDS, UPDATE_INPUT_BUDGET,
                   UPDATE_OUTPUT_BUDGET, "update_step_limit", "update_time_limit", "update_token_ceiling_output",
                   "update_token_ceiling_input")


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
    `failed`, so no record says `retrying` without an attempt after it. The call's number is taken from the run's one
    counter when its first attempt passes the gate (§4.G.4), so a call stopped at the gate leaves no gap. An attempt
    in flight when its task is cancelled is recorded `failed` from what it streamed before the cancellation goes on
    (§4.G.1 item 7). `count` adds each recorded attempt to its step's budgets."""

    def __init__(self, run: "_Run", purpose: str, model: str, est_input: int, count=None):
        self.run, self.purpose, self.model, self.est, self.count = run, purpose, model, est_input, count
        self.call_no: int | None = None
        self.attempt = 1
        self.t0 = time.monotonic()
        self.ms, self.raw, self.chars = 0, None, 0
        self.pending: tuple | None = None          # (attempt, error kind, usage, usage object, duration)

    def failed_now(self, e: ServiceError) -> None:
        self.ms = _ms(self.t0)
        self.raw = getattr(e, "raw_usage", None)
        self.chars = getattr(e, "streamed_chars", 0) or 0

    async def record(self, usage: Usage, shown: dict | None, *, attempt: int, outcome: str, error_kind,
                     duration_ms: int) -> Usage:
        await self.run.record_usage(self.purpose, usage, shown, call_no=self.call_no, attempt=attempt,
                                    outcome=outcome, error_kind=error_kind, duration_ms=duration_ms)
        if self.count is not None:
            self.count(usage)
        return usage

    async def on_retry(self, next_attempt: int, error: ServiceError, wait_s: float) -> None:
        usage, shown = self.run.failure_usage(self.model, self.raw, self.est, self.chars)
        self.pending = (next_attempt - 1, error.kind, usage, shown, self.ms)
        log.info("run %s: %s call %d attempt %d failed (%s); retrying in %.1f s", self.run.ctx.run_id, self.purpose,
                 self.call_no, next_attempt - 1, error.kind, wait_s)

    async def flush(self, outcome: str) -> None:
        if self.pending is not None:
            attempt, kind, usage, shown, ms = self.pending
            self.pending = None
            await self.record(usage, shown, attempt=attempt, outcome=outcome, error_kind=kind, duration_ms=ms)

    async def gate(self, n: int, budget=None) -> None:
        self.attempt = n
        if self.pending is not None:
            try:
                if budget is not None:
                    budget(self.pending[2])
                await self.run.ctx.before_paid_call("anthropic", self.purpose)
            except BaseException:          # a budget stop, RunStopped, a cancellation or anything else
                await self.flush("failed")
                raise
            await self.flush("retrying")
        else:
            await self.run.ctx.before_paid_call("anthropic", self.purpose)
        if self.call_no is None:
            self.call_no = self.run.next_call_no()
        self.t0 = time.monotonic()

    async def completed(self, res: StreamResult, outcome: str, kind) -> Usage:
        return await self.record(usage_from_raw(res.usage, self.model), res.usage, attempt=self.attempt,
                                 outcome=outcome, error_kind=kind, duration_ms=_ms(self.t0))

    async def failed_finally(self, e: ServiceError) -> None:
        await self.flush("failed")         # never left pending (with_retries raises without a further attempt)
        usage, shown = self.run.failure_usage(self.model, self.raw, self.est, self.chars)
        await self.record(usage, shown, attempt=self.attempt, outcome="failed", error_kind=e.kind, duration_ms=self.ms)

    async def unexpected(self, e: BaseException) -> None:
        """An unexpected exception in our own code during an attempt handed to the streamer (an `on_block` callback
        included; the caller re-raises it): the attempt was sent and may be billed, so it is recorded `failed` with
        `internal`, priced from what it streamed and reported (the streamer leaves that on the exception, as on a
        cancellation), or from its input estimate when it saw nothing (T3.3), and the call numbers keep no gap."""
        await self.flush("failed")
        raw, chars, _ = partial_of(e)
        self.raw, self.chars, self.ms = raw, chars, _ms(self.t0)
        usage, shown = self.run.failure_usage(self.model, raw, self.est, chars)
        await self.record(usage, shown, attempt=self.attempt, outcome="failed", error_kind="internal",
                          duration_ms=self.ms)

    async def cancelled(self, e: BaseException) -> None:
        """§4.G.1 item 7: the attempt in flight, priced from what it streamed and reported (P4.5, P4.10). GAP: the
        closed ErrorKind has no word for our own cancellation; the cut stream is `stream_broken`, or `connection`
        when no stream had begun (the request dropped before a response began)."""
        await self.flush("failed")
        raw, chars, started = partial_of(e)
        self.raw, self.chars, self.ms = raw, chars, _ms(self.t0)
        usage, shown = self.run.failure_usage(self.model, raw, self.est, chars)
        log.info("run %s: %s call %d attempt %d cancelled in flight; recorded", self.run.ctx.run_id, self.purpose,
                 self.call_no, self.attempt)
        await self.record(usage, shown, attempt=self.attempt, outcome="failed",
                          error_kind="stream_broken" if started else "connection", duration_ms=self.ms)


# ---------- one conversation, two steps (§4.G.2) ----------

class _Conversation:
    """The machinery research and the update step share. A subclass sets `tools_here` and `submit_name` and gives its
    own status line, error ends and tools; the messages, the request builder and the estimate are the run's, so the
    update step continues research's conversation exactly."""

    tools_here: frozenset = frozenset()
    submit_name: str = ""

    def __init__(self, run: "_Run", limits: _Limits):
        self.run, self.ctx, self.lim = run, run.ctx, limits
        self.step = limits.step
        self.round_no = 0
        self.input_used = 0                          # every attempt of this step, actual or estimated (T3.3, T3.4)
        self.output_used = 0
        self.status_for_round = ""
        self.accepted_results: list[dict] | None = None

    async def emit(self, kind: str, data: dict) -> int:
        return await self.ctx.emit(kind, data)

    # -- hooks --
    def status_line(self, round_no: int) -> str:
        raise NotImplementedError

    def end_for_error(self, e: ServiceError) -> _End:
        raise NotImplementedError

    def begin_turn(self) -> None:
        """Before a turn's tools run."""

    async def before_send(self, call_no: int) -> None:
        """Once the gate has let a call's first attempt go."""

    def stored(self, inp):
        """A call's input as its tool_call stores it: research's, exactly as Claude sent it (P4.19)."""
        return inp

    def wrong_step(self, name: str, inp) -> _Out:
        raise NotImplementedError

    def submit(self, inp, same_turn: bool) -> tuple[_Out, object, bool]:
        raise NotImplementedError

    async def run_own_tool(self, tid: str, name: str, inp) -> _Out:
        """Emits the call's tool_call and runs it."""
        raise NotImplementedError

    async def after_result(self, out: _Out, call_no: int, ci: int, block: dict, ti: int, user_index: int) -> None:
        """After a tool's tool_result."""

    # -- the budget (T3.3, T3.4) --
    def next_input_estimate(self) -> int:
        """The next call's input, estimated before it is sent (T3.3): the system prompt, the tools and the messages
        at the corpus's ratio (no fixed floor, P4.18), or, once a call of this conversation has reported its usage,
        that call's input and output plus what was added since. The update step carries research's on (§4.G.4)."""
        run = self.run
        if run.last_ok is None:
            return (run.est(run.system_text) + run.est_json(run.tool_list)
                    + sum(run.est_json(m["content"]) for m in run.messages))
        total, output, n = run.last_ok
        return total + output + sum(run.est_json(m["content"]) for m in run.messages[n + 1:])

    def output_left(self) -> int:
        return self.lim.output_budget - self.output_used

    def count_usage(self, u: Usage) -> None:
        """Every attempt of this step counts toward this step's budgets, and only toward them (§4.G.4)."""
        self.input_used += total_input(u)
        self.output_used += u.output_tokens

    def limit_stop(self) -> str | None:
        """The limits before a round, in order (T1.11, T3.3, T3.5; §4.G.3, §4.G.4); the input budget is next."""
        if self.round_no >= self.lim.max_rounds:
            return self.lim.stop_rounds
        if self.ctx.seconds_left() <= 0:
            return self.lim.stop_time
        if self.output_left() <= 0:
            return self.lim.stop_output
        return None

    # -- the rounds --
    async def rounds(self) -> _End:
        try:
            while True:
                stop = self.limit_stop()
                if stop is not None:
                    return _End(stop)
                est = self.next_input_estimate()
                if self.input_used + est > self.lim.input_budget:
                    return _End(self.lim.stop_input)
                self.round_no += 1
                await self.emit("round_started", {"step": self.step, "round": self.round_no,
                                                  "status_line": self.status_for_round})
                try:
                    res, call_no = await self.call(est)
                except _BudgetStop as b:
                    return _End(b.kind)
                except ServiceError as e:
                    return self.end_for_error(e)
                if res.stop_reason == "refusal":
                    return _End("refusal", failure_reason="refusal")
                self.run.messages.append({"role": "assistant", "content": res.content})
                if res.stop_reason in OUTPUT_STOP_REASONS:   # T3.3: a call stopped by max_tokens, or the window
                    log.warning("run %s: %s call %d stopped (%s); the step ends at its output ceiling",
                                self.ctx.run_id, self.step, call_no, res.stop_reason)
                    return _End(self.lim.stop_output)
                results, accepted = await self.run_tools(res, call_no)
                if accepted:
                    self.accepted_results = results
                    return _End("submitted")
                self.status_for_round = self.status_line(self.round_no + 1)
                self.run.messages.append({"role": "user", "content": results + [{"type": "text",
                                                                                  "text": self.status_for_round}]})
        except RunStopped as e:
            return _End("abandoned") if e.reason == "abandoned" else _End(self.lim.stop_time)

    def request(self, max_tokens: int) -> dict:
        return self.run.conversation_request(self.lim.model, self.lim.effort, max_tokens)

    async def call(self, est: int) -> tuple[StreamResult, int]:
        """One call of this step through with_retries (T3.3), each attempt recorded with ctx.record_usage."""
        run = self.run
        att = _Attempts(run, self.lim.purpose, self.lim.model, est, count=self.count_usage)
        sent = {"done": False}

        def budget(pending: Usage) -> None:
            # T3.4: every attempt counts toward the step's budgets, so a retry never crosses them
            if self.input_used + total_input(pending) + est > self.lim.input_budget:
                raise _BudgetStop(self.lim.stop_input)
            if self.output_left() - pending.output_tokens <= 0:
                raise _BudgetStop(self.lim.stop_output)

        async def before(n: int) -> None:
            await att.gate(n, budget)

        async def attempt(n: int) -> StreamResult:
            if not sent["done"]:           # only once the gate has let the request go (a fragment is what was sent)
                sent["done"] = True
                await self.before_send(att.call_no)
            request = self.request(self.output_left())
            try:                           # only an attempt handed to the streamer is recorded
                res = await run.deps.anthropic.stream(request, LOOP_CALL_DEADLINE_S, None, step=self.step)
            except ServiceError as e:
                att.failed_now(e)
                raise
            except asyncio.CancelledError as e:
                await att.cancelled(e)
                raise
            except Exception as e:
                await att.unexpected(e)
                raise
            refused = res.stop_reason == "refusal"     # billed, so its usage is real (T3.3)
            usage = await att.completed(res, "failed" if refused else "ok", "refusal" if refused else None)
            if not refused:
                run.last_ok = (total_input(usage), usage.output_tokens, len(run.messages))
            log.info("run %s: %s call %d attempt %d %s, stop %s", self.ctx.run_id, self.step, att.call_no, n,
                     "refused" if refused else "ok", res.stop_reason)
            return res

        try:
            res = await with_retries(attempt, ANTHROPIC_POLICY, before, att.on_retry, retry_sleep)
        except ServiceError as e:
            await att.failed_finally(e)
            raise
        except asyncio.CancelledError:
            await att.flush("failed")          # a failed attempt waiting for its retry
            raise
        return res, att.call_no

    # -- the tools --
    async def emit_call(self, tid: str, name: str, inp) -> None:
        await self.emit("tool_call", {"step": self.step, "round": self.round_no, "tool_use_id": tid, "name": name,
                                      "input": inp})

    async def emit_result(self, tid: str, name: str, out: _Out) -> None:
        await self.emit("tool_result", {"step": self.step, "tool_use_id": tid, "name": name, "is_error": out.is_error,
                                        "content": out.event_content if out.event_content is not None
                                        else "\n\n".join(out.blocks), **out.extra})

    async def emit_stopped_result(self, tid: str, name: str) -> None:
        """The run stopped (or our code failed) before this tool could finish: nothing was sent to Claude for it."""
        await self.emit("tool_result", {"step": self.step, "tool_use_id": tid, "name": name, "is_error": True,
                                        "content": "", **_empty_extra(name)})

    async def run_tools(self, res: StreamResult, call_no: int) -> tuple[list[dict], bool]:
        """The turn's tools in Claude's order (§4.G). A submit must be the turn's only call: with any other call (an
        unknown or a wrong-step one included), or a second submit, every submit is refused and the other calls run as
        usual (P4.16, rule 1). A tool of the other step is refused (§4.G.2). Every known tool_use gets its tool_call
        and tool_result; the results go back to Claude in Claude's order."""
        uses = [(ti, ci, b) for ti, (ci, b) in enumerate((i, b) for i, b in enumerate(res.content)
                                                         if b.get("type") == "tool_use")]
        same_turn = len(uses) > 1                                                 # rule 1, P4.16
        self.begin_turn()
        user_index = len(self.run.messages)      # the index the tool results' user message will have
        results: list[dict | None] = [None] * len(uses)
        accepted_any = False
        for ti, ci, b in uses:
            name, tid, inp = b.get("name"), b.get("id"), b.get("input")
            if name not in TOOL_NAMES:
                log.warning("run %s: Claude called an unknown tool", self.ctx.run_id)
                results[ti] = _tool_result(tid, [prompts.message("unknown_tool", name=name,
                                                                 tools=", ".join(TOOL_NAMES))], True)
                continue
            if name not in self.tools_here:                                       # §4.G.2: never counted
                log.info("run %s: %s refused in the %s step", self.ctx.run_id, name, self.step)
                out = self.wrong_step(name, inp)
                await self.emit_call(tid, name, self.stored(inp))
            elif name == self.submit_name:
                out, shown, accepted = self.submit(inp, same_turn)   # before tool_call: P4.3 needs the guard's result
                accepted_any = accepted_any or accepted
                await self.emit_call(tid, name, shown)
            else:
                out = await self.run_own_tool(tid, name, inp)
            await self.emit_result(tid, name, out)
            await self.after_result(out, call_no, ci, b, ti, user_index)
            results[ti] = _tool_result(tid, out.blocks, out.is_error)
        return [r for r in results if r is not None], accepted_any


def _wrong_step_extra(name: str, inp, kept_count: int) -> dict:
    """§4.G.2: a wrong-step call's result fields, by tool."""
    if name in ("search_meaning", "search_exact"):
        extra = {"found": [], "matched_again": []}
    elif name == "read_passages":
        raw = inp.get("target") if isinstance(inp, dict) else None
        extra = {"read": [], "target": raw if isinstance(raw, str) else ""}
    elif name == "keep_passages":
        extra = {"kept": [], "kept_count": kept_count}               # as it stands
    elif name == "search_web_updates":
        extra = {"web": [], "web_repeats": [], "web_status": "refused_by_us"}
    else:
        extra = {"submit": {"accepted": False, "rule": "wrong_step"}}
    extra["wrong_step"] = True
    return extra


# ---------- research (§4.G.3) ----------

class _Research(_Conversation):
    tools_here = RESEARCH_TOOLS
    submit_name = "submit_answer"

    def __init__(self, run: "_Run"):
        super().__init__(run, _research_limits())
        self.corpus = run.corpus
        self.seen: set[str] = set()                 # passages whose text Claude was sent (T1.7)
        self.seen_before_turn: frozenset[str] = frozenset()   # what Claude had seen when it wrote this turn's calls
        self.pending: list[tuple[str, int, int, int, str]] = []
        self.accepted: dict | None = None

    async def start(self) -> _End:
        first = [{"type": "text", "text": prompts.message("first_message", question=self.ctx.question)}]
        self.status_for_round = self.status_line(1)
        first.append({"type": "text", "text": self.status_for_round})
        self.run.messages.append({"role": "user", "content": first})
        return await self.rounds()

    def status_line(self, round_no: int) -> str:
        return prompts.status_line(round_no, len(self.run.kept))

    def end_for_error(self, e: ServiceError) -> _End:
        log.warning("run %s: research call failed (%s)", self.ctx.run_id, e.kind)
        if e.kind in SPEND_STOP:
            return _End("spend_limit", failure_reason=e.kind, stop_kind=SPEND_STOP[e.kind])
        if e.kind in FATAL_KINDS:
            return _End("failed", failure_reason=e.kind)
        # GAP: T3.3 composes after "transient failures"; our deadline, an unreadable reply, a protocol error and a
        # timeout are not in its list either way, and are treated as transient: the kept passages are composed.
        return _End("error_stopped", failure_reason=e.kind)

    def begin_turn(self) -> None:
        # T1.7: a keep may name only passages shown before this turn; this turn's results are not yet seen by Claude
        self.seen_before_turn = frozenset(self.seen)

    async def before_send(self, call_no: int) -> None:
        """T4.3(7): each passage's block in the previous round's tool result, before this call's paid_call (§6)."""
        for pid, mi, ti, bi, text in self.pending:
            await self.emit("api_fragment", {"step": "research", "passage_id": pid, "call_no": call_no,
                                             "role": "request",
                                             "path": f"messages[{mi}].content[{ti}].content[{bi}]",
                                             "json": {"type": "text", "text": text}})
        self.pending = []

    def wrong_step(self, name: str, inp) -> _Out:
        return _Out([rejection("wrong_step", "update_tool", name=name)], True,
                    _wrong_step_extra(name, inp, len(self.run.kept)))

    async def run_own_tool(self, tid: str, name: str, inp) -> _Out:
        await self.emit_call(tid, name, inp)
        try:
            return await self.execute_tool(name, inp)
        except Exception:                       # RunStopped, or an unexpected exception: the call still gets its result
            await self.emit_stopped_result(tid, name)
            raise

    async def after_result(self, out: _Out, call_no: int, ci: int, block: dict, ti: int, user_index: int) -> None:
        await self.run.emit_warnings()           # right after the result that set the flag
        for pid in dict.fromkeys(out.resp_pids):
            await self.emit("api_fragment", {"step": "research", "passage_id": pid, "call_no": call_no,
                                             "role": "response", "path": f"content[{ci}]", "json": block})
        for pid, bi in out.block_pids:
            self.pending.append((pid, user_index, ti, bi, out.blocks[bi]))

    async def execute_tool(self, name: str, inp) -> _Out:
        if name == "search_meaning":
            return await self.search_meaning(inp)
        if name == "search_exact":
            return await self.search_exact(inp)
        if name == "read_passages":
            return await self.read_passages(inp)
        return self.keep_passages(inp)

    async def show(self, pid: str, blocks: list[str], block_pids: list, mark: str | None = None) -> None:
        """Send one passage's block, with its attached footnotes; every passage sent gets its event first (§6)."""
        await self.run.ensure_passage(pid)
        bi = len(blocks)
        blocks.append(fmt.passage_block(self.corpus, pid, mark))
        block_pids.append((pid, bi))
        self.seen.add(pid)
        for f in self.corpus.attached_footnotes(pid):
            await self.run.ensure_passage(f.id)
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
        res = await self.run.deps.meaning.search(query, lambda p: matches(p, f) and not excluded_by_none_of(p, f),
                                                 self.ctx, self.run.deps.voyage, sleep=retry_sleep)
        if res.status == "unavailable":
            return _Out([res.message_for_claude or UNAVAILABLE_NOTE], True,
                        {"found": [], "matched_again": [], "not_reranked": False})
        self.run.corpus_searched = True
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
            hits = self.run.deps.keyword.search(*lists, f, limit + len(self.seen))   # room to top up (§4.B)
        except ToolInputError as e:
            return _Out([e.message], True, {"found": [], "matched_again": []})
        self.run.corpus_searched = True
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
        kept = self.run.kept
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
            return _Out([e.message], True, {"kept": [], "refused": [], "kept_count": len(kept)})
        applied, refused = [], []
        for it in items:
            pid, reason = it["id"], it["reason"]
            if pid not in self.seen_before_turn:
                why = rejection("keep", "unseen_id", id=pid)
            elif not reason.strip():
                why = rejection("keep", "reason_empty", id=pid)
            elif len(reason) > KEEP_REASON_MAX:
                why = rejection("keep", "reason_too_long", id=pid, length=len(reason))
            elif pid not in kept and len(kept) >= KEEP_CAP:
                why = rejection("keep", "cap_reached", id=pid, count=len(kept))
            else:
                why = None
            if why is not None:
                refused.append({"id": pid, "why": why})
                continue
            replaced = pid in kept
            if replaced:
                kp = kept[pid]
                kp.history.append(kp.reason)
                kp.reason = reason
            else:
                kept[pid] = KeptPassage(passage_id=pid, reason=reason, kept_at_round=self.round_no)
            applied.append({"id": pid, "reason": reason, "replaced": replaced})
        if not applied:
            text = rejection("keep", "nothing_applied", problems="\n".join(r["why"] for r in refused))
            return _Out([text], True, {"kept": [], "refused": refused, "kept_count": len(kept)})
        new = [a["id"] for a in applied if not a["replaced"]]
        again = [a["id"] for a in applied if a["replaced"]]
        parts = []
        if new:
            parts.append(f"Kept {len(new)} passage{'s' if len(new) != 1 else ''}: {', '.join(new)}.")
        if again:
            parts.append(f"Replaced the reason for {', '.join(again)}.")
        parts.append(f"{len(kept)} passage{'s are' if len(kept) != 1 else ' is'} kept in all.")
        text = " ".join(parts)
        if refused:
            text += "\nNot kept:\n" + "\n".join(r["why"] for r in refused)
        extra = {"kept": applied, "kept_count": len(kept)}
        if refused:
            extra["refused"] = refused
        return _Out([text], False, extra, None, [], [a["id"] for a in applied])

    def submit(self, inp, same_turn: bool) -> tuple[_Out, object, bool]:
        """submit_answer(out_of_scope, note?) (T1.10 amended by P4.16 and P4.19): rule 1, the input check, the note cap
        (P4.6), rule 2, rule 3, then `no_note`. Research never sees a web page, so its call is stored as Claude sent
        it: no copy guard and no findings check (P4.19). Returns the result, the input as stored and whether it was
        accepted."""
        def refuse(rule, text):
            log.info("run %s: submit_answer refused (%s)", self.ctx.run_id, rule)
            return _Out([text], True, {"submit": {"accepted": False, "rule": rule}}), inp, False

        if same_turn:                                                                     # rule 1
            return refuse("same_turn", rejection("submit", "rule_1_same_turn"))
        try:                                                                              # the input check
            check_fields("submit_answer", inp, ("out_of_scope", "note"), ("out_of_scope",))
            if not isinstance(inp["out_of_scope"], bool):
                raise ToolInputError("'out_of_scope' must be true or false.")
            note = text_field(inp, "note")
        except ToolInputError as e:
            return refuse(None, e.message)
        if note is not None and len(note) > NOTE_MAX:                                    # P4.6
            return refuse("note_too_long", rejection("submit", "note_too_long", length=len(note)))
        out_of_scope = inp["out_of_scope"]
        if not out_of_scope:
            if not self.run.corpus_searched:                                              # rule 2
                return refuse("no_search", rejection("submit", "rule_2_no_search"))
            if not self.run.kept and not note:                                            # rule 3
                return refuse("nothing_kept", rejection("submit", "rule_3_nothing_kept"))
        elif not note:                                                                    # T1.10, v1.3
            return refuse("no_note", rejection("submit", "out_of_scope_no_note"))
        self.accepted = {"out_of_scope": out_of_scope, "note": note}
        n = len(self.run.kept)
        decision, _ = self.run.update_decision(True, out_of_scope)
        if decision == "start":                       # §4.G.3: the text that opens the update step, sent to Claude
            text = (prompts.message("update_start", passages=prompts.kept_passages_text(n)) if n
                    else prompts.message("update_start_note"))
        elif out_of_scope or not n:                   # never sent
            text = prompts.message("submit_accepted_note")
        else:
            text = prompts.message("submit_accepted_answer", passages=prompts.kept_passages_text(n))
        log.info("run %s: submit_answer accepted", self.ctx.run_id)
        return _Out([text], False, {"submit": {"accepted": True}}), inp, True


# ---------- the update step (§4.G.4) ----------

def findings_shape(findings) -> None:
    """submit_update's input check on `update_findings` (contract v2.0 §4.G.2): each finding exactly {statement,
    sources}. F's checks read only those two, so an extra key would pass unchecked. The message never repeats the
    extra keys, which are Claude's text. A findings value that is not a list is left to the findings checks."""
    if not isinstance(findings, list):
        return
    for n, f in enumerate(findings, 1):
        if not isinstance(f, dict) or set(f) != {"statement", "sources"}:
            raise ToolInputError(f"Finding {n} of 'update_findings' must be an object with exactly the fields "
                                 f"statement and sources, and nothing else.")


class _Update(_Conversation):
    tools_here = UPDATE_TOOLS
    submit_name = "submit_update"

    def __init__(self, run: "_Run", research: _Research):
        super().__init__(run, _update_limits())
        self.research = research
        self.accepted: dict | None = None

    async def start(self) -> _End:
        await self.emit("update_started", {"kept": list(self.run.kept)})
        self.status_for_round = self.status_line(1)
        # §4.G.2: research's messages as they stand, then the accepted submit's result and the update status line
        self.run.messages.append({"role": "user", "content": list(self.research.accepted_results or [])
                                  + [{"type": "text", "text": self.status_for_round}]})
        return await self.rounds()

    def unavailable(self) -> bool:
        return self.ctx.flags.exa_unavailable is not None

    def status_line(self, round_no: int) -> str:
        return prompts.status_line_update(round_no, searches_counted=self.run.counted, unavailable=self.unavailable())

    def end_for_error(self, e: ServiceError) -> _End:
        log.warning("run %s: update call failed (%s)", self.ctx.run_id, e.kind)
        if e.kind in SPEND_STOP:
            return _End("spend_limit", failure_reason=e.kind, stop_kind=SPEND_STOP[e.kind])
        return _End("failed", failure_reason=e.kind)

    def ended_fields(self, end: _End) -> dict:
        """update_ended's data (§6)."""
        k = end.kind
        if k == "submitted":
            e, stop_kind, failure = "submitted", None, None
        elif k == "abandoned":
            e, stop_kind, failure = "abandoned", None, None
        elif k == "spend_limit":
            e, stop_kind, failure = "stopped", end.stop_kind, end.failure_reason
        elif k in UPDATE_STOPS:
            e, stop_kind, failure = "stopped", k, None
        else:                                       # failed, refusal
            e, stop_kind, failure = "failed", None, end.failure_reason or "internal"
        return {"end": e, "stop_kind": stop_kind, "failure_reason": failure, "rounds": self.round_no,
                "searches": self.run.counted}

    # -- no page's words in a refused call (§4.G.2, §1, T2.2, P4.3) --
    def guard_texts(self, texts: list[str]) -> set[int]:
        """The indexes of the texts that repeat COPY_GUARD_WORDS or more consecutive words of a page returned in the
        run, words that are also the corpus's exempt (P4.9). Nothing before any page was returned."""
        if not self.run.pages or not texts:
            return set()
        report = copy_guard_report(texts, None, self.run.page_texts(), COPY_GUARD_WORDS,
                                   exempt=corpus_exemption(self.run.corpus))
        return set(report.flagged_statements)

    def stored(self, inp):
        """§4.G.2: once a page was returned, every update-step call's input as stored and streamed, accepted or
        refused: each text at any depth, keys included, through the copy guard, each flagged one withheld. Claude's
        own conversation keeps its input."""
        flagged = self.guard_texts(texts_in(inp))
        return withhold_texts(inp, flagged) if flagged else inp

    def stored_params(self, params):
        """The band's `searches[].params` and the event's copy of the search result show the same withheld text as
        the stored tool_call (§4.G.2); Exa and Claude get the search as written."""
        if not self.run.pages:
            return params
        fields = [(name, None) for name in ("query", "start_published_date", "end_published_date", "category", "type")
                  if isinstance(getattr(params, name), str)]
        fields += [(name, i) for name in ("include_domains", "exclude_domains") for i in range(len(getattr(params, name)))]
        texts = [getattr(params, name) if i is None else getattr(params, name)[i] for name, i in fields]
        flagged = self.guard_texts(texts)
        if not flagged:
            return params
        changes: dict = {}
        for idx in sorted(flagged):
            name, i = fields[idx]
            if i is None:
                changes[name] = WITHHELD
            else:
                values = list(changes.get(name, getattr(params, name)))
                values[i] = WITHHELD
                changes[name] = tuple(values)
        return dataclasses.replace(params, **changes)

    def guard_out(self, out: _Out) -> _Out:
        """A refused call's result as its event stores it: a string field our code copied from Claude's input (a read
        target, an error message quoting a field) withheld the same way. Claude still gets the text as written."""
        if not self.run.pages:
            return out
        if isinstance(out.extra.get("target"), str) and self.guard_texts([out.extra["target"]]):
            out.extra["target"] = WITHHELD
        content = out.event_content if out.event_content is not None else "\n\n".join(out.blocks)
        if self.guard_texts([content]):
            out.event_content = WITHHELD
        return out

    def wrong_step(self, name: str, inp) -> _Out:
        extra = _wrong_step_extra(name, inp, len(self.run.kept))
        return self.guard_out(_Out([rejection("wrong_step", "research_tool", name=name)], True, extra))

    # -- search_web_updates (T2.1 to T2.5) --
    async def run_own_tool(self, tid: str, name: str, inp) -> _Out:
        """T2.1 to T2.5. Input refused by our code is not counted; Claude gets format_for_claude, the event gets
        format_for_events, so no page text is ever emitted (T2.2, P1.7)."""
        refused = {"web": [], "web_repeats": [], "web_status": "refused_by_us"}
        params = None
        if self.run.counted >= UPDATE_SEARCHES:
            out = _Out([rejection("update_search", "fourth_search")], True, dict(refused))
        else:
            try:
                params = parse_params(inp)
                out = None
            except ToolInputError as e:
                out = _Out([e.message], True, dict(refused))
        if out is not None:                                    # refused by our code
            await self.emit_call(tid, name, self.stored(inp))
            return self.guard_out(out)
        await self.emit_call(tid, name, self.stored(inp))
        shown = self.stored_params(params)                     # against the pages known when the call was stored
        try:
            return await self.search(params, shown)
        except Exception:                       # RunStopped, or an unexpected exception: the call still gets its result
            await self.emit_stopped_result(tid, name)
            raise

    async def search(self, params, shown) -> _Out:
        """`params` go to Exa and Claude; `shown` (the same, guarded) to the band and the event."""
        run = self.run
        search_no = run.counted + 1
        self.start_schema_check()
        outcome = await run.deps.updates.search(params, search_no, run.seen_urls, self.ctx)
        if outcome.kind != "unavailable":
            run.counted += 1
        for pg in outcome.pages:
            run.pages[pg.id] = pg
        run.band_searches.append({"search_no": search_no, "params": params_as_dict(shown), "fixed": fixed_settings(),
                                  "status": outcome.kind, "returned": len(outcome.pages) + len(outcome.repeats),
                                  "undated": outcome.undated})
        log.info("run %s: update search %d %s", self.ctx.run_id, search_no, outcome.kind)
        extra = {"web": [_page_detail(pg) for pg in outcome.pages], "web_repeats": list(outcome.repeats),
                 "web_status": outcome.kind}
        if outcome.kind != "unavailable":
            extra["search_no"] = search_no       # an unavailable search is not counted (T2.4), so it has no number
        out = _Out([format_for_claude(params, outcome)], outcome.kind != "ok", extra,
                   event_content=format_for_events(shown, outcome))
        if outcome.kind == "ok":
            return out
        # A search that did not return pages: its event content carries Exa's own message (refused_by_exa), which can
        # echo a query that repeats a page, so it is guarded as a refused result's content is (§4.G.2). An ok
        # search's content is our header and the pages' details (T2.2), left as D formats it.
        return self.guard_out(out)

    def start_schema_check(self) -> None:
        """T2.5: Exa's tool listing, compared once per instance on its first update search; warnings logged only."""
        updates = self.run.deps.updates
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

    # -- submit_update (T2.3, P4.3, P4.9, P4.13, P4.19) --
    def guard_report(self, inp):
        """The copy guard over the submit's statements (one entry per finding, so the indexes line up), its overview
        and its skip reason, once any page was returned in the run (T2.3 item 3, P4.3, P4.13); runs of words that are
        also the corpus's are exempt (P4.9). None when no page was returned, or there is nothing to guard."""
        if not isinstance(inp, dict) or not self.run.pages:
            return None
        findings = inp.get("update_findings")
        statements = []
        if isinstance(findings, list):
            statements = [f.get("statement") if isinstance(f, dict) and isinstance(f.get("statement"), str) else ""
                          for f in findings]
        overview = inp.get("update_overview") if isinstance(inp.get("update_overview"), str) else None
        skip = inp.get("update_skip_reason")
        skip = skip if isinstance(skip, str) and skip.strip() else None
        if not statements and not overview and not skip:
            return None
        return copy_guard_report(statements, overview, self.run.page_texts(), COPY_GUARD_WORDS, skip_reason=skip,
                                 exempt=corpus_exemption(self.run.corpus))

    def submit(self, inp, same_turn: bool) -> tuple[_Out, object, bool]:
        """submit_update(update_findings?, update_overview?, update_skip_reason?) (§4.G.4): rule 1, the input check,
        the findings checks, the copy guard, then `no_check` (refused every time, waived once the update check became
        unavailable during the step). A refused call is stored with each flagged statement, a flagged overview and a
        flagged skip reason withheld, whichever rule refuses it (P4.3, P4.13); every call, accepted too, has every
        other text of it guarded as well (§4.G.2). Returns the result, the input as stored and whether it was
        accepted."""
        run = self.run
        guard = self.guard_report(inp)
        shown = inp
        if guard is not None and (guard.flagged_statements or guard.overview_flagged or guard.skip_reason_flagged):
            shown = withhold_flagged(inp, guard.flagged_statements, guard.overview_flagged,
                                     skip_reason_flagged=guard.skip_reason_flagged)

        def refuse(rule, text):
            log.info("run %s: submit_update refused (%s)", self.ctx.run_id, rule)
            return (self.guard_out(_Out([text], True, {"submit": {"accepted": False, "rule": rule}})),
                    self.stored(shown), False)

        if same_turn:                                                                     # rule 1
            return refuse("same_turn", rejection("submit_update", "rule_1_same_turn"))
        try:                                                                              # the input check
            check_fields("submit_update", inp, ("update_findings", "update_overview", "update_skip_reason"))
            skip = text_field(inp, "update_skip_reason")
            findings_shape(inp.get("update_findings"))
        except ToolInputError as e:
            return refuse(None, e.message)
        findings, overview = inp.get("update_findings"), inp.get("update_overview")
        if findings is not None or overview is not None:                                 # T2.3 item 2
            problems = check_update_findings(findings, overview, set(run.pages), run.counted)
            if problems:
                return refuse("findings", rejection("submit_update", "findings_problems", problems="\n".join(problems)))
        if guard is not None and guard.problems:                                          # T2.3 item 3
            if guard.skip_reason_flagged and not (guard.flagged_statements or guard.overview_flagged):
                text = rejection("submit_update", "copy_guard_skip_reason", pages=pages_named(guard.skip_reason_pages))
            else:
                text = rejection("submit_update", "copy_guard", problems="\n".join(guard.problems))
            return refuse("copy_guard", text)
        if run.counted == 0 and not skip and not self.unavailable():                    # no_check, waived (P2.11)
            return refuse("no_check", rejection("submit_update", "no_check"))
        self.accepted = {"skip": skip,
                         "findings": [{"statement": f["statement"], "sources": list(f["sources"])}
                                      for f in findings or []],
                         "overview": overview if isinstance(overview, str) and overview.strip() else None}
        run.update_accepted = self.accepted
        log.info("run %s: submit_update accepted", self.ctx.run_id)
        return (_Out([prompts.message("submit_update_accepted")], False, {"submit": {"accepted": True}}),
                self.stored(inp), True)


# ---------- the run (§4.G.1) ----------

class _Run:
    def __init__(self, ctx: RunContext, deps: LoopDeps):
        self.ctx, self.deps, self.corpus = ctx, deps, deps.corpus
        self.system_text = _loop_system(self.corpus)
        self.tool_list = build_tool_list()
        self.ratio = chars_per_token(self.corpus)
        self.messages: list[dict] = []              # one conversation: research, then the update step (§4.G.2)
        self.last_ok: tuple[int, int, int] | None = None   # (total input, output, messages in that request)
        self.calls = 0                              # the run's one counter of Claude calls
        self.stops: list[str] = []                  # every budget or limit stop, in order (v1.4)
        self.emitted: set[str] = set()              # passages with a `passage` event
        self.kept: dict[str, KeptPassage] = {}
        self.corpus_searched = False
        self.pages: dict[str, WebPage] = {}         # every page returned in the run; text only for Claude and the guard
        self.band_searches: list[dict] = []
        self.counted = 0                            # update searches that count (T2.1)
        self.seen_urls: dict[str, str] = {}
        self.update_accepted: dict | None = None
        self.update_end: dict | None = None
        self.warned: set[str] = set()
        self.answer_texts: list[str] = []
        self.research: _Research | None = None

    # -- events --
    async def emit(self, kind: str, data: dict) -> int:
        return await self.ctx.emit(kind, data)

    async def ensure_passage(self, pid: str) -> None:
        if pid not in self.emitted:
            self.emitted.add(pid)
            await self.emit("passage", fmt.passage_event(self.corpus.passages[pid]))

    async def emit_warnings(self) -> None:
        """The Voyage warning (T3.3), once each, from ctx.flags."""
        for flag, code in WARNINGS:
            if getattr(self.ctx.flags, flag) and code not in self.warned:
                self.warned.add(code)
                await self.emit("warning", {"code": code})

    def next_call_no(self) -> int:
        self.calls += 1
        return self.calls

    def page_texts(self) -> dict[str, str]:
        return {pid: pg.text for pid, pg in self.pages.items()}

    def add_stop(self, kind: str | None) -> None:
        """A budget or limit stop, recorded once, in the order it happened, from any step (v1.4, §4.G.6)."""
        if kind and kind not in self.stops:
            self.stops.append(kind)

    def update_unavailable(self) -> str | None:
        """Why the update check is unavailable for this run, or None while it is available (T2.4)."""
        if self.ctx.flags.exa_unavailable is not None:
            return self.ctx.flags.exa_unavailable
        return None if self.ctx.update_check_available else "no_credit"

    def update_decision(self, submitted: bool, out_of_scope: bool) -> tuple[str, str | None]:
        return update_decision(submitted=submitted, out_of_scope=out_of_scope, corpus_searched=self.corpus_searched,
                               unavailable=self.update_unavailable())

    # -- tokens --
    def est(self, text: str) -> int:
        return math.ceil(len(text) / self.ratio)

    def est_json(self, obj) -> int:
        return self.est(json.dumps(obj, ensure_ascii=False))

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

    async def record_usage(self, purpose: str, usage: Usage, shown: dict | None, *, call_no: int | None, attempt: int,
                           outcome: str, error_kind, duration_ms: int) -> Usage:
        """One attempt, through H's record_usage (the agreed convention): `usage` is what E prices; `raw_usage` is
        Claude's usage object (marked estimated on a failed attempt), or None when it reported none (§6)."""
        await self.ctx.record_usage(usage, purpose=purpose, attempt=attempt, max_attempts=MAX_ATTEMPTS,
                                    outcome=outcome, error_kind=error_kind, duration_ms=duration_ms,
                                    raw_usage=shown, call_no=call_no)
        return usage

    # -- the requests --
    def conversation_request(self, model: str, effort: str, max_tokens: int) -> dict:
        """One request of the research conversation, for research and the update step alike (P2.1, T1.14, T3.3,
        P4.19): every field but `max_tokens` and `messages` is the same in both, key order included, so the update
        step reads research's cache (§4.G.2). Sources, read Oct 24, 2026:
        - thinking: adaptive (https://platform.claude.com/docs/en/build-with-claude/adaptive-thinking); display left
          at its default, omitted (T3.1);
        - effort: `output_config.effort` (https://platform.claude.com/docs/en/build-with-claude/effort);
        - caching: a 1-hour breakpoint on the system prompt (tools, system prompt and catalog come before it in the
          prefix), plus top-level automatic caching (5 minutes) for the growing conversation; a 1-hour entry must
          come before 5-minute ones (https://platform.claude.com/docs/en/build-with-claude/prompt-caching); a cache
          entry is read only when everything before it is identical, tools first;
        - tool_choice left at auto: forced tool use is a 400 on this model
          (https://platform.claude.com/docs/en/api/errors, "Forced tool use not supported")."""
        return {
            "model": model,
            "max_tokens": max_tokens,
            "system": [{"type": "text", "text": self.system_text, "cache_control": {"type": "ephemeral", "ttl": "1h"}}],
            "tools": self.tool_list,
            "messages": list(self.messages),
            "thinking": {"type": "adaptive"},
            "output_config": {"effort": effort},
            "cache_control": {"type": "ephemeral"},
        }

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
            "limits": {"rounds": MAX_ROUNDS, "loop_input_tokens": LOOP_INPUT_BUDGET,
                       "loop_output_tokens": LOOP_OUTPUT_BUDGET, "update_rounds": UPDATE_MAX_ROUNDS,
                       "update_input_tokens": UPDATE_INPUT_BUDGET, "update_output_tokens": UPDATE_OUTPUT_BUDGET,
                       "update_searches": UPDATE_SEARCHES, "composition_max_tokens": COMPOSITION_MAX_TOKENS,
                       "deadline_s": RUN_DEADLINE_S},
            "coverage": {k: cov[k] for k in ("latest_decision_full_pull", "latest_decision_in_corpus", "ingested")},
            "update_check_available": bool(self.ctx.update_check_available),
            "models": {"loop": LOOP_MODEL, "update": UPDATE_MODEL, "composition": COMPOSITION_MODEL},
            "corpus_label": self.ctx.corpus_label,
        })
        self.research = research = _Research(self)
        end = await research.start()
        log.info("run %s: research ended (%s) after %d rounds", self.ctx.run_id, end.kind, research.round_no)
        await self.emit_warnings()
        if end.kind in LIMIT_STATE:
            self.add_stop(end.kind)          # before composing, so a failed composition still records it (v1.4)
        if end.kind == "spend_limit":
            self.add_stop(end.stop_kind)
        plan = self.plan(end)
        accepted = research.accepted
        decision, reason = self.update_decision(end.kind == "submitted",
                                                bool(accepted and accepted["out_of_scope"]))
        update_task = None
        if decision == "start":
            # §4.G.1 item 4: the update task is created first, so with the fakes the stream is deterministic
            update_task = asyncio.create_task(self.update_branch(research))
        else:
            log.info("run %s: update step not started (%s)", self.ctx.run_id, decision)
            await self.emit("update_band", self.band(started=False, unavailable=reason))
        comp_task = asyncio.create_task(self.compose(plan.scope)) if plan.final is None else None
        try:
            comp = await comp_task if comp_task is not None else None
        except BaseException:
            # §4.G.1 item 6: an unexpected exception (or our own cancellation) in the composition cancels the update
            # step, which emits nothing more; the original is re-raised as it is, never as an ExceptionGroup.
            if update_task is not None and not update_task.done():
                update_task.cancel()
                await asyncio.wait({update_task})
            if update_task is not None and not update_task.cancelled() and update_task.exception() is not None:
                log.error("run %s: the cancelled update step raised %s", self.ctx.run_id,
                          type(update_task.exception()).__name__)
            raise
        if update_task is not None:
            await update_task                # never raises (§4.G.1 item 5), unless this run is cancelled
        await self.close(**self.end_fields(plan, comp))

    def plan(self, end: _End) -> _Plan:
        """Research's end, as v1.9's (§4.G.6): what the run ends with, or what the composition completes."""
        k = end.kind
        if k == "abandoned":
            return _Plan(final={"state": "abandoned"})                    # T3.2: composes nothing
        if k == "spend_limit":
            return _Plan(final={"state": "spend_limit", "stop_kind": end.stop_kind})
        if k == "refusal":
            return _Plan(final={"state": "refusal", "failure_reason": "refusal"})
        if k == "failed":
            return _Plan(final={"state": "failed", "failure_reason": end.failure_reason})
        if k == "submitted":
            sub = self.research.accepted
            if sub["out_of_scope"]:
                return _Plan(final={"state": "no_sources", "no_sources_reason": "out_of_scope", "note": sub["note"]})
            if not self.kept:
                return _Plan(final={"state": "no_sources", "no_sources_reason": "nothing_found", "note": sub["note"]})
            return _Plan(state="answered", scope=sub["note"])
        if k in LIMIT_STATE:
            if not self.kept:
                return _Plan(final={"state": LIMIT_STATE[k], "stop_kind": k})   # T1.11: nothing kept, nothing composed
            return _Plan(state=LIMIT_STATE[k], stop_kind=k)
        if k == "error_stopped":
            if not self.kept:
                return _Plan(final={"state": "failed", "failure_reason": end.failure_reason})     # T3.3
            return _Plan(state="error_stopped", base_failure=end.failure_reason)
        raise AssertionError(f"unknown research end {k}")

    def end_fields(self, plan: _Plan, comp: _Comp | None) -> dict:
        """run_ended's fields from research's end and the composition's (§6, v1.3)."""
        if plan.final is not None:
            return plan.final
        if comp.outcome == "abandoned":
            return {"state": "abandoned"}
        if comp.outcome == "spend":
            return {"state": "spend_limit", "stop_kind": comp.stop_kind}
        if comp.outcome == "refused":
            return {"state": "refusal", "failure_reason": "refusal"}
        if comp.outcome == "failed":
            return {"state": "failed", "failure_reason": comp.kind}
        scope_note = plan.scope if plan.state == "answered" else None
        if comp.outcome == "complete":
            return {"state": plan.state, "stop_kind": plan.stop_kind, "failure_reason": plan.base_failure,
                    "answer_end": "complete", "scope_note": scope_note}
        if comp.outcome == "cut_off":
            return {"state": plan.state, "stop_kind": plan.stop_kind or "composition_max_tokens",
                    "failure_reason": plan.base_failure, "answer_end": "cut_off", "scope_note": scope_note}
        return {"state": plan.state, "stop_kind": plan.stop_kind, "failure_reason": comp.kind,
                "answer_end": "incomplete", "scope_note": scope_note}

    async def update_branch(self, research: _Research) -> None:
        """The update step, then update_ended and update_band (§4.G.4). Never raises out of itself (§4.G.1 item 5):
        an unexpected exception ends the step `failed` with `internal`. Its own cancellation propagates, and then it
        emits nothing more. It never changes the answer or the run's own end."""
        step = None
        try:
            step = _Update(self, research)
            end = await step.start()
            fields = step.ended_fields(end)
            log.info("run %s: update step ended (%s) after %d rounds", self.ctx.run_id, end.kind, step.round_no)
        except Exception as e:
            log.error("run %s: the update step raised %s; ended as failed (internal)", self.ctx.run_id,
                      type(e).__name__)
            fields = {"end": "failed", "stop_kind": None, "failure_reason": "internal",
                      "rounds": step.round_no if step is not None else 0, "searches": self.counted}
        try:
            self.add_stop(fields["stop_kind"])
            self.update_end = fields
            await self.emit("update_ended", fields)
            await self.emit("update_band", self.band(started=True))
        except Exception as e:
            log.error("run %s: the update step's end could not be emitted (%s)", self.ctx.run_id, type(e).__name__)

    def band(self, *, started: bool, unavailable: str | None = None) -> dict:
        sub = self.update_accepted
        end = self.update_end or {}
        if started:
            unavailable = self.ctx.flags.exa_unavailable          # became unavailable during the step
        findings = sub["findings"] if sub else []
        outcome, reason = band_outcome(started=started, unavailable=unavailable, searches_counted=self.counted,
                                       submitted=sub is not None, findings=findings,
                                       skip_reason=sub["skip"] if sub else None, end=end.get("end"),
                                       stop_kind=end.get("stop_kind"), failure_reason=end.get("failure_reason"))
        return {"outcome": outcome, "reason": reason, "searches": self.band_searches, "findings": findings,
                "overview": sub["overview"] if sub else None,
                "pages": [_page_detail(pg) for pg in self.pages.values()]}

    async def close(self, state: str, *, stop_kind=None, failure_reason=None, no_sources_reason=None, note=None,
                    scope_note=None, answer_end: str = "none") -> None:
        self.add_stop(stop_kind)             # already recorded where it happened; kept as the end's own, in case
        await self.emit("run_ended", {
            "state": state, "stop_kind": stop_kind, "stop_kinds": list(self.stops),
            "no_sources_reason": no_sources_reason, "note": note, "scope_note": scope_note, "answer_end": answer_end,
            "failure_reason": failure_reason, "rounds": self.research.round_no if self.research else 0,
            "answer_chars": sum(len(t) for t in self.answer_texts), "totals": self.ctx.totals()})
        log.info("run %s: ended %s (%s), %d rounds", self.ctx.run_id, state, stop_kind or failure_reason or answer_end,
                 self.research.round_no if self.research else 0)

    # -- composition (T1.8 amended by P4.20, T1.9, T1.11; §4.G.5) --
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
        """COMPOSITION_MODEL (Sonnet 5.5, P4.20) at COMPOSITION_EFFORT, adaptive thinking, uncached (T1.11, T3.3),
        `max_tokens` COMPOSITION_MAX_TOKENS (16,000, P4.18), custom content documents with citations enabled (T1.9)."""
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
        # Estimated only to price an attempt that fails with no usage (T3.3); nothing to compare it with (P4.18).
        est = self.est(request["system"]) + self.est_json(request["messages"])
        blocks: list[tuple[int, dict, list[dict]]] = []
        st = {"started": False, "dropped": 0, "mismatched": 0}
        att = _Attempts(self, "composition", COMPOSITION_MODEL, est)

        async def before(n: int) -> None:
            await att.gate(n)

        async def on_block(ci: int, block: dict) -> None:
            cits, dropped, mismatched = map_citations(block, docs, self.corpus, att.call_no, ci)
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
                await self.emit("composition_started", {"call_no": att.call_no, "documents": docs})
                for i, pid in enumerate(docs):
                    await self.emit("api_fragment", {"step": "composition", "passage_id": pid,
                                                     "call_no": att.call_no, "role": "request",
                                                     "path": f"messages[0].content[{i}]", "json": documents[i]})
            try:                           # only an attempt handed to the streamer is recorded
                return await self.deps.anthropic.stream(request, COMPOSITION_CALL_DEADLINE_S, on_block,
                                                        step="composition")
            except ServiceError as e:
                att.failed_now(e)
                if blocks:
                    return _Broken(e)          # T3.3: never retried once a block was shown
                raise
            except asyncio.CancelledError as e:
                await att.cancelled(e)
                raise
            except Exception as e:
                await att.unexpected(e)
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
                self.add_stop(SPEND_STOP[e.kind])
                return _Comp("spend", stop_kind=SPEND_STOP[e.kind])
            return _Comp("failed", kind=e.kind)
        except asyncio.CancelledError:
            await att.flush("failed")
            raise
        if st["dropped"] or st["mismatched"]:
            # v1.3: a mapping fault; nothing was attached for these, so the page lights no sentence Claude did not cite
            log.error("run %s: composition call %d: %d citation(s) pointed outside the documents and %d disagreed "
                      "with our sentences; none was attached", self.ctx.run_id, att.call_no, st["dropped"],
                      st["mismatched"])
        if isinstance(res, _Broken):
            await att.failed_finally(res.error)
            self.add_stop(SPEND_STOP.get(res.error.kind))
            await self.response_fragments(blocks, att.call_no)
            await self.run_checks(docs)
            return _Comp("incomplete", kind=res.error.kind)
        refused = res.stop_reason == "refusal"
        await att.completed(res, "failed" if refused else "ok", "refusal" if refused else None)
        if res.stop_reason == "max_tokens":
            self.add_stop("composition_max_tokens")          # recorded even if nothing usable came of it (v1.4)
        await self.response_fragments(blocks, att.call_no)
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
                await self.emit("api_fragment", {"step": "composition", "passage_id": pid, "call_no": call_no,
                                                 "role": "response", "path": f"content[{ci}]", "json": block})

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
