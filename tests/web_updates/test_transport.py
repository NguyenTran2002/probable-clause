"""McpExaTransport and FakeExaTransport (contract §4.D; T2.5, T2.4). The mcp package's network pieces are replaced:
no test opens a connection or holds a real key."""

import asyncio
import json
from contextlib import asynccontextmanager

import anyio
import httpx2
import pytest
from mcp import types
from mcp.shared.exceptions import MCPError

from api import settings
from api.errors import ServiceError
from api.web_updates import exa as exa_module
from api.web_updates.exa import FakeExaTransport, McpExaTransport, exa_response, exa_result, parse_tool_error

pytestmark = pytest.mark.anyio

KEY = "test-key-not-real-0123456789"
TOOL = "web_search_advanced_exa"


class Rec:
    def __init__(self):
        self.headers = None
        self.http_timeout = None
        self.url = None
        self.initialized = 0
        self.closed = 0
        self.calls: list[tuple] = []
        self.list_calls = 0
        self.sessions = 0


def text_result(text, is_error=False):
    return types.CallToolResult(content=[types.TextContent(type="text", text=text)], is_error=is_error)


def install(monkeypatch, rec, *, result=None, call_exc=None, init_exc=None, init_sleep=0.0, call_sleep=0.0, tools=None,
            open_exc=None):
    @asynccontextmanager
    async def fake_http(headers=None, timeout=None, auth=None):
        rec.headers, rec.http_timeout = headers, timeout
        yield object()

    @asynccontextmanager
    async def fake_stream(url, *, http_client=None, **kw):
        rec.url = url
        rec.sessions += 1
        if open_exc:
            raise open_exc
        yield ("read-stream", "write-stream")

    class FakeClientSession:
        def __init__(self, read, write, **kw):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            rec.closed += 1
            return False

        async def initialize(self):
            rec.initialized += 1
            await anyio.sleep(init_sleep)
            if init_exc:
                raise init_exc

        async def call_tool(self, name, arguments=None, **kw):
            rec.calls.append((name, arguments))
            await anyio.sleep(call_sleep)
            if call_exc:
                raise call_exc
            return result

        async def list_tools(self, **kw):
            rec.list_calls += 1
            return types.ListToolsResult(tools=tools or [])

    monkeypatch.setattr(exa_module, "create_mcp_http_client", fake_http)
    monkeypatch.setattr(exa_module, "streamable_http_client", fake_stream)
    monkeypatch.setattr(exa_module, "ClientSession", FakeClientSession)


@pytest.fixture
def rec():
    return Rec()


@pytest.fixture(autouse=True)
def key(monkeypatch):
    monkeypatch.setenv("EXA_API_KEY", KEY)


ARGS = {"query": "synthetic", "type": "auto", "numResults": 10, "textMaxCharacters": 4000}


async def call(timeout=5.0, args=None):
    return await McpExaTransport().call(args or ARGS, timeout)


# --- the session --------------------------------------------------------------------------------------------------

async def test_one_session_per_call_with_the_key_only_in_the_header(monkeypatch, rec):
    body = exa_response([exa_result(url="https://example.test/a", title="T", published="2026-07-01T00:00:00.000Z", text="x")])
    install(monkeypatch, rec, result=text_result(json.dumps(body)))
    out = await call()
    assert out == body
    assert rec.headers == {"x-api-key": KEY}
    assert rec.url == settings.EXA_MCP_URL.value and KEY not in rec.url
    assert rec.sessions == 1 and rec.initialized == 1 and rec.closed == 1
    assert rec.calls == [(TOOL, ARGS)]


async def test_each_call_opens_its_own_session(monkeypatch, rec):
    install(monkeypatch, rec, result=text_result(json.dumps(exa_response([]))))
    t = McpExaTransport()
    await t.call(ARGS, 5)
    await t.call(ARGS, 5)
    assert rec.sessions == 2 and rec.initialized == 2 and rec.closed == 2


async def test_the_key_is_read_when_the_call_is_made(monkeypatch, rec):
    install(monkeypatch, rec, result=text_result(json.dumps(exa_response([]))))
    t = McpExaTransport()
    monkeypatch.setenv("EXA_API_KEY", "a-second-synthetic-key")
    await t.call(ARGS, 5)
    assert rec.headers == {"x-api-key": "a-second-synthetic-key"}


@pytest.mark.parametrize("value", [None, "", "   "])
async def test_a_missing_key_is_an_auth_failure_and_opens_no_session(monkeypatch, rec, value):
    install(monkeypatch, rec, result=text_result("{}"))
    if value is None:
        monkeypatch.delenv("EXA_API_KEY")
    else:
        monkeypatch.setenv("EXA_API_KEY", value)
    with pytest.raises(ServiceError) as e:
        await call()
    assert e.value.service == "exa" and e.value.kind == "auth"
    assert rec.sessions == 0 and rec.calls == []


# --- tool results -------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("status,kind", [
    (400, "bad_request"), (401, "auth"), (402, "no_credit"), (403, "permission"), (404, "not_found"), (413, "too_large"),
    (429, "rate_limited"), (418, "bad_request"), (500, "server_error"), (502, "server_error"), (503, "server_error"),
    (504, "gateway_timeout"),
])
async def test_an_error_result_is_classified_by_its_status(monkeypatch, rec, status, kind):
    install(monkeypatch, rec, result=text_result(f"{TOOL} error ({status}): Some message from Exa\nTimestamp: 2026-10-24T18:22:17.250Z", True))
    with pytest.raises(ServiceError) as e:
        await call()
    assert (e.value.service, e.value.kind, e.value.status) == ("exa", kind, status)
    assert e.value.message == "Some message from Exa"                  # Exa's own words, without the timestamp line


async def test_an_error_result_with_no_status_is_a_protocol_failure(monkeypatch, rec):
    install(monkeypatch, rec, result=text_result(f"{TOOL} error: request aborted", True))
    with pytest.raises(ServiceError) as e:
        await call()
    assert e.value.kind == "protocol" and e.value.status is None


async def test_the_no_more_credits_tag_alone_means_no_credit(monkeypatch, rec):
    install(monkeypatch, rec, result=text_result(f"{TOOL} error: NO_MORE_CREDITS: the account has no remaining credits", True))
    with pytest.raises(ServiceError) as e:
        await call()
    assert e.value.kind == "no_credit"


@pytest.mark.parametrize("result", [
    text_result("this is not json"),
    text_result("[1, 2, 3]"),
    text_result('"just a string"'),
    types.CallToolResult(content=[], is_error=False),
    types.CallToolResult(content=[types.ImageContent(type="image", data="AAAA", mime_type="image/png")], is_error=False),
])
async def test_a_reply_we_cannot_read_is_unreadable(monkeypatch, rec, result):
    install(monkeypatch, rec, result=result)
    with pytest.raises(ServiceError) as e:
        await call()
    assert e.value.kind == "unreadable"


async def test_an_error_result_without_text_is_a_protocol_failure(monkeypatch, rec):
    install(monkeypatch, rec, result=types.CallToolResult(content=[], is_error=True))
    with pytest.raises(ServiceError) as e:
        await call()
    assert e.value.kind == "protocol"


def test_parse_tool_error_shapes():
    assert parse_tool_error(f"{TOOL} error (400): Invalid request body | The company category does not support dates\n"
                            "Timestamp: 2026-10-24T18:22:17.250Z") == (400, "Invalid request body | The company category does not support dates")
    assert parse_tool_error(f"{TOOL} error (401): Invalid API key. Provide a valid key") == (401, "Invalid API key. Provide a valid key")
    assert parse_tool_error(f"{TOOL} error: boom") == (None, "boom")
    assert parse_tool_error("something else entirely") == (None, "something else entirely")
    assert parse_tool_error("") == (None, "")


# --- protocol errors, connection errors, timeouts -----------------------------------------------------------------

@pytest.mark.parametrize("message,kind,status", [
    ("Authentication required. Use OAuth or provide an API key.", "auth", 401),
    ("Invalid API key", "auth", 401),
    ("Server returned an error response", "protocol", None),
    ("SSE stream failed: Server-sent event exceeded the 1048576 byte limit.", "protocol", None),
    ("Internal server error", "protocol", None),
])
async def test_mcp_errors_are_classified_by_their_message(monkeypatch, rec, message, kind, status):
    install(monkeypatch, rec, call_exc=MCPError(-32000, message))
    with pytest.raises(ServiceError) as e:
        await call()
    assert (e.value.kind, e.value.status) == (kind, status)


async def test_an_mcp_error_during_the_handshake_is_classified_the_same_way(monkeypatch, rec):
    install(monkeypatch, rec, init_exc=MCPError(-32001, "Authentication required. Use OAuth or provide an API key."))
    with pytest.raises(ServiceError) as e:
        await call()
    assert e.value.kind == "auth" and rec.calls == []


async def test_an_exception_group_is_classified_by_what_is_inside_it(monkeypatch, rec):
    install(monkeypatch, rec, call_exc=ExceptionGroup("task group", [MCPError(-32000, "Authentication required.")]))
    with pytest.raises(ServiceError) as e:
        await call()
    assert e.value.kind == "auth"


@pytest.mark.parametrize("exc", [httpx2.ConnectError("refused"), httpx2.ReadError("reset"), httpx2.RemoteProtocolError("dropped"),
                                  ConnectionResetError("reset"), OSError("network unreachable")])
async def test_connection_failures(monkeypatch, rec, exc):
    install(monkeypatch, rec, call_exc=exc)
    with pytest.raises(ServiceError) as e:
        await call()
    assert e.value.kind == "connection"


async def test_a_failure_to_open_the_connection_is_a_connection_failure(monkeypatch, rec):
    install(monkeypatch, rec, open_exc=httpx2.ConnectError("refused"))
    with pytest.raises(ServiceError) as e:
        await call()
    assert e.value.kind == "connection"


async def test_an_http_status_error_keeps_its_status(monkeypatch, rec):
    req = httpx2.Request("POST", "https://mcp.example.test/mcp")
    install(monkeypatch, rec, call_exc=httpx2.HTTPStatusError("bad", request=req, response=httpx2.Response(401, request=req)))
    with pytest.raises(ServiceError) as e:
        await call()
    assert (e.value.kind, e.value.status) == ("auth", 401)
    install(monkeypatch, rec, call_exc=httpx2.HTTPStatusError("bad", request=req, response=httpx2.Response(503, request=req)))
    with pytest.raises(ServiceError) as e:
        await call()
    assert (e.value.kind, e.value.status) == ("server_error", 503)


async def test_an_unexpected_exception_is_a_protocol_failure(monkeypatch, rec):
    install(monkeypatch, rec, call_exc=ValueError("weird"))
    with pytest.raises(ServiceError) as e:
        await call()
    assert e.value.kind == "protocol"


async def test_the_timeout_covers_the_search(monkeypatch, rec):
    install(monkeypatch, rec, result=text_result("{}"), call_sleep=5)
    with pytest.raises(ServiceError) as e:
        await call(timeout=0.05)
    assert e.value.kind == "timeout" and rec.closed == 1


async def test_the_timeout_covers_the_handshake_too(monkeypatch, rec):
    install(monkeypatch, rec, result=text_result("{}"), init_sleep=5)
    with pytest.raises(ServiceError) as e:
        await call(timeout=0.05)
    assert e.value.kind == "timeout" and rec.calls == []


async def test_the_http_client_gets_a_timeout_no_longer_than_ours(monkeypatch, rec):
    install(monkeypatch, rec, result=text_result(json.dumps(exa_response([]))))
    await call(timeout=7.0)
    t = rec.http_timeout
    assert t is not None and max(t.connect, t.read, t.write, t.pool) <= 7.0


async def test_the_key_never_appears_in_an_error(monkeypatch, rec):
    for exc in (MCPError(-32000, f"failed for {KEY} somewhere"), RuntimeError(f"url with {KEY}"),
                httpx2.ConnectError(f"cannot reach host using {KEY}")):
        install(monkeypatch, rec, call_exc=exc)
        with pytest.raises(ServiceError) as e:
            await call()
        assert KEY not in e.value.message and KEY not in str(e.value) and KEY not in repr(e.value)
    install(monkeypatch, rec, result=text_result(f"{TOOL} error (400): bad thing with {KEY} in it", True))
    with pytest.raises(ServiceError) as e:
        await call()
    assert KEY not in e.value.message


async def test_the_scrub_uses_the_same_stripped_key_as_the_header(monkeypatch, rec):
    # An environment value with a trailing newline: the header carries the stripped key, so that is what Exa can echo.
    monkeypatch.setenv("EXA_API_KEY", f"  {KEY}\n")
    install(monkeypatch, rec, result=text_result(f"{TOOL} error (401): Invalid API key {KEY} was refused", True))
    with pytest.raises(ServiceError) as e:
        await call()
    assert rec.headers == {"x-api-key": KEY}
    assert KEY not in e.value.message and KEY not in str(e.value) and "[key]" in e.value.message
    install(monkeypatch, rec, call_exc=MCPError(-32000, f"failed for {KEY}\n"))
    with pytest.raises(ServiceError) as e:
        await call()
    assert KEY not in e.value.message and KEY not in str(e.value)


@pytest.mark.parametrize("exc", [asyncio.CancelledError(), BaseExceptionGroup("tasks", [asyncio.CancelledError()])])
async def test_a_cancellation_is_not_turned_into_a_service_error(monkeypatch, rec, exc):
    install(monkeypatch, rec, call_exc=exc)
    with pytest.raises(BaseException) as e:
        await call()
    assert not isinstance(e.value, ServiceError)
    assert rec.closed == 1


async def test_no_retry_inside_the_transport(monkeypatch, rec):
    install(monkeypatch, rec, call_exc=httpx2.ConnectError("refused"))
    with pytest.raises(ServiceError):
        await call()
    assert len(rec.calls) == 1 and rec.sessions == 1


# --- the free tool listing ----------------------------------------------------------------------------------------

def tool(name=TOOL, props=None):
    schema = {"type": "object", "properties": props or {"query": {"type": "string"}}, "required": ["query"]}
    return types.Tool(name=name, description="d", input_schema=schema)


async def test_list_tool_schema_returns_the_tools_input_schema(monkeypatch, rec):
    install(monkeypatch, rec, tools=[tool("other_tool"), tool(props={"query": {"type": "string"}, "numResults": {"type": "number"}})])
    schema = await McpExaTransport().list_tool_schema()
    assert set(schema["properties"]) == {"query", "numResults"} and schema["required"] == ["query"]
    assert rec.list_calls == 1 and rec.calls == [] and rec.headers == {"x-api-key": KEY}


async def test_list_tool_schema_raises_when_the_tool_is_not_listed(monkeypatch, rec):
    install(monkeypatch, rec, tools=[tool("other_tool")])
    with pytest.raises(ServiceError) as e:
        await McpExaTransport().list_tool_schema()
    assert e.value.kind == "protocol"


async def test_list_tool_schema_needs_the_key_too(monkeypatch, rec):
    install(monkeypatch, rec, tools=[tool()])
    monkeypatch.delenv("EXA_API_KEY")
    with pytest.raises(ServiceError) as e:
        await McpExaTransport().list_tool_schema()
    assert e.value.kind == "auth" and rec.sessions == 0


# --- the fake -----------------------------------------------------------------------------------------------------

async def test_the_fake_plays_its_script_in_order_and_records_calls():
    f = FakeExaTransport([exa_response([]), FakeExaTransport.failure("timeout")])
    assert await f.call({"query": "a"}, 30.0) == exa_response([])
    with pytest.raises(ServiceError) as e:
        await f.call({"query": "b"}, 30.0)
    assert e.value.kind == "timeout"
    assert f.calls == [({"query": "a"}, 30.0), ({"query": "b"}, 30.0)]


async def test_the_fake_refuses_a_call_the_test_did_not_script():
    with pytest.raises(AssertionError):
        await FakeExaTransport().call({"query": "a"}, 30.0)


@pytest.mark.parametrize("kind,status", [
    ("no_credit", 402), ("auth", 401), ("key_refused", 401), ("bad_request", 400), ("permission", 403), ("not_found", 404),
    ("too_large", 413), ("rate_limited", 429), ("server_error", 503), ("gateway_timeout", 504), ("connection", None),
    ("timeout", None), ("protocol", None), ("unreadable", None),
])
def test_the_fake_has_every_failure_kind(kind, status):
    e = FakeExaTransport.failure(kind)
    assert isinstance(e, ServiceError) and e.service == "exa" and e.status == status
    assert e.kind == ("auth" if kind == "key_refused" else kind)


def test_the_fake_rejects_an_unknown_failure_name():
    with pytest.raises(KeyError):
        FakeExaTransport.failure("sideways")


async def test_the_fake_awaits_a_scripted_coroutine():
    async def later(args):
        return exa_response([exa_result(url="https://example.test/x", title=args["query"])])

    out = await FakeExaTransport([later]).call({"query": "slow"}, 30.0)
    assert out["results"][0]["title"] == "slow"


async def test_the_fake_can_script_a_result_from_the_arguments():
    f = FakeExaTransport([lambda args: exa_response([exa_result(url="https://example.test/x", title=args["query"])])])
    out = await f.call({"query": "echo"}, 30.0)
    assert out["results"][0]["title"] == "echo"


async def test_the_fake_does_not_keep_the_callers_dict():
    f = FakeExaTransport([exa_response([])])
    args = {"query": "a", "includeDomains": ["x.test"]}
    await f.call(args, 30.0)
    args["includeDomains"].append("y.test")
    assert f.calls[0][0]["includeDomains"] == ["x.test"]


async def test_the_fake_lists_a_tool_schema():
    f = FakeExaTransport(tool_schema={"type": "object", "properties": {"query": {"type": "string"}}})
    assert (await f.list_tool_schema())["properties"]["query"]["type"] == "string"
    with pytest.raises(ServiceError):
        await FakeExaTransport(tool_schema=FakeExaTransport.failure("timeout")).list_tool_schema()
