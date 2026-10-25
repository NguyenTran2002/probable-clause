"""The one place the Anthropic SDK is called (contract §4.G; T3.3): streamed, SDK retries off, our deadline.

Sources (all read Oct 24, 2026):
  - streaming with the Python SDK, `client.messages.stream(...)`, its events and `get_final_message()`:
    https://platform.claude.com/docs/en/build-with-claude/streaming and the installed SDK
    (`anthropic` 2.3.0, `lib/streaming/_messages.py`): usage arrives on `message_start` and is updated by
    `message_delta` (cumulative counts); a mid-stream SSE `error` event is raised as an `APIStatusError` whose
    response status is 200 (`_streaming.py`).
  - errors: https://platform.claude.com/docs/en/api/errors and https://platform.claude.com/docs/en/api/rate-limits
    ("Reaching your spend cap", "Setting your own spend limit"). How the two special cases are told apart (§2):
      * the usage tier's spend cap is a 429 `rate_limit_error` with "no `retry-after` header"; "On the Messages
        API, `error.details.error_code` is `enforced_spend_limit_reached`. Use it to tell this response apart from
        a rate limit." Its message begins "You have reached your API usage limits".
      * a spend limit we set (organisation or workspace, the Console's) is a 400 `invalid_request_error` whose
        "message starts with `You have reached your specified API usage limits`, or `You have reached your
        specified workspace API usage limits` for a workspace limit".
    Conservative reading: only those markers make `spend_cap` / `spend_limit`. A 429 merely lacking `retry-after`
    stays `rate_limited`, since misreading it would pause live research for the month (T3.3, T5.4).
"""

import asyncio
import copy
import inspect
import json
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Protocol

import anthropic
import httpx2

from api.errors import ErrorKind, ServiceError

log = logging.getLogger("probable_clause.loop")

SPEND_CAP_CODE = "enforced_spend_limit_reached"
SPEND_CAP_PREFIX = "You have reached your API usage limits"
SPEND_LIMIT_PREFIXES = ("You have reached your specified API usage limits",
                        "You have reached your specified workspace API usage limits")

OnBlock = Callable[[int, dict], Awaitable[None] | None]


@dataclass
class StreamResult:
    """A completed response. `content` and `usage` are exactly what the API sent, as JSON (T4.3, T4.5)."""
    content: list[dict]
    stop_reason: str | None
    usage: dict
    stop_details: dict | None = None
    model: str | None = None
    request_id: str | None = None
    blocks_delivered: int = 0


class StreamFailed(ServiceError):
    """A ServiceError from a Claude call, carrying the usage its stream reported before it failed, if any (T3.3:
    "Spend for a failed attempt is the usage its stream reported, or an estimate of its input")."""

    def __init__(self, kind: ErrorKind, status: int | None = None, message: str = "",
                 retry_after_s: float | None = None, *, raw_usage: dict | None = None, started: bool = False,
                 blocks_delivered: int = 0, streamed_chars: int = 0):
        super().__init__("anthropic", kind, status, message, retry_after_s)
        self.raw_usage = raw_usage
        self.started = started
        self.blocks_delivered = blocks_delivered
        self.streamed_chars = streamed_chars       # text, thinking and tool input streamed before the failure


class AnthropicStreamer(Protocol):
    async def stream(self, request: dict, deadline_s: float, on_block: OnBlock | None) -> StreamResult:
        """Stream one request. `on_block(content_index, block)` is awaited for each completed text block.
        Raises ServiceError (StreamFailed) with an ErrorKind (§2)."""
        ...


# ---------- error classification (§2) ----------

def _error_body(body) -> dict:
    if isinstance(body, dict):
        err = body.get("error")
        if isinstance(err, dict):
            return err
    return {}


def _retry_after(headers) -> float | None:
    raw = headers.get("retry-after") if headers is not None else None
    if raw is None:
        return None
    try:
        v = float(raw)
    except ValueError:
        return None
    return v if v >= 0 else None


def classify_status(status: int, body, *, mid_stream: bool = False) -> ErrorKind:
    """§2's mapping for Anthropic. `mid_stream`: an SSE error event after the stream began (status 200)."""
    err = _error_body(body)
    message = err.get("message") if isinstance(err.get("message"), str) else ""
    details = err.get("details") if isinstance(err.get("details"), dict) else {}
    if details.get("error_code") == SPEND_CAP_CODE or message.startswith(SPEND_CAP_PREFIX):
        return "spend_cap"
    if any(message.startswith(p) for p in SPEND_LIMIT_PREFIXES):
        return "spend_limit"
    if mid_stream:
        return "stream_broken"      # T3.3: an error after a loop call's stream began
    if status == 400:
        return "bad_request"
    if status == 401:
        return "auth"
    if status == 403:
        return "permission"
    if status == 404:
        return "not_found"
    if status == 413:
        return "too_large"
    if status == 429:
        return "rate_limited"
    if status == 504:
        return "gateway_timeout"
    if status == 529:
        return "overloaded"
    if status >= 500:
        return "server_error"
    # GAP: §2 names no kind for 402, 409, 422 or another 4xx; they are the account's or our fault, so the closest
    # never-retried kind is used.
    return "bad_request"


class _CallbackError(Exception):
    def __init__(self, inner: BaseException):
        super().__init__(type(inner).__name__)
        self.inner = inner


def _usage_json(usage) -> dict | None:
    if usage is None:
        return None
    try:
        return usage.to_dict(mode="json")
    except Exception:
        return None


class SdkAnthropicStreamer:
    """The real client: `anthropic.AsyncAnthropic(api_key=..., max_retries=0)` (contract §1: retries are ours)."""

    def __init__(self, api_key: str, *, base_url: str | None = None, http_client: httpx2.AsyncClient | None = None):
        if not api_key:
            raise ValueError("an Anthropic API key is required")
        kwargs: dict = {"api_key": api_key, "max_retries": 0}
        if base_url is not None:
            kwargs["base_url"] = base_url
        if http_client is not None:
            kwargs["http_client"] = http_client
        self._client = anthropic.AsyncAnthropic(**kwargs)

    async def aclose(self) -> None:
        """Close the client's connections (for the API's shutdown)."""
        await self._client.close()

    async def stream(self, request: dict, deadline_s: float, on_block: OnBlock | None) -> StreamResult:
        state = {"started": False, "message": False, "usage": None, "blocks": 0, "chars": 0}

        def failed(kind: ErrorKind, status=None, message="", retry_after=None) -> StreamFailed:
            return StreamFailed(kind, status, message, retry_after, raw_usage=state["usage"],
                                started=state["started"], blocks_delivered=state["blocks"],
                                streamed_chars=state["chars"])

        try:
            async with asyncio.timeout(deadline_s):            # our deadline per call (T3.3)
                async with self._client.messages.stream(**request, timeout=deadline_s) as s:
                    state["started"] = True
                    async for event in s:
                        etype = getattr(event, "type", None)
                        if etype == "message_start":
                            state["message"] = True
                            state["usage"] = _usage_json(event.message.usage)
                        elif etype == "message_delta":
                            snap = _usage_json(s.current_message_snapshot.usage)
                            if snap is not None:
                                state["usage"] = snap
                        elif etype == "content_block_delta":
                            d = event.delta     # what was generated so far, for a failed attempt's output (T3.3)
                            state["chars"] += len(getattr(d, "text", None) or getattr(d, "thinking", None)
                                                  or getattr(d, "partial_json", None) or "")
                        elif etype == "content_block_stop" and on_block is not None:
                            block = event.content_block
                            if getattr(block, "type", None) == "text":
                                try:
                                    out = on_block(event.index, block.to_dict(mode="json"))
                                    if inspect.isawaitable(out):
                                        await out
                                except Exception as e:
                                    raise _CallbackError(e) from None
                                state["blocks"] += 1
                    if not state["message"]:
                        raise failed("unreadable", None, "the stream carried no message")
                    final = await s.get_final_message()
                    request_id = s.request_id
        except _CallbackError as e:
            raise e.inner
        except StreamFailed:
            raise
        except TimeoutError:
            raise failed("deadline", None, "the call passed its deadline") from None
        except anthropic.APIStatusError as e:
            mid = e.status_code == 200
            kind = classify_status(e.status_code, e.body, mid_stream=mid)
            retry_after = None if mid else _retry_after(e.response.headers)
            raise failed(kind, None if mid else e.status_code, f"HTTP {e.status_code}", retry_after) from None
        except anthropic.APITimeoutError:
            raise failed("deadline", None, "the call timed out") from None
        except anthropic.APIConnectionError:
            raise failed("stream_broken" if state["started"] else "connection", None, "connection failed") from None
        except httpx2.TimeoutException:
            raise failed("deadline", None, "the call timed out") from None
        except httpx2.HTTPError:
            raise failed("stream_broken" if state["started"] else "connection", None, "transport failed") from None
        except anthropic.APIResponseValidationError:
            raise failed("unreadable", None, "the reply did not match its schema") from None
        except anthropic.APIError:
            raise failed("protocol", None, "the API call failed") from None
        except ValueError:
            raise failed("unreadable", None, "the reply could not be parsed") from None
        return StreamResult(
            content=[b.to_dict(mode="json") for b in final.content],
            stop_reason=final.stop_reason,
            usage=_usage_json(final.usage) or {},
            stop_details=final.stop_details.to_dict(mode="json") if getattr(final, "stop_details", None) else None,
            model=getattr(final, "model", None),
            request_id=request_id,
            blocks_delivered=state["blocks"],
        )


# ---------- the fake (contract §12) ----------

@dataclass
class FakeTurn:
    """One scripted response. `break_after=k`: the stream delivers k text blocks, then fails with `error`
    (default: stream_broken, with `partial_usage` as the usage it reported)."""
    content: list[dict]
    stop_reason: str = "end_turn"
    usage: dict | None = None
    stop_details: dict | None = None
    break_after: int | None = None
    error: ServiceError | None = None
    partial_usage: dict | None = None


def raw_usage(input_tokens: int = 0, *, w5: int = 0, w1: int = 0, read: int = 0, output: int = 0) -> dict:
    """A usage object in the API's shape."""
    return {"input_tokens": input_tokens, "cache_creation_input_tokens": w5 + w1, "cache_read_input_tokens": read,
            "cache_creation": {"ephemeral_5m_input_tokens": w5, "ephemeral_1h_input_tokens": w1},
            "output_tokens": output, "service_tier": "standard"}


@dataclass
class FakeAnthropic:
    """Scripted turns: tool calls, text blocks with citations, errors (contract §12). Each `stream` pops the next
    item: a FakeTurn, an exception (raised), or a function of the request returning either."""
    script: list = field(default_factory=list)
    requests: list = field(default_factory=list)
    deadlines: list = field(default_factory=list)

    def push(self, *items) -> None:
        self.script.extend(items)

    async def stream(self, request: dict, deadline_s: float, on_block: OnBlock | None) -> StreamResult:
        self.requests.append(copy.deepcopy(request))
        self.deadlines.append(deadline_s)
        if not self.script:
            raise AssertionError("FakeAnthropic: the test did not script this call")
        item = self.script.pop(0)
        if callable(item) and not isinstance(item, (FakeTurn, BaseException)):
            item = item(request)
        if isinstance(item, BaseException):
            raise item
        delivered = chars = 0
        for i, b in enumerate(item.content):
            if item.break_after is not None and delivered >= item.break_after:
                break
            chars += len(b.get("text") or b.get("thinking") or "") + (len(json.dumps(b["input"])) if "input" in b else 0)
            if b.get("type") == "text" and on_block is not None:
                out = on_block(i, copy.deepcopy(b))
                if inspect.isawaitable(out):
                    await out
                delivered += 1
        if item.break_after is not None:
            if item.error is not None:
                if isinstance(item.error, StreamFailed) and not item.error.streamed_chars:
                    item.error.streamed_chars, item.error.started = chars, True
                raise item.error
            raise StreamFailed("stream_broken", None, "scripted break", raw_usage=item.partial_usage,
                               started=True, blocks_delivered=delivered, streamed_chars=chars)
        usage = item.usage
        if usage is None:
            out_tokens = int(request.get("max_tokens", 0)) if item.stop_reason == "max_tokens" else 50
            usage = raw_usage(1000, output=out_tokens)
        return StreamResult(content=copy.deepcopy(item.content), stop_reason=item.stop_reason,
                            usage=copy.deepcopy(usage), stop_details=item.stop_details,
                            model=request.get("model"), request_id="req_fake", blocks_delivered=delivered)


_fake_ids = {"n": 0}


def tool_use(name: str, input: dict, id: str | None = None) -> dict:
    if id is None:
        _fake_ids["n"] += 1
        id = f"toolu_fake_{_fake_ids['n']:04d}"
    return {"type": "tool_use", "id": id, "name": name, "input": input}


def text(t: str, citations: list[dict] | None = None) -> dict:
    b = {"type": "text", "text": t}
    if citations:
        b["citations"] = citations
    return b


def thinking(signature: str = "sig-fake") -> dict:
    return {"type": "thinking", "thinking": "", "signature": signature}


def cite(document_index: int, start: int, end: int, cited_text: str, title: str | None = None) -> dict:
    """A content_block_location citation; `end` is exclusive, as the API sends it."""
    return {"type": "content_block_location", "cited_text": cited_text, "document_index": document_index,
            "document_title": title, "start_block_index": start, "end_block_index": end}
