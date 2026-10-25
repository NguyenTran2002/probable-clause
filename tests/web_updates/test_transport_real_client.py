"""McpExaTransport against the real `mcp` client, talking to an in-process fake server through httpx2's MockTransport.
No socket is opened and no key is real: this checks that our use of the mcp package (session, headers, JSON and SSE
replies, error mapping, the time limit) works with the library as installed."""

import asyncio
import json

import httpx2
import pytest

from api.web_updates import exa as exa_module
from api.web_updates.exa import McpExaTransport, UpdateSearch, exa_response, exa_result
from api.web_updates.params import parse_params

pytestmark = pytest.mark.anyio

KEY = "synthetic-key-for-tests"
TOOL = "web_search_advanced_exa"


class FakeExaServer:
    """Just enough of MCP's streamable HTTP for initialize, tools/list and tools/call."""

    def __init__(self, mode="ok", delay_s=0.0):
        self.mode = mode
        self.delay_s = delay_s
        self.requests: list[httpx2.Request] = []
        self.tool_calls: list[dict] = []

    async def __call__(self, request: httpx2.Request) -> httpx2.Response:
        self.requests.append(request)
        if request.method == "GET":
            return httpx2.Response(405)
        if request.method == "DELETE":
            return httpx2.Response(200)
        msg = json.loads(request.content)
        method = msg.get("method")
        if self.delay_s:
            await asyncio.sleep(self.delay_s)
        if method == "initialize":
            return self._json(msg, {"protocolVersion": msg["params"]["protocolVersion"], "capabilities": {"tools": {}},
                                    "serverInfo": {"name": "fake-exa", "version": "0"}}, {"mcp-session-id": "s1"})
        if method == "notifications/initialized":
            return httpx2.Response(202)
        if method == "tools/list":
            return self._json(msg, {"tools": [{"name": TOOL, "description": "d", "inputSchema": {
                "type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}}]})
        if method == "tools/call":
            self.tool_calls.append(msg["params"])
            return self._tool_call(msg)
        return self._json(msg, {})

    @staticmethod
    def _json(msg, result, headers=None):
        return httpx2.Response(200, headers={"content-type": "application/json", **(headers or {})},
                               json={"jsonrpc": "2.0", "id": msg["id"], "result": result})

    def _tool_call(self, msg):
        ok_body = json.dumps(exa_response([exa_result(url="https://example.test/a", text="Synthetic text.")]))
        text_block = lambda t, err=False: {"content": [{"type": "text", "text": t}], "isError": err}   # noqa: E731
        if self.mode == "ok":
            return self._json(msg, text_block(ok_body))
        if self.mode == "sse":
            data = json.dumps({"jsonrpc": "2.0", "id": msg["id"], "result": text_block(ok_body)})
            return httpx2.Response(200, headers={"content-type": "text/event-stream"}, content=f"event: message\ndata: {data}\n\n".encode())
        if self.mode == "tool_402":
            return self._json(msg, text_block(f"{TOOL} error (402): NO_MORE_CREDITS\nTimestamp: 2026-10-24T18:22:17.250Z", True))
        if self.mode == "tool_400":
            return self._json(msg, text_block(f"{TOOL} error (400): Invalid request body | a synthetic reason", True))
        if self.mode == "gateway_401":
            return httpx2.Response(401, headers={"content-type": "application/json"}, json={
                "jsonrpc": "2.0", "id": None, "error": {"code": -32001, "message": "Authentication required. Use OAuth or provide an API key."}})
        if self.mode == "http_500":
            return httpx2.Response(500, text="Internal Server Error")
        raise AssertionError(self.mode)


@pytest.fixture(autouse=True)
def env(monkeypatch):
    monkeypatch.setenv("EXA_API_KEY", KEY)


def serve(monkeypatch, server):
    def client(headers=None, timeout=None, auth=None):
        return httpx2.AsyncClient(transport=httpx2.MockTransport(server), headers=headers, timeout=timeout)

    monkeypatch.setattr(exa_module, "create_mcp_http_client", client)


async def test_a_json_reply(monkeypatch):
    server = FakeExaServer("ok")
    serve(monkeypatch, server)
    body = await McpExaTransport().call({"query": "q", "type": "auto"}, 5.0)
    assert body["results"][0]["url"] == "https://example.test/a"
    assert server.tool_calls == [{"name": TOOL, "arguments": {"query": "q", "type": "auto"}}]
    assert {r.headers.get("x-api-key") for r in server.requests} == {KEY}
    assert all(KEY not in str(r.url) for r in server.requests)
    assert [r.method for r in server.requests].count("POST") >= 3          # initialize, initialized, the call


async def test_an_sse_reply(monkeypatch):
    serve(monkeypatch, FakeExaServer("sse"))
    body = await McpExaTransport().call({"query": "q"}, 5.0)
    assert body["results"][0]["title"] == "Synthetic title"


async def test_an_error_tool_result_becomes_a_service_error(monkeypatch):
    from api.errors import ServiceError
    serve(monkeypatch, FakeExaServer("tool_402"))
    with pytest.raises(ServiceError) as e:
        await McpExaTransport().call({"query": "q"}, 5.0)
    assert (e.value.kind, e.value.status, e.value.message) == ("no_credit", 402, "NO_MORE_CREDITS")
    serve(monkeypatch, FakeExaServer("tool_400"))
    with pytest.raises(ServiceError) as e:
        await McpExaTransport().call({"query": "q"}, 5.0)
    assert (e.value.kind, e.value.status) == ("bad_request", 400)


async def test_a_gateway_401_is_an_auth_failure(monkeypatch):
    from api.errors import ServiceError
    serve(monkeypatch, FakeExaServer("gateway_401"))
    with pytest.raises(ServiceError) as e:
        await McpExaTransport().call({"query": "q"}, 5.0)
    assert (e.value.kind, e.value.status) == ("auth", 401)


async def test_a_gateway_500_is_a_failure_that_is_not_ours_to_retry(monkeypatch):
    from api.errors import ServiceError
    server = FakeExaServer("http_500")
    serve(monkeypatch, server)
    with pytest.raises(ServiceError) as e:
        await McpExaTransport().call({"query": "q"}, 5.0)
    assert e.value.kind == "protocol"
    assert len(server.tool_calls) == 1


async def test_a_slow_server_hits_the_time_limit_during_the_handshake(monkeypatch):
    from api.errors import ServiceError
    server = FakeExaServer("ok", delay_s=5)
    serve(monkeypatch, server)
    with pytest.raises(ServiceError) as e:
        await McpExaTransport().call({"query": "q"}, 0.2)
    assert e.value.kind == "timeout" and server.tool_calls == []


async def test_the_tool_listing(monkeypatch):
    serve(monkeypatch, FakeExaServer("ok"))
    schema = await McpExaTransport().list_tool_schema()
    assert schema["properties"] == {"query": {"type": "string"}} and schema["required"] == ["query"]


async def test_a_whole_search_through_the_real_client(monkeypatch, make_store, make_ctx):
    serve(monkeypatch, FakeExaServer("ok"))
    ctx, store = make_ctx(), make_store()
    o = await UpdateSearch(McpExaTransport(), store).search(parse_params({"query": "synthetic"}), 1, {}, ctx)
    assert o.kind == "ok" and [p.id for p in o.pages] == ["web-1-1"] and o.cost_usd == 0.007


async def test_a_402_through_the_real_client_ends_the_checks_for_the_run(monkeypatch, make_store, make_ctx):
    serve(monkeypatch, FakeExaServer("tool_402"))
    ctx, store = make_ctx(), make_store()
    o = await UpdateSearch(McpExaTransport(), store).search(parse_params({"query": "synthetic"}), 1, {}, ctx)
    assert o.kind == "unavailable" and o.unavailable_reason == "no_credit"
    assert ctx.flags.exa_unavailable == "no_credit" and "set_flag" in store.names() and "record_stop" in store.names()
