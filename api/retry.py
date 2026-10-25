"""Our own retries for Anthropic and Voyage calls (T3.3; contract §4.R). Owned by the main session.

Exa is never retried by our code (T2.4). Every attempt is preceded by
`before_attempt` (the heartbeat and deadline check, T3.2) and every retry is
announced through `on_retry`, so it shows as a step and is logged.
"""

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import TypeVar

from api import settings
from api.errors import ErrorKind, ServiceError

T = TypeVar("T")


@dataclass(frozen=True)
class RetryPolicy:
    retries: int                       # retries after the first attempt
    waits_s: tuple[float, ...]         # wait before retry 1, 2, ...
    retryable: frozenset[ErrorKind]
    honour_retry_after: bool


# T3.3: up to 2 retries on a rate-limit 429, 500, 504, 529, a connection failure, or an error after a loop
# call's stream began. Never: 400, 401, 403, 404, 413, the spend-cap 429, a refusal, or our own deadline.
# "stream_broken" is raised only by loop calls; a composition that fails after its first block is not
# retried, and the composition code raises a non-retryable kind in that case (T3.3).
ANTHROPIC_POLICY = RetryPolicy(
    retries=int(settings.ANTHROPIC_RETRIES.value),
    waits_s=tuple(settings.waits(settings.ANTHROPIC_RETRY_WAITS_S)),
    retryable=frozenset({"rate_limited", "server_error", "gateway_timeout", "overloaded", "connection", "stream_broken"}),
    honour_retry_after=True,
)

# T3.3: 10 s per request, up to 2 retries at 1 s then 3 s. Which failures: the transient ones (Claude's call,
# contract §4.R); a 401 is never retried and makes meaning search unavailable for the run.
VOYAGE_POLICY = RetryPolicy(
    retries=int(settings.VOYAGE_RETRIES.value),
    waits_s=tuple(settings.waits(settings.VOYAGE_RETRY_WAITS_S)),
    retryable=frozenset({"rate_limited", "server_error", "gateway_timeout", "connection", "timeout"}),
    honour_retry_after=True,
)


async def with_retries(
    attempt: Callable[[int], Awaitable[T]],
    policy: RetryPolicy,
    before_attempt: Callable[[int], Awaitable[None]],
    on_retry: Callable[[int, ServiceError, float], Awaitable[None]],
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
) -> T:
    """Run `attempt(n)` for n = 1, 2, ... until it returns, or raise its last ServiceError.

    `on_retry(next_attempt, error, wait_s)` is awaited before each wait. Any exception
    other than ServiceError propagates at once (RunStopped from `before_attempt` included).
    """
    n = 1
    while True:
        await before_attempt(n)
        try:
            return await attempt(n)
        except ServiceError as e:
            if e.kind not in policy.retryable or n > policy.retries:
                raise
            wait = policy.waits_s[min(n - 1, len(policy.waits_s) - 1)]
            if policy.honour_retry_after and e.retry_after_s is not None:
                wait = e.retry_after_s
            await on_retry(n + 1, e, wait)
            await sleep(wait)
            n += 1
