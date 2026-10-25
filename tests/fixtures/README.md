# Test fixtures for the frontend mock (contract §12, P0.3)

Data for the mock the frontend session builds against, and for the backend's tests later. The main session owns it.

Regenerate (no network, no keys; the output is identical on every run):

    .venv/bin/python tests/fixtures/make_fixtures.py            # writes everything
    .venv/bin/python tests/fixtures/make_fixtures.py --summary  # also prints each run's tool results and ends
    .venv/bin/pytest -q tests/contract                          # schema, order rules and consistency

Nothing here is a real run. The streams are produced by a script that calls the merged code wherever it can.

## What is real, and what is approximate

Real (taken from the merged code, never typed in):

- every `passage` event: `Corpus.load`, the sentence offsets, the section labels, the joiners (the `before_chatrie` stream loads the corpus without *Chatrie*, label and coverage dates included);
- search results from `search_exact`: `KeywordIndex.search` with `parse_filters`; `read_passages`: `Corpus.read`; all error messages from those calls;
- the `checks` event: `check_answer` run on the stream's own answer blocks and kept passages; the check-flags stream's two flags are its real output;
- the update searches: `parse_params`, `params_as_dict`, `fixed_settings`, `format_for_events`; the refusals of a submit: `check_update_findings` and `copy_guard_report`; the rejection and status-line texts: `api/prompts/rejections.json` and `loop_messages.json`; the meaning-search notes: `NOT_RERANKED_NOTE` and `UNAVAILABLE_NOTE`;
- every price: `price(Usage)`; the `prices` object: `price_sources()`; every limit: `api/settings.py`; the run's `totals` are summed from its own `paid_call` events (a test checks it).

Approximate or invented:

- **The loop's tool-result text** (`tool_result.content`, and the `messages[...]` text fragments) follows T1.6's shape (header, loop text with `[n. <label>]` markers, attached footnotes, a "matched again" line) but builder G will write the real format. The status line has the real template.
- **Meaning-search order** is the nearest neighbours, in the real vectors file, of a stand-in passage, not a live Voyage query. The query text Claude "typed" is plausible, not what was embedded. Reranking is not modelled except as success or failure.
- **Web pages** are samples on `example.test` domains, every title starts with `[Sample]`, and their text is invented filler that only its length ever reaches an event (as the placeholder `[page text: <n> characters, not stored]`). The findings describe what a sample page "reports"; none of it is real news.
- **Tokens and times**: token counts are the text's characters over the corpus's own characters-per-token ratio; the cache pattern is a 12,000-token one-hour write on call 1, then cache reads; latencies and the thinking tokens inside `output_tokens` are invented but plausible. The recording dates are synthetic (Oct 24, 2026, Chicago time, one stream every seven minutes).
- **The answers** are written by hand for each question; every citation is checked against the passages' sentences (a test does it for every block).
- Thinking blocks are not modelled: an assistant message holds an optional text block, then the `tool_use` blocks.

## The files

Each stream is `{"format", "slug", "question", "recorded_at", "commit": "fixture", "models", "prices", "corpus_label", "events"}` (contract §11.2). Each `events` line is one envelope. The sizes are about 3.4 MB for all 30 streams.

| File | What it shows |
|---|---|
| `answered-phone-location-records` | The answered run: 7 rounds, 9 kept (one re-kept with a new reason, one dissent), two update searches (one repeat), update band `found`, a quotation checked and found, about 45 s and $0.24. Also the source of the reconnect fixture. |
| `answered-phone-location-records-after-n185` | The reconnect fixture. The extra top-level field `"after": 185` and only the events after `n = 185` (the fifth round onward). Equal to the source stream's tail (a test checks it). |
| `replay-geofence-before-chatrie` | A replay (T5.6): `corpus_label: before_chatrie`, the corpus without *Chatrie* (coverage ends 2018-06-22), a search that matches nothing ("geofence"), and an update check that finds a sample page reporting the later decision. |
| `out-of-scope-reply` | `no_sources`, `out_of_scope`: one round, a note, band `skipped`. |
| `nothing-found-reply` | `no_sources`, `nothing_found`: real searches that match nothing relevant, an update search, band `nothing_relevant`. |
| `step-limit-stop` | Twelve rounds, then an answer built from what was kept: `step_limit`, band `not_summarised` (a search ran, no submit). |
| `token-ceiling-input` | `token_ceiling` / `token_ceiling_input`. Calls that failed and were retried count toward the ceiling (T3.3), so it is reached in six rounds. The biggest file. |
| `token-ceiling-output` | `token_ceiling` / `token_ceiling_output`: the last loop call is cut at `max_tokens` (its output is the exact remainder of the budget, and nothing comes of it). |
| `time-limit-stop` | `time_limit` after ten minutes of slow calls (t_ms past 600,000); band `not_run`. |
| `pause-and-resume` | `paused` and `resumed` before a call; a scope note on a normal answer; band `skipped`. |
| `abandoned-run` | `paused`, never resumed; `abandoned` 60 s after the last heartbeat; no answer; band `not_run`. |
| `interrupted-run` | Stops mid-research, then H's `run_ended` with state `interrupted`: `n` is the last stored + 1, the totals are summed from its stored `paid_call` events, and it has no band (it is sent on the stream only). |
| `submit-refused-copy-guard` | A submit refused for its findings (an unknown source, a statement with no source), then by the copy guard with the flagged statement withheld in the stored `tool_call` (P4.3), then accepted; band `found`. |
| `submit-refused-basic-rules-then-declined` | Rules `same_turn`, `no_search`, `nothing_kept` and `no_update_check`, a read error with the valid range, a keep with one never-shown ID refused, then accepted after the reminder: band `declined`. |
| `check-flags` | A changed word inside a quotation (`quotation_not_found`) and *Entick v. Carrington* (`not_in_corpus`), both real outputs of `check_answer`. |
| `band-unavailable-no-credit` | A 402 on the first search of the run: the search is listed with status `unavailable`, rule 4 is waived, band `unavailable` with reason `no_credit`. |
| `band-unavailable-key-refused` | The same with a 401: reason `key_refused`. |
| `band-unavailable-credit-flag-at-start` | `run_started.update_check_available: false` (the Atlas flag is set), the first message tells Claude, no search is tried; band `unavailable`, `searches: []`. |
| `update-search-statuses` | Every way an update search ends: `refused_by_us` (a bad date, not counted), `refused_by_exa`, `failed` (30 s, list price), `ok`, and a fourth search refused by our code. Band `found`. |
| `voyage-warning-degraded` | The rerank fails three times: `paid_call` `retrying`, `retrying`, `failed`; the results come back `not_reranked`; the `warning` `meaning_search_degraded`. |
| `voyage-warning-unavailable` | The embed fails three times; the result is an error saying keyword search still works; the `warning` `meaning_search_unavailable`; the next meaning search works. |
| `retries-anthropic-and-voyage-recovered` | Retries that worked: a loop call (`rate_limited`), a Voyage embed and rerank, and the composition (`overloaded`). |
| `error-stopped-loop-retries-exhausted` | A loop call fails three times (`overloaded`); the answer is built from what was kept: `error_stopped`, `answer_end: complete`. |
| `composition-incomplete-stream-broken` | The composition stream breaks after the first blocks: state `answered`, `answer_end: incomplete`, `failure_reason: stream_broken`; the checks run on the part shown. |
| `composition-failed-before-first-block` | The composition fails three times before any block: `failed`, no answer, no checks; the kept passages stay. |
| `answer-cut-off-length-limit` | The composition stops at `max_tokens` (12,000 output tokens, most of them thinking), the last block cut mid-word: `answered`, `stop_kind: composition_max_tokens`, `answer_end: cut_off`. |
| `failed-nothing-kept` | A loop call fails three times with nothing kept: `failed`, no composition. |
| `refusal` | The `refusal` stop reason in round 1: the call is billed (its `paid_call` has real usage, outcome `failed`, `error_kind: refusal`), state `refusal`. |
| `spend-limit-console` | The Console's spend limit (a 400, never retried): `spend_limit` / `console_spend_limit`. |
| `spend-limit-tier-cap` | The usage tier's spend cap (a 429, never retried): `spend_limit` / `tier_spend_cap`; band `not_summarised`. |

`http/*.json` are `{"description", "method", "path", "status", "headers", "body"}`, with `body` the exact string sent: `/health` (`health-ready`, `-paused-day`, `-paused-month`, `-unknown`), the wake-protocol answers that are not our JSON (`cloud-run-429`, `-500`, `-503`, `gateway-502`; representative bodies, not captures), `POST /runs` (`post-runs-201`, the `400`s, `413`, the three `503`s), the stream's first frames with `X-Accel-Buffering: no` (`get-events-200-stream`), the `404` for an expired run, and `POST /runs/{id}/alive` (`204`, `404`).

## Coverage across the set (a test checks it)

- **`run_ended.state`**: all 11. **`stop_kind`**: all seven the schema allows (`step_limit`, `token_ceiling_input`, `token_ceiling_output`, `composition_max_tokens`, `console_spend_limit`, `tier_spend_cap`, `time_limit`). `daily_cap`, `monthly_cap` and `exa_no_credit` never end a run, and the schema no longer allows them.
- **Band outcomes**: `found`, `nothing_relevant`, `skipped`, `declined`, `unavailable`, `not_summarised`, `not_run`.
- **`answer_end`**: all four. **`no_sources_reason`**: both. **Warnings**: both codes. **Submit rules**: all six. **Web statuses**: all five. **Tools**: all six. **Event kinds**: all fifteen.
- **Retries**: Anthropic (loop and composition) and Voyage (embed and rerank), each `retrying` then `ok` or `failed`.

## Conventions

Ruled by the main session in contract v1.1 (section 6): `paused.since_ms` and `resumed.since_ms`; `failure_reason` as an `ErrorKind`; `answer_end: incomplete` with state `answered`; a failed attempt's `usage: null` with `estimated: true`; the limits checked before a round; the `searches` list; the order of answer blocks and the composition's `paid_call`. The rest are this generator's choices where the contract is silent.

- `paused.since_ms` is how long since the last heartbeat when the run paused (at least `ATTENDED_WINDOW_S`); `resumed.since_ms` is how long the run was paused.
- A `retrying` or `failed` `paid_call` carries the number of the attempt that failed (as `MeaningIndex` records it); its `usage` is `null`, `estimated` is `true`, and its cost is the estimated input at the uncached price (T3.3). The totals count it; a test recovers its tokens from the cost.
- `paid_call.usage` is Claude's raw usage object; for Voyage it is `{"total_tokens": n}`; for Exa it is `null`. `max_attempts` is 3 for Claude and Voyage, 1 for Exa.
- Answer blocks stream before the composition's `paid_call` (its usage is only known at the end of the response); the response `api_fragment`s follow it (§6). The `checks` event follows the last block, then `update_band`, then `run_ended`. A stream with no answer has no `checks` event.
- The `warning` event comes right after the `tool_result` that first set the flag.
- Time and token limits are checked before a round starts, so a run that stops for them has no `round_started` for the call it did not make. A pause that ends in abandonment keeps its `round_started`.
- `update_band.searches` lists every search that reached the check or was found unavailable (with its own `search_no`), and not a search our code refused; `returned` counts new pages and repeats. `tool_result.is_error` is true for every web status but `ok`.
- A `keep_passages` input can name an ID that was never shown (the refused keep in `submit-refused-basic-rules-then-declined`); it has no `passage` event, and the `tool_result` lists it under `refused`.
- `failure_reason` is the error kind (`overloaded`, `server_error`, `stream_broken`, `refusal`); it is null for `spend_limit`, whose `stop_kind` says why.
- A composition that fails before its first block ends `failed`; one that breaks after a block ends `answered` with `answer_end: incomplete` and `failure_reason: stream_broken` (ruled, v1.1). `error_stopped` is a loop stopped by an error after retries, composed from what was kept.
