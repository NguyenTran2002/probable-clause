"""Export real runs' saved events as replay files (contract §11.2, T5.6): `replays/<slug>.json` and `replays/index.json`.

A replay is a run's events as they were streamed, never edited (T5.6). Each run is checked before it is written:
its envelopes number 1 to N with no gap, every one passes `contracts/events.schema.json`, the stream ends with
`run_ended`, and no web result carries page text (§1). The index lists the chips in the order given.

    uv run python scripts/export_replay.py --commit 84c0db4 \\
        phone-search-arrest=data/verification/replays/phone-search-arrest-<run_id>.jsonl@c74b3e0 ...

`--commit` is the code the runs were recorded on (the API's `/health` commit); a run recorded on other code names
its own after `@`. Reads no secret, calls nothing.
Exit 0 when every file was written, 1 when a run failed a check (nothing is written then).
"""

import argparse
import json
import re
import sys
from pathlib import Path

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from api.state.prices import price_sources  # noqa: E402

SCHEMA = json.loads((ROOT / "contracts" / "events.schema.json").read_text(encoding="utf-8"))
OUT = ROOT / "replays"
SLUG = re.compile(r"[a-z0-9-]+")


def load(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def problems(events: list[dict]) -> list[str]:
    out: list[str] = []
    if not events:
        return ["no events"]
    validator = Draft202012Validator(SCHEMA)
    for i, env in enumerate(events, 1):
        if env.get("n") != i:
            out.append(f"envelope {i} is numbered {env.get('n')}")
            break
        out.extend(f"{env.get('kind')} n={env.get('n')}: {e.message}" for e in validator.iter_errors(env))
        if env.get("kind") == "tool_result":
            for item in (env["data"].get("web") or []):
                if isinstance(item, dict) and "text" in item:
                    out.append(f"tool_result n={env['n']}: a web result carries page text")
    if events[0].get("kind") != "run_started":
        out.append("the first event is not run_started")
    if events[-1].get("kind") != "run_ended":
        out.append("the last event is not run_ended")
    if len({e.get("run") for e in events}) != 1:
        out.append("events from more than one run")
    return out


def document(slug: str, events: list[dict], commit: str) -> dict:
    started = events[0]["data"]
    return {"format": 1, "slug": slug, "question": started["question"], "recorded_at": events[0]["at"],
            "commit": commit, "models": started["models"], "prices": price_sources(),
            "corpus_label": started["corpus_label"], "events": events}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("runs", nargs="+", metavar="slug=events.jsonl[@commit]")
    ap.add_argument("--commit", help="the commit of every run that names none")
    ap.add_argument("--out", type=Path, default=OUT)
    a = ap.parse_args()

    docs: list[dict] = []
    failed = False
    for arg in a.runs:
        slug, _, rest = arg.partition("=")
        path, _, commit = rest.partition("@")
        commit = commit or a.commit
        if not SLUG.fullmatch(slug) or not path or not commit:
            print(f"{arg}: expected slug=path[@commit], the slug in lower case, digits and hyphens, and a commit")
            return 1
        events = load(Path(path))
        found = problems(events)
        for p in found:
            print(f"{slug}: {p}")
        failed |= bool(found)
        if not found:
            docs.append(document(slug, events, commit))
    if failed:
        print("nothing written")
        return 1

    a.out.mkdir(parents=True, exist_ok=True)
    for d in docs:
        (a.out / f"{d['slug']}.json").write_text(json.dumps(d, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"{d['slug']}: {len(d['events'])} events, {d['corpus_label']}, recorded {d['recorded_at']}")
    index = [{k: d[k] for k in ("slug", "question", "recorded_at", "corpus_label")} for d in docs]
    (a.out / "index.json").write_text(json.dumps(index, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"index.json: {len(index)} replays")
    return 0


if __name__ == "__main__":
    sys.exit(main())
