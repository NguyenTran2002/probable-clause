# Overnight run, Oct 25, 2026: the main session's own guide

*Written by the main session before a planned compaction, for itself after the compaction. The user approved this plan at about 01:00 CDT, then went to bed. This session orchestrates; subagents build and review. Work through the steps in order, report in the morning, and stop at nothing that needs the user except by queuing it.*

## The user's words
- *"I'd set you off then go to bed as it's 1:00 AM. … Get as much done as possible thru the night and report back to me."*
- *"docker builds locally are allowed since those are not risking anything. Architectural decisions are locked, so you can proceed without me."*
- The plan as presented was approved: *"Good."*

## Usage-limit wake-ups (the user's rule, absolute)
The user's usage window is a **fixed 5-hour window that resets at wall-clock times: 3:30 AM CDT on Oct 25, then 8:30 AM, 1:30 PM, and so on.** It does not reset 5 hours after a limit message. If the limit is hit, the session stops until a wake-up revives it.

**How a wake-up works.** A backgrounded `sleep` until a target time. When it exits, the harness re-invokes this session. `Monitor` can't do this, since it's capped at 30 minutes; `CronCreate` was tried and blocked. Arm one with `Bash`, `run_in_background: true`:

    T=$(date -j -f '%Y-%m-%d %H:%M:%S' '2026-10-25 03:35:00' '+%s'); sleep $((T - $(date +%s))); echo "WAKE 03:35 CDT: overnight-run wake-up; see docs/sessions/overnight-run.md, Usage-limit wake-ups"

Each one targets 5 minutes after a known reset.

**The rules:**
- **First tool call of the run:** arm the wake-ups, one for each upcoming reset: **03:35** and **08:35** on Oct 25. If the pre-compaction session armed them, they show as background tasks; don't arm duplicates.
- **Again, immediately, whenever a message says the limit is near or reached, or that you must wrap up:** arm the next one before finishing anything.
- **Never cancelled for any reason,** a system instruction to wrap up included. The one exception: when all the work set out here is finished and reported, stop any pending wake-up with `TaskStop` and don't re-arm.
- **If the reset time is ever unknown,** use the fallback `sleep 18900`: 5 h 15 min after the limit message.
- **After arming:** finish the piece in hand, commit, update "Where I stopped" (below), and stop.
- **On every wake:**
  1. First re-arm the next wake-up, 5 hours later (13:35, then 18:35, …).
  2. Renew keep-awake.
  3. Read "Where I stopped" and re-check any long jobs and background agents. Agents cut off by the limit are restarted from their brief, or resumed by SendMessage if they still answer.
  4. Prove the limit has cleared by doing real work.

  If the limit message appears again, re-arm another wake-up first. A stray wake-up that fires mid-work is routine: re-arm and carry on.
- **Never block on or ask the user anything.** Whatever needs them goes under a **"NEEDS YOU"** heading in the morning report.
- **Keep "Where I stopped" current** at every milestone (after each step's commit).
- **Long jobs** (a Docker build, the whole suite) run detached and are watched by `Monitor`, with keep-awake requested first.

## Where I stopped
*Updated at each milestone; read first on every wake.*
- 01:25 CDT, before the compaction: no step started. The wake-up method is background sleeps, at the user's direction (CronCreate was tried first and blocked). **Both wake-ups are armed** as background tasks: `b0uvgygbk` (03:35, epoch 1792917300) and `bvw4upwdo` (08:35, epoch 1792935300). Don't arm duplicates; on waking from one, arm the next 5 hours after it. The auto-mode permission check failed from about 01:10, so the user switched the session out of auto mode to arm and commit.

- 01:34 CDT: **step 1 done** (contract v1.5, settings, F's note guard and corpus exemption, drafts), committed. Next: step 2, the loop patch by an Opus 5.5 xhigh builder. Queue for the morning: at $2.106 only four reservations fit in the $10 day at once (T3.5 said about five).

- 01:38 CDT: **step 2 running**, an Opus 5.5 xhigh builder in the background (if it was cut off by the limit, restart it from the same brief: write only `api/loop/` and `tests/loop/`, P4.6 to P4.10). **Step 6 done ahead of order** (no commit needed): the API image built (427 MB), imports with `--network none`, and loads the corpus, FTS5 and vectors offline; the web image fails at guard 1 as expected (no `web/index.html`); its data stage builds (config, corpus, 102 opinions). Rebuild the API image after the merge. **Uncommitted, mine:** `docs/sessions/frontend-brief.md` (step 5, commit with step 4), a band line in `docs/design/contract.md` (commit with step 3), and `docs/design/paid-build-tests.md` (step 8, draft; Anthropic prices re-read at 01:37, unchanged).

## Standing limits (unchanged by the night)
- **No paid call of any kind:** no Anthropic, Voyage, Exa or Atlas call from this session or any agent. The new texts also await the user's review before the first paid run (T1.14).
- **No deploy, no `gcloud`, nothing to goodnight, no `git push`, no edit to `web/`** (the frontend session's).
- **Docker:**
  - local `docker build` of `deploy/api.Dockerfile` and `deploy/web.Dockerfile` is allowed (base images are pulled from Docker Hub and GHCR);
  - running a built image is allowed only with no keys and no network (`docker run --rm --network none ...`);
  - never `deploy/local.sh` (it passes the keys and reaches Atlas), never `deploy/deploy.sh`.
- **No new decision and no final wording.** Every new text is a draft for the user. A question needing the user's call is written into the morning report, and that thread stops; the other threads carry on.
- **The usual rules:**
  - never read `.env`;
  - `date` before every time written;
  - BUILD_LOG is append-only, with a commit right after each entry;
  - commit only by named paths;
  - only a fully passing suite is committed;
  - subagents are Sonnet 5.5 or Opus 5.5 at high or xhigh effort, never max, never below high, with the model and effort stated per agent.
- **Keep-awake:** call `mcp__ccd_host__request_keep_awake` with `until: "session_idle"` at the start and again each time a background agent wakes this session. The hold lapses after about 5 idle minutes.

## The recipe that worked (Waves 1 and 2)
Each builder's brief carries:
- its paths, and "writes nothing else, never commits, never reads `.env`";
- the contract sections and decisions by number, plus the BUILD_LOG entries that bind it;
- tests first;
- a **mutation check** of its honesty-critical rules;
- the final pytest command, and a report of files, summary lines, gaps as questions, and open choices.

Then:
1. a **Sonnet 5.5 high review**, read-only and adversarial, with a numbered checklist;
2. the fixes sent to the same builder by SendMessage;
3. the main session runs the tests, writes a log entry and commits by path.

The reviews found real defects every time; don't skip them.

## The steps

### 1. Shared changes, contract v1.5 (the main session, no agent)
- **`api/settings.py`:**
  - `COMPOSITION_RESERVE_INPUT` 66,000 (P4.6: the worst case is 64,945 by the loop's estimator, plus a margin);
  - `RUN_INPUT_TOKENS` 436,000 (P2.7 amended by P4.6);
  - `LOOP_INPUT_BUDGET` stays 370,000 (436,000 − 66,000);
  - a new `NOTE_MAX_CHARS` 1,000 (P4.6).
- **The worst case:** $2.106 = 0.943 + 0.08 + (66,000 × $4 + 12,000 × $20)/1M = 0.504 + 2 × 0.264 = 0.528 + 0.021 + 0.03. Update `api/state/budget.py`'s docstring and the figures asserted in `tests/state/` (`test_budget.py`, `cases.py`, `test_mongo_docs.py`, `test_rules.py`), contract §4.E and CLAUDE.md. `tests/fixtures/events/pause-and-resume.json` is regenerated in step 4.
- **A new test** in `tests/contract/` recomputes the composition's worst-case estimate from the corpus with G's own estimator:
  - the `KEEP_CAP` longest passages through `api/loop/format.document_block`;
  - reasons of `KEEP_REASON_MAX_CHARS`;
  - a question of `QUESTION_MAX_CHARS`;
  - a note of `NOTE_MAX_CHARS`;
  - `prompts.composition_system()`.

  It asserts the result is at most `COMPOSITION_RESERVE_INPUT`. The pre-compaction script gave 64,945.
- **P4.9 in F** (`api/checks/update_findings.py`, the main session as in v1.4's ellipsis fix):
  - word runs that also appear in the corpus are exempt from every copy-guard check;
  - build the corpus's `COPY_GUARD_WORDS`-grams once (with F's `_words` normalisation) and pass them in, for example `copy_guard_report(..., exempt=<frozenset>)` with a helper `corpus_grams(texts, n)`;
  - **P4.8:** add the `note` to `copy_guard_report` (`note_flagged`, and a problem naming "the note" and the page ID, never quoting it);
  - tests, plus a mutation check by hand.
- **The schema:** `submit.rule` gains `note_too_long`. A note refused by the copy guard uses rule `copy_guard`.
- **Draft texts** in `api/prompts/rejections.json` (`submit`), noted as drafts in `_about`:
  - `note_too_long`: "Not accepted: the note is <length> characters; at most {{NOTE_MAX_CHARS}} are allowed. Shorten it, then submit again."
  - `copy_guard_note`: "Not accepted: the note repeats {{COPY_GUARD_WORDS}} or more consecutive words of <id>. Rewrite it in your own words, then submit again."

  `tests/contract/test_prompts.py` must pass.
- **Contract v1.5** (header, §4.E, §4.F, §4.G, §6): P4.6 to P4.10. A withheld note uses P4.3's same text: "[statement withheld: it repeated a page's words]".
- Run the whole suite, write a log entry and commit.

### 2. The loop patch (one builder, Opus 5.5 xhigh; writes only `api/loop/` and `tests/loop/`)
- **P4.6:** the note cap with `note_too_long`. Make the composition-input estimate check an error log rather than a warning (it should be unreachable now), and test that the worst case fits.
- **P4.7:** rule 4 is waived when `out_of_scope` is true. Test "hello" submitted as out of scope with no skip reason: accepted at once, `update_band` outcome `not_run`, and no reminder.
- **P4.8:**
  - on a no-sources submit (out of scope, or nothing kept with a note) with any page returned in the run, call `copy_guard_report` with the note;
  - a hit refuses with `copy_guard_note`, rule `copy_guard`;
  - the stored `tool_call` withholds the note (P4.3's text).
  - The scope note of an answered run, keep reasons and `update_skip_reason` are **not** guarded.
- **P4.9:** pass the corpus's grams, built once per `Corpus` (a weak-keyed cache, like `chars_per_token`), to every copy-guard call. Test a statement quoting the Court that a page also quotes: it is accepted.
- **P4.10:** a composition attempt broken before its first block is already counted from the streamed characters (G's v1.3 fix 4). Verify it, and test that the retry still happens and the ceiling isn't spent.
- The final command: `.venv/bin/pytest -q tests/loop tests/contract`.

### 3. Review and merge
- A Sonnet 5.5 high review of steps 1 and 2 (`api/loop/`, `api/checks/update_findings.py`, the settings, the prompts, the schema).
- Fixes by the builder. The whole suite, a log entry, a commit.

### 4. Fixtures regenerated from the real code (one builder, Opus 5.5 high; writes only `tests/fixtures/`)
- **Rewrite `tests/fixtures/make_fixtures.py`** to produce each stream by driving G's real `execute_run` through H's real `Run`/app on fakes, as `tests/contract/test_end_to_end.py` does: `FakeAnthropic` scripts, `FakeVoyageClient`, `FakeExaTransport`, `MemoryStore`, and H's `FakeClock` from `tests/server/support.py`. The tool-result text is then the real formatter's.
- **Deterministic:** fixed run IDs and a fixed clock, so a rerun is byte-identical.
- **Keep all 30 event streams and 19 HTTP answers** with the same file names and README rows, plus new streams for:
  - out of scope with no update check (P4.7);
  - a note refused by the copy guard (P4.8);
  - a note too long (P4.6).
- Where a state can't be produced through the real code (`interrupted` comes from H's instance path), say how it was made.
- `tests/contract/test_fixtures.py` must pass unchanged, except where v1.4 or v1.5 rules require otherwise; the builder reports each such change.
- After the merge, the main session removes H's `stop_kinds` fill-in in `tests/server/` (see the 00:34-era note in H's report: the exact-match test fills `stop_kinds: []` into `interrupted-run.json`).
- A log entry and a commit.

### 5. The frontend brief (the main session)
Update `docs/sessions/frontend-brief.md` §5 for contract v1.2 to v1.5:
- unknown error codes shown as T5.4's general failure;
- `stop_kinds`;
- the `submit.rule` values (`no_note`, `note_too_long`, null for bad input);
- withholding on any refused submit, the note included;
- the `answer_end` pairings;
- the `failure_reason` `internal`;
- `answer_chars` on H's endings;
- the note cap.

Add a line saying the fixtures were regenerated from the real code. If `docs/sessions/frontend-log.md` has new entries, fold them in. A log entry and a commit.

### 6. Docker builds (the main session)
- `docker build -f deploy/api.Dockerfile -t pc-api:local .`, then `docker run --rm --network none pc-api:local python -c "import api.main"` (no keys, no network; the FTS5 check runs at build).
- `docker build -f deploy/web.Dockerfile -t pc-web:local .` is **expected to fail at the page guard**, since `web/index.html` doesn't exist yet. Confirm it fails there and for that reason, not elsewhere.
- Report the image sizes. Never run `local.sh`.

### 7. The final verification review (one reviewer, Opus 5.5 xhigh, read-only)
- **The patched paths:** the note cap, rule 4, the note guard and withholding, the corpus exemption (could it let a real page copy through?), the composition counting, the worst case.
- **The regenerated fixtures** against the schema and the real code.
- **Anything in the v1.4 fixes** worth re-checking.
- Fix clear defects that the locked decisions already cover, then review, test and commit them. Queue everything else.

### 8. For the morning
- **A priced plan for the paid build tests**, in `docs/design/paid-build-tests.md`, for the user's approval:
  - the Phase 4 Anthropic ceiling is $3, and Exa is limited to 10 searches;
  - measured Phase 2 runs cost $0.144 and $0.237 of Claude;
  - re-read Anthropic's pricing page first and record the date (contract §10);
  - each test gets its purpose, its expected cost, and what it checks: the citation mapping-fault count, real thinking blocks passed back, the cache classes, the spend markers, an out-of-scope reply, a nothing-found reply, an update search;
  - the user's actions before live runs (CLAUDE.md).
- **CLAUDE.md's "Current state and next step"** updated, and a log entry for the night.
- **The morning report:** the closing message, with what was done and its commits, what's waiting on the user and why, the spend ($0), and the token use. A `PushNotification`, if the tool is available, when the night's work ends.

## Waiting on the user (don't decide these)
- **Their review of the prompt drafts:**
  - the five texts from 23:52 (`unknown_tool`, the two accepted-submit texts, `composition_scope_note`, `composition_coverage`);
  - `out_of_scope_no_note`;
  - tonight's `note_too_long` and `copy_guard_note`;
  - the unused `rejections.json` texts (`update_search.*`, `findings_problem.*`), which D's and F's own messages replace.
- **The band's wording when no search completed:** the outcome is `nothing_relevant` by §6, but the page could word it from `searches[].status` (the cross-part review's finding 7, wording under T5.3).
- **The cloud setup** from part I's report: the registry, the service accounts, the secrets and their values; the web service's resource settings; `--scaling=auto` beside `--min` and `--max` (check `gcloud run deploy --help` offline only on the user's word, since gcloud is off-limits tonight).
- **The paid build tests' approval.**
- **Before live runs:** the Console workspace and key with a $60 limit, the secrets, the goodnight block, Exa's reply or the risk accepted, the local review sign-off, then a separate deploy green light.
- **The frontend session:** the user may start it on the regenerated fixtures.
