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
