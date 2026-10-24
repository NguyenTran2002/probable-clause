"""P1.1 verification, the scripted part: every corpus paragraph against the official text.

For each case, every paragraph and footnote of the built corpus is located in
the official PDF's text (anchored on runs of 8 words, so where footnotes are
printed does not matter) and aligned word by word. Reported per case:
  - paragraphs not found in the official text at all;
  - every word-level difference, labelled by a third copy's reading where one
    exists (CourtListener's Harvard scan for the older cases, the Court's slip
    text for the newer ones):
      third-agrees-corpus        the official copy alone differs (likely OCR noise)
      third-agrees-official      the corpus alone differs (likely a corpus error)
      three-way                  all three differ
      no-third                   no third reading available
      ligature-restored          the corpus restored a letter the PDF font drops
      hyphenation-at-line-break  same letters, word divided differently, where the
                                 official copy breaks a line
      hyphenation-solid          same letters, where the official copy prints the
                                 word without a hyphen mid-line
  - pages: for the Lawbox cases, whose page breaks the build takes from the
    official PDF, every body word's page is checked against Harvard's own page
    markers (an independent source); for every case, each paragraph's first
    word is checked against the official PDF's page;
  - official text covered by no corpus paragraph, in runs of 15+ words
    (expected: syllabus, counsel, running heads; anything else is missing text).

Usage:
    uv run python scripts/verify_corpus.py [case_key ...]
Writes data/verification/text/<case>.json and prints a summary.
"""

import difflib
import html
import json
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from corpus_align import K, align, kgram_index, locate, norm_tokens, official_stream, token_offsets, word_pages  # noqa: E402

RAW = ROOT / "data" / "raw"
CASES = ROOT / "data" / "corpus" / "cases"
OUT = ROOT / "data" / "verification" / "text"
INTERRUPTION = 8  # official-only runs this long inside a paragraph are page furniture


def pdf_labels(case: dict, key: str) -> tuple[Path, list[int]]:
    pdfs = json.loads((RAW / "pdfs" / "manifest.json").read_text())
    pdf = RAW / "pdfs" / pdfs[key]["file"]
    from corpus_pdf import classify, read_pages
    pages = read_pages(pdf)
    if case["source"]["kind"] == "slip-opinion-pdf":
        _, info = classify(pages)
        labels, last = [], 1
        for m in info:
            last = m["label"] if m["label"] is not None else last
            labels.append(last)
        return pdf, labels
    first = int(pdfs[key]["file"].rsplit("-", 1)[-1].split(".")[0])
    return pdf, [first + i for i in range(len(pages))]


def opinions_of(key: str) -> list[dict]:
    idx = json.loads((RAW / "pull_index.json").read_text())
    cluster = json.loads((RAW / "clusters" / f"{idx[key]['cluster']}.json").read_text())
    return [json.loads((RAW / "opinions" / f"{u.rstrip('/').rsplit('/', 1)[-1]}.json").read_text())
            for u in cluster["sub_opinions"]]


def harvard(key: str) -> tuple[list[str], list[int | None]] | None:
    """Harvard's scan of the U.S. Reports: body words (footnotes left out, since
    Harvard prints them after the opinion) with the page each falls on, from
    Harvard's own page markers."""
    toks, pages = [], []
    for op in opinions_of(key):
        x = op.get("xml_harvard")
        if not x or op.get("type") == "010combined":
            continue
        x = re.sub(r"<footnote\b.*?</footnote>|<footnotemark>.*?</footnotemark>", " ", x, flags=re.S)
        labels = re.findall(r'<page-number[^>]*label="(\d+)"', x)
        page = int(labels[0]) - 1 if labels else None
        for part in re.split(r'(<page-number[^>]*label="\d+"[^>]*>.*?</page-number>)', x, flags=re.S):
            m = re.match(r'<page-number[^>]*label="(\d+)"', part)
            if m:
                page = int(m.group(1))
                continue
            for t in norm_tokens(html.unescape(re.sub(r"<[^>]+>", " ", part))):
                toks.append(t)
                pages.append(page)
    return (toks, pages) if toks else None


def third_copy(case: dict, key: str) -> list[str] | None:
    """An independent third reading: Harvard for Lawbox cases, else the slip text."""
    if case["source"]["kind"] == "courtlistener-lawbox":
        h = harvard_all(key)
        return h
    for op in opinions_of(key) if key in json.loads((RAW / "pull_index.json").read_text()) else []:
        if op.get("plain_text"):
            return norm_tokens(re.sub(r"(\w)-\s*\n\s*(\w)", r"\1\2", op["plain_text"]))
    return None


def harvard_all(key: str) -> list[str] | None:
    parts = []
    for op in opinions_of(key):
        if op.get("xml_harvard") and op.get("type") != "010combined":
            x = re.sub(r"<page-number[^>]*>.*?</page-number>|<footnotemark>.*?</footnotemark>", " ", op["xml_harvard"], flags=re.S)
            parts.append(html.unescape(re.sub(r"<[^>]+>", " ", x)))
    return norm_tokens(" ".join(parts)) if parts else None


def corpus_units(case: dict):
    for oi, op in enumerate(case["opinions"]):
        for pi, p in enumerate(op["paragraphs"]):
            if p.get("kind") == "section":
                continue
            yield {"where": f"op{oi}.p{pi}", "body": True, "text": p["text"],
                   "page_start": p["page_start"], "page_breaks": p.get("page_breaks", [])}
        for f in op["footnotes"]:
            breaks = f.get("page_breaks") or [[] for _ in f["paragraphs"]]
            starts = f.get("page_starts") or [f["page"]] * len(f["paragraphs"])
            for qi, t in enumerate(f["paragraphs"]):
                yield {"where": f"op{oi}.fn{f['label']}.{qi}", "body": False, "text": t,
                       "page_start": starts[qi], "page_breaks": breaks[qi] if qi < len(breaks) else []}


def corpus_word_pages(u: dict) -> list[int]:
    offs = token_offsets(u["text"])
    out, breaks = [], sorted(u["page_breaks"], key=lambda b: b["offset"])
    for o in offs:
        page = u["page_start"]
        for b in breaks:
            if b["offset"] <= o:
                page = b["page"]
        out.append(page)
    return out


def is_ligature_restoration(c: str, o: str) -> bool:
    """c is o with an "i" or "l" put back after an "f" (once or more)."""
    if len(c) <= len(o) or not o:
        return False
    return re.fullmatch(re.sub(r"f", "f[il]?", re.escape(o)), c) is not None


def verify(key: str) -> dict:
    case = json.loads((CASES / f"{key}.json").read_text())
    pdf, labels = pdf_labels(case, key)
    units = list(corpus_units(case))
    vocab = {t for u in units for t in norm_tokens(u["text"])}
    otoks, opages, obroken = official_stream(pdf, labels, vocab)
    oindex = kgram_index(otoks)
    third = third_copy(case, key)
    tindex = kgram_index(third) if third else None
    hv = harvard(key) if case["source"]["kind"] == "courtlistener-lawbox" else None
    hindex = kgram_index(hv[0]) if hv else None
    covered = [False] * len(otoks)

    aligned, not_found, diffs, page_issues, harvard_pages = 0, [], [], [], []
    interruptions, near, h_near = 0, 0, 0
    for u in units:
        ptoks = norm_tokens(u["text"])
        if not ptoks:
            continue
        hit = align(ptoks, otoks, oindex, near)
        if hit is None:
            not_found.append({"where": u["where"], "text": u["text"][:200]})
            continue
        base, sm = hit
        near = base
        aligned += 1
        window = otoks[base:base + len(sm.b)]
        for i in range(base, base + len(window)):
            covered[i] = True
        cpages = corpus_word_pages(u)
        opg = word_pages(ptoks, base, sm, opages)
        if opg[0] is not None and opg[0] != cpages[0]:
            page_issues.append({"where": u["where"], "corpus_page": cpages[0], "official_page": opg[0],
                                "text": u["text"][:80]})
        # Independent page check against Harvard's own markers (body text only).
        if hv and u["body"]:
            h = align(ptoks, hv[0], hindex, h_near)
            if h:
                h_near = h[0]
                hpg = word_pages(ptoks, h[0], h[1], hv[1])
                bad = [i for i, (a, b) in enumerate(zip(cpages, hpg)) if b is not None and a != b]
                if bad:
                    harvard_pages.append({"where": u["where"], "words_off": len(bad),
                                          "near": " ".join(ptoks[max(0, bad[0] - 3):bad[0] + 3]),
                                          "corpus": cpages[bad[0]], "harvard": hpg[bad[0]]})
        for tag, a0, a1, b0, b1 in sm.get_opcodes():
            if tag == "equal":
                continue
            c_seg, o_seg = ptoks[a0:a1], window[b0:b1]
            if tag == "insert" and len(o_seg) >= INTERRUPTION:
                interruptions += 1  # a running head or footnote printed inside the paragraph
                for i in range(base + b0, base + b1):
                    covered[i] = False
                continue
            if tag == "replace" and len(o_seg) >= INTERRUPTION and split_across(c_seg, o_seg):
                interruptions += 1  # a word broken across a page, furniture between
                continue
            ctx = " ".join(ptoks[max(0, a0 - 6):a1 + 6])
            if c_seg and o_seg and "".join(c_seg) == "".join(o_seg):
                at_break = any(i in obroken for i in range(base + b0, base + b1))
                diffs.append({"where": u["where"], "corpus": " ".join(c_seg), "official": " ".join(o_seg),
                              "third": None, "context": ctx,
                              "label": "hyphenation-at-line-break" if at_break else "hyphenation-solid"})
                continue
            if len(c_seg) == len(o_seg) and c_seg and all(is_ligature_restoration(c, o) or c == o for c, o in zip(c_seg, o_seg)):
                diffs.append({"where": u["where"], "corpus": " ".join(c_seg), "official": " ".join(o_seg),
                              "third": None, "context": ctx, "label": "ligature-restored"})
                continue
            label, t_seg = "no-third", None
            if tindex is not None:
                left = ptoks[max(0, a0 - K):a0]
                probe = left + c_seg + ptoks[a1:a1 + K]
                tpos = locate(probe, tindex) if len(probe) >= K else None
                if tpos is not None:
                    t_from = tpos + len(left)
                    for width in sorted({len(c_seg), len(o_seg)}):
                        cand = third[t_from:t_from + width]
                        if cand == c_seg:
                            label, t_seg = "third-agrees-corpus", cand
                            break
                        if cand == o_seg:
                            label, t_seg = "third-agrees-official", cand
                            break
                    else:
                        label, t_seg = "three-way", third[t_from:t_from + max(len(c_seg), len(o_seg), 1)]
            diffs.append({"where": u["where"], "corpus": " ".join(c_seg), "official": " ".join(o_seg),
                          "third": " ".join(t_seg) if t_seg is not None else None, "label": label, "context": ctx})

    uncovered, run = [], []
    for i, c in enumerate(covered + [True]):
        if not c and i < len(otoks):
            run.append(i)
        else:
            if len(run) >= 15:
                uncovered.append({"page": opages[run[0]], "words": len(run),
                                  "text": " ".join(otoks[run[0]:run[0] + 40])})
            run = []

    report = {
        "key": key, "units": len(units), "aligned": aligned, "not_found": not_found,
        "diffs": diffs, "diff_labels": dict(Counter(d["label"] for d in diffs)),
        "page_issues": page_issues, "harvard_page_issues": harvard_pages,
        "uncovered_official": uncovered, "interruptions": interruptions,
        "official_words": len(otoks), "official_words_covered": sum(covered), "third_copy": bool(third),
    }
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f"{key}.json").write_text(json.dumps(report, indent=1, ensure_ascii=False))
    return report


def split_across(c_seg: list[str], o_seg: list[str]) -> bool:
    """True if every corpus word appears in o_seg whole, or as two halves with
    other text between (a word hyphenated across a page break)."""
    sm = difflib.SequenceMatcher(None, c_seg, o_seg, autojunk=False)
    matched = {i for b in sm.get_matching_blocks() for i in range(b.a, b.a + b.size)}
    for i, tok in enumerate(c_seg):
        if i in matched:
            continue
        if not any(o_seg[x] and tok.startswith(o_seg[x]) and o_seg[x] + o_seg[y] == tok
                   for x in range(len(o_seg)) for y in range(x + 2, len(o_seg))):
            return False
    return True


def main() -> int:
    keys = sys.argv[1:] or sorted(p.stem for p in CASES.glob("*.json"))
    total = Counter()
    print(f"{'case':16} {'units':>5} {'missing':>7} {'diffs':>5} {'pg-off':>6} {'pg-harv':>7} {'uncov':>5}")
    for key in keys:
        r = verify(key)
        total.update(r["diff_labels"])
        print(f"{key:16} {r['units']:>5} {len(r['not_found']):>7} {len(r['diffs']):>5} {len(r['page_issues']):>6} "
              f"{len(r['harvard_page_issues']):>7} {len(r['uncovered_official']):>5}")
    print(dict(total), sum(total.values()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
