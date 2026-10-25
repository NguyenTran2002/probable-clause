"""The update check: Exa's hosted MCP server behind our wrapper (contract §4.D; T2.1 to T2.5, P2.8, P2.11).

Rules this module keeps:
  - One MCP session per search (T2.5); the key only in the `x-api-key` header, read from the environment when a call is
    made, never logged and scrubbed out of every error message; the 30 s limit covers the handshake too.
  - A paid call is never retried by our code (T2.4, P2.8). `search` records its usage once, except for a 402 or 401, which
    are not counted and record nothing.
  - No page text is stored or streamed (T2.2, P1.3, P1.7): text lives on `WebPage.text` for Claude and the copy guard
    only; `api/web_updates/format.py` is where it is kept out of events.
  - Logs hold run IDs, numbers, states and error kinds, never queries or page text (T3.7).
"""

import copy
import inspect
import json
import logging
import math
import os
import re
import time
import unicodedata
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime
from typing import Literal, Protocol
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

import anyio
import httpx2
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client
from mcp.shared._httpx_utils import create_mcp_http_client
from mcp.shared.exceptions import MCPError

from api import settings
from api.errors import ErrorKind, ServiceError
from api.protocols import Store
from api.types import RunContext, Usage, WebPage
from api.web_updates.params import (
    CATEGORIES,
    EXA_ARGUMENT_NAMES,
    EXA_TEXT_ARGUMENT,
    TYPES,
    WebSearchParams,
    to_exa_arguments,
)

log = logging.getLogger("api.web_updates")

TOOL_NAME = "web_search_advanced_exa"   # T2.5; scripts/probe_exa.py
KEY_ENV = "EXA_API_KEY"                 # read from the process environment, never from a file (brief §10.7)


# --- the wrapper's result -------------------------------------------------------------------------------------------

@dataclass
class WebSearchOutcome:
    kind: Literal["ok", "refused_by_exa", "failed", "unavailable"]
    unavailable_reason: Literal["no_credit", "key_refused"] | None
    pages: list[WebPage]                  # new pages, in Exa's order
    repeats: list[str]                    # IDs of pages an earlier search in this run returned (T2.2)
    undated: int
    exa_message: str | None               # Exa's own message, for refused_by_exa
    cost_usd: float                       # informational: already recorded through ctx.record_usage


# --- transports -----------------------------------------------------------------------------------------------------

class ExaTransport(Protocol):
    async def call(self, arguments: dict, timeout_s: float) -> dict: ...     # Exa's parsed JSON; raises ServiceError
    async def list_tool_schema(self) -> dict: ...                           # free; for the schema check (T2.5)


_ERROR_TEXT = re.compile(r"^\S+ error(?: \((\d{3})\))?:\s*(.*)$", re.S)
_TIMESTAMP_LINE = re.compile(r"\n?Timestamp:[^\n]*\s*$")


def parse_tool_error(text: str) -> tuple[int | None, str]:
    """Exa's error tool results read `<tool> error (<status>): <message>`, or `<tool> error: <message>` when the
    status is not known, with a trailing `Timestamp:` line (phase2-findings §4; observed for 400 and 401)."""
    text = (text or "").strip()
    m = _ERROR_TEXT.match(text)
    status, message = (int(m.group(1)) if m.group(1) else None, m.group(2)) if m else (None, text)
    return status, _TIMESTAMP_LINE.sub("", message).strip()


def _kind_for_status(status: int) -> ErrorKind:
    if status == 402:
        return "no_credit"
    if status == 401:
        return "auth"
    return {403: "permission", 404: "not_found", 413: "too_large", 429: "rate_limited", 504: "gateway_timeout"}.get(
        status, "bad_request" if 400 <= status < 500 else "server_error")


def _scrub(message: str, key: str | None) -> str:
    return message.replace(key, "[key]") if key else message


def _leaves(e: BaseException):
    """The exceptions inside (possibly nested) exception groups, which anyio's task groups raise."""
    if isinstance(e, BaseExceptionGroup):
        for sub in e.exceptions:
            yield from _leaves(sub)
    else:
        yield e


def _from_mcp_error(e: MCPError, key: str | None) -> ServiceError:
    """A protocol-level error. Gateway failures reach us this way (phase2-findings §4); the HTTP status is not kept
    by the mcp client, so the two that matter are told apart by their message."""
    message = _scrub(str(e.message or ""), key)
    low = message.lower()
    if any(s in low for s in ("authentication required", "invalid api key", "unauthorized")):
        return ServiceError("exa", "auth", 401, message)
    if "rate limit" in low or "too many requests" in low:
        return ServiceError("exa", "rate_limited", 429, message)
    return ServiceError("exa", "protocol", None, message)


def _to_service_error(e: BaseException, key: str | None) -> ServiceError:
    leaves = list(_leaves(e))
    for x in leaves:
        if isinstance(x, ServiceError):
            return x
    for x in leaves:
        if isinstance(x, (TimeoutError, httpx2.TimeoutException)):
            return ServiceError("exa", "timeout", None, "the search timed out")
        if isinstance(x, MCPError):
            return _from_mcp_error(x, key)
        if isinstance(x, httpx2.HTTPStatusError):
            status = x.response.status_code
            return ServiceError("exa", _kind_for_status(status), status, f"HTTP {status}")
        if isinstance(x, (httpx2.TransportError, OSError)):
            return ServiceError("exa", "connection", None, "could not reach Exa")
    return ServiceError("exa", "protocol", None, type(leaves[0]).__name__ if leaves else "unknown")


def _tool_result_to_dict(result, key: str | None) -> dict:
    """Exa's JSON from a tool result, or the ServiceError its error result stands for."""
    blocks = getattr(result, "content", None) or []
    text = "".join(b.text for b in blocks if getattr(b, "type", None) == "text" and isinstance(getattr(b, "text", None), str))
    if getattr(result, "is_error", False):
        status, message = parse_tool_error(text)
        message = _scrub(message, key)
        if status is None and "NO_MORE_CREDITS" in message:
            status = 402
        kind: ErrorKind = _kind_for_status(status) if status is not None else "protocol"
        raise ServiceError("exa", kind, status, message)
    try:
        body = json.loads(text)
    except ValueError:
        raise ServiceError("exa", "unreadable", None, "the reply was not JSON") from None
    if not isinstance(body, dict):
        raise ServiceError("exa", "unreadable", None, "the reply was not a JSON object")
    return body


class McpExaTransport:
    """The real transport: one MCP session per call (T2.5), no retries of our own (T2.4)."""

    def __init__(self, url: str | None = None, tool_name: str = TOOL_NAME):
        self._url = url or str(settings.EXA_MCP_URL.value)
        self._tool = tool_name

    @staticmethod
    def _key() -> str:
        key = (os.environ.get(KEY_ENV) or "").strip()
        if not key:
            raise ServiceError("exa", "auth", None, "no Exa key is configured")   # our configuration fault (T2.4)
        return key

    async def _run(self, timeout_s: float, key: str, work: Callable):
        """Open a session, run `work(session)`, close it, all inside one time limit that covers the handshake."""
        try:
            with anyio.fail_after(timeout_s):
                async with create_mcp_http_client(headers={"x-api-key": key}, timeout=httpx2.Timeout(timeout_s)) as http:
                    async with streamable_http_client(self._url, http_client=http) as (read, write):
                        async with ClientSession(read, write) as session:
                            await session.initialize()
                            return await work(session)
        except Exception as e:
            raise _to_service_error(e, key) from None

    async def call(self, arguments: dict, timeout_s: float) -> dict:
        async def work(session):
            return await session.call_tool(self._tool, arguments)

        key = self._key()                         # the one stripped key: the header sends it, and errors are scrubbed of it
        result = await self._run(timeout_s, key, work)
        return _tool_result_to_dict(result, key)

    async def list_tool_schema(self) -> dict:
        async def work(session):
            return await session.list_tools()

        listing = await self._run(float(settings.EXA_TIMEOUT_S.value), self._key(), work)
        for tool in listing.tools:
            if tool.name == self._tool:
                return dict(getattr(tool, "input_schema", None) or getattr(tool, "inputSchema", None) or {})
        raise ServiceError("exa", "protocol", None, f"{self._tool} is not in the server's tool list")


# What each failure kind looks like on the wire; synthetic messages.
_FAKE_FAILURES: dict[str, tuple[ErrorKind, int | None, str]] = {
    "no_credit": ("no_credit", 402, "Payment required: NO_MORE_CREDITS (synthetic)"),
    "auth": ("auth", 401, "Invalid API key (synthetic)"),
    "key_refused": ("auth", 401, "Invalid API key (synthetic)"),
    "bad_request": ("bad_request", 400, "Invalid request body | a synthetic Exa message"),
    "permission": ("permission", 403, "Forbidden (synthetic)"),
    "not_found": ("not_found", 404, "Not found (synthetic)"),
    "too_large": ("too_large", 413, "Request too large (synthetic)"),
    "rate_limited": ("rate_limited", 429, "Too many requests (synthetic)"),
    "server_error": ("server_error", 503, "Service unavailable (synthetic)"),
    "gateway_timeout": ("gateway_timeout", 504, "Gateway timeout (synthetic)"),
    "connection": ("connection", None, "could not reach Exa"),
    "timeout": ("timeout", None, "the search timed out"),
    "protocol": ("protocol", None, "protocol error (synthetic)"),
    "unreadable": ("unreadable", None, "the reply was not JSON"),
}
_UNSET = object()


class FakeExaTransport:
    """Scripted results and every failure kind (contract §12). Each `call` pops the next script item: a dict is
    returned, an exception is raised, a function is called with the arguments (and awaited if it returns a coroutine,
    so a test can make a call slow). Nothing is retried or reordered."""

    def __init__(self, script=(), tool_schema=_UNSET):
        self._script = list(script)
        self.tool_schema = tool_schema
        self.calls: list[tuple[dict, float]] = []

    def push(self, item) -> None:
        self._script.append(item)

    @staticmethod
    def failure(kind: str) -> ServiceError:
        """The ServiceError the real transport raises for this kind of failure. KeyError for a name it does not know."""
        error_kind, status, message = _FAKE_FAILURES[kind]
        return ServiceError("exa", error_kind, status, message)

    async def call(self, arguments: dict, timeout_s: float) -> dict:
        self.calls.append((copy.deepcopy(arguments), timeout_s))
        if not self._script:
            raise AssertionError("FakeExaTransport: the test did not script this call")
        item = self._script.pop(0)
        if isinstance(item, BaseException):
            raise item
        out = item(arguments) if callable(item) else item
        return await out if inspect.isawaitable(out) else out

    async def list_tool_schema(self) -> dict:
        if self.tool_schema is _UNSET:
            raise AssertionError("FakeExaTransport: the test did not give a tool schema")
        if isinstance(self.tool_schema, BaseException):
            raise self.tool_schema
        return self.tool_schema


def exa_result(*, url, title="Synthetic title", published="2026-07-01T00:00:00.000Z", text="Synthetic page text.",
               author=None, id=None) -> dict:
    """One synthetic result in Exa's shape (fields as observed: id, url, title, publishedDate, author, text, image).
    A field given as None is left out, as Exa leaves out what it does not know."""
    r = {"id": id or str(url), "url": url, "image": "https://example.test/image.png"}
    for key, value in (("title", title), ("publishedDate", published), ("author", author), ("text", text)):
        if value is not None:
            r[key] = value
    return r


def exa_response(results: list, cost_total: float | None = 0.007) -> dict:
    """A synthetic Exa reply: `results` plus the bookkeeping fields Exa sends. cost_total None leaves `costDollars` out."""
    body = {"requestId": "synthetic-request", "resolvedSearchType": "neural", "searchTime": 321.0, "results": results}
    if cost_total is not None:
        body["costDollars"] = {"total": cost_total, "search": {"neural": cost_total}}
    return body


# --- reading Exa's reply --------------------------------------------------------------------------------------------

_DATE_PART = re.compile(r"(\d{4}-\d{2}-\d{2})(?:\Z|[T ])")


def _published(v) -> str | None:
    """The date part of what Exa sent, as written, with no time-zone conversion (T2.2); None if there is none to read."""
    if not isinstance(v, str):
        return None
    m = _DATE_PART.match(v.strip())
    if not m:
        return None
    try:
        date.fromisoformat(m.group(1))
    except ValueError:
        return None
    return m.group(1)


def _http_url(v) -> str | None:
    """The URL if it is http or https (scheme case folded), else None: other results are dropped (contract §4.D)."""
    if not isinstance(v, str):
        return None
    url = v.strip()
    if not url or any(c.isspace() or unicodedata.category(c) == "Cc" for c in url):
        return None
    try:
        parts = urlsplit(url)
        host = parts.hostname
    except ValueError:
        return None
    if parts.scheme.lower() not in ("http", "https") or not host:
        return None
    return parts.scheme.lower() + url[len(parts.scheme):]


def _url_key(url: str) -> str:
    """What makes two URLs the same page for repeats: scheme and host case, a fragment and a trailing slash don't."""
    p = urlsplit(url)
    return f"{p.scheme.lower()}://{p.netloc.lower()}{p.path.rstrip('/')}{'?' + p.query if p.query else ''}"


def _line(v, limit: int | None = None) -> str:
    """One line: control characters and runs of whitespace become single spaces; cut to `limit` (a title or author line
    by default, settings.EXA_HEADER_FIELD_MAX_CHARS) with an ellipsis."""
    limit = int(settings.EXA_HEADER_FIELD_MAX_CHARS.value) if limit is None else limit
    s = " ".join("".join(" " if unicodedata.category(c) in ("Cc", "Zl", "Zp") else c for c in str(v)).split())
    return s if len(s) <= limit else s[: limit - 1] + "…"


def _page_text(v, cap: int) -> tuple[str, bool]:
    """The opening `cap` characters, and whether it may have been cut. We send the cap to Exa, which cuts to it without
    saying so (observed: capped results came back at exactly the cap), so a text as long as the cap counts as cut."""
    raw = v if isinstance(v, str) else ""
    cleaned = "".join(c for c in raw if c in "\t\n\r" or unicodedata.category(c) != "Cc")
    return cleaned[:cap], len(raw) >= cap


def _cost(body: dict) -> float | None:
    cd = body.get("costDollars")
    total = cd.get("total") if isinstance(cd, dict) else None
    if isinstance(total, bool) or not isinstance(total, (int, float)) or not math.isfinite(total) or total < 0:
        return None
    return float(total)


def _read_reply(body, p: WebSearchParams, search_no: int, seen_urls: dict[str, str]):
    """(new pages, repeat IDs, undated count, Exa's reported cost). Raises ServiceError("unreadable") for a reply
    that has no result list. Does not touch `seen_urls`; the caller adds the new pages on success."""
    if not isinstance(body, dict) or not isinstance(body.get("results"), list):
        raise ServiceError("exa", "unreadable", None, "the reply had no result list")
    cap = int(settings.EXA_TEXT_CHARS.value)
    pages: list[WebPage] = []
    repeats: list[str] = []
    local: dict[str, str] = {}
    undated = 0
    for r in body["results"][: p.num_results]:
        if not isinstance(r, dict):
            continue
        url = _http_url(r.get("url"))
        if url is None:
            continue
        published = _published(r.get("publishedDate"))
        undated += published is None
        key = _url_key(url)
        first = seen_urls.get(key) or local.get(key)
        if first is not None:
            if first not in repeats:
                repeats.append(first)
            continue
        text, truncated = _page_text(r.get("text"), cap)
        author = _line(r["author"]) if isinstance(r.get("author"), str) and r["author"].strip() else None
        title = _line(r["title"]) if isinstance(r.get("title"), str) and r["title"].strip() else "(untitled)"
        page = WebPage(id=f"web-{search_no}-{len(pages) + 1}", title=title, url=url, domain=urlsplit(url).hostname or "",
                       published=published, author=author, text=text, truncated=truncated)
        pages.append(page)
        local[key] = page.id
    return pages, repeats, undated, _cost(body)


# --- the schema check -----------------------------------------------------------------------------------------------

_EXPECTED_TYPES = {
    "query": {"string"}, "numResults": {"number", "integer"}, "type": {"string"}, "category": {"string"},
    "includeDomains": {"array"}, "excludeDomains": {"array"}, "startPublishedDate": {"string"},
    "endPublishedDate": {"string"}, "textMaxCharacters": {"number", "integer"},
}
_ENUMS_WE_SEND = {"type": TYPES, "category": CATEGORIES}


def check_schema(listing) -> list[str]:
    """Warnings where Exa's listed input schema differs from what we send (T2.5). Pure; never raises."""
    schema = listing
    if isinstance(listing, dict):
        for k in ("inputSchema", "input_schema"):
            if isinstance(listing.get(k), dict):
                schema = listing[k]
                break
    if not isinstance(schema, dict) or not isinstance(schema.get("properties"), dict) or not schema["properties"]:
        return ["Exa's tool listing has no input properties to check"]
    props = schema["properties"]
    sent = [*EXA_ARGUMENT_NAMES.values(), EXA_TEXT_ARGUMENT]
    warnings: list[str] = []
    for name in sent:
        spec = props.get(name)
        if not isinstance(spec, dict):
            warnings.append(f"Exa's tool no longer lists the argument {name}, which we send")
            continue
        declared = spec.get("type")
        declared = {declared} if isinstance(declared, str) else set(declared or ())
        if declared and not declared & _EXPECTED_TYPES[name]:
            warnings.append(f"Exa lists {name} as {'/'.join(sorted(declared))}; we send {'/'.join(sorted(_EXPECTED_TYPES[name]))}")
        if isinstance(spec.get("enum"), list):
            for value in _ENUMS_WE_SEND.get(name, ()):
                if value not in spec["enum"]:
                    warnings.append(f"Exa's {name} no longer accepts the value {value}, which we send")
    cap = int(settings.EXA_TEXT_CHARS.value)
    low, high = 1, int(settings.MAX_RESULTS_CAP.value)
    num, text = props.get("numResults") or {}, props.get(EXA_TEXT_ARGUMENT) or {}
    if isinstance(num.get("maximum"), (int, float)) and num["maximum"] < high:
        warnings.append(f"Exa's numResults maximum is {num['maximum']}; we send up to {high}")
    if isinstance(num.get("minimum"), (int, float)) and num["minimum"] > low:
        warnings.append(f"Exa's numResults minimum is {num['minimum']}; we send as few as {low}")
    if isinstance(text.get("minimum"), (int, float)) and text["minimum"] > cap:
        warnings.append(f"Exa's {EXA_TEXT_ARGUMENT} minimum is {text['minimum']}; we send {cap}")
    if isinstance(text.get("maximum"), (int, float)) and text["maximum"] < cap:
        warnings.append(f"Exa's {EXA_TEXT_ARGUMENT} maximum is {text['maximum']}; we send {cap}")
    for name in schema.get("required") or []:
        if name not in sent:
            warnings.append(f"Exa now requires the argument {name}, which we do not send")
    return warnings


# --- the search -----------------------------------------------------------------------------------------------------

def _unavailable(reason: Literal["no_credit", "key_refused"]) -> WebSearchOutcome:
    return WebSearchOutcome("unavailable", reason, [], [], 0, None, 0.0)


def _classify(e: ServiceError) -> Literal["no_credit", "key_refused", "refused", "failed"]:
    """T2.4's four kinds, from the error: 402 and 401 are unavailable; any other 4xx is Exa refusing the search;
    everything else (5xx after Exa's own retries, protocol, connection, timeout, unreadable) is a failed search."""
    if e.status == 402 or e.kind == "no_credit":
        return "no_credit"
    if e.status == 401 or e.kind == "auth":
        return "key_refused"
    if e.status is not None and 400 <= e.status < 500:
        return "refused"
    if e.status is None and e.kind in ("bad_request", "permission", "not_found", "too_large", "rate_limited"):
        return "refused"
    return "failed"


class UpdateSearch:
    def __init__(self, transport: ExaTransport, store: Store, now: Callable[[], datetime] | None = None):
        self._transport = transport
        self._store = store
        self._now = now or (lambda: datetime.now(ZoneInfo(str(settings.TIME_ZONE.value))))

    async def search(self, p: WebSearchParams, search_no: int, seen_urls: dict[str, str], ctx: RunContext) -> WebSearchOutcome:
        """One update search, at most once and never retried (T2.4, P2.8). Adds the new pages' URLs to `seen_urls`."""
        if ctx.flags.exa_unavailable:                                   # decided earlier in this run
            return _unavailable(ctx.flags.exa_unavailable)
        try:
            until = await self._store.flag_until("exa_out_of_credit", self._now())
        except Exception as e:                                          # the flag only saves a call; do not block on it
            log.warning("run %s: could not read the Exa credit flag (%s)", ctx.run_id, type(e).__name__)
            until = None
        if until is not None:                                           # P2.11: out of credit until the 1st
            ctx.flags.exa_unavailable = "no_credit"
            return _unavailable("no_credit")

        await ctx.before_paid_call("exa", "update_search")              # RunStopped propagates: nothing was spent
        started = time.monotonic()
        error: ServiceError | None = None
        try:
            body = await self._transport.call(to_exa_arguments(p), float(settings.EXA_TIMEOUT_S.value))
            pages, repeats, undated, cost = _read_reply(body, p, search_no, seen_urls)
        except ServiceError as e:
            error = e
        except TimeoutError:
            error = ServiceError("exa", "timeout", None, "the search timed out")
        except Exception as e:
            error = ServiceError("exa", "protocol", None, type(e).__name__)
        ms = int((time.monotonic() - started) * 1000)

        if error is None:
            # A search whose reply carries no `costDollars` is charged at list price, so it is marked as estimated (T2.4).
            usage = Usage(service="exa", model=p.type, exa_cost_usd=cost, estimated=cost is None)
            cost_usd = await ctx.record_usage(usage, purpose="update_search", attempt=1, max_attempts=1, outcome="ok",
                                              error_kind=None, duration_ms=ms)
            # After the ledger: if recording raises, the pages never reach Claude, so their URLs stay unseen.
            seen_urls.update({_url_key(pg.url): pg.id for pg in pages})
            log.info("run %s: update search %d ok, %d new pages, %d ms", ctx.run_id, search_no, len(pages), ms)
            return WebSearchOutcome("ok", None, pages, repeats, undated, None, cost_usd)

        what = _classify(error)
        log.info("run %s: update search %d %s (%s), %d ms", ctx.run_id, search_no, what, error.kind, ms)

        if what in ("no_credit", "key_refused"):
            # Not counted, no cost (T2.4): record_usage is not called, so no paid_call event is emitted. The gate
            # was passed, so the lifecycle is told no record follows (contract v1.4).
            await ctx.call_not_billed("exa", "update_search")
            ctx.flags.exa_unavailable = what
            if what == "no_credit":
                now = self._now()
                for write in (lambda: self._store.set_flag("exa_out_of_credit", now),
                              lambda: self._store.record_stop("exa_no_credit", ctx.run_id, now, {"service": "exa", "status": 402})):
                    try:
                        await write()
                    except Exception as e:
                        log.warning("run %s: could not record the Exa credit stop (%s)", ctx.run_id, type(e).__name__)
            else:
                log.error("run %s: Exa refused our key (configuration fault)", ctx.run_id)   # this run only (T2.4)
            return _unavailable(what)

        # Counted. A failed search is priced by E at list price for its type (T2.4); a refusal is counted at an explicit zero.
        usage = Usage(service="exa", model=p.type, estimated=True) if what == "failed" else Usage(
            service="exa", model=p.type, exa_cost_usd=0.0)
        cost_usd = await ctx.record_usage(usage, purpose="update_search", attempt=1, max_attempts=1, outcome="failed",
                                          error_kind=error.kind, duration_ms=ms)
        if what == "refused":
            return WebSearchOutcome("refused_by_exa", None, [], [], 0, _line(error.message, int(settings.EXA_MESSAGE_MAX_CHARS.value)),
                                    cost_usd)
        return WebSearchOutcome("failed", None, [], [], 0, None, cost_usd)

    async def schema_check(self) -> list[str]:
        """Compare Exa's free tool listing with what we send. Warnings only; never raises, never blocks (T2.5)."""
        try:
            warnings = check_schema(await self._transport.list_tool_schema())
        except Exception as e:
            warnings = [f"could not list Exa's tool to check its schema ({getattr(e, 'kind', type(e).__name__)})"]
        for w in warnings:
            log.warning("exa schema check: %s", w)
        return warnings
