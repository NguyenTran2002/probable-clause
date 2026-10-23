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
