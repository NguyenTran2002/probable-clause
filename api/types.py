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


@dataclass(frozen=True)
class Passage:
    """One citable unit of the corpus: a content paragraph, or a whole footnote (contract §3)."""
    id: str                       # "katz-3-p1" or "katz-3-n1" (T1.6)
    kind: PassageKind
    case_key: str                 # "katz"
    opinion_id: str               # "katz-3"
    text: str                     # the citable text, exactly as in data/corpus (no markers)
    sentences: tuple[tuple[int, int], ...]   # [start, end) offsets into text; they tile it (T1.9)
    case_name: str
    citation: str                 # "389 U.S. 347", as the manifest writes it
    decided: str                  # "1967-12-18"
    opinion_type: str             # the exact type, e.g. "concurrence in the judgment"
    opinion_groups: tuple[OpinionGroup, ...]   # T1.4's groups; one or two
    authors: tuple[str, ...]      # surnames; empty for per curiam
    joined_by: tuple[str, ...]
    section: str | None           # label from numbered headings and appendix titles only (T1.6)
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
    decided_from: str | None = None   # "YYYY" or "YYYY-MM-DD", inclusive
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
    model: str
    input_tokens: int = 0             # Anthropic: uncached input
    cache_write_5m_tokens: int = 0
    cache_write_1h_tokens: int = 0
    cache_read_tokens: int = 0
    output_tokens: int = 0
    exa_cost_usd: float | None = None  # Exa's costDollars when reported
    estimated: bool = False


@dataclass(frozen=True)
class WebPage:
    """One page an update search returned (T2.2). `text` goes to Claude only, never to events."""
    id: str                           # "web-<search>-<n>"
    title: str
    url: str
    domain: str
    published: str | None             # "YYYY-MM-DD", Exa's date part as written; None if absent
    author: str | None
    text: str
    truncated: bool


class RunStopped(Exception):
    """Raised inside the loop when the run must stop before the next paid call."""
    def __init__(self, reason: Literal["abandoned", "deadline", "budget", "spend_limit"], detail: str = ""):
        super().__init__(reason, detail)
        self.reason = reason
        self.detail = detail


class RunContext(Protocol):
    """What the loop (G) gets from the lifecycle (H) and the budget (E). Contract §6."""
    run_id: str
    question: str
    update_check_available: bool

    async def emit(self, kind: str, data: dict) -> int:
        """Store and stream one event; returns its number. Never blocks on Atlas."""

    async def before_paid_call(self, service: Service, purpose: str) -> None:
        """Wait while paused; raise RunStopped if abandoned, past the deadline, or over budget."""

    async def record_usage(self, usage: Usage, purpose: str, attempt: int, ok: bool) -> float:
        """Price the call, move it from reserved to spent, return its cost in dollars."""

    def seconds_left(self) -> float:
        """Until the run deadline (T3.5)."""


@dataclass
class KeptPassage:
    passage_id: str
    reason: str
    kept_at_round: int


@dataclass
class RunTotals:
    calls: dict[str, int] = field(default_factory=dict)          # by purpose
    tokens: dict[str, int] = field(default_factory=dict)         # input, cache_read, cache_write, output
    cost_usd: dict[str, float] = field(default_factory=dict)     # loop, composition, exa, voyage
