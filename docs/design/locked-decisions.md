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
