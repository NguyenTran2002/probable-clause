"""scripts/embed_corpus.py: dry run, batching, cache, output format, with the fake client, in tmp_path (no network)."""

import hashlib
import importlib.util
import json
import re
from pathlib import Path

import numpy as np
import pytest

from api.errors import ServiceError
from api.search.meaning import MeaningIndex, embedded_text
from api.search.voyage import FakeVoyageClient
from tests.search.support import make_passage, recording_sleep


SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "embed_corpus.py"


@pytest.fixture(scope="module")
def script():
    spec = importlib.util.spec_from_file_location("embed_corpus_under_test", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def price(usage):
    return usage.input_tokens * 0.12 / 1_000_000


class Exploding:
    async def embed(self, *a, **k):
        raise AssertionError("a dry run must make no Voyage call")

    rerank = embed


def run(script, tmp_path, passages, argv, client=None, **kw):
    sleep = kw.pop("sleep", recording_sleep())
    return script.main(
        argv + ["--out", str(tmp_path / "vectors"), "--cache", str(tmp_path / "cache")],
        passages=passages, price_fn=price, client=client, sleep=sleep, today=lambda: "2026-10-24",
        env_path=tmp_path / "no.env", **kw), sleep


# ---- batching

def test_batches_respect_item_and_token_limits_and_cover_everything_in_order(script):
    texts = ["x" * 30] * 200 + ["y" * 90_000] * 5 + ["z" * 30] * 10
    batches = script.plan_batches(texts)
    flat = [i for b in batches for i in b]
    assert flat == list(range(len(texts)))
    for b in batches:
        assert len(b) <= script.MAX_BATCH_ITEMS
        assert sum(script.estimate_tokens(texts[i]) for i in b) <= script.MAX_BATCH_EST_TOKENS or len(b) == 1
    assert script.MAX_BATCH_EST_TOKENS * 2 <= 120_000   # half of voyage-law-2's 120K per request (docs)


def test_a_single_huge_text_still_gets_its_own_batch(script):
    assert script.plan_batches(["a", "b" * 1_000_000, "c"]) == [[0], [1], [2]]


# ---- dry run

def test_dry_run_calls_nothing_and_writes_nothing(script, tmp_path, passages, capsys):
    code, sleep = run(script, tmp_path, passages, [], client=Exploding())
    out = capsys.readouterr().out
    assert code == 0 and sleep.waits == []
    assert not (tmp_path / "vectors").exists() and not (tmp_path / "cache").exists()
    assert "dry run" in out.lower() and "--confirm" in out
    assert re.search(r"8 passages", out) and "$" in out


def test_dry_run_builds_no_client(script, tmp_path, passages, monkeypatch):
    monkeypatch.setattr(script, "make_client", lambda *a, **k: pytest.fail("no client in a dry run"))
    code, _ = run(script, tmp_path, passages, [])
    assert code == 0


# ---- the paid run (fake client)

def test_confirmed_run_writes_the_vectors_file_and_manifest(script, tmp_path, passages, capsys):
    fake = FakeVoyageClient()
    code, _ = run(script, tmp_path, passages, ["--confirm"], client=fake)
    assert code == 0
    out = tmp_path / "vectors"
    raw = (out / "voyage-law-2.f32").read_bytes()
    assert len(raw) == 8 * 1024 * 4
    mat = np.frombuffer(raw, dtype="<f4").reshape(8, 1024)
    expect = np.array([fake.vector_for(embedded_text(p)) for p in passages], dtype="<f4")
    assert np.array_equal(mat, expect)                          # rows in passage reading order
    m = json.loads((out / "manifest.json").read_text())
    assert set(m) == {"model", "dimension", "count", "created", "units"}
    assert (m["model"], m["dimension"], m["count"], m["created"]) == ("voyage-law-2", 1024, 8, "2026-10-24")
    assert m["units"] == [{"id": p.id, "sha256": hashlib.sha256(embedded_text(p).encode()).hexdigest()} for p in passages]
    text = capsys.readouterr().out
    assert "tokens" in text and "$" in text


def test_the_output_loads_back_into_a_meaning_index(script, tmp_path, passages):
    run(script, tmp_path, passages, ["--confirm"], client=FakeVoyageClient())
    idx = MeaningIndex.load(tmp_path / "vectors", passages)
    assert len(idx.passages) == 8


def test_documents_are_embedded_with_input_type_document(script, tmp_path, passages):
    fake = FakeVoyageClient()
    run(script, tmp_path, passages, ["--confirm"], client=fake)
    assert {c[2] for c in fake.calls} == {"document"}
    sent = [t for c in fake.calls for t in c[1]]
    assert sent == [embedded_text(p) for p in passages]


def test_created_date_is_a_chicago_date_by_default(script):
    from datetime import datetime
    from zoneinfo import ZoneInfo
    assert script.chicago_today() == datetime.now(ZoneInfo("America/Chicago")).date().isoformat()


# ---- cache and pacing

def test_a_rerun_pays_nothing_twice(script, tmp_path, monkeypatch, capsys):
    ps = [make_passage(i) for i in range(1, 8)]
    monkeypatch.setattr(script, "MAX_BATCH_ITEMS", 3)
    first = FakeVoyageClient()
    run(script, tmp_path, ps, ["--confirm"], client=first)
    assert len(first.calls) == 3                                  # 3 + 3 + 1
    capsys.readouterr()
    second = FakeVoyageClient()
    code, sleep = run(script, tmp_path, ps, ["--confirm"], client=second)
    assert code == 0 and second.calls == [] and sleep.waits == []
    assert "cached" in capsys.readouterr().out.lower()


def test_a_partial_cache_only_pays_for_the_missing_batches(script, tmp_path, monkeypatch):
    ps = [make_passage(i) for i in range(1, 8)]
    monkeypatch.setattr(script, "MAX_BATCH_ITEMS", 3)
    boom = ServiceError("voyage", "server_error", 500, "boom")
    failing = FakeVoyageClient(embed_failures=[None, boom])
    code, _ = run(script, tmp_path, ps, ["--confirm"], client=failing)
    assert code != 0 and len(failing.calls) == 2                  # no retry of the paid request
    assert not (tmp_path / "vectors" / "voyage-law-2.f32").exists()
    later = FakeVoyageClient()
    code, _ = run(script, tmp_path, ps, ["--confirm"], client=later)
    assert code == 0 and len(later.calls) == 2                    # the first batch came from the cache


def test_changed_text_does_not_hit_the_cache(script, tmp_path):
    a = [make_passage(1, text="one"), make_passage(2, text="two")]
    b = [make_passage(1, text="one"), make_passage(2, text="TWO")]
    run(script, tmp_path, a, ["--confirm"], client=FakeVoyageClient())
    fake = FakeVoyageClient()
    run(script, tmp_path, b, ["--confirm"], client=fake)
    assert len(fake.calls) == 1


def test_pacing_sleeps_between_requests_not_after_the_last_and_not_for_cache_hits(script, tmp_path, monkeypatch):
    ps = [make_passage(i) for i in range(1, 8)]
    monkeypatch.setattr(script, "MAX_BATCH_ITEMS", 3)
    code, sleep = run(script, tmp_path, ps, ["--confirm"], client=FakeVoyageClient())
    assert code == 0 and len(sleep.waits) == 2 and all(w >= script.MIN_SECONDS_BETWEEN_REQUESTS for w in sleep.waits)


def test_the_failure_message_names_the_kind_and_never_the_key(script, tmp_path, passages, capsys):
    fake = FakeVoyageClient(embed_failures=[ServiceError("voyage", "auth", 401, "Voyage returned HTTP 401")])
    code, _ = run(script, tmp_path, passages, ["--confirm"], client=fake)
    assert code != 0 and "auth" in capsys.readouterr().err


# ---- the key

def test_the_key_is_read_from_the_env_file_in_process(script, tmp_path):
    env = tmp_path / "x.env"
    env.write_text("# c\nOTHER=1\nexport VOYAGE_API_KEY='abc123'\n")
    assert script.read_key(env) == "abc123"


def test_a_missing_key_exits_without_calling_anything(script, tmp_path, passages, monkeypatch):
    monkeypatch.delenv("VOYAGE_API_KEY", raising=False)
    (tmp_path / "x.env").write_text("OTHER=1\n")
    with pytest.raises(SystemExit) as e:
        script.main(["--confirm", "--out", str(tmp_path / "v"), "--cache", str(tmp_path / "c")],
                    passages=passages, price_fn=price, env_path=tmp_path / "x.env", today=lambda: "2026-10-24")
    assert "VOYAGE_API_KEY" in str(e.value)


def test_the_scripts_client_gets_the_batch_timeout(script):
    from api import settings
    c = script.make_client("k")
    assert c._timeout_s == float(settings.VOYAGE_BATCH_TIMEOUT_S.value)
    assert c._timeout_s > float(settings.VOYAGE_TIMEOUT_S.value)


def test_a_fully_cached_rerun_needs_no_key_and_builds_no_client(script, tmp_path, passages, monkeypatch):
    run(script, tmp_path, passages, ["--confirm"], client=FakeVoyageClient())
    monkeypatch.delenv("VOYAGE_API_KEY", raising=False)
    monkeypatch.setattr(script, "make_client", lambda *a, **k: pytest.fail("no client when nothing is to be paid"))
    monkeypatch.setattr(script, "read_key", lambda *a, **k: pytest.fail("no key read when nothing is to be paid"))
    code, sleep = run(script, tmp_path, passages, ["--confirm"])
    assert code == 0 and sleep.waits == []
    assert (tmp_path / "vectors" / "voyage-law-2.f32").exists()
