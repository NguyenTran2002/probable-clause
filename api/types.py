"""Types shared across the API's parts (contract §2). Owned by the main session.

Builders import these and never redefine them. A change here is a contract
change: the main session makes it, bumps the contract version and tells every
builder.
"""

from dataclasses import dataclass, field
from typing import Literal, Protocol

OpinionGroup = Literal["majority", "plurality", "concurrence", "dissent"]
Service = Literal["anthropic", "voyage", "exa"]
PassageKind = Literal["paragraph", "footnote"]
Purpose = Literal["loop", "update", "composition", "embed", "rerank", "update_search"]
Step = Literal["research", "update", "composition"]     # contract v2.0, §6: the step an event belongs to
STEP_OF_PURPOSE: dict[str, str] = {"loop": "research", "embed": "research", "rerank": "research",
                                   "update": "update", "update_search": "update", "composition": "composition"}
CallOutcome = Literal["ok", "retrying", "failed"]
CorpusLabel = Literal["full", "before_chatrie"]


@dataclass(frozen=True)
class Passage:
    """One citable unit of the corpus: a content paragraph, or a whole footnote (contract §3)."""
    id: str                       # "katz-1-p1" or "katz-1-n1" (T1.6; opinions counted from 1)
    kind: PassageKind
    case_key: str                 # "katz"
    opinion_id: str               # "katz-1"
    text: str                     # the citable text, exactly as in data/corpus (no markers)
    sentences: tuple[tuple[int, int], ...]   # [start, end) offsets into text; they tile it (T1.9)
    case_name: str
    citation: str                 # as the manifest writes it, e.g. "389 U.S. 347"
    decided: str                  # "1967-12-18"
    slip_opinion: bool            # True for Chatrie: pages are slip pages, restarting in each opinion
    opinion_type: str             # the exact type, e.g. "concurrence in the judgment"
    opinion_groups: tuple[OpinionGroup, ...]   # T1.4's groups; one or two
    authors: tuple[str, ...]      # surnames; empty for per curiam
    joined_by: tuple[str, ...]
    joined_by_source: str         # the manifest's, e.g. "not printed" (P1.18): empty joined_by is then unknown
    section: str | None           # contract §3's label rule
    page_start: int
    page_end: int
    position: int                 # 1-based among the opinion's passages of this kind
    of: int                       # how many passages of this kind the opinion has
    paragraph_kind: str | None    # "text", "quote" or "appendix" for paragraphs; None for footnotes
    footnote_label: str | None    # the printed label, for footnotes
    footnotes: tuple[str, ...] = ()   # IDs of footnotes this paragraph cites, in order of reference
    cited_by: tuple[str, ...] = ()    # IDs of paragraphs citing this footnote
    marker_offsets: tuple[tuple[int, str], ...] = ()  # (offset into text, footnote ID): where "[n. label]" goes in loop text


@dataclass(frozen=True)
class Filters:
    """The optional shared filters of both search tools (T1.4). Empty means unset."""
    cases: tuple[str, ...] = ()
    decided_from: str | None = None   # "YYYY" or "YYYY-MM-DD", inclusive; a year is the whole year
    decided_to: str | None = None
    opinion_types: tuple[OpinionGroup, ...] = ()
    authors: tuple[str, ...] = ()     # surnames, or "per curiam"
    none_of: tuple[str, ...] = ()     # words or quoted phrases to exclude
    include_footnotes: bool = True


@dataclass(frozen=True)
class Hit:
    passage_id: str
    score: float
    reranked: bool = True             # False when meaning search fell back to embedding order (T3.3)


@dataclass(frozen=True)
class Usage:
    """One paid call's usage as its provider reported it (or estimated, T3.3)."""
    service: Service
    model: str                        # Claude or Voyage model; "auto" or "lite" for Exa
    input_tokens: int = 0             # Anthropic: uncached input; Voyage: tokens billed
    cache_write_5m_tokens: int = 0
    cache_write_1h_tokens: int = 0
    cache_read_tokens: int = 0
    output_tokens: int = 0
    exa_cost_usd: float | None = None  # Exa's costDollars when reported
    estimated: bool = False


@dataclass(frozen=True)
class WebPage:
    """One page an update search returned (T2.2). `text` goes to Claude and the copy guard only, never to events."""
    id: str                           # "web-<search>-<n>"
    title: str
    url: str                          # http or https only; other results are dropped (contract §4.D)
    domain: str
    published: str | None             # "YYYY-MM-DD", Exa's date part as written; None if absent or unparseable
    author: str | None
    text: str
    truncated: bool


@dataclass
class RunFlags:
    """Per-run state the search parts read and set (contract §4.C, §4.D). Never shared across runs."""
    voyage_unavailable: bool = False          # a 401, for the rest of this run (T3.3)
    meaning_degraded: bool = False            # some search not reranked (T3.3): the warning
    meaning_unavailable_once: bool = False    # some search had no meaning results (T3.3): the warning
    exa_unavailable: Literal["no_credit", "key_refused"] | None = None   # T2.4
    voyage_spent_usd: float = 0.0             # this run's Voyage spend, held under VOYAGE_RUN_BOUND_USD (T3.4, v1.4)


class RunStopped(Exception):
    """Raised by `before_paid_call` when the run must stop before the next paid call."""
    def __init__(self, reason: Literal["abandoned", "deadline"], detail: str = ""):
        super().__init__(reason, detail)
        self.reason = reason
        self.detail = detail


class RunContext(Protocol):
    """What the loop (G) and the search parts (C, D) get from the lifecycle (H). Contract §6, §4.H."""
    run_id: str
    question: str
    update_check_available: bool
    corpus_label: CorpusLabel
    flags: RunFlags

    async def emit(self, kind: str, data: dict) -> int:
        """Store and stream one event; returns its number. Never blocks on Atlas. Safe to call from the update step
        and the composition at once: numbers follow the order of the calls, with no gap (contract v2.0)."""

    async def before_paid_call(self, service: Service, purpose: Purpose) -> None:
        """Wait while paused; raise RunStopped("abandoned") if abandoned, or RunStopped("deadline")
        past the run deadline (never for purpose "composition", contract §4.H). Safe to call from the update step
        and the composition at once: one `paused` and one `resumed` per pause (contract v2.0)."""

    async def call_not_billed(self, service: Service, purpose: Purpose) -> None:
        """A call `before_paid_call` cleared was refused before anything was billed (Exa's 402 or 401, T2.4), so no
        `record_usage` follows it (contract v1.4)."""

    async def record_usage(self, usage: Usage | None, *, purpose: Purpose, attempt: int, max_attempts: int,
                           outcome: CallOutcome, error_kind: str | None, duration_ms: int,
                           raw_usage: dict | None = None, call_no: int | None = None) -> float:
        """The one emitter of `paid_call` events: prices the attempt (T3.3, T3.4), records its cost to the day's
        and month's spend (P4.21), adds it to the totals, emits the event with the `step` of its purpose
        (STEP_OF_PURPOSE), and returns its cost in dollars."""

    def totals(self) -> dict:
        """The run's totals in contract §6.2's shape, kept by record_usage."""

    def seconds_left(self) -> float:
        """Until the run deadline (T3.5)."""


@dataclass
class KeptPassage:
    passage_id: str
    reason: str
    kept_at_round: int
    history: list[str] = field(default_factory=list)   # earlier reasons, replaced by re-keeps (T1.7)
