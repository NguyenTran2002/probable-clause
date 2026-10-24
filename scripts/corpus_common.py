"""Shared pieces of the corpus builder: opinion headings, types, Justices' names.

Used by build_corpus.py (Lawbox HTML) and corpus_pdf.py (official PDFs).
"""

import html
import re
import unicodedata

# A heading names one or more Justices and ends at its role phrase, so a sentence
# in the body that merely mentions a Justice ("..., dissenting, stated ...") is
# not one.
JUSTICE = r"(?:MR\.?|ME\.)?\s*(?:CHIEF\s+)?JUSTICE\s+[A-Z][A-Za-z'’\-]+|THE\s+CHIEF\s+JUSTICE"
WHO = rf"(?P<who>(?:{JUSTICE})(?:(?:,? and |, )(?:{JUSTICE}))*)"
# "with whom MR. JUSTICE X joins" contains periods, so this clause may too.
WITH = r"(?P<with>,? (?:with whom|in which|while|after stating the (?:case|facts))[^:]{0,300}?)"
ROLE = (
    r"delivered the opinion of the Court"
    r"|announced the judgment of the Court(?: and (?:delivered )?an opinion)?(?:,? in which[^:]{0,250}?joins?)?"
    r"|(?:concurring|dissenting)(?:[^.:,]|, and ){0,60}?"
    r"|took no part in the consideration or decision of (?:this|these) cases?"
)
HEADING = re.compile(rf"^{WHO}{WITH}?,?\s*(?P<role>{ROLE})\s*[.:](?=\s|$)", re.I)
# A heading with no role ("MR. JUSTICE HOLMES:"); its type comes from ROLELESS.
BARE = re.compile(rf"^{WHO}:(?=\s|$)", re.I)
# A one-paragraph statement ("MR. JUSTICE BLACK, while adhering to ..., concurs
# in the judgment of the Court for the reasons set forth in ...").
STATEMENT = re.compile(rf"^{WHO}{WITH}?,?\s*(?P<role>concurs? in the (?:judgment|result)|dissents?)\b[^:]{{0,400}}\.$", re.I)
PER_CURIAM = re.compile(r"^PER CURIAM\.?(?=\s|$)", re.I)

# Headings that name no role, typed by reading the opinion; each is flagged for
# P1.1 verification against the official text and SCDB's vote counts.
ROLELESS = {
    ("olmstead", "Holmes"): "dissent",  # "I am not prepared to say ... I think it a less evil"
    ("goldman", "Stone"): "concurrence in the judgment",  # would overrule Olmstead, but do not dissent (P1.19)
}
# Statements written as a sentence about a Justice, not as a heading. Keyed by
# case and the statement's opening words.
STATEMENTS = {
    ("on_lee", "MR. JUSTICE BLACK believes"): "dissent",
}


def text_of(fragment: str) -> str:
    """Plain text of an HTML fragment. Also repairs Lawbox's encoding: its em
    dashes are the Windows-1252 byte 0x97 read as a Unicode control character,
    with a stray space beside it (the U.S. Reports set em dashes closed up)."""
    t = html.unescape(re.sub(r"<[^>]+>", "", fragment))
    t = re.sub(r"[ \t\n]*\x97[ \t\n]*", "\u2014", t)
    return unicodedata.normalize("NFC", re.sub(r"\s+", " ", t)).strip()


QUOTES = str.maketrans({"\u2018": "'", "\u2019": "'", "\u201a": "'", "\u201b": "'", "`": "'",
                        "\u201c": '"', "\u201d": '"', "\u201e": '"', "\u201f": '"'})

# A centered line that is a section marker: a Part numeral or letter, "* * *".
SECTION = re.compile(r"^(?:[IVXL]+(?:[–-][A-Z0-9]+)*\.?|[A-Z]\.?|\d{1,2}\.?|\([a-z0-9]{1,3}\)|\*(?: \*)*)$")


def straighten(text: str) -> str:
    """Quotation marks and apostrophes as straight ASCII (P1.17). One character
    for one, so recorded offsets stay valid."""
    return text.translate(QUOTES)


def joiners(who: str, with_clause: str | None, role: str) -> tuple[list[str], str | None]:
    """Justices joining an opinion, from its heading: the "with whom ... join"
    clause, or a plurality's "in which ... join". Partial joins are noted."""
    clause = (with_clause or "") + (" " + role if "in which" in role.lower() else "")
    names = [n for n in justices(clause) if n not in justices(who)]
    note = clause.strip(" ,") if re.search(r"\bas to\b|\bPart", clause) else None
    return names, note


def opinion_type(role: str) -> str:
    r = role.lower()
    if "took no part" in r:
        return "note"
    if "announced the judgment" in r:
        return "plurality"
    if "delivered the opinion" in r:
        return "majority"
    if "concurring in part" in r and "judgment" in r:
        return "concurrence in part and in the judgment"
    if "dissent" in r and "concur" in r:
        return "concurrence in part and dissent in part"
    if "dissent" in r:
        return "dissent"
    if "judgment" in r or "result" in r:
        return "concurrence in the judgment"
    if "concurring in part" in r:
        return "concurrence in part"
    return "concurrence"


def justices(s: str) -> list[str]:
    names = []
    for m in re.finditer(r"(THE CHIEF JUSTICE)|(?:CHIEF\s+)?JUSTICE\s+([A-Z][A-Za-z'’\-]+)", s, re.I):
        if m.group(1):
            names.append("The Chief Justice")
        else:
            name = m.group(2).replace("’", "'").title()
            names.append(re.sub(r"^Mc(.)", lambda x: "Mc" + x.group(1).upper(), name))
    return names
