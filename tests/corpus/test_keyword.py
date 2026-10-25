"""KeywordIndex: FTS5 with porter and unicode61 (contract §4.B, T1.2, T1.4, T1.13)."""

import re
import sqlite3

import pytest

from api.corpus import keyword
from api.corpus.filters import excluded_by_none_of, parse_filters
from api.corpus.keyword import KeywordIndex
from api.errors import ToolInputError
from api.settings import KEYWORD_ITEMS_PER_LIST, value
from api.types import Filters


def ids(hits):
    return [h.passage_id for h in hits]


def test_fts5_check_fails_clearly(monkeypatch):
    class Conn:
        def execute(self, *a, **k):
            raise sqlite3.OperationalError("no such module: fts5")
    with pytest.raises(RuntimeError) as e:
        keyword.require_fts5(Conn())
    assert "FTS5" in str(e.value)


def test_compile_builds_quoted_phrases_and_word_groups():
    q = KeywordIndex.compile(["probable cause", '"pen register"'], ["x", "y z"], ["bad"])
    assert '("probable" AND "cause")' in q and '"pen register"' in q and '("y" AND "z")' in q
    assert " NOT " in q and '"bad"' in q
    # Claude never writes syntax: operators and punctuation are dropped into quoted tokens
    q2 = KeywordIndex.compile(["a OR b*"], [], ["NEAR(x y)"])
    assert "*" not in q2 and "NEAR(" not in q2 and '"near"' in q2 and '"or"' in q2


def test_compile_all_any_none_shapes():
    assert KeywordIndex.compile(["a", "b"], [], []) == '("a" AND "b")'
    assert KeywordIndex.compile([], ["a", "b"], []) == '(("a" OR "b"))'
    assert KeywordIndex.compile(["a"], ["b", "c"], ["d"]) == '("a" AND ("b" OR "c")) NOT ("d")'
    assert KeywordIndex.compile(["a b"], [], []) == '(("a" AND "b"))'
    assert KeywordIndex.compile(['"a b"'], [], []) == '("a b")'


@pytest.mark.parametrize("bad", ["warrant", None, 5, ["warrant", 3], ["warrant", None], [["warrant"]], {"a": 1}])
def test_bad_list_types_raise_tool_input_error(bad):
    for pos in range(3):
        args = [["x"], ["x"], ["x"]]
        args[pos] = bad
        with pytest.raises(ToolInputError):
            KeywordIndex.compile(*args)


def test_search_bad_list_types(index):
    for bad in ("warrant", None, 5, ["warrant", 3], [None]):
        with pytest.raises(ToolInputError):
            index.search(bad, [], [], Filters(), 8)
        with pytest.raises(ToolInputError):
            index.search([], bad, [], Filters(), 8)
        with pytest.raises(ToolInputError):
            index.search(["warrant"], [], bad, Filters(), 8)
    with pytest.raises(ToolInputError):
        index.search(["warrant"], [], [], Filters(none_of="telephone"), 8)       # a bare string, not a tuple of items


def test_word_forms_match(index, corpus):
    hits = index.search(["searches"], [], [], Filters(), 2462)
    assert hits
    # the stem "search" is found in passages that say "search" and "searching" but not "searches"
    texts = [corpus.passages[h.passage_id].text.lower() for h in hits]
    assert any("searching" in t and "searches" not in t for t in texts)


def test_a_quoted_item_is_a_phrase(index, corpus):
    phrase = index.search([], ['"pen register"'], [], Filters(), 2462)
    assert phrase
    for h in phrase:
        t = corpus.passages[h.passage_id].text.lower()
        assert "pen register" in t
    both = index.search(["pen", "register"], [], [], Filters(), 2462)
    assert len(both) >= len(phrase)


def test_citation_string_phrase(index, corpus):
    hits = index.search([], ['"389 U. S. 347"'], [], Filters(), 50)
    assert hits and all("389 U. S. 347" in corpus.passages[h.passage_id].text for h in hits)


def test_all_of_narrows_and_any_of_widens(index):
    a = set(ids(index.search(["warrant"], [], [], Filters(), 5000)))
    b = set(ids(index.search(["warrant", "telephone"], [], [], Filters(), 5000)))
    c = set(ids(index.search([], ["warrant", "telephone"], [], Filters(), 5000)))
    assert b < a < c


def test_none_of_excludes(index, corpus):
    base = index.search(["warrant"], [], [], Filters(), 5000)
    cut = index.search(["warrant"], [], ["telephone"], Filters(), 5000)
    assert 0 < len(cut) < len(base)
    assert all("telephone" not in corpus.passages[h.passage_id].text.lower() for h in cut)
    # filters.none_of applies too
    cut2 = index.search(["warrant"], [], [], Filters(none_of=("telephone",)), 5000)
    assert ids(cut2) == ids(cut)


def test_bm25_order_best_first_and_limit(index):
    hits = index.search([], ["warrant", "wiretap"], [], Filters(), 30)
    assert len(hits) == 30
    scores = [h.score for h in hits]
    assert scores == sorted(scores, reverse=True)
    assert all(h.reranked for h in hits)
    assert ids(index.search([], ["warrant", "wiretap"], [], Filters(), 5)) == ids(hits)[:5]
    assert index.search(["warrant"], [], [], Filters(), 0) == []


def test_search_is_deterministic(index):
    a = index.search([], ["warrant"], [], Filters(), 100)
    b = index.search([], ["warrant"], [], Filters(), 100)
    assert a == b


def test_filters_apply(index, corpus):
    f = parse_filters({"cases": ["katz"], "include_footnotes": False}, corpus)
    hits = index.search([], ["telephone"], [], f, 100)
    assert hits and all(corpus.passages[h.passage_id].case_key == "katz" and corpus.passages[h.passage_id].kind == "paragraph" for h in hits)
    f2 = parse_filters({"decided_from": "2018"}, corpus)
    hits = index.search([], ["warrant"], [], f2, 100)
    assert hits and all(corpus.passages[h.passage_id].decided >= "2018-01-01" for h in hits)
    f3 = parse_filters({"opinion_types": ["dissent"]}, corpus)
    hits = index.search([], ["warrant"], [], f3, 100)
    assert hits and all("dissent" in corpus.passages[h.passage_id].opinion_groups for h in hits)


def test_footnotes_are_searchable_alone(index, corpus):
    f = parse_filters({"cases": ["boyd"]}, corpus)
    hits = index.search([], ["Note"], [], f, 5000)
    assert any(corpus.passages[h.passage_id].kind == "footnote" for h in hits)


def test_errors(index):
    with pytest.raises(ToolInputError):
        index.search([], [], ["x"], Filters(), 8)
    with pytest.raises(ToolInputError):
        index.search([], [], [], Filters(), 8)
    cap = value(KEYWORD_ITEMS_PER_LIST)
    with pytest.raises(ToolInputError) as e:
        index.search([f"w{i}" for i in range(cap + 1)], [], [], Filters(), 8)
    assert str(cap) in e.value.message
    with pytest.raises(ToolInputError):
        index.search(["x"] * 1, [], [f"n{i}" for i in range(cap + 1)], Filters(), 8)
    index.search([f"w{i}" for i in range(cap)], [], [], Filters(), 8)       # exactly the cap is fine
    with pytest.raises(ToolInputError):
        index.search(["---"], [], [], Filters(), 8)                         # no word in the item
    with pytest.raises(ToolInputError):
        index.search([""], [], [], Filters(), 8)


def test_no_match_is_an_empty_list(index):
    assert index.search(["zzzzqqqq"], [], [], Filters(), 8) == []


def test_pre_chatrie_index_has_no_chatrie(corpus_pre):
    idx = KeywordIndex(corpus_pre)
    hits = idx.search([], ["warrant", "geofence", "location"], [], Filters(), 5000)
    assert hits and not any(h.passage_id.startswith("chatrie-") for h in hits)


# ---- unquoted multi-word items are AND groups; quoted items are phrases (T1.4)

def _text(corpus, hit):
    return corpus.passages[hit.passage_id].text.lower()


@pytest.mark.parametrize("where", ["all_of", "any_of"])
def test_unquoted_multi_word_item_means_all_words_anywhere(index, corpus, where):
    def run(item):
        a = {"all_of": [item], "any_of": []} if where == "all_of" else {"all_of": [], "any_of": [item]}
        return index.search(a["all_of"], a["any_of"], [], Filters(), 5000)
    loose, phrase = run("unreasonable searches"), run('"unreasonable searches"')
    assert phrase and len(loose) > len(phrase)
    assert {h.passage_id for h in phrase} <= {h.passage_id for h in loose}
    for h in loose:
        t = _text(corpus, h)
        assert "unreason" in t and "search" in t          # substrings: the match is on porter word forms
    assert any("unreasonable search" not in _text(corpus, h) for h in loose)
    for h in phrase:
        assert "unreason" in _text(corpus, h) and "search" in _text(corpus, h)   # a phrase of word forms


def test_unquoted_multi_word_none_of_means_all_words_present(index, corpus):
    base = {h.passage_id for h in index.search([], ["the"], [], Filters(), 5000)}
    loose = {h.passage_id for h in index.search([], ["the"], ["search warrant"], Filters(), 5000)}
    phrase = {h.passage_id for h in index.search([], ["the"], ['"search warrant"'], Filters(), 5000)}
    assert loose < phrase < base
    for pid in base - loose:
        words = set(re.findall(r"[a-z]+", corpus.passages[pid].text.lower()))
        assert {"search", "warrant"} <= words
    for pid in loose:
        words = set(re.findall(r"[a-z]+", corpus.passages[pid].text.lower()))
        assert not {"search", "warrant"} <= words


# ---- none_of is exact: no stemming, and the same through both tools (ruling 1)

NONE_OF_CASES = [
    ["search"], ["searching"], ["searches"], ['"pen register"'], ["pen register"], ["telephone", "booth"],
    ['"probable cause"', "wiretap"], ["Fourth Amendment"], ["privacy"], ['"reasonable expectation"'],
    ["warrant probable"], ["o'connor"],
]


@pytest.mark.parametrize("none_of", NONE_OF_CASES)
def test_none_of_is_the_same_through_both_tools(index, corpus, none_of):
    f = Filters(none_of=tuple(none_of))
    base = [h.passage_id for h in index.search([], ["the"], [], Filters(), 5000)]
    assert len(base) > 2000
    through_keyword = [h.passage_id for h in index.search([], ["the"], none_of, Filters(), 5000)]
    through_filter = [h.passage_id for h in index.search([], ["the"], [], f, 5000)]
    through_python = [pid for pid in base if not excluded_by_none_of(corpus.passages[pid], f)]
    assert through_keyword == through_python == through_filter
    assert len(through_python) < len(base)


def test_none_of_does_not_stem(index, corpus):
    base = {h.passage_id for h in index.search(["search"], [], [], Filters(), 5000)}    # porter: search, searching, searches
    cut = {h.passage_id for h in index.search(["search"], [], ["search"], Filters(), 5000)}
    assert cut, "passages that say 'searching' or 'searches' but not 'search' survive"
    assert base > cut
    for pid in cut:
        words = set(re.findall(r"[a-z]+", corpus.passages[pid].text.lower()))
        assert "search" not in words
    assert any(w in re.findall(r"[a-z]+", corpus.passages[pid].text.lower()) for pid in cut for w in ("searching", "searches"))


def test_combined_none_of_cap(index):
    cap = value(KEYWORD_ITEMS_PER_LIST)
    own = [f"a{i}" for i in range(cap - 2)]
    flt = Filters(none_of=tuple(f"b{i}" for i in range(5)))
    with pytest.raises(ToolInputError) as e:
        index.search(["warrant"], [], own, flt, 8)
    msg = e.value.message
    assert "none_of" in msg and str(cap) in msg and str(len(own) + 5) in msg
    assert "filters" in msg.lower() and "together" in msg.lower()
    # exactly at the cap is fine
    index.search(["warrant"], [], own, Filters(none_of=("b0", "b1")), 8)
