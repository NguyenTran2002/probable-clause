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
- Phase 4 scripts: `scripts/check_sentences.py` (A: the splitter over every passage; report under `data/verification/sentences/`), `build_web_data.py` (B: reader files, `corpus.json`, `config.json`; `--out <dir>`), `embed_corpus.py` (C: the embedding, spends only with `--confirm`, cache under `data/cache/voyage/`), `spend_report.py` (E: read-only; `uv run --env-file .env python scripts/spend_report.py --open-reservations`; exit 1 open, 2 unreadable), `probe_voyage.py` (the key's endpoint, one 2-token call).
- `data/vectors/`: `voyage-law-2.f32` and `manifest.json`, committed (a0a4d1f), the main session's; regenerated only by `embed_corpus.py --confirm` with approval, and only if an embedded text changes (section labels or corpus text).
- `tests/fixtures/`: the main session's. `events/` (30 streams) and `http/` (19 answers) for the mock frontend and the backend tests, regenerated by `tests/fixtures/make_fixtures.py` (deterministic); `sentences/hardest.json`. `tests/contract/test_fixtures.py` checks them.
- Phase 2 paid checks: `scripts/probe_common.py` (spend ledger and ceiling, no retries), `probe_loop.py` (a simulated research loop on the corpus), `probe_exa.py` (Exa's MCP server). Outputs under `data/verification/phase2/` (gitignored).
- `data/`: `data/raw/` (raw CourtListener responses and official PDFs) and `data/cache/` (fetched pages) are gitignored and never committed; `data/corpus/` (the frozen corpus) is committed (P1.22); `data/verification/` (verification reports and agent findings) stays local.
- `web/`: the frontend session's page (served as is, T4.2); `web/looktests/` its Phase 1 look tests (P1.6); `webdev/` its mock server and Node tests (never served); `web/_generated/` (gitignored) `build_web_data.py`'s output for local use.
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

*Updated Oct 24, 2026, 22:51 CDT, before a planned compaction; Wave 2 next.*

- **State:** Phases 0 to 3 done (tag `phase-3-done`). Decisions P0.1 to P2.12, T1.1 to T5.6 and P4.1 to P4.3 are locked in `docs/design/locked-decisions.md`; `BUILD_LOG.md` is the authoritative record (P2.12). Architecture in summary: `docs/design/design-note.md` (approved). Corpus frozen and committed: `data/corpus/` (32 cases, 102 opinions, 599,096 tokens, 2,462 passages, 11,005 sentences); text changes only through `scripts/corrections.json` (P1.21).
- **Resume by reading:** the brief in full; `locked-decisions.md` in full; `design-note.md`; **`docs/design/contract.md` in full (v1.1)** and `contracts/events.schema.json`; the main session's shared code (`api/types.py`, `settings.py`, `errors.py`, `retry.py`, `protocols.py`, `api/prompts/`); the Phase 4 entries of `BUILD_LOG.md` from 21:12 on (each part's merge entry lists its rulings); `tests/fixtures/README.md`. Say in one line where you are resuming.
- **Done in Phase 4 (all logged):**
  - Step 0: scaffold, T1.5, contract v1 (Opus xhigh review), P4.2, P4.3; **prompt drafts approved by the user** (21:55, *"I checked the prompts. They are good to go."*).
  - **Wave 1 merged:** A splitter ba250cb, B corpus index 826d9ea, C meaning search 0b80bf6, D update check 611eb79, E money and state c70156e, F answer checks 7d87bee. Each had a Sonnet 5.5 high review; the reviews found real defects (F's false passes, E's T3.7 denylist and host names in error chains), all fixed. Contract v1.1 holds the main session's rulings.
  - **Voyage:** platform key (`scripts/probe_voyage.py`), list prices confirmed from Voyage's page, `rerank-3` confirmed by the user, a throwaway end-to-end run and a rerank comparison (10 of 12 positions reordered); **corpus embedded** (a0a4d1f, 524,853 tokens, $0.0630).
  - **Atlas:** E's 40 Atlas tests pass against `Probable_Clause_test` (22:09), nothing left behind (run: `PC_ATLAS_TEST=1 uv run --frozen --env-file .env pytest -q tests/state/test_store_atlas.py`).
  - **Fixtures** (5dd4d15) and the **frontend brief** rewritten (f6d70f6): the user can start the frontend session for the real page against the mock; it writes `web/` and `webdev/`.
  - Whole suite: **2,907 passed, 47 skipped**. Tree clean; nothing pushed.
- **Next: Wave 2, on the user's go** (the user: *"We'll compact before wave 2. Prep the ground first."*). Three background builders in one message (contract §13): **G** loop and composition, **Opus 5.5 xhigh**; **H** API and run lifecycle, **Opus 5.5 high**; **I** images and deploy scripts, **Sonnet 5.5 high**. G and H depend on each other only through `RunContext` (`api/types.py`) and `execute_run`'s signature: H tests with a fake `execute_run`, G tests with a fake `RunContext`; neither waits on the other.
  - **Each brief (the Wave 1 recipe, which worked):** its contract part plus §1, §2, §6, §13 by section; the decisions it implements by number; its exact paths (writes nothing else; never commits; never reads `.env`; no network except reading public docs with WebFetch where named; no paid call; no `uv add`; no database server); tests first; a mutation check of its own honesty-critical logic; run `.venv/bin/pytest -q tests/<area> tests/contract` and report results, files, every contract gap as a question, and every choice the contract left open. Then a Sonnet 5.5 high review per part (adversarial, read-only), fixes by the builder via SendMessage, the main session runs the tests, commits that part's paths by name with a log entry.
  - **G's brief also carries:** read Anthropic's docs (WebFetch) for streaming with the SDK, custom content documents with citations (`content_block_location`), adaptive thinking and the effort setting, prompt caching with a one-hour breakpoint, and how the usage tier's spend-cap 429 and the Console spend-limit 400 are told apart (cite in a comment, contract §2); prompts from `api/prompts/` with `{{SETTING}}` / `{{corpus field}}` / `<per call>` filling (`tests/contract/test_prompts.py`); failed Claude attempts recorded with `api.state.prices.failed_attempt_usage(service, model, estimated_input_tokens)`; `copy_guard_report` and P4.3's withholding of `flagged_statements` in the stored `tool_call`; D's `schema_check()` on the instance's first update search; D's `params_as_dict`/`fixed_settings` for the band, `returned = len(pages) + len(repeats)`, `seen_urls` keys are normalised URLs; prices by the requested model ID (exact match); F's checks run off the event loop; the passage header writes "per curiam" when `authors` is empty and `joined_by_source` says so; the fixtures' event shapes are the target (G's real tool-result text replaces the fixtures' approximate text, and the main session then regenerates the fixtures from G's formatter).
  - **H's brief also carries:** run records exactly in the shape of `api/state/records.py`'s docstring (allowlisted); run IDs matching `[A-Za-z0-9_-]{1,128}` (e.g. `secrets.token_urlsafe(16)`); never log a store exception chain; `Store` per `api/protocols.py` (no `count_run_started`: `reserve` counts the start); `/health` from `store.live_status`; `PC_ENV`, `PC_CORPUS=before_chatrie` refused when live, `PC_COMMIT`; the HTTP fixtures in `tests/fixtures/http/` are the target answers.
  - **I's brief also carries:** written, never run; the Cloud Run block of `api/settings.py`; `deploy.sh` runs `spend_report.py --open-reservations` first and stops on exit 1 or 2; `local.sh` for the user's local review (API 8000 with `PC_ENV=test`, web 8080 proxying `/api/`); nginx written from scratch (no goodnight code), `Cache-Control: no-cache`; the web image serves `web/` (not `webdev/`, not `web/_generated/`, generating its own with `build_web_data.py`), `replays/`, `web/fonts/`.
  - **After Wave 2:** merge, the whole suite, one Opus 5.5 xhigh review of the honesty-critical paths (citation mapping, the two checks, the reservation, the heartbeat gate); regenerate the fixtures from G's formatter; paid build tests (Anthropic ceiling **$3 for Phase 4**, each priced first and approved; at most 10 Exa searches); then the whole stack locally for the user's review; deploy only after the user's sign-off and a separate green light.
- **P4.1's rules:** subagents Sonnet 5.5 or Opus 5.5, effort high or xhigh only, never below high, never max; state model and effort per agent. Agents never commit; the main session commits each part's paths by name. No deploy before the user's local review sign-off and a separate green light.
- **Lock pattern (keep it):** each decision gets its own `BUILD_LOG.md` entry with a `date` heading, written with its `locked-decisions.md` entry in one commit, and the reply names the log entry. Phase 4 decisions are numbered P4.n (next: P4.4). Approvals and checks the user asks for get a log entry with the user's words on the DECISION line. Time-writing rule: run `date` in its own step, then write the time it printed.
- **Settled facts to build with:** loop `claude-sonnet-5-5` high (P2.1), composition `claude-opus-5-5` high (T1.8); limits 12 steps, 400K/20K tokens, 3 update searches, $10 a day, $60 a month (P2.6, P2.7); worst case reserved $1.674 (T3.4, asserted by test); measured Phase 2 runs $0.144 and $0.237 of Claude, about 30 and 45 s; GCP project `probable-clause` (1066460440617), us-central1 (T3.5); Atlas `Probable_Clause` (live) and `Probable_Clause_test`; Voyage at `https://api.voyageai.com/v1`; repo `NguyenTran2002/probable-clause`, page at `nguyennhattran.com/probable-clause` (P2.9).
- **The user's actions before live runs** (design note §9): a Console workspace and key with a $60 monthly limit (T3.4); how secret values reach Secret Manager (T3.5); the goodnight block on the user's green light (T3.5); Exa's reply or the risk accepted (P1.3); sign-off on the local review, then a separate deploy green light (P4.1). (The Atlas training toggle is not needed: the Voyage key is a platform key.)
- **Spend so far:** Anthropic ledger $0.6964 (Phases 2 and 3); Phase 4 Anthropic $0 of its $3 ceiling. Voyage in Phase 4 about $0.0635 at list price (likely within free tokens). Exa in Phase 4: none of its 10 searches.
- **Observed in the Phase 2 probes, useful for G** (findings §1 to §3): Claude read IDs and metadata placed in each result's header; made two or three searches per turn; ran the update check unprompted; once kept and submitted in the same turn. Exa needs a text cap per result (1 MB event limit).
- **How the corpus is built** (re-runnable, in order): `scripts/pull_courtlistener.py`, `fetch_official_pdfs.py`, `build_corpus.py` (`CORPUS_OUT=<dir>`), `verify_corpus.py` (`VERIFY_OUT=<dir>`), `verify_lineup.py`, `build_manifest.py`, `filter_check.py`. Verification record (local, gitignored) under `data/verification/`.
- **Known, left as built** (P1.22 and later): "supersensitive" (*Jardines*); paragraph division inside the *Kyllo* and *Carpenter* appendices and one *Shultz* footnote; one *Ciraolo* footnote marker one character early; `lineup.json`'s *White* and *Chatrie* lineups (report only); *Kyllo*'s `header_footnotes_dropped`; *Chatrie*'s "Pet. for. Cert." typo (the splitter guards against it).
