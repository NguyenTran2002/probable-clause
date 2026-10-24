"""Pull the Phase 1 cases from CourtListener into the raw cache (P1.2, P1.9).

1. One citation-lookup request resolves every case's U.S. Reports citation (and,
   for recent cases, its S. Ct. citation) to CourtListener clusters.
2. For each resolved cluster: the cluster, its docket and every opinion, with
   all fields, saved raw under data/raw/. Anything already cached is skipped,
   so nothing is fetched twice.

Requests are serial, at most one every 4 s (15 a minute; basis: the user's EDU
limits of 20 a minute and 1,000 an hour). No automatic retry: on any error the
script stops and reports. The token is read from .env into this process only
and never printed.

Usage:
    uv run python scripts/pull_courtlistener.py
"""

import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from probe_courtlistener import API, token

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
MIN_INTERVAL_S = 4.0  # 15 requests a minute, below the user's 20 a minute
TIMEOUT_S = 60  # placeholder until measured

# (key, name, U.S. citation, S. Ct. citation or None, role)
# Citations are from general knowledge; the lookup confirms each.
CASES = [
    ("olmstead", "Olmstead v. United States", "277 U.S. 438", None, "core"),
    ("goldman", "Goldman v. United States", "316 U.S. 129", None, "core"),
    ("on_lee", "On Lee v. United States", "343 U.S. 747", None, "core"),
    ("silverman", "Silverman v. United States", "365 U.S. 505", None, "core"),
    ("lopez", "Lopez v. United States", "373 U.S. 427", None, "core"),
    ("katz", "Katz v. United States", "389 U.S. 347", None, "core"),
    ("white", "United States v. White", "401 U.S. 745", None, "core"),
    ("miller", "United States v. Miller", "425 U.S. 435", None, "core"),
    ("smith", "Smith v. Maryland", "442 U.S. 735", None, "core"),
    ("knotts", "United States v. Knotts", "460 U.S. 276", None, "core"),
    ("karo", "United States v. Karo", "468 U.S. 705", None, "core"),
    ("ciraolo", "California v. Ciraolo", "476 U.S. 207", None, "core"),
    ("dow", "Dow Chemical Co. v. United States", "476 U.S. 227", None, "core"),
    ("florida_v_riley", "Florida v. Riley", "488 U.S. 445", None, "core"),
    ("kyllo", "Kyllo v. United States", "533 U.S. 27", None, "core"),
    ("jones", "United States v. Jones", "565 U.S. 400", "132 S. Ct. 945", "core"),
    ("jardines", "Florida v. Jardines", "569 U.S. 1", "133 S. Ct. 1409", "core"),
    ("riley", "Riley v. California", "573 U.S. 373", "134 S. Ct. 2473", "core"),
    ("grady", "Grady v. North Carolina", "575 U.S. 306", "135 S. Ct. 1368", "core"),
    ("carpenter", "Carpenter v. United States", "585 U.S. 296", "138 S. Ct. 2206", "core"),
    # Filter-check additions (P1.14).
    ("berger", "Berger v. New York", "388 U.S. 41", None, "core"),
    ("ex_parte_jackson", "Ex parte Jackson", "96 U.S. 727", None, "core"),
    ("boyd", "Boyd v. United States", "116 U.S. 616", None, "core"),
    ("hester", "Hester v. United States", "265 U.S. 57", None, "core"),
    ("lee", "United States v. Lee", "274 U.S. 559", None, "core"),
    ("shultz", "California Bankers Assn. v. Shultz", "416 U.S. 21", None, "core"),
    ("jacobsen", "United States v. Jacobsen", "466 U.S. 109", None, "core"),
    ("oliver", "Oliver v. United States", "466 U.S. 170", None, "core"),
    ("dunn", "United States v. Dunn", "480 U.S. 294", None, "core"),
    ("greenwood", "California v. Greenwood", "486 U.S. 35", None, "core"),
    # Considered at the filter check and left out (P1.14); raw cache only.
    ("quon", "City of Ontario v. Quon", "560 U.S. 746", "130 S. Ct. 2619", "excluded"),
]
# Choice among duplicate clusters, made after reading both (filled in by hand,
# with the reason logged in BUILD_LOG.md).
# The other cluster of Jones and Quon is a scan of the Lawyers' Edition (L. Ed. page
# labels, a Westlaw citation): commercial-reporter text, excluded. Goldman's other
# cluster (2443377) holds only a Lawbox copy of the text; it stays in the raw cache.
CHOSEN: dict[str, int] = {"goldman": 103664, "jones": 622304, "quon": 148797}

# No citation on CourtListener as of Oct 23, 2026 (probe_courtlistener.py).
KNOWN_CLUSTERS = {"chatrie": ("Chatrie v. United States", 10881683, "core")}

_last = 0.0
requests_made = 0


def call(url: str, data: dict | None = None):
    """One paced request. Returns parsed JSON; exits on any HTTP error."""
    global _last, requests_made
    wait = MIN_INTERVAL_S - (time.monotonic() - _last)
    if wait > 0:
        time.sleep(wait)
    body = urllib.parse.urlencode(data).encode() if data else None
    req = urllib.request.Request(url, data=body, headers={"Authorization": f"Token {token()}"})
    _last = time.monotonic()
    requests_made += 1
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_S) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        sys.exit(f"STOP: {e.code} on {url}: {e.read()[:300]!r} ({requests_made} requests made)")


def cached(kind: str, obj_id: int | str, url: str) -> dict:
    path = RAW / kind / f"{obj_id}.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    data = call(url)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=1, ensure_ascii=False), encoding="utf-8")
    return data


def lookup() -> list:
    """One lookup for every case not yet looked up; earlier lookups are cached."""
    path = RAW / "citation_lookup.json"
    extra = RAW / "citation_lookup_2.json"
    if path.exists():
        done = json.loads(path.read_text(encoding="utf-8"))
        have = {r["citation"] for r in done}
        missing = [us for _, _, us, _, _ in CASES if us not in have]
        if missing and not extra.exists():
            data = call(f"{API}/citation-lookup/", {"text": "; ".join(missing)})
            extra.write_text(json.dumps(data, indent=1, ensure_ascii=False), encoding="utf-8")
        return done + (json.loads(extra.read_text(encoding="utf-8")) if extra.exists() else [])
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    cites = [c for _, _, us, sct, _ in CASES for c in (us, sct) if c]
    data = call(f"{API}/citation-lookup/", {"text": "; ".join(cites)})
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=1, ensure_ascii=False), encoding="utf-8")
    return data


def resolve(results: list) -> dict:
    """Map each case key to one cluster id, or to a problem string."""
    by_cite = {r["citation"]: r for r in results}
    out = {}
    for key, name, us, sct, role in CASES:
        found = {}
        for cite in (us, sct):
            r = by_cite.get(cite) if cite else None
            if r is None:
                continue
            found[cite] = (r["status"], [c["id"] for c in r.get("clusters", [])])
        ids = {i for status, cl in found.values() if status == 200 for i in cl}
        dupes = {i for status, cl in found.values() if status == 300 for i in cl}
        if len(ids) == 1:
            out[key] = {"name": name, "role": role, "cluster": ids.pop(), "lookup": found}
        else:
            out[key] = {"name": name, "role": role, "cluster": CHOSEN.get(key),
                        "candidates": sorted(ids | dupes), "lookup": found}
    for key, (name, cid, role) in KNOWN_CLUSTERS.items():
        out[key] = {"name": name, "role": role, "cluster": cid, "lookup": "known cluster id"}
    return out


def main() -> int:
    cases = resolve(lookup())
    unresolved = [k for k, v in cases.items() if v["cluster"] is None]
    for k in unresolved:
        print(f"UNRESOLVED {k}: {cases[k]['lookup']}")

    # Duplicate clusters: fetch every candidate so the choice is made from the data.
    for key, case in cases.items():
        for cid in case.get("candidates", []):
            fetch_case(cid)
            print(f"CANDIDATE {key}: cluster {cid}")

    for key, case in cases.items():
        cid = case["cluster"]
        if cid is None:
            continue
        case.update(fetch_case(cid))
        print(f"{key:16} {cid:>9} {case['date_filed']} {case['source']!s:>6} "
              f"{len(case['opinion_types'])} ops {case['opinion_types']}  {case['case_name']}")

    (RAW / "pull_index.json").write_text(json.dumps(cases, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"\n{requests_made} requests made this run; {len(unresolved)} unresolved")
    return 1 if unresolved else 0


def fetch_case(cid: int) -> dict:
    """Cluster, docket and every opinion for one cluster, through the cache."""
    cluster = cached("clusters", cid, f"{API}/clusters/{cid}/")
    docket_url = cluster["docket"]
    docket_id = docket_url.rstrip("/").rsplit("/", 1)[-1]
    cached("dockets", docket_id, docket_url)
    types = []
    for op_url in cluster.get("sub_opinions") or []:
        op_id = op_url.rstrip("/").rsplit("/", 1)[-1]
        types.append(cached("opinions", op_id, op_url).get("type"))
    return {
        "case_name": cluster.get("case_name"),
        "date_filed": cluster.get("date_filed"),
        "source": cluster.get("source"),
        "citations": [f"{c['volume']} {c['reporter']} {c['page']}" for c in cluster.get("citations", [])],
        "docket": int(docket_id),
        "opinion_types": types,
    }


if __name__ == "__main__":
    sys.exit(main())
