"""The price table and what a paid call cost (T3.4; contract §10).

One source and one date per provider. Claude and Exa are read from the usage a call reported; a failed attempt
that reported none is priced as T3.3 says (see `failed_attempt_usage`). Prices are USD per million tokens, except
Exa's, which are per search with text.
"""

import math

from api.types import Service, Usage

_PER_M = 1_000_000

PRICE_TABLE: dict = {
    "anthropic": {
        # T3.4: "Anthropic's pricing page, Oct 24, 2026". The main session re-reads the page before the first
        # paid build test and records the date (contract §10).
        "source": "Anthropic's pricing page (https://platform.claude.com/docs/en/about-claude/pricing), as recorded in T3.4",
        "date": "2026-10-24",
        "confirmed": True,
        "unit": "USD per million tokens",
        # Exact ids only. No dated snapshot id is known, so none is listed; add one here explicitly if it is ever seen.
        "models": {
            "claude-sonnet-5-5": {"input": 2.0, "output": 10.0, "cache_write_5m": 2.5, "cache_write_1h": 4.0, "cache_read": 0.10},
            "claude-opus-5-5": {"input": 4.0, "output": 20.0, "cache_write_5m": 5.0, "cache_write_1h": 8.0, "cache_read": 0.20},
        },
    },
    "exa": {
        # contract §10: observed in the Phase 2 paid checks; `costDollars` wins when Exa reports it (T2.4).
        "source": "Exa's list prices for a search with text, observed in the Phase 2 paid checks (phase2-findings §4)",
        "date": "2026-10-24",
        "confirmed": True,
        "unit": "USD per search",
        "types": {"auto": 0.007, "lite": 0.004},
    },
    "voyage": {
        # contract §10: read by the main session before embed_corpus.py --confirm. The key is a Voyage platform key
        # (api.voyageai.com accepted it, scripts/probe_voyage.py, Oct 24, 2026), so Voyage's own page applies.
        # Free tokens (50M for voyage-law-2) are not modelled: list price is the conservative figure for the caps.
        "source": "Voyage AI pricing page (https://docs.voyageai.com/docs/pricing), read Oct 24, 2026",
        "date": "2026-10-24",
        "confirmed": True,
        "unit": "USD per million tokens",
        "models": {"voyage-law-2": 0.12, "rerank-3": 0.05},
    },
}


def price_sources() -> dict:
    """{"anthropic": {"source", "date"}, "exa": {...}, "voyage": {...}}: the `prices` object of contract §6.2."""
    return {p: {"source": PRICE_TABLE[p]["source"], "date": PRICE_TABLE[p]["date"]} for p in ("anthropic", "exa", "voyage")}


def _lookup(models: dict, model: str, service: str):
    """The table's entry for exactly this model id. No prefix or family matching: a dated snapshot id prices only
    if PRICE_TABLE lists it, and none is known yet. Everything else raises, rather than guessing a price."""
    if model not in models:
        raise ValueError(f"no {service} price for model {model!r}: add exactly that id to PRICE_TABLE with its source")
    return models[model]


def list_price_exa(type: str) -> float:
    """Exa's list price for one search of this type ("auto" or "lite")."""
    types = PRICE_TABLE["exa"]["types"]
    if type not in types:
        raise ValueError(f"no Exa list price for search type {type!r}")
    return types[type]


def failed_attempt_usage(service: Service, model: str, estimated_input_tokens: int = 0) -> Usage:
    """The Usage to record for an attempt that failed and reported none (T3.3, T2.4).

    Claude and Voyage: the caller's estimate of the request's input, priced at the uncached input price.
    Exa: no tokens; `price` charges the list price of the search type, which is `model` here (T2.4).
    `price` never invents a token count: a caller passing 0 for Claude or Voyage records $0.
    """
    if service == "exa":
        return Usage(service="exa", model=model, estimated=True)
    return Usage(service=service, model=model, input_tokens=estimated_input_tokens, estimated=True)


def price(u: Usage) -> float:
    """What one paid call cost at list price, in dollars (T3.4)."""
    for name in ("input_tokens", "cache_write_5m_tokens", "cache_write_1h_tokens", "cache_read_tokens", "output_tokens"):
        if getattr(u, name) < 0:
            raise ValueError(f"{name} is negative")
    if u.service == "anthropic":
        p = _lookup(PRICE_TABLE["anthropic"]["models"], u.model, "Anthropic")
        total = (u.input_tokens * p["input"]
                 + u.cache_write_5m_tokens * p["cache_write_5m"]
                 + u.cache_write_1h_tokens * p["cache_write_1h"]
                 + u.cache_read_tokens * p["cache_read"]
                 + u.output_tokens * p["output"])
        return total / _PER_M
    if u.service == "voyage":
        per_m = _lookup(PRICE_TABLE["voyage"]["models"], u.model, "Voyage")
        return u.input_tokens * per_m / _PER_M
    if u.service == "exa":
        if u.exa_cost_usd is not None:
            if not math.isfinite(u.exa_cost_usd) or u.exa_cost_usd < 0:
                raise ValueError("exa_cost_usd must be a finite, non-negative number")
            return float(u.exa_cost_usd)
        return list_price_exa(u.model)
    raise ValueError(f"unknown service {u.service!r}")
