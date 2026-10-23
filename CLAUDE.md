# CLAUDE.md

Working file for the agent. The spec is `PROBABLE_CLAUSE_KICKOFF.md` (the brief); read it in full at the start of every session.

## Rules that always apply

- At the end of each phase or session, append an entry to `BUILD_LOG.md`.
- This brief is frozen. `docs/design/locked-decisions.md` holds every later decision and wins over the brief.
- Every time written anywhere comes from `date`, run immediately before writing it. Never estimate a time.
- Before a planned compaction, update "Current state and next step".

More, each from the brief:

- **Dates shown to a person are America/Chicago**, converted explicitly (`TZ=America/Chicago date`; in code, `zoneinfo`). Never take a date from a UTC timestamp (§10.7).
- **Never read or edit `.env`.** `.claude/settings.json` denies it. Check secrets with `uv run python scripts/check_env.py [--phase N]`, which prints only set / empty / missing / commented out. Ask the user to fill `.env` before the first step that needs a secret.
- **BUILD_LOG.md is append-only.** Entry format in brief §10.2. The DECISION line records only the user's judgement, quoted where useful. Run `date` right before writing the heading, and commit right after appending.
- **Git:** commit as you go; never squash, rebase, amend pushed commits, or force-push; tag `phase-<n>-done` at each phase end; stays local until the user says to push; never commit a session transcript.
- **No `.png`, `.jpg` or `.jpeg` file is ever committed** (locked-decisions P0.4). `.gitignore` blocks them; don't force-add one. The project's own `.svg` and `.ico` files are allowed.
- **No absolute local paths** in any committed file. Use repo-relative paths or `~`.
- **Counts come from scripts**, never by eye. **Timeouts and retries name their basis** (a measurement, or "placeholder until measured"). A paid request is never retried automatically.
- **Restate before acting** when an instruction reads two ways (brief §0). Stop and ask in every case in brief §12.
- **Any deploy, any `gcloud` command that creates or changes cloud resources (scaling included), and any change to goodnight: only on the user's explicit green light.**
- Wording: status word is "working"; never "exhaustive", "comprehensive", "settled law", "guaranteed accurate", "citator", "no hallucinations" (brief §10.6).

## Stack (locked-decisions P0.1)

- Python 3.13 via uv (`.python-version` pins 3.13). FastAPI on uvicorn. Frontend chosen in Phase 3.
- `uv sync` to install; `uv run python <script>` to run. Dependencies are added with `uv add` when the code that needs them arrives.

## Layout

- `PROBABLE_CLAUSE_KICKOFF.md`: the brief, frozen.
- `BUILD_LOG.md`: the raw record, append-only. Written by the main session only.
- `docs/design/locked-decisions.md`: every decision after the brief. Written by the main session only.
- `docs/research/licensing.md`: licences and terms of every source, with each quote string-matched against its page.
- `docs/sessions/frontend-brief.md`: the frontend session's brief. `docs/sessions/frontend-log.md`: its own append-only log (frontend session only).
- `scripts/check_env.py`: reports which secrets are set.
- `scripts/probe_courtlistener.py`: one authenticated request to confirm the CourtListener token works.
- `scripts/verify_quotes.py`: re-fetches cited pages and string-matches quotes (brief §9's re-check). Cache under `data/cache/pages/`.
- `data/` (gitignored for now): `data/raw/` for raw CourtListener responses and official PDFs, `data/cache/` for fetched pages. Never committed.
- `web/looktests/`: the frontend session's look tests (P1.6).
- `.env.example`: the variable names; the user creates `.env`.

## Environment quirks (from the previous build)

- `uv run uvicorn` stalled in the preview tool: launch `.venv/bin/uvicorn` directly.
- `preview_start` failed with `EPERM`: serve from a background shell instead.
- The shell is **zsh, which does not split an unquoted variable.** Write `gcloud` flags out in full; never pass them through a variable.
- Claude Code transcripts live outside the repo, under `~/.claude/projects/`. `cleanupPeriodDays` stays unset at the user's direction (P0.5); don't change it.
- **CourtListener limits for the user's EDU account: 20 requests a minute, 1,000 an hour** (stated by the user, Oct 23, 2026). The API returns no rate-limit headers, so pacing is ours: about 15 a minute, serially, and cache every raw response so nothing is fetched twice.
- Some pages (SCDB, case.law, Exa's collection pages) render by JavaScript and can't be string-matched; `curl` with a browser user agent reaches courtlistener.com/terms when WebFetch gets 403.

## Two sessions in one checkout (P0.3, P1.6)

Two Claude Code sessions share this folder and the `main` branch. The **main session** runs the phases and owns every shared file. The **frontend session**, started by the user, builds the art-direction look tests now and the mock frontend from Phase 4.

**If you are the frontend session:** your brief is `docs/sessions/frontend-brief.md`. Read it in full first. You write only under `web/looktests/` (later `web/`) and `docs/sessions/frontend-log.md`, and never call CourtListener.

**Rules for both:**
- One writer per file.
- Commit only your own paths, by name (`git commit -- <paths>`); never `git add -A` or `git add .`.
- Never `git stash`, `reset`, `checkout -- .`, `restore` on another session's files, a branch switch, rebase or amend.
- On `index.lock`, wait and retry; never delete it.
- Only the main session tags, and only after the frontend session is idle with its work committed.
- Only the main session touches `.venv`, `pyproject.toml` and `uv.lock`.
- Dev servers: main session on 8000; frontend session on another port (8765 suggested).

**If you are the main session:** fold `docs/sessions/frontend-log.md` into `BUILD_LOG.md` and `locked-decisions.md` under your own timestamped entries. Never edit `web/`. Before tagging a phase, check `git status` for the frontend session's uncommitted work and ask the user.

## Current state and next step

*Updated Oct 23, 2026, 17:11 CDT, before a planned compaction.*

- **State:** Phase 0 done (`phase-0-done`). Phase 1 has not started its pull. Done so far in Phase 1:
  - pre-pull checks: all four secrets set; the CourtListener token works
  - the licensing research (`docs/research/licensing.md`)
  - decisions locked: P0.1 to P0.5 and P1.1 to P1.6

  Read `locked-decisions.md` in full after compaction.
- **Waiting on others:**
  - The user is emailing Exa (hello@exa.ai) for written permission to show update-check results and store them in replays (P1.3). If no answer comes by launch, proceed with synthesis plus links and log the risk as accepted.
  - The user is starting the frontend session for look tests (P1.6). It may already be working in `web/looktests/`.
- **Open questions for the user:**
  - Keep *every* SCDB-derived field out of the manifest, so no SCDB citation is owed (proposed, not answered; P1.2 covers only `scdb_decision_direction`)?
  - Optionally email Free Law Project to confirm the portfolio use is in scope.
- **Next: Phase 1 (Corpus), on the user's signal after compaction.** Do not start before the signal.
  1. Propose the inclusion rule (brief §4.1), resolving the *Riley* tension. The user decides.
  2. Pull the cases from CourtListener (§4.3), with these settings:
     - Pace: about 15 requests a minute, serial.
     - Fetch all fields of each docket, cluster and opinion, raw, into `data/raw/` (P1.2). Record each cluster's `source` code.
     - Run the three first tests (§4.4): opinion splitting, text artifacts, page numbers.
     - Known: *Chatrie* (cluster 10881683) has one sub-opinion (likely a Combined Opinion), and no citation on CourtListener. The Court's Term 2025 table lists it as **609 U.S. 605**, so check whether the official PDF is final.
  3. Clean the text (§4.5), with these rules from the licensing notes:
     - Strip any West or Lexis headnotes and summaries, and any embedded S. Ct. or L. Ed. star-paging markers.
     - Pinpoints use U.S. Reports pages only.
     - Keep the syllabus separate and labelled as the Reporter's.
     - Never paraphrase.
  4. Build the manifest: metadata, coverage dates (§4.6), the filter check (§4.7, the user decides each addition), and token counts (§4.8, Anthropic token counting).
  5. Official PDFs for verification: **ask the user's permission once, with the full list** (filename, source, approximate size), before downloading from supremecourt.gov or GovInfo.
  6. Exhaustive verification (P1.1): scripts check everything; Opus subagents, not told your conclusions, judge every listed difference; one independent subagent builds its own case list.
  7. The user approves the corpus. Freeze it, log, update this section, commit, tag `phase-1-done`.
