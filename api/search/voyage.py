"""Voyage AI clients: the real HTTP one, and the fake for tests (contract §4.C, §12).

Request and response shapes are from Voyage's public docs (read Oct 24, 2026):
  - embeddings: https://docs.voyageai.com/reference/embeddings-api
      POST {base}/embeddings {input: [str], model, input_type: "query"|"document", truncation}
      -> {data: [{embedding: [float], index}], usage: {total_tokens}}
  - rerank: https://docs.voyageai.com/reference/reranker-api
      POST {base}/rerank {query, documents: [str], model, top_k?, truncation}
      -> {data: [{index, relevance_score}], usage: {total_tokens}}, sorted by score, best first
  - rate limits (HTTP 429, no retry-after header documented): https://docs.voyageai.com/docs/rate-limits
Auth is `Authorization: Bearer <key>`.

The client never retries (T3.3: our retries are api/retry.py's, each one shown as a step). Every failure is
raised as a ServiceError with an ErrorKind. Error messages never hold the response body, the query or the key (T3.7).
"""

import asyncio
import hashlib
import os
from collections.abc import Callable
from typing import Literal, Protocol

import httpx2
import numpy as np

from api import settings
from api.errors import ErrorKind, ServiceError
from api.types import Usage

InputType = Literal["query", "document"]


class VoyageClient(Protocol):
    async def embed(self, texts: list[str], input_type: InputType) -> tuple[list[list[float]], Usage]: ...

    async def rerank(self, query: str, documents: list[str]) -> tuple[list[tuple[int, float]], Usage]:
        """Every document, best first, as (index into `documents`, relevance score)."""
        ...


def _kind_for_status(status: int) -> ErrorKind:
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
    if status >= 500:
        return "server_error"
    return "bad_request"


def _retry_after(response: httpx2.Response) -> float | None:
    raw = response.headers.get("retry-after")
    if raw is None:
        return None
    try:
        value = float(raw)
    except ValueError:
        return None          # an HTTP-date form is not used by Voyage; fall back to our own wait
    return value if value >= 0 else None


class HttpVoyageClient:
    """Voyage over plain HTTP (httpx2). The base URL, key and timeout are read when used, never logged."""

    def __init__(self, base_url: str | None = None, api_key: str | None = None, timeout_s: float | None = None,
                 transport: httpx2.AsyncBaseTransport | None = None):
        self._base_url = base_url
        self._api_key = api_key
        self._timeout_s = float(timeout_s if timeout_s is not None else settings.VOYAGE_TIMEOUT_S.value)
        self._transport = transport

    def _url(self, path: str) -> str:
        # PLACEHOLDER until the key's endpoint is checked (T5.5): VOYAGE_BASE_URL overrides the setting.
        base = self._base_url or os.environ.get("VOYAGE_BASE_URL") or str(settings.VOYAGE_BASE_URL.value)
        return base.rstrip("/") + path

    def _key(self) -> str:
        key = self._api_key or os.environ.get("VOYAGE_API_KEY")
        if not key:
            raise ServiceError("voyage", "auth", None, "VOYAGE_API_KEY is not set")
        return key

    async def _post(self, path: str, body: dict) -> dict:
        key = self._key()
        try:
            async with asyncio.timeout(self._timeout_s):     # one deadline for the whole request (T3.3)
                async with httpx2.AsyncClient(transport=self._transport, timeout=self._timeout_s) as http:
                    response = await http.post(
                        self._url(path), json=body,
                        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
        except (TimeoutError, httpx2.TimeoutException):
            raise ServiceError("voyage", "timeout", None, "Voyage did not answer in time") from None
        except httpx2.TransportError:
            raise ServiceError("voyage", "connection", None, "Voyage could not be reached") from None
        except httpx2.HTTPError:
            raise ServiceError("voyage", "protocol", None, "Voyage request failed") from None
        if response.status_code != 200:
            raise ServiceError("voyage", _kind_for_status(response.status_code), response.status_code,
                               f"Voyage returned HTTP {response.status_code}", retry_after_s=_retry_after(response))
        try:
            data = response.json()
            if not isinstance(data, dict):
                raise ValueError
            return data
        except ValueError:
            raise ServiceError("voyage", "unreadable", 200, "Voyage's reply was not JSON") from None

    @staticmethod
    def _tokens(data: dict) -> int:
        try:
            return int(data["usage"]["total_tokens"])
        except (KeyError, TypeError, ValueError):
            raise ServiceError("voyage", "unreadable", 200, "Voyage's reply had no token count") from None

    async def embed(self, texts: list[str], input_type: InputType) -> tuple[list[list[float]], Usage]:
        # truncation off: a text over the model's limit is an error, never a silently shortened embedding.
        data = await self._post("/embeddings", {
            "input": texts, "model": settings.EMBED_MODEL.value, "input_type": input_type, "truncation": False})
        tokens = self._tokens(data)
        try:
            rows = sorted(data["data"], key=lambda r: r["index"])
            vectors = [[float(x) for x in r["embedding"]] for r in rows]
            indexes = [r["index"] for r in rows]
        except (KeyError, TypeError, ValueError):
            raise ServiceError("voyage", "unreadable", 200, "Voyage's embeddings reply was malformed") from None
        if indexes != list(range(len(texts))):
            raise ServiceError("voyage", "unreadable", 200, "Voyage returned the wrong number of embeddings")
        return vectors, Usage(service="voyage", model=str(settings.EMBED_MODEL.value), input_tokens=tokens)

    async def rerank(self, query: str, documents: list[str]) -> tuple[list[tuple[int, float]], Usage]:
        data = await self._post("/rerank", {
            "query": query, "documents": documents, "model": settings.RERANK_MODEL.value})
        tokens = self._tokens(data)
        try:
            ranked = [(int(r["index"]), float(r["relevance_score"])) for r in data["data"]]
        except (KeyError, TypeError, ValueError):
            raise ServiceError("voyage", "unreadable", 200, "Voyage's rerank reply was malformed") from None
        ranked.sort(key=lambda t: -t[1])        # stable: the API already sends best first
        return ranked, Usage(service="voyage", model=str(settings.RERANK_MODEL.value), input_tokens=tokens)


class FakeVoyageClient:
    """Deterministic vectors from a hash; failures scripted per call (contract §12).

    `embed_failures` and `rerank_failures` are consumed one per call, in order: a ServiceError is raised, None
    succeeds; once the list is used up every call succeeds. `calls` records ("embed", texts, input_type) and
    ("rerank", query, documents). `rerank_score(query, document)` sets the relevance, hash-based by default.
    """

    def __init__(self, dimension: int | None = None, *, embed_failures: list[ServiceError | None] | None = None,
                 rerank_failures: list[ServiceError | None] | None = None,
                 rerank_score: Callable[[str, str], float] | None = None):
        self.dimension = int(dimension or settings.EMBED_DIMENSION.value)
        self._embed_failures = list(embed_failures or [])
        self._rerank_failures = list(rerank_failures or [])
        self._rerank_score = rerank_score
        self.calls: list[tuple] = []

    def vector_for(self, text: str) -> list[float]:
        seed = int.from_bytes(hashlib.sha256(text.encode("utf-8")).digest()[:8], "big")
        v = np.random.default_rng(seed).standard_normal(self.dimension)
        return (v / np.linalg.norm(v)).tolist()

    @staticmethod
    def _next(failures: list[ServiceError | None]) -> None:
        if failures:
            scripted = failures.pop(0)
            if scripted is not None:
                raise scripted

    async def embed(self, texts: list[str], input_type: InputType) -> tuple[list[list[float]], Usage]:
        self.calls.append(("embed", list(texts), input_type))
        self._next(self._embed_failures)
        tokens = sum(max(1, len(t.split())) for t in texts)
        return [self.vector_for(t) for t in texts], Usage(
            service="voyage", model=str(settings.EMBED_MODEL.value), input_tokens=tokens)

    async def rerank(self, query: str, documents: list[str]) -> tuple[list[tuple[int, float]], Usage]:
        self.calls.append(("rerank", query, list(documents)))
        self._next(self._rerank_failures)
        score = self._rerank_score or (lambda q, d: int.from_bytes(
            hashlib.sha256((q + "\x00" + d).encode("utf-8")).digest()[:4], "big") / 2**32)
        ranked = sorted(((i, float(score(query, d))) for i, d in enumerate(documents)), key=lambda t: -t[1])
        tokens = len(query.split()) * len(documents) + sum(len(d.split()) for d in documents)
        return ranked, Usage(service="voyage", model=str(settings.RERANK_MODEL.value), input_tokens=max(1, tokens))
