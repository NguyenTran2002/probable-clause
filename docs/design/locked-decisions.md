# Locked decisions

Every decision made after the kickoff brief (`PROBABLE_CLAUSE_KICKOFF.md`, frozen at the first commit) lives here. **This file wins over the brief on any conflict.**

Numbering: `P<phase>.<n>` for decisions made in Phases 0 to 2 and 4 to 5; `T<topic>.<n>` for the Phase 3 architecture conversation. A superseded decision stays in place, marked superseded, with its replacement entered below it. Dates are America/Chicago.

---

## Phase 0: Bootstrap

### P0.1 Stack: Python 3.13 via uv, FastAPI on uvicorn

- **Decision:** Brief §2, Claude's default 1, is locked: Python 3.13 managed with uv, FastAPI served by uvicorn. The frontend stack is still chosen in Phase 3.
- **User's words:** *"On the default stack, I want Python 3.13 with uv and fast api. Lock this. (Open to future adjustment in case something goes wrong, but that would be highly unlikely.)"*
- **Note:** Locked, with the user open to adjusting it only if something goes wrong. Any change goes through the user and is entered here as a superseding decision.
- **Date:** Oct 23, 2026

### P0.2 No screenshots or images committed to the repo — SUPERSEDED by P0.4

- **Decision:** Brief §2, Claude's default 7, carries over in the user's wording: no screenshots or images are ever committed to this repository. `.gitignore` excludes common image formats to enforce it.
- **User's words:** *"On screenshots or images, we will never commit any to the repo, lock that too."*
- **Open for Phase 3:** whether a favicon or a wordmark file counts as an image under this rule. Until the user says otherwise, none is committed, and the wordmark is set in text and CSS.
- **Date:** Oct 23, 2026

### P0.3 A second Claude Code session for the mock frontend, in the same checkout

- **Decision:** In Phase 4, the frontend is built by a **second Claude Code session** working on a mock frontend, instead of the frontend subagent named in brief §3. Both sessions work in the same folder and on the same branch (no worktree). The organization, as proposed by Claude and approved by the user:
  1. **File ownership, one writer per file.** The main session owns the backend, corpus, `scripts/`, `tests/`, deploy, `pyproject.toml`/`uv.lock`, and every shared document. The frontend session writes only under `web/` and its own notes file. The interfaces contract, CLAUDE.md, the brief and this file are read-only to it.
  2. **The mock is built against the interfaces contract only**, with a machine-checkable event schema (`contracts/events.schema.json` or similar) that both the backend's event tests and the frontend's mock fixtures validate against. Contract changes have one writer, the main session, which versions them and tells the frontend session. Mock fixtures share the replay format, and cover waking, disconnect and reconnect, abandoned and interrupted runs, rejections, the step limit, verifier flags and the daily cap.
  3. **Shared documents have one writer, the main session.** The frontend session keeps its own append-only `docs/sessions/frontend-log.md` (same entry format, headings from `date`, user decisions marked `DECISION (user)` with the user's words). The main session folds those into `BUILD_LOG.md` and this file under its own timestamped entries.
  4. **Git in a shared working tree:** each session commits only its own paths by name (`git commit -- <paths>`), never `git add -A` or `git add .`; never `git stash`, `reset`, `checkout -- .`, or a branch switch; on `index.lock`, wait and retry, never delete it; only the main session tags phase ends, after the frontend session is idle and committed; separate dev-server ports; only the main session touches `.venv`.
  5. **Start condition:** after art direction is locked (Phase 3) and contract v1 is committed (start of Phase 4). The details go in the Phase 4 build plan, which the user approves before the build starts.
- **User's words:** *"In a future phase where decisions on the backend are settled and this claude code session is on implementation, I'd want to be iterating on a mock frontend with a second claude code session to cut time and be more efficient."* On the proposal: *"The plan looks sound to me."*
- **Date:** Oct 23, 2026

### P0.4 Image block narrowed to PNG and JPEG (supersedes P0.2)

- **Decision:** The no-images rule covers `.png`, `.jpg` and `.jpeg` files only; those are never committed. The project's own `.svg` and `.ico` files (for example a favicon or wordmark) may be committed. This also settles the favicon and wordmark question P0.2 left open for Phase 3. `.gitignore` blocks exactly those three formats.
- **User's words:** *"Correction: for image blocking, only count jpeg, jpg, and png. I wouldn't have any image in any other format. The project itself might use svg and ico."*
- **Date:** Oct 23, 2026

### P0.5 Transcript retention left at the default

- **Decision:** `cleanupPeriodDays` stays unset (Claude Code's default cleanup, about 30 days). The agent does not change it.
- **User's words:** *"Transcript retention, leave cleanupPeriodDays alone for now. This project will be done in 2 days."*
- **Date:** Oct 23, 2026

---

## Phase 1: Corpus

### P1.1 Exhaustive corpus verification, scripts plus independent subagents

- **Decision:** Phase 1 ends with exhaustive verification, not the spot check brief §4.5 asks for. Scripts check everything mechanically: every cleaned opinion aligned word by word against the official PDF text with every difference listed; every opinion in the Court's lineup present after splitting, with correct boundaries; every metadata field compared against the official text. Opus subagents, each given a batch of cases and none told the main session's conclusions, judge every listed difference (cleaning artifact, real difference, or OCR noise in the official PDF) and check opinion type, author and joiners. One further subagent builds its own case list from scratch and compares it with the corpus, alongside the citation-graph filter check (§4.7).
- **User's words:** *"At the end of Phase 1, subagents to verify the corpus exhaustively will be crucial here. We also want to pull all relevant metadata for each corpus item."* On the design: *"Verification design with subagents looks good to me."*
- **Date:** Oct 23, 2026

### P1.2 Pull all metadata; keep `scdb_decision_direction` out of the manifest and the prompt

- **Decision:** Every field CourtListener holds for each docket, cluster and opinion is cached raw (gitignored). A curated manifest carries what the app uses. The Supreme Court Database's `scdb_decision_direction` (a liberal or conservative coding of each outcome) stays in the raw cache only: never in the manifest, the system prompt, a tool result, or the page, because it would break the political-heat guardrail (brief §2, "never says whether the Court was right").
- **User's words:** *"We also want to pull all relevant metadata for each corpus item."* On the exclusion: *"Keeping scdb_decision_direction out is a good catch."*
- **Date:** Oct 23, 2026

### P1.3 The update check shows Claude's synthesis plus source links, never Exa's content

- **Decision:** Exa stays as the update-check search (brief §2 unchanged). On the page and in replays, the update-check band shows **Claude's own synthesis** of what the search found, plus a **link to each source** (title, URL, published date). It never shows page text, highlights, or Citations `cited_text` drawn from web results. Internally, Citations still mark which sentences are grounded in a web result; on screen, such a sentence links to its source instead of quoting it. This changes how brief §6.3 and §6.4 display results. Every parameter Claude chose is still shown, and the honesty label still applies.
- **Why:** Exa's Terms §4.2(a), read literally, require written permission to display, copy or publish information obtained through the service (`docs/research/licensing.md` §4). Synthesis plus links removes any republication of third-party web text. It does not by itself satisfy the literal clause ("modify", "create derivative works from" are also listed), so the user is emailing Exa (hello@exa.ai, the address named in the terms) for written permission covering public display and stored replays. If no answer arrives before launch, the project proceeds with this design and the remaining risk is logged as accepted by the user.
- **User's words:** *"Exa, can we only display what Claude synthesize after doing the search? This will avoid directly copying and pasting Exa's returning content."* Then: *"Draft the Exa email and give me an email address to send it to. Hopefully we'll get a response back soon. Otherwise, we proceed as normal."* and *"I lock all three decisions here with you"*.
- **Date:** Oct 23, 2026

### P1.4 Anthropic Usage Policy: the case rests on what the tool does

- **Decision:** Probable Clause proceeds as planned under Anthropic's Usage Policy. The basis, as recorded:
  - The tool does not do the high-risk activity. It explains what the Court held and shows verbatim evidence, and never applies the law to a person's own facts (brief §2). The policy published for Nov 12, 2026 excludes exactly this: "explaining what a law says … without applying it to the individual's circumstances".
  - The page discloses AI use, and tells visitors to check factual assertions independently (Commercial Terms §D.3).
  - The README and page do **not** claim that the visitor is the "human in the loop".
- **Gap, recorded:** the policy in force until Nov 12 (since Sep 15, 2025) treats consumer-facing "legal" use as high-risk, and its full text was not found. Describing a holding could be read as legal interpretation under that wording. The user accepts this reading.
- **User's words:** *"On Anthropic's Usage Policy, we have AI disclosure and we don't provide legal advice. It's a research and citation tool, with the user is the human review piece because the project only ever present up evidence."* Then: *"I lock all three decisions here with you"*.
- **Date:** Oct 23, 2026

### P1.5 Crediting Claude: plain descriptive sentences, as in the previous build

- **Decision:** Claude, Claude Code and Anthropic are named only in plain, factual sentences, following the previous build's README. Examples:
  - a README section headed "How this was built with Claude Code"
  - on the page, a sentence such as "Answers are written by Claude, Anthropic's model, through the Claude API"
  - the non-affiliation line near the name (brief default 4)

  No logos, no badge or tagline-style credit, no Claude brand colours, nothing implying endorsement. This replaces default 4's "Built with Claude" footer idea. The README's licence section says the opinion text is public domain and not covered by the code licence. Exact page wording is settled in Phase 3.
- **User's words:** *"On "Built with Claude" wording, I used this phrase in the past that is not trade marked and was just a literal sentence "How this was built with Claude Code" in the README."* Then: *"I lock all three decisions here with you"*.
- **Date:** Oct 23, 2026

### P1.6 Art-direction look tests start now, in a second session the user starts

- **Decision:** The Phase 3 art-direction look tests (brief §7.3) move forward to run alongside Phase 1, in a second Claude Code session that **the user starts**, in this same folder and branch (not a worktree), under P0.3's rules. Its brief is `docs/sessions/frontend-brief.md`. This changes P0.3's start condition for look tests only. The contract-bound mock frontend still waits for contract v1 (start of Phase 4). The art direction the user picks is locked by the main session in Phase 3 as a T-entry, from the frontend session's log.
- **User's words:** *"Starting the look test in parallel with phase 1 would be nice?"* Then: *"I want to start the look test session myself, so prep the ground for that session, and let me know where to point that session to kick start it."*
- **Date:** Oct 23, 2026

### P1.7 Exa emailed; build on P1.3 without waiting

- **Decision:** The user has emailed Exa for written permission (P1.3). Until the user reports an actual reply, assume none: build the update check as Claude's synthesis plus links to the sources, with no Exa content shown or stored.
- **User's words:** *"Emailed Exa. Assume no response from them until I come back with an actual response. We proceed with Claude's summary plus links to the sources."*
- **Date:** Oct 23, 2026
