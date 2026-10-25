# Probable Clause: design note

*Phase 3's gate (brief §3), written Oct 24, 2026 by the main session for the user's review. It summarises; the decisions themselves are in `docs/design/locked-decisions.md` (index) and `BUILD_LOG.md` (the authoritative record, P2.12), and each section names the entries it rests on. Where this note and an entry differ, the entry wins.*

## 1. What is being built, and the one guarantee

A research tool for U.S. Supreme Court opinions on the Fourth Amendment and digital technology, for legal researchers. Claude searches a frozen corpus of **32 cases (102 opinions, 599,094 tokens)**, keeps the passages that bear on the question with a reason for each, and an answer is written from those kept passages only, with every citation pointing at exact sentences. It does research, not advice: it never applies the law to a person's own facts and never says whether the Court was right (brief §2).

**The guarantee is narrow:** *"This passage appears word for word in this opinion, as normalised from the official text."* (T5.2). A citation shows where words are, not that they prove the point. Two checks run by our own code, not by AI, sit under the answer: quotations found in the kept passages, and full case names and U.S. Reports citations found in the corpus (T1.12, T5.2). Short case names are not checked, and the page says so. The general case-name verifier of brief §2 was dropped because it could not be done reliably (T1.12).

## 2. A run, end to end

1. **Start.** The page sends the question (2,000 characters at most, T3.7) to `POST /runs`. The worst case of a run (about $1.67) is reserved against the $10 daily and $60 monthly caps in one atomic Atlas update, or the run is refused (T3.4). The loop starts when the page attaches to `GET /runs/{id}/events` (T3.1).
2. **The loop**, on Sonnet 5.5 at high effort (P2.1), at most 12 rounds and 400K input / 20K output tokens (P2.7), with six tools:
   - `search_meaning`: Voyage `voyage-law-2` vectors held in memory, reranked by `rerank-3` (T1.1, T3.6);
   - `search_exact`: SQLite FTS5 from `all_of` / `any_of` / `none_of` lists our code compiles (T1.2);
   - both take one optional `filters` object, presented to Claude as optional, with opinion types in four groups Claude is told about (T1.4);
   - `read_passages`: by ID or page, 0 to 10 around, returned as marked blocks (T1.3, T1.6);
   - `keep_passages`: batched, a reason each, re-keeping replaces the reason, cap 40 (T1.7);
   - `search_web_updates`: the update check through Exa's MCP server, 3 a run (T2.1 to T2.5);
   - `submit_answer`: the stop signal, refused by four rules (same-turn search, no search yet, nothing kept with no note, no update check once), and checked for the band's findings and the copy guard (T1.10, T2.3).
   No citing-cases lookup; Claude traces later cases by keyword search on the citation string (T1.13). The system prompt's outline is T1.14 (with the query rule of T5.5).
3. **Composition**, on Opus 5.5 at high effort (T1.8), with no tools: each kept passage goes in as a custom content document of **our** sentences (a conservative splitter, built and checked in Phase 4), metadata and the keep reason in `context` (T1.9). Claude cites any run of whole sentences; uncited text is synthesis, marked by its lack of an underline (T1.11, T5.2). Markdown is rendered with raw HTML and links off; `max_tokens` 12,000 (T1.11, T4.2).
4. **The checks** run when the answer finishes streaming (T1.12).
5. **The update-check band**, kept apart from the corpus evidence: Claude's own statements naming their sources, checked by our code to have come back in this run, never called verified, never showing page text (P1.3, T2.3, T5.3). The outcome (found, nothing relevant, skipped, declined after reminder, unavailable) is worked out by our code.
6. **Out of scope or nothing found:** Claude's note to the visitor takes the answer's place, labelled as a reply with no sources (T1.10).

**Fallbacks:** the step limit, the token ceiling, the 10-minute run deadline or an error after retries all compose from what was kept, labelled; with nothing kept, no answer (T1.11, T3.3, T3.5).

## 3. Lifecycle and infrastructure

- **Streaming:** Server-Sent Events, numbered and stored, the answer one block at a time with its citations, so a reconnect or a replay shows exactly what was shown (T3.1).
- **Disconnects:** a heartbeat from the page every 10 s, checked before every paid call; unattended at 25 s, the run pauses; at 60 s it is abandoned and composes nothing; no paid call starts while nobody is connected (brief §2, T3.2).
- **Retries:** Anthropic and Voyage calls retried by our code, up to twice, each retry shown as a step; never hidden in the SDK; Exa never retried by us (T3.3, T2.4). A degraded meaning search shows a warning (T3.3, T5.4).
- **Spend:** list prices computed from each response's usage, Exa's reported cost, Voyage at list price; every budget stop recorded; test runs on `Probable_Clause_test` (T3.4).
- **Cloud Run** in project `probable-clause`, us-central1: a static nginx web service (max 2) and the API (max 1, min 0, 512 MiB), both behind one new goodnight block on `nguyennhattran.com/probable-clause`, forwarding no client IP; secrets in Secret Manager (T3.5, T4.2). Cold starts accepted (brief §2); the wake protocol of brief §8.5 with wake on landing (T3.6).
- **Retention:** run events 24 hours; per-run records without question or answer text; no cookies, no analytics, no IP use; the privacy note names each provider's own retention (T3.7, T5.5, `docs/research/retention.md`).

## 4. The interface

The machinery prototype in Evergreen (`web/looktests/machinery/`) is the baseline (T4.1), in plain JavaScript modules with no build step (T4.2). What changes from it: source cards Found → Kept → kept and cited / kept, not cited / not kept; no syllabus; the band in T2.3's shape; the checks' flags; a reader fetching one file per opinion from the web service; "View API calls" showing the exact fragments sent and each response's `usage` (T4.3). Every new state (waking, paused, reconnecting, retries, abandoned, replays, one question per run) goes in an element the prototype already has (T4.4). A run's total cost for Claude and Exa, labelled as such (T4.5). Fonts are served by our own web service (T5.5). Sizes checked at 1440×900, 393×852 and 852×393 (T4.1).

## 5. The wording and the replays

Every line on the page is the user's final text: the pitch, disclosure, not-legal-advice and affiliation lines, the credits per text source and the Apache 2.0 licence (T5.1); the guarantee, coverage, answer key, checks, cost label and text-status note (T5.2); the band (T5.3); every run state and stop label (T5.4); the privacy note (T5.5). Figures in that text follow their settings. Text sent to Claude (prompts, tool descriptions, rejections) is written in the build and reviewed by the user before its first paid run (T1.14).

**Replays (T5.6):** five recorded runs, four on the full corpus and the geofence question on a corpus that ends before *Chatrie*, labelled; never edited; each reviewed by the user; recorded in Phase 5 (about $2 to $3, approved then).

## 6. Limits and costs, as measured

- **Measured in Phase 2** (findings §3, Sonnet throughout): two runs of 4 and 6 rounds cost $0.144 and $0.237 of Claude and took about 30 and 45 s.
- **Estimated with composition on Opus** (T1.8): about $0.19 to $0.31 a run, so the $10 day covers roughly 32 to 53 such runs.
- **Worst case reserved per run:** about $1.67 (T3.4); about five runs at once within $10 (T3.5).
- **Exa:** at most $0.021 a run (T2.1). **Voyage:** very likely within its free tokens, still counted by the caps (T4.5).
- **Spend so far:** $0.6964 of Phase 2's $2 Anthropic ceiling. Phase 4's ceiling is $3 (P4.1).

## 7. Accepted risks and open edges

- **Exa's terms** (P1.3, P1.7): read literally, §4.2(a) asks for written permission to display information obtained through the service. The design shows only Claude's synthesis and links, never page text. The user emailed Exa; with no reply, the project proceeds on this design, and **before launch the remaining risk is recorded as accepted by the user, or the user's reply changes it.**
- **Exa's licence over queries** (T5.5, `retention.md`): Exa may keep and use queries; Claude is told to keep personal details out of them, and the privacy note says so. Tested in Phase 5 with a question that carries a name.
- **Anthropic's Usage Policy** (P1.4): the tool explains what the Court said and never applies it to a person's facts, which the policy published for Nov 12, 2026 excludes from its high-risk case.
- **Cold starts:** accepted for cost (brief §2); measured after the first deploy and in Phase 5.
- **What the checks do not cover:** short case names; whether a cited passage proves the point; whether a case is still good law (T1.12, T5.1).

## 8. Placeholders to measure in Phase 5

From the closing sections of the working doc: 50 semantic candidates and 10 items per keyword list (T1.4); 300-character reasons and the 40-passage cap (T1.7); the 30,000 / 12,000 composition reserve (T1.11); the four-word quotation minimum (T1.12); 4,000 characters per web result, the 10-word copy guard, Exa's 30 s timeout and handshake (T2.2 to T2.5); heartbeat 10 s, attended 25 s, grace 60 s, watchdog 45 s, keep-alive 15 s (T3.1, T3.2); loop and composition deadlines 120 s and 300 s, retry waits, Voyage 10 s (T3.3); the 10-minute run deadline, the 900 s API timeout, web max 2, API 512 MiB (T3.5); the 2,000-character question cap (T3.7); the 90 s and 5-minute long-wait steps (T3.6). Each is marked "placeholder until measured" in code and in the contract (brief §10.7).

## 9. The user's actions before live runs

- A Console workspace and key for the live service with a $60 monthly limit (T3.4).
- How secret values reach Secret Manager (T3.5).
- The goodnight block, reviewed and deployed only on the user's green light (T3.5).
- If the Voyage key turns out to be an Atlas key, the Atlas training toggle turned off too (T5.5).
- Exa's reply, or the risk accepted, before launch (P1.3).
- Sign-off on the local review, then a separate green light for the deploy (P4.1).

## 10. What Phase 4 starts with

The locked build plan, P4.1: the scaffold with `LICENSE`, T1.5 (Oliver's "II", no subagent), interfaces contract v1 with its event schema checked by an Opus xhigh subagent, and the prompt drafts for the user's review; then Wave 1 (six subagents: the splitter, the corpus index, meaning search, the Exa wrapper, money and state, the answer checks) and Wave 2 (the loop and composition, the API and lifecycle, the images and deploy script); the frontend by the frontend session against contract v1 (P0.3); reviews after each builder and one at the end; the whole stack run locally for the user's review before any deploy.

**The user's approval of this note closes Phase 3:** a log entry, CLAUDE.md updated, and the tag `phase-3-done` once the frontend session is idle with its work committed.
