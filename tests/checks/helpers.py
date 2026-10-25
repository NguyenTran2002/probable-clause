"""Shared helpers for the answer-check tests. Paths are built from the repository root."""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = json.loads((ROOT / "data" / "corpus" / "manifest.json").read_text())


def manifest_without(*keys):
    """The manifest as the checks get it under the recording-only switch (contract §3)."""
    cases = [c for c in MANIFEST["cases"] if c["key"] not in keys]
    return {**MANIFEST, "cases": cases}


def inner_span(blocks, inner):
    """(block, start, end_block, end) of `inner` inside the single block that holds it once."""
    for i, b in enumerate(blocks):
        if b.count(inner) == 1:
            s = b.index(inner)
            return i, s, i, s + len(inner)
    raise AssertionError("inner text not found exactly once in one block")
