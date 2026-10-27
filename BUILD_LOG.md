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

## Oct 24, 2026, 20:02 CDT — Phase 3: Architecture, tagged
**Asked:** Tag `phase-3-done` once the frontend session is idle with its work committed (P0.3).
**Came back:** `git status` clean, no worktrees beyond the main checkout; the frontend session's last commit (45ccae0) is folded in. CLAUDE.md's tag line updated; `phase-3-done` placed on this commit. Next: Phase 4, step 0 of P4.1.
**DECISION (user):**
- *"Frontend session is closed and concluded."*

## Oct 24, 2026, 20:10 CDT — Phase 4: Build, step 0 (scaffold; T1.5, Oliver's Part II heading)
**Asked:** Start Phase 4, step 0 of P4.1: the scaffold, T1.5, then contract v1.
**Came back:**
- **Scaffold** (commit ecb2f0c): `LICENSE`, the standard Apache 2.0 text, copied from a local package's licence file (md5 3b83ef96387f14655fc854ddc3c6bd57, identical in two independent packages) rather than downloaded; the `api/` package, `tests/` with a smoke test, `contracts/`; pytest settings in `pyproject.toml`. Dependencies added at once with `uv add`: fastapi 0.162.0, uvicorn 0.54.0, pymongo 4.19.0, numpy 2.5.4, httpx2 2.16.0, jsonschema 4.26.0; pytest 9.1.1 for development. Claude's call: Voyage is reached through its HTTP API with `httpx2` (the client the Anthropic SDK already uses), not the `voyageai` package, so timeouts and retries stay in our code (T3.3). SQLite's FTS5 is present in the local Python (3.53.4); the image is checked in the build (T3.6).
- **T1.5:** *Oliver*'s Part II heading added through `scripts/corrections.json` (an `insert_after` entry, source `main_T1.5`, page 176). Confirmed by the main session against the page image, with no subagent: page 176 of `USREPORTS-466-170.pdf`, rendered locally and viewed, prints "II" centred above "The rule announced in *Hester v. United States*". The table's `about` text notes this one entry was confirmed by the main session.
- **Checks re-run:** `build_corpus.py` built to a scratch folder first: only `oliver.json` differed, by the heading and its log line. Then built in place; `verify_corpus.py` and `verify_lineup.py` exit 0; every text report identical except *Oliver*'s, which differs only in paragraph positions after the heading; `lineup.json` unchanged. `build_manifest.py`: 32 cases, 102 opinions, **599,096 tokens** (was 599,094; *Oliver*'s majority 8,618 → 8,620 tokens, 4,132 → 4,133 words; 102 free token-count requests). `check_structure.py`: *Oliver*'s heading-sequence error is gone, the `html` copy and Harvard's scan now agree with the corpus, and Lawbox shows the corpus holding the "II" it drops, as expected. No other case changed.
- The design note's "599,094 tokens" is left as approved; this entry records the change.
**Spend:** none (token counting is free).
**DECISION (user):**
- *"Start Phase 4, step 0 of P4.1: the scaffold, T1.5, then contract v1."*

## Oct 24, 2026, 20:42 CDT — Phase 4: Build, step 0 (interfaces contract v1, reviewed)
**Asked:** Contract v1, after the scaffold and T1.5 (P4.1, step 0).
**Came back:**
- **Contract v1** (`docs/design/contract.md`), with `contracts/events.schema.json` and the main session's shared code: `api/types.py`, `api/settings.py` (every figure with its basis; 39 marked placeholder), `api/errors.py` (a closed vocabulary of error kinds), `api/retry.py` (T3.3's retries, with tests), `api/protocols.py` (the Atlas store's interface). Parts A to I with paths, signatures and ownership; endpoints and the wake protocol; every event kind; Atlas collections; prices; reader, replay, `corpus.json` and `config.json` formats; fakes and fixtures. Tests: 25 passed.
- **Review:** an Opus 5.5 xhigh subagent, not shown the main session's reasoning, checked the draft (commit f00905a) against P0.1 to P4.1, the brief, the design note, the corpus and the prototype: 48 items (8 blocking, 22 significant, 18 minor). It confirmed by script the passage counts, the vectors size, *Carpenter* as the latest case without *Chatrie*, and the opinion-group mapping. Main ones, all fixed in the contract except the two left to the user:
  - opinion IDs: the manifest's `id` counts from 0, T1.6 from 1 (checked: `katz-0` … `katz-4`); the contract now numbers from 1 and never uses the manifest's;
  - Exa page text would have reached stored events through the tool result's text; now replaced by a placeholder (T2.2, P1.7);
  - one emitter of spend events (`record_usage`), totals on the run context, who emits the run's end, the run deadline still composing (T3.5), the error vocabulary and retry-after, the full event stored in Atlas, TTL fields as dates;
  - budget-stop recording assigned, the Console spend-limit pause given a flag, the worst-case formula written out ($1.674, T3.4), the `/health` rule, per-run flags for Voyage and Exa unavailability, the section-label rule, *Chatrie*'s slip pages, joiners "not printed" (P1.18), the pre-*Chatrie* switch's live guard, the wake protocol (brief §3, §8.5), `corpus.json`, the local same-origin route, the deploy-time reservation check, fixtures per P0.3.
- **A count corrected:** the corpus has 2,462 passages (1,964 paragraphs, 498 footnotes); Phase 3's "2,748 units" (T3.6) also counted 286 section headings, which T1.6 says are never passages. The vectors file is about 10.1 MB, not 11.3 MB.
- **Open for the user (contract §14):** a submit refused by the copy guard carries page text into the stored `tool_call` event (T3.1 against T2.2 and P1.7); and whether to record the 2,462 correction as a superseding entry (P2.12).
- `tests/fixtures/sentences/hardest.json`: the ten passages of `scripts/probe_chunking.py`, committed for the splitter's tests.
**Spend:** none (the review subagent made no paid calls).
**DECISION (user):** none new; working under *"Start Phase 4, step 0 of P4.1: the scaffold, T1.5, then contract v1."*

## Oct 24, 2026, 20:50 CDT — Phase 4: Build, the passage count corrected (P4.2)
**Asked:** Record the corrected passage count (contract §14, open item 2) as its own decisions entry.
**Came back:** P4.2 in `locked-decisions.md`: 2,462 passages (1,964 paragraphs, 498 footnotes, by script after T1.5), not T3.6's 2,748 units, which also counted the 286 section headings; vectors about 10.1 MB, not 11.3 MB. T3.6's heading marked as corrected by P4.2; the contract's open item 2 closed. Open item 1 (the copy guard and stored page text) stays open; the user asked for more context.
**DECISION (user):**
- *"On the 2,462 passages count, record the correction as its own decisions entry."*
- *"On copy guard, can you give me more context here?"*

## Oct 24, 2026, 20:52 CDT — Phase 4: Build, the copy guard and stored events (P4.3)
**Asked:** More context on contract §14's open item 1 (a submit refused by the copy guard would carry page text into the stored `tool_call` event); then lock option A.
**Came back:**
- Context given: T3.1 stores exactly what Claude sent; T2.2 and P1.7 store no page text; the copy guard (T2.3) refuses a statement repeating 10 or more consecutive words of a returned page, so the refused submit's input is the one place copied words would reach the stream, Atlas (24 hours) and a published replay. Options: A, redact only the flagged statements; B, withhold all findings of a refused submit; C, keep the input exact. Recommended A.
- P4.3 locked (amends T3.1): flagged statements replaced by "[statement withheld: it repeated a page's words]" in the stored and streamed event; Claude's conversation unchanged; the refusal message never quotes the page. Contract §6 and the schema's description updated; §14 has no open items. Tests: 25 passed.
**DECISION (user):**
- *"On copy guard, can you give me more context here?"*
- *"Lock option A: redact only the flagged statements in the stored and streamed event."*

## Oct 24, 2026, 21:12 CDT — Phase 4: Build, Wave 1 started; prompt drafts; part C merged
**Asked:** *"Start wave 1 let's go!"*
**Came back:**
- **Wave 1 launched:** six background builders, each on its own paths per contract §13, with no keys, network, paid calls or commits:
  - A, the sentence splitter, Opus 5.5 xhigh;
  - B, the corpus index, Sonnet 5.5 high;
  - C, meaning search, Sonnet 5.5 high;
  - D, the Exa wrapper, Sonnet 5.5 xhigh;
  - E, money and state, Sonnet 5.5 xhigh;
  - F, the answer checks, Sonnet 5.5 xhigh.
- **Prompt drafts** (23f1ca2) in `api/prompts/`, for the user's review before the first paid run (T1.14):
  - the loop system prompt, with T5.5's query rule;
  - the composition prompt (T1.11);
  - the tool descriptions (T1.4, T2.1);
  - the rejection texts (T1.7, T1.10, T2.3, T2.4), none quoting a page;
  - the loop messages.
  - Figures are setting placeholders, checked by `tests/contract/test_prompts.py`.
- **Contract v1.1** (23f1ca2, 222f14a):
  - `loop_messages.json` is added to G's prompt files.
  - `embed_corpus.py` reads passages through B's `Corpus` and prices through E's `price`.
  - The embedded header writes "Part" only before numbered labels.
  - Appendix titles stay verbatim as labels, and footnotes take their citing paragraph's label. These were settled after the main session read B's label list: 102 opinions, 37 distinct labels, counts summing to 2,462.
- **Shared code** (222f14a):
  - `RETRY_AFTER_MAX_S`, 30 s (a placeholder): a longer retry-after is not waited out inside a run.
  - `VOYAGE_BATCH_TIMEOUT_S`, 120 s (a placeholder), for the embedding's never-retried batches.
- **Part C merged:** `api/search/`, `scripts/embed_corpus.py`, `tests/search/`.
  - The Sonnet 5.5 high review found no blocking defect. Its fixes were made by the builder: the batch timeout, no key read on a fully cached rerun, tests for one HTTP call per failure and for the default timeout.
  - Tests: 117 passed (search and contract).
  - Not run with `--confirm`.
  - Voyage's docs disagree on whether `rerank-3` exists: it is listed in the reranker guide and the rate-limit table, but not in the API reference's model list. To confirm before the first live run.
**Spend:** none.
**DECISION (user):** *"Start wave 1 let's go!"*

## Oct 24, 2026, 21:19 CDT — Phase 4: Build, Wave 1, part B merged
**Asked:** Part B, the corpus index (contract §4.B), under *"Start wave 1 let's go!"*
**Came back:**
- **Part B:** `api/corpus/` (except `sentences.py`), `scripts/build_web_data.py`, `tests/corpus/` (except `test_sentences.py`).
  - Counts by test: 1,964 paragraph and 498 footnote passages, 2,462 in all; 102 opinions.
  - Footnote references match one to one in label order, in every opinion.
  - The pre-*Chatrie* corpus has 31 cases and 97 opinions, with both latest dates 2018-06-22.
- **Labels:** 37 distinct labels, reviewed by the main session before any embedding, with no wrong label found.
- **Review** by a Sonnet 5.5 high subagent: no blocking defect.
  - Footnote offsets are insertion points, confirmed from the data: 155 of 498 references sit at the end of the text. The contract wording was fixed (bd0506b).
  - Fixes made by the builder:
    - bad list types raise a tool error;
    - `read` targets are case-insensitive;
    - the catalog states its counts;
    - the labels file is written only on request;
    - the marker tests are exact.
- **Main session's rulings** (contract v1.1, bd0506b; the tool descriptions say so):
  - `none_of` matches exact words and phrases, unstemmed, on both search tools. The two tools had differed by up to 129 passages on one exclusion.
  - An unquoted item of several words needs all its words, anywhere in the passage; only a quoted item is an exact phrase.
- **Tests:** 169 passed (corpus and contract), run on the stand-in splitter. Builder A's `sentences.py` has not landed yet; the run with the real splitter comes at the Wave 1 merge.
**Spend:** none.
**DECISION (user):** none new.

## Oct 24, 2026, 21:25 CDT — Phase 4: Build, Wave 1, part D merged
**Asked:** Part D, the update check (contract §4.D), under *"Start wave 1 let's go!"*
**Came back:**
- **Part D:** `api/web_updates/`, `tests/web_updates/`. It covers:
  - validation as T2.1;
  - one MCP session per search, with the 30 s timeout covering the handshake;
  - the key only in `x-api-key`;
  - no retries;
  - the four failure kinds of T2.4;
  - the 402 flag and stop;
  - repeats tracked by URL, IDs `web-<search>-<n>`, dates as written;
  - both formatters, page text replaced in the events text.
  - The real `mcp` client is tested against an in-process fake server.
- **Review** by a Sonnet 5.5 high subagent: no blocking defect. With sockets patched to raise, every test still passed. No path was found from page text to a log, an error or an event.
  - Fixes made by the builder:
    - the key scrub uses the stripped key;
    - Exa's message is capped;
    - an ok reply with no reported cost is marked estimated;
    - cancellation propagates unrecorded.
- **Main session's rulings** (contract §4.D, v1.1, 9740eb2):
  - Recording follows T2.4. A search refused by Exa is recorded at $0. An unavailable search (402, 401) records no paid call. A failed one is recorded at list price, as estimated.
  - G runs the schema check.
  - New placeholders: `EXA_HEADER_FIELD_MAX_CHARS` 300 and `EXA_MESSAGE_MAX_CHARS` 500.
- **Tests:** 407 passed (web updates and contract).
**Spend:** none.
**DECISION (user):** none new.

## Oct 24, 2026, 21:39 CDT — Phase 4: Build, Wave 1, part E merged
**Asked:** Part E, money and state (contract §4.E), under *"Start wave 1 let's go!"*
**Came back:**
- **Part E:** `api/state/`, `scripts/spend_report.py`, `tests/state/`. It covers:
  - Chicago clock helpers;
  - the price table (Voyage marked unconfirmed);
  - `worst_case_usd()` = 0.943 + 0.08 + 0.36 + 0.24 + 0.021 + 0.03 = **$1.674**, asserted by test;
  - `MemoryStore` and `MongoStore`, one shared semantic suite.
- **`reserve`** is one conditional update of the month's document, with missing fields guarded. Tests race two runs for the last room, and ten runs for five places.
- **Review** by a Sonnet 5.5 high subagent: the money logic is sound, and the worst case recomputes to $1.674. Fixes made by the builder:
  - run records and stop details are checked against **allowlists** (T3.7); the reviewer showed the first denylist let `q`, `prompt` and `content` through;
  - no driver error, which could carry Atlas host names, survives in an exception chain;
  - `spend_report.py` exits 2 on any failure to read, so a crash no longer reads as "reservation open";
  - prices match exact model IDs only;
  - negative reserved figures are shown as anomalies.
  - Known and documented: a reservation whose update times out on our side but lands later stays counted until cleaned by hand. This errs safe: it cannot overspend.
- **Shared code** (8492353):
  - `count_run_started` is removed from the `Store` protocol (`reserve` counts the start in the same update).
  - The report reads are added to the protocol.
  - `ATLAS_RESERVE_TRIES` is 5, a placeholder.
- **Not yet run:** the 41 Atlas-gated tests, which need `MONGODB_URI` and `PC_ATLAS_TEST=1`. Before its first fixes, the builder ran its suite against a throwaway local `mongod` on a unix socket, with no TCP; it was stopped and its data deleted afterwards. Asked not to repeat this.
- **Tests:** 1,219 passed, 41 skipped (state and contract).
**Spend:** none.
**DECISION (user):** none new.

## Oct 24, 2026, 21:42 CDT — Phase 4: Build, Wave 1, part A merged (the splitter, T1.9)
**Asked:** Part A, the sentence splitter (contract §4.A, T1.9), under *"Start wave 1 let's go!"*
**Came back:**
- **Part A:** `api/corpus/sentences.py`, `scripts/check_sentences.py`, `tests/corpus/test_sentences.py`.
- **Corpus figures:**
  - All 2,462 passages tile, and every footnote join is a boundary.
  - 11,005 sentences (9,337 in paragraphs, 1,668 in footnotes).
  - 8,543 splits.
  - Suspicious splits: "v." 0, "No." 3, section sign 60, initial 21, reporter abbreviation 176, short capitalised word 4, number 713.
  - The ten hardest passages give 50 sentences.
- **The main session's sample review** (T1.9, no subagent): 39 suspicious splits drawn across every category, plus the builder's 12. Every one is a true sentence end.
- **Review** by a Sonnet 5.5 high subagent: no blocking defect. It found no case where the splitter splits more readily than T1.9 allows, except one hyphen edge with no corpus effect; tiling was fuzzed on 60,000 strings.
  - Fixes made by the builder:
    - case-insensitive abbreviations (a lowercase word matches lowercase entries only);
    - the hyphen rule narrowed;
    - a linear blank-line scan replacing a quadratic regex;
    - tests killing every surviving mutant (21 of 21 caught).
  - The corpus splits are unchanged: SHA `3aaa2c7d…6391f` before and after.
  - The main session's suggestion to list "no" was withdrawn: it removed one true split in *Kyllo* ("answered no. | See"), now pinned by a test.
- **Kept as is:** "supra" stays on the list ("in doubt, do not split"). The *Chatrie* typo "Pet. for. Cert." stays as known (P1.21); the splitter guards against it.
- **Tests:** 459 passed (corpus and contract). Builder B's corpus tests now run on the real splitter.
**Spend:** none.
**DECISION (user):** none new.

## Oct 24, 2026, 21:52 CDT — Phase 4: Build, Wave 1, part F merged; Wave 1 complete
**Asked:** Part F, the answer checks (contract §4.F; T1.12, T2.3), under *"Start wave 1 let's go!"*
**Came back:**
- **Part F:** `api/checks/`, `tests/checks/`.
  - The quotation check implements T1.12's conventions: punctuation inside the closing mark, nested quotation marks, ellipses, bracketed alterations including the source's own.
  - The full-citation check gives "not in this corpus" (P1.10).
  - The findings checks and the copy guard (T2.3) are included. `copy_guard_report` gives G the flagged statements for P4.3.
  - All 1,932 quotations in the corpus are found when their own passage is the kept text.
- **Review** by a Sonnet 5.5 high subagent, which found **false passes** (results the page would state as true when they are not). All are fixed and tested with the reviewer's inputs:
  - a whole-word bracket could swallow or insert a negation ("is [reasonable]" for "is not reasonable"); brackets now never add or remove a negation, prefix forms included;
  - a name whose right party only began with a corpus party resolved ("Smith v. Maryland Casualty Co."); the right party must now match exactly;
  - a name followed by another corpus case's citation passed ("Katz v. United States, 565 U.S. 400"); the citation now flags.
- **Silent misses fixed:** multi-paragraph quotations, blockquotes, and inch marks breaking the quotation pairing. Two false flags fixed: "Ass'n" and "Dow Chem. Co.".
- **Matching is bounded:** the reviewer's 189 s case now takes under 0.2 s. A quotation that can't be decided within the step budget is flagged, never passed.
- **Main session's rulings** (contract v1.1, 5625308):
  - `QUOTATION_BRACKET_MAX_SOURCE_WORDS` is set to **3**, a placeholder; part F measured that the corpus's quotations need at most 1.
  - The composition prompt now asks for double quotation marks or a blockquote, and never a bracket that changes the meaning.
  - Offsets are code points, which the page converts for JavaScript.
- **Wave 1 complete:** parts A to F are merged. **The whole suite: 2,364 passed, 41 skipped** (the Atlas-gated tests of part E).
**Spend:** none in Wave 1. The Anthropic ledger is unchanged at $0.6964.
**Next:**
- The 41 Atlas tests against `Probable_Clause_test`, with `MONGODB_URI` (set).
- The embedding: it needs `VOYAGE_API_KEY` (missing), Voyage's prices from the billing page and the key's endpoint checked (T5.5), then `--confirm` on the user's approval. `rerank-3`'s existence also needs confirming; Voyage's docs disagree.
- The fixtures and the frontend brief update; then Wave 2.
- The prompt drafts await the user's review before the first paid run.
**DECISION (user):** none new.

## Oct 24, 2026, 21:55 CDT — Phase 4: Build, the prompt drafts approved; rerank-3 confirmed; Voyage key set
**Asked:** The user reviewed the prompt drafts in `api/prompts/` (T1.14: reviewed before their first paid run). These include the main session's calls in `tools.json`: `none_of` exact on both tools, and multi-word items needing all their words. The user also checked `rerank-3` and added the Voyage key.
**Came back:**
- The prompt drafts stand as committed (23f1ca2, as amended by bd0506b and 5625308), approved for the first paid run.
- `rerank-3` is confirmed valid by the user. It answers the open point from part C's review: Voyage's docs disagreed.
- `VOYAGE_API_KEY` reports **set** (`scripts/check_env.py`; the file itself was not read).
- Next: Voyage's list prices with their source, the key's endpoint (T5.5), and a dry run of the embedding for its cost. Then `--confirm` only on approval.
**DECISION (user):**
- *"I checked the prompts. They are good to go."*
- *"rerank-3 is valid, I just check."*
- *"Voyage API key is included in .env. Do NOT read the file yourself."*

## Oct 24, 2026, 21:58 CDT — Phase 4: Build, Voyage checked end to end before the embedding
**Asked:** The checks before the embedding (contract §10, T5.5). Then, on the user's word, *"send a throwaway run first to confirm end to end working"*.
**Came back:**
- **The key's endpoint** (`scripts/probe_voyage.py`, 97e94ed): one one-word embedding, 2 tokens, was accepted by `api.voyageai.com`. It is a Voyage platform key, so the user's opt-out on Voyage's dashboard applies and no Atlas toggle is needed (T5.5). `VOYAGE_BASE_URL`'s basis is updated.
- **Prices** (Voyage's pricing page, https://docs.voyageai.com/docs/pricing, read Oct 24, 2026): `voyage-law-2` $0.12 and `rerank-3` $0.05 per million tokens. Marked confirmed in `api/state/prices.py`. The 50M free embedding tokens are not modelled, since list price is the conservative figure for the caps.
- **Dry run of the whole corpus:** 2,462 passages in 39 batches, about 653,063 tokens estimated (an over-estimate), about $0.0784 at list price.
- **Throwaway run** (a scratchpad script, outputs in the scratchpad only; `data/vectors/` untouched):
  - 12 real passages went through `embed_corpus.main --confirm`: 2,619 tokens, $0.0003.
  - `MeaningIndex.load` accepted them: model, dimension and text hashes all checked.
  - One real meaning search, "whether listening to a telephone booth conversation with an electronic device is a search", made the query embed (17 tokens, 413 ms) and a rerank of all 12 (2,398 tokens, 549 ms). Status ok, every hit reranked, no flags. The top four were *Katz* (katz-1-p1, katz-3-p1, katz-1-p10, katz-3-p3).
  - Each attempt was recorded once with its cost.
  - A second `--confirm` run paid nothing; its batch came from the cache.
**Spend:** Voyage, about 7,650 tokens in all, about $0.0004 at list price, likely within the free tokens. Anthropic: none.
**DECISION (user):** *"Wait, send a throwaway run first to confirm end to end working"*

## Oct 24, 2026, 22:02 CDT — Phase 4: Build, the rerank compared with the embedding order
**Asked:** *"Reranking also worked?"*, then *"Do that comparison too just to confirm"*.
**Came back:** a throwaway scratchpad script over the same 12 rows. One query embed (17 tokens) gave the cosine order, then `rerank-3` ranked the same documents (2,398 tokens).
- The rerank moved **10 of 12 positions**.
- Both orders put the four *Katz* passages first and *Berger*'s appendix last.
- The rerank lifted katz-1-p1 (the opening of the majority) from 4th to 1st and katz-1-p2 from 11th to 8th, and put *Kyllo* above *Smith*.
- Its order matches what the earlier `MeaningIndex.search` returned, so the search uses the rerank's order.
**Spend:** Voyage, 2,415 tokens, about $0.0001 at list price. Anthropic: none.
**DECISION (user):** *"Do that comparison too just to confirm"*

## Oct 24, 2026, 22:06 CDT — Phase 4: Build, the corpus embedded (voyage-law-2)
**Asked:** *"Approved: run embed_corpus.py --confirm on the full corpus."*
**Came back:**
- `scripts/embed_corpus.py --confirm`: 2,462 passages in 39 batches, **524,853 tokens**, **$0.0630 at list price** (the dry run's over-estimate was 653,063 tokens and $0.0784).
- Output: `data/vectors/voyage-law-2.f32` (10,084,352 bytes, as P4.2 expects: 2,462 × 1,024 × 4) and `manifest.json` (model voyage-law-2, dimension 1024, count 2,462, created 2026-10-24, one SHA-256 per embedded text).
- **Checks:**
  - `MeaningIndex.load` accepts the vectors against the full corpus and against the pre-*Chatrie* corpus (2,323 passages).
  - Rows come in reading order.
  - Every value is finite, and every row has unit norm.
  - Nearest neighbours look sensible (katz-1-p1 → other *Katz* majority paragraphs; kyllo-1-p10 → *Kyllo*'s footnotes and dissent).
  - 2,458 distinct rows. The six repeats are texts that are identical word for word: four "The Commission recommends:" rows in White's *Berger* appendix, and two *Olmstead* footnotes citing *Gouled*.
- Whole suite: 2,364 passed, 41 skipped.
**Spend:** Voyage, 524,853 tokens, $0.0630 at list price, likely within the account's 50M free tokens. Anthropic: none.
**DECISION (user):** *"Approved: run embed_corpus.py --confirm on the full corpus."*

## Oct 24, 2026, 22:09 CDT — Phase 4: Build, part E's store tested against Atlas
**Asked:** *"Yes, run part E's Atlas-gated tests against Probable_Clause_test."*
**Came back:**
- `PC_ATLAS_TEST=1 uv run --frozen --env-file .env pytest -q tests/state/test_store_atlas.py` gave **40 passed in 49.12 s**. `uv` loaded the URI into the test process; the main session did not read `.env`.
- The 40 are the shared semantic suite run on `MongoStore` against the real Atlas server, plus the check that the TTL fields are BSON dates and the TTL index is set.
- The suite includes two runs racing for the last room under the cap (only one gets in) and ten runs racing for five places (exactly five get in).
- The earlier "41 skipped" was these 40 plus the event-fixture test, which skips until the fixtures exist.
- **Clean-up checked:** each test used randomly prefixed collections dated 2030 and dropped them. Afterwards `Probable_Clause_test` holds only its existing `init` collection, with no test collection left. The live database `Probable_Clause` was not touched.
**Spend:** none.
**DECISION (user):** *"Yes, run part E's Atlas-gated tests against Probable_Clause_test."*

## Oct 24, 2026, 22:48 CDT — Phase 4: Build, fixtures for the mock frontend; frontend brief rewritten
**Asked:** *"Proceed on to the fixtures and the frontend brief update"*
**Came back:**
- **Fixtures** (contract §12), written by a Sonnet 5.5 xhigh subagent to the main session's brief and reviewed by the main session.
  - `tests/fixtures/make_fixtures.py` regenerates them deterministically: two runs gave identical files, checked by the main session.
  - **30 event streams** (3.3 MB), in the replay format of §11.2:
    - an answered run (phone location records: *Carpenter*, *Smith*, *Miller*, *Katz*);
    - both no-sources replies;
    - every limit stop (step, token input and output, time, length cut-off, both spend limits);
    - a pause and resume, an abandoned run, an interrupted run;
    - loop and composition failures, and a refusal;
    - a copy-guard refusal with P4.3's withholding, and a declined update check;
    - check flags (a misquotation and *Entick v. Carrington*, real `check_answer` output);
    - every band outcome, both Voyage warnings, retries;
    - a reconnect after `n = 185`;
    - a replay on the pre-*Chatrie* corpus.
  - **19 HTTP answers:** `/health` states; Cloud Run's plain-text 429, 500 and 503 and a gateway HTML 502 (representative, written from scratch); every `POST /runs` refusal; expired-run 404s.
  - **Real wherever code exists:** passages from `Corpus`, cited text sliced from real sentence spans, checks from `check_answer`, web results through `format_for_events` (synthetic `example.test` pages, no page text), costs from `price`, rejection texts from `api/prompts/`. The loop's tool-result text is approximate until builder G, as the README says.
  - `tests/contract/test_fixtures.py` checks for every stream:
    - the order rules, cited text and totals;
    - passages named only after their `passage` event;
    - the web IDs, the one `run_ended`, the re-run checks;
    - coverage of every state, stop kind and band outcome, and the allowed pairings of state and `answer_end`.
- **Main session's rulings on the builder's questions** (contract §6 and the schema, v1.1):
  - `run_ended.stop_kind` allows only the seven kinds that end a run.
  - `failure_reason` is an `ErrorKind` or null.
  - `since_ms` is defined.
  - `answer_end: incomplete` goes with state `answered`.
  - A failed attempt with no usage has `usage: null` and `estimated: true`.
- **Frontend brief** rewritten (f6d70f6) for the real page against a mock:
  - the frontend session writes `web/` (served) and `webdev/` (mock and Node tests, never served);
  - the generated reader and config files are in the gitignored `web/_generated/`;
  - the contract details found in Wave 1;
  - the checks at three sizes and no third-party request.
- **Whole suite:** 2,907 passed, 47 skipped (the reconnect fixture's checks that need a stream's first events, and the Atlas-gated tests).
**Spend:** none.
**DECISION (user):** *"Proceed on to the fixtures and the frontend brief update"*

## Oct 24, 2026, 22:51 CDT — Phase 4: Build, ground prepared for a compaction before Wave 2
**Asked:** *"We'll compact before wave 2. Prep the ground first."*
**Came back:** CLAUDE.md's "Current state and next step" rewritten for resuming at Wave 2:
- what to read;
- what Phase 4 has done, with commits;
- the Wave 1 brief recipe, to be reused;
- the notes Wave 1 left for G, H and I (failed-attempt usage, P4.3 withholding, the schema check, record shapes, run-ID form, the web image's contents);
- the sequence after Wave 2;
- spend so far.
The layout list gains the Phase 4 scripts, `data/vectors/`, `tests/fixtures/`, `webdev/` and `web/_generated/`. Tree clean, nothing pushed. Wave 2 waits for the user's go after the compaction.
**Spend:** none.
**DECISION (user):** *"We'll compact before wave 2. Prep the ground first."*

## Oct 24, 2026, 22:58 CDT — Phase 4: Build, Wave 2 started
**Asked:** *"Let's start Wave 2."*
**Came back:**
- **Wave 2 launched:** three background builders, each on its own paths per contract §13, with no keys, paid calls or commits:
  - G, the research loop and composition (`api/loop/`, `tests/loop/`), Opus 5.5 xhigh. It may read Anthropic's public docs with WebFetch for streaming, citations, adaptive thinking and effort, one-hour caching, and the two spend errors.
  - H, the API and run lifecycle (`api/server/`, `api/main.py`, `tests/server/`), Opus 5.5 high.
  - I, the images and deploy files (`deploy/`, `tests/deploy/`), Sonnet 5.5 high. The files are written, never run; `deploy.sh` is tested only under stub commands, to prove the open-reservations check stops it first.
- **Agreed between G and H in the briefs** (within contract v1.1, no change to it):
  - `api.loop` exports `execute_run`, `LoopDeps`, `AnthropicStreamer`, `StreamResult`, `FakeAnthropic` and `SdkAnthropicStreamer(api_key)`;
  - `api/main.py` exposes `app` (`uvicorn api.main:app`) and imports `api.loop` only inside its deps factory;
  - in `record_usage`, `usage` is what is priced and `raw_usage` is Claude's exact usage object, written as `paid_call.usage` (null for a failed attempt with no usage).
- **Each part:** tests first, a mutation check of its honesty-critical rules, then a Sonnet 5.5 high review, the fixes, the tests run by the main session, and a commit of that part's paths with a log entry.
- **I's brief** excludes `web/looktests/` from the web image (the Phase 1 look tests, not the page), as a choice to report back.
**Spend:** none.
**DECISION (user):** *"Let's start Wave 2."*

## Oct 24, 2026, 23:14 CDT — Phase 4: Build, Wave 2, part I merged (images and deploy files)
**Asked:** Wave 2 (*"Let's start Wave 2."*); part I, contract §4.I.
**Came back:**
- **Part I merged:** `deploy/` and `tests/deploy/`.
  - Files: `api.Dockerfile`, `web.Dockerfile`, their `.dockerignore` files, `nginx.conf` (production), `nginx.local.conf` (the local profile), `deploy.sh` and `local.sh`.
  - **Written, never run.** Nothing was built, pushed or deployed. `deploy.sh` ran only under stub commands in the tests, on a `PATH` the real `gcloud` and `docker` are not on.
- **Images pinned by tag** (read Oct 24, 2026, and fetched again by the reviewer): `python:3.13.17-slim-trixie`, `ghcr.io/astral-sh/uv:0.13.5`, `nginx:1.30.6-alpine3.24-slim`. Both Dockerfiles use `uv sync --locked`, so a stale lock fails the build.
- **The Sonnet 5.5 high review found real defects, all fixed by the builder:**
  - **The page guard could not fail:** nginx's own welcome page satisfied it, so a deploy before the frontend lands would have published that page. The image now empties nginx's folder first, then requires our `index.html`, at least one `.woff2` with its licence text (T5.5), `config.json`, `corpus.json` and `opinions/`.
  - **The spend gate's timing:** it ran once, minutes before the API's revision was replaced. It now runs first and again immediately before the API's `gcloud run deploy`, with stub tests for both.
  - **`local.sh` passed all of `.env` with quotes kept**, `COURTLISTENER_API_TOKEN` included. It now loads `.env` through `uv run --env-file` and passes only the four keys the API needs, with `PC_ENV=test`.
  - nginx: `charset utf-8`, `gzip_vary on`, one worker; `.DS_Store` excluded.
- **The builder's choices, for the user to judge at the local review:**
  - `web/looktests/`, `web/_generated/` and `webdev/` are not served.
  - **CSP:** only the page's own origin (T5.5). `style-src` allows inline styles so the page's code can set style attributes; scripts are `'self'` only.
  - **Names:** services `probable-clause-api` and `probable-clause-web`; service accounts `pc-api@` and `pc-web@probable-clause.iam.gserviceaccount.com`; the Artifact Registry repo `probable-clause`; secrets `pc-anthropic-api-key`, `pc-voyage-api-key`, `pc-exa-api-key`, `pc-mongodb-uri`, each pinned to its newest enabled version.
  - The gate reads the live database (`--env live`). `deploy.sh` checks that the registry, service accounts and secrets exist and creates none. nginx keeps no access log and uvicorn runs with `--no-access-log` (T3.7).
- **Path prefix:** goodnight strips `/probable-clause/` before the web service and `/probable-clause/api/` before the API (T3.5), so nginx serves from the root. Locally, `/api/` is proxied to the API with the prefix stripped and buffering off for the event stream.
- **Open, for the user before any deploy:**
  - how the registry, the service accounts, the secrets and their values are created (T3.5 left the secrets open);
  - whether the port, service names and the web service's CPU, memory, concurrency and timeout belong in `api/settings.py`;
  - `--scaling=auto` beside `--min` and `--max`, undocumented either way. The main session checks it with `gcloud run deploy --help` (offline) before any green light.
- **Tests:** 610 passed, 9 skipped (deploy and contract). The 2 `nginx -t` skips are because no nginx binary is installed, so neither config has been parsed by nginx yet.
**Spend:** none.
**DECISION (user):** *"Let's start Wave 2."* No new decision. The choices above are the builder's, to be judged at the user's local review.

## Oct 24, 2026, 23:33 CDT — Phase 4: Build, failed Voyage attempts priced at an estimate (part C fix)
**Asked:** builder H's first contract question: part C recorded a failed Voyage attempt with no usage, so it was priced at $0.
**Came back:**
- **The defect:** `MeaningIndex._call` passed `usage=None` for `retrying` and `failed` attempts. The attempt was counted, but priced at $0 against the caps, while T3.3 and contract §6 (v1.1) price it from the caller's input estimate. The worst case's Voyage bound ($0.03 a run) still held, so no cap could be overrun by more than that.
- **The fix, by the main session in C's merged code:**
  - Each failed attempt is now recorded with E's `failed_attempt_usage("voyage", model, estimate)`, so it is marked `estimated`.
  - **The estimate** is characters ÷ `VOYAGE_CHARS_PER_TOKEN_ESTIMATE`, rounded up:
    - the embed counts the query;
    - the rerank counts query × documents + documents, Voyage's own count (docs.voyageai.com/docs/reranker, read Oct 24, 2026).
- **New setting** `VOYAGE_CHARS_PER_TOKEN_ESTIMATE = 3`, the main session's. Its basis: 3.73 characters a token measured on the corpus embedding (1,956,650 characters, 524,853 tokens), rounded down so the estimate over-counts.
- **Tests:** C's retry tests now assert the estimate for the embed and the rerank. Search, state and contract tests: 1,851 passed, 47 skipped.
**Spend:** none.
**DECISION (user):** none; a fix within T3.3 as locked.

## Oct 24, 2026, 23:40 CDT — Phase 4: Build, Wave 2, contract v1.2 (after part H's review)
**Asked:** builder H's ten contract questions, and its Sonnet 5.5 high review.
**Came back:**
- **H's review found real defects; H is fixing them now:**
  - a cancel during `record_usage` could drop a billed cost and then release the reservation;
  - an estimated Voyage usage was shown as Voyage's own;
  - **the shutdown path was unreachable while a stream was attached.** uvicorn runs the lifespan shutdown only after connections close, and Cloud Run sends SIGKILL 10 s after SIGTERM. Each run killed this way would have kept $1.674 reserved against the caps;
  - `create_run` leaked the reservation on cancellation;
  - `isdigit()` accepted non-ASCII digits;
  - `interrupted` was skipped when the page was ahead of Atlas.
- **Contract v1.2, the main session's rulings** (this file; `contract.md`'s header lists them):
  - `ErrorKind` gains `internal`, for H's `failed` after an unexpected exception (`api/errors.py` and the schema's `failure_reason`).
  - `interrupted`'s `n` is one more than the larger of the last stored event and the page's `Last-Event-ID`, so the page always receives it. Stored events are replayed only while their numbers run on without a gap.
  - §5 lists the extra codes: `bad_request`, `not_found`, `method_not_allowed`, `internal`, and `atlas_unreachable` on an events read or a heartbeat. The page shows any code it has no words for as T5.4's general failure.
  - `answer_chars` is always the length of the answer text streamed, so H's `failed` and `interrupted` keep `answer_end: none` with what arrived. The fixture test is adjusted.
  - **Shutdown:** `SHUTDOWN_GRACE_S = 5`, uvicorn's `--timeout-graceful-shutdown` (in `deploy/api.Dockerfile`, with a test). Basis: Cloud Run's 10 s between SIGTERM and SIGKILL (docs.cloud.google.com/run/docs/container-contract, read Oct 24, 2026).
- **Left as built:**
  - the spend-limit pause's own message under `paused_month`;
  - no run record for an unattached run that expires;
  - finished runs kept in memory for `EVENTS_TTL_S`;
  - an index failure at start-up is not fatal.
  - Both stop kinds, `console_spend_limit` and `tier_spend_cap`, set the spend-limit flag, which is the safe reading.
- **For the final Opus review and the user:**
  - **No tripwire** stops a run whose spend passes its reservation. The contract relies on G's limits, so a bug there is unbounded for that run.
  - **A reservation left by a SIGKILL** stays counted until cleared by hand. `deploy.sh`'s gate reports it, but nothing clears it.
  - **Unattached runs:** five `POST /runs` with no stream hold the $10 day's room for `UNATTACHED_RUN_EXPIRY_S` (120 s), at no cost to whoever sends them. This follows from T3.1 and T3.4 as locked.
- **Tests:** deploy, contract, state and search: 1,891 passed, 49 skipped.
**Spend:** none.
**DECISION (user):** none; the main session's rulings within the locked decisions, announced to G and H.

## Oct 24, 2026, 23:52 CDT — Phase 4: Build, Wave 2, contract v1.3 (after part G's review)
**Asked:** builder G's report and its Sonnet 5.5 high review.
**Came back:**
- **G built** `api/loop/`: the six tools, the loop, composition with custom content documents and citations, and the SDK client (138 tests; 45 mutations, all caught).
  - **SDK, from Anthropic's docs** (read Oct 24, 2026, SDK 2.3.0): adaptive thinking; `output_config.effort` "high" for both models; a one-hour breakpoint on the system block, which also covers the tools rendered before it, then the request's top-level automatic breakpoint; `max_retries=0`.
  - **The spend errors:** the tier spend cap is a 429 whose `error.details.error_code` is `enforced_spend_limit_reached`; the Console spend limit is a 400 whose message begins "You have reached your specified (workspace) API usage limits" (platform.claude.com/docs/en/api/rate-limits). A 429 without those markers stays `rate_limited`, so a misread can't pause research for a month.
- **The review** found no defect in the citation mapping (checked on `berger-1-p1`), the SDK request or the spend markers. **It did find real defects, which G is fixing now:**
  - a keep after a submit in the same turn was silently dropped (T1.10 allows it);
  - a broken stream was priced for its input only, so up to about $0.24 of Opus output went uncounted against the reservation and the output ceiling;
  - a last attempt could read `retrying` with no retry after it;
  - end pairings the fixture rules forbade;
  - smaller robustness points.
- **Contract v1.3, the main session's rulings:**
  - a turn's tools run in Claude's order with `submit_answer` last;
  - **withholding (P4.3) applies to any refused submit** with statements the copy guard flags, not only one refused by the copy guard, since no page's words are ever stored (§1). This is G's stricter reading, adopted;
  - `submit.rule` gains `no_note`, for `out_of_scope` without a note;
  - `step_limit`, `token_ceiling` and `time_limit` keep their own `stop_kind` when their composition is then cut off. These three and `error_stopped` may end `incomplete`;
  - a citation's response path is `content[k]` with k at or after the block index, since thinking blocks come first;
  - **a citation whose `cited_text` disagrees with our slice is not attached, and is logged as a mapping fault,** so no sentence Claude did not cite is ever lit. The first paid build test checks the count;
  - `tool_call` may name an ID before its `passage` event, since its input is Claude's exactly.
- **Prompt drafts added** (`api/prompts/`, for the user's review before the first paid run, T1.14): G's own texts, moved out of the code:
  - the unknown-tool error;
  - the two accepted-submit texts;
  - the composition request's scope-note and coverage lines;
  - the out-of-scope-without-note refusal.
- **For the user, before the first paid run:**
  - **Composition input:** the 40 longest passages (`KEEP_CAP`) are about 30,500 tokens of text, against `COMPOSITION_RESERVE_INPUT`'s 30,000, before keep reasons, metadata and the prompt. A full keep list can therefore push the composition, and so the run, past its reserved worst case (T3.4's $1.674). G only warns today.
  - **The copy guard covers statements and the overview only** (T2.3). `note` and `update_skip_reason` are stored and shown unguarded, although Claude saw page text.
  - **Two sources for some texts:** `rejections.json`'s `update_search.*` and `findings_problem.*` texts go unused, because D's and F's own messages (reviewed in Wave 1) are sent instead.
- **Tests:** contract, 571 passed, 7 skipped.
**Spend:** none.
**DECISION (user):** none; the main session's rulings within the locked decisions, announced to G and H.

## Oct 24, 2026, 23:56 CDT — Phase 4: Build, Wave 2, part H merged (the API and run lifecycle)
**Asked:** Wave 2 (*"Let's start Wave 2."*); part H, contract §4.H.
**Came back:**
- **Part H merged:**
  - `api/server/`: `app.py`, `run.py`, `registry.py`, `sse.py`, `clock.py`, `totals.py`, `summary.py`;
  - `api/main.py`, which exposes `app` and imports `api.loop` only inside its deps factory;
  - `tests/server/`.
- **What it does:**
  - **Endpoints** per §5, answering as `tests/fixtures/http/` does.
  - **The reservation:** made at `POST /runs` and released once on every end path, in a shielded `finally`. It stays counted while a paid call is unrecorded or a cost is unsettled.
  - **The heartbeat gate** in §4.H's order: abandoned, then the deadline (composition exempt), then the unattended pause, with Atlas polled and the run abandoned at `ABANDON_AFTER_S`.
  - **Events:** numbered with no gaps, copied to Atlas in order without holding up the stream, replayed from `Last-Event-ID`, with one stream per run (a second attach replaces the first, T3.1).
  - **On another instance,** `interrupted` is sent on the stream only, never stored.
  - **Run records** in `api/state/records.py`'s allowlisted shape. Logs hold error kinds only, never an exception chain.
- **Review fixes (from the review logged at 23:40), each with a test:**
  - a cancel mid-settle keeps the cost counted;
  - an estimated usage is shown as `usage: null`;
  - **shutdown closes every stream and releases reservations within `SHUTDOWN_GRACE_S`**, with releases run at once and a hung Atlas unable to hold it;
  - a cancelled `create_run` releases;
  - ASCII digits only in headers;
  - `interrupted` numbered and replayed per v1.2;
  - `failed` carries `internal`;
  - the extra codes.
- **The builder's choices,** besides those the 23:40 entry rules on:
  - both spend stop kinds set the spend-limit flag;
  - the question's tabs and newlines become spaces, other control characters are removed, and zero-width characters are kept;
  - composition still pauses when unattended;
  - calls due together share one pause.
- **Mutation check:** 54 mutations at first, then 18 of the touched rules after the fixes. All are caught, except one equivalent: the order of a decrement the `finally` makes irrelevant. The builder says it wrote most of its tests after the code, not first; the mutation check is the evidence they have teeth.
- **Tests:** server and contract, 762 passed, 7 skipped.
**Spend:** none.
**DECISION (user):** *"Let's start Wave 2."* No new decision.

## Oct 25, 2026, 00:07 CDT — Phase 4: Build, Wave 2, part G merged; Wave 2 complete
**Asked:** Wave 2 (*"Let's start Wave 2."*); part G, contract §4.G.
**Came back:**
- **Part G merged:**
  - `api/loop/`: `run.py`, `streamer.py`, `tools.py`, `format.py`, `prompts.py`, and `__init__.py` exporting the six names agreed with H;
  - `tests/loop/`.
  - What G built, and what Anthropic's docs said, are in the 23:52 entry.
- **Review fixes (from the review logged at 23:52), each with a test:**
  - a turn's tools run with the submit last, so a same-turn keep counts;
  - G's texts are read from `api/prompts/`;
  - the v1.3 end pairings;
  - **a broken stream's spend:** a failed attempt records as output the larger of what the stream reported and an estimate from the characters it streamed, and counts against the output ceiling;
  - no `retrying` record without a following attempt;
  - **a citation whose text disagrees with our slice is not attached** and is logged as a mapping fault;
  - SDK validation errors classified;
  - no empty text block;
  - the gap-filling choices marked `# GAP`.
- **Mutation check:** 45 mutations at first, then 25 of the touched rules. All caught after one test was added.
- **Tests:**
  - loop and contract: 735 passed, 7 skipped;
  - **the whole suite: 3,302 passed, 49 skipped.**
- **Wave 2 is complete:** G, H and I are merged, each reviewed by Sonnet 5.5 high with its defects fixed. Contract v1.2 and v1.3 hold the rulings.
- **Next, per P4.1:**
  1. one Opus 5.5 xhigh review of the honesty-critical paths;
  2. an end-to-end test of the whole backend on fakes;
  3. the fixtures regenerated from G's formatter;
  4. the user's decisions listed at 23:52;
  5. the user's review of the prompt drafts;
  6. paid build tests within $3, each priced and approved.
**Spend:** none.
**DECISION (user):** *"Let's start Wave 2."* No new decision.

## Oct 25, 2026, 00:34 CDT — Phase 4: Build, the cross-part review (Opus 5.5 xhigh) and contract v1.4
**Asked:** P4.1's final review of the honesty-critical paths after Wave 2, read-only. It drove G's real `execute_run` through H's real `Run` on fakes, with scripts in the scratchpad.
**Came back:**
- **Sound, with evidence:**
  - **Citation mapping:** document order, one block per sentence, inclusive ranges, our own `cited_text`, mismatches dropped. No character outside the BMP is in the corpus.
  - **The checks as G calls them:** 3,000 fuzzed answers raised no exception.
  - **The band's rules** and P4.3's withholding through to Atlas.
  - **The reservation:** released exactly once.
  - **The heartbeat gate** before every attempt.
  - **The `record_usage` convention** across C, D, G and H; `api/main.py`'s wiring.
  - **T3.7** in every log and record.
- **Defects found and fixed now (contract v1.4, the main session's rulings within the locked decisions):**
  - **A false pass in the quotation check (F), demonstrated and reproduced by the main session.** `"that the Constitution did . . . forbid the obtaining"` was reported found against *Berger*'s "did not forbid". An ellipsis now matches the smallest gap in the source, and a gap holding a negation fails the match. Fixed by the main session, with tests. A mutation restoring the old rule fails 4 of them. A fair ellipsis over an unrelated "not" is now flagged, which is the safe direction.
  - **A keep whose reason was written before its passage was seen was accepted (G):** a read in the same turn showed the passage first, and T1.7 requires the keep be refused. Keeps are now checked against what was shown before the turn began. Fixed by G.
  - **A loop limit's budget stop was lost** when the composition then failed or was cut off (T3.4). `run_ended.stop_kinds` now lists every budget and limit stop in order, and H records each once. Fixed by G and H.
  - **An Exa 402 or 401 left a paid call marked in flight (D and H).** A later abnormal end would then have kept the whole $1.62 reserved, and `deploy.sh`'s gate would have blocked deploys until it was cleared by hand. `RunContext.call_not_billed` undoes the gate's count; D calls it on that path. Fixed by the main session (D) and H.
  - **Voyage's per-run bound (`VOYAGE_RUN_BOUND_USD`, $0.03) was assumed by the worst case but never enforced:** 60 meaning searches in a turn cost $0.032. C now checks each call with all its allowed attempts priced. Over the bound, the embed is not run (`unavailable`), or the results come back in embedding order (`not_reranked`). Fixed by the main session, with tests.
- **For the user (money and wording; see the reply):**
  - **The real maximum of one run as the code stands:** about $2.16 recorded against the $1.674 reserved. The excess comes from the composition input (estimated at up to 64,535 tokens against a 30,000 reserve, with failed attempts priced at that estimate) and from Voyage, now bounded.
  - **Hidden thinking on a broken stream:** Sonnet 5.5 and Opus 5.5 default to `display: "omitted"`, so thinking tokens are billed but never streamed. A broken attempt is recorded with the output that was visible only, up to $0.08 short per loop attempt and $0.24 per composition attempt.
  - **No tripwire** stops a run at its reservation.
  - **Page words reach events through keep reasons and notes, demonstrated:** 14 consecutive page words placed in a keep reason were stored in `tool_call`, `tool_result.kept`, the composition fragments and `scope_note`. The copy guard covers only the update statements and overview (T2.3).
  - **The band says `nothing_relevant` when no search completed** (failed or refused by Exa), which follows §6 and T2.4 to the letter. The page could word it from `searches[].status`.
- **Tests:** the whole suite, 3,322 passed, 49 skipped.
**Spend:** none.
**DECISION (user):** none yet; the money and wording questions above are put to the user.

## Oct 25, 2026, 00:41 CDT — Phase 4: Build, no spend tripwire (P4.4)
**Asked:** whether a tripwire should stop a run whose recorded spend reaches its reservation (the cross-part review's finding 2).
**Came back:** locked as P4.4: no tripwire. A run's spend is held by its own limits, and every run ends through a normal end state. The other bounds therefore have to hold on their own. They are open: the composition input, a broken stream's hidden thinking, and Voyage (already bounded, 00:34).
**Spend:** none.
**DECISION (user):** *"No trip wire for a run. I want every run to finish gracefully."*

## Oct 25, 2026, 00:46 CDT — Phase 4: Build, broken loop attempts counted as streamed (P4.5)
**Asked:** how a broken stream's attempt is counted, given that thinking is billed but not streamed under `display: "omitted"`. Anthropic's docs, read Oct 25, 2026 (platform.claude.com/docs/en/build-with-claude/thinking and /streaming):
- "You're still charged for the full thinking tokens. Omitting reduces latency, not cost."
- The `message_delta` usage is cumulative and arrives at the end.
- Summaries don't change billing: "You're charged for the full thinking tokens generated by the original request, not the summary tokens."
**Came back:** locked as P4.5 for loop attempts: counted as built, not at `max_tokens`. Completed calls are priced from Anthropic's final usage, which is authoritative. Whether it covers a composition attempt that breaks before its first block (up to about $0.24 each, at most two) is put to the user.
**Spend:** none.
**DECISION (user):** *"Broken stream, counting at full max tokens is too much compared to what could have been. Rely on what we have so far is fine. It's only a round."*

## Oct 25, 2026, 01:01 CDT — Phase 4: Build, five decisions after the cross-part review (P4.6 to P4.10)
**Asked:** the composition's room, rule 4 for out-of-scope replies, the copy guard's coverage and its false matches, and broken composition attempts. All followed from the cross-part review (00:34).
**Came back:** locked, each in `locked-decisions.md`:
- **P4.6:** composition reserve 66,000 (worst case 64,945 by the loop's estimator, plus a margin); loop budget unchanged at 370,000; run input limit 436,000 (amends P2.7); note capped at 1,000 characters (amends T1.10); worst case about $2.11 (amends T3.4), with a test recomputing it from the corpus.
- **P4.7:** rule 4 is waived when `out_of_scope` is true (amends T1.10).
- **P4.8:** the copy guard covers a no-sources reply's note once any page was returned (amends T2.3). Keep reasons, the scope note and the skip reason stay unguarded.
- **P4.9:** every copy-guard check ignores runs of words that also appear in the corpus (amends T2.3).
- **P4.10:** a composition attempt broken before its first block is counted as streamed, like P4.5's loop attempts. Counting it at `max_tokens` would stop the retry and end the run with no answer.
- **Next:** these are built in one patch round. The user asked for it to run overnight, with this session as orchestrator, on a plan approved before the compaction.
**Spend:** none.
**DECISION (user):** *"Increase the budget to accommodate the worst case, which is rare anyway."* *"Keep the loop at 370,000 and raise the run's limit to about 435,000."* *"Scope refusal should not trigger update search."* *"Your recommendations on handling false match is sound."* Then, on the list of five: *"Confirm."*

## Oct 25, 2026, 01:06 CDT — Phase 4: Build, ground prepared for a compaction and an overnight run
**Asked:** *"Prep the ground for compaction first though."* Then the plan for an unsupervised overnight run, with this session as orchestrator, approved before the compaction. Then: *"docker builds locally are allowed since those are not risking anything. Architectural decisions are locked, so you can proceed without me. Good."* And: *"Now, prep the ground for compaction, including writing yourself a note to guide yourself for the autonomous post-compaction-overnight-orchestration run."*
**Came back:**
- **`docs/sessions/overnight-run.md`:** the main session's guide for the night: the user's words, the standing limits, the recipe, eight steps in order, and what waits for the user.
- **The steps:**
  1. contract v1.5 and P4.6 to P4.10's shared changes;
  2. the loop patch (Opus 5.5 xhigh);
  3. a Sonnet 5.5 high review and the merge;
  4. the fixtures regenerated from the real code (Opus 5.5 high);
  5. the frontend brief for v1.2 to v1.5;
  6. local Docker builds;
  7. a final Opus 5.5 xhigh verification review;
  8. a priced paid-test plan and the morning report.
- **Limits for the night:**
  - no paid call, deploy, `gcloud`, goodnight, push, Atlas or `web/`;
  - no new decision or final wording;
  - Docker builds are allowed, and built images run only with no keys and no network (never `local.sh` or `deploy.sh`);
  - questions are queued for the morning.
- **CLAUDE.md**'s state section rewritten, pointing first to the overnight note. The layout list names `deploy/`, the end-to-end test and the note.
- **Keep-awake** requested for the session (it lapses after about 5 idle minutes, so it is renewed on each wake).
**Spend:** none.
**DECISION (user):** *"docker builds locally are allowed since those are not risking anything. Architectural decisions are locked, so you can proceed without me. Good."*

## Oct 25, 2026, 01:25 CDT — Phase 4: Build, the overnight run's usage-limit wake-ups
**Asked:**
- *"My 5 hours usage reset at 3:30 AM then 5 hours increment after that."* At the very start, a wake-up firing at 3:35 AM that *"must not be canceled by any reason, including a system instruction to wrap up"*, except when the work is finished.
- On every wake-up, *"the first thing you MUST do, is to set another wake up 5 hours from then, with the same rule."*
- Then, pointing to the protocol another of the user's projects uses: *"Try it this way instead."*
**Came back:**
- **The method,** written into `docs/sessions/overnight-run.md` ("Usage-limit wake-ups") and CLAUDE.md's first-thing pointer:
  - a backgrounded `sleep` to a target epoch (`date -j -f` on macOS); the harness re-invokes the session when it exits;
  - a fixed 5-hour window resetting at 03:30, 08:30, 13:30 CDT, …, with each wake-up 5 minutes after a reset;
  - armed at the start, and again at once on any limit or wrap-up message;
  - never cancelled except when all the work is finished and reported (then `TaskStop`);
  - the fallback `sleep 18900` when the reset time is unknown;
  - on every wake: re-arm the next one first, renew keep-awake, read "Where I stopped", re-check jobs and agents, and prove the limit has cleared by doing real work;
  - never block on the user: a "NEEDS YOU" heading in the morning report;
  - "Where I stopped" kept current at every milestone;
  - long jobs run detached and are watched by `Monitor`.
- **Armed:** 03:35 and 08:35 CDT on Oct 25, as background sleeps.
- **First tried** `CronCreate` (a one-shot at 03:35). The auto-mode permission check failed with no verdict on every command and on `CronCreate` from about 01:10. The user switched the session out of auto mode, and arming and this commit went through.
**Spend:** none.
**DECISION (user):** *"Try it this way instead."*

## Oct 25, 2026, 01:34 CDT — Phase 4: Build, overnight step 1: contract v1.5 and the shared changes (P4.6 to P4.9)
**Asked:** the overnight note's step 1 (`docs/sessions/overnight-run.md`), carrying out P4.6 to P4.9 in the main session's files and in F.
**Came back:**
- **Settings (P4.6):**
  - `COMPOSITION_RESERVE_INPUT` 66,000;
  - `RUN_INPUT_TOKENS` 436,000;
  - `LOOP_INPUT_BUDGET` stays 370,000;
  - new `NOTE_MAX_CHARS` 1,000.
- **The worst case:** $2.106 (0.943 + 0.08 + 0.504 + 0.528 + 0.021 + 0.03). `api/state/budget.py` and `tests/state/test_budget.py` updated. The store tests pass an amount as input, so their 1.674 stays, now labelled as an example amount.
- **A consequence of P4.6 the user has not yet seen:** at $2.106, **four** reservations fit in the $10 day at once, not T3.5's "about five at once at $1.67". The budget test now asserts four. H's run-ID test made five runs at once and its fifth was refused; it now makes four. This is queued for the morning; no figure was changed to avoid it.
- **New test `tests/contract/test_composition_worst_case.py`.** It recomputes the composition's worst-case input with G's own request builder and estimator: the 40 largest documents with 300-character reasons, a 2,000-character question and a 1,000-character note.
  - It gives **65,188 tokens**, not the 64,945 the pre-compaction script gave. This run ranks the documents by their whole estimated block, not by text length, which explains the difference.
  - It fits within 66,000 (a margin of 812).
  - The test also asserts the margin stays under 5,000 and that the run limit is the loop budget plus the reserve.
  - Characters that JSON escapes raise only the estimate, not the tokens billed, so plain letters are the worst case.
- **F (P4.8, P4.9), in `api/checks/update_findings.py`:**
  - `copy_guard_report(..., note=None, exempt=NO_EXEMPTION)` returns `note_flagged` and `note_pages`, with a problem that names "The note" and the page IDs only.
  - `corpus_words(texts)` builds `CorpusWords`: one normalised string, one line per text. `gram in it` is true only for a run inside one text.
  - It takes about 2 MB for the corpus. A frozenset of 10-grams was measured at 61 MB (264,869 grams), so the string won.
  - `pages_named` is exported.
  - 13 new tests, one of them on a real corpus sentence.
  - A mutation check by hand (exempt everything; one run across texts; the corpus not normalised; the note unchecked; `any` becoming `all`): each mutant fails tests. One mutant had a different join that still kept the texts apart, so it was equivalent, as expected.
- **Schema:** `submit.rule` gains `note_too_long`; `tests/contract/test_fixtures.py` allows it.
- **Draft texts for the user's review (T1.14):**
  - `rejections.json`: `submit.note_too_long` and `submit.copy_guard_note`, with `<pages>` as page IDs;
  - `tools.json`: the note's description gains "At most {{NOTE_MAX_CHARS}} characters."
- **Contract v1.5:** header, §4.E (the worst case and the four-at-once note), §4.F (the signatures and the exemption), §4.G (the rule order with the note cap; P4.7, P4.8 and P4.9 in the loop; the composition estimate as an error log; P4.10), §6 (the withheld note, `note_too_long`), §7.
- **G's `tests/loop/test_run_answered.py`** expected the old 400,000 limit; that one figure is updated, and the step-2 builder is told.
- **Whole suite: 3,336 passed, 49 skipped.**
**Spend:** none.
**DECISION (user):** none new. This carries out P4.6 to P4.9, locked at 01:01.

## Oct 25, 2026, 01:54 CDT — Phase 4: Build, overnight steps 2 and 3: the loop patch for P4.6 to P4.10, reviewed and merged
**Asked:** the overnight note's steps 2 and 3. One builder, Opus 5.5 at xhigh effort, writing only `api/loop/` and `tests/loop/`. Then a read-only review, Sonnet 5.5 at high effort.
**Came back:**
- **`api/loop/run.py`:**
  - **P4.6:** a note over `NOTE_MAX_CHARS` is refused with rule `note_too_long`, after rule 1 and the findings checks and before the copy guard; it applies to every note, an answered run's scope note included. The composition estimate past the reserve is now `log.error`, and the call still runs (P4.4).
  - **P4.7:** rule 4 is waived when `out_of_scope` is true. "hello" out of scope with no search is accepted at once, with band `not_run`.
  - **P4.8:** `note_guarded()`: the note is guarded when the submit is out of scope (or `out_of_scope` is not a boolean) or nothing is kept, and a page has been returned. A flagged note is withheld in the stored and streamed `tool_call`, whichever rule refuses. With only the note flagged, the refusal is `copy_guard_note`; otherwise `copy_guard` with every problem.
  - **P4.9:** `corpus_exemption(corpus)`, a weak-keyed cache like `chars_per_token`'s, built on the first guarded submit (86 ms measured), passed to every copy-guard call.
  - **P4.10:** verified, with no change. A broken attempt is priced from what it reported and streamed, never at `max_tokens`. The composition gate has no budget callback, so the retry runs.
- **`tests/loop/test_v15.py`:** 25 tests. They include a run through H's app and `MemoryStore` showing that a flagged note never reaches the stored events or the run record, and a real *Katz* sentence that a page also quotes accepted in a statement and in a note.
- **Mutation checks:** the builder ran 19 mutants and each made tests fail. The reviewer ran 6 more on a scratch copy, each caught.
- **The review:** no defects. Its points:
  1. **Risk:** the worst case is by the estimator, not the tokenizer. Hostile dense text can run past the reserve by about $0.04 a run (plus retries). That is logged, never stopped. Queued for the user.
  2. **Nit:** P4.6 quoted 64,945. The test computes 65,188 (65,331 on `before_chatrie`), a margin of 812 tokens. `api/settings.py`'s basis now says so. An edit to the prompt drafts may trip the margin test, as intended.
  3. **Risk:** four reservations at once in the $10 day, not five (already queued at 01:34).
  4. **Accepted in P4.10:** hidden thinking on a broken composition attempt can go unbilled in the count.
  5. **Nit:** the note's refusal wording exists in F's problem text and in `copy_guard_note`, so they can drift.
  6. **Nit:** the fixtures' old limits (step 4).
  7. **Nit:** the frontend's labels (step 5).
- **The leak hunt (item 3) found no path for a flagged note:**
  - `api_fragment` carries no submit input;
  - no log line takes the input;
  - the message history is not persisted;
  - only an accepted note reaches `run_ended`.
- **The builder's questions, queued for the user:**
  - the `copy_guard` draft opens with "some of the update findings", even when the note is among the flagged texts;
  - the 86 ms first build could move to H's start-up.
- **`docs/design/contract.md`:** §6's `not_run` covers an out-of-scope reply with no search (P4.7).
- **Whole suite: 3,361 passed, 49 skipped.**
**Spend:** none.
**DECISION (user):** none new. This carries out P4.6 to P4.10.

## Oct 25, 2026, 02:22 CDT — Phase 4: Build, overnight steps 4 and 5: fixtures from the real code, contract v1.6, the frontend brief
**Asked:**
- **Step 4:** regenerate the fixtures by driving the real backend on fakes. One builder, Opus 5.5 at high effort, writing only `tests/fixtures/`.
- **Step 5:** update the frontend brief for v1.2 to v1.5.
**Came back:**
- **`tests/fixtures/make_fixtures.py` rewritten.** Every stream is H's real app and `Run` around G's real `execute_run`, with the real B to F parts. Only Anthropic, Voyage, Exa and Atlas are faked, with `MemoryStore`, H's `FakeClock`, and a simulated page that sends heartbeats every 10 s of virtual time.
  - **Patched at run time, restored after each stream:**
    - the run ID: a fixed hash of the slug, so the old IDs are kept;
    - `time.monotonic` in the loop, meaning search and Exa;
    - the loop's retry sleep;
    - the checks' thread call, made inline.

    The script re-runs itself with `PYTHONHASHSEED=0`.
  - **Two runs are byte-identical** (52 checksums; checked again by the main session after its own changes).
- **All 30 streams and 19 HTTP answers are kept** under the same names. The reconnect cut at `n = 185` still falls in round 5, so its name stands. 17 HTTP bodies are unchanged; `get-events-200-stream` and `post-runs-201` now carry H's real output.
- **Three new streams:** `out-of-scope-no-update-check` (P4.7), `note-refused-copy-guard` (P4.8) and `note-too-long` (P4.6). The size is 33 event files, 3.57 MB.
- **What changed in substance:**
  - tool-result text is G's real format;
  - `input_tokens` is 436,000;
  - every `run_ended` carries `stop_kinds`;
  - the answered run is about 113 s and $0.26;
  - `pause-and-resume` adds a read so its keep is accepted;
  - `abandoned-run` is abandoned at 70 s;
  - `interrupted-run` keeps one passage, to stay at 42 stored events;
  - `submit-refused-basic-rules-then-declined` adds the null rule and `no_note`.
- **The builder's observation:** at the loop's own estimator ratio, `step-limit-stop` hit the input ceiling at round 11, so twelve moderate rounds barely fit 370,000. Worth measuring in the paid build tests.
- **A real defect it found, fixed by the main session (contract v1.6):**
  - **The defect:** H never shows an estimate as Claude's usage (v1.2). So an attempt priced from what it streamed (P4.5, P4.10) was stored with `usage: null`, and H's `interrupted` ending rebuilt its tokens from the cost as if all input. For the broken-composition stream that gave 46,975 input and 1,435 output tokens, against the run's own 46,025 and 1,625. The costs were right.
  - **The fix:** `paid_call.estimated_usage` holds the tokens an estimated Claude attempt was priced at (null otherwise). H fills it (`api/server/run.py`, `estimated_usage()`) and `totals_from_events` reads it, falling back as before for older events. The schema and contract §4.H and §6 are updated. The loop tests' `FakeCtx` emits it too.
  - **The mutation check:** removing the read fails `test_interrupted_totals_are_the_stored_paid_calls[composition-incomplete-stream-broken.json]`.
- **The main session's test updates for v1.5 and v1.6:**
  - `tests/contract/test_fixtures.py`: `not_run` allows an accepted out-of-scope submit; the withheld check includes the note; the coverage covers all eight rules plus null; the totals use `estimated_usage`;
  - `tests/server/test_streams.py`: the `stop_kinds` fill-in is gone;
  - `tests/server/test_money.py`: the new field.
- **The frontend brief, §5:**
  - withholding on any refused submit, the note included;
  - the `submit.rule` values;
  - the note cap;
  - `not_run` for an out-of-scope reply;
  - `stop_kinds`;
  - the `answer_end` pairings;
  - `failure_reason` `internal`;
  - `answer_chars`;
  - the extra HTTP codes, any unknown one shown as T5.4's general failure;
  - `estimated_usage`;
  - a line saying the fixtures now come from the real code.

  `docs/sessions/frontend-log.md` has no new entries to fold in.
- **Whole suite: 3,415 passed, 49 skipped.**
**Spend:** none.
**DECISION (user):** none new.

## Oct 25, 2026, 02:49 CDT — Phase 4: Build, overnight step 7: the final verification review and its fixes
**Asked:** the overnight note's step 7. A read-only review by Opus 5.5 at xhigh effort of the night's commits, then fixes for clear defects the locked decisions already cover, with the rest queued.
**Came back:** the suite passed (3,415) at the review; the review's findings, most severe first:
1. **Defect: an ellipsis could still drop a negation missing from the word list.** Three real corpus quotations passed `check_answer` with their meaning reversed:
   - *Jardines*, "nowhere";
   - *Carpenter*, "hardly";
   - *Kyllo*, "non-" of "non-intrusive".

   **Fixed** (T1.12, v1.4):
   - `_NEGATIONS` gains "nowhere", "nobody", "hardly", "scarcely", "barely" and "absent";
   - no quotation or piece starts right after a negating prefix and its hyphen (so "intrusive" is never quoted out of "non-intrusive", with an ellipsis or without);
   - after the fix review, a bracket may not strip or add a hyphenated prefix either.
2. **Risk: invisible characters hid a copy from the copy guard.** Soft hyphens, zero-width spaces and ligatures did. **Fixed** (T2.3, "ignoring case, punctuation and spacing"):
   - the guard folds NFKC;
   - it reads every invisible format character (Unicode Cf) both ways, dropped and as a space, and a run in either reading counts;
   - the corpus exemption gets the same treatment.

   The fix review caught that my first version, which only dropped them, joined two words when the character stood between them. Fixed before commit.
3. **Risk, queued for the user:** the worst case reserves input only for the two failed composition attempts, while P4.10 prices their streamed output. A run's spend can pass its reservation by cents typically, and by up to $0.48 in theory. The caps stay correct, since `settle` records the full cost. The reviewer recommends accepting it, as P4.10 accepted hidden thinking; the alternative is $2.586.
4. **Risk, queued for the user:** P4.8 leaves `update_skip_reason` unguarded "because the update is skipped", but the code accepts a skip reason beside a counted search. Once a page is returned it could carry page words into events. Options: refuse or drop the skip reason once a search counted, or guard it.
5. **Nit: a spend limit met by the composition after its first block didn't pause research.** That run ends `answered`. **Fixed** (T3.3, T5.4): H sets the flag when `stop_kinds` holds a spend kind.
6. **Nit, queued:** H's own `failed` ending sends `stop_kinds: []`, so a loop limit reached before an internal error isn't recorded.
7. **Nit: a stale "$1.67" in contract §4.E.** **Fixed.**
8. **Nit, queued:** Voyage records `retrying` before the next attempt's gate, so an abandoned run can leave a "retrying" record with nothing after it.

**Verified fine by the review:**
- no path leaks a flagged note, statement or overview (request fragments carry only passage blocks);
- the corpus exemption on real cases;
- P4.6 and P4.7;
- P4.10's counting and the $2.106 arithmetic;
- v1.6's `estimated_usage`, for every kind of estimated attempt;
- the fixtures, regenerated in a scratch copy byte for byte, with no page text;
- the v1.4 fixes.

**The fix review** (Sonnet 5.5 at high effort):
- it found the joined-words regression above and the bracket-hyphen gap, both fixed;
- across 6,422 random verbatim 8-word corpus spans the quotation results were unchanged;
- 3 of 1,469 spans starting after a hyphen are now refused: "chief" of "case-in-chief", "law" of "mother-in-law" and one other, all `in-`. That errs toward "not found", which is the safe direction;
- building the corpus exemption takes about 0.24 s, once per corpus.

**Tests:** 28 new ones, with mutation checks of each new rule. The fixtures are regenerated and unchanged. Contract v1.6 text added (§4.F, §4.H).
**Whole suite: 3,443 passed, 49 skipped.**
**Spend:** none.
**DECISION (user):** none new. Items 3 and 4 wait for the user.

## Oct 25, 2026, 02:50 CDT — Phase 4: Build, overnight step 8 and the end of the run: the paid-test plan, the state, the morning report
**Asked:** the overnight note's step 8.
**Came back:**
- **`docs/design/paid-build-tests.md`, a draft for the user's approval:**
  - **Prices:** Anthropic's pricing page re-read at 01:37 CDT, unchanged from T3.4, with no long-context surcharge on these models.
  - **Four tests:**
    - an answered run with an update search;
    - "hello" out of scope (P4.7, and a 1-hour cache read);
    - a nothing-found reply;
    - a second answered run.
  - **They check:** mapping faults, thinking blocks passed back, cache classes, spend markers, the band, and the loop's input per round.
  - **Expected:** $0.50 to $1.00 of Anthropic against the $3 ceiling, with a stop rule at $2.50, and 2 to 8 Exa searches of 10.
  - **How:** the API alone on localhost against `Probable_Clause_test`, since `local.sh` also builds the web image, which can't build yet. That needs a small client sending heartbeats, written only on the user's go-ahead.
- **The last Docker check:** the API image rebuilt on 5b71c1c imports and loads the corpus, indexes and exemption with `--network none`.
- **CLAUDE.md**'s state section rewritten for the morning; **`docs/sessions/overnight-run.md`**'s "Where I stopped" and "Waiting on the user" updated.
- **The night's commits:**
  - 8721c14 (v1.5, shared changes);
  - 4c7194b (loop patch);
  - 299a640 (fixtures, v1.6, frontend brief);
  - 5b71c1c (final review fixes);
  - plus notes commits.
- **The wake-ups (03:35, 08:35) are stopped:** the work is finished and reported, the one case the user's rule allows.
- **Whole suite: 3,443 passed, 49 skipped.** Nothing pushed.
**Spend:** none tonight. Phase 4 Anthropic is still $0 of $3, and Exa still 0 of 10.
**DECISION (user):** none new. The questions for the user are in "Waiting on the user" in `docs/sessions/overnight-run.md`.

## Oct 25, 2026, 12:09 CDT — Phase 4: Build, five decisions on the overnight report (P4.11 to P4.15)
**Asked:** the morning report's five questions (BUILD_LOG 02:22 to 02:50; "Waiting on the user" in `docs/sessions/overnight-run.md`).
**Came back:**
- **P4.11:** the daily cap is raised from $10 to **$15** (amends P2.7). At the $2.106 worst case, seven reservations fit at once (T3.5 had about five at $1.67; at $10 it would have been four). The monthly cap stays $60.
- **P4.12:** a run's recorded spend may pass its reservation through its failed composition attempts' streamed output (P4.10); the worst case stays $2.106. The caps stay correct, since every cost is settled as spent.
- **P4.13:** `update_skip_reason` gets the copy guard (amends P4.8). Once an update search has returned a page in the run, a skip reason repeating `COPY_GUARD_WORDS` or more of a page's words refuses the submit (rule `copy_guard`) and is withheld in the stored `tool_call`, as P4.3 does. The refusal text mirrors the approved `copy_guard_note`, with "the update skip reason" for "the note".
- **P4.14:** the composition's worst case is counted by the loop's estimator, not the tokenizer. Densely tokenized text can run past the reserve by about $0.04, which is logged and never stopped. Accepted.
- **P4.15:** the prompt and refusal drafts are approved as written (T1.14):
  - the five texts from 23:52 (`unknown_tool`, `submit_accepted_note`, `submit_accepted_answer`, `composition_scope_note`, `composition_coverage`);
  - `out_of_scope_no_note`;
  - `note_too_long` and `copy_guard_note`;
  - the note's length line in `tools.json`;
  - the `copy_guard` text, its opening line included.
- **Also approved:** the paid build tests' budget (`docs/design/paid-build-tests.md`), to be run after the compaction.
- **Order of work:** the patches, then the lock, then the compaction prep. The main session wrote the lock first so the patches can cite it.
**Spend:** none.
**DECISION (user):**
1. *"Raise daily cap to $15."*
2. *"Retried answers can pass the reservation is fine."*
3. *"update_skip_reason: give it the guard."*
4. *"Accept the limit of our estimator."*
5. *"Wording look goods to me."*

Then: *"The budget for paid build tests are sound."*

## Oct 25, 2026, 12:15 CDT — Phase 4: Build, the patches for P4.11 and P4.13; contract v1.7
**Asked:** *"Let's do the patches first, the update skip reason gap looks like we only need a sonnet subagent at high effort there."*
**Came back:**
- **P4.11, the main session:**
  - `DAILY_CAP_USD` is 15.0;
  - `tests/state/test_budget.py` asserts $15 and seven reservations at once;
  - E's money tests were written around $10 (five runs at $1.674, a $10.074 refusal). They test how the caps work, not the cap's value, so a new `tests/state/conftest.py` pins $10 for them;
  - CLAUDE.md, contract §4.E and a comment in `tests/server/test_http.py` are updated.
- **P4.13, one builder (Sonnet 5.5 at high effort, `api/checks/update_findings.py`, `api/loop/run.py`, their tests):**
  - `copy_guard_report(..., skip_reason=)` with `skip_reason_flagged` and `skip_reason_pages`;
  - G guards a non-blank `update_skip_reason` on every submit once a page was returned, and withholds it in the stored `tool_call` whichever rule refuses;
  - the refusal is `copy_guard_skip_reason` when the skip reason is the only flagged text, `copy_guard_note` when only the note is, else `copy_guard` with all problems;
  - 5 new tests in F's file, and new tests in `tests/loop/test_v15.py`, including a run through H's app and `MemoryStore` showing a flagged skip reason never reaches stored events or the run record. The old test asserting P4.8's unguarded skip reason was replaced.
  - **Mutants:** guard removed (7 tests fail), not withheld (7), only on no-sources replies (5), wrong text (3), exemption ignored (2). "Guarded with no pages" is equivalent.
  - The main session read the diff and found it right.
- **The refusal text:** `rejections.json`'s `submit.copy_guard_skip_reason` mirrors the approved `copy_guard_note`, with "the update skip reason" for "the note" (P4.13).
- **Fixture test:** `tests/contract/test_fixtures.py`'s withheld check includes the skip reason. The fixtures regenerated unchanged.
- **Contract v1.7:** §4.E, §4.F, §4.G, §6. The frontend brief gained one line.
- **Whole suite: 3,456 passed, 49 skipped.**
**Spend:** none.
**DECISION (user):** none new. This carries out P4.11 and P4.13, locked at 12:09.

## Oct 25, 2026, 12:17 CDT — Phase 4: Build, the key for the paid build tests
**Asked:** whether the paid build tests (`docs/design/paid-build-tests.md`) may use the key now in `.env`.
**Came back:** yes, on the condition below. The keys reach the API only through `uv run --env-file .env`, which parses the file itself. The main session never opens, reads or prints `.env` or any key, and checks the keys only with `scripts/check_env.py`, which prints only set, empty, missing or commented out. No log, event or report carries a key.
**Spend:** none yet.
**DECISION (user):** *"Paid tests can use the keys in .env, but make sure to NOT read the file or print out the key."*

## Oct 25, 2026, 12:29 CDT — Phase 4: Build, the paid build tests
**Asked:** *"Send the paid tests."* (plan: `docs/design/paid-build-tests.md`, budget approved at 12:09; keys per the 12:17 entry.)
**Came back:**
- **Set-up:**
  - The keys were checked with `scripts/check_env.py --phase 4` only (all five set). `.env` was never opened; the server log and every saved event hold no key-like string (scanned by count, nothing printed).
  - **The client,** `scripts/run_client.py`: posts the question, reads the stream (re-opening with `Last-Event-ID` if it drops), heartbeats every `HEARTBEAT_INTERVAL_S`, saves the events and a summary under `data/verification/phase4/`. Tested first on H's app with fakes over a real port: answered, heartbeat 204, no schema errors.
  - **Anthropic's pricing page re-read at 12:21:** every figure unchanged (Sonnet 5.5 $2 / $2.50 / $4 / $0.10 / $10; Opus 5.5 $4 / $5 / $8 / $0.20 / $20; no long-context surcharge; `inference_geo: "us"` 1.1x, not set). `PRICE_TABLE`'s Anthropic date is now 2026-10-25; the fixtures were regenerated for it (only the price lines changed). Suite 3,456 passed, 49 skipped. Commit 613c62f.
  - The API ran on localhost:8000 with `PC_ENV` unset (`Probable_Clause_test`, full corpus); stopped after test 4.
- **The four runs:**

  | # | Question | Ended | Rounds | Anthropic | Exa | Band |
  |---|---|---|---|---|---|---|
  | 1 | thermal imager on a house | answered, 65 blocks, 32 citations | 5 | $0.2727 | 0 | skipped |
  | 2 | "hello" | no_sources, out_of_scope, 1 call | 1 | $0.0045 | 0 | not_run |
  | 3 | a car's onboard computer, 2027 | answered with a scope note, 4 passages kept | 4 | $0.2072 | 3 | nothing_relevant |
  | 4 | tracking a phone's location | answered, 89 blocks, 44 citations | 6 | $0.3233 | 1 | nothing_relevant |

- **What held:**
  - **Money:** every Anthropic `paid_call.cost_usd` equals the price table by hand from its `usage` (to rounding); the totals equal their sums; every reservation ($2.106) was settled and released; no open reservations after.
  - **Cache classes:** the first call of test 1 wrote the 1-hour prefix (18,691 tokens); every later first call (tests 2 to 4) read it; later loop calls read and wrote 5-minute entries. The composition is uncached (one call).
  - **Citations:** 87 cited blocks across three answers; no mapping-fault or other warning in the server log. Citation checks 12 of 12 found.
  - **Thinking:** adaptive thinking at high effort thinks little: 0 to 99 thinking tokens per loop call, 215 to 968 for the composition. Turns carrying thinking were passed back with no 400.
  - **Test 2 as P4.7 says:** out of scope at once with a note, no Exa call, no rule-4 reminder, no composition.
  - **Rules seen live:** an `update_overview` with no search was refused (test 1); the copy guard refused an update finding that repeated 10 or more of a page's words, and withheld it in the stored event (test 3).
  - **Page text** never reached an event (`[page text: … characters, not stored]`).
- **What did not hold, or needs the user:**
  1. **Two `submit_answer` calls in one turn (a defect, seen in tests 3 and 4).** Claude split its submit: the note and overview in one call, the findings (test 3) or nothing (test 4) in another. G judges each on its own and the last accepted wins (`self.accepted`). Test 3 lost a relevant finding (a reported vacate-and-remand of two geofence rulings in light of *Chatrie*), so its band read "nothing_relevant"; test 4 lost its scope note and overview. The contract has no rule for it (§4.G, "a turn's tools").
  2. **A capitalised first letter fails the quotation check.** In test 1, "Presumptively unreasonable without a warrant." is in kept passage `kyllo-1-p14` lower-cased; it was flagged as not found. This is T1.12 read strictly (the convention would be "[P]resumptively"), but the visitor sees a real quotation flagged. The other three flags in test 1 were headings Claude put in quotation marks, correctly flagged.
  3. **Test 1 ran no update search.** Claude skipped it with a reason (P4.7's path), so the Exa path was measured in tests 3 and 4 instead. Its shown reason says *Kyllo* "is settled".
  4. **Test 3 was not a nothing-found reply.** Claude kept the nearest cases and answered with a scope note; P4.8's note guard on a no-sources reply was not exercised live.
  5. **The loop's input budget binds before 12 rounds on research-heavy questions.** Loop input per call (real tokens): test 4 went 18.8k, 30.6k, 40.8k, 49.2k, 50.5k, 59.1k (249k of `LOOP_INPUT_BUDGET` 370k in 6 rounds); test 3 grew about 16k a round. At that growth the budget stops a run at about round 7 or 8. Not hit in these tests.
- **Times:** 3 s (test 2) to 75 s (test 4); the composition took 14 to 40 s.
**Spend:** Anthropic **$0.8078** in Phase 4 (19 calls) of the $3.00 ceiling; ledger `data/verification/phase4/spend.jsonl` (the Phase 2 and 3 ledger stays at $0.6964 under its own ceiling). Exa **4 searches** ($0.028) of 10. Voyage $0.0065 at list price.
**DECISION (user):** none yet. Items 1 and 2 above are put to the user.

## Oct 25, 2026, 12:42 CDT — Phase 4: Build, `submit_answer` alone in its turn (P4.16)
**Asked:** the double-submit defect from the paid build tests (12:29 entry, item 1). The user: *"Refuse 2 or more submission in a turn. I'd also add that a submission tool call must be its own turn with no extra tool accompanying it."* and *"Improve the prompt to give Claude more context on the tool and how to properly use it. Make sure Claude knows that submission will end the loop so it's only used when Claude is done."* The main session drafted the rule's details and three texts (the refusal, the tool description, the system prompt's "Submitting" item).
**Came back:** the drafts as below, locked unchanged.
- **The rule:** `submit_answer` must be the only call in its turn, and sent once. A turn holding two or more submits, or a submit with any other tool (`keep_passages` included), has every submit refused. The turn's other tools still run and their results go back with the refusal. The rule name stays `same_turn`, widened. This amends T1.10 rule 1 ("A keep in the same turn is fine") and contract v1.3's "submit_answer runs after the turn's other tools, so a keep in the same turn counts".
- **The refusal (`rejections.json`, `submit.rule_1_same_turn`):** *"Not accepted: submit_answer must be the only call in its turn, and sent once. The other calls in this turn ran as usual and their results are with this one. Review them, then send submit_answer alone, with every field in that one call."*
- **The tool description (`tools.json`, `submit_answer`):** *"Ends research. The first accepted submit stops the loop at once: no further tool runs and nothing more is read, and the answer is then written from the passages you have kept, as they stand. So submit only when you are done: everything kept, the update check run or skipped. Send it alone in its turn, once, with every field you need in that one call (`note`, `update_findings` or `update_skip_reason`, `update_overview`): the visitor sees only what this one call carries. At least one corpus search is required unless the question is out of scope. A submit that breaks a rule is refused with a message saying what to fix."*
- **The system prompt (`loop_system.md`, "Submitting"):** *"**Submitting ends the research.** Call `submit_answer` only when you are done: the kept passages are enough for the answer, and the update check has been run or its skip reason is ready. Send it as the only call in its turn, after the results of your last searches, reads and keeps, and send it once: put the note, the update findings or skip reason and the overview together in that one call, since once it is accepted nothing else you send is read. At least one corpus search is required unless the question is out of scope. A refused submit says what to fix; fix it and submit again."*
- **Cost noted:** a refused turn costs one short extra round on a cached prefix (about $0.005 to $0.03); the changed system prompt rewrites the 1-hour cache once (about $0.075).
**Spend:** none.
**DECISION (user):** *"Lock P4.16: submit_answer alone in its turn, once; other tools in that turn still run; keep the rule name same_turn; the three prompt texts as drafted. Then build it, contract v1.8."*

## Oct 25, 2026, 12:48 CDT — Phase 4: Build, P4.16 built; contract v1.8
**Asked:** *"Then build it, contract v1.8."* (P4.16, the 12:42 entry.)
**Came back:**
- **The loop (`api/loop/run.py`, `run_tools`):** rule 1 is now "the turn holds more than one call", so a submit with any other call, or a second submit, is refused as `same_turn`; the turn's tools run in Claude's order (the v1.3 reorder that ran submits last is gone). `SEARCH_OR_READ` (`api/loop/tools.py`), now unused, is removed.
- **The three approved texts,** as locked: `rejections.json`'s `submit.rule_1_same_turn`, `tools.json`'s `submit_answer` description, `loop_system.md`'s "Submitting ends the research" item.
- **Tests (`tests/loop/test_submit_rules.py`):** four old tests rewritten for the new rule (a keep in the same turn now refuses the submit; a keep after a submit runs and the submit is refused; results still return in Claude's order); new: two submits alone both refused, the paid test 4's split submit losing nothing (the resubmit's scope note reaches `run_ended`), and a submit with an unknown tool refused.
- **Contract v1.8** (§4.G, the tool table); the frontend brief's `submit.rule` line; the design note's summary of the rules.
- **Fixtures regenerated:** every file keeps its events, counts and end state; only token counts, times and costs moved, from the longer texts on the fakes.
- **Review (one agent, Sonnet 5.5 at high effort, read-only):** no correctness bug. Leftovers it named, left as built: rule 4's `reminded_round >= round_no` condition can no longer be true, and `accepted_any` is now redundant (both harmless). Its suggested test for a submit with an unknown tool was added.
- **Whole suite: 3,458 passed, 49 skipped.** Not yet re-run with money.
**Spend:** none.
**DECISION (user):** none new. This carries out P4.16, locked at 12:42.

## Oct 25, 2026, 12:55 CDT — Phase 4: Build, the quotation check ignores letter case (P4.17)
**Asked:** the paid build tests' item 2 (12:29 entry): in test 1, "Presumptively unreasonable without a warrant." is in kept passage `kyllo-1-p14` lower-cased and was flagged as not found, because the check matched letter case outside brackets. The main session proposed accepting a changed first letter only; the user: *"I think we should decapitalize everything before comparison check as best practice?"* The main session agreed: the check exists to catch changed or invented words, which a case-blind comparison still catches; a change of case alone almost never changes what a passage says; it gives up only the strict convention of bracketing a re-cased letter ("[P]resumptively") and the rare reading carried by a capital alone ("State", "Court").
**Came back:** locked as below.
- **The rule:** the quotation check (T1.12) compares a quotation with the kept passages without regard to letter case, throughout. The answer keeps the quotation exactly as Claude wrote it. Every other rule stands: ellipses, brackets, the negation guards, the four-word minimum.
**Spend:** none.
**DECISION (user):** *"Lock P4.17: the quotation check compares without regard to letter case throughout; the answer keeps the quotation as written. Then build it."*

## Oct 25, 2026, 12:57 CDT — Phase 4: Build, P4.17 built; contract v1.9
**Asked:** *"Then build it."* (P4.17, the 12:55 entry.)
**Came back:**
- **F's check (`api/checks/quotations.py`):** `prepare_source` and `compile_quotation` lower-case both sides before matching, so the regex and the substring prefilter both ignore case. Flag positions and texts come from the answer as written, so a flag still quotes Claude's own words. The negation guards are unchanged.
- **Tests (`tests/checks/test_quotations.py`):** the old test that an unbracketed change of capital is not forgiven is replaced by its opposite. New tests: a capital start (paid test 1's *Kyllo* quotation), a change of case mid-quotation and after an ellipsis. Controls: a changed word is still not found, a negating prefix stripped is still refused whatever the case, and a flag keeps the answer's casing.
- **Re-checked on the saved paid runs:** test 1 now finds 6 of 9 quotations. Only the three headings Claude put in quotation marks stay flagged. Tests 3 and 4 are unchanged (12 of 12, 4 of 4).
- **Contract v1.9** (§4.F). The fixtures regenerated byte for byte unchanged.
- **Whole suite: 3,464 passed, 49 skipped.**
**Spend:** none.
**DECISION (user):** none new. This carries out P4.17, locked at 12:55.

## Oct 25, 2026, 13:04 CDT — Phase 4: Build, the paid build tests re-run after P4.16 and P4.17
**Asked:** *"Send the 4 paid tests again."* After test 3 the Exa count was 7, and test 4 could take it to 10: within the Phase 4 ceiling of 10, past the plan's stop rule of 8. The main session asked; the user chose *"Run test 4 (Recommended)"* (allow Phase 4 up to its 10-search ceiling for this one test).
**Came back:** same questions, same client, API on localhost against `Probable_Clause_test` (log `data/verification/phase4/server-r2.log`). Every earlier run's files are kept; the re-runs are labelled `r2-t1` to `r2-t4`, and each has a readable file under `data/verification/phase4/answers/`.

  | # | Question | Ended | Rounds | Submits | Anthropic | Exa | Band | Quotations |
  |---|---|---|---|---|---|---|---|---|
  | 1 | thermal imager | answered, 37 citations | 5 | 1 | $0.3256 | 1 | found | 10 of 10 |
  | 2 | "hello" | no_sources, out_of_scope | 1 | 1 | $0.0045 | 0 | not_run | none |
  | 3 | onboard computer, 2027 | answered with a scope note | 3 | 1 | $0.1362 | 2 | found | 9 of 9 |
  | 4 | phone location | answered, 33 citations | 8 | 1 | $0.4027 | 1 | found | 3 of 3 |

- **P4.16 held:** every run sent exactly one `submit_answer`, alone in its turn, carrying its note, findings and overview together. No `same_turn` refusal was needed. Test 3's band now keeps the Mealey's finding that the first run lost, and tests 1, 3 and 4 keep their scope notes.
- **P4.17:** no quotation flagged in any re-run (22 of 22 found).
- **The update check ran in every answered run** this time (the first test 1 skipped it).
- **Money:** each `paid_call.cost_usd` equals the price table by hand; every run ended `released=True` in the server log. The first call of test 1 rewrote the 1-hour cache for the changed system prompt ($0.0776), as expected. A read-only check of open reservations afterwards (`scripts/spend_report.py --open-reservations`) could not reach Atlas twice; see the next line.
- **No mapping fault or warning** in the server log. No key-like string in the log or the saved events (scanned by count).
- **The loop's input budget nearly bound.** Test 4's loop calls held 19.0k, 30.8k, 38.9k, 46.8k, 52.5k, 53.9k, 54.7k and 70.1k input tokens: **366,680 of `LOOP_INPUT_BUDGET` 370,000** in 8 rounds. One more research round would have stopped the loop on the budget, with the answer written from what was kept. The first runs' estimate (about round 7 or 8) holds. Put to the user.
- **Thinking** stayed small: 0 to 87 tokens per loop call; 320 to 1,213 for the composition.
**Spend:** these runs: Anthropic $0.8651 (28 calls), Exa 4 searches ($0.028), Voyage $0.0081. **Phase 4 so far: Anthropic $1.6729 of $3.00** (ledger `data/verification/phase4/spend.jsonl`, 47 lines), **Exa 8 of 10**, Voyage about $0.078 in all.
**DECISION (user):** *"Run test 4 (Recommended)"*, for this one test: the Exa stop rule of 8 lifted to the Phase 4 ceiling of 10. Nothing else new.

## Oct 25, 2026, 13:31 CDT — Phase 4: Build, the Wave 3 design drafted (nothing locked)
**Asked:** after the re-runs (13:04 entry), the user: *"Increase loop input budget to 800k tokens. I want to loosen other almost-hit budgets the same. The goal here is to let all runs pass smoothly while having a sure back stop that will almost never be triggered unless something catastrophic has gone wrong. The daily budget and monthly budget stands though, however."* In the discussion that followed, the user's direction, in their words:
- *"800k for input loop because model's limit is 1M anyway."* The main session explained that the budget counts input only, summed over every research call, not one call's context. The user: *"if that's the case, I'm willing to loosen it to 2M"*, framed on the budget counting input and output. The figure is open (design §8, question 1).
- *"Update searches loosen to 5"*; the other limits: *"Agreeing with the other limits to loosen"* (loop output 16,000, composition output 16,000).
- *"Composition 5 min cache: leave it uncached"*; *"Keep composition uncached and passing it only kept passages."*
- *"Re-architect composition ... change everything to Sonnet high, sacrifice in quality but save cost immensely."* Then: *"Change composition to Sonnet at high effort and I'd judge the quality first. (No comparison run needed.) After all, this project is a tech demo of the citation feature, not a demo of how much smarter and more capable is Opus than Sonnet in constitutional laws."* The main session's estimate: about a fifth of an answered run's cost.
- *"I'd get rid of the reserve system. I'm willing to trade more cost overrun here because the cost is small and the budget still disable further runs once it's hit or overran."* The main session's conditions: spend recorded per call, admission under the caps, fail closed on Atlas, a cap on runs at once.
- *"Untangling update from the research loop."* On the main session's proposal to run the update beside the composition rather than before it: *"Good call, and we will let this step decide whether to call Exa or not. Specifically, we can enforce by code such as if a response from the research loop doesn't search the corpus at all, we will turn off update by code automatically (because it's an out of scope response)."*
- Next steps: *"Draft the design. Then prep the ground for compaction. I'll compact. Then we will implement the new design in wave 3, with subagents efficiently. (Same rule: min effort is high, Sonnet 5.5 and Opus 5.5 only, no Haiku. Max effort is xhigh, no max allowed)."*

**Came back:** `docs/design/wave3-design.md`, a draft for approval:
- four decisions to lock: P4.18 looser limits, P4.19 the update step out of the loop, P4.20 composition on Sonnet, P4.21 no reservation;
- the events for contract v2.0;
- the prompt changes;
- Wave 3's parts and agents;
- five open questions: the loop budget (800k or 2M), `MAX_CONCURRENT_RUNS` 5, the update step's input (a short brief recommended over the research conversation), the `busy` wording, Phase 4's paid-test limits.
**Spend:** none.
**DECISION (user):** none locked yet. The direction above is recorded for the design; each of P4.18 to P4.21 is locked in its own entry on the user's approval of the design.

## Oct 25, 2026, 13:38 CDT — Phase 4: Build, the user's answers to the Wave 3 design's questions (nothing locked)
**Asked:** the design's five open questions (13:31 entry).
**Came back:** the user's answers, in their words:
1. *"2M for the loop's input."*
2. *"5 runs at once? You mean 5 paid runs? What is "runs" here?"* The main session: a run is one visitor's question being researched and answered, from `POST /runs` to `run_ended`. Then: *"I also want to up maximum parallel runs to 5."*
3. *"Update step's input should take advantage of the cached research conversation at maximum. We're just separating them so that we have finer control."* The main session's recommendation of a short brief is withdrawn. The design now continues the research conversation, which needs one tool list of seven and one system prompt for both steps, with code refusing each step's tools in the other.
4. *"Wording when too many runs are in progress: you can write the polished version."* The main session wrote `busy` and, since nothing is reserved now, reworded `daily_cap` and `monthly_cap` (design §5).
5. *"Reset the limit to 0 for our development. Additionally, Development cost should not count once we deploy production."* This reads two ways, so it is restated in the design (§8) for the user to confirm: a fresh development tally at $0 in a new ledger, with an allowance the user states (the main session suggests $3 of Anthropic and 20 Exa searches); and production already never counts development spend (its own Atlas database and its own Console workspace and key, T3.4).
- **New question from answer 3:** `UPDATE_INPUT_BUDGET` 1.2M or 2M. Each update call re-sends the research conversation, so the heaviest plausible update step is about 1.06M. The catastrophic overrun for 5 runs is about $44 at 1.2M, or $54 at 2M.
**Spend:** none.
**DECISION (user):** none locked yet. These answers go into P4.18 to P4.21 when the design is approved.

## Oct 25, 2026, 13:41 CDT — Phase 4: Build, the Wave 3 design's last two answers (nothing locked)
**Asked:** the two items left open at 13:38: `UPDATE_INPUT_BUDGET` (1.2M or 2M), and the restated development allowance.
**Came back:** the user's answers, written into `docs/design/wave3-design.md` §8:
- `UPDATE_INPUT_BUDGET` **2,000,000**. With 5 runs at once the catastrophic overrun is about $54, against the Console's $60 monthly limit.
- **Development spend:** Wave 3's paid tests start a fresh tally at $0 in a new ledger (`data/verification/wave3/spend.jsonl`), with an allowance of $3.00 of Anthropic and 20 Exa searches. Each paid test still runs only on the user's go. The Phase 4 ledger closes at $1.6729 and 8 Exa searches. Production never counts development spend: it has its own Atlas database and its own Console workspace and key (T3.4).
- The design has no open question left. On the user's approval, P4.18 to P4.21 are locked, with the development allowance as P4.22.
**Spend:** none.
**DECISION (user):** *"UPDATE_INPUT_BUDGET 2M. Development allowance as you restated it: a fresh tally at $0, $3 Anthropic and 20 Exa searches."* Not yet a lock: the design waits for the user's approval.

## Oct 25, 2026, 13:47 CDT — Phase 4: Build, the Wave 3 design and plan approved
**Asked:** approval of `docs/sessions/wave3-plan.md` and, with it, `docs/design/wave3-design.md` (every §8 question answered, 13:38 and 13:41 entries), locking P4.18 to P4.22.
**Came back:** approved. The five decisions follow, each in its own entry. The plan's steps 0 to 6 run after the user's compaction.
**Spend:** none.
**DECISION (user):** *"Looks good to me. Record then prep the ground for compaction."*

## Oct 25, 2026, 13:47 CDT — Phase 4: Build, looser limits (P4.18)
**Asked:** the user, after the re-runs: *"Increase loop input budget to 800k tokens. I want to loosen other almost-hit budgets the same. The goal here is to let all runs pass smoothly while having a sure back stop that will almost never be triggered unless something catastrophic has gone wrong. The daily budget and monthly budget stands though, however."*
**Came back:** design §3 P4.18 and §4:
- `LOOP_INPUT_BUDGET` 2,000,000 (input only, summed over every research call);
- `UPDATE_INPUT_BUDGET` 2,000,000;
- `LOOP_OUTPUT_BUDGET` 16,000;
- `COMPOSITION_MAX_TOKENS` 16,000;
- `UPDATE_SEARCHES_PER_RUN` 5;
- `UPDATE_MAX_ROUNDS` 8 and `UPDATE_OUTPUT_BUDGET` 6,000 (placeholders);
- `MAX_ROUNDS` 12, `KEEP_CAP` 40 and the deadlines unchanged;
- `RUN_INPUT_TOKENS`, `RUN_OUTPUT_TOKENS`, `COMPOSITION_RESERVE_INPUT` and `FIXED_PREFIX_TOKENS_ESTIMATE` removed.
- The daily ($15) and monthly ($60) caps stand.
**Spend:** none.
**DECISION (user):** *"2M for the loop's input."*, *"Update searches loosen to 5"*, *"Agreeing with the other limits to loosen."*, *"UPDATE_INPUT_BUDGET 2M."*, approved with the design: *"Looks good to me."*

## Oct 25, 2026, 13:47 CDT — Phase 4: Build, the update check as its own step (P4.19)
**Asked:** the user: *"Untangling update from the research loop."*
**Came back:** design §2 and §3 P4.19:
- Research ends with `submit_answer(out_of_scope, note?)`. Rule 4, P4.7's waiver and the copy guard on the note go; research never sees a web page.
- The update step then runs beside the composition. It continues the research conversation for its cache: one tool list of seven and one system prompt, with each step's tools refused in the other.
- It decides whether to search, with up to 5 searches, and ends with `submit_update`. Its rules are `same_turn`, `no_check`, the findings checks and the copy guard.
- Our code turns it off when research never searched the corpus (out of scope), or when Exa is unavailable.
- The band loses `declined`. The events gain the `step` field and `update_started` / `update_ended` (contract v2.0).
**Spend:** none.
**DECISION (user):** *"Good call, and we will let this step decide whether to call Exa or not. Specifically, we can enforce by code such as if a response from the research loop doesn't search the corpus at all, we will turn off update by code automatically (because it's an out of scope response)."* and *"Update step's input should take advantage of the cached research conversation at maximum. We're just separating them so that we have finer control."*, approved with the design.

## Oct 25, 2026, 13:47 CDT — Phase 4: Build, composition on Sonnet 5.5 at high effort (P4.20)
**Asked:** the user: *"change everything to Sonnet high, sacrifice in quality but save cost immensely."*
**Came back:** design §3 P4.20. `COMPOSITION_MODEL` is `claude-sonnet-5-5` at high effort. It stays uncached, with only the kept passages as sources; the approved composition prompt is unchanged. The main session's estimate of the saving is about a fifth of an answered run's cost.
**Spend:** none.
**DECISION (user):** *"Change composition to Sonnet at high effort and I'd judge the quality first. (No comparison run needed.) After all, this project is a tech demo of the citation feature, not a demo of how much smarter and more capable is Opus than Sonnet in constitutional laws."* and *"Keep composition uncached and passing it only kept passages."*, approved with the design.

## Oct 25, 2026, 13:47 CDT — Phase 4: Build, no reservation (P4.21)
**Asked:** the user: *"I'd get rid of the reserve system. I'm willing to trade more cost overrun here because the cost is small and the budget still disable further runs once it's hit or overran."*
**Came back:** design §3 P4.21:
- **Admission:** a run starts only while today's and the month's spend are under the caps, the spend-limit flag is clear, and fewer than `MAX_CONCURRENT_RUNS` (5) runs are in progress. Otherwise it is refused (`daily_cap`, `monthly_cap`, `spend_limit_paused`, `atlas_unreachable`, or the new `busy`).
- **Spend:** each paid call's cost is recorded as it happens. Runs in progress always finish. It fails closed when Atlas can't be reached.
- **The overrun bound:** typically under $2. The catastrophic case is about $54 for 5 runs at the 2M budgets, behind the Console's $60 monthly limit.
- **What goes:** reservations (`reserve`, `settle`, `release`, expiry, `--open-reservations`), and the worst case as a gate.
- **The refusal texts** are the main session's, per the user (design §5).
**Spend:** none.
**DECISION (user):** the quote above; *"I also want to up maximum parallel runs to 5."*; *"Wording when too many runs are in progress: you can write the polished version."*, approved with the design.

## Oct 25, 2026, 13:47 CDT — Phase 4: Build, Wave 3's development allowance (P4.22)
**Asked:** the user: *"Reset the limit to 0 for our development. Additionally, Development cost should not count once we deploy production."* This read two ways, so the main session restated it (design §8).
**Came back:**
- Wave 3's paid tests start a fresh tally at $0 in `data/verification/wave3/spend.jsonl`, with **$3.00 of Anthropic and 20 Exa searches**. Each paid test runs only on the user's go.
- The Phase 4 ledger closes at $1.6729 and 8 Exa searches.
- Production never counts development spend: it has its own Atlas database (`Probable_Clause`, `PC_ENV=live`) and its own Console workspace and key with the $60 monthly limit (T3.4). The two must not share a key.
**Spend:** none.
**DECISION (user):** *"Development allowance as you restated it: a fresh tally at $0, $3 Anthropic and 20 Exa searches."*, approved with the design.

## Oct 25, 2026, 14:17 CDT — Phase 4: Build, Wave 3 step 0 (contract v2.0, shared code, prompt drafts)
**Asked:** the user, after the compaction: *"Proceed with Wave 3."* (`docs/sessions/wave3-plan.md`, step 0 items 2 to 7).
**Came back:**
- **Contract v2.0** (`docs/design/contract.md`) and `contracts/events.schema.json`. The envelope is `v: 2`, with `step`, `update_started` and `update_ended`; the band loses `declined`; `submit_update` and `wrong_step`; `cost_usd.update`; `503 busy`.
- **The shared code:** `api/settings.py` holds P4.18's figures, `UPDATE_*` and `MAX_CONCURRENT_RUNS`; the removed settings are gone; `ATLAS_RESERVE_TRIES` is now `ATLAS_ADMIT_TRIES`. `api/types.py` gains `Purpose` `update`, `Step` and `STEP_OF_PURPOSE`. `api/protocols.py` replaces `reserve`/`settle`/`release`/`open_reservations` with `admit` and `record_spend`, adds `Admission`, and gains four update stop kinds.
- **Prompt drafts** for the user's review before the first paid run (T1.14):
  - `loop_system.md` is shared by both steps, with a new "After research: the update step" section;
  - `tools.json` has seven tools, `submit_update` among them;
  - `loop_messages.json` adds `update_start`, `update_start_note`, `status_line_update` and `submit_update_accepted`;
  - `rejections.json` adds `submit_update` (`no_check` new) and `wrong_step`.
- **Two calls of the main session's, for the user to check:**
  - `WORST_CASE_COMPOSITION_INPUT` (66,000) feeds only the documented worst case and is never a gate;
  - a fourth update stop kind, `update_time_limit`.
- **The Opus 5.5 xhigh contract review** found 15 items, all applied before any builder started:
  - **Honesty:** a refused call in the update step (a wrong-step `submit_answer` note, a malformed `submit_update`) could store a page's words. Every refused call's stored input there now goes through the copy guard once a page was returned. This carries §1, T2.2 and P4.3 to v2.0; no decision changes.
  - **Prompts:** `update_start_note` for a nothing-found reply.
  - **Cancellation:** await the cancelled branch; record an attempt in flight; nothing after `run_ended`.
  - **Admission:** the busy slot is freed in a `finally`.
  - **The band:** its order of precedence.
  - **`stop_kinds`:** each kind once.
  - **The worst case corrected to $11.161 a run (about $55.81 for 5),** counting the composition's output on all three attempts (P4.10). It was $10.841 and about $54 in the design.
  - **Wording:** the deploy script's use of `spend_report.py`; counting by step in H; the cache-prefix test byte for byte; the wrong-step result fields; streams with no `update_ended`.
- **The frontend brief** gains §5a: what v2.0 changes, and what waits for the new fixtures.
- **The whole suite is expected to fail** from this commit until the wave's parts land (contract §13).
**Spend:** none.
**DECISION (user):** none needed. The design and plan were approved at 13:47; the prompt drafts await the user's review before step 6.

## Oct 25, 2026, 16:10 CDT — Phase 4: Build, Wave 3 built and reviewed (steps 1 to 5)
**Asked:** the user: *"Proceed with Wave 3."* (`docs/sessions/wave3-plan.md`).
**Came back:**
- **The parts, each built by an agent and then reviewed by a fresh one** (models and efforts per P4.1):
  - **E** (built Sonnet 5.5 high, reviewed Sonnet 5.5 high) — 46eb3e9, 5b080db. The reservation is gone; `admit` checks the caps strictly under, with `runs_started` counted in the same update; `record_spend` makes one `$inc` per paid call; `live_status` works from spend; the documented worst case is $11.161. **Atlas caught a real defect:** Atlas refuses `$expr` in an upsert's filter (code 224), which the fake had allowed, so every admission would have failed closed. Fixed (the conditional update is never an upsert), and the fake now refuses it too. `test_store_atlas.py` passes 45 of 45 against `Probable_Clause_test`.
  - **H** (built Sonnet 5.5 high, reviewed Sonnet 5.5 high) — 3a6b16e. `busy` at `MAX_CONCURRENT_RUNS`, with the slot taken before Atlas is awaited and freed in a `finally`. Spend is recorded per call, with `paid_call` emitted before the Atlas write. Envelope `v: 2`, `step` on `paid_call`, counting by step. **New setting (the main session's):** `RUN_WATCHDOG_S`, so a hung run can't hold a slot for good.
  - **G** (built Opus 5.5 xhigh, reviewed Opus 5.5 high) — ac2c86d. Research and the update step share one conversation machinery and one request builder; a test checks the update step's prefix byte for byte. The update step continues research's messages. Wrong-step refusals run both ways. `submit_update` runs its rules in contract order. The composition is on Sonnet. Both branches run as tasks, with a cancelled branch awaited and the original exception re-raised, and an in-flight attempt recorded. **The review found two honesty gaps:** an extra key inside an accepted finding, and dict keys in a refused call, both of which could carry a page's words into events. Fixed. **Contract §4.G.2 now guards every stored update-step call** once a page has come back, accepted ones and the band's search params included. That carries §1 and T2.2 to v2.0, with no decision changed.
  - **I** (the main session) — 83b1ab1. The deploy gate reads the live month; there are no reservations left to check.
- **Step 4, the main session's files** — 2fe685d, d3a0ce1:
  - `run_client.py` and `render_run.py` read `step` and the update step (still reading v1 recordings); new runs go to `data/verification/wave3/`;
  - fixtures regenerated through the real backend: 39 streams and 20 HTTP answers, byte-identical on every run;
  - the contract tests rewritten for v2.0;
  - `test_composition_worst_case.py` recast against `WORST_CASE_COMPOSITION_INPUT`.
- **Step 5, the Opus 5.5 xhigh review across the parts** — fe9f3c7. It found no defect in the money path, the honesty rules or the cache. Applied:
  - D records an Exa search cancelled in flight;
  - Exa's own message is guarded;
  - `model_context_window_exceeded` is treated as `max_tokens` in both steps;
  - `RUN_WATCHDOG_S` raised to 2,400 s (about 1,695 s is the longest legitimate run), with `run_client.py`'s timeout above it;
  - three fixtures for the update lane's endings (a cancelled branch, abandonment, the update time limit);
  - the frontend brief corrected: withheld text can appear anywhere in the update step; a `tool_call` may never get its result; `paused` is run-wide.
- **Accepted, not changed (the main session's call, for the user to check):**
  - H's `failed` ending drops research's stop kinds, so a research limit followed by an unexpected exception isn't recorded in `budget_stops`;
  - spend writes sit on each branch's path (up to `ATLAS_OP_TIMEOUT_S` each against a slow Atlas);
  - `UPDATE_OUTPUT_BUDGET` 6,000 may bind a long submit. Watch it in the paid tests.
- **Checks:**
  - the whole suite: **2,943 passed, 54 skipped**;
  - the API image built (427 MB), and its corpus, indexes, exemption and loop load with `--network none`;
  - `spend_report.py --month 2026-10 --env test` reached `Probable_Clause_test` (the 13:04 failure did not recur): $1.7435 spent, 8 runs started, no stops.
- **Nothing pushed.** The frontend session can now build the step log, the band's timing, the removal of `declined`, and `busy` against the v2.0 fixtures.
**Spend:** none (fakes only; Atlas test database reads and writes are free).
**DECISION (user):** none taken. Waiting on the user: the review of the prompt drafts (T1.14), then the go for step 6's paid tests (P4.22).

## Oct 25, 2026, 16:15 CDT — Phase 4: Build, Wave 3's prompt drafts approved (P4.23)
**Asked:** the user's review of the v2.0 prompt drafts before the first paid run (T1.14).
**Came back:** the drafts committed in 5642d5f and fe9f3c7:
- `api/prompts/loop_system.md`: one system prompt for both steps, with research's items without the update check and the new "After research: the update step" section;
- `tools.json`: seven tools, `submit_answer` without the update fields, and `search_web_updates` and `submit_update` marked as the update step's;
- `loop_messages.json`: `status_line` without the update count, `status_line_update`, `update_start`, `update_start_note` and `submit_update_accepted`;
- `rejections.json`: `submit_update` (its rule 1, the moved findings and copy-guard texts, `no_check`) and `wrong_step`;
- the `busy` and cap refusal texts of contract §5.
**Spend:** none.
**DECISION (user):** *"The prompt drafts are approved. Run the four Wave 3 paid tests under P4.22's allowance."*

## Oct 25, 2026, 16:20 CDT — Phase 4: Build, Wave 3's paid tests (w3-t1 to w3-t4)
**Asked:** the user: *"The prompt drafts are approved. Run the four Wave 3 paid tests under P4.22's allowance."*
**Came back:** the four questions of `docs/design/paid-build-tests.md`, run through the local API (`PC_ENV` unset, `Probable_Clause_test`) with `scripts/run_client.py` on the v2.0 code (51cc3f4). Anthropic's pricing page was re-read first, and its Sonnet 5.5 row matches the price table. Events, summaries and rendered answers are under `data/verification/wave3/` (local, kept).
- **w3-t1, the thermal imager:**
  - `answered`, 3 research rounds, 49 blocks, 24 citations; quotations 10 of 10 found and citations 4 of 4.
  - The update step skipped the web search: *"The question is governed by a 2001 decision (Kyllo) already in the corpus."* Band `skipped`.
  - **$0.1841** (the morning's re-run: $0.3355), 39 s.
- **w3-t2, "hello":**
  - `no_sources` / `out_of_scope` in one call that read the 1-hour prefix; no update step, band `not_run`.
  - **$0.0048**. The note has a grammar slip: "Does police need a warrant".
- **w3-t3, a 2027 onboard-computer case:**
  - `no_sources` / `nothing_found` in 2 research rounds; no composition.
  - The update step still ran: 2 searches, 5 findings, an overview, band `found`.
  - **$0.1307**, 22 s. The morning's re-run answered this question from kept passages; this run kept none.
- **w3-t4, phone location without a warrant:**
  - `answered`, 6 research rounds, 61 blocks, 30 citations; quotations 10 of 10, citations 4 of 4.
  - One update search, and empty findings with an overview: band `nothing_relevant`.
  - **$0.2452** (the morning's re-run: $0.4104), 51 s.
  - Research's input was 234,236, against the morning's 366,680 with web pages in research.
- **The cache works as designed (P4.19):** each update step's first call read research's whole conversation from cache, since its cache read equals research's last read plus write:
  - t1: 33,653 = 30,449 + 3,204;
  - t3: 25,730;
  - t4: 48,846.
- **No limit came near:**
  - research input at most 234,236 of 2,000,000;
  - update input at most 120,526 of 2,000,000;
  - update output at most 1,040 of 6,000;
  - composition output at most 3,435 of 16,000.
- **No faults:** no mapping faults, tracebacks or error lines in `server.log`; no refused submits; every submit was sent alone.
- **Atlas agrees to the cent:** `Probable_Clause_test` went from $1.7435 to $2.3084, the four runs' paid calls summed ($0.5649 with Exa and Voyage), and runs started from 8 to 12. Per-call spend recording (P4.21) works on the real database.
- **For the user to judge:**
  - the composition's quality on Sonnet (P4.20), from `data/verification/wave3/answers/`;
  - t1's skip of the update search;
  - t2's grammar slip.
**Spend:** Wave 3's tally (P4.22, `data/verification/wave3/spend.jsonl`, 23 lines): **Anthropic $0.5383 of $3.00, Exa 3 of 20 searches** ($0.021). Voyage $0.0057 at list price.
**DECISION (user):** pending: the composition's quality on Sonnet.

## Oct 25, 2026, 16:23 CDT — Phase 4: Build, composition on Sonnet confirmed after the paid tests (P4.20)
**Asked:** P4.20 left the composition's quality on Sonnet for the user to judge from the next paid runs.
**Came back:** the user read Wave 3's four rendered answers (`data/verification/wave3/answers/`).
**Spend:** none.
**DECISION (user):** *"I checked the answers, and quality is surprisingly good. Looks like we don't need Opus level reasoning when we already hand Sonnet all the necessary primary sources."* P4.20 stands as built.

## Oct 25, 2026, 16:38 CDT — Phase 4: Build, the live Anthropic workspace and its key (P4.24)
**Asked:** the main session's list before any deploy, item 1: a Console workspace and key for the live site with a $60 monthly limit (T3.4).
**Came back:**
- The user has set up the workspace, with a $60 monthly limit and alerts at several break points.
- The live key goes into `.env` under its own name (the name is settled below, as a follow-up). A deployment script then creates the GCP secret from `.env` programmatically, without the key ever being read or printed by the session.
**Spend:** none.
**DECISION (user):** *"A separate Anthropic workspace for the live site with $60 monthly limit and alerts at multiple break points has been set up. I can put the new API key to .env, then you can have a deployment script programmatically create the secret in GCP without reading the key."*

## Oct 25, 2026, 16:38 CDT — Phase 4: Build, the cloud setup's credentials (P4.25)
**Asked:** item 2: how the registry, service accounts and secrets are set up (T3.5, part I's open questions), and whether production gets its own Voyage, Exa and Atlas credentials.
**Came back:**
- The GCP project is `probable-clause`, already reserved by the user (T3.5).
- **Anthropic:** a separate live key (P4.24).
- **Voyage and Exa:** the same keys as development.
- **Atlas:** the same URI, with production writing to the separate `Probable_Clause` database (`PC_ENV=live`, T3.5). No new database user.
**Spend:** none.
**DECISION (user):** *"For cloud set up, I already reserved us a project probable-clause. Anthropic API key is separtae per item 1. Voyage and Exa reuse the same key is fine since the spend is so low. For Atlas, use a separate Probable_Clause database for production, same URI."*

## Oct 25, 2026, 16:38 CDT — Phase 4: Build, green light to modify goodnight (P4.26)
**Asked:** item 3: the goodnight block (T3.5), written in goodnight's repository, shown to the user first.
**Came back:** the user's green light to modify goodnight to incorporate this site. What exactly it covers, and when the block goes live, is restated below as a follow-up.
**Spend:** none.
**DECISION (user):** *"Green light to modify goodnight to incorporate this site."*

## Oct 25, 2026, 16:38 CDT — Phase 4: Build, Exa's terms: the risk accepted without a reply (P4.27)
**Asked:** item 4: Exa's reply to the request for written permission (P1.3).
**Came back:**
- Exa has not replied.
- The project proceeds without the reply. The update band shows only Claude's synthesis and links (P1.3), and the copy guard catches most cases (T2.3, P4.19).
**Spend:** none.
**DECISION (user):** *"Exa didn't respond to us yet. The risk is small because it's their literal service plus we already had guards to catch most cases."*

## Oct 25, 2026, 16:38 CDT — Phase 4: Build, the main session builds and stands up the frontend (P4.28)
**Asked:** the user's plan: the main session preps the ground, compacts, then builds the real frontend in this session.
**Came back:**
- The main session takes over `web/` and `webdev/`, and builds the real page itself, with no parallel builders. Fresh subagents only review: the honesty-critical paths and the narrow widths.
- `docs/sessions/frontend-log.md` stays as the historical record. The old frontend session is retired (the user archives it), so there is never a second writer on `web/`.
- **What this amends:**
  - P0.3 and P1.6: the second session existed to develop the prototype in parallel;
  - P4.1 item 5: "the frontend is built by the frontend session".
**Spend:** none.
**DECISION (user):** *"About the frontend, yes, we're changing locked arrangements. The previous arrangements are only meant to develop the frontend prototype in parallel, the merge and final stand up are always meant to be in the main thread. I agree with you building the frontend yourself without parallel builders."*

## Oct 25, 2026, 16:38 CDT — Phase 4: Build, the local review clarified (P4.1)
**Asked:** items 5 and 6: the user's sign-off on the local review, then a separate deploy green light.
**Came back:**
- The local review is the main session standing the whole app up locally, for the user to test it as a user.
- The user's sign-off follows that testing.
- There is no deploy green light until then. P4.1 is unchanged.
**Spend:** none.
**DECISION (user):** *"I want you to stand up the app locally for me to test it as an user."* and *"No deployment green light yet till I have tested the app locally."*

## Oct 25, 2026, 16:43 CDT — Phase 4: Build, the live key's name (P4.29)
**Asked:** what the live Anthropic key (P4.24) is named in `.env`.
**Came back:**
- The name is `ANTHROPIC_API_KEY_LIVE`, distinct from the development `ANTHROPIC_API_KEY`, so local runs can never use the live key.
- It is added to `.env.example` for the user to fill, and to `scripts/check_env.py` (needed from phase 5, the deploy; it reports only set, empty or missing).
**Spend:** none.
**DECISION (user):** *"Live key name ANTHROPIC_API_KEY_LIVE. Edit .env.example so I can put it in."*

## Oct 25, 2026, 16:43 CDT — Phase 4: Build, the cloud setup script deferred (P4.30)
**Asked:** when the script that creates the registry, the service accounts, the secrets and their access rule is written and run (P4.25).
**Came back:**
- The user green-lights writing it, but deferred: after the frontend, right before deployment.
- Running it creates cloud resources, so it still runs only with the deploy green light (CLAUDE.md).
**Spend:** none.
**DECISION (user):** *"Green light on writing the set up script. Defer this till after the frontend and right before deployment though, no rush."*

## Oct 25, 2026, 16:43 CDT — Phase 4: Build, goodnight's location (P4.26)
**Asked:** where goodnight's repository is, for P4.26's change.
**Came back:**
- It lives in `~/Documents/Developer/framedbytran` (present on this machine).
- **The main session's restated reading of P4.26, which the user did not correct:** the block is written and committed in that repository and shown to the user. It goes live only with the deploy green light, once the services' addresses exist. That repository is never pushed without the user's word.
**Spend:** none.
**DECISION (user):** *"Developer/framedbytran"*

## Oct 25, 2026, 16:43 CDT — Phase 4: Build, the frontend's design questions left to the main session (P4.31)
**Asked:** the questions the v2.0 page raises:
- how the update step shows beside the answer;
- the wording for the new "update check unavailable" reasons;
- where `busy` appears;
- whether the cost line shows the update step separately.
**Came back:** the main session decides each during the frontend build, records each call in the log, and the user refines afterwards.
**Spend:** none.
**DECISION (user):** *"You can proceed with your judgement for these during the frontend stand up, and I will refine afterward if needed."*

## Oct 25, 2026, 16:46 CDT — Phase 4: Build, the replays: T5.6's five, recorded after the local review (P4.32)
**Asked:** whether Wave 3's paid runs become the production replays, and whether to commit `data/verification/`.
**Came back:**
- The replays stay T5.6's five questions, recorded after the user's local review on the final code, under T5.6's recording rules (the user reviews each before it is published).
- Replays reach the site as `replays/<slug>.json` (contract §11.2), exported and committed.
- `data/verification/` stays uncommitted. Its run files are kept on this machine, as the keep-every-run rule says.
**Spend:** none now. T5.6's estimate for the recordings was $2 to $3, approved when they run.
**DECISION (user):** *"Keep T5.6's five replay questions, recorded after the local review on the final code. Don't commit data/verification."*

## Oct 25, 2026, 16:49 CDT — Phase 4: Build, the frontend build plan approved (P4.33)
**Asked:** the user's approval of `docs/sessions/frontend-plan.md` (proposed 16:48, 7b8e67b), before a planned compaction.
**Came back:** the plan as written. The steps:
- **Step 0:** the main session's calls under P4.31, logged at the start: the step log's two groups after research, the band's new unavailable lines, `busy` as the run's last step, the cost line's split, Sonnet in the credits, withheld text shown as it is, and the new `config.json` figures.
- **Step 1:** the two downloads, on the user's OK; the skeleton; the mock server in `webdev/`.
- **Steps 2 to 7:** the run model from the events first, Node-tested over every fixture; then the screens, sources and answer, the band, checks and costs, the two modals, and every other state.
- **Step 8:** an Opus 5.5 xhigh review of the honesty paths, and a Sonnet 5.5 high review of the states, layout and accessibility.
- **Step 9:** `deploy/local.sh`, and the user testing as a visitor; then the sign-off.

The deploy green light stays separate.
**Spend:** none.
**DECISION (user):** *"The frontend plan looks good. Approved."*

## Oct 25, 2026, 16:52 CDT — Phase 4: Build, the frontend's step 0: the main session's calls under P4.31, and `config.json`'s new figures
**Asked:** the user's go after the compaction: *"Proceed with standing up the frontend as planned."* Step 0 of `docs/sessions/frontend-plan.md` (P4.33).
**Came back:** the main session's calls, each the user's to refine afterwards (P4.31):
- **The update step in the step log:** research's steps first; once research ends, two groups stacked in the one column, "Writing the answer" (the composition) and "Update check, running beside the answer" (the update step's rounds, searches and submit). Events go to their group by `step`, whatever order they arrive in; each group has its own spinner and closes on its own end, or on `run_ended` (a cancelled or interrupted branch, an unanswered `tool_call` included). The band stays where T4.3 puts it and fills in when `update_band` arrives.
- **The band's unavailable lines beside T5.3's two** (`no_credit`, `key_refused`), by `reason`:
  - `update_step_limit`: *"Update check unavailable: it stopped at its step limit before summarising."*
  - `update_time_limit`: *"Update check unavailable: the run reached its time limit first."*
  - `update_token_ceiling_input`, `update_token_ceiling_output`: *"Update check unavailable: it reached its token limit."*
  - `console_spend_limit`, `tier_spend_cap`, `spend_limit`, `spend_cap`: *"Update check unavailable: this site's monthly API spending limit was reached."*
  - any other error kind: *"Update check unavailable: the check failed (<reason>)."*, the reason in T5.4's plain words where it has them (overloaded, rate limited, server error, connection lost), and the bare unavailable line for a code with no words (brief §5a).
- **`busy`:** the run's last step, where T4.4 puts a `POST /runs` refusal, in contract §5's words, the number written out from `MAX_CONCURRENT_RUNS`.
- **The cost line:** T5.2's total line unchanged; expanded, it splits into research, the update check, the answer and Exa (`totals.claude.cost_usd`'s `loop`, `update`, `composition`; `exa.cost_usd`).
- **The credits:** T5.1's line names Sonnet 5.5 for the answers too, following T1.8 as P4.20 amends it: *"research and answers on Claude Sonnet 5.5"*.
- **Withheld text** (contract §4.G.2) is shown as it arrives, in the step log's muted style, never styled as an error.
- **`config.json` gains seven figures** the wording names, so none is typed into the page: `UPDATE_SEARCHES_PER_RUN`, `EXA_NUM_RESULTS_DEFAULT`, `EXA_TEXT_CHARS`, `MAX_CONCURRENT_RUNS`, `RUN_DEADLINE_S` (the plan's five), and `ABANDON_AFTER_S` ("over a minute") and `EVENTS_TTL_S` ("24 hours"), which T5.4's lines also name. `api/corpus/web_data.py`'s `CONFIG_NAMES` and its test edited by the main session; contract **v2.1** says so in §11.3. Retry lines need no figure: `paid_call` carries `attempt` and `max_attempts`.

Checks: `tests/corpus/test_web_data.py` and `tests/deploy/` pass (48 passed, 2 skipped); `web/_generated/` regenerated.
**Spend:** none.
**DECISION (user):** *"Proceed with standing up the frontend as planned."* The calls above are the main session's (P4.31), not the user's.

## Oct 25, 2026, 17:50 CDT — Phase 4: Build, the frontend built, reviewed and stood up locally (frontend plan steps 1 to 9)
**Asked:** *"Proceed with standing up the frontend as planned."* (`docs/sessions/frontend-plan.md`, P4.33.)
**Came back:**
- **Step 1, the downloads, on the user's OK** (*"Yes, both"*), each checked before use:
  - the fonts: 10 `.woff2` files (Instrument Sans v4, Newsreader v26, JetBrains Mono v24; Latin and Latin Extended; 588,376 bytes) from fonts.gstatic.com, since google/fonts ships only `.ttf`; the three OFL texts from google/fonts;
  - markdown-it 15.0.3's `dist/browser/markdown-it.esm.min.mjs` and licence, from the npm tarball, its sha512 matching the registry.
- **The page, `web/`** (a9f1f0a, 7a91257, 7fa7c07, d9f4f2e): `index.html`, `css/`, and 16 modules (`text`, `model`, `answer`, `cp`, `dom`, `config`, `wake`, `stream`, `steps`, `sources`, `band`, `costs`, `apicalls`, `reader`, `replay`, `view`, `main`). The prototype's look, against contract v2.1. Every string is a text node; nothing is inserted as markup.
- **The mock, `webdev/serve.py`** (standard library, port 8765): the page, the generated files, replays, and contract §5's endpoints played from the fixtures, with dev-only switches for each failure answer, a cold start, speed and a dropped connection.
- **Checks:**
  - Node tests, `node --test webdev/test/`: **65 pass**. They cover the run model over all 39 fixtures, placement by step, the answer renderer (citations, flags across blocks, code points, the straddle fallback), the wake protocol and the stream client.
  - Every fixture plays live through the mock with no console error and nothing left spinning.
  - No horizontal scroll at 1440×900, 393×852 and 852×393, in light and dark, measured by element rectangles.
  - The page contacts only its own origin.
  - The whole Python suite: **2,943 passed, 54 skipped**.
- **Step 8, two read-only reviews:**
  - **Opus 5.5 xhigh (the honesty paths)** found and the main session fixed:
    - a Markdown table crashed the answer;
    - an error while drawing an event became an endless reconnect loop;
    - an HTML entity could decode to the renderer's private sentinels and fake, cut or hide a check flag;
    - the status and step log claimed an answer while none was being written;
    - the band said Claude searched the web when a search met an out-of-credit or refused key;
    - multi-paragraph footnotes were never lit in the reader, and page numbers at a sentence's start were lost;
    - a Voyage outage was titled as the site's refusal;
    - a partial answer in a failed run read "Finished".

    Tables, code blocks and entities now stay plain text.
  - **Sonnet 5.5 high (states, layout, accessibility)** found and the main session fixed:
    - a replay chip racing a live run;
    - steps redrawn on every event, dropping keyboard focus and re-announcing the log;
    - a long unbroken question widening the page;
    - a failed composition still showing the answer's heading;
    - the reload path's "Try again" with no button;
    - no timeout before headers;
    - focus lost on a phone when a citation opens the sources pane;
    - Escape does not unpin a citation;
    - smooth scrolling under reduced motion;
    - flags with no accessible name;
    - the drag-to-backdrop close;
    - the AI disclosure hidden on a sideways phone;
    - transition rejections.
- **Step 9:** `deploy/local.sh` was run by the main session (its header updated to P4.1's 16:38 clarification). Both images built and run:
  - the API, `PC_ENV=test`, development keys, `Probable_Clause_test`, ready in 1.9 s;
  - the page at http://localhost:8080.

  The recorded-run chips play two of Wave 3's real paid runs from today (w3-t1 thermal imager, w3-t4 phone tracking), written to a local `replays/` that `.git/info/exclude` keeps out of git. The real replays are recorded after the review (P4.32). No question has been asked of the local API.
- **The main session's calls, for the user to refine (P4.31), beyond step 0's (16:52):**
  - **Step titles:** "Searching by meaning", "Searching for exact words", "Reading in the opinion", "Keeping passages", "Finishing research", "Summarising the update check", "Asking Claude for the next step" (shown only while a call is waiting or when it retried), "Refused: not this step's tool", "Refused by this site's checks", "Checked the answer".
  - **The groups' intro lines:** "Research finished with N passages kept. The answer and the update check start side by side." and, with nothing kept, "… so no answer is written. The update check runs next."
  - **Status lines:**
    - "Research · <the status line Claude sees>", "Writing the answer · the update check runs beside it", "Update check";
    - "Finished: … and Claude's reply" for a no-sources reply;
    - "Stopped after N s." for a run that ended without its answer.
  - **The answer's own lines:**
    - "Incomplete: the run ended before the answer was finished, and the checks did not run on it." for a failed or interrupted run with a partial answer;
    - "The answer could not be written" and "Wrote part of the answer before an error" as the composition step's titles;
    - "No full case names or U.S. Reports citations to check.";
    - each flag note starts with the flagged words in quotation marks, then T5.2's line.
  - **Failure words:** "timed out", "an error on this site" and "an unreadable reply" for kinds T5.4's four don't name, in retry lines and failure lines. The band's unavailable line uses T5.4's four only.
  - **The band:** it is not shown when no search ran (T2.3 #5). Its honesty label shows only above a search that ran. Its fixed line reads the run's own recorded figures.
  - **The wake lines without recorded runs:** T5.4 #1's two lines without their pointer to recorded runs.
  - **The credits:** "Built with the Claude API (research and answers on Claude Sonnet 5.5) …" (step 0).
  - **The trace figure:** a real citation from w3-t1 (*Kyllo*).
- **Questions for the user, left as the decisions have them:**
  - **Light-mode contrast** (T4.1's palette): the passage-ID pills are about 3.6 to 4.25 to 1 on their tints, and "Not kept" cards' muted text is about 2.9 to 1. Darkening the source hues or dropping the cards' opacity would change the locked look.
  - **The skipped band line:** T5.3 #4 gives both "Update check skipped: <reason>" and "Claude's reason: <reason>"; the page shows only the first, so the reason is not repeated.
  - **The cost line** counts our estimates for attempts that reported no usage (T3.3) in the total. The API window labels them as ours; T5.2's line says "from each response's token counts".
**Failures:**
- Write turned `\u` escapes into literal characters; the private-use ones were rewritten as escapes.
- A card state named `cited` collided with the answer's `.cited` class; renamed.
- A CRLF split across stream chunks ended a frame early; a Node test caught it.
- A boot-order error (a `let` used before its line) blanked the page once during the fixes; caught by the browser sweep.
**Spend:** none. The local stack has made no paid call.
**DECISION (user):** *"Yes, both"* (the two downloads, asked in this sitting). No other decision; the calls above are the main session's.

## Oct 25, 2026, 18:22 CDT — Frontend: the user's review, round 1 (the empty band, the thinking line, tool calls paced)
**Asked:**
- First, whether the page was built from the wrong prototype.
- Then the user withdrew that (*"My bad it was the right prototype, but this bug came back to life"*) and pointed to a screenshot: at the start of a run, the run view ended partway down the window with an empty band below it.
- Then two polish items:
  - "Asking Claude for the next step" becomes "Claude is thinking";
  - tool calls that arrive together appear at least 0.5 s apart, in live runs and replays.
**Came back:**
- **The prototype:** the page is built from `web/looktests/machinery/` at badc05f. Every edit to it, in git and in every session's transcript, falls between 17:56 and 20:17 CDT on Oct 23, so there is no later version.
- **The empty band (7ef82b9):**
  - The prototype's `body` grid had two rows: the switcher banner, then the run view.
  - The banner was dropped but the rows were kept, so `#run` fell into the content-sized row (measured 524 of 900 px) and an empty 376 px row took the rest.
  - The fix from Oct 23 (frontend-log 19:50) pinned the rows inside `#run` and still holds; this was the grid one level up.
  - Now one full-height row. Measured at 1440×900, 393×852 and 852×393: the panes and the composer reach the bottom, with no sideways scroll, and a finished run scrolls inside its pane.
- **The thinking line:**
  - "Claude is thinking", in the user's words.
  - Its past form, shown only when the call retried or failed, is "Claude was thinking" (the main session's call).
- **The pace:** `web/js/pace.js`, between the event source and the view, for live runs and replays.
  - Events keep their order. A tool call is held until 500 ms after the previous one appeared, and anything behind it waits with it.
  - A quiet event (a reload catching up on stored events, or "Skip to the end") is never held, and first releases whatever waits.
  - A replay or run ends on screen only after its last held event is shown.
  - A give-up or an expiry shows the held events before reattaching, so the reattach starts from the last event on screen.
- **Checked:**
  - Node: 70 tests pass (5 new for the pace, including every fixture played at its recorded times: each event once, in order, no two tool calls closer than 0.5 s).
  - Browser, the real phone-tracking run: the three calls recorded at 11,837, 11,839 and 11,843 ms appeared at 11.86, 12.36 and 12.86 s, and every later call stayed at least 0.5 s apart. "Skip to the end" finished the run at once.
**Failures:** none.
**Spend:** none.
**DECISION (user):** *"'Asking Claude for the next step' -> Claude is thinking (more natural)"*; *"add an intentional delay just a bit so that every tool call appears after 0.5s the other at the minimum. This should be the case for both replay and live runs"*.

## Oct 25, 2026, 18:28 CDT — Frontend: the user's review, round 2 (the pace at 1 s; step 5 paced)
**Asked:** *"Step 5, finish research should also get that delay as well."* And: *"increase the delay to 1 second. The current 0.5s still feel too abrupt to me."*
**Came back:**
- **Why step 5 looked unpaced:** in the thermal-imager run, "Finishing research" (`submit_answer`) comes about 1 s after step 4, so the 0.5 s gap never held it. But the next stage arrives within 3 ms of it: `update_started`, the update check's first round and `composition_started`. So the two groups and "Writing the answer" landed with step 5.
- **Read both ways and done both (the main session's call):**
  - every tool call waits at least 1 s after the previous paced item, step 5 included;
  - the first event of the stage after research (`update_started`, `composition_started` or `update_band`, whichever comes first) also waits 1 s after step 5.
  - The rest of that stage arrives with its first event, so the two groups appear together.
- **`TOOL_CALL_GAP_MS` is 1,000** (the user's figure).
- **Checked:**
  - Node: 71 tests pass (a new one for the stage's wait; every fixture now checks 1 s between tool calls and the stage start).
  - Browser, the thermal-imager run: steps 3, 4 and 5 at 21.86, 22.86 and 23.86 s, the groups at 24.86 s, the update check's submit at 25.86 s.
**Failures:** none.
**Spend:** none.
**DECISION (user):** the two quotes above.

## Oct 25, 2026, 18:36 CDT — Frontend: the user's review, round 3 (the pace at 3 s; the status dot removed; testing during iteration)
**Asked:**
- *"1 second is still too abrupt. Increase it to 3 seconds (except for the very first step where we don't need any artificial delay) because each tool call still has a lot of content."*
- Remove the pulsing dot beside the status line ("Recorded run…"), which repeats the working step's own pulsing dot.
- A change of workflow for the iteration rounds (below).
**Came back:**
- **`TOOL_CALL_GAP_MS` is 3,000.** The first tool call of a run is never held (the pacer starts with no previous item), so only later calls and the stage after research wait.
- **The status line's dot is gone** (`.status.working::before` removed), in live runs and replays alike. The working step's dot and the group heads' dots stay.
- **The pace tests:** the unit tests keep an explicit 1 s gap; the fixture test checks the page's own figure.
- **Checked:** only what changed, per the user's new rule. `webdev/test/pace.test.mjs` passes (6 tests), and the rebuilt stack serves the new figure and stylesheet.
**Failures:** none.
**Spend:** none.
**DECISION (user):**
- The 3 s gap, quoted above.
- On testing: *"Since we're doing quick iterations, you don't need to run exhaustive test after each iteration. Instead, run tests for what matters only. Once we've finished iterating, we will run the full suite. This is so we can speed up during the iteration process."* Saved to the main session's memory. The full suite (Python and Node) and the browser sweep run once iterating ends, before the sign-off.

## Oct 25, 2026, 18:41 CDT — Frontend: the user's review, round 4 (only research paced; the replay notice at the top)
**Asked:**
- *"This delay should not apply to the composition call writing the answer or the update check, just for the research loop."*
- *"This line "Recorded run, Oct 25, 2026. A real run, replayed at its recorded pace. It makes no new calls.", I want it spawn up top at the start of the run while everything else spawns bottom and get pushed up."*
**Came back:**
- **The pace:** only research's tool calls (`step: "research"`) are held, 3 s apart, the first never.
  - "Finishing research" (`submit_answer`) is one of them, so it is still paced.
  - Round 2's wait for the stage after research is removed; it read the user's round-2 request the other way. The groups, the update check's calls and the answer arrive with step 5.
- **The replay notice:** `margin-bottom: auto` in the thread's column, so it sits at the top from the start while the rest stacks from the bottom. Once the run outgrows the pane, it scrolls away with the conversation.
- **Checked (only what changed):**
  - `webdev/test/pace.test.mjs` passes (6 tests; the stage test replaced by one where nothing after research is held).
  - In the browser at the start of a replay: the notice at 124 to 189 px of a pane running 92 to 943, the question at 800 to 882, the composer below.
**Failures:** none.
**Spend:** none.
**DECISION (user):** the two quotes above.

## Oct 25, 2026, 18:51 CDT — Frontend: the user's review, round 5 (autoscroll restored; the cost line kept in view)
**Asked:**
- The page stopped following the answer as it streams. It worked before the iteration rounds, and scrolling down by hand latched it again.
- At the run's end the cost line sat half hidden.
- Opening the cost line left its parts behind the composer.
**Came back:**
- **Cause of the lost autoscroll (a regression from rounds 1 to 4):**
  - Pinning was decided per event: follow only if the pane was within 260 px of its bottom before the event.
  - With research paced at 3 s, "Finishing research" is held, and everything behind it reaches the screen in one burst: the groups, the band and the first answer paragraphs. Measured: about 990 px in one tick.
  - A smooth scroll still under way left the pane "far" from a bottom that had just moved, so following stopped for the rest of the run.
- **The fix:** the pin is decided by the visitor's own scrolling, never by measuring at each event.
  - A pane starts pinned. A scroll within a second of the visitor's own wheel, touch, key or scrollbar grab sets it from where they left it (within 260 px of the bottom pins it).
  - Our own scrolls never change it.
  - The same holds for the sources pane.
- **The half-hidden cost line:** when a run ends, the dock grows (the line under the composer returns) and covered the conversation's last lines. A `ResizeObserver` on the conversation pane now keeps a pinned pane at its bottom when the pane resizes.
- **Opening the cost line:** its `toggle` scrolls the pane just far enough to show all of it.
- **Checked (only what changed), in the browser on the thermal-imager replay:**
  - the answer followed to its end, and the end left the cost line fully above the dock (891 to 911 px; the pane ends at 927);
  - opened, it moved up to 726 to 911;
  - scrolling up 800 px mid-answer stayed put (1,490 px from the bottom 3 s later); scrolling back down latched again.
**Failures:** the first try of the fold's reveal never ran. A function named `reveal` already existed in `view.js` (the passage reveal), and the later declaration replaced it; renamed `revealFold`.
**Spend:** none.
**DECISION (user):** none beyond the three requests (bug fixes).

## Oct 25, 2026, 19:42 CDT — Frontend: the user's review, round 6 (sources and credits, and privacy, as pages of their own)
**Asked (the user):** "I want they all to open in a new tab that is a new page such as nguyennhattran.com/probable-clause/sources-and-credits. That means building the 2 simple pages too (GitHub is already its own page.) I want the line Source code on GitHub to be at the sale line as Sources and credits and Privacy buttons."
**Came back:**
- **Two pages:** `web/sources-and-credits.html` and `web/privacy.html`, with `web/js/page.js` filling them from `text.js`, so the wording still lives in one place. The credits page reads `corpus.json` for its counts and dates; if that fails, it says so (`PAGE_FAILURE`, a new line). Each has the wordmark linking back to the start page.
- **The URLs:** `sources-and-credits` and `privacy`, beside the start page. nginx now tries `$uri.html` (both profiles, `tests/deploy/test_nginx.py` updated), and so does the mock. Under goodnight's prefix that is `/probable-clause/sources-and-credits`. With a trailing slash the address is a 404, not a page with broken paths.
- **The footer:** the folds are gone. One line of three links ("Sources and credits", "Privacy", "Source code on GitHub"), each opening in a new tab. "Independent project. Not affiliated with Anthropic." stays as its own line, above the links on the landing page and below them under the composer. On a phone the run's dock still hides both, as before.
- **The main session's calls (wording):**
  - "Source code on GitHub" loses its full stop, now that it is one of three links.
  - On the privacy page the note's bold lead "Privacy." is dropped, since the page's heading says it.
- **Checked (only what changed):**
  - In the browser on the mock: the three links on one line at 1,391 px, each with `target="_blank"`.
  - Both pages render with their text and links. On the privacy page, the four provider links open in a new tab.
  - Under the composer at 1440×900, the links sit on one line above the affiliation.
  - `tests/deploy`: 40 passed, 2 skipped. Node: 71 passed.
**Failures:** none.
**Spend:** none.
**DECISION (user):** the request quoted above.

## Oct 25, 2026, 19:51 CDT — Frontend: the user's review, round 7 (the run screen's dock cleaned up)
**Asked (the user):** the bottom of the run screen "looks like an absolute mess straight from a horror movie. Let's discuss this." The main session's diagnosis:
- The from-scratch line hung off the dock's left edge, outside the composer's column. Its `margin: … 0 0 !important` cancelled the auto side margins.
- 6 to 8 lines of fine print sat under the composer on every run, repeating the landing page.
- The strip mixed three alignments and three text sizes.
After the discussion: *"Let's give this a try: the dock keeps the status, the composer and the from-scratch line; the disclaimers go under each answer; the links go in the top bar."*
**Came back:**
- **The dock:** the status line, the composer and the from-scratch line, now centred under the composer in its column (0.8125rem, the status line's size; 0.75rem on a phone). `#dock-fine` and its `.disclaimer` styles are removed.
- **The disclaimers:** the not-legal-advice line and the AI disclosure, each its own paragraph (T4.1), now appear once per run.
  - They sit at the run's end, under the answer's checks line and above the cost line, so every ending gets them, a run with no answer included.
  - The landing page keeps them, so the AI disclosure is still seen before the first question.
- **The links:** "Sources and credits", "Privacy" and "Source code on GitHub" sit to the right of the run screen's top bar, muted and not underlined until hovered.
  - Hidden on a phone, where there is no room; the landing page has them.
  - Shown sideways.
- **The affiliation:** now on the landing page only.
- **Checked (only what changed), in the browser on the thermal-imager replay, skipped to the end:**
  - **1440×900:** the composer, the status and the from-scratch line share one column (94 to 914 px). The checks, the two disclaimers and the cost line run in that order (579 to 752). The links are on one line in the bar.
  - **393×852:** no horizontal scroll, and the bar's links are hidden. The dock is the status, the composer and the from-scratch line, which wraps to two centred lines.
  - **852×393:** the links fit in the bar (498 to 836 of 852), and the from-scratch line stays hidden, as before.
  - Node: 71 passed.
**Failures:** none.
**Spend:** none.
**DECISION (user):** the direction quoted above. Not a lock; the main session's calls are the order (disclaimers before the cost line), the sizes, and the bar's link style.

## Oct 25, 2026, 19:59 CDT — Frontend: the user's review, round 8; the checks are an add-on, shown only as flags (P4.34)
**Asked (the user):** "I think we can also remove this line "Checked by this site's code..." to reduce clutter. Thoughts?" The main session advised folding it rather than removing it, since on a clean answer it is the only sign the checks ran. The user: *"My pov is that the project's is show casing claude citations, and these additional checks are good quality of life add on, not guarantees."* Then:
> * The line under each answer goes.
> * The flags and their notes stay as they are. (i. e. when the check catches something, we still flag)
> * "The checks did not run on it", on a partial answer should probably not display anything because again the checks are add on, not the key piece.
> * Update and log my decision.

**Came back:**
- **The checks line under the answer is removed.** Its texts are removed too: `CHECKS_PREFIX`, `checksParts`, `CHECKS_NOT_IN_CORPUS`, `CHECKS_SHORT_NAMES`, and the `.checks` style.
- **The flags are unchanged:** the quotation flag and the citation flag, each with its note, in the answer where the words are.
- **The labels on a partial answer.** The main session's reading of the third point: the incompleteness itself is not about the checks and stays; only the words about the checks go.
  - `PARTIAL_UNCHECKED` is now *"Incomplete: the run ended before the answer was finished."*
  - By the same reasoning, T5.4's end label `INCOMPLETE` drops its last sentence, "The checks ran on the part shown." It is now *"Incomplete: the answer stopped partway because of an error."* This point is the main session's extension, flagged to the user.
- **Left as is:** the step log's "Checked the answer" step, which is a step in the log, not a claim under the answer.
- **Checked (only what changed), in the mock:**
  - `check-flags`: 2 flagged spans with their 2 notes, no checks line, and the disclaimers and cost line at the end.
  - `composition-incomplete-stream-broken`: the end label reads "Incomplete: the answer stopped partway because of an error.", and no sentence about the checks remains under the answer.
  - Node: 71 passed.
**Failures:** none.
**Spend:** none.
**DECISION (user):** the four points quoted above; locked as P4.34, amending T5.2 #4 and T5.4 #6.

## Oct 25, 2026, 20:20 CDT — Frontend: the user's review, round 9; the landing page in two parts
**Asked (the user):** "I'd want us to rethink the landing page for both desktop and mobile together. For desktop, in particular, it looks quite off because there are just too much empty spaces, and it's not responsive. For mobile view, it's too dense. I'm thinking a minimal landing view, then user can scroll down to read more?" After two mockups, with one change of theirs: "the text "or watch a recorded run" should be on its own line, then the chips of the recorded runs below it, arranged responsively to screen sizes." Then: *"Yes, build the landing page as sketched: the first screen, the citation figure below it, the footer, and the recorded runs on their own line."*
**Came back:**
- **The first screen fills one screen** (`.first`, `min-height: 100dvh`). It holds the wordmark, the pitch, the question box and the recorded runs, with a quiet "How the citations work" link and a chevron at its bottom edge. The link points to the section below, and the scroll is smooth unless reduced motion is set.
- **The recorded runs:** the label is on its own line, and the chips sit below it in a grid (`minmax(min(100%, 18rem), 1fr)`), side by side where they fit and one to a line on a phone. They show the full questions, as cards rather than pills, because the questions wrap.
- **Below the first screen** (`.below`, `#how`):
  - The figure gets a wider column (68rem) and a heading, "How the citations work" (`HOW_IT_WORKS`), with its caption above the cards.
  - Its three cards stack below 960 px rather than below 760 px, so a sideways phone gets them stacked.
  - Then the footer: a rule across the wide column, with the disclaimers, the coverage line, the affiliation and the three links.
- **Left as is:** the pitch's wording. The main session said it would draft a shorter one and show it before it goes in; it is not drafted yet.
- **Checked (only what changed), in the mock:**
  - **1440×900:** the first screen is exactly 900 tall. The two chips sit side by side (406 px each). The hint sits at 844 to 880. The three cards are in a row (338 to 341 px each). There is no horizontal scroll.
  - **393×852:** the first screen is exactly 852 tall, with everything on it. The chips are one to a line (361 px). There is no horizontal scroll.
  - **852×393:** the first screen runs to 548, since its content is taller than the screen. The chips sit side by side and the cards are stacked. There is no horizontal scroll.
  - Node: 71 passed.
**Failures:** none.
**Spend:** none.
**DECISION (user):** the direction and the approval quoted above. Not a lock; the main session's calls are the 68rem column, the 960 px point where the cards stack, the hint's wording, and the cards for the chips.

## Oct 25, 2026, 20:26 CDT — Frontend: the user's review, round 10; the pitch in the user's words
**Asked (the user):** "Use this pitch instead: See Claude Citations in action. Ask anything about the Fourth Amendment and surveillance technology, from wiretaps to phone location data. (Bold highlighted line.) Claude searches 32 Supreme Court cases, keeps the passages that bear on your question, and writes an answer with *precise citations* (make these 2 letters stand out). (Less highlighted line.) I'm also open to improvements on the copy as well. I want this to be intuitive, catchy, and easy to understand."
**Came back:**
- **The pitch is two lines, as worded by the user.** `T.pitch` now returns `{lead, more}`, and the count of cases still comes from `corpus.json`.
  - **The lead** is semibold, in the ink colour, and slightly larger: 1.25rem, or 1.125rem on a phone.
  - **The second line** is muted and smaller: 1.0625rem, or 1rem on a phone.
  - **"precise citations"** is in the brand green and semibold. The main session read "these 2 letters" as these two words.
- **`rich()` gains `{em}`,** used only here.
- **Checked (only what changed), in the mock:**
  - **393×852:** the first screen still fits. The hero ends at 713 and the hint starts at 796. There is no horizontal scroll.
  - **1440×900:** the lead wraps to two lines and the second line to two.
  - Node: 71 passed.
**Failures:** none.
**Spend:** none.
**DECISION (user):** the pitch's wording and emphasis, quoted above. Not a lock; the main session offered copy suggestions in its reply, none applied.

## Oct 25, 2026, 20:33 CDT — Frontend: the user's review, round 11; the pitch's first line
**Asked (the user):** "Swap to "Claude’s Citations"" and "The first line becomes "See Claude’s Citations in action. Ask anything about the Fourth Amendment and surveillance, from wiretaps to phone location data."" On the main session's suggested ending ("…and writes an answer where every citation points to the exact sentences it rests on."): *"it doesn't really make sense to a reader what that means. We need to more intuitively, while still accurately, describe what citations really does and how it does it. You're allowed to refetch the docs if needed."*
**Came back:**
- **The pitch's lead is now the user's line, word for word.** The second line is unchanged until the user picks a new one.
- **Anthropic's citations page was re-read** (platform.claude.com/docs/en/build-with-claude/citations, fetched just now). What it says, in the main session's words:
  - The model marks its citations in a standard format.
  - The API turns them into locations in the documents and takes `cited_text` from the document itself. The page calls that "better citation reliability": citations "are guaranteed to contain valid pointers to the provided documents".
  - For custom content documents, the blocks are used as given, and a citation names a range of them. Here each block is one sentence.
- **Wording options** for what citations do are in the reply, none applied.
- **Checked:** Node passed 71. The change is a string only, so it was not checked in the browser.
**Failures:** none.
**Spend:** none.
**DECISION (user):** the first line, quoted above. Not a lock.

## Oct 25, 2026, 20:38 CDT — Frontend: the user's review, round 12; the pitch's second line
**Asked (the user):** "Consider this modified version of mine, "Claude searches 32 Supreme Court cases, keeps the passages that bear on your question, and writes an answer with precise citations: each one is copied word for word from the opinion by code, not regenerated by the AI, guaranteeing precision citing." (Or change the "guaranteeing precision citing" to something else, you get the idea of what I'm trying to say…)"
**Came back:**
- **The second line is the user's, with two changes by the main session.** It now reads: *"Claude searches 32 Supreme Court cases, keeps the passages that bear on your question, and writes an answer with precise citations: each quote is copied word for word from the opinion by code, not regenerated by the AI, so it matches what the Court wrote exactly."* "precise citations" is still marked.
  - **"each one" became "each quote".** What the code copies is the quoted text, not the citation.
  - **The ending became "so it matches what the Court wrote exactly".** The guarantee in Anthropic's docs covers only valid pointers into the documents, so the quoted words are the opinion's own. It does not cover the quote supporting the claim, and "guaranteed accurate" is among brief §10.6's forbidden words.
- **Checked (only what changed), in the mock:**
  - **393×852:** the first screen still fits. The hero ends at 749 and the hint starts at 796.
  - **375×667, a small phone:** the first screen grows to 791, so the hint sits under the content and the page scrolls. There is no horizontal scroll.
  - Node: 71 passed.
**Failures:** none.
**Spend:** none.
**DECISION (user):** the line quoted above, with its ending left to the main session. Not a lock.

## Oct 25, 2026, 20:57 CDT — Frontend: the user's review, round 13; a passage's tag reads as a citation (P4.35)
**Asked (the user):** after the landing figure's redesign was mocked, *"Discuss whether we can make the tag friendlier without losing organization."* The main session proposed citation-style tags. The user suggested a hybrid, `kyllo-majority-p29-13531`, and the main session advised against it:
- the trailing number would be a second, made-up ID;
- "p29" would mean a page where today's "p" means a paragraph;
- it still reads as code, at 24 characters.

It offered the ¶ as the tie-breaker instead. The user: *"Your proposal works. To confirm, this would be a frontend change only with nothing touching the backend and API right?"* The main session confirmed this from the code: each passage's event carries every field the tag needs. It noted that the change amends T4.3 #3. Then: *"Yes, lock it as P4.35 and build it: tags like "Kyllo at 29", the opinion type when it isn't the majority, "n.1" for footnotes, the ¶ mark only when two tags in one answer would match, and the real ID kept in the hover text, the card's small print and the API view."*
**Came back:**
- **`text.js`:**
  - `SHORT_NAMES` holds 32 curated short names. Both Rileys are in full: "Florida v. Riley" and "Riley v. California".
  - `passageTag(p, level)` writes the tag at three levels:
    - level 0 is the case, page, footnote and opinion parenthetical;
    - level 1 adds ", ¶N", the paragraph number from the ID;
    - level 2 also names the author.
  - The parentheticals use a citation's verbs: "dissenting", "concurring", "concurring in judgment", "plurality" and so on.
- **`model.js`:**
  - `tagsFor(run, ids)` raises a tag's level only where two tags in the set would read the same.
  - `tagOf(run, id)` gives the cards and the step log level 1 always, and level 2 only when needed. This is the main session's call: those lists hold many passages from the same pages.
- **The answer (`answer.js`, `view.js`):** each tag is unique within the answer. Its hover text is the ID, and its screen-reader label is "Source: <tag>".
- **The step log's chips and the source cards** show `tagOf`, with the ID as hover text.
  - The card's small print ends "ID kyllo-1-p1.", in the code face.
  - The footnotes folded inside a card show their tags.
- **Unchanged:** the API view's title and fragments, which keep the ID, and the landing figure's live data. The figure's static tag now reads "Kyllo at 29", with the ID as hover text.
- **Tests:** new `webdev/test/tags.test.mjs`, 5 tests:
  - the forms;
  - all 32 corpus cases have distinct short names;
  - the ¶ appears only on a clash;
  - over every fixture, the answer's tags are distinct, and so are all the run's passage tags;
  - over the whole corpus (from the local `web/_generated/`), all 2,462 passages are distinct at level 2.
- **Checked:**
  - Node: 76 passed.
  - In the mock, `answered-phone-location-records` gave these tags, among others:
    - "Carpenter at 309";
    - "Smith at 744";
    - "Katz at 361 (concurring)";
    - "Carpenter at 316, ¶41" and "Carpenter at 316, ¶40", the only clash in that answer;
    - "Carpenter at 362 (dissenting)".
  - The cards read "Carpenter at 310 n.3" and "Chatrie, slip op. at 1, ¶1 (dissenting)", with "ID carpenter-1-p41." in the small print.
**Failures:** none.
**Spend:** none.
**DECISION (user):** quoted above; locked as P4.35, amending T4.3 #1 and #3.

## Oct 25, 2026, 21:07 CDT — Frontend: the user's review, round 14; the read step's target and the three-step citation figure
**Asked (the user):** with a screenshot of a read step showing `kyllo-1-p13` and "1 before, 2 after": *"One place where we missed. Also, change it to 1 paragraph before, 2 paragraphs after for accuracy and clarity. Redo the relevant part of the landing page as well."* The main session read the last sentence as building the three-step citation section it had mocked, which its previous reply had offered.
**Came back:**
- **The read step names its target as a citation (P4.35),** with the target Claude sent as hover text.
  - **A passage ID** gets the passage's tag ("Kyllo at 39, ¶13").
  - **A page target** reads as a citation: "katz:351" becomes "Katz at 351", and Chatrie's "chatrie-2:12" becomes "Chatrie, slip op. at 12 (dissenting)".
  - **Anything else** shows as sent. `readTarget` is in `model.js`; `pageTarget` and `readAround` are in `text.js`.
- **The span reads in paragraphs:** "1 paragraph before, 2 paragraphs after", and "no paragraphs before, 1 paragraph after" when one side is empty.
  - **Both sides empty** reads "only this paragraph". That wording is the main session's.
  - **A footnote target** counts footnotes, since a read adds passages of the target's own kind (the tool's description).
- **The landing figure is three numbered steps,** as mocked in round 13's discussion.
  - **Heading:** "Follow one citation". **Lead:** "A real answer from this site, traced back to the Court’s words in three steps."
  - **Step 1, "Claude makes a claim":** the answer's sentence with its tag, "Kyllo at 29".
  - **Step 2, "The citation points into the opinion":** the opinion's sentence, highlighted, with "533 U.S., at 29".
  - **Step 3, "Code copies the quote, word for word":** the API response trimmed to three fields, each with a comment: "// which opinion", "// which sentences" and "// the quote, copied by code". "Show the full API response" folds out the six-line original.
  - **Layout:** each step's words sit in a 17rem column beside its card on wider screens, and above it below 760 px. The column is now 60rem.
  - **Wording** (`FIG_STEPS`, `FIG_NOTES`, `FIG_FULL`, `FIG_TITLE`, and a new `TRACE_CAPTION`) lives in `text.js`. The figure's old row and connector styles are removed.
- **Checked (only what changed):**
  - Node: 77 passed, with a new test of the read target and the span.
  - **The mock's `step-limit-stop`:** the reads show "Jones at 404, ¶9" and "Knotts at 281, ¶15 | 1 paragraph before, 1 paragraph after", each with its ID as hover text.
  - **The landing at 1440×900:** the words' column is 272 px and the cards are 656 px.
  - **The landing at 393×852:** the cards are 361 px with no horizontal scroll, and the full response opens.
**Failures:** none.
**Spend:** none.
**DECISION (user):** the wording and the redo, quoted above. Not a lock; the main session's calls are the figure's step wording, "only this paragraph", and footnotes counted as footnotes.

## Oct 25, 2026, 21:10 CDT — Frontend: the user's review, round 15; the scroll hint's wording
**Asked (the user):** *"Quick change, update "How the citations work" to "How Claude's citations work""*
**Came back:** `HOW_IT_WORKS`, the first screen's link down to the figure, now reads "How Claude’s citations work", with a typographic apostrophe as in the pitch. The figure's heading stays "Follow one citation". Its comment no longer calls this string the figure's heading.
**Checked:** Node passed 77. The change is a string only, so it was not checked in the browser.
**Failures:** none.
**Spend:** none.
**DECISION (user):** the wording quoted above. Not a lock.

## Oct 25, 2026, 21:17 CDT — Frontend: the user's review, round 16; the bottom of the landing page
**Asked (the user):** *"similar to how we tidied up the bottom of the page during the chat UI, brainstorm with me how do we tidy up the bottom of the landing page as well. Currently, it's a clear after thought section with no coherent design whatsoever."* Three options were mocked up: A, two columns; B, the warnings as the figure's closing note with a short footer; C, one column with labels. Then: *"Go with B: the two warnings as the figure's closing note, then a one-line footer. Keep the locked wording unless I approve the shortened line."*
**Came back:**
- **The figure's closing note:** the not-legal-advice line and the AI disclosure (T5.1 #3 and #4, word for word) sit under the three steps in an `aside`, under the heading "What it won’t do" (`LIMITS_TITLE`, the main session's wording, from the mock-up). It uses the steps' grid (heading in the 17rem column, text beside it) after a hairline, and stacks below 760 px. This matches the run screen, which keeps the same two lines under each answer.
- **The footer** is now the figure's width (60rem, was 68rem; the unused `--wide` token is removed) and left-aligned. The coverage line (T5.2 #2) is on its own line, then the affiliation line on the left with the three links on the right. The locked wording is kept, so the footer is two lines, not one. The shortened single line from the mock-up waits for the user's approval.
- **Checked (only what changed):**
  - Node: 77 passed.
  - **The mock at 1440×900:** the note, the steps and the footer all start at x 240 and are 960 px wide. The affiliation and the links share one row; the links end at the right edge.
  - **The mock at 393×852:** the note stacks (361 px), the links wrap under the affiliation, and there is no horizontal scroll.
**Failures:** none.
**Spend:** none.
**DECISION (user):** option B, quoted above, with the locked wording kept. Not a lock; the main session's calls are the heading "What it won’t do" and the two-line footer.

## Oct 25, 2026, 21:22 CDT — Frontend: the user's review, round 16 closed; the footer stays two lines
**Asked (the user):** *"Keep the footer's two lines with the locked wording."*
**Came back:** no change. The footer built at 21:17 stays as it is (7101ec2): the coverage line (T5.2 #2), then the affiliation line (T5.1 #5) with the links. The shortened single line from the mock-up is dropped.
**Checked:** nothing, since nothing changed.
**Failures:** none.
**Spend:** none.
**DECISION (user):** the locked wording stays, quoted above. Not a lock.

## Oct 25, 2026, 23:08 CDT — Frontend: the user's review, round 17; the annotated amendment on the landing
**Asked (the user):** the landing is *"too minimal and it's not hooking enough"*, and they wanted it to *"scream constitutional vibe"*. Mock-ups led to the user's choices:
- the scope: *"Rework the first view only: the amendment as the backdrop behind the wordmark and the question box, everything else and T4.1's look kept."*
- the layout: *"Move the hero down and drop the amendment's lines higher, so more notes fit above it."*
- the exit into a run, which keeps "probable cause" (the user: *"What about a direction where when a run initiate, the forth amendments just disappear or exit somehow?"*).
- the notes. The user asked what links a word to a quote. The answer was that a note should be the Court's reading of the word. They set the rule: *"each note is the Court's reading of its word, from majority opinions that are still good law."* Then: *"Keep 60 limit because otherwise we're pasting paragraphs on screen."*, *"allow marked omission, proceed"*, and *"Approve the 26 as listed, with each quote's own page and the quoting lines. Build the landing."*
- the font: *"Yes, download Caveat (Recommended)"*.
**Came back:**
- **The notes:** `web/js/margin.js` (new). The amendment's text (`AMENDMENT` in text.js) sits large and pale behind the first view. The hero now sits at the foot of the first view and the amendment starts at its head.
  - A handwritten note writes itself beside a word the hero leaves visible, every 3.6 s, with at most two on screen at once. The older note erases itself, and a leader runs to the word's underline.
  - The 26 notes are `MARGIN_NOTES` in text.js. Each has a quote (at most 60 characters, any omission marked " … "), its passage ID, the page the quote starts on, and a "quoting" line where the majority adopts someone else's words.
  - On screen the quote marks curl and inner quotes become single. No word changes.
- **The exit:** when a run or replay starts:
  - the notes erase and the pitch, the form and the runs step back;
  - the amendment's words fall away except *probable cause*, which gets a written caret and "l";
  - after 2.1 s the run screen shows, with the wordmark moving into the bar as before.
  - The run itself starts at once underneath, so nothing waits on the show. With reduced motion there's no exit and two still notes.
- **A pause control:** a "Pause the notes" button, needed because content that moves for more than five seconds must be pausable (WCAG 2.2.2). The main session added it on its own call. On phones the hero fills the first view, so there are no notes and no button.
- **The font:** Caveat v23, Latin, from fonts.gstatic.com (74,572 bytes), with its OFL text, `@font-face` in fonts.css. No third party is contacted at runtime (T5.5).
- **The quote work:**
  - Three agent rounds: Opus 5.5, high effort, read-only, writing only to the scratchpad.
  - Each list was checked by a scratch script against `web/_generated` (verbatim pieces in order, majority only, length, the page the quote starts on), and the main session read each pick in its paragraph.
  - Dropped on the way: dissents and history lines (the user's rule); 4 picks whose meaning changed without their qualifiers; a "place" note that turned a fair probability into a certainty. Papers, the place, and Oath or affirmation have no notes, because no short, faithful majority reading exists in the corpus.
- **The test:** `webdev/test/margin.test.mjs` (new). It checks that:
  - the amendment's text and its anchors are right;
  - every note is at most 60 characters with properly marked omissions and no banned word;
  - every note is copied from a majority opinion of its case in the committed corpus;
  - from `web/_generated`, every note's passage and its citation via `passageTag`;
  - the curled quote marks;
  - a note's spot and leader.
**Checked:**
- Node: 84 passed.
- **The mock server, at 1440×900, light:** notes appear with the Caveat face loaded, and there is no horizontal scroll.
- **At 1280×800, dark:** the hero is at 228–720, the link down at 744, and the first view fits.
- **At the pane's width:** the exit fades the words by 1.1 s, writes the "l" by 1.5 s, and shows the run by 2.3 s. Going home brings the amendment and notes back.
- **At 375×812, dark:** no horizontal scroll, and no notes or button.
- Timing taken under viewport emulation was throttled to one timer a second, so the exit was timed without emulation.
**Failures:** in the first browser pass, the pause button overlapped the "How Claude’s citations work" link on a phone. Fixed by hiding both the notes and the button below 760 px.
**Spend:** none paid. The agents ran on the session's plan.
**DECISION (user):** the design and the 26 notes, quoted above. Not a lock. The main session's calls:
- the pace (3.6 s per note, 45 ms per character, a 2.1 s exit);
- the pause control and its wording;
- no notes on phones;
- the curled marks.

## Oct 25, 2026, 23:15 CDT — Frontend: the user's review, round 17 locked; the landing page (P4.36)
**Asked (the user):** after trying round 17 at localhost:8080: *"Looks good! Lock this landing page"*
**Came back:** P4.36 locks the landing page as built at 23:08 (f13afd3); no code change.
- The first view: the annotated amendment behind the hero, which sits at the foot.
- The 26 margin notes and the rule they follow.
- The exit into a run.
- Caveat.
- Everything below the first view as it stood: the figure, "What it won’t do", the footer.
The main session's calls from 23:08 are locked with it, as the user approved the page as built: the pace, the pause control and its wording, no notes on phones, and the curled marks.
**Checked:** nothing, since nothing changed.
**Failures:** none.
**Spend:** none.
**DECISION (user):** lock the landing page, quoted above. Locked as P4.36.

## Oct 25, 2026, 23:25 CDT — Frontend: the user's review, round 18; the exit's "l" set in the word
**Asked (the user):** with a screenshot of the exit's last frame: *"The current disappearance animation doesn't really display probable clause cleanly but it's some weird drawings"*
**Came back:** the cause was the written "l". It was a Caveat letter in its own box, which was only as wide as the letter's advance (7 px at 40 px). Its reveal (`clip-path`) cut the ink outside that box, so only a green sliver showed above "cause", with the caret under it.
- Now the "l" goes into the word itself, as `c|l|ause`. It is in the amendment's italic and the page's green, like the wordmark's "l". Its room opens in 0.45 s and it drops in.
- Nothing clips it. The caret is gone, so the last frame reads "probable clause".
- Timing is unchanged: the "l" starts at 1.15 s, and the run shows at 2.1 s.
- `web/js/margin.js` (the exit) and `web/css/style.css` (`.amend .ins`; the Caveat rule for the old `.ins` is removed).
- This departs from P4.36's "a written caret and 'l'". It is not locked until the user says so.
**Checked:**
- Node: `margin.test.mjs`, 7 passed.
- **The mock server, at the pane's width,** with the exit frozen before the run shows: the words read "probable clause" and the "l" is in the brand green.
- **Unfrozen:** the run shows by 3 s. Going home brings back "probable cause", with no "l" left and the leaving state cleared.
**Failures:** none.
**Spend:** none.
**DECISION (user):** the complaint, quoted above. The fix is the main session's call, not yet locked.

## Oct 25, 2026, 23:27 CDT — Frontend: the user's review, round 18 locked; the exit's inserted "l" (P4.37)
**Asked (the user):** after trying round 18: *"Lock the inserted l because that's clearer."*
**Came back:** P4.37 locks the exit's "l" as built at 23:25 (7c3c8da). P4.36 point 3 is amended: *probable cause* takes no written caret or Caveat "l". Instead the "l" is set into "c|ause" in the amendment's italic and the page's green, as in the wordmark, and the last frame reads "probable clause". No code change.
**Checked:** nothing, since nothing changed.
**Failures:** none.
**Spend:** none.
**DECISION (user):** lock the inserted "l", quoted above. Locked as P4.37.

## Oct 25, 2026, 23:28 CDT — Frontend: the user's review, round 19; the exit holds "probable clause" longer
**Asked (the user):** *"What's the timing on the animation currently? I want it to hang a bit more before the run start?"*
**Came back:** until now the exit ran in this order, measured in the mock:
- the notes erase and the hero steps back (0.45 s);
- the words fall from 0.25 s to 0.9 s and are gone by about 1.6 s;
- *probable cause* brightens at 0.5 s;
- the "l" starts at 1.15 s and lands at 1.78 s;
- the run screen showed at 2.1 s, so the finished "probable clause" held for only about 0.35 s.

`EXIT_MS` in `web/js/margin.js` goes from 2,100 to 2,900 ms, so the finished frame now holds for about 1.1 s. Only the run screen waits; the run itself still starts at once. This departs from P4.36's 2.1 s exit and is not locked until the user says so.
**Checked:** the mock server, timed without viewport emulation. The "l" is inserted at 1,156 ms; its width, opacity and drop end at 1,647, 1,681 and 1,781 ms; the run screen shows at 2,910 ms.
**Failures:** none.
**Spend:** none.
**DECISION (user):** a longer hang, quoted above. The 2.9 s is the main session's call, not yet locked.

## Oct 25, 2026, 23:29 CDT — Frontend: the user's review, round 20; only "probable clause" is left at the exit's end
**Asked (the user):** *"Additionally, I want everything disappear other than the probable clause letters in the amendment, including every other highlights and text literally everything"*
**Came back:** before this change, the exit's last frame still showed the hero's wordmark, which was kept so it could fly into the bar.
- The wordmark now fades with everything else in 0.45 s.
- While the page is leaving, the wordmark drops out of the view transition (`view-transition-name: none`), so the bar's wordmark appears with the run screen and doesn't fly in from an invisible one.
- Everything else already went: the notes, their leaders and underlines erase, and the other words fall with their underlines.
- The change is `web/css/style.css` only, in the `.first.leaving` rules.
- This departs from P4.36 point 3, "the wordmark moving into the bar". It is not locked until the user says so.
**Checked:** the mock server, with notes on screen when the run starts.
- Frozen before the run screen: the only things visible in the landing are "probable", "c|l|ause" and the "l", and no leader is left.
- Unfrozen: the run screen shows with the bar's wordmark at full opacity.
- Going home brings the hero's wordmark back at full opacity, with its transition name restored, and the amendment reads "probable cause" again.
**Failures:** none.
**Spend:** none.
**DECISION (user):** the request, quoted above. Not a lock.

## Oct 25, 2026, 23:31 CDT — Frontend: the user's review, rounds 19 and 20 locked; the exit's hold and final frame (P4.38)
**Asked (the user):** after trying rounds 19 and 20: *"Tried it, lock the 2.9 s exit and the final frame with only "probable clause"."*
**Came back:** P4.38 locks the exit as built at 23:28 (eae8a4e) and 23:29 (868bd92). It amends P4.36 points 3 and 4, with no code change:
- the run screen shows 2.9 s after a run starts, not 2.1 s, so the finished "probable clause" holds for about 1.1 s;
- everything but the amendment's "probable clause" fades, the wordmark included, and the wordmark no longer flies into the bar.
**Checked:** nothing, since nothing changed.
**Failures:** none.
**Spend:** none.
**DECISION (user):** lock the 2.9 s exit and the final frame, quoted above. Locked as P4.38.

## Oct 25, 2026, 23:35 CDT — Frontend: the user's review, round 21; no note writes once a run starts
**Asked (the user):** *"Sometimes, as the l insertion animation plays, you can still see some notes getting written"*
**Came back:** a defect in `web/js/margin.js`. It reproduced in the mock at 1280×800, with a run started while a note was writing:
- **A note kept writing.** Its next line wrote itself 0.56 s after the run started. The exit erased the lines already written, but the timer for the next line, and the one for its citation, were still pending.
- **A new note started.** A whole new note began at 2.2 s. The page queues two ticks when it opens (0.6 s and 2.8 s), and only the repeating interval was stopped on exit, not those.
- **The same gap, a third way:** a note already being erased by the normal cycle was not in the list the exit erased, so it kept its slow erase.

The fix:
- the exit now cancels every pending timer before it schedules its own;
- a tick does nothing once the exit has begun;
- the exit fast-erases every note on the page, including those already erasing, which are now tracked (`going`).

P4.36 to P4.38 are unchanged.
**Checked:**
- Node: all 84 passed.
- **The mock at 1280×800,** a run started mid-note: nothing written after the click but the line already writing at the moment of the click. No note was born, notes and leaders were all gone by 1.5 s, and the run screen showed.
- **A run started with a note erasing:** nothing written, and nothing left by 1.5 s.
- **Going home:** the notes resume, two on the page.
Timings under viewport emulation are throttled, so only the order was checked, not the times.
**Failures:** the defect above.
**Spend:** none.
**DECISION (user):** the report, quoted above. A defect fix, no lock needed.

## Oct 25, 2026, 23:40 CDT — Frontend: the user's review, round 22; "probable clause" no longer turns back into "cause"
**Asked (the user):** *"Final polish, the animation currently goes: probable cause -> probable clause -> but then BACK to probable cause"*
**Came back:** a defect in `web/js/main.js`. `toRun()` called `swap('run')` and then, in the same moment, `margin.stop()`. That cleared the landing and took the "l" out of "clause" before the view transition photographed the old frame, so the cross-fade showed "probable cause".
- In the mock, an instrumented `startViewTransition` recorded "probable clause" when it was called and "probable cause" when the old frame was captured.
- Now `swap()` returns a promise that resolves when the transition has finished, or skipped. `toRun()` clears the landing only then, and only if the run screen is still showing, so a quick "home" isn't undone.
- P4.36 to P4.38 are unchanged.
**Checked:**
- Node: all 84 passed.
- **The mock, instrumented:** the old frame is captured with "probable clause". After the transition the hidden landing has reset, with no notes and no "l", and the run screen shows.
- **Going home:** "probable cause", with the leaving state cleared.
**Failures:** the defect above.
**Spend:** none.
**DECISION (user):** the report, quoted above. A defect fix, no lock needed.

## Oct 26, 2026, 00:15 CDT — Frontend: the user's review, round 23; the log trimmed to research, "Later developments" under the answer, "Search opinions"
**Asked (the user):** *"Build round 23: the trimmed log, the web check below the answer with the new wording and reveal, Search opinions, and the new placeholder."*
The discussion before it, in the user's words:
- *"I want to remove these elements because they are redundant. User can already see the answer being written and the update result whether they ran or not."*
- *"we will show it after the answer finishes streaming if streaming finishes first then show it whenever the update check finishes. I want an on-brand insertion animation not something abrupt."*
- *"'update check' is something vague and hard to grasp what it means to the average user too."* On the main session's drafts: *"your drafts on later devs and such are good"*. The pointer's "above" to "below": *"Approve the necessary change in wording."*
- On the copy guard's refusals: *"The guard and refused site wording is something we built to protect ourselves. I'm thinking it's not even necessary to report to the user ... Just show them the final result?"*, agreed.
- The button: *"Search Opinions, how about that? 'Find the Court's words' is too damn long for a button."* It is set in sentence case, "Search opinions", to match "Ask another question".
- The "No tools in this call…" line: *"it's already implicit and we don't want to dig into the weed too deep here."*

**Came back:**
- **The step log** (`web/js/steps.js`) shows research only and ends at "Finished research". The "Writing the answer" and "Update check, running beside the answer" groups are gone, with their intro lines, "Checked the answer", the web search's steps and its refused summaries. A pause or resume after research still shows.
- **The box** (`web/js/view.js`, `band.js`) now sits under the answer and its two warnings, above the run's cost line. It comes in when the run ends, which is when both the answer and the web search are done, so it never pushes what is being read.
  - If the answer finishes first, a quiet line holds its place: "Still checking the web for anything newer…", with the pulsing dot.
  - **Its arrival:** its dashed edge is inked around it clockwise from the top left (0.9 s), and its lines come up one by one (0.07 s apart). The drawn edge then hands over to the box's own border. With reduced motion it is a plain fade. A replay skipped to the end, or a reload catching up, shows it without animation, as before.
  - The pointer under the answer comes in with the box.
- **The wording** (`web/js/text.js`), as drafted in the discussion:
  - the heading "Later developments";
  - the label, the guarantee, the findings and overview headings, "How Claude searched", the site's settings line (without "no Exa highlights or summaries"), "Nothing newer found…", "Claude didn't search the web: <reason>", "Web search unavailable: …", the not-summarised line and the pointer ("…see below");
  - the status lines: "checking the web for anything newer";
  - the credits, the privacy note, the pre-*Chatrie* label and the cost part: "web search".
  - The label drops "a date filter skips pages with no published date"; each page still shows its date or "no published date".
- **The button** reads "Search opinions" on the landing and in the dock, set from `T.SEARCH`. On a phone it stays on one line: `.primary` gets `white-space: nowrap`, and the question box (`.field textarea`) takes `width: 0` so its default width no longer pushes the dock past the screen. That overflow was found in this round's check and fixed.
- **The placeholder:** "What has the Court said about heat cameras aimed at a house?"
- **Not changed:** the chips. Their text comes from the recorded runs, so the new questions arrive with the replays (P4.32).

**Checked:**
- Node: all 84 passed.
- **The mock, a run whose web search ends after the answer:**
  - the log ends at "Finished research";
  - the waiting line appears once the answer is done, with the status "Checking the web for anything newer · the answer is written";
  - at the end the order is answer, warnings, box, cost line.
- **A run whose search found something:** the new wording throughout, and the pointer "…see below" under the answer.
- **The reveal, on a recorded run with its animations paused halfway:** the dashed edge drawn from the top left around past the right side, and the lines coming up in order.
- **Phone width (375 px), landing and dock:** the button on one line and no sideways scroll.
- **Desktop (1280 px):** the landing form is unchanged.

The mock's sample events carry old timestamps, so a mock live run counts as catching up and plays without animations. The reveal was therefore checked on a recorded run.

**Failures:** the phone overflow above, fixed before commit.
**Spend:** none.
**DECISION (user):** the requests and agreements quoted above. To lock after the user tries it: the trimmed log, the box's place and arrival, and the refusals left off the page (amending P4.3's step-log line); the new wording (amending T5.3 and the pointer, T1.11's line); the button; the placeholder; and the new questions for T5.6, still to be settled.

## Oct 26, 2026, 00:22 CDT — Frontend: the user's review, round 24; the box's page links line up on the left
**Asked (the user):** *"Looking good! 1 thing to patch, why is the indentation so weird here?"* The screenshot showed the list of every page the search returned, staggered across the box.
**Came back:** a clash of class names in `web/css/style.css`. A general `.links` rule, written for the fine print's row of links (`main.js`: flex, wrapping, centred), also matched the box's page lists, which `band.js` gives the same class. Each page link was laid out as a centred flex item, so each line started at a different place. The defect predates round 23; the box at the bottom of the run made it plain.
- **The fix:** the rule now applies only to `p.links`, the fine print's paragraph. The box's lists (`ul.links`) keep their own rules.
**Checked:**
- Node: all 84 passed.
- **The mock, a run whose search found something:** all three page lists in the box are blocks, and every link starts at the box's left edge.
- **The landing's fine print:** its row of links is still flex, laid out as before (its own `#landing-fine` rule).
**Failures:** the defect above.
**Spend:** none.
**DECISION (user):** the report, quoted above. A defect fix, no lock needed.

## Oct 26, 2026, 00:24 CDT — Frontend: the user's review, round 23 locked; the step log shows research only (P4.39)
**Asked (the user):** after trying rounds 23 and 24: *"Looking good! Lock as is."*
**Came back:** P4.39 locks the step log as built in round 23 (f1b5883), with no code change:
- the log shows research's steps only and ends at "Finished research";
- the "Writing the answer" and "Update check, running beside the answer" groups go, with their intro lines, "Checked the answer", "No tools in this call…", the web search's steps and its refused summaries;
- a pause or resume after research still shows.
It amends P4.3: a summary the copy guard refused is no longer shown anywhere on the page. Its stored and streamed events are unchanged. It also replaces the main session's two groups (P4.31, step 0's call) and T5.3 #6's step-log lines.
**Checked:** nothing, since nothing changed.
**Failures:** none.
**Spend:** none.
**DECISION (user):** *"Lock as is."* Locked as P4.39.

## Oct 26, 2026, 00:24 CDT — Frontend: the user's review, round 23 locked; "Later developments" under the answer (P4.40)
**Asked (the user):** *"Lock as is."*
**Came back:** P4.40 locks the web search's box as built in round 23 (f1b5883), with no code change:
- it sits under the answer and its two warnings, above the run's cost line;
- it comes in when the run ends, once both the answer and the web search are done, and while the search runs on after the answer, "Still checking the web for anything newer…" holds its place;
- its dashed edge is inked around it from the top left (0.9 s) and its lines come up one by one, or a plain fade with reduced motion;
- the pointer under the answer comes with it.
It amends T4.3 #4 (the band above the answer) and P4.31's placement.
**Checked:** nothing, since nothing changed.
**Failures:** none.
**Spend:** none.
**DECISION (user):** *"Lock as is."* Locked as P4.40.

## Oct 26, 2026, 00:24 CDT — Frontend: the user's review, round 23 locked; the web search's wording (P4.41)
**Asked (the user):** *"Lock as is."* On the drafts before round 23: *"your drafts on later devs and such are good"*, and on the pointer: *"Approve the necessary change in wording."*
**Came back:** P4.41 locks the wording in `web/js/text.js` as built in round 23 (f1b5883), with no code change. "Update check" is retired from what the page shows: the box is "Later developments" and the feature "the web search". It amends:
- T5.3 #1 to #5: the label, the guarantee, the box's parts, the outcome lines and the pointer;
- T5.1 #6: the credits' "for the web search";
- T5.5: the privacy note's "for the web search";
- T5.6 #2: the pre-*Chatrie* label's "to show the web search finding it".
**Checked:** nothing, since nothing changed.
**Failures:** none.
**Spend:** none.
**DECISION (user):** *"Lock as is."* Locked as P4.41.

## Oct 26, 2026, 00:24 CDT — Frontend: the user's review, round 23 locked; "Search opinions" and the placeholder (P4.42)
**Asked (the user):** *"Lock as is."* On the button before round 23: *"Search Opinions, how about that?"*
**Came back:** P4.42 locks, as built in round 23 (f1b5883), with no code change:
- the button reads "Search opinions" on the landing and in the dock, in sentence case, on one line at phone width;
- the question box's placeholder is "What has the Court said about heat cameras aimed at a house?"
It replaces the main session's "Research" and placeholder (P4.31). The new replay questions for T5.6 are not part of this lock and are still to be settled.
**Checked:** nothing, since nothing changed.
**Failures:** none.
**Spend:** none.
**DECISION (user):** *"Lock as is."* Locked as P4.42.

## Oct 26, 2026, 00:31 CDT — Frontend: the user's review, round 25; the palette tried as Evergreen deepened
**Asked (the user):** *"I want tech and legal at the same time but that's hard to mix. What do you think?"* The main session proposed splitting by role: the court's words on paper, the machinery on the dark API window, with one bright green kept for what is live. It sketched three directions (Evergreen deepened, court navy, oxblood and brass) next to the current palette. The user: *"Let's try evergreen deepened. Modify the palette directly?"*
**Came back:** only the tokens at the top of `web/css/style.css` changed, as a try, not a lock.
- **Neutrals:** a new neutral hue `--hn` (85) warms them to paper. `--h0` (158) now sets only the brand and the API window.
- **Brand:** lowered from oklch(0.52 0.17) to oklch(0.42 0.085) in light, and from oklch(0.72 0.14) to oklch(0.76 0.10) in dark.
- **New `--live`:** the brighter green, oklch(0.52 0.14) in light and oklch(0.82 0.13) in dark. It is used only by the working step's marker, the waiting line's dot and the two carets.
- **The API window:** a green-black panel in both modes.
- **Shadows and the dialog backdrop:** tinted from the paper hue, no longer green.
- **Unchanged:** the source hues, the flag red and the dark mode that follows the system (T4.1).
The main session's call: the light `--live` went from 0.60 to 0.52 lightness, so the step number on it passes 4.5:1.
**Checked:**
- **Contrast, by a script** (OKLCH to sRGB, WCAG ratios), both modes. In light: ink 16.2, muted 6.3 (5.8 on surface), brand text 7.8, the button 7.8, the live marker 4.8, the flag 5.1, the API window's text 13.4 and its muted text 5.9, the four source hues 4.6 to 5.0. In dark every pair is 6.5 or more. The old light brand on the old paper measured 4.7.
- **Looked at in the mock,** in light and dark at 1280 px: the landing, a replay skipped to the end, the sources panel and the API window.
- No Node tests were run, since nothing they cover changed.
**Failures:** none.
**Spend:** none.
**DECISION (user):** none yet; a try for the user to look at.

## Oct 26, 2026, 00:35 CDT — Frontend: the user's review, round 25 locked; the palette is Evergreen deepened (P4.43)
**Asked (the user):** *"Looks really good. Lock."*
**Came back:** P4.43 locks the palette as built in round 25 (9491bcb), with no code change:
- warm paper neutrals;
- a deep, quiet brand green;
- `--live` for what is working right now;
- a green-black API window.
The source hues, flag red and system-following dark mode are kept from T4.1. It amends T4.1's palette and closes the light-mode contrast item from 17:50.
**Checked:** nothing, since nothing changed (contrast was measured at 00:31).
**Failures:** none.
**Spend:** none.
**DECISION (user):** *"Looks really good. Lock."* Locked as P4.43.

## Oct 26, 2026, 00:39 CDT — Frontend: the user's review, round 26; the margin notes on phones
**Asked (the user):** *"Quick check, on mobile, the noting in the frontend is not working?"* The main session explained that P4.36 turns the notes off below 760 px. The user: *"Just turn on notes on phone quickly."*
**Came back:**
- **The phone gate is removed.** `web/js/margin.js` no longer skips notes below 760 px.
- **Room for the notes (the main session's call).** Removing the gate alone showed no note, because on a phone the hero covered every keyword but "right" (hero from 53 px to 740 px on a 375 × 812 view). The phone layout in `web/css/style.css` now starts the hero 11rem down. The amendment's first lines ("right", "secure", "persons", "houses", "effects") stay clear above it, with room for one note beside one of their words.
- **The pause control is shown on phones** (WCAG 2.2.2), in the top right corner. At the bottom it overlapped "How Claude's citations work", and the notes already keep out of its box.
**Cost:** at 375 × 812, the second recorded-run chip now sits below the first view, about 50 px lower than before.
**Checked:**
- In the mock at 375 × 812, notes appeared on "effects" (*Jacobsen*), "houses" (*Dunn*) and "home", each with its leader. Nothing scrolls sideways, and the pause control and the link don't overlap.
- Starting a recorded run clears the notes and shows the run screen.
- Node tests: 84 of 84 pass.
**Failures:** none.
**Spend:** none.
**DECISION (user):** none yet. This would amend P4.36's "no notes on phones" if locked.

## Oct 26, 2026, 00:41 CDT — Frontend: the user's review, round 26 locked; the margin notes show on phones (P4.44)
**Asked (the user):** *"Lock frontend as is. Prepare for compaction."*
**Came back:** P4.44 locks round 26 (0a5aab4) as built, with no code change:
- notes at every width;
- the phone hero starting 11rem down;
- the pause control in the top right corner on phones.
It amends P4.36's "no notes on phones". The frontend now stands as locked through P4.44.
The main session read "Lock frontend as is" as locking what is built. It did not read it as the local review's sign-off, so that sign-off is not logged here. The full suite and the browser sweep still wait for the user's word that iterating is done.
CLAUDE.md's current state is updated for the compaction.
**Checked:** nothing, since nothing changed (round 26 was checked at 00:39).
**Failures:** none.
**Spend:** none.
**DECISION (user):** *"Lock frontend as is."* Locked as P4.44.

## Oct 26, 2026, 00:42 CDT — Frontend: the user's review continues
**Asked (the user):** *"Nope, iterating is still on. Prep for compaction."*
**Came back:**
- "Lock frontend as is" (00:41) locked P4.44 only. It was not the local review's sign-off.
- The full suite, the browser sweep and the sign-off wait until the user says iterating is done.
- CLAUDE.md's current state now says so.
**Checked:** nothing, since nothing changed.
**Failures:** none.
**Spend:** none.
**DECISION (user):** *"Nope, iterating is still on."*

## Oct 26, 2026, 01:03 CDT — Frontend: the user's review, round 27; the fonts tried as Founding print, behind master tokens
**Asked (the user):** after a mockup of four font sets (scratch only, not committed): *"Try stand up founding print. Also, use master variables to make things easier for us in the future as well. (So no multiple changes across many files.) Unless, it'd be too much of a refactor."* Then: *"Yes, download the 16 font files and the 3 licence texts."*
**Came back:**
- **Master tokens.** No refactor was needed: fonts were already named only in `fonts.css` (the files) and `style.css`'s tokens, except the margin notes' Caveat. Every family is now named once, in `style.css`'s type block:
  - `--ui`, the product;
  - `--src`, the Court's words;
  - `--display`, the amendment behind the first view;
  - `--display-i`, its italic phrase, for a display cut with no italic;
  - `--code`, the API;
  - `--hand`, the margin notes.
  A change of font is its `@font-face` rules in `fonts.css` plus one token.
- **Founding print:**
  - IBM Plex Sans v23 for `--ui`;
  - Libre Caslon Text v5 for `--src` and `--display-i`;
  - Libre Caslon Display v18 for `--display`;
  - IBM Plex Mono v20 for `--code`;
  - Caveat kept for `--hand`.
- **The files:** 16 `.woff2` files (Latin and Latin Extended, 288 KB) from fonts.gstatic.com, and 3 SIL OFL 1.1 texts from github.com/google/fonts (`OFL-ibmplex.txt`, `OFL-librecaslontext.txt`, `OFL-librecaslondisplay.txt`), downloaded Oct 26, 2026 on the user's word. Each file was checked as woff2 and each licence as OFL 1.1.
- The old fonts' files and faces stay until a choice is locked, so going back is three tokens.
**Checked:**
- In the browser pane, on the mock:
  - the landing at 1280×800, with the notes, the hero and the chips;
  - the exit animation, where "probable cause" is in Caslon Text italic;
  - a recorded run's answer, source cards and API window;
  - dark mode;
  - the phone landing at 375×812, with notes shown and no sideways scroll.
- The browser loaded exactly the new families plus Caveat.
- Node tests: 84 of 84 pass.
- `tests/deploy`: 40 passed, 2 skipped.
**Failures:** none.
**Spend:** none.
**DECISION (user):** none yet. This would amend T4.1's fonts if locked.

## Oct 26, 2026, 01:05 CDT — Frontend: the user's review, round 27 locked; the fonts are Founding print (P4.45)
**Asked (the user):** *"Lock founding print. Prepare for compaction."*
**Came back:** P4.45 locks round 27 (cf58b57) as built, with no code change:
- the type tokens, every family named once in `style.css`;
- IBM Plex Sans and Mono;
- Libre Caslon Text and Display;
- Caveat kept for the notes.
It amends T4.1's fonts, and T4.1's heading now says so.
The former fonts' files stay in `web/fonts/`. No token names them, so they are never fetched; removing them is the user's call.
**Checked:** nothing, since nothing changed (round 27 was checked at 01:03).
**Failures:** none.
**Spend:** none.
**DECISION (user):** *"Lock founding print."* Locked as P4.45.

## Oct 26, 2026, 01:05 CDT — Frontend: the user's review continues; prepared for compaction
**Asked (the user):** *"Lock founding print. Prepare for compaction."*
**Came back:** CLAUDE.md's current state now covers:
- rounds 1 to 27, with P4.45 locked;
- the type tokens;
- the former fonts left unused;
- `local-cf58b57` on 8080;
- the next number, P4.46.
Iterating continues (00:42). The full suite, the browser sweep and the sign-off still wait for the user's word that it is done. The scratch mockup server on 8790 is stopped.
**Checked:** nothing, since nothing changed in the code.
**Failures:** none.
**Spend:** none.
**DECISION (user):** none beyond P4.45.

## Oct 26, 2026, 01:09 CDT — Frontend: the user's review, round 28; back to the top before the exit
**Asked (the user):** *"whenever a person hit search opinions or click on any recorded run, we should first scroll them up top before we play our probable clause l insertion animation. Otherwise, they would miss it."*
**Came back:** `toRun` in `web/js/main.js` now calls a new `toTop()` before `margin.exit()`. When the landing is scrolled down, the page glides back to the top. The exit, with the "l" sliding into "clause", starts once the page is at the top. It also starts if the page stops moving for 8 frames, for example when a hand is on the wheel, or after `TOP_CAP_MS` (1,500 ms) at the latest. At the top, or with reduced motion, the exit starts at once, as before. The run still starts underneath at once, so the scroll never holds the run up. The token is checked again after the scroll, so a newer click or run wins.
- The main session's call: the cap of 1,500 ms. Basis, measured in the mock: 811 ms back from the phone landing's foot (1,049 px); 461 ms from 392 px at 1280×800.
**Checked:** in the mock, by tracking the scroll position and the exit's start in the page:
- a recorded-run chip from the phone landing's foot, 375×812: the exit started at 811 ms, at the top, and the "l" went in at the top;
- "Search opinions" from 392 px down, 1280×800: the exit started at 461 ms, at the top;
- a chip clicked at the top: the exit started after 10 ms, so there is no delay.
Node tests: 84 of 84.
**Failures:** none.
**Spend:** none.
**DECISION (user):** none yet.

## Oct 26, 2026, 01:15 CDT — Frontend: the user's review, round 28 locked; the frontend finished (P4.46)
**Asked (the user):** *"Frontend is finished. Lock. Prepare for compaction. Then, I'm thinking we should do in order: 1. Full test. 2. Populate and cache in parallel a few runs. (Questions need approval first.) 3. Deploy."* Also: *"I want cache replay to be a frontend isolation. The frontend getting loaded still wake backend, but cache replay should not rely on any extra components. (Let me know if this is not already the case.)"*
**Came back:**
- P4.46 locks round 28 (2341af0) as built, with no code change, and ends the local review: iterating is over.
- The user's order for what comes next is recorded in P4.46.
- **Replays are already frontend-only.** A replay is two static files on the web service: `replays/index.json` and `replays/<slug>.json`. The same page code plays them as it plays a live run. Everything a replay opens (`config.json`, `corpus.json`, `opinions/*.json`) is static on the web service too. The only API call on the landing is the wake (`api/health`), which a replay never waits on. Production's `nginx.conf` has no `/api/` location, so the web service does not depend on the API at all.
- `replays/` keeps the two local review files until the real replays replace them in step 2.
**Checked:** the web container alone, from the 2341af0 image with no API container, so `/api/health` answered 502:
- the page loaded (200);
- the thermal-imager chip played. After "Skip to the end" the answer showed 8,741 characters and 60 controls, with `playing` cleared;
- the network log showed only static files, apart from the landing's wake retries to `api/health` (all 502);
- the reader's files are served (`opinions/berger-1.json`, 200).
The full stack was then rebuilt with `deploy/local.sh`.
**Failures:** none. Stopping the API container made `local.sh` remove both containers, by design (its cleanup), so the web container was started alone by hand for the check.
**Spend:** none.
**DECISION (user):** *"Frontend is finished. Lock."* Locked as P4.46. The order: full test, then the replays (questions approved first), then the deploy. The replays stay frontend-only (the user's words above). That is already the case, so nothing changed.

## Oct 26, 2026, 01:16 CDT — Frontend: finished; prepared for compaction
**Asked (the user):** *"Prepare for compaction."*
**Came back:** CLAUDE.md's current state now covers:
- the frontend finished (P4.46);
- the user's order: the full test, then the replays (questions approved first, P4.22's remaining allowance), then the deploy on its green light;
- the replays kept frontend-only;
- the review's locks, P4.36 to P4.46;
- what stays the user's call;
- `local-2341af0` on 8080;
- the next number, P4.47.
**Checked:** nothing, since nothing changed in the code.
**Failures:** none.
**Spend:** none.
**DECISION (user):** none beyond P4.46.

## Oct 26, 2026, 01:18 CDT — Frontend: the former fonts removed (P4.47)
**Asked (the user):** *"Remove the old font files."*
**Came back:**
- Deleted 10 `.woff2` files and 3 OFL texts from `web/fonts/`: Instrument Sans, Newsreader and JetBrains Mono.
- Removed their 12 `@font-face` rules from `web/css/fonts.css`, and rewrote its opening comment to match.
- What is left: 17 faces (Caveat plus Founding print's 16) and 4 OFL texts. `web/fonts/` is now 424 KB.
- Every `url()` in `fonts.css` names a file that exists. The credits page names no fonts, so nothing else changed.
- `web/looktests/machinery/` loads those families from Google Fonts itself, not from `web/fonts/`, so it is untouched (P1.6's record).
- P4.45's heading now says P4.47 amends it.
**Checked:**
- in the mock: the page's font set lists only Caveat, IBM Plex Sans and Mono, and Libre Caslon Text and Display, with none in error. The six files fetched all answered 200. The body is in IBM Plex Sans and the amendment in Libre Caslon Display;
- Node tests: 84 of 84;
- the deploy tests: 40 passed, 2 skipped (the web image's guard still finds `.woff2` files and an OFL text).
**Failures:** none.
**Spend:** none.
**DECISION (user):** *"Remove the old font files."* Locked as P4.47.

## Oct 26, 2026, 01:26 CDT — Full test before the replays (the user's step 1)
**Asked (the user):** *"Full test, launch."* This is step 1 of the order locked in P4.46.
**Came back:** every suite passes, and the browser sweep found no defect. Nothing was changed.
**Checked:**
- the whole Python suite (`.venv/bin/pytest -q`): **2,943 passed, 54 skipped**, the same count as at Wave 3's merge;
- the Atlas tests against `Probable_Clause_test` (`PC_ATLAS_TEST=1`, `tests/state/test_store_atlas.py`): 45 passed. These are 45 of the 54 the full suite skips;
- the Node tests (`node --test webdev/test/`): 84 of 84;
- the browser sweep on the local stack (`deploy/local.sh`, `local-c74b3e0`, 8080):
  - **landing at 654 px, light:** loaded with only the five current font families and none in error, every resource answering 200, and no sideways scroll;
  - **the thermal-imager replay at 654 px:** played at its recorded pace. "Skip to the end" reached the finished answer, with "Later developments" (no web search), the cost line and the finish line;
  - **a citation tag:** tapping one at this width switched to Sources and lit the cited passage, and "View source" opened the reader at `jardines-2-p5` with the cited sentence marked;
  - **landing and a replay at 1280×800, dark:** both rendered, filling the viewport, with no sideways scroll;
  - **phone, 375×812, light:** the phone-tracking chip pressed from the landing's foot glided back to the top in 910 ms. The run view followed at 2,962 ms, so the exit played after the scroll (P4.46). The replay played and skipped to its end (the web search's band and the cost line), with no element past the viewport edge and no failed request;
  - **phone, 375×812, dark:** the landing and the "Follow one citation" figure rendered.
- One screenshot of the figure after a wheel scroll came back blank. The page itself showed every step at full opacity, and a second screenshot showed the figure, so the blank came from the screenshot, not the page.
**Failures:** none.
**Spend:** none. No live run was started. Only replays were played.
**DECISION (user):** none. Next is the replays (step 2): the questions go to the user for approval first.

## Oct 26, 2026, 01:34 CDT — The replays recorded: four runs, three with false or arguable flags (the user's step 2)
**Asked (the user):** *"Run the four replay questions"*:
1. "What has the Court said about searching a phone after an arrest?"
2. "When is tracking a car with GPS a search?"
3. "What has the Court said about geofence warrants?"
4. "Can police watch a backyard from the air?"

**Came back:**
- Four real paid runs, started together at 01:28 on the local API (`local-c74b3e0`, `PC_ENV=test`, the development keys, `Probable_Clause_test`) with `scripts/run_client.py`.
- Every run answered in full (`answered`, `complete`, no stop) on the full corpus.

| Run | Rounds | Kept of found | Answer blocks | Citations | Web search band | Time | Cost |
|---|---|---|---|---|---|---|---|
| `phone-search-arrest` | 5 | 28 of 55 | 101 | 50 | nothing relevant | 63 s | $0.3027 |
| `gps-tracking-car` | 5 | 28 of 54 | 85 | 42 | nothing relevant | 61 s | $0.3257 |
| `geofence-warrants` | 7 | 40 of 80 | 112 | 62 | nothing relevant (Chatrie's remand reported in the overview) | 81 s | $0.4316 |
| `backyard-from-air` | 6 | 19 of 44 | 67 | 33 | found (no new decision on drones; commentary) | 53 s | $0.3050 |

- **Files:**
  - the events and summaries are in `data/verification/replays/` (local, kept);
  - the rendered answers are in `data/verification/replays/answers/`.
- **`scripts/export_replay.py` (new):** writes the replay files of contract §11.2 and `index.json` from saved events, in the order given.
  - Before writing, it checks each run: envelopes numbered 1 to N, the schema, `run_started` first and `run_ended` last, one run, and no page text on a web result.
  - It rebuilt the earlier local thermal-imager replay byte for byte from its events.
  - It exported the four runs to `replays/` in the user's order, with commit `c74b3e0`. The two local review files were removed: they were copies of Wave 3's runs, which stay in `data/verification/wave3/`.
  - `replays/` is still excluded from git and nothing in it is committed, since T5.6 has the user review each recording before it is published.
- **The answer checks' flags,** read against the opinions:
  - **`phone-search-arrest`:** none. 14 of 14 quotations were found.
  - **`gps-tracking-car`, false:**
    - flagged: "where a classic trespassory search is not involved and resort must be had to *Katz* analysis" (*Jones*, `jones-1-p21`);
    - the opinion has these words exactly;
    - the answer italicised *Katz* inside the quotation, and the quotation check compares the `*` marks literally;
    - with the marks removed, `check_quotation` finds it.
  - **`geofence-warrants`, false, same cause:**
    - flagged: "re-ups arguments, point-for-point, that *Carpenter* specifically rejected." (`chatrie-1-n7`);
    - the opinion has these words exactly.
  - **`backyard-from-air`, false (citation check):**
    - flagged: "*Chatrie v. United States* (Alito, joined by Thomas and Barrett)" as `not_in_corpus`;
    - the case-name walk runs on into a parenthesis that opens with a capitalised word and reads the name as "Chatrie v. United States (Alito", which matches no case;
    - it is the same without italics. "*Carpenter v. United States* (2018)" is not flagged;
    - the page draws it in red beside a Chatrie citation.
  - **`backyard-from-air`, arguable (quotation check):**
    - flagged: "knowingly expose[] [an area] to the public" (*Florida v. Riley*);
    - the opinion quotes *Katz*: "What a person knowingly exposes to the public";
    - "[an area]" is an inserted bracket with no source words behind it, so the flag holds under the check's rules (T1.12), though the bracketing is ordinary legal style.
- These are defects in part F's checks (`api/checks/quotations.py`, `api/checks/citations.py`), found on the final code after the user said the frontend was finished. Nothing is fixed. T5.6 makes it the user's call, run by run: publish as recorded with the flags, or re-record.

**Checked:**
- in the browser, on the rebuilt local stack (`local-3fc61d0`, which differs only in `BUILD_LOG.md`):
  - the four chips at 375×812 in the user's order, no sideways scroll;
  - each replay played at its recorded pace and skipped to its end (the finish line, the cost line, "Later developments");
  - the flags drawn: `phone-search-arrest` 0, `gps-tracking-car` 1, `geofence-warrants` 1, `backyard-from-air` 2;
- `replays/geofence-warrants.json` is 1.03 MB and is served as 169 KB gzipped.

**Failures:** the three runs' false flags above. No run failed.
**Spend:**
- Anthropic, Voyage and Exa together: $1.3651 today in `Probable_Clause_test` (`spend_report.py`; month $3.6735);
- Exa: 4 searches;
- left of P4.22's allowance: about $1.09 and 13 Exa searches.

**DECISION (user):** none yet. Open:
- whether to publish each flagged run as recorded or to fix the checks and re-record it (T5.6);
- T5.6's fifth replay, the geofence question on the corpus that ends before *Chatrie*, which was not in this request.

## Oct 26, 2026, 01:35 CDT — The replays: the check fixes, the re-recording and its allowance (P4.48)
**Asked (the user):** *"Fix the two check bugs with tests, then re-record the three flagged runs. New allowance: $3.00 and 10 Exa searches."*
**Came back:** locked as P4.48.
- The two false-flag defects (01:34) are to be fixed in `api/checks/`, tests first:
  - Markdown emphasis inside a quotation;
  - a case name running into a following parenthesis.
- The bracketed insertion in *Florida v. Riley* stays flagged (T1.12).
- To re-record: `gps-tracking-car`, `geofence-warrants`, `backyard-from-air`. `phone-search-arrest` is kept.
- The new allowance is $3.00 and 10 Exa searches, counted from the test database's month total of $3.6735.

**Checked:** nothing yet.
**Failures:** none.
**Spend:** none.
**DECISION (user):** the fixes, the re-recording of the three runs, and the allowance, as quoted. Locked as P4.48.

## Oct 26, 2026, 01:43 CDT — The replays: the checks fixed, three runs re-recorded, all four clean (P4.48)
**Asked (the user):** *"Fix the two check bugs with tests, then re-record the three flagged runs. New allowance: $3.00 and 10 Exa searches."*
**Came back:**
- **The fixes,** tests first (84c0db4). The 16 new tests were written before the code: 12 failed as expected, and 4 that guard what must not change already passed.
  - **`api/checks/quotations.py`:** `_strip_marks` also drops Markdown emphasis: every `*`, and any `_` not inside a word. This applies to the quotation and the source alike, so:
    - "*Katz*" inside a quotation reads as "Katz";
    - star paging ("Commentaries *225", *Ciraolo*) still matches;
    - an underscore inside a URL in *Chatrie*'s footnotes stays a character;
    - a changed word is still flagged when it is italicised.
    - The corpus holds 51 `*` (star paging and "* * *" breaks) and 6 `_` (inside URLs), counted by script.
  - **`api/checks/citations.py`:** `_walk_right` stops at a token that opens a parenthesis or bracket.
    - "Chatrie v. United States (Alito, joined by …)" resolves.
    - "Hester v. Ohio (Holmes, J.)" is flagged as "Hester v. Ohio".
    - "Carpenter v. United States (2018)" resolves as before.
  - The bracketed insertion in *Florida v. Riley* stays a flag (P4.48 #2).
  - The 01:34 replays' exact sentences, run through the fixed functions, now pass.
- **The re-recordings,** started together at 01:39 on `local-84c0db4` (`PC_ENV=test`, `Probable_Clause_test`). Each answered in full with no stop:

| Run | Rounds | Kept of found | Answer blocks | Citations | Quotations | Names and cites | Web search band | Time | Cost |
|---|---|---|---|---|---|---|---|---|---|
| `gps-tracking-car` | 4 | 23 of 38 | 67 | 33 | 2 of 2 | 4 of 4 | found (cert denied in *Thompson v. Wilson*, Oct 5, 2026; commentary; no new ruling) | 44 s | $0.2133 |
| `geofence-warrants` | 6 | 40 of 95 | 112 | 56 | 8 of 8 | 1 of 1 | nothing relevant | 64 s | $0.3511 |
| `backyard-from-air` | 6 | 20 of 52 | 61 | 30 | 1 of 1 | 5 of 5 | found (no new decision on drones; commentary) | 54 s | $0.2376 |

  No flags on any of the three. The answers' wording differs from the first recordings, so the fixes are tested by the unit tests, not by these runs.
- **The export:** `scripts/export_replay.py` now takes a commit per run (`slug=events.jsonl@commit`).
  - The four went to `replays/` in the user's order:
    - `phone-search-arrest`, the 01:28 run at `c74b3e0`, byte for byte unchanged;
    - the three re-recordings, at `84c0db4`.
  - The first recordings of the three stay in `data/verification/replays/`, kept, not exported.
  - `replays/` is still uncommitted until the user has reviewed the recordings (T5.6).

**Checked:**
- the whole suite: **2,959 passed, 54 skipped** (2,943 and 16 new);
- the Node tests: 84 of 84;
- the browser, on the rebuilt stack at 375×812:
  - the GPS and geofence replays skipped to their ends;
  - the backyard replay played at its recorded pace to "Finished: 6 tool rounds and the answer, 54 s.";
  - every one had 0 flags drawn, the cost line and no sideways scroll, and the GPS band showed its finding.

**Failures:** none.
**Spend:**
- Anthropic, Voyage and Exa together: $0.8020 (`spend_report.py`; test database month total $4.4755);
- Exa: 3 searches;
- left of P4.48's allowance: $2.198 and 7 Exa searches.

**DECISION (user):** none beyond P4.48. Open:
- the user's review of the four recordings before they are committed and published (T5.6);
- T5.6's fifth replay, the geofence question on the corpus that ends before *Chatrie*.

## Oct 26, 2026, 01:45 CDT — The replays: every one from the newest recordings (P4.49)
**Asked (the user):** *"Hold up, I want the newest recordings used across the board, not using anything separate for phones."*
**Came back:** locked as P4.49, amending P4.48 #3.
- The main session's reading, stated to the user: there is no phone-only recording, and every replay plays at every screen size. The "phone" replay is the question about searching a phone after an arrest, kept from `c74b3e0`.
- Either way the action is the same: re-record `phone-search-arrest` on `84c0db4`, so all four replays come from the same code.
- The first recording stays in `data/verification/replays/`.

**Checked:** nothing yet.
**Failures:** none.
**Spend:** none yet. About $0.30 expected, inside P4.48's $2.198 and 7 Exa searches left.
**DECISION (user):** as quoted. Locked as P4.49.

## Oct 26, 2026, 01:47 CDT — The replays: phone-search re-recorded, all four from 84c0db4 (P4.49)
**Asked (the user):** *"Hold up, I want the newest recordings used across the board, not using anything separate for phones."*
**Came back:**
- **The re-recording:** `phone-search-arrest`, run `LHdjNk0iXw_0fRhlj1MzlA`, started at 01:45 on `local-84c0db4`. It answered in full with no stop:
  - 5 rounds, 25 kept of 43 found;
  - 77 answer blocks with 38 citations;
  - quotations 3 of 3, names and cites 4 of 4, **no flags**;
  - the web search band: found (the overview reports no new ruling on phone searches after an arrest and *Riley* still governing; the later activity is *Chatrie*, a Second Circuit border-search decision and a New Jersey geofence ruling);
  - 43 s, $0.2044.
- **The export:** all four went to `replays/` at `84c0db4`, in the user's order:
  - `phone-search-arrest`, 01:45;
  - `gps-tracking-car`, `geofence-warrants` and `backyard-from-air`, 01:39.
- The 01:28 recording of the phone-search question stays in `data/verification/replays/`, kept but not exported.
- **No replay is specific to a screen size.** `web/js/replay.js` and `main.js` pick a replay by its slug alone, so the same four files play on phones and on wide screens.
- `replays/` is still uncommitted until the user has reviewed the recordings (T5.6).

**Checked:**
- the stack, rebuilt (`local-ed2dd8e`, the same code as `84c0db4` plus the log), serves the new file;
- in the browser at 375×812:
  - the index lists the four chips in order;
  - the phone-search replay skipped to "Finished: 5 tool rounds and the answer, 43 s.", with "Recorded run, Oct 26, 2026.", the cost line, 0 flags and no sideways scroll.

**Failures:** none.
**Spend:**
- $0.2044 (test database month total $4.6799);
- 1 Exa search;
- left of P4.48's allowance: $1.9936 and 6 Exa searches.

**DECISION (user):** P4.49, as quoted. Open:
- the user's review of the four recordings before they are committed and published (T5.6);
- T5.6's fifth replay, the geofence question on the corpus that ends before *Chatrie*.

## Oct 26, 2026, 01:48 CDT — The replays approved and committed (P4.50)
**Asked (the user):** *"I reviewed the four replays. Approved: commit replays/ and take it out of the exclude."*
**Came back:** locked as P4.50.
- **`.git/info/exclude`:** its `replays/` line and that line's comment are removed (it is local to this checkout and not committed).
- **Committed in `replays/`:** `index.json` and the four replays, 2.3 MB in all. All four are at `84c0db4`:

| Replay | Run | Events |
|---|---|---|
| `phone-search-arrest` | `LHdjNk0iXw_0fRhlj1MzlA` | 353 |
| `gps-tracking-car` | `9iRQPOXNhjC6NlqhUK5nIw` | 333 |
| `geofence-warrants` | `SAKUNhVxhcGBpbEdiVE2RQ` | 629 |
| `backyard-from-air` | `pdUkkt0HsWENVDDY_gWkKw` | 378 |

- Before committing, a scan of the five files found no local paths, user names or key-like strings.
- **Stale comments updated:**
  - `deploy/local.sh` no longer says the replays are never committed;
  - `deploy/web.Dockerfile` no longer says they are written in Phase 5. Its conditional copy is unchanged.

**Checked:** see the next entry's test run.
**Failures:** none.
**Spend:** none.
**DECISION (user):** the four recordings approved as recorded, `replays/` committed and taken out of the exclude. Locked as P4.50.

## Oct 26, 2026, 01:50 CDT — The replays committed: tests and the rebuilt stack (P4.50)
**Asked (the user):** the check for P4.50 (01:48).
**Came back:** nothing changed. The stack was rebuilt from the committed tree.
**Checked:**
- the whole suite: 2,959 passed, 54 skipped. The deploy tests pass with `replays/` committed: the web image still copies it only through its bind mount;
- the Node tests: 84 of 84;
- `deploy/local.sh` rebuilt both images (`local-d20ae44`). The web service serves the five `replays/` files byte for byte as committed (SHA-256 compared).

**Failures:** none.
**Spend:** none.
**DECISION (user):** none beyond P4.50. Next, in the user's order: the deploy, only on its explicit green light, with the cloud setup script (P4.30) and the goodnight block (P4.26), each on its own green light. T5.6's fifth replay stays open.

## Oct 26, 2026, 02:16 CDT — Frontend: the user's review, round 29; the later-developments box reordered, its scroll capped
**Asked (the user):** *"I want us to rearrange the later development box because they can get quite long an unituitive."* The new order: the heading; the line on what Claude searched; *"Claude's overview (and promote the header?)"*; *"What Claude found, in its own words"*; the line on what this site checks; the links and summaries; *"How Claude searched"*; every page the search returned. Then: *"scroll to expose at most to the line "Claude's overview" only, and nothing more, not even the overview content, so that user can still see the actual answer above and won't get disoriented."* And: *"in case the answer finishes streaming but the later development search has not, then, the user already did their own scrolling (up down doesn't matter), we shall not scroll them automatically anymore but let them find the section on their own."*
**Came back:** built in `web/js/band.js` and `web/js/view.js`:
1. **The order,** for a box with findings: "Later developments"; the line on what Claude searched (T5.3); "Claude's overview" and the overview; "What Claude found, in its own words"; the line on what this site checks (moved under that heading, since it is about the points below it); the points and their links; "How Claude searched"; every page returned.
2. **The overview heading is promoted:** it was a small muted label inside the overview's paragraph and is now a subheading like the box's other two. For a box without findings, the short outcome line ("Nothing newer found…", the skip or unavailable line) still comes first and the overview after it, since the overview explains it (main session's call).
3. **The scroll at the run's end** stops with the box's first subheading at the bottom of the conversation, 12 px clear: "Claude's overview" where there is one, otherwise the next subheading. It never scrolls up, and the dock growing at the run's end keeps the same limit. A box with no subheading follows to the bottom as before. The heading's place is measured from the box and the heading's offset inside it, since the heading itself moves while the box inks in.
4. **Hands off after the visitor's own scroll:** once the answer is written and the web search still runs, any scroll of the visitor's, up or down, means the run's end does not scroll at all. The flag clears with the next run. It is set by the same input detection as the pinning (a wheel, touch, key or scrollbar grab within a second), so scrolls of the page's own never set it.

**Checked:**
- Node tests: 84 of 84.
- In the browser on the mock (8765), served from the working tree:
  - the GPS replay: the box's children are in the new order, and the run's end stopped with "Claude's overview" 898 px down a 908 px pane, against a bottom 1,277 px further, with the answer's last lines in view;
  - the same replay with its last web search moved to end 12 s after the answer, in the page only (the committed file is unchanged): with no input, the waiting line came at 44 s and was followed, then the box came in 12 s later and the scroll stopped at the overview heading. With a wheel scroll up during the wait, the box came in and nothing moved (4,472 px before and after);
  - at phone width (375 × 812), the backyard replay skipped to the end stopped with the overview heading at 560 px in a 571 px pane, the answer's end still showing.
- A first attempt at the moved-search test played 4× fast. That bunched research's tool calls, and the 3 s spacing between them (`pace.js`) held the whole run back to one burst. It was the test's doing, so the test was re-run at the recorded pace.
- Nothing else is affected, so the Python suite was not re-run (quick-iteration rule).

**Failures:** none.
**Spend:** none.
**DECISION (user):** the direction above, as quoted. Not locked: round 29 waits for the user's look. The local stack (8080) is rebuilt from this commit for it.

## Oct 26, 2026, 02:26 CDT — Frontend: the user's review, round 29 locked; the later-developments box reordered (P4.51)
**Asked (the user):** *"Lock as is."*
**Came back:** P4.51 locks round 29 (a3b1dbe) as built, with no code change:
- the box's new order, with the overview first under its own subheading;
- the run's end scrolling only as far as the box's first subheading;
- no scroll at all after the visitor's own scroll during the web search's wait.

It amends P4.40.
**Checked:** nothing, since nothing changed (round 29 was checked at 02:16). The local stack runs `local-a3b1dbe`.
**Failures:** none.
**Spend:** none.
**DECISION (user):** round 29 locked as is (P4.51).

## Oct 26, 2026, 02:33 CDT — The replays: a tighter question recorded to replace the geofence chip
**Asked (the user):** *"Go with "Can police get your Google location history without a warrant?" Record it under the P4.48 allowance and let me review before export."* The reason given: the geofence question is "too broad, leading to Claude trying to read as many passages as possible".
**Came back:**
- **The run:** `location-history-warrant`, run `HvxrPtB_UvIVgr1SorxjTA`, started at 02:32 on `local-a3b1dbe` (`PC_ENV=test`, `Probable_Clause_test`), with `scripts/run_client.py`. The backend is the same as at `84c0db4`: `git diff 84c0db4 HEAD -- api` is empty. It answered in full with no stop:

| Run | Rounds | Kept of found | Reads | Answer blocks | Citations | Quotations | Names and cites | Web search band | Time | Cost |
|---|---|---|---|---|---|---|---|---|---|---|
| `location-history-warrant` | 6 | 25 of 50 | 2 | 59 | 29 | 2 of 2 | 0 of 0 | found | 51 s | $0.2413 |
| `geofence-warrants` (01:39, for comparison) | 6 | 40 of 95 | 12 | 112 | 56 | 8 of 8 | 1 of 1 | nothing relevant | 64 s | $0.3511 |

  - **No flags.**
  - **Kept:** 18 passages from *Chatrie*'s majority, 3 from *Carpenter* (the warrant rule and its exigency exception), 2 from Jackson's concurrence, 2 from Gorsuch's, and 2 from Alito's dissent.
  - **Web search band:** found. Its findings are the Fourth Circuit setting argument on remand (Mealey's, Oct 20, 2026) and *State v. Hobbs* (N.J. App., Oct 2, 2026, as a Paul, Weiss memo reports it), which applied *Chatrie* to suppress geofence evidence.
- **Read against the opinion, two points for the user's review** (the checks don't test either one):
  - **The dissent's joins.** The answer says "Alito, J., dissenting (joined by Justices Thomas and Barrett)". The heading has Thomas joining Part I only and Barrett joining Parts II–B, II–C–1 and II–C–2. The two cited passages, `chatrie-4-p24` and `chatrie-4-p30`, sit in II–B–2 and II–C–2, so Barrett joins them and Thomas does not.
  - **Exigency.** The answer says "The *Chatrie* majority passages here do not separately discuss exceptions for Location History." That is true of the kept passages, but the majority's footnote 11 (`chatrie-1-n11`, not kept) says the decision "does not call into doubt, in such circumstances, a warrantless geofence search".
- **Files:**
  - the events, summary and client log are in `data/verification/replays/` (local, kept);
  - the rendered answer is `data/verification/replays/answers/location-history-warrant-HvxrPtB_UvIVgr1SorxjTA.md`.
- **Not exported.** `replays/` is unchanged and still holds the four approved replays (P4.50), the user's review first.

**Checked:** the run's events through `render_run.py`; the two points above against `data/corpus/cases/chatrie.json`.
**Failures:** none.
**Spend:**
- $0.2413 (`spend_report.py`; test database month total $4.9212);
- 1 Exa search;
- left of P4.48's allowance: $1.7523 and 5 Exa searches.

**DECISION (user):** none yet. Open:
- whether this run replaces `geofence-warrants`, as recorded or re-recorded;
- T5.6's fifth replay, the geofence question on the corpus that ends before *Chatrie*.

## Oct 26, 2026, 02:34 CDT — Correction to 02:33: the majority's kept passages
**Asked (the user):** nothing; the main session's correction.
**Came back:**
- The 02:33 entry says 18 kept passages came from *Chatrie*'s majority. It is **16**. The entry was counted by eye, against the rule that counts come from scripts.
- Counted by script from the run's `keep_passages` calls:
  - 25 kept in all;
  - 16 from `chatrie-1`, the majority;
  - 3 from `carpenter-1`;
  - 2 each from `chatrie-2` (Jackson), `chatrie-3` (Gorsuch) and `chatrie-4` (Alito);
  - 2 `read_passages` calls.

**Checked:** the counts above, by script.
**Failures:** the miscount at 02:33.
**Spend:** none.
**DECISION (user):** none.

## Oct 26, 2026, 02:37 CDT — The replays: the location-history question re-recorded
**Asked (the user):** *"Re-record the location-history question once more under the P4.48 allowance and show me the new answer before export."*
**Came back:**
- **The run:** `location-history-warrant`, run `bLe0Pl-WUxOnNjQWauyXmg`, started at 02:36 on `local-a3b1dbe` (`PC_ENV=test`, `Probable_Clause_test`). It answered in full with no stop. Counts are from the run's events, by script:

| Run | Rounds | Kept of found | Reads | Answer blocks | Citations | Quotations | Names and cites | Web search band | Time | Cost |
|---|---|---|---|---|---|---|---|---|---|---|
| `bLe0Pl-WUxOnNjQWauyXmg` (02:36) | 5 | 26 of 40 | 0 | 51 | 29 | 18 of 18 | 2 of 2 | nothing relevant | 49 s | $0.2153 |
| `HvxrPtB_UvIVgr1SorxjTA` (02:32) | 6 | 25 of 50 | 2 | 59 | 29 | 2 of 2 | 0 of 0 | found | 51 s | $0.2413 |

  - **No flags.**
  - **Kept:** 12 from `chatrie-1` (the majority), 5 from `carpenter-1`, 4 from `chatrie-4` (Alito), 2 each from `chatrie-2` (Jackson) and `chatrie-3` (Gorsuch), and 1 from `chatrie-5` (Barrett).
- **Against 02:33's two points:**
  - **The dissent's joins.** This answer names no joins for Alito and gives Barrett's own dissent its own line, so nothing in it misstates who joined what.
  - **Exigency.** It isn't mentioned at all. The answer says "The passages do not set out a standalone rule about what warrant or other process suffices for Location History." Footnote 11 (`chatrie-1-n11`) again was not kept.
- **New in this answer:** *Carpenter*'s footnote reserving the short-period question (`carpenter-1-n3`), tied to *Chatrie*'s two hours, and Alito on where the line between *Carpenter* and the third-party doctrine now falls (`chatrie-4-p38`), labelled as his view.
- **The web search band:** nothing relevant.
  - It searched the same remand query and got 10 pages, among them Mealey's on the Fourth Circuit's remand argument and the Paul, Weiss memo on *State v. Hobbs*, both of which the 02:32 run reported as findings.
  - This time it submitted no findings. Its overview reads: "Web reports after the corpus date describe follow-on activity in Chatrie and early lower-court use of it. They do not change what the June 29, 2026 opinions held."
- **Files:**
  - the events, summary and client log (`location-history-warrant.r2.log`) are in `data/verification/replays/`;
  - the rendered answer is `data/verification/replays/answers/location-history-warrant-bLe0Pl-WUxOnNjQWauyXmg.md`.
- **Not exported.** `replays/` is unchanged.

**Checked:** the run's events through `render_run.py`; the citations named above, read in the rendered answer.
**Failures:** none.
**Spend:**
- $0.2153 (`spend_report.py`; test database month total $5.1365);
- 1 Exa search;
- left of P4.48's allowance: $1.5370 and 4 Exa searches.

**DECISION (user):** none yet. Open:
- which run, if either, replaces `geofence-warrants`;
- T5.6's fifth replay, the geofence question on the corpus that ends before *Chatrie*.

## Oct 26, 2026, 02:40 CDT — The replays: the location-history run exported as the third chip, uncommitted, on the local stack
**Asked (the user):** *"Export the 02:36 location-history run (bLe0Pl-WUxOnNjQWauyXmg) in place of geofence-warrants, as the third chip, and stand it up locally so I can look at it in the page."*
**Came back:**
- **The export:** `scripts/export_replay.py` wrote the four replays in this order:
  1. `phone-search-arrest`, at `84c0db4`;
  2. `gps-tracking-car`, at `84c0db4`;
  3. `location-history-warrant` (run `bLe0Pl-WUxOnNjQWauyXmg`), at `a3b1dbe`, the commit its API reported. The backend at `a3b1dbe` is the same as at `84c0db4`;
  4. `backyard-from-air`, at `84c0db4`.
  - The three approved replays came out byte for byte the same (`git diff` shows only `index.json`).
  - `replays/geofence-warrants.json` is removed from the working tree. It is still in git at `d20ae44`, and its run's events are kept in `data/verification/replays/`.
  - `replays/location-history-warrant.json` is 446,687 bytes.
- **Nothing is committed.** `replays/` differs from the approved P4.50 set until the user approves the swap.
- **The stack:** `deploy/local.sh` was stopped and rerun. The web image copies `replays/` from the working tree, so it serves the uncommitted export:
  - the API reports `local-c648401`;
  - `index.json` lists the four chips in the order above;
  - `geofence-warrants.json` returns 404.

**Checked:** in the browser on `localhost:8080`:
- the four chips in order, at 375×812 with no sideways scroll;
- the location-history replay, skipped to its end:
  - "Finished: 5 tool rounds and the answer, 49 s.";
  - "Recorded run, Oct 26, 2026.";
  - the cost line, "about $0.21 at list prices";
  - Later developments, which reads "Nothing newer found. That doesn't mean nothing has changed." and then the overview, "Web reports after the corpus date describe follow-on activity in Chatrie and early lower-court use of it."

**Failures:** none.
**Spend:** none.
**DECISION (user):** none yet. Open:
- approving the swap, which commits `replays/` and amends P4.50;
- T5.6's fifth replay, the geofence question on the corpus that ends before *Chatrie*.

## Oct 26, 2026, 02:43 CDT — The replays: the location-history replay approved and committed (P4.52)
**Asked (the user):** *"I reviewed the location-history replay. Approved: commit replays/ with it in place of geofence-warrants."*
**Came back:** locked as P4.52, amending P4.50.
- **Committed in `replays/`:** all at `84c0db4` except the third, at `a3b1dbe`:

| Chip | Replay | Run | Events |
|---|---|---|---|
| 1 | `phone-search-arrest` | `LHdjNk0iXw_0fRhlj1MzlA` | 353 |
| 2 | `gps-tracking-car` | `9iRQPOXNhjC6NlqhUK5nIw` | 333 |
| 3 | `location-history-warrant` | `bLe0Pl-WUxOnNjQWauyXmg` | 301 |
| 4 | `backyard-from-air` | `pdUkkt0HsWENVDDY_gWkKw` | 378 |

  - `geofence-warrants.json` is deleted from `replays/`. It stays in git history at `d20ae44`, and its run's events are kept in `data/verification/replays/`.
  - Phones 1, 2 and 4 are byte for byte the files P4.50 approved.
- **Before committing:**
  - a scan of `location-history-warrant.json` found no local paths, user names or key-like strings;
  - `tests/deploy/test_images.py`, the tests that touch `replays/`, passed 14 of 14;
  - the stack on 8080 already serves these files (02:40). Its image was built from this working tree, so it needs no rebuild for the swap.

**Checked:** the scan and the tests above.
**Failures:** none.
**Spend:** none.
**DECISION (user):** the location-history replay approved, committed in place of `geofence-warrants`, as quoted. Locked as P4.52.

## Oct 26, 2026, 02:44 CDT — Correction to 02:43: a typo; CLAUDE.md updated for P4.52
**Asked (the user):** nothing; the main session's correction.
**Came back:**
- The 02:43 entry says "Phones 1, 2 and 4 are byte for byte the files P4.50 approved." It should say **chips** 1, 2 and 4: `phone-search-arrest`, `gps-tracking-car` and `backyard-from-air`.
- **CLAUDE.md's current state** now records:
  - P4.52;
  - the chips' order;
  - the allowance left: $1.5370 and 4 Exa searches;
  - the running stack, `local-c648401`;
  - the next number, P4.53.

**Checked:** nothing beyond the files.
**Failures:** the typo at 02:43.
**Spend:** none.
**DECISION (user):** none.

## Oct 26, 2026, 02:52 CDT — Phase 4: Build, closed (P4.53)
**Asked (the user):** *"We're done with Phase 4 Build."*
**Came back:** locked as P4.53.
- **Phase 4 ends here, before the first deploy.** The brief's table puts the first deploy and the first cold-start sample at the end of Phase 4 (§3). At the user's word they move into Phase 5, under P5.1 below.
- **What Phase 4 built** (every part logged above):
  - the backend, parts A to I, on contract v2.1;
  - the frontend (P4.28 to P4.47, P4.51);
  - the four replays (P4.50, P4.52).
- **The whole suite at the last full run:** 2,959 passed and 54 skipped (BUILD_LOG 01:26, after P4.48).
- **Tagged** `phase-4-done` on this commit. `git worktree list` shows only the main checkout, so no worktree is left to remove.
- **Still open, carried into Phase 5:**
  - T5.6's fifth replay;
  - the skipped band line's repeated reason (17:50);
  - the cost line counting our estimates (17:50).

**Checked:** `git worktree list`.
**Failures:** none.
**Spend:** none.
**DECISION (user):** Phase 4 closed, as quoted. Locked as P4.53.

## Oct 26, 2026, 02:52 CDT — Phase 5: the deploy green-lit, setup, deploy and goodnight (P5.1)
**Asked:** the deploy's order, as the main session proposed it just before this entry: the free prep; then green light 1, the cloud setup script (P4.30); green light 2, `deploy/deploy.sh`; green light 3, goodnight's block deployed (P4.26); green light 4, the first live paid run on the domain. Also four questions: the GitHub link, the Phase 4 tag, turning the site off, the public Cloud Run addresses.
**Came back:** locked as P5.1.
- **Green lights 1, 2 and 3 are given.** The main session runs the setup script, then `deploy.sh`, then deploys goodnight with this site's block.
- **The first live paid run on the domain is the user's own,** not the main session's.
- **The GitHub link** (`github.com/NguyenTran2002/probable-clause`) is correct. The repo is pushed later, on the user's word; until then the link is a dead page.
- **The off switch** after launch is removing goodnight's block: accepted.
- **The public Cloud Run addresses** (T3.5): accepted.

**Checked:** nothing yet.
**Failures:** none.
**Spend:** none.
**DECISION (user):** *"GitHub link github.com/NguyenTran2002/probable-clause is correct. We will push soon."* On the off switch: *"Sure."* On the public addresses: *"Not a problem."* Then: *"I'll greenlight 1, 2, and 3. For green light 4, I'd do the live paid run on the domain myself."* Locked as P5.1.

## Oct 26, 2026, 03:06 CDT — Phase 5: deployed, live at nguyennhattran.com/probable-clause (P5.1)
**Asked:** P5.1's green lights 1 to 3: the setup script, `deploy/deploy.sh`, goodnight's block.
**Came back:**
- **The setup script, `deploy/setup.sh`** (042b36d, P4.30), with `tests/deploy/test_setup.py` (8 tests under stubs):
  - it enables Cloud Run, Artifact Registry, Secret Manager and IAM;
  - it creates the registry `probable-clause` and the service accounts `pc-api` and `pc-web`;
  - it creates four secrets from `.env`, each value written by a uv-started Python process straight into gcloud's standard input; the Anthropic secret takes `ANTHROPIC_API_KEY_LIVE`;
  - it gives `pc-api` alone `secretmanager.secretAccessor` on each;
  - it is safe to rerun: each piece is made only when missing.
- **Before the cloud,** both images were built locally for linux/amd64, without pushing. The API image started under emulation on `Probable_Clause_test` and was ready in 3.6 s.
- **Green light 1, the setup script,** ran after 02:52 and before 02:58 CDT (its own time was not recorded) and exited 0. The check that followed:
  - each secret compared against `.env` inside a Python process, printing only "matches": 4 of 4;
  - each secret's only reader is `pc-api`;
  - the live and development Anthropic keys differ.
  - gcloud warned "filter keys were not present … state" while each secret had no version yet; harmless.
  - `gcloud auth configure-docker` found the registry's helper already in `~/.docker/config.json`, so nothing there changed.
- **Green light 2, `deploy.sh`,** ran from 02:58:25 to 02:59:31 CDT and exited 0, at commit `042b36d`:
  - the spend check read `Probable_Clause`: no spend in October;
  - `probable-clause-api-00001-hpd` at `https://probable-clause-api-1066460440617.us-central1.run.app`, `PC_ENV=live`;
  - `probable-clause-web-00001-vl4` at `https://probable-clause-web-1066460440617.us-central1.run.app`;
  - read back: automatic scaling, max 1 (API) and 2 (web), request-based billing, startup boost, ingress all.
- **The first cold-start sample** (brief §3, §8.5), from Cloud Run's logs, a start after a deploy:
  - "Starting new instance" (DEPLOYMENT_ROLLOUT) at 07:59:03.18 UTC, ready at 07:59:18.44 UTC: **15.3 s**;
  - the app was ready 11.8 s after its process started; about 3.1 s before that was the container;
  - the app's steps: corpus 3.4 s, keyword index 0.16 s, vectors 0.23 s, Atlas indexes 0.60 s, **clients and the loop 7.4 s** (1.1 s locally under emulation). That step is the largest share and is for Phase 5 to look at.
- **Smoke tests on the Cloud Run addresses:** the API's `/health` 200 with commit `042b36d`; the web's page, `replays/index.json` (the four chips in order), the location-history replay, `config.json`, `corpus.json`, an opinion file, the credits and privacy pages all 200; `geofence-warrants.json` and `api/health` on the web service 404, as built.
- **Green light 3, goodnight** (`~/Documents/Developer/framedbytran`, never pushed):
  - the block, fenced `# === probable-clause ===` in `goodnight/nginx.conf`, committed as 29983d4, with a line in that repo's CLAUDE.md (7d62d8c):
    - a bare `/probable-clause` 302s to `/probable-clause/`;
    - `/probable-clause/api/*` goes to the API with the prefix stripped, buffering and caching off, 300 s read timeout;
    - everything else under the prefix goes to the web service, prefix stripped;
    - `X-Forwarded-For`, `X-Real-IP` and `Forwarded` are cleared on both, so no client IP is forwarded (T3.5). Without that, nginx would pass the inbound `X-Forwarded-For` through.
  - **Checked before it went live:** `nginx -t` passed; goodnight's image run locally served the page, a replay, an opinion and the live API's `/health` under the prefix, and `/goodnight`, `/jev-demo/`, `/haiku-decision-api/health` and the catch-all redirect as before.
  - **Deployed** with goodnight's own `deploy.sh` from 03:03:34 to 03:05:03 CDT: `goodnight-00015-nt9` serves 100%, replacing `goodnight-00014-llq` (the rollback revision).
- **On the domain:**
  - every path above answers 200 under `https://nguyennhattran.com/probable-clause/`, and the API's `/health` reports commit `042b36d`;
  - the domain's other routes are unchanged: `/goodnight`, `/self-exempt`, `/jev-demo/`, `/ads-workbench/`, `/fullstackinsurancepoc/`, `/statefunclaimsadjudicator/`, `/haiku-decision-api/` 200, and `/` 302s to `/goodnight`;
  - in the browser at 375×812: no sideways scroll, no console errors, the wake call 200, and the phone-search replay played to "Finished: 5 tool rounds and the answer, 43 s."
- **No live run was made.** The first one is the user's (P5.1).

**Checked:** as above; `tests/deploy/` 48 passed, 2 skipped.
**Failures:** none.
**Spend:** none on Anthropic, Voyage or Exa. Cloud Run, Artifact Registry and Secret Manager now bill in `probable-clause`, min 0 instances.
**DECISION (user):** none beyond P5.1.

## Oct 26, 2026, 03:11 CDT — Phase 5: four replays for now; T5.6's fifth deferred (P5.2)
**Asked:** the open item carried by P4.53: T5.6's fifth replay, the question on the corpus that ends before *Chatrie*. The main session recommended recording it with the location-history question.
**Came back:** locked as P5.2. The site keeps its four replays for now (P4.50, P4.52). T5.6's fifth replay is deferred, not dropped. Three of the four end with the band's outcome `found` (counted by script from `update_band` in each replay).
**Spend:** none.
**DECISION (user):** *"Let's keep it to four replays for now."* Locked as P5.2.

## Oct 26, 2026, 03:11 CDT — Phase 5: the skipped band line left as built (P5.3)
**Asked:** the open item from "Oct 25, 2026, 17:50 CDT": T5.3 #4 gives both "Update check skipped: <reason>" and "Claude's reason: <reason>", and the page shows only the first, so the reason is not repeated. The main session recommended keeping it as built.
**Came back:** locked as P5.3. The page stays as built for now; T5.3 #4's second line is not shown.
**Spend:** none.
**DECISION (user):** *"Leave at is for now."* Locked as P5.3.

## Oct 26, 2026, 03:11 CDT — Phase 5: the cost line's note on estimates, and a redeploy now (P5.4)
**Asked:** the open item from "Oct 25, 2026, 17:50 CDT": the cost line's total counts this site's estimates for attempts that reported no usage (T3.3), while its note (T5.2) says "from each response's token counts". The main session recommended a short note shown only when an estimate is in the total.
**Came back:** locked as P5.4: the note is added and the site redeployed now, which is the deploy green light for this change.
**Spend:** none.
**DECISION (user):** *"Add and redeploy now."* Locked as P5.4.

## Oct 26, 2026, 03:19 CDT — Phase 5: the cost line's estimate note built and redeployed (P5.4)
**Asked:** P5.4: add the note, and redeploy now.
**Came back:**
- **The change** (62d6272):
  - `model.js` counts the run's `paid_call` events with `estimated: true`, Claude's and Exa's only, since Voyage is not in the shown total;
  - `costs.js` adds one line under the cost details' note when that count is above 0, from `text.js`'s `COST_ESTIMATED`: "Includes this site’s estimate for N attempt(s) that reported no usage.";
  - runs with no estimate, and so all four replays, are unchanged (no replay has an estimated `paid_call`).
- **Tests:**
  - two new Node tests: the count matches every fixture's estimated Claude and Exa attempts, and the wording for 1 and 3 attempts. The Node tests: 86 passed;
  - the whole Python suite: 2,967 passed, 54 skipped.
- **In the page,** on the mock with `retries-anthropic-and-voyage-recovered`: the details read "Includes this site’s estimate for 3 attempts that reported no usage." The fixture's three Voyage estimates are not counted. The mock is back on its default fixture and speed.
- **Before the redeploy:** the API's logs for the past hour show no `/runs` request except the main session's 404 probe at 03:02, and `Probable_Clause` has no spend, so no live run was cut off.
- **The redeploy,** `deploy.sh` from 03:14:34 to 03:16:04 CDT, exit 0, at commit `62d6272`: `probable-clause-api-00002-f67` and `probable-clause-web-00002-jfn`. goodnight is untouched.
- **On the domain:** `/health` reports commit `62d6272`; the served `text.js`, `costs.js` and `model.js` carry the change; the page, the replay index, an opinion file and `/goodnight` answer 200.
- **Not done:** this redeploy's start-up time. The log query for it stalled and was stopped, and the second, simpler query returned nothing. The first sample (03:06) stands.

**Checked:** as above.
**Failures:** the stalled log query.
**Spend:** none on Anthropic, Voyage or Exa.
**DECISION (user):** none beyond P5.4.

## Oct 26, 2026, 03:30 CDT — Phase 5: the first live run, the user's own (P5.1)
**Asked (the user):** *"Record this run."* The user sent the site's first live run on the domain at 03:25 CDT (P5.1's green light 4, the user's own).
**Came back:**
- **The run:** `_o1-_Zf7-NAjvA-xR_QDZA`, question "What does the police need to enter a house?", from 03:25:10 to 03:26:07 CDT, on revision `probable-clause-api-00002-f67` (commit `62d6272`), full corpus, all three steps on `claude-sonnet-5-5`.
- **Outcome:**
  - `answered`, answer complete (5,214 characters, 45 blocks, 22 citations to 11 passages);
  - 5 research rounds: 3 meaning searches, 1 exact search, 3 keep calls, 13 passages kept;
  - no stop, no retry, no estimated attempt (so P5.4's note did not show);
  - the scope note says the corpus lacks the home-entry cases themselves (such as *Payton*), seen only as cited in later opinions.
- **The checks:** quotations 22 of 22 found; case names 5 of 8 found, with three flagged as not in the corpus: *Warden v. Hayden*, *Schneckloth v. Bustamonte* and *Payton v. New York*. All three are real cases outside the 32; the flag says a real case outside them is flagged too, so the check behaved as built.
- **The web search was skipped by Claude,** no Exa search. Its reason: the question concerns the baseline rule for entering a home, and the corpus runs through mid-2026, so a web check was unlikely to turn up anything bearing on it.
- **Spend:** Claude $0.1970 (research $0.1408, web search step $0.0056, answer $0.0506), Voyage $0.0020 (6 requests), Exa $0. Together $0.1991, which is what `spend_report.py --env live` reads for the day: 1 run started, no stops. 190,474 input tokens, 145,198 of them from cache; 4,580 output.
- **Through goodnight** (the API's request log): `POST /runs` 201; one event stream for 56.6 s with no reconnect; a heartbeat every 10 s, each 204. The first real stream through goodnight's block worked.
- **Kept** (keep every run): the 229 events, numbered 1 to 229 with no gap, are in `data/verification/live/live-first-_o1-_Zf7-NAjvA-xR_QDZA.jsonl` with its summary, and the rendered answer in `data/verification/live/answers/`. They were read back through the live API's `GET /runs/{id}/events` by the new `scripts/fetch_run.py`, which starts nothing and never overwrites a saved run; Atlas drops the events after 24 hours (T3.7). Local only, not committed (P4.32).

**Checked:** the counts above by script from the saved events.
**Failures:** none.
**Spend:** the run's $0.1991, on the live workspace (Anthropic) and the shared Voyage key; no spend by the main session.
**DECISION (user):** none.

## Oct 26, 2026, 04:06 CDT — Phase 5: the README and the prompts published now, and the first push (P5.5)
**Asked (the user):** four answers on the open items, then the time wording, then the wrap-up and the push. *"1. You can consult this prompt extraction script at [the previous build's repository]. You can make a copy of it, or you can write a brand new file. Generally, you can consult the [previous] project without bring its code over. 2. Don't worry about transcript clean up for now. 3. I'm overriding Phase 5 for this instance to bring our GitHub page online asap as the site is already live. We will write the README as a complete document, with no open item. When we had a chance to do a cold start test, then we will update it. 4. Sure, check them."* On the time: *"I'm thinking 2 full time days equivalent? Discuss with me."* After the measurement: *"Your recommendations are sound. One thing to note though, do NOT mention the [previous] project in this project. It's meant to be a reference within this conversation only."* *"Wrap up the repo, then push. You have my green light. If there's anything needs editing, I will come back and send you more instructions, and we will re-export prompts."* *"Oh, don't forget that we had 2 conversations working on this project, the other conversation being the frontend one."* (Square brackets mark where the other project's name or path is left out, as the user asked.)
**Came back:**
- **The time, measured, not converted.** Every measure came out above two eight-hour days, so a "days equivalent" was not used. By the rule now in `scripts/extract_prompts.py` (a prompt more than two hours after the one before starts a new sitting; a sitting runs from its first prompt to its last activity), the export at 04:06 reads four sittings, 35.0 hours, Oct 23 16:15 to Oct 26 04:06 CDT. The README calls it part time and says breaks under two hours are counted.
- **`scripts/extract_prompts.py`,** written new in this repo; the previous build's script was read for its approach only. It reads every top-level transcript of both conversations (the frontend one is the two transcripts of Oct 23 named in the script), keeps typed prompts only, deduplicates across files by ID and by time and text, redacts local paths, images, an e-mail address and the other project's name (each marked), marks pasted text, stops on a secret-like string, and writes the flag list outside the repo. The export: 304 prompts (289 main, 15 frontend), 12,062 words, 32 compactions, 75 subagents. The flag list holds 21 prompts (17 with images, 5 naming the other project, 1 with a local path; some have more than one), and a search of the published file found no local path, e-mail address or the other project's name left. **`docs/PROMPTS.md`** is published.
- **The README,** written from the log, `locked-decisions.md`, the tags and the code. A fresh Opus 5.5 agent at xhigh effort fact-checked it against the repository and found 22 discrepancies; all were fixed. Among them: quotations in Claude's prose are not copied by the API (only cited text is); the chunking examples were replaced with the ones the log records; the 10-minute limit does not stop the answer; the contract belongs to Phase 4; and the first live run was at 03:25. Counts come from scripts: the corpus counts from `check_sentences.py` and the manifest, lines of code from `git ls-files`, commits per phase from the tags, and the cost table from `replays/` and the 03:30 entry.
- **The neighbourhood, re-checked Oct 26, 2026 (item 4):**
  - Free Law Project's "Combat Hallucinations and Look Up Citations with our New API" (https://free.law/2024/04/16/citation-lookup-api/, April 16, 2024) launches the citation lookup "to combat this problem and provide a guardrail for those that are using AI to generate legal content", built on "nearly ten million citations";
  - "AI Tools and Assistants such as Claude Can Now Connect to CourtListener's Full Functionality" (https://free.law/2026/05/12/courtlistener-is-now-available-inside-claude/, May 12, 2026) says the connector is live in Anthropic's connector directory and lists "Citation verification".
  - The brief's "announced" is now "launched"; the README says "offers".
- **The other project's name** is removed from `docs/research/phase2-findings.md`'s tag line. It stays where the record cannot change: the frozen brief, and the append-only log (a route list in the 03:06 entry).
- **Tests:** the whole Python suite, 2,967 passed and 54 skipped; the Node tests, 86 passed.
- **Before the push:**
  - the whole history was searched for secret-like strings (only test fakes), absolute local paths (none outside tests that assert their absence) and `.png`/`.jpg`/`.jpeg` files (none);
  - the largest file is `data/vectors/voyage-law-2.f32` (10.1 MB);
  - the GitHub repository `NguyenTran2002/probable-clause` exists, public and empty.

**Checked:** as above.
**Failures:** the first README draft carried the 22 discrepancies above, all caught by the fact-check before commit. My first time measurement counted 337 prompts, not 304, because it did not deduplicate across transcript files.
**Spend:** none.
**DECISION (user):** P5.5, as asked above.

## Oct 26, 2026, 11:51 CDT — Phase 5: a cold start measured after 7 h 24 min idle; later sittings are not build time (P5.6)
**Asked (the user):** *"Without pinging the live site (frontend and backend alike), can you check if we're clear to do a cold start measurement?"* Then: *"Proceed with measurements. Check the logs right before, send one health check through the domain, then read the start from the logs and report."* Then: *"Log this sample as a BUILD_LOG entry, update the README's cold-start text and timeline, and commit. I want to be clear that we're not including this as development time as the app is already done and no longer being modified, but we will re-export and publish the prompts again."* After the process was laid out: *"Looks good to me. Proceed with: Fix the extractor, Log the sample, Re-export the prompts, Update README, Commit, Push."*
**Came back:**
- **The check before** (read only, 11:39 to 11:42 CDT): both services on automatic scaling, the API with a maximum of 1 instance and the web service 2, no minimum on either; the API's newest request was a `/health` at 04:17:51 CDT, with no instance start after it; no scheduled job or task in this session. Idle for 7 h 24 min.
- **The sample:** one `GET /probable-clause/api/health` through the domain, sent at 11:42:13.884 CDT (16:42:13.884 UTC), with no warm-up and no retry. Answer: 200, `ready: true`, commit `62d6272`.
  - **Caller's side:** 32.516 s in all (name lookup 0.114 s, connect 0.140 s, TLS 0.243 s, first byte 32.516 s).
  - **Cloud Run's log, UTC:**

    | Time | Event |
    |---|---|
    | 16:42:14.689 | the request arrived (0.8 s after it was sent, so the gateway was not cold; its own logs were not read) |
    | 16:42:14.740 | "Starting new instance", reason autoscaling |
    | 16:42:19.193 | the Python process started (4.5 s after the instance) |
    | 16:42:46.251 | the app ready, "api.server ready in 27.051 s" |
    | 16:42:46.254 | startup probe succeeded, 31.5 s after "Starting new instance" |

    Cloud Run's logged latency for the request was 31.337 s; about 1.2 s of the caller's time was outside Cloud Run.
  - **The app's start-up steps** (its own log), this sample against the first deploy's: corpus 5.7 s against 3.4 s; keyword index, vectors and Atlas indexes about 1.4 s against 1.0 s; "clients and the loop" **19.9 s against 7.4 s**; ready at 27.1 s against 11.8 s. That step imports `api.loop` (the Anthropic SDK and the MCP client, `api/main.py`) and builds the clients; why it took 19.9 s was not measured.
- **Other starts read from the logs,** same two lines ("Starting new instance" to "startup probe succeeded"): 15.3 s at the first deploy (02:59 CDT); **44.4 s at the 03:15 redeploy**, which the 03:19 entry recorded as not measured; **30.7 s at 04:17**, a visitor's landing after about 48 minutes idle (all its page files were revalidated with 304, a returning browser).
- **What the samples show:** two natural starts, after about 48 minutes and after 7 h 24 min idle, were within a second of each other (30.7 s and 31.5 s). Two samples are too few to call a trend; the brief expects long idles to run longer. The page's "taking longer than usual" message comes at 90 s (`LONG_WAIT_S`) and its give-up at 300 s, so a 32 s start shows the counter only.
- **Stray traffic seen:** the 04:17 landing above, and at 09:44 CDT a `GET /api` on the web service's own address (404).
- **No cloud change.** No scaling change, no deploy, no goodnight change. The instance is warm and idles out on its own.
- **The prompts extractor** (`scripts/extract_prompts.py`) was fixed. A dry run for this re-export showed it would end the last build sitting at the 11:38 reopening of this session, reading 19.4 hours and a build total of 42.7. A sitting now ends at the last record reached from its last prompt without a gap over two hours, never past the next sitting; and the build ends at the first push (commit `4ad0ea2`, 04:07:44 CDT): a sitting that starts after it is listed as after the build and never added to the build's prompts, words or hours. With the fix the build is 304 prompts, 12,062 words, **35.1 hours** in four sittings (the 35.0 in the P5.5 entry and the README was the export at 04:06, before the wrap-up ended at 04:08; this entry corrects it, and that entry is not edited). This measurement is a fifth sitting, after the build.
- **The README:** the cold-start text now gives all four starts, and the timeline gains a row for this measurement with no hours counted; the build time reads 35.1 hours.

**Checked:** the sample's figures from the caller's output and Cloud Run's logs (UTC read against the CDT clock); the build figures by running the extractor into the scratchpad before the real export.
**Failures:** the extractor's sitting-end rule (above), found by a dry run before anything was published; my first in-memory test of the fix let one sitting run into the next, a mistake in the test only, corrected before the real change. For the health check's reply I used a temporary file in `/tmp` rather than the scratchpad; it was deleted at once.
**Spend:** none. `/health` calls no paid service.
**DECISION (user):** P5.6, as asked above.

## Oct 26, 2026, 12:22 CDT — Phase 5: the README's opening points to the process; the build section expanded (P5.7)
**Asked (the user):** *"I want to modify the current version to highlight the process more and call attention to it much earlier"*, from a reference README the user named (read for its structure only; nothing copied, not named here). Then: *"The "Here for the process?" section is too long. It's meant to be a pointer with some hook information but not laying out everything in the interest of space."* Then: *"Let's take out the "and one stretch run overnight while the author slept" part at the very beginning. We still leave it in the full body below as I think an engineer understanding how to build with claude code will see how well the overnight run is regulated and carried out. However, having that part at the very beginning can trigger an HR recruiter who might not be that familiar with Claude Code."* Then: *"Everything looks good to me. You'll just need to re-export the prompt (including this one), update some counters here and there, commit, then push."*
**Came back:**
- **The opening:** the affiliation line moved under the title in italics; the not-legal-advice statement is its own paragraph; a one-sentence "Here for the process?" callout (35.1 hours over four sittings, 304 prompts, every one published) links to the build section.
- **The build section,** still at the end:
  - "The numbers" gains three rows, each counted by a script: 358 commits up to the first push (`git rev-list --count 4ad0ea2`); 134 entries in `locked-decisions.md` and 198 in `BUILD_LOG.md` up to the first push; 75 subagents.
  - "How the work was run" opens with the author's *"Zoom out and discuss this holistically with me first before we proceed."* and gains points on discussing then locking (35 of the 304 build prompts use "discuss", 10 invite a push back, 23 open a Phase 3 topic), the two conversations in one folder, the subagent model and effort rule (stated as a rule, since 23 earlier subagents ran at default effort), the overnight run of Oct 25 (01:27 to 02:50, 9 commits, no paid calls, nothing pushed), planned compactions, the priced paid tests ($0.5383 of $3.00 and 3 of 20 searches in Wave 3), and the page's 29 review rounds.
  - The timeline gains a row for this sitting, after the build; "The record" links the overnight plan and the frontend log.
- **The prompts,** re-exported: the build is unchanged (304 prompts, 12,062 words, 35.1 hours, four sittings); after the build, 8 prompts in one sitting, 0.7 hours so far. 22 prompts carry a redaction (the 21 before and one from this sitting); the flag list was read and no local path, e-mail address or the previous project's name is in the file.
- **The extractor:** compactions are now split at the build's end, like prompts and hours: 32 in the build, 1 after it (this sitting's).

**Checked:** every new count by script (the prompts file for prompt counts, git, the log, `locked-decisions.md`); each "Open topic" prompt's time falls in Phase 3; no banned words, em dashes, "the user", local paths or the previous project's name in the README; every relative link resolves.
**Failures:** a first count of prompts saying "open to" (32) was mostly "Open topic"; it was dropped before the draft was shown.
**Spend:** none.
**DECISION (user):** P5.7, as asked above.

## Oct 27, 2026, 11:35 CDT — Phase 5: the waking step unnumbered, and replaced by the first tool step (P5.8)
**Asked (the user),** after a cold-start run on the live site: *"I noticed that "Starting the research server" is also numbered 1 as well."* *"We should have this step to be not-numbered for consistency."* *"Preferably, as soon as the first tool call is in, replace Starting the research server with it."*
**Came back:**
- **The cause:** the step log is three lists (`web/js/steps.js`): the waking step, research's steps, and the run's last step. Each `.steps` list resets the CSS counter, so the waking step was 1 and research's first step was 1 again. The run's last step (a refusal, or an end the visitor is told about, such as "interrupted") had the same defect: it showed 1 after research's steps.
- **The fix:**
  - `style.css`: the waking step and the run's last step keep their mark on the rail with no number; research's steps alone are counted.
  - `steps.js`: the waking step is removed when the first tool step shows. While Claude's first call is thinking, the waking step stays, done and unnumbered, above "Claude is thinking" (1); the first search then takes its place. If the server never starts, the waking step stays with its "did not start" line, as before.
  - The run's last step unnumbered is the main session's call, the same defect as the one reported; it is one CSS selector to undo.
- **Not deployed and not pushed.** The live site still numbers the waking step until a redeploy, on the user's green light.

**Checked:** on the mock (8765), with a cold start of 8 s and events at a fifth of their speed: the waking step pulsing with no number; then done, unnumbered, above "Claude is thinking" with 1; then removed as "Searching by meaning" showed with 1. A refused run (`busy`): its last step unnumbered. The page's Node tests: 86 passed.
**Failures:** none.
**Spend:** none.
**DECISION (user):** P5.8, as asked above.
