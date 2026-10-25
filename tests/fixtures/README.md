# Test fixtures for the frontend mock (contract §12, P0.3)

Data for the mock the frontend session builds against, and for the backend's tests. The main session owns it.

Regenerate (no network, no keys; the output is byte-identical on every run):

    .venv/bin/python tests/fixtures/make_fixtures.py            # writes everything
    .venv/bin/python tests/fixtures/make_fixtures.py --summary  # also prints each run's tool results and end
    .venv/bin/pytest -q tests/contract                          # schema, order rules and consistency

Nothing here is a real run, but every stream is the real backend's output.

## How the streams are made

Each stream is recorded through the whole backend, as `tests/contract/test_end_to_end.py` runs it: H's app (`api.server.create_app`) and its `Run` around G's `execute_run`, with B's corpus and keyword index, C's meaning search over the committed vectors, D's update search, E's prices and `MemoryStore`, and F's checks. The page's side is simulated: it posts `POST /runs`, reads `GET /runs/{id}/events` (the SSE frames are what the file holds), and posts `POST /runs/{id}/alive` every `HEARTBEAT_INTERVAL_S` of virtual time. Only the outside services are faked, with their parts' own fakes: `FakeAnthropic` (G), `FakeVoyageClient` (C), `FakeExaTransport` (D), `MemoryStore` (E). Time is `FakeClock` (tests/server/support.py), virtual, so a ten-minute run takes a few milliseconds to record.

Run-time seams the generator patches for each stream and restores afterwards (no source file is changed): the run ID (`api.server.app.secrets`, a fixed hash of the slug); `time.monotonic` in `api.loop.run`, `api.search.meaning` and `api.web_updates.exa` (the virtual clock, so `duration_ms` is the fake's latency); `api.loop.run.retry_sleep` (the virtual clock's sleep, so retry waits pass in virtual time); `api.loop.run.anyio` (F's checks run inline rather than in a worker thread). The script re-executes itself with `PYTHONHASHSEED=0`, and every random choice is seeded by the stream's slug.

States that come from H rather than G are made through H's real paths:
- **`pause-and-resume`** and **`abandoned-run`**: the simulated page stops sending heartbeats for a while (pause) or for good (abandoned), and H's gate before a paid call pauses, resumes on the next heartbeat, or abandons the run `ABANDON_AFTER_S` after the last one.
- **`interrupted-run`**: the third loop call never answers; the generator reads the events Atlas holds (`MemoryStore`), lets that instance go, and 41 s later opens the stream on a second app instance over the same store, which replays the stored events and ends them with H's `interrupted` (`api/server/sse.py`), as `tests/server/test_streams.py::test_interrupted_matches_the_fixture_exactly` does. It holds 42 stored events (that test's neighbours count on it).
- **`band-unavailable-credit-flag-at-start`**: the Atlas flag `exa_out_of_credit` is set in the store before `POST /runs`, so H starts the run with `update_check_available: false`.

## What is real, and what is approximate

Real (the merged code's own output, never typed in): every envelope, number, time stamp and order; every `passage` event and every tool-result text Claude was sent (G's format, B's search results, read errors and filters, C's notes); the status lines; the update searches' parameters, statuses and texts (D); the refusals of a submit and their texts (F's `check_update_findings` and copy guard, G's rules, `api/prompts/rejections.json`); every `paid_call` (H's `record_usage`, priced by E), the totals and the `prices` object; the `checks` event (F's `check_answer` on the streamed blocks); the band; every `run_ended`, `stop_kinds` included.

What the generator decides, as a fake service would:
- **What Claude says.** Each loop turn's tool calls and their inputs, and the answer's blocks and citations, are scripted per stream. Every citation is the exact slice of its passage's sentences (G maps it and refuses a mismatch; a test checks every block). Thinking blocks are present with empty text, as the API returns them with display omitted.
- **Token counts are whatever the fake Claude reports.** It counts characters at a fixed ratio, set so that the loop's fixed prefix (system prompt, catalog and tools) comes out at `FIXED_PREFIX_TOKENS_ESTIMATE` (12,000): the prefix is a one-hour cache write on the first call and a cache read after; the growing conversation is a five-minute write; the composition is uncached. Output is the tool input's tokens plus scripted or seeded thinking tokens. The loop's own estimator (the corpus's characters per token) counts higher, so its limit checks fire a little early, as they would in a live run.
- **Latencies are whatever the fakes report**, in virtual seconds: a loop call is about 0.9 s plus its output at 85 tokens a second; the composition thinks at 90 tokens a second before its first block and streams each block at 55 a second; Voyage takes 0.3 s to embed and 0.6 s to rerank; Exa 2 to 5 s (a timeout 30 s). The slow calls in `time-limit-stop` are set by hand. Our code's own work takes no virtual time, so many events share a `t_ms`.
- **Meaning-search order comes from the `FakeVoyageClient`'s behaviour,** configured: each scripted query embeds as the committed vector of a stand-in passage, and the rerank scores the same closeness, so the order is that passage's nearest neighbours in the real vectors file. The query text Claude "typed" is plausible, not what was embedded. Voyage's token counts are the fake's (words in, as `FakeVoyageClient` counts them).
- **Web pages** are samples on `example.test` domains, every title starts with `[Sample]`, and their text is invented filler (with, where a stream needs one, an invented lead sentence for the copy guard to catch). Page text reaches no event except as the placeholder `[page text: <n> characters, not stored]`. The findings describe what a sample page "reports"; none of it is real news.
- **The recording dates** are synthetic: Oct 24, 2026, 22:00 Chicago time, one stream every seven minutes in the order below.

## The files

Each stream is `{"format", "slug", "question", "recorded_at", "commit": "fixture", "models", "prices", "corpus_label", "events"}` (contract §11.2). Each `events` line is one envelope. The sizes are about 3.6 MB for all 33 streams and 76 KB for the HTTP answers. Durations and costs below are the streams' own (virtual seconds, list prices).

| File | What it shows |
|---|---|
| `answered-phone-location-records` | The answered run: 7 rounds, 9 kept (one re-kept with a new reason, one dissent), two update searches (the second returns a page of the first again, a repeat), update band `found`, a quotation checked and found, about 113 s and $0.26. Also the source of the reconnect fixture. |
| `answered-phone-location-records-after-n185` | The reconnect fixture. The extra top-level field `"after": 185` and only the events after `n = 185` (the fifth round onward). Equal to the source stream's tail (a test checks it). |
| `replay-geofence-before-chatrie` | A replay (T5.6): `corpus_label: before_chatrie`, the corpus without *Chatrie* (coverage ends 2018-06-22), a keyword search whose term "geofence" matches nothing (its results come from "tower dumps"), and an update check that finds a sample page reporting the later decision. |
| `out-of-scope-reply` | `no_sources`, `out_of_scope`: one round, a note and a skip reason, band `skipped`. Its first call is long enough for a keep-alive line (the source of `get-events-200-stream`). |
| `out-of-scope-no-update-check` | P4.7: "hello", out of scope, a note, no search of any kind and no skip reason: accepted at once, band `not_run`. |
| `nothing-found-reply` | `no_sources`, `nothing_found`: real searches that match nothing relevant, an update search, band `nothing_relevant`. |
| `note-refused-copy-guard` | P4.8: a nothing-found reply after an update search returned a sample page. The first submit's note repeats ten words of the page: refused with rule `copy_guard` (the note's own message) and the note withheld in the stored `tool_call`; the reworded note is accepted. Band `nothing_relevant`. |
| `note-too-long` | P4.6: an out-of-scope note of 1,184 characters refused with rule `note_too_long`, then a shorter one accepted; band `skipped`. |
| `step-limit-stop` | Twelve rounds, then an answer built from what was kept: `step_limit`, band `not_summarised` (a search ran, no submit). |
| `token-ceiling-input` | `token_ceiling` / `token_ceiling_input` in six heavy rounds. Calls that failed and were retried count toward the ceiling (T3.3). The biggest file. |
| `token-ceiling-output` | `token_ceiling` / `token_ceiling_output` in nine rounds: the last loop call stops at `max_tokens`, its output exactly what was left of the loop's budget, and nothing comes of it. |
| `time-limit-stop` | `time_limit` after seven slow calls (about 90 s each; the stop comes before round 8, past 600 s); band `not_run`. |
| `pause-and-resume` | No heartbeat for 40 s while the first call runs: `paused` before round 2's call (28.5 s since the last heartbeat), `resumed` 11.5 s later on the page's next heartbeat; a scope note on a normal answer; band `skipped`. |
| `abandoned-run` | The heartbeats stop at 10 s: `paused` before round 3's call (30 s since the last), never resumed; `abandoned` 60 s after the last heartbeat; no answer; band `not_run`. |
| `interrupted-run` | Stops mid-research when the instance goes away during round 3's call; another instance's `run_ended` with state `interrupted` 41 s later: `n` is the last stored + 1, the totals are summed from its stored `paid_call` events, `stop_kinds: []`, and it has no band (it is sent on the stream only). |
| `submit-refused-copy-guard` | A submit refused for its findings (an unknown source, a statement with no source), then by the copy guard with the flagged statement withheld in the stored `tool_call` (P4.3), then accepted; band `found`. |
| `submit-refused-basic-rules-then-declined` | Nine rounds: rule `same_turn` (a read error with the valid range beside it), `no_search`, a bad `out_of_scope` (rule null), `no_note`, `nothing_kept`, a keep with one never-shown ID refused, `no_update_check`, then accepted after the reminder: band `declined`. |
| `check-flags` | A changed word inside a quotation (`quotation_not_found`) and *Entick v. Carrington* (`not_in_corpus`), both F's real output. |
| `band-unavailable-no-credit` | A 402 on the first search of the run: the search is listed with status `unavailable`, rule 4 is waived, band `unavailable` with reason `no_credit`. |
| `band-unavailable-key-refused` | The same with a 401: reason `key_refused`. |
| `band-unavailable-credit-flag-at-start` | `run_started.update_check_available: false` (the Atlas flag is set), the first message tells Claude, no search is tried; band `unavailable`, `searches: []`. |
| `update-search-statuses` | Every way an update search ends: `refused_by_us` (a bad date, not counted), `refused_by_exa` (counted at $0), `failed` (a 30 s timeout, list price for `lite`), `ok`, and a fourth search refused by our code. Band `found`. |
| `voyage-warning-degraded` | The rerank fails three times: `paid_call` `retrying`, `retrying`, `failed`; the results come back `not_reranked`; the `warning` `meaning_search_degraded`. |
| `voyage-warning-unavailable` | The embed fails three times; the result is an error saying keyword search still works; the `warning` `meaning_search_unavailable`; the next meaning search works. |
| `retries-anthropic-and-voyage-recovered` | Retries that worked: a loop call (`rate_limited`), a Voyage embed and rerank, and the composition (`overloaded`). |
| `error-stopped-loop-retries-exhausted` | A loop call fails three times (`overloaded`); the answer is built from what was kept: `error_stopped`, `answer_end: complete`. |
| `composition-incomplete-stream-broken` | The composition stream breaks after three blocks: state `answered`, `answer_end: incomplete`, `failure_reason: stream_broken`; the checks run on the part shown. The broken attempt is priced from what it streamed (P4.10), so its estimated cost includes output tokens. |
| `composition-failed-before-first-block` | The composition fails three times before any block: `failed`, no answer, no checks; the kept passages stay. |
| `answer-cut-off-length-limit` | The composition stops at `max_tokens` (12,000 output tokens, as the fake reports), the last block cut mid-word: `answered`, `stop_kind: composition_max_tokens`, `answer_end: cut_off`. |
| `failed-nothing-kept` | A loop call fails three times with nothing kept: `failed`, no composition. |
| `refusal` | The `refusal` stop reason in round 1: the call is billed (its `paid_call` has real usage, outcome `failed`, `error_kind: refusal`), state `refusal`. |
| `spend-limit-console` | The Console's spend limit (a 400, never retried): `spend_limit` / `console_spend_limit`. |
| `spend-limit-tier-cap` | The usage tier's spend cap (a 429, never retried): `spend_limit` / `tier_spend_cap`; band `not_summarised`. |

`http/*.json` are `{"description", "method", "path", "status", "headers", "body"}`, with `body` the exact string sent. All but four are H's real answers, taken from the app on a `MemoryStore` filled as each case needs (headers kept: `Content-Type`, `Cache-Control`, `X-Accel-Buffering`): `/health` (`health-ready`, `-paused-day`, `-paused-month`, `-unknown`), `POST /runs` (`post-runs-201`, with the out-of-scope-reply stream's run ID; the `400`s, `413`, the three `503`s), the stream's first frames with `X-Accel-Buffering: no` (`get-events-200-stream`, the out-of-scope-reply stream's text as sent, keep-alive line included), the `404` for an expired run, and `POST /runs/{id}/alive` (`204`, `404`). The wake-protocol answers that are not our JSON (`cloud-run-429`, `-500`, `-503`, `gateway-502`) are representative bodies, not captures.

## Coverage across the set (a test checks it)

- **`run_ended.state`**: all 11. **`stop_kind`**: all seven the schema allows (`step_limit`, `token_ceiling_input`, `token_ceiling_output`, `composition_max_tokens`, `console_spend_limit`, `tier_spend_cap`, `time_limit`). `daily_cap`, `monthly_cap` and `exa_no_credit` never end a run, and the schema does not allow them. **`stop_kinds`** is on every `run_ended`.
- **Band outcomes**: all seven (`found`, `nothing_relevant`, `skipped`, `declined`, `unavailable`, `not_summarised`, `not_run`), `not_run` both for a run stopped before any search or submit and for an out-of-scope reply with no search (P4.7).
- **`answer_end`**: all four. **`no_sources_reason`**: both. **Warnings**: both codes. **Web statuses**: all five. **Tools**: all six. **Event kinds**: all fifteen.
- **`submit.rule`**: all eight values (`same_turn`, `findings`, `copy_guard` for statements and for a note, `no_search`, `nothing_kept`, `no_update_check`, `no_note`, `note_too_long`) and null for bad input.
- **Retries**: Anthropic (loop and composition) and Voyage (embed and rerank), each `retrying` then `ok` or `failed`.

## Conventions

These are the code's, not the generator's; the contract (§6) is the reference.

- `paused.since_ms` is how long since the last heartbeat when the run paused (at least `ATTENDED_WINDOW_S`); `resumed.since_ms` is how long the run was paused.
- A `retrying` or `failed` `paid_call` carries the number of the attempt that failed. An attempt that reported no usage has `usage: null` and `estimated: true`, priced from G's input estimate at the uncached price (T3.3); one that streamed output first is priced with that output too (P4.5, P4.10), still shown as `usage: null`.
- `paid_call.usage` is Claude's raw usage object; for Voyage it is `{"total_tokens": n}`; for Exa it is `null`. `max_attempts` is 3 for Claude and Voyage, 1 for Exa.
- Answer blocks stream before the composition's `paid_call`; the response `api_fragment`s follow it (§6). The `checks` event follows the last block, then `update_band`, then `run_ended`. A stream with no answer has no `checks` event.
- The `warning` event comes right after the `tool_result` that first set the flag.
- Time and token limits are checked before a round starts, so a run that stops for them has no `round_started` for the call it did not make. A pause that ends in abandonment keeps its `round_started`.
- `update_band.searches` lists every search that reached the check or was found unavailable (with its own `search_no`), and not a search our code refused; `returned` counts new pages and repeats. `tool_result.is_error` is true for every web status but `ok`.
- A `keep_passages` input can name an ID that was never shown; it has no `passage` event, and the `tool_result` lists it under `refused`.
