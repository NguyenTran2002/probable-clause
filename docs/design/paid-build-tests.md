# Paid build tests, Phase 4: the plan for the user's approval

*Drafted by the main session during the overnight run of Oct 25, 2026. **The budget was approved by the user at 12:09 CDT** ("The budget for paid build tests are sound"; BUILD_LOG, P4.11 to P4.15). The prompt drafts were approved at the same time (P4.15). Nothing has been run yet; the tests run on the user's go.*

## Limits
- **Anthropic:** the Phase 4 ceiling is **$3.00**. Spent so far in Phase 4: $0.
- **Exa:** at most **10 searches** in Phase 4. Used so far: 0.
- **Voyage:** a few cents at list price (the queries' embeds and reranks; the corpus is already embedded).
- **Atlas:** `Probable_Clause_test` only. The API runs with `PC_ENV` unset, so it uses the test database.
- **Stop rule:** after each test, add up its `run_ended.totals`. Stop before any test that would take the running Anthropic total past **$2.50**, or the Exa count past 8. This leaves room under both ceilings for one rerun.

## Prices
Anthropic's pricing page (https://platform.claude.com/docs/en/about-claude/pricing), re-read Oct 25, 2026, 01:37 CDT.
- **Unchanged from T3.4 and `api/state/prices.py`.** Per million tokens:
  - Sonnet 5.5: $2 input, $2.50 for a 5-minute cache write, $4 for a 1-hour write, $0.10 for a cache read, $10 output;
  - Opus 5.5: $4, $5, $8, $0.20 and $20.
- **No long-context surcharge** on these models.
- **Global routing is the default.** `inference_geo: "us"` would add 1.1x; the loop doesn't set it.

The page is re-read once more right before the tests, and `PRICE_TABLE`'s Anthropic date is updated then (contract §10).

## How the tests run
- **The API alone on localhost.** `deploy/local.sh` can't run yet: it also builds the web image, which fails until `web/index.html` exists.
- **The user starts the API** with their keys from `.env`:

  ```bash
  uv run --env-file .env .venv/bin/uvicorn api.main:app --port 8000
  ```

  The server's log is kept for the mapping-fault lines.
- **Each test** is one `POST /runs` with its question, then:
  - the stream read from `GET /runs/{id}/events`;
  - a heartbeat to `POST /runs/{id}/alive` every `HEARTBEAT_INTERVAL_S`, so the run isn't paused as unattended;
  - the events saved under `data/verification/phase4/` (local only).
- **This needs a small client.** `curl` alone can't send heartbeats while it reads the stream. Writing that client is listed below as a step for the user's go-ahead. It makes no paid call itself; the server does.

## The tests

| # | Test | Question (draft) | What it checks | Expected Anthropic cost | Exa |
|---|---|---|---|---|---|
| 1 | **An answered run with an update search** | "Can police use a thermal imager on my house from the street?" | **Citations:** the mapping-fault count (server log and `answer_block` citations): 0 expected, and any fault is the first thing to read. **Thinking:** blocks passed back between loop turns with no 400. **Cache classes:** the first loop call writes the 1-hour prefix; later calls read it and write 5-minute entries (each `paid_call.usage`'s `cache_creation`). **Spend markers:** each `paid_call.cost_usd` against the price table by hand; the totals equal their sum; the reservation is settled and released in `Probable_Clause_test`. **Update check:** at least one search, page text never in events, the band's outcome. | $0.19 to $0.35 (Phase 2 measured $0.144 of loop and composition at Sonnet prices; $0.188 with Opus composing, BUILD_LOG 429; adaptive thinking at high effort may add output) | 1 to 3 |
| 2 | **An out-of-scope reply** (P4.7) | "hello" | Submitted out of scope at once with a note, no corpus search needed, **no Exa call and no rule-4 reminder**, band outcome `not_run`, no composition call. The second test within the hour, so the 1-hour prefix is a **cache read**, not a write. | about $0.01 to $0.03 (one or two Sonnet calls on a cached prefix) | 0 |
| 3 | **A nothing-found reply** | A Fourth Amendment question the corpus can't answer, for example "Did the Supreme Court decide a case about police searching a car's onboard computer in 2027?" (draft) | Corpus searches, nothing kept, a note, no composition; `no_sources_reason`; if an update search returned a page, P4.8's note guard is live. | $0.05 to $0.15 | 0 to 2 |
| 4 | **A second answered run** (citations at scale) | "When may police track a phone's location without a warrant?" (*Carpenter* and its line) | More cited blocks for the mapping-fault count, with a longer composition; Phase 2's dearer question. | $0.25 to $0.45 (Phase 2: $0.237, $0.309 with Opus composing) | 1 to 3 |

**Expected in total:** about **$0.50 to $1.00** of Anthropic, against the $3 ceiling, and 2 to 8 Exa searches of 10. The worst case of one run is $2.106 (P4.6), so the stop rule is checked after every test, never only at the end.

**Also measured in tests 1 and 4: the loop's input per round.** On the fakes, at the loop's own estimator ratio, twelve moderate rounds barely fit the 370,000 loop budget (the step-limit fixture reached the input ceiling at round 11; BUILD_LOG 02:22). The real tokens per round, against the estimator's figure, show whether `LOOP_INPUT_BUDGET` or the estimator needs the user's attention before launch.

**Not tested with money:** the spend-limit and spend-cap stops (they would need a real limit to be hit), retries, the deadline and abandonment. All are covered by the fakes (`tests/loop`, `tests/server`, `tests/contract/test_end_to_end.py`).

## What the main session reports after the tests
- Each run's totals, cache classes and mapping faults.
- Whether real thinking blocks round-tripped.
- The band outcomes.
- Any difference between `paid_call.cost_usd` and the price table by hand.
- A BUILD_LOG entry, with the Anthropic ledger updated.

## What the user does or decides first
1. ~~Approve this plan~~: the budget was approved, Oct 25, 12:09.
2. ~~The texts~~: approved (P4.15).
3. **The key:**
   - T3.4 asks for a Console workspace and key with a $60 monthly limit before live runs.
   - For these build tests, say whether the key now in `.env` may be used.
   - Check it with `uv run python scripts/check_env.py --phase 4`.
4. **Approve the client** (above). Or run the four tests from the browser pane by hand once the page exists.
