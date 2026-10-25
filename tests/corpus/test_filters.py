"""parse_filters, matches and excluded_by_none_of (contract §4.B, T1.4)."""

import pytest

from api.corpus.filters import excluded_by_none_of, matches, parse_filters
from api.errors import ToolInputError
from api.types import Filters


def test_none_and_empty_are_unset(corpus):
    assert parse_filters(None, corpus) == Filters()
    assert parse_filters({}, corpus) == Filters()
    raw = {"cases": [], "opinion_types": [], "authors": [], "none_of": [], "decided_from": None, "decided_to": None}
    assert parse_filters(raw, corpus) == Filters()


def test_every_value_means_unset(corpus):
    f = parse_filters({"cases": sorted(corpus.case_keys), "opinion_types": ["majority", "plurality", "concurrence", "dissent"],
                       "authors": sorted({a for p in corpus.passages.values() for a in p.authors} | {"per curiam"})}, corpus)
    assert f == Filters()


def test_every_value_is_per_corpus(corpus_pre):
    # Chatrie's keys and authors are not values of the pre-Chatrie corpus
    with pytest.raises(ToolInputError):
        parse_filters({"cases": ["chatrie"]}, corpus_pre)
    with pytest.raises(ToolInputError):
        parse_filters({"authors": ["Barrett"]}, corpus_pre)


def test_values_are_normalised(corpus):
    f = parse_filters({"cases": ["Katz", " jones "], "opinion_types": ["Dissent"], "authors": ["stewart", "PER CURIAM"],
                       "none_of": ["  warrant ", '"probable cause"'], "include_footnotes": False,
                       "decided_from": 1967, "decided_to": "2001-06-11"}, corpus)
    assert f.cases == ("katz", "jones")
    assert f.opinion_types == ("dissent",)
    assert f.authors == ("Stewart", "per curiam")
    assert f.none_of == ("warrant", '"probable cause"')
    assert f.include_footnotes is False
    assert (f.decided_from, f.decided_to) == ("1967", "2001-06-11")


@pytest.mark.parametrize("raw", [
    {"cases": ["not_a_case"]},
    {"cases": "katz"},
    {"cases": [3]},
    {"decided_from": "last Tuesday"},
    {"decided_from": "1967-13-01"},
    {"decided_to": "20-01"},
    {"decided_from": "1990", "decided_to": "1980"},
    {"opinion_types": ["majority opinion"]},
    {"opinion_types": "dissent"},
    {"authors": ["Nobody"]},
    {"none_of": [""]},
    {"none_of": "x"},
    {"include_footnotes": "yes"},
    {"cases": 5},
    {"cases": {"katz": 1}},
    {"authors": "Stewart"},
    {"authors": [None]},
    {"opinion_types": 3},
    {"none_of": 3},
    {"none_of": [["a"]]},
    {"max_results": 5},
    {"all_of": ["x"]},
])
def test_bad_input_raises(raw, corpus):
    with pytest.raises(ToolInputError) as e:
        parse_filters(raw, corpus)
    assert e.value.message


def test_bad_input_messages_name_the_valid_values(corpus):
    with pytest.raises(ToolInputError) as e:
        parse_filters({"cases": ["katzz"]}, corpus)
    assert "katz" in e.value.message and "katzz" in e.value.message
    with pytest.raises(ToolInputError) as e:
        parse_filters({"opinion_types": ["x"]}, corpus)
    for g in ("majority", "plurality", "concurrence", "dissent"):
        assert g in e.value.message
    with pytest.raises(ToolInputError) as e:
        parse_filters({"decided_from": "1967-02-30"}, corpus)
    assert "YYYY" in e.value.message


def test_too_many_none_of_items(corpus):
    with pytest.raises(ToolInputError):
        parse_filters({"none_of": [f"w{i}" for i in range(11)]}, corpus)


def test_a_year_means_the_whole_year(corpus):
    katz = corpus.passages["katz-1-p1"]                     # decided 1967-12-18
    assert matches(katz, parse_filters({"decided_from": "1967", "decided_to": "1967"}, corpus))
    assert matches(katz, parse_filters({"decided_to": "1967"}, corpus))
    assert not matches(katz, parse_filters({"decided_to": "1966"}, corpus))
    assert matches(katz, parse_filters({"decided_from": "1967"}, corpus))
    assert not matches(katz, parse_filters({"decided_from": "1968"}, corpus))
    assert matches(katz, parse_filters({"decided_from": "1967-12-18", "decided_to": "1967-12-18"}, corpus))
    assert not matches(katz, parse_filters({"decided_to": "1967-12-17"}, corpus))
    assert not matches(katz, parse_filters({"decided_from": "1967-12-19"}, corpus))


def test_matches_cases_types_authors_footnotes(corpus):
    katz1 = corpus.passages["katz-1-p1"]
    fn = corpus.passages["katz-1-n1"]
    assert matches(katz1, Filters())
    assert matches(katz1, parse_filters({"cases": ["katz"]}, corpus))
    assert not matches(katz1, parse_filters({"cases": ["jones"]}, corpus))
    assert matches(katz1, parse_filters({"opinion_types": ["majority"]}, corpus))
    assert not matches(katz1, parse_filters({"opinion_types": ["dissent"]}, corpus))
    assert matches(katz1, parse_filters({"authors": ["Stewart"]}, corpus))
    assert not matches(katz1, parse_filters({"authors": ["Harlan"]}, corpus))
    assert matches(fn, Filters()) and not matches(fn, Filters(include_footnotes=False))
    assert matches(katz1, Filters(include_footnotes=False))


def test_two_group_opinion_matches_both(corpus):
    p = next(p for p in corpus.passages.values() if p.opinion_type == "concurrence in part and dissent in part")
    assert matches(p, parse_filters({"opinion_types": ["concurrence"]}, corpus))
    assert matches(p, parse_filters({"opinion_types": ["dissent"]}, corpus))
    assert not matches(p, parse_filters({"opinion_types": ["majority"]}, corpus))


def test_per_curiam_author(corpus):
    pc = corpus.passages["clinton-1-p1"]
    assert matches(pc, parse_filters({"authors": ["per curiam"]}, corpus))
    assert not matches(corpus.passages["katz-1-p1"], parse_filters({"authors": ["per curiam"]}, corpus))
    assert not matches(pc, parse_filters({"authors": ["Stewart"]}, corpus))


def test_matches_ignores_none_of(corpus):
    p = corpus.passages["katz-1-p1"]
    assert matches(p, Filters(none_of=("telephone",)))


def test_excluded_by_none_of(corpus):
    p = corpus.passages["katz-1-p1"]       # mentions "telephone booth" and "Fourth Amendment"
    assert excluded_by_none_of(p, Filters(none_of=("telephone",)))
    assert excluded_by_none_of(p, Filters(none_of=("TELEPHONE",)))
    assert excluded_by_none_of(p, Filters(none_of=('"telephone booth"',)))
    assert excluded_by_none_of(p, Filters(none_of=("telephone booth",)))
    assert not excluded_by_none_of(p, Filters(none_of=('"booth telephone"',)))
    assert not excluded_by_none_of(p, Filters(none_of=("zebra",)))
    assert not excluded_by_none_of(p, Filters())
    assert excluded_by_none_of(p, Filters(none_of=("zebra", "booth")))
    # whole words: "tele" is not "telephone"
    assert not excluded_by_none_of(p, Filters(none_of=("tele",)))


def test_none_of_unquoted_multi_word_is_all_words_quoted_is_a_phrase(corpus):
    p = corpus.passages["katz-1-p1"]       # "telephone booth" appears; "booth telephone" does not
    assert excluded_by_none_of(p, Filters(none_of=("booth telephone",)))              # both words are there
    assert not excluded_by_none_of(p, Filters(none_of=('"booth telephone"',)))        # not as a phrase
    assert excluded_by_none_of(p, Filters(none_of=('"telephone booth"',)))
    assert not excluded_by_none_of(p, Filters(none_of=("telephone zebra",)))          # one word missing
    assert excluded_by_none_of(p, Filters(none_of=("zebra", "telephone booth")))


def test_none_of_does_not_stem(corpus):
    p = next(q for q in corpus.passages.values() if " searching " in f" {q.text.lower()} " and " search " not in f" {q.text.lower()} ")
    assert not excluded_by_none_of(p, Filters(none_of=("search",)))
    assert excluded_by_none_of(p, Filters(none_of=("searching",)))
