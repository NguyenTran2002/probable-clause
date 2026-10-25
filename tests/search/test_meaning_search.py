"""MeaningIndex.search: order, degraded paths, retries, records (T1.4, T3.3, contract §4.C)."""

import logging

import numpy as np
import pytest

from api import settings
from api.errors import ServiceError
from api.search.meaning import MeaningIndex, embedded_text
from api.search.voyage import FakeVoyageClient
from api.types import RunStopped
from tests.search.support import FakeContext, make_passage, recording_sleep, write_vectors

pytestmark = pytest.mark.anyio

ALL = lambda p: True  # noqa: E731


def build(tmp_path, passages, fake=None):
    write_vectors(tmp_path, passages, fake)
    return MeaningIndex.load(tmp_path, passages)


def err(kind, status=None, **kw):
    return ServiceError("voyage", kind, status, kind, **kw)


def expected_embedding_order(fake, query, passages):
    q = np.array(fake.vector_for(query))
    scored = [(float(np.dot(q, np.array(fake.vector_for(embedded_text(p))))), p.id) for p in passages]
    return [pid for _, pid in sorted(scored, key=lambda t: -t[0])]


# ---- the normal path

async def test_ok_path_reranks_everything_and_orders_by_rerank_score(tmp_path, ctx):
    passages = [make_passage(i, text="word " * (i * 7 % 11 + 1)) for i in range(1, 9)]
    fake = FakeVoyageClient(rerank_score=lambda q, d: -float(len(d)))   # shortest text first
    idx = build(tmp_path, passages, fake)
    res = await idx.search("warrant", ALL, ctx, fake)
    assert res.status == "ok" and res.message_for_claude is None
    assert len(res.hits) == len(passages) and all(h.reranked for h in res.hits)
    by_len = sorted(passages, key=lambda p: len(embedded_text(p)))
    assert [h.passage_id for h in res.hits] == [p.id for p in by_len]
    scores = [h.score for h in res.hits]
    assert scores == sorted(scores, reverse=True)
    assert not (ctx.flags.meaning_degraded or ctx.flags.meaning_unavailable_once or ctx.flags.voyage_unavailable)


async def test_query_is_embedded_as_a_query_and_candidates_are_reranked_as_embedded_texts(tmp_path, passages, ctx):
    fake = FakeVoyageClient()
    idx = build(tmp_path, passages, fake)
    await idx.search("a plain description", ALL, ctx, fake)
    kind, texts, input_type = fake.calls[0]
    assert (kind, texts, input_type) == ("embed", ["a plain description"], "query")
    kind, query, docs = fake.calls[1]
    assert kind == "rerank" and query == "a plain description"
    assert sorted(docs) == sorted(embedded_text(p) for p in passages)


async def test_candidates_are_the_closest_by_dot_product_in_that_order(tmp_path, ctx):
    fake = FakeVoyageClient()
    ps = [make_passage(i) for i in range(1, 8)]
    idx = build(tmp_path, ps, fake)
    await idx.search("warrant", ALL, ctx, fake)
    docs = fake.calls[1][2]
    order = expected_embedding_order(fake, "warrant", ps)
    by_text = {embedded_text(p): p.id for p in ps}
    assert [by_text[d] for d in docs] == order


async def test_only_semantic_candidates_are_reranked(tmp_path, ctx):
    ps = [make_passage(i) for i in range(1, 61)]
    fake = FakeVoyageClient()
    idx = build(tmp_path, ps, fake)
    res = await idx.search("warrant", ALL, ctx, fake)
    n = int(settings.SEMANTIC_CANDIDATES.value)
    assert len(fake.calls[1][2]) == n and len(res.hits) == n
    assert {h.passage_id for h in res.hits} == set(expected_embedding_order(fake, "warrant", ps)[:n])


async def test_keep_filters_before_ranking_and_is_never_sent_to_voyage(tmp_path, passages, ctx):
    fake = FakeVoyageClient()
    idx = build(tmp_path, passages, fake)
    res = await idx.search("x", lambda p: p.position % 2 == 0, ctx, fake)
    assert {h.passage_id for h in res.hits} == {"katz-1-p2", "katz-1-p4", "katz-1-p6", "katz-1-p8"}
    assert len(fake.calls[1][2]) == 4


async def test_nothing_kept_means_ok_with_no_hits_and_no_voyage_call(tmp_path, passages, ctx):
    fake = FakeVoyageClient()
    idx = build(tmp_path, passages, fake)
    res = await idx.search("x", lambda p: False, ctx, fake)
    assert res.status == "ok" and res.hits == [] and fake.calls == [] and ctx.log == []


async def test_records_in_order_embed_then_rerank(tmp_path, passages, ctx):
    fake = FakeVoyageClient()
    idx = build(tmp_path, passages, fake)
    await idx.search("x", ALL, ctx, fake)
    assert ctx.log == [
        ("before", "voyage", "embed"), ("usage", "embed", 1, "ok", None),
        ("before", "voyage", "rerank"), ("usage", "rerank", 1, "ok", None),
    ]
    first = ctx.usages[0]
    assert first["usage"].service == "voyage" and first["usage"].model == "voyage-law-2"
    assert ctx.usages[1]["usage"].model == "rerank-3"
    assert first["max_attempts"] == 3 and first["duration_ms"] >= 0


# ---- retries and degraded paths

async def test_embed_retried_then_succeeds(tmp_path, passages, ctx, sleeps):
    fake = FakeVoyageClient(embed_failures=[err("server_error", 500), err("timeout")])
    idx = build(tmp_path, passages, fake)
    res = await idx.search("x", ALL, ctx, fake, sleep=sleeps)
    assert res.status == "ok"
    embeds = [u for u in ctx.usages if u["purpose"] == "embed"]
    assert [(u["attempt"], u["outcome"], u["error_kind"]) for u in embeds] == [
        (1, "retrying", "server_error"), (2, "retrying", "timeout"), (3, "ok", None)]
    # a failed attempt is recorded at an estimate of its input (T3.3): ceil(len("x") / 3) = 1 token
    failed = embeds[0]["usage"]
    assert failed.estimated and failed.model == "voyage-law-2" and failed.input_tokens == 1
    assert not embeds[2]["usage"].estimated
    assert sleeps.waits == [1.0, 3.0]                       # VOYAGE_POLICY's waits (T3.3)
    # before_paid_call ran before every attempt, in step with the records
    assert [e for e in ctx.log if e[0] == "before"].count(("before", "voyage", "embed")) == 3


async def test_retry_after_wins_over_the_wait(tmp_path, passages, ctx, sleeps):
    fake = FakeVoyageClient(rerank_failures=[err("rate_limited", 429, retry_after_s=4.5)])
    idx = build(tmp_path, passages, fake)
    res = await idx.search("x", ALL, ctx, fake, sleep=sleeps)
    assert res.status == "ok" and sleeps.waits == [4.5]


async def test_embed_failing_after_retries_is_unavailable(tmp_path, passages, ctx, sleeps, caplog):
    fake = FakeVoyageClient(embed_failures=[err("server_error", 500)] * 3)
    idx = build(tmp_path, passages, fake)
    res = await idx.search("secret query text", ALL, ctx, fake, sleep=sleeps)
    assert res.status == "unavailable" and res.hits == []
    assert "keyword search" in res.message_for_claude.lower()
    assert ctx.flags.meaning_unavailable_once and not ctx.flags.meaning_degraded
    assert not ctx.flags.voyage_unavailable
    assert len([c for c in fake.calls if c[0] == "embed"]) == 3 and not [c for c in fake.calls if c[0] == "rerank"]
    outcomes = [(u["attempt"], u["outcome"]) for u in ctx.usages]
    assert outcomes == [(1, "retrying"), (2, "retrying"), (3, "failed")]
    assert ctx.usages[-1]["error_kind"] == "server_error"
    assert all(u["usage"].estimated and u["usage"].input_tokens == 6 for u in ctx.usages)   # 17 characters / 3
    assert "secret query text" not in caplog.text


async def test_rerank_failing_after_retries_falls_back_to_embedding_order(tmp_path, ctx, sleeps):
    ps = [make_passage(i) for i in range(1, 8)]
    fake = FakeVoyageClient(rerank_failures=[err("gateway_timeout", 504)] * 3)
    idx = build(tmp_path, ps, fake)
    res = await idx.search("warrant", ALL, ctx, fake, sleep=sleeps)
    assert res.status == "not_reranked"
    assert "keyword search" in res.message_for_claude.lower() and "not reranked" in res.message_for_claude.lower()
    assert [h.passage_id for h in res.hits] == expected_embedding_order(fake, "warrant", ps)
    assert all(not h.reranked for h in res.hits)
    assert ctx.flags.meaning_degraded and not ctx.flags.meaning_unavailable_once
    rr = [(u["attempt"], u["outcome"]) for u in ctx.usages if u["purpose"] == "rerank"]
    assert rr == [(1, "retrying"), (2, "retrying"), (3, "failed")]
    # query tokens x documents + document tokens (Voyage's count), from characters at 3 a token
    docs = idx.texts
    chars = len("warrant") * len(docs) + sum(len(d) for d in docs)
    for u in (u for u in ctx.usages if u["purpose"] == "rerank"):
        assert u["usage"].estimated and u["usage"].model == "rerank-3"
        assert u["usage"].input_tokens == -(-chars // 3) > 0


async def test_embedding_order_fallback_keeps_cosine_scores(tmp_path, ctx, sleeps):
    ps = [make_passage(i) for i in range(1, 6)]
    fake = FakeVoyageClient(rerank_failures=[err("server_error", 500)] * 3)
    idx = build(tmp_path, ps, fake)
    res = await idx.search("warrant", ALL, ctx, fake, sleep=sleeps)
    scores = [h.score for h in res.hits]
    assert scores == sorted(scores, reverse=True) and all(-1.0001 <= s <= 1.0001 for s in scores)


async def test_a_non_retryable_error_is_not_retried(tmp_path, passages, ctx, sleeps):
    fake = FakeVoyageClient(rerank_failures=[err("bad_request", 400)])
    idx = build(tmp_path, passages, fake)
    res = await idx.search("x", ALL, ctx, fake, sleep=sleeps)
    assert res.status == "not_reranked" and sleeps.waits == []
    assert len([c for c in fake.calls if c[0] == "rerank"]) == 1
    assert [u["outcome"] for u in ctx.usages if u["purpose"] == "rerank"] == ["failed"]


async def test_401_on_embed_marks_voyage_unavailable_for_the_run(tmp_path, passages, ctx, sleeps, caplog):
    fake = FakeVoyageClient(embed_failures=[err("auth", 401)])
    idx = build(tmp_path, passages, fake)
    with caplog.at_level(logging.ERROR):
        first = await idx.search("x", ALL, ctx, fake, sleep=sleeps)
    assert first.status == "unavailable" and ctx.flags.voyage_unavailable and ctx.flags.meaning_unavailable_once
    assert sleeps.waits == [] and len(fake.calls) == 1
    assert "configuration" in caplog.text.lower()
    n_log = len(ctx.log)
    second = await idx.search("y", ALL, ctx, fake, sleep=sleeps)
    assert second.status == "unavailable" and "keyword search" in second.message_for_claude.lower()
    assert len(fake.calls) == 1 and len(ctx.log) == n_log        # no further Voyage call, nothing recorded


async def test_401_on_rerank_also_stops_later_searches(tmp_path, passages, ctx, sleeps):
    fake = FakeVoyageClient(rerank_failures=[err("auth", 401)])
    idx = build(tmp_path, passages, fake)
    first = await idx.search("x", ALL, ctx, fake, sleep=sleeps)
    assert first.status == "not_reranked" and ctx.flags.voyage_unavailable and ctx.flags.meaning_degraded
    calls = len(fake.calls)
    second = await idx.search("y", ALL, ctx, fake, sleep=sleeps)
    assert second.status == "unavailable" and len(fake.calls) == calls


async def test_flags_are_per_run_context(tmp_path, passages, sleeps):
    fake = FakeVoyageClient(embed_failures=[err("auth", 401)])
    idx = build(tmp_path, passages, fake)
    a, b = FakeContext(), FakeContext()
    await idx.search("x", ALL, a, fake, sleep=sleeps)
    res = await idx.search("x", ALL, b, fake, sleep=sleeps)
    assert res.status == "ok" and not b.flags.voyage_unavailable


async def test_run_stopped_before_embed_propagates(tmp_path, passages, sleeps):
    fake = FakeVoyageClient()
    idx = build(tmp_path, passages, fake)
    ctx = FakeContext(stop_on_call=1)
    with pytest.raises(RunStopped):
        await idx.search("x", ALL, ctx, fake, sleep=sleeps)
    assert fake.calls == [] and ctx.usages == []


async def test_run_stopped_before_rerank_propagates_and_is_not_a_degraded_search(tmp_path, passages, sleeps):
    fake = FakeVoyageClient()
    idx = build(tmp_path, passages, fake)
    ctx = FakeContext(stop_on_call=2)
    with pytest.raises(RunStopped):
        await idx.search("x", ALL, ctx, fake, sleep=sleeps)
    assert [c[0] for c in fake.calls] == ["embed"] and not ctx.flags.meaning_degraded


async def test_run_stopped_before_a_retry_propagates(tmp_path, passages, sleeps):
    fake = FakeVoyageClient(embed_failures=[err("server_error", 500)])
    idx = build(tmp_path, passages, fake)
    ctx = FakeContext(stop_on_call=2)
    with pytest.raises(RunStopped):
        await idx.search("x", ALL, ctx, fake, sleep=sleeps)
    assert len(fake.calls) == 1 and not ctx.flags.meaning_unavailable_once


async def test_a_reply_with_a_wrong_sized_vector_is_unavailable(tmp_path, passages, ctx, sleeps):
    class Bad(FakeVoyageClient):
        async def embed(self, texts, input_type):
            vecs, usage = await super().embed(texts, input_type)
            return [v[:10] for v in vecs], usage

    fake = Bad()
    idx = build(tmp_path, passages, FakeVoyageClient())
    res = await idx.search("x", ALL, ctx, fake, sleep=sleeps)
    assert res.status == "unavailable" and ctx.flags.meaning_unavailable_once


async def test_a_rerank_reply_with_a_bad_index_is_not_reranked(tmp_path, passages, ctx, sleeps):
    class Bad(FakeVoyageClient):
        async def rerank(self, query, documents):
            ranked, usage = await super().rerank(query, documents)
            return [(99, 1.0)] + ranked[1:], usage

    fake = Bad()
    idx = build(tmp_path, passages, FakeVoyageClient())
    res = await idx.search("x", ALL, ctx, fake, sleep=sleeps)
    assert res.status == "not_reranked" and all(not h.reranked for h in res.hits) and ctx.flags.meaning_degraded


async def test_a_short_rerank_reply_keeps_the_missing_candidates_unreranked_at_the_end(tmp_path, passages, ctx, sleeps):
    class Short(FakeVoyageClient):
        async def rerank(self, query, documents):
            ranked, usage = await super().rerank(query, documents)
            return ranked[:3], usage

    fake = Short()
    idx = build(tmp_path, passages, FakeVoyageClient())
    res = await idx.search("x", ALL, ctx, fake, sleep=sleeps)
    assert len(res.hits) == len(passages)
    assert [h.reranked for h in res.hits] == [True] * 3 + [False] * (len(passages) - 3)
    assert res.status == "not_reranked" and ctx.flags.meaning_degraded
