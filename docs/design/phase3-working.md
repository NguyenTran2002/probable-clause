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

Revised Oct 24, 2026, 14:30 CDT, with the user's four additions (quoted below the table) folded in.

| # | Topic | Status | Notes |
|---|---|---|---|
| 1 | Retrieval method, and one search tool or several | **Locked T1.1** (two tools; `voyage-law-2` + `rerank-3`) | User's item 2. Findings §5. FTS5 measured: 0.04 s index, 3.55 MB, under 1 ms a query. No Anthropic embeddings; Voyage `voyage-law-2` recommended by Anthropic. **Restate first:** the probe's `search_corpus` is already keyword search (FTS5, bm25), so "a keyword-based search tool in addition" reads two ways (a second, meaning-based search beside it; or an exact-match tool beside a ranked one) |
| 2 | How Claude queries: inputs and filters before the search runs | Open; user's full review. **Keyword fields locked T1.2** | User's item 3 (date filter, excluding passages with certain words, etc.). Probe: query only. Candidates: case, date range, opinion type, author, exclusions, result count |
| 3 | How passages reach Claude | Open; user's full review. **Read-around as one unified block locked T1.3** | Result size, metadata in `title`, repeats, context growth under append-only history |
| 4 | The keep tool's shape | Open; user's full review | P2.3 locked keep-only with a reason. Open: un-keep, reason length, batch shape |
| 5 | Citation granularity: Claude chooses how much to cite | Open | User's item 4; replaces "paragraph or sentence blocks" (P2.4). Mechanism fact: a citation is a range of whole text blocks, so the split sets the smallest unit and Claude picks the span (one sentence to the whole paragraph with sentence blocks). Source panel always shows the cited sentence inside its paragraph (prototype already does). Sentence splitting in legal text (U. S., v., Id., ellipses) must be exact |
| 6 | `submit_answer` and the rejection rules | Open | Brief §5.4; the rejection never fired naturally in the probe |
| 7 | The composition call | Open | Inputs, synthesis marking, step-limit fallback |
| 8 | Case-name verifier: reliable, or not offered | Open | User's item 1. **Brief §2 row** ("In the minimum demo"), so dropping it is a superseding decision by the user. P1.10 wording rule depends on it |
| 9 | Citing-cases lookup | Open | Brief §3 cut list, second |
| 10 | System prompt outline | Open | Brief §5.6; full text written in the build |

### Discussion notes

*(Filled in as topics are discussed: options shown, the user's questions, what is still open.)*

**The user's four additions, Oct 24, 2026, 14:30 CDT** (verbatim, for the log at the end of Area 1):

1. *"I'm concerned of the fragile deterministic case-name verifier, particularly how do we recognize robustly what is a case name to check within Claude's answer without requesting Claude to write it as structured output (which breaks Citations feature). I'm considering not offering this if it's something we cannot check reliably. The response is covered under the AI disclosure already, and adding a check that isn't reliable might give false confidence to user."*
2. *"On search corpus, I'm pondering whether we'd want to also offer a keyword-based search tool in addition as well for Claude to dynamically pick and choose thru its research loop."*
3. *"For all search tools, should we consider giving Claude more filtering options before the search is ran? Claude can filter by date, for example, or exclude any passage containing certain words, etc."*
4. *"From the current architecture, the Composition call is the only place where Citations is in action, which makes sense because for Citations to work, we must not be using structured output. However, with the context of legal citation, citing a sentence (within the context of a passage) is often a more frequent practice than citing whole passage. This is from my experience in Constitutional Law class back in college. Thus, I want us to explore giving Claude flexibility in deciding not only what to cite but also how much to cite. Then, in the source panel, we always show the sentence within a paragraph."*

Then: *"Let's list out topics and go into them one at a time together."*

**Topic 1, opened Oct 24, 2026; noted 14:39 CDT** (from scratch, not from the brief). The user's words: *"Let's zoom out from the brief for a moment and discuss retrieval method from scratch here. The brief was written as a starting point only. Currently, I'm thinking of 2 parallel search stacks: 1. RAG with Reranker supported by Voyage AI. Vector search preferably not handled by our free MongoDB cluster. 2. Keyword based search. 3. Both with filtering optionalities for Claude. I'm open to more retrieval ideas, though."*

- Facts gathered: 2,250 paragraphs (median 610 characters, 90th percentile 1,346, max 5,201) and **498 footnotes** (median 412, max 5,055), so 2,748 retrievable units; the Phase 2 probe indexed paragraphs only, not footnotes. Voyage facts from `data/verification/phase2/agent4_retrieval.md` (Oct 24): `voyage-4`/`-4-large`/`-4-lite` (200M free tokens), `voyage-law-2` (legal, 16K context, 50M free), `rerank-3`/`-3-lite` (200M free, 32K context); key is created in MongoDB Atlas but the API does not use the cluster; Voyage latency undocumented.
- Shown to the user: vectors held in memory in the API container (about 11 MB at 1024 dimensions, brute-force dot product), not in any database; two tools vs one fused tool vs one tool with a mode; reranker on semantic results; more ideas (metadata header prepended to the embedded text, Claude-written context, a corpus catalog in the system prompt, a neighbouring-paragraph read tool for topic 3, footnotes as units); whole corpus in context considered and not recommended (P2.7's 400K ceiling, the visible search is the demo); a small retrieval test to pick the models on evidence.
- Recommendation given: lock the shape now, pick the models after the test.

- **Locked T1.1**, Oct 24, 14:48 CDT: *"I'm thinking 2 tools in parallel is the right choice here. For model on the RAG stack, lock voyage-law-2 and rerank-3."* The models were picked by the user, so the retrieval test is not needed to choose them. Still to confirm: vectors in memory in the container; footnotes as searchable units; the metadata header on embedded text.
- **Raised by the user with T1.1, for topic 2:** *"On keyword searches, I'd want us to offer Claude flexibilities here, including searching for sources that contain multiple keywords only (for more narrowing) or searching for sources that contain any of the set of potential keywords."* Proposed: structured fields (`all_of`, `any_of`, `none_of`, quoted phrases; perhaps `near`) compiled by our code to FTS5, rather than raw FTS5 syntax.
- **Raised by the user with T1.1, for topic 3:** *"I'm also considering giving Claude an option to request more context around any given passage on demand. Thought on this?"* Proposed: a third corpus tool reading up to a few units before and after a passage within its opinion (and the footnotes it cites), returned as citable, keepable results.
- **Locked T1.2 and T1.3**, Oct 24, 14:54 CDT (quotes in the log entry of that time). T1.3's open details for topic 3: span cap, same opinion only, cited footnotes, per-unit IDs inside a unified block, neighbours already seen. Format note for topic 3: citations are used only in the composition call, so loop results need not be `search_result` blocks; a unified block could be one text block with inline unit IDs.
- **Topic 2 opened** right after (filters and inputs for both tools). Manifest facts: decided 1878-05-13 to 2026-06-29; 38 authors; opinion types majority 30, plurality 2, dissent 40, concurrence 12, concurrence in the judgment 11, concurrence in part and in the judgment 4, concurrence in part and dissent in part 2, concurrence in part 1 (counted by script).
