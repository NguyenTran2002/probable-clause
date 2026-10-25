# Wave 3 plan: building the Wave 3 design

*Proposed Oct 25, 2026 by the main session; **approved by the user at 13:47 CDT** ("Looks good to me."). It builds `docs/design/wave3-design.md` (P4.18 to P4.22). The main session follows it after the compaction, from step 0, item 2 (item 1, the locks, is done). Nothing in it spends money until step 6, and step 6 runs only on the user's go.*

## Rules for the whole wave

- **Agents (the user, P4.1):** Sonnet 5.5 or Opus 5.5 only, never Haiku; effort high or xhigh, never max. Each agent's model and effort is stated when it starts. Agents never commit. The main session reads every diff and commits each part's paths by name.
- **One writer per file.** Each agent gets an explicit list of the paths it may write. Nothing outside its part, and never `web/`, `.env`, `pyproject.toml` or `uv.lock`.
- **Keys:** no agent gets a key or runs a paid call. Every test runs on fakes. The keys in `.env` are used only in step 6, by the main session, through `uv run --env-file .env` (the user, 12:17).
- **The lock pattern:** every decision is logged in BUILD_LOG and indexed in `locked-decisions.md` in one commit, and a `date` call is made before every time written.
- **Stop and ask** if the design reads two ways at any point, or a part would need to change a locked decision other than P4.18 to P4.22.
- **Every run's files are kept** (the user). The new ledger is `data/verification/wave3/spend.jsonl`.

## Step 0: lock and write the shared ground (the main session, no agents)

1. **Lock P4.18 to P4.22** in the user's words, each in its own entry (on approval of this plan).
2. **Contract v2.0** (`docs/design/contract.md`):
   - parts D, E, F (the guard's callers), G and H, and the events (§6), tools (§7), Atlas (§8), settings (§9) and ownership (§13);
   - and `contracts/events.schema.json`: the `step` field, `update_started` and `update_ended`, the band without `declined`, the new `submit.rule` values, `run_started.limits`, `totals.claude.cost_usd.update`, and `busy`.
3. **The shared code:**
   - `api/settings.py`: the new, changed and removed figures, each with its basis;
   - `api/protocols.py`: the `Store` without reserve, settle and release; with admission, `record_spend` and the live status from spend;
   - `api/types.py` and `api/errors.py` as the contract needs.
4. **The prompt drafts** (`api/prompts/`):
   - `loop_system.md` shared by both steps;
   - `tools.json` with seven tools and `submit_update`;
   - `loop_messages.json` with `update_start` and the status lines;
   - `rejections.json` with `no_check`, the two wrong-step refusals and the copy-guard texts under `submit_update`;
   - the `busy` and cap texts in H's table come from the design.
   - **The user reviews these before step 6** (T1.14). The builders work from the drafts.
5. **An Opus 5.5 xhigh review of contract v2.0 and the schema** before any builder starts, as v1 had (P4.1). Read-only, it reports gaps, contradictions and anything a builder would have to guess. The main session fixes them and bumps the version.
6. **The frontend brief:** what changes and what to wait for (the step log, the band's timing, `declined`'s removal, `busy`), so the frontend session can go on with the rest.
7. **Commit.** Contract v2.0, the schema, the shared code and the drafts are committed together.

## Step 1: Wave 3a, in parallel

- **E, money and state** (Sonnet 5.5, high).
  - **Writes:** `api/state/` and `tests/state/`; `scripts/spend_report.py`.
  - **Builds:**
    - admission (today's and the month's spend under the caps, the spend-limit flag, fail closed);
    - `record_spend`, one atomic increment per paid call to the day's and month's documents;
    - `live_status` from spend;
    - `MemoryStore` with the same semantics;
    - reservations removed (`reserve`, `settle`, `release`, expiry, `--open-reservations`);
    - the worst-case figure kept only as a documented, tested number.
  - **Tested against** the Mongo fake, plus the Atlas tests that already run against `Probable_Clause_test` with no paid call.
- **G, research, the update step and the two branches** (Opus 5.5, xhigh). One agent, because research and the update step share `run.py`'s request building, retries, budgets, tool dispatch and events.
  - **Writes:** `api/loop/` and `tests/loop/`.
  - **Builds:**
    - **the conversation machinery** factored out of `_Run`, so research and the update step share the request, the retries, the per-step budgets and the tool dispatch, with one tool list of seven;
    - **research trimmed:** no update tools allowed; `submit_answer(out_of_scope, note?)` with its rules; no rule 4; no copy guard on the note;
    - **the update step:** it continues the research conversation (the accepted submit's result carries `update_start`); only `search_web_updates` and `submit_update` are allowed; it has its own limits and stops, and calls F's findings checks and copy guard;
    - **composition** on Sonnet with `COMPOSITION_MAX_TOKENS` 16,000; otherwise unchanged;
    - **`execute_run`** running the update step and the composition side by side (asyncio tasks), with the update step turned off by code when research never searched (out of scope) or Exa is unavailable;
    - **one event stream** with the `step` field, ending after both branches;
    - **abandonment, pauses, the deadline and the spend-limit stop** applying to both branches.
  - **Tests:** the existing loop tests are rewritten where the design changes them, plus new ones:
    - the update step reading research's cached prefix (the request's prefix byte-identical, checked on the fake);
    - each step's tools refused in the other;
    - `no_check`;
    - the update step failing without touching the answer;
    - both branches' events interleaved and valid;
    - out of scope with no update call;
    - nothing found with the update step running and no composition.
- **D and F:** no agent. D's Exa wrapper is unchanged (5 searches comes from settings). F is unchanged; its copy guard and findings checks are called by the update step.

## Step 2: Wave 3b

- **H, the API and the run lifecycle** (Sonnet 5.5, high), after E is merged, since its tests run on E's `MemoryStore`.
  - **Writes:** `api/server/`, `api/main.py` and `tests/server/`.
  - **Builds:**
    - admission through E, with the `busy` refusal at `MAX_CONCURRENT_RUNS` (the registry's count of runs in progress) and the new cap texts;
    - each `paid_call` recorded to spend as it happens;
    - no reservation anywhere;
    - `/health` from the live status;
    - totals with `update`;
    - `run_ended` after both branches;
    - the `stop_kinds` from either branch.
- **I, deploy** (the main session, small): `deploy.sh` stops calling `--open-reservations`, and checks `PC_ENV=live` instead. `tests/deploy/` follows.

## Step 3: reviews, one per part

Each review is a fresh agent, read-only, given the diff and the design (not the main session's conclusions):
- **E:** Sonnet 5.5, high.
- **G:** Opus 5.5, high. It's honesty-critical: citations, the copy guard, page text never in events.
- **H:** Sonnet 5.5, high.

The main session checks each finding, fixes or queues it, and re-runs the part's tests. Each part is committed after its review.

## Step 4: the main session's own files

1. `tests/fixtures/make_fixtures.py`:
   - streams with update steps, `busy`, update-step failure and limit stops, and nothing found with an update step;
   - `declined` and the reservation streams dropped;
   - regenerated, deterministic.
2. `tests/contract/`:
   - `test_end_to_end.py` through both branches;
   - `test_composition_worst_case.py` removed or recast, since the reserve is gone;
   - `test_fixtures.py` for the new streams.
3. `scripts/run_client.py` and `scripts/render_run.py` for the `step` field and the update lane.
4. The fixtures README.

## Step 5: one review across the parts, then the whole

1. **One Opus 5.5 xhigh review across E, G, H and the fixtures,** as at the end of Wave 2: the seams, the money path, the event order under the two branches, and anything only visible when the parts run together. The main session fixes or queues each finding.
2. **The whole suite.** Then the API image built and loaded offline (Docker, `--network none`).
3. **A free Atlas check:** reach `Probable_Clause_test` with `scripts/spend_report.py` (this was unreachable after the re-runs).
4. **A BUILD_LOG entry for the wave,** CLAUDE.md's state updated, and the frontend session told the fixtures are ready.

## Step 6: the paid tests, on the user's go only

- **Before:** the user approves the prompt drafts (T1.14).
- **Then:** the four tests again (the same questions, labels `w3-t1` to `w3-t4`) against `Probable_Clause_test`, under P4.22's allowance: **$3.00 of Anthropic and 20 Exa searches, from a fresh tally at $0**. They are checked after each test and stopped before a test that could pass either.
- **What they check:**
  - the update step's cache reads (its first call reading research's prefix);
  - one submit per step;
  - the composition's quality on Sonnet, for the user to judge from the rendered answers;
  - the real cost per run against the earlier runs;
  - the loop's and the update step's input against their 2M budgets.
- **After:** a BUILD_LOG entry and the new ledger.

## What waits for the user along the way

- **Now:** approval of this plan, and with it the design, so that P4.18 to P4.22 are locked.
- **After step 0:** nothing, unless the contract review finds something that reads two ways.
- **Before step 6:** the prompt drafts, and the go for the paid tests.
- **After step 6:** the composition's quality on Sonnet, and the frontend session's next round.

## Rough size

- **Agents:** eight in all (one contract review, three builders, three part reviews, and one review across the parts). That's within the medium guideline of under 10.
- **Paid spend:** none before step 6. Step 6 is expected at about $1.00 to $1.50 of Anthropic and 4 to 12 Exa searches.
