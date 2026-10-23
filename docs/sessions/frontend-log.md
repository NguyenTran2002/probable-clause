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
