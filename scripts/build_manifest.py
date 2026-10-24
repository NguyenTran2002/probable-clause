"""Corpus manifest: case and opinion metadata, coverage dates, token counts (§4.6, §4.8).

Reads data/corpus/cases/ and writes data/corpus/manifest.json. Case names and
citations come from the case list (scripts/pull_courtlistener.py); decision dates
from the official text (verified by verify_lineup.py), never CourtListener's
`date_filed`. No SCDB field is read (P1.8).

Token counts use Anthropic's token-counting endpoint (free; counts are
model-specific) with the model under consideration, one request per opinion:
its body paragraphs and footnotes, as Citations would receive them.

Usage:
    uv run python scripts/build_manifest.py [--no-tokens]
"""

import json
import sys
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from pull_courtlistener import CASES, KNOWN_CLUSTERS

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
CORPUS = ROOT / "data" / "corpus"
ENV_PATH = ROOT / ".env"
MODEL = "claude-sonnet-5-5"  # the user's leaning (brief §2); confirmed in Phase 2
PACE_S = 0.5  # placeholder until measured; the endpoint is rate-limited
CHICAGO = ZoneInfo("America/Chicago")

ROLE = {key: role for key, _, _, _, role in CASES} | {k: v[2] for k, v in KNOWN_CLUSTERS.items()}
NAME = {key: name for key, name, _, _, _ in CASES} | {k: v[0] for k, v in KNOWN_CLUSTERS.items()}
US_CITE = {key: us for key, _, us, _, _ in CASES}
# The Court's Term 2025 table assigns Chatrie 609 U.S. 605 (licensing notes);
# its text here is the slip opinion, paginated as such.
US_CITE["chatrie"] = "609 U.S. ___ (slip opinion; assigned 609 U.S. 605)"


def api_key() -> str:
    for raw in ENV_PATH.read_text(encoding="utf-8").splitlines():
        line = raw.strip().removeprefix("export ")
        if line.startswith("ANTHROPIC_API_KEY="):
            return line.split("=", 1)[1].strip().strip("'\"")
    sys.exit("ANTHROPIC_API_KEY not found in .env")


def opinion_text(op: dict) -> str:
    parts = [op["heading"]] + [p["text"] for p in op["paragraphs"]]
    for f in op["footnotes"]:
        parts += [f"[{f['label']}] " + "\n".join(f["paragraphs"])]
    return "\n\n".join(parts)


def main() -> int:
    count = "--no-tokens" not in sys.argv
    client = None
    if count:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key())

    cases, total_tokens, requests = [], 0, 0
    for path in sorted(CORPUS.glob("cases/*.json")):
        c = json.loads(path.read_text())
        key = c["key"]
        decided = datetime.strptime(c["decided_text"], "%B %d, %Y").date().isoformat()
        ops = []
        for n, op in enumerate(c["opinions"]):
            text = opinion_text(op)
            tokens = None
            if client:
                tokens = client.messages.count_tokens(
                    model=MODEL, messages=[{"role": "user", "content": text}]).input_tokens
                requests += 1
                time.sleep(PACE_S)
                total_tokens += tokens if ROLE[key] == "core" else 0
            ops.append({
                "id": f"{key}-{n}", "type": op["type"], "author": op["author"], "joined_by": op["joined_by"],
                "joined_by_source": op.get("joined_by_source", "heading"), "joined_by_note": op.get("joined_by_note"),
                "heading": op["heading"], "statement": op.get("statement", False),
                "paragraphs": sum(1 for p in op["paragraphs"] if p["kind"] != "section"),
                "footnotes": len(op["footnotes"]), "words": len(text.split()), "tokens": tokens,
            })
        cases.append({
            "key": key, "name": NAME[key], "citation": US_CITE[key], "decided": decided,
            "decided_source": c.get("decided_source", "official text"),
            "role": ROLE[key], "source": c["source"], "not_participating": c.get("notes", []),
            "slip_opinion": c["source"]["kind"] == "slip-opinion-pdf", "opinions": ops,
        })

    core = [x for x in cases if x["role"] == "core"]
    pulled = datetime.fromtimestamp((RAW / "citation_lookup.json").stat().st_mtime, CHICAGO).date().isoformat()
    manifest = {
        "coverage": {
            "latest_decision_full_pull": max(x["decided"] for x in cases),
            "latest_decision_in_corpus": max(x["decided"] for x in core),
            "ingested": pulled,
            "note": "The full pull is every case pulled: the core cases plus City of Ontario v. Quon, considered and left out (P1.14), whose date is earlier than the latest core case.",
        },
        "token_model": MODEL if count else None,
        "core_cases": len(core), "core_opinions": sum(len(x["opinions"]) for x in core),
        "core_tokens": total_tokens if count else None,
        "cases": cases,
    }
    (CORPUS / "manifest.json").write_text(json.dumps(manifest, indent=1, ensure_ascii=False))

    print(f"{'case':16} {'decided':10} {'role':12} {'ops':>3} {'words':>7} {'tokens':>7}")
    for x in cases:
        w = sum(o["words"] for o in x["opinions"])
        t = sum(o["tokens"] or 0 for o in x["opinions"])
        print(f"{x['key']:16} {x['decided']} {x['role']:12} {len(x['opinions']):>3} {w:>7} {t:>7}")
    print(f"core: {manifest['core_cases']} cases, {manifest['core_opinions']} opinions, {total_tokens} tokens "
          f"({MODEL}); {requests} token-count requests")
    print("coverage:", manifest["coverage"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
