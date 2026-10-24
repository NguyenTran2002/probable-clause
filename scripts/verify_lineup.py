"""P1.1 verification of each case's metadata: decision date and opinion lineup.

For each built case:
  - decision date: the corpus's (from the source's header) against the official
    PDF's "Decided ..." line and CourtListener's `date_filed`;
  - opinions: type, author and joiners as the corpus has them, beside the
    Reporter's lineup paragraph from the official PDF where the volume prints
    one, and CourtListener's Harvard split (types and authors) where it exists;
  - votes (P1.8): the number of Justices who wrote or joined a dissent, against
    SCDB's `scdb_votes_minority`. Opinions dissenting in part are counted
    separately and flagged, since SCDB counts votes on the outcome.
Nothing from SCDB goes into the corpus; this is checking only.

Usage:
    uv run python scripts/verify_lineup.py
Writes data/verification/lineup.json and prints a table.
"""

import json
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
CASES = ROOT / "data" / "corpus" / "cases"
OUT = ROOT / "data" / "verification" / "lineup.json"


def official_front(key: str) -> str:
    pdfs = json.loads((RAW / "pdfs" / "manifest.json").read_text())
    out = subprocess.run(["pdftotext", "-f", "1", "-l", "6", str(RAW / "pdfs" / pdfs[key]["file"]), "-"],
                         capture_output=True, text=True).stdout
    return re.sub(r"\s+", " ", out.replace("ﬁ", "fi").replace("ﬂ", "fl").replace("­", ""))


def iso(d: str | None) -> str | None:
    try:
        return datetime.strptime(d, "%B %d, %Y").date().isoformat() if d else None
    except ValueError:
        return None


def main() -> int:
    idx = json.loads((RAW / "pull_index.json").read_text())
    rows = []
    for path in sorted(CASES.glob("*.json")):
        case = json.loads(path.read_text())
        key = case["key"]
        cl = json.loads((RAW / "clusters" / f"{idx[key]['cluster']}.json").read_text())
        front = official_front(key)
        decided_off = re.search(r"Decided ([A-Z][a-z]+ \d{1,2}, \d{4})", front)
        m = re.search(r"([A-Z][A-Za-z’' ]+, (?:C\. )?J\., (?:delivered|announced).{0,900}?)(?:[A-Z][a-z]+ [A-Z]?\.? ?[A-Z][a-z]+ argued| argued the cause|$)", front)
        lineup = m.group(1).strip() if m else None
        harvard = []
        for u in cl["sub_opinions"]:
            op = json.loads((RAW / "opinions" / f"{u.rstrip('/').rsplit('/', 1)[-1]}.json").read_text())
            if op.get("xml_harvard") and op["type"] != "010combined":
                harvard.append(f"{op['type'][3:]}:{op.get('author_str') or ''}")
        dissenters, partial = set(), set()
        for o in case["opinions"]:
            people = set(o["author"]) | set(o["joined_by"])
            if o["type"] == "dissent":
                dissenters |= people
            elif "dissent" in o["type"]:
                partial |= people
        row = {
            "key": key,
            "decided_corpus": iso(case["decided_text"]),
            "decided_official": iso(decided_off.group(1)) if decided_off else None,
            "date_filed_courtlistener": cl["date_filed"],
            "opinions": [{"type": o["type"], "author": o["author"], "joined_by": o["joined_by"],
                          "heading": o["heading"], "typed_by_table": o.get("typed_by_table", False)}
                         for o in case["opinions"]],
            "not_participating": case.get("notes", []),
            "official_lineup": lineup,
            "harvard_split": harvard,
            "dissenters": sorted(dissenters), "dissenting_in_part": sorted(partial - dissenters),
            "scdb_votes_majority": cl.get("scdb_votes_majority"),
            "scdb_votes_minority": cl.get("scdb_votes_minority"),
        }
        flags = []
        if row["decided_official"] and row["decided_corpus"] != row["decided_official"]:
            flags.append("date: corpus differs from official")
        if row["decided_corpus"] != row["date_filed_courtlistener"]:
            flags.append("date: CourtListener date_filed differs")
        if row["scdb_votes_minority"] is not None and len(dissenters) != row["scdb_votes_minority"]:
            flags.append(f"votes: {len(dissenters)} dissenting (+{len(row['dissenting_in_part'])} in part) vs SCDB minority {row['scdb_votes_minority']}")
        if harvard and len(harvard) != len(case["opinions"]):
            flags.append(f"opinions: corpus {len(case['opinions'])} vs Harvard split {len(harvard)}")
        if any(o.get("typed_by_table") for o in case["opinions"]):
            flags.append("type set by table")
        row["flags"] = flags
        rows.append(row)
        print(f"{key:16} {row['decided_corpus']} official={row['decided_official']} cl={row['date_filed_courtlistener']} "
              f"dissent={len(dissenters)}(+{len(row['dissenting_in_part'])}) scdb={row['scdb_votes_majority']}-{row['scdb_votes_minority']} "
              f"lineup={'yes' if lineup else 'no'} | {'; '.join(flags)}")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(rows, indent=1, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
