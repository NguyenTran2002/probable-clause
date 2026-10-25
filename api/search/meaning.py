"""Meaning search: Voyage embeddings held in memory, a brute-force dot product, a rerank (T1.1, T1.4, T3.3, T3.6).

`MeaningIndex.search` prices nothing: it hands each attempt's `Usage` to `ctx.record_usage` (the lifecycle's).
Logs hold run IDs, kinds and timings, never the query or any passage text (T3.7).
"""

import asyncio
import hashlib
import json
import logging
import time
from collections.abc import Awaitable, Callable, Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import numpy as np

from api import settings
from api.errors import ServiceError
from api.retry import VOYAGE_POLICY, with_retries
from api.search.voyage import VoyageClient
from api.types import Hit, Passage, Purpose, RunContext

log = logging.getLogger("probable_clause.meaning")

VECTORS_FILE = "voyage-law-2.f32"
MANIFEST_FILE = "manifest.json"

NOT_RERANKED_NOTE = (
    "These results are not reranked: the meaning-search reranker did not answer, so they are in order of "
    "closeness to the query only and may be less precise. Keyword search still works.")
UNAVAILABLE_NOTE = "Meaning search is unavailable for this search. Keyword search still works; use it instead."


def embedded_text(p: Passage) -> str:
    """One header line, then the text (T3.6): '<case name> (<year>), <exact type>, <authors or per curiam>[, Part <section>]'
    (an appendix label is written without "Part", contract v1.1).

    The year is the manifest's date text, never a timestamp (brief §10.7). The header is never part of the citable text.
    """
    authors = " and ".join(p.authors) if p.authors else "per curiam"
    header = f"{p.case_name} ({p.decided[:4]}), {p.opinion_type}, {authors}"
    if p.section:
        # Contract v1.1: "Part" only for numbered labels; an appendix label ("Appendix", "APPENDIX ...") stands as it is.
        header += f", {p.section}" if p.section.lower().startswith("appendix") else f", Part {p.section}"
    return f"{header}\n{p.text}"


def text_sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


@dataclass
class MeaningResult:
    hits: list[Hit]                      # every reranked candidate (up to SEMANTIC_CANDIDATES), best first; the caller tops up
    status: Literal["ok", "not_reranked", "unavailable"]
    message_for_claude: str | None       # the "not reranked" note, or the error saying keyword search still works


class MeaningIndex:
    def __init__(self, passages: list[Passage], matrix: np.ndarray):
        self.passages = passages                                   # reading order, as given to load
        self.matrix = matrix                                       # float32, unit-normalised rows, same order
        self.texts = [embedded_text(p) for p in passages]          # what Voyage embedded, and what rerank reads

    @classmethod
    def load(cls, vectors_dir: Path, passages: Iterable[Passage]) -> "MeaningIndex":
        """Reads the vectors file and manifest; raises ValueError if the model, dimension, size, count or any
        given passage's embedded-text hash disagrees. Rows of passages not given (an excluded case) are dropped (T3.6)."""
        vectors_dir = Path(vectors_dir)
        manifest = json.loads((vectors_dir / MANIFEST_FILE).read_text(encoding="utf-8"))
        raw = (vectors_dir / VECTORS_FILE).read_bytes()
        if manifest.get("model") != settings.EMBED_MODEL.value:
            raise ValueError(f"vectors manifest model {manifest.get('model')!r} is not {settings.EMBED_MODEL.value!r}")
        dim = manifest.get("dimension")
        if dim != settings.EMBED_DIMENSION.value:
            raise ValueError(f"vectors manifest dimension {dim!r} is not {settings.EMBED_DIMENSION.value}")
        units = manifest.get("units", [])
        if manifest.get("count") != len(units):
            raise ValueError(f"vectors manifest count {manifest.get('count')!r} does not match its {len(units)} units")
        if len(raw) != len(units) * int(dim) * 4:
            raise ValueError(f"vectors file size {len(raw)} bytes does not match {len(units)} rows of {dim} float32")
        rows = {u["id"]: (i, u["sha256"]) for i, u in enumerate(units)}
        matrix = np.frombuffer(raw, dtype="<f4").reshape(len(units), int(dim))
        kept: list[Passage] = []
        picks: list[int] = []
        for p in passages:
            if p.id not in rows:
                raise ValueError(f"no embedded vector for passage {p.id}")
            i, digest = rows[p.id]
            if digest != text_sha256(embedded_text(p)):
                raise ValueError(f"embedded-text hash for {p.id} differs from the vectors manifest; re-embed")
            kept.append(p)
            picks.append(i)
        chosen = matrix[picks].astype("float32", copy=True) if picks else np.zeros((0, int(dim)), dtype="float32")
        norms = np.linalg.norm(chosen, axis=1, keepdims=True)
        chosen /= np.where(norms == 0, 1.0, norms)
        return cls(kept, chosen)

    async def search(self, query: str, keep: Callable[[Passage], bool], ctx: RunContext, voyage: VoyageClient,
                     *, sleep: Callable[[float], Awaitable[None]] = asyncio.sleep) -> MeaningResult:
        """`keep` is the caller's filter (B's matches and excluded_by_none_of). `sleep` is a test seam for the retry waits."""
        if ctx.flags.voyage_unavailable:
            ctx.flags.meaning_unavailable_once = True
            return MeaningResult([], "unavailable", UNAVAILABLE_NOTE)

        rows = [i for i, p in enumerate(self.passages) if keep(p)]
        if not rows:
            return MeaningResult([], "ok", None)

        try:
            vectors, = await self._call(ctx, "embed", lambda: voyage.embed([query], "query"), sleep)
        except ServiceError as e:
            self._note_failure(ctx, e, "embed")
            ctx.flags.meaning_unavailable_once = True
            return MeaningResult([], "unavailable", UNAVAILABLE_NOTE)
        q = np.asarray(vectors[0], dtype="float32")
        if q.shape != (self.matrix.shape[1],) or not np.all(np.isfinite(q)):
            log.error("voyage embed reply unusable run=%s: wrong dimension or non-finite values", ctx.run_id)
            ctx.flags.meaning_unavailable_once = True
            return MeaningResult([], "unavailable", UNAVAILABLE_NOTE)
        norm = float(np.linalg.norm(q))
        if norm > 0:
            q = q / norm

        sub = np.asarray(rows)
        sims = self.matrix[sub] @ q
        order = np.argsort(-sims, kind="stable")[: int(settings.SEMANTIC_CANDIDATES.value)]
        cand = [int(sub[j]) for j in order]
        cand_scores = [float(sims[j]) for j in order]
        embedding_order = [Hit(self.passages[r].id, s, reranked=False) for r, s in zip(cand, cand_scores)]

        try:
            ranked, = await self._call(ctx, "rerank", lambda: voyage.rerank(query, [self.texts[r] for r in cand]), sleep)
        except ServiceError as e:
            self._note_failure(ctx, e, "rerank")
            ctx.flags.meaning_degraded = True
            return MeaningResult(embedding_order, "not_reranked", NOT_RERANKED_NOTE)

        seen: set[int] = set()
        hits: list[Hit] = []
        for idx, score in ranked:
            if not 0 <= idx < len(cand) or idx in seen:
                log.error("voyage rerank reply unusable run=%s: bad or repeated index", ctx.run_id)
                ctx.flags.meaning_degraded = True
                return MeaningResult(embedding_order, "not_reranked", NOT_RERANKED_NOTE)
            seen.add(idx)
            hits.append(Hit(self.passages[cand[idx]].id, float(score), reranked=True))
        if len(seen) < len(cand):          # a short reply: the rest follow in embedding order, marked so
            hits.extend(h for j, h in enumerate(embedding_order) if j not in seen)
            ctx.flags.meaning_degraded = True
            return MeaningResult(hits, "not_reranked", NOT_RERANKED_NOTE)
        return MeaningResult(hits, "ok", None)

    @staticmethod
    def _note_failure(ctx: RunContext, e: ServiceError, purpose: str) -> None:
        if e.kind == "auth":
            ctx.flags.voyage_unavailable = True
            log.error("voyage configuration fault run=%s purpose=%s: key refused (401); meaning search "
                      "is off for the rest of the run", ctx.run_id, purpose)
        else:
            log.warning("voyage %s failed run=%s kind=%s status=%s", purpose, ctx.run_id, e.kind, e.status)

    @staticmethod
    async def _call(ctx: RunContext, purpose: Purpose, request, sleep) -> tuple:
        """One Voyage request through our retries; every attempt is recorded (contract §4.C). Returns (result,)."""
        max_attempts = VOYAGE_POLICY.retries + 1
        state = {"attempt": 1, "ms": 0}

        async def attempt(n: int):
            state["attempt"] = n
            t0 = time.monotonic()
            try:
                result, usage = await request()
            except ServiceError:
                state["ms"] = round((time.monotonic() - t0) * 1000)
                raise
            await ctx.record_usage(usage, purpose=purpose, attempt=n, max_attempts=max_attempts, outcome="ok",
                                   error_kind=None, duration_ms=round((time.monotonic() - t0) * 1000))
            return (result,)

        async def on_retry(next_attempt: int, error: ServiceError, wait_s: float) -> None:
            await ctx.record_usage(None, purpose=purpose, attempt=next_attempt - 1, max_attempts=max_attempts,
                                   outcome="retrying", error_kind=error.kind, duration_ms=state["ms"])

        async def before(n: int) -> None:
            await ctx.before_paid_call("voyage", purpose)

        try:
            return await with_retries(attempt, VOYAGE_POLICY, before, on_retry, sleep)
        except ServiceError as e:
            await ctx.record_usage(None, purpose=purpose, attempt=state["attempt"], max_attempts=max_attempts,
                                   outcome="failed", error_kind=e.kind, duration_ms=state["ms"])
            raise
