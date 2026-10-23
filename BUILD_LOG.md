# Build log

Append-only. Never edit past entries; corrections go in a later entry. Headings come from `date` (America/Chicago), run immediately before writing them.

---

## Oct 23, 2026, 16:23 CDT — Phase 0: Bootstrap

**Asked:** Read the kickoff brief and discuss kicking off the project. Up front, the user proposed that once backend decisions are settled and the main session is implementing, a second Claude Code session iterates on a mock frontend to save time, and asked how to organize two sessions in the same folder that log to and update the same documents. Then: lock the stack and the no-images rule, and start Phase 0.

**Came back:**
- A proposal for the two-session setup: one writer per file (the frontend session writes only `web/` and its own notes file); the mock built against the interfaces contract with a machine-checkable event schema, sharing the replay format; the main session as the only writer of `BUILD_LOG.md`, `locked-decisions.md` and CLAUDE.md, folding in the frontend session's own append-only log; git rules for a shared working tree; start after art direction is locked and contract v1 is committed. Recorded as P0.3.
- git initialized on `main`. First commit `4e518ae`: the brief, unchanged (SHA-256 of the working file and of the committed blob match).
- Scaffold: CLAUDE.md; `docs/design/locked-decisions.md` (P0.1 to P0.3); uv project pinned to Python 3.13 (uv 0.11.29, CPython 3.13.9), no dependencies yet; `.env.example` with `COURTLISTENER_API_TOKEN`, `ANTHROPIC_API_KEY`, `EXA_API_KEY`, `MONGODB_URI`; `.gitignore` covering secrets, raw caches, PDFs and image formats; `.claude/settings.json` denying the agent `Read`, `Edit` and `Write` on `.env` plus common shell reads of it.
- `scripts/check_env.py`: reports set / empty / missing / commented out per variable, never a value; `--phase N` limits the check. Tested against a throwaway file outside the repo (quoted value, commented-out key, empty value, duplicate key). No `.env` exists yet.
- Transcript retention: `cleanupPeriodDays` is not set in the user, local, remote or managed settings, so Claude Code's default cleanup (about 30 days) applies to this session's transcript. Reported to the user; not changed.

**Failures:** None. One self-correction before the first scaffold commit: a `*.jsonl` rule in `.gitignore` (meant for transcripts) was removed, since transcripts live outside the repo and the rule could have hidden corpus files.

**DECISION (user):**
- Stack locked (P0.1): *"On the default stack, I want Python 3.13 with uv and fast api. Lock this. (Open to future adjustment in case something goes wrong, but that would be highly unlikely.)"*
- No images in the repo (P0.2): *"On screenshots or images, we will never commit any to the repo, lock that too."*
- Two-session frontend plan approved (P0.3): *"The plan looks sound to me."*
- *"Start with Phase 0."*

## Oct 23, 2026, 16:54 CDT — Phase 1: Corpus (before the pull: checks and licensing)

**Asked:** Narrow the image block to PNG and JPEG, leave transcript retention alone, run checks now that `.env` is filled (without reading it), and discuss the way forward as a whole: which Phase 1 steps are the user's, exhaustive verification by subagents, pulling all metadata, and whether the frontend mock can start during the pull. Then, as a load-bearing first step: confirm the licence and terms of every source before pulling, since they also shape the frontend.

**Came back:**
- `.gitignore` now blocks only `.png`, `.jpg`, `.jpeg` (P0.4 supersedes P0.2); P0.5 records transcript retention left at the default. CLAUDE.md records the user's CourtListener limits.
- `check_env.py`: all four variables set. `scripts/probe_courtlistener.py`, one authenticated request: cluster 10881683 is *Chatrie v. United States*, decided 2026-06-29, with one sub-opinion (likely a Combined Opinion needing splitting) and no citation. No rate-limit headers are returned.
- P1.1 (exhaustive verification design) and P1.2 (all metadata pulled raw; `scdb_decision_direction` excluded) locked.
- `docs/research/licensing.md`: licences and terms of every source, from three research subagents. The main session re-fetched every page and string-matched every quote (details in the file). Headline findings:
  - Opinions and the syllabus are public domain; West and Lexis editorial matter is not.
  - CourtListener permits this non-commercial use. It forbids implying that Free Law Project endorsed AI analysis.
  - **Exa's terms, read literally, require written permission to display results publicly or store them for replays.**
  - **Anthropic's Usage Policy in force until Nov 12, 2026 treats consumer-facing legal use as high-risk; the Nov 12 version excludes explaining what the law says without applying it to someone's facts.**
  - AI disclosure and an independent-checking notice are required on the page.
  - The Court's own table gives *Chatrie* as 609 U.S. 605.
- Spend: none; one CourtListener request (free).

**Failures:**
- Two of 18 CourtListener quotes did not match at first. One differed only by a space at a link boundary. The other is on SCDB's JavaScript-rendered page and could not be verified.
- The subagent was blocked (403) from courtlistener.com/terms; a direct fetch worked.

**DECISION (user):**
- *"Correction: for image blocking, only count jpeg, jpg, and png. I wouldn't have any image in any other format. The project itself might use svg and ico."* (P0.4)
- *"Transcript retention, leave cleanupPeriodDays alone for now. This project will be done in 2 days."* (P0.5)
- CourtListener limits for the EDU account: *"It's 20 RPM and 1000 RPH for my EDU account."*
- Timing: *"We don't have to commit hard timing plan into docs because I'll keep the time. Your job with time is to mainly log things correctly using system time."*
- *"Verification design with subagents looks good to me."* (P1.1); *"Keeping scdb_decision_direction out is a good catch."* (P1.2)
- *"Let's confirm license of all sources we want to pull and see what we're allowed to do with them first, because this also affects the frontend design as well."*

## Oct 23, 2026, 17:11 CDT — Phase 1: Corpus (decisions on licensing; prep for compaction and the second session)

**Asked:** Discuss three positions on the licensing findings: show only Claude's synthesis of Exa results; the Usage Policy is met because the tool gives no legal advice and discloses AI; credit Claude with plain sentences as in the previous build, whose README the agent was to fetch and read in full. Then: draft the Exa email with an address to send it to; lock all three decisions; don't start Phase 1, prepare for a compaction instead; prepare the ground for a look-test session the user starts, and say where to point it.

**Came back:**
- Read the previous build's README in full (221 lines, fetched with `gh`). It names products only in plain descriptive sentences, opens with a non-affiliation line, uses no logo or badge, and excludes the corpus from its code licence.
- Advice given before locking:
  - Synthesis plus source links removes any republication of web text, but does not by itself satisfy the literal Exa clause, which also lists "modify" and "create derivative works from".
  - The Usage Policy case is stronger resting on what the tool does than on "the user is the human review".
  - The earlier note was too broad: it should have said to avoid a badge-style tagline, not that Claude can't be named.
- Locked P1.3 to P1.6. P1.6 moves the art-direction look tests ahead of Phase 3, into a second session the user starts.
- Exa's contact: the terms name hello@exa.ai six times; support@exa.ai is on its contact and pricing pages. Email drafted for the user to send.
- `docs/sessions/frontend-brief.md`: the frontend session's brief (scope, P0.3 rules, log format, what each look must show, states, notices, checks).
- `scripts/verify_quotes.py`: the quote checker from the licensing research, moved into the repo for Phase 2's re-check.
- CLAUDE.md: two-session rules, layout, and a current-state section written for resuming after compaction.

**Failures:** None.

**DECISION (user):**
- *"Exa, can we only display what Claude synthesize after doing the search? This will avoid directly copying and pasting Exa's returning content."* On the email: *"Hopefully we'll get a response back soon. Otherwise, we proceed as normal."* (P1.3)
- *"On Anthropic's Usage Policy, we have AI disclosure and we don't provide legal advice. It's a research and citation tool, with the user is the human review piece because the project only ever present up evidence."* (P1.4)
- *"On "Built with Claude" wording, I used this phrase in the past that is not trade marked and was just a literal sentence "How this was built with Claude Code" in the README."* (P1.5)
- *"I lock all three decisions here with you"*
- *"Don't proceed with Phase 1 right away, prep the ground for compaction. I will compact this conversation and then give you the signal to proceed with Phase 1 after compaction."*
- *"I want to start the look test session myself, so prep the ground for that session, and let me know where to point that session to kick start it."* (P1.6)

## Oct 23, 2026, 17:17 CDT — Phase 1: Corpus (Exa follow-up, SCDB fields; ready for compaction)

**Asked:** The user emailed Exa; proceed on synthesis plus links without waiting. Give more context on the SCDB fields so the user can decide. Then, with every decision locked, prepare for compaction.

**Came back:**
- P1.7 locked: assume no reply from Exa until the user reports one.
- SCDB context, from CourtListener's `cl/search/models.py` (current `main`, read Oct 23, 2026): clusters carry exactly four SCDB fields. These are `scdb_id`, `scdb_decision_direction` (1 Conservative, 2 Liberal, 3 Unspecifiable), `scdb_votes_majority` and `scdb_votes_minority`.
- Options laid out: exclude entirely; verification only (recommended); show on the page.
- Also flagged: the cluster `headnotes` and `summary` fields may hold commercial-reporter editorial matter. Plan: leave them out unless shown to be official, and report in Phase 1.
- P1.8 locked: SCDB fields are used for verification only.
- CLAUDE.md's current-state section updated for the compaction.

**Failures:** None.

**DECISION (user):**
- *"Emailed Exa. Assume no response from them until I come back with an actual response. We proceed with Claude's summary plus links to the sources."* (P1.7)
- *"Let's use the SCDB fields as verification only."* (P1.8)
- *"If all decisions are locked, prep the ground for compaction."*
