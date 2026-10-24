# Frontend session log

Append-only. Kept by the frontend session (locked-decisions P0.3, P1.6), in the entry format of brief §10.2. The main session folds these entries into `BUILD_LOG.md` and `locked-decisions.md`.

---

## Oct 23, 2026, 17:34 CDT — Look tests: three directions built
**Asked:** Read `docs/sessions/frontend-brief.md` and follow it as the frontend session. After the proposal of three looks: build them.
**Came back:**
- Proposed three looks before building: Slip opinion, Cover stock, Evidence log. Read the "no real-looking citation on invented text" rule as: every case fictional and obviously so (for example *Exemplar v. United States*, 000 U.S. 101 (1967)), fictional justices named for trees, passage text bracketed as sample, web sources on example.com, .org and .net.
- Built under `web/looktests/`:
  - `index.html`, linking all three.
  - Per look, an `index.html` (the full sample run) and a `states.html`, each with its own `style.css`.
  - Every look renders the same run: two corpus searches with queries; two reviews; a rejected `submit_answer` shown as a step; an update search with every parameter; the accepted submit; the composition step; the update-check band (Claude's summary plus links, never quoted text); and the answer.
  - The answer shows cited sentences linked to passages, uncited synthesis marked as Claude's, and a verifier flag on *Phantom v. United States*.
  - Seven passages cover majority, plurality, concurrence, dissent and a syllabus (labelled as the Reporter's, "no part of the opinion of the Court"). One case is a slip opinion carrying the revision note.
  - Each passage carries case, citation, decision date, opinion type, author, joiners, the retrieving query and the narrow guarantee sentence.
  - Every notice the brief lists has a place: not legal advice, not a citator, not exhaustive, AI disclosure, independent checking, coverage line, Free Law Project credit with non-endorsement, unofficial-text status, Claude credit, non-affiliation, and the about-a-day privacy note. All wording is the brief's drafts, marked placeholder on every page.
  - The states pages show waking up (elapsed time, no duration promised), working, reconnecting then caught up, interrupted, cap reached, stopped at the step limit, update check declined after reminder with a sample reason, update check unavailable, and replay with its date.
- The looks:
  1. **Slip opinion.** White paper and black ink. Old Standard TT stands in for the Century family that Rule 33.1(b) names for briefs, since Century Schoolbook is not on Google Fonts. Small-caps justices and footnote markers in the answer. The "l" and links are a proofreader's blue (#2348a8). Passages sit in a margin beside the search that found them; on a phone, they sit inline under it.
  2. **Cover stock.** Colours from the brief covers in Supreme Court Rule 33.1, checked on Cornell LII's copy of the rule on Oct 23, 2026. Each colour marks one kind of text: light blue for opinion, tan for syllabus, yellow for the web check, light green for Claude's synthesis, orange for not accepted, light red for a name not found, and gray for notices. The "l" is dark green. Kept and discarded are shown by shape and words, not colour. Public Sans with Source Serif 4. On a phone, a sticky Research/Passages switch.
  3. **Evidence log.** A timed log, with passages as exhibits on manila tags stamped kept or discarded. The syllabus is on a gray tag, and the web check sits in a dashed outside box. Archivo with its width axis; the "l" is ochre (#a87412). On a phone, the exhibits sit in a bottom sheet with a running count.
- No JavaScript anywhere. The phone switch and the bottom sheet run on links and `:target`/`:has()`, and a passage link in the answer opens its pane.
- Checked with element rectangles, served from `python3 -m http.server 8765`. All 7 pages at 1440×900, 393×852 and 852×393: `scrollWidth` equals `clientWidth` on every one, and no element extends past the viewport. The phone switch, the bottom sheet, and passage links opening their pane were checked by setting the hash and reading rectangles.
- Fonts, all from Google Fonts, all SIL Open Font License (OFL), per each family's METADATA.pb in the google/fonts repository: Old Standard TT, Public Sans, Source Serif 4, Archivo. No script libraries.
- Wording grep: none of the banned words; "live" only in "live research" and "live run"; no em dashes; no absolute paths; no image files.
**Failures:**
- The Write hook opened each new file as a `file://` or `data:` tab without its stylesheet. That confused one screenshot until I closed those tabs and measured only the served tab.
- Old Standard TT rendered bold italic case names as synthesized until weight 1,700 was requested.
- In look 3, a `.tag` class name clashed with the synthesis label; renamed to `.synth-label` before anything rendered wrong.
**DECISION (user):** Approved the proposal as made: *"Build the three looks as proposed."* No direction picked yet.

## Oct 23, 2026, 19:04 CDT — Look tests: the machinery prototype
**Asked:**
- The user set the three looks aside and restated the vision: a tech demo first, legal in flavour. The audience is technical people coming to see Claude and Citations at work. It should be sleek, modern, easy to follow and catchy, with a landing page that turns into the research view when a question is typed or a recorded-run chip is clicked.
- After discussion, the user asked for a prototype that shows the raw API and the machinery underneath, to find the right balance by seeing it.
- Then the user asked me to check the Citations docs on citation granularity, and to make the prototype handle both paragraph and sentence citations.
**Came back:**
- `web/looktests/machinery/` (`index.html`, `style.css`, `run.js`), a throwaway prototype, linked from `web/looktests/index.html`:
  - **Landing page:** the wordmark, one line on what the demo does, a question box, three recorded-run chips, and a small figure following one citation from the answer, to the cited text in a kept passage, to the block in the API response.
  - **The transition:** submitting a question or clicking a chip moves the question box into the run view's header, using the View Transitions API, which falls back to an instant swap.
  - **The run:** a scripted sample plays out live. Steps appear with Claude's own words between tool calls. Passages arrive, then are marked kept or discarded. The rejected submit, the web update check with every parameter, the accepted submit, and the answer streaming word by word. Then our case-name check flags *Phantom v. United States*. There is a "Skip to the end" button.
  - **A switch between three views:**
    - **Plain:** the product alone.
    - **Annotated:** adds each tool call as a line of code, which block of the answer each sentence is, and block numbers inside passages.
    - **API traffic:** adds a dark third column with every request and response, in Messages API shapes with sample values. Each request shows only the message new to it. Web result page text is withheld from the column (P1.3).
  - **Each kept passage has its own colour.** Clicking or hovering a cited sentence draws a thread in that colour, from the sentence, to the cited text in the passage, to its citation block in the response.
  - **Type:** Instrument Sans for the product, Newsreader for court text, JetBrains Mono for the API. All three are from Google Fonts under the SIL Open Font License.
  - **Script:** plain JavaScript, no library and no build step. The brief asks for as little as possible; a live run and the transition can't be done without some.
- **Citation granularity, checked against the docs on Oct 23, 2026:**
  - The Citations page says plain text and PDF documents are chunked into sentences ("sentence chunking lets Claude cite a single sentence or chain together multiple consecutive sentences"). Custom content documents use the provided blocks "as-is".
  - The search results page says of `search_result` blocks, which the brief's `search_corpus` returns: "The text block is the minimal citable unit: Claude cites whole blocks, not substrings within a block. To get finer-grained citations, split your search result content into smaller blocks." `cited_text` is "The full text of the cited block(s), concatenated."
  - So with one paragraph per text block, as the brief has it, citations are whole paragraphs. Splitting a passage into one block per sentence would give sentence citations and keep everything else. That choice is the backend's.
- **The prototype now handles both, with one rendering path:**
  - Each passage is a list of text blocks. Each citation is a passage ID plus a block range `[start, end)`, as `search_result_location` reports it.
  - The cited range is highlighted inside its paragraph, with the rest dimmed but readable.
  - The mock data has both kinds. P-01, P-05 and P-07 are sentence blocks: one citation is a single sentence, another chains two sentences. P-02, P-03, P-04 and P-06 are single paragraph blocks.
  - The frontend splits no sentences.
- **ASSUMPTION for the Phase 3 interfaces contract (not a locked decision):** a passage reaches the frontend as an ordered list of text blocks, exactly as sent in the `search_result`'s `content`, so that concatenating them reproduces the passage. A citation reaches it as a passage ID plus `start_block_index` and `end_block_index`, end exclusive. Paragraph mode is one block per passage. The frontend never splits text itself.
- **Checked** with element rectangles at 1440×900, 393×852 and 852×393, in every view and pane:
  - No horizontal scroll, and no element outside the viewport.
  - On a phone, tapping a cited sentence opens Sources with the cited range in view.
- Wording grep is clean: none of the banned words, no em dashes, no absolute paths.
**Failures:**
- Chrome cancelled one of two smooth `scrollIntoView` calls made at once on different panes, so the passage never scrolled into view. Replaced with a per-pane scroll.
- Switching panes on a phone replayed every entry animation. Now only newly arrived content animates.
- The citation list was defined before the answer data, which stopped the script loading. Moved it after the data.
- The thread's endpoint landed under a sticky column header. It is now clamped below the header.
**DECISION (user):**
- The vision, in the user's words: *"The demo is legal flavor, but it's a TECH demo foremost."* *"I want sleek, modern, easy to follow and catchy, all the good UXUI principles that will hold a person's attention to see the tech in action."* *"We would want a very intuitive and impressive landing page that transitions into the research UXUI after a natural language request is typed in, or an user clicking a chip of a recorded request."*
- The audience: *"most likely a technical person, looking to see Claude and Claude Citations in action."* When the answer finishes, *"they should be thinking that Claude Citation is a really neat feature that can be easily and effectively incorporated into my systems."*
- On showing the machinery: *"Showing the raw API and underneath machinery might actually be a great thing. Let's prototype it up first because it would be hard to find the right balance without seeing it visually."*
- On granularity: sentence blocks are *"Not yet on the backend; that's the main session's call. But build the prototype to handle both"*. One rendering path with no mode switch, the cited range highlighted in context, no sentence splitting in the frontend, mock passages of both kinds. *"Record this shape as an assumption for the Phase 3 interfaces contract, not a locked decision."*
- No direction picked yet. The user has not yet said which of Plain, Annotated and API traffic is closest to right.

## Oct 23, 2026, 19:31 CDT — Look tests: prototype polish (chat layout, API window, palettes)
**Asked:** Six polish items on the machinery prototype:
1. When hovering a cited sentence, scroll the sources to it.
2. Stop the question jumping to the header when a run starts.
3. A familiar chat layout that moves up step by step.
4. Replace the Plain, Annotated and API traffic switch with a labelled button on each source that opens a window with the API traffic and the rendered source.
5. Mock up a few colour palettes, with dark mode that follows the system.
6. Fix the kept stripe sticking out past the card's rounded corner.
**Came back:**
- **Chat layout.**
  - On submit, the landing question box glides down to become the composer at the bottom of the conversation (View Transitions API, with an instant swap as fallback). The question appears as a message bubble just above it.
  - The conversation is anchored to the bottom, so steps, the update check and the answer stack up from the composer and push earlier content upward.
  - While the run works, the composer is disabled, with the status line above it and a "Skip to the end" button. When the run finishes, the composer takes a new question.
  - The header now holds only the wordmark.
  - The notices sit under the composer: the not-legal-advice, not-a-citator, not-exhaustive and AI lines, with source credits and coverage under "Sources and credits".
- **Hover.** Hovering a cited sentence lights the cited blocks in their paragraph and scrolls the Sources pane to them, but only if they are out of view. The thread now starts at the answer column's right edge, so it no longer crosses the following text.
- **API window.**
  - The view switch is gone. Each source card has a "View API calls" button that opens a modal: the rendered source on the left (cited ranges lit), and on the right, in order, every exchange that touched that passage. These are:
    1. the search call
    2. the tool result carrying the passage's text blocks
    3. the keep or discard decision
    4. the refused submit and its error result
    5. the accepted submit
    6. the passage's place in the composition call, with its `search_result_index`
    7. each answer block that cites it, with the `search_result_location`
  - A discarded passage ends with a note that the composition call never saw it.
  - On a phone the modal is full screen and stacked.
- **Palettes.** Three options, switchable from the prototype banner along with System, Light or Dark (remembered per browser):
  - **Cobalt:** cool blue-grey neutrals, cobalt accent.
  - **Evergreen:** green-grey neutrals, deep green accent.
  - **Violet:** violet-grey neutrals, violet accent.
- **How the palettes are built.** Each is defined in OKLCH from a single hue that tints the neutrals and sets the accent. Four source hues share one lightness and chroma, so no kept passage looks louder than another, and red is kept for the verifier flag. Dark mode follows `prefers-color-scheme` unless the viewer picks Light or Dark.
- **Card edge.** The kept stripe is now the card's own left border, so it follows the rounded corners.
- **Checked** with element rectangles at 1440×900, 393×852 and 852×393:
  - No horizontal scroll on the landing page, the conversation, the sources or the modal.
  - On a phone, tapping a cited sentence opens Sources with the cited range in view.
  - Sideways, the conversation keeps 210 px: there the notice line shortens to its first sentence and the banner shows only its controls.
- Wording grep is clean.
**Failures:**
- On a phone, the modal measured 6 px short of the screen. It was caught mid-animation; the computed size is the full screen. The browser's `dialog:modal` size limits needed an id selector to override.
- Calling the saved-palette restore before the thread state existed would have thrown, so the restore moved to the end of the script.
- Sideways, the first layout left the conversation 127 px tall.
**DECISION (user):** *"This is a very good start."* Then, in the user's words: hovering a cited sentence should make *"the right hand section … scroll to the right source on hover"*; the question being *"teleported all the way to the header … can be confusing"*; *"I'd want a familiar chat UI, where things start moving up a bit by a bit as more steps are taken"*; *"getting rid of the Plain, Annotated, and API traffic toggle to declutter. Instead, for each source, there should be a clearly labeled button that will display the request and response that led to that citation, ideally in a modal"* showing *"both API traffics and the rendered source"*; *"No coherent color palette. Mock up a few options? I want automatic dark mode handling as well that follow system's settings."*; and the stripe *"protruding further than the rounded border"* is *"jarring if unfixed."* No palette picked yet.

## Oct 23, 2026, 19:50 CDT — Look tests: Evergreen chosen; layout bug, outline, API window, answer key
**Asked:** Make Evergreen the palette. Then four polish items: the lit outline was not flush with the stripe; the API window used too much vertical space; at the start of a run the Sources panel did not reach the bottom and the composer did not sit at the bottom; and the synthesis tags made the answer hard to read. Also a check that decisions are being recorded with correct times.
**Came back:**
- **Layout bug (found by measuring the grid):**
  - Cause: the run view has three grid rows: header, phone tab bar, panes. On desktop the tab bar is hidden, so the panes were auto-placed into the tab bar's row, which sizes to its content. The empty third row took the rest of the screen. Measured rows: 53, 302 and 504 px, with the panes in the 302 px row. This only showed while the panes were short, at the start of a run.
  - Fix: each part is pinned to its own row. At the start of a run the composer now ends at the viewport bottom (852 of 852 on a phone, and at the bottom on desktop), and the Sources panel runs full height.
- **Card edges (inspected at 8× by rendering a copy of the card with CSS `zoom: 8`):**
  - Unlit: the border is one colour all the way round, tinted with the passage's hue for kept cards, so no corner has a colour seam. The stripe is an inset shadow that follows the inner curve and thins to nothing.
  - Lit: a single border, 2 px with a 5 px left side, and no shadows. Both tries that combined a border with a ring or an inset stripe left an antialiased hairline where the shapes met.
  - Padding gives back the extra width: the text offset and card size measured identical lit and unlit (20.2 and 15.4 px offsets; 399 by 398.7 px).
- **API window:**
  - Height is capped at 36rem (it was close to the full screen), with tighter header and padding.
  - Each exchange is a one-line row with a preview of what it carried, and opens on click. The citation opens by default; for a discarded passage, the discard decision does.
  - JSON keeps objects up to 84 characters on one line.
  - On a phone it stays full screen.
- **Answer:**
  - The "Claude's synthesis, no source" tags are gone, and synthesis is no longer greyed. The answer reads as plain prose with cited sentences underlined in their passage's colour.
  - A key under the heading reads: "Underlined sentences rest on a passage Claude kept; hover or tap one to see the exact text it cites. Sentences without a line are Claude's own synthesis and have no source." The wording is a placeholder.
- **Evergreen** is now the default. The palette is saved under a new storage key so everyone starts on Evergreen. Cobalt and Violet stay in the banner switcher for now.
- **Stylesheet and script now carry a version query (`?v=8`).** Browsers had been showing a stale copy, which is why an earlier screenshot showed old content.
- **Checked:**
  - 1440×900, 393×852 and 852×393: no horizontal scroll on the conversation, the sources or the modal.
  - The only element measured past the edge is a preview line clipped by its own ellipsis.
**Failures:** Two attempts at the lit outline, a ring and then an inset stripe, each left a hairline at 8× before the single-border version.
**Correction to earlier entries (append-only, so noted here):**
- The 19:04 entry paraphrased, but did not quote, the user rejecting the three looks. The user's words were: *"These all looks pretty bad. (That's why I compacted to keep the context lean and less influenced by past works.)"* and *"Let's zoom out a bit and let me clarify the vision"*.
- The decisions in the 19:04 entry were made across several turns between 17:34 and 19:04 and recorded together. Its heading time is when the entry was written, not when each decision was made.
**DECISION (user):**
- Palette: *"I like evergreen to help keep the eye strain down while reading thru text heavy legal docs."*
- On the answer: *"present the answer normally, with cited sentences highlighted appropriately, where as not highlighted sentences are assumed to be Claude's synthesis. We can guide the user right underneath the Answer header which sentence is synthesis and which is supported by citation."*
- On the outline: *"use code to investigate and ensure everything smoothes into each other perfectly."*
- On the API window: *"The API modal is using too much vertical space, decrease it."*
- On the layout bug: called it a *"Critical display bug"* and *"jarring"*.

## Oct 23, 2026, 20:03 CDT — Look tests: wider conversation; source reader
**Asked:** On desktop, widen the conversation by 50%, growing equally on both sides. Next to each source's "View API calls", add a "View source" button that opens a reader modal with the whole text, starting at the cited excerpt.
**Came back:**
- **Width.** The conversation's maximum width went from 46rem to 69rem, and the composer's from 41rem to 61.5rem, both centred.
  - At 1440 px wide the column beside Sources is 1008 px, so the conversation now fills that column: 1008 px, up from 736 px (46rem).
  - The full 69rem shows only on wider screens.
  - Answer lines at 1440 px run to about 928 px.
- **"View source" reader.** Each source card has a "View source" button (¶) beside "View API calls".
  - It opens a reader modal holding the whole opinion the passage came from:
    - a heading and byline in the Court's form (for example "Justice Sycamore, with whom Justice Tamarind joins, concurring.")
    - the paragraphs
    - page numbers in the left margin, as in the printed reports, set so the excerpt lands on its pinpoint page
    - a closing note on unofficial text, plus the slip-opinion note where it applies
  - The modal opens scrolled so the retrieved passage is centred, set off in its passage colour. The sentences the answer cites are lit and the rest of the passage is dimmed, so the cited text is read in context. A discarded passage is shown in grey and labelled "later discarded".
  - A "Back to the excerpt" button returns to it after scrolling.
  - On a phone the reader is full screen, and page numbers sit above their paragraph as "U.S. Reports page 318".
  - The text is mock: every paragraph except the retrieved passage is a labelled placeholder until Phase 1's corpus is ready. A syllabus passage opens the syllabus, with the Reporter's label.
- **ASSUMPTION for the Phase 3 interfaces contract (not a locked decision):** the reader needs, for each passage, the full text of the opinion or syllabus it came from, the passage's position in it, and page breaks with page numbers if Phase 1 finds them (brief §4.4 test 3). If there are no page breaks, the reader drops the margin numbers.
- **Checked** at 1440×900, 393×852 and 852×393:
  - No horizontal scroll on the conversation, sources or reader.
  - On desktop the excerpt opens centred in the reader (measured 290 to 470 px in a 759 px viewport).
**Failures:** None.
**DECISION (user):** *"Good improvements."* Then: *"On desktop, increase the amount of width that the chat interface uses by 50% to both sizes."* Read as 50% wider overall, growing equally on both sides. Also: *"For each source, next to View API calls buttons, have a View Source button that will open a reader modal that lets the user scroll thru the whole actual text, starting from the cited excerpt."*

## Oct 23, 2026, 20:13 CDT — Look tests: 25% chat width shared with the landing page; API window opens at the citation; reader page numbers
**Asked:**
- Change the conversation's growth from 50% to 25% over the original width, equally on both sides.
- Make the landing page use the same width as the conversation, for the input box and all its text.
- Make "View API calls" open scrolled to the response that produced the citation.
- Fix the reader's page number being clipped by the excerpt box.
**Came back:**
- **One width token** (`--chat: 51.25rem`, 820 px) now sets the reading width everywhere: the conversation, the composer, and every landing block (wordmark, pitch, input, recorded-run chips, the trace figure, the fine print).
  - It is the original content width (41rem, 656 px) plus 25%.
  - Measured at 1440 px: landing blocks, steps, answer and composer are all 820 px wide and share one left edge.
  - The conversation's side gutters stay outside that width, so the composer and the text above it now line up exactly. Before, the composer had been a little narrower than the text.
- **API window** opens scrolled to the last open exchange:
  - for a cited passage, "Claude cited it in the answer";
  - for a discarded passage, the discard decision;
  - otherwise, the latest exchange.
  - On desktop the traffic column scrolls (measured at its maximum, with the citation 63 px below its top). On a phone and sideways, where the whole modal body scrolls, that body scrolls instead.
- **Reader page numbers.**
  - Cause of the clipping: the excerpt box extends 1.1rem into the left margin, where the page numbers sit.
  - Margin numbers now end 1.85rem left of the text. The excerpt's own page number hangs outside its box in the same column: measured 12 px clear of the box and aligned with the other numbers.
  - The reader keeps 5.25rem of side room on desktop so the numbers never meet the modal edge, even at 800 px wide.
- **Checked** at 1440×900, 800×700, 393×852 and 852×393: no horizontal scroll on the landing page, conversation, sources, API window or reader.
**Failures:** The first version of the scroll-to-citation worked on desktop only. On a phone the traffic column doesn't scroll on its own. Fixed by scrolling whichever part actually scrolls.
**DECISION (user):** *"You understood my 50% request correctly. I changed my mind, however, I want only 25% growth overall to both sides compared to the original width now."*
- *"I want in the landing page, the width we use to match the width we use in the chat UI, not just for the text input box but also for the text presented on this landing page."*
- *"View API calls button after opening the modal should automatically scroll down to the response that results in the citation, which is at the bottom of the API calls stack usually."*
- *"The view source modal is having some text clipping where you can see the number is being clipped by the drawn box."*
