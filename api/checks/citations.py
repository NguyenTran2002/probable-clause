"""The full-citation check (T1.12, P1.10): every full "X v. Y" case name and every U.S. Reports citation in the
answer must resolve to the corpus manifest, else it is "not in this corpus", never "does not exist".

Short names ("Katz") and short cites ("389 U. S., at 351") are not checked, and the page says so (T5.2).

How a name is read. Each " v. " in the text with a capitalised word on both sides is a candidate. The words on its
right are walked out over capitalised words, stopping at punctuation that ends a clause, a line, a dash, "and", a
lowercase word or a word that opens a sentence. The candidate resolves if a manifest case name fits it:
 - the right party must EQUAL the manifest's (so "Hester v. United States Postal Service" is not Hester);
 - the left party only has to END with the manifest's, whatever stands before it (so "In" or "See" before the name
   cannot hide a corpus case). Residual looseness, kept on purpose: "Whitfield Katz v. United States" resolves as
   Katz. A wrong left party before a right name that is exactly a corpus party cannot be told from a lead-in word.
The span shown for one that does not resolve is walked out the same way on the left.

A resolved full name immediately followed by a U.S. Reports citation that resolves only to other corpus cases
makes the citation "not in this corpus": as a pair it is not a corpus citation.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# GAP: tuning of the heuristics below, not in api/settings.py (T1.12 fixes no figure for names); placeholders.
_MAX_PARTY_TOKENS = 8       # most tokens walked into one party for display
_NEIGHBOUR_TOKENS = 12      # tokens looked at each side of " v. " when resolving: longer than any corpus party name

_REPORTER = re.compile(r"(?<![\w.])(\d{1,3})\s+U\.?\s?S\.?\s+(\d{1,4}|_{2,})(?!\w)")
_TOKEN = re.compile(r"--+|[—–]|(?:(?!--)[^\s—–])+")     # words; a dash stands apart and ends any name
_MANIFEST_REPORTER = re.compile(r"(\d{1,3})\s+U\.\s?S\.\s+(\d{1,4}|_{2,})")

_LEAD_CHARS = "*_\"“”‘’'([{"
_TRAIL_CHARS = "*_\"“”‘’')]},;:!?."
_OPENERS = "([{\"“‘'"
_CLAUSE_ENDS = ",;:)]}!?."

_ABBREVIATIONS = {"co", "corp", "inc", "ltd", "llc", "assn", "ass'n", "assoc", "bros", "dept", "dep't", "no", "mr",
                  "mrs", "ms", "dr", "jr", "sr", "st", "mt", "ft", "natl", "intl", "rel", "tel", "pub", "nat", "bd",
                  "mfg", "ins", "ry", "chem"}
_CONNECTORS = {"of", "the", "de", "la", "ex", "rel", "parte", "du", "von", "van", "der", "del", "&"}
# Capitalised words that open a sentence or a citation signal, never a party (display only).
_SIGNAL_WORDS = {"in", "under", "see", "cf", "compare", "and", "but", "the", "as", "also", "both", "like", "unlike",
                 "since", "with", "following", "thus", "after", "before", "similarly", "because", "although",
                 "while", "when", "whether", "where", "there", "this", "that", "here", "then", "for", "from", "of",
                 "at", "by", "to", "so", "if", "even", "only", "accord", "per", "citing", "applying", "reading",
                 "contrast", "consider", "contra", "accordingly", "indeed", "yet", "or", "nor", "e.g", "i.e"}
# Prose that can follow a name without punctuation: titles, and capitalised words that open a sentence.
_AFTER_A_NAME = {"chief", "justice", "justices", "judge", "judges", "i", "we", "it", "he", "she", "they", "this",
                 "that", "these", "those", "there", "here", "but", "and", "or", "then", "thus", "so", "yet", "see",
                 "cf", "compare", "however", "moreover", "indeed", "also", "in", "under", "on", "at", "by", "to",
                 "for", "from", "with", "as", "if", "when", "while", "since", "because", "although"}
_SUFFIXES = {"co", "company", "corp", "corporation", "inc", "incorporated", "ltd", "llc"}
_WORD_FORMS = {"assn": "association", "assoc": "association", "bros": "brothers", "dept": "department",
               "chem": "chemical"}      # "Ass'n" reaches "assn" once its apostrophe is gone
_V_TOKENS = {"v", "v.", "vs", "vs."}


@dataclass(frozen=True)
class _Token:
    start: int          # offsets of the whole token
    end: int
    lead: str
    core: str
    cstart: int         # offsets of the core (an abbreviation's period included)
    cend: int
    trail: str
    line_ends: bool = False     # a line break follows: a name does not run over it

    @property
    def ends_clause(self) -> bool:
        return self.line_ends or any(c in _CLAUSE_ENDS for c in self.trail)

    @property
    def low(self) -> str:
        return self.core.lower().rstrip(".")


@dataclass(frozen=True)
class Mention:
    start: int          # offsets into the joined answer
    end: int
    text: str
    kind: str           # "name" or "citation"
    resolved: bool


def _is_abbreviation(core: str) -> bool:
    return core.lower().replace("’", "'") in _ABBREVIATIONS or (len(core) == 1 and core.isupper()) or "." in core


def _tokens(text: str) -> list[_Token]:
    out = []
    found = list(_TOKEN.finditer(text))
    for n, m in enumerate(found):
        raw, a = m.group(), m.start()
        i = 0
        while i < len(raw) and raw[i] in _LEAD_CHARS:
            i += 1
        j = len(raw)
        while j > i and raw[j - 1] in _TRAIL_CHARS:
            j -= 1
        core = raw[i:j]
        if raw[j:j + 1] == "." and core and _is_abbreviation(core):
            j += 1                       # "Co." keeps its period; it does not end a clause
            core += "."
        line_ends = n + 1 < len(found) and "\n" in text[m.end():found[n + 1].start()]
        out.append(_Token(a, m.end(), raw[:i], core, a + i, a + j, raw[j:], line_ends))
    return out


def _is_name_word(t: _Token) -> bool:
    return bool(t.core) and t.core[0].isupper()


def _is_connector(t: _Token) -> bool:
    return t.low in _CONNECTORS


def _is_the_after_of(tokens: list[_Token], i: int, step: int) -> bool:
    """"the" belongs to a party only inside "of the" ("Department of the Treasury")."""
    j = i + step
    return 0 <= j < len(tokens) and tokens[j].low == "of"


def _is_v(t: _Token) -> bool:
    return t.core.lower() in _V_TOKENS


def _norm_words(core: str) -> list[str]:
    """A token as comparison words: lower case, no punctuation, possessive dropped, 'U.S.' as 'United States'."""
    if core.replace(".", "").upper() == "US" and (core == "US" or "." in core):
        return ["united", "states"]
    low = core.lower()
    if low.endswith("'s") or low.endswith("’s"):
        low = low[:-2]
    low = low.replace("'", "").replace("’", "")
    return [_WORD_FORMS.get(w, w) for w in re.findall(r"[^\W_]+", low)]


def _party(words: list[str]) -> list[str]:
    """A party's words without a trailing 'Co.', 'Inc.' and the like, which writers drop."""
    words = list(words)
    while words and words[-1] in _SUFFIXES:
        words.pop()
    return words


class Resolver:
    """The manifest's names and U.S. Reports citations (contract §3: the manifest the checks use)."""

    def __init__(self, manifest: dict):
        self.reporters: dict[tuple[int, int | None], set[int]] = {}    # citation -> the cases that carry it
        self.names: list[tuple[int, list[str], list[str]]] = []
        for index, case in enumerate(manifest.get("cases", [])):
            for m in _MANIFEST_REPORTER.finditer(case.get("citation", "") or ""):
                page = m.group(2)
                self.reporters.setdefault((int(m.group(1)), None if page.startswith("_") else int(page)), set()).add(index)
            name = case.get("name", "") or ""
            if " v. " in name:
                left, right = name.split(" v. ", 1)
                left_words = _party([w for t in _tokens(left) for w in _norm_words(t.core)])
                right_words = _party([w for t in _tokens(right) for w in _norm_words(t.core)])
                if left_words and right_words:
                    self.names.append((index, left_words, right_words))

    def reporter_cases(self, volume: int, page: int | None) -> set[int]:
        return self.reporters.get((volume, page), set())

    def name_cases(self, before: list[_Token], right: list[_Token], runs_into_a_name: bool) -> set[int]:
        """The corpus cases this name can be. The right party must equal the manifest's; if the words after
        the " v. " run straight into another name ("... United States Smith v. Maryland") a shorter right party is
        tried too. The left party only has to end with the manifest's."""
        left = _party([w for t in before for w in _norm_words(t.core)])
        words = _party([w for t in right for w in _norm_words(t.core)])
        found = set()
        for index, l, r in self.names:
            if len(left) < len(l) or left[-len(l):] != l:
                continue
            if words == r or (runs_into_a_name and words[:len(r)] == r and len(words) > len(r)):
                found.add(index)
        return found


def _walk_left(tokens: list[_Token], v: int) -> list[_Token]:
    out: list[_Token] = []
    i = v - 1
    while i >= 0 and len(out) < _MAX_PARTY_TOKENS:
        t = tokens[i]
        before_suffix = (t.trail.strip("*_") == "," and i + 1 < v and tokens[i + 1].low in _SUFFIXES)   # "Foo, Inc. v."
        if (t.ends_clause and not before_suffix) or not (_is_name_word(t) or _is_connector(t)):
            break
        if t.low == "the" and not t.core[0].isupper() and not _is_the_after_of(tokens, i, -1):
            break
        out.append(t)
        if any(c in _OPENERS for c in t.lead):
            break
        i -= 1
    out.reverse()
    return out


def _walk_right(tokens: list[_Token], v: int) -> tuple[list[_Token], bool]:
    """The right party's tokens, and whether the walk stopped at the " v. " of the next name."""
    out: list[_Token] = []
    j = v + 1
    if j >= len(tokens) or not _is_name_word(tokens[j]):
        return out, False
    at_next_name = False
    while j < len(tokens) and len(out) < _MAX_PARTY_TOKENS:
        t = tokens[j]
        if _is_v(t):
            at_next_name = True
            break
        if (j > v + 1 and t.low in _AFTER_A_NAME) or not (_is_name_word(t) or _is_connector(t)):
            break
        if t.low == "the" and not _is_the_after_of(tokens, j, -1) and j != v + 1:
            break
        out.append(t)
        if t.ends_clause:
            break
        j += 1
    while out and _is_connector(out[-1]) and not out[-1].ends_clause:
        out.pop()
    return out, at_next_name


def _display_left(tokens: list[_Token]) -> list[_Token]:
    """Without a leading connector or a capitalised signal word ("In", "See", "Compare")."""
    i = 0
    while i < len(tokens) and (_is_connector(tokens[i]) or tokens[i].low in _SIGNAL_WORDS):
        i += 1
    return tokens[i:]


_BETWEEN_NAME_AND_CITATION = re.compile(r"[\s*_,]*")


def find_mentions(text: str, resolver: Resolver) -> list[Mention]:
    """Every full case name and U.S. Reports citation in `text`, in order, resolved or not."""
    cites: list[tuple[Mention, set[int]]] = []
    for m in _REPORTER.finditer(text):
        page = m.group(2)
        cases = resolver.reporter_cases(int(m.group(1)), None if page.startswith("_") else int(page))
        cites.append((Mention(m.start(), m.end(), m.group(0), "citation", bool(cases)), cases))
    names: list[tuple[Mention, set[int]]] = []
    tokens = _tokens(text)
    for v, tok in enumerate(tokens):
        if not _is_v(tok):
            continue
        left = _walk_left(tokens, v)
        right, at_next_name = _walk_right(tokens, v)
        shown_left = _display_left(left)
        if not shown_left or not right or not _is_name_word(shown_left[-1]):
            continue
        before = tokens[max(0, v - _NEIGHBOUR_TOKENS):v]
        cases = resolver.name_cases(before, right, at_next_name)
        start, end = shown_left[0].cstart, right[-1].cend
        if right[-1].core.lower().endswith(("'s", "’s")):
            end -= 2
        names.append((Mention(start, end, text[start:end], "name", bool(cases)), cases))

    # A name and the citation right after it must be one case (T1.12 review).
    for name, name_cases in names:
        if not name.resolved:
            continue
        for k, (cite, cite_cases) in enumerate(cites):
            if cite.start >= name.end and cite.resolved and _BETWEEN_NAME_AND_CITATION.fullmatch(text[name.end:cite.start]):
                if name_cases.isdisjoint(cite_cases):
                    cites[k] = (Mention(cite.start, cite.end, cite.text, "citation", False), cite_cases)
                break
    mentions = [m for m, _ in names] + [m for m, _ in cites]
    mentions.sort(key=lambda m: (m.start, m.end))
    return mentions
