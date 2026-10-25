"""The corpus as citable passages (contract §3, §4.B; T1.6, T1.9, T5.6).

Loads data/corpus/ (frozen, committed) into `Passage` objects: one per content paragraph and one per
footnote. Section headings are never passages (T1.6); they only set the section label.
"""

import copy
import json
import re
from pathlib import Path
from typing import Sequence

from api.corpus.sentences import split_sentences
from api.errors import ToolInputError
from api.settings import READ_AROUND_MAX, value
from api.types import CorpusLabel, OpinionGroup, Passage

CASE_PAGE_FORMS = "'<case_key>:<U.S. Reports page>' (for example 'katz:350')"
PASSAGE_FORMS = "a passage ID such as 'katz-1-p12' or 'katz-1-n1'"
PASSAGE_ID = re.compile(r"^(?P<opinion>[a-z0-9_]+-\d+)-(?P<kind>[pn])(?P<n>\d+)$")
OPINION_ID = re.compile(r"^[a-z0-9_]+-\d+$")
ROMAN = ["I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X", "XI", "XII"]


# ---------- section labels (contract §3) ----------

def _norm_head(s: str) -> str:
    return re.sub(r"[\s.]", "", s).upper()


def level(label: str):
    """The reading of a numbered heading. A copy of scripts/check_structure.py's `level()` (the existing reading
    of I/V/C/D, numerals or letters), so the api image does not depend on scripts/; a test compares the two."""
    t = _norm_head(label)
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


_LETTER_WITH_TITLE = re.compile(r"^\s*([A-Z])\.\s+(\S.*)$")
_APPENDIX_TITLE = re.compile(r"^\s*APPENDIX\b", re.I)


def _heading_part(text: str):
    """(level, numeral text) of a numbered heading, or None for rows that are not labels."""
    lv = level(text)[0]
    if isinstance(lv, int):
        return lv, text.strip().rstrip(".").strip()
    m = _LETTER_WITH_TITLE.match(text)      # "A. TITLE I—THE RECORDKEEPING REQUIREMENTS": the letter only
    if m and not re.search(r"[a-z]{3}", m.group(2)):
        lv = level(m.group(1))[0]
        if isinstance(lv, int):
            return lv, m.group(1)
    return None


def label_paragraphs(items: Sequence[tuple[str, str]]) -> list[str | None]:
    """The section label of each non-section item, from (kind, text) rows in reading order (T1.6).

    Numbered headings build a stack joined with "-"; an appendix title row becomes the label of what follows,
    unnumbered title rows inside it change nothing; omission rows and letterhead lines are not labels.
    """
    stack: list[tuple[int, str]] = []
    appendix: str | None = None
    out: list[str | None] = []
    for kind, text in items:
        if kind == "section":
            if _APPENDIX_TITLE.match(text):
                appendix = text.strip()
                continue
            part = _heading_part(text)
            if part and appendix is None:
                lv, numeral = part
                while stack and stack[-1][0] >= lv:
                    stack.pop()
                stack.append((lv, numeral))
            continue
        if appendix is not None:
            out.append(appendix)
        elif kind == "appendix":
            out.append("Appendix")           # an appendix with no title row (the Kyllo and Carpenter dissents)
        else:
            out.append("-".join(t for _, t in stack) or None)
    return out


# ---------- small helpers ----------

CREDITS = {"courtlistener-lawbox": "courtlistener", "govinfo-us-reports-pdf": "us_reports", "slip-opinion-pdf": "slip_opinion"}


def credit_of(case_manifest: dict) -> str:
    kind = case_manifest["source"]["kind"]
    if kind not in CREDITS:
        raise ValueError(f"{case_manifest['key']}: unknown text source kind {kind!r}")
    return CREDITS[kind]


def opinion_groups(opinion_type: str) -> tuple[OpinionGroup, ...]:
    """T1.4's four groups; a type with both concurrence and dissent maps to both."""
    t = opinion_type.lower()
    groups: list[OpinionGroup] = []
    if "plurality" in t:
        groups.append("plurality")
    if "concurring" in t or "concurrence" in t:
        groups.append("concurrence")
    if "dissent" in t:
        groups.append("dissent")
    if not groups:
        if t != "majority":
            raise ValueError(f"unknown opinion type {opinion_type!r}")
        groups.append("majority")
    return tuple(groups)


def _resolve_root(root: Path) -> Path:
    root = Path(root)
    if (root / "manifest.json").exists():
        return root
    if (root / "data" / "corpus" / "manifest.json").exists():      # the repository root
        return root / "data" / "corpus"
    raise FileNotFoundError(f"no corpus manifest under {root}")


def _last_page(first: int, breaks: list[dict]) -> int:
    return max([first] + [b["page"] for b in breaks])


# ---------- the corpus ----------

class Corpus:
    label: CorpusLabel
    passages: dict[str, Passage]
    manifest: dict
    coverage: dict
    catalog_text: str
    case_keys: frozenset[str]

    @classmethod
    def load(cls, root: Path, exclude: tuple[str, ...] = ()) -> "Corpus":
        """Load the frozen corpus. `exclude=("chatrie",)` is the recording-only switch (T5.6, contract §3)."""
        if tuple(exclude) not in ((), ("chatrie",)):
            raise ValueError("exclude must be () or ('chatrie',): the only switch T5.6 allows")
        self = cls()
        corpus_dir = _resolve_root(root)
        manifest = json.loads((corpus_dir / "manifest.json").read_text(encoding="utf-8"))
        self.label = "before_chatrie" if exclude else "full"
        manifest = copy.deepcopy(manifest)
        manifest["cases"] = [c for c in manifest["cases"] if c["key"] not in exclude]
        if exclude:
            latest = max(c["decided"] for c in manifest["cases"])
            manifest["coverage"]["latest_decision_full_pull"] = latest
            manifest["coverage"]["latest_decision_in_corpus"] = latest
            manifest["core_cases"] = len(manifest["cases"])
            manifest["core_opinions"] = sum(len(c["opinions"]) for c in manifest["cases"])
            manifest["core_tokens"] = sum(o["tokens"] for c in manifest["cases"] for o in c["opinions"])
        self.manifest = manifest
        cov = manifest["coverage"]
        self.coverage = {k: cov[k] for k in ("latest_decision_full_pull", "latest_decision_in_corpus", "ingested")}
        self.case_keys = frozenset(c["key"] for c in manifest["cases"])
        self.passages = {}
        self._opinions: dict[str, dict] = {}       # opinion_id -> {"case", "paragraph": [ids], "footnote": [ids]}
        for case_m in manifest["cases"]:
            case = json.loads((corpus_dir / "cases" / f"{case_m['key']}.json").read_text(encoding="utf-8"))
            for k, (op_m, op) in enumerate(zip(case_m["opinions"], case["opinions"]), 1):
                self._add_opinion(case_m, k, op_m, op)
        self._order = {pid: i for i, pid in enumerate(self.passages)}
        self.authors = frozenset(
            {a for p in self.passages.values() for a in p.authors}
            | ({"per curiam"} if any(not p.authors for p in self.passages.values()) else set()))
        self.catalog_text = self._catalog()
        return self

    # -- loading --

    def _add_opinion(self, case_m: dict, k: int, op_m: dict, op: dict) -> None:
        oid = f"{case_m['key']}-{k}"
        rows = [(p["kind"], p["text"]) for p in op["paragraphs"]]
        labels = iter(label_paragraphs(rows))
        paragraphs = [(p, next(labels)) for p in op["paragraphs"] if p["kind"] != "section"]
        footnotes = op["footnotes"]
        refs = [(i, r) for i, (p, _) in enumerate(paragraphs, 1) for r in p["footnote_refs"]]
        if len(refs) != len(footnotes) or any(r["label"] != f["label"] for (_, r), f in zip(refs, footnotes)):
            raise ValueError(f"{oid}: footnote references do not match the footnotes one to one in label order")
        cited_by: dict[int, int] = {}                      # footnote number -> paragraph number
        fn_ids_of: dict[int, list[str]] = {}
        marks_of: dict[int, list[tuple[int, str]]] = {}
        for n, (pi, r) in enumerate(refs, 1):
            cited_by[n] = pi
            fn_ids_of.setdefault(pi, []).append(f"{oid}-n{n}")
            marks_of.setdefault(pi, []).append((r["offset"], f"{oid}-n{n}"))
        common = dict(
            case_key=case_m["key"], opinion_id=oid, case_name=case_m["name"], citation=case_m["citation"],
            decided=case_m["decided"], slip_opinion=bool(case_m["slip_opinion"]), opinion_type=op_m["type"],
            opinion_groups=opinion_groups(op_m["type"]),
            authors=tuple(a for a in op_m["author"] if a.lower() != "per curiam"),
            joined_by=tuple(op_m["joined_by"]), joined_by_source=op_m["joined_by_source"])
        ids = {"paragraph": [], "footnote": []}
        section_of: dict[int, str | None] = {}
        for i, (p, label) in enumerate(paragraphs, 1):
            pid = f"{oid}-p{i}"
            section_of[i] = label
            marks = tuple(sorted(marks_of.get(i, []), key=lambda m: m[0]))
            self.passages[pid] = Passage(
                id=pid, kind="paragraph", text=p["text"], sentences=_tile(p["text"]), section=label,
                page_start=p["page_start"], page_end=_last_page(p["page_start"], p["page_breaks"]),
                position=i, of=len(paragraphs), paragraph_kind=p["kind"], footnote_label=None,
                footnotes=tuple(fn_ids_of.get(i, [])), marker_offsets=marks, **common)
            ids["paragraph"].append(pid)
        for n, f in enumerate(footnotes, 1):
            pid = f"{oid}-n{n}"
            text = "\n\n".join(f["paragraphs"])
            breaks = [b for pb in f["page_breaks"] for b in pb]
            pages = [f["page"]] + list(f.get("page_starts", []))
            self.passages[pid] = Passage(
                id=pid, kind="footnote", text=text, sentences=_tile(text), section=section_of[cited_by[n]],
                page_start=f["page"], page_end=max(pages + [b["page"] for b in breaks]),
                position=n, of=len(footnotes), paragraph_kind=None, footnote_label=f["label"],
                cited_by=(f"{oid}-p{cited_by[n]}",), **common)
            ids["footnote"].append(pid)
        self._opinions[oid] = {"case": case_m["key"], "manifest": op_m, **ids}

    # -- text --

    def loop_text(self, passage_id: str) -> str:
        """The paragraph's text with a "[n. <label>]" marker at each footnote reference (contract §3).

        A reference's `offset` is where the marker goes: the text before it is text[:offset]."""
        p = self.passages[passage_id]
        if not p.marker_offsets:
            return p.text
        out, last = [], 0
        for off, fid in p.marker_offsets:
            out.append(p.text[last:off])
            out.append(f"[n. {self.passages[fid].footnote_label}]")
            last = off
        out.append(p.text[last:])
        return "".join(out)

    def attached_footnotes(self, passage_id: str) -> list[Passage]:
        return [self.passages[f] for f in self.passages[passage_id].footnotes]

    # -- reads (T1.3, T1.6) --

    def read(self, target: str, before: int, after: int) -> list[Passage]:
        top = int(value(READ_AROUND_MAX))
        for name, n in (("before", before), ("after", after)):
            if isinstance(n, bool) or not isinstance(n, int) or not 0 <= n <= top:
                raise ToolInputError(f"'{name}' must be a whole number from 0 to {top}; got {n!r}.")
        if not isinstance(target, str) or not target.strip():
            raise ToolInputError(f"Give one target: {PASSAGE_FORMS}, or {CASE_PAGE_FORMS}.")
        target = target.strip().lower()          # IDs and case keys are lower case
        if ":" in target:
            selected = self._page_passages(target)
        else:
            selected = [self._passage_target(target)]
        groups: dict[tuple[str, str], list[int]] = {}
        for p in selected:
            lst = self._opinions[p.opinion_id][p.kind]
            groups.setdefault((p.opinion_id, p.kind), []).append(lst.index(p.id))
        keep: set[str] = set()
        for (oid, kind), idxs in groups.items():
            lst = self._opinions[oid][kind]
            keep.update(lst[max(0, min(idxs) - before): max(idxs) + after + 1])
        return [self.passages[pid] for pid in sorted(keep, key=self._order.__getitem__)]

    def _unknown_case(self, name: str) -> ToolInputError:
        return ToolInputError(f"Unknown case or opinion '{name}'. Case keys: {', '.join(sorted(self.case_keys))}.")

    def _passage_target(self, target: str) -> Passage:
        if target in self.passages:
            return self.passages[target]
        m = PASSAGE_ID.match(target)
        if m and m.group("opinion") in self._opinions:
            oid = m.group("opinion")
            o = self._opinions[oid]
            fn = (f" and footnotes {o['footnote'][0]} to {o['footnote'][-1]}" if o["footnote"]
                  else "; it has no footnotes")
            raise ToolInputError(f"No passage '{target}'. {oid} has paragraphs {o['paragraph'][0]} to {o['paragraph'][-1]}{fn}.")
        if m:
            case_key = m.group("opinion").rsplit("-", 1)[0]
            ops = [o for o in self._opinions if o.rsplit("-", 1)[0] == case_key]
            if ops:
                raise ToolInputError(f"No opinion '{m.group('opinion')}'. Case {case_key} has opinions {ops[0]} to {ops[-1]}.")
        raise ToolInputError(f"Unknown target '{target}'. A target is {PASSAGE_FORMS}, or {CASE_PAGE_FORMS}. "
                             f"Case keys: {', '.join(sorted(self.case_keys))}.")

    def _page_passages(self, target: str) -> list[Passage]:
        left, _, right = target.partition(":")
        left, right = left.strip(), right.strip()
        if not right.isdigit():
            raise ToolInputError(f"'{target}': the part after ':' must be a page number. A page target is {CASE_PAGE_FORMS}.")
        page = int(right)
        if left in self.case_keys:
            ops = [oid for oid, o in self._opinions.items() if o["case"] == left]
            if self.passages[self._opinions[ops[0]]["paragraph"][0]].slip_opinion:
                raise ToolInputError(
                    f"{left} is a slip opinion: its pages restart at 1 in each of its opinions, so a case-level page "
                    f"is ambiguous. Give the opinion and its slip page instead: '<opinion_id>:<slip page>', for "
                    f"example '{ops[0]}:{page}' (opinions {ops[0]} to {ops[-1]}).")
            found = [p for p in self.passages.values()
                     if p.case_key == left and p.page_start <= page <= p.page_end]
            what = f"{left} has no passage on U.S. Reports page {page}"
            lo = min(p.page_start for p in self.passages.values() if p.case_key == left)
            hi = max(p.page_end for p in self.passages.values() if p.case_key == left)
            rng = f"its passages run from page {lo} to page {hi}"
        elif OPINION_ID.match(left) and left in self._opinions:
            ps = [p for p in self.passages.values() if p.opinion_id == left]
            if not ps[0].slip_opinion:
                raise ToolInputError(f"'{target}': page targets for {ps[0].case_key} use U.S. Reports pages with the case "
                                     f"key: '{ps[0].case_key}:{page}'. The '<opinion_id>:<page>' form is for slip opinions only.")
            found = [p for p in ps if p.page_start <= page <= p.page_end]
            what = f"{left} has no passage on slip page {page}"
            rng = f"its passages run from slip page {min(p.page_start for p in ps)} to slip page {max(p.page_end for p in ps)}"
        else:
            raise self._unknown_case(left)
        if not found:
            raise ToolInputError(f"{what}; {rng}.")
        return found

    # -- catalog (T1.6) --

    def _catalog(self) -> str:
        lines = [
            f"Corpus: {len(self.manifest['cases'])} Supreme Court cases, {len(self._opinions)} opinions. Passage IDs: "
            "<opinion ID>-p<n> for a paragraph, <opinion ID>-n<n> for a footnote, counted from 1 in each opinion.",
            "The opinion-type filter groups the exact types into four groups (majority, plurality, concurrence, dissent); "
            "results show each opinion's exact type, and you describe opinions by the exact type, never by the group. "
            "An opinion concurring in part and dissenting in part belongs to both concurrence and dissent.",
        ]
        for c in self.manifest["cases"]:
            lines.append("")
            slip = c["slip_opinion"]
            lines.append(f"{c['key']} | {c['name']} | {c['citation']} | decided {c['decided']}")
            for k in range(1, len(c["opinions"]) + 1):
                oid = f"{c['key']}-{k}"
                o = self._opinions[oid]
                m = o["manifest"]
                ps = [self.passages[i] for i in o["paragraph"] + o["footnote"]]
                lo, hi = min(p.page_start for p in ps), max(p.page_end for p in ps)
                pages = (f"slip pages {lo} to {hi}" if slip else f"U.S. Reports pages {lo} to {hi}")
                par = _range("paragraph", o["paragraph"])
                fn = _range("footnote", o["footnote"])
                author = ", ".join(m["author"]) if m["author"] else "unknown"
                lines.append(f"  {oid} | {m['type']} | {author} | {_joiners(m)} | {par} | {fn} | {pages}")
        return "\n".join(lines)


def _range(noun: str, ids: list[str]) -> str:
    """The count beside the ID range (contract §3): "31 paragraphs (x-p1 to x-p31)", "0 footnotes"."""
    if not ids:
        return f"0 {noun}s"
    if len(ids) == 1:
        return f"1 {noun} ({ids[0]})"
    return f"{len(ids)} {noun}s ({ids[0]} to {ids[-1]})"


def _joiners(m: dict) -> str:
    if m["joined_by_source"] == "per curiam":
        return "per curiam"
    if m["joined_by"]:
        s = "joined by " + ", ".join(m["joined_by"])
    elif m["joined_by_source"] == "not printed":
        s = "joined by: not printed"      # an empty list here means unknown, never nobody (P1.18)
    else:
        s = "joined by no one"
    if m.get("joined_by_note"):
        s += f" ({m['joined_by_note']})"
    return s


def _tile(text: str) -> tuple[tuple[int, int], ...]:
    return tuple((int(a), int(b)) for a, b in split_sentences(text))


# ---------- the label list the main session reviews before the embedding ----------

def section_label_report(corpus: Corpus) -> str:
    """For each opinion, its distinct labels in reading order with the number of passages under each."""
    by_opinion: dict[str, dict[str | None, int]] = {}
    for p in corpus.passages.values():
        counts = by_opinion.setdefault(p.opinion_id, {})
        counts[p.section] = counts.get(p.section, 0) + 1
    lines = []
    for oid, counts in by_opinion.items():
        first = next(p for p in corpus.passages.values() if p.opinion_id == oid)
        lines.append(f"{oid} [{first.opinion_type}; {', '.join(first.authors) or 'per curiam'}; "
                     f"{sum(counts.values())} passages; {len(counts)} labels]")
        for label, n in counts.items():
            lines.append(f"  {'(none)' if label is None else label}  ({n})")
    return "\n".join(lines) + "\n"


def write_section_labels(corpus: Corpus, path: Path) -> None:
    """Write the label list for the main session's review (data/verification/sections/labels.txt, gitignored)."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(section_label_report(corpus), encoding="utf-8")
