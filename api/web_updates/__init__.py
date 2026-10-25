"""The update check (contract §4.D): Exa's hosted MCP server behind our wrapper tool."""

from api.web_updates.exa import (
    ExaTransport,
    FakeExaTransport,
    McpExaTransport,
    UpdateSearch,
    WebSearchOutcome,
)
from api.web_updates.format import format_for_claude, format_for_events
from api.web_updates.params import (
    WebSearchParams,
    fixed_settings,
    params_as_dict,
    parse_params,
    to_exa_arguments,
)

__all__ = [
    "ExaTransport", "FakeExaTransport", "McpExaTransport", "UpdateSearch", "WebSearchOutcome", "WebSearchParams",
    "fixed_settings", "format_for_claude", "format_for_events", "params_as_dict", "parse_params", "to_exa_arguments",
]
