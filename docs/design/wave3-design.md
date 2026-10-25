# Wave 3 design: research, then update and composition side by side

*Drafted Oct 25, 2026 by the main session for the user's approval, after the paid build tests and their re-runs (BUILD_LOG, 12:29 and 13:04). Nothing here is locked. On approval each numbered decision below is locked in its own BUILD_LOG entry with its `locked-decisions.md` entry, and contract v2.0 is written before any builder starts. Where this draft and a locked entry differ, the entry wins until the new one is locked.*

*Marked **(user)** where the user decided it in discussion, **(main session)** where it is the main session's call for the user to check.*

## 1. Why

The paid runs showed three things:
- **The loop's input budget is the one limit that binds.** Test 4's re-run used 366,680 of 370,000 tokens in 8 rounds, partly because each web search's pages ride along in every later round.
- **The update check is tangled into research.** It shares `submit_answer` with the answer, so rule 4, the skip reason, the copy guard on the note and the findings checks all sit in one submit. P4.16 was the latest patch for that tangle.
- **The reservation adds friction for little gain.** One run holds $2.11 of the day, soon $3 to $4 with looser limits, so only 3 or 4 runs fit at once. The settle, release and expiry logic is a whole subsystem, and the open-reservation check couldn't reach Atlas after the re-runs.

The aim **(user)**: every normal run passes smoothly. Each limit is a backstop that fires only when something has gone badly wrong. The daily cap ($15) and monthly cap ($60) stand.

## 2. A run, end to end

1. **Admission.** `POST /runs` admits the run if all of these hold: today's spend is under the daily cap, the month's is under the monthly cap, the Anthropic spend-limit flag is clear, and fewer than `MAX_CONCURRENT_RUNS` runs are in progress. Nothing is reserved. If Atlas can't be reached, the run is refused, as today (fail closed).
2. **Research** (Sonnet 5.5, high effort): the loop as today, without the update check. It may use `search_meaning`, `search_exact`, `read_passages`, `keep_passages` and `submit_answer(out_of_scope, note?)`; the two update tools are in its list (for the shared cache) but refused until it submits.
3. **When research is accepted, two branches start at once:**
   - **The update step** (Sonnet 5.5, high effort): the research conversation continued, reading its cache, with its own limits and only `search_web_updates` and `submit_update` allowed. It decides whether to search. It ends with its findings, an overview, or a reason for skipping.
   - **Composition** (Sonnet 5.5, high effort): unchanged except for the model. Only the kept passages go in as sources, uncached.
4. **The checks** run on the answer when it finishes; **the band** is built from the update step's submit.
5. **`run_ended`** is sent when both branches are done.

**When the update step runs** **(user)**: our code turns it off when research never searched the corpus, which means an out-of-scope reply (rule 2 requires a search otherwise). Then the band is `not_run` and no update call is made.
- When research searched but kept nothing (a "nothing found" reply), the update step **does** run, since the web may report a decision the corpus lacks (test 3). Composition doesn't run, because nothing was kept.
- When Exa is marked out of credit or its key is refused, the update step isn't started either (no Claude call), and the band is `unavailable`, as today.

## 3. The decisions to lock

### P4.18 Looser limits (user)

| Setting | Now | New | Basis |
|---|---|---|---|
| `LOOP_INPUT_BUDGET` | 370,000 | **2,000,000** (user) | test 4 used 366,680 in 8 rounds |
| `LOOP_OUTPUT_BUDGET` | 8,000 | 16,000 | 4,574 seen (57%) |
| `COMPOSITION_MAX_TOKENS` | 12,000 | 16,000 | 5,481 seen (46%); a cut-off answer is the worst failure a visitor sees |
| `UPDATE_SEARCHES_PER_RUN` | 3 | 5 | 3 of 3 used once |
| `MAX_ROUNDS` | 12 | 12, unchanged | 8 seen; 12 is the graceful stop |
| `KEEP_CAP` | 40 | 40, unchanged | 27 seen |
| Deadlines (run 600 s, loop call 120 s, composition call 300 s) | | unchanged | 17%, 18%, 14% used |

**What `LOOP_INPUT_BUDGET` measures:** input tokens only (uncached, cache writes and cache reads), summed over every research call in the run. The loop checks it before each round against an estimate of the next call. Output has its own budget. It isn't the model's context window: one call holds at most about 70k to 150k tokens, while the budget adds up every call.
- **What research alone uses**, with the web pages moved out: about 690k for 12 rounds at test 4's pace (each round adds about 7k).
- **At 800k:** the round limit nearly always binds first.
- **At 2M:** it binds only in a runaway, such as a bug that keeps growing the conversation.
- **The catastrophic cost of research's input** (every token billed as a fresh 5-minute write): $2.02 at 800k, $5.02 at 2M.

`RUN_INPUT_TOKENS`, `RUN_OUTPUT_TOKENS`, `COMPOSITION_RESERVE_INPUT` and `FIXED_PREFIX_TOKENS_ESTIMATE` are removed. They existed so the loop left room for the composition inside one run-wide limit, and to price the reservation. Each step now has its own limits (§4).

### P4.19 The update check leaves the research loop and continues its conversation (user; the mechanics are the main session's)

- **Research's `submit_answer`** keeps `out_of_scope` and `note`. It loses `update_skip_reason`, `update_findings` and `update_overview`.
  - Its rules become: rule 1 (alone in its turn and sent once, P4.16), rule 2 (a corpus search unless out of scope), rule 3 (nothing kept needs a note), `no_note` (out of scope needs a note), and the note cap.
  - **Rule 4 goes**, and with it P4.7's waiver and the reminder logic.
  - **The copy guard on the note goes** (P4.8, P4.13 for the note). Research no longer sees any web page, so it can't copy one.
- **The update step** **(main session)**:
  - **Its input (user): the research conversation itself, for its cache.** *"Update step's input should take advantage of the cached research conversation at maximum. We're just separating them so that we have finer control."* The update step's first call is the research conversation as it stands, then the accepted `submit_answer`'s result, carrying the update step's instructions as a user turn. Every update call after that adds to the same conversation.
    - **What sharing the cache needs** (main session): a cache entry is reused only when everything before it is identical: the tool list, then the system prompt, then the messages. So:
      - **One tool list for both steps:** research and the update step both send all seven tools. Our code refuses `search_web_updates` and `submit_update` during research ("the update step comes after you submit"), and the four research tools and `submit_answer` during the update step ("research is finished").
      - **One system prompt for both:** `loop_system.md` describes both steps, so the update guidance moves into a short section of it rather than a separate file.
      - The update step's first call then reads the whole research conversation from cache at $0.10 per million tokens. Only the instructions turn and each search's pages are new.
    - **The 1-hour breakpoint stays on the system prompt;** the automatic 5-minute one covers the growing conversation in both steps, as today.
    - **Research still never sees a web page:** pages arrive only in the update step, after research has ended, so dropping the copy guard on research's note stays sound.
  - **Its tools:** `search_web_updates` (at most 5 a run, unchanged inside) and `submit_update(update_findings?, update_overview?, update_skip_reason?)`.
  - **Its rules:**
    - `same_turn`, as P4.16;
    - `no_check`: refused when no search ran and no skip reason was given (this replaces rule 4, with no reminder state);
    - the findings checks (T2.3);
    - the copy guard on statements, overview and skip reason (P4.3, P4.13, with P4.9's corpus exemption).
  - **Its limits:** `UPDATE_MAX_ROUNDS` 8, `UPDATE_OUTPUT_BUDGET` 6,000, and `UPDATE_INPUT_BUDGET` **2,000,000** (user). Because every update call re-sends the research conversation, its input budget must be sized like research's:
    - **typical:** research ends near 50k tokens, 2 searches, 3 update calls: about 180k;
    - **the heaviest plausible:** research ends near 150k (12 rounds), 5 searches of about 10k tokens of pages each, 6 calls: about 1.06M;
    - **1.2M** covers that heaviest case; **2M** matches research and fires only in a runaway.
    - **Real cost stays small:** most of that input is a cache read. A typical update step costs about $0.05 to $0.10, mostly the pages' first write and its output.
  - **Retries** as for research (T3.3).
  - **If it fails or hits a limit,** the band shows `not_summarised` when a search ran, else `unavailable` with the error, and the answer isn't touched.
- **The band's outcomes:**
  - `found`, `nothing_relevant`, `skipped`, `unavailable` and `not_summarised` stay;
  - `not_run` now means out of scope, or the run ended before the update step started;
  - **`declined` goes**: with no rule 4 there is nothing to decline.
- **The research loop's status line** loses "update searches n of 3". The update step has its own.

### P4.20 Composition on Sonnet 5.5 at high effort (user)

- `COMPOSITION_MODEL` becomes `claude-sonnet-5-5`, with high effort.
- Everything else about the composition stands (T1.9, T1.11): only kept passages as custom-content sources, the scope note, keep reasons in `context`, no tools, uncached **(user)**, the approved system prompt.
- The user judges the answers' quality in the next paid runs, with no comparison run first **(user)**: *"this project is a tech demo of the citation feature."*
- **Expected saving:** composition output costs half (Sonnet's $10 per million tokens against Opus's $20) and so does its input ($2 against $4). That's about a fifth of an answered run's cost: test 4's re-run would drop from $0.40 to about $0.30.

### P4.21 No reservation: admission, spend recorded per call, a cap on runs at once (user; the conditions are the main session's)

- **Admission:**
  - a run is admitted only while today's spend is under `DAILY_CAP_USD` and the month's is under `MONTHLY_CAP_USD`, the spend-limit flag is clear, and fewer than `MAX_CONCURRENT_RUNS` runs are in progress;
  - otherwise it's refused with today's codes (`daily_cap`, `monthly_cap`, `spend_limit_paused`, `atlas_unreachable`) or a new `busy`.
- **Spend recorded as it happens:** each paid call's cost is added atomically to the day's and month's totals when the call ends. A crash then loses at most one call's figure.
- **Runs in progress always finish.** A run is never stopped because the day's cap was passed during it. **(user)** *"I'm willing to trade more cost overrun here."*
- **The bound on overrun:** at most `MAX_CONCURRENT_RUNS` runs can be in progress when the cap is reached.
  - **Typical:** 5 runs × about $0.40, so under $2 past the cap.
  - **Catastrophic** (every input token billed as a fresh 5-minute write, every limit reached; research 2M, composition three attempts, Exa and Voyage at their bounds):
    - with `UPDATE_INPUT_BUDGET` 1.2M: research $5.18, update $3.06, composition $0.56, Exa and Voyage $0.07, about **$8.87 a run**, so about **$44** for 5 runs;
    - with `UPDATE_INPUT_BUDGET` 2M (**chosen by the user**): about **$10.87 a run**, so about **$54** for 5 runs.
  - **The outer backstop:** Anthropic's Console limit on the live workspace ($60 a month, T3.4), outside our code. At 2M the catastrophic overrun comes close to it.
- **`MAX_CONCURRENT_RUNS` = 5** **(user)**. A run is one visitor's question being researched and answered, from `POST /runs` to `run_ended`. Each run makes its own paid calls; a sixth visitor asking while five runs are in progress is refused with `busy`. It's one instance's registry count. Cloud Run's API service is `max 1` (T3.5), so one count covers the service.
- **What goes:**
  - `reserve`, `settle` and `release`, and reservation expiry;
  - `--open-reservations` in `spend_report.py` and its use in `deploy.sh`;
  - the worst-case formula as an admission gate. It's kept only as a documented figure, tested, for the overrun bound above;
  - P4.12 (spend past the reservation) and P4.14 (the composition's worst case by the estimator) have nothing left to govern;
  - `/health`'s `live_research` is worked out from spend against the caps (`paused_day` at or over the daily cap, `paused_month` at or over the monthly cap).
- **What stays:** the caps and their stops recorded (P2.7, P4.11), the spend-limit flag and pause (T3.4), the run records, `Probable_Clause_test` for tests.

## 4. Settings after Wave 3

- **Kept:** `MAX_ROUNDS` 12; `KEEP_CAP` 40; `DAILY_CAP_USD` 15; `MONTHLY_CAP_USD` 60; the deadlines; `VOYAGE_RUN_BOUND_USD`; the note and finding caps.
- **Changed:** `LOOP_INPUT_BUDGET` 2,000,000; `LOOP_OUTPUT_BUDGET` 16,000; `COMPOSITION_MODEL` `claude-sonnet-5-5`; `COMPOSITION_MAX_TOKENS` 16,000; `UPDATE_SEARCHES_PER_RUN` 5.
- **New:** `UPDATE_MODEL` `claude-sonnet-5-5` and `UPDATE_EFFORT` `high`; `UPDATE_MAX_ROUNDS` 8; `UPDATE_INPUT_BUDGET` 2,000,000; `UPDATE_OUTPUT_BUDGET` 6,000; `MAX_CONCURRENT_RUNS` 5.
- **Removed:** `RUN_INPUT_TOKENS`, `RUN_OUTPUT_TOKENS`, `COMPOSITION_RESERVE_INPUT`, `FIXED_PREFIX_TOKENS_ESTIMATE` (and the reservation's settings, if any are left after E's change).

## 5. Events and the page (contract v2.0)

The events stay one numbered stream per run. The two branches' events interleave in the order they happen. The page has to place them by their step, not by position.

- **A `step` field** (`research`, `update`, `composition`) on `round_started`, `tool_call`, `tool_result`, `paid_call` and `api_fragment`. `paid_call.purpose` gains `update`.
- **New `update_started` and `update_ended`.**
  - `update_started` marks the branch's start, with the kept IDs research ended with.
  - `update_ended` carries the step's own stop kind, if any.
  - `update_band` stays the band's single summary, sent when the update step ends (or at once when it's turned off).
- **`run_started.limits`:** `rounds`, `loop_input_tokens`, `loop_output_tokens`, `update_searches`, `update_rounds`, `composition_max_tokens`. The old run-wide token fields go.
- **`run_ended`:** unchanged fields.
  - `stop_kinds` gains the update step's stops (`update_step_limit`, `update_token_ceiling_input`, `update_token_ceiling_output`). They never change the run's `state`, which comes from research and the composition.
  - `totals.claude.cost_usd` gains `update`.
- **`submit.rule`:**
  - on `submit_answer`: `same_turn`, `no_search`, `nothing_kept`, `no_note`, `note_too_long`, or null;
  - on `submit_update`: `same_turn`, `no_check`, `findings`, `copy_guard`, or null;
  - `no_update_check` goes.
- **Refusals at `POST /runs`** (the API's messages; the user asked the main session to write them, and the page's own lines follow T5.4):
  - **`busy`** (503, new): *"Five questions are being researched right now, the most this site handles at once. Please try again in a minute."* The number follows `MAX_CONCURRENT_RUNS`.
  - **`daily_cap`**, reworded since nothing is reserved: *"Today's spending has reached the daily cap, so no new question can start until midnight, Central Time."*
  - **`monthly_cap`**, likewise: *"This month's spending has reached the monthly cap, so no new question can start until the 1st."*
  - `spend_limit_paused` and `atlas_unreachable` stay as they are.
- **The frontend session:**
  - **must wait for the new fixtures** for the step log (two lanes, or the update steps grouped after research), the band's timing, `declined`'s removal and the `busy` refusal;
  - **may go on** with everything else: sources, the answer, citations, the reader, checks and replays.

## 6. Prompts (the main session drafts; the user approves before the first paid run, T1.14)

- **`loop_system.md`** (shared by both steps, for the cache): the research items lose the update check; the "Submitting" item loses the update fields; a new short section describes the update step that follows a submit (its purpose, the window advice, the findings rules, when to skip, and "describe, never evaluate"); the research status line loses the update count.
- **`tools.json`:**
  - `submit_answer` loses the update fields, and its description loses "the update check run or skipped";
  - one tool list of seven for both steps: `search_web_updates` and the new `submit_update` are added, each description saying which step may use it.
- **`loop_messages.json`:** a new `update_start` message, the accepted submit's result that opens the update step; `submit_accepted_*` texts adjusted; the update step's status line.
- **`rejections.json`:**
  - `rule_4_no_update_check`, `copy_guard_note` and research's findings texts go;
  - `submit_update.no_check` and the two wrong-step refusals are new;
  - the copy-guard texts move under `submit_update`.
- **`composition_system.md`:** unchanged. The model changes; the user judges the result.

## 7. Wave 3: who builds what (P4.1's rules: Sonnet 5.5 or Opus 5.5, effort high or xhigh, never max, no Haiku; agents never commit; model and effort stated per agent)

1. **The main session first:**
   - lock P4.18 to P4.21;
   - write contract v2.0, `events.schema.json`, `api/settings.py`, `api/protocols.py` and `api/types.py`;
   - draft the prompts for the user's review;
   - update the frontend brief.
2. **Wave 3a, in parallel** (independent folders):
   - **E, money and state** (Sonnet 5.5 high): admission, per-call spend, no reservations, `spend_report.py`, `tests/state/`.
   - **F** (no agent): unchanged. Its copy guard and findings checks are called from the update step.
   - **I** (main session, small): `deploy.sh` stops calling `--open-reservations`.
3. **Wave 3b**, after 3a's interfaces are fixed:
   - **G, research, the update step and the side-by-side run** (Opus 5.5 xhigh: the honesty-critical part, and the largest change). It covers research trimmed, the new update step, composition on Sonnet, the two branches with their limits, stops and events, and `tests/loop/`. It may split into G1 (research and composition) and G2 (the update step) if the contract makes the seam clean.
   - **H, API and lifecycle** (Sonnet 5.5 high): admission, `busy`, the count of runs at once, the end of a run after both branches, `/health`, `tests/server/`.
4. **Reviews:** one Sonnet 5.5 high review per part, then one Opus 5.5 xhigh review across the parts. Fixtures are regenerated by the main session (`make_fixtures.py`, deterministic), and the whole suite is run.
5. **Then, with the user's approval:** the four paid tests again. Phase 4 has $1.33 of Anthropic and 2 Exa searches left, so an Exa top-up of the Phase 4 limit needs the user's word first.

## 8. The user's answers

**Answered (Oct 25, 2026):**
1. `LOOP_INPUT_BUDGET` **2,000,000**.
2. `MAX_CONCURRENT_RUNS` **5**; a run is one visitor's question in progress.
3. The update step **continues the research conversation**, for its cache (P4.19 above).
4. The refusal wording: written by the main session (§5).
5. `UPDATE_INPUT_BUDGET` **2,000,000** (user), so the catastrophic overrun for 5 runs is about **$54**, against the Console's $60 monthly limit.
6. **Development spend (user):** *"Development allowance as you restated it: a fresh tally at $0, $3 Anthropic and 20 Exa searches."*
   - Wave 3's paid tests start a fresh tally at $0 in a new ledger (`data/verification/wave3/spend.jsonl`). The Phase 4 ledger stays as it is, closed at $1.6729 and 8 Exa searches.
   - The allowance is **$3.00 of Anthropic and 20 Exa searches**; each paid test still runs only on the user's go.
   - Development never counts against production: the live service has its own Atlas database (`Probable_Clause`, `PC_ENV=live`) and its own Console workspace and key with the $60 monthly limit (T3.4). The two must not share a key. Nothing new is built for it; the deploy check confirms `PC_ENV=live`.

**Nothing is still open.** On the user's approval of this design, P4.18 to P4.21 are locked, with the development allowance as P4.22.
