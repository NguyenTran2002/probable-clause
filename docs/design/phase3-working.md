# Phase 3 working document

*The main session's working notes for the Phase 3 architecture conversation. Started Oct 24, 2026, 14:14 CDT, at the user's direction. Not a record of decisions: `BUILD_LOG.md` is the record and `locked-decisions.md` its index (P2.12). This file says where the conversation stands, so it survives a compaction.*

## How to resume after a compaction

1. Read the brief in full, then `docs/design/locked-decisions.md`, then this file.
2. Read `docs/research/phase2-findings.md` for the facts behind Area 1 to 3.
3. Pick up at the first topic below not marked locked. Say in one line where you are resuming.

## How Phase 3 runs (the user's directions)

- **One area at a time, then a compaction.** *"I want us to compact after each area, so how about you keep a working document for yourself somewhere of your choosing within this repo. (It's fine to have git track this document.)"* (Oct 24, 2026, 14:14 CDT.) Before each compaction: a BUILD_LOG entry for the area, CLAUDE.md's current state, and this file, all committed.
- **Topic by topic inside an area:** options with a recommendation, then wait. Nothing is locked without the user's words.
- **Each locked topic is a T-entry** (`T<area>.<n>`), written to `BUILD_LOG.md` and `locked-decisions.md` in one commit.
- **Area 1, topics 2 to 4** (querying, surfacing, the keep tool): the user reviews in full and gives the green light before anything is locked (P2.3).
- Subagents, if any: Sonnet 5.5 at high effort or above, never max; no Opus by default (P2.5, memory).

## Areas

| Area | T | Status |
|---|---|---|
| 1. The research loop | T1 | **In progress** (opened Oct 24, 14:14 CDT) |
| 2. The update check (Exa wrapper) | T2 | Not started |
| 3. Run lifecycle and infrastructure | T3 | Not started |
| 4. The interface | T4 | Not started |
| 5. The user's wording and the replays | T5 | Not started |
| Design note (Phase 3's gate) | — | After Area 5 |

Proposed by the main session on Oct 24, 2026; the user started on it with *"Let's start with Area 1, the research loop."* What each area covers is in the BUILD_LOG entry that closes it; the Area 1 list is below.

---

## Area 1: The research loop

### The placeholder architecture, as it stands

From brief §5, P2.3, P2.4, and what `scripts/probe_loop.py` actually ran in Phase 2. Shown to the user as a diagram on Oct 24, 14:14 CDT.

```
visitor question
  -> backend loop (max 12 tool rounds; Sonnet 5.5, high effort, adaptive thinking, automatic caching)
       system prompt (coverage dates, research-not-advice, describe-never-evaluate, types, dates, update check, out of scope)
       tools:
         search_corpus(query)            -> SQLite FTS5 (porter), OR of terms/phrases, bm25, top 8 paragraphs
                                            each a search_result block: title = "[id] case, cite, decided, type by author; page"
                                            content = one text block (the paragraph), citations on
                                            no dedupe: a passage already seen comes back again
         keep_passages([{id, reason}])   -> kept set (keep-only, P2.3); unknown IDs reported
         search_web_updates(query, dates)-> stub in the probe; Exa wrapper is Area 2
         submit_answer(kept_ids, summary?, out_of_scope)
                                         -> §5.4 rejections as error tool results: no corpus search (hard, repeatable);
                                            no update check (once, then accept and show "declined after reminder")
       history append-only (thinking blocks, P2 findings §2)
  -> composition call: no tools, new system prompt, question + kept passages as search_result blocks
       (probe compared paragraph blocks and sentence blocks), citations on
  -> case-name verifier (deterministic, "not in this corpus", P1.10)
  -> answer: cited sentences link to passages; uncited = Claude's synthesis
  step-limit fallback: compose over what was kept, labelled; nothing kept -> say so
```

### Measured facts to design with

- Corpus: 32 cases, 102 opinions, **2,250 paragraphs**, 599,094 tokens (counted by script, Oct 24, 14:14 CDT).
- Probe runs (findings §3): location question 6 steps, 12 searches, 30 kept, $0.237; thermal 4 steps, 7 searches, 14 kept, $0.144. Most of a step's cost is the cache write for its new search results, about 11,000 tokens for three searches of 8 paragraphs.
- **Repeats:** passages surfaced again in later searches, from the probe outputs (counted by script, Oct 24, 14:14 CDT): location 96 surfaced, 83 unique; thermal 56 surfaced, 33 unique. Each repeat is paid as a cache write and then read at every later step.
- Claude read the IDs and metadata in `title`; made two or three searches per turn; ran the update check unprompted in both runs; once kept and submitted in the same turn.
- Sentence blocks: citations of one or two sentences; `cited_text` always equalled the blocks' text (97 of 97).
- Composition is uncached (a new prompt): 9,326 input tokens for 14 kept passages; 15,454 (paragraph) or 18,526 (sentence) for 30.

### Topics

| # | Topic | Status | Notes |
|---|---|---|---|
| 1 | Retrieval method | Open | Findings §5. FTS5 measured: 0.04 s index, 3.55 MB, under 1 ms a query. No Anthropic embeddings; Voyage `voyage-law-2` recommended by Anthropic |
| 2 | How Claude queries the corpus | Open; user's full review | `search_corpus` inputs: query only in the probe. Candidates: filters (case, date range, opinion type), result count |
| 3 | How passages reach Claude | Open; user's full review | Result size, metadata in `title`, repeats, context growth under append-only history |
| 4 | The keep tool's shape | Open; user's full review | P2.3 locked keep-only with a reason. Open: un-keep, reason length, batch shape |
| 5 | Citable unit: paragraph or sentence blocks | Open | P2.4; findings §1. Frontend renders both (fold-in, Oct 23 20:48) |
| 6 | `submit_answer` and the rejection rules | Open | Brief §5.4; the rejection never fired naturally in the probe |
| 7 | The composition call | Open | Inputs, synthesis marking, step-limit fallback, verifier placement |
| 8 | Citing-cases lookup | Open | Brief §3 cut list, second |
| 9 | System prompt outline | Open | Brief §5.6; full text written in the build |

### Discussion notes

*(Filled in as topics are discussed: options shown, the user's questions, what is still open.)*
