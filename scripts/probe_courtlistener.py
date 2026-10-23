"""One authenticated CourtListener request, to confirm the token works.

Fetches a single cluster (default: Chatrie v. United States, cluster 10881683,
as linked by a third-party site in brief §4.1) with field selection, and prints
the status, a few public fields, and any rate-limit headers. The token is
loaded from .env into this process only and is never printed.

Usage:
    uv run python scripts/probe_courtlistener.py [cluster_id]
"""

import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

ENV_PATH = Path(__file__).resolve().parent.parent / ".env"
API = "https://www.courtlistener.com/api/rest/v4"
FIELDS = "id,case_name,date_filed,citations,docket,sub_opinions"
# Placeholder until measured: one request, no retry.
TIMEOUT_S = 30


def token() -> str:
    for raw in ENV_PATH.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if line.startswith("export "):
            line = line[len("export "):]
        if line.startswith("COURTLISTENER_API_TOKEN="):
            return line.split("=", 1)[1].strip().strip("'\"")
    sys.exit("COURTLISTENER_API_TOKEN not found in .env")


def main() -> int:
    cluster = sys.argv[1] if len(sys.argv) > 1 else "10881683"
    url = f"{API}/clusters/{cluster}/?fields={FIELDS}"
    req = urllib.request.Request(url, headers={"Authorization": f"Token {token()}"})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_S) as resp:
            status, headers, body = resp.status, resp.headers, resp.read()
    except urllib.error.HTTPError as e:
        status, headers, body = e.code, e.headers, e.read()

    print(f"GET /clusters/{cluster}/ -> {status}")
    for name, value in headers.items():
        if "ratelimit" in name.lower() or name.lower() == "retry-after":
            print(f"  header {name}: {value}")
    try:
        data = json.loads(body)
    except ValueError:
        print(f"  non-JSON body ({len(body)} bytes)")
        return 1
    if status != 200:
        print(f"  body: {json.dumps(data)[:300]}")
        return 1
    print(f"  case_name: {data.get('case_name')}")
    print(f"  date_filed: {data.get('date_filed')}")
    print(f"  citations: {data.get('citations')}")
    print(f"  docket: {data.get('docket')}")
    print(f"  sub_opinions: {len(data.get('sub_opinions') or [])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
