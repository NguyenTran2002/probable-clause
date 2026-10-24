"""Build the cleaned corpus from the raw cache (brief §4.4, §4.5; P1.9, P1.11).

Reads data/raw/ (CourtListener JSON and the official PDFs) and writes one JSON
file per case to data/corpus/cases/. Each case holds its opinions, split by the
Court's own headings; each opinion holds paragraphs and footnotes, with U.S.
Reports page breaks recorded as offsets into the text, never left in it.

Cleaning is deterministic and never rewrites words. Allowed changes (§4.5):
stripping HTML, removing page markers and footnote markers (recorded as
offsets), removing running heads, page numbers and print-job lines, rejoining
words broken across lines, restoring ligature letters the PDF's font map drops
(only where another copy of the same case confirms the word), and normalising
whitespace. Every change is counted per opinion in the case's "cleaning" stats.

Usage:
    uv run python scripts/build_corpus.py [case_key ...]
"""

import json
import re
import sys
from pathlib import Path

from corpus_align import align, kgram_index, norm_tokens, official_stream, token_offsets, word_pages
from corpus_pdf import build_pdf_case, read_pages
from corpus_common import BARE, HEADING, PER_CURIAM, ROLELESS, STATEMENT, STATEMENTS, WHO, justices, opinion_type, text_of

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
OUT = ROOT / "data" / "corpus" / "cases"

# Text source of record per case (P1.11). Lawbox: CourtListener's Lawbox copy.
LAWBOX = {
    "olmstead": 101320, "goldman": 2443377, "on_lee": 105021, "silverman": 106187,
    "lopez": 106622, "berger": 107483, "katz": 107564, "white": 108304,
    "miller": 109433, "smith": 110118, "knotts": 110882, "karo": 111257,
    "ciraolo": 111666, "dow": 111667, "florida_v_riley": 112175,
    # Filter-check additions (P1.14).
    "ex_parte_jackson": 89759, "boyd": 91573, "hester": 100413, "lee": 101118,
    "shultz": 109005, "jacobsen": 111143, "oliver": 111146, "dunn": 111833, "greenwood": 112067,
}

# Official PDFs (P1.11): file, first U.S. page, the CourtListener cluster whose
# opinion holds the Court's slip text (the reference copy for repairs), and
# whether the PDF itself is a slip opinion.
PDF_CASES = {
    "jardines": ("USREPORTS-569-1.pdf", 1, 856347, False),
    "riley": ("USREPORTS-573-373.pdf", 373, 2680439, False),
    "grady": ("USREPORTS-575-306.pdf", 306, 2789928, False),
    "carpenter": ("USREPORTS-585-296.pdf", 296, 4510032, False),
    "jones": ("USREPORTS-565-400.pdf", 400, 622304, False),  # P1.12
    "kyllo": ("USREPORTS-533-27.pdf", 27, 118443, False),  # P1.15
    "chatrie": ("25-112_0am4.pdf", 1, None, True),
}

# ---------------------------------------------------------------------------
# Lawbox: one combined HTML document per case.

def lawbox_case(key: str, cluster_id: int) -> dict:
    cluster = json.loads((RAW / "clusters" / f"{cluster_id}.json").read_text())
    combined = None
    for url in cluster["sub_opinions"]:
        op = json.loads((RAW / "opinions" / f"{url.rstrip('/').rsplit('/', 1)[-1]}.json").read_text())
        if op.get("html_lawbox"):
            combined = op
    doc = combined["html_lawbox"]
    body, _, notes_html = doc.partition("<h2>NOTES</h2>")

    # Paragraph-level blocks in document order: <p>, <blockquote>, <center>.
    blocks = []
    for m in re.finditer(r"<(p|blockquote|center)\b[^>]*>(.*?)</\1>", body, re.S):
        tag, inner = m.group(1), m.group(2)
        if tag == "blockquote":
            parts = re.findall(r"<p\b[^>]*>(.*?)</p>", inner, re.S) or [inner]
            blocks += [("quote", p) for p in parts]
        elif tag == "center" and "<p" in inner:
            blocks += [("center", p) for p in re.findall(r"<p\b[^>]*>(.*?)</p>", inner, re.S)]
        else:
            blocks.append((tag, inner))

    header_text = text_of(body.split("<p", 1)[0]) if body else ""
    decided = re.search(r"Decided ([A-Z][a-z]+ \d{1,2}, \d{4})", text_of(body[:4000]))
    argued = re.search(r"Argued ([^.]*?\d{4})", text_of(body[:4000]))

    page = int(cluster_cite_page(cluster))
    opinions, notes_for_case, current = [], [], None
    stats = {"page_markers": 0, "footnote_markers": 0}
    marker_queue = []  # (label, opinion index, page) in text order
    header_markers = []  # footnote markers in the header (e.g. "Together with No. ...")

    for kind, inner in blocks:
        # Record page markers and footnote markers as offsets, then remove them.
        para, breaks, refs, pos = "", [], [], 0
        for m in re.finditer(r'<span class="star-pagination">\*?(\d+)</span>|<sup>\[([^\]]+)\]</sup>', inner):
            para += inner[pos:m.start()]
            pos = m.end()
            clean_len = len(text_of(para + "x")) - 1
            if m.group(1):
                page = int(m.group(1))
                breaks.append({"offset": clean_len, "page": page})
                stats["page_markers"] += 1
            else:
                refs.append({"offset": clean_len, "label": m.group(2)})
                stats["footnote_markers"] += 1
        para += inner[pos:]
        text = text_of(para)
        if not text:
            continue

        quote = kind == "quote"
        st = STATEMENT.match(text) if not quote and len(text) < 600 else None
        listed = next((t for (k, prefix), t in STATEMENTS.items() if k == key and text.startswith(prefix)), None)
        if listed and not quote:
            st = re.match(rf"^{WHO}", text, re.I)
        h = None if quote or st else HEADING.match(text)
        bare = None if quote or st or h else BARE.match(text)
        pc = PER_CURIAM.match(text) if not quote and not opinions else None
        if st or h or bare or pc:
            m = st or h or bare
            if st:
                # The statement is its own text.
                otype, end = listed or opinion_type(st.group("role")), 0
            elif h:
                otype, end = opinion_type(h.group("role")), h.end()
            elif bare:
                otype, end = ROLELESS.get((key, justices(bare.group("who"))[0])), bare.end()
            else:
                otype, end = "majority", pc.end()
            rest = text[end:].strip()
            heading = text if st else text[:end].strip()
            if otype == "note":
                notes_for_case.append(heading)
                continue
            current = {
                "heading": heading,
                "type": otype or "UNTYPED",
                "author": justices(m.group("who")) if m else ["Per Curiam"],
                "joined_by": justices((m.groupdict().get("with") or "")) if m else [],
                "statement": bool(st),
                "typed_by_table": bool(listed) or bool(bare),
                "paragraphs": [],
                "footnotes": [],
            }
            opinions.append(current)
            if not rest:
                continue
            shift = len(text) - len(rest)
            breaks = [{"offset": max(0, b["offset"] - shift), "page": b["page"]} for b in breaks]
            refs = [{"offset": max(0, r["offset"] - shift), "label": r["label"]} for r in refs]
            text = rest
        start_page = page_at_start(breaks, page)
        if current is None:
            header_markers += [(r["label"], start_page) for r in refs]
            continue  # header matter before the first opinion
        current["paragraphs"].append({
            "text": text,
            "kind": "quote" if quote else "text",
            "page_start": start_page,
            "page_breaks": breaks,
            "footnote_refs": refs,
        })
        for r in refs:
            marker_queue.append((r["label"], len(opinions) - 1, start_page))

    # Notes: "[n] text" paragraphs, continuing until the next "[n]".
    notes = []
    for p in re.findall(r"<p\b[^>]*>(.*?)</p>", notes_html, re.S):
        t = text_of(p)
        m = re.match(r"^\[([^\]]+)\]\s*(.*)$", t, re.S)
        if m:
            notes.append({"label": m.group(1), "paragraphs": [m.group(2)]})
        elif notes and t:
            notes[-1]["paragraphs"].append(t)
    # Assign each note to the opinion whose marker it answers, in order per label.
    by_label = {}
    for n in notes:
        by_label.setdefault(n["label"], []).append(n)
    header_notes = []
    for label, _ in header_markers:
        if by_label.get(label):
            header_notes.append(by_label[label].pop(0)["paragraphs"])
    unmatched_markers = []
    for label, op_i, pg in marker_queue:
        queue = by_label.get(label)
        if queue:
            n = queue.pop(0)
            opinions[op_i]["footnotes"].append({"label": label, "page": pg, "paragraphs": n["paragraphs"]})
        else:
            unmatched_markers.append(label)
    unmatched_notes = [n["label"] for q in by_label.values() for n in q]

    return {
        "key": key,
        "source": {"kind": "courtlistener-lawbox", "cluster": cluster_id, "opinion": combined["id"]},
        "decided_text": decided.group(1) if decided else None,
        "argued_text": argued.group(1) if argued else None,
        "notes": notes_for_case,
        "header_footnotes": header_notes,
        "opinions": opinions,
        "cleaning": {**stats, "unmatched_footnote_markers": unmatched_markers,
                     "unmatched_notes": unmatched_notes},
    }


def reanchor_pages(case: dict, key: str) -> None:
    """Take a Lawbox case's page breaks from the official PDF. Lawbox moves its
    page markers to nearby sentence ends, and gives footnotes no page; the
    official PDF's word stream carries the printed page of every word."""
    pdfs = json.loads((RAW / "pdfs" / "manifest.json").read_text())
    name = pdfs[key]["file"]
    pdf = RAW / "pdfs" / name
    first = int(name.rsplit("-", 1)[-1].split(".")[0])
    labels = [first + i for i in range(len(read_pages(pdf)))]
    units = [p for op in case["opinions"] for p in op["paragraphs"] if p["kind"] != "section"]
    vocab = {t for op in case["opinions"] for p in op["paragraphs"] for t in norm_tokens(p["text"])}
    vocab |= {t for op in case["opinions"] for f in op["footnotes"] for x in f["paragraphs"] for t in norm_tokens(x)}
    otoks, opages, _, _ = official_stream(pdf, labels, vocab)
    oindex = kgram_index(otoks)
    stats = {"paragraphs_reanchored": 0, "paragraphs_not_found": 0, "breaks_changed": 0}
    near = 0

    def pages_for(text: str) -> tuple[int, list] | None:
        nonlocal near
        ptoks = norm_tokens(text)
        hit = align(ptoks, otoks, oindex, near) if ptoks else None
        if hit is None:
            stats["paragraphs_not_found"] += 1
            return None
        near = hit[0]
        pages = word_pages(ptoks, hit[0], hit[1], opages)
        known = [pg for pg in pages if pg is not None]
        if not known:
            return None
        last = known[0]
        for i, pg in enumerate(pages):  # unmatched words take the page before; never go back
            last = pg if pg is not None and pg >= last else last
            pages[i] = last
        offs = token_offsets(text)
        breaks = [{"offset": offs[i], "page": pages[i]} for i in range(1, len(pages)) if pages[i] != pages[i - 1]]
        stats["paragraphs_reanchored"] += 1
        return pages[0], breaks

    for op in case["opinions"]:
        for p in op["paragraphs"]:
            if p["kind"] == "section":
                continue
            got = pages_for(p["text"])
            if got:
                if got[1] != p["page_breaks"] or got[0] != p["page_start"]:
                    stats["breaks_changed"] += 1
                p["page_start"], p["page_breaks"] = got
        for f in op["footnotes"]:
            starts, breaks = [], []
            for x in f["paragraphs"]:
                got = pages_for(x)
                starts.append(got[0] if got else f["page"])
                breaks.append(got[1] if got else [])
            f["page"], f["page_starts"], f["page_breaks"] = starts[0], starts, breaks
    case["cleaning"]["pages_from_official_pdf"] = stats


def slip_text(cluster_id: int) -> str | None:
    """A reference copy of the same case for repairs: the Court's slip opinion
    text as CourtListener holds it, or else its Lawbox copy."""
    cluster = json.loads((RAW / "clusters" / f"{cluster_id}.json").read_text())
    ops = [json.loads((RAW / "opinions" / f"{u.rstrip('/').rsplit('/', 1)[-1]}.json").read_text())
           for u in cluster["sub_opinions"]]
    for op in ops:
        if op.get("plain_text"):
            return op["plain_text"]
    for op in ops:
        if op.get("html_lawbox"):
            return text_of(op["html_lawbox"].replace("</p>", "\n"))
    return None


def cluster_cite_page(cluster: dict) -> str:
    for c in cluster.get("citations", []):
        if c["reporter"] == "U.S.":
            return c["page"]
    return "0"


def page_at_start(breaks: list, page_after: int) -> int:
    """The page a paragraph starts on: the page before its first break at offset > 0."""
    if not breaks:
        return page_after
    first = breaks[0]
    return first["page"] if first["offset"] == 0 else first["page"] - 1


def main() -> int:
    keys = sys.argv[1:] or list(LAWBOX) + list(PDF_CASES)
    OUT.mkdir(parents=True, exist_ok=True)
    for key in keys:
        if key in LAWBOX:
            case = lawbox_case(key, LAWBOX[key])
            reanchor_pages(case, key)
        elif key in PDF_CASES:
            name, first, ref_op, slip = PDF_CASES[key]
            ref = slip_text(ref_op) if ref_op else None
            case = build_pdf_case(key, RAW / "pdfs" / name, first, ref, slip,
                                  {"kind": "slip-opinion-pdf" if slip else "govinfo-us-reports-pdf", "file": name})
        else:
            print(f"{key}: no adapter yet")
            continue
        (OUT / f"{key}.json").write_text(json.dumps(case, indent=1, ensure_ascii=False))
        ops = ", ".join(f"{o['type']}:{'/'.join(o['author'])}({len(o['paragraphs'])}p,{len(o['footnotes'])}fn)"
                        for o in case["opinions"])
        c = case["cleaning"]
        print(f"{key:16} {case['decided_text']} | {ops} | notes={case['notes']} "
              f"| unmatched fn markers={c['unmatched_footnote_markers']} notes={c['unmatched_notes']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
