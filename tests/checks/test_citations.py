"""The full-citation check (T1.12, P1.10): full "X v. Y" names and U.S. Reports citations.

One that does not resolve to the manifest is "not in this corpus", never "does not
exist". Short names are not checked, and the check says so.
"""

import pytest

from api.checks import check_answer
from tests.checks.helpers import MANIFEST, manifest_without


def check(answer, manifest=MANIFEST):
    blocks = answer if isinstance(answer, list) else [answer]
    return check_answer(blocks, [], manifest)


def flagged(r):
    return [f.text for f in r.flags if f.kind == "not_in_corpus"]


# --- U.S. Reports citations

@pytest.mark.parametrize("cite", ["389 U. S. 347", "389 U.S. 347", "389 U.S. 347,", "389  U. S.  347", "389 U.S. 347)"])
def test_reporter_citation_resolves_however_spaced(cite):
    r = check(f"The test comes from {cite} and stays.")
    assert (r.citations_checked, r.citations_found) == (1, 1), cite
    assert r.flags == [] and r.not_in_corpus == []


def test_pin_cite_resolves_on_volume_and_first_page():
    r = check("See 389 U. S. 347, 351 (1967); also 388 U.S. 41, 55.")
    assert (r.citations_checked, r.citations_found) == (2, 2)


def test_unresolved_reporter_citation_is_flagged_as_written():
    answer = "The rule appears at 389 U. S. 999, 1001 in the reports."
    r = check(answer)
    assert (r.citations_checked, r.citations_found) == (1, 0)
    assert r.not_in_corpus == ["389 U. S. 999"]
    [f] = r.flags
    assert f.kind == "not_in_corpus" and f.text == "389 U. S. 999"
    assert (f.block, f.end_block) == (0, 0)
    assert answer[f.start:f.end] == "389 U. S. 999"


def test_right_page_wrong_volume_is_not_found():
    r = check("It is at 390 U.S. 347 in the reports.")
    assert r.citations_found == 0 and r.not_in_corpus == ["390 U.S. 347"]


def test_other_reporters_are_not_checked():
    r = check("See 95 Eng. Rep. 807 and 88 S. Ct. 507 and 19 L. Ed. 2d 576.")
    assert (r.citations_checked, r.citations_found, r.flags) == (0, 0, [])


def test_short_cite_with_at_has_no_first_page_and_is_not_checked():
    r = check("As the Court said, 389 U. S., at 351, the Amendment protects people.")
    assert r.citations_checked == 0


def test_every_manifest_citation_resolves():
    for c in MANIFEST["cases"]:
        cite = c["citation"]
        if "slip" in cite:
            continue
        r = check(f"At {cite} the Court wrote.")
        assert (r.citations_checked, r.citations_found) == (1, 1), cite


def test_chatrie_slip_citation_forms():
    # The manifest says "609 U.S. ___ (slip opinion; assigned 609 U.S. 605)".
    for cite in ("609 U.S. 605", "609 U. S. 605", "609 U.S. ___", "609 U. S. ___"):
        r = check(f"See {cite} (2026).")
        assert (r.citations_checked, r.citations_found) == (1, 1), cite
    r = check("See 609 U.S. 999 (2026).")
    assert r.citations_found == 0


def test_chatrie_citation_is_unresolved_when_the_case_is_excluded():
    m = manifest_without("chatrie")
    r = check("See 609 U.S. 605 (2026).", m)
    assert r.citations_found == 0 and r.not_in_corpus == ["609 U.S. 605"]


# --- full case names

def test_name_in_the_corpus_is_found():
    r = check("The Court decided Katz v. United States in 1967.")
    assert (r.citations_checked, r.citations_found) == (1, 1)
    assert r.flags == [] and r.not_in_corpus == []


def test_name_and_its_citation_count_separately():
    r = check("See Katz v. United States, 389 U.S. 347 (1967).")
    assert (r.citations_checked, r.citations_found) == (2, 2)


def test_name_outside_the_corpus_is_flagged_not_in_corpus():
    answer = "The principle goes back to Entick v. Carrington, which the Court noted."
    r = check(answer)
    assert (r.citations_checked, r.citations_found) == (1, 0)
    assert r.not_in_corpus == ["Entick v. Carrington"]
    [f] = r.flags
    assert f.kind == "not_in_corpus" and f.text == "Entick v. Carrington"
    assert answer[f.start:f.end] == "Entick v. Carrington"


@pytest.mark.parametrize("lead", ["In", "See", "Under", "Compare", "Cf.", "See also", "See, e.g.,", "But", "And"])
def test_a_sentence_opening_word_is_not_part_of_the_name(lead):
    r = check(f"{lead} Entick v. Carrington, 95 Eng. Rep. 807 (1765), the Court looked back.")
    assert r.not_in_corpus == ["Entick v. Carrington"], lead


def test_name_in_italic_markers():
    r = check("The Court decided *Katz v. United States* and *Entick v. Carrington* then.")
    assert (r.citations_checked, r.citations_found) == (2, 1)
    assert r.not_in_corpus == ["Entick v. Carrington"]


def test_name_ending_a_sentence_or_followed_by_punctuation():
    for tail in (".", ",", ";", ":", ")", " (1967).", "'s holding"):
        r = check(f"We turn to Katz v. United States{tail} Then more.")
        assert (r.citations_checked, r.citations_found) == (1, 1), tail


def test_possessive_name_is_found():
    r = check("Riley v. California's holding was narrow.")
    assert (r.citations_checked, r.citations_found) == (1, 1)


def test_two_names_joined_by_and():
    r = check("Smith v. Maryland and Katz v. United States both matter.")
    assert (r.citations_checked, r.citations_found) == (2, 2)


def test_two_names_in_a_string_cite():
    r = check("See Smith v. Maryland, 442 U.S. 735 (1979); Katz v. United States, 389 U.S. 347 (1967); Entick v. Carrington.")
    assert (r.citations_checked, r.citations_found) == (5, 4)
    assert r.not_in_corpus == ["Entick v. Carrington"]


def test_lowercase_words_before_the_name_are_not_part_of_it():
    r = check("The Court's holding in Entick v. Carrington and Chief Justice Roberts on Carpenter v. United States.")
    assert r.not_in_corpus == ["Entick v. Carrington"]
    assert r.citations_found == 1


@pytest.mark.parametrize("name", [
    "California v. Riley",          # parties swapped from Riley v. California
    "Jones v. United States",       # United States v. Jones is in the corpus; this is another case
    "Katz v. United Kingdom",
    "Katz v. United State",
    "Smith v. Marylan",
    "Miller v. United States",
])
def test_near_misses_are_not_in_this_corpus(name):
    r = check(f"The Court cited {name}, which it applied.")
    assert (r.citations_checked, r.citations_found) == (1, 0), name
    assert r.not_in_corpus == [name]


def test_same_name_different_case_is_caught_by_its_citation():
    r = check("See United States v. Miller, 307 U.S. 174 (1939).")
    assert (r.citations_checked, r.citations_found) == (2, 1)
    assert r.not_in_corpus == ["307 U.S. 174"]


@pytest.mark.parametrize("name,written", [
    ("Dow Chemical Co. v. United States", "Dow Chemical Co. v. United States"),
    ("Dow Chemical Co. v. United States", "Dow Chemical v. United States"),
    ("Dow Chemical Co. v. United States", "Dow Chemical Company v. United States"),
    ("California Bankers Assn. v. Shultz", "California Bankers Association v. Shultz"),
    ("United States v. Jones", "U.S. v. Jones"),
    ("On Lee v. United States", "On Lee v. United States"),
    ("California v. Ciraolo", "California v. Ciraolo"),
])
def test_corpus_names_resolve_across_ordinary_variants(name, written):
    assert name in {c["name"] for c in MANIFEST["cases"]}
    r = check(f"The Court reached {written}, on the facts.")
    assert (r.citations_checked, r.citations_found) == (1, 1), written


def test_every_manifest_name_resolves_with_a_sentence_opening_word():
    for c in MANIFEST["cases"]:
        if " v. " not in c["name"]:
            continue
        for lead in ("In", "See", "Under", "Compare"):
            r = check(f"{lead} {c['name']}, the Court held.")
            assert (r.citations_checked, r.citations_found) == (1, 1), (lead, c["name"])


def test_ex_parte_name_has_no_v_and_only_its_citation_is_checked():
    r = check("In Ex parte Jackson, 96 U.S. 727 (1878), the Court wrote.")
    assert (r.citations_checked, r.citations_found) == (1, 1)


def test_excluded_case_name_is_not_in_the_corpus():
    r = check("In Chatrie v. United States the Court held.", manifest_without("chatrie"))
    assert r.not_in_corpus == ["Chatrie v. United States"]
    r = check("In Chatrie v. United States the Court held.")
    assert (r.citations_checked, r.citations_found) == (1, 1)


def test_corporate_suffix_after_a_comma_stays_in_the_name():
    r = check("The Court discussed Thrifty-Tel, Inc. v. Bezenek at length.")
    assert r.not_in_corpus == ["Thrifty-Tel, Inc. v. Bezenek"]


def test_name_in_parentheses():
    r = check("(Entick v. Carrington) and (see Katz v. United States).")
    assert r.not_in_corpus == ["Entick v. Carrington"]
    assert (r.citations_checked, r.citations_found) == (2, 1)


def test_a_capitalised_word_after_the_name_is_not_part_of_it():
    r = check("In Entick v. Carrington the Court looked back; in Entick v. Carrington Justice Harlan agreed.")
    assert r.not_in_corpus == ["Entick v. Carrington"]
    assert len(r.flags) == 2 and all(f.text == "Entick v. Carrington" for f in r.flags)


def test_party_names_with_of_the():
    r = check("The agency in Foo v. Department of the Treasury lost.")
    assert r.not_in_corpus == ["Foo v. Department of the Treasury"]


@pytest.mark.parametrize("dash", ["—", "–", "--", " — "])
def test_a_dash_ends_the_name(dash):
    r = check(f"The rule from Entick v. Carrington{dash}a case from 1765{dash}came first.")
    assert r.not_in_corpus == ["Entick v. Carrington"]
    r = check(f"The rule from Katz v. United States{dash}a landmark{dash}came later.")
    assert (r.citations_checked, r.citations_found) == (1, 1)


def test_short_names_are_not_checked():
    r = check("Katz and Smith and Carpenter shaped the law; Entick too, and Boyd, but not Weeks.")
    assert (r.citations_checked, r.citations_found, r.flags, r.not_in_corpus) == (0, 0, [], [])


def test_the_word_v_in_other_uses_is_not_a_name():
    r = check("Figure v. the baseline, and a lowercase x v. y are not case names.")
    assert r.citations_checked == 0


def test_repeated_name_is_counted_and_flagged_each_time_listed_once():
    r = check("Entick v. Carrington came first. Later, Entick v. Carrington was cited again, as was Katz v. United States.")
    assert (r.citations_checked, r.citations_found) == (3, 1)
    assert len(r.flags) == 2
    assert r.not_in_corpus == ["Entick v. Carrington"]


def test_names_and_citations_inside_a_quotation_are_checked_too():
    answer = 'The Court said "see Rios v. United States, 364 U. S. 253" there.'
    r = check(answer)
    assert (r.citations_checked, r.citations_found) == (2, 0)
    assert r.not_in_corpus == ["Rios v. United States", "364 U. S. 253"]


def test_name_split_across_two_blocks_gets_a_two_block_flag():
    blocks = ["The Court looked at Entick v.", " Carrington for the rule."]
    r = check(blocks)
    [f] = r.flags
    assert (f.block, f.start) == (0, blocks[0].index("Entick"))
    assert (f.end_block, f.end) == (1, len(" Carrington"))
    assert f.text == "Entick v. Carrington"
    assert r.not_in_corpus == ["Entick v. Carrington"]


def test_citation_split_across_blocks_is_found():
    r = check(["See 389 U. S.", " 347 (1967)."])
    assert (r.citations_checked, r.citations_found, r.flags) == (1, 1, [])


def test_flags_are_in_answer_order_names_and_citations_mixed():
    answer = "First 399 U.S. 100, then Entick v. Carrington, then 12 U.S. 3."
    r = check(answer)
    assert [f.text for f in r.flags] == ["399 U.S. 100", "Entick v. Carrington", "12 U.S. 3"]
    assert [f.start for f in r.flags] == sorted(f.start for f in r.flags)


def test_flag_text_is_exactly_the_slice_of_the_blocks():
    blocks = ["Intro. ", "*Entick v. Carrington*, 95 Eng. Rep. 807, and 12 U.S. 3."]
    r = check(blocks)
    for f in r.flags:
        assert f.block == f.end_block
        assert blocks[f.block][f.start:f.end] == f.text


def test_text_with_no_citations():
    r = check("The Court decided the case in 1967 and held that a search occurred.")
    assert (r.citations_checked, r.citations_found, r.flags, r.not_in_corpus) == (0, 0, [], [])


def test_real_corpus_text_citations():
    # Katz's own text (data/corpus/cases/katz.json): two cases outside the corpus, United States v. Lee inside.
    text = ("See Lewis v. United States, 385 U. S. 206, 210; United States v. Lee, 274 U. S. 559, 563. "
            "But what he seeks to preserve as private may be protected. See Rios v. United States, 364 U. S. 253; "
            "Ex parte Jackson, 96 U. S. 727, 733.")
    r = check(text)
    assert r.not_in_corpus == ["Lewis v. United States", "385 U. S. 206", "Rios v. United States", "364 U. S. 253"]
    assert (r.citations_checked, r.citations_found) == (7, 3)


# --- review round: the right party must be exactly the manifest's

@pytest.mark.parametrize("name", [
    "Berger v. New York Times",
    "Smith v. Maryland Casualty Co.",
    "Boyd v. United States Steel",
    "Hester v. United States Postal Service",
    "United States v. Jones Lang",
    "Riley v. California Department of Revenue",
])
def test_a_longer_right_party_is_not_the_corpus_case(name):
    r = check(f"The Court cited {name}, which it applied.")
    assert (r.citations_checked, r.citations_found) == (1, 0), name
    assert r.not_in_corpus == [name]


@pytest.mark.parametrize("tail", [" held", ".", ",", ";", ")", "'s holding", "—and", " *and", " (1967)", " 389 U.S. 347"])
def test_the_exact_right_party_resolves_whatever_follows(tail):
    r = check(f"We turn to Katz v. United States{tail} then more.")
    assert r.citations_found == r.citations_checked and r.citations_checked >= 1, tail


def test_a_list_of_names_without_punctuation_still_resolves_each():
    r = check("Compare Katz v. United States Smith v. Maryland Riley v. California in turn.")
    assert (r.citations_checked, r.citations_found) == (3, 3)
    r = check("Katz v. United States\nSmith v. Maryland\nRiley v. California")
    assert (r.citations_checked, r.citations_found) == (3, 3)


def test_a_capitalised_sentence_starter_after_the_name_does_not_spoil_it():
    for after in ("I think", "We hold", "It was", "The Court", "This rule", "In 1967", "But later"):
        r = check(f"Katz v. United States {after} so.")
        assert (r.citations_checked, r.citations_found) == (1, 1), after


def test_the_left_side_stays_loose():
    # Residual looseness: anything before the corpus left party is ignored, so a person's name in front still resolves.
    for written in ("In Carpenter v. United States", "Whitfield Katz v. United States", "See Katz v. United States"):
        r = check(f"{written}, the Court held.")
        assert (r.citations_checked, r.citations_found) == (1, 1), written


# --- review round: a name and a citation that disagree

def test_name_followed_by_the_citation_of_another_corpus_case_flags_the_citation():
    answer = "See Katz v. United States, 565 U.S. 400 (2012)."
    r = check(answer)
    assert (r.citations_checked, r.citations_found) == (2, 1)
    assert r.not_in_corpus == ["565 U.S. 400"]
    [f] = r.flags
    assert answer[f.start:f.end] == "565 U.S. 400" and f.kind == "not_in_corpus"


def test_pin_cite_and_italics_do_not_hide_the_disagreement():
    r = check("See *Katz v. United States*, 565 U.S. 400, 404 (2012).")
    assert r.not_in_corpus == ["565 U.S. 400"]


def test_name_and_citation_that_agree_pass_with_or_without_a_pin_cite():
    for cite in ("389 U. S. 347", "389 U. S. 347, 351", "389 U.S. 347, 351 (1967)"):
        r = check(f"See Katz v. United States, {cite}.")
        assert (r.citations_checked, r.citations_found, r.flags) == (2, 2, []), cite
    r = check("See *Katz v. United States*, 389 U.S. 347 (1967).")
    assert r.flags == []


def test_chatrie_pair_agrees_in_both_citation_forms():
    for cite in ("609 U.S. 605", "609 U.S. ___"):
        r = check(f"See Chatrie v. United States, {cite} (2026).")
        assert r.flags == [], cite


def test_a_citation_not_directly_after_the_name_is_not_paired():
    r = check("Katz v. United States held it; see also 565 U.S. 400.")
    assert r.flags == []


def test_unresolved_name_with_a_corpus_citation_flags_only_the_name():
    r = check("See Entick v. Carrington, 389 U.S. 347.")
    assert r.not_in_corpus == ["Entick v. Carrington"]


def test_two_pairs_in_a_string_cite():
    r = check("See Katz v. United States, 389 U.S. 347; Smith v. Maryland, 565 U.S. 400.")
    assert r.not_in_corpus == ["565 U.S. 400"]
    assert (r.citations_checked, r.citations_found) == (4, 3)


# --- review round: abbreviations that used to flag a corpus case

@pytest.mark.parametrize("written", [
    "Dow Chem. Co. v. United States",
    "Dow Chemical Co. v. United States",
    "Dow Chem. Company v. United States",
    "California Bankers Ass'n v. Shultz",
    "California Bankers Assn. v. Shultz",
    "California Bankers Association v. Shultz",
    "California Bankers Ass’n v. Shultz",
])
def test_corpus_names_resolve_with_their_usual_abbreviations(written):
    r = check(f"See {written}, 000 U.S. 0.")
    assert [f.text for f in r.flags if "v." in f.text] == [], written
    r = check(f"The Court looked at {written} next.")
    assert (r.citations_checked, r.citations_found) == (1, 1), written


# --- a name ends at an opening parenthesis (P4.48)

@pytest.mark.parametrize("written", [
    "A 2026 dissent in *Chatrie v. United States* (Alito, joined by Thomas and Barrett) lists *Ciraolo* among them.",
    "A 2026 dissent in Chatrie v. United States (Alito, joined by Thomas and Barrett) lists Ciraolo among them.",
    "See Carpenter v. United States (Roberts, C. J.) on this.",
    "See Kyllo v. United States [Scalia, J.] on this.",
])
def test_a_parenthetical_after_a_corpus_name_is_not_part_of_it(written):
    # The replays, Oct 26, 2026: backyard-from-air flagged "Chatrie v. United States* (Alito" as not in the corpus.
    r = check(written)
    assert flagged(r) == [], written
    assert r.not_in_corpus == []


def test_a_name_not_in_the_corpus_is_flagged_without_its_parenthetical():
    answer = "In Hester v. Ohio (Holmes, J.) the field was open."
    r = check(answer)
    assert flagged(r) == ["Hester v. Ohio"]


def test_a_year_parenthetical_still_resolves():
    r = check("In *Carpenter v. United States* (2018), the Court held so.")
    assert flagged(r) == []
