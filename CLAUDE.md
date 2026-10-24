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
- `data/`: `data/raw/` (raw CourtListener responses and official PDFs) and `data/cache/` (fetched pages) are gitignored and never committed; `data/corpus/` (the frozen corpus) is committed (P1.22); `data/verification/` (verification reports and agent findings) stays local.
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

*Updated Oct 23, 2026, 21:17 CDT, at the end of Phase 1.*

- **State:** Phases 0 and 1 done (tag `phase-1-done`). Decisions P1.1 to P1.22 locked; read `docs/design/locked-decisions.md` in full. The corpus is frozen and committed: `data/corpus/` (32 core cases, 102 opinions, 599,094 tokens; `manifest.json`; `README.md` with sources and attribution). Rebuilding reproduces it from the local raw cache (order below). The text changes only through `scripts/corrections.json`, each entry agent-confirmed (P1.21).
- **Next: Phase 2**, per the brief.
- **How the corpus is built** (re-runnable, in order): `scripts/pull_courtlistener.py` (resumes from cache), `fetch_official_pdfs.py` (33 approved PDFs), `build_corpus.py` (`CORPUS_OUT=<dir>` to build elsewhere), `verify_corpus.py` (`VERIFY_OUT=<dir>`; includes the comma and period report), `verify_lineup.py`, `build_manifest.py` (token counts, free endpoint), `filter_check.py` (done).
- **Verification record** (local, gitignored): `data/verification/text/` (script reports), `data/verification/agents/` (briefs `BRIEF.md`, `BRIEF_ROUND2.md`, `BRIEF_FINAL.md`; findings `batch1-10`, `r2_batch1-6`, `final_a`-`final_d`, `final_case`, `final_pages2`; `final_checklist.json`). `docs/sessions/phase1-handoff.md` is the round-2 handoff, now historical.
- **Frontend session:** the direction is chosen (machinery prototype, Evergreen; folded into `BUILD_LOG.md`); it is locked as a T-entry in Phase 3 (P1.6). Open for the contract: sentence or paragraph text blocks (brief §5).
- **Known, left as built** (P1.22 and the final pass): "supersensitive" (*Jardines*) unresolvable from the print; paragraph division inside the *Kyllo* and *Carpenter* appendices and one *Shultz* footnote; one *Ciraolo* footnote marker one character early; `lineup.json` shows no printed lineup for *White* and *Chatrie* though one is printed (verifier report only; the corpus joiners are right); *Kyllo*'s `header_footnotes_dropped` reads 0 for its excluded amici note.
