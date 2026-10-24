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
import json
import re
import subprocess
import unicodedata
from collections import Counter
from pathlib import Path

from corpus_common import HEADING, PER_CURIAM, SECTION, joiners, justices, opinion_type, straighten

LIGATURES = {"ﬀ": "ff", "ﬁ": "fi", "ﬂ": "fl", "ﬃ": "ffi", "ﬄ": "ffl"}
DICT_PATH = Path("/usr/share/dict/words")
RAW_OPINIONS = Path(__file__).resolve().parent.parent / "data" / "raw" / "opinions"
_VOCAB = None


def vocabulary() -> set[str]:
    """Known English words: the system word list, the GCIDE and Webster's 1913
    lists (english-words package), and the words of the Lawbox copies in the raw
    cache, which supply legal terms and inflected forms."""
    global _VOCAB
    if _VOCAB is None:
        from english_words import get_english_words_set
        words = get_english_words_set(["web2", "gcide"], lower=True)
        if DICT_PATH.exists():
            words |= {w.strip().lower() for w in DICT_PATH.read_text().splitlines()}
        seen = Counter()
        for f in RAW_OPINIONS.glob("*.json"):
            lb = json.loads(f.read_text()).get("html_lawbox") or ""
            # Whole words only: "4th" must not contribute "th".
            seen.update({t.lower() for t in re.findall(r"(?<![A-Za-z0-9])[A-Za-z]+(?![A-Za-z0-9])",
                                                     re.sub(r"<[^>]+>", " ", lb))})
        # A Lawbox word counts only if two opinions use it: a one-off may be an
        # error of that copy ("thermalimaging").
        _VOCAB = words | {w for w, n in seen.items() if n >= 2}
    return _VOCAB
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
                t = unicodedata.normalize("NFC", html.unescape(w.group(5)))
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
                # Never a period (an ellipsis is spaced periods) or a bracket closing "[ ]".
                stray_punct = (merged and re.fullmatch(r"[,;:)\]’”]+", w["t"])
                               and not merged[-1]["t"].endswith("[")
                               and merged[-1]["t"] != "."  # ". . . ”": the print spaces an ellipsis from its quote
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
    # Body type size: the most common line height, rounded to half a point and
    # weighted by words (a scan's body lines scatter between 16.0 and 16.2,
    # while its footnotes may all read exactly 12.8).
    sizes = Counter()
    for p in pages:
        for l in p:
            sizes[round(l["h"] * 2) / 2] += len(l["words"])
    top = sizes.most_common(1)[0][0]
    body_h = Counter(l["h"] for p in pages for l in p if round(l["h"] * 2) / 2 == top).most_common(1)[0][0]
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

    def __init__(self, reference_text: str | None, own_text: str, lossy: bool, interior_text: str = ""):
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
        # Words printed inside a line (not first or last on it): how the document
        # itself prints a word when no line break is involved.
        self.mid_tokens = Counter(t.lower().replace("’", "'") for t in WORD.findall(interior_text))
        self.mid_hyphenated = Counter(m.lower().replace("’", "'")
                                      for m in re.findall(r"\b\w+(?:-\w+)+\b", interior_text))
        self.dict = vocabulary()
        self.log = {"ligatures_restored": [], "ligatures_unresolved": [],
                    "hyphens_joined": 0, "hyphen_decisions": []}

    def known(self, w: str) -> bool:
        # Not the document's own vocabulary: in a lossy PDF the broken forms
        # ("frst") recur and would vouch for themselves.
        w = w.lower().replace("’", "'")
        base = re.sub(r"'s$|s'$", "", w)
        # The word list has few inflected forms: try the common endings off.
        forms = {w, base} | {base[:-len(e)] + r for e, r in (("ies", "y"), ("es", ""), ("s", ""), ("ed", ""), ("ed", "e"),
                                                             ("ing", ""), ("ing", "e"), ("ly", ""))
                              if base.endswith(e) and len(base) - len(e) >= 3}
        forms |= {f[:-1] for f in list(forms) if len(f) > 4 and f[-1] == f[-2]}  # "referr" -> "refer"
        return any(x in self.ref_vocab or x in self.dict or x.replace("'", "’") in self.ref_vocab for x in forms)

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
        """Join a word broken at a line end ("left-" or "left" + soft hyphen) with
        "right", keeping the hyphen or not. The evidence is how this document
        prints the word inside a line; the reference copy is not used for the
        joined form, since its own extraction may have joined line breaks."""
        a = re.sub(r"^\W+", "", left.rstrip("-\u00ad"))
        b = re.sub(r"\W+$", "", right)
        a_core = WORD.findall(a)[-1] if WORD.findall(a) else a
        b_core = WORD.findall(b)[0] if WORD.findall(b) else b
        joined_core = (a_core + b_core).lower().replace("’", "'")
        hyph = f"{a_core}-{b_core}".lower().replace("’", "'")
        n_h = sum(c for h, c in self.mid_hyphenated.items() if hyph in h) + \
            sum(1 for h in self.ref_hyphenated if hyph in h.replace("’", "'"))
        n_j = self.mid_tokens.get(joined_core, 0) + self.mid_tokens.get(re.sub(r"'s$", "", joined_core), 0)
        lig_join = False
        if self.lossy and not n_j:
            fixed = self.ligature(a_core + b_core, "", "")  # "signi-" + "cance"
            lig_join = fixed.lower() != (a_core + b_core).lower()
        digits = bool(re.search(r"\d", a_core + b_core))
        if n_h > n_j:
            keep, why = True, f"printed hyphenated {n_h}x"
        elif n_j > n_h or lig_join:
            keep, why = False, f"printed solid {n_j}x"
        elif digits:
            keep, why = True, "number"
        elif a_core[:1].isupper() and b_core[:1].islower():
            keep, why = False, "name broken at a line end"
        elif self.known(joined_core):
            keep, why = False, "dictionary word"
        else:
            keep, why = True, "joined form unattested"
        self.log["hyphen_decisions"].append(f"{a_core}-|{b_core} -> {'kept' if keep else 'joined'} ({why})")
        if keep:
            self.log["hyphens_kept_count"] = self.log.get("hyphens_kept_count", 0) + 1
            return left.rstrip("\u00ad").rstrip("-") + "-" + right
        self.log["hyphens_joined"] += 1
        return left.rstrip("\u00ad").rstrip("-") + right


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


RULE = re.compile(r"^[—_\-–\s]{4,}$")  # a footnote separator rule
URLISH = re.compile(r"(https?://|www\.)\S*$")


def build_pdf_case(key: str, pdf: Path, first_page: int, reference_text: str | None,
                   slip: bool, source: dict) -> dict:
    pages = read_pages(pdf)
    body_h, info = classify(pages)
    lossy = not any(w["t"].endswith("­") for p in pages for l in p for w in l["words"]) and not slip
    own_text = " ".join(w["t"] for p in pages for l in p for w in l["words"])
    interior = " ".join(w["t"] for p in pages for l in p if l["kind"] != "header"
                        for w in l["words"][1:-1] if not w.get("sup"))
    rep = Repairer(reference_text, own_text, lossy=lossy and reference_text is not None, interior_text=interior)
    if slip:
        rep.lossy = False  # the slip PDF keeps its ligatures; only hyphens need deciding
    stream = lines_to_stream(pages, info, first_page, slip)

    first_text = " ".join(w["t"] for p in pages[:3] for l in p for w in l["words"])
    decided = re.search(r"Decided\s+([A-Z][a-z]+ \d{1,2}, \d{4})", first_text)
    argued = re.search(r"Argued\s+([A-Z][a-z]+ \d{1,2}, \d{4})", first_text)

    body_paras, foot_items = [], []
    cur_body = cur_foot = None
    in_caption = in_appendix = False

    def new_para(kind, line):
        return {"text": "", "kind": kind, "page_start": line["page"], "page_breaks": [],
                "footnote_refs": [], "last_page": line["page"], "heading_size": line["h"] < body_h * 0.97}

    def append_words(para, words, line):
        pending_page = line["page"] if para["last_page"] != line["page"] and para["text"] else None
        para["last_page"] = line["page"]
        for w in words:
            t = w["t"]
            if w.get("sup"):
                para["footnote_refs"].append({"offset": len(para["text"]), "label": t})
                continue
            prev = para["text"]
            first_on_line = w is words[0] and para.get("_line_end")
            if not prev:
                para["text"] = t
            elif first_on_line and prev.endswith(("-", "­")) and not prev.endswith("--"):
                # A word broken at the line end: soft hyphens mark real compound
                # hyphens too, so every break is decided the same way.
                head = prev.rsplit(" ", 1)
                if URLISH.search(head[-1]):
                    joined = head[-1].rstrip("­") + t
                else:
                    joined = rep.hyphen(head[-1], t)
                para["text"] = (head[0] + " " if len(head) == 2 else "") + joined
            elif first_on_line and (prev.endswith(("—", "–", "/", "www.")) or URLISH.search(prev.rsplit(" ", 1)[-1] or "")
                                    and not prev.endswith((".", ",", ")"))):
                para["text"] = prev + t  # closed-up dash, or a URL broken at the line end
            elif ((re.fullmatch(r"[,;:)\]]+", t) and not prev.endswith("[")) or prev.endswith("—")
                  or (t.startswith("—") and not prev.endswith(". . ."))):  # ". . . —was" keeps its space
                para["text"] = prev + t  # no space before closing punctuation or around an em dash
            else:
                para["text"] = prev + " " + t
            if pending_page is not None:
                # The break falls where this word starts (inside it, if hyphen-joined).
                para["page_breaks"].append({"offset": max(0, len(para["text"]) - len(t)), "page": pending_page})
                pending_page = None
        para["_line_end"] = True

    for line in stream:
        words = line["words"]
        text = " ".join(w["t"] for w in words if not w.get("sup")).strip()
        margin = line["margin"] or line["x0"]
        indent = line["x0"] - margin
        if slip:
            # Each slip opinion opens with the Court's caption; drop it.
            if line["kind"] == "body" and text == "SUPREME COURT OF THE UNITED STATES":
                in_caption = True
            if in_caption:
                if re.fullmatch(r"\[[A-Z][a-z]+ \d{1,2}, \d{4}\]", text):
                    in_caption = False
                continue
        if RULE.fullmatch(text):
            continue  # the rule printed above footnotes
        appendix_title = line["kind"] == "body" and bool(re.match(r"APPENDIX\b", text, re.I)) and len(text) < 120
        if appendix_title:
            in_appendix = True  # an appendix's captions are small type, not footnotes
        elif line["kind"] == "body" and HEADING.match(text):
            in_appendix = False  # the next opinion begins
        labelled = line["kind"] == "foot" and words[0].get("sup")
        if line["kind"] == "body" or (in_appendix and not labelled):
            centered = line["x0"] - margin > 40 and (line["right"] or line["x1"]) - line["x1"] > 40
            section = centered and bool(SECTION.match(text))
            # A line of small capitals ("Justice Kennedy, Justice Alito") is small
            # too; a heading line is indented and opens like a heading.
            heading_line = (line["h"] < body_h * 0.97 and line["kind"] == "body" and (6 <= indent <= 16 or centered)
                            and bool(re.match(r"(MR\.? |THE CHIEF|CHIEF JUSTICE|JUSTICE|PER CURIAM)", text, re.I)))
            starts = (cur_body is None or centered or 6 <= indent <= 16
                      or (heading_line and not (cur_body and cur_body["heading_size"]))
                      or (cur_body and cur_body["heading_size"] and not heading_line
                          and cur_body["text"].rstrip().endswith((".", ":")))
                      or (cur_body and cur_body["kind"] in ("section", "centered")))
            if line["kind"] == "foot" and cur_body and cur_body["kind"] == "appendix" and not (6 <= indent <= 16):
                starts = False
            starts = starts or appendix_title
            if starts:
                kind = "section" if section else ("appendix" if in_appendix else ("centered" if centered else "text"))
                cur_body = new_para(kind, line)
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

    # "* * *" arrives as three centered lines; a centered non-section line is
    # its own paragraph (as "It is so ordered." can be).
    merged = []
    for p in body_paras:
        if merged and p["kind"] == "section" and re.fullmatch(r"\*( \*)*", p["text"]) \
                and merged[-1]["kind"] == "section" and re.fullmatch(r"\*( \*)*", merged[-1]["text"]):
            merged[-1]["text"] += " " + p["text"]
            continue
        if p["kind"] == "centered":
            p["kind"] = "text"
        merged.append(p)
    body_paras = merged

    # Ligature repair, word by word with context, before offsets are final.
    def fix_para(p):
        if not rep.lossy:
            return
        # A letter-spaced word the text layer split ("af ter"): two non-words that
        # make a known word together are one word, not a dropped ligature.
        for m in reversed(list(re.finditer(r"\b([A-Za-z]{1,6}) ([A-Za-z]{1,8})\b", p["text"]))):
            a, b = m.group(1), m.group(2)
            if not rep.known(a) and not rep.known(b) and rep.known(a + b):
                at = m.start(2) - 1
                p["text"] = p["text"][:at] + p["text"][at + 1:]
                for key_ in ("page_breaks", "footnote_refs"):
                    for item in p[key_]:
                        item["offset"] -= 1 if item["offset"] > at else 0
                rep.log.setdefault("split_words_joined", []).append(a + "|" + b)
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
    opinions, current, marker_queue = [], None, []
    first_heading = None
    for i, p in enumerate(body_paras):
        text = p["text"].strip()
        h = HEADING.match(text)
        pc = PER_CURIAM.match(text) if not opinions else None
        if (h or pc) and (p["heading_size"] or len(text) < 400):
            otype = opinion_type(h.group("role")) if h else "majority"
            if otype == "note":
                continue
            first_heading = i if first_heading is None else first_heading
            names, note = joiners(h.group("who"), h.group("with"), h.group("role")) if h else ([], None)
            current = {"heading": text[:(h or pc).end()], "type": otype,
                       "author": justices(h.group("who")) if h else ["Per Curiam"],
                       "joined_by": names, "joined_by_note": note,
                       "statement": False, "typed_by_table": False,
                       "paragraphs": [], "footnotes": []}
            opinions.append(current)
            rest = text[(h or pc).end():].strip()
            if not rest:
                continue
            shift = len(text) - len(rest)
            p = {**p, "text": rest,
                 "page_breaks": [{**b, "offset": max(0, b["offset"] - shift)} for b in p["page_breaks"]],
                 "footnote_refs": [{**r, "offset": max(0, r["offset"] - shift)} for r in p["footnote_refs"]]}
        if current is None:
            continue
        current["paragraphs"].append({k: p[k] for k in ("text", "kind", "page_start", "page_breaks", "footnote_refs")})
        for r in p["footnote_refs"]:
            marker_queue.append((r["label"], len(opinions) - 1))

    # Footnotes printed before the first opinion heading belong to the caption,
    # counsel or syllabus (their markers may sit in lines that are not body text).
    first_heading = first_heading or 0
    header_count = sum(1 for f in foot_items if f["after_para"] <= first_heading)
    foot_items = [f for f in foot_items if f["after_para"] > first_heading]

    by_label = {}
    for f in foot_items:
        by_label.setdefault(f["label"], []).append(f)
    unmatched_markers = []
    for label, op_i in marker_queue:
        q = by_label.get(label)
        if q:
            f = q.pop(0)
            opinions[op_i]["footnotes"].append({
                "label": label, "page": f["page"],
                "paragraphs": [x["text"] for x in f["paras"]],
                "page_starts": [x["page_start"] for x in f["paras"]],
                "page_breaks": [x["page_breaks"] for x in f["paras"]],
            })
        else:
            unmatched_markers.append(label)

    for op in opinions:  # P1.17
        op["heading"] = straighten(op["heading"])
        for p in op["paragraphs"]:
            p["text"] = straighten(p["text"])
        for f in op["footnotes"]:
            f["paragraphs"] = [straighten(x) for x in f["paragraphs"]]

    return {
        "key": key,
        "source": source,
        "decided_text": decided.group(1) if decided else None,
        "argued_text": argued.group(1) if argued else None,
        "notes": [],
        "header_footnotes_dropped": header_count,
        "opinions": opinions,
        "cleaning": {
            "body_type_size": body_h,
            "lossy_font": rep.lossy,
            "unmatched_footnote_markers": unmatched_markers,
            "unmatched_notes": [f["label"] for q in by_label.values() for f in q],
            **rep.log,
        },
    }
