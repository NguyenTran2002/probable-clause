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
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
OUT = ROOT / "data" / "corpus" / "cases"

# Text source of record per case (P1.11). Lawbox: CourtListener's Lawbox copy.
LAWBOX = {
    "olmstead": 101320, "goldman": 2443377, "on_lee": 105021, "silverman": 106187,
    "lopez": 106622, "berger": 107483, "katz": 107564, "white": 108304,
    "miller": 109433, "smith": 110118, "knotts": 110882, "karo": 111257,
    "ciraolo": 111666, "dow": 111667, "florida_v_riley": 112175, "kyllo": 118443,
}

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
    keys = sys.argv[1:] or list(LAWBOX)
    OUT.mkdir(parents=True, exist_ok=True)
    for key in keys:
        if key in LAWBOX:
            case = lawbox_case(key, LAWBOX[key])
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
