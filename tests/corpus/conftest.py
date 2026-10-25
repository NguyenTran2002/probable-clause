"""Fixtures for the corpus tests. Builder A's splitter may not exist yet: a trivial stand-in with the same
signature is registered only when the real module cannot be imported (contract §13)."""

import sys
import types
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
CORPUS_DIR = ROOT / "data" / "corpus"

try:
    import api.corpus.sentences  # noqa: F401
except ImportError:
    stand_in = types.ModuleType("api.corpus.sentences")

    def split_sentences(text: str) -> list[tuple[int, int]]:
        """Stand-in: spans split after each blank line, tiling the text."""
        spans, start = [], 0
        while start < len(text):
            cut = text.find("\n\n", start)
            end = len(text) if cut < 0 else cut + 2
            while end < len(text) and text[end].isspace():
                end += 1
            spans.append((start, end))
            start = end
        return spans or [(0, 0)]

    stand_in.split_sentences = split_sentences
    sys.modules["api.corpus.sentences"] = stand_in


@pytest.fixture(scope="session")
def corpus_dir():
    return CORPUS_DIR


@pytest.fixture(scope="session")
def corpus(corpus_dir):
    from api.corpus.store import Corpus
    return Corpus.load(corpus_dir)


@pytest.fixture(scope="session")
def corpus_pre(corpus_dir):
    from api.corpus.store import Corpus
    return Corpus.load(corpus_dir, exclude=("chatrie",))


@pytest.fixture(scope="session")
def index(corpus):
    from api.corpus.keyword import KeywordIndex
    return KeywordIndex(corpus)
