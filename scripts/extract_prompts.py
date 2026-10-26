"""Every prompt typed in this project's two Claude Code conversations, in order, as `docs/PROMPTS.md` (brief §10.5).

Reads the transcripts Claude Code keeps under `~/.claude/projects/` for this folder (read only; the transcripts
themselves are never committed). Two conversations worked here: the main one, which ran every phase across
several transcript files (each compaction or resume starts a new file), and the frontend one, which built the
look tests on Oct 23, 2026 (P0.3, P1.6).

A typed prompt is a top-level user record that is not a tool result, a slash command or its output, a shell
command, a notification, a compaction summary or a subagent's message, plus any prompt typed while Claude was
busy (queued). Records are deduplicated across files by ID and by time and text, since a continued transcript
repeats the records it carries over.

Sittings: a prompt more than two hours after the one before starts a new sitting; a sitting runs from its first
prompt to the last recorded activity (a prompt or a reply) before the next. Breaks under two hours are counted.

Redactions, each marked where it happens: local paths become `~` or "[temporary path]", images become
"[image not published]" (P0.4), the e-mail address and the name of another project of the author's are
replaced. A secret-like string stops the export. The flag list (prompts with a redaction) goes to `--flags`,
outside the repo, for review.

    uv run python scripts/extract_prompts.py --flags <path outside the repo>

Times are America/Chicago (§10.7). Reads no secret, calls nothing. Exit 0 when written, 1 when stopped.
"""

import argparse
import json
import re
import statistics
import sys
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
TRANSCRIPTS = Path.home() / ".claude" / "projects" / re.sub(r"[^A-Za-z0-9]", "-", str(ROOT))
OUT = ROOT / "docs" / "PROMPTS.md"
CT = ZoneInfo("America/Chicago")
SITTING_GAP = timedelta(hours=2)

FRONTEND = {"4d7c2cf3-4dc2-4029-b1b6-dd937b4e17a5", "a19b23a6-08d8-4423-aaad-3ff9e2acef8a"}  # the look tests, Oct 23

NOT_TYPED = ("<local-command", "<command-name", "<command-message", "<task-notification", "[Request interrupted",
             "<side-sessions-event", "<ci-monitor-event", "<bash-", "This session is being continued",
             "<system-reminder", "<user-prompt-submit-hook")
SECRET = re.compile(r"sk-ant-[A-Za-z0-9_-]{8,}|mongodb(\+srv)?://[^\s/]*:[^\s/@]*@|\bpa-[A-Za-z0-9_-]{20,}|"
                    r"\bgh[pousr]_[A-Za-z0-9]{20,}")
REDACT = [
    (re.compile(r"/Users/[^/\s]+/"), "~/", "local path"),
    (re.compile(r"(/private)?/tmp/[^\s\"'`)]+"), "[temporary path]", "temporary path"),
    (re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[a-z]{2,}"), "[e-mail]", "e-mail"),
    (re.compile(r"haiku[ -]decision[ -]api|haiku[ -]decision|the haiku project", re.I), "[another project]",
     "another project"),
]
PASTED = re.compile(r"</?pasted_content[^>]*>")
RESENT = timedelta(minutes=10)                  # the same text again this soon is one prompt sent twice


def ts(o):
    return datetime.fromisoformat(o["timestamp"].replace("Z", "+00:00"))


def text_of(content):
    """The typed text and its image count, or None for a tool result."""
    if isinstance(content, str):
        return content, 0
    blocks = [b for b in content or [] if isinstance(b, dict)]
    if any(b.get("type") == "tool_result" for b in blocks):
        return None
    text = "\n\n".join(b.get("text", "") for b in blocks if b.get("type") == "text")
    return text, sum(1 for b in blocks if b.get("type") == "image")


def read_all():
    prompts, activity, compactions, seen = [], set(), {}, set()
    for path in sorted(TRANSCRIPTS.glob("*.jsonl")):
        conversation = "frontend" if path.stem in FRONTEND else "main"
        for line in path.open(encoding="utf-8"):
            try:
                o = json.loads(line)
            except json.JSONDecodeError:
                continue
            if o.get("isSidechain") or "timestamp" not in o:
                continue
            kind = o.get("type")
            if kind in ("user", "assistant"):
                activity.add(ts(o))
            if kind == "system" and o.get("subtype") == "compact_boundary":
                compactions[o.get("uuid") or o["timestamp"]] = ts(o)
            found = None
            if kind == "user" and not (o.get("isMeta") or o.get("isCompactSummary")):
                found = text_of((o.get("message") or {}).get("content"))
            elif kind == "attachment" and (o.get("attachment") or {}).get("type") == "queued_command":
                at = o["attachment"]
                if at.get("commandMode") == "prompt" and not at.get("isMeta"):
                    found = text_of(at.get("prompt"))
            if not found:
                continue
            text, images = found
            if not (text.strip() or images) or text.lstrip().startswith(NOT_TYPED):
                continue
            keys = {o.get("uuid"), (o["timestamp"], text)} - {None}
            if keys & seen:
                continue
            seen |= keys
            prompts.append({"at": ts(o), "text": text.strip(), "images": images, "conversation": conversation})
    prompts.sort(key=lambda p: p["at"])
    kept = [p for i, p in enumerate(prompts)
            if not (i and p["text"] == prompts[i - 1]["text"] and p["at"] - prompts[i - 1]["at"] < RESENT)]
    return kept, sorted(activity), sorted(set(compactions.values()))


def subagents():
    """Each subagent's model and effort, from the metadata Claude Code keeps beside its transcript."""
    runs = {}
    for meta in TRANSCRIPTS.glob("*/subagents/*.meta.json"):
        m = json.loads(meta.read_text(encoding="utf-8"))
        key = f"{m.get('model') or 'the parent model'}, {m.get('effort') or 'default'} effort"
        runs[key] = runs.get(key, 0) + 1
    return dict(sorted(runs.items(), key=lambda kv: -kv[1]))


def clean(p):
    if SECRET.search(p["text"]):
        raise SystemExit(f"stopped: a secret-like string in the prompt at {local(p['at'])}; nothing written")
    text, hits = PASTED.sub(lambda m: "[pasted text ends]" if m.group(0)[1] == "/" else "[pasted text begins]",
                            p["text"]), []
    for pattern, replacement, label in REDACT:
        text, n = pattern.subn(replacement, text)
        if n:
            hits.append(label)
    if p["images"]:
        text += ("\n\n" if text else "") + "[image not published]" + (f" ×{p['images']}" if p["images"] > 1 else "")
        hits.append("image")
    return text, hits


def sittings(prompts, activity):
    groups = [[prompts[0]]]
    for a, b in zip(prompts, prompts[1:]):
        (groups.append([b]) if b["at"] - a["at"] > SITTING_GAP else groups[-1].append(b))
    out = []
    for i, g in enumerate(groups):
        start = g[0]["at"]
        nxt = groups[i + 1][0]["at"] if i + 1 < len(groups) else None
        end = max(t for t in activity if t >= start and (nxt is None or t < nxt))
        out.append({"start": start, "end": end, "prompts": g})
    return out


def local(t, fmt="%Y-%m-%d %H:%M"):
    return t.astimezone(CT).strftime(fmt)


def hours(a, b):
    return (b - a).total_seconds() / 3600


def words(text):
    return len(text.split())


def render(prompts, groups, compactions, agents):
    texts = [clean(p) for p in prompts]
    by_id = {id(p): t for p, t in zip(prompts, texts)}
    counts = [words(t) for t, _ in texts]
    total_h = sum(hours(g["start"], g["end"]) for g in groups)
    per_conv = {c: sum(1 for p in prompts if p["conversation"] == c) for c in ("main", "frontend")}
    lines = [
        "# Every prompt",
        "",
        "Every prompt typed in the two Claude Code conversations that built Probable Clause, in order, generated from "
        "the transcripts by [`scripts/extract_prompts.py`](../scripts/extract_prompts.py). The **main** conversation "
        "ran every phase; the **frontend** conversation built the look tests on Oct 23, 2026. Subagents' messages, "
        "slash commands, tool output and Claude's replies are left out.",
        "",
        "Times are Chicago time (CDT). A prompt more than two hours after the one before starts a new sitting; a "
        "sitting runs from its first prompt to the last activity before the next, so breaks under two hours are "
        "counted and this is not time at the desk. Local paths, images, an e-mail address and the name of another "
        "of the author's projects are redacted where they occur, marked in square brackets, as is text the author "
        "pasted in. A prompt sent twice with the same text within ten minutes is listed once.",
        "",
        "## Figures",
        "",
        "| | |",
        "|---|---|",
        f"| Prompts | {len(prompts)} ({per_conv['main']} main, {per_conv['frontend']} frontend) |",
        f"| Words | {sum(counts):,}, median {statistics.median(counts):.0f} a prompt |",
        f"| Span | {local(groups[0]['start'])} to {local(groups[-1]['end'])} CDT |",
        f"| Time in sittings | {total_h:.1f} hours, in {len(groups)} sittings |",
        f"| Context compactions | {len(compactions)} |",
        f"| Subagents started | {sum(agents.values())} ({'; '.join(f'{n} {k}' for k, n in agents.items())}) |",
        "",
        "### Sittings",
        "",
        "| Sitting | From | To | Hours | Prompts | Words |",
        "|---|---|---|---|---|---|",
    ]
    for i, g in enumerate(groups, 1):
        w = sum(words(by_id[id(p)][0]) for p in g["prompts"])
        lines.append(f"| {i} | {local(g['start'])} | {local(g['end'])} | {hours(g['start'], g['end']):.1f} "
                     f"| {len(g['prompts'])} | {w:,} |")
    pending = list(compactions)
    for i, g in enumerate(groups, 1):
        lines += ["", f"## Sitting {i}: {local(g['start'])} to {local(g['end'], '%H:%M')} CDT", ""]
        for p in g["prompts"]:
            while pending and pending[0] < p["at"]:
                if pending[0] >= g["start"]:
                    lines += [f"*Context compacted at {local(pending[0], '%H:%M')}.*", ""]
                pending.pop(0)
            text, _ = by_id[id(p)]
            lines.append(f"**{local(p['at'], '%b %d, %H:%M')}** · {p['conversation']}")
            lines.append("")
            lines += [("> " + l) if l.strip() else ">" for l in text.splitlines()]
            lines.append("")
    stats = {"prompts": len(prompts), "main": per_conv["main"], "frontend": per_conv["frontend"],
             "words": sum(counts), "median_words": statistics.median(counts), "sittings": len(groups),
             "hours": round(total_h, 1), "start": local(groups[0]["start"]), "end": local(groups[-1]["end"]),
             "compactions": len(compactions), "subagents": agents}
    flags = [f"{local(p['at'])} [{', '.join(h)}] {t[:160]!r}" for p, (t, h) in zip(prompts, texts) if h]
    return "\n".join(lines).rstrip() + "\n", stats, flags


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--out", type=Path, default=OUT)
    ap.add_argument("--flags", type=Path, required=True, help="where to write the flag list (outside the repo)")
    a = ap.parse_args()
    if a.flags.resolve().is_relative_to(ROOT):
        print("--flags must be outside the repo")
        return 1
    prompts, activity, compactions = read_all()
    groups = sittings(prompts, activity)
    text, stats, flags = render(prompts, groups, compactions, subagents())
    a.out.write_text(text, encoding="utf-8")
    a.flags.write_text("\n".join(flags) + "\n", encoding="utf-8")
    print(json.dumps(stats))
    print(f"{len(flags)} prompts with a redaction listed in the flag file")
    return 0


if __name__ == "__main__":
    sys.exit(main())
