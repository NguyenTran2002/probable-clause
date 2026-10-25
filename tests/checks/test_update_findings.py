"""check_update_findings (T2.3 item 2) and the copy guard (T2.3 item 3, P4.3).

Every returned message is written to Claude and stored in events, so none quotes a
page's words (contract §4.F). The leak tests use page text that would be easy to leak.
"""

import re

import pytest

from api.checks import CopyGuardReport, check_update_findings, copy_guard, copy_guard_report, corpus_words
from api.settings import (COPY_GUARD_WORDS, UPDATE_FINDINGS_MAX, UPDATE_OVERVIEW_MAX_CHARS,
                          UPDATE_SOURCES_PER_STATEMENT, UPDATE_STATEMENT_MAX_CHARS)

RETURNED = {"web-1-1", "web-1-2", "web-2-1"}


def finding(statement="A court of appeals discussed the ruling.", sources=("web-1-1",)):
    return {"statement": statement, "sources": list(sources)}


# --- check_update_findings

def test_a_valid_set_has_no_problems():
    assert check_update_findings([finding(), finding(sources=["web-1-2", "web-2-1"])], "An overview.", RETURNED, 2) == []


def test_empty_findings_and_no_overview_are_fine_with_a_search_run():
    assert check_update_findings([], None, RETURNED, 1) == []


def test_empty_findings_are_fine_when_no_search_ran():
    # An empty list means nothing was found; there is nothing to refuse (the outcome is worked out by code).
    assert check_update_findings([], None, set(), 0) == []


def test_findings_with_no_search_run_are_refused():
    problems = check_update_findings([finding()], None, set(), 0)
    assert len(problems) >= 1
    assert any("no update search" in p for p in problems)


def test_overview_with_no_search_run_is_refused():
    problems = check_update_findings([], "A synthesis of nothing.", set(), 0)
    assert len(problems) == 1 and "update_overview" in problems[0]


def test_unknown_source_id_is_named_with_its_statement():
    problems = check_update_findings([finding(), finding(sources=["web-1-1", "web-9-9"])], None, RETURNED, 1)
    assert len(problems) == 1
    assert "Statement 2" in problems[0] and "web-9-9" in problems[0]


def test_each_unknown_id_in_each_statement_is_named():
    problems = check_update_findings([finding(sources=["web-8-1"]), finding(sources=["web-9-9", "web-7-7"])], None, RETURNED, 1)
    text = " ".join(problems)
    assert "Statement 1" in text and "Statement 2" in text
    assert all(i in text for i in ("web-8-1", "web-9-9", "web-7-7"))


def test_statement_with_no_source_is_refused():
    problems = check_update_findings([finding(sources=[])], None, RETURNED, 1)
    assert len(problems) == 1 and "Statement 1" in problems[0] and "no source" in problems[0]


def test_statement_with_missing_sources_key_is_refused():
    problems = check_update_findings([{"statement": "A claim."}], None, RETURNED, 1)
    assert len(problems) == 1 and "Statement 1" in problems[0] and "no source" in problems[0]


def test_statement_with_no_text_is_refused():
    problems = check_update_findings([{"statement": "  ", "sources": ["web-1-1"]}, {"sources": ["web-1-1"]}], None, RETURNED, 1)
    assert len(problems) == 2
    assert "Statement 1" in problems[0] and "Statement 2" in problems[1]


def test_malformed_entries_are_problems_not_exceptions():
    problems = check_update_findings(["just a string", {"statement": 5, "sources": "web-1-1"},
                                      {"statement": "ok", "sources": [3]}], None, RETURNED, 1)
    assert len(problems) >= 3
    assert all(isinstance(p, str) for p in problems)


def test_findings_cap():
    n = UPDATE_FINDINGS_MAX.value + 1
    problems = check_update_findings([finding() for _ in range(n)], None, RETURNED, 1)
    assert len(problems) == 1
    assert str(n) in problems[0] and str(UPDATE_FINDINGS_MAX.value) in problems[0]


def test_findings_at_the_cap_are_fine():
    assert check_update_findings([finding() for _ in range(UPDATE_FINDINGS_MAX.value)], None, RETURNED, 1) == []


def test_statement_length_cap():
    cap = UPDATE_STATEMENT_MAX_CHARS.value
    assert check_update_findings([finding("x" * cap)], None, RETURNED, 1) == []
    problems = check_update_findings([finding("x" * (cap + 1))], None, RETURNED, 1)
    assert len(problems) == 1 and "Statement 1" in problems[0] and str(cap) in problems[0]


def test_sources_per_statement_cap():
    cap = UPDATE_SOURCES_PER_STATEMENT.value
    ids = {f"web-1-{i}" for i in range(1, cap + 2)}
    assert check_update_findings([finding(sources=[f"web-1-{i}" for i in range(1, cap + 1)])], None, ids, 1) == []
    problems = check_update_findings([finding(sources=[f"web-1-{i}" for i in range(1, cap + 2)])], None, ids, 1)
    assert len(problems) == 1 and "Statement 1" in problems[0] and str(cap) in problems[0]


def test_overview_length_cap():
    cap = UPDATE_OVERVIEW_MAX_CHARS.value
    assert check_update_findings([], "y" * cap, RETURNED, 1) == []
    problems = check_update_findings([], "y" * (cap + 1), RETURNED, 1)
    assert len(problems) == 1 and "update_overview" in problems[0] and str(cap) in problems[0]


def test_problems_come_in_a_stable_order():
    problems = check_update_findings([finding(sources=["web-9-9"]), finding(sources=[])], "z" * 700, RETURNED, 1)
    assert [p.split(" ")[0] for p in problems][:2] == ["Statement", "Statement"]
    assert "Statement 1" in problems[0] and "Statement 2" in problems[1] and "update_overview" in problems[2]


def test_a_bad_source_id_is_not_echoed_when_it_is_not_an_id():
    leaked = "Police departments across the country have begun using drones to photograph yards"
    problems = check_update_findings([finding(sources=[leaked])], None, RETURNED, 1)
    assert len(problems) == 1
    assert "Statement 1" in problems[0]
    assert "Police departments" not in problems[0]


# --- the copy guard

PAGE_A = ("Police departments across the country have begun using drones to photograph backyards, "
          "and a federal appeals court said on Tuesday that the practice needs a warrant in most cases.")
PAGE_B = "An unrelated article about tax policy, municipal bonds, and the quarterly report of a regional utility."
PAGES = {"web-1-1": PAGE_A, "web-1-2": PAGE_B}

COPIED = "Police departments across the country have begun using drones to photograph backyards"  # 12 words


def test_copy_guard_words_from_settings():
    assert COPY_GUARD_WORDS.value == 10


def test_a_paraphrase_passes():
    r = copy_guard_report(["Some police agencies now photograph yards from drones, a court reported."], None, PAGES, 10)
    assert r.problems == [] and r.flagged_statements == set() and r.overview_flagged is False


def test_ten_consecutive_words_trip_the_guard():
    r = copy_guard_report([COPIED], None, PAGES, 10)
    assert r.flagged_statements == {0}
    assert len(r.problems) == 1
    assert "Statement 1" in r.problems[0] and "web-1-1" in r.problems[0] and "web-1-2" not in r.problems[0]


def test_nine_consecutive_words_do_not():
    nine = "Police departments across the country have begun using drones"
    assert len(nine.split()) == 9
    assert copy_guard_report([nine], None, PAGES, 10).problems == []
    assert copy_guard_report([nine], None, PAGES, 9).flagged_statements == {0}


def test_the_run_can_be_inside_a_longer_statement():
    s = "According to one report, " + COPIED + ", though it is unclear what follows."
    assert copy_guard_report([s], None, PAGES, 10).flagged_statements == {0}


def test_case_punctuation_and_spacing_are_ignored():
    s = "POLICE   departments, across the country -- have begun using DRONES to\nphotograph (backyards)."
    assert copy_guard_report([s], None, PAGES, 10).flagged_statements == {0}


def test_apostrophes_and_hyphens_do_not_hide_a_copy():
    page = {"web-3-1": "The court's decision on state-of-the-art thermal imaging devices was a close call for the panel."}
    s = "The courts decision on state of the art thermal imaging devices was a close call for the panel"
    assert copy_guard_report([s], None, page, 10).flagged_statements == {0}


def test_statements_are_numbered_from_one_and_flagged_by_index():
    r = copy_guard_report(["A fresh paraphrase of nothing in particular.", COPIED, "Another clean one."], None, PAGES, 10)
    assert r.flagged_statements == {1}
    assert "Statement 2" in r.problems[0]


def test_the_overview_has_its_own_name_and_flag():
    r = copy_guard_report(["clean statement"], COPIED, PAGES, 10)
    assert r.flagged_statements == set() and r.overview_flagged is True
    assert len(r.problems) == 1 and r.problems[0].startswith("The overview") and "web-1-1" in r.problems[0]


def test_statement_and_overview_both_flagged():
    r = copy_guard_report([COPIED], COPIED, PAGES, 10)
    assert r.flagged_statements == {0} and r.overview_flagged is True
    assert len(r.problems) == 2


def test_every_page_a_text_copies_is_named():
    pages = {"web-1-1": PAGE_A, "web-2-4": "Intro. " + COPIED + " and more words follow here.", "web-1-2": PAGE_B}
    [p] = copy_guard_report([COPIED], None, pages, 10).problems
    assert "web-1-1" in p and "web-2-4" in p and "web-1-2" not in p


def test_a_court_quotation_found_in_an_article_trips_it():
    quote = "the Fourth Amendment protects people not places and what a person knowingly exposes to the public"
    page = {"web-1-1": "Writing in 1967 the Court said that " + quote + " is not a subject of protection."}
    assert copy_guard_report(["The justices said " + quote + "."], None, page, 10).flagged_statements == {0}


def test_no_message_quotes_a_page_or_a_statement():
    r = copy_guard_report([COPIED + " and a leaked tail of words"], COPIED, PAGES, 10)
    assert len(r.problems) == 2
    for p in r.problems:
        for word_run in re.findall(r"\w+(?: \w+){2}", PAGE_A + " " + COPIED):
            assert word_run.lower() not in p.lower(), word_run
        assert "photograph" not in p and "drones" not in p and "backyards" not in p


def test_messages_are_only_numbers_and_ids():
    [p] = copy_guard_report([COPIED], None, PAGES, 10).problems
    stripped = re.sub(r"web-\d+-\d+", "", p)
    assert "drones" not in stripped
    # the message is short plain instruction text
    assert len(p) < 300


def test_nothing_to_check_cases():
    assert copy_guard_report([], None, PAGES, 10).problems == []
    assert copy_guard_report([COPIED], None, {}, 10).problems == []
    assert copy_guard_report(["", "short"], "", PAGES, 10).problems == []


def test_n_words_below_one_is_refused():
    with pytest.raises(ValueError):
        copy_guard_report([COPIED], None, PAGES, 0)


def test_report_type():
    assert isinstance(copy_guard_report([], None, {}, 10), CopyGuardReport)


# --- P4.8: the note of a no-sources reply

def test_the_note_is_flagged_and_names_the_page_only():
    r = copy_guard_report([], None, PAGES, 10, note="I could not find this. " + COPIED + ".")
    assert r.note_flagged is True and r.note_pages == ["web-1-1"]
    assert r.flagged_statements == set() and r.overview_flagged is False
    [p] = r.problems
    assert p.startswith("The note") and "web-1-1" in p
    assert "drones" not in p and "photograph" not in p


def test_a_reworded_note_passes():
    r = copy_guard_report([], None, PAGES, 10, note="The corpus does not cover drone photography of yards.")
    assert r.note_flagged is False and r.note_pages == [] and r.problems == []


def test_no_note_given_means_no_note_check():
    r = copy_guard_report([COPIED], None, PAGES, 10)
    assert r.note_flagged is False and len(r.problems) == 1


def test_note_and_statements_are_reported_together():
    r = copy_guard_report([COPIED], None, PAGES, 10, note=COPIED)
    assert r.flagged_statements == {0} and r.note_flagged is True and len(r.problems) == 2


# --- P4.9: a run of words that is also the corpus's is not a copy of the page

KATZ = "the Fourth Amendment protects people not places and what a person knowingly exposes to the public"


def test_a_court_quotation_a_page_also_quotes_is_exempt():
    page = {"web-1-1": "Writing in 1967 the Court said that " + KATZ + " is not a subject of protection."}
    exempt = corpus_words(["For " + KATZ.replace("people not", "people, not") + ", even in his own home or office."])
    r = copy_guard_report(["The justices said " + KATZ + "."], None, page, 10, exempt=exempt)
    assert r.problems == [] and r.flagged_statements == set()


def test_the_exemption_covers_the_overview_and_the_note_too():
    page = {"web-1-1": "Writing in 1967 the Court said that " + KATZ + " is not a subject of protection."}
    exempt = corpus_words([KATZ])
    r = copy_guard_report([], "As the Court put it, " + KATZ + ".", page, 10, note=KATZ, exempt=exempt)
    assert r.problems == [] and r.overview_flagged is False and r.note_flagged is False


def test_the_page_s_own_words_around_a_court_quotation_still_trip_it():
    # the quotation is exempt; the run that carries on into the page's own words is not
    tail = "is not a subject of protection according to this analysis"
    page = {"web-1-1": "Writing in 1967 the Court said that " + KATZ + " " + tail + "."}
    exempt = corpus_words([KATZ])
    r = copy_guard_report(["Quoting: " + KATZ + " " + tail], None, page, 10, exempt=exempt)
    assert r.flagged_statements == {0}


def test_the_page_s_own_words_alone_still_trip_it_with_the_corpus_exempt():
    exempt = corpus_words([KATZ, "An unrelated passage of the corpus about warrants and probable cause."])
    assert copy_guard_report([COPIED], None, PAGES, 10, exempt=exempt).flagged_statements == {0}


def test_a_run_split_across_two_corpus_texts_is_not_exempt():
    words = KATZ.split()
    exempt = corpus_words([" ".join(words[:8]), " ".join(words[8:])])
    page = {"web-1-1": "Writing in 1967 the Court said that " + KATZ + " is not a subject of protection."}
    assert copy_guard_report([KATZ], None, page, 10, exempt=exempt).flagged_statements == {0}


def test_the_exemption_is_normalised_as_the_page_is():
    page = {"web-1-1": "The COURT'S words: " + KATZ.upper() + "!"}
    exempt = corpus_words(["the court’s words, " + KATZ.replace("people not", "people—not")])
    assert copy_guard_report(["The courts words " + KATZ], None, page, 10, exempt=exempt).problems == []


def test_a_sentence_of_the_real_corpus_is_exempt():
    from api.corpus.store import Corpus
    from tests.loop.support import ROOT
    corpus = Corpus.load(ROOT)
    exempt = corpus_words(p.text for p in corpus.passages.values())
    p = next(p for p in corpus.passages.values() if len(p.text.split()) > 40)
    quote = " ".join(p.text.split()[5:25])
    page = {"web-1-1": "An article quoting the Court: " + quote + ". More of the article's own words here."}
    assert copy_guard_report([quote], None, page, 10).flagged_statements == {0}           # without the exemption
    assert copy_guard_report([quote], None, page, 10, exempt=exempt).problems == []         # with it


# --- the binding signature: copy_guard(texts, page_texts, n_words) -> list[str]

def test_binding_copy_guard_returns_problem_strings():
    problems = copy_guard([COPIED], [PAGE_A, PAGE_B], 10)
    assert len(problems) == 1 and isinstance(problems[0], str)
    assert "Statement 1" in problems[0]


def test_binding_copy_guard_passes_a_paraphrase():
    assert copy_guard(["A brief unrelated remark."], [PAGE_A, PAGE_B], 10) == []


def test_binding_copy_guard_does_not_quote_pages():
    [p] = copy_guard([COPIED], [PAGE_A], 10)
    assert "drones" not in p and "photograph" not in p


# --- nothing from a page or a statement is ever written into a message

LEAKY_PAGE = ("Quokka marmalade festival organisers confirmed that the zeppelin ordinance was repealed after "
              "the mayor's pomegranate speech, according to the harbour gazette of Port Winterbourne.")
LEAKY_WORDS = ["quokka", "marmalade", "festival", "zeppelin", "ordinance", "pomegranate", "harbour", "gazette",
               "winterbourne", "organisers", "repealed"]


def test_no_page_word_appears_in_any_message():
    statement = "Quokka marmalade festival organisers confirmed that the zeppelin ordinance was repealed after the mayor's pomegranate"
    r = copy_guard_report([statement], statement, {"web-4-2": LEAKY_PAGE}, 10)
    assert len(r.problems) == 2
    for p in r.problems:
        assert not any(w in p.lower() for w in LEAKY_WORDS), p
    for p in copy_guard([statement], [LEAKY_PAGE], 10):
        assert not any(w in p.lower() for w in LEAKY_WORDS), p


def test_findings_problems_never_echo_statement_text():
    secret = "Quokka marmalade festival organisers confirmed zeppelin"
    problems = check_update_findings([{"statement": secret * 40, "sources": [secret]},
                                      {"statement": secret, "sources": []}], secret * 40, RETURNED, 1)
    assert problems
    for p in problems:
        assert not any(w in p.lower() for w in LEAKY_WORDS), p


# --- the shapes copy_guard_report tolerates

def test_pages_given_as_a_list_are_named_by_position():
    r = copy_guard_report([COPIED], None, [PAGE_B, PAGE_A], 10)
    assert r.flagged_statements == {0} and "#2" in r.problems[0]


def test_a_missing_page_text_or_statement_is_skipped():
    r = copy_guard_report([None, COPIED], None, {"web-1-1": None, "web-1-2": PAGE_A}, 10)
    assert r.flagged_statements == {1} and "web-1-2" in r.problems[0]


# --- review round: bad shapes are problems, never exceptions

def test_a_non_string_overview_is_a_problem_not_an_exception():
    for bad in (5, ["a"], {"x": 1}):
        problems = check_update_findings([finding()], bad, RETURNED, 1)
        assert len(problems) == 1 and "update_overview" in problems[0], bad
        problems = check_update_findings([], bad, set(), 0)
        assert any("update_overview" in p for p in problems) and all(isinstance(p, str) for p in problems)


def test_findings_that_are_not_a_list_are_a_problem():
    for bad in ("a string", {"statement": "x", "sources": ["web-1-1"]}, 3):
        problems = check_update_findings(bad, None, RETURNED, 1)
        assert len(problems) == 1 and "update_findings" in problems[0], bad


def test_source_id_shape_is_ascii_only():
    arabic = "web-١-٢"      # Arabic-indic digits: \d would match them
    problems = check_update_findings([finding(sources=[arabic])], None, RETURNED, 1)
    assert len(problems) == 1 and arabic not in problems[0]


# --- invisible and compatibility characters do not hide a copy (the final review, Oct 25, 2026)

@pytest.mark.parametrize("dirty", [
    "Police departments across the coun\u00adtry have begun using drones to photograph backyards",   # soft hyphen
    "Police departments across the coun\u200btry have begun using drones to photograph backyards",   # zero-width space
    "Police departments across the coun\u2060try have begun using drones to photograph backyards",   # word joiner
    "Police departments across the coun\ufefftry have begun using drones to photograph backyards",   # BOM
    "Police departments across the \uff43ountry have begun using drones to photograph backyards",    # full-width c
])
def test_invisible_characters_in_the_page_do_not_hide_a_copy(dirty):
    # the odd character sits in the fifth word, so without the fix neither side keeps ten words in a row
    clean = "Police departments across the country have begun using drones to photograph backyards."
    assert copy_guard_report([clean], None, {"web-1-1": dirty}, 10).flagged_statements == {0}
    assert copy_guard_report([dirty], None, {"web-1-1": clean}, 10).flagged_statements == {0}


def test_a_ligature_in_the_page_does_not_hide_a_copy():
    page = {"web-1-1": "The of\ufb01cers \ufb01led a warrant application \ufb01rst and the judge signed it that very afternoon."}
    s = "The officers filed a warrant application first and the judge signed it that very afternoon"
    assert copy_guard_report([s], None, page, 10).flagged_statements == {0}


def test_the_exemption_is_normalised_the_same_way():
    page = {"web-1-1": "Writing in 1967 the Court said that " + KATZ + " is not a subject of protection."}
    exempt = corpus_words([KATZ.replace("protects", "pro\u00adtects")])
    assert copy_guard_report([KATZ], None, page, 10, exempt=exempt).problems == []


@pytest.mark.parametrize("sep", ["​", "‎", "‏", "⁠", "‍"])
def test_an_invisible_character_between_words_does_not_hide_a_copy_either(sep):
    # read both ways: an invisible character inside a word joins it, one standing for a space splits it
    clean = "Police departments across the country have begun using drones to photograph backyards."
    dirty = clean.replace(" ", sep)
    assert copy_guard_report([clean], None, {"web-1-1": dirty}, 10).flagged_statements == {0}
    assert copy_guard_report([dirty], None, {"web-1-1": clean}, 10).flagged_statements == {0}


# --- P4.13: the update skip reason

def test_the_skip_reason_is_flagged_and_names_the_page_only():
    r = copy_guard_report([], None, PAGES, 10, skip_reason="Not needed. " + COPIED + ".")
    assert r.skip_reason_flagged is True and r.skip_reason_pages == ["web-1-1"]
    assert r.flagged_statements == set() and r.overview_flagged is False and r.note_flagged is False
    [p] = r.problems
    assert p.startswith("The update skip reason") and "web-1-1" in p
    assert "drones" not in p and "photograph" not in p


def test_a_reworded_skip_reason_passes():
    r = copy_guard_report([], None, PAGES, 10, skip_reason="A newer ruling could not change what Katz held.")
    assert r.skip_reason_flagged is False and r.skip_reason_pages == [] and r.problems == []


def test_no_skip_reason_given_means_no_skip_reason_check():
    for given in (None, ""):
        r = copy_guard_report([COPIED], None, PAGES, 10, skip_reason=given)
        assert r.skip_reason_flagged is False and len(r.problems) == 1


def test_skip_reason_note_and_statements_are_reported_together():
    r = copy_guard_report([COPIED], COPIED, PAGES, 10, note=COPIED, skip_reason=COPIED)
    assert r.flagged_statements == {0} and r.overview_flagged and r.note_flagged and r.skip_reason_flagged
    assert [p.split(" repeats")[0] for p in r.problems] == ["Statement 1", "The overview", "The note",
                                                            "The update skip reason"]


def test_the_exemption_covers_the_skip_reason_too():
    page = {"web-1-1": "Writing in 1967 the Court said that " + KATZ + " is not a subject of protection."}
    r = copy_guard_report([], None, page, 10, skip_reason=KATZ, exempt=corpus_words([KATZ]))
    assert r.problems == [] and r.skip_reason_flagged is False
    assert copy_guard_report([], None, page, 10, skip_reason=KATZ).skip_reason_flagged is True
