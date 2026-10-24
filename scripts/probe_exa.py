"""Phase 2 paid check: Exa's hosted MCP server, through our own MCP client (brief §6, §9 item 4; P2.5).

At most 20 search requests, counted in data/verification/phase2/exa_requests.jsonl.
Questions it settles:
  - the advanced tool's schema as the server lists it (tools/list, free);
  - the output format, recorded as field names and counts only;
  - what each call costs (`costDollars` in the response), lite against auto;
  - whether a published-date filter returns pages that have no published date;
  - the error shapes: a parameter combination the docs say fails, and a bad key.

Exa's page text is never written to the repo (P1.3, P1.7): the summary under
data/verification/phase2/ holds field names, counts, dates and costs; the raw
responses go to the directory given by --raw (the session scratchpad).

Usage:
    uv run python scripts/probe_exa.py --raw <dir> [--only label,label]
"""

import asyncio
import json
import sys
from pathlib import Path

from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client
from mcp.shared._httpx_utils import create_mcp_http_client

from probe_common import OUT, env_value, save

URL = "https://mcp.exa.ai/mcp?tools=web_search_advanced_exa"
TOOL = "web_search_advanced_exa"
MAX_REQUESTS = 20  # P2.5
COUNT = OUT / "exa_requests.jsonl"

Q = "Fourth Amendment geofence warrant Supreme Court"
SINCE = "2026-06-29"  # Chatrie's decision date, the corpus's latest
CALLS = [
    ("lite", {"query": Q, "type": "lite", "numResults": 10}),
    ("auto", {"query": Q, "type": "auto", "numResults": 10}),
    ("auto_since", {"query": Q, "type": "auto", "numResults": 10, "startPublishedDate": SINCE}),
    ("lite_since", {"query": Q, "type": "lite", "numResults": 10, "startPublishedDate": SINCE}),
    ("auto_domain_since", {"query": "Chatrie v. United States geofence", "type": "auto", "numResults": 10,
                           "includeDomains": ["supremecourt.gov"], "startPublishedDate": "2026-06-01"}),
    # Without a date filter, full text for 10 results overflowed the MCP client's
    # 1 MB event limit on the first run; these cap the text per result.
    ("lite_capped", {"query": Q, "type": "lite", "numResults": 10, "textMaxCharacters": 2000}),
    ("auto_capped", {"query": Q, "type": "auto", "numResults": 10, "textMaxCharacters": 2000}),
    ("auto_company_since", {"query": "geofence warrant", "type": "auto", "numResults": 5,
                            "category": "company", "startPublishedDate": SINCE}),
]


def used() -> int:
    return len(COUNT.read_text().splitlines()) if COUNT.exists() else 0


def summarise(label: str, args: dict, result) -> dict:
    out = {"label": label, "args": args, "isError": getattr(result, "is_error", None)}
    blocks = getattr(result, "content", []) or []
    out["content_types"] = [b.type for b in blocks]
    out["structuredContent"] = getattr(result, "structured_content", None) is not None
    text = "".join(getattr(b, "text", "") for b in blocks)
    try:
        data = json.loads(text)
    except ValueError:
        out["text_head"] = text[:400]  # an error message, not page text
        return out
    res = data.get("results", [])
    out["top_keys"] = sorted(data)
    out["costDollars"] = data.get("costDollars")
    out["searchTime"] = data.get("searchTime")
    out["n_results"] = len(res)
    out["result_keys"] = sorted({k for r in res for k in r})
    dates = [r.get("publishedDate") for r in res]
    out["n_without_publishedDate"] = sum(1 for d in dates if not d)
    out["publishedDates"] = dates
    out["domains"] = [r.get("url", "").split("/")[2] if "//" in r.get("url", "") else "" for r in res]
    out["text_chars"] = [len(r.get("text") or "") for r in res]
    return out


async def run(raw_dir: Path, key: str, calls, list_tools: bool) -> list:
    summaries = []
    async with create_mcp_http_client(headers={"x-api-key": key}) as http:
        async with streamable_http_client(URL, http_client=http) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                if list_tools:
                    tools = await session.list_tools()
                    save("exa_tools_list.json", [t.model_dump() for t in tools.tools])
                    print(f"tools/list: {[t.name for t in tools.tools]}")
                for label, args in calls:
                    if used() >= MAX_REQUESTS:
                        sys.exit(f"Exa request cap {MAX_REQUESTS} reached; {label} not sent")
                    with COUNT.open("a") as f:
                        f.write(json.dumps({"label": label}) + "\n")
                    try:
                        result = await session.call_tool(TOOL, args)
                    except Exception as e:  # a protocol error, not a tool error
                        s = {"label": label, "args": args, "protocol_error": repr(e)[:400]}
                    else:
                        (raw_dir / f"exa_{label}.json").write_text(result.model_dump_json(indent=2))
                        s = summarise(label, args, result)
                    print(f"  {label}: {json.dumps({k: s.get(k) for k in ('isError', 'n_results', 'n_without_publishedDate', 'costDollars', 'protocol_error', 'text_head')})}")
                    summaries.append(s)
    return summaries


def main() -> int:
    if "--raw" not in sys.argv:
        sys.exit(__doc__)
    raw_dir = Path(sys.argv[sys.argv.index("--raw") + 1])
    raw_dir.mkdir(parents=True, exist_ok=True)
    OUT.mkdir(parents=True, exist_ok=True)
    only = sys.argv[sys.argv.index("--only") + 1].split(",") if "--only" in sys.argv else None
    calls = [c for c in CALLS if only is None or c[0] in only]
    summaries = asyncio.run(run(raw_dir, env_value("EXA_API_KEY"), calls, list_tools=only is None))
    if only is None or "bad_key" in only:
        # A key Exa does not know: the error's shape (no credit used).
        try:
            summaries += asyncio.run(run(raw_dir, "not-a-real-key", [("bad_key", {"query": Q, "type": "lite", "numResults": 1})], False))
        except BaseException as e:  # connection-level refusal
            summaries.append({"label": "bad_key", "connection_error": repr(e)[:400]})
            print(f"  bad_key: connection error {repr(e)[:200]}")
    # Merge with earlier runs, newest result per label.
    path = OUT / "exa_probe_summary.json"
    merged = {s["label"]: s for s in (json.loads(path.read_text()) if path.exists() else [])}
    merged |= {s["label"]: s for s in summaries}
    save("exa_probe_summary.json", list(merged.values()))
    print(f"Exa requests used: {used()} of {MAX_REQUESTS}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
