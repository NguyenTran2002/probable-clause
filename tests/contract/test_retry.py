"""api/retry.py follows T3.3: which failures are retried, how many times, with which waits."""

import pytest

from api import settings
from api.errors import ServiceError
from api.retry import ANTHROPIC_POLICY, VOYAGE_POLICY, with_retries


def run(policy, errors, result="ok"):
    """Fail with each error in turn, then return `result`. Returns (result or exception, log)."""
    log, waits = [], []
    seq = list(errors)

    async def attempt(n):
        log.append(("attempt", n))
        if seq:
            raise seq.pop(0)
        return result

    async def before(n):
        log.append(("before", n))

    async def on_retry(n, e, wait):
        log.append(("retry", n, e.kind, wait))

    async def sleep(s):
        waits.append(s)

    async def go():
        return await with_retries(attempt, policy, before, on_retry, sleep)
    return go, log, waits


@pytest.mark.anyio
async def test_overloaded_retried_twice_with_placeholder_waits():
    go, log, waits = run(ANTHROPIC_POLICY, [ServiceError("anthropic", "overloaded", 529)] * 2)
    assert await go() == "ok"
    assert waits == [2.0, 8.0]
    assert [x for x in log if x[0] == "before"] == [("before", 1), ("before", 2), ("before", 3)]


@pytest.mark.anyio
async def test_third_failure_raises():
    go, _, _ = run(ANTHROPIC_POLICY, [ServiceError("anthropic", "server_error", 500)] * 3)
    with pytest.raises(ServiceError):
        await go()


@pytest.mark.anyio
@pytest.mark.parametrize("kind", ["spend_cap", "spend_limit", "deadline", "refusal", "bad_request", "auth",
                                  "permission", "not_found", "too_large"])
async def test_never_retried_anthropic(kind):
    go, log, _ = run(ANTHROPIC_POLICY, [ServiceError("anthropic", kind)])
    with pytest.raises(ServiceError):
        await go()
    assert ("attempt", 2) not in log


@pytest.mark.anyio
async def test_retry_after_wins():
    go, _, waits = run(ANTHROPIC_POLICY, [ServiceError("anthropic", "rate_limited", 429, retry_after_s=5.0)])
    assert await go() == "ok"
    assert waits == [5.0]


@pytest.mark.anyio
async def test_retry_after_past_cap_fails_without_waiting():
    over = settings.RETRY_AFTER_MAX_S.value + 1
    go, log, waits = run(VOYAGE_POLICY, [ServiceError("voyage", "rate_limited", 429, retry_after_s=over)])
    with pytest.raises(ServiceError):
        await go()
    assert waits == [] and ("attempt", 2) not in log


@pytest.mark.anyio
async def test_voyage_timeout_retried_401_not():
    go, _, waits = run(VOYAGE_POLICY, [ServiceError("voyage", "timeout")])
    assert await go() == "ok" and waits == [1.0]
    go, log, _ = run(VOYAGE_POLICY, [ServiceError("voyage", "auth", 401)])
    with pytest.raises(ServiceError):
        await go()

