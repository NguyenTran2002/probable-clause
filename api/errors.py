"""Errors shared across the API's parts (contract §2). Owned by the main session."""

from typing import Literal

from api.types import Service

# The closed vocabulary every client classifies its failures into (contract §2).
# api/retry.py decides from it which failures are retried (T3.3).
ErrorKind = Literal[
    "rate_limited",     # 429 from request rate limits (Anthropic, Voyage)
    "spend_cap",        # Anthropic 429 for the usage tier's spend cap: never retried (T3.3)
    "spend_limit",      # Anthropic 400 for the Console workspace's spend limit: never retried (T3.3, T3.4)
    "overloaded",       # Anthropic 529
    "server_error",     # 500 and other 5xx not listed here
    "gateway_timeout",  # 504
    "connection",       # connection refused, reset or dropped before a response began
    "stream_broken",    # an error after a loop call's stream began (T3.3)
    "timeout",          # a per-request timeout of a client we set (Voyage 10 s, Exa 30 s)
    "deadline",         # our own per-call deadline on a Claude call: never retried (T3.3)
    "refusal",          # Claude's `refusal` stop reason (T3.3)
    "bad_request",      # 400 other than spend_limit
    "auth",             # 401
    "permission",       # 403
    "not_found",        # 404
    "too_large",        # 413
    "no_credit",        # Exa 402 NO_MORE_CREDITS (T2.4)
    "protocol",         # an MCP or HTTP protocol error
    "unreadable",       # a reply our code cannot parse
    "internal",         # an unexpected exception in our own code: H's `failed` (contract v1.2)
]


class ToolInputError(Exception):
    """Bad input from Claude. Becomes an error tool_result, shown as a step (T3.7).

    `message` is written to Claude: what was wrong and how to fix it.
    """

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


class ServiceError(Exception):
    """An outside service failed. `retry_after_s` carries a retry-after header when one was sent."""

    def __init__(self, service: Service, kind: ErrorKind, status: int | None = None, message: str = "",
                 retry_after_s: float | None = None):
        super().__init__(service, kind, status, message)
        self.service = service
        self.kind = kind
        self.status = status
        self.message = message
        self.retry_after_s = retry_after_s
