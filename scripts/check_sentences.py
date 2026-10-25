"""Check the sentence splitter over the whole corpus (contract §4.A, T1.9).

Builds the passage texts from data/corpus/ itself, by contract §3's rules, so
it does not depend on the corpus index:
  - opinions are numbered from 1 in the manifest's order (`katz-1`);
  - every paragraph whose kind is not `section` is a passage, numbered from 1
    within its opinion (`katz-1-p1`);
  - each footnote is one passage, numbered from 1 in the opinion's footnote
    order (`katz-1-n1`), its paragraphs joined with "\\n\\n".

Asserts the passage counts, that every passage's sentences tile its text, and
that every footnote's paragraph join is a sentence boundary. Then lists the
suspicious splits (a split before a capital that follows "v.", "No.", a
section sign, a reporter abbreviation, an initial, a short capitalised word or
a number) for the main session's sampled review (T1.9; no subagent).

Usage:
    .venv/bin/python scripts/check_sentences.py
Writes data/verification/sentences/report.json (local, gitignored) and prints a summary.
"""

import json
import re
import statistics
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from api.corpus.sentences import LEGAL_ABBREVIATIONS, split_sentences  # noqa: E402
from api.settings import TIME_ZONE  # noqa: E402

CORPUS = ROOT / "data" / "corpus"
OUT = ROOT / "data" / "verification" / "sentences"

# GAP: the passage counts are not in api/settings.py. Basis: contract §3 and P4.2 (counted by script, Oct 24, 2026).
PARAGRAPH_PASSAGES = 1964
FOOTNOTE_PASSAGES = 498
ALL_PASSAGES = 2462

CONTEXT = 40  # characters shown on each side of a split in the report
CATEGORIES = ["v.", "No.", "section_sign", "initial", "reporter_abbreviation", "short_capitalised_word", "number"]
ABBREVIATION_WORDS = frozenset(e.split()[-1].removesuffix(".") for e in LEGAL_ABBREVIATIONS)
NUMBER = re.compile(r"\$?\d+(?:[.,:\-–]\d+)*%?")
CANDIDATE = re.compile(r"[.?!][\"')\]]*\s+(?=[\"'(\[]*[A-Z])")


def passages() -> list[dict]:
    manifest = json.loads((CORPUS / "manifest.json").read_text())
    out = []
    for case in manifest["cases"]:
        key = case["key"]
        data = json.loads((CORPUS / "cases" / f"{key}.json").read_text())
        assert len(data["opinions"]) == len(case["opinions"]), key
        for k, (listed, op) in enumerate(zip(case["opinions"], data["opinions"]), start=1):
            assert listed["type"] == op["type"], (key, k)
            content = [p for p in op["paragraphs"] if p["kind"] != "section"]
            for n, p in enumerate(content, start=1):
                out.append({"id": f"{key}-{k}-p{n}", "kind": "paragraph", "text": p["text"]})
            for n, f in enumerate(op["footnotes"], start=1):
                out.append({"id": f"{key}-{k}-n{n}", "kind": "footnote", "text": "\n\n".join(f["paragraphs"])})
    return out


def assert_tiles(text: str, spans: list[tuple[int, int]], pid: str) -> None:
    assert spans and spans[0][0] == 0 and spans[-1][1] == len(text), pid
    assert all(a < b for a, b in spans), pid
    assert all(b == c for (_, b), (c, _) in zip(spans, spans[1:])), pid
    assert "".join(text[a:b] for a, b in spans) == text, pid


def stop_before(text: str, cut: int) -> int | None:
    """The index of the stop that ends the sentence before `cut`, or None for a blank-line split."""
    m = re.search(r"[.?!][\"')\]]*\s+$", text[:cut])
    return m.start() if m and "\n\n" not in m.group(0) else None


def category(text: str, stop: int) -> str | None:
    """Contract §4.A's suspicious kinds, read from the token before the stop (and the token before that)."""
    before = text[:stop].split()
    token = before[-1] if before else ""
    prev = before[-2] if len(before) > 1 else ""
    core = token.lstrip("\"'([").rstrip("\"')]").removesuffix(".")
    core = re.split(r"[-–—]", core)[-1]
    if core in ("v", "vs"):
        return "v."
    if core in ("No", "Nos") or prev in ("No.", "Nos."):
        return "No."
    if prev in ("§", "§§") or "§" in token:
        return "section_sign"
    if re.fullmatch(r"[A-Z]", core) and not (core == "S" and prev == "U."):
        return "initial"
    if core in ABBREVIATION_WORDS or (NUMBER.fullmatch(token) and prev.rstrip(",").removesuffix(".") in ABBREVIATION_WORDS):
        return "reporter_abbreviation"
    if re.fullmatch(r"[A-Z][A-Za-z']{1,3}", core) and len(core.replace("'", "")) <= 4:
        return "short_capitalised_word"
    if NUMBER.fullmatch(token):
        return "number"
    return None


def context(text: str, cut: int) -> str:
    return text[max(0, cut - CONTEXT):cut] + "|" + text[cut:cut + CONTEXT]


def main() -> int:
    ps = passages()
    kinds = Counter(p["kind"] for p in ps)
    assert kinds["paragraph"] == PARAGRAPH_PASSAGES, kinds
    assert kinds["footnote"] == FOOTNOTE_PASSAGES, kinds
    assert len(ps) == ALL_PASSAGES and len({p["id"] for p in ps}) == ALL_PASSAGES

    sentences = Counter()
    lengths = []
    per_passage = []
    triggers = Counter()
    suspicious = {c: [] for c in CATEGORIES}
    declined = Counter()
    for p in ps:
        text, pid = p["text"], p["id"]
        spans = split_sentences(text)
        assert_tiles(text, spans, pid)
        starts = {a for a, _ in spans}
        assert all(m.end() in starts for m in re.finditer("\n\n", text)), pid   # the join is a boundary (§3)
        sentences[p["kind"]] += len(spans)
        per_passage.append(len(spans))
        lengths += [b - a for a, b in spans]
        cuts = [a for a, _ in spans[1:]]
        for cut in cuts:
            stop = stop_before(text, cut)
            if stop is None:
                triggers["blank_line"] += 1
                continue
            triggers[text[stop]] += 1
            c = category(text, stop)
            if c:
                suspicious[c].append({"passage": pid, "offset": cut, "context": context(text, cut)})
        for m in CANDIDATE.finditer(text):
            if m.end() not in starts:
                declined[category(text, m.start()) or "other"] += 1

    total = sum(sentences.values())
    report = {
        "generated": datetime.now(ZoneInfo(TIME_ZONE.value)).isoformat(timespec="seconds"),
        "rule": "T1.9; contract §4.A (api/corpus/sentences.py)",
        "passages": {"paragraph": kinds["paragraph"], "footnote": kinds["footnote"], "total": len(ps)},
        "sentences": {
            "total": total, "paragraph": sentences["paragraph"], "footnote": sentences["footnote"],
            "per_passage_median": statistics.median(per_passage), "per_passage_max": max(per_passage),
            "chars_median": statistics.median(lengths), "chars_max": max(lengths),
            "single_sentence_passages": sum(1 for n in per_passage if n == 1),
        },
        "splits": {"total": total - len(ps), "after": dict(sorted(triggers.items()))},
        "suspicious_counts": {c: len(v) for c, v in suspicious.items()},
        "suspicious": suspicious,
        "declined_candidates": dict(sorted(declined.items())),
        "notes": [
            "Each split is listed under the first category that fits, in the order of suspicious_counts.",
            "A split after a closing bracket or quotation mark is categorised by the word inside it, never as a number.",
            "declined_candidates counts stop, whitespace, capital places the splitter did not split, by the same categories.",
        ],
    }
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "report.json").write_text(json.dumps(report, indent=1, ensure_ascii=False) + "\n")

    print(f"passages: {kinds['paragraph']} paragraphs + {kinds['footnote']} footnotes = {len(ps)}; all tile")
    print(f"sentences: {total} ({sentences['paragraph']} in paragraphs, {sentences['footnote']} in footnotes)")
    print(f"splits: {total - len(ps)}, after {dict(sorted(triggers.items()))}")
    print("suspicious splits: " + ", ".join(f"{c} {len(v)}" for c, v in suspicious.items()))
    print(f"declined candidates: {dict(sorted(declined.items()))}")
    print(f"wrote {(OUT / 'report.json').relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
