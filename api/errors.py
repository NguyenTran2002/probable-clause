"""Errors shared across the API's parts (contract §2). Owned by the main session."""

from api.types import Service


class ToolInputError(Exception):
    """Bad input from Claude. Becomes an error tool_result, shown as a step (T3.7).

    `message` is written to Claude: what was wrong and how to fix it.
    """

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


class ServiceError(Exception):
    """An outside service failed. `kind` is the part's own classification
    (for example "rate_limited", "overloaded", "server_error", "connection",
    "timeout", "auth", "no_credit", "bad_request")."""

    def __init__(self, service: Service, kind: str, status: int | None = None, message: str = ""):
        super().__init__(service, kind, status, message)
        self.service = service
        self.kind = kind
        self.status = status
        self.message = message
