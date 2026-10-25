"""A saved run's events (scripts/run_client.py) as one Markdown file a person can read: the question, the answer with
numbered citations, the checks' flags, the scope note, the update band, every submit Claude sent, the trail of each
step (research, then the update step, contract v2.0) and the cost. Read-only; makes no call. Reads v1 recordings too,
whose events have no `step` (all research then).

    uv run python scripts/render_run.py data/verification/wave3/w3-t1-*.jsonl

Each file is written next to its events under `answers/` (local only, like the events), never over an older one.
"""

import json
import sys
from pathlib import Path

SUBMITS = ("submit_answer", "submit_update")


def render(events: list[dict]) -> str:
    by_kind = lambda k: [e["data"] for e in events if e["kind"] == k]          # noqa: E731
    first = lambda k: next(iter(by_kind(k)), None)                               # noqa: E731
    start, end, checks, band = first("run_started"), first("run_ended"), first("checks"), first("update_band")
    passages = {p["id"]: p for p in by_kind("passage")}
    out = [f"# {start['question']}", "",
           f"Run `{events[0]['run']}`, started {events[0]['at']}. Ended **{end['state']}** "
           f"(answer {end['answer_end']}, {end['rounds']} rounds, {events[-1]['t_ms'] / 1000:.1f} s).", ""]

    if end.get("note"):
        out += ["## Note to the visitor", "", end["note"], ""]
    if end.get("scope_note"):
        out += ["## Scope note", "", end["scope_note"], ""]

    blocks = by_kind("answer_block")
    sources: list[dict] = []
    if blocks:
        text = []
        for b in blocks:
            text.append(b["text"])
            for c in b["citations"]:
                sources.append(c)
                text.append(f"<sup>[{len(sources)}]</sup>")
        out += ["## Answer", "", "".join(text), ""]
        out += ["## Citations", ""]
        for i, c in enumerate(sources, 1):
            p = passages.get(c["passage_id"], {})
            where = f"{p.get('case_name', '?')}, {p.get('opinion_type', '?')}"
            if p.get("authors"):
                where += f" ({', '.join(p['authors'])})"
            out.append(f"{i}. `{c['passage_id']}`, sentences {c['first_sentence']} to {c['last_sentence']}, "
                       f"{where}: \"{c['cited_text'].strip()}\"")
        out.append("")

    if checks:
        out += ["## Checks", "",
                f"- Quotations: {checks['quotations_found']} of {checks['quotations_checked']} found in the kept passages",
                f"- Full case names and citations: {checks['citations_found']} of {checks['citations_checked']} found "
                f"in the corpus" + (f"; not in this corpus: {', '.join(checks['not_in_corpus'])}"
                                   if checks["not_in_corpus"] else "")]
        out += [f"- **Flag ({f['kind']}):** \"{f['text']}\" (block {f['block']})" for f in checks["flags"]]
        out.append("")

    if band:
        out += ["## Update band", "", f"Outcome: **{band['outcome']}**", ""]
        if band.get("reason"):
            out += [f"Reason given: {band['reason']}", ""]
        if band.get("overview"):
            out += [f"Overview: {band['overview']}", ""]
        for f in band.get("findings") or []:
            out.append(f"- {f['statement']} (sources: {', '.join(f['sources'])})")
        for s in band.get("searches") or []:
            out.append(f"- Search {s['search_no']}: \"{s['params']['query']}\" from {s['params'].get('start_published_date')}"
                       f", {s['status']}, {s.get('returned')} pages")
        for p in band.get("pages") or []:
            out.append(f"  - `{p['id']}` {p['title']} ({p['domain']}, published {p['published']}) {p['url']}")
        out.append("")

    calls = {e["tool_use_id"]: e for e in by_kind("tool_call")}
    results = {e["tool_use_id"]: e for e in by_kind("tool_result")}
    submits = [c for c in calls.values() if c["name"] in SUBMITS]
    if submits:
        out += ["## Every submit Claude sent", ""]
        for c in submits:
            r = results.get(c["tool_use_id"], {})
            verdict = "refused" if r.get("is_error") else "accepted"
            rule = (r.get("submit") or {}).get("rule")
            out += [f"**{c.get('step', 'research').capitalize()} round {c['round']}, `{c['name']}`, {verdict}"
                    + (f" ({rule})" if rule else "") + ":**", "", "```json",
                    json.dumps(c["input"], ensure_ascii=False, indent=2), "```"]
            if r.get("is_error") or c.get("step") == "update" or "update_start" in r.get("content", ""):
                out += ["", "> " + r.get("content", "").strip().replace("\n", "\n> ")]
            out.append("")

    upd = first("update_ended")
    for step, title in (("research", "Research trail"), ("update", "Update step trail")):
        trail = [c for c in calls.values() if c.get("step", "research") == step and c["name"] not in SUBMITS]
        if step == "update" and not trail and upd is None:
            continue
        out += [f"## {title}", ""]
        if step == "update" and upd is not None:
            out += [f"Ended **{upd['end']}** after {upd['rounds']} rounds and {upd['searches']} counted searches"
                    + (f", stop {upd['stop_kind']}" if upd.get("stop_kind") else "")
                    + (f", failure {upd['failure_reason']}" if upd.get("failure_reason") else "") + ".", ""]
        for c in trail:
            r = results.get(c["tool_use_id"], {})
            mark = " *(refused: wrong step)*" if r.get("wrong_step") else ""
            out.append(f"- Round {c['round']}: `{c['name']}` {json.dumps(c['input'], ensure_ascii=False)}{mark}")
        out.append("")

    t = end.get("totals") or {}
    if t:
        cl = t["claude"]
        cost = cl["cost_usd"]
        out += ["## Cost", "",
                f"- Claude: {cl['calls']} calls, ${cost['loop']:.4f} research + ${cost.get('update', 0.0):.4f} update step + "
                f"${cost['composition']:.4f} composition",
                f"- Claude tokens: {cl['input_tokens']:,} input ({cl['cache_read_tokens']:,} cache reads, "
                f"{cl['cache_write_tokens']:,} cache writes), {cl['output_tokens']:,} output",
                f"- Exa: {t['exa']['searches']} searches, ${t['exa']['cost_usd']:.4f}",
                f"- Voyage: {t['voyage']['requests']} requests, ${t['voyage']['cost_usd']:.4f}", ""]
    return "\n".join(out)


def main(paths: list[str]) -> int:
    for name in paths:
        path = Path(name)
        events = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
        target = path.parent / "answers" / (path.stem + ".md")
        if target.exists():
            print(f"kept, not overwritten: {target}")
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(render(events), encoding="utf-8")
        print(f"wrote {target}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
