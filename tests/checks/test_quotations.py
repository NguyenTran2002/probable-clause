"""The quotation check (T1.12), one convention at a time.

Corpus quotation marks are straight (P1.17); Claude's text may be curly. Only what
T1.12 lists is allowed: punctuation inside the closing mark, nested quotes changed
between double and single, ellipses for omitted words, bracketed alterations
(including those already in the source). Letter case is ignored throughout (P4.17).
Nothing else is forgiven.
"""

import pytest

from api.checks import check_answer
from api.settings import QUOTATION_MIN_WORDS
from tests.checks.helpers import MANIFEST, inner_span

SRC = (
    'But this effort to decide whether or not a given "area," viewed in the abstract, is '
    '"constitutionally protected" deflects attention from the problem presented by this case. '
    "For the Fourth Amendment protects people, not places. What a person knowingly exposes to "
    "the public, even in his own home or office, is not a subject of Fourth Amendment protection."
)
# Katz's own text has bracketed alterations (data/corpus/cases/katz.json).
BRACKETED_SRC = (
    "In affirming his conviction, the Court of Appeals rejected the contention that the recordings "
    'had been obtained in violation of the Fourth Amendment, because "[t]here was no physical '
    'entrance into the area occupied by [the petitioner]." We granted certiorari.'
)


def check(answer, kept=(SRC,)):
    blocks = answer if isinstance(answer, list) else [answer]
    return check_answer(blocks, list(kept), MANIFEST)


N = QUOTATION_MIN_WORDS.value
MADE_UP = ["zephyr", "quill", "marmot", "obelisk", "tundra", "nectar", "pylon", "gossamer", "ember", "lattice"]


def made_up(n):
    return " ".join(MADE_UP[:n])


def test_exact_quotation_is_found():
    r = check('The Court said "the Fourth Amendment protects people, not places" in Katz.')
    assert (r.quotations_checked, r.quotations_found) == (1, 1)
    assert r.flags == []


def test_unfound_quotation_is_flagged_with_its_spot():
    answer = 'The Court said "the Fourth Amendment protects every person everywhere" today.'
    r = check(answer)
    assert (r.quotations_checked, r.quotations_found) == (1, 0)
    [f] = r.flags
    assert f.kind == "quotation_not_found"
    assert (f.block, f.start, f.end_block, f.end) == inner_span([answer], "the Fourth Amendment protects every person everywhere")
    assert f.text == "the Fourth Amendment protects every person everywhere"


def test_quotation_shorter_than_the_threshold_is_not_checked():
    r = check(f'He called it "{made_up(N - 1)}" and moved on.')   # not in the source
    assert (r.quotations_checked, r.quotations_found, r.flags) == (0, 0, [])


def test_quotation_of_exactly_the_threshold_is_checked():
    r = check(f'He called it "{made_up(N)}" and moved on.')
    assert r.quotations_checked == 1 and r.quotations_found == 0


def test_quotation_is_found_in_any_kept_passage():
    other = "A completely different sentence about telephone booths and wiretaps in public."
    r = check('It said "telephone booths and wiretaps in public" here.', kept=[SRC, other])
    assert (r.quotations_checked, r.quotations_found) == (1, 1)


def test_nothing_kept_means_nothing_found():
    r = check('It said "the Fourth Amendment protects people" here.', kept=[])
    assert (r.quotations_checked, r.quotations_found) == (1, 0)
    assert len(r.flags) == 1


def test_no_quotations_at_all():
    r = check("The Court decided the case in 1967.")
    assert (r.quotations_checked, r.quotations_found, r.flags) == (0, 0, [])


# --- punctuation inside the closing quote mark

@pytest.mark.parametrize("tail", [",", ".", ""])
def test_punctuation_inside_the_closing_mark_is_forgiven(tail):
    # The source reads "...places." here; Claude's comma or period inside the mark is its own.
    r = check(f'The Court held "the Fourth Amendment protects people, not places{tail}" in Katz.')
    assert (r.quotations_checked, r.quotations_found) == (1, 1)


def test_punctuation_inside_the_mark_differs_from_the_source_ending():
    # The source has a comma after "home or office"; Claude ends the quote with a period inside the mark.
    r = check('It said "What a person knowingly exposes to the public, even in his own home or office." Yes.')
    assert (r.quotations_checked, r.quotations_found) == (1, 1)


def test_other_closing_punctuation_is_part_of_the_quotation():
    # Only the comma and the period go inside the mark as a matter of course; ? ! ; : belong to the quotation.
    src = "Is that really a search of the home? The Court said it was."
    assert check('It asked "Is that really a search of the home?" there.', kept=[src]).quotations_found == 1
    assert check('It asked "Is that really a search of the home." there.', kept=[src]).quotations_found == 1
    assert check('It asked "Is that really a search of the home;" there.', kept=[src]).quotations_found == 0
    src2 = "That really was a search of the home. The Court said so."
    assert check('It said "That really was a search of the home?" there.', kept=[src2]).quotations_found == 0
    assert check('It said "That really was a search of the home!" there.', kept=[src2]).quotations_found == 0


def test_punctuation_inside_the_quotation_must_still_match():
    # The comma after "people" is inside the quotation, not at its end.
    r = check('The Court held "the Fourth Amendment protects people not places" in Katz.')
    assert (r.quotations_checked, r.quotations_found) == (1, 0)


# --- ellipses

@pytest.mark.parametrize("dots", ["...", ". . .", "…", "[...]", "[. . .]", ". . . ."])
def test_ellipsis_stands_for_omitted_words(dots):
    r = check(f'It said "What a person knowingly exposes {dots} is not a subject of Fourth Amendment protection."')
    assert (r.quotations_checked, r.quotations_found) == (1, 1), dots


def test_ellipsis_pieces_must_come_in_source_order():
    r = check('It said "is not a subject of Fourth Amendment ... What a person knowingly exposes" there.')
    assert (r.quotations_checked, r.quotations_found) == (1, 0)


def test_each_piece_around_an_ellipsis_must_be_in_the_source():
    r = check('It said "What a person knowingly exposes ... is a subject of Fourth Amendment protection" there.')
    assert r.quotations_found == 0


def test_ellipsis_at_the_edges_is_ignored():
    r = check('It said "... the Fourth Amendment protects people, not places ..." there.')
    assert (r.quotations_checked, r.quotations_found) == (1, 1)


def test_ellipsis_does_not_bridge_two_passages():
    a = "The Fourth Amendment protects people, not places."
    b = "Nothing in this section shall be construed to prevent the transmission of information."
    r = check('It said "The Fourth Amendment protects people ... the transmission of information" there.', kept=[a, b])
    assert r.quotations_found == 0


def test_words_across_an_ellipsis_count_toward_the_threshold():
    short = made_up(N - 2) + " ... " + MADE_UP[N - 2]       # N - 1 words in all
    assert check(f'It said "{short}" there.').quotations_checked == 0
    enough = made_up(N - 1) + " ... " + MADE_UP[N - 1]      # N words in all
    assert check(f'It said "{enough}" there.').quotations_checked == 1


# --- bracketed alterations

def test_changed_capital_is_marked_by_brackets():
    # Source "For the Fourth Amendment": Claude starts mid-sentence. The source word is lower case already.
    r = check('The Court held that "[t]he Fourth Amendment protects people, not places" in Katz.')
    assert (r.quotations_checked, r.quotations_found) == (1, 1)


def test_changed_capital_in_the_other_direction():
    # Source "What a person knowingly exposes": Claude lowers the W because the quote is mid-sentence.
    r = check('It held that "[w]hat a person knowingly exposes to the public is not protected" here.',
              kept=["What a person knowingly exposes to the public is not protected by the Amendment."])
    assert (r.quotations_checked, r.quotations_found) == (1, 1)


# --- letter case (P4.17: the comparison ignores it throughout)

def test_an_unbracketed_lower_case_start_is_found():
    # Source "What a person knowingly exposes": Claude lowers the W with no brackets.
    r = check('It held that "what a person knowingly exposes to the public, even in his own home" here.')
    assert (r.quotations_checked, r.quotations_found) == (1, 1)


def test_an_unbracketed_capital_start_is_found():
    # The paid build tests, test 1: Kyllo has "is presumptively unreasonable without a warrant."
    r = check('**"Presumptively unreasonable without a warrant."** The holding treats it so.',
              kept=["the surveillance is a 'search' and is presumptively unreasonable without a warrant."])
    assert (r.quotations_checked, r.quotations_found) == (1, 1)


def test_a_change_of_case_mid_quotation_is_found():
    r = check('It said "for the fourth amendment protects People, not places" there.')
    assert (r.quotations_checked, r.quotations_found) == (1, 1)


def test_a_change_of_case_after_an_ellipsis_is_found():
    r = check('It said "the problem presented by this case . . . The Fourth Amendment protects people" there.')
    assert (r.quotations_checked, r.quotations_found) == (1, 1)


def test_ignoring_case_still_flags_a_changed_word():
    # control: the same quotation as above with one word changed is still not found
    r = check('It held that "What a person knowingly reveals to the public, even in his own home" here.')
    assert (r.quotations_checked, r.quotations_found) == (1, 0)


def test_ignoring_case_still_refuses_a_stripped_negating_prefix():
    # control: "Intrusive" quoted out of "non-intrusive", whatever the case
    kept = ["The officers used a non-intrusive scan of the home from the street that night."]
    for q in ('"Intrusive scan of the home from the street"', '"intrusive scan of the home from the street"'):
        r = check(f"It described an {q} there.", kept=kept)
        assert (r.quotations_checked, r.quotations_found) == (1, 0), q
    r = check('It described a "Non-intrusive scan of the home from the street" there.', kept=kept)
    assert (r.quotations_checked, r.quotations_found) == (1, 1)


def test_the_answer_keeps_the_quotation_as_written():
    # P4.17: only the comparison ignores case; a flag quotes the answer's own text
    r = check('It held that "What a person knowingly REVEALS to the public, even in his own home" here.')
    assert r.flags and "REVEALS" in r.flags[0].text


def test_bracketed_replacement_of_words():
    r = check('The Court said that "What [the defendant] knowingly exposes to the public" is unprotected.',
              kept=["What a person knowingly exposes to the public is unprotected, he said."])
    assert r.quotations_found == 1


def test_bracketed_insertion_without_source_words():
    r = check('It said "the Fourth Amendment [itself] protects people, not places" there.')
    assert r.quotations_found == 1


def test_bracket_at_the_end_of_a_word():
    # The source itself reads exercis[ing] (Carpenter); Claude copies it, or writes it out.
    src = 'The communication speaks of "exercis[ing] the full reach of our constitutional powers to outlaw surveillance."'
    r = check('It spoke of "exercis[ing] the full reach of our constitutional powers" there.', kept=[src])
    assert r.quotations_found == 1
    r = check('It spoke of "exercising the full reach of our constitutional powers" there.', kept=[src])
    assert r.quotations_found == 1
    # an ending added by Claude where the source has the bare word
    r = check('It found "the officers search[ed] the premises without a warrant" there.',
              kept=["the officers search the premises without a warrant, it said"])
    assert r.quotations_found == 1


def test_bracket_cannot_hide_a_long_run_of_source_words():
    long_gap = " ".join(f"w{i}" for i in range(settings.QUOTATION_BRACKET_MAX_SOURCE_WORDS.value + 20))
    r = check('It said "the Fourth [anything] protects people" there.',
              kept=[f"the Fourth {long_gap} protects people"])
    assert r.quotations_found == 0


def test_brackets_already_in_the_source_quoted_as_the_source_has_them():
    r = check('The Court of Appeals found "[t]here was no physical entrance into the area occupied by [the petitioner]" in the case.',
              kept=[BRACKETED_SRC])
    assert (r.quotations_checked, r.quotations_found) == (1, 1)


def test_source_brackets_quoted_without_them():
    r = check('The Court of Appeals found "there was no physical entrance into the area occupied by the petitioner" there.',
              kept=[BRACKETED_SRC])
    assert r.quotations_found == 1


def test_source_brackets_with_a_different_bracket_in_the_quote():
    r = check('It found "[T]here was no physical entrance into the area occupied by [the defendant]" there.',
              kept=[BRACKETED_SRC])
    assert r.quotations_found == 1


def test_a_quotation_that_is_all_brackets_has_nothing_to_check():
    r = check('He added "[the Court meant something else entirely]" with a flourish.')
    assert (r.quotations_checked, r.quotations_found, r.flags) == (0, 0, [])


# --- contiguity and word boundaries

def test_skipping_words_without_an_ellipsis_is_not_forgiven():
    r = check('It said "the Fourth Amendment protects not places" there.')
    assert r.quotations_found == 0


def test_a_quotation_must_start_and_end_on_word_boundaries():
    r = check('It said "ourth Amendment protects people" there.')
    assert r.quotations_found == 0
    r = check('It said "Fourth Amendment protects peopl" here too.')
    assert r.quotations_found == 0
    r = check('It said "the Fourth Amendment protects people" there.', kept=["the Fourth Amendment protects peoples"])
    assert r.quotations_found == 0


def test_whitespace_differences_are_ignored():
    r = check('It said "the Fourth   Amendment protects\npeople, not places" there.',
              kept=["For the Fourth Amendment\nprotects  people, not places."])
    assert r.quotations_found == 1


def test_footnote_passages_joined_with_blank_lines():
    r = check('The note says "the statute provides that wire communication" there.',
              kept=["18 U. S. C. § 1084. That statute provides in pertinent part:\n\n\"(a) Whoever"])
    assert r.quotations_found == 0   # "the statute" is not in the source; "That statute provides" is
    r = check('The note says "That statute provides in pertinent part" there.',
              kept=["18 U. S. C. § 1084. That statute provides in pertinent part:\n\n\"(a) Whoever"])
    assert r.quotations_found == 1


# --- quotation marks

def test_nested_quotes_changed_from_double_to_single():
    src = 'The Court noted that the "reasonable expectation of privacy" test turns on two questions.'
    r = check('The Court noted that "the \'reasonable expectation of privacy\' test turns on two questions."', kept=[src])
    assert (r.quotations_checked, r.quotations_found) == (1, 1)


def test_nested_quotes_single_in_the_source():
    src = "The Court noted that the 'reasonable expectation of privacy' test turns on two questions."
    r = check('The Court noted that "the \'reasonable expectation of privacy\' test turns on two questions."', kept=[src])
    assert r.quotations_found == 1


def test_nested_single_quotes_with_the_period_outside():
    src = 'He said the "twofold requirement" is met, and the test turns on "two questions."'
    r = check("He said \"the 'twofold requirement' is met, and the test turns on 'two questions'.\"", kept=[src])
    assert r.quotations_found == 1


def test_apostrophes_inside_words_must_match():
    r = check('It noted "over the petitioner\'s objection, to introduce evidence" there.',
              kept=["over the petitioner's objection, to introduce evidence of the calls."])
    assert r.quotations_found == 1
    r = check('It noted "over the petitioners objection, to introduce evidence" there.',
              kept=["over the petitioner's objection, to introduce evidence of the calls."])
    assert r.quotations_found == 0


def test_curly_quotation_marks_in_claudes_text():
    r = check("The Court held “the Fourth Amendment protects people, not places” in Katz.")
    assert (r.quotations_checked, r.quotations_found) == (1, 1)
    assert r.flags == []


def test_curly_apostrophes_and_nested_curly_single_quotes():
    src = "over the petitioner's objection, the \"reasonable expectation\" test applies to this case here."
    r = check("It noted “over the petitioner’s objection, the ‘reasonable expectation’ test applies to this case here.”", kept=[src])
    assert (r.quotations_checked, r.quotations_found) == (1, 1)


def test_curly_flag_span_excludes_the_marks():
    answer = "It said “the Fourth Amendment protects every person everywhere” today."
    [f] = check(answer).flags
    assert (f.block, f.start, f.end_block, f.end) == inner_span([answer], "the Fourth Amendment protects every person everywhere")


def test_straight_marks_used_by_a_mix_of_open_and_close():
    r = check("It said “the Fourth Amendment protects people, not places\" in Katz.")
    assert (r.quotations_checked, r.quotations_found) == (1, 1)


def test_single_quoted_text_alone_is_not_a_quotation():
    r = check("It was called 'a truly absurd rule' by everyone.")
    assert r.quotations_checked == 0


def test_a_stray_mark_in_one_paragraph_does_not_shift_the_next():
    answer = 'The bolt was 5" long.\n\nThe Court said "the Fourth Amendment protects people, not places" in Katz.'
    r = check(answer)
    assert (r.quotations_checked, r.quotations_found, r.flags) == (1, 1, [])


# --- blocks and offsets

def test_quotation_spanning_two_blocks_is_found():
    blocks = ['The Court said "the Fourth Amendment protects', ' people, not places" in Katz.']
    r = check(blocks)
    assert (r.quotations_checked, r.quotations_found, r.flags) == (1, 1, [])


def test_flag_for_a_quotation_spanning_blocks_runs_from_block_to_block():
    blocks = ['The Court said "the Fourth Amendment protects', ' every person everywhere" in Katz.']
    [f] = check(blocks).flags
    assert (f.block, f.start) == (0, blocks[0].index("the Fourth"))
    assert (f.end_block, f.end) == (1, len(" every person everywhere"))
    assert f.text == "the Fourth Amendment protects every person everywhere"


def test_flag_spanning_a_blank_block_in_between():
    blocks = ['It said "the Fourth Amendment', "", ' protects every person everywhere" there.']
    [f] = check(blocks).flags
    assert (f.block, f.end_block) == (0, 2)
    assert f.text == "the Fourth Amendment protects every person everywhere"


def test_offsets_index_the_blocks_exactly_as_given():
    blocks = ["  Lead  ", 'x "the Fourth Amendment protects every person" y', ' and "a second made-up quotation here" z']
    r = check(blocks)
    assert len(r.flags) == 2
    for f in r.flags:
        assert f.block == f.end_block
        assert blocks[f.block][f.start:f.end] == f.text
    assert [f.block for f in r.flags] == [1, 2]


def test_quotation_whose_opening_mark_ends_a_block():
    blocks = ['He said "', 'the Fourth Amendment protects every person" there']
    [f] = check(blocks).flags
    assert (f.block, f.start) == (1, 0)
    assert (f.end_block, f.end) == (1, len("the Fourth Amendment protects every person"))


def test_quotation_whose_closing_mark_ends_a_block():
    blocks = ['He said "the Fourth Amendment protects every person"', " there"]
    [f] = check(blocks).flags
    assert (f.end_block, f.end) == (0, len(blocks[0]) - 1)


def test_two_quotations_in_one_block_each_counted():
    r = check('A "the Fourth Amendment protects people" and B "made up words go right here" end.')
    assert (r.quotations_checked, r.quotations_found) == (2, 1)
    assert len(r.flags) == 1


def test_a_quotation_containing_a_non_ascii_character_keeps_offsets_in_code_points():
    answer = 'Façade: "the Fourth Amendment protects every person" end.'
    [f] = check(answer).flags
    assert answer[f.start:f.end] == f.text


# --- real corpus text

def test_every_window_of_real_passages_is_found_and_altered_ones_are_not():
    import json
    from tests.checks.helpers import ROOT

    texts = []
    for name in ("katz", "carpenter", "riley", "jones"):
        d = json.loads((ROOT / "data" / "corpus" / "cases" / f"{name}.json").read_text())
        for op in d["opinions"]:
            texts += [p["text"] for p in op["paragraphs"] if p["kind"] != "section"]
    texts = [t for t in texts if len(t.split()) >= 30]
    assert len(texts) > 100
    for t in texts:
        words = t.split(" ")
        window = " ".join(words[5:17])
        # skip windows with the passage's own marks, brackets or ellipses and windows with odd spacing
        if '"' in window or "[" in window or ". ." in window or "" in window.split(" "):
            continue
        r = check_answer([f'He wrote "{window}" here.'], [t], MANIFEST)
        assert r.quotations_found == 1, window
        altered = window.replace(words[8], words[8] + "xyz", 1)
        r = check_answer([f'He wrote "{altered}" here.'], [t], MANIFEST)
        assert r.quotations_found == 0, altered


# --- brackets already in the corpus, in the forms the opinions use

def test_possessive_after_a_bracket():
    src = "In sum, the Court held that Carpenter's location records were protected by the Fourth Amendment."
    r = check("It held \"that [Carpenter]'s location records were protected\" there.", kept=[src])
    assert r.quotations_found == 1


def test_apostrophe_inside_a_bracket():
    src = ('The writ spoke of "[F]or a man[\']s house is his Castle, & domus sua cuique est tutissimum refugium '
           '[each man\'s home is his safest refuge]" in the old books.')
    r = check('The writ said "[F]or a man[\']s house is his Castle, & domus sua cuique est tutissimum refugium '
              '[each man\'s home is his safest refuge]" there.', kept=[src])
    assert (r.quotations_checked, r.quotations_found) == (1, 1)


def test_long_bracket_copied_from_the_source_is_found():
    src = ("It reasoned that all of the records [which are required to be kept pursuant to the Bank Secrecy Act,] "
           "pertain to transactions to which the bank was itself a party.")
    quote = ("all of the records [which are required to be kept pursuant to the Bank Secrecy Act,] "
             "pertain to transactions to which the bank was itself a party")
    r = check(f'It said "{quote}" there.', kept=[src])
    assert r.quotations_found == 1


def test_bracket_followed_by_a_comma_in_the_middle():
    src = "The agent saw Mitch Miller [respondent], 3859 Mathis Street, and the house."
    r = check('It said "saw Mitch Miller [respondent], 3859 Mathis Street" there.', kept=[src])
    assert r.quotations_found == 1
    r = check('It said "saw Mitch Miller [the defendant], 3859 Mathis Street" there.', kept=[src])
    assert r.quotations_found == 1


def test_bracket_then_closing_period_is_not_a_part_of_the_check():
    src = 'because "[t]here was no physical entrance into the area occupied by [the petitioner]." We granted'
    r = check('The lower court said "[t]here was no physical entrance into the area occupied by [the defendant]." Right.', kept=[src])
    assert r.quotations_found == 1


def test_an_opinions_ellipsis_with_a_comma_after_it():
    src = ('"At the time of [the] agent[\'s] visits . . . , the top half of the front of the barn was covered by a '
           'fishnet type material."')
    r = check('The record says "At the time of [the] agent[\'s] visits . . . , the top half of the front of the barn" here.',
              kept=[src])
    assert r.quotations_found == 1


def test_ellipsis_written_two_ways_for_the_same_omission():
    src = "What a person knowingly exposes to the public, even in his own home or office, is not a subject of protection."
    for dots in ("...", ". . .", "…", ". . . ."):
        r = check(f'It said "What a person knowingly exposes {dots} is not a subject of protection" there.', kept=[src])
        assert r.quotations_found == 1, dots


def test_the_whole_corpus_quotes_itself():
    # Every quotation inside every corpus passage is found when that passage is the kept text: 1,900 or so real
    # quotations with the brackets, ellipses and nested marks the opinions use.
    import json
    from tests.checks.helpers import ROOT

    checked = 0
    for path in sorted((ROOT / "data" / "corpus" / "cases").glob("*.json")):
        d = json.loads(path.read_text())
        for op in d["opinions"]:
            texts = [p["text"] for p in op["paragraphs"] if p["kind"] != "section"]
            texts += ["\n\n".join(fn["paragraphs"]) for fn in op.get("footnotes", [])]
            for t in texts:
                r = check_answer([t], [t], MANIFEST)
                bad = [f.text for f in r.flags if f.kind == "quotation_not_found"]
                assert not bad, (path.name, bad)
                checked += r.quotations_checked
    assert checked > 1000


def test_many_brackets_and_ellipses_on_a_repetitive_passage_stay_fast():
    import time

    src = "the " * 300 + "end"
    brackets = " ".join(f"the [{chr(97 + i)}]" for i in range(12)) + " the zzz"
    ellipses = " ... ".join(["the"] * 12) + " zzz"
    for quote in (brackets, ellipses):
        started = time.perf_counter()
        r = check(f'It said "{quote}" there.', kept=[src])
        assert r.quotations_found == 0
        assert time.perf_counter() - started < 2


# --- review round: brackets must not change a negation

from api import settings  # noqa: E402

NEG_SRC = ("The Court wrote that the fact that the electronic device employed to achieve that end did not happen to "
           "penetrate the wall of the booth can have no constitutional significance.")


def test_bracket_that_drops_a_negation_is_flagged():
    r = check('It said "employed to achieve that end [did] penetrate the wall of the booth" there.', kept=[NEG_SRC])
    assert (r.quotations_checked, r.quotations_found) == (1, 0)
    [f] = r.flags
    assert f.text == "employed to achieve that end [did] penetrate the wall of the booth"


def test_bracket_that_flips_unreasonable_to_reasonable_is_flagged():
    for src in ("A search conducted without a warrant is unreasonable unless it falls within a specific exception.",
                "A search conducted without a warrant is not reasonable unless it falls within a specific exception.",
                "A search conducted without a warrant is per se unreasonable unless it falls within a specific exception."):
        r = check('It said "A search conducted without a warrant is [reasonable] unless it falls within a specific exception" here.',
                  kept=[src])
        assert (r.quotations_checked, r.quotations_found) == (1, 0), src


def test_bracket_that_inserts_a_negation_is_flagged():
    src = "The officers did not need a warrant here, the Court said."
    r = check('It said "The officers did not need a warrant [never] here" there.', kept=[src])
    assert (r.quotations_checked, r.quotations_found) == (1, 0)
    for word in ("not", "no", "none", "nothing", "neither", "nor", "without", "didn't", "cannot"):
        r = check(f'It said "The officers did not need a warrant [{word}] here" there.', kept=[src])
        assert r.quotations_found == 0, word


def test_bracket_that_replaces_a_negation_with_a_negation_is_fine():
    src = "The fact that the device did not penetrate the wall of the booth can have no constitutional significance."
    for word in ("never", "not", "didn't"):
        r = check(f'It said "that the device did [{word}] penetrate the wall of the booth" there.', kept=[src])
        assert r.quotations_found == 1, word
    # a replacement of exactly the allowed number of words, a negation on each side
    k = settings.QUOTATION_BRACKET_MAX_SOURCE_WORDS.value
    run = " ".join(["not"] + MADE_UP[:k - 1])
    src = f"the officers did {run} enter the home at all"
    r = check('It said "the officers did [never] enter the home at all" there.', kept=[src])
    assert r.quotations_found == 1
    run = " ".join(["not"] + MADE_UP[:k])        # one more word than a bracket may stand for
    src = f"the officers did {run} enter the home at all"
    r = check('It said "the officers did [never] enter the home at all" there.', kept=[src])
    assert r.quotations_found == 0


def test_bracket_copied_from_the_source_with_its_negation_is_fine():
    src = "The fact that the device did [not] happen to penetrate the wall of the booth can have no significance."
    r = check('It said "that the device did [not] happen to penetrate the wall of the booth" there.', kept=[src])
    assert r.quotations_found == 1
    # Claude restates the same bracketed word (still a negation)
    r = check('It said "that the device did [never] happen to penetrate the wall of the booth" there.', kept=[src])
    assert r.quotations_found == 1


def test_a_bracket_without_negations_on_either_side_still_passes():
    r = check('The Court said that "What [the defendant] knowingly exposes to the public" is unprotected.',
              kept=["What a person knowingly exposes to the public is unprotected, he said."])
    assert r.quotations_found == 1


def test_a_changed_prefix_is_not_taken_for_a_negation_unless_the_words_pair_up():
    src = "The united front of the unit met in the town hall to decide the question of income."
    r = check('It said "The [uniform] front of the [troop] met in the town hall to decide" here.', kept=[src])
    assert r.quotations_found == 1
    # "unit" and "united" differ by letters but are not a prefix pair ("un" + "it" is not "united")
    r = check('It said "The united front of the [unit] met in the town hall to decide" here.', kept=[src])
    assert r.quotations_found == 1


def test_attached_bracket_that_adds_a_negating_prefix_or_ending_is_flagged():
    r = check('It said "the search was [in]valid under the Fourth Amendment" here.',
              kept=["the search was valid under the Fourth Amendment, the Court held."])
    assert r.quotations_found == 0
    r = check('It said "the officers do[n\'t] need a warrant to enter" here.',
              kept=["the officers do need a warrant to enter, the Court held."])
    assert r.quotations_found == 0
    r = check('It said "the officers [un]reasonably searched the home" here.',
              kept=["the officers reasonably searched the home, the Court held."])
    assert r.quotations_found == 0


def test_attached_negating_bracket_copied_from_the_source_is_fine():
    src = "The Court held that the search was [un]reasonable under the Fourth Amendment as applied here."
    r = check('It said "the search was [un]reasonable under the Fourth Amendment" there.', kept=[src])
    assert r.quotations_found == 1
    r = check('It said "the search was unreasonable under the Fourth Amendment" there.', kept=[src])
    assert r.quotations_found == 1


def test_bracket_span_limit_is_the_setting():
    k = settings.QUOTATION_BRACKET_MAX_SOURCE_WORDS.value
    run = " ".join(MADE_UP[:k])
    src = f"the Fourth {run} protects people here"
    assert check('It said "the Fourth [anything] protects people" there.', kept=[src]).quotations_found == 1
    longer = " ".join(MADE_UP[:k] + ["extra"])
    src = f"the Fourth {longer} protects people here"
    assert check('It said "the Fourth [anything] protects people" there.', kept=[src]).quotations_found == 0


# --- review round: quotation pairing

P1 = "For the Fourth Amendment protects people, not places."
P2 = "What a person knowingly exposes to the public, even in his own home or office, is not a subject of protection."


def test_a_multi_paragraph_quotation_continues_across_the_break():
    answer = f'The Court wrote: "{P1}\n\n"{P2}" That was the rule.'
    r = check(answer, kept=[P1, P2])
    assert (r.quotations_checked, r.quotations_found, r.flags) == (1, 1, [])


def test_a_multi_paragraph_quotation_with_an_altered_part_is_flagged_across_its_span():
    altered = P2.replace("knowingly", "carelessly")
    answer = f'The Court wrote: "{P1}\n\n"{altered}" That was the rule.'
    r = check(answer, kept=[P1, P2])
    assert (r.quotations_checked, r.quotations_found) == (1, 0)
    [f] = r.flags
    assert f.text == answer[f.start:f.end] and f.text.startswith("For the Fourth") and f.text.endswith("of protection.")
    assert "\n\n" in f.text


def test_three_paragraph_quotation():
    p3 = "Nothing else about the matter was decided in that case at all."
    answer = f'It read: "{P1}\n\n"{P2}\n\n"{p3}" Done.'
    r = check(answer, kept=[P1, P2, p3])
    assert (r.quotations_checked, r.quotations_found, r.flags) == (1, 1, [])


def test_multi_paragraph_quotation_across_blocks():
    blocks = [f'It read: "{P1}\n\n', f'"{P2}" Done.']
    r = check(blocks, kept=[P1, P2])
    assert (r.quotations_checked, r.quotations_found, r.flags) == (1, 1, [])
    blocks = [f'It read: "{P1}\n\n', '"What a person carelessly exposes to the public is not protected" Done.']
    [f] = check(blocks, kept=[P1, P2]).flags
    assert (f.block, f.end_block) == (0, 1)


def test_an_unclosed_quotation_not_continued_is_left_unchecked():
    answer = f'He said "{P1}\n\nThe next paragraph has no mark.'
    r = check(answer, kept=[P2])
    assert (r.quotations_checked, r.flags) == (0, [])


def test_a_new_quotation_after_a_closed_one_is_not_a_continuation():
    answer = f'He said "{P1}" fine.\n\n"{P2}" And so on.'
    r = check(answer, kept=[P1, P2])
    assert (r.quotations_checked, r.quotations_found) == (2, 2)


def test_markdown_blockquote_is_one_quotation_without_its_markers():
    answer = f"The Court wrote:\n\n> {P1}\n> {P2.split(',')[0]},\n> even in his own home or office, is not a subject of protection.\n\nThat was it."
    r = check(answer, kept=[P1 + " " + P2])
    assert (r.quotations_checked, r.quotations_found, r.flags) == (1, 1, [])


def test_markdown_blockquote_not_found_is_flagged_from_first_word_to_last():
    answer = "Intro.\n\n> For the Fourth Amendment protects every person\n> in every place at once.\n\nOutro."
    r = check(answer, kept=[P1])
    [f] = r.flags
    assert f.kind == "quotation_not_found"
    assert answer[f.start:f.end] == f.text
    assert f.text.startswith("For the Fourth") and f.text.endswith("at once.")


def test_markdown_blockquote_shorter_than_the_threshold_is_not_checked():
    r = check(f"Intro.\n\n> {made_up(N - 1)}\n\nOutro.")
    assert r.quotations_checked == 0


def test_a_paragraph_with_one_line_not_in_the_blockquote_is_not_a_blockquote():
    r = check(f"Intro.\n\n> {made_up(N)}\nand a plain line here\n\nOutro.")
    assert r.quotations_checked == 0


def test_inch_mark_after_a_digit_is_not_a_quotation_mark():
    answer = 'He said 5" tall and "violated the garbage upon which he justifiably relied" here.'
    r = check(answer, kept=["violated the privacy upon which he justifiably relied while using the booth"])
    assert (r.quotations_checked, r.quotations_found) == (1, 0)
    [f] = r.flags
    assert f.text == "violated the garbage upon which he justifiably relied"
    r = check(answer.replace("garbage", "privacy"), kept=["violated the privacy upon which he justifiably relied while using the booth"])
    assert (r.quotations_checked, r.quotations_found, r.flags) == (1, 1, [])


def test_a_closing_mark_right_after_a_digit_still_closes():
    r = check('It cited "389 U.S. 347 and 388 U.S. 41" together.', kept=["see 389 U.S. 347 and 388 U.S. 41, both"])
    assert (r.quotations_checked, r.quotations_found) == (1, 1)


# --- review round: matching is bounded and memoised

def test_forty_repeated_pieces_against_repetitive_passages_finish_fast():
    import time

    passages = ["of the " * 2000 + "end" for _ in range(30)]
    quote = " ... ".join(["of the"] * 40) + " ... zzz"
    words = " ".join(["of the"] * 40)
    for q in (quote, words + " zzz", " [x] ".join(["of the"] * 40) + " zzz"):
        started = time.perf_counter()
        r = check(f'It said "{q}" there.', kept=passages)
        elapsed = time.perf_counter() - started
        assert r.quotations_found == 0 and elapsed < 1, (q[:30], elapsed)


def test_realistic_worst_case_many_passages_many_quotations_stays_fast():
    import time

    passages = [(SRC + " ") * 12 for _ in range(40)]                       # 40 kept passages of about 4,000 characters
    quotes = [f'"the Fourth Amendment protects people, not places{i}"' for i in range(25)]
    quotes += ['"a [t]he ... what a person ... is not a subject of Fourth Amendment protection"'] * 5
    started = time.perf_counter()
    r = check("Answer. " + " and ".join(quotes), kept=passages)
    assert time.perf_counter() - started < 1
    assert r.quotations_checked == 30


def test_a_quotation_that_cannot_be_decided_in_the_budget_is_flagged_never_passed(monkeypatch):
    from api.checks import quotations

    assert check('It said "the Fourth Amendment protects people, not places" there.').quotations_found == 1
    monkeypatch.setattr(quotations, "MATCH_STEP_BUDGET", 1)
    r = check('It said "the Fourth Amendment protects people, not places" there.')
    assert (r.quotations_checked, r.quotations_found) == (1, 0)
    assert [f.kind for f in r.flags] == ["quotation_not_found"]


# ---- an ellipsis never drops a negation (contract v1.4, after the cross-part review)

NEG_SOURCE = "The argument was that the Constitution did not forbid the obtaining of evidence by wiretapping."


@pytest.mark.parametrize("quote", [
    '"that the Constitution did . . . forbid the obtaining"',
    '"that the Constitution did … forbid the obtaining"',
    '"that the Constitution did... forbid the obtaining"',
    '"the Constitution . . . forbid the obtaining of evidence"',
])
def test_an_ellipsis_over_a_negation_is_flagged(quote):
    r = check_answer([f"The Court wrote {quote}."], [NEG_SOURCE], MANIFEST)
    assert r.quotations_checked == 1 and r.quotations_found == 0
    assert [f.kind for f in r.flags] == ["quotation_not_found"]


def test_an_ellipsis_over_words_without_a_negation_still_matches():
    r = check_answer(['The Court wrote "the Constitution did not . . . the obtaining of evidence".'], [NEG_SOURCE], MANIFEST)
    assert r.quotations_found == 1 and r.flags == []


def test_an_ellipsis_takes_the_smallest_gap():
    # "the" occurs before and after the negation: the match may start after it, so the gap holds no "not"
    source = "Not the first time; the officers did search the house and the officers did leave."
    r = check_answer(['He wrote "the officers did search . . . the officers did leave".'], [source], MANIFEST)
    assert r.quotations_found == 1 and r.flags == []
    r = check_answer(['He wrote "Not the first time . . . did search the house".'], [source], MANIFEST)
    assert r.quotations_found == 1


# ---- more negation words, and a negating prefix dropped by an ellipsis (the final review, Oct 25, 2026)

@pytest.mark.parametrize("source,whole,dropped", [
    ("That right is nowhere to be found in the annals of Anglo-American jurisprudence.",
     "is nowhere to be found in the annals", "is . . . to be found in the annals"),
    ("A statutory disclosure requirement is hardly sufficient to give someone an ownership interest.",
     "disclosure requirement is hardly sufficient to give someone", "disclosure requirement is . . . sufficient to give someone"),
    ("The officers searched and nobody objected to the entry of the house that night.",
     "officers searched and nobody objected to the entry", "officers searched and . . . objected to the entry"),
    ("The warrant was scarcely supported by the affidavit the officer had sworn that day.",
     "warrant was scarcely supported by the affidavit", "warrant was . . . supported by the affidavit"),
    ("The device was barely visible from the street where the officers had parked.",
     "device was barely visible from the street", "device was . . . visible from the street"),
    ("The search was valid absent exigent circumstances that would justify the entry.",
     "search was valid absent exigent circumstances", "search was valid . . . exigent circumstances"),
    ("It is a non-intrusive device which emits no rays or beams and shows a crude visual image.",
     "is a non-intrusive device which emits no rays", "is a . . . intrusive device which emits no rays"),
    ("The entry was un-announced and the officers carried their weapons drawn into the room.",
     "entry was un-announced and the officers carried", "entry was . . . announced and the officers carried"),
])
def test_an_ellipsis_over_another_negation_or_a_negating_prefix_is_flagged(source, whole, dropped):
    r = check_answer([f'The Court wrote "{whole}".'], [source], MANIFEST)
    assert (r.quotations_checked, r.quotations_found) == (1, 1), whole      # the control: the quote itself is found
    r = check_answer([f'The Court wrote "{dropped}".'], [source], MANIFEST)
    assert r.quotations_checked == 1 and r.quotations_found == 0, dropped
    assert [f.kind for f in r.flags] == ["quotation_not_found"]


def test_the_real_corpus_cases_of_the_final_review_are_flagged():
    from api.corpus.store import Corpus
    from tests.loop.support import ROOT
    corpus = Corpus.load(ROOT)
    for pid, whole, dropped in [
        ("jardines-3-p1", "that is nowhere to be found in the annals of Anglo-American jurisprudence",
         "that is . . . to be found in the annals of Anglo-American jurisprudence"),
        ("carpenter-4-p47", "a statutory disclosure requirement is hardly sufficient to give someone an ownership interest",
         "a statutory disclosure requirement is . . . sufficient to give someone an ownership interest"),
        ("kyllo-1-p3", "is a non-intrusive device which emits no rays or beams",
         "is a . . . intrusive device which emits no rays or beams"),
        ("kyllo-1-p3", "non-intrusive device which emits no rays or beams", ". . . intrusive device which emits no rays or beams"),
    ]:
        text = corpus.passages[pid].text
        r = check_answer([f'The Court wrote "{whole}".'], [text], corpus.manifest)
        assert r.quotations_found == 1, (pid, whole)
        r = check_answer([f'The Court wrote "{dropped}".'], [text], corpus.manifest)
        assert r.quotations_checked == 1 and r.quotations_found == 0, (pid, dropped)


def test_a_hyphenated_word_in_a_gap_that_is_not_a_negating_prefix_still_matches():
    source = "The officers made a long-term plan and the court approved the warrant that day."
    r = check_answer(['He wrote "officers made a . . . plan and the court approved".'], [source], MANIFEST)
    assert r.quotations_found == 1 and r.flags == []


def test_a_quotation_never_starts_right_after_a_negating_prefix():
    source = "On remand the court found that it is a non-intrusive device which emits no rays or beams at all."
    for q in ["intrusive device which emits no rays", ". . . intrusive device which emits no rays"]:
        r = check_answer([f'He wrote "{q}".'], [source], MANIFEST)
        assert r.quotations_checked == 1 and r.quotations_found == 0, q
    r = check_answer(['He wrote "a non-intrusive device which emits no rays".'], [source], MANIFEST)
    assert r.quotations_found == 1
    r = check_answer(['He wrote "Non-intrusive devices emit nothing at all".'], ["Non-intrusive devices emit nothing at all, it said."], MANIFEST)
    assert r.quotations_found == 1


def test_a_quotation_may_start_after_a_hyphen_that_is_not_a_negating_prefix():
    source = "The officers made a long-term plan and the court approved the warrant that day."
    r = check_answer(['He wrote "term plan and the court approved".'], [source], MANIFEST)
    assert r.quotations_found == 1


def test_a_bracket_that_strips_a_hyphenated_negating_prefix_is_flagged():
    source = "On remand the court found that it is a non-intrusive device on the house which emits no rays."
    r = check_answer(['He wrote "it is a [intrusive] device on the house".'], [source], MANIFEST)
    assert r.quotations_checked == 1 and r.quotations_found == 0
    r = check_answer(['He wrote "it is a [non-intrusive] device on the house".'], [source], MANIFEST)
    assert r.quotations_found == 1
