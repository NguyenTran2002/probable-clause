"""The sentence splitter (contract §4.A, T1.9).

Claude cites runs of these sentences, so a wrong split cuts a citation in half
while a missed split only makes a citation a little longer: in doubt, no split.
Examples are corpus text, verbatim, unless marked synthetic.
"""

import json
import random
import re
import time
from pathlib import Path

import pytest

from api.corpus.sentences import LEGAL_ABBREVIATIONS, split_sentences

ROOT = Path(__file__).resolve().parents[2]
HARDEST = ROOT / "tests" / "fixtures" / "sentences" / "hardest.json"


def sentences(text: str) -> list[str]:
    return [text[a:b] for a, b in split_sentences(text)]


def assert_tiles(text: str, spans: list[tuple[int, int]]) -> None:
    """No gap, no overlap, in order; no empty span; whitespace trails a sentence, never leads one."""
    if not text:
        assert spans == []
        return
    assert spans[0][0] == 0 and spans[-1][1] == len(text)
    for (a, b), (c, _) in zip(spans, spans[1:]):
        assert b == c
    for a, b in spans:
        assert a < b
    for _, b in spans[:-1]:
        assert text[b - 1].isspace() and not text[b].isspace()
    if text.strip():
        assert all(text[a:b].strip() for a, b in spans)


# ---- tiling, as a property

PIECES = [
    "The", "Court", "held", "it", "law", "Katz", "Amendment", "States", "Id.,", "Ibid.", "See", "Cf.", "at",
    "657", "338", "U.", "S.", "v.", "No.", "§", "§§", "e.", "g.,", "supra", "How.", "Cal.", "Pen.", "Stat.",
    "J.", "(1958)", "[t]he", '"', "'", "(", ")", "[", "]", ".", "?", "!", ",", ";", ":", ". . .", " . . . .",
    "\n", "\n\n", "\n\n\n", " ", "  ", "\t", "—", "-", "–", "1st", "$5,000", "Comm'n", "e.g.", "A", "a",
    "“", "”", "‘", "’", "U.S.C.", "Cal.-based", "1958-Smith", "AMEND.", "para.", "Paras.", "no.", "me.",
    "[p]roperty", "own—movements", "CONST.", "1.", "SEC.",
]


def random_texts(n: int, seed: int) -> list[str]:
    rng = random.Random(seed)
    out = ["", " ", "\n\n", "  \n\n  ", ".", "A.", "a. B", "\n\nA. B. c.\n\n"]
    for _ in range(n):
        parts = rng.choices(PIECES, k=rng.randint(1, 40))
        seps = rng.choices(["", " ", " ", " ", "\n\n"], k=len(parts))
        out.append("".join(p + s for p, s in zip(parts, seps)))
    return out


def test_spans_tile_random_texts():
    for text in random_texts(4000, seed=19):
        spans = split_sentences(text)
        assert_tiles(text, spans)
        assert split_sentences(text) == spans  # deterministic


def test_return_shape():
    spans = split_sentences("The authority of the Boyd decision has never been impeached. Its basic principle.")
    assert isinstance(spans, list) and all(isinstance(s, tuple) and len(s) == 2 for s in spans)
    assert all(isinstance(x, int) for s in spans for x in s)


def test_empty_and_blank_text():
    assert split_sentences("") == []
    assert split_sentences("   ") == [(0, 3)]
    assert split_sentences("\n\n") == [(0, 2)]


def corpus_passages() -> list[tuple[str, str]]:
    manifest = json.loads((ROOT / "data" / "corpus" / "manifest.json").read_text())
    out = []
    for case in manifest["cases"]:
        data = json.loads((ROOT / "data" / "corpus" / "cases" / f"{case['key']}.json").read_text())
        for op in data["opinions"]:
            out += [(case["key"], p["text"]) for p in op["paragraphs"] if p["kind"] != "section"]
            out += [(case["key"], "\n\n".join(f["paragraphs"])) for f in op["footnotes"]]
    return out


def test_spans_tile_every_corpus_passage():
    passages = corpus_passages()
    assert len(passages) == 2462  # contract §3, P4.2
    for _, text in passages:
        spans = split_sentences(text)
        assert_tiles(text, spans)
        starts = {a for a, _ in spans}
        assert all(m.end() in starts for m in re.finditer("\n\n", text))


def allowed_cut(text: str, cut: int) -> bool:
    """The oracle (contract §4.A): a split falls at a blank line, or after a stop, closing marks and whitespace
    and before opening marks and a capital."""
    before = text[:cut]
    gap = before[len(before.rstrip()):]
    if "\n\n" in gap:
        return True
    if not re.search(r"[.?!][\"')\]]*\s+\Z", before):
        return False
    m = re.match(r"[\"'(\[]*(.)", text[cut:], re.S)
    return bool(m) and m.group(1).isupper()


def test_every_split_is_one_the_rule_allows():
    texts = random_texts(4000, seed=23) + [t for _, t in corpus_passages()]
    for text in texts:
        for start, _ in split_sentences(text)[1:]:
            assert allowed_cut(text, start), (text[max(0, start - 30):start], text[start:start + 30])


# ---- whitespace and paragraph breaks

def test_whitespace_after_a_sentence_belongs_to_it():
    text = "searches and seizures under the guise of law. This protection reaches all alike"
    assert sentences(text) == ["searches and seizures under the guise of law. ", "This protection reaches all alike"]
    # synthetic: every space and newline of the gap goes with the sentence before it
    assert sentences("under the guise of law.  \n The protection") == ["under the guise of law.  \n ", "The protection"]


def test_blank_line_always_ends_a_sentence():
    text = '18 U. S. C. § 1084. That statute provides in pertinent part:\n\n"(a) Whoever being engaged'
    assert sentences(text) == ["18 U. S. C. § 1084. ", "That statute provides in pertinent part:\n\n",
                               '"(a) Whoever being engaged']
    # synthetic: even after an abbreviation, and the whole whitespace run goes with the sentence before
    assert sentences("Cal.\n\nPen. Code") == ["Cal.\n\n", "Pen. Code"]
    assert sentences("Cal. \n\n\n Pen.") == ["Cal. \n\n\n ", "Pen."]
    # leading blank lines have no sentence to end
    assert sentences("\n\nCal. Pen.") == ["\n\nCal. Pen."]


def test_omission_rows_between_paragraphs():
    text = 'wooden locked gate . . . .\n\n. . . . .\n\n"Q. How high was that gate?'
    assert sentences(text) == ["wooden locked gate . . . .\n\n", ". . . . .\n\n", '"Q. How high was that gate?']


# ---- each part of T1.9's rule

def check(text: str, expected: list[str]) -> None:
    assert "".join(expected) == text, "the expected sentences must join back into the text"
    assert sentences(text) == expected


def test_us_reports():
    check("Wolf v. Colorado, 338 U. S. 25, 27; Stefanelli v. Minard, 342 U. S. 117, 119; Frank v. Maryland, "
          "359 U. S. 360, 362. Only two Terms ago",
          ["Wolf v. Colorado, 338 U. S. 25, 27; Stefanelli v. Minard, 342 U. S. 117, 119; Frank v. Maryland, "
           "359 U. S. 360, 362. ", "Only two Terms ago"])
    check("Present Law and Practice. In 1928 the U. S. Supreme Court decided that evidence",
          ["Present Law and Practice. ", "In 1928 the U. S. Supreme Court decided that evidence"])
    check("vacated by the Court of Appeals for the Tenth Circuit. U. S. West, Inc. v. FCC, 182 F. 3d 1224, "
          "1240 (1999). Notably, the carrier",
          ["vacated by the Court of Appeals for the Tenth Circuit. ",
           "U. S. West, Inc. v. FCC, 182 F. 3d 1224, 1240 (1999). ", "Notably, the carrier"])


def test_versus():
    check('"subversive of all the comforts of society." Entick v. Carrington, 19 How. St. Tr. 1029, 1066 (1765). '
          "And the Founders so decided",
          ['"subversive of all the comforts of society." ',
           "Entick v. Carrington, 19 How. St. Tr. 1029, 1066 (1765). ", "And the Founders so decided"])


def test_number_abbreviation():
    check("See Brief for Petitioner in No. 13–132, p. 20; Brief for Respondent in No. 13–212, p. 41. "
          "That is a sensible concession.",
          ["See Brief for Petitioner in No. 13–132, p. 20; Brief for Respondent in No. 13–212, p. 41. ",
           "That is a sensible concession."])
    check("The above figures relate to Case No. 493. In Nos. 532-533, the Government evidence fills 278 pages",
          ["The above figures relate to Case No. 493. ", "In Nos. 532-533, the Government evidence fills 278 pages"])
    check("United States v. Distillery No. Twenty-eight. In that case Judge Gresham adds",
          ["United States v. Distillery No. Twenty-eight. ", "In that case Judge Gresham adds"])


def test_initials():
    check("Carter, 525 U. S., at 97 (opinion of Scalia, J.). The Fourth Amendment, as relevant here",
          ["Carter, 525 U. S., at 97 (opinion of Scalia, J.). ", "The Fourth Amendment, as relevant here"])
    check("Atkinson v. John E. Doherty & Co., 121 Mich. 372; 80 N. W. 285; Jones v. Herald Post Co., 230 Ky. 227",
          ["Atkinson v. John E. Doherty & Co., 121 Mich. 372; 80 N. W. 285; Jones v. Herald Post Co., 230 Ky. 227"])
    check("by permitting broad searches of homes. M. Smith, The Writs of Assistance Case 475 (1978)",
          ["by permitting broad searches of homes. ", "M. Smith, The Writs of Assistance Case 475 (1978)"])
    check("During the Civil War General J. E. B. Stuart is reputed to have had",
          ["During the Civil War General J. E. B. Stuart is reputed to have had"])


def test_section_sign():
    check("terms of the Fourth Amendment. N. Y. Code Crim. Proc. § 793. If the Court wished",
          ["terms of the Fourth Amendment. ", "N. Y. Code Crim. Proc. § 793. ", "If the Court wished"])
    check("Md. Ann. Code, Art. 35, §§ 92, 93 (1957); Mass. Gen. Laws, c. 272, § 99 (Supp. 1966); Mich. Stat. Ann.",
          ["Md. Ann. Code, Art. 35, §§ 92, 93 (1957); Mass. Gen. Laws, c. 272, § 99 (Supp. 1966); Mich. Stat. Ann."])
    # a section number with a letter is not a number: in doubt, no split
    check("a Justice of the State Supreme Court, as provided by § 813-a. The order permitted",
          ["a Justice of the State Supreme Court, as provided by § 813-a. The order permitted"])


def test_reporter_and_code_abbreviations():
    for text in [
        "Cal. Pen. Code § 640; Colo. Rev. Stat. Ann. § 40-4-17 (1963); Conn. Gen. Stat. Rev. § 53-140 (1958);",
        'A More Than "Adequate" Nonfederal Ground, 61 Calif. L. Rev. 273 (1973); Project Report',
        "8 Harv. Civ. Rights-Civ. Lib. L. Rev. 271 (1973)",
        "Maine v. Thornton, No. CR82-10 (Me. Super. Ct., Apr. 16, 1982), App. to Pet. for Cert. in No. 82-1273",
        "made to employees (Treas. Reg. § 31.6001 et seq.), corporations to report",
        "Hanauer v. Doane, 12 Wall. 342, 349; Trist v. Child, 21 Wall. 441, 448; Meguire v. Corwine, 101 U. S. 108, 111;",
        "Kennett v. Chambers, 14 How. 38, 52; Marshall v. Baltimore & Ohio R. R. Co., 16 How. 314, 334;",
        "Pollard v. Roberts, 283 F. Supp. 248 (ED Ark.), aff'd per curiam, 393 U. S. 14 (1968)",
        "Early in the morning of May 1, 1981, a supervisor at the Minneapolis-St. Paul Airport Federal Express office",
        "Kugler & Strahilevitz, Actual Expectations of Privacy, Fourth Amendment Doctrine, and the Mosaic Theory, "
        "2015 S. Ct. Rev. 205, 261; Bradley, Two Models",
        "Yeager, Search, Seizure and the Positive Law: Expectations of Privacy Outside the Fourth Amendment, "
        "84 J. Crim. L. & C. 249, 251 (1993); Thomas, Time Travel",
    ]:
        check(text, [text])
    check('and the persons or things to be seized." U. S. Const., Amend. IV.',
          ['and the persons or things to be seized." ', "U. S. Const., Amend. IV."])


def test_numbers():
    check("between the Fourth and Fifth Amendments. Id., at 657. So also, the Court's insistence",
          ["between the Fourth and Fifth Amendments. ", "Id., at 657. ", "So also, the Court's insistence"])
    # a number after the stop does not start a sentence
    check("United States Servicemen's Fund v. Eastland, 159 U. S. App. D. C. 352. 488 F. 2d 1252 (1973).",
          ["United States Servicemen's Fund v. Eastland, 159 U. S. App. D. C. 352. 488 F. 2d 1252 (1973)."])
    check("Statutes of California 1862, p. 288, CCLXII. During the Civil War",  # a Roman numeral is no word
          ["Statutes of California 1862, p. 288, CCLXII. During the Civil War"])
    # a citation that is a whole sentence still ends at its number
    check("386 U. S. 954. The petition for certiorari also challenged",
          ["386 U. S. 954. ", "The petition for certiorari also challenged"])
    check("ty of infiltrating their organizations. P. 201. The Congress, though",
          ["ty of infiltrating their organizations. ", "P. 201. ", "The Congress, though"])


def test_list_and_section_numbers_label_what_follows():
    # a number that opens its sentence, or follows only a section or case label, does not end it
    for text in [
        "1. We hold there was no error in denying the inspection of the witnesses' memoranda.",
        '"SEC. 5. That in all suits and proceedings other than criminal arising',
        'APPENDIX "§ 2703. Required disclosure of customer communications or records',
        "No. 82-15. Acting on reports that marihuana was being raised on the farm",
    ]:
        check(text, [text])
    check('The questions presented in the petition for certiorari are:\n\n"1. Whether warrantless installation',
          ["The questions presented in the petition for certiorari are:\n\n", '"1. Whether warrantless installation'])
    check("the inspection of the witnesses' memoranda. The judge was clearly right",
          ["the inspection of the witnesses' memoranda. ", "The judge was clearly right"])


def test_quotations_closing_after_the_stop():
    check('the gist of the Fourth Amendment is "[t]he security of one\'s privacy against arbitrary intrusion by the '
          'police." Wolf v. Colorado, 338 U. S. 25, 27',
          ['the gist of the Fourth Amendment is "[t]he security of one\'s privacy against arbitrary intrusion by the '
           'police." ', "Wolf v. Colorado, 338 U. S. 25, 27"])
    check('the standards "should be much more stringent than those applied to search warrants." Id., at 408, 248',
          ['the standards "should be much more stringent than those applied to search warrants." ',
           "Id., at 408, 248"])
    # a citation (a number) after a nested quotation's lone closing mark is not a new sentence
    check("affirm that he 'knew it to be true at the time.' \" 3 Wigmore, Evidence (3d ed. 1940), § 747. "
          '"It follows from the nature',
          ["affirm that he 'knew it to be true at the time.' \" 3 Wigmore, Evidence (3d ed. 1940), § 747. ",
           '"It follows from the nature'])
    check('a time-stamped record known as cell-site location information (CSLI). The precision of this',
          ["a time-stamped record known as cell-site location information (CSLI). ", "The precision of this"])


def test_for_example():
    check("by an invalid subpoena, see, e. g. Hale v. Henkel, 201 U. S. 43, 76; Federal Trade Comm'n v. American",
          ["by an invalid subpoena, see, e. g. Hale v. Henkel, 201 U. S. 43, 76; Federal Trade Comm'n v. American"])


def test_supra_and_id():
    # "supra" is on the list (contract §4.A): no split after it, even where a sentence plainly ends
    check("Boyne City, G. & A. R. Co. v. Anderson, supra. See generally Annotation, Admissibility",
          ["Boyne City, G. & A. R. Co. v. Anderson, supra. See generally Annotation, Admissibility"])
    # "Ibid." is a short capitalised word: no split after it
    check('the essence of Lord Camden\'s judgment." Ibid. The Act—the Court found—violated',
          ['the essence of Lord Camden\'s judgment." ', "Ibid. The Act—the Court found—violated"])


def test_lowercase_abbreviations():
    for text in [
        "challenges of statutes on their face is present, cf. Thornhill v. Alabama, 310 U. S. 88, 98",
        'central to the Fourth Amendment," Ohio ex rel. Eaton v. Price, 364 U. S. 263, 272',
        "cert. denied sub nom. Williams v. United States, 461 U. S. 931 (1983)",
        "Metcalf v. Clark, 41 Barb. 45; Williams ads. Reed, 29 N. J. L. 385; Hill v. Goodrich, 32 Conn. 588;",
        "See also 18 U. S. C. § 2510 et seq. Since that time, electronic surveillance",
        "May, Constitutional History of England (2d ed.), vol. III, pp. 1-10.",
        'As amended L. 1958, c. 676, eff. July 1, 1958."',
        # the corpus has "Pet. for. Cert.": "Cert." never begins a sentence
        'over the course of 127 days," Pet. for. Cert. in Carpenter v. United States',
    ]:
        check(text, [text])


def test_capitalised_words():
    # five letters or more and not an abbreviation: a sentence ends
    check("upheld in Lewis and Hoffa. The argument of the plurality",
          ["upheld in Lewis and Hoffa. ", "The argument of the plurality"])
    check("MR. JUSTICE HOLMES and MR. JUSTICE BRANDEIS. I agree also",
          ["MR. JUSTICE HOLMES and MR. JUSTICE BRANDEIS. ", "I agree also"])
    # four letters or fewer: in doubt, no split
    check("at least without running afoul of Katz. But that result strikes most lawyers",
          ["at least without running afoul of Katz. But that result strikes most lawyers"])
    check("robbed nine different stores in Michigan and Ohio. The suspect identified",
          ["robbed nine different stores in Michigan and Ohio. The suspect identified"])


def test_ellipsis_rows_never_end_a_sentence_alone():
    check('the fairness of procedures . . . ." At 329, n. 7. There, two judges',
          ['the fairness of procedures . . . ." At 329, n. 7. ', "There, two judges"])
    check('(Okla. App. 1986) ("[C]urtilage . . . includes, among other things, garages',
          ['(Okla. App. 1986) ("[C]urtilage . . . includes, among other things, garages'])
    # synthetic
    check("at the time . . . . The next", ["at the time . . . . The next"])
    check("at the time. . . . The next", ["at the time. . . . The next"])
    check("at the time... The next", ["at the time... The next"])


def test_question_and_exclamation_marks():
    check("the particular search and seizure reasonable or not? We have just this Term held",
          ["the particular search and seizure reasonable or not? ", "We have just this Term held"])
    check('can be plugged into the back to take everything down. Have fun!" The advertised price is $18.95.',
          ["can be plugged into the back to take everything down. ", 'Have fun!" ', "The advertised price is $18.95."])
    # a capitalised word before "?" may end a title inside a citation: no split
    check("Colb, What Is a Search? Two Conceptual Flaws in Fourth Amendment Doctrine",
          ["Colb, What Is a Search? Two Conceptual Flaws in Fourth Amendment Doctrine"])
    check("escape the strictures of the Fourth Amendment? It seems obvious",
          ["escape the strictures of the Fourth Amendment? It seems obvious"])


def test_no_split_inside_a_parenthetical():
    text = hardest()["dunn-3-p10"]
    tail = text[text.index("State v. Lee, 120 Ore."):]
    assert "a barn. As construed" in tail
    check(tail, [tail])


def test_tokens_that_are_not_words_do_not_end_a_sentence():
    # synthetic: periods inside the token, and closing marks with no word in them
    for text in ["18 U.S.C. Next", 'the law ". The next', "the law (). The next"]:
        check(text, [text])


def test_a_single_lowercase_letter_is_an_abbreviation():
    check("as provided in clause b. The next", ["as provided in clause b. The next"])   # synthetic


def test_single_quotation_marks_open_a_sentence():
    check("whether expectations of privacy are legitimate. 'The premise that property interests control",
          ["whether expectations of privacy are legitimate. ", "'The premise that property interests control"])


def test_brackets_inside_a_word_are_alterations():
    check('In Texas, "computer . . . data" can constitute "[p]roperty." Tex. Penal Code Ann. §33.01(16)',
          ['In Texas, "computer . . . data" can constitute "[p]roperty." ', "Tex. Penal Code Ann. §33.01(16)"])


def test_brackets_pair_only_within_a_paragraph():
    # synthetic: an unclosed "(" does not pair with a ")" after a blank line
    check("See (a note.\n\nThe law. The next) end.", ["See (a note.\n\n", "The law. ", "The next) end."])


def test_dash_pieces_only_in_words():
    # the last piece of a hyphenated or dashed word is read; never of a token holding periods or digits
    check("about his cell phone's—meaning his own—movements. The police invade",
          ["about his cell phone's—meaning his own—movements. ", "The police invade"])
    for text in ["See Cal.-based. The", "See 1958-Smith. The"]:   # synthetic
        check(text, [text])


def test_curly_quotation_marks_decline():
    # synthetic: the corpus has straight marks only (P1.17); curly marks are neither closing nor opening
    for text in ["by the police.” Wolf v. Colorado", "the law. “The next", "the law. ‘The next", "the law.’ The next"]:
        check(text, [text])


def test_long_whitespace_runs_take_linear_time():
    cases = [
        (" " * 100_000 + "\n\n" + " " * 100_000, 1),
        (" " * 200_000 + "Next", 1),
        ("The law." + " " * 100_000 + "\n\n" + " " * 100_000 + "The end.", 2),
        ("The law." + " " * 200_000 + "The end.", 2),
    ]
    for text, expected in cases:
        start = time.perf_counter()
        spans = split_sentences(text)
        assert time.perf_counter() - start < 0.5
        assert_tiles(text, spans)
        assert len(spans) == expected


def test_the_next_sentence_must_open_with_a_capital():
    # synthetic: lowercase, digits and a lone quotation mark do not start a sentence
    for text in ["the law. the next", "the law. 3 id.", 'the law. " The next', "the law. (a) Whoever"]:
        check(text, [text])
    check('the law. "[T]he next', ["the law. ", '"[T]he next'])
    check("the law. (The next.)", ["the law. ", "(The next.)"])


# ---- the abbreviation list

def test_contract_examples_are_on_the_list():
    assert isinstance(LEGAL_ABBREVIATIONS, frozenset)
    assert {"U. S.", "How.", "Cal.", "Pen.", "Stat.", "supra", "e. g."} <= LEGAL_ABBREVIATIONS


@pytest.mark.parametrize("abbreviation", sorted(LEGAL_ABBREVIATIONS))
def test_no_split_after_any_listed_abbreviation(abbreviation):
    stop = "" if abbreviation.endswith(".") else "."
    for form in {abbreviation, abbreviation.upper(), abbreviation[0].upper() + abbreviation[1:]}:
        text = f"See the citation {form}{stop} The next words"  # synthetic
        check(text, [text])


def test_abbreviations_match_in_any_case():
    for text in ["U. S. CONST. AMEND. IV. X", "Cal. Const., amend. IV. Section", "para. Next", "Paras. Next"]:
        check(text, [text])   # synthetic
    # "no." is a word: only the capitalised "No." is an abbreviation (kyllo-1-p4)
    check("hence constitutional must be answered no. See Illinois v. Rodriguez",
          ["hence constitutional must be answered no. ", "See Illinois v. Rodriguez"])


def test_a_lowercase_word_matches_only_lowercase_abbreviations():
    # "me." is a word and "Me." is Maine; so with "app." ("App."), "wall." ("Wall.") and "pen." ("Pen.")
    check("that closes the matter for me. In interpreting the Bill of Rights",
          ["that closes the matter for me. ", "In interpreting the Bill of Rights"])
    check("and when he sets up a Google app. See supra, at 3–4. The prompt",
          ["and when he sets up a Google app. ", "See supra, at 3–4. ", "The prompt"])
    check("officers on the other side of the wall. On its facts",
          ["officers on the other side of the wall. ", "On its facts"])
    check('in another room—the "bull pen." The call numbers',
          ['in another room—the "bull pen." ', "The call numbers"])


# ---- the ten hardest passages (scripts/probe_chunking.py), each sentence's opening words checked by hand

HARDEST_EXPECTED = {
    "berger-1-n5": ["Ala. Code, Tit. 48, § 414 (1958); Alaska Stat."],
    "lopez-3-p16": [
        "The authority of the Boyd decision", "Its basic principle,", "Thus we have held", "Wolf v. Colorado,",
        "Only two Terms ago,", "Id., at 657.", "So also, the Court's insistence", "And see Poe v. Ullman,",
    ],
    "dunn-3-p10": ["The overwhelming majority of state courts", "See, e. g., Brown v. Oklahoma City,"],
    "goldman-3-n3": ["See Pavesich v. New England", "Cf. Henry v. Cherry & Webb,", "See also § 51 of the New York"],
    "carpenter-3-n10": ["Kugler & Strahilevitz,"],
    "olmstead-3-n16": ["See Hannay v. Eve,", "Compare Holman v. Johnson, 1 Cowp. 341."],
    "white-5-n17.3": ["See also Terry v. Ohio,"],
    "shultz-5-p10": [
        "Nor can I accept", "The First Amendment gives", "See NAACP v. Alabama,", "See also Lamont v. Postmaster",
        "It is certainly inconsistent", "The net result of this requirement,", "And, given the widespread",
        "The technique of examining bank accounts", "See, e. g., Pollard v. Roberts,",
    ],
    "lopez-3-n1": [
        "See Burgman v. United States,", '"The ground for receiving', "Boyne City, G. & A. R. Co. v. Anderson, supra.",
        "This is to be contrasted", '"The witness must be able', "The usual phrase requires",
        '"It follows from the nature', "In this respect it differs", "It is to be noted",
    ],
    "berger-5-p8": [
        "The Court's precipitate neglect", "Opinions of the state courts", "People v. Cohen, 42 Misc.",
        "The terms are frequently employed", "See, e. g., People v. Rogers,", "Further, a lower state court",
        "People v. Cohen, supra, at 407-408,", "Indeed, the court went on", "Id., at 408,", "Compare Siegel v. People,",
        "The court in Cohen", "New York's statutory requirements", "N. Y. Code Crim. Proc. § 793.",
        "If the Court wished",
    ],
}


def hardest() -> dict[str, str]:
    return {p["probe_id"]: p["text"] for p in json.loads(HARDEST.read_text())["passages"]}


def test_hardest_fixture_is_the_ten():
    assert set(hardest()) == set(HARDEST_EXPECTED)


@pytest.mark.parametrize("probe_id", sorted(HARDEST_EXPECTED))
def test_hardest_passages(probe_id):
    text = hardest()[probe_id]
    spans = split_sentences(text)
    assert_tiles(text, spans)
    got = [text[a:b] for a, b in spans]
    assert len(got) == len(HARDEST_EXPECTED[probe_id]), [s[:40] for s in got]
    for sentence, opening in zip(got, HARDEST_EXPECTED[probe_id]):
        assert sentence.startswith(opening), (sentence[:60], opening)


def test_hardest_total():
    assert sum(len(split_sentences(t)) for t in hardest().values()) == 50
