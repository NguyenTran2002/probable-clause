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
- Corpus pipeline (Phase 1): `scripts/pull_courtlistener.py`, `fetch_official_pdfs.py`, `build_corpus.py` (with `corpus_common.py`, `corpus_pdf.py`, `corpus_align.py`, and the reviewed `corrections.json`), `verify_corpus.py`, `verify_lineup.py`, `build_manifest.py`, `filter_check.py`. Order and purpose under "Current state and next step".
- `data/` (gitignored for now): `data/raw/` for raw CourtListener responses and official PDFs, `data/cache/` for fetched pages, `data/corpus/` for the built corpus, `data/verification/` for verification reports and agent findings. Raw responses are never committed; whether the cleaned corpus is committed is decided at the freeze.
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

*Updated Oct 23, 2026, 20:14 CDT, before a planned compaction.*

- **State:** Phase 0 done. Phase 1 decisions P1.1 to P1.21 locked; read `docs/design/locked-decisions.md` in full (P1.21 replaces P1.16's automatic corrections). The corpus is 32 core cases (21 original, 10 from the filter check, *Clinton*). Built, never committed: `data/corpus/cases/*.json`, `data/corpus/manifest.json` (gitignored until the freeze). The built files are the pre-fix build; fixes from verification round 2 are written in the scripts (committed, untested) but not yet applied.
- **Read next: `docs/sessions/phase1-handoff.md`.** It lists every open finding from verification rounds 1 and 2 and the next steps in order: make two-scan report-only (P1.21); move all agent-confirmed corrections into `scripts/corrections.json` (new entry types for page breaks and notes); finish the generic fixes; add the comma and period check; rebuild and re-verify by script; run the final agent pass; report to the user for approval; then freeze, log, commit, tag.
- **How the corpus is built** (re-runnable, in order): `scripts/pull_courtlistener.py` (resumes from cache), `fetch_official_pdfs.py` (33 approved PDFs), `build_corpus.py` (`CORPUS_OUT=<dir>` to test elsewhere), `verify_corpus.py`, `verify_lineup.py`, `build_manifest.py` (token counts, free endpoint), `filter_check.py` (done).
- **Verification agents' findings** are in `data/verification/agents/` (gitignored): round 1 `batch1-6.json`, round 2 `r2_batch1-6.json`, new cases `batch7-10.json`, the independent case list `independent_list.json`; briefs `BRIEF.md` (updated for P1.17 to P1.18 conventions) and `BRIEF_ROUND2.md`. Agents run on Opus and are never told the main session's conclusions.
- **Frontend session:** it has uncommitted work in `web/looktests/machinery/`. Never touch it; before tagging, ask the user.
- **Open for the user:** *Boyd*'s quoted caption on p.618 (include or not); at the freeze, whether to commit the cleaned corpus (brief default 3).
