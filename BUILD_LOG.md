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

## Oct 24, 2026, 17:00 CDT — Phase 3: Architecture, Area 1 (citing-cases lookup cut, T1.13)

**Asked:** Area 1, topic 9: the citing-cases lookup of brief §5.2 ("if time allows"), second on brief §3's cut list. The user asked whether it needs its own infrastructure.

**Came back:**
- Citations between corpus cases in the opinion text (script): 805 occurrences resolving to another corpus case (509 full, 296 short pinpoint forms) in 524 passages; 30 of 32 cases cited by another (Boyd by 22, Katz by 19, Olmstead by 18).
- The proposed `find_citing(case, filters?)` would need a citation index built once by script (about 70 KB, estimate) and a lookup at run time. Cross-checked against CourtListener's `opinions_cited` graph: all 217 of its case pairs found in the text, 12 more found; 2 of those were false matches of the quick rule (a short citation resolved by volume alone: Greenwood's "Leon, 468 U. S., at 908" as Karo; Shultz's "274 U. S., at 263" as Lee), fixed by a page-range rule; Knotts → White real and missing from CourtListener; 9 recent cases citing recent ones.
- Alternative: Claude finds citing passages with keyword search on the citation string.

**DECISION (user):**
- *"The idea of the tool find_citing(case, filters?) is sound on the consumption end (Claude), but I'm reading that we'd need to build the underlying infrastructure? For each case, we will need to parse and store what are the cases that it is citing?"*
- T1.13: *"Cut the citing lookup; Claude uses keyword search on the citation string. Lock topic 9."*

## Oct 24, 2026, 17:04 CDT — Phase 3: Architecture, Area 1 (the loop's system prompt, T1.14)

**Asked:** Area 1, topic 10: an outline of the research loop's system prompt (the composition prompt is outlined in T1.11), and how to handle a borderline question such as an employer reading work email.

**Came back:** a five-part outline (role and the division of labour; the corpus, its coverage dates from the manifest, text notes, the ID scheme and the catalog; research strategy with the tools; judgement rules; out-of-scope and borderline questions); a status line on each turn's tool results; a one-hour cache breakpoint on the fixed opening (tools, system prompt, catalog; about 12,000 tokens, estimate); the user's review of the drafted prompt text before its first paid run.

**DECISION (user):** T1.14: *"Lock topic 10 as T1.14 as proposed; borderline questions like the employer email get researched (the state-action limit), not flagged out of scope."*

## Oct 24, 2026, 17:05 CDT — Phase 3: Architecture, Area 1 closed (the research loop)

**Asked:** Finish Area 1, the research loop, topic by topic, then compact before Area 2 (*"I want us to compact after each area"*).

**Came back:**
- Fourteen decisions, T1.1 to T1.14, each with its own entry above:
  - retrieval as two search tools, semantic on `voyage-law-2` with `rerank-3`, and keyword (T1.1)
  - keyword lists `all_of`, `any_of`, `none_of` (T1.2)
  - read-around as one marked result (T1.3)
  - optional filters and query inputs (T1.4)
  - *Oliver*'s heading fixed at the start of Phase 4 (T1.5)
  - how passages reach Claude, with `read_passages` and the catalog (T1.6)
  - batched keeps with reasons, no withdraw list (T1.7)
  - composition on Opus 5.5 at high effort (T1.8)
  - sentence citations from our splitter, as custom content documents (T1.9)
  - `submit_answer` and four rejection rules (T1.10)
  - the composition call (T1.11)
  - a quotation check and a narrow full-citation check in place of the general verifier (T1.12)
  - no citing-cases lookup (T1.13)
  - the loop's system prompt outline (T1.14)
- Superseded or amended along the way: brief §2's kept-ID list (T1.10) and Case-name verifier row (T1.12); P1.10 (T1.12); P1.21 for one entry (T1.5); P2.1 for composition (T1.8); T1.6 and T1.7 for the composition call (T1.9).
- New scripts: `scripts/check_structure.py` (headings and footnote markers against every raw copy, read only) and `scripts/probe_chunking.py` (Anthropic's plain-text sentence chunking).
- Carried forward, recorded in `docs/design/phase3-working.md`:
  - **For the design note:** vectors held in memory in the API container; a metadata header prepended to the embedded text.
  - **For the start of Phase 4:** T1.5; the sentence splitter's check and sampled review (T1.9).
  - **For build tests:** plain-text loop results (T1.6); custom-content citation ranges (T1.9); Citations, thinking and effort on Opus (T1.8); Markdown straddling (T1.11).
  - **For Phase 4:** the user's review of both prompt drafts (T1.14).
  - **For Phase 5:** the Sonnet against Opus composition comparison (T1.8), and every placeholder measured.
  - **For Areas 2 to 5:** their own items.

**Failures:**
- Phase 1's verification had skipped section headings by design, and *Oliver*'s missing "II" had passed the agents. Found while designing T1.6; a read-only structure check of all headings and footnote markers followed (one defect, none in markers).
- Estimates later corrected by measurement:
  - the corpus catalog, estimated at 4,000 to 5,000 tokens, counted at 7,257
  - a paragraph, "about 150 tokens", is about 231 (median) once section headings are excluded
- The Phase 2 sentence splitter broke citations (491 suspicious splits across the corpus); replaced by a conservative splitter (T1.9).
- My quick rule for resolving short citations matched two citations to the wrong corpus case; caught by the cross-check against CourtListener's graph and fixed with a page-range rule, before the lookup was cut (T1.13).
- I recommended prose-only answers, then withdrew it when the Phase 2 answers showed no citation crossing Markdown structure (T1.11).
- Two times written with "~" in working files were replaced by `date` readings before commit.

**Spend:** Anthropic: 1 call, $0.1422 (the chunking probe, Sonnet 5.5 at low effort); token counting free. Ledger total $0.6964 of the $2.00 ceiling. No Exa or Voyage calls.

**DECISION (user):**
- How Phase 3 runs: *"I want us to compact after each area, so how about you keep a working document for yourself somewhere of your choosing within this repo. (It's fine to have git track this document.)"* And, on the record: *"Don't forget we're ALWAYS keeping BUILD LOG updated with system time as well."*
- The four topics the user added to Area 1, verbatim:
  1. *"I'm concerned of the fragile deterministic case-name verifier, particularly how do we recognize robustly what is a case name to check within Claude's answer without requesting Claude to write it as structured output (which breaks Citations feature). I'm considering not offering this if it's something we cannot check reliably. The response is covered under the AI disclosure already, and adding a check that isn't reliable might give false confidence to user."*
  2. *"On search corpus, I'm pondering whether we'd want to also offer a keyword-based search tool in addition as well for Claude to dynamically pick and choose thru its research loop."*
  3. *"For all search tools, should we consider giving Claude more filtering options before the search is ran? Claude can filter by date, for example, or exclude any passage containing certain words, etc."*
  4. *"From the current architecture, the Composition call is the only place where Citations is in action, which makes sense because for Citations to work, we must not be using structured output. However, with the context of legal citation, citing a sentence (within the context of a passage) is often a more frequent practice than citing whole passage. This is from my experience in Constitutional Law class back in college. Thus, I want us to explore giving Claude flexibility in deciding not only what to cite but also how much to cite. Then, in the source panel, we always show the sentence within a paragraph."*
- On usage: *"don't send any subagent out again because this is a targeted fix. I also want to conserve usage as well. Push back otherwise."*

## Oct 24, 2026, 17:18 CDT — Phase 3: Architecture, Area 2 (the update-check tool's inputs, T2.1)
**Asked:** Resume Phase 3 after the compaction with Area 2, the update check: topics first, then topic 1, what Claude sets on `search_web_updates`, what our server limits, and what the check costs.
**Came back:**
- Area 2's five topics, confirmed by the user: the tool's inputs, limits and cost; what a result looks like to Claude; the band's summary and links; errors and unavailability; the MCP connection. Raised for topic 3: P1.3's internal Citations grounding of web results has nothing to run on, since loop results are plain text (T1.6) and the band's summary is written in the loop (T1.11).
- Facts for topic 1, from Phase 2's `tools/list` and the agent's reading of Exa's tool source: crawl dates are ignored by the API; `includeText` and `excludeText` are deprecated; `additionalQueries` works only with deep types the tool cannot send; `fast` and `instant` are legacy; `lite` is cache-only and refuses most optional fields; the `pdf` and `github` categories are being deprecated; `company` and `people` refuse date filters; summaries are Exa-written text at $1 per 1,000 pages. Phase 2 probe: `auto` $0.007 and about 1.9 s of Exa's search time, `lite` $0.004 and about 0.3 s. Exa accepts up to 1,200 domains per list, as hostnames, path prefixes or subdomain wildcards.
- The brief's "Claude controls every search field" read two ways (every field Exa offers, or every field of our wrapper as §6.2 lists them); restated before proposing.
- T2.1 locked: see `docs/design/locked-decisions.md`.
**DECISION (user):**
- Topics: *"The five topics work. Open topic 1."*
- The one correction to the proposal: *"I only have 1 correction here, for include and exclude domains, set a high limit (100) to prevent overrun only and give Claude flexibilities."*
- T2.1: *"Lock topic 1 as T2.1: reading B, domains up to 100 each, the rest as proposed."*

## Oct 24, 2026, 17:33 CDT — Phase 3: Architecture, Area 2 (what a web result looks like to Claude, T2.2)
**Asked:** Area 2, topic 2: how an update-check result reaches Claude. The user distrusted Exa's highlights, chose 4,000 characters and asked how the text is made, asked why converting Exa's dates would lose accuracy, and then chose to take Exa's date as written.
**Came back:**
- From Exa's cached docs: `text` is the page's full text, converted to clean markdown with ads and navigation stripped; the character cap shortens that text (the opening, INFERRED from "limit"); highlights are "Text snippets the LLM identifies as most relevant", so model-chosen; the API's main-content and section settings are not exposed by the MCP tool, so Exa's defaults apply.
- Size at 4,000 characters: about 10,000 to 13,000 tokens a 10-result search (estimate), about $0.01 to $0.02 more a run than 2,000 for one update search.
- Dates (script on the Phase 2 probe summary): 28 of 32 dated results at exactly midnight UTC, 4 with a real time (news pages, e.g. Reuters 2026-06-29T14:17:34Z); every supremecourt.gov result at midnight UTC or undated. Read as a moment and converted, the Court's *Chatrie* page (2026-06-29T00:00Z) would show as June 28 in every U.S. zone, before the decision; so midnight values are printed dates. A rule with visitor-zone conversion for real moments was proposed, then replaced by the user's simpler choice.
- T2.2 locked: see `docs/design/locked-decisions.md`.
**Failures:** My first explanation of the date problem did not make clear why converting would lose accuracy; the user asked, and the supremecourt.gov example answered it.
**DECISION (user):**
- *"I'm leaning not trusting Exa's highlight here."* *"Let's keep 4000 but is this 4000 first characters of all pages? Not excerpts within a page? How are these characters generated?"*
- *"Wait I'm not clear on how you're saying converting date will lose accuracy here."* *"By frontend's time zone, I mean the timezone of every visitor's browser."* Then: *"Oh I see. In that case, what about we don't bother with handling date at all?"* and *"I mean take Exa's date as written, with no conversion"*.
- T2.2: *"Lock topic 2 as T2.2 as restated."*

## Oct 24, 2026, 17:40 CDT — Phase 3: Architecture, Area 2 (the band's summary and links, T2.3)
**Asked:** Area 2, topic 3: how the update-check band's summary is written and tied to its sources, given the conflict found when Area 2 opened. The user chose option A and asked to go through its details.
**Came back:**
- The conflict: P1.3 assumed Citations would ground the band's sentences, but the summary is written in the loop (T1.11), where web results are plain text (T1.6, T2.2) and a tool input carries no citations.
- Three options: (A) structured findings in `submit_answer`, each statement naming the `web-` IDs it rests on, checked by our code; (B) a separate Citations call after the loop (estimate +$0.02 to $0.08 a run), its `cited_text` discarded; (C) free text plus a list of links. Recommended A: no web text reaches the page either way, a Citations pointer proves only that a span exists, not that it supports the statement, and A costs nothing.
- Eight details of A proposed and accepted: fields and caps; when they are checked; a copy guard against republishing page text; the outcome worked out by our code; out-of-scope and nothing-kept runs; the fallbacks; the band's contents; what replays store.
- T2.3 locked: see `docs/design/locked-decisions.md`. P1.3 and T1.10 marked amended.
**DECISION (user):**
- *"Go with option A, structured findings in submit_answer. Let's go through the details."*
- T2.3: *"Lock topic 3 as T2.3: option A with the eight details as proposed."*

## Oct 24, 2026, 17:43 CDT — Phase 3: Architecture, Area 2 (errors and unavailability, T2.4)
**Asked:** Area 2, topic 4: what happens when the update check fails or is unavailable.
**Came back:**
- Facts from Phase 2 and the agent's reading of Exa's tool source: Exa's refusals arrive as error tool results (the 400 and 401 seen in Phase 2), transport and gateway failures as protocol errors (the 1 MB event limit); 402 `NO_MORE_CREDITS` when the credit runs out, back on the 1st (reset time zone undocumented); 429 above 10 queries a second team-wide; Exa retries its own 500 to 504 twice (P2.8); its tool aborts at 300 s. The tool list and system prompt are fixed and cached (T1.14), so the tool cannot be withdrawn while unavailable.
- Proposal: four kinds of failure (refused by our code, refused by Exa, failed, unavailable), each with what Claude gets, whether it counts toward the 3 searches and what cost is recorded; a monthly unavailability flag in Atlas; a 30 s timeout as a placeholder; no retries by our code.
- T2.4 locked: see `docs/design/locked-decisions.md`.
**DECISION (user):**
- T2.4: *"Lock topic 4 as T2.4 as proposed."*

## Oct 24, 2026, 17:46 CDT — Phase 3: Architecture, Area 2 (the MCP connection, T2.5)
**Asked:** Area 2, topic 5: how our backend holds its connection to Exa's hosted MCP server.
**Came back:**
- Facts: Exa's hosted server is stateless (a fresh handler per request, from its source) over streamable HTTP; the Phase 2 probe used the official `mcp` package (2.3.0) with the key in the `x-api-key` header and one session for several calls; the handshake was not timed.
- Three options: a session per search, per run, or one kept open for the instance. Recommended per search: a stateless server gains only the handshake from a held session, a held session can go stale while the instance idles or is throttled, and per-search keeps one run's failures from another's.
- T2.5 locked: see `docs/design/locked-decisions.md`.
**DECISION (user):**
- T2.5: *"Lock topic 5 as T2.5: a session per search, the rest as proposed."*

## Oct 24, 2026, 17:46 CDT — Phase 3: Architecture, Area 2 closed (the update check)
**Asked:** After the compaction, run Area 2, the update check through Exa's MCP server, topic by topic, then prepare the next compaction.
**Came back:**
- Five decisions, T2.1 to T2.5, each with its own entry above (17:18, 17:33, 17:40, 17:43, 17:46):
  - T2.1: Claude sets the fields of our own wrapper (brief §2 read as the §6.2 list): query, optional published dates, domains up to 100 each, `news` or `publication`, `auto` or `lite`, 1 to 10 results; summaries, crawl dates, text filters, subpages and the rest left out; 3 searches a run; Exa's cost counted toward the caps.
  - T2.2: one plain-text block per page with our `web-` IDs; the opening 4,000 characters of Exa's cleaned text inside data markers; no highlights; Exa's dates taken as written, with no conversion.
  - T2.3: the band's statements as structured findings in `submit_answer`, each naming its sources, checked by our code, with a copy guard against republishing page text; the outcome worked out by our code.
  - T2.4: four kinds of failure; a monthly out-of-credit flag in Atlas; a 30 s timeout (placeholder); no retries by our code; no raw error on the page.
  - T2.5: a session per search to Exa's server; a schema check that warns.
- Amended along the way: P1.3 (Citations no longer ground the band; Claude names sources, our code checks them) and T1.10 (two new `submit_answer` fields), by T2.3. One exception to brief §10.7 recorded in T2.2 (Exa's dates as written).
- Carried forward, recorded in `docs/design/phase3-working.md`:
  - **Area 3:** the Exa key's route into Cloud Run; the Atlas flag (T2.4); Exa's cost in the spend counters (T2.1); no Exa call while nobody is connected.
  - **Area 4:** the band's layout, its outcomes and the collapsed list of pages (T2.3).
  - **Area 5:** the honesty label; a replacement for brief §6.4's guarantee sentence; source links never called verified; the "not summarised" and "unavailable" wording (T2.3, T2.4).
  - **Build and Phase 5:** inspect what the first 4,000 characters of real pages hold; measure the cap, the copy guard's 10 words, the 30 s timeout and the handshake; trigger every failure kind.
**Failures:** My first explanation of why converting Exa's dates loses a day did not make the reason clear; the user asked, and the supremecourt.gov example answered it (T2.2).
**DECISION (user):**
- Area 2's topics: *"The five topics work. Open topic 1."*
- The user's own calls along the way: *"for include and exclude domains, set a high limit (100) to prevent overrun only and give Claude flexibilities"*; *"I'm leaning not trusting Exa's highlight here."*; *"Let's keep 4000"*; *"I mean take Exa's date as written, with no conversion"*; *"Go with option A, structured findings in submit_answer."*
- The five locks: *"Lock topic 1 as T2.1: reading B, domains up to 100 each, the rest as proposed."* *"Lock topic 2 as T2.2 as restated."* *"Lock topic 3 as T2.3: option A with the eight details as proposed."* *"Lock topic 4 as T2.4 as proposed."* *"Lock topic 5 as T2.5: a session per search, the rest as proposed."*

## Oct 24, 2026, 17:55 CDT — Phase 3: Architecture, Area 3 (starting a run and streaming it, T3.1)
**Asked:** Open Area 3 (run lifecycle and infrastructure) after the compaction, topics first; then topic 1: how a run starts and how it reaches the page.
**Came back:**
- Area 3's topics: the six drafted before the compaction, with Cloud Run split into its infrastructure (topic 5) and its start-up and wake protocol (topic 6), and the paid calls (topic 3) moved before the spend counters (topic 4). Confirmed by the user.
- Facts for topic 1: the Phase 2 loop turns held only tool calls, no text from Claude, and empty thinking blocks (thinking text is omitted by default); content paragraphs average 774 characters (script), so a run's passage text is about 80 to 120 KB (estimate); the corpus files are 2.4 MB.
- Three transports compared: Server-Sent Events with a create request and a stream request; one streaming POST plus a reconnect GET; WebSocket (Cloud Run passes its disconnects on, but it needs a goodnight change and a hand-written resume, and a suspended iPhone page still needs a liveness signal). Recommended Server-Sent Events, the answer streamed one text block at a time, thinking summaries off, passage text inside the events.
- T3.1 locked: see `docs/design/locked-decisions.md`.
**DECISION (user):**
- Topics: *"The seven topics work. Open topic 1."*
- T3.1: *"Your recommendations work here. Lock and proceed."*

## Oct 24, 2026, 17:58 CDT — Phase 3: Architecture, Area 3 (disconnect detection and the grace window, T3.2)
**Asked:** Area 3, topic 2: how the server knows the page is still connected, so no paid call starts while nobody is (brief §2, P2.10).
**Came back:**
- Facts from the Phase 2 Cloud Run notes: Cloud Run passes a client disconnect to the container only over WebSockets or end-to-end HTTP/2; goodnight is itself a Cloud Run service on HTTP/1.1, so its nginx probably never sees the browser leave; nginx proxies HTTP/2 upstream only since 1.29.4 (goodnight's version not recorded); Anthropic still charges an abandoned request that was on track to succeed. Inferred: our stream request stays open in the container after the browser leaves until our code ends it.
- Options: a heartbeat from the page; end-to-end HTTP/2 through goodnight and the API (two goodnight changes, still blind to a half-open connection); WebSocket (set aside by T3.1). Recommended the heartbeat, with placeholder timings (10 s heartbeat, 25 s attended, 60 s grace, 45 s page watchdog).
- T3.2 locked: see `docs/design/locked-decisions.md`.
**Failures:** In the working doc I wrote topic 2's opening time as 17:59 CDT before running `date`, which then read 17:57. Corrected in the working doc (commit `8b27450`); no log heading was affected.
**DECISION (user):**
- T3.2: *"Lock option A. Proceed."*

## Oct 24, 2026, 18:04 CDT — Phase 3: Architecture, Area 3 (the paid calls during a run, T3.3)
**Asked:** Area 3, topic 3: how the Claude and Voyage calls behave during a run (timeouts, errors, budgets, caching). The user then directed retries: *"I'm leaning allowing retries for both Anthropic and Voyage. Especially when Voyage fails, I want to display a warning to user that quality of this response is affected due to this."*
**Came back:**
- Facts: Anthropic's errors page (a spend-limit 400; rate-limit and spend-cap 429s; 500, 504, 529; errors after a stream has started; retry 500 and 529 with backoff); the loop's share of the per-run budget is 8,000 output and 370,000 input tokens once T1.11's composition reserve is held back (Phase 2 loops used 2,906 and 1,622 output tokens); Voyage's limits are per minute and per organisation, a free-trial organisation moves to Tier 1 by adding a payment method, and the free-trial figures are not on the cached pages.
- First proposal: streamed Claude calls with no retries; on a transient loop failure, compose from what was kept. Revised at the user's direction: visible retries by our own code for Anthropic and Voyage, with four cautions (no retry on our own deadline, which may pay twice; none on the spend-cap 429; composition retried only before its first block; the SDK's hidden retries stay off); Voyage degrades to unreranked results or points Claude to keyword search, and the page warns. Wording "quality is affected" narrowed to "meaning search was degraded or unavailable", since the effect on the answer is not measured (final wording Area 5).
- T3.3 locked: see `docs/design/locked-decisions.md`. Supersedes brief §10.7's "a paid request is never retried automatically" for Anthropic and Voyage calls; amends P2.8 and T1.11. Exa keeps T2.4 (no retries by our code). The live-run request stays never retried (brief §8.5).
- Pending with the user: the Voyage organisation's tier and per-minute limits, read from the Atlas console.
**DECISION (user):**
- Retries: *"I'm leaning allowing retries for both Anthropic and Voyage. Especially when Voyage fails, I want to display a warning to user that quality of this response is affected due to this."*
- T3.3: *"Lock topic 3 as T3.3 with retries as revised; compose from what was kept after retries run out."*

## Oct 24, 2026, 18:13 CDT — Phase 3: Architecture, Area 3 (spend counters and caps, T3.4)
**Asked:** Area 3, topic 4: how spend is counted and the $10 daily and $60 monthly caps enforced (P2.6, P2.7, brief §8.1, §8.4). Before it, the user stated the Voyage tier: *"I'm on Usage tier 1 for Voyage. Practically, we will never hit any limit. It's only during initial processing where we process every passage that we're at risk."*
**Came back:**
- The cache-read price conflict settled from Anthropic's pricing page (cached Oct 24, 13:29 CDT): Sonnet 5.5 $0.10 per million, Opus 5.5 $0.20; the claude-api skill's $0.20 for Sonnet is wrong, findings §3 stands.
- Worst-case run cost from the T3.3 budget, by arithmetic: about $1.67 (loop input $0.943, loop output $0.08, composition $0.36, two composition attempts failing before their first block $0.24, Exa $0.021, Voyage under $0.03).
- Three options: check at the start only; reserve the worst case at the start (B1); reserve a typical amount and extend during the run (B2). Recommended B1: one Atlas document per Chicago month, so the check and the reservation are one atomic update and the caps are never overshot however many instances run.
- At the user's direction, every budget stop is recorded in Atlas (counts per day and a record per refusal) with a read-only report script.
- T3.4 locked: see `docs/design/locked-decisions.md`.
**Failures:** In the working doc I wrote topic 4's opening time as 18:08 CDT; the clock read 18:09. Corrected in the working doc (commit `f21948f`). From here on `date` runs in its own step before any time is written.
**DECISION (user):**
- B1 and the budget log: *"B1 is good, but I'd also want it logged in our database how many times have a run failed due to budget as well. This is for me to keep an eye on usage and refusal just in case."*
- T3.4: *"Record everything stopped due to budget regardless of how as long as it's a budget concern. Lock otherwise."*

## Oct 24, 2026, 18:26 CDT — Phase 3: Architecture, Area 3 (Cloud Run and the gateway, T3.5)
**Asked:** Area 3, topic 5: the two Cloud Run services, timeouts, concurrency, secrets, the goodnight gateway and the client IP. The user cleared a read of goodnight: *"You're clear to read goodnight's nginx.conf and its Cloud Run settings. Don't bring any of its code over here though--contamination."*
**Came back:**
- Facts from Phase 2 (findings §6): request timeout default 300 s, maximum 3,600 s; max instances exceeded during deploys and replacements, with in-flight grace up to the request timeout; the previous build's API at 512 MiB, 1 vCPU, concurrency 80, 300 s.
- goodnight, read only (its `nginx.conf`, `deploy.sh`, `Dockerfile` and `gcloud run services describe`; nothing copied into this repo): the domain's front door, one routing block per app; its live revision has a 300 s request timeout, max 1 instance, concurrency 250, 256 MiB, startup boost, min 0; unpinned `nginx:alpine`. So a stream through it is cut at 300 s and resumes by T3.1, with no change to goodnight's timeout; visitors' IPs stay in goodnight's own request logs, outside this project.
- The user's answers: Atlas open to all addresses, cluster in GCP us-central1, database `Probable_Clause` created; client IP dropped; Secret Manager. Then: the URI's user is readWrite on `Probable_Clause` only, plus `Probable_Clause_test` for testing; GCP project `probable-clause` created (number 1066460440617, confirmed ACTIVE with a read-only `gcloud projects describe`).
- T3.5 locked: see `docs/design/locked-decisions.md`.
**DECISION (user):**
- Atlas and the IP: *"Atlas cluster is opened to all IPs, so with the URI you're covered."* *"Cluster is in GCP / Iowa (us-central1). I already set up a new empty database in the cluster for you, named Probable_Clause"* *"Good on both notes."*
- Database user, test database, project: *"URI is limited to readWrite only on Probable_Clause."* *"I've added a new db Probable_Clause_test to the MongoDB cluster, and your URI now also has readWrite against that db too for you to test."* *"probable-clause (id) project created on GCP. Project number 1066460440617."*
- T3.5: *"Lock otherwise."*

## Oct 24, 2026, 18:28 CDT — Phase 3: Architecture, Area 3 (start-up and the wake protocol, T3.6)
**Asked:** Area 3, topic 6: what the API loads at start, how its start is timed, and how the page wakes it (brief §8.1, §8.5), with T1.1's two open points (vectors in memory; a header on the embedded text).
**Came back:**
- Facts: brief §8.5's protocol and the previous build's measured starts (12.6 to 32.4 s after deploys, 21.5 to 49.5 s after idle, app ready 1 to 5 s after its process started); Cloud Run holds a request during a start for at least 10 s, then 429 or 500 (findings §6); goodnight also scales to zero (T3.5); voyage-law-2's 1,024 dimensions make the vectors 11.3 MB as float32 (arithmetic); FTS5 indexes the corpus in 0.04 s; uvicorn opens its port after the app's startup (inferred from its log order).
- Proposal: vectors in memory; the vectors file built once and committed with a manifest; the keyword index built at start; everything loaded and timed before the port opens; `/health` ready-only with T3.4's status; the page's wake handling, a fresh check before each run, and the long-wait states (90 s, 5 minutes; placeholders); measurement as brief §8.5; a one-line header on the text Voyage embeds.
- T3.6 locked: see `docs/design/locked-decisions.md`. T1.1's open points are settled.
**DECISION (user):**
- T3.6: *"Lock topic 6 as T3.6: vectors in memory, the vectors file committed, the header on embedded text, the rest as proposed."*

## Oct 24, 2026, 18:38 CDT — Phase 3: Architecture, Area 3 (protections and retention, T3.7)
**Asked:** Area 3, topic 7: input caps, tool-input handling, safe rendering, what is stored and for how long, and the privacy note (brief §8.3).
**Came back:**
- Facts: brief §8.3; Anthropic's strict tool use allows at most 24 optional parameters across all strict schemas and no numeric or length constraints (structured-outputs page, cached), so it likely cannot cover every tool here; the question reaches every Claude call, and Claude's searches reach Voyage and Exa.
- Proposal: a 2,000-character question cap (placeholder) checked before any paid call; our code validating every tool input, strict mode only where it fits; Markdown rendered with raw HTML off and only Exa-returned `http`/`https` links; retention per record type; no question, query or answer text in logs; no cookies or analytics; the privacy note's contents. One choice for the user: run events kept 24 hours or 1 hour.
- T3.7 locked: see `docs/design/locked-decisions.md`.
**DECISION (user):**
- T3.7: *"Lock topic 7 as T3.7 with run events kept 24 hours, the rest as proposed."*

## Oct 24, 2026, 18:38 CDT — Phase 3: Architecture, Area 3 closed (run lifecycle and infrastructure)
**Asked:** Run Area 3 after the compaction, topics first, one topic at a time, each locked in the user's words.
**Came back:**
- Seven topics, confirmed by the user, all locked:
  - T3.1 (17:55): starting a run and streaming it — Server-Sent Events (`POST /runs`, `GET /runs/{id}/events`), the loop starting when the first stream attaches, numbered events, the answer one block at a time, no thinking summaries, passage text in the events, memory first with Atlas copies, replays in the same format.
  - T3.2 (17:58): disconnect detection — a heartbeat from the page (10 s; attended under 25 s; abandoned 60 s after the last; page watchdog 45 s), checked before every paid call.
  - T3.3 (18:04): the paid calls — streamed Claude calls, per-call deadlines, the loop's 370,000 / 8,000-token share of the budget, visible retries by our code for Anthropic and Voyage, composition from what was kept once retries run out, a page warning when meaning search was degraded.
  - T3.4 (18:13): spend counters and caps — the worst case (about $1.67) reserved atomically at the start in one Atlas document per Chicago month, settled as calls complete; every budget stop recorded; a Console workspace limit as backstop; test runs on their own database.
  - T3.5 (18:26): Cloud Run and the gateway — the `probable-clause` project, the two services' settings, a 900 s API timeout, a 10-minute run deadline, one new goodnight block forwarding no client IP, Secret Manager, Atlas `Probable_Clause` and `Probable_Clause_test`.
  - T3.6 (18:28): start-up and the wake protocol — vectors in memory, the vectors file committed, a header on the embedded text, everything loaded and timed before the port opens, the page's wake handling and long-wait states.
  - T3.7 (18:38): protections and retention — a 2,000-character question cap, every tool input validated, safe rendering, run events kept 24 hours, statistics without question text kept, no cookies or analytics, the privacy note's contents.
- Superseded or amended: brief §10.7's "a paid request is never retried automatically", for Anthropic and Voyage calls (T3.3); P2.8 and T1.11 amended (T3.3); T1.1's open points settled (T3.6). The brief §8.2 per-visitor limit was already gone (P2.6).
- Read with the user's permission: goodnight's configuration and Cloud Run settings, read only, nothing copied into this repository.
- Carried forward: the working doc's "Area 3 closed" section (build, interfaces contract, Phase 5 measurements and tests, Areas 4 and 5); Area 4's proposed topics drafted there for after the compaction.
**Failures:** Two working-doc times written before reading the clock (topic 2 at 17:59 for 17:57; topic 4 at 18:08 for 18:09), both corrected and logged in the T3.2 and T3.4 entries; `date` now runs in its own step before any time is written.
**DECISION (user):**
- Topics: *"The seven topics work. Open topic 1."*
- T3.1: *"Your recommendations work here. Lock and proceed."*
- T3.2: *"Lock option A. Proceed."*
- T3.3: *"I'm leaning allowing retries for both Anthropic and Voyage. Especially when Voyage fails, I want to display a warning to user that quality of this response is affected due to this."* Then *"Lock topic 3 as T3.3 with retries as revised; compose from what was kept after retries run out."*
- Voyage tier: *"I'm on Usage tier 1 for Voyage. Practically, we will never hit any limit. It's only during initial processing where we process every passage that we're at risk."*
- T3.4: *"B1 is good, but I'd also want it logged in our database how many times have a run failed due to budget as well. This is for me to keep an eye on usage and refusal just in case."* Then *"Record everything stopped due to budget regardless of how as long as it's a budget concern. Lock otherwise."*
- goodnight read: *"You're clear to read goodnight's nginx.conf and its Cloud Run settings. Don't bring any of its code over here though--contamination."*
- T3.5: Atlas open to all addresses, in us-central1, database `Probable_Clause`; client IP dropped and Secret Manager (*"Good on both notes."*); the URI's user readWrite on `Probable_Clause` and `Probable_Clause_test`; the GCP project `probable-clause` (1066460440617); *"Lock otherwise."*
- T3.6: *"Lock topic 6 as T3.6: vectors in memory, the vectors file committed, the header on embedded text, the rest as proposed."*
- T3.7: *"Lock topic 7 as T3.7 with run events kept 24 hours, the rest as proposed."*

## Oct 24, 2026, 18:50 CDT — Phase 3: Architecture, Area 4 (art direction, T4.1)

**Asked:** Open Area 4 (the interface) after the compaction. On the first draft of nine topics, the user pointed out that the frontend prototype is done and locked, and asked what that changes about the area. Then, with five topics confirmed, record the art-direction T-entry (P1.6) for the user's sign-off.

**Came back:**
- Area 4 re-scoped: the prototype (`web/looktests/machinery/`, commit badc05f) is the baseline, and what it shows stays. The area covers only what it leaves open, what Areas 1 to 3 force on it, and what it never built. Five topics: (1) record the lock; (2) the frontend stack; (3) where Areas 1 to 3 change the prototype ("discarded" cards against P2.3, the band's draft label against T2.3, the red verifier flag against T1.12, "View source" needing the whole opinion against T3.1, "View API calls" contents with composition and custom documents, T1.9); (4) new pieces in the prototype's style (states outside a normal run, retries and pauses, the answer's stop labels); (5) whether each call's cost is shown.
- T4.1 drafted from the fold-ins (Oct 23, 20:48; Oct 24, 13:59) and the frontend log (19:04 to 20:18), each point checked in the prototype's code (the wordmark's "l" in its own span, the Google Fonts link, `prefers-color-scheme`, `--chat: 51.25rem`). Locked as T4.1.

**DECISION (user):** *"Wait, the frontend prototype is done and locked. What will that change about this area?"* *"The five topics work. Open topic 1."* Then: *"Lock topic 1 as T4.1 as drafted."*

## Oct 24, 2026, 18:52 CDT — Phase 3: Architecture, Area 4 (the frontend stack, T4.2)

**Asked:** Area 4, topic 2: choose the frontend stack (brief §2 default 1, "Frontend chosen in Phase 3").

**Came back:**
- Facts: the prototype is three files (about 1,470 lines), plain JavaScript, no library, no build step, building markup with `innerHTML` and an escape helper; its stale-cache trouble was handled with `?v=` query strings, which T4.1 drops. Node 26.8.1 and npm 11.7.0 are on this machine.
- Options laid out: (A) plain JavaScript as ES modules, no build step, one vendored Markdown library; (B) Vite with plain TypeScript; (C) a component framework, a rewrite of the locked prototype. Recommended A. Locked as T4.2.

**DECISION (user):** *"Lock topic 2 as T4.2: option A as proposed."*

## Oct 24, 2026, 18:54 CDT — Phase 3: Architecture, Area 4 (where Areas 1 to 3 change the prototype, T4.3)

**Asked:** Area 4, topic 3: the changes Areas 1 to 3 force on the locked prototype (T4.1), each the smallest change to what is built.

**Came back:**
- Read in the prototype's `run.js`: Reviewing → Kept or Discarded cards with reasons; a syllabus card and reader; four hues for four kept passages with an ID pill after each citation; the band as one summary, a links list and one parameter list; a case-name check step with a wavy red underline; `search_result_location` citations; `submit_answer` with a `kept` list; mock reader text with one source credit for every case; the API window built from per-passage request and response fragments.
- Corpus case files measured by script: 32 files, 2,454,857 bytes, the largest 320,464; each paragraph carries `page_start` and `page_breaks`.
- Seven changes proposed (cards, syllabus, hues, the band, the checks, View source, View API calls), with two choices: the reader's opinion text from static per-opinion files on the web service (6a, amending T3.1), and exact API fragments carried in the events (7b). Locked as T4.3.

**DECISION (user):** *"Lock topic 3 as T4.3: the seven changes as proposed, 6(a) and 7(b)."*

## Oct 24, 2026, 18:56 CDT — Phase 3: Architecture, Area 4 (new pieces in the prototype's style, T4.4)

**Asked:** Area 4, topic 4: where the states and labels the prototype never built go, in its existing elements and styles.

**Came back:**
- Read in the prototype's `index.html`: the status line above the composer, the composer ("Ask another question", "Skip to the end"), the landing's recorded-run chips, the disclaimer with folded sources and credits.
- Twelve placements proposed: waking and the long wait; paused by a cap or Atlas unreachable; reconnecting, paused and resumed; retries inside their step; interrupted and abandoned; reload reattaching; the Voyage warning above the answer; stop labels at the top or end of the answer; a failed composition with no try-again; no-sources replies; replays labelled with their Chicago recording date, "Skip to the end" for replays only; one question per run, the composer starting a fresh run screen. Locked as T4.4; T3.7's "to confirm in Area 4" (follow-ups as new runs) settled.

**DECISION (user):** *"Lock topic 4 as T4.4 as proposed."*

## Oct 24, 2026, 19:00 CDT — Phase 3: Architecture, Area 4 (costs shown, T4.5)

**Asked:** Area 4, topic 5: whether each call's cost is shown (left open by T3.1).

**Came back:**
- Options laid out: (A) nothing; (B) one run-total line when the run ends, split by service on expand; (C) B plus figures on every step; (D) each response's exact `usage` object in "View API calls". Recommended B with D.
- The user's change: Voyage left out of the shown cost, since its use is very likely within its free tokens. Restated: the total line covers Claude (loop and answer) and Exa and says so; T3.4's caps still count Voyage at list price (display change only). Locked as T4.5.

**DECISION (user):** *"Voyage is very likely free because we make so few requests that it'd still be within free tier even tho I added money to the account and am at Tier 1. So just total up Claude and Exa code with option B and D?"* Then: *"This matches what I wanted. Lock area 4."*

## Oct 24, 2026, 19:00 CDT — Phase 3: Architecture, Area 4 closed (the interface)

**Asked:** Run Area 4 after the compaction, one topic at a time, each locked in the user's words. On the first draft of nine topics the user pointed out that the prototype is done and locked, so the area was re-scoped to what the prototype leaves open.
**Came back:**
- Five topics, confirmed by the user, all locked:
  - T4.1 (18:50): art direction — the machinery prototype in Evergreen (commit badc05f) as the build's baseline: the landing-to-chat flow, the sources column, underlined citations with hover, the answer key, "View API calls" and "View source", the wordmark, palette, type, the 51.25rem width, the three test sizes; the prototype-only parts dropped.
  - T4.2 (18:52): the frontend stack — plain JavaScript modules, no build step, markdown-it vendored with raw HTML and links off, elements built with text, a pinned nginx web service with `Cache-Control: no-cache`, Node's built-in test runner.
  - T4.3 (18:54): where Areas 1 to 3 change the prototype — cards Found, Kept, then kept and cited, kept not cited, or not kept; no syllabus; hues repeating in keep order; the band in T2.3's shape; the two checks' flags and line; the reader fetching per-opinion files from the web service; exact API fragments in the events.
  - T4.4 (18:56): new pieces in the prototype's style — waking and the long wait, cap-paused, reconnecting, retries, interrupted and abandoned, reload, the Voyage warning, stop labels, a failed composition, no-sources replies, replays, one question per run.
  - T4.5 (19:00): costs — a run total for Claude and Exa, labelled so, and each response's exact `usage` in the API window; Voyage not shown, still counted by the caps.
- Amended: T3.1 (the reader fetches whole opinions as static files, T4.3). Settled: brief §2 default 1 (frontend stack, T4.2); T3.7's follow-up question (T4.4).
- Carried forward: the working doc's "Area 4 closed" section (build, interfaces contract, Phase 5, Area 5); Area 5's proposed topics drafted there for after the compaction.
**DECISION (user):**
- Scope: *"Wait, the frontend prototype is done and locked. What will that change about this area?"* Then *"The five topics work. Open topic 1."*
- T4.1: *"Lock topic 1 as T4.1 as drafted."*
- T4.2: *"Lock topic 2 as T4.2: option A as proposed."*
- T4.3: *"Lock topic 3 as T4.3: the seven changes as proposed, 6(a) and 7(b)."*
- T4.4: *"Lock topic 4 as T4.4 as proposed."*
- T4.5: *"Voyage is very likely free because we make so few requests that it'd still be within free tier even tho I added money to the account and am at Tier 1. So just total up Claude and Exa code with option B and D?"* Then *"This matches what I wanted. Lock area 4."*

## Oct 24, 2026, 19:14 CDT — Phase 3: Architecture, Area 5 (the standing lines, T5.1)
**Asked:** Resume Phase 3 after the compaction with Area 5 (the user's wording and the replays); confirm its topics; open topic 1, the lines that sit on every screen; then lock it.
**Came back:**
- Area 5's six topics confirmed, with the text-status note added to topic 2.
- Read in the prototype (read only): the pitch, the trace figure's caption, the landing footer, the run screen's disclaimer and folded credits. Two placeholders were inaccurate: the credit gave CourtListener as the source of all text (by `data/corpus/README.md`, 25 cases come from CourtListener's Lawbox copies, 6 from the official U.S. Reports on GovInfo, *Chatrie* from the slip opinion), and the disclosure named one model where two run (T1.8). The trace figure still showed `search_result_location`, replaced by custom content documents in T1.9.
- Drafts with recommendations for the pitch, the caption, the not-legal-advice line, the AI disclosure (Usage Policy and Commercial Terms requirements, licensing.md §5), the affiliation line, sources and credits (Free Law Project non-endorsement, licensing.md §2), the reader's three credit lines, and "live" (brief default 6); five questions for the user.
- T5.1 locked: the lines as restated after the user's answers, with brief defaults 2 (Apache 2.0) and 6 ("live") settled.
**DECISION (user):**
- Topics: *"The six topics work, with the text-status note added. Open topic 1."*
- Answers: *"1. We can link to the repo, which is https://github.com/NguyenTran2002/probable-clause. No need to mention my name though. 2. Leave out it is. 3. I'll give it Apache 2.0. 4. We're going with 2b anyway. 5. Live wording is correct."*
- T5.1: *"Lock."*

## Oct 24, 2026, 19:18 CDT — Phase 3: Architecture, Area 5 (the guarantee, coverage and checks, T5.2)
**Asked:** Open topic 2 (the guarantee, coverage, answer key, the checks' line and flags, the cost label, the text-status note); then lock it with the recommended drafts.
**Came back:**
- Read in the prototype's `run.js` (read only): the card's guarantee, the answer key, the old case-name flag note, the reader's text-status sentence.
- Three placeholders said more than holds: "verbatim in this opinion" is true of the normalised corpus copy; "rest on a passage" overstates what a citation shows (brief §1); T1.12's example line says "cited passages", but its quotation check compares against the kept passages and allows standard quoting edits.
- Facts by script from the manifest: 32 cases decided 1878-05-13 to 2026-06-29; the full-pull and corpus latest dates are the same day; ingested 2026-10-23.
- Drafts with recommendations for six lines; T5.2 locked with every recommendation. T1.12's example line is reworded by it.
**DECISION (user):**
- T5.2: *"Lock topic 2 as T5.2 with the recommended drafts."*

## Oct 24, 2026, 19:21 CDT — Phase 3: Architecture, Area 5 (the update-check band, T5.3)
**Asked:** Open topic 3 (the update-check band's wording); then lock it with the recommended drafts.
**Came back:**
- Read in the prototype's `run.js` (read only): the band's heading, brief §6.4's draft label with a fixed date, the summary paragraph, the links list, the parameter list, the update step's lines.
- Brief §6.4's label assumes a "since <date>" window, but Claude chooses the window and may set none (T2.1); it also omits that a date filter skips undated pages and that dates are Exa's estimates (T2.2). §6.4's guarantee sentence ("text as fetched") no longer fits, since no web text is shown (T2.3).
- Drafts with recommendations for the honesty label, the replacement guarantee sentence, the band's parts, every outcome line, the pointer under the answer (T1.11) and the step lines; T5.3 locked with every recommendation.
**DECISION (user):**
- T5.3: *"Lock topic 3 as T5.3 with the recommended drafts."*

## Oct 24, 2026, 19:25 CDT — Phase 3: Architecture, Area 5 (run states and stop labels, T5.4)
**Asked:** Open topic 4 (the wording of every run state and stop label); then lock it with the recommended drafts.
**Came back:**
- Read T4.4's twelve pieces and the rules behind them in T1.10, T1.11 and T3.2 to T3.6. Already fixed and kept: brief §5.7's step-limit label, brief §7.2's paused-for-today message, T4.4's "Reconnecting…" and "Recorded run, <Chicago date>". Kept from the rules: no measured start range shown until one is measured (brief §7.2); the Voyage warning never claims the answer's quality suffered (T3.3).
- Drafts with recommendations in nine groups: waking, paused and unavailable, connection, retries and failures, the Voyage warning, stop labels, no-sources replies, replays and the one-question line, rejections and the finish line; T5.4 locked with every recommendation.
**DECISION (user):**
- T5.4: *"Lock topic 4 as T5.4 with the recommended drafts."*

## Oct 24, 2026, 19:36 CDT — Phase 3: Architecture, Area 5 (the privacy note, T5.5)
**Asked:** Open topic 5 (the privacy note, T3.7) and read the retention pages directly, without a subagent; then add the query rule, self-host the fonts (amending T4.1) and lock the note.
**Came back:**
- `docs/research/retention.md`: Anthropic, Voyage (MongoDB), Exa, Cloud Run and Cloud Logging, and Google Fonts. Every quote was string-matched by `scripts/verify_quotes.py`; Exa's terms were checked as extracted PDF text; Google Fonts' FAQ renders by JavaScript, so it was matched in the built-in browser. Findings: Anthropic deletes API inputs and outputs within 30 days (up to 2 years if flagged; longer if the law requires). MongoDB may use what is sent to Voyage to improve its models unless the organisation opts out. Exa's terms take a perpetual licence to store and use queries, and its privacy policy says query data trains its models. Cloud Logging keeps request logs 30 days by default. Google Fonts receives the visitor's IP address and sets no cookies.
- Four choices put to the user. The user checked two in their own accounts: Voyage training opted out on the Voyage AI dashboard (Terms of Service, Section 3(iii)), and goodnight's request logs kept 30 days. Recorded in `retention.md`; the screenshot is not committed.
- T5.5 locked: the note's text, a query rule added to the loop's system prompt (amends T1.14), and the fonts served by our own web service (amends T4.1).
**DECISION (user):**
- *"Open topic 5. Read the retention pages yourself, no subagent."*
- *"I checked myself, and goodnight keeps request logs for 30 days, the default, so your note's "30 days by default" is correct. Voyage AI is also dropped out as well."*
- T5.5: *"Add the query rule and self-host the fonts (amending T4.1). Lock the privacy note as T5.5."*

## Oct 24, 2026, 19:39 CDT — Phase 3: Architecture, Area 5 (the replays, T5.6)
**Asked:** Open topic 6 (the replays: how many, the questions, the pre-*Chatrie* option, recording rules); then lock it with the four recommended questions, the pre-*Chatrie* replay as a fifth, and the recording rules as proposed.
**Came back:**
- Facts from brief §2, §7.4 and §12, T2.3, T4.4, T5.4 and T4.5. Without *Chatrie*, the latest corpus case is *Carpenter*, 2018-06-22 (manifest, script).
- Five candidate questions, each showing a different behaviour; the pre-*Chatrie* options; recording rules; the Phase 5 spend estimated at about $2 to $3 (five runs at about $0.19 to $0.31, plus retakes), to be approved then.
- T5.6 locked as asked.
**DECISION (user):**
- T5.6: *"Lock topic 6 as T5.6: the four recommended questions, the pre-Chatrie replay as the fifth, and the recording rules as proposed."*

## Oct 24, 2026, 19:40 CDT — Phase 3: Architecture, Area 5 closed (the user's wording and the replays)
**Asked:** Run Area 5 after the compaction, topic by topic; then lock the area, close it and prepare for the compaction.
**Came back:**
- Six topics, confirmed by the user with the text-status note added to topic 2, all locked:
  - T5.1 (19:14): the standing lines — pitch, the trace caption, the not-legal-advice line, the AI disclosure, affiliation with the repository link and no author name, sources and credits per actual text source, the reader's three credit lines; brief defaults 2 (Apache 2.0) and 6 ("live" once actually up) settled.
  - T5.2 (19:18): the guarantee ("word for word … as normalised"), the coverage line with all three dates, the answer key, the checks' line and flags, the cost label, the text-status note; T1.12's example line reworded.
  - T5.3 (19:21): the update-check band — honesty label, a replacement guarantee sentence, the band's parts, every outcome line, the pointer under the answer, the step lines.
  - T5.4 (19:25): every run state and stop label.
  - T5.5 (19:36): the privacy note, from `docs/research/retention.md`; a rule keeping personal details out of Voyage and Exa queries (T1.14 amended); fonts served by our own web service (T4.1 amended); Voyage training opted out and goodnight's 30-day logs, checked by the user.
  - T5.6 (19:39): five replays, four on the full corpus and the geofence question on a corpus ending before *Chatrie*; recording rules.
- Amended: T1.12 (T5.2), T1.14 and T4.1 (T5.5). Settled: brief defaults 2 and 6 (T5.1); §7.4's pre-*Chatrie* option (T5.6).
- New research record: `docs/research/retention.md`.
- Carried forward: the working doc's "Area 5 closed" section (build, Phase 5, the design note). Phase 3's five areas are closed; the design note is next.
**Spend:** none (reads only).
**DECISION (user):**
- Topics: *"The six topics work, with the text-status note added. Open topic 1."*
- T5.1: *"1. We can link to the repo, which is https://github.com/NguyenTran2002/probable-clause. No need to mention my name though. 2. Leave out it is. 3. I'll give it Apache 2.0. 4. We're going with 2b anyway. 5. Live wording is correct."* Then *"Lock."*
- T5.2: *"Lock topic 2 as T5.2 with the recommended drafts."*
- T5.3: *"Lock topic 3 as T5.3 with the recommended drafts."*
- T5.4: *"Lock topic 4 as T5.4 with the recommended drafts."*
- T5.5: *"Open topic 5. Read the retention pages yourself, no subagent."* Then *"I checked myself, and goodnight keeps request logs for 30 days, the default, so your note's "30 days by default" is correct. Voyage AI is also dropped out as well."* Then *"Add the query rule and self-host the fonts (amending T4.1). Lock the privacy note as T5.5."*
- T5.6: *"Lock topic 6 as T5.6: the four recommended questions, the pre-Chatrie replay as the fifth, and the recording rules as proposed."*
- Close: *"Lock area 5. Close it and prepare for the compaction."*

## Oct 24, 2026, 19:58 CDT — Phase 3: Architecture, the Phase 4 build plan (P4.1)
**Asked:** After the compaction, propose an efficient subagent-driven build plan, using Sonnet 5.5 and Opus 5.5 subagents at no effort below high and never max; then add a local review of the whole stack before any deploy; then lock it and proceed.
**Came back:**
- The plan, proposed in chat and locked as P4.1:
  - Step 0, main session only: the scaffold (LICENSE, `api/`, `tests/`, `contracts/`, every dependency added at once), T1.5, interfaces contract v1 with `contracts/events.schema.json` (checked against T1.1 to T5.6 by an Opus xhigh subagent not shown the main session's reasoning), and the prompt drafts for the user's review.
  - Wave 1, six subagents in parallel against fakes, no paid calls: the sentence splitter (Opus xhigh), the corpus index (Sonnet high), meaning search (Sonnet high), the Exa wrapper (Sonnet xhigh), money and state (Sonnet xhigh), the answer checks (Sonnet xhigh).
  - Wave 2: the research loop and composition (Opus xhigh), the API and run lifecycle (Opus high), the images and the deploy script, written and never run (Sonnet high). The goodnight block stays with the main session, on the user's green light.
  - A Sonnet high review after each builder; one Opus xhigh review of the honesty-critical paths at the end. Agents never commit; the main session commits each agent's paths by name after running the tests.
  - The frontend is built by the frontend session (P0.3), from the prototype against contract v1.
  - Integration: the offline suite, the paid build tests (Anthropic ceiling $3 for Phase 4, the corpus embedding on Voyage, at most 10 Exa searches, each priced first), the user's prompt review, then **the whole stack run locally for the user's review**, then deploy and the first cold-start sample only on the user's sign-off and a separate green light.
- The design note (Phase 3's gate) is still to be written; "proceed" read as writing it next.
**DECISION (user):**
- *"Propose an efficient subagent driven build plan to me. You're allowed to use both Sonnet 5.5 and Opus 5.5 subagents. Never use any effort level below high, and you're also barred from ever using max effort level as well (for both models)."*
- *"Plan looks right, but I want to add that we have to spin things up locally for review first before any deploy."*
- *"Lock. Proceed."*

## Oct 24, 2026, 20:01 CDT — Phase 3: Architecture, closed (the design note approved)
**Asked:** Write the design note (Phase 3's gate) after the build plan was locked; then, once approved, close Phase 3.
**Came back:**
- `docs/design/design-note.md` (commit ef38f1c), about 1,800 words: what is built and the narrow guarantee (T5.2); a run end to end (T1.1 to T1.14, T2.1 to T2.5); lifecycle and infrastructure (T3.1 to T3.7); the interface (T4.1 to T4.5); the wording and the replays (T5.1 to T5.6); limits and costs as measured (P2.7, findings §3, T1.8, T3.4); accepted risks and open edges (P1.3, P1.7, P1.4, T5.5, cold starts, what the checks do not cover); the placeholders to measure in Phase 5; the user's actions before live runs; what Phase 4 starts with (P4.1).
- Phase 3 in all: five areas, 37 T-entries (T1.1 to T5.6), the build plan P4.1, and the design note. The tree is clean, no worktrees were left by the phase, and the frontend session's last commit (45ccae0) is already folded in.
- The tag `phase-3-done` waits on the user's word that the frontend session is idle (CLAUDE.md, P0.3).
**Spend:** none this sitting; Phase 3's only paid call was `scripts/probe_chunking.py` ($0.1422, T1.9).
**DECISION (user):**
- *"Design note approved. Close Phase 3."*
