"""FakeVoyageClient: deterministic vectors, scripted failures (contract §12)."""

import numpy as np
import pytest

from api.errors import ServiceError
from api.search.voyage import FakeVoyageClient

pytestmark = pytest.mark.anyio


async def test_vectors_are_deterministic_unit_length_and_1024_wide():
    fake = FakeVoyageClient()
    (a, b), usage = await fake.embed(["alpha", "beta"], "document")
    (a2,), _ = await FakeVoyageClient().embed(["alpha"], "document")
    assert a == a2 and a != b
    assert len(a) == 1024 and abs(np.linalg.norm(a) - 1.0) < 1e-5
    assert usage.service == "voyage" and usage.model == "voyage-law-2" and usage.input_tokens > 0


async def test_the_same_text_embeds_the_same_for_query_and_document():
    fake = FakeVoyageClient()
    (q,), _ = await fake.embed(["alpha"], "query")
    (d,), _ = await fake.embed(["alpha"], "document")
    assert q == d


async def test_rerank_returns_every_document_best_first():
    fake = FakeVoyageClient(rerank_score=lambda q, d: float(len(d)))
    ranked, usage = await fake.rerank("q", ["aa", "a", "aaaa", "aaa"])
    assert [i for i, _ in ranked] == [2, 3, 0, 1]
    assert [s for _, s in ranked] == [4.0, 3.0, 2.0, 1.0]
    assert usage.model == "rerank-3"


async def test_scripted_failures_are_consumed_in_order_then_it_succeeds():
    boom = ServiceError("voyage", "server_error", 500, "boom")
    fake = FakeVoyageClient(embed_failures=[boom, None, boom])
    with pytest.raises(ServiceError):
        await fake.embed(["x"], "query")
    await fake.embed(["x"], "query")
    with pytest.raises(ServiceError):
        await fake.embed(["x"], "query")
    await fake.embed(["x"], "query")  # exhausted: succeeds
    assert len(fake.calls) == 4


async def test_rerank_failures_are_separate_from_embed_failures():
    fake = FakeVoyageClient(rerank_failures=[ServiceError("voyage", "timeout")])
    await fake.embed(["x"], "query")
    with pytest.raises(ServiceError):
        await fake.rerank("q", ["a"])
    assert [c[0] for c in fake.calls] == ["embed", "rerank"]
