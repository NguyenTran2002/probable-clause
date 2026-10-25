"""SdkAnthropicStreamer against httpx2's MockTransport serving recorded-shape SSE: the request it sends, the
streaming, the final message and usage, and the error classification of contract §2. No network."""

import asyncio
import json

import httpx2
import pytest

from api.errors import ServiceError
from api.loop.run import _Research, _Run
from api.loop.streamer import SdkAnthropicStreamer, StreamFailed, classify_status
from tests.loop.support import FakeCtx, make_deps

pytestmark = pytest.mark.anyio

USAGE_START = {"input_tokens": 12, "cache_creation_input_tokens": 12000, "cache_read_input_tokens": 0,
               "cache_creation": {"ephemeral_5m_input_tokens": 0, "ephemeral_1h_input_tokens": 12000},
               "output_tokens": 1, "service_tier": "standard"}


def sse(*events) -> bytes:
    return "".join(f"event: {e['type']}\ndata: {json.dumps(e)}\n\n" for e in events).encode()


def message_start(model="claude-sonnet-5-5"):
    return {"type": "message_start", "message": {"id": "msg_1", "type": "message", "role": "assistant", "model": model,
                                                 "content": [], "stop_reason": None, "stop_sequence": None,
                                                 "usage": USAGE_START}}


def thinking_block(i):
    return [{"type": "content_block_start", "index": i, "content_block": {"type": "thinking", "thinking": "", "signature": ""}},
            {"type": "content_block_delta", "index": i, "delta": {"type": "signature_delta", "signature": "EqQBsig"}},
            {"type": "content_block_stop", "index": i}]


def tool_block(i, name="search_exact", inp=None):
    inp = inp if inp is not None else {"any_of": ["booth"]}
    return [{"type": "content_block_start", "index": i, "content_block": {"type": "tool_use", "id": "toolu_01", "name": name, "input": {}}},
            {"type": "content_block_delta", "index": i, "delta": {"type": "input_json_delta", "partial_json": json.dumps(inp)}},
            {"type": "content_block_stop", "index": i}]


def text_block(i, text, citations=()):
    evs = [{"type": "content_block_start", "index": i, "content_block": {"type": "text", "text": "", "citations": []}}]
    for c in citations:
        evs.append({"type": "content_block_delta", "index": i, "delta": {"type": "citations_delta", "citation": c}})
    evs.append({"type": "content_block_delta", "index": i, "delta": {"type": "text_delta", "text": text}})
    evs.append({"type": "content_block_stop", "index": i})
    return evs


def message_end(stop_reason="end_turn", output=321):
    return [{"type": "message_delta", "delta": {"stop_reason": stop_reason, "stop_sequence": None},
             "usage": {"output_tokens": output}}, {"type": "message_stop"}]


class Server:
    def __init__(self, *responses):
        self.responses = list(responses)
        self.requests: list[httpx2.Request] = []

    async def __call__(self, request: httpx2.Request) -> httpx2.Response:
        self.requests.append(request)
        r = self.responses.pop(0)
        if isinstance(r, BaseException):
            raise r
        if callable(r):
            return await r(request)
        return r

    def body(self, i=0) -> dict:
        return json.loads(self.requests[i].content)


def ok(*events, headers=None):
    return httpx2.Response(200, headers={"content-type": "text/event-stream", **(headers or {})}, content=sse(*events))


def error(status, body, headers=None):
    return httpx2.Response(status, headers={"content-type": "application/json", **(headers or {})}, json=body)


def streamer(server) -> SdkAnthropicStreamer:
    return SdkAnthropicStreamer("test-key-not-real", http_client=httpx2.AsyncClient(transport=httpx2.MockTransport(server)))


def loop_request(world) -> dict:
    """Research's request, from the one builder research and the update step share (§4.G.2)."""
    deps, _ = make_deps(world, [])
    run = _Run(FakeCtx(), deps)
    run.messages.append({"role": "user", "content": [{"type": "text", "text": "The visitor's question:\n\nx"}]})
    return _Research(run).request(8000)


async def test_loop_request_on_the_wire(world):
    server = Server(ok(message_start(), *thinking_block(0), *tool_block(1), *message_end("tool_use", 77)))
    res = await streamer(server).stream(loop_request(world), 120.0, None, step="research")
    body = server.body()
    req = server.requests[0]
    assert req.url.path == "/v1/messages" and req.headers["authorization"] == "Bearer test-key-not-real"   # SDK 2.3.0
    assert req.headers.get("anthropic-version")
    assert body["model"] == "claude-sonnet-5-5" and body["max_tokens"] == 8000 and body["stream"] is True
    assert body["thinking"] == {"type": "adaptive"} and body["output_config"] == {"effort": "high"}
    assert body["cache_control"] == {"type": "ephemeral"}
    assert body["system"][0]["cache_control"] == {"type": "ephemeral", "ttl": "1h"}
    assert [t.get("strict", False) for t in body["tools"]] == [False, False, True, True, True, True, True]
    assert [t["name"] for t in body["tools"]][-2:] == ["search_web_updates", "submit_update"]
    assert "tool_choice" not in body and "temperature" not in body
    # the final message, exactly as the API sent it
    assert res.stop_reason == "tool_use"
    assert res.content[0] == {"type": "thinking", "thinking": "", "signature": "EqQBsig"}
    assert res.content[1] == {"type": "tool_use", "id": "toolu_01", "name": "search_exact", "input": {"any_of": ["booth"]}}
    assert res.usage["output_tokens"] == 77 and res.usage["cache_creation"]["ephemeral_1h_input_tokens"] == 12000
    assert len(server.requests) == 1


async def test_composition_request_and_streamed_blocks(world):
    from api.loop import format as fmt
    deps, _ = make_deps(world, [])
    run = _Run(FakeCtx(), deps)
    p = world.corpus.passages["katz-1-p6"]
    request = run.composition_request([fmt.document_block(p, "r")], None)
    cited = p.text[p.sentences[0][0]:p.sentences[1][1]]
    c = {"type": "content_block_location", "cited_text": cited, "document_index": 0, "document_title": "T",
         "start_block_index": 0, "end_block_index": 2}
    server = Server(ok(message_start("claude-sonnet-5-5"), *thinking_block(0), *text_block(1, "Intro. "),
                       *text_block(2, "Cited. ", [c]), *message_end("end_turn", 900)))
    seen = []

    async def on_block(i, block):
        seen.append((i, block))

    res = await streamer(server).stream(request, 300.0, on_block, step="composition")
    body = server.body()
    assert body["model"] == "claude-sonnet-5-5" and body["max_tokens"] == 16000
    assert body["output_config"] == {"effort": "high"} and "cache_control" not in body
    doc = body["messages"][0]["content"][0]
    assert doc["type"] == "document" and doc["source"]["type"] == "content" and doc["citations"] == {"enabled": True}
    assert [b["text"] for b in doc["source"]["content"]] == [p.text[a:b] for a, b in p.sentences]
    assert [i for i, _ in seen] == [1, 2]
    assert seen[1][1]["citations"][0]["end_block_index"] == 2 and seen[1][1]["text"] == "Cited. "
    assert res.blocks_delivered == 2 and res.content[2]["citations"][0]["cited_text"] == cited


SPEND_CAP = {"type": "error", "error": {"type": "rate_limit_error", "message": "You have reached your API usage limits: "
             "your organization has crossed its monthly API usage threshold.",
             "details": {"error_code": "enforced_spend_limit_reached"}}, "request_id": "req_x"}
SPEND_LIMIT = {"type": "error", "error": {"type": "invalid_request_error",
               "message": "You have reached your specified API usage limits. You will regain access on 2026-11-01."}}
WS_LIMIT = {"type": "error", "error": {"type": "invalid_request_error",
            "message": "You have reached your specified workspace API usage limits. Access resumes 2026-11-01."}}


@pytest.mark.parametrize("status,body,headers,kind,retry_after", [
    (429, SPEND_CAP, {}, "spend_cap", None),
    (429, {"type": "error", "error": {"type": "rate_limit_error", "message": "Number of request tokens has exceeded"}},
     {"retry-after": "3"}, "rate_limited", 3.0),
    (429, {"type": "error", "error": {"type": "rate_limit_error", "message": "rate limited"}}, {}, "rate_limited", None),
    (400, SPEND_LIMIT, {}, "spend_limit", None),
    (400, WS_LIMIT, {}, "spend_limit", None),
    (400, {"type": "error", "error": {"type": "invalid_request_error", "message": "messages: bad"}}, {}, "bad_request", None),
    (401, {"type": "error", "error": {"type": "authentication_error", "message": "x"}}, {}, "auth", None),
    (403, {"type": "error", "error": {"type": "permission_error", "message": "x"}}, {}, "permission", None),
    (404, {"type": "error", "error": {"type": "not_found_error", "message": "x"}}, {}, "not_found", None),
    (413, {"type": "error", "error": {"type": "request_too_large", "message": "x"}}, {}, "too_large", None),
    (500, {"type": "error", "error": {"type": "api_error", "message": "x"}}, {}, "server_error", None),
    (504, {"type": "error", "error": {"type": "timeout_error", "message": "x"}}, {}, "gateway_timeout", None),
    (529, {"type": "error", "error": {"type": "overloaded_error", "message": "x"}}, {}, "overloaded", None),
])
async def test_error_classification(world, status, body, headers, kind, retry_after):
    server = Server(error(status, body, headers))
    with pytest.raises(ServiceError) as e:
        await streamer(server).stream(loop_request(world), 120.0, None, step="research")
    assert e.value.kind == kind and e.value.status == status and e.value.retry_after_s == retry_after
    assert e.value.service == "anthropic"
    assert len(server.requests) == 1                     # the SDK's own retries are off (max_retries=0)


async def test_a_mid_stream_error_is_stream_broken_with_the_usage_reported(world):
    err = {"type": "error", "error": {"type": "overloaded_error", "message": "Overloaded"}}
    body = sse(message_start(), *thinking_block(0)) + f"event: error\ndata: {json.dumps(err)}\n\n".encode()
    server = Server(httpx2.Response(200, headers={"content-type": "text/event-stream"}, content=body))
    with pytest.raises(StreamFailed) as e:
        await streamer(server).stream(loop_request(world), 120.0, None, step="research")
    assert e.value.kind == "stream_broken" and e.value.started and e.value.raw_usage["input_tokens"] == 12


async def test_a_connection_failure_before_the_stream(world):
    server = Server(httpx2.ConnectError("refused"))
    with pytest.raises(StreamFailed) as e:
        await streamer(server).stream(loop_request(world), 120.0, None, step="research")
    assert e.value.kind == "connection" and e.value.raw_usage is None


async def test_our_deadline(world):
    async def slow(request):
        await asyncio.sleep(5)
        return ok(message_start(), *message_end())
    server = Server(slow)
    with pytest.raises(StreamFailed) as e:
        await streamer(server).stream(loop_request(world), 0.05, None, step="research")
    assert e.value.kind == "deadline"


async def test_a_refusal_is_a_completed_response(world):
    server = Server(ok(message_start(), *message_end("refusal", 5)))
    res = await streamer(server).stream(loop_request(world), 120.0, None, step="research")
    assert res.stop_reason == "refusal" and res.usage["output_tokens"] == 5


async def test_a_callback_error_is_not_classified(world):
    server = Server(ok(message_start(), *text_block(0, "x"), *message_end()))

    async def boom(i, b):
        raise KeyError("not an API error")

    with pytest.raises(KeyError) as e:
        await streamer(server).stream(loop_request(world), 120.0, boom, step="research")
    # what the stream reported and streamed rides on the exception, so the attempt is priced from it
    from api.loop.streamer import partial_of
    raw, chars, started = partial_of(e.value)
    assert raw["input_tokens"] == 12 and chars == 1 and started is True


def test_classify_status_markers():
    assert classify_status(429, SPEND_CAP) == "spend_cap"
    assert classify_status(429, {"error": {"message": "x", "details": {"error_code": "enforced_spend_limit_reached"}}}) == "spend_cap"
    assert classify_status(400, SPEND_LIMIT) == "spend_limit"
    assert classify_status(200, {"error": {"type": "overloaded_error"}}, mid_stream=True) == "stream_broken"
    assert classify_status(402, {}) == "bad_request" and classify_status(503, {}) == "server_error"


def test_an_api_key_is_required():
    with pytest.raises(ValueError):
        SdkAnthropicStreamer("")


async def test_a_broken_stream_reports_what_it_streamed(world):
    err = {"type": "error", "error": {"type": "overloaded_error", "message": "Overloaded"}}
    body = sse(message_start(), *text_block(0, "x" * 500), *tool_block(1, inp={"any_of": ["y" * 100]})) + \
        f"event: error\ndata: {json.dumps(err)}\n\n".encode()
    server = Server(httpx2.Response(200, headers={"content-type": "text/event-stream"}, content=body))
    with pytest.raises(StreamFailed) as e:
        await streamer(server).stream(loop_request(world), 120.0, None, step="research")
    assert e.value.streamed_chars == 500 + len(json.dumps({"any_of": ["y" * 100]}))


async def test_step_is_never_sent_and_must_be_a_step(world):
    server = Server(ok(message_start(), *thinking_block(0), *message_end("end_turn", 3)))
    await streamer(server).stream(loop_request(world), 120.0, None, step="update")
    assert "step" not in server.body()
    with pytest.raises(ValueError):
        await streamer(Server()).stream(loop_request(world), 120.0, None, step="loop")


async def test_a_cancelled_stream_carries_what_it_streamed(world):
    """Contract v2.0 §4.G.1 item 7: the cancellation goes on, with the usage reported and the characters streamed."""
    from api.loop.streamer import partial_of
    reached = asyncio.Event()

    async def body(request):
        async def chunks():
            yield sse(message_start(), *text_block(0, "x" * 300))
            reached.set()
            await asyncio.sleep(30)
            yield sse(*message_end())
        return httpx2.Response(200, headers={"content-type": "text/event-stream"}, content=chunks())

    task = asyncio.create_task(streamer(Server(body)).stream(loop_request(world), 120.0, None, step="research"))
    await reached.wait()
    for _ in range(20):
        await asyncio.sleep(0)
    task.cancel()
    with pytest.raises(asyncio.CancelledError) as e:
        await task
    raw, chars, started = partial_of(e.value)
    assert started is True and raw["input_tokens"] == 12 and chars == 300
