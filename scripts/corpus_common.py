"""Shared pieces of the corpus builder: opinion headings, types, Justices' names.

Used by build_corpus.py (Lawbox HTML) and corpus_pdf.py (official PDFs).
"""

import html
import re

# A heading names one or more Justices and ends at its role phrase, so a sentence
# in the body that merely mentions a Justice ("..., dissenting, stated ...") is
# not one.
JUSTICE = r"(?:MR\.?|ME\.)?\s*(?:CHIEF\s+)?JUSTICE\s+[A-Z][A-Za-z'’\-]+|THE\s+CHIEF\s+JUSTICE"
WHO = rf"(?P<who>(?:{JUSTICE})(?:(?:,? and |, )(?:{JUSTICE}))*)"
# "with whom MR. JUSTICE X joins" contains periods, so this clause may too.
WITH = r"(?P<with>,? (?:with whom|in which|while)[^:]{0,300}?)"
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
    ("goldman", "Stone"): "concurrence",  # would overrule Olmstead, but do not dissent
}
# Statements written as a sentence about a Justice, not as a heading. Keyed by
# case and the statement's opening words.
STATEMENTS = {
    ("on_lee", "MR. JUSTICE BLACK believes"): "dissent",
}


def text_of(fragment: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", "", fragment))).strip()


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
