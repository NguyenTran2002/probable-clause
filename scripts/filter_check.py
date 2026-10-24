"""Filter check (brief §4.7, P1.9), in both directions.

Forward: Supreme Court opinions that cite the core cases, from CourtListener's
citation graph (search `cites:` over every core opinion ID, paged through), with
the number of distinct core cases each one cites.
Backward: the U.S. Reports citations in the core opinions' own text, with the
number of distinct core cases citing each, resolved to case names through
CourtListener's citation-lookup API.

Candidates are listed for the user, who decides each addition; nothing is added
here. Raw responses are cached under data/raw/filter_check/. Requests are
serial, one every 4 s (the user's limit is 20 a minute), no automatic retry.

Usage:
    uv run python scripts/filter_check.py
Writes data/verification/filter_check.json and prints both lists.
"""

import json
import re
import sys
import urllib.parse
from collections import defaultdict
from pathlib import Path

from probe_courtlistener import API
from pull_courtlistener import call

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
CACHE = RAW / "filter_check"
OUT = ROOT / "data" / "verification" / "filter_check.json"
US = re.compile(r"\b(\d{1,3}) U\. ?S\. (\d{1,4})\b")


def cached_call(name: str, url: str, data: dict | None = None):
    path = CACHE / f"{name}.json"
    if path.exists():
        return json.loads(path.read_text())
    out = call(url, data)
    CACHE.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(out, indent=1, ensure_ascii=False))
    return out


def main() -> int:
    idx = json.loads((RAW / "pull_index.json").read_text())
    manifest = json.loads((ROOT / "data" / "corpus" / "manifest.json").read_text())
    core = {c["key"] for c in manifest["cases"] if c["role"] == "core"}
    pulled = {c["key"] for c in manifest["cases"]}

    # Every opinion ID of every pulled cluster (duplicates included) -> case key.
    op_case, own_clusters = {}, set()
    for key, c in idx.items():
        for cid in [c["cluster"]] + c.get("candidates", []):
            if cid is None:
                continue
            own_clusters.add(cid)
            cl = json.loads((RAW / "clusters" / f"{cid}.json").read_text())
            for u in cl["sub_opinions"]:
                op_case[int(u.rstrip("/").rsplit("/", 1)[-1])] = key
    core_ids = sorted(i for i, k in op_case.items() if k in core)

    # Forward.
    q = "cites:(" + " OR ".join(str(i) for i in core_ids) + ")"
    url = f"{API}/search/?" + urllib.parse.urlencode({"q": q, "type": "o", "court": "scotus", "order_by": "dateFiled desc"})
    forward, page = {}, 0
    while url:
        d = cached_call(f"forward_{page:03d}", url)
        for r in d["results"]:
            if r["cluster_id"] in own_clusters:
                continue
            cited = {op_case[i] for o in r.get("opinions", []) for i in o.get("cites", []) if op_case.get(i) in core}
            entry = forward.setdefault(r["cluster_id"], {"name": r["caseName"], "date": r["dateFiled"],
                                                         "citation": r.get("citation"), "cites_core": set()})
            entry["cites_core"] |= cited
        url, page = d.get("next"), page + 1
    fwd = sorted(({**v, "cluster": k, "cites_core": sorted(v["cites_core"])} for k, v in forward.items()),
                 key=lambda e: (-len(e["cites_core"]), e["date"]))

    # Backward.
    cited_by = defaultdict(set)
    for c in manifest["cases"]:
        if c["role"] != "core":
            continue
        case = json.loads((ROOT / "data" / "corpus" / "cases" / f"{c['key']}.json").read_text())
        text = " ".join([p["text"] for o in case["opinions"] for p in o["paragraphs"]] +
                        [x for o in case["opinions"] for f in o["footnotes"] for x in f["paragraphs"]])
        own = c["citation"].split(" (")[0]
        for vol, pg in US.findall(text):
            cite = f"{vol} U.S. {pg}"
            if cite != own:
                cited_by[cite].add(c["key"])
    own_cites = {m["citation"].split(" (")[0] for m in manifest["cases"]}
    top = sorted(((k, v) for k, v in cited_by.items() if len(v) >= 3 and k not in own_cites),
                 key=lambda kv: -len(kv[1]))
    lookup = cached_call("backward_lookup", f"{API}/citation-lookup/", {"text": "; ".join(k for k, _ in top)})
    names = {r["citation"]: (r["clusters"][0]["case_name"], r["clusters"][0]["date_filed"], r["clusters"][0]["id"])
             for r in lookup if r.get("status") == 200 and r.get("clusters")}
    bwd = [{"citation": k, "cited_by_core": sorted(v), "name": names.get(k, (None,))[0],
            "date": names.get(k, (None, None))[1], "cluster": names.get(k, (None, None, None))[2]} for k, v in top]

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"forward": fwd, "backward": bwd}, indent=1, ensure_ascii=False))
    print(f"FORWARD: {len(fwd)} Supreme Court cases cite at least one core case; citing 3 or more:")
    for e in fwd:
        if len(e["cites_core"]) >= 3:
            print(f"  {len(e['cites_core']):>2}  {e['date']}  {e['name'][:60]:60} {e['cites_core']}")
    print(f"BACKWARD: U.S. Reports cases cited by 3 or more core cases ({len(bwd)}):")
    for e in bwd:
        print(f"  {len(e['cited_by_core']):>2}  {e['citation']:14} {e['date'] or '':10}  {(e['name'] or '?')[:55]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
