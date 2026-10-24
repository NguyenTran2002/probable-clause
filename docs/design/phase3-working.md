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
| 2 | How Claude queries: inputs and filters before the search runs | **Locked T1.4** (keyword fields T1.2) | User's item 3 (date filter, excluding passages with certain words, etc.). Probe: query only. Candidates: case, date range, opinion type, author, exclusions, result count |
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
- **Topic 2 review, 15:00 CDT:** the user asked what the opinion-type groups mean (*"I'm not clear on what do you mean for the opinion types here. Can you give me more context?"*) and asked that filters be clearly optional: *"with this many filter options, which is good, I want us to clearly present them as optional to Claude, so that Claude does not mistaken and try to fill every filters for all requests."* Answered with corpus examples (Katz: Harlan's concurrence is the source of the expectation-of-privacy test; Chatrie: Gorsuch concurring in the judgment; Karo, Dow: concurring in part and dissenting in part); options A groups, B exact types, C both; proposed making filters optional in the schema (one optional `filters` object, nothing required), the descriptions, the system prompt, empty lists treated as unset, and a check in testing.
- **15:05 CDT:** the user chose the four groups with a condition: *"Use four groups HOWEVER, Claude must be aware of this because it's a deviation from standards."* And on the wording: *"this description needs improvement "Most searches need no filters. Add one only to narrow a search you have a reason to narrow." My take is that this encourage Claude to add only one filter most of the time, which is not what we want."* Revised wording proposed (none, one or several; each narrows; unset restricts nothing) and three places where the grouping is stated (filter description, system prompt catalog, exact type in every result and in the answer). Topic 2 to lock as T1.4 on the user's approval of the wording.
- **Locked T1.4**, Oct 24, 15:07 CDT. **Topic 3 opened** right after.
- **Topic 3 proposal shown:** (1) loop results as plain text, not `search_result` blocks (citations only in composition); (2) a header per passage: ID, case, citation, date, exact type and author, page, position in the opinion; joiners in the catalog only; (3) footnote markers inline in loop text only (`[n. *]`), composition text clean; (4) repeats: matched-again IDs listed in one line, the result backfilled to `max_results` new passages; read-around exempt (T1.3); (5) read-around: 0 to 3 units each side (placeholder), same opinion, cited footnotes included, a footnote read returns its citing paragraph; requested passage marked; (6) worst-case growth estimate well under the 400K ceiling. Footnote IDs need a clean form (labels include `*`): proposed `<opinion>-n<k>`.
- **Topic 3 review, 15:16 CDT.** The user: *"What you said about "Results come back as plain text." is a bit confusing to me. Can you clarify and give me more context here."* *"I also need you to clarify how is footnote being handled. The intuitive way would be for us to automatically attaching footnotes to any passage that cites them, right within it, but are we deviating from it? Why?"* *"Read around reach, I want to give Claude flexibility here and we trust Claude's judgement. Give it 0 to 10."* *"Also, read around wouldn't just return a blob of text, we should return all the requested passages with clear markings."* *"Question: what's the average and median length of a passage in our corpus?"*
  - Measured (script): paragraphs mean 676 / median 610 characters, 111 / 99 words; footnotes 583 / 411 characters, 97 / 69 words; all 2,748 units 659 / 576 characters, 108 / 94 words. Tokens estimated at the corpus-wide 0.331 tokens per character: paragraphs about 224 mean / 202 median, footnotes 193 / 136, all units 218 / 191. (Earlier "about 150 tokens a paragraph" was low.) 357 of 2,250 paragraphs cite footnotes, 498 references, at most 8 in one paragraph; 2 footnotes are cited twice, 6 by no paragraph.
  - Answered: "plain text" means the tool result is a list of text blocks, one per passage, each starting with its header, rather than `search_result` blocks; the deciding fact is that a tool result holding search results may hold nothing else (findings §1), so no matched-again line, read-around label or no-match note could sit beside them; untested in the probe (Claude read `search_result` titles there), to check in build tests. Footnotes: switched to the intuitive way, attached inside the citing passage, after its text, each with its own ID; still searchable alone, a footnote hit naming the paragraph that cites it. Read-around 0 to 10 each side; each passage its own marked block, in reading order (clarifies T1.3's "unified block").
