# Build log

Append-only. Never edit past entries; corrections go in a later entry. Headings come from `date` (America/Chicago), run immediately before writing them.

---

## Oct 23, 2026, 16:23 CDT — Phase 0: Bootstrap

**Asked:** Read the kickoff brief and discuss kicking off the project. Up front, the user proposed that once backend decisions are settled and the main session is implementing, a second Claude Code session iterates on a mock frontend to save time, and asked how to organize two sessions in the same folder that log to and update the same documents. Then: lock the stack and the no-images rule, and start Phase 0.

**Came back:**
- A proposal for the two-session setup: one writer per file (the frontend session writes only `web/` and its own notes file); the mock built against the interfaces contract with a machine-checkable event schema, sharing the replay format; the main session as the only writer of `BUILD_LOG.md`, `locked-decisions.md` and CLAUDE.md, folding in the frontend session's own append-only log; git rules for a shared working tree; start after art direction is locked and contract v1 is committed. Recorded as P0.3.
- git initialized on `main`. First commit `4e518ae`: the brief, unchanged (SHA-256 of the working file and of the committed blob match).
- Scaffold: CLAUDE.md; `docs/design/locked-decisions.md` (P0.1 to P0.3); uv project pinned to Python 3.13 (uv 0.11.29, CPython 3.13.9), no dependencies yet; `.env.example` with `COURTLISTENER_API_TOKEN`, `ANTHROPIC_API_KEY`, `EXA_API_KEY`, `MONGODB_URI`; `.gitignore` covering secrets, raw caches, PDFs and image formats; `.claude/settings.json` denying the agent `Read`, `Edit` and `Write` on `.env` plus common shell reads of it.
- `scripts/check_env.py`: reports set / empty / missing / commented out per variable, never a value; `--phase N` limits the check. Tested against a throwaway file outside the repo (quoted value, commented-out key, empty value, duplicate key). No `.env` exists yet.
- Transcript retention: `cleanupPeriodDays` is not set in the user, local, remote or managed settings, so Claude Code's default cleanup (about 30 days) applies to this session's transcript. Reported to the user; not changed.

**Failures:** None. One self-correction before the first scaffold commit: a `*.jsonl` rule in `.gitignore` (meant for transcripts) was removed, since transcripts live outside the repo and the rule could have hidden corpus files.

**DECISION (user):**
- Stack locked (P0.1): *"On the default stack, I want Python 3.13 with uv and fast api. Lock this. (Open to future adjustment in case something goes wrong, but that would be highly unlikely.)"*
- No images in the repo (P0.2): *"On screenshots or images, we will never commit any to the repo, lock that too."*
- Two-session frontend plan approved (P0.3): *"The plan looks sound to me."*
- *"Start with Phase 0."*

## Oct 23, 2026, 16:54 CDT — Phase 1: Corpus (before the pull: checks and licensing)

**Asked:** Narrow the image block to PNG and JPEG, leave transcript retention alone, run checks now that `.env` is filled (without reading it), and discuss the way forward as a whole: which Phase 1 steps are the user's, exhaustive verification by subagents, pulling all metadata, and whether the frontend mock can start during the pull. Then, as a load-bearing first step: confirm the licence and terms of every source before pulling, since they also shape the frontend.

**Came back:**
- `.gitignore` now blocks only `.png`, `.jpg`, `.jpeg` (P0.4 supersedes P0.2); P0.5 records transcript retention left at the default. CLAUDE.md records the user's CourtListener limits.
- `check_env.py`: all four variables set. `scripts/probe_courtlistener.py`, one authenticated request: cluster 10881683 is *Chatrie v. United States*, decided 2026-06-29, with one sub-opinion (likely a Combined Opinion needing splitting) and no citation. No rate-limit headers are returned.
- P1.1 (exhaustive verification design) and P1.2 (all metadata pulled raw; `scdb_decision_direction` excluded) locked.
- `docs/research/licensing.md`: licences and terms of every source, from three research subagents. The main session re-fetched every page and string-matched every quote (details in the file). Headline findings:
  - Opinions and the syllabus are public domain; West and Lexis editorial matter is not.
  - CourtListener permits this non-commercial use. It forbids implying that Free Law Project endorsed AI analysis.
  - **Exa's terms, read literally, require written permission to display results publicly or store them for replays.**
  - **Anthropic's Usage Policy in force until Nov 12, 2026 treats consumer-facing legal use as high-risk; the Nov 12 version excludes explaining what the law says without applying it to someone's facts.**
  - AI disclosure and an independent-checking notice are required on the page.
  - The Court's own table gives *Chatrie* as 609 U.S. 605.
- Spend: none; one CourtListener request (free).

**Failures:**
- Two of 18 CourtListener quotes did not match at first. One differed only by a space at a link boundary. The other is on SCDB's JavaScript-rendered page and could not be verified.
- The subagent was blocked (403) from courtlistener.com/terms; a direct fetch worked.

**DECISION (user):**
- *"Correction: for image blocking, only count jpeg, jpg, and png. I wouldn't have any image in any other format. The project itself might use svg and ico."* (P0.4)
- *"Transcript retention, leave cleanupPeriodDays alone for now. This project will be done in 2 days."* (P0.5)
- CourtListener limits for the EDU account: *"It's 20 RPM and 1000 RPH for my EDU account."*
- Timing: *"We don't have to commit hard timing plan into docs because I'll keep the time. Your job with time is to mainly log things correctly using system time."*
- *"Verification design with subagents looks good to me."* (P1.1); *"Keeping scdb_decision_direction out is a good catch."* (P1.2)
- *"Let's confirm license of all sources we want to pull and see what we're allowed to do with them first, because this also affects the frontend design as well."*

## Oct 23, 2026, 17:11 CDT — Phase 1: Corpus (decisions on licensing; prep for compaction and the second session)

**Asked:** Discuss three positions on the licensing findings: show only Claude's synthesis of Exa results; the Usage Policy is met because the tool gives no legal advice and discloses AI; credit Claude with plain sentences as in the previous build, whose README the agent was to fetch and read in full. Then: draft the Exa email with an address to send it to; lock all three decisions; don't start Phase 1, prepare for a compaction instead; prepare the ground for a look-test session the user starts, and say where to point it.

**Came back:**
- Read the previous build's README in full (221 lines, fetched with `gh`). It names products only in plain descriptive sentences, opens with a non-affiliation line, uses no logo or badge, and excludes the corpus from its code licence.
- Advice given before locking:
  - Synthesis plus source links removes any republication of web text, but does not by itself satisfy the literal Exa clause, which also lists "modify" and "create derivative works from".
  - The Usage Policy case is stronger resting on what the tool does than on "the user is the human review".
  - The earlier note was too broad: it should have said to avoid a badge-style tagline, not that Claude can't be named.
- Locked P1.3 to P1.6. P1.6 moves the art-direction look tests ahead of Phase 3, into a second session the user starts.
- Exa's contact: the terms name hello@exa.ai six times; support@exa.ai is on its contact and pricing pages. Email drafted for the user to send.
- `docs/sessions/frontend-brief.md`: the frontend session's brief (scope, P0.3 rules, log format, what each look must show, states, notices, checks).
- `scripts/verify_quotes.py`: the quote checker from the licensing research, moved into the repo for Phase 2's re-check.
- CLAUDE.md: two-session rules, layout, and a current-state section written for resuming after compaction.

**Failures:** None.

**DECISION (user):**
- *"Exa, can we only display what Claude synthesize after doing the search? This will avoid directly copying and pasting Exa's returning content."* On the email: *"Hopefully we'll get a response back soon. Otherwise, we proceed as normal."* (P1.3)
- *"On Anthropic's Usage Policy, we have AI disclosure and we don't provide legal advice. It's a research and citation tool, with the user is the human review piece because the project only ever present up evidence."* (P1.4)
- *"On "Built with Claude" wording, I used this phrase in the past that is not trade marked and was just a literal sentence "How this was built with Claude Code" in the README."* (P1.5)
- *"I lock all three decisions here with you"*
- *"Don't proceed with Phase 1 right away, prep the ground for compaction. I will compact this conversation and then give you the signal to proceed with Phase 1 after compaction."*
- *"I want to start the look test session myself, so prep the ground for that session, and let me know where to point that session to kick start it."* (P1.6)

## Oct 23, 2026, 17:17 CDT — Phase 1: Corpus (Exa follow-up, SCDB fields; ready for compaction)

**Asked:** The user emailed Exa; proceed on synthesis plus links without waiting. Give more context on the SCDB fields so the user can decide. Then, with every decision locked, prepare for compaction.

**Came back:**
- P1.7 locked: assume no reply from Exa until the user reports one.
- SCDB context, from CourtListener's `cl/search/models.py` (current `main`, read Oct 23, 2026): clusters carry exactly four SCDB fields. These are `scdb_id`, `scdb_decision_direction` (1 Conservative, 2 Liberal, 3 Unspecifiable), `scdb_votes_majority` and `scdb_votes_minority`.
- Options laid out: exclude entirely; verification only (recommended); show on the page.
- Also flagged: the cluster `headnotes` and `summary` fields may hold commercial-reporter editorial matter. Plan: leave them out unless shown to be official, and report in Phase 1.
- P1.8 locked: SCDB fields are used for verification only.
- CLAUDE.md's current-state section updated for the compaction.

**Failures:** None.

**DECISION (user):**
- *"Emailed Exa. Assume no response from them until I come back with an actual response. We proceed with Claude's summary plus links to the sources."* (P1.7)
- *"Let's use the SCDB fields as verification only."* (P1.8)
- *"If all decisions are locked, prep the ground for compaction."*

## Oct 23, 2026, 17:42 CDT — Phase 1: Corpus (inclusion rule and scope)

**Asked:** Start Phase 1. Then discuss widening the corpus to everything related to the Fourth Amendment ("better to contain extra than missing something"), and a direction of mechanical inclusion, programmatic verification with a few spot checks, and scope enforced by the prompt. Then: how much that would load the database, and how long processing, chunking and embedding would take. Then narrow again, since the goal is showcasing Citations.

**Came back:**
- A proposed three-part inclusion rule resolving the *Riley* tension (part b) and a second one the agent found, *Jardines* (part c), plus the cases the planning draft's wording also catches.
- Four CourtListener search requests (counts only): 984 Supreme Court cases mention "Fourth Amendment"; 329 also quote "unreasonable searches and seizures"; 154 match other phrasings without that phrase; about 1,115 match any phrasing.
- Discussion of widening: agreed in principle at first, with pushback on matching a single phrase and on undefined spot checks; then estimates (unmeasured) for the wide corpus: 10 to 25 million tokens, 50,000 to 125,000 chunks, a pull of about 6 hours, an index that would press against the free Atlas tier. Observed that Claude, not the visitor, writes the search queries, which may make keyword search enough.
- Locked P1.9 (scope and inclusion rule, 21 cases, two-way filter check) and P1.10 (verifier says "not in this corpus").

**Failures:** None. One inconsistency noted: the search counts overlap by about 23 more cases than they should; moot after narrowing.

**DECISION (user):**
- *"I'm considering widening the corpus to anything related to the Fourth Amendment."* Then: *"Let's narrow. The goal of the project is show casing Claude Citation, and it doesn't need a huge corpus to effectively showcase that."*
- Atlas: *"My Atlas cluster is free tier, with only about half of its storage left."*
- *"Thanks for incorporating my suggestions. We can lock here."* (P1.9, P1.10)

## Oct 23, 2026, 18:26 CDT — Phase 1: Corpus (pull, first tests, text sources, cleaning)

**Asked:** Approve the text-source plan and the download of 23 official PDFs; proceed with the pull, the three first tests and cleaning.

**Came back:**
- `scripts/pull_courtlistener.py`: one citation-lookup request, then each case's cluster, docket and opinions, raw, paced at one request every 4 s. 22 cases resolved (21 core plus *Berger* and *Quon* for the filter check), 146 requests. *Riley*'s U.S. citation is not on CourtListener (resolved by S. Ct.). *Goldman*, *Jones* and *Quon* each have two clusters; for *Jones* and *Quon* the second is a Lawyers' Edition scan (commercial), excluded.
- First tests (§4.4):
  - Splitting: the Harvard split holds for the older cases, with labelling errors (*Lopez* splits Brennan's dissent in two; *White* and *On Lee* fold Black's statements into the majority); `joined_by` is empty for every opinion; the five recent cases arrive as one combined slip opinion each.
  - Artifacts: the Harvard scans carry OCR misreadings that §4.5 cannot fix; Lawbox text is clean; the born-digital U.S. Reports PDFs of *Riley*, *Grady* and *Carpenter* drop the letter after "f" in "fi"/"fl" ligatures and have no soft hyphens.
  - Page numbers: U.S. Reports pages for all cases except *Chatrie* (slip pages).
- CourtListener's `date_filed` is wrong for *Ciraolo* and *Florida v. Riley*; dates come from the official text. The `headnotes`, `summary` and `syllabus` fields are empty on all 26 clusters.
- P1.11 locked; `scripts/fetch_official_pdfs.py` downloaded the 23 PDFs (71,180,581 bytes, SHA-256 recorded).
- `scripts/build_corpus.py` with `corpus_common.py` and `corpus_pdf.py`: splits each case on the Court's own headings, records U.S. page breaks and footnote markers as offsets, attaches footnotes to their opinions, and drops running heads, captions and print matter. For the lossy PDFs it restores ligature letters and resolves line-end hyphens only where the Court's slip text of the same case confirms the word in context. Built so far (script counts): 21 cases, 75 opinions, 1,599 paragraphs, 331 footnotes; 450 ligature letters restored; 57 hyphen decisions logged for review.

**Failures:**
- One CourtListener request returned 502 (server error) after 90 requests; re-run by hand, resuming from the cache.
- Splitting needed several fixes, each found by comparing against the Harvard split: headings whose "with whom MR. JUSTICE ..." clause contains periods; a quoted "dissenting, stated" taken as a heading; *Kyllo*'s mixed-case headings; wrapped headings; small capitals split into separate words in the slip PDF. Two role-less headings (Holmes in *Olmstead*; Stone and Frankfurter in *Goldman*) and one statement (Black in *On Lee*) are typed by an explicit table, flagged for verification.
- The first ligature repair assumed whole ligatures were dropped; the font keeps the "f". It also trusted the document's own vocabulary, where the broken forms recur, and produced one wrong repair ("Ayer" to "flAyer"). Fixed before any output was kept.
- Page labels first took the volume number from "Cite as: 573 U. S. 373"; fixed to the standalone page number, and every PDF's labels checked for continuity.

**DECISION (user):**
- *"Approved: use the text-source plan as proposed, and download the 23 official PDFs listed."* (P1.11)

## Oct 23, 2026, 19:52 CDT — Phase 1: Corpus (verification round 1, filter check, rework)

**Asked:** Approve P1.12 and P1.13; then the filter-check additions and *Kyllo*'s switch (P1.14, P1.15) and the download of nine more official PDFs; then four decisions on how to fix what verification found (P1.16 to P1.19).

**Came back:**
- Scripted verification (`scripts/verify_corpus.py`, `scripts/verify_lineup.py`): every corpus paragraph aligned word by word with the official PDF's text layer, each difference labelled by a third copy; punctuation compared; pages checked against the PDF and against Harvard's independent page markers; official text left uncovered listed.
- Manifest and token counts (`scripts/build_manifest.py`): after the additions, 31 core cases, 99 opinions, 598,889 tokens (`claude-sonnet-5-5`, token-counting endpoint, free). Coverage: latest decision June 29, 2026, in the full pull and in the corpus; ingested Oct 23, 2026.
- Two-way filter check (`scripts/filter_check.py`): 235 later Supreme Court cases cite a core case; 51 earlier cases are cited by three or more core cases. An independent agent's own list from the inclusion rule contained all 21 original core cases and proposed *Clinton v. Virginia* (1964), offered to the user after P1.14 was decided.
- Verification round 1: six Opus agents, each given batches of cases and none told the main session's conclusions, judged every listed difference against the page images and checked every opinion's heading, type, author, joiners, boundaries, footnotes, date and votes. Structure, dates and votes were right in all 21 cases; all 428 ligature restorations checked out. They found wording errors in the Lawbox copies (for example *Olmstead* "We have to chose", *Lopez* "notwithstanding are the verdict", *Miller* "400 U. S. 322" for 409, *White* "nothing" for "noting"), Lawbox's dropped Part numerals, omission rows and appendix headings, and systematic faults in the main session's cleaning (line-end compound hyphens dropped, break hyphens kept in names, ellipses collapsed, URLs and dashes spaced, plurality joiners missed, about 15 wrong page breaks, footnote separator rules kept).
- The rework (`scripts/build_corpus.py`, `corpus_pdf.py`, `corpus_align.py`, `corpus_common.py`): hyphens decided by how each document prints the word mid-line; ellipses, brackets, URLs and dashes as printed; separator rules dropped; sections and appendices recognised; quotes straightened (P1.17); Lawbox's Part numerals and encodings restored; 50 two-scan corrections (P1.16); body text aligned only with official body lines and footnotes near their marker's page; a reviewed corrections table (`scripts/corrections.json`, 9 entries) for what scans cannot correct; majority joiners from the Reporter's lineup (P1.18), "The Chief Justice" resolved by date. The nine additions were pulled (46 requests), their PDFs downloaded (32 official PDFs, 100,164,787 bytes in all), and built.
- CourtListener's `date_filed` is wrong for six cases (*Ciraolo*, *Dunn*, *Florida v. Riley*, *Karo*, *On Lee*, *White*). *Ex parte Jackson*'s volume prints the Term, not a decision date; its date comes from CourtListener and is flagged.

**Failures:**
- *Carpenter*'s footnotes vanished once (appendix mode stayed on past Kennedy's appendix); *Oliver*'s footnotes went unrecognised (the scan's body heights scatter, so the most common height was the footnote size); a Lawbox one-off ("thermalimaging") vouched for itself as a word. Each was fixed before results were kept.
- The macOS word list (Webster's 1934) lacks words such as "coordinate" and "committed"; a fuller list (`english-words`, dev dependency) and the Lawbox copies' shared vocabulary now back the hyphen decisions.
- The verifier itself produced artifacts (running heads and footnotes printed inside paragraphs, words split across pages); reading the official text by region removed most.

**DECISION (user):**
- *"Jones and Quon take their text from the official PDF -> This is a more reliable and authoritative way."* (P1.12)
- *"Syllabus -> Strictly leave out of the citable corpus because they aren't from the Court."* (P1.13)
- *"Approve your recommended additions (the five squarely in the rule, plus Greenwood, Ex parte Jackson, Shultz, Berger and Boyd; leave out Quon and the rest). Also switch Kyllo to its official PDF."* (P1.14, P1.15)
- *"Approved: download the nine official GovInfo PDFs listed."*
- *"Take your recommendations on all four: correct Lawbox where both scans agree and have agents review every correction; straight quotation marks throughout; majority joiners from the Reporter's lineup where printed; Goldman's Stone and Frankfurter statement as concurrence in the judgment."* (P1.16 to P1.19)

## Oct 23, 2026, 20:14 CDT — Phase 1: Corpus (verification round 2; Clinton added; corrections policy changed)

**Asked:** Add *Clinton v. Virginia* (pull, official PDF, build, verify). Then, after round 2: apply only agent-confirmed corrections, keep the two-scan check as a report, run a comma and period check and a final agent pass. Then prepare for compaction.

**Came back:**
- *Clinton v. Virginia* (377 U.S. 158) pulled (6 requests), official PDF downloaded (33 official PDFs in all), built; its verification agent found no errors. Corpus: 32 cases.
- Verification round 2: ten Opus agents. Six re-checked the 21 original cases against round 1 (`BRIEF_ROUND2.md`); three verified the ten earlier additions in full; one verified *Clinton*. Structure and metadata were right in every case (headings, types, authors, joiners including lineup joiners and partial joins, boundaries, footnotes, sections, dates, votes). Nearly every round-1 error was fixed. Clean: *Kyllo*, *Grady*, *Jacobsen*, *Hester*, *Clinton*.
- Found in round 2: about half the automatic two-scan corrections were wrong (roughly 26 right, 22 wrong; shared OCR misreadings); about 25 comma and period errors in the Lawbox copies, which the scripts did not compare; about 12 page breaks one word off or matched to a citation in a later opinion; more Lawbox encodings (Windows-1252 bytes for "œ" and "†", a double-escaped entity, closed ellipses); a few PDF spacing faults. Every open item is listed in `docs/sessions/phase1-handoff.md`.
- Fixes written and committed untested (see the handoff file); the corpus in `data/corpus/` is still the pre-fix build.
- Locked P1.20 (*Clinton*) and P1.21 (only agent-confirmed corrections change the text; amends P1.16).

**Failures:** The two-scan rule (P1.16) proved unreliable in practice: two independent OCRs of the same page often make the same mistake. Replaced by P1.21.

**DECISION (user):**
- *"Add Clinton v. Virginia: pull it, download its official PDF (approved), build and verify it."* (P1.20)
- *"I want to apply only agent-confirmed corrections from the reviewed table; keep the two-scan check as a report of candidates, not an automatic change. Run the comma/period check and the final agent pass you described."* (P1.21)
- *"However, we're at context limit here. I would have to compact. I want you to prep the ground and prepare for compaction first."*

## Oct 23, 2026, 20:48 CDT — Frontend look tests folded in (direction chosen)

**Asked:** (Frontend session, folded in by the main session from `docs/sessions/frontend-log.md`, entries from Oct 23 17:34 to 20:18.) Build art-direction look tests (P1.6); then, after the user set the first three aside, a prototype showing the machinery under the demo; then a run of polish rounds; then record the chosen direction.

**Came back:**
- Three looks (Slip opinion, Cover stock, Evidence log) were built and set aside by the user.
- The chosen direction is the machinery prototype, `web/looktests/machinery/` as of commit badc05f: a tech demo first, legal in flavour. The landing page's question box glides down into a chat-style conversation that grows from the bottom; sources sit in a column beside it, marked kept or discarded; cited sentences are underlined in their passage's colour and hovering one lights the cited text in its paragraph; unmarked sentences are Claude's synthesis, explained by a key under the Answer heading. Each source has "View API calls" (every Messages API exchange that touched it, opening at the citation) and "View source" (a reader with the whole opinion, U.S. Reports page numbers in the margin, opened at the excerpt).
- Palette Evergreen (OKLCH, green-grey neutrals, four source hues at equal lightness and chroma, red kept for the verifier flag), dark mode following the system; type Instrument Sans, Newsreader and JetBrains Mono (Google Fonts, SIL Open Font License); one reading width, 51.25rem.
- Citation granularity, checked against the Citations docs: `search_result` text blocks are the minimal citable unit, so one paragraph per block gives paragraph citations and one sentence per block gives sentence citations. The prototype renders both with one path. Which one the backend sends is the main session's call (brief §5), still open.
- Assumptions recorded for the Phase 3 interfaces contract, not locked: a passage arrives as its ordered list of text blocks and a citation as passage ID plus block range; "View source" needs each passage's full opinion text, its position and its page breaks (Phase 1 provides page breaks); "View API calls" needs every exchange that touched a passage, from the run's event stream or replay, web page text excluded (P1.3).
- Prototype-only, to drop in the real build: the palette and theme switcher banner, the scripted run, the mock opinion text, the version query strings. Notice wording, the not-legal-advice line, the update-check label and the answer key are placeholders for the user to write.

**Failures:** Recorded in the frontend log (layout grid bug at the start of a run, card-outline hairlines, smooth-scroll cancellation, stale cached assets); each fixed in that session.

**DECISION (user):** *"Yes. This prototype, in Evergreen, is the chosen direction. Log it and get it ready for the main session to fold in."* Under P1.6 the direction is locked as a T-entry in Phase 3, from this record.

## Oct 23, 2026, 21:17 CDT — Phase 1: Corpus (final pass; approved and frozen)

**Asked:** After compaction, carry out P1.21: make the two-scan check report-only, move every agent-confirmed correction into the reviewed table, finish the generic fixes, add the comma and period check, rebuild, run the final agent pass, and report for approval. Then, on approval: include *Boyd*'s caption, commit the cleaned corpus with attribution, and freeze.

**Came back:**
- Two-scan check report-only (`cleaning.two_scan_candidates`): 27 candidates and 22 filtered, every one judged in round 2.
- Reviewed corrections table (`scripts/corrections.json`): 77 entries, each confirmed by a verification agent against the page image, each naming its batch. New entry types: `set_note`, `page_starts_at`, `remove_break`, `split_at`.
- Page alignment: every page break listed in the round-2 handoff now comes out right from the code (a break before a word opening with a quote or parenthesis had been pushed one word late; footnotes wholly on their marker's page are looked for there alone; run-on footnotes searched over three pages; the nearest well-supported match preferred, so *Boyd*'s statute no longer matches *Miller*'s later quotation of it; damaged page-split words take the official page; paragraph pages never go back within an opinion).
- PDF cases: same-height line pieces joined (*Chatrie*'s paragraph split in four), URL line breaks, closing quotes after a thin print gap, nested opening quotes, a line-end hyphen kept before a capital, hyphen evidence from line-end words. Lawbox: Windows-1252 footnote labels, ellipsis and fraction spacing, "MR. JUSTICE", reargued and submitted dates.
- Comma and period check in `scripts/verify_corpus.py`: where the official text layer and Harvard agree and the corpus differs. On the earlier build it caught all 8 of *Berger*'s comma errors; on the final build its 10 candidates were judged by agents (shared OCR misreadings and printed specks).
- Final agent pass: four Opus agents over all 32 cases (`BRIEF_FINAL.md`, `final_checklist.json`), then three short follow-ups (four-dot ellipses, capitalisation, divided words at page turns). All 52 table entries checked were right; every listed page break was right. They found about 25 more errors, all fixed through code or the table and confirmed: thin print gaps read as spaces, letterspaced words ("Car roll"), URL and capital hyphens, five closed-up four-dot ellipses, "liquor License", "Secretary", two run-in paragraphs merged in *Berger*'s appendix, and 10 page breaks that put a divided word on the later page (convention set: on the page where it begins).
- Frozen corpus: 32 cases, 102 opinions, 599,094 tokens (`claude-sonnet-5-5`, token-counting endpoint). Committed under `data/corpus/` with a README giving sources and attribution. Raw responses, PDFs and verification output stay local. Locked P1.22.

**Failures:**
- The first build of the round-2 code dropped *Boyd*'s dagger footnotes (labels left as raw Windows-1252 bytes) and spaced an ellipsis after opening quotes; both fixed before anything was kept.
- Joining same-height line pieces at first also joined running-head pieces ("388 U. S." with "Opinion of the Court"), which then leaked into the official body stream; limited to gaps under 40 pt (body gaps measured up to 22 pt, running heads 79 pt and more).
- A script meant to find divided words at page turns misread *Shultz*'s ("re-|quired" taken as "report"); the confirming agent caught it.

**DECISION (user):** *"Approved. Include Boyd's p.618 caption as a quote paragraph, commit the cleaned corpus with attribution (default 3), and accept the two smaller points as recommended. Go ahead with the freeze."* (P1.22)

## Oct 24, 2026, 13:59 CDT — Frontend look tests: the user's directions along the way (supplement)

**Asked:** The user asked that `BUILD_LOG.md` hold every decision now that the frontend look-test conversation has concluded. The fold-in of Oct 23, 20:48 CDT recorded only the final choice of direction. This entry carries the user's directions from the frontend session's own log (`docs/sessions/frontend-log.md`, entries of Oct 23, 17:34 to 20:18 CDT), quoted from its DECISION lines. That log had no later entries, and the frontend session has nothing uncommitted.

**Came back:**
- 17:34, three looks: *"Build the three looks as proposed."* No direction picked.
- 19:04, the machinery prototype:
  - The vision: *"The demo is legal flavor, but it's a TECH demo foremost."* *"I want sleek, modern, easy to follow and catchy, all the good UXUI principles that will hold a person's attention to see the tech in action."* *"We would want a very intuitive and impressive landing page that transitions into the research UXUI after a natural language request is typed in, or an user clicking a chip of a recorded request."*
  - The audience: *"most likely a technical person, looking to see Claude and Claude Citations in action."* When the answer finishes, *"they should be thinking that Claude Citation is a really neat feature that can be easily and effectively incorporated into my systems."*
  - The machinery: *"Showing the raw API and underneath machinery might actually be a great thing. Let's prototype it up first because it would be hard to find the right balance without seeing it visually."*
  - Granularity: sentence blocks are *"Not yet on the backend; that's the main session's call. But build the prototype to handle both"*. *"Record this shape as an assumption for the Phase 3 interfaces contract, not a locked decision."*
- 19:31, polish:
  - *"This is a very good start."*
  - Hovering a cited sentence should make *"the right hand section … scroll to the right source on hover"*.
  - The question being *"teleported all the way to the header … can be confusing"*; *"I'd want a familiar chat UI, where things start moving up a bit by a bit as more steps are taken"*.
  - *"getting rid of the Plain, Annotated, and API traffic toggle to declutter. Instead, for each source, there should be a clearly labeled button that will display the request and response that led to that citation, ideally in a modal"*, showing *"both API traffics and the rendered source"*.
  - *"No coherent color palette. Mock up a few options? I want automatic dark mode handling as well that follow system's settings."*
  - The stripe *"protruding further than the rounded border"* is *"jarring if unfixed."*
- 19:50, Evergreen chosen:
  - *"I like evergreen to help keep the eye strain down while reading thru text heavy legal docs."*
  - The answer: *"present the answer normally, with cited sentences highlighted appropriately, where as not highlighted sentences are assumed to be Claude's synthesis. We can guide the user right underneath the Answer header which sentence is synthesis and which is supported by citation."*
  - The outline: *"use code to investigate and ensure everything smoothes into each other perfectly."*
  - The API window: *"The API modal is using too much vertical space, decrease it."* The layout bug: a *"Critical display bug"*, *"jarring"*.
- 20:03, wider conversation and source reader:
  - *"Good improvements."* *"On desktop, increase the amount of width that the chat interface uses by 50% to both sizes."*
  - *"For each source, next to View API calls buttons, have a View Source button that will open a reader modal that lets the user scroll thru the whole actual text, starting from the cited excerpt."*
- 20:13, width revised: *"You understood my 50% request correctly. I changed my mind, however, I want only 25% growth overall to both sides compared to the original width now."*
- 20:17, disclosure line: *"Good. One last polish note, the sentence "Answers are written by Claude, Anthropic's model, through the Claude API; check them against the opinions.", start it on a new line always."*
- 20:18, the direction: *"Yes. This prototype, in Evergreen, is the chosen direction. Log it and get it ready for the main session to fold in."* (Folded in at 20:48; locked as a T-entry in Phase 3 under P1.6.)

**DECISION (user):** That this log is where every decision is kept: *"BUILD LOG is our authoritative and final source of updating decision now that the front end parallel conversation has concluded. Make sure it's up to date."*

## Oct 24, 2026, 13:59 CDT — Phase 2: Research

**Asked:** Discuss and kick off Phase 2, the research of brief §9, then lay out the research plan for approval before running it. The user asked that the plan not default to Opus: subagents on Sonnet 5.5 at high effort at the least, extra-high where needed, never max. The user also asked for a check of the goodnight gateway's request timeout, read only, keeping that project's code out of this repository and logging at most that one figure. Then close the phase.

**Came back:**
- Findings in `docs/research/phase2-findings.md`. They came from six read-only research agents (Sonnet, high or extra-high effort) plus paid checks from committed scripts (`scripts/probe_common.py`, `probe_loop.py`, `probe_exa.py`; the `mcp` package added).
- **A simulated loop on the real corpus,** at the product's settings (Sonnet 5.5, high effort, automatic caching, SQLite FTS5 search, a stubbed update check):

  | Run | Steps | Claude cost | Elapsed |
  |---|---|---|---|
  | First question | 6 | $0.237 | about 45 s |
  | Second question | 4 | $0.144 | about 30 s |

  The brief had estimated $0.35 to $0.45 a run uncached.
- **Citations:** 97 of 97 citations' `cited_text` equalled the cited blocks' text exactly. Sentence blocks narrowed citations to one or two sentences.
- **Other API behaviour:**
  - Claude made two or three searches per turn.
  - A rejected `submit_answer`, returned as an error result with thinking intact, was accepted by the API. Claude then ran another update search. The trigger was artificial, since Claude ran the update check unprompted in both runs.
- **Exa through its MCP server:**
  - A search costs $0.004 on Lite and $0.007 on Auto, with page text included at no extra charge.
  - Deep search can't be sent through the server.
  - A published-date filter appears to drop undated pages.
  - The server retries Exa's 5xx errors twice on its side.
- **Settled from the docs:**
  - A cache read on Sonnet 5.5 is $0.10 per million tokens; the brief had flagged this as contradicted.
  - Forced `tool_choice` is a 400 on Sonnet 5.5.
  - Thinking blocks need an append-only history.
  - Cloud Run does not pass a client disconnect to the container over HTTP/1.1.
  - Anthropic offers no embeddings model.
  - The Console has monthly spend limits but no daily one.
- **Name check:** no product or repository called "Probable Clause" was found. The trademark registry could not be read by the agents.
- **goodnight's Cloud Run request timeout: 300 s.**
- **Sources re-checked:**
  - `scripts/verify_quotes.py` matched 439 of 488 web quotes exactly, plus all 38 quotes from the previous build's files.
  - An agent not told the conclusions confirmed the other 49 by hand.
  - A further agent checked all 126 claims in the draft findings against their cited pages and the probe outputs. Its 22 corrections were applied before the findings were committed: 10 claims citing a neighbouring page, 7 worded too strongly, and 5 figures off. None was unsupported.
- **Decisions P2.1 to P2.11** locked in `docs/design/locked-decisions.md`.

**Failures:**
- The Claude API reference used to draft the probe gave Sonnet 5.5's cache read as $0.20. The pricing agent found $0.10 on Anthropic's pricing page, and I confirmed it there before any paid call.
- The first Exa run lost two requests: full page text for 10 results overflowed the MCP client's 1 MB event limit. Capping the text at 2,000 characters per result fixed it. Whether the two failed requests were billed is not known.
- The Exa probe first read the error flag under the wrong field name (`isError` for `is_error`), so its summary shows null for the two error replies. The raw replies show true. Fixed for the later requests.
- The first thinking-removal test was skipped, because the first turn had no thinking block. It was rerun on the first turn that had one, and the removal was accepted.
- The claims check found 22 problems in the draft findings, listed above; all fixed before commit.

**Spend:**
- Anthropic: 16 calls on `claude-sonnet-5-5`, $0.5541 (ceiling $2).
- Exa: 9 requests from the free credit. Five reported $0.029 in all; two failed with no reported cost, and two error replies (a rejected filter combination and an invalid key) cost nothing.

**DECISION (user):**
- Model, P2.1: *"For model check, let's lock Sonnet 5.5 at high effort and only increase the effort or ponder Opus if we see evidence that Sonnet 5.5 at high cannot handle what we want."*
- Exa prices, P2.2: *"It's from my console so it's authoritative."*
- Keep-only triage, P2.3: *"Instead we should expose only keep tool, with sources not acted on by Claude simply discarded."* And: *"only what is kept would want a reason. Everything else discarded."* How passages are surfaced and queried stays open for Phase 3, with the user's green light.
- Citable text, P2.4: *"On sticking with Phase's 1 work and finding, you have my green light here."*
- Research plan, P2.5: *"The research plan looks good to me. One note though, use Sonnet 5.5 at high effort in the minimum. You're allowed to set extra high effort for certain parts of the plan. However, you're barred from using Sonnet 5.5 at max effort."*
- No per-visitor limit, P2.6: *"On cap on runs per visitor, uncap it. We will control with daily cost cap and monthly cost cap only."*
- Limits, P2.7: *"Stick with these limits: 12 steps, 400K input and 20K output tokens per run, 3 update searches, the $10 daily cap and the $60 monthly cap."*
- Exa retries, P2.8: *"Exa's server-side retries are allowed."*
- Name, P2.9: *"Probable Clause as a name is fine."* The repository is reserved, and the frontend will be served at nguyennhattran.com/probable-clause.
- Disconnect detection, P2.10: carried to Phase 3.
- No keyless fallback, P2.11: *"Agreed: no keyless fallback. When the credit runs out the update check shows as unavailable until the 1st. Close Phase 2."*

## Oct 24, 2026, 14:02 CDT — Records: BUILD_LOG first, locked-decisions as its index

**Asked:** The user made this log the authoritative record of decisions. They asked whether to retire `docs/design/locked-decisions.md` or keep it alongside the log.

**Came back:**
- The proposal: keep `locked-decisions.md` as the index of decisions in force, ranked under this log. The order is this log first, the decisions file second, the brief third.
- A conflict is fixed by a superseding entry in the decisions file, never by editing the log. Each decisions entry names the log entry that records it.
- New decisions are written to both files in the same commit.
- Applied:
  - Each existing entry, P0.1 to P2.11, gained a **Log** line naming its log entry: the entry where the decision was made, found by matching the user's quoted words.
  - The decisions file's header and the CLAUDE.md rule lines were updated to the new order.
  - The decision is recorded as P2.12. It came after the `phase-2-done` tag; Phase 3 has not started.

**DECISION (user):** *"Keep locked-decisions.md as the index of decisions in force, under BUILD_LOG: the log wins on any conflict, and each entry names its log entry. Lock it."* (P2.12)

## Oct 24, 2026, 14:48 CDT — Phase 3: Architecture, Area 1 (retrieval, T1.1)

**Asked:** Start Phase 3. Split it into areas and finish one at a time, compacting after each area, with a working document the main session keeps in the repo. Draw the current placeholder loop. Add four topics to Area 1 (the case-name verifier's reliability, a second search tool, filters before a search runs, Claude choosing how much to cite). Then discuss retrieval from scratch, not from the brief.

**Came back:**
- Phase 3 split into five areas plus the design note: the research loop (T1), the update check (T2), run lifecycle and infrastructure (T3), the interface (T4), the user's wording and the replays (T5). Working document `docs/design/phase3-working.md`; CLAUDE.md points to it.
- Two diagrams of the placeholder loop (brief §5, P2.3, P2.4, `scripts/probe_loop.py`), shown in the conversation.
- Area 1 revised to ten topics, the user's four additions folded in.
- Retrieval facts: 2,250 paragraphs and 498 footnotes (2,748 searchable units; the Phase 2 probe indexed paragraphs only); in the probe runs 13 of 96 and 23 of 56 surfaced passages were repeats. Options shown: vectors held in the API container rather than a database; two tools, one fused tool, or one tool with a mode; a reranker on semantic results; a metadata header on the embedded text; a corpus catalog in the system prompt; a tool to read around a passage; the whole corpus in context (not recommended: P2.7's 400K ceiling).

**DECISION (user):**
- How Phase 3 runs: *"I want us to compact after each area, so how about you keep a working document for yourself somewhere of your choosing within this repo. (It's fine to have git track this document.)"*
- Retrieval from scratch: *"Let's zoom out from the brief for a moment and discuss retrieval method from scratch here. The brief was written as a starting point only. Currently, I'm thinking of 2 parallel search stacks: 1. RAG with Reranker supported by Voyage AI. Vector search preferably not handled by our free MongoDB cluster. 2. Keyword based search. 3. Both with filtering optionalities for Claude."*
- T1.1: *"I'm thinking 2 tools in parallel is the right choice here. For model on the RAG stack, lock voyage-law-2 and rerank-3."*

## Oct 24, 2026, 14:54 CDT — Phase 3: Architecture, Area 1 (keyword fields T1.2, read-around T1.3)

**Asked:** The user wanted Claude to be able to narrow a keyword search (every keyword must appear) or widen it (any of several), and asked for thoughts on letting Claude request more context around a passage on demand.

**Came back:**
- Keyword search: SQLite FTS5 supports AND, OR, NOT, phrases, nearness and prefixes. Two ways to expose it: raw search syntax written by Claude, or structured fields (`all_of`, `any_of`, `none_of`, quoted items as phrases) compiled by our code; recommended the fields (no malformed queries, plain display in the step log). Noted that the porter tokenizer matches word forms.
- Read-around: recommended a third corpus tool reading up to about 3 units on each side of a passage, within its opinion, with the footnotes the passage cites (each paragraph records its `footnote_refs`), results keepable, on demand only.

**DECISION (user):**
- T1.2: *"I'd decide to go with Claude writing structured fields. This would be easier on the model as well. all_of, any_of, then none_of would be suitable. Our code will build the query."*
- T1.3: *"On reading around a passage on demand, I'm thinking we should return the full requested content WITH the passage Claude has already read as well so Claude see a unified block instead of having to make the mental connection that the block it already saw is fitting into the middle of this somewhere. This is a trade off to gain more quality and accuracy while incurring a bit more cost and time."*

## Oct 24, 2026, 15:07 CDT — Phase 3: Architecture, Area 1 (query inputs and filters, T1.4)

**Asked:** Area 1, topic 2, reviewed in full by the user: how Claude queries both search tools, and the filters before a search runs. The user asked what the opinion-type groups meant, and that the filters be presented to Claude as clearly optional.

**Came back:**
- The design: shared optional filters (`cases`, `decided_from`/`decided_to`, `opinion_types` in four groups, `authors`, `none_of` on both tools, `include_footnotes`) inside one optional `filters` object; `max_results` 1 to 10, default 8, clamped; the semantic tool's single `query` (filter, top 50 by vector as a placeholder, `rerank-3`, top `max_results`); the keyword lists (T1.2), at least one item in `all_of` or `any_of`, quoted items as phrases, about 10 items per list as a placeholder; error results for bad input, "no passages matched" with the filters repeated; a corpus catalog in the system prompt. Sorting by date considered and left out.
- Opinion types explained with corpus examples: the corpus records eight exact types from the printed headings (30 majority, 2 plurality, 40 dissent, 30 across the concurring forms and the mixed type); Harlan's concurrence in *Katz* is the source of the expectation-of-privacy test.
- Optional filters made explicit in the schema, the descriptions, the system prompt and our code (empty lists treated as unset), with a count of Claude's filter use in testing. The tool-description wording was redrafted after the user's objection.

**DECISION (user):**
- *"I'm not clear on what do you mean for the opinion types here. Can you give me more context?"*
- *"with this many filter options, which is good, I want us to clearly present them as optional to Claude, so that Claude does not mistaken and try to fill every filters for all requests."*
- *"Use four groups HOWEVER, Claude must be aware of this because it's a deviation from standards."*
- *"this description needs improvement "Most searches need no filters. Add one only to narrow a search you have a reason to narrow." My take is that this encourage Claude to add only one filter most of the time, which is not what we want."*
- T1.4: *"Lock topic 2 as T1.4 with the revised wording and the four groups stated to Claude."*

## Oct 24, 2026, 15:47 CDT — Phase 3: Architecture, Area 1 (structure check; Oliver's heading, T1.5)

**Asked:** While reviewing topic 3, the user asked how reliable the detection of section headings is, and whether they would be excluded or merged into adjacent passages. After the main session found *Oliver*'s majority missing its "II", the user raised the principle: *"See how you missed Oliver's heading II even though we technically did verify in Phase 1?"* Then: run a read-only structure check on headings and footnote markers against the raw sources, with no corpus changes.

**Came back:**
- Why Phase 1 missed it: `scripts/verify_corpus.py` skips `section` paragraphs by design, so the word-by-word check never covered headings; round 2's agents reported sections right, and missed it. Headings rested on agent reading only. Footnote marker positions had no scripted check either. Both become load-bearing in Phase 3 (section labels in passage headers; footnotes attached inside the citing passage).
- `scripts/check_structure.py` (read only): each of the 1,964 paragraphs matched by its opening words to every raw copy (Lawbox, CourtListener's `html` copy and Harvard's scan for the Lawbox cases; Harvard and the slip copies for the PDF cases), then 286 headings and 498 footnote markers compared, plus the corpus's own consistency.
  - Headings: one defect, *Oliver*'s missing "II" (p. 176), present in the official PDF, the `html` copy and Harvard; Lawbox, the build's source, drops it. Every other difference traced to a copy's own gap, with the other copies agreeing with the corpus.
  - Markers: no defects. Every opinion's markers pair with its footnotes in order, labels matching. Riley's 3 markers confirmed in the official PDF; Carpenter's and Chatrie's 40 markers found in the official PDF text right after the same words.
  - For the design: footnote labels repeat within an opinion (*Boyd*), so footnotes link by order; three omission rows and *White*'s appendix letterhead and signature lines are typed `section`, so section labels come only from numbered headings and appendix titles.
- Passage lengths measured: the 1,964 content paragraphs average 774 characters (median 696); 286 of the 2,250 corpus "paragraphs" are section headings. The corpus catalog for the system prompt counted at 7,257 tokens (`count_tokens`).

**DECISION (user):**
- *"Your proposed handling of section headings stored as paragraphs looks fine, but I wonder how fragile is our detection? And would we then be excluding those headings forever? Should we inspect and merge the headings into adjacent passages?"*
- *"Well my issue is more in principle though. See how you missed Oliver's heading II even though we technically did verify in Phase 1?"*
- *"Run the read-only structure check on headings and footnote markers against the raw sources and report what it finds. No corpus changes."*
- T1.5: *"Fix Oliver's missing II through the corrections table at the start of Phase 4, confirmed against the page image, with the Phase 1 checks and the structure check re-run and logged. However, don't send any subagent out again because this is a targeted fix. I also want to conserve usage as well. Push back otherwise."*

## Oct 24, 2026, 15:50 CDT — Phase 3: Architecture, Area 1 (how passages reach Claude, T1.6)

**Asked:** Area 1, topic 3, reviewed in full by the user: how passages reach Claude. Along the way the user asked what "plain text" results meant, how footnotes are handled, the average and median passage length, and proposed two additions: reading a passage directly by its ID, and giving Claude each case's metadata.

**Came back:**
- Result format explained: a tool result holding `search_result` blocks may hold nothing else, so loop results are text blocks, one per passage, each with a header; the composition call keeps `search_result` blocks. Untested in the probe; checked in build tests.
- Footnotes switched to the user's intuitive way (attached inside the citing passage). Read-around reach set to 0 to 10; each passage its own marked block.
- Direct reads merged with read-around into one `read_passages` tool, targets by ID or by case and U.S. Reports page (221 paragraphs cite "ante/post/supra, at <page>", 13 mention a Part); IDs counted from 1 (the probe's 0-based IDs made `katz-2-p1` the second paragraph). Case metadata folded into the corpus catalog (7,257 tokens, counted).
- Section headings and footnote markers checked by script before locking (entry of 15:47 CDT).

**DECISION (user):**
- *"What you said about "Results come back as plain text." is a bit confusing to me. Can you clarify and give me more context here."*
- *"I also need you to clarify how is footnote being handled. The intuitive way would be for us to automatically attaching footnotes to any passage that cites them, right within it, but are we deviating from it? Why?"*
- *"Read around reach, I want to give Claude flexibility here and we trust Claude's judgement. Give it 0 to 10."*
- *"Also, read around wouldn't just return a blob of text, we should return all the requested passages with clear markings."*
- *"what about adding a tool that let Claude enter a passage ID directly and read that passage? … This is for example in cases of a passage mentioning another passage that is outside the read around bound."* And: *"we should also have a tool that let Claude get metadata of a case as well especially how many passages, what's the id of the first few ones and of the last few ones, or fold this data into an existing tool."*
- On reads: *"A read always returns what Claude asked for, even if it was seen before. Claude asked deliberately."* *"An unknown ID or page comes back as an error result giving the valid range."* *"On limit per call, I'm thinking just one target per call? If Claude wants to read more passage, it can make more read_passages() tool call?"* *"ID counting from 1 for more natural IDs is good."*
- T1.6: *"Lock."*
- On the record: *"Don't forget we're ALWAYS keeping BUILD LOG updated with system time as well."*

## Oct 24, 2026, 16:06 CDT — Phase 3: Architecture, Area 1 (the keep tool, T1.7)

**Asked:** Area 1, topic 4, reviewed in full by the user: the keep tool's shape. The user proposed leaving out a way to withdraw a keep, letting the composition call simply not cite passages it doesn't need, and asked how caching works for the composition call.

**Came back:**
- From the Phase 2 runs (script): one keep call per run, at the end (30 and 14 passages at once); reasons median 53 and 75 characters, longest 132; `submit_answer` repeated every kept ID. Composition already leaves kept passages uncited: 29 of 30, 25 of 30, 14 of 14 cited.
- The proposal: batched keeps, made as Claude goes alongside its next searches; only passages already shown can be kept; one-sentence reasons, refused over 300 characters; re-keeping replaces the reason; partial success reported with the running total; a cap of 40 kept passages (placeholder); footnotes kept separately. A `withdraw` list was proposed, then dropped for the user's design, on one condition: the composition call starts fresh, so each kept passage's reason must reach it, carrying any correction made in the loop.
- Caching: the composition call is a new prompt (own system prompt, no tools, only the kept passages), so the loop's cache cannot apply without continuing the loop conversation, which would put every unkept passage before the writer. Its input is about $0.02 to $0.04 a run; output costs more. Details in topic 7.

**DECISION (user):**
- *"On withdrawal, I'm thinking the synthesis call will simply not cite passages it doesn't need. So we will see everything in the source panel, but some of them won't be cited. Would that be a good design?"*
- *"for the synthesis call, how is context caching working here? (Defer if it's coming up in a separate topic.)"*
- T1.7: *"Lock topic 4 as T1.7: no withdraw list; re-keeping replaces the reason; each kept passage's reason goes to the composition call; the rest as proposed."*
- Raised, not decided: *"since the composition call is pretty independent and does not get fed the same context, so caching doesn't matter, should swap to Opus at high effort?"*

## Oct 24, 2026, 16:09 CDT — Phase 3: Architecture, Area 1 (composition on Opus, T1.8)

**Asked:** The user asked whether the composition call, being independent of the loop's context and cache, should run on Opus at high effort.

**Came back:**
- No technical blocker: composition is its own conversation, so the loop's cache and thinking history are untouched.
- Priced from the Phase 2 composition tokens (script; Opus 5.5 at $4 input and $20 output per million, findings §3): composition $0.072 → $0.143 and $0.044 → $0.088; a whole run $0.238 → $0.309 and $0.144 → $0.188, about +30%; runs per $10 day 42 → 32 and 69 → 53. Opus's own output length and speed not measured.
- Recommended keeping Sonnet under P2.1 until a side-by-side comparison with the real composition prompt, with the composition model as its own setting.

**DECISION (user):**
- *"since the composition call is pretty independent and does not get fed the same context, so caching doesn't matter, should swap to Opus at high effort?"*
- T1.8: *"Let's switch to Opus 5.5 at high for quality and we will compare again with Sonnet 5.5 at high effort later as well."*

## Oct 24, 2026, 16:23 CDT — Phase 3: Architecture, Area 1 (citation granularity, T1.9)

**Asked:** Area 1, topic 5 (the user's addition): let Claude decide not only what to cite but how much, with the source panel always showing the cited sentence inside its paragraph. The user then asked whether whole passages could be fed and cited at any length, and approved a diagnostic call on the hardest passages.

**Came back:**
- A citation is a range of whole blocks, so the split sets the smallest unit and Claude picks the span. The Phase 2 splitter, run over the corpus (2,610 paragraphs and footnote paragraphs), made 11,660 blocks with 491 splits right after a short capitalised word, mostly inside citations; a conservative variant made 11,093 with 68, erring towards leaving two sentences together.
- From the Citations docs (cached Oct 24): plain-text documents are "automatically chunked into sentences"; custom content documents are "used as-is and no further chunking is done"; no option cites less than its smallest unit.
- `scripts/probe_chunking.py`: the ten hardest passages (chosen by script) as plain-text documents, Claude citing each piece separately. Anthropic's chunking broke legal citations in 133 of 200 pieces ("205 F. Supp. ‖ 692", "Code Crim. ‖ Proc.", *Berger*'s statute footnote in 70 pieces, 69 broken); prose, "U. S." and "Id., at 657." split correctly. Our conservative splitter on the same passages: 54 blocks, none broken, matching Anthropic's correct boundaries where they can be counted.

**Spend:** Anthropic: 1 call on `claude-sonnet-5-5` at low effort, $0.1422 (11,562 input, 11,912 output tokens); Phase 2 and 3 ledger total $0.6964 of the $2.00 ceiling.

**DECISION (user):**
- *"Consider whether we can feed whole passage, and let Claude cite within them however much or however little Claude wants? Or is it something technically not possible with this Citations feature?"*
- *"You have the same idea as mine. Send the diagnostic calls with the hardest passage."*
- T1.9: *"Lock topic 5 as T1.9: our conservative splitter, sentence blocks sent as custom content documents with metadata and the keep reason in context, the rest as proposed."*

## Oct 24, 2026, 16:32 CDT — Phase 3: Architecture, Area 1 (submit_answer and the rejection rules, T1.10)

**Asked:** Area 1, topic 6: `submit_answer` and brief §5.4's rejection rules, now that the loop has two search tools, a read tool and a keep set. The user asked whether a person asking an out-of-scope question would get a natural response.

**Came back:**
- From the Phase 2 runs (script): two or three searches a turn; the update check run unprompted both times (once in the same turn as two searches); keep and submit once in the same turn; `submit_answer` repeated every kept ID; no rejection fired naturally.
- The proposal: no kept-ID list in `submit_answer`; an optional `note` (required when out of scope or nothing kept) and an optional `update_skip_reason`; four rules in order (a submit in the same turn as a search or read is refused; no corpus search, refused and repeatable, a read alone not counting; nothing kept with no note, refused; no update check and no skip reason, refused once, then accepted and labelled, a failed attempt counting and the rule waived while the update check is unavailable); no composition call when out of scope or nothing kept.
- Out-of-scope traced: one Sonnet call, about $0.03 to $0.04 (estimate; mostly the 7,257-token catalog), speed not measured. Three gaps found and fixed: the note written to the visitor rather than as a log line; a scope note for partly in-scope questions; personal-situation questions kept in scope (brief §5.6). A borderline case (an employer reading work email) left for the system prompt, topic 10.

**DECISION (user):**
- *"Would a person asking an out of scope question get a natural response back with the current design?"*
- T1.10: *"Lock topic 6 as T1.10 as proposed, with the out-of-scope additions: note written to the visitor, a scope note for mixed questions, personal-situation questions kept in scope."*

## Oct 24, 2026, 16:46 CDT — Phase 3: Architecture, Area 1 (the composition call, T1.11)

**Asked:** Area 1, topic 7: the composition call. The user set `max_tokens`, asked whether the update check should be folded into the answer, chose no length target, and asked why the answer should be held to prose.

**Came back:**
- Phase 2's answers (script): 1,142, 1,139 and 821 words; 60 to 67% of characters cited; all three used Markdown.
- The proposal: inputs (question, scope note, coverage dates, kept passages as custom content documents in date order with metadata and the keep reason in `context`); unkept footnotes and web results left out; a composition prompt outline; synthesis worked out mechanically as uncited text; streaming; an output reserve held back from the per-run budget; the step-limit and token-ceiling fallback; no composition on an abandoned run; a failed composition shown, never retried automatically.
- The update check, from brief §6.4 and P1.3: shown in its own band, never folded into the answer; the band's synthesis written in the loop by the Claude that read the results (mechanics in Area 2); one fixed line from our code pointing from the answer to the band when the check found something.
- Format: prose only was recommended, then withdrawn on evidence: of 96 cited text blocks in Phase 2, none held a line break, heading or list marker; all 34 headings and list markers sat in uncited blocks; bold and italics in cited blocks were always balanced.

**DECISION (user):**
- *"Set the max tokens to 12000 just in case."*
- *"the update check ran within the research loop, so we need to pass it on to fold it in? Or are we just showing the update check within the research loop but never within composition?"* Then: *"On the update check, I agree with your suggestions there."*
- *"I'm thinking of not suggesting Claude with a length target and see how it goes first. We already had max token as the hard backstop."*
- *"Why do we want to keep it to prose only? We can let Claude write naturally and render accordingly?"*
- T1.11: *"Lock topic 7 as T1.11: Claude writes naturally in Markdown and the page renders it, with the straddle fallback; no length target; max_tokens 12,000 with a cut-off label; the update check kept out of composition; the rest as proposed."*

## Oct 24, 2026, 16:51 CDT — Phase 3: Architecture, Area 1 (answer checks, T1.12)

**Asked:** Area 1, topic 8 (the user's addition): whether the deterministic case-name verifier can recognise case names in Claude's answer reliably without structured output, and whether to offer it at all, weighed together with a quotation check.

**Came back:** a trial of both checks on the three Phase 2 answers (scratchpad script):
- Case names: full "X v. Y" names (3, 1 and 3) and italic spans all resolved to the corpus, but one answer italicised nothing. A name *outside* the corpus can be found only as a full "X v. Y" name or a U.S. Reports citation; a short form cannot be told from a word or a person's name ("Riley" is two corpus cases; "White" and "Miller" are cases and Justices). The brief's "every case name resolves" cannot be checked reliably.
- Quotations: 31 of four or more words. A first pass flagged 5; all 5 were verbatim, the flags coming from legal quoting conventions (punctuation inside the closing quote, nested quotes turned single, an ellipsis, a source's own "[ ]"). With those handled, 31 of 31 matched. The check closes a gap the API leaves open: `cited_text` is verbatim, but words Claude quotes in its own sentence are not guaranteed.

**DECISION (user):**
- The concern that opened the topic: *"I'm concerned of the fragile deterministic case-name verifier, particularly how do we recognize robustly what is a case name to check within Claude's answer without requesting Claude to write it as structured output (which breaks Citations feature). I'm considering not offering this if it's something we cannot check reliably. The response is covered under the AI disclosure already, and adding a check that isn't reliable might give false confidence to user."*
- T1.12: *"Drop the general case-name verifier. Keep the quotation check and the narrow full-citation check, each worded exactly. Lock topic 8."*
