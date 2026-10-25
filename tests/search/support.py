"""Helpers for part C's tests: passages built directly, a fake RunContext, a vectors folder (contract §4.C, §12)."""

import hashlib
import json
from pathlib import Path

import numpy as np

from api import settings
from api.search.meaning import embedded_text
from api.search.voyage import FakeVoyageClient
from api.types import CallOutcome, Passage, RunFlags, RunStopped, Usage


def make_passage(n: int, **over) -> Passage:
    text = over.pop("text", f"Passage number {n} says something about searches and seizures. A second sentence follows.")
    fields = dict(
        id=f"katz-1-p{n}", kind="paragraph", case_key="katz", opinion_id="katz-1", text=text,
        sentences=((0, len(text)),), case_name="Katz v. United States", citation="389 U.S. 347",
        decided="1967-12-18", slip_opinion=False, opinion_type="majority", opinion_groups=("majority",),
        authors=("Stewart",), joined_by=(), joined_by_source="printed", section=None,
        page_start=350, page_end=350, position=n, of=100, paragraph_kind="text", footnote_label=None,
    )
    fields.update(over)
    return Passage(**fields)


class FakeContext:
    """A RunContext stand-in that records every call in order and can stop the run."""

    def __init__(self, stop_on_call: int | None = None):
        self.run_id = "run-test"
        self.question = "a question that must never reach Voyage"
        self.update_check_available = True
        self.corpus_label = "full"
        self.flags = RunFlags()
        self.log: list[tuple] = []          # ("before", service, purpose) and ("usage", ...) in order
        self.usages: list[dict] = []
        self.stop_on_call = stop_on_call
        self._before_calls = 0

    async def emit(self, kind, data):
        return 0

    async def before_paid_call(self, service, purpose):
        self._before_calls += 1
        self.log.append(("before", service, purpose))
        if self.stop_on_call is not None and self._before_calls == self.stop_on_call:
            raise RunStopped("abandoned")

    async def record_usage(self, usage: Usage | None, *, purpose, attempt, max_attempts, outcome: CallOutcome,
                           error_kind, duration_ms, raw_usage=None, call_no=None):
        rec = dict(usage=usage, purpose=purpose, attempt=attempt, max_attempts=max_attempts, outcome=outcome,
                   error_kind=error_kind, duration_ms=duration_ms)
        self.usages.append(rec)
        self.log.append(("usage", purpose, attempt, outcome, error_kind))
        return 0.0

    def totals(self):
        return {}

    def seconds_left(self):
        return 100.0


def recording_sleep():
    """A sleep replacement that records the waits asked for in `.waits`."""
    waits: list[float] = []

    async def _sleep(s: float) -> None:
        waits.append(s)

    _sleep.waits = waits
    return _sleep


def write_vectors(dirpath: Path, passages, client: FakeVoyageClient | None = None, *, model=None, dimension=None,
                  tamper: dict | None = None) -> Path:
    """Writes voyage-law-2.f32 and manifest.json the way scripts/embed_corpus.py does, using the fake's vectors."""
    client = client or FakeVoyageClient()
    dirpath.mkdir(parents=True, exist_ok=True)
    texts = [embedded_text(p) for p in passages]
    mat = np.array([client.vector_for(t) for t in texts], dtype="<f4")
    (dirpath / "voyage-law-2.f32").write_bytes(mat.tobytes())
    manifest = {
        "model": model or settings.EMBED_MODEL.value,
        "dimension": dimension or settings.EMBED_DIMENSION.value,
        "count": len(passages),
        "created": "2026-10-24",
        "units": [{"id": p.id, "sha256": hashlib.sha256(t.encode("utf-8")).hexdigest()} for p, t in zip(passages, texts)],
    }
    manifest.update(tamper or {})
    (dirpath / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    return dirpath
