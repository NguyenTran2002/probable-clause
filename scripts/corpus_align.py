"""Aligning corpus paragraphs with another copy of the same text, word by word.

Used by build_corpus.py (to take Lawbox page breaks from the official PDF) and
verify_corpus.py (to list every difference from the official text). Words are
compared lowercased, without punctuation.
"""

import difflib
import re
from collections import Counter, defaultdict
from pathlib import Path

K = 8  # words in an anchor run
LIG = {"ﬀ": "ff", "ﬁ": "fi", "ﬂ": "fl", "ﬃ": "ffi", "ﬄ": "ffl"}
TOKEN = re.compile(r"[a-z0-9]+")


def norm_tokens(text: str) -> list[str]:
    for k, v in LIG.items():
        text = text.replace(k, v)
    return TOKEN.findall(text.replace("­", "").lower())


def token_offsets(text: str) -> list[int]:
    """Character offset of each word norm_tokens() would return, for corpus text
    (which already has no ligature characters or soft hyphens)."""
    return [m.start() for m in TOKEN.finditer(text.lower())]


def official_stream(pdf: Path, labels: list[int], vocab: set) -> tuple[list[str], list[int], set]:
    """The official PDF's words in reading order, each with its page label, and
    the indices of words rejoined from a line-end hyphen. Read from word boxes,
    not poppler's plain text, which silently drops line-end hyphens. A broken
    word is rejoined without its hyphen when the joined form is one the corpus
    uses; otherwise the hyphen stays."""
    from corpus_pdf import read_pages
    flat = []
    for i, lines in enumerate(read_pages(pdf)):
        for line in lines:
            words = [w["t"] for w in line["words"]]
            for j, w in enumerate(words):
                flat.append((w, labels[i], j == len(words) - 1))
    toks, pages, broken = [], [], set()
    k = 0
    while k < len(flat):
        w, label, line_end = flat[k]
        if line_end and w.endswith(("-", "­")) and k + 1 < len(flat):
            joined = norm_tokens(w[:-1] + flat[k + 1][0])
            ts = joined if joined and all(t in vocab for t in joined) else norm_tokens(w[:-1] + "-" + flat[k + 1][0])
            for t in ts:
                broken.add(len(toks))
                toks.append(t)
                pages.append(label)
            k += 2
            continue
        for t in norm_tokens(w):
            toks.append(t)
            pages.append(label)
        k += 1
    return toks, pages, broken


def kgram_index(toks: list[str]) -> dict:
    idx = defaultdict(list)
    for i in range(len(toks) - K + 1):
        idx[tuple(toks[i:i + K])].append(i)
    return idx


def locate(ptoks: list[str], index: dict, near: int | None = None) -> int | None:
    """Start of a paragraph in a token stream.

    Each matching run of K words votes for an implied start. Runs that occur
    elsewhere too (a syllabus repeating the facts, a phrase used twice) give
    stray votes, so a candidate needs real support, and positions after the
    previous paragraph (`near`) are preferred. Text printed inside a paragraph
    (a running head, a footnote) shifts the implied start of everything after
    it, so the earliest well-supported start close to the best one wins."""
    votes = Counter()
    for j in range(0, max(1, len(ptoks) - K + 1)):
        for pos in index.get(tuple(ptoks[j:j + K]), ()):
            votes[pos - j] += 1
    if not votes:
        return None
    top = max(votes.values())
    strong = {v for v, c in votes.items() if c >= min(top, max(3, 0.2 * top))}
    if near is not None:
        forward = {v for v in strong if v >= near - 50}
        strong = forward or strong
    best = max(strong, key=lambda v: (votes[v], -v))
    return min(v for v in strong if best - 2 * len(ptoks) - 600 <= v <= best)


def fuzzy_near(ptoks: list[str], toks: list[str], near: int, reach: int = 1500) -> int | None:
    """Start of the closest match for a short paragraph near `near` (OCR may
    have changed a word), if at least 60% of its words match."""
    n, best, best_r = len(ptoks), None, 0.6
    for i in range(max(0, near - 50), min(len(toks) - n + 1, near + reach)):
        r = difflib.SequenceMatcher(None, ptoks, toks[i:i + n], autojunk=False).ratio()
        if r > best_r:
            best, best_r = i, r
    return best


def exact_near(ptoks: list[str], toks: list[str], near: int) -> int | None:
    """Start of an exact occurrence of a short paragraph, nearest to `near`."""
    n = len(ptoks)
    hits = [i for i in range(len(toks) - n + 1) if toks[i:i + n] == ptoks]
    return min(hits, key=lambda i: abs(i - near)) if hits else None


def align(ptoks: list[str], otoks: list[str], oindex: dict, near: int):
    """Align one paragraph's words with the stream. Returns (base, matcher) where
    the matcher compares ptoks with otoks[base:base + span], or None if the
    paragraph cannot be found."""
    if len(ptoks) >= K:
        start = locate(ptoks, oindex, near)
    else:
        start = exact_near(ptoks, otoks, near)
        start = start if start is not None else fuzzy_near(ptoks, otoks, near)
    if start is None:
        return None
    # Wide enough to span running heads and footnotes printed inside a paragraph.
    lo, hi = max(0, start - 20), min(len(otoks), start + 2 * len(ptoks) + 600)
    sm = difflib.SequenceMatcher(None, ptoks, otoks[lo:hi], autojunk=False)
    blocks = [b for b in sm.get_matching_blocks() if b.size]
    if not blocks:
        return None
    w0, w1 = blocks[0].b, blocks[-1].b + blocks[-1].size
    base = lo + w0
    return base, difflib.SequenceMatcher(None, ptoks, otoks[base:lo + w1], autojunk=False)


def word_pages(ptoks: list[str], base: int, sm, opages: list[int]) -> list[int | None]:
    """The official page of each corpus word that matched, else None."""
    out = [None] * len(ptoks)
    for b in sm.get_matching_blocks():
        for i in range(b.size):
            out[b.a + i] = opages[base + b.b + i]
    return out
