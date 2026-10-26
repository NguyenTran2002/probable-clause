"""The quotation check (T1.12): every quotation of QUOTATION_MIN_WORDS or more words must appear in the kept passages.

Allowed, and nothing more (T1.12): punctuation inside the closing quote mark; nested quotes changed between
double and single; ellipses for omitted words; bracketed alterations, including those already in the source; and
Markdown emphasis marks, which are not words (P4.48: "*Katz*" inside a quotation reads as "Katz").
A changed capital is a bracketed alteration ("[t]he"); an unbracketed one is not forgiven. A bracket may stand for
a few source words but never adds or removes a negation.

A quotation is a double-quoted span (straight or curly; the corpus is straight throughout, P1.17), a
multi-paragraph quotation by the legal convention (a paragraph that opens one without closing it, then a paragraph
that begins with a quotation mark), or a Markdown blockquote. A mark straight after a digit that opens nothing is an
inch mark. The text is the answer exactly as streamed, blocks joined with nothing between, so a quotation may open
in one block and close in another.

Matching is bounded: a quotation that cannot be decided within MATCH_STEP_BUDGET steps is not found (flagged).
"""

from __future__ import annotations

import re
from bisect import bisect_right
from dataclasses import dataclass

from api.settings import QUOTATION_BRACKET_MAX_SOURCE_WORDS, QUOTATION_MIN_WORDS

# GAP: not in api/settings.py. Steps (matches found, ends compared) one quotation may use across all kept passages
# before it counts as undecided. Measured: the 1,932 real quotations in the corpus use at most 26 steps
# each; 100,000 is about 4,000 times that and decides a contrived worst case in a fraction of a second.
MATCH_STEP_BUDGET = 100_000

_CURLY_DOUBLE = "“”„‟"
_CURLY_SINGLE = "‘’‚‛"
_TO_STRAIGHT = str.maketrans({**{c: '"' for c in _CURLY_DOUBLE}, **{c: "'" for c in _CURLY_SINGLE}})
_PARAGRAPH_BREAK = re.compile(r"\n[ \t\r]*\n")
_BLOCKQUOTE_MARK = re.compile(r"[ \t]*(?:>[ \t]?)+")
# An apostrophe inside a word stays, also beside a bracket: "[Carpenter]'s", "agent['s]". Any other single mark goes.
_NOT_INSIDE_A_WORD = re.compile(r"(?<![\w\[\]])'|'(?![\w\]])")
# Markdown emphasis (P4.48): every asterisk goes, and an underscore not inside a word ("supplemental_information"
# in a URL stays). From the source too, so star paging ("Commentaries *225") still matches.
_EMPHASIS = re.compile(r"\*+|(?<![^\W_])_+|_+(?![^\W_])")
_SPECIAL = re.compile(r"\[([^\[\]]*)\]|(?:\.\s*){3,4}|…")  # a bracket group, or an ellipsis
_ELLIPSIS_CONTENT = re.compile(r"[\s.…]*[.…][\s.…]*")
_TRAILING_PUNCTUATION = ".,"    # T1.12: punctuation inside the closing quote mark; American style puts only these two there

# A bracket may not add or remove a negation (T1.12 review). Words, and prefixes that negate the word they start.
_NEGATIONS = {"not", "no", "never", "nor", "none", "nothing", "neither", "without", "cannot",
              # the final review, Oct 25, 2026: these reverse a sentence just as well when an ellipsis drops them
              "nowhere", "nobody", "hardly", "scarcely", "barely", "absent"}
_NEGATING_PREFIXES = ("un", "in", "im", "il", "ir", "non", "dis")
_PREFIX_REMAINDER_MIN = 4       # "reasonable" and "unreasonable" pair up; "to" and "into" do not


@dataclass(frozen=True)
class Quotation:
    start: int      # offsets into the joined answer, from the first quoted word to the last (marks outside)
    end: int
    text: str       # the joined answer between start and end, exactly
    parts: tuple[str, ...]   # what is compared: one string, or one per paragraph of a multi-paragraph quotation


@dataclass(frozen=True)
class Boundary:
    """What lies between two pieces of a quotation in the source."""
    kind: str                       # "gap": an ellipsis, any run of words; "words": a bracket standing for a few words
    literal: str | None = None      # a bracket's own words, as a source that has the bracket already has them
    allowed: int = 0                # source words a "words" boundary may stand for


@dataclass(frozen=True)
class Piece:
    pattern: re.Pattern
    needles: tuple[str, ...]        # literal runs the source must contain, checked before the pattern is run


@dataclass(frozen=True)
class CompiledQuotation:
    words: int                              # words as Claude wrote them, ellipses excluded
    pieces: tuple[Piece, ...]               # in order, each found over a prepared source; empty: nothing to check
    boundaries: tuple[Boundary, ...]        # one fewer than the pieces


# --- finding quotations in the answer

def find_quotations(text: str) -> list[Quotation]:
    """Quotations of the joined answer. A blank line ends the pairing, unless the paragraph after it begins with a
    quotation mark and the one before left a quotation open (the legal convention for a long quotation)."""
    found: list[Quotation] = []
    bounds = []
    position = 0
    for m in _PARAGRAPH_BREAK.finditer(text):
        bounds.append((position, m.start()))
        position = m.end()
    bounds.append((position, len(text)))
    carry = None
    for p0, p1 in bounds:
        block = _blockquote(text, p0, p1)
        if block:
            found.append(block)
            carry = None
        else:
            carry = _scan(text, p0, p1, carry, found)
    return found


def _blockquote(text: str, p0: int, p1: int) -> Quotation | None:
    """A paragraph all of whose lines begin with ">" is one quotation, without the markers."""
    pieces = []
    offset = p0
    for line in text[p0:p1].split("\n"):
        m = _BLOCKQUOTE_MARK.match(line)
        if not m:
            return None
        body = line[m.end():]
        lead = len(body) - len(body.lstrip())
        if body.strip():
            pieces.append((offset + m.end() + lead, offset + m.end() + len(body.rstrip())))
        offset += len(line) + 1
    if not pieces:
        return None
    start, end = pieces[0][0], pieces[-1][1]
    return Quotation(start, end, text[start:end], (" ".join(text[s:e] for s, e in pieces),))


def _scan(text: str, p0: int, p1: int, carry, found: list[Quotation]):
    """Pair the marks of one paragraph. Returns the segments of a quotation still open at its end, else None."""
    para = text[p0:p1]
    segments: list[tuple[int, int]] = []
    opened: int | None = None
    nested = 0
    first = 0
    if carry is not None:
        lead = len(para) - len(para.lstrip())
        if para[lead:lead + 1] in ('"', "“"):
            segments, opened, first = list(carry), lead + 1, lead + 1
    for i in range(first, len(para)):
        ch = para[i]
        if ch == "“":
            if opened is None:
                opened, nested, segments = i + 1, 0, []
            else:
                nested += 1
        elif ch == "”":
            if opened is not None:
                if nested:
                    nested -= 1
                else:
                    segments.append((p0 + opened, p0 + i))
                    _emit(found, text, segments)
                    opened, segments = None, []
        elif ch == '"':
            if opened is None:
                if i and para[i - 1].isdigit():
                    continue            # 5" tall: an inch mark opens nothing
                opened, nested, segments = i + 1, 0, []
            else:
                segments.append((p0 + opened, p0 + i))
                _emit(found, text, segments)
                opened, nested, segments = None, 0, []
    if opened is None:
        return None
    return segments + [(p0 + opened, p1)]


def _emit(found: list[Quotation], text: str, segments: list[tuple[int, int]]):
    kept = []
    for s, e in segments:
        inner = text[s:e]
        s += len(inner) - len(inner.lstrip())
        e -= len(inner) - len(inner.rstrip())
        if e > s:
            kept.append((s, e))
    if kept:
        start, end = kept[0][0], kept[-1][1]
        found.append(Quotation(start, end, text[start:end], tuple(text[s:e] for s, e in kept)))


# --- the quotation as comparison patterns

def _strip_marks(s: str) -> str:
    """Curly to straight, then every double mark and every single mark that is not an apostrophe inside a
    word goes, and so do Markdown emphasis marks (P4.48). Applied to the quotation and to the source alike, so
    nested quotes may change (T1.12)."""
    s = _EMPHASIS.sub("", s.translate(_TO_STRAIGHT).replace('"', ""))
    return _NOT_INSIDE_A_WORD.sub("", s)


def prepare_source(text: str) -> str:
    """A kept passage as the comparison sees it: marks stripped, brackets already in the source dropped
    (their content stays), whitespace collapsed, lower-cased (P4.17: the comparison ignores letter case; the
    answer keeps the quotation as written)."""
    s = _strip_marks(text.replace("[", "").replace("]", ""))
    return re.sub(r"\s+", " ", s).strip().lower()


def _parse(s: str):
    """Split a mark-stripped quotation into ("t", text), ("b", bracket content) and ("e", None) segments."""
    segments: list[tuple[str, str | None]] = []
    pos = 0

    def add_text(t):
        if t:
            if segments and segments[-1][0] == "t":
                segments[-1] = ("t", segments[-1][1] + t)
            else:
                segments.append(("t", t))

    for m in _SPECIAL.finditer(s):
        add_text(s[pos:m.start()])
        pos = m.end()
        if m.group(0).startswith("["):
            content = m.group(1)
            if _ELLIPSIS_CONTENT.fullmatch(content):
                segments.append(("e", None))
            elif content.strip():
                segments.append(("b", content.strip()))
            # an empty bracket, "assure[ ]", leaves nothing behind
        else:
            segments.append(("e", None))
    add_text(s[pos:])
    return segments


def _spaced(s: str) -> str:
    return " ".join(re.escape(w) for w in s.split(" "))


def _meaningful(group) -> bool:
    return any(kind == "t" and any(c.isalnum() for c in value) for kind, value in group)


def _trim(group):
    items = [list(x) for x in group]
    if items and items[0][0] == "t":
        items[0][1] = items[0][1].lstrip()
    if items and items[-1][0] == "t":
        items[-1][1] = items[-1][1].rstrip()
    return [tuple(x) for x in items if not (x[0] == "t" and not x[1])]


def _merge(a: Boundary | None, b: Boundary) -> Boundary:
    if a is None:
        return b
    if a.kind == "gap" or b.kind == "gap":
        return Boundary("gap")
    return Boundary("words", " ".join(x for x in (a.literal, b.literal) if x), a.allowed + b.allowed)


def _plain(word: str) -> str:
    return re.sub(r"^[^\w]+|[^\w]+$", "", word.lower())


def _negated(words) -> bool:
    """A negation word in an ellipsis's gap. A piece never starts right after a negating prefix and its hyphen
    (`_to_pattern`), so "non-" cannot be dropped that way; a gap holding a whole prefixed word ("non-intrusive",
    "unreasonable") is allowed, as an ellipsis omits whole words."""
    return any(w in _NEGATIONS or w.endswith("n't") for w in map(_plain, words))


def _prefix_pair(a_words, b_words) -> bool:
    """"unreasonable" (or "non-intrusive") in one and "reasonable" (or "intrusive") in the other: a bracket that
    strips or adds a negating prefix."""
    for a in map(_plain, a_words):
        for b in map(_plain, b_words):
            for p in _NEGATING_PREFIXES:
                if ((a in (p + b, p + "-" + b) and len(b) >= _PREFIX_REMAINDER_MIN)
                        or (b in (p + a, p + "-" + a) and len(a) >= _PREFIX_REMAINDER_MIN)):
                    return True
    return False


def _changes_meaning(replaced: list[str], bracket: list[str]) -> bool:
    return _negated(replaced) != _negated(bracket) or _prefix_pair(replaced, bracket)


def _negating_letters(content: str) -> bool:
    """Bracketed letters inside a word that carry a negation: "[un]", "do[n't]"."""
    low = content.lower().strip()
    return low in _NEGATING_PREFIXES or _negated(low.split())


def count_words(inner: str) -> int:
    s = re.sub(r"\s+", " ", _strip_marks(inner)).strip()
    flat = "".join(" " if kind == "e" else value for kind, value in _parse(s))
    return sum(1 for w in flat.split() if any(c.isalnum() for c in w))


def compile_quotation(inner: str) -> CompiledQuotation:
    """The quotation as ordered pieces with what may lie between them. `pieces` is empty if no source word is left
    to check (a quotation made of brackets alone). Lower-cased, like the sources (P4.17)."""
    s = re.sub(r"\s+", " ", _strip_marks(inner)).strip().lower()
    segments = _parse(s)

    flat = "".join(" " if kind == "e" else value for kind, value in segments)
    words = sum(1 for w in flat.split() if any(c.isalnum() for c in w))
    allowed = int(QUOTATION_BRACKET_MAX_SOURCE_WORDS.value)

    groups: list[list[tuple[str, str]]] = []
    boundaries: list[Boundary] = []
    pending: Boundary | None = None
    current: list[tuple[str, str]] = []

    def close(boundary: Boundary | None):
        nonlocal current, pending
        group, current = _trim(current), []
        if _meaningful(group):
            if groups:
                boundaries.append(pending or Boundary("gap"))
            groups.append(group)
            pending = boundary
        elif boundary is not None and groups:
            pending = _merge(pending, boundary)    # leading and trailing ones say nothing worth checking

    for i, (kind, value) in enumerate(segments):
        if kind == "t":
            current.append(("t", value))
        elif kind == "e":
            close(Boundary("gap"))
        else:
            before = segments[i - 1] if i else None
            after = segments[i + 1] if i + 1 < len(segments) else None
            attached = bool(before and before[0] == "t" and before[1][-1].isalnum()) or \
                bool(after and after[0] == "t" and after[1][0].isalnum())
            if attached:     # an alteration inside a word: "[t]he", "exercis[ing]"
                current.append(("r" if _negating_letters(value) else "o", value))
            else:            # whole words: "[the defendant]"
                close(Boundary("words", " ".join(value.split()), allowed))
    close(None)

    while groups:
        groups[-1] = _trim(_drop_closing_punctuation(groups[-1]))
        if _meaningful(groups[-1]):
            break
        groups.pop()
        if boundaries:
            boundaries.pop()
    if not groups:
        return CompiledQuotation(words, (), ())
    return CompiledQuotation(words, tuple(_to_pattern(g) for g in groups), tuple(boundaries))


def _drop_closing_punctuation(group):
    items = list(group)
    if items and items[-1][0] == "t":
        stripped = items[-1][1].rstrip(_TRAILING_PUNCTUATION).rstrip()
        items[-1] = ("t", stripped)
        if not stripped:
            items.pop()
    return items


def _to_pattern(group) -> Piece:
    parts = []
    for kind, value in group:
        if kind == "t":
            parts.append(_spaced(value))
        elif kind == "o":    # the bracketed letters, in either case, or nothing of them
            parts.append("(?:(?i:" + _spaced(" ".join(value.split())) + "))?")
        else:                # "r": letters that carry a negation must be there, as the source has them
            parts.append("(?i:" + _spaced(" ".join(value.split())) + ")")
    first = group[0][1][0]
    last = group[-1][1][-1]
    # never right after a negating prefix and its hyphen: "intrusive" quoted out of "non-intrusive" reverses it
    start = (r"(?<![\w'])" + "".join(rf"(?<!\b(?i:{p})-)" for p in _NEGATING_PREFIXES)) if first.isalnum() else ""
    end = r"(?![\w'])" if last.isalnum() else ""
    pattern = re.compile("(?=(" + start + "".join(parts) + end + "))")    # lookahead: every start, overlapping too
    return Piece(pattern, tuple(value for kind, value in group if kind == "t"))


# --- matching, bounded

class _Undecided(Exception):
    """The step budget ran out. The quotation is then treated as not found."""


class _Budget:
    def __init__(self, steps: int):
        self.left = steps

    def spend(self, n: int):
        self.left -= n
        if self.left < 0:
            raise _Undecided


def _gap_ok(boundary: Boundary, gap: str) -> bool:
    if boundary.kind == "gap":
        return True
    words = gap.split()
    if boundary.literal is not None and " ".join(words) == boundary.literal:
        return True                                  # the bracket's own words, copied from the source
    if len(words) > boundary.allowed:
        return False
    return not _changes_meaning(words, (boundary.literal or "").split())


def _reached(boundary: Boundary, ends: list[int], source: str, start: int, budget: _Budget) -> bool:
    """Does an earlier piece end where `boundary` allows a piece to start at `start`? `ends` is sorted."""
    i = bisect_right(ends, start)
    if boundary.kind == "gap":
        # An ellipsis matches the smallest gap, after the latest earlier end; every larger gap holds it, so a
        # negation there fails every reading: ". . ." never drops a "not" (contract v1.4).
        if not i:
            return False
        budget.spend(1)
        return not _negated(source[ends[i - 1]:start].split())
    literal = len(boundary.literal or "")
    while i:
        budget.spend(1)
        i -= 1
        gap = source[ends[i]:start]
        if _gap_ok(boundary, gap):
            return True
        if len(gap) > literal + 2 and len(gap.split()) > boundary.allowed:
            break    # ends farther back only widen the gap
    return False


class Matches:
    """Every match of a piece in a source, found once: sorted starts and their ends."""

    def __init__(self, piece: Piece, source: str):
        found = []
        if all(needle in source for needle in piece.needles):
            found = [(m.start(1), m.end(1)) for m in piece.pattern.finditer(source)]
        self.starts = [s for s, _ in found]
        self.ends = [e for _, e in found]

    def __len__(self):
        return len(self.starts)


def _chain(compiled: CompiledQuotation, source: str, matches_of, budget: _Budget) -> bool:
    """The pieces in order, each starting where the boundary before it allows. Every match of every piece is
    considered, so a repetitive passage cannot send the search into backtracking."""
    ends: list[int] = []
    for k, piece in enumerate(compiled.pieces):
        matches = matches_of(piece)
        budget.spend(1)
        if not len(matches):
            return False
        if k == 0:
            ends = sorted(set(matches.ends))
            continue
        boundary = compiled.boundaries[k - 1]
        ends = sorted({e for s, e in zip(matches.starts, matches.ends)
                       if _reached(boundary, ends, source, s, budget)})
        if not ends:
            return False
    return True


def quotation_in(compiled: CompiledQuotation, prepared_sources: list[str], cache: dict | None = None,
                 budget: _Budget | None = None) -> bool:
    """True if the quotation occurs inside one kept passage. An ellipsis does not bridge two passages. A quotation
    the budget cannot decide is not found."""
    if not compiled.pieces:
        return True
    cache = {} if cache is None else cache
    budget = budget or _Budget(MATCH_STEP_BUDGET)
    try:
        for index, source in enumerate(prepared_sources):
            def matches_of(piece, index=index, source=source):
                key = (index, piece.pattern.pattern)
                if key not in cache:
                    cache[key] = Matches(piece, source)
                    budget.spend(len(cache[key]))
                return cache[key]
            if _chain(compiled, source, matches_of, budget):
                return True
    except _Undecided:
        return False
    return False


def check_quotation(q: Quotation, prepared_sources: list[str], cache: dict | None = None) -> tuple[bool, bool]:
    """(counted, found): counted if the quotation has QUOTATION_MIN_WORDS or more words and a source word to check;
    found if every part is in a kept passage."""
    compiled = [compile_quotation(part) for part in q.parts]
    if sum(c.words for c in compiled) < min_words() or not any(c.pieces for c in compiled):
        return False, False
    budget = _Budget(MATCH_STEP_BUDGET)
    cache = {} if cache is None else cache
    return True, all(quotation_in(c, prepared_sources, cache, budget) for c in compiled)


def min_words() -> int:
    return int(QUOTATION_MIN_WORDS.value)
