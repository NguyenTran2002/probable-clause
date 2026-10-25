"""embedded_text: one header line, then the text (T3.6, contract §4.C)."""

from api.search.meaning import embedded_text
from tests.search.support import make_passage


def test_header_then_text():
    p = make_passage(1, text="The Fourth Amendment protects people, not places.")
    assert embedded_text(p) == (
        "Katz v. United States (1967), majority, Stewart\nThe Fourth Amendment protects people, not places."
    )


def test_per_curiam_when_no_authors():
    p = make_passage(1, authors=(), opinion_type="per curiam")
    assert embedded_text(p).split("\n")[0] == "Katz v. United States (1967), per curiam, per curiam"


def test_several_authors_and_the_section():
    p = make_passage(1, authors=("Scalia", "Thomas"), opinion_type="concurrence in the judgment", section="III-A")
    assert embedded_text(p).split("\n")[0] == (
        "Katz v. United States (1967), concurrence in the judgment, Scalia and Thomas, Part III-A"
    )


def test_no_section_means_no_part():
    assert ", Part" not in embedded_text(make_passage(1, section=None))


def test_year_comes_from_the_decision_date_text_not_a_timestamp():
    p = make_passage(1, decided="2018-06-22")
    assert "(2018)" in embedded_text(p)


def test_footnote_text_is_embedded_whole():
    p = make_passage(1, kind="footnote", text="One.\n\nTwo.", footnote_label="3", paragraph_kind=None)
    assert embedded_text(p).endswith("\nOne.\n\nTwo.")


def test_numbered_labels_get_part():
    for label in ("I", "III-A", "II-B-1"):
        assert embedded_text(make_passage(1, section=label)).split("\n")[0].endswith(f", Part {label}")


def test_appendix_labels_stand_without_part():
    for label in ("Appendix", "APPENDIX TO OPINION OF MR. JUSTICE WHITE.", "APPENDIX I TO OPINION OF DOUGLAS, J., DISSENTING"):
        header = embedded_text(make_passage(1, section=label)).split("\n")[0]
        assert header == f"Katz v. United States (1967), majority, Stewart, {label}"
        assert "Part" not in header
