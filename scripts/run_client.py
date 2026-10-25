"""Phase 4's paid build tests: one question to the local API, its stream read to the end, a heartbeat every
HEARTBEAT_INTERVAL_S, and every event saved (docs/design/paid-build-tests.md).

The client makes no paid call itself; the server does. It reads no secret.

    uv run python scripts/run_client.py --label t1 "Can police use a thermal imager on my house from the street?"

Events go to `data/verification/wave3/<label>-<run_id>.jsonl` (local only; Phase 4's runs stay under `phase4/`), one envelope per line, and a summary
to `<label>-<run_id>.summary.json`. Exit 0 when `run_ended` arrived, 2 when the run was refused, 1 otherwise.
"""

import argparse
import asyncio
import json
import sys
from pathlib import Path

import httpx2

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from api import settings  # noqa: E402

OUT = ROOT / "data" / "verification" / "wave3"
RECONNECTS = 3           # placeholder: the stream is re-opened with Last-Event-ID if it drops before run_ended
RUN_TIMEOUT_S = 1_200    # placeholder: a run's own deadline is shorter; this only stops a hung client


def parse_frames(buffer: str) -> tuple[list[dict], str]:
    """Complete SSE frames in `buffer` as envelopes, and the unfinished rest. Comment lines are keep-alives."""
    events: list[dict] = []
    while "\n\n" in buffer:
        raw, buffer = buffer.split("\n\n", 1)
        data = [line[5:].lstrip() for line in raw.split("\n") if line.startswith("data:")]
        if data:
            events.append(json.loads("\n".join(data)))
    return events, buffer


def summarise(run_id: str, events: list[dict]) -> dict:
    paid = [e["data"] for e in events if e["kind"] == "paid_call"]
    blocks = [e["data"] for e in events if e["kind"] == "answer_block"]
    end = next((e["data"] for e in events if e["kind"] == "run_ended"), None)
    band = next((e["data"] for e in events if e["kind"] == "update_band"), None)
    update = next((e["data"] for e in events if e["kind"] == "update_ended"), None)
    kinds: dict[str, int] = {}
    for e in events:
        kinds[e["kind"]] = kinds.get(e["kind"], 0) + 1
    return {
        "run_id": run_id,
        "events": len(events),
        "kinds": kinds,
        "state": end and end.get("state"),
        "answer_end": end and end.get("answer_end"),
        "stop_kind": end and end.get("stop_kind"),
        "rounds": end and end.get("rounds"),
        "totals": end and end.get("totals"),
        "update_band": band and band.get("outcome"),
        "update_step": update,
        "answer_blocks": len(blocks),
        "citations": sum(len(b.get("citations") or []) for b in blocks),
        "paid_calls": [{k: p.get(k) for k in ("step", "service", "purpose", "cost_usd", "estimated", "usage")} for p in paid],
    }


async def heartbeat(client: httpx2.AsyncClient, run_id: str, last: list[int], done: asyncio.Event) -> None:
    interval = float(settings.HEARTBEAT_INTERVAL_S.value)
    while not done.is_set():
        try:
            r = await client.post(f"/runs/{run_id}/alive", json={"last_event": last[0]})
            if r.status_code != 204:
                print(f"  heartbeat: {r.status_code} {r.text[:200]}", file=sys.stderr)
        except httpx2.HTTPError as e:
            print(f"  heartbeat failed: {type(e).__name__}", file=sys.stderr)
        try:
            await asyncio.wait_for(done.wait(), interval)
        except TimeoutError:
            pass


async def read_stream(client: httpx2.AsyncClient, run_id: str, events: list[dict], last: list[int],
                      sink, quiet: bool) -> bool:
    """Read until run_ended; True if it arrived."""
    for attempt in range(RECONNECTS + 1):
        headers = {"Last-Event-ID": str(last[0])} if last[0] else {}
        try:
            async with client.stream("GET", f"/runs/{run_id}/events", headers=headers, timeout=None) as resp:
                if resp.status_code != 200:
                    print(f"  events: {resp.status_code} {(await resp.aread())[:200]!r}", file=sys.stderr)
                    return False
                buffer = ""
                async for chunk in resp.aiter_text():
                    got, buffer = parse_frames(buffer + chunk.replace("\r\n", "\n"))
                    for env in got:
                        if env["n"] <= last[0]:
                            continue
                        events.append(env)
                        last[0] = env["n"]
                        sink.write(json.dumps(env, ensure_ascii=False) + "\n")
                        sink.flush()
                        if not quiet:
                            step = env["data"].get("step") if isinstance(env.get("data"), dict) else None
                            print(f"  {env['n']:>4} {env['t_ms']:>7} ms  {env['kind']}" + (f"  [{step}]" if step else ""))
                        if env["kind"] == "run_ended":
                            return True
        except httpx2.HTTPError as e:
            print(f"  stream dropped ({type(e).__name__}), attempt {attempt + 1}", file=sys.stderr)
        print(f"  stream closed before run_ended, reconnecting after event {last[0]}", file=sys.stderr)
    return False


async def run(base: str, question: str, label: str, out: Path, quiet: bool) -> int:
    out.mkdir(parents=True, exist_ok=True)
    async with httpx2.AsyncClient(base_url=base, timeout=30) as client:
        r = await client.post("/runs", json={"question": question})
        if r.status_code != 201:
            print(f"refused: {r.status_code} {r.text}")
            return 2
        run_id = r.json()["run_id"]
        path = out / f"{label}-{run_id}.jsonl"
        print(f"run {run_id} -> {path.relative_to(ROOT) if path.is_relative_to(ROOT) else path}")
        events: list[dict] = []
        last = [0]
        done = asyncio.Event()
        with path.open("w", encoding="utf-8") as sink:
            beat = asyncio.create_task(heartbeat(client, run_id, last, done))
            try:
                ended = await asyncio.wait_for(read_stream(client, run_id, events, last, sink, quiet), RUN_TIMEOUT_S)
            except TimeoutError:
                print("client timeout: the run did not end", file=sys.stderr)
                ended = False
            finally:
                done.set()
                await beat
        summary = summarise(run_id, events)
        path.with_suffix(".summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
        print(json.dumps({k: summary[k] for k in ("state", "answer_end", "stop_kind", "rounds", "update_band", "update_step",
                                                 "answer_blocks", "citations", "totals")}, indent=2))
        return 0 if ended else 1


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("question")
    ap.add_argument("--label", required=True)
    ap.add_argument("--base", default="http://127.0.0.1:8000")
    ap.add_argument("--out", type=Path, default=OUT)
    ap.add_argument("--quiet", action="store_true")
    a = ap.parse_args()
    return asyncio.run(run(a.base, a.question, a.label, a.out, a.quiet))


if __name__ == "__main__":
    sys.exit(main())
