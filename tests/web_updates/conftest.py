"""Fakes for part D's tests: a minimal Store and RunContext of our own (builder E's MemoryStore and H's context
are separate work). Every page, title and URL in these tests is synthetic; no real web text is committed."""

from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from api.types import RunFlags, RunStopped, Usage
from api.web_updates.exa import FakeExaTransport, UpdateSearch

CHICAGO = ZoneInfo("America/Chicago")
LIST_PRICE = {"auto": 0.007, "lite": 0.004}   # T2.4: what a failed search is recorded at (E's job in production)


class FakeStore:
    """Only the three Store methods part D uses. `calls` records them in order."""

    def __init__(self, flag_until: datetime | None = None, *, read_fails: bool = False, writes_fail: bool = False):
        self.flag = flag_until
        self.read_fails = read_fails
        self.writes_fail = writes_fail
        self.calls: list[tuple] = []

    async def flag_until(self, name, now):
        self.calls.append(("flag_until", name))
        if self.read_fails:
            raise ConnectionError("atlas down")
        return self.flag if name == "exa_out_of_credit" else None

    async def set_flag(self, name, now):
        self.calls.append(("set_flag", name))
        if self.writes_fail:
            raise ConnectionError("atlas down")
        self.flag = datetime(2026, 11, 1, tzinfo=CHICAGO)

    async def record_stop(self, kind, run_id, now, detail):
        self.calls.append(("record_stop", kind, run_id, dict(detail)))
        if self.writes_fail:
            raise ConnectionError("atlas down")

    def names(self) -> list[str]:
        return [c[0] for c in self.calls]


class FakeCtx:
    """The part of RunContext that `search` uses."""

    def __init__(self, *, stop: RunStopped | None = None):
        self.run_id = "run-test-1"
        self.question = "a question"
        self.update_check_available = True
        self.corpus_label = "full"
        self.flags = RunFlags()
        self.stop = stop
        self.before: list[tuple] = []
        self.usages: list[dict] = []
        self.events: list[tuple] = []
        self.order: list[str] = []

    async def emit(self, kind, data):
        self.events.append((kind, data))
        return len(self.events)

    async def before_paid_call(self, service, purpose):
        self.order.append("before_paid_call")
        self.before.append((service, purpose))
        if self.stop:
            raise self.stop

    async def record_usage(self, usage, *, purpose, attempt, max_attempts, outcome, error_kind, duration_ms,
                           raw_usage=None, call_no=None):
        self.order.append("record_usage")
        self.usages.append(dict(usage=usage, purpose=purpose, attempt=attempt, max_attempts=max_attempts,
                                outcome=outcome, error_kind=error_kind, duration_ms=duration_ms))
        return self.price(usage)

    @staticmethod
    def price(usage: Usage | None) -> float:
        if usage is None:
            return 0.0
        if usage.exa_cost_usd is not None:
            return usage.exa_cost_usd
        return LIST_PRICE[usage.model] if usage.estimated else 0.0

    def totals(self):
        return {}

    def seconds_left(self):
        return 600.0


@pytest.fixture
def store():
    return FakeStore()


@pytest.fixture
def ctx():
    return FakeCtx()


@pytest.fixture
def transport():
    return FakeExaTransport()


@pytest.fixture
def searcher(transport, store):
    return UpdateSearch(transport, store)


@pytest.fixture
def make_store():
    return FakeStore


@pytest.fixture
def make_ctx():
    return FakeCtx
