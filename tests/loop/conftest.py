"""Part G's fixtures: the real corpus, its keyword index and the committed vectors, loaded once."""

import pytest

from api.corpus.keyword import KeywordIndex
from api.corpus.store import Corpus
from api.search.meaning import MeaningIndex
from tests.loop.support import ROOT, World


@pytest.fixture(scope="session")
def world() -> World:
    corpus = Corpus.load(ROOT)
    return World(corpus, KeywordIndex(corpus), MeaningIndex.load(ROOT / "data" / "vectors", corpus.passages.values()))


@pytest.fixture(scope="session")
def world_before_chatrie() -> World:
    corpus = Corpus.load(ROOT, exclude=("chatrie",))
    return World(corpus, KeywordIndex(corpus), MeaningIndex.load(ROOT / "data" / "vectors", corpus.passages.values()))


@pytest.fixture(autouse=True)
def no_real_waits(monkeypatch):
    """Retry waits are recorded, not slept (api/retry.py's waits, T3.3)."""
    waits: list[float] = []

    async def fake_sleep(seconds: float) -> None:
        waits.append(seconds)

    monkeypatch.setattr("api.loop.run.retry_sleep", fake_sleep)
    return waits
