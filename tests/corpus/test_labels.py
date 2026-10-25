"""Section labels (contract §3, T1.6): the rule, and the list the main session reviews before the embedding."""

import sys
from pathlib import Path

import pytest

import os

from api.corpus.store import label_paragraphs, level, section_label_report, write_section_labels

ROOT = Path(__file__).resolve().parents[2]
LABELS_FILE = ROOT / "data" / "verification" / "sections" / "labels.txt"


def labels(*items):
    """items: ("S", heading) for a section row, ("T", text) for a paragraph, ("A", text) for an appendix paragraph."""
    seq = []
    for kind, text in items:
        seq.append(("section" if kind == "S" else {"T": "text", "A": "appendix", "Q": "quote"}[kind], text))
    return label_paragraphs(seq)


def test_numbered_headings_join_with_a_dash():
    got = labels(("T", "x"), ("S", "I."), ("T", "x"), ("S", "A"), ("T", "x"), ("S", "B"), ("T", "x"), ("S", "II"), ("T", "x"))
    assert got == [None, "I", "I-A", "I-B", "II"]


def test_trailing_periods_dropped_and_a_new_part_resets_the_subpart():
    got = labels(("S", "II."), ("S", "A."), ("T", "x"), ("S", "III."), ("T", "x"), ("S", "A."), ("T", "x"))
    assert got == ["II-A", "III", "III-A"]


def test_deeper_levels():
    got = labels(("S", "II"), ("S", "B"), ("S", "1"), ("T", "x"), ("S", "2"), ("T", "x"), ("S", "C"), ("S", "1"), ("T", "x"))
    assert got == ["II-B-1", "II-B-2", "II-C-1"]


def test_a_letter_heading_with_a_title_contributes_its_letter_only():
    got = labels(("S", "I"), ("S", "A. TITLE I—THE RECORDKEEPING REQUIREMENTS"), ("T", "x"),
                 ("S", "B. TITLE II—FOREIGN FINANCIAL TRANSACTION REPORTING REQUIREMENTS"), ("T", "x"),
                 ("S", "IV"), ("S", "D. PLAINTIFF ACLU'S FIRST AMENDMENT CHALLENGE"), ("T", "x"))
    assert got == ["I-A", "I-B", "IV-D"]


def test_omission_rows_and_separators_are_not_labels():
    got = labels(("S", ". . . . ."), ("T", "x"), ("S", "I"), ("T", "x"), ("S", "* * *"), ("T", "x"), ("S", "*"), ("T", "x"))
    assert got == [None, "I", "I", "I"]


def test_appendix_title_is_the_label_and_title_rows_inside_do_not_change_it():
    got = labels(("S", "II."), ("T", "x"), ("S", "APPENDIX TO OPINION OF MR. JUSTICE WHITE."), ("S", "A NATIONAL STRATEGY AGAINST ORGANIZED CRIME"),
                 ("A", "x"), ("S", "PROOF OF CRIMINAL VIOLATION"), ("A", "x"))
    assert got == ["II", "APPENDIX TO OPINION OF MR. JUSTICE WHITE.", "APPENDIX TO OPINION OF MR. JUSTICE WHITE."]


def test_two_appendices_and_letterhead_lines():
    got = labels(("S", "III"), ("T", "x"),
                 ("S", "APPENDIX I TO OPINION OF DOUGLAS, J., DISSENTING"), ("S", "THE WHITE HOUSE WASHINGTON"), ("S", "May 21, 1940"),
                 ("A", "x"), ("S", "APPENDIX II TO OPINION OF DOUGLAS, J., DISSENTING"), ("S", "June 30, 1965"), ("A", "x"))
    assert got == ["III", "APPENDIX I TO OPINION OF DOUGLAS, J., DISSENTING", "APPENDIX II TO OPINION OF DOUGLAS, J., DISSENTING"]


def test_an_appendix_without_a_title_row_is_labelled_appendix():
    got = labels(("S", "III"), ("T", "x"), ("S", "* * *"), ("T", "x"), ("A", "x"), ("A", "x"))
    assert got == ["III", "III", "Appendix", "Appendix"]


def test_label_is_none_before_the_first_heading():
    assert labels(("T", "x"), ("Q", "y")) == [None, None]


def test_level_matches_check_structure():
    scripts = str(ROOT / "scripts")
    sys.path.insert(0, scripts)
    try:
        import check_structure
    except Exception:
        pytest.skip("scripts/check_structure.py does not import here")
    finally:
        sys.path.remove(scripts)
    for s in ["I.", "II", "XII", "A", "B.", "D", "C", "1", "12.", "a", "* * *", "*", ". . . . .", "APPENDIX TO OPINION OF X, J.",
              "A. TITLE I—X", "May 21, 1940", "IV", "V", "X", "L"]:
        assert level(s) == check_structure.level(s), s


def test_real_corpus_labels(corpus):
    # Oliver's majority has its Part II (T1.5)
    oliver = {p.section for p in corpus.passages.values() if p.opinion_id == "oliver-1" and p.kind == "paragraph"}
    assert "II" in oliver and "III-A" in oliver
    kyllo = [p for p in corpus.passages.values() if p.opinion_id == "kyllo-2" and p.paragraph_kind == "appendix"]
    assert kyllo and all(p.section == "Appendix" for p in kyllo)
    first = corpus.passages["katz-1-p1"]
    assert first.section is None
    shultz = {p.section for p in corpus.passages.values() if p.opinion_id == "shultz-1"}
    assert {"I-A", "I-B", "I-C", "IV-A", "IV-D", "V"} <= shultz
    berger = {p.section for p in corpus.passages.values() if p.opinion_id == "berger-6"}
    assert "APPENDIX TO OPINION OF MR. JUSTICE WHITE." in berger


def test_footnote_takes_its_citing_paragraphs_label(corpus):
    for p in corpus.passages.values():
        if p.kind == "footnote":
            assert p.section == corpus.passages[p.cited_by[0]].section


def test_the_labels_report(corpus):
    text = section_label_report(corpus)
    if os.environ.get("PC_WRITE_LABELS") == "1":      # the review file is rewritten only on request
        write_section_labels(corpus, LABELS_FILE)
        assert LABELS_FILE.read_text(encoding="utf-8") == text
    lines = text.splitlines()
    assert any(l.startswith("katz-1") for l in lines)
    for oid in {p.opinion_id for p in corpus.passages.values()}:
        assert any(l.startswith(oid + " ") or l.startswith(oid + "\n") or l == oid for l in lines), oid
    # passages counted under labels add up
    import re
    total = 0
    for l in lines:
        m = re.match(r"\s+(.*?)\s+\((\d+)\)$", l)
        if m:
            total += int(m.group(2))
    assert total == len(corpus.passages)


def test_write_section_labels_writes_the_report(corpus, tmp_path):
    out = tmp_path / "deep" / "labels.txt"
    write_section_labels(corpus, out)
    assert out.read_text(encoding="utf-8") == section_label_report(corpus)
