# The frontend build plan: the real page, built and stood up by the main session

*Proposed Oct 25, 2026 by the main session; **approved by the user at 16:49 CDT** ("The frontend plan looks good. Approved."), P4.33. After the compaction, the main session follows it from step 1. Nothing in it spends money until step 9, the user's local review.*

## What is being built, and against what

The real page under `web/`, carried forward from the approved prototype `web/looktests/machinery/` (T4.1, commit badc05f), against **contract v2.0**. The binding sources, in order:
1. `docs/design/locked-decisions.md`:
   - T4.1 to T4.5 (the look, the stack, the seven changes, the new pieces, costs);
   - T5.1 to T5.6 (every wording, final text);
   - P4.18 to P4.32 (Wave 3).
2. `docs/design/contract.md` v2.0:
   - §5 and §5.1 (endpoints, the wake protocol);
   - §6 (every event; the page places events by `step`);
   - §11 (reader files, replays, `corpus.json`, `config.json`);
   - `contracts/events.schema.json`.
3. `docs/sessions/frontend-brief.md` §4 to §6 (what to build, the details easy to miss, how to check) and §5a (what v2.0 changed). It was written for the frontend session; from P4.28 it is the main session's spec.
4. The 39 event fixtures and 20 HTTP fixtures in `tests/fixtures/` (v2.0, the real backend's output), with their README.

**The page is the honesty layer for a visitor:** citations light only the sentences the API returned, flags show where our checks failed, withheld text stays withheld, and no web page text is ever shown. Those paths get their own review (step 8).

## Rules for this build

- **The main session writes `web/` and `webdev/` (P4.28),** with no parallel builders. Fresh subagents only review, Sonnet 5.5 or Opus 5.5 at high or xhigh effort, never max (P4.1). They never commit.
- **The stack is T4.2's:** plain ES modules, no build step, markdown-it vendored at an exact version, text inserted as text (never markup built from strings holding visitor, Claude, corpus or web content), Node's built-in test runner. What is under `web/` is exactly what is served.
- **Every figure comes from `config.json`** (generated from `api/settings.py`), never typed into the code.
- **Every wording is T5's, exactly.** Where T5 has none, the main session writes it under P4.31, logs it, and the user refines afterwards.
- **No request to any origin but the page's own:** the fonts are self-hosted (T5.5), with no CDN at run time.
- **No `.png`, `.jpg` or `.jpeg` file is committed** (P0.4). The screenshots used to check the page stay in the scratchpad.
- **The lock pattern** and `date` before every time written, as always. One BUILD_LOG entry per sitting, plus one per user decision.

## Step 0: the calls P4.31 leaves to the main session (made and logged at the start, refined by the user later)

1. **The update step on the page.**
   - In the step log, research's steps come first. Once research ends, the steps branch into two groups side by side in time but stacked on the page:
     - **"Writing the answer"**, the composition;
     - **"Update check, running beside the answer"**, the update step's rounds, searches and submit.
   - Events go to their group by `step`, whatever order they arrive in. Each group shows its own spinner and closes on its own end, or on `run_ended`.
   - The band stays where T4.3 puts it, in the conversation beside the answer. It fills in when `update_band` arrives, which may come before or after the answer is done.
   - This is the main session's reading of brief §5a's "two lanes, or grouped after research". It is narrower than two lanes and fits the prototype's single column at phone width.
2. **The update band's new unavailable reasons**, beside T5.3's two. Drafts:
   - the round limit: *"Update check unavailable: it stopped at its step limit before summarising."*;
   - the time limit: *"…: the run reached its time limit first."*;
   - the token limits: *"…: it reached its token limit."*;
   - the spend limit: *"…: this site's monthly API spending limit was reached."*;
   - another error: *"…: the check failed (<reason>)."*

   `declined` is dropped (P4.19). T5.3's fixed line reads its figures from `config.json` (5 searches now, P4.18).
3. **`busy`:** shown where T4.4 places a `POST /runs` refusal (the run's last step), worded as contract §5's text: *"Five questions are being researched right now, the most this site handles at once. Please try again in a minute."* The number is in words, from `config.json`.
4. **The cost line (T4.5, T5.2):**
   - the total line unchanged;
   - expanded, it splits into research, the update check, the answer and Exa;
   - T5.1's credits name Sonnet 5.5 for the answers (T1.8 follows P4.20).
5. **Withheld text** (contract §4.G.2) is shown as it is, in the step log's muted style, never styled as an error.
6. **`config.json` gains** `UPDATE_SEARCHES_PER_RUN`, `EXA_NUM_RESULTS_DEFAULT`, `EXA_TEXT_CHARS`, `MAX_CONCURRENT_RUNS` and `RUN_DEADLINE_S`, which the wording needs (B's `api/corpus/web_data.py` list, edited by the main session).

## Step 1: the ground (the main session)

1. **Two downloads, on the user's OK:** each named with its source, exact version and size before it is fetched.
   - **The three font families** as `.woff2` with their SIL Open Font License texts, from the official google/fonts repository: Instrument Sans, Newsreader and JetBrains Mono, only the weights the prototype uses.
   - **markdown-it** at an exact version, with its licence, from the npm registry.
2. **The skeleton:**
   - `web/index.html` from the prototype's markup, the switcher banner and the `?v=` strings dropped (T4.1);
   - `web/css/` from its stylesheet, `@font-face` pointing at `web/fonts/`;
   - `web/js/` split by concern (below).
3. **`webdev/`:**
   - **the mock server:** Python standard library, port 8765, serving `web/`, the generated files at the site root, and the contract §5 endpoints played from the fixtures, with a dev-only switch for which fixture `POST /runs` plays and for each failure answer (brief §4);
   - **the Node tests.**

**The modules (`web/js/`), one concern each:**

| Module | Concern |
|---|---|
| `dom.js` | creating elements and setting text; no `innerHTML` with content |
| `text.js` | every T5 wording, in one place, with the figures filled from `config.json` |
| `config.js` | loading `config.json` and `corpus.json` |
| `wake.js` | the wake protocol (§5.1): one check in flight, anything not our JSON means "still starting", the long-wait and give-up steps |
| `stream.js` | the SSE client: `Last-Event-ID` reconnects, the watchdog, heartbeats, the run ID in sessionStorage, reload back into the run |
| `model.js` | the run's state built from events, by `step`, with no DOM; Node-tested over every fixture |
| `steps.js` | the step log: research, then the two groups |
| `sources.js` | the cards: Found, Kept, cited or not, hues in keep order, footnotes folded (T4.3) |
| `answer.js` | markdown-it, the citations' underlines and lit sentence ranges, the straddle fallback (T1.11), flags with code-point to UTF-16 offsets |
| `band.js` | the update check band (T4.3, T5.3) |
| `costs.js` | the cost line |
| `apicalls.js` | the "View API calls" modal, from the exact fragments |
| `reader.js` | the "View source" reader, fetching `opinions/<id>.json` |
| `replay.js` | replays at the recorded pace, "Skip to the end" |
| `main.js` | wiring: landing, run screen, one question per run |

## Steps 2 to 7: the build, in this order

2. **`model.js` first, with its Node tests:** every fixture's events produce the expected run state:
   - sources and their states;
   - steps by step, including the cancelled branch with no `update_ended`;
   - citations as sentence ranges;
   - flags across blocks;
   - the band;
   - the totals.

   This is where most bugs would hide, and it needs no browser.
3. **The landing page and the run screen:** the glide from the question box to the conversation, the status line, the composer, the one-question-per-run line, and the step log with its two groups.
4. **Sources and the answer** (the honesty-critical part):
   - cards;
   - cited sentences underlined in their passage's hue;
   - hover or tap lights the exact cited sentences inside the paragraph, with the connecting line;
   - the answer key, the passage-ID pills and the straddle fallback;
   - the check flags with their wavy underline and the summary line.
5. **The band, the checks line, the stop labels, no-sources replies, the Voyage warning and the cost line.**
6. **The two modals:** "View API calls" (the exact fragments and each response's `usage`, opening at the citation) and "View source" (the whole opinion, page numbers in the margin, the excerpt centred and lit, "Back to the excerpt", the reader's credit line and the text-status note).
7. **Every other state**, each driven by its fixture or HTTP answer through the mock:
   - waking, the long wait and give up;
   - paused for the day or month;
   - Atlas unreachable;
   - `busy`;
   - reconnecting;
   - paused and resumed;
   - abandoned, interrupted, expired;
   - retries and failures;
   - refusal, spend limit, rejected submits, wrong-step calls;
   - replays (the fixture replay; the real ones are recorded later, P4.32);
   - reload back into a run.

**Checks along the way (brief §6):**
- every fixture plays end to end in the browser pane with no console errors;
- the Node tests pass;
- every view at 1440×900, 393×852 and 852×393, in light and dark, with no horizontal scroll, measured by element rectangles;
- no request to another origin, checked in the network panel;
- the wording rules (brief §10.6);
- the whole Python suite still passes, since `tests/contract/` validates the fixtures the mock plays.

## Step 8: reviews by fresh agents, read-only

- **The honesty paths** (Opus 5.5, xhigh):
  - citations light exactly the sentences the event names and nothing else;
  - the code-point offsets of flags;
  - the straddle fallback;
  - withheld text never "restored";
  - no web page text anywhere;
  - text never inserted as markup;
  - links only from Exa's URL fields, with `noopener noreferrer`;
  - every T5 wording used exactly.
- **The states, layout and accessibility** (Sonnet 5.5, high): every fixture's state, the three sizes and dark mode, keyboard and focus in the modals, screen-reader labels.

The main session checks each finding, fixes or queues it, and commits `web/` and `webdev/` by path after each review.

## Step 9: standing it up locally for the user (P4.1, as clarified at 16:38)

1. **`deploy/local.sh`** builds both images and runs them:
   - the API on port 8000 with `PC_ENV=test`, so live runs go to `Probable_Clause_test` and are paid with the development key;
   - the web service on port 8080, its local nginx profile proxying `/api/` to the API.

   The web image's page guard then passes: `index.html`, the fonts with their licence and the generated files are present.
2. **Recorded runs during the review:** the real replays are recorded after it (P4.32), so the chips play the fixture replay from a local-only `replays/` folder, never committed.
3. **The user tests it as a visitor.** Each question is a real paid run, about $0.18 to $0.25 for an answered one. P4.22's allowance has $2.46 and 17 Exa searches left; if the user wants more room for testing, the main session asks for a new allowance first. The test database's $15 daily cap also applies.
4. **The user's sign-off,** in their words, logged. The deploy green light is separate (P4.1).

## After the sign-off (not part of this plan; listed so nothing is lost)

- **The replays (P4.32):** T5.6's five, recorded on the final code, about $2 to $3, each reviewed by the user, exported to `replays/`.
- **The cloud setup script (P4.30),** written then; run only with the deploy green light.
- **The goodnight block (P4.26),** in `~/Documents/Developer/framedbytran`, shown to the user; live only with the deploy green light.
- **The deploy itself,** on its own green light.

## What waits for the user

- **Now:** approval of this plan. Then the compaction.
- **In step 1:** the OK for the two downloads.
- **In step 9:** a new allowance only if the remaining $2.46 is too little for the testing wanted, then the sign-off.
- **Afterwards:** refinements to the step 0 calls.
