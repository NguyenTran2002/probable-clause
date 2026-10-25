"""The static files the web image carries (contract §11.1, §11.3, §5.1; T4.3, T5.1).

Always generated from the full corpus: the recording-only switch never reaches the web files.
"""

import json
from pathlib import Path

from api import settings
from api.corpus.store import Corpus, _resolve_root, credit_of

# The page's figures (contract §5.1), by the names api/settings.py gives them.
# From v2.0 also the figures the page's wording names (T5.3, T5.4, contract §5's busy text; P4.31).
CONFIG_NAMES = ("WAKE_CHECK_TIMEOUT_S", "WAKE_CHECK_GAP_S", "LONG_WAIT_S", "WAKE_GIVE_UP_S", "HEARTBEAT_INTERVAL_S",
                "PAGE_WATCHDOG_S", "QUESTION_MAX_CHARS", "UPDATE_SEARCHES_PER_RUN", "EXA_NUM_RESULTS_DEFAULT",
                "EXA_TEXT_CHARS", "MAX_CONCURRENT_RUNS", "RUN_DEADLINE_S", "ABANDON_AFTER_S", "EVENTS_TTL_S")


def _write(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")


def reader_file(case_m: dict, k: int, op_m: dict, op: dict, credit: str) -> dict:
    oid = f"{case_m['key']}-{k}"
    paragraphs, n_par, n_ref = [], 0, 0
    for p in op["paragraphs"]:
        is_section = p["kind"] == "section"
        if not is_section:
            n_par += 1
        refs = []
        for r in p["footnote_refs"]:
            n_ref += 1
            refs.append({"offset": r["offset"], "label": r["label"], "footnote_id": f"{oid}-n{n_ref}"})
        paragraphs.append({"id": None if is_section else f"{oid}-p{n_par}", "kind": p["kind"], "text": p["text"],
                           "page_start": p["page_start"], "page_breaks": p["page_breaks"], "footnote_refs": refs})
    footnotes = [{"id": f"{oid}-n{n}", "label": f["label"], "page": f["page"], "paragraphs": f["paragraphs"],
                  "page_starts": f["page_starts"], "page_breaks": f["page_breaks"]}
                 for n, f in enumerate(op["footnotes"], 1)]
    authors = [a for a in op_m["author"] if a.lower() != "per curiam"]       # as Passage.authors (types.py)
    return {"opinion_id": oid,
            "case": {"key": case_m["key"], "name": case_m["name"], "citation": case_m["citation"],
                     "decided": case_m["decided"], "slip_opinion": bool(case_m["slip_opinion"]), "credit": credit},
            "type": op_m["type"], "authors": authors, "joined_by": op_m["joined_by"],
            "joined_by_source": op_m["joined_by_source"], "joined_by_note": op_m["joined_by_note"],
            "heading": op_m["heading"], "paragraphs": paragraphs, "footnotes": footnotes}


def build_web_data(corpus_root: Path, out_dir: Path) -> None:
    """Write opinions/<opinion_id>.json, corpus.json and config.json into out_dir."""
    corpus = Corpus.load(corpus_root)          # full corpus; also checks the data loads as passages
    corpus_dir = _resolve_root(corpus_root)
    out = Path(out_dir)
    cases, counts = [], {}
    for case_m in corpus.manifest["cases"]:
        case = json.loads((corpus_dir / "cases" / f"{case_m['key']}.json").read_text(encoding="utf-8"))
        credit = credit_of(case_m)
        counts[credit] = counts.get(credit, 0) + 1
        ops = []
        for k, (op_m, op) in enumerate(zip(case_m["opinions"], case["opinions"]), 1):
            r = reader_file(case_m, k, op_m, op, credit)
            for p in r["paragraphs"]:
                assert p["id"] is None or p["id"] in corpus.passages
            _write(out / "opinions" / f"{r['opinion_id']}.json", r)
            ops.append({"opinion_id": r["opinion_id"], "type": r["type"], "authors": r["authors"],
                        "joined_by": r["joined_by"], "joined_by_source": r["joined_by_source"],
                        "joined_by_note": r["joined_by_note"], "heading": r["heading"],
                        "paragraphs": op_m["paragraphs"], "footnotes": op_m["footnotes"]})
        cases.append({"key": case_m["key"], "name": case_m["name"], "citation": case_m["citation"],
                      "decided": case_m["decided"], "slip_opinion": bool(case_m["slip_opinion"]), "credit": credit,
                      "opinions": ops})
    _write(out / "corpus.json", {
        "cases": cases, "case_count": len(cases), "opinion_count": sum(len(c["opinions"]) for c in cases),
        "earliest_decided": min(c["decided"] for c in cases), "coverage": corpus.coverage, "source_counts": counts})
    _write(out / "config.json", {n: getattr(settings, n).value for n in CONFIG_NAMES})
