"""P4.6: the composition's worst-case input, recomputed from the corpus and the settings with the loop's own request
builder and estimator, fits in COMPOSITION_RESERVE_INPUT, so the figure cannot fall behind the code."""

from types import SimpleNamespace

import pytest

from api import settings
from api.corpus.store import Corpus
from api.loop import format as fmt
from api.loop.run import _Run, chars_per_token, sort_documents
from tests.loop.support import ROOT


@pytest.fixture(scope="module")
def corpus() -> Corpus:
    return Corpus.load(ROOT)


def worst_case_estimate(corpus: Corpus) -> int:
    """The KEEP_CAP largest documents, each with a keep reason of KEEP_REASON_MAX_CHARS, a question of
    QUESTION_MAX_CHARS and a scope note of NOTE_MAX_CHARS. Plain letters: a character JSON escapes (a quotation mark,
    a newline) raises the loop's estimate, not the tokens billed, so it is not part of the worst case."""
    reason = "r" * int(settings.KEEP_REASON_MAX_CHARS.value)
    run = SimpleNamespace(corpus=corpus, ctx=SimpleNamespace(question="q" * int(settings.QUESTION_MAX_CHARS.value)))
    run.ratio = chars_per_token(corpus)
    run.est = lambda text: _Run.est(run, text)
    run.est_json = lambda obj: _Run.est_json(run, obj)
    run.composition_ask = lambda note: _Run.composition_ask(run, note)
    size = {pid: run.est_json(fmt.document_block(p, reason)) for pid, p in corpus.passages.items()}
    largest = sorted(size, key=lambda pid: (-size[pid], pid))[:int(settings.KEEP_CAP.value)]
    documents = [fmt.document_block(corpus.passages[pid], reason) for pid in sort_documents(largest, corpus)]
    request = _Run.composition_request(run, documents, "n" * int(settings.NOTE_MAX_CHARS.value))
    return run.est(request["system"]) + run.est_json(request["messages"])


def test_the_composition_worst_case_fits_in_its_reserve(corpus):
    est = worst_case_estimate(corpus)
    assert est <= int(settings.COMPOSITION_RESERVE_INPUT.value), est


def test_the_reserve_keeps_only_a_small_margin(corpus):
    # P4.6: the reserve is the worst case "plus a small margin"; a reserve far above it overstates the worst case
    est = worst_case_estimate(corpus)
    assert int(settings.COMPOSITION_RESERVE_INPUT.value) - est < 5_000, est


def test_the_run_limit_is_the_loop_budget_plus_the_reserve():
    assert (int(settings.RUN_INPUT_TOKENS.value)
            == int(settings.LOOP_INPUT_BUDGET.value) + int(settings.COMPOSITION_RESERVE_INPUT.value))
