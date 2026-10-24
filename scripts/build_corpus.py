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

import html
import json
import re
import subprocess
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

from corpus_align import align, kgram_index, norm_tokens, official_stream, token_offsets, word_pages
from corpus_pdf import build_pdf_case, read_pages
from corpus_common import (BARE, HEADING, PER_CURIAM, ROLELESS, STATEMENT, STATEMENTS, WHO, joiners, justices,
                           opinion_type, straighten, text_of)

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
    "clinton": 106815,  # P1.20
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

FRACTIONS = {"1/2": "\u00bd", "1/4": "\u00bc", "3/4": "\u00be", "1/3": "\u2153", "2/3": "\u2154"}


def lawbox_text(fragment: str) -> str:
    """Plain text of a Lawbox fragment, with Lawbox's own encodings put back to
    the printed forms the verification agents found on the page images:
    "1/2" for "\u00bd"; "___" for a 2-em dash; "....." for a row of omission
    points; ".. . ." for ". . . ."; closed-up abbreviations ("U.S.", "F.2d",
    "N.Y.", "MR.ZIEMBA") where the U.S. Reports space them. Quotation marks are
    then made straight (P1.17)."""
    t = text_of(fragment)
    t = re.sub(r"(?<![\d/])([123])/([234])(?![\d/])", lambda m: FRACTIONS.get(m.group(0), m.group(0)), t)
    t = re.sub(r"_{3,}", "\u2014\u2014", t)
    t = re.sub(r"(?<![.\w])\.\.\.\.\.(?!\.)", ". . . . .", t)
    t = t.replace(".. . .", ". . . .")
    for _ in range(3):
        t = re.sub(r"\b([A-Z])\.(?=(?:[A-Z]\.|\d))", r"\1. ", t)
    t = re.sub(r"\b(MR|MRS|MESSRS|DR)\.(?=[A-Z])", r"\1. ", t)
    return straighten(t)


def lawbox_case(key: str, cluster_id: int) -> dict:
    cluster = json.loads((RAW / "clusters" / f"{cluster_id}.json").read_text())
    combined = None
    for url in cluster["sub_opinions"]:
        op = json.loads((RAW / "opinions" / f"{url.rstrip('/').rsplit('/', 1)[-1]}.json").read_text())
        if op.get("html_lawbox"):
            combined = op
    doc = combined["html_lawbox"]
    body, _, notes_html = doc.partition("<h2>NOTES</h2>")

    # Paragraph-level blocks in document order: <p>, <blockquote>, <center>, and
    # <h2>, which holds the Part numerals ("I", "II", "A") and appendix titles.
    blocks = []
    for m in re.finditer(r"<(p|blockquote|center|h2)\b[^>]*>(.*?)</\1>", body, re.S):
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
        # Footnote markers: "<sup>[3]</sup>", or malformed as "<sup></sup>[3]".
        for m in re.finditer(r'<span class="star-pagination">\*?(\d+)</span>|<sup>\[([^\]]+)\]</sup>|<sup></sup>\[(\d+)\]', inner):
            para += inner[pos:m.start()]
            pos = m.end()
            clean_len = len(lawbox_text(para + "x")) - 1
            if m.group(1):
                page = int(m.group(1))
                breaks.append({"offset": clean_len, "page": page})
                stats["page_markers"] += 1
            else:
                refs.append({"offset": clean_len, "label": m.group(2) or m.group(3)})
                stats["footnote_markers"] += 1
        para += inner[pos:]
        text = lawbox_text(para)
        if not text:
            continue
        if kind == "h2":
            if current is not None:
                current["paragraphs"].append({"text": text, "kind": "section", "page_start": page_at_start(breaks, page),
                                              "page_breaks": [], "footnote_refs": []})
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
            heading = "" if st else text[:end].strip()  # a statement is its own text, not a heading
            if otype == "note":
                notes_for_case.append(heading)
                continue
            current = {
                "heading": heading,
                "type": otype or "UNTYPED",
                "author": justices(m.group("who")) if m else ["Per Curiam"],
                **dict(zip(("joined_by", "joined_by_note"),
                           joiners(m.group("who"), m.groupdict().get("with"), m.groupdict().get("role") or "")
                           if m else ([], None))),
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
            marker_queue.append((r["label"], len(opinions) - 1, start_page,
                                 (len(current["paragraphs"]) - 1, r["offset"])))

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
    for label, op_i, pg, at in marker_queue:
        queue = by_label.get(label)
        if queue:
            n = queue.pop(0)
            opinions[op_i]["footnotes"].append({"label": label, "page": pg, "marker": at,
                                                "paragraphs": [lawbox_text(x) for x in n["paragraphs"]]})
        else:
            unmatched_markers.append(label)
    unmatched_notes = [n["label"] for q in by_label.values() for n in q]

    return {
        "key": key,
        "source": {"kind": "courtlistener-lawbox", "cluster": cluster_id, "opinion": combined["id"]},
        "decided_text": decided.group(1) if decided else None,
        "argued_text": argued.group(1) if argued else None,
        "notes": notes_for_case,
        "header_footnotes_dropped": len(header_notes),
        "opinions": opinions,
        "cleaning": {**stats, "unmatched_footnote_markers": unmatched_markers,
                     "unmatched_notes": unmatched_notes},
    }


def official_pdf(key: str) -> tuple[Path, list[int]]:
    pdfs = json.loads((RAW / "pdfs" / "manifest.json").read_text())
    name = pdfs[key]["file"]
    first = int(name.rsplit("-", 1)[-1].split(".")[0])
    pdf = RAW / "pdfs" / name
    return pdf, [first + i for i in range(len(read_pages(pdf)))]


def case_vocab(case: dict) -> set:
    v = {t for op in case["opinions"] for p in op["paragraphs"] for t in norm_tokens(p["text"])}
    return v | {t for op in case["opinions"] for f in op["footnotes"] for x in f["paragraphs"] for t in norm_tokens(x)}


def snap(text: str, offset: int) -> int:
    """A page break that falls inside a printed word ("petitioner'|s") moves to
    the start of the next word."""
    if 0 < offset < len(text) and not text[offset - 1].isspace():
        nxt = text.find(" ", offset)
        return nxt + 1 if nxt != -1 else offset
    return offset


def pages_from(text: str, otoks: list, opages: list, oindex: dict, near: int):
    """Align one paragraph with an official stream; return (start page, breaks,
    stream position), or None."""
    ptoks = norm_tokens(text)
    hit = align(ptoks, otoks, oindex, near) if ptoks else None
    if hit is None:
        return None
    pages = word_pages(ptoks, hit[0], hit[1], opages)
    known = [pg for pg in pages if pg is not None]
    if not known:
        return None
    last = known[0]
    for i, pg in enumerate(pages):  # unmatched words take the page before; never go back
        last = pg if pg is not None and pg >= last else last
        pages[i] = last
    offs = token_offsets(text)
    breaks = [{"offset": snap(text, offs[i]), "page": pages[i]} for i in range(1, len(pages)) if pages[i] != pages[i - 1]]
    return pages[0], breaks, hit[0]


def reanchor_pages(case: dict, key: str) -> None:
    """Take a Lawbox case's page breaks from the official PDF. Lawbox moves its
    page markers to nearby sentence ends and gives footnotes no page. Body text
    is aligned with the PDF's body lines only (running heads such as "GOLDMAN v.
    UNITED STATES" would otherwise capture nearby words), and each footnote with
    the footnote lines of its marker's page and the next."""
    pdf, labels = official_pdf(key)
    vocab = case_vocab(case)
    btoks, bpages, *_ = official_stream(pdf, labels, vocab, "body")
    ftoks, fpages, *_ = official_stream(pdf, labels, vocab, "foot")
    bindex = kgram_index(btoks)
    stats = {"paragraphs_reanchored": 0, "paragraphs_not_found": 0, "breaks_changed": 0}
    near = 0
    for op in case["opinions"]:
        for p in op["paragraphs"]:
            if p["kind"] == "section":
                continue
            got = pages_from(p["text"], btoks, bpages, bindex, near)
            if not got:
                stats["paragraphs_not_found"] += 1
                continue
            stats["paragraphs_reanchored"] += 1
            if got[1] != p["page_breaks"] or got[0] != p["page_start"]:
                stats["breaks_changed"] += 1
            p["page_start"], p["page_breaks"], near = got
        for p in op["paragraphs"]:  # a section numeral takes the page of what follows it
            if p["kind"] == "section":
                nxt = next((q for q in op["paragraphs"][op["paragraphs"].index(p) + 1:] if q["kind"] != "section"), None)
                p["page_start"] = nxt["page_start"] if nxt else p["page_start"]
        for f in op["footnotes"]:
            pi, off = f.get("marker", (None, None))
            mpage = f["page"]
            if pi is not None and pi < len(op["paragraphs"]):
                para = op["paragraphs"][pi]
                mpage = para["page_start"]
                for b in para["page_breaks"]:
                    if b["offset"] <= off:
                        mpage = b["page"]
            idx = [i for i, pg in enumerate(fpages) if mpage <= pg <= mpage + 1]
            sub_t = [ftoks[i] for i in idx]
            sub_p = [fpages[i] for i in idx]
            sub_index = kgram_index(sub_t)
            starts, breaks = [], []
            for x in f["paragraphs"]:
                got = pages_from(x, sub_t, sub_p, sub_index, 0) if sub_t else None
                if got:
                    stats["paragraphs_reanchored"] += 1
                else:
                    stats["paragraphs_not_found"] += 1
                starts.append(got[0] if got else (starts[-1] if starts else mpage))
                breaks.append(got[1] if got else [])
            f["page"], f["page_starts"], f["page_breaks"] = starts[0], starts, breaks
            f.pop("marker", None)
    case["cleaning"]["pages_from_official_pdf"] = stats


def harvard_tokens(key: str) -> list[str]:
    idx = json.loads((RAW / "pull_index.json").read_text())
    cluster = json.loads((RAW / "clusters" / f"{idx[key]['cluster']}.json").read_text())
    parts = []
    for u in cluster["sub_opinions"]:
        op = json.loads((RAW / "opinions" / f"{u.rstrip('/').rsplit('/', 1)[-1]}.json").read_text())
        if op.get("xml_harvard") and op["type"] != "010combined":
            x = re.sub(r"<page-number[^>]*>.*?</page-number>|<footnotemark>.*?</footnotemark>", " ", op["xml_harvard"], flags=re.S)
            parts.append(html.unescape(re.sub(r"<[^>]+>", " ", x)))
    return norm_tokens(" ".join(parts))


def two_scan_corrections(case: dict, key: str) -> None:
    """P1.16: correct Lawbox where two independent scans of the print agree.

    Each paragraph and footnote is aligned with the official PDF's text layer.
    At every short difference (up to 6 words on either side), the official
    reading replaces Lawbox's only if Harvard's scan has the official reading in
    the same context and not Lawbox's. The replacement is the official words as
    printed, quotation marks straightened. Every correction is logged."""
    pdf, labels = official_pdf(key)
    vocab = case_vocab(case)
    htoks = harvard_tokens(key)
    if not htoks:
        case["cleaning"]["two_scan_corrections"] = []
        return
    h4 = defaultdict(list)
    for i in range(len(htoks) - 3):
        h4[tuple(htoks[i:i + 4])].append(i)

    def in_harvard(seq: list[str]) -> bool:
        if len(seq) < 4:
            return False
        return any(htoks[i:i + len(seq)] == seq for i in h4.get(tuple(seq[:4]), ()))

    log = []
    streams = {}
    for region in ("body", "foot"):
        t, pg, _, _, raw = official_stream(pdf, labels, vocab, region)
        streams[region] = (t, pg, raw, kgram_index(t))

    def correct(text: str, region: str, where: str) -> tuple[str, list]:
        otoks, opages, oraw, oindex = streams[region]
        ptoks = norm_tokens(text)
        hit = align(ptoks, otoks, oindex, 0) if len(ptoks) >= 3 else None
        if hit is None:
            return text, []
        base, sm = hit
        offs = [(m.start(), m.end()) for m in re.finditer(r"[a-z0-9]+", text.lower())]
        edits = []
        for tag, a0, a1, b0, b1 in sm.get_opcodes():
            if tag == "equal" or a1 - a0 > 6 or b1 - b0 > 6:
                continue
            c_seg, o_seg = ptoks[a0:a1], otoks[base + b0:base + b1]
            left, right = ptoks[max(0, a0 - 4):a0], ptoks[a1:a1 + 4]
            if not (in_harvard(left + o_seg + right) and not in_harvard(left + c_seg + right)):
                continue
            # The official words as printed, from the first token's start to the last's end.
            words, last = [], None
            for j in range(base + b0, base + b1):
                w, s0, e0 = oraw[j]
                if last is not None and last[0] == w and last[1] == j - 1:
                    words[-1] = (w, words[-1][1], e0)
                else:
                    words.append((w, s0, e0))
                last = (w, j)
            printed = straighten(" ".join(w[s0:e0] if len(words) == 1 else
                                          (w[s0:] if k == 0 else (w[:e0] if k == len(words) - 1 else w))
                                          for k, (w, s0, e0) in enumerate(words)))
            if c_seg:
                start, stop = offs[a0][0], offs[a1 - 1][1]
            else:  # official has words Lawbox lacks: insert them, as printed, before the next word
                w_last, _, _ = oraw[base + b1 - 1]
                w_first, s_first, _ = oraw[base + b0]
                printed = straighten(" ".join(dict.fromkeys(oraw[j][0] for j in range(base + b0, base + b1))))
                printed = printed[s_first:] if printed.startswith(w_first) else printed
                start = stop = offs[a0][0] if a0 < len(offs) else len(text)
                printed = printed + " " if a0 < len(offs) else " " + printed
            if not o_seg:  # Lawbox has words the print lacks: remove them and a space
                stop = offs[a1][0] if a1 < len(offs) else stop
                if a1 >= len(offs) and start > 0 and text[start - 1] == " ":
                    start -= 1
                printed = ""
            page = opages[base + b0] if b1 > b0 else opages[base + max(0, b0 - 1)]
            edits.append((start, stop, printed, text[start:stop], page))
        for start, stop, printed, before, page in sorted(edits, reverse=True):
            text = text[:start] + printed + text[stop:]
        for start, stop, printed, before, page in sorted(edits):
            log.append({"where": where, "page": page, "lawbox": before, "corrected": printed})
        return text, sorted(edits)

    def shift_refs(refs, edits):
        for start, stop, printed, before, page in sorted(edits, reverse=True):
            delta = len(printed) - (stop - start)
            for r in refs:
                if r["offset"] >= stop:
                    r["offset"] += delta
                elif r["offset"] > start:
                    r["offset"] = start + len(printed)

    for oi, op in enumerate(case["opinions"]):
        for pi, p in enumerate(op["paragraphs"]):
            if p["kind"] == "section":
                continue
            p["text"], edits = correct(p["text"], "body", f"op{oi}.p{pi}")
            shift_refs(p["footnote_refs"], edits)
            shift_refs(p["page_breaks"], edits)
            # footnote markers recorded against this paragraph move too
            for f in op["footnotes"]:
                if f.get("marker") and f["marker"][0] == pi:
                    tmp = [{"offset": f["marker"][1]}]
                    shift_refs(tmp, edits)
                    f["marker"] = (pi, tmp[0]["offset"])
        for f in op["footnotes"]:
            f["paragraphs"] = [correct(x, "foot", f"op{oi}.fn{f['label']}.{qi}")[0]
                               for qi, x in enumerate(f["paragraphs"])]
    case["cleaning"]["two_scan_corrections"] = log


CORRECTIONS = Path(__file__).resolve().parent / "corrections.json"


def apply_corrections(case: dict, key: str) -> None:
    """The reviewed corrections table (scripts/corrections.json, P1.16): replace
    an exact string, insert printed lines after a paragraph, or set paragraphs'
    kind. Every entry must apply exactly once, or the build stops."""
    entries = [e for e in json.loads(CORRECTIONS.read_text())["entries"] if e["case"] == key]
    log = []

    def units():
        for op in case["opinions"]:
            for p in op["paragraphs"]:
                yield op, p, None
            for f in op["footnotes"]:
                for qi in range(len(f["paragraphs"])):
                    yield op, f, qi

    for e in entries:
        if "find" in e:
            hits = [(op, u, qi) for op, u, qi in units()
                    if (u["text"] if qi is None else u["paragraphs"][qi]).count(e["find"])]
            total = sum((u["text"] if qi is None else u["paragraphs"][qi]).count(e["find"]) for _, u, qi in hits)
            if total != 1:
                sys.exit(f"{key}: correction {e['find']!r} found {total} times")
            op, u, qi = hits[0]
            text = u["text"] if qi is None else u["paragraphs"][qi]
            at, delta = text.index(e["find"]), len(e["replace"]) - len(e["find"])
            text = text.replace(e["find"], e["replace"])
            if qi is None:
                u["text"] = text
                for item in u["footnote_refs"] + u["page_breaks"]:
                    item["offset"] += delta if item["offset"] > at else 0
            else:
                u["paragraphs"][qi] = text
            log.append({"replaced": e["find"], "with": e["replace"], "source": e["source"]})
        elif "insert_after" in e:
            spots = [(op, i) for op in case["opinions"] for i, p in enumerate(op["paragraphs"]) if e["insert_after"] in p["text"]]
            n = e.get("occurrence")
            if (n is None and len(spots) != 1) or (n is not None and len(spots) < n):
                sys.exit(f"{key}: insertion point {e['insert_after']!r} found {len(spots)} times")
            op, i = spots[(n or 1) - 1]
            new = [{"text": t, "kind": e["kind"], "page_start": e["page"], "page_breaks": [], "footnote_refs": []}
                   for t in e["texts"]]
            op["paragraphs"][i + 1:i + 1] = new
            log.append({"inserted": e["texts"], "after": e["insert_after"], "source": e["source"]})
        elif "kind_from" in e:
            for op in case["opinions"]:
                idx = [i for i, p in enumerate(op["paragraphs"]) if e["kind_from"] in p["text"]]
                end = [i for i, p in enumerate(op["paragraphs"]) if e["kind_to"] in p["text"]]
                if idx and end:
                    for p in op["paragraphs"][idx[0]:end[-1] + 1]:
                        if p["kind"] == "text":
                            p["kind"] = e["kind"]
                    log.append({"kind": e["kind"], "from": e["kind_from"], "to": e["kind_to"], "source": e["source"]})
                    break
            else:
                sys.exit(f"{key}: kind range {e['kind_from']!r} not found")
    case["cleaning"]["reviewed_corrections"] = log


JUSTICES = ("Waite Clifford Swayne Miller Davis Field Strong Bradley Hunt Harlan Woods Matthews Gray Blatchford "
            "Lamar Fuller Brewer Brown Shiras Jackson White Peckham McKenna Holmes Day Moody Lurton Hughes VanDevanter "
            "Pitney McReynolds Brandeis Clarke Taft Sutherland Butler Sanford Stone Roberts Cardozo Black Reed "
            "Frankfurter Douglas Murphy Byrnes Rutledge Burton Vinson Clark Minton Warren Brennan Whittaker Stewart "
            "Goldberg Fortas Marshall Burger Blackmun Powell Rehnquist Stevens O'Connor Scalia Kennedy Souter Thomas "
            "Ginsburg Breyer Alito Sotomayor Kagan Gorsuch Kavanaugh Barrett").split()
CHIEFS = [("1874-03-04", "Waite"), ("1888-10-08", "Fuller"), ("1910-12-19", "White"), ("1921-07-11", "Taft"),
          ("1930-02-24", "Hughes"), ("1941-07-03", "Stone"), ("1946-06-24", "Vinson"), ("1953-10-05", "Warren"),
          ("1969-06-23", "Burger"), ("1986-09-26", "Rehnquist"), ("2005-09-29", "Roberts")]


def chief_on(iso_date: str) -> str:
    return [name for since, name in CHIEFS if since <= iso_date][-1]


def lineup_joiners(case: dict, key: str) -> None:
    """P1.18: the majority's joiners from the Reporter's lineup paragraph, where
    the volume prints one; otherwise recorded as not printed. Scans break
    small-capital names into pieces ("Reh nq ui st"), so the lineup is read with
    spaces removed and each name matched against the list of Justices."""
    pdfs = json.loads((RAW / "pdfs" / "manifest.json").read_text())
    front = subprocess.run(["pdftotext", "-f", "1", "-l", "8", str(RAW / "pdfs" / pdfs[key]["file"]), "-"],
                           capture_output=True, text=True).stdout
    flat = re.sub(r"\s+", "", front.replace("\u00ad", "").replace("\ufb01", "fi").replace("\ufb02", "fl"))
    flat = flat.replace("’", "'").lower()
    known = {j.lower(): j for j in JUSTICES}
    for op in case["opinions"]:
        if op["author"] == ["Per Curiam"]:
            op["joined_by_source"] = "per curiam"  # an opinion of the Court with no author or joiners
            continue
        if op["type"] not in ("majority", "plurality"):
            continue
        author = op["author"][0].replace("’", "'").lower()
        m = re.search(rf"{re.escape(author)},(?:c\.)?j\.,(?:delivered|announced)(.{{0,900}}?)joined\.", flat)
        if not m or re.search(r"\.[a-z']+,(?:c\.)?j\.,filed", m.group(1)):
            if op["type"] == "majority":
                op["joined_by_source"] = "not printed"
            continue
        full, partial = [], []
        for seg in (m.group(1) + "joined").split("joined")[:-1]:
            names = names_in(seg.split("which", 1)[1] if "which" in seg else "", known, author)
            parts = re.search(r"in(parts?[ivx0-9,–\-and]+)ofwhich", seg)
            if parts:
                raw = parts.group(1)
                nums = [x.upper() for x in re.split(r",|and", re.sub(r"^parts?", "", raw)) if x]
                listed = nums[0] if len(nums) == 1 else ", ".join(nums[:-1]) + " and " + nums[-1]
                partial.append(f"{'Parts' if len(nums) > 1 else 'Part'} {listed}: {', '.join(names)}")
            elif "inwhich" in seg:
                full += [n for n in names if n not in full]
        if op["type"] == "majority" or not op["joined_by"]:
            op["joined_by"] = full
        if partial:
            op["joined_by_note"] = "joined in part, per the Reporter's lineup: " + "; ".join(partial)
        op["joined_by_source"] = "lineup"


def names_in(clause: str, known: dict, author: str) -> list[str]:
    """Justices' names in a space-stripped lineup clause ("burger,c.j.,and
    blackmunandpowell,jj."), segmented against the list of Justices."""
    out = []
    for part in clause.split(","):
        part = part.strip(" .")
        best = {0: []}
        for i in range(len(part)):  # shortest segmentation into names, "and", titles
            if i not in best:
                continue
            for tok in list(known) + ["and", "c.j.", "jj.", "j."]:
                if part.startswith(tok, i) and (i + len(tok) not in best or len(best[i]) + 1 < len(best[i + len(tok)])):
                    best[i + len(tok)] = best[i] + [tok]
        for tok in best.get(len(part), []):
            if tok in known and tok != author and known[tok] not in out:
                out.append(known[tok])
    return out


def resolve_chief(case: dict) -> None:
    """"The Chief Justice" in a heading, as the Chief Justice on the decision date."""
    iso = datetime.strptime(case["decided_text"], "%B %d, %Y").date().isoformat()
    chief = chief_on(iso)
    for op in case["opinions"]:
        op["author"] = [chief if n == "The Chief Justice" else n for n in op["author"]]
        op["joined_by"] = [chief if n == "The Chief Justice" else n for n in op["joined_by"]]


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
            two_scan_corrections(case, key)
            reanchor_pages(case, key)
        elif key in PDF_CASES:
            name, first, ref_op, slip = PDF_CASES[key]
            ref = slip_text(ref_op) if ref_op else None
            case = build_pdf_case(key, RAW / "pdfs" / name, first, ref, slip,
                                  {"kind": "slip-opinion-pdf" if slip else "govinfo-us-reports-pdf", "file": name})
        else:
            print(f"{key}: no adapter yet")
            continue
        apply_corrections(case, key)
        lineup_joiners(case, key)
        if not case.get("decided_text"):
            # The early U.S. Reports print the Term, not the decision date.
            idx = json.loads((RAW / "pull_index.json").read_text())
            cl = json.loads((RAW / "clusters" / f"{idx[key]['cluster']}.json").read_text())
            case["decided_text"] = datetime.strptime(cl["date_filed"], "%Y-%m-%d").strftime("%B %-d, %Y")
            case["decided_source"] = "CourtListener date_filed; no decision date printed in the U.S. Reports"
        resolve_chief(case)
        (OUT / f"{key}.json").write_text(json.dumps(case, indent=1, ensure_ascii=False))
        ops = ", ".join(f"{o['type']}:{'/'.join(o['author'])}({len(o['paragraphs'])}p,{len(o['footnotes'])}fn)"
                        for o in case["opinions"])
        c = case["cleaning"]
        print(f"{key:16} {case['decided_text']} | {ops} | notes={case['notes']} "
              f"| unmatched fn markers={c['unmatched_footnote_markers']} notes={c['unmatched_notes']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
