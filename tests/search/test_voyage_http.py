"""HttpVoyageClient against httpx2's MockTransport: request shape, response parsing, error mapping (no network)."""

import json

import httpx2
import pytest

from api.errors import ServiceError
from api.search.voyage import HttpVoyageClient

pytestmark = pytest.mark.anyio


def client_with(handler, monkeypatch, key="test-key", **kw):
    if key is not None:
        monkeypatch.setenv("VOYAGE_API_KEY", key)
    else:
        monkeypatch.delenv("VOYAGE_API_KEY", raising=False)
    return HttpVoyageClient(transport=httpx2.MockTransport(handler), **kw)


def embed_reply(vectors, tokens=7):
    return httpx2.Response(200, json={
        "object": "list", "model": "voyage-law-2", "usage": {"total_tokens": tokens},
        "data": [{"object": "embedding", "embedding": v, "index": i} for i, v in enumerate(vectors)],
    })


async def test_embed_request_shape_and_parsing(monkeypatch):
    seen = {}

    def handler(request: httpx2.Request):
        seen["url"] = str(request.url)
        seen["auth"] = request.headers["authorization"]
        seen["body"] = json.loads(request.content)
        # out of order on purpose: the client sorts by index
        return httpx2.Response(200, json={
            "usage": {"total_tokens": 11},
            "data": [{"index": 1, "embedding": [0.0, 1.0]}, {"index": 0, "embedding": [1.0, 0.0]}],
        })

    c = client_with(handler, monkeypatch, base_url="https://example.test/v1")
    vectors, usage = await c.embed(["a", "b"], "document")
    assert vectors == [[1.0, 0.0], [0.0, 1.0]]
    assert (usage.service, usage.model, usage.input_tokens) == ("voyage", "voyage-law-2", 11)
    assert seen["url"] == "https://example.test/v1/embeddings"
    assert seen["auth"] == "Bearer test-key"
    assert seen["body"]["input"] == ["a", "b"] and seen["body"]["model"] == "voyage-law-2"
    assert seen["body"]["input_type"] == "document"


async def test_base_url_comes_from_the_environment_when_not_passed(monkeypatch):
    seen = {}

    def handler(request):
        seen["url"] = str(request.url)
        return embed_reply([[1.0]])

    monkeypatch.setenv("VOYAGE_BASE_URL", "https://other.test/v1/")
    c = client_with(handler, monkeypatch)
    await c.embed(["a"], "query")
    assert seen["url"] == "https://other.test/v1/embeddings"


async def test_rerank_request_shape_and_sorting(monkeypatch):
    seen = {}

    def handler(request):
        seen["url"] = str(request.url)
        seen["body"] = json.loads(request.content)
        return httpx2.Response(200, json={"usage": {"total_tokens": 5}, "data": [
            {"index": 0, "relevance_score": 0.2}, {"index": 2, "relevance_score": 0.9}, {"index": 1, "relevance_score": 0.5}]})

    c = client_with(handler, monkeypatch)
    ranked, usage = await c.rerank("the query", ["d0", "d1", "d2"])
    assert ranked == [(2, 0.9), (1, 0.5), (0, 0.2)]
    assert usage.model == "rerank-3" and usage.input_tokens == 5
    assert seen["url"].endswith("/rerank")
    assert seen["body"]["query"] == "the query" and seen["body"]["documents"] == ["d0", "d1", "d2"]
    assert seen["body"]["model"] == "rerank-3"
    assert "top_k" not in seen["body"]  # every document comes back


@pytest.mark.parametrize("status,kind", [
    (400, "bad_request"), (401, "auth"), (403, "permission"), (404, "not_found"), (413, "too_large"),
    (422, "bad_request"), (429, "rate_limited"), (500, "server_error"), (502, "server_error"),
    (503, "server_error"), (504, "gateway_timeout"),
])
async def test_status_mapping(monkeypatch, status, kind):
    c = client_with(lambda r: httpx2.Response(status, json={"detail": "secret text of the query"}), monkeypatch)
    with pytest.raises(ServiceError) as e:
        await c.embed(["a"], "query")
    assert (e.value.service, e.value.kind, e.value.status) == ("voyage", kind, status)
    assert "secret text" not in str(e.value) and "secret text" not in e.value.message  # T3.7


async def test_retry_after_header_is_carried(monkeypatch):
    c = client_with(lambda r: httpx2.Response(429, headers={"retry-after": "7"}), monkeypatch)
    with pytest.raises(ServiceError) as e:
        await c.rerank("q", ["a"])
    assert e.value.kind == "rate_limited" and e.value.retry_after_s == 7.0


async def test_unusable_retry_after_is_ignored(monkeypatch):
    c = client_with(lambda r: httpx2.Response(429, headers={"retry-after": "Wed, 21 Oct 2026 07:28:00 GMT"}), monkeypatch)
    with pytest.raises(ServiceError) as e:
        await c.rerank("q", ["a"])
    assert e.value.retry_after_s is None


async def test_timeout_and_connection_failures(monkeypatch):
    def slow(request):
        raise httpx2.ReadTimeout("slow", request=request)

    def refused(request):
        raise httpx2.ConnectError("refused", request=request)

    with pytest.raises(ServiceError) as e:
        await client_with(slow, monkeypatch).embed(["a"], "query")
    assert e.value.kind == "timeout" and e.value.status is None
    with pytest.raises(ServiceError) as e:
        await client_with(refused, monkeypatch).embed(["a"], "query")
    assert e.value.kind == "connection"


async def test_whole_request_deadline(monkeypatch):
    import asyncio

    async def hang(request):
        await asyncio.sleep(5)
        return embed_reply([[1.0]])

    c = client_with(hang, monkeypatch, timeout_s=0.05)
    with pytest.raises(ServiceError) as e:
        await c.embed(["a"], "query")
    assert e.value.kind == "timeout"


@pytest.mark.parametrize("payload", [
    "not json", {"data": []}, {"usage": {"total_tokens": 1}}, {"usage": {"total_tokens": 1}, "data": [{"index": 0}]},
])
async def test_unreadable_replies(monkeypatch, payload):
    def handler(request):
        if isinstance(payload, str):
            return httpx2.Response(200, content=payload.encode())
        return httpx2.Response(200, json=payload)

    with pytest.raises(ServiceError) as e:
        await client_with(handler, monkeypatch).embed(["a"], "query")
    assert e.value.kind == "unreadable"


async def test_wrong_number_of_vectors_is_unreadable(monkeypatch):
    with pytest.raises(ServiceError) as e:
        await client_with(lambda r: embed_reply([[1.0]]), monkeypatch).embed(["a", "b"], "query")
    assert e.value.kind == "unreadable"


async def test_missing_key_is_an_auth_failure_and_makes_no_request(monkeypatch):
    called = []
    c = client_with(lambda r: called.append(r) or embed_reply([[1.0]]), monkeypatch, key=None)
    with pytest.raises(ServiceError) as e:
        await c.embed(["a"], "query")
    assert e.value.kind == "auth" and not called


async def test_the_key_never_appears_in_an_error(monkeypatch):
    c = client_with(lambda r: httpx2.Response(401), monkeypatch, key="sk-very-secret")
    with pytest.raises(ServiceError) as e:
        await c.embed(["a"], "query")
    assert "sk-very-secret" not in repr(e.value) and "sk-very-secret" not in e.value.message


async def test_a_failing_request_makes_exactly_one_http_call(monkeypatch):
    for status in (500, 429, 504):
        calls = []

        def handler(request, status=status):
            calls.append(request)
            return httpx2.Response(status)

        with pytest.raises(ServiceError):
            await client_with(handler, monkeypatch).embed(["a"], "query")
        assert len(calls) == 1               # no hidden retries inside the client (T3.3)
    calls.clear()

    def refused(request):
        calls.append(request)
        raise httpx2.ConnectError("refused", request=request)

    with pytest.raises(ServiceError):
        await client_with(refused, monkeypatch).rerank("q", ["a"])
    assert len(calls) == 1


def test_default_timeout_is_the_setting():
    from api import settings
    assert HttpVoyageClient()._timeout_s == float(settings.VOYAGE_TIMEOUT_S.value)
