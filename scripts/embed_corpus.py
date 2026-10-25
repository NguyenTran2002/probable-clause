"""Embed every corpus passage once with Voyage voyage-law-2 (T1.1, T3.6; contract §4.C).

    uv run python scripts/embed_corpus.py            # dry run: counts and an estimate, no network, no key read
    uv run python scripts/embed_corpus.py --confirm  # spends: the main session runs this, after approval

Output (the main session commits it beside the corpus, P1.22):
  data/vectors/voyage-law-2.f32   row-major float32, one 1,024-wide row per passage in reading order
  data/vectors/manifest.json      model, dimension, count, created (a Chicago date), units [{id, sha256}]
Each batch is cached under data/cache/voyage/ (gitignored) before the next is sent, so a rerun never pays twice.
A failed request is not retried by this script (a paid request is never retried automatically): the batches
already paid stay cached and the run stops with the error's kind.

Pacing, from Voyage's public docs (read Oct 24, 2026):
  - https://docs.voyageai.com/docs/rate-limits : Tier 1 is 3M tokens a minute and 2,000 requests a minute for
    the "voyage 1 & 2 series" row, which is the row voyage-law-2 falls under by family (the page does not name
    voyage-law-2 itself: inferred).
  - https://docs.voyageai.com/reference/embeddings-api : at most 1,000 inputs and 120K tokens per request for
    voyage-law-2; context 16K tokens per text (https://docs.voyageai.com/docs/embeddings).
The figures below keep well under those; each is marked GAP because the contract gives no pacing figure.

The key is read in-process (the environment, else .env) and never printed.
"""

import argparse
import asyncio
import hashlib
import json
import math
import os
import sys
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from api import settings  # noqa: E402
from api.errors import ServiceError  # noqa: E402
from api.search.meaning import embedded_text, text_sha256  # noqa: E402
from api.search.voyage import HttpVoyageClient  # noqa: E402
from api.types import Usage  # noqa: E402

DEFAULT_OUT = ROOT / "data" / "vectors"
DEFAULT_CACHE = ROOT / "data" / "cache" / "voyage"
VECTORS_NAME = "voyage-law-2.f32"

# GAP: inputs per request. Basis: Voyage allows 1,000; a small batch wastes little when one request fails and is
# never retried automatically.
MAX_BATCH_ITEMS = 64
# GAP: estimated tokens per request. Basis: Voyage's limit is 120K per request for voyage-law-2; this is under half.
MAX_BATCH_EST_TOKENS = 50_000
# GAP: characters per token for the estimate used in batching, pacing and the dry run. Basis: placeholder until
# measured; 3 over-counts for English legal prose, which keeps the estimate on the safe side.
CHARS_PER_TOKEN = 3
# GAP: target tokens a minute. Basis: half of the Tier 1 limit of 3M (docs.voyageai.com/docs/rate-limits).
TARGET_TOKENS_PER_MINUTE = 1_500_000
# GAP: the shortest gap between paid requests. Basis: 60 requests a minute, far under the Tier 1 limit of 2,000.
MIN_SECONDS_BETWEEN_REQUESTS = 1.0


def estimate_tokens(text: str) -> int:
    return max(1, math.ceil(len(text) / CHARS_PER_TOKEN))


def plan_batches(texts: list[str]) -> list[list[int]]:
    """Consecutive index groups: at most MAX_BATCH_ITEMS each and MAX_BATCH_EST_TOKENS estimated (a lone huge text alone)."""
    batches: list[list[int]] = []
    current: list[int] = []
    tokens = 0
    for i, text in enumerate(texts):
        t = estimate_tokens(text)
        if current and (len(current) >= MAX_BATCH_ITEMS or tokens + t > MAX_BATCH_EST_TOKENS):
            batches.append(current)
            current, tokens = [], 0
        current.append(i)
        tokens += t
    if current:
        batches.append(current)
    return batches


def batch_key(texts: list[str]) -> str:
    h = hashlib.sha256()
    h.update(f"{settings.EMBED_MODEL.value}|document|".encode())
    for t in texts:
        h.update(text_sha256(t).encode())
    return h.hexdigest()[:40]


def chicago_today() -> str:
    return datetime.now(ZoneInfo(str(settings.TIME_ZONE.value))).date().isoformat()


def read_key(env_path: Path) -> str:
    """VOYAGE_API_KEY from an env file, in-process (pattern of scripts/probe_common.py)."""
    if env_path.exists():
        for raw in env_path.read_text(encoding="utf-8").splitlines():
            line = raw.strip().removeprefix("export ")
            if line.startswith("VOYAGE_API_KEY="):
                value = line.split("=", 1)[1].strip().strip("'\"")
                if value:
                    return value
    sys.exit("VOYAGE_API_KEY not found in the environment or .env (run scripts/check_env.py)")


def make_client(api_key: str) -> HttpVoyageClient:
    # A batch is never retried, so the timeout must not cut off one that was already billed (placeholder in settings).
    return HttpVoyageClient(api_key=api_key, timeout_s=float(settings.VOYAGE_BATCH_TIMEOUT_S.value))


def _read_cache(path: Path, count: int, dim: int) -> tuple[list[list[float]], int] | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        vectors, tokens = data["embeddings"], int(data["tokens"])
    except (OSError, ValueError, KeyError, TypeError):
        return None
    if len(vectors) != count or any(len(v) != dim for v in vectors):
        return None
    return vectors, tokens


def _write_atomic(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_bytes(data)
    os.replace(tmp, path)


def _plan(texts: list[str], cache_dir: Path, dim: int):
    """Each batch with its cache path and whatever the cache already holds."""
    plan = []
    for idx in plan_batches(texts):
        batch = [texts[i] for i in idx]
        path = cache_dir / f"{batch_key(batch)}.json"
        plan.append((idx, batch, path, _read_cache(path, len(batch), dim)))
    return plan


async def embed_all(texts: list[str], client, cache_dir: Path, dim: int, sleep) -> tuple[list[list[float]], int, int]:
    """Returns (vectors in order, tokens total, tokens paid this run). Cached batches cost nothing and are not paced."""
    vectors: list[list[float]] = [[] for _ in texts]
    total = paid = 0
    paid_before = False
    plan = _plan(texts, cache_dir, dim)
    for n, (idx, batch, path, cached) in enumerate(plan, 1):
        if cached is not None:
            got, tokens = cached
            print(f"batch {n}/{len(plan)}: cached ({tokens} tokens already paid)")
        else:
            if paid_before:
                est = sum(estimate_tokens(t) for t in batch)
                await sleep(max(MIN_SECONDS_BETWEEN_REQUESTS, est / TARGET_TOKENS_PER_MINUTE * 60))
            got, usage = await client.embed(batch, "document")      # no retry: a paid request is never retried
            paid_before = True
            tokens = usage.input_tokens
            _write_atomic(path, json.dumps({"model": settings.EMBED_MODEL.value, "tokens": tokens,
                                            "embeddings": got}).encode())
            paid += tokens
            print(f"batch {n}/{len(plan)}: {len(batch)} passages, {tokens} tokens")
        total += tokens
        for i, v in zip(idx, got):
            vectors[i] = v
    return vectors, total, paid


def write_output(out_dir: Path, passages, texts: list[str], vectors: list[list[float]], created: str) -> None:
    import numpy as np

    dim = int(settings.EMBED_DIMENSION.value)
    mat = np.asarray(vectors, dtype="<f4")
    if mat.shape != (len(passages), dim):
        raise ValueError(f"vectors have shape {mat.shape}, expected {(len(passages), dim)}")
    manifest = {
        "model": settings.EMBED_MODEL.value, "dimension": dim, "count": len(passages), "created": created,
        "units": [{"id": p.id, "sha256": text_sha256(t)} for p, t in zip(passages, texts)],
    }
    _write_atomic(out_dir / VECTORS_NAME, mat.tobytes())
    _write_atomic(out_dir / "manifest.json", (json.dumps(manifest, indent=1) + "\n").encode())


def _cost(price_fn: Callable[[Usage], float], tokens: int) -> float:
    return price_fn(Usage(service="voyage", model=str(settings.EMBED_MODEL.value), input_tokens=tokens))


def main(argv=None, *, passages=None, price_fn=None, client=None, sleep=None, today=None, env_path=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--confirm", action="store_true", help="spend: call Voyage (without it, a dry run with no network)")
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--cache", type=Path, default=DEFAULT_CACHE)
    args = ap.parse_args(argv)

    if passages is None:       # the one passage reader is builder B's (contract §4.C, ruling for Wave 1)
        from api.corpus.store import Corpus
        passages = list(Corpus.load(ROOT / "data" / "corpus").passages.values())
    if price_fn is None:       # the one price table is builder E's
        from api.state.prices import price as price_fn
    passages = list(passages)
    texts = [embedded_text(p) for p in passages]
    dim = int(settings.EMBED_DIMENSION.value)
    plan = _plan(texts, args.cache, dim)
    to_pay = [b for b in plan if b[3] is None]
    est_new = sum(estimate_tokens(t) for _, batch, _, _ in to_pay for t in batch)

    print(f"{len(passages)} passages in {len(plan)} batches; {len(plan) - len(to_pay)} already cached")
    if not args.confirm:
        print(f"dry run: no network, no key read. Estimated tokens still to pay for: about {est_new:,} "
              f"({CHARS_PER_TOKEN} characters a token, an over-estimate); at list price about "
              f"${_cost(price_fn, est_new):.4f}.")
        print("Run again with --confirm to spend.")
        return 0

    voy = client
    if voy is None and to_pay:       # a fully cached rerun needs no key and no client
        key = os.environ.get("VOYAGE_API_KEY") or read_key(env_path or ROOT / ".env")
        voy = make_client(key)
    try:
        vectors, total, paid = asyncio.run(embed_all(texts, voy, args.cache, dim, sleep or asyncio.sleep))
    except ServiceError as e:
        print(f"embedding stopped: voyage {e.kind} (status {e.status}); batches already paid are cached, "
              "nothing is retried automatically.", file=sys.stderr)
        return 1
    write_output(args.out, passages, texts, vectors, (today or chicago_today)())
    print(f"voyage-law-2 tokens: {total:,} total, {paid:,} paid in this run, {total - paid:,} from the cache")
    print(f"cost at list price: ${_cost(price_fn, paid):.4f} this run, ${_cost(price_fn, total):.4f} for the whole file")
    print(f"wrote {args.out / VECTORS_NAME} and manifest.json ({len(passages)} rows)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
