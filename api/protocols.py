"""The Atlas store's interface (contract §4.E, §8). Owned by the main session.

E implements it twice (MongoStore, MemoryStore); every other part codes against
this protocol. Contract v2.0 (P4.21): no reservation. A run is admitted while
spend is under the caps, and each paid call's cost is recorded as it happens.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Literal, Protocol

StopKind = Literal[
    "daily_cap", "monthly_cap", "step_limit", "token_ceiling_input", "token_ceiling_output",
    "composition_max_tokens", "console_spend_limit", "tier_spend_cap", "exa_no_credit", "time_limit",
    "update_step_limit", "update_token_ceiling_input", "update_token_ceiling_output", "update_time_limit",
    "atlas_unreachable",
]
# T3.4; the limit stops (time_limit, update_time_limit) and atlas_unreachable are not budget stops
BUDGET_STOPS: frozenset[str] = frozenset(StopKind.__args__) - {"atlas_unreachable", "time_limit", "update_time_limit"}


@dataclass(frozen=True)
class Admission:
    """A run admitted (P4.21): its spend counts toward this Chicago day and month (contract §4.E)."""
    run_id: str
    month: str          # "2026-10", Chicago
    day: str            # "2026-10-24", Chicago


@dataclass(frozen=True)
class Refusal:
    kind: Literal["daily_cap", "monthly_cap", "atlas_unreachable", "spend_limit_paused"]


class Store(Protocol):
    async def ensure_indexes(self) -> None: ...
    # events (TTL 24 h) and heartbeats (TTL 10 min)
    async def append_events(self, run_id: str, events: list[dict]) -> None: ...
    async def read_events(self, run_id: str, after: int) -> list[dict]: ...
    async def put_heartbeat(self, run_id: str, last_event: int, now: datetime) -> None: ...
    async def latest_heartbeat(self, run_id: str) -> datetime | None: ...
    # per-run records, no question or answer text (T3.7)
    async def upsert_run_record(self, record: dict) -> None: ...
    # money (T3.4 amended by P4.21)
    async def admit(self, run_id: str, now: datetime) -> Admission | Refusal: ...
        # one conditional update: the day's and month's spent under the caps and the spend-limit flag clear;
        # counts the day's runs_started in the same update; records a cap refusal's stop itself (contract §4.E)
    async def record_spend(self, a: Admission, cost_usd: float) -> None: ...
        # one atomic increment of the month's and the day's spent; raises when Atlas can't be reached
    async def record_stop(self, kind: StopKind, run_id: str | None, now: datetime, detail: dict) -> None: ...
    # reads for scripts/spend_report.py and tests
    async def read_month(self, month: str) -> dict | None: ...
    async def read_stops(self, *, day: str | None = None, month: str | None = None) -> list[dict]: ...
    async def get_run_record(self, run_id: str) -> dict | None: ...
    # flags (T2.4, T3.3)
    async def flag_until(self, name: Literal["exa_out_of_credit", "anthropic_spend_limit"], now: datetime) -> datetime | None: ...
    async def set_flag(self, name: Literal["exa_out_of_credit", "anthropic_spend_limit"], now: datetime) -> None: ...
    # /health (T3.4)
    async def live_status(self, now: datetime, timeout_s: float) -> dict: ...
