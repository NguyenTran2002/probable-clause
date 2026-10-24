"""Phase 3 paid check: where Anthropic's Citations splits a plain-text document into sentences.

Area 1, topic 5: a kept passage could go to the composition call whole, as a
plain-text document, and Citations would split it into sentences itself
("Plain text documents are automatically chunked into sentences"). How that
splitting treats legal citations ("U. S.", "19 How.", "Cal. Pen. Code") is not
documented. This sends the hardest passages in the corpus as plain-text
documents and asks Claude to cite each smallest citable piece separately, so
the citations' character ranges show where the pieces begin and end.

The passages are chosen by script: the paragraphs and footnotes with the most
periods that follow a short capitalised word or an initial and precede a
capital (the places a naive splitter breaks citations apart), under 2,500
characters, one per case; plus the hardest passage with an omission row
(". . .") and with a sentence ending inside quotation marks.

Model and effort: Sonnet 5.5 at low effort. Splitting is applied to the
document before the model sees it (INFERRED, not documented), so the model
should not change the boundaries; low effort keeps the call cheap.

Every call goes through probe_common.call (ledger, ceiling, no retries).
Outputs (data/verification/phase3/, gitignored): the chosen passages, the raw
response, and the pieces per passage.

Usage:
    uv run python scripts/probe_chunking.py [--select-only]
"""

import json
import re
import sys
from pathlib import Path

from probe_common import ROOT, call, client

CASES = ROOT / "data" / "corpus" / "cases"
OUT = ROOT / "data" / "verification" / "phase3"
MAX_CHARS = 2500  # keeps the call small
N_HARDEST = 8
ABBR_STOP = re.compile(r'(?:\b[A-Z][a-z]{0,3}|\b[A-Z])\.\s+(?=["(\[]?[A-Z0-9])')

SYSTEM = ("You are testing how documents are divided for citation. For each document, in order, "
          "cite every smallest citable piece of it, one piece per citation, in the order the pieces appear, "
          "covering the whole document. Never combine two pieces in one citation and never skip a piece. "
          "Before each citation write only the document number and piece number, like \"3.7 \", and nothing else.")


def units():
    for path in sorted(CASES.glob("*.json")):
        d = json.loads(path.read_text())
        for oi, op in enumerate(d["opinions"], start=1):
            for pi, p in enumerate((q for q in op["paragraphs"] if q["kind"] != "section"), start=1):
                yield {"id": f"{path.stem}-{oi}-p{pi}", "case": path.stem, "text": p["text"]}
            for ni, f in enumerate(op["footnotes"], start=1):
                for qi, t in enumerate(f["paragraphs"]):
                    yield {"id": f"{path.stem}-{oi}-n{ni}" + (f".{qi + 1}" if qi else ""), "case": path.stem, "text": t}


def select() -> list[dict]:
    pool = [u | {"score": len(ABBR_STOP.findall(u["text"]))} for u in units() if len(u["text"]) <= MAX_CHARS]
    pool.sort(key=lambda u: -u["score"])
    chosen, cases = [], set()
    for u in pool:
        if u["case"] not in cases and len(chosen) < N_HARDEST:
            chosen.append(u)
            cases.add(u["case"])
    for pattern, why in ((r"\. \. \.", "omission row"), (r'[.?!]["\']\s+[A-Z]', "sentence ending in a quotation")):
        extra = next(u for u in pool if re.search(pattern, u["text"]) and u not in chosen)
        chosen.append(extra | {"why": why})
    return chosen


def pieces(resp, docs) -> dict:
    out = {d["id"]: [] for d in docs}
    for b in resp.content:
        if b.type != "text":
            continue
        for c in b.citations or []:
            d = c.model_dump()
            if d.get("type") == "char_location":
                doc = docs[d["document_index"]]
                s, e = d["start_char_index"], d["end_char_index"]
                out[doc["id"]].append({"start": s, "end": e, "text": doc["text"][s:e],
                                       "cited_text_matches": d["cited_text"] == doc["text"][s:e]})
    return out


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    docs = select()
    (OUT / "chunking_passages.json").write_text(json.dumps(docs, indent=2, ensure_ascii=False))
    for i, d in enumerate(docs, start=1):
        print(f"{i:2} {d['id']:22} score {d['score']:2} {len(d['text']):5} chars {d.get('why', '')}")
    if "--select-only" in sys.argv:
        return 0
    content = [{"type": "document", "source": {"type": "text", "media_type": "text/plain", "data": d["text"]},
                "title": f"Document {i}", "citations": {"enabled": True}} for i, d in enumerate(docs, start=1)]
    content.append({"type": "text", "text": "Cite every piece of every document, one piece per citation, as instructed."})
    resp = call(client(), "chunking", "plain-text-documents", max_tokens=16000, system=SYSTEM,
                messages=[{"role": "user", "content": content}], output_config={"effort": "low"})
    (OUT / "chunking_response.json").write_text(resp.model_dump_json(indent=2))
    result = pieces(resp, docs)
    (OUT / "chunking_pieces.json").write_text(json.dumps(result, indent=2, ensure_ascii=False))
    for d in docs:
        ps = sorted(result[d["id"]], key=lambda p: p["start"])
        covered = sum(p["end"] - p["start"] for p in ps)
        print(f"{d['id']}: {len(ps)} pieces, {covered} of {len(d['text'])} characters cited")
    return 0


if __name__ == "__main__":
    sys.exit(main())
