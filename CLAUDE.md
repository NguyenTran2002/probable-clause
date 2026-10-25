# CLAUDE.md

Working file for the agent. The spec is `PROBABLE_CLAUSE_KICKOFF.md` (the brief); read it in full at the start of every session.

## Rules that always apply

- At the end of each phase or session, append an entry to `BUILD_LOG.md`.
- This brief is frozen. `docs/design/locked-decisions.md` holds every later decision and wins over the brief.
- **`BUILD_LOG.md` is the authoritative record of decisions and wins over `locked-decisions.md`**, which is the index of decisions in force (P2.12). Write each new decision to both in the same commit; each decisions entry gets a **Log** line naming its log entry. Fix a conflict with a superseding decisions entry, never by editing the log.
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

- Python 3.13 via uv (`.python-version` pins 3.13). FastAPI on uvicorn. Frontend: plain JavaScript modules, no build step, markdown-it vendored, a pinned nginx web service (T4.2).
- `uv sync` to install; `uv run python <script>` to run; `.venv/bin/pytest -q` for the tests (importlib mode, anyio for async). Phase 4's dependencies were added at once (P4.1): anthropic, mcp, fastapi, uvicorn, pymongo, numpy, httpx2 (Voyage over plain HTTP), jsonschema; pytest for development. A new one only by the main session.

## Layout

- `PROBABLE_CLAUSE_KICKOFF.md`: the brief, frozen.
- `BUILD_LOG.md`: the raw record and the authoritative record of decisions, append-only. Written by the main session only.
- `docs/design/locked-decisions.md`: the index of decisions in force, under the log and over the brief (P2.12). Written by the main session only.
- `docs/design/design-note.md`: Phase 3's design note, approved by the user (the architecture in summary, pointing to the entries).
- `docs/design/contract.md`: **interfaces contract v1**, the builders' spec (parts A to I, signatures, events, Atlas, ownership in §13). One writer, the main session. `contracts/events.schema.json`: every event, machine-checked.
- `api/`: the backend. The main session owns `api/types.py`, `api/settings.py` (every figure with its basis), `api/errors.py`, `api/retry.py`, `api/protocols.py`, `api/prompts/`; builders own their parts' folders (contract §13). `tests/`: per-part folders; `tests/contract/`, `tests/fixtures/` are the main session's. `LICENSE`: Apache 2.0.
- `docs/design/phase3-working.md`: the main session's Phase 3 working notes, now historical; its "Area N closed" sections list what each area carried into Phases 4 and 5. Not a decisions record.
- `docs/research/licensing.md`: licences and terms of every source, with each quote string-matched against its page.
- `docs/research/phase2-findings.md`: the Phase 2 research (brief §9), every claim with its source and tag, sources re-checked.
- `docs/research/retention.md`: what each provider keeps of what the page sends (Area 5, T5.5), quotes string-matched.
- `docs/sessions/frontend-brief.md`: the frontend session's brief. `docs/sessions/frontend-log.md`: its own append-only log (frontend session only).
- `scripts/check_env.py`: reports which secrets are set.
- `scripts/probe_courtlistener.py`: one authenticated request to confirm the CourtListener token works.
- `scripts/verify_quotes.py`: re-fetches cited pages and string-matches quotes (brief §9's re-check). Cache under `data/cache/pages/`.
- Corpus pipeline (Phase 1): `scripts/pull_courtlistener.py`, `fetch_official_pdfs.py`, `build_corpus.py` (with `corpus_common.py`, `corpus_pdf.py`, `corpus_align.py`, and the reviewed `corrections.json`), `verify_corpus.py`, `verify_lineup.py`, `build_manifest.py`, `filter_check.py`. Order and purpose under "Current state and next step".
- `scripts/probe_chunking.py`: Phase 3 paid check of Anthropic's plain-text sentence chunking (T1.9). Outputs under `data/verification/phase3/`.
- `scripts/check_structure.py`: read-only check of section headings and footnote markers against every raw copy (Phase 3; Phase 1's word check skipped both). Report under `data/verification/structure/`.
- Phase 2 paid checks: `scripts/probe_common.py` (spend ledger and ceiling, no retries), `probe_loop.py` (a simulated research loop on the corpus), `probe_exa.py` (Exa's MCP server). Outputs under `data/verification/phase2/` (gitignored).
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

Two Claude Code sessions share this folder and the `main` branch. The **main session** runs the phases and owns every shared file. The **frontend session**, started by the user, built the art-direction look tests (Phase 1) and builds the real page against a mock in Phase 4 (brief rewritten Oct 24, 2026).

**If you are the frontend session:** your brief is `docs/sessions/frontend-brief.md`. Read it in full first. You write only under `web/` (what is served) and `webdev/` (your mock server and Node tests, never served), and `docs/sessions/frontend-log.md`; you never call CourtListener or any paid service. `web/_generated/` (gitignored) holds `scripts/build_web_data.py`'s output for local use.

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

*Updated Oct 24, 2026, 22:48 CDT, after Wave 1, the embedding, the Atlas tests and the fixtures.*

- **State:** Phases 0 to 3 done. Decisions P0.1 to P2.12, T1.1 to T5.6 and P4.1 to P4.3 are locked in `docs/design/locked-decisions.md`; `BUILD_LOG.md` is the authoritative record (P2.12). The architecture in summary: `docs/design/design-note.md` (approved Oct 24, 2026, 20:01 CDT). The corpus is frozen and committed: `data/corpus/` (32 core cases, 102 opinions, 599,096 tokens since T1.5; `manifest.json`; `README.md`). The text changes only through `scripts/corrections.json` (P1.21; T1.5 is the one main-session-confirmed exception).
- **Tag:** `phase-3-done` placed Oct 24, 2026, 20:02 CDT, after the user's word: *"Frontend session is closed and concluded."* The frontend session restarts only when the user starts it for the mock frontend (after contract v1).
- **Now: Phase 4, the build, run by P4.1.** Read first: the brief in full; `locked-decisions.md` in full; `design-note.md`; the "Area N closed" sections of `docs/design/phase3-working.md` (the build items, build tests and Phase 5 items per area); `docs/research/phase2-findings.md`; `docs/research/retention.md`; **`docs/design/contract.md` in full** and the main session's shared code in `api/`. Say in one line where you are resuming.
- **Progress (Oct 24, 2026, 21:52 CDT):** step 0 done (scaffold, T1.5, contract v1 and now v1.1, P4.2, P4.3, prompt drafts 23f1ca2). **Wave 1 done:** parts A to F merged (A ba250cb, B 826d9ea, C 0b80bf6, D 611eb79, E c70156e, F 7d87bee), each after a Sonnet 5.5 high review and the builder's fixes; contract v1.1 rulings logged in each part's BUILD_LOG entry. Whole suite: 2,364 passed, 41 skipped (part E's Atlas-gated tests). Corpus: 2,462 passages, 11,005 sentences; labels reviewed (37 distinct). No spend in Wave 1.
- **Next, in order:** (done: the prompt drafts approved by the user, 21:55; the corpus embedded, a0a4d1f, 524,853 tokens, $0.0630) E's Atlas tests passed against `Probable_Clause_test` (40, 22:09); the fixtures (5dd4d15: 30 streams, 19 HTTP answers, `tests/fixtures/make_fixtures.py`) and the frontend brief (f6d70f6) are done, so the user can start the frontend session. (1) Wave 2 (G, H, I) with briefs from contract §4.G to §4.I and these Wave 1 notes: G passes `failed_attempt_usage(...)` with an estimate for failed Claude attempts, calls `copy_guard_report` and withholds `flagged_statements` (P4.3), calls D's `schema_check()` on the instance's first update search, prices by the requested model ID (exact match), runs F's checks off the event loop; H sends run records in the shape of `api/state/records.py`'s docstring, generates run IDs matching `[A-Za-z0-9_-]{1,128}`, and never logs an exception chain from the store; the passage header writes "per curiam" when `authors` is empty and `joined_by_source` says so.
- **Voyage, settled:** the key is a Voyage platform key (`scripts/probe_voyage.py`); prices from Voyage's pricing page, confirmed; `rerank-3` confirmed valid by the user; rerank checked to reorder results (10 of 12 in a throwaway comparison).
- **P4.1 in short:**
  - **Step 0, the main session only:** the scaffold (`LICENSE` Apache 2.0; `api/`, `tests/`, `contracts/`; every dependency added at once with `uv add`); T1.5 (Oliver's "II", page image confirmed by the main session, **no subagent**, Phase 1 checks and `check_structure.py` re-run, logged); **interfaces contract v1** (`docs/design/contract.md`, `contracts/events.schema.json`: endpoints, run states, Atlas collections, settings with each value's basis, the price table, per-opinion and replay formats, every module's signatures), checked against T1.1 to T5.6 by an Opus 5.5 xhigh subagent not shown the main session's reasoning; the prompt drafts (loop, composition, tool descriptions, rejection texts) for the user's review, written while Wave 1 runs.
  - **Wave 1, six subagents in parallel, own paths, tests first, against fakes, no paid calls, no keys:** A splitter and its check (T1.9), Opus xhigh; B corpus index (loader, FTS5, `read_passages`, filters, reader files, the pre-*Chatrie* switch), Sonnet high; C meaning search (paced embedding script, vectors file, in-memory search, rerank, degraded mode), Sonnet high; D Exa wrapper (T2.1 to T2.5), Sonnet xhigh; E money and state (Atlas, atomic reservation, ledger, budget stops, price table, retry wrapper, `spend_report.py`), Sonnet xhigh; F answer checks (T1.12, T2.3), Sonnet xhigh.
  - **Wave 2, after Wave 1 is merged:** G loop and composition, Opus xhigh; H API and run lifecycle, Opus high; I images and deploy script (written, never run), Sonnet high. The goodnight block stays with the main session, on the user's green light.
  - **Checks:** a Sonnet high review per builder (against its contract section; `git status` for writes outside its paths); the main session runs the tests and commits each agent's paths by name (agents never commit); one Opus xhigh review at the end of the honesty-critical paths (citation mapping, the two checks, the reservation, the heartbeat gate).
  - **Frontend:** the frontend session (P0.3), from the locked prototype against contract v1. Update `docs/sessions/frontend-brief.md` for the mock frontend when contract v1 is ready, and tell the user so they can start it.
  - **Integration:** offline suite; paid build tests (Anthropic ceiling **$3 for Phase 4**, the corpus embedding on Voyage, at most 10 Exa searches, each priced first and approved); the user reviews the prompts before their first paid run; **then the whole stack locally for the user's review** (API on 8000, web on its own port, the deploy images if Docker is available, `Probable_Clause_test`, the hard states walked through); **deploy and the first cold-start sample only after the user's sign-off and a separate green light.**
- **Subagent models (P4.1, the user's rule):** Sonnet 5.5 or Opus 5.5, effort high or xhigh only, never below high, never max, for either model. State the model and effort per agent.
- **Lock pattern (keep it):** each decision gets its own `BUILD_LOG.md` entry with a `date` heading, written with its `locked-decisions.md` entry in one commit, and the reply names the log entry (memory: log every lock visibly). Phase 4 decisions are numbered P4.n.
- **Time-writing rule:** run `date` in its own step, then write the time it printed. Never type a time in the same command that reads the clock.
- **Settled facts to build with** (details in the entries): loop on `claude-sonnet-5-5` high (P2.1), composition on `claude-opus-5-5` high (T1.8); limits 12 steps, 400K/20K tokens, 3 update searches, $10 a day, $60 a month, no per-visitor limit (P2.6, P2.7); measured runs $0.144 and $0.237 of Claude, about 30 and 45 s (findings §3); worst case reserved about $1.67 (T3.4); GCP project `probable-clause` (1066460440617), us-central1 (T3.5); Atlas databases `Probable_Clause` (live) and `Probable_Clause_test` (local and test runs) (T3.5); repo `NguyenTran2002/probable-clause`, frontend at `nguyennhattran.com/probable-clause` (P2.9).
- **The user's actions before live runs** (design note §9): a Console workspace and key with a $60 monthly limit (T3.4); how secret values reach Secret Manager (T3.5); the goodnight block on the user's green light (T3.5); the Atlas training toggle if the Voyage key is an Atlas key (T5.5, checked from the key's endpoint in Phase 4); Exa's reply or the risk accepted before launch (P1.3); sign-off on the local review, then a separate deploy green light (P4.1).
- **Observed in the Phase 2 probes, useful for the loop** (findings §1 to §3): Claude read IDs and metadata placed in each result's header; made two or three searches per turn; ran the update check unprompted; once kept and submitted in the same turn. Exa needs a text cap per result (1 MB event limit).
- **Spend so far:** Anthropic ledger $0.6964 (Phases 2 and 3, `probe_common.py`). Phase 4's ceiling is $3 (P4.1), counted separately.
- **How the corpus is built** (re-runnable, in order): `scripts/pull_courtlistener.py` (resumes from cache), `fetch_official_pdfs.py` (33 approved PDFs), `build_corpus.py` (`CORPUS_OUT=<dir>` to build elsewhere), `verify_corpus.py` (`VERIFY_OUT=<dir>`), `verify_lineup.py`, `build_manifest.py`, `filter_check.py` (done).
- **Verification record** (local, gitignored): `data/verification/text/`, `data/verification/agents/` (briefs and findings of Phase 1), `data/verification/phase2/`, `data/verification/phase3/`, `data/verification/structure/`. `docs/sessions/phase1-handoff.md` is historical.
- **Known, left as built** (P1.22 and the final pass): "supersensitive" (*Jardines*) unresolvable from the print; paragraph division inside the *Kyllo* and *Carpenter* appendices and one *Shultz* footnote; one *Ciraolo* footnote marker one character early; `lineup.json` shows no printed lineup for *White* and *Chatrie* though one is printed (verifier report only); *Kyllo*'s `header_footnotes_dropped` reads 0 for its excluded amici note.
