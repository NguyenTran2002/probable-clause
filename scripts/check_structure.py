"""Structure check: section headings and footnote markers against the raw sources.

Phase 1's word-by-word check (verify_corpus.py) skips section headings and does
not look at footnote marker positions. Phase 3 gives both a job (a section label
in each passage's header; footnotes attached inside the passage that cites them),
so this checks them, read only. Nothing in the corpus is changed.

For each case, every raw copy CourtListener holds is parsed into blocks (the
Lawbox HTML, the `html` copy, Harvard's scan, the slip text's HTML). Each corpus
paragraph is matched to a source block by its opening words. Then, per matched
paragraph:
  - headings: the headings printed just before it in the corpus against the
    heading-like blocks just before it in the source (count, then label);
  - footnote markers: each marker's label and the word just before it, in the
    corpus (`footnote_refs`) against the source's markers in that block.
Plus the corpus's own consistency: every heading sequence well formed (I, II,
III; A, B under each), every marker's footnote present, every footnote cited
(or listed), every marker at the end of a word.

A difference is a candidate for review, not a verdict: Lawbox is known to drop
Part numerals (round 1), Harvard's OCR garbles short headings, and sources split
paragraphs differently.

Usage:
    uv run python scripts/check_structure.py [case_key ...]
Writes data/verification/structure/report.json and prints a summary.
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

from corpus_align import norm_tokens  # noqa: E402
from verify_corpus import opinions_of  # noqa: E402

CASES = ROOT / "data" / "corpus" / "cases"
OUT = ROOT / "data" / "verification" / "structure"
KEY_WORDS = 10  # opening words used to match a corpus paragraph to a source block
FUZZY = 0.75  # difflib cutoff when the opening words differ (OCR, corrections)
ROMAN = ["I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X", "XI", "XII"]
FN = "\x00"  # sentinel around a marker label inside a source block
LABEL_MAP = {"\x86": "†", "\x87": "‡"}  # Windows-1252 dagger bytes in Lawbox


def norm_label(s: str) -> str:
    s = html.unescape(s)
    for k, v in LABEL_MAP.items():
        s = s.replace(k, v)
    return re.sub(r"[\s\[\]().]", "", s)


def norm_head(s: str) -> str:
    return re.sub(r"[\s.]", "", s).upper()


def is_heading_like(text: str) -> bool:
    """Short, no run of three lowercase letters (so "Reversed." is not one), some letter or *."""
    return (len(text) <= 100 and not re.search(r"[a-z]{3}", text)
            and bool(re.search(r"[A-Za-z*]", text)) or bool(re.fullmatch(r"\d{1,2}\.?", text)))


def level(label: str):
    t = norm_head(label)
    if re.fullmatch(r"\*+", t):
        return ("sep", None)
    if t in ROMAN:
        return (1, ROMAN.index(t))
    if re.fullmatch(r"[A-Z]", t):
        return (2, ord(t) - 65)
    if re.fullmatch(r"\d+", t):
        return (3, int(t) - 1)
    if re.fullmatch(r"[a-z]", label.strip().rstrip(".")):
        return (4, ord(label.strip()[0]) - 97)
    return ("title", None)


# ---------- sources ----------

MARKERS = [
    r'<a class="footnote" href="#fn[^"]*"[^>]*>(.*?)</a>',
    r"<footnotemark>(.*?)</footnotemark>",
    r"<sup>(?:<a[^>]*>)?\s*\[?([^<\]]{1,4})\]?\s*(?:</a>)?</sup>",
]


def blocks_from_html(s: str) -> list[str]:
    s = re.sub(r'<span class="(?:star-pagination|num)"[^>]*>.*?</span>|<page-number[^>]*>.*?</page-number>', " ", s, flags=re.S)
    for pat in MARKERS:
        s = re.sub(pat, lambda m: f" {FN}{norm_label(re.sub(r'<[^>]+>', '', m.group(1)))}{FN}", s, flags=re.S)
    parts = re.split(r"</?(?:p|h\d|center|div|br|author|blockquote|li)\b[^>]*>", s)
    out = []
    for p in parts:
        t = html.unescape(re.sub(r"<[^>]+>", " ", p))
        t = re.sub(r"\s+", " ", t.replace("\x97", "\u2014")).strip()
        if t:
            out.append(t)
    return out


def sources(key: str, kind: str) -> dict[str, list[str]]:
    """Every raw copy of the case's body text, as blocks; footnote bodies removed."""
    ops = opinions_of(key)
    out = {}
    combined = [o for o in ops if o.get("type") == "010combined"]
    split = [o for o in ops if o.get("type") != "010combined"]
    for o in combined:
        if o.get("html_lawbox"):
            body = re.split(r"<h2>\s*NOTES\s*</h2>", o["html_lawbox"])[0]
            out["lawbox"] = blocks_from_html(body)
        if o.get("html"):
            body = o["html"].split('<div class="footnotes">')[0]
            out["html"] = blocks_from_html(body)
        if o.get("html_with_citations") and kind != "courtlistener-lawbox" and not o.get("html_lawbox"):
            h = o["html_with_citations"]
            if h.lstrip().startswith("<pre"):  # the slip opinion's text layout: headings only, by stream
                out["slip_text"] = html.unescape(re.sub(r"<[^>]+>", "", h))
            else:
                body = re.split(r'<div class="footnotes">|<h2>\s*NOTES\s*</h2>', h)[0]
                out["slip_html"] = blocks_from_html(body)
    harv = [o["xml_harvard"] for o in (split or combined) if o.get("xml_harvard")]
    if harv:
        x = re.sub(r"<footnote\b.*?</footnote>", " ", " ".join(harv), flags=re.S)
        out["harvard"] = blocks_from_html(x)
    return out


def split_markers(block: str) -> tuple[str, list[tuple[str, str]]]:
    """Block text without markers, and each marker's (label, word before it)."""
    marks, clean = [], []
    for i, piece in enumerate(block.split(FN)):
        if i % 2:
            before = norm_tokens(" ".join(clean))
            marks.append((piece, before[-1] if before else ""))
        else:
            clean.append(piece)
    return re.sub(r"\s+", " ", " ".join(clean)).strip(), marks


# ---------- corpus ----------

def corpus_units(case: dict) -> list[dict]:
    units = []
    for oi, op in enumerate(case["opinions"]):
        heads = []
        for pi, p in enumerate(op["paragraphs"]):
            if p["kind"] == "section":
                heads.append(p["text"])
                continue
            marks = []
            for r in p.get("footnote_refs", []):
                before = norm_tokens(p["text"][: r["offset"]])
                marks.append((norm_label(r["label"]), before[-1] if before else ""))
            units.append({"where": f"op{oi}.p{pi}", "op": oi, "text": p["text"], "heads": heads, "marks": marks})
            heads = []
    return units


def consistency(case: dict) -> dict:
    out = {"sequence": [], "order_mismatch": [], "marker_not_at_word_end": [], "section_without_label": []}
    for oi, op in enumerate(case["opinions"]):
        last = {}
        for pi, p in enumerate(op["paragraphs"]):
            if p["kind"] != "section":
                continue
            lv, n = level(p["text"])
            if isinstance(lv, int):
                exp = last.get(lv, -1) + 1
                if n != exp:
                    out["sequence"].append({"where": f"op{oi}.p{pi}", "heading": p["text"], "expected_position": exp + 1})
                last[lv] = n
                for deeper in [k for k in last if k > lv]:
                    del last[deeper]
        # Footnotes link to markers by order (labels repeat: Boyd prints "*" on several pages).
        refs = [(pi, r) for pi, p in enumerate(op["paragraphs"]) for r in p.get("footnote_refs", [])]
        foots = [norm_label(f["label"]) for f in op["footnotes"]]
        for k in range(max(len(refs), len(foots))):
            rl = norm_label(refs[k][1]["label"]) if k < len(refs) else None
            fl = foots[k] if k < len(foots) else None
            if rl != fl:
                out["order_mismatch"].append({"op": oi, "position": k + 1, "marker": rl, "footnote": fl,
                                              "where": f"op{oi}.p{refs[k][0]}" if k < len(refs) else None})
        for pi, r in refs:
            o, t = r["offset"], op["paragraphs"][pi]["text"]
            if not (0 < o <= len(t)) or t[o - 1].isspace() or (o < len(t) and t[o].isalnum()):
                out["marker_not_at_word_end"].append({"where": f"op{oi}.p{pi}", "label": r["label"], "offset": o,
                                                      "context": t[max(0, o - 30):o] + "|" + t[o:o + 20]})
        for pi, p in enumerate(op["paragraphs"]):
            if p["kind"] == "section" and not re.search(r"[A-Za-z0-9*]", p["text"]):
                out["section_without_label"].append({"where": f"op{oi}.p{pi}", "text": p["text"]})
    return out


# ---------- comparison ----------

def opening(text: str) -> str:
    return " ".join(norm_tokens(text)[:KEY_WORDS])


def compare(units: list[dict], blocks: list[str]) -> dict:
    parsed = [split_markers(b) for b in blocks]
    keys = [opening(t) for t, _ in parsed]
    exact = {}
    for j, k in enumerate(keys):
        exact.setdefault(k, j)
    matched, used = {}, set()
    for i, u in enumerate(units):
        k = opening(u["text"])
        j = exact.get(k)
        if j is None or j in used:
            cands = [kk for jj, kk in enumerate(keys) if jj not in used and not is_heading_like(parsed[jj][0])]
            best = difflib.get_close_matches(k, cands, n=1, cutoff=FUZZY)
            j = next((jj for jj, kk in enumerate(keys) if best and kk == best[0] and jj not in used), None)
        if j is not None:
            matched[i] = j
            used.add(j)
    heads, marks = [], []
    prev_j, pending, prev_op = None, [], None
    for i, u in enumerate(units):
        j = matched.get(i)
        if u["op"] != prev_op:
            pending, prev_op = [], u["op"]
        if j is None:  # an unmatched paragraph's headings belong to the next comparison
            pending += u["heads"]
            continue
        u = {**u, "heads": pending + u["heads"]}
        pending = []
        first_of_opinion = i == 0 or units[i - 1]["op"] != u["op"] or not any(
            matched.get(ii) is not None for ii in range(i) if units[ii]["op"] == u["op"])
        if prev_j is not None and prev_j < j:
            src_heads = [parsed[jj][0] for jj in range(prev_j + 1, j) if is_heading_like(parsed[jj][0])]
            if first_of_opinion:  # the source's opinion heading line sits here; compare section headings only
                src_heads = [h for h in src_heads if level(h)[0] != "title"]
            c = [h for h in u["heads"] if re.search(r"[A-Za-z0-9*]", h)]  # omission rows are not headings
            kind = None
            if len(src_heads) > len(c):
                kind = "source_has_more"
            elif len(src_heads) < len(c):
                kind = "corpus_has_more"
            else:
                for ch, sh in zip(c, src_heads):
                    if isinstance(level(sh)[0], int) and norm_head(ch) != norm_head(sh):
                        kind = "label_differs"  # only where the source label is clean (not OCR-garbled)
            if kind:
                heads.append({"kind": kind, "where": u["where"], "corpus": c, "source": src_heads,
                              "next_words": " ".join(u["text"].split()[:8])})
        sm = parsed[j][1]
        if Counter(u["marks"]) != Counter(sm):
            cl, sl = sorted(l for l, _ in u["marks"]), sorted(l for l, _ in sm)
            numeric_only = cl == sl and all(
                a == b or (a.isdigit() and b.isdigit()) for (_, a), (_, b) in zip(sorted(u["marks"]), sorted(sm)))
            marks.append({"kind": "citation_numbers_only" if numeric_only else "differs", "where": u["where"],
                          "corpus": u["marks"], "source": sm, "next_words": " ".join(u["text"].split()[:8])})
        prev_j = j
    return {"paragraphs": len(units), "matched": len(matched), "heading_diffs": heads, "marker_diffs": marks,
            "source_markers": sum(len(m) for _, m in parsed)}


HEAD_LINE = re.compile(r"^ {10,}([IVX]+|[A-Z]|\d{1,2}|\*(?: \*)*)\.?\s*$")


def compare_stream(units: list[dict], text: str) -> dict:
    """Headings only, for a slip opinion laid out as text: each corpus paragraph is
    found by its opening words in the token stream; centred label lines between
    one paragraph's opening and the next are that paragraph's headings."""
    toks, heads_at = [], {}
    text = re.sub(r"(\w)-\n\s*(\w)", r"\1\2", text)
    for line in text.split("\n"):
        m = HEAD_LINE.match(line)
        if m:
            heads_at.setdefault(len(toks), []).append(m.group(1))
        else:
            toks.extend(norm_tokens(line))
    joined = " " + " ".join(toks) + " "
    starts = [0]
    for t in toks:
        starts.append(starts[-1] + len(t) + 1)
    heads, prev, matched, pending = [], None, 0, []
    for u in units:
        key = " " + opening(u["text"]) + " "
        at = joined.find(key, starts[prev] if prev is not None else 0)
        idx = starts.index(at) if at >= 0 and at in starts else None
        if idx is None:  # an unmatched paragraph's headings belong to the next comparison
            pending += u["heads"]
            continue
        u = {**u, "heads": pending + u["heads"]}
        pending = []
        matched += 1
        if prev is not None:
            src = [h for k in sorted(heads_at) if prev < k <= idx for h in heads_at[k]]
            c = [h for h in u["heads"] if re.search(r"[A-Za-z0-9*]", h)]
            if [norm_head(x) for x in c] != [norm_head(x) for x in src]:
                kind = "source_has_more" if len(src) > len(c) else "corpus_has_more" if len(src) < len(c) else "label_differs"
                heads.append({"kind": kind, "where": u["where"], "corpus": c, "source": src,
                              "next_words": " ".join(u["text"].split()[:8])})
        prev = idx
    return {"paragraphs": len(units), "matched": matched, "heading_diffs": heads, "marker_diffs": [],
            "markers": "not checked: the slip text has no machine-readable markers"}


def main() -> int:
    keys = sys.argv[1:] or sorted(p.stem for p in CASES.glob("*.json"))
    OUT.mkdir(parents=True, exist_ok=True)
    report = {}
    for key in keys:
        case = json.loads((CASES / f"{key}.json").read_text())
        units = corpus_units(case)
        r = {"source_kind": case["source"]["kind"], "consistency": consistency(case), "sources": {}}
        for name, blocks in sources(key, case["source"]["kind"]).items():
            r["sources"][name] = compare_stream(units, blocks) if name == "slip_text" else compare(units, blocks)
        report[key] = r
        cons = {k: len(v) for k, v in r["consistency"].items() if v}
        srcs = "; ".join(f"{n} {s['matched']}/{s['paragraphs']}, H{len(s['heading_diffs'])} "
                         f"M{sum(1 for d in s['marker_diffs'] if d['kind'] == 'differs')}" for n, s in r["sources"].items())
        print(f"{key:18} {srcs or 'no raw copy'}{' | ' + str(cons) if cons else ''}")
    (OUT / "report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False))
    print(f"wrote {OUT / 'report.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
