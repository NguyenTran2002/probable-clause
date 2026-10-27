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
- `docs/sessions/overnight-run.md`: the main session's guide for the overnight run of Oct 25, 2026 (approved plan, limits, steps, what waits for the user), kept for the record.
- `docs/design/paid-build-tests.md`: the priced plan for Phase 4's paid build tests (approved; run Oct 25, results in BUILD_LOG). `scripts/run_client.py`: the client that ran them; `scripts/render_run.py`: a saved run as a readable Markdown file. `scripts/export_replay.py`: saved runs as replay files and `replays/index.json` (contract §11.2), each run checked first.
- `docs/design/wave3-design.md`: the Wave 3 design (update step beside composition, composition on Sonnet, no reservation, looser limits), approved Oct 25, 13:47 (P4.18 to P4.22).
- `docs/sessions/wave3-plan.md`: the main session's plan for building Wave 3 (steps 0 to 6, agents, reviews, the paid tests), approved Oct 25, 13:47.
- `docs/sessions/frontend-brief.md`: the frontend session's brief. `docs/sessions/frontend-log.md`: its own append-only log (frontend session only).
- `scripts/check_env.py`: reports which secrets are set.
- `README.md` (P5.5, fact-checked) and `docs/PROMPTS.md`, written by `scripts/extract_prompts.py` from both conversations' transcripts (the frontend's two transcript IDs are named in the script).
- `scripts/probe_courtlistener.py`: one authenticated request to confirm the CourtListener token works.
- `scripts/verify_quotes.py`: re-fetches cited pages and string-matches quotes (brief §9's re-check). Cache under `data/cache/pages/`.
- Corpus pipeline (Phase 1): `scripts/pull_courtlistener.py`, `fetch_official_pdfs.py`, `build_corpus.py` (with `corpus_common.py`, `corpus_pdf.py`, `corpus_align.py`, and the reviewed `corrections.json`), `verify_corpus.py`, `verify_lineup.py`, `build_manifest.py`, `filter_check.py`. Order and purpose under "Current state and next step".
- `scripts/probe_chunking.py`: Phase 3 paid check of Anthropic's plain-text sentence chunking (T1.9). Outputs under `data/verification/phase3/`.
- `scripts/check_structure.py`: read-only check of section headings and footnote markers against every raw copy (Phase 3; Phase 1's word check skipped both). Report under `data/verification/structure/`.
- Phase 4 scripts: `scripts/check_sentences.py` (A: the splitter over every passage; report under `data/verification/sentences/`), `build_web_data.py` (B: reader files, `corpus.json`, `config.json`; `--out <dir>`), `embed_corpus.py` (C: the embedding, spends only with `--confirm`, cache under `data/cache/voyage/`), `spend_report.py` (E: read-only; `uv run --env-file .env python scripts/spend_report.py --month YYYY-MM --env test`; exit 0 read, 2 unreadable), `probe_voyage.py` (the key's endpoint, one 2-token call).
- `data/vectors/`: `voyage-law-2.f32` and `manifest.json`, committed (a0a4d1f), the main session's; regenerated only by `embed_corpus.py --confirm` with approval, and only if an embedded text changes (section labels or corpus text).
- `deploy/`: part I's images, nginx configs, `deploy.sh` (written, never run without the user's green light) and `local.sh` (the user's local review). `tests/contract/test_end_to_end.py`: the whole backend on fakes.
- `tests/fixtures/`: the main session's. `events/` (30 streams) and `http/` (19 answers) for the mock frontend and the backend tests, regenerated by `tests/fixtures/make_fixtures.py` (deterministic); `sentences/hardest.json`. `tests/contract/test_fixtures.py` checks them.
- Phase 2 paid checks: `scripts/probe_common.py` (spend ledger and ceiling, no retries), `probe_loop.py` (a simulated research loop on the corpus), `probe_exa.py` (Exa's MCP server). Outputs under `data/verification/phase2/` (gitignored).
- `data/`: `data/raw/` (raw CourtListener responses and official PDFs) and `data/cache/` (fetched pages) are gitignored and never committed; `data/corpus/` (the frozen corpus) is committed (P1.22); `data/verification/` (verification reports and agent findings) stays local.
- `web/`: the page (served as is, T4.2), the main session's from P4.28; `web/looktests/` the Phase 1 look tests and the approved prototype (P1.6, T4.1); `webdev/` the mock server and Node tests (never served); `web/_generated/` (gitignored) `build_web_data.py`'s output for local use.
- `.env.example`: the variable names; the user creates `.env`.

## Environment quirks (from the previous build)

- `uv run uvicorn` stalled in the preview tool: launch `.venv/bin/uvicorn` directly.
- `preview_start` failed with `EPERM`: serve from a background shell instead.
- The shell is **zsh, which does not split an unquoted variable.** Write `gcloud` flags out in full; never pass them through a variable.
- Claude Code transcripts live outside the repo, under `~/.claude/projects/`. `cleanupPeriodDays` stays unset at the user's direction (P0.5); don't change it.
- **CourtListener limits for the user's EDU account: 20 requests a minute, 1,000 an hour** (stated by the user, Oct 23, 2026). The API returns no rate-limit headers, so pacing is ours: about 15 a minute, serially, and cache every raw response so nothing is fetched twice.
- Some pages (SCDB, case.law, Exa's collection pages) render by JavaScript and can't be string-matched; `curl` with a browser user agent reaches courtlistener.com/terms when WebFetch gets 403.

## Two sessions in one checkout (P0.3, P1.6), retired by P4.28

**From Oct 25, 2026 (P4.28) the main session builds and owns `web/` and `webdev/`; the frontend session is retired and `docs/sessions/frontend-log.md` is the historical record. The rules below are kept for the record.**


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

**If you are the main session:** you own `web/` and `webdev/` (P4.28); log frontend work in `BUILD_LOG.md`. Before tagging a phase, check `git status` for the frontend session's uncommitted work and ask the user.

## Current state and next step

*Updated Oct 27, 2026, 11:50 CDT: the waking step unnumbered (P5.8, BUILD_LOG 11:35) and replaced by research's first step, "Claude is thinking" included (P5.9, BUILD_LOG 11:50); redeployed at `c39434b` (`probable-clause-api-00003-zhs`, `probable-clause-web-00003-c85`) and pushed (BUILD_LOG 11:59); the README's opening points to the process in one sentence and its build section is expanded (P5.7, BUILD_LOG 12:22); a cold start measured (31.5 s after 7 h 24 min idle; BUILD_LOG 11:51) and P5.6 locked: later sittings are not build time. **Pushed to GitHub** (`origin` = `github.com/NguyenTran2002/probable-clause`, `main` and the phase tags; P5.5, BUILD_LOG "Oct 26, 2026, 04:06 CDT"), with `README.md` and `docs/PROMPTS.md`. Phase 4 is closed and tagged `phase-4-done` (P4.53, 02:52). **The site is live at `https://nguyennhattran.com/probable-clause/`** (P5.1; BUILD_LOG "Oct 26, 2026, 03:06 CDT"), redeployed at commit `62d6272` for P5.4's cost note (BUILD_LOG 03:19), `PC_ENV=live`, writing to `Probable_Clause`. The first live run was the user's (03:25). Phase 5 decisions are P5.n (next: P5.10): P5.2 four replays for now, P5.3 the skipped band line as built, P5.4 the cost line's estimate note, P5.5 the README and prompts published now and the first push, P5.6 sittings after the first push are not build time, P5.7 the README's process callout (one sentence, no overnight run in it) and the expanded build section, P5.8 the waking step unnumbered, P5.9 replaced by research's first step.*

- **Live now (P5.1):**
  - **Cloud** (project `probable-clause`): `deploy/setup.sh` made the registry `probable-clause`, the service accounts `pc-api` and `pc-web`, and four secrets readable by `pc-api` alone (the Anthropic one from `ANTHROPIC_API_KEY_LIVE`). Rerunnable; a secret with an enabled version is left as it is, so changing a key means adding a version by hand, on the user's word.
  - **Services:** `probable-clause-api-00003-zhs` and `probable-clause-web-00003-c85`, from `deploy.sh` at `c39434b` (BUILD_LOG Oct 27, 11:59); before them `-00002-f67` and `-00002-jfn`, and the first deploy's `-00001-hpd` and `-00001-vl4`. A redeploy is `./deploy/deploy.sh` on a clean tree, on the user's green light.
  - **goodnight:** the `# === probable-clause ===` block in `~/Documents/Developer/framedbytran/goodnight/nginx.conf` (29983d4; CLAUDE.md note 7d62d8c; never pushed), live as `goodnight-00015-nt9`; the revision before it is `goodnight-00014-llq`. It clears `X-Forwarded-For`, `X-Real-IP` and `Forwarded`. The off switch is removing that block (P5.1).
  - **First cold-start sample** (after the deploy): 15.3 s from "Starting new instance" to ready; the app's own 11.8 s, of which "clients and the loop" is 7.4 s.
  - **First live run** (the user's, BUILD_LOG 03:30): `_o1-_Zf7-NAjvA-xR_QDZA`, answered, $0.1991; kept in `data/verification/live/` by `scripts/fetch_run.py` (reads an ended run's stored events back through the API before Atlas's 24-hour TTL).
  - **GitHub:** pushed (P5.5). Before any later push: re-export the prompts (`uv run python scripts/extract_prompts.py --flags <path outside the repo>`, then read the flag list), copy its build figures (hours, prompts, words, compactions in the build, subagents) into the README, and add a timeline row for the new sitting (brief §10.5). The build ended at commit `4ad0ea2` (P5.6): later sittings are listed in PROMPTS.md as after the build and never added to the README's build time or counts. The README never names the previous project (P5.5); nothing is pushed without the user's word, given for each push.
- **Phase 5 still to do** (brief §3), after the README went up first (P5.5): the open items below; a second long-idle sample, ideally overnight (§8.5; one was taken at 11:42, P5.6); the disconnect tests and the grace window (§8.5). Each result goes into the README's timeline and cold-start text when run, as an "after the build" row.
- **Phase 4's closing order (P4.46, BUILD_LOG "Oct 26, 2026, 01:15 CDT"), all done:**
  1. **The full test: done** (BUILD_LOG 01:26). Every suite passed and the browser sweep was clean. Since the fixes (P4.48) the whole suite is 2,959 passed and 54 skipped.
  2. **The replays: done, approved and committed (P4.50, amended by P4.52)** (BUILD_LOG 01:34, 01:35, 01:43, 01:45, 01:47; 02:33 to 02:43):
     - The four chips, in the user's order, are in `replays/` (contract §11.2), written by `scripts/export_replay.py`:
       - in order: `phone-search-arrest`, `gps-tracking-car`, `location-history-warrant`, `backyard-from-air`;
       - three were recorded at `84c0db4`, after P4.48 fixed two false-flag defects in `api/checks/`: `phone-search-arrest` at 01:45 (P4.49), the GPS and backyard questions at 01:39;
       - `location-history-warrant` ("Can police get your Google location history without a warrant?", run `bLe0Pl-WUxOnNjQWauyXmg`) was recorded at 02:36 on `a3b1dbe`, whose backend is the same. It replaced `geofence-warrants`, which was too broad for a demo (P4.52). Its first take at 02:32 is kept, not exported;
       - no replay is specific to a screen size: the page picks a replay by its slug alone.
       - All four have no flags.
     - **Approved and committed (P4.50, 01:48):** `replays/` is out of `.git/info/exclude`, and its five files are in git. Re-record a replay only deliberately, with the user (T5.6 #3).
     - Every run's events are kept in `data/verification/replays/`, the superseded first recordings included. The rendered answers are in `data/verification/replays/answers/`.
     - **P4.48's allowance:** $3.00 and 10 Exa searches, counted from the test database's $3.6735. At 02:37 the total was $5.1365, so $1.4630 and 6 searches are used; $1.5370 and 4 searches are left.
     - **Still open:** T5.6's fifth replay, the geofence question on the corpus that ends before *Chatrie*, which the user's request did not include.
  3. **The deploy: done** (P5.1, BUILD_LOG 03:06), above.
- **Replays are frontend-only (the user, 01:15), and already were.** A replay is static files on the web service (`replays/index.json`, `replays/<slug>.json`), played by the page's own code. `config.json`, `corpus.json` and `opinions/*.json` are static too. The landing's wake (`api/health`) is the only API call and a replay never waits on it. Checked at 01:15 with the web container alone and no API. Keep it that way.
- **The review's locks** (BUILD_LOG from "Oct 25, 2026, 17:50 CDT" to "Oct 26, 2026, 01:15 CDT"):
  - P4.36, the landing;
  - P4.37 and P4.38, its exit animation;
  - P4.39, the step log showing research only;
  - P4.40, "Later developments" under the answer, inked in at the run's end;
  - P4.41, the web search's wording ("update check" retired from the page);
  - P4.42, "Search opinions" and the placeholder;
  - P4.43, the palette, Evergreen deepened;
  - P4.44, the margin notes on phones;
  - P4.45, the fonts, Founding print. **Every family is named once, in `style.css`'s type tokens** (`--ui`, `--src`, `--display`, `--display-i`, `--code`, `--hand`); `fonts.css` loads the files;
  - P4.46, back to the top before the exit (`toTop()` in `main.js`, `TOP_CAP_MS` 1,500 ms measured), and the frontend finished;
  - P4.47, the former fonts removed;
  - P4.52, the third chip (02:43): the location-history question in place of the geofence question; `replays/geofence-warrants.json` is out of `replays/`, its run kept in `data/verification/replays/`;
  - P4.51, round 29 (a3b1dbe):
    - the later-developments box reordered: the overview first, under its own subheading, then the findings with the line on what this site checks;
    - the run's end scrolls only until the box's first subheading reaches the pane's bottom (`bandCap`, `capBottom()` in `view.js`), never up;
    - no scroll at all at the run's end once the visitor scrolls during the web search's wait after the answer (`leftAlone`, `webWaiting()`).
    - Testing that wait needs a replay whose web search ends after its answer, and none of the four does. At 02:16 one was retimed in the page only, at the recorded pace: a replay compressed in time bunches research's tool calls, and `pace.js`'s 3 s spacing then holds the whole run back to one burst.
- **The former fonts are removed** (P4.47, 01:18): `web/fonts/` holds only Founding print and Caveat.
- **Deferred (P5.2, P5.3):**
  - T5.6's fifth replay, the one that watches the web search find a decision the corpus lacks (*Chatrie*). Three of the four already end with the band's outcome `found` (later related activity), so brief §2's "at least one replay shows the update check finding something" is met in the letter;
  - the skipped band line's second line, left as built (P5.3). The cost line's estimates: done (P5.4).
- **Running now:** the mock (`webdev/serve.py`, 8765, started from a plain background shell) and `deploy/local.sh` (8080, `local-c648401`, rebuilt for the location-history replay (BUILD_LOG 02:40), serving the four replays now committed under P4.52; the API on 8000 with `PC_ENV=test`, the development keys and `Probable_Clause_test`). Stopping the API container makes `local.sh` remove both containers (its cleanup). Mock live runs play quietly (the fixtures' timestamps are old), so animations are checked on a replay.
- **The frontend** (BUILD_LOG "Oct 25, 2026, 16:52 CDT" and "17:50 CDT"): `web/` (the page; 16 modules; fonts and markdown-it 15.0.3 vendored), `webdev/serve.py` (the mock, `.venv/bin/python webdev/serve.py`, port 8765, switches at `/__dev/`), Node tests `node --test webdev/test/` (84). Contract v2.1 (`config.json` gains seven figures).
- **Done today since Wave 3** (BUILD_LOG 16:15 to 16:46):
  - P4.23, the prompts approved;
  - the paid tests at 16:20 ($0.5383 of $3.00, Exa 3 of 20);
  - P4.20 confirmed;
  - P4.24 to P4.32:
    - the live key `ANTHROPIC_API_KEY_LIVE`;
    - the cloud credentials;
    - goodnight's green light and location;
    - Exa's risk accepted;
    - the main session builds the frontend;
    - the local review clarified;
    - the design calls left to the main session;
    - the setup script deferred;
    - the replays.
- **Built in Wave 3** (BUILD_LOG "Oct 25, 2026, 14:17 CDT" and "16:10 CDT"):
  - contract **v2.0** and the schema (5642d5f);
  - E (46eb3e9, 5b080db), H (3a6b16e), I (83b1ab1), G (ac2c86d);
  - fixtures and contract tests (d3a0ce1);
  - the cross-part review's fixes (fe9f3c7).
  - The whole suite: **2,943 passed, 54 skipped.** The Atlas tests pass against `Probable_Clause_test` with `PC_ATLAS_TEST=1 uv run --env-file .env .venv/bin/pytest -q tests/state/test_store_atlas.py`.
- **The main session's calls to flag to the user** (in the log): `WORST_CASE_COMPOSITION_INPUT` (documented worst case only), the `update_time_limit` stop kind, `RUN_WATCHDOG_S` (2,400 s), the copy guard over every stored update-step call (accepted ones and the band's search params too), D recording a cancelled Exa search, and three risks accepted (H's `failed` ending drops research's stop kinds; spend writes sit on each branch's path; the update output budget may bind).
- **The frontend session** can now build the step log, the band's timing, the removal of `declined` and `busy` against the v2.0 fixtures (frontend brief §5a); the user tells it.
- **The user's direction for the design** is quoted in BUILD_LOG, "Oct 25, 2026, 13:31 CDT", "13:38 CDT" and "13:41 CDT"; the locks at "13:47 CDT".
- **Wave 3's agents (the user):** *"min effort is high, Sonnet 5.5 and Opus 5.5 only, no Haiku. Max effort is xhigh, no max allowed."* Agents never commit; the main session commits each part's paths by name (P4.1).
- **Done today, all logged:**
  - the paid build tests (12:29);
  - P4.16, `submit_answer` alone in its turn (12:42 and 12:48, contract v1.8);
  - P4.17, the quotation check ignoring letter case (12:55 and 12:57, contract v1.9);
  - the re-runs (13:04): one submit per run, 22 of 22 quotations found; test 4's loop used 366,680 of 370,000.
- **Closed:** the 13:04 Atlas failure of `spend_report.py` did not recur (16:10: read `Probable_Clause_test`, $1.7435 spent today).
- **Reading the answers:** `uv run python scripts/render_run.py <events.jsonl>` writes a readable file under `data/verification/phase4/answers/`.
- **Keep every run** (the user): run files are never overwritten or deleted. Atlas keeps events only 24 hours, so the local files are the only lasting copy; whether to commit them is the user's call.
- **The keys in `.env`** reach the API only through `uv run --env-file .env`; check them only with `uv run python scripts/check_env.py --phase 4`. Never open, cat, grep or print `.env` or a key (the user, 12:17). Start the API with `uv run --env-file .env .venv/bin/uvicorn api.main:app --port 8000` (`PC_ENV` unset for the test database).
- **State:** Wave 3 built (contract v2.0); see above. Phases 0 to 3 done (tag `phase-3-done`). P4.16 locked (`submit_answer` alone in its turn); P4.17 (quotations compared without regard to case). Phase 4 Waves 1 and 2 merged and reviewed, patched overnight for P4.6 to P4.10, then for P4.11 and P4.13. Decisions P0.1 to P2.12, T1.1 to T5.6 and **P4.1 to P4.53** and **P5.1 to P5.4** are locked (P4.11 to P4.15 at 12:09, P4.16 at 12:42, P4.17 at 12:55, P4.18 to P4.22 at 13:47, not yet built; the prompt drafts are approved, P4.15). `BUILD_LOG.md` is the authoritative record (P2.12). Corpus frozen: 32 cases, 102 opinions, 2,462 passages, 11,005 sentences.
- **Resume by reading:**
  - the brief;
  - `locked-decisions.md`, P4.1 to P4.22 above all (P4.18 to P4.22 amend or supersede 14 earlier entries, marked in their headings);
  - `docs/design/contract.md` (**v2.0**) and `contracts/events.schema.json`;
  - the shared code (`api/types.py`, `settings.py`, `errors.py`, `retry.py`, `protocols.py`, `api/prompts/`);
  - BUILD_LOG's entries from "22:58" (Wave 2) on;
  - `tests/fixtures/README.md`;
  - `docs/design/paid-build-tests.md` (the plan; run twice);
  - **`docs/design/wave3-design.md`** and **`docs/sessions/wave3-plan.md`** (both approved), and BUILD_LOG's entries from 12:29 on;
- **Done in Phase 4 (all logged):**
  - Step 0 and the prompts (approved 21:55).
  - **Wave 1,** A to F.
  - **Voyage:** corpus embedded (a0a4d1f).
  - **Atlas:** E's tests pass against `Probable_Clause_test`.
  - **Wave 2:**
    - I: deploy files, f5a3ca7;
    - H: API and lifecycle, ccd532e;
    - G: loop and composition, 84af0d4.
    - Each part had a Sonnet 5.5 high review. Contracts v1.2 to v1.4 hold the rulings. The end-to-end test runs on fakes (a41c500).
  - **P4.4 to P4.10 locked** (2488bac, c997778, 1d785eb).
  - **Overnight, Oct 25:**
    - **Contract v1.5** and the shared changes (8721c14): the reserve at 66,000, the run limit at 436,000, the worst case $2.106, `NOTE_MAX_CHARS`, F's note guard and corpus exemption, draft texts.
    - **The loop patch,** reviewed (4c7194b).
    - **Fixtures regenerated by driving the real backend on fakes,** with contract v1.6 adding `paid_call.estimated_usage` (a real defect in H's `interrupted` totals) and the frontend brief updated (299a640).
    - **The final Opus review's fixes** (5b71c1c): ellipsis negations and hyphenated prefixes, the copy guard's Unicode, the spend flag from `stop_kinds`.
    - **Docker:** the API image builds (427 MB) and loads offline. The web image stops at its page guard, as expected until `web/index.html` exists.
  - **The morning, Oct 25:** P4.11 to P4.15 locked (1cace11); the daily cap at $15 and the skip reason's copy guard, contract v1.7 (2685ddd).
  - **Whole suite: 3,456 passed, 49 skipped.** Nothing pushed.
- **After the paid tests, on the user's word:**
  - the frontend session on the regenerated fixtures;
  - the cloud setup questions (part I's report) and the band's wording when no search completed (T5.3);
  - the user's actions before live runs (below);
  - the local review, then a separate deploy green light (P4.1).
- **P4.1's rules:**
  - subagents Sonnet 5.5 or Opus 5.5, effort high or xhigh only, never max, with model and effort stated per agent;
  - agents never commit; the main session commits each part's paths by name;
  - no deploy before the user's local review sign-off and a separate green light.
- **Lock pattern (keep it):** each decision gets its own `BUILD_LOG.md` entry with a `date` heading, written with its `locked-decisions.md` entry in one commit, and the reply names the log entry. Phase 4 decisions were numbered P4.n (closed at P4.53); Phase 5's are P5.n (next: P5.10). Run `date` in its own step, then write the time it printed.
- **Settled facts to build with:**
  - **Models:** research and the update step `claude-sonnet-5-5` high (P2.1, P4.19); composition `claude-sonnet-5-5` high (P4.20, built).
  - **Limits (P4.18, built):** 12 research rounds; loop input 2M, loop output 16,000; update rounds 8, update input 2M, update output 6,000; 5 update searches; composition output 16,000; no run-wide limit; `MAX_CONCURRENT_RUNS` 5; `RUN_WATCHDOG_S` 2,400. **$15 a day** (P4.11), $60 a month, unchanged.
  - **No reservation (P4.21, built):** admission under the caps, spend recorded per call, at most 5 runs at once (`busy`). The documented worst case is $11.161 a run, so 5 runs could overrun a cap by about $55.81; the Console's $60 monthly limit is the outer backstop.
  - **Places:** GCP project `probable-clause` (1066460440617), us-central1; Atlas `Probable_Clause` and `Probable_Clause_test`; Voyage at `https://api.voyageai.com/v1` (platform key); repo `NguyenTran2002/probable-clause`; page at `nguyennhattran.com/probable-clause`.
- **The SDK, read from Anthropic's docs** (G's report, 23:52 and 00:46 entries):
  - adaptive thinking; `output_config.effort` "high"; a 1-hour breakpoint on the system block plus the top-level automatic one;
  - thinking display defaults to "omitted" and is billed in full;
  - the final `message_delta` usage is cumulative and authoritative;
  - spend cap: a 429 with `enforced_spend_limit_reached`; spend limit: a 400 "You have reached your specified … API usage limits".
- **The user's actions before live runs:**
  - a Console workspace and key with a $60 monthly limit (T3.4);
  - how secret values reach Secret Manager, plus the registry and service accounts (T3.5, part I's questions);
  - the goodnight block on the user's green light;
  - Exa's reply or the risk accepted (P1.3);
  - **the review of the prompt drafts** (T1.14);
  - sign-off on the local review, then a separate deploy green light (P4.1).
- **Spend so far:** Anthropic ledger $0.6964 (Phases 2 and 3); Phase 4 closed at Anthropic $1.6729 and Exa 8 searches (ledger `data/verification/phase4/spend.jsonl`); Voyage in Phase 4 about $0.078 at list price. **Wave 3's tally starts at $0** (P4.22): $3.00 of Anthropic and 20 Exa searches, ledger `data/verification/wave3/spend.jsonl`.
- **How the corpus is built** (re-runnable, in order): `scripts/pull_courtlistener.py`, `fetch_official_pdfs.py`, `build_corpus.py` (`CORPUS_OUT=<dir>`), `verify_corpus.py` (`VERIFY_OUT=<dir>`), `verify_lineup.py`, `build_manifest.py`, `filter_check.py`.
- **Known, left as built** (P1.22 and later): "supersensitive" (*Jardines*); paragraph division inside the *Kyllo* and *Carpenter* appendices and one *Shultz* footnote; one *Ciraolo* footnote marker one character early; `lineup.json`'s *White* and *Chatrie* lineups (report only); *Kyllo*'s `header_footnotes_dropped`; *Chatrie*'s "Pet. for. Cert." typo (the splitter guards against it).
