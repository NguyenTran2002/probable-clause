"""Official PDFs as text of record (P1.11): GovInfo U.S. Reports and the slip opinion.

Reads word positions with `pdftotext -bbox-layout` (poppler). Each line is sorted
by type size relative to the document's body text:
  - running heads: small lines above the first body line on a page (they carry
    the page number, which becomes the page label);
  - body: body-size lines, including opinion headings and section numerals;
  - footnotes: small lines below the last body line on a page;
  - footnote markers: superscript words (much smaller than body text).

Two volumes' fonts need repair, and both repairs are confirmed against another
copy of the same case before anything changes:
  - Ligatures: some PDFs map the "fi" and "fl" ligatures to a bare "f", so
    "officers" extracts as "offcers" and "filed" as "fled". A ligature is
    restored only where the reference copy (the Court's slip opinion text, as
    CourtListener holds it) has the repaired word in the same context, or, for a
    non-word, where exactly one repaired form is a known word.
  - Line-end hyphens: where the PDF has no soft hyphens, a "-" at a line end
    may be a real hyphen or a break. Joined or kept according to which form the
    reference copy and the document itself use elsewhere.
Every repair and every unresolved case is listed in the case's cleaning stats.
"""

import html
import re
import subprocess
from collections import Counter
from pathlib import Path

from corpus_common import HEADING, PER_CURIAM, justices, opinion_type

LIGATURES = {"ﬀ": "ff", "ﬁ": "fi", "ﬂ": "fl", "ﬃ": "ffi", "ﬄ": "ffl"}
DICT_PATH = Path("/usr/share/dict/words")
WORD = re.compile(r"[A-Za-z][A-Za-z'’]*[A-Za-z]|[A-Za-z]")


def read_pages(pdf: Path) -> list[list[dict]]:
    """Every line of every page: words with their boxes and heights."""
    out = subprocess.run(["pdftotext", "-bbox-layout", str(pdf), "-"],
                         capture_output=True, text=True, check=True).stdout
    pages = []
    for pg in re.finditer(r"<page [^>]*>(.*?)</page>", out, re.S):
        lines = []
        for ln in re.finditer(r"<line [^>]*>(.*?)</line>", pg.group(1), re.S):
            words = []
            for w in re.finditer(r'<word xMin="([\d.]+)" yMin="([\d.]+)" xMax="([\d.]+)" yMax="([\d.]+)">(.*?)</word>',
                                 ln.group(1)):
                t = html.unescape(w.group(5))
                for k, v in LIGATURES.items():
                    t = t.replace(k, v)
                words.append({"t": t, "x0": float(w.group(1)), "y0": float(w.group(2)),
                              "x1": float(w.group(3)), "h": float(w.group(4)) - float(w.group(2))})
            # Small capitals arrive as separate words with no gap ("J" "USTICE"):
            # merge letters that touch. Footnote markers are not letters, so stay apart.
            merged = []
            for w in words:
                touching = (merged and w["x0"] - merged[-1]["x1"] < 0.8 and w["t"][:1].isalpha()
                            and merged[-1]["t"][-1:].isalpha())
                # After small capitals, a comma can arrive as its own word ("ALITO ,").
                stray_punct = (merged and re.fullmatch(r"[,.;:)\]’”]+", w["t"])
                               and w["x0"] - merged[-1]["x1"] < 4 and not w["h"] < merged[-1]["h"] * 0.7
                               and not merged[-1]["h"] < w["h"] * 0.7)  # never onto a footnote marker
                if touching or stray_punct:
                    merged[-1] = {**merged[-1], "t": merged[-1]["t"] + w["t"], "x1": w["x1"],
                                  "h": max(merged[-1]["h"], w["h"])}
                else:
                    merged.append(w)
            # An asterisk or dagger footnote marker can arrive fused to its word
            # ("approach.*", "*United"): split it off as its own superscript word.
            split = []
            for w in merged:
                # Not before a digit: "*303" is a star page cited in the text.
                m = re.fullmatch(r"([*†‡]+)([^\W\d]\S*)|(\S+?)([*†‡]+)", w["t"])
                if m and m.group(1):
                    split += [{**w, "t": m.group(1), "fused_marker": True}, {**w, "t": m.group(2)}]
                elif m and m.group(4):
                    split += [{**w, "t": m.group(3)}, {**w, "t": m.group(4), "fused_marker": True}]
                else:
                    split.append(w)
            words = split
            if words:
                lines.append({"words": words, "x0": words[0]["x0"], "x1": words[-1]["x1"],
                              "y0": min(w["y0"] for w in words),
                              "h": Counter(round(w["h"], 1) for w in words).most_common(1)[0][0]})
        pages.append(sorted(lines, key=lambda l: (round(l["y0"]), l["x0"])))
    return pages


def classify(pages: list[list[dict]]) -> tuple[float, list[dict]]:
    """Label each line header / body / foot, and find each page's label and margin."""
    body_h = Counter(l["h"] for p in pages for l in p).most_common(1)[0][0]
    small, sup = body_h * 0.9, body_h * 0.7
    info = []
    for lines in pages:
        body_idx = [i for i, l in enumerate(lines) if l["h"] >= small]
        first_body = body_idx[0] if body_idx else len(lines)
        last_body = body_idx[-1] if body_idx else -1
        label = None
        for i, l in enumerate(lines):
            if i < first_body:
                l["kind"] = "header"
                # The page number stands alone on its own line; the volume and
                # first page inside "Cite as: 573 U. S. 373" are not it.
                if len(l["words"]) == 1 and re.fullmatch(r"\d+", l["words"][0]["t"]) and label is None:
                    label = int(l["words"][0]["t"])
            elif i <= last_body:
                l["kind"] = "body"
            else:
                l["kind"] = "foot"
            for w in l["words"]:
                # A footnote marker is small and is a number or symbol; small
                # capitals in a heading are small too, but are letters.
                w["sup"] = (w["h"] < sup and bool(re.fullmatch(r"[\d*†‡§]+", w["t"]))) or w.get("fused_marker", False)
        body_x = Counter(round(l["x0"], 0) for l in lines if l["kind"] == "body" and l["x1"] - l["x0"] > 200)
        foot_x = Counter(round(l["x0"], 0) for l in lines if l["kind"] == "foot" and l["x1"] - l["x0"] > 200)
        info.append({"label": label,
                     "margin": body_x.most_common(1)[0][0] if body_x else None,
                     "foot_margin": foot_x.most_common(1)[0][0] if foot_x else None,
                     "right": max((l["x1"] for l in lines if l["kind"] == "body"), default=None)})
    return body_h, info


class Repairer:
    """Ligature and line-end hyphen decisions, checked against a reference copy."""

    def __init__(self, reference_text: str | None, own_text: str, lossy: bool):
        self.lossy = lossy
        ref = reference_text or ""
        # Join the reference's own line-end hyphens for its vocabulary; keep both forms.
        ref_joined = re.sub(r"(\w)-\s*\n\s*(\w)", r"\1\2", ref)
        self.ref_tokens = [t.lower() for t in WORD.findall(ref_joined)]
        self.ref_vocab = set(self.ref_tokens)
        self.ref_hyphenated = {m.lower() for m in re.findall(r"\b\w+(?:-\w+)+\b", re.sub(r"-\s*\n\s*", "", ref))}
        self.ref_trigrams = Counter(zip(self.ref_tokens, self.ref_tokens[1:], self.ref_tokens[2:]))
        self.ref_bigrams = Counter(zip(self.ref_tokens, self.ref_tokens[1:]))
        own = [t.lower() for t in WORD.findall(own_text)]
        self.own_vocab = Counter(own)
        self.own_hyphenated = {m.lower() for m in re.findall(r"\b\w+(?:-\w+)+\b", own_text)}
        self.dict = {w.strip().lower() for w in DICT_PATH.read_text().splitlines()} if DICT_PATH.exists() else set()
        self.log = {"ligatures_restored": [], "ligatures_unresolved": [],
                    "hyphens_joined": 0, "hyphens_kept": [], "hyphens_unresolved": []}

    def known(self, w: str) -> bool:
        # Not the document's own vocabulary: in a lossy PDF the broken forms
        # ("frst") recur and would vouch for themselves.
        w = w.lower()
        return w in self.ref_vocab or w in self.dict

    @staticmethod
    def candidates(core: str) -> set[str]:
        """Forms with the dropped ligature letter restored. These fonts keep the
        "f" and drop what follows it ("first" -> "frst", "officer" -> "offcer")."""
        out = set()
        for i, ch in enumerate(core):
            if ch in "fF":
                out |= {core[:i + 1] + x + core[i + 1:] for x in ("i", "l")}
        return out

    def ligature(self, core: str, prev: str, nxt: str) -> str:
        """Return the word with a dropped ligature restored, or unchanged."""
        if not self.lossy or not core:
            return core
        cands = sorted(c for c in self.candidates(core) if self.known(c))
        if not cands:
            return core
        p, n, low = prev.lower(), nxt.lower(), core.lower()

        def ctx(w):
            w = w.lower()
            return 2 * self.ref_trigrams[(p, w, n)] + self.ref_bigrams[(p, w)] + self.ref_bigrams[(w, n)]

        if self.known(core):
            # A real word ("led") is changed only if the reference supports the
            # repaired form ("filed") in this context and not the word as extracted.
            best = max(cands, key=ctx)
            if ctx(best) > 0 and ctx(core) == 0:
                self.log["ligatures_restored"].append(f"{prev} [{core}->{best}] {nxt}")
                return best
            return core
        ranked = sorted(cands, key=ctx, reverse=True)
        if len(cands) == 1 or ctx(ranked[0]) > ctx(ranked[1]):
            self.log["ligatures_restored"].append(f"{prev} [{core}->{ranked[0]}] {nxt}")
            return ranked[0]
        self.log["ligatures_unresolved"].append(f"{prev} [{core}?{cands}] {nxt}")
        return core

    def hyphen(self, left: str, right: str) -> str:
        """Join a line-end "left-" with "right": drop the hyphen or keep it."""
        a = re.sub(r"^\W+", "", left[:-1])
        b = re.sub(r"\W+$", "", right)
        a_core = WORD.findall(a)[-1] if WORD.findall(a) else a
        b_core = WORD.findall(b)[0] if WORD.findall(b) else b
        joined_core = (a_core + b_core).lower()
        hyph = f"{a_core}-{b_core}".lower()
        joined_ok = joined_core in self.ref_vocab or self.own_vocab.get(joined_core, 0) > 0 or joined_core in self.dict
        hyph_ok = any(hyph in h for h in self.ref_hyphenated) or any(hyph in h for h in self.own_hyphenated)
        if self.lossy and not joined_ok:
            # The join may also hide a dropped ligature ("signi-" + "cance").
            fixed = self.ligature(a_core + b_core, "", "")
            joined_ok = fixed.lower() != joined_core
        if b_core[:1].isupper() or a_core.isdigit():
            keep = True  # "Miami-" + "Dade", "A-" + "35": a real hyphen
        elif hyph_ok and not joined_ok:
            keep = True
        elif joined_ok and not hyph_ok:
            keep = False
        elif joined_ok and hyph_ok:
            # Both forms attested: follow whichever the reference uses more often.
            n_h = sum(h.count(hyph) for h in self.ref_hyphenated) + sum(h.count(hyph) for h in self.own_hyphenated)
            n_j = self.ref_tokens.count(joined_core)
            keep = n_h >= n_j
            self.log["hyphens_unresolved"].append(
                f"{left}{right} (both forms attested: hyphenated {n_h}, joined {n_j}; {'kept' if keep else 'joined'})")
        else:
            keep = False
            self.log["hyphens_unresolved"].append(f"{left}{right} (neither form attested; joined)")
        if keep:
            self.log["hyphens_kept"].append(f"{left}{right}")
            return left + right
        self.log["hyphens_joined"] += 1
        return left[:-1] + right


def lines_to_stream(pages, info, first_page: int, slip: bool):
    """Flatten body and footnote lines into one reading-order stream of lines."""
    stream = []
    page_no = first_page
    for i, (lines, meta) in enumerate(zip(pages, info)):
        if meta["label"] is not None:
            page_no = meta["label"]
        elif i > 0:
            page_no += 1
        for l in lines:
            if l["kind"] in ("body", "foot"):
                stream.append({**l, "page": page_no, "page_index": i,
                               "margin": meta["margin"] if l["kind"] == "body" else (meta["foot_margin"] or meta["margin"]),
                               "right": meta["right"]})
    return stream


def build_pdf_case(key: str, pdf: Path, first_page: int, reference_text: str | None,
                   slip: bool, source: dict) -> dict:
    pages = read_pages(pdf)
    body_h, info = classify(pages)
    lossy = not any(w["t"].endswith("\u00ad") for p in pages for l in p for w in l["words"]) and not slip
    own_text = " ".join(w["t"] for p in pages for l in p for w in l["words"])
    rep = Repairer(reference_text, own_text, lossy=lossy and reference_text is not None)
    if slip:
        rep.lossy = False  # the slip PDF keeps its ligatures; only hyphens need deciding
    stream = lines_to_stream(pages, info, first_page, slip)

    first_text = " ".join(w["t"] for p in pages[:3] for l in p for w in l["words"])
    decided = re.search(r"Decided\s+([A-Z][a-z]+ \d{1,2}, \d{4})", first_text)
    argued = re.search(r"Argued\s+([A-Z][a-z]+ \d{1,2}, \d{4})", first_text)

    # Paragraphs, separately for body and footnotes, in reading order.
    body_paras, foot_items = [], []
    cur_body = cur_foot = None
    in_caption = False

    def new_para(kind, line):
        return {"text": "", "kind": kind, "page_start": line["page"], "page_breaks": [],
                "footnote_refs": [], "last_page": line["page"], "heading_size": line["h"] < body_h * 0.97}

    def append_words(para, words, line):
        pending_page = line["page"] if para["last_page"] != line["page"] and para["text"] else None
        para["last_page"] = line["page"]
        for idx, w in enumerate(words):
            t = w["t"]
            if w.get("sup") and para["kind"] != "foot-label":
                para["footnote_refs"].append({"offset": len(para["text"].rstrip("\u00ad")), "label": t})
                continue
            if not para["text"]:
                para["text"] = t
                continue
            prev = para["text"]
            if prev.endswith("\u00ad"):
                para["text"] = prev[:-1] + t
            elif prev.endswith("-") and w is words[0] and para.get("_line_end"):
                if rep.lossy or slip:
                    head = prev.rsplit(" ", 1)
                    joined = rep.hyphen(head[-1], t)
                    para["text"] = (head[0] + " " if len(head) == 2 else "") + joined
                else:
                    para["text"] = prev + t  # a hard hyphen in a soft-hyphen PDF is real
            elif prev.endswith(("—", "–")) and w is words[0] and para.get("_line_end"):
                para["text"] = prev + t
            else:
                para["text"] = prev + " " + t
            if pending_page is not None:
                # The break falls where this word starts (inside it, if hyphen-joined).
                para["page_breaks"].append({"offset": len(para["text"]) - len(t), "page": pending_page})
                pending_page = None
        para["_line_end"] = True

    for li, line in enumerate(stream):
        words = line["words"]
        text = " ".join(w["t"] for w in words if not w.get("sup"))
        margin = line["margin"] or line["x0"]
        indent = line["x0"] - margin
        if slip:
            # Each slip opinion opens with the Court's caption; drop it.
            if line["kind"] == "body" and text.strip() == "SUPREME COURT OF THE UNITED STATES":
                in_caption = True
            if in_caption:
                if re.fullmatch(r"\[[A-Z][a-z]+ \d{1,2}, \d{4}\]", text.strip()):
                    in_caption = False
                continue
        if line["kind"] == "body":
            centered = line["x0"] - margin > 40 and (line["right"] or line["x1"]) - line["x1"] > 40
            heading_line = line["h"] < body_h * 0.97
            starts = (cur_body is None or centered or 6 <= indent <= 16
                      or (heading_line and not (cur_body and cur_body["heading_size"]))
                      or (cur_body and cur_body["heading_size"] and not heading_line
                          and cur_body["text"].rstrip().endswith((".", ":")))
                      or (cur_body and cur_body["kind"] == "section"))
            if starts:
                cur_body = new_para("section" if centered else "text", line)
                body_paras.append(cur_body)
            append_words(cur_body, words, line)
        else:
            label_word = words[0] if words[0].get("sup") else None
            if label_word is not None:
                cur_foot = {"label": label_word["t"], "page": line["page"], "paras": [],
                            "after_para": len(body_paras)}
                foot_items.append(cur_foot)
                para = new_para("foot", line)
                cur_foot["paras"].append(para)
                append_words(para, words[1:], line)
            elif cur_foot is not None:
                para = cur_foot["paras"][-1]
                if 6 <= indent <= 16 and para["text"]:
                    para = new_para("foot", line)
                    cur_foot["paras"].append(para)
                append_words(para, words, line)

    # Ligature repair, word by word with context, before offsets are final.
    def fix_para(p):
        if not rep.lossy:
            return
        tokens = list(re.finditer(r"\S+", p["text"]))
        out, shift_points = [], []
        pos = 0
        for i, m in enumerate(tokens):
            tok = m.group(0)
            prev = WORD.findall(tokens[i - 1].group(0))[-1] if i and WORD.findall(tokens[i - 1].group(0)) else ""
            nxt = WORD.findall(tokens[i + 1].group(0))[0] if i + 1 < len(tokens) and WORD.findall(tokens[i + 1].group(0)) else ""
            # Each word part of the token ("case-specifc" has two).
            new_tok, parts = tok, list(WORD.finditer(tok))
            for j in range(len(parts) - 1, -1, -1):
                core = parts[j].group(0)
                before = parts[j - 1].group(0) if j else prev
                after = parts[j + 1].group(0) if j + 1 < len(parts) else nxt
                fixed = rep.ligature(core, before, after)
                if fixed != core:
                    new_tok = new_tok[:parts[j].start()] + fixed + new_tok[parts[j].end():]
            out.append(p["text"][pos:m.start()])
            if new_tok != tok:
                shift_points.append((m.start(), len(new_tok) - len(tok)))
            out.append(new_tok)
            pos = m.end()
        out.append(p["text"][pos:])
        p["text"] = "".join(out)
        for key_ in ("page_breaks", "footnote_refs"):
            for item in p[key_]:
                item["offset"] += sum(d for at, d in shift_points if at < item["offset"])

    for p in body_paras:
        fix_para(p)
    for f in foot_items:
        for p in f["paras"]:
            fix_para(p)

    # Split into opinions on the Court's headings; everything before the first
    # heading (syllabus, lineup, counsel) is not opinion text.
    opinions, current, header_refs = [], None, []
    marker_queue = []
    for p in body_paras:
        text = p["text"].strip()
        h = HEADING.match(text)
        pc = PER_CURIAM.match(text) if not opinions else None
        if (h or pc) and (p["heading_size"] or len(text) < 400):
            otype = opinion_type(h.group("role")) if h else "majority"
            if otype == "note":
                continue
            heading = text[:(h or pc).end()]
            current = {"heading": heading, "type": otype,
                       "author": justices(h.group("who")) if h else ["Per Curiam"],
                       "joined_by": justices(h.group("with") or "") if h else [],
                       "statement": False, "typed_by_table": False,
                       "paragraphs": [], "footnotes": []}
            opinions.append(current)
            rest = text[(h or pc).end():].strip()
            if not rest:
                header_refs += [(r["label"], p["page_start"]) for r in p["footnote_refs"]]
                continue
            shift = len(text) - len(rest)
            p = {**p, "text": rest,
                 "page_breaks": [{**b, "offset": max(0, b["offset"] - shift)} for b in p["page_breaks"]],
                 "footnote_refs": [{**r, "offset": max(0, r["offset"] - shift)} for r in p["footnote_refs"]]}
        if current is None:
            header_refs += [(r["label"], p["page_start"]) for r in p["footnote_refs"]]
            continue
        para = {k: p[k] for k in ("text", "kind", "page_start", "page_breaks", "footnote_refs")}
        current["paragraphs"].append(para)
        for r in p["footnote_refs"]:
            marker_queue.append((r["label"], len(opinions) - 1))

    # Footnotes printed before the first opinion heading belong to the caption,
    # counsel or syllabus (their markers may sit in lines that are not body text).
    first_heading = next((i for i, p in enumerate(body_paras)
                          if HEADING.match(p["text"].strip()) and (p["heading_size"] or len(p["text"]) < 400)), 0)
    header_items = [f for f in foot_items if f["after_para"] <= first_heading]
    foot_items = [f for f in foot_items if f["after_para"] > first_heading]
    header_refs = []  # handled by position above

    # Footnotes: matched to markers in reading order, label by label.
    by_label = {}
    for f in foot_items:
        by_label.setdefault(f["label"], []).append(f)
    for label, _ in header_refs:
        if by_label.get(label):
            by_label[label].pop(0)
    unmatched_markers = []
    for label, op_i in marker_queue:
        q = by_label.get(label)
        if q:
            f = q.pop(0)
            opinions[op_i]["footnotes"].append({
                "label": label, "page": f["page"],
                "paragraphs": [x["text"] for x in f["paras"]],
                "page_breaks": [x["page_breaks"] for x in f["paras"]],
            })
        else:
            unmatched_markers.append(label)

    return {
        "key": key,
        "source": source,
        "decided_text": decided.group(1) if decided else None,
        "argued_text": argued.group(1) if argued else None,
        "notes": [],
        "header_footnotes": [[x["text"] for x in f["paras"]] for f in header_items],
        "opinions": opinions,
        "cleaning": {
            "body_type_size": body_h,
            "lossy_font": rep.lossy,
            "unmatched_footnote_markers": unmatched_markers,
            "unmatched_notes": [f["label"] for q in by_label.values() for f in q],
            **rep.log,
        },
    }
