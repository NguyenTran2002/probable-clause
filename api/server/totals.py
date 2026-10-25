"""A run's totals (contract §6.2, T4.5), kept live by `record_usage` or summed from stored `paid_call` events.

- `calls` (Claude) and `requests` (Voyage) count attempts, since each is billed; Exa's `searches` count the
  searches that reached Exa and were recorded (T2.4).
- `input_tokens` is all input: uncached + cache writes + cache reads.
- Prices come from `price_sources()`.
"""

from api import settings
from api.state.prices import PRICE_TABLE, price_sources
from api.types import Usage

COST_DIGITS = 10          # rounding of dollar figures in events: float noise only, as the fixtures write them


def model_for(purpose: str) -> str:
    """The model each purpose is priced by when a call reported no usage (contract §6, T3.3)."""
    return {
        "loop": str(settings.LOOP_MODEL.value),
        "composition": str(settings.COMPOSITION_MODEL.value),
        "embed": str(settings.EMBED_MODEL.value),
        "rerank": str(settings.RERANK_MODEL.value),
        "update_search": "auto",          # the dearer Exa type: a conservative price when none is known (T3.4)
    }[purpose]


SERVICE_OF_PURPOSE = {"loop": "anthropic", "composition": "anthropic", "embed": "voyage", "rerank": "voyage",
                      "update_search": "exa"}


class Totals:
    def __init__(self) -> None:
        self.claude_calls = 0
        self.input_tokens = 0
        self.cache_read = 0
        self.cache_write = 0
        self.output_tokens = 0
        self.cost = {"loop": 0.0, "composition": 0.0}
        self.exa_searches = 0
        self.exa_cost = 0.0
        self.voyage_requests = 0
        self.voyage_cost = 0.0

    def add(self, service: str, purpose: str, usage: Usage | None, cost: float) -> None:
        if service == "anthropic":
            self.claude_calls += 1
            if usage is not None:
                w = usage.cache_write_5m_tokens + usage.cache_write_1h_tokens
                self.input_tokens += usage.input_tokens + w + usage.cache_read_tokens
                self.cache_read += usage.cache_read_tokens
                self.cache_write += w
                self.output_tokens += usage.output_tokens
            self.cost[purpose] += cost
        elif service == "exa":
            self.exa_searches += 1
            self.exa_cost += cost
        else:
            self.voyage_requests += 1
            self.voyage_cost += cost

    def add_tokens(self, input_tokens: int, cache_read: int, cache_write: int, output: int) -> None:
        self.input_tokens += input_tokens
        self.cache_read += cache_read
        self.cache_write += cache_write
        self.output_tokens += output

    def total_cost(self) -> float:
        return round(self.cost["loop"] + self.cost["composition"] + self.exa_cost + self.voyage_cost, COST_DIGITS)

    def as_dict(self) -> dict:
        r = lambda x: round(x, COST_DIGITS)  # noqa: E731
        return {
            "claude": {"calls": self.claude_calls, "input_tokens": self.input_tokens,
                       "cache_read_tokens": self.cache_read, "cache_write_tokens": self.cache_write,
                       "output_tokens": self.output_tokens,
                       "cost_usd": {"loop": r(self.cost["loop"]), "composition": r(self.cost["composition"])}},
            "exa": {"searches": self.exa_searches, "cost_usd": r(self.exa_cost)},
            "voyage": {"requests": self.voyage_requests, "cost_usd": r(self.voyage_cost)},
            "prices": price_sources(),
        }


def _int(v) -> int:
    return v if isinstance(v, int) and not isinstance(v, bool) and v >= 0 else 0


def totals_from_events(events: list[dict]) -> Totals:
    """The totals of the stored `paid_call` events (the `interrupted` ending, contract §4.H).

    A Claude attempt priced from an estimate is stored with `usage: null` and its priced tokens in
    `estimated_usage` (v1.6). An event without that field (written before v1.6) was priced from its estimated
    input at the uncached price (T3.3), so its input tokens are recovered from its cost.
    """
    t = Totals()
    for e in events:
        if e.get("kind") != "paid_call":
            continue
        d = e.get("data") or {}
        service, purpose = d.get("service"), d.get("purpose")
        cost = d.get("cost_usd") or 0.0
        if service == "anthropic" and purpose in ("loop", "composition"):
            t.add("anthropic", purpose, None, cost)
            u = d.get("usage")
            if u is None and isinstance(d.get("estimated_usage"), dict):
                u = d["estimated_usage"]
            if u is None:
                per_m = PRICE_TABLE["anthropic"]["models"][model_for(purpose)]["input"]
                t.add_tokens(round(cost * 1_000_000 / per_m), 0, 0, 0)
            elif isinstance(u, dict):
                w = _int(u.get("cache_creation_input_tokens"))
                read = _int(u.get("cache_read_input_tokens"))
                t.add_tokens(_int(u.get("input_tokens")) + w + read, read, w, _int(u.get("output_tokens")))
        elif service in ("exa", "voyage"):
            t.add(service, purpose, None, cost)
    return t
