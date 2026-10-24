"""Phase 2 paid check: a simulated research loop on the real corpus (brief §5, §9 items 1-3; P2.5).

One question goes through a loop shaped like the planned one, on the product's
model and effort (P2.1): Claude calls `search_corpus` (SQLite FTS5 over the
corpus paragraphs, results returned as search result blocks), `keep_passages`
(keep-only triage, P2.3), a stubbed `search_web_updates` (no Exa call; it
reports nothing found) and `submit_answer`, which is rejected by the brief §5.4
rules. Then the final composition call, with no tools, over the kept passages
only, twice: one text block per passage, and one text block per sentence.

What it records (data/verification/phase2/, gitignored):
  - per step: usage (uncached input, cache writes, cache reads, output), cost,
    the tool calls made in that turn (several in one turn?);
  - whether a rejected submit_answer, returned as an error tool result with
    the thinking blocks passed back intact, is accepted and handled;
  - whether a request with an earlier turn's thinking blocks removed is refused;
  - for each composition: every citation, and whether its cited_text is exactly
    the text of the blocks it points to.

Every call goes through probe_common.call (ledger, $2 ceiling, no retries).

Usage:
    uv run python scripts/probe_loop.py [--question location|thermal] [--strip-only]
"""

import json
import re
import sqlite3
import sys
from pathlib import Path

from probe_common import EFFORT, call, client, save

ROOT = Path(__file__).resolve().parent.parent
CORPUS = ROOT / "data" / "corpus"
MAX_STEPS = 12  # brief §8.2 starting value
MAX_TOKENS = 16000  # placeholder until measured; covers thinking at high effort
RESULTS_PER_SEARCH = 8  # placeholder; the retrieval design is Phase 3's

QUESTION = (
    "When does the government's collection of location data about a person's phone count as a "
    "Fourth Amendment search? How did the Court get from Smith v. Maryland to the geofence case?"
)

SYSTEM = """You are the research engine of Probable Clause, a tool for legal researchers that finds verbatim passages in U.S. Supreme Court opinions on the Fourth Amendment and technology.

Corpus coverage: decisions through June 29, 2026 (the latest decision in the full pull and in this corpus); pulled October 23, 2026. The corpus holds 32 Supreme Court cases and no other courts, statutes or regulations.

How to work:
- Search the corpus with search_corpus as many times as you need. Each result is one paragraph of one opinion, with its case, citation, decision date, opinion type, author and page.
- Keep the passages that bear on the question with keep_passages, each with a short reason. Do not account for passages you leave; anything not kept is discarded.
- Near the end, run search_web_updates to look for anything published after the corpus coverage date (new decisions, pending cases). Narrow date windows find new decisions; wider ones catch pending cases and their coverage. You choose the query and the date window.
- Call submit_answer with the IDs of the kept passages when you are done. If the question is outside the corpus's subject, set out_of_scope.

Rules:
- Research, not advice. For a question about someone's own situation, present what the Court held and the factors it weighed, and stop short of saying how it applies to them.
- Describe, never evaluate: what the Court held and where the opinions disagree, never whether it was right.
- Opinion types matter: never present a dissent or a concurrence as the holding.
- Dates matter: a later case can overrule, narrow, revive or merely cite an earlier one. Date order alone is not treatment."""

COMPOSE_SYSTEM = """You write the answer for Probable Clause from the passages provided, which are verbatim paragraphs of U.S. Supreme Court opinions that a research step kept. Cite the passages for every statement drawn from them. Statements of your own synthesis carry no citation. Describe what the Court held and where the opinions disagree; never say whether the Court was right; never present a dissent or concurrence as the holding; do not apply the law to anyone's own facts. Name only cases you cite from the passages."""

TOOLS = [
    {
        "name": "search_corpus",
        "description": "Full-text search over the corpus paragraphs. Returns up to 8 paragraphs, best match first. Words are matched in any order; put a phrase in double quotes to match it exactly.",
        "input_schema": {
            "type": "object",
            "properties": {"query": {"type": "string", "description": "Search terms or quoted phrases."}},
            "required": ["query"],
        },
    },
    {
        "name": "keep_passages",
        "description": "Record passages you keep as evidence, each with a short reason. Only kept passages can be cited in the answer. Passages you do not keep need no call.",
        "input_schema": {
            "type": "object",
            "properties": {
                "passages": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {"id": {"type": "string"}, "reason": {"type": "string"}},
                        "required": ["id", "reason"],
                    },
                }
            },
            "required": ["passages"],
        },
    },
    {
        "name": "search_web_updates",
        "description": "Search the web for material published after a date you choose, to flag developments after the corpus coverage date. Results are a convenience and never part of the cited evidence.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "start_published_date": {"type": "string", "description": "YYYY-MM-DD"},
                "end_published_date": {"type": "string", "description": "YYYY-MM-DD"},
            },
            "required": ["query", "start_published_date"],
        },
    },
    {
        "name": "submit_answer",
        "description": "Stop researching. Lists the kept passage IDs the answer will be written from.",
        "input_schema": {
            "type": "object",
            "properties": {
                "kept_ids": {"type": "array", "items": {"type": "string"}},
                "summary": {"type": "string", "description": "Optional one-line summary."},
                "out_of_scope": {"type": "boolean"},
            },
            "required": ["kept_ids", "out_of_scope"],
        },
    },
]


# ---------- corpus and search ----------

def load_passages() -> dict:
    manifest = json.loads((CORPUS / "manifest.json").read_text())
    passages = {}
    for case in manifest["cases"]:
        data = json.loads((CORPUS / "cases" / f"{case['key']}.json").read_text())
        for meta, op in zip(case["opinions"], data["opinions"]):
            for i, p in enumerate(op["paragraphs"]):
                pid = f"{meta['id']}-p{i}"
                passages[pid] = {
                    "id": pid,
                    "text": p["text"],
                    "case": case["name"],
                    "citation": case["citation"],
                    "decided": case["decided"],
                    "type": meta["type"],
                    "author": ", ".join(meta["author"]) or "per curiam",
                    "page": p["page_start"],
                }
    return passages


def build_index(passages: dict) -> sqlite3.Connection:
    db = sqlite3.connect(":memory:")
    db.execute("CREATE VIRTUAL TABLE p USING fts5(id UNINDEXED, text, tokenize='porter unicode61')")
    db.executemany("INSERT INTO p VALUES (?, ?)", [(k, v["text"]) for k, v in passages.items()])
    return db


def fts_query(q: str) -> str:
    phrases = re.findall(r'"([^"]+)"', q)
    words = re.findall(r"[A-Za-z0-9]+", re.sub(r'"[^"]+"', " ", q))
    terms = [f'"{p}"' for p in phrases] + [f'"{w}"' for w in words if len(w) > 1]
    return " OR ".join(terms)


def search(db, q: str) -> list[str]:
    fq = fts_query(q)
    if not fq:
        return []
    rows = db.execute("SELECT id FROM p WHERE p MATCH ? ORDER BY bm25(p) LIMIT ?", (fq, RESULTS_PER_SEARCH))
    return [r[0] for r in rows]


def title_of(p: dict) -> str:
    return f"[{p['id']}] {p['case']}, {p['citation']}, decided {p['decided']}; {p['type']} by {p['author']}; page {p['page']}"


SPLIT = re.compile(r'(?<=[.?!])["\')\]]*\s+(?=["(\[]?[A-Z])')
ABBREV = re.compile(r'(?:\b(?:U|S|v|Mr|Mrs|Id|n|nn|Cf|No|Co|Inc|Ct|F|Cal|App|J|JJ|C|Supp|ed|Ed|cl|art|Art|Stat|Rev|Dept|Gen|Corp|Bros|St|e\.g|i\.e|cf|See|p|pp|L|Rep)\.|\b[A-Z]\.)$')


def sentences(text: str) -> list[str]:
    """Split into sentence blocks whose concatenation is exactly the text."""
    out, start = [], 0
    for m in SPLIT.finditer(text):
        head = text[start:m.start()].rstrip('"\')]')
        if ABBREV.search(head):
            continue
        out.append(text[start:m.end()])
        start = m.end()
    out.append(text[start:])
    assert "".join(out) == text
    return [s for s in out if s]


def result_block(p: dict, by_sentence: bool = False) -> dict:
    parts = sentences(p["text"]) if by_sentence else [p["text"]]
    return {
        "type": "search_result",
        "source": f"https://probable-clause.invalid/passage/{p['id']}",
        "title": title_of(p),
        "content": [{"type": "text", "text": t} for t in parts],
        "citations": {"enabled": True},
    }


# ---------- the loop ----------

def block_dicts(content) -> list[dict]:
    return [b if isinstance(b, dict) else b.model_dump(exclude_none=True) for b in content]


def run_loop(c, passages, db) -> dict:
    messages = [{"role": "user", "content": QUESTION}]
    state = {"searched": False, "updated": False, "update_reminded": False, "kept": {}}
    steps, final = [], None
    for step in range(1, MAX_STEPS + 1):
        resp = call(c, "loop", f"step{step}", max_tokens=MAX_TOKENS, system=SYSTEM, tools=TOOLS,
                    messages=messages, output_config={"effort": EFFORT}, cache_control={"type": "ephemeral"})
        messages.append({"role": "assistant", "content": resp.content})
        uses = [b for b in resp.content if b.type == "tool_use"]
        rec = {"step": step, "stop_reason": resp.stop_reason, "usage": resp.usage.model_dump(),
               "block_types": [b.type for b in resp.content],
               "tool_calls": [{"name": u.name, "input": u.input} for u in uses], "results": []}
        steps.append(rec)
        print(f"step {step}: {[u.name for u in uses]} stop={resp.stop_reason}")
        if not uses:
            break
        results = []
        for u in uses:
            if u.name == "search_corpus":
                state["searched"] = True
                ids = search(db, u.input.get("query", ""))
                rec["results"].append({"tool": u.name, "ids": ids})
                content = [result_block(passages[i]) for i in ids] or [{"type": "text", "text": "No passages matched."}]
                results.append({"type": "tool_result", "tool_use_id": u.id, "content": content})
            elif u.name == "keep_passages":
                ok, bad = [], []
                for item in u.input.get("passages", []):
                    (ok if item.get("id") in passages else bad).append(item.get("id"))
                    if item.get("id") in passages:
                        state["kept"][item["id"]] = item.get("reason", "")
                msg = f"Kept {len(ok)} passage(s)." + (f" Unknown IDs, not kept: {bad}." if bad else "")
                results.append({"type": "tool_result", "tool_use_id": u.id, "content": msg, "is_error": bool(bad and not ok)})
            elif u.name == "search_web_updates":
                state["updated"] = True
                results.append({"type": "tool_result", "tool_use_id": u.id,
                                "content": "No results. (Test run: the web search is not connected; this does not mean nothing has changed.)"})
            elif u.name == "submit_answer":
                oos = bool(u.input.get("out_of_scope"))
                if not state["searched"] and not oos:
                    err = "Not accepted: a corpus search is required before submitting."
                elif not state["updated"] and not state["update_reminded"]:
                    state["update_reminded"] = True
                    err = "Not accepted: no update check has been run. Run one, or explain why it isn't needed, then resubmit."
                else:
                    err = None
                if err:
                    rec["rejected"] = err
                    results.append({"type": "tool_result", "tool_use_id": u.id, "content": err, "is_error": True})
                else:
                    final = u.input
                    results.append({"type": "tool_result", "tool_use_id": u.id, "content": "Accepted."})
            else:
                results.append({"type": "tool_result", "tool_use_id": u.id, "content": f"Unknown tool {u.name}.", "is_error": True})
        messages.append({"role": "user", "content": results})
        if final is not None:
            break
    return {"steps": steps, "final": final, "kept": state["kept"], "messages": messages}


# ---------- thinking blocks removed from history ----------

def strip_test(c, messages) -> dict:
    """Resend the conversation up to the assistant turn after the first one with thinking, that turn's thinking removed."""
    asst = [i for i, m in enumerate(messages) if m["role"] == "assistant"]
    with_thinking = [i for i in asst if any(b["type"] == "thinking" for b in block_dicts(messages[i]["content"]))]
    later = [i for i in asst if with_thinking and i > with_thinking[0]]
    if not with_thinking or not later:
        return {"skipped": "no assistant turn with thinking followed by another turn"}
    first = with_thinking[0]
    cut = messages[: later[0]]
    blocks = block_dicts(messages[first]["content"])
    removed = sum(1 for b in blocks if b["type"] in ("thinking", "redacted_thinking"))
    cut = cut[:first] + [{"role": "assistant", "content": [b for b in blocks if b["type"] not in ("thinking", "redacted_thinking")]}] + cut[first + 1:]
    try:
        resp = call(c, "strip", "thinking-removed", max_tokens=MAX_TOKENS, system=SYSTEM, tools=TOOLS,
                    messages=cut, output_config={"effort": EFFORT})
    except Exception as e:  # a refused request is not billed
        return {"removed_blocks": removed, "outcome": "refused", "error": repr(e)[:600]}
    return {"removed_blocks": removed, "outcome": "accepted", "stop_reason": resp.stop_reason,
            "usage": resp.usage.model_dump()}


# ---------- composition ----------

def compose(c, passages, kept_ids, by_sentence: bool) -> dict:
    blocks = [result_block(passages[i], by_sentence) for i in kept_ids]
    content = [{"type": "text", "text": f"Question: {QUESTION}\n\nWrite the answer from these passages."}] + blocks
    label = "sentences" if by_sentence else "paragraphs"
    resp = call(c, "compose", label, max_tokens=MAX_TOKENS, system=COMPOSE_SYSTEM,
                messages=[{"role": "user", "content": content}], output_config={"effort": EFFORT})
    checks, text_out = [], []
    for b in resp.content:
        if b.type != "text":
            continue
        text_out.append(b.text)
        for cit in b.citations or []:
            d = cit.model_dump()
            entry = {"type": d.get("type"), "cited_text": d.get("cited_text"), "loc": {k: d.get(k) for k in ("search_result_index", "start_block_index", "end_block_index", "source", "title")}}
            if d.get("type") == "search_result_location":
                sr = blocks[d["search_result_index"]]  # index among search results, in order
                cited = [t["text"] for t in sr["content"][d["start_block_index"]:d["end_block_index"]]]
                span = "".join(cited)
                entry["exact"] = d["cited_text"] == span
                # The docs don't say how several blocks are joined; record which separator matches.
                entry["joined_by"] = next((name for name, sep in (("nothing", ""), ("space", " "), ("newline", "\n")) if d["cited_text"] == sep.join(cited)), None)
                entry["in_passage"] = d["cited_text"] in "".join(t["text"] for t in sr["content"])
                entry["blocks_in_result"] = len(sr["content"])
            checks.append(entry)
    return {"label": label, "stop_reason": resp.stop_reason, "usage": resp.usage.model_dump(),
            "n_blocks": sum(len(b["content"]) for b in blocks), "citations": checks,
            "answer": "".join(text_out), "content": block_dicts(resp.content)}


QUESTIONS = {
    "location": QUESTION,
    "thermal": "What did the Court hold about using a thermal imager on a home, and how have later cases relied on that holding?",
}


def main() -> int:
    global QUESTION
    tag = sys.argv[sys.argv.index("--question") + 1] if "--question" in sys.argv else "location"
    QUESTION = QUESTIONS[tag]
    suffix = "" if tag == "location" else f"_{tag}"
    if "--strip-only" in sys.argv:
        messages = json.loads((ROOT / "data" / "verification" / "phase2" / f"loop_messages{suffix}.json").read_text())
        save(f"strip_test{suffix}.json", r := strip_test(client(), messages))
        print(r)
        return 0
    passages = load_passages()
    db = build_index(passages)
    print(f"{len(passages)} passages indexed")
    c = client()
    loop = run_loop(c, passages, db)
    save(f"loop_run{suffix}.json", {k: v for k, v in loop.items() if k != "messages"})
    save(f"loop_messages{suffix}.json", [{"role": m["role"], "content": m["content"] if isinstance(m["content"], str) else
                                 (block_dicts(m["content"]) if m["role"] == "assistant" else m["content"])} for m in loop["messages"]])
    kept = [i for i in (loop["final"] or {}).get("kept_ids", []) if i in loop["kept"]] or list(loop["kept"])
    save(f"strip_test{suffix}.json", strip_test(c, loop["messages"]))
    if kept:
        for by_sentence in ((False, True) if tag == "location" else (True,)):
            r = compose(c, passages, kept, by_sentence)
            save(f"compose_{r['label']}{suffix}.json", r)
            ok = sum(1 for x in r["citations"] if x.get("exact"))
            print(f"compose/{r['label']}: {len(r['citations'])} citations, {ok} exact")
    return 0


if __name__ == "__main__":
    sys.exit(main())
