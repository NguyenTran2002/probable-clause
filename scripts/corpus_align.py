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


RUNNING_HEAD = re.compile(
    r"^(\d{1,4}|october term,? \d{4}\.?|opinion of the court\.?|syllabus\.?|per curiam\.?|cite as:.*"
    r"|\d{1,3} u\. ?s\.?.*|.*\bv\. .*\.?|.*\bj\., (dissenting|concurring).*|.*\bdissenting\.?|.*\bconcurring.*"
    r"|argument for .*|statement of the case\.?|appendix.*|[\d-]+ o-[\d-]+)$", re.I)


def page_regions(lines: list[dict]) -> list[str]:
    """Each line's region: "head" (running heads at the top of the page, which
    scans set in body type, so size alone cannot tell), "body" or "foot"."""
    out, top = [], lines[0]["y0"] if lines else 0
    for i, l in enumerate(lines):
        text = " ".join(w["t"] for w in l["words"]).strip()
        if l.get("kind") == "header" or (i < 5 and l["y0"] <= top + 40 and RUNNING_HEAD.match(text)):
            out.append("head")
        else:
            out.append("foot" if l.get("kind") == "foot" else "body")
    return out


def official_stream(pdf: Path, labels: list[int], vocab: set, region: str | None = None):
    """The official PDF's words in reading order. Returns tokens, each token's page
    label, the indices of tokens rejoined from a line-end hyphen, the punctuation
    after each token, and each token's raw printed word with its span in it.

    `region` limits the stream to "body" (running heads dropped) or "foot". Read
    from word boxes, not poppler's plain text, which silently drops line-end
    hyphens. A broken word is rejoined without its hyphen when the joined form is
    a known word; otherwise the hyphen stays."""
    from corpus_pdf import classify, read_pages
    pages = read_pages(pdf)
    classify(pages)
    flat = []
    for i, lines in enumerate(pages):
        regions = page_regions(lines)
        for line, reg in zip(lines, regions):
            if reg == "head" or (region and reg != region):
                continue
            words = [w["t"] for w in line["words"]]
            for j, w in enumerate(words):
                flat.append((w, labels[i], j == len(words) - 1))
    toks, pages_out, broken, after, raw = [], [], set(), [], []

    def add(word: str, label: int, from_break: bool):
        low = word.replace("\u00ad", "").lower()
        for k, v in LIG.items():
            low = low.replace(k, v)
        clean = word.replace("\u00ad", "")
        for k, v in LIG.items():
            clean = clean.replace(k, v)
        ms = list(TOKEN.finditer(low))
        if not ms:
            if after:
                after[-1] += low
            return
        if after:
            after[-1] += low[:ms[0].start()]
        for n, m in enumerate(ms):
            if from_break:
                broken.add(len(toks))
            toks.append(m.group(0))
            pages_out.append(label)
            after.append(low[m.end():ms[n + 1].start()] if n + 1 < len(ms) else low[m.end():])
            raw.append((clean, m.start(), m.end()))

    k = 0
    while k < len(flat):
        w, label, line_end = flat[k]
        if line_end and w.endswith(("-", "\u00ad")) and k + 1 < len(flat):
            joined = norm_tokens(w[:-1] + flat[k + 1][0])
            add(w[:-1] + flat[k + 1][0] if joined and all(t in vocab for t in joined) else w[:-1] + "-" + flat[k + 1][0],
                label, True)
            k += 2
            continue
        add(w, label, False)
        k += 1
    return toks, pages_out, broken, after, raw


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
