# Frontend session brief: the real page, against a mock

*Rewritten Oct 24, 2026 by the main session for Phase 4 (P4.1), replacing the look-test brief of Oct 23. If you are the frontend session, read this file in full, then the files it names, before doing anything.*

---

## 1. Who you are and what you are for

You are the **frontend session** of Probable Clause. The **main session** works in this same folder and branch. It builds the backend (Wave 2 of P4.1 is starting: the research loop, the API and the deploy files) and owns every shared document.

**Your job:** build the real page under `web/`, from the locked prototype (T4.1) and against **interfaces contract v1.1**. Drive it from a local mock that plays the main session's fixtures.

**You are done when:**
- every fixture plays correctly through your mock;
- every view passes the size checks (§6);
- your Node tests pass;
- the user has reviewed it locally and says so. That sign-off goes in your log in the user's words.

Deploying is not yours. The page later runs against the real API in the local review of the whole stack (P4.1).

## 2. Read first

1. `PROBABLE_CLAUSE_KICKOFF.md` in full, the frozen brief. Above all §1, §2, §7 (the interface), §8.5 (waking) and §10.6 (wording rules).
2. `docs/design/locked-decisions.md`. It **wins over the brief**. Yours above all:
   - **the look and the stack:** T4.1 (the prototype is the baseline), T4.2 (plain ES modules, markdown-it, no build step), T4.3 (the seven changes to the prototype), T4.4 (new pieces), T4.5 (costs);
   - **every wording entry:** T5.1 to T5.6. The texts there are final; use them exactly;
   - **the behaviours behind the page:** T1.6, T1.7, T1.9 to T1.12, T2.2 to T2.4, T3.1, T3.2, T3.6 and T3.7, and P4.3.
3. `docs/design/contract.md` (v1.1). It is the spec you build against:
   - §5: the endpoints;
   - §5.1: the wake protocol, which the page implements;
   - §6: every event. `contracts/events.schema.json` is binding;
   - §11: reader files, replays, `corpus.json` and `config.json`.
4. `docs/design/design-note.md`, for the architecture in one read.
5. Your own log, `docs/sessions/frontend-log.md`, and the prototype at `web/looktests/machinery/` (commit badc05f, T4.1).
6. `CLAUDE.md`, including its "If you are the frontend session" section.

Load the **frontend-design** skill before designing anything new.

## 3. Rules for sharing this folder (P0.3)

- **Write only under `web/` and `webdev/`, and your log `docs/sessions/frontend-log.md`.**
  - `web/` is exactly what the web service serves (T4.2), so nothing for development goes there.
  - `webdev/` is yours for what is never served: the mock server, the Node tests, helper scripts.
  - Never edit anything else. `tests/fixtures/`, `contracts/`, `api/`, `scripts/`, `docs/design/`, `BUILD_LOG.md` and `CLAUDE.md` are the main session's. If one needs a change (a fixture is wrong, the schema can't express something), tell the user, and the main session makes it.
- **Commit only your own paths, by name:** `git add web webdev docs/sessions/frontend-log.md && git commit -m "..." -- web webdev docs/sessions/frontend-log.md`. Never `git add -A` or `git add .`.
- **Git you never touch:**
  - Never `git stash`, `reset`, `checkout -- .`, `restore` on paths you don't own, a branch switch, `rebase`, `commit --amend`, or a tag.
  - On `index.lock`, wait and retry; never delete it.
  - End every commit message with your session's attribution line.
- Don't touch `.venv`, `pyproject.toml` or `uv.lock`, and never run `uv add` or `uv sync`. Never read or edit `.env`. Make no paid calls and no calls to CourtListener, Exa, Voyage or Anthropic.
- **No `.png`, `.jpg` or `.jpeg` file is ever committed** (P0.4). `.svg`, `.ico` and `.woff2` are fine.
- No absolute local paths in committed files.
- **Ports:** the main session uses 8000 for the API; use 8765 for your mock.

## 4. What you build

**The page, in `web/`:**
- **From the prototype.** Carry `web/looktests/machinery/` forward into `web/`, split into ES modules by concern: the stream client, the renderer, the source panel, the modals, the wake logic, the band, the checks.
- **Drop** what T4.1 lists: the palette and theme banner, the scripted run, the mock opinion text, the `?v=` strings. Leave `web/looktests/` as it is, for the record.
- **Fonts (T5.5):** Instrument Sans, Newsreader and JetBrains Mono, served as `.woff2` from `web/fonts/` with the SIL Open Font License text beside them. No request to Google Fonts or any other third party; the page contacts no one but its own origin.
- **markdown-it (T4.2):** vendored at an exact version, with its licence file. Raw HTML off and links off in the answer.
- **Text is inserted as text.** Create elements and set their text. Never build markup from strings holding visitor, Claude, corpus or web content (T3.7). The only links to the web are the update band's, built by your code from the event's URL fields, opening with `noopener noreferrer`.
- **The page always calls `api/...` relative to its own URL** (contract §4.I). There is no CORS and no absolute API origin.

**The mock, in `webdev/`:** a small local server, with the Python standard library or Node and no dependencies. It serves:
- `web/` as the site root;
- the generated files at the same root: `opinions/<opinion_id>.json`, `corpus.json` and `config.json`;
- under `api/`, the contract §5 endpoints, played from fixtures:
  - `GET /health` answers from `tests/fixtures/http/`;
  - `POST /runs` returns a run whose stream is one fixture. Pick the fixture with a query parameter or a dev-only switch in `webdev/`, never in `web/`;
  - `GET /runs/{id}/events` plays its events as Server-Sent Events. Each event is `id: <n>`, `event: <kind>` and `data: <envelope>`; events are paced by their `t_ms`; a comment line comes every `KEEPALIVE_S`; `Last-Event-ID` is honoured; and the stream closes after `run_ended`;
  - `POST /runs/{id}/alive` returns 204;
  - the failure answers: Cloud Run's plain-text 429, 500 and 503, the gateway's HTML 502, the `POST /runs` refusals, and the 404 for an expired run. Each one is a switch, so every state of T4.4 and T5.4 can be shown.
- **The generated files:** the main session wrote them to `web/_generated/` (gitignored) with `scripts/build_web_data.py --out web/_generated`. In production they sit at the site root beside `web/`'s files. Your mock serves them there, and you may rerun that script into the same folder.

**The fixtures,** which you read and never edit:
- `tests/fixtures/events/*.json`: one run per state, in the replay format of contract §11.2, with real corpus passages, real check results and real prices. The README there says what each shows.
- `tests/fixtures/http/*.json`.
- If they are still being written when you start, the main session will tell the user when they land.

## 5. Contract details easy to miss

- **Citations** carry `passage_id`, `first_sentence` and `last_sentence`, both **inclusive** indexes into the passage's `sentences`, plus `cited_text`. The sources panel always shows the cited sentences lit inside the full paragraph (T1.9).
- **Check flags** run from (`block`, `start`) to (`end_block`, `end`) and may span answer blocks. **Offsets are Python code points;** convert them for JavaScript strings, which count UTF-16 units, so a character outside the Basic Multilingual Plane doesn't shift the marks.
- **Reader files:** a footnote's `page_starts` and `page_breaks` are per paragraph, in the order of its `paragraphs`. Paragraphs with a null `id` are section headings.
- **Per curiam:** `authors` is empty and `joined_by_source` says so. Write "per curiam". When `joined_by_source` is "not printed", an empty `joined_by` means **unknown**, never "joined by nobody" (P1.18).
- **A refused submit** may show "[statement withheld: it repeated a page's words]" in place of a statement (P4.3). Show it as it is.
- **The band** never shows page text, only titles, domains, URLs and dates as written (T2.2): "published <date> (Exa's estimate)".
- **`api_fragment`** events carry the exact JSON for "View API calls" (T4.3(7)). Show them as they are; never rebuild them.
- **Costs (T4.5):** one total line for Claude and Exa from `run_ended.totals`, expandable into the loop, the answer and Exa. Voyage is not shown.
- **Replays (brief §7.4, T5.6):** later, from `replays/index.json` and `replays/<slug>.json`, served by the web service, never by the API. The fixture set includes one replay to build against.
- **The wake protocol (contract §5.1):**
  - one `/health` check in flight at a time;
  - anything that isn't our JSON means the server is still starting;
  - a fresh `/health` right before `POST /runs`, which is **never retried automatically**;
  - the long-wait steps at `LONG_WAIT_S` and `WAKE_GIVE_UP_S`;
  - heartbeats every `HEARTBEAT_INTERVAL_S`;
  - a reconnect after `PAGE_WATCHDOG_S` of silence;
  - the run ID in sessionStorage.
  - All of these figures come from `config.json`, never typed into the code.

## 6. How to check

- **Node's built-in test runner, no dependencies (T4.2),** with tests under `webdev/`. Test at least:
  - the stream client: ordering, reconnect from `Last-Event-ID`, the watchdog;
  - the renderer: citations to sentence ranges, flags across blocks, the code-point offsets;
  - the straddle fallback: a citation crossing Markdown structure is shown as plain text, with its underline and link intact (T1.11).
- **Every fixture plays end to end** in the browser pane with no console errors.
- **Sizes:** check every view at 1440×900, 393×852 and 852×393 (T4.1), with no horizontal scroll.
  - Measure by element rectangles (`getBoundingClientRect`, `scrollWidth` against `clientWidth`), not by eye.
  - Bring the tab to the front first.
  - Check dark mode too.
- **No request to any origin but the page's own.** Check it in the network panel.
- **Wording rules** (brief §10.6): the status word is "working"; never "exhaustive", "comprehensive", "settled law", "guaranteed accurate", "citator" (except in "not a citator") or "no hallucinations".

## 7. Your log

`docs/sessions/frontend-log.md`, append-only, in `BUILD_LOG.md`'s entry format (brief §10.2), with headings like `## <date and time> — Mock frontend: <short name>`.
- Run `TZ=America/Chicago date "+%b %-d, %Y, %H:%M %Z"` right before each heading, never estimating a time. Commit right after appending.
- Write an entry at the end of each sitting and whenever the user decides something. The DECISION line records only the user's judgement, quoted.
- The main session folds your entries into `BUILD_LOG.md` and `locked-decisions.md`. Don't number decisions.

## 8. Stop and ask the user when

- You are ready to propose how you'll split the modules and the mock, before building.
- A fixture, the schema or the contract can't express something the page must show. Describe it, and let the main session change the shared file.
- Any wording is needed that T5.1 to T5.6 don't give.
- The page is ready for the user's local review.
- An instruction can be read two ways: say in one line how you read it, and wait (brief §0).
