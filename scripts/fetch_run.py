"""Saves an ended run's stored events from the API before Atlas's 24-hour TTL removes them (T3.7, keep every run).

It reads `GET /runs/{id}/events` from the start, which replays the stored events and closes after `run_ended`; it
starts nothing and makes no paid call. It reads no secret.

    uv run python scripts/fetch_run.py --label live-first --base https://nguyennhattran.com/probable-clause/api <run_id>

Events go to `data/verification/live/<label>-<run_id>.jsonl` (local only), one envelope per line, and a summary to
`<label>-<run_id>.summary.json`; an existing file is never overwritten. Exit 0 when `run_ended` arrived, 1 otherwise.
"""

import argparse
import json
import sys
from pathlib import Path

import httpx2

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.run_client import parse_frames, summarise  # noqa: E402

OUT = ROOT / "data" / "verification" / "live"
READ_TIMEOUT_S = 60      # placeholder: well above the API's 15 s keep-alive; an ended run's events arrive at once


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("run_id")
    ap.add_argument("--label", required=True)
    ap.add_argument("--base", required=True)
    ap.add_argument("--out", type=Path, default=OUT)
    a = ap.parse_args()

    events_path = a.out / f"{a.label}-{a.run_id}.jsonl"
    summary_path = a.out / f"{a.label}-{a.run_id}.summary.json"
    if events_path.exists() or summary_path.exists():
        print(f"{events_path.name}: already saved; not overwritten")
        return 1

    events: list[dict] = []
    buffer = ""
    timeout = httpx2.Timeout(30, read=READ_TIMEOUT_S)
    with httpx2.Client(timeout=timeout) as client:
        with client.stream("GET", f"{a.base.rstrip('/')}/runs/{a.run_id}/events",
                           headers={"Accept": "text/event-stream"}) as r:
            if r.status_code != 200:
                print(f"events: HTTP {r.status_code}: {r.read().decode(errors='replace')[:200]}")
                return 1
            for chunk in r.iter_text():
                batch, buffer = parse_frames(buffer + chunk)
                events.extend(batch)
                if events and events[-1].get("kind") == "run_ended":
                    break

    a.out.mkdir(parents=True, exist_ok=True)
    events_path.write_text("".join(json.dumps(e, ensure_ascii=False) + "\n" for e in events), encoding="utf-8")
    summary = summarise(a.run_id, events)
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    ended = bool(events) and events[-1].get("kind") == "run_ended"
    print(f"{events_path.name}: {len(events)} events, run_ended {'yes' if ended else 'NO'}")
    return 0 if ended else 1


if __name__ == "__main__":
    sys.exit(main())
