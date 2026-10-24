# Locked decisions

The index of decisions in force, made after the kickoff brief (`PROBABLE_CLAUSE_KICKOFF.md`, frozen at the first commit). **`BUILD_LOG.md` is the authoritative record of every decision and wins over this file on any conflict; this file wins over the brief** (P2.12). Each entry names the log entry that records it. A conflict is fixed by a superseding entry here, never by editing the log, and a new decision is written to both files in the same commit.

Numbering: `P<phase>.<n>` for decisions made in Phases 0 to 2 and 4 to 5; `T<topic>.<n>` for the Phase 3 architecture conversation. A superseded decision stays in place, marked superseded, with its replacement entered below it. Dates are America/Chicago.

---

## Phase 0: Bootstrap

### P0.1 Stack: Python 3.13 via uv, FastAPI on uvicorn

- **Decision:** Brief §2, Claude's default 1, is locked: Python 3.13 managed with uv, FastAPI served by uvicorn. The frontend stack is still chosen in Phase 3.
- **User's words:** *"On the default stack, I want Python 3.13 with uv and fast api. Lock this. (Open to future adjustment in case something goes wrong, but that would be highly unlikely.)"*
- **Note:** Locked, with the user open to adjusting it only if something goes wrong. Any change goes through the user and is entered here as a superseding decision.
- **Date:** Oct 23, 2026
- **Log:** `BUILD_LOG.md`, "Oct 23, 2026, 16:23 CDT — Phase 0: Bootstrap"

### P0.2 No screenshots or images committed to the repo — SUPERSEDED by P0.4

- **Decision:** Brief §2, Claude's default 7, carries over in the user's wording: no screenshots or images are ever committed to this repository. `.gitignore` excludes common image formats to enforce it.
- **User's words:** *"On screenshots or images, we will never commit any to the repo, lock that too."*
- **Open for Phase 3:** whether a favicon or a wordmark file counts as an image under this rule. Until the user says otherwise, none is committed, and the wordmark is set in text and CSS.
- **Date:** Oct 23, 2026
- **Log:** `BUILD_LOG.md`, "Oct 23, 2026, 16:23 CDT — Phase 0: Bootstrap"

### P0.3 A second Claude Code session for the mock frontend, in the same checkout

- **Decision:** In Phase 4, the frontend is built by a **second Claude Code session** working on a mock frontend, instead of the frontend subagent named in brief §3. Both sessions work in the same folder and on the same branch (no worktree). The organization, as proposed by Claude and approved by the user:
  1. **File ownership, one writer per file.** The main session owns the backend, corpus, `scripts/`, `tests/`, deploy, `pyproject.toml`/`uv.lock`, and every shared document. The frontend session writes only under `web/` and its own notes file. The interfaces contract, CLAUDE.md, the brief and this file are read-only to it.
  2. **The mock is built against the interfaces contract only**, with a machine-checkable event schema (`contracts/events.schema.json` or similar) that both the backend's event tests and the frontend's mock fixtures validate against. Contract changes have one writer, the main session, which versions them and tells the frontend session. Mock fixtures share the replay format, and cover waking, disconnect and reconnect, abandoned and interrupted runs, rejections, the step limit, verifier flags and the daily cap.
  3. **Shared documents have one writer, the main session.** The frontend session keeps its own append-only `docs/sessions/frontend-log.md` (same entry format, headings from `date`, user decisions marked `DECISION (user)` with the user's words). The main session folds those into `BUILD_LOG.md` and this file under its own timestamped entries.
  4. **Git in a shared working tree:** each session commits only its own paths by name (`git commit -- <paths>`), never `git add -A` or `git add .`; never `git stash`, `reset`, `checkout -- .`, or a branch switch; on `index.lock`, wait and retry, never delete it; only the main session tags phase ends, after the frontend session is idle and committed; separate dev-server ports; only the main session touches `.venv`.
  5. **Start condition:** after art direction is locked (Phase 3) and contract v1 is committed (start of Phase 4). The details go in the Phase 4 build plan, which the user approves before the build starts.
- **User's words:** *"In a future phase where decisions on the backend are settled and this claude code session is on implementation, I'd want to be iterating on a mock frontend with a second claude code session to cut time and be more efficient."* On the proposal: *"The plan looks sound to me."*
- **Date:** Oct 23, 2026
- **Log:** `BUILD_LOG.md`, "Oct 23, 2026, 16:23 CDT — Phase 0: Bootstrap"

### P0.4 Image block narrowed to PNG and JPEG (supersedes P0.2)

- **Decision:** The no-images rule covers `.png`, `.jpg` and `.jpeg` files only; those are never committed. The project's own `.svg` and `.ico` files (for example a favicon or wordmark) may be committed. This also settles the favicon and wordmark question P0.2 left open for Phase 3. `.gitignore` blocks exactly those three formats.
- **User's words:** *"Correction: for image blocking, only count jpeg, jpg, and png. I wouldn't have any image in any other format. The project itself might use svg and ico."*
- **Date:** Oct 23, 2026
- **Log:** `BUILD_LOG.md`, "Oct 23, 2026, 16:54 CDT — Phase 1: Corpus (before the pull: checks and licensing)"

### P0.5 Transcript retention left at the default

- **Decision:** `cleanupPeriodDays` stays unset (Claude Code's default cleanup, about 30 days). The agent does not change it.
- **User's words:** *"Transcript retention, leave cleanupPeriodDays alone for now. This project will be done in 2 days."*
- **Date:** Oct 23, 2026
- **Log:** `BUILD_LOG.md`, "Oct 23, 2026, 16:54 CDT — Phase 1: Corpus (before the pull: checks and licensing)"

---

## Phase 1: Corpus

### P1.1 Exhaustive corpus verification, scripts plus independent subagents

- **Decision:** Phase 1 ends with exhaustive verification, not the spot check brief §4.5 asks for. Scripts check everything mechanically: every cleaned opinion aligned word by word against the official PDF text with every difference listed; every opinion in the Court's lineup present after splitting, with correct boundaries; every metadata field compared against the official text. Opus subagents, each given a batch of cases and none told the main session's conclusions, judge every listed difference (cleaning artifact, real difference, or OCR noise in the official PDF) and check opinion type, author and joiners. One further subagent builds its own case list from scratch and compares it with the corpus, alongside the citation-graph filter check (§4.7).
- **User's words:** *"At the end of Phase 1, subagents to verify the corpus exhaustively will be crucial here. We also want to pull all relevant metadata for each corpus item."* On the design: *"Verification design with subagents looks good to me."*
- **Date:** Oct 23, 2026
- **Log:** `BUILD_LOG.md`, "Oct 23, 2026, 16:54 CDT — Phase 1: Corpus (before the pull: checks and licensing)"

### P1.2 Pull all metadata; keep `scdb_decision_direction` out of the manifest and the prompt

- **Decision:** Every field CourtListener holds for each docket, cluster and opinion is cached raw (gitignored). A curated manifest carries what the app uses. The Supreme Court Database's `scdb_decision_direction` (a liberal or conservative coding of each outcome) stays in the raw cache only: never in the manifest, the system prompt, a tool result, or the page, because it would break the political-heat guardrail (brief §2, "never says whether the Court was right").
- **User's words:** *"We also want to pull all relevant metadata for each corpus item."* On the exclusion: *"Keeping scdb_decision_direction out is a good catch."*
- **Date:** Oct 23, 2026
- **Log:** `BUILD_LOG.md`, "Oct 23, 2026, 16:54 CDT — Phase 1: Corpus (before the pull: checks and licensing)"

### P1.3 The update check shows Claude's synthesis plus source links, never Exa's content

- **Decision:** Exa stays as the update-check search (brief §2 unchanged). On the page and in replays, the update-check band shows **Claude's own synthesis** of what the search found, plus a **link to each source** (title, URL, published date). It never shows page text, highlights, or Citations `cited_text` drawn from web results. Internally, Citations still mark which sentences are grounded in a web result; on screen, such a sentence links to its source instead of quoting it. This changes how brief §6.3 and §6.4 display results. Every parameter Claude chose is still shown, and the honesty label still applies.
- **Why:** Exa's Terms §4.2(a), read literally, require written permission to display, copy or publish information obtained through the service (`docs/research/licensing.md` §4). Synthesis plus links removes any republication of third-party web text. It does not by itself satisfy the literal clause ("modify", "create derivative works from" are also listed), so the user is emailing Exa (hello@exa.ai, the address named in the terms) for written permission covering public display and stored replays. If no answer arrives before launch, the project proceeds with this design and the remaining risk is logged as accepted by the user.
- **User's words:** *"Exa, can we only display what Claude synthesize after doing the search? This will avoid directly copying and pasting Exa's returning content."* Then: *"Draft the Exa email and give me an email address to send it to. Hopefully we'll get a response back soon. Otherwise, we proceed as normal."* and *"I lock all three decisions here with you"*.
- **Date:** Oct 23, 2026
- **Log:** `BUILD_LOG.md`, "Oct 23, 2026, 17:11 CDT — Phase 1: Corpus (decisions on licensing; prep for compaction and the second session)"

### P1.4 Anthropic Usage Policy: the case rests on what the tool does

- **Decision:** Probable Clause proceeds as planned under Anthropic's Usage Policy. The basis, as recorded:
  - The tool does not do the high-risk activity. It explains what the Court held and shows verbatim evidence, and never applies the law to a person's own facts (brief §2). The policy published for Nov 12, 2026 excludes exactly this: "explaining what a law says … without applying it to the individual's circumstances".
  - The page discloses AI use, and tells visitors to check factual assertions independently (Commercial Terms §D.3).
  - The README and page do **not** claim that the visitor is the "human in the loop".
- **Gap, recorded:** the policy in force until Nov 12 (since Sep 15, 2025) treats consumer-facing "legal" use as high-risk, and its full text was not found. Describing a holding could be read as legal interpretation under that wording. The user accepts this reading.
- **User's words:** *"On Anthropic's Usage Policy, we have AI disclosure and we don't provide legal advice. It's a research and citation tool, with the user is the human review piece because the project only ever present up evidence."* Then: *"I lock all three decisions here with you"*.
- **Date:** Oct 23, 2026
- **Log:** `BUILD_LOG.md`, "Oct 23, 2026, 17:11 CDT — Phase 1: Corpus (decisions on licensing; prep for compaction and the second session)"

### P1.5 Crediting Claude: plain descriptive sentences, as in the previous build

- **Decision:** Claude, Claude Code and Anthropic are named only in plain, factual sentences, following the previous build's README. Examples:
  - a README section headed "How this was built with Claude Code"
  - on the page, a sentence such as "Answers are written by Claude, Anthropic's model, through the Claude API"
  - the non-affiliation line near the name (brief default 4)

  No logos, no badge or tagline-style credit, no Claude brand colours, nothing implying endorsement. This replaces default 4's "Built with Claude" footer idea. The README's licence section says the opinion text is public domain and not covered by the code licence. Exact page wording is settled in Phase 3.
- **User's words:** *"On "Built with Claude" wording, I used this phrase in the past that is not trade marked and was just a literal sentence "How this was built with Claude Code" in the README."* Then: *"I lock all three decisions here with you"*.
- **Date:** Oct 23, 2026
- **Log:** `BUILD_LOG.md`, "Oct 23, 2026, 17:11 CDT — Phase 1: Corpus (decisions on licensing; prep for compaction and the second session)"

### P1.6 Art-direction look tests start now, in a second session the user starts

- **Decision:** The Phase 3 art-direction look tests (brief §7.3) move forward to run alongside Phase 1, in a second Claude Code session that **the user starts**, in this same folder and branch (not a worktree), under P0.3's rules. Its brief is `docs/sessions/frontend-brief.md`. This changes P0.3's start condition for look tests only. The contract-bound mock frontend still waits for contract v1 (start of Phase 4). The art direction the user picks is locked by the main session in Phase 3 as a T-entry, from the frontend session's log.
- **User's words:** *"Starting the look test in parallel with phase 1 would be nice?"* Then: *"I want to start the look test session myself, so prep the ground for that session, and let me know where to point that session to kick start it."*
- **Date:** Oct 23, 2026
- **Log:** `BUILD_LOG.md`, "Oct 23, 2026, 17:11 CDT — Phase 1: Corpus (decisions on licensing; prep for compaction and the second session)"

### P1.7 Exa emailed; build on P1.3 without waiting

- **Decision:** The user has emailed Exa for written permission (P1.3). Until the user reports an actual reply, assume none: build the update check as Claude's synthesis plus links to the sources, with no Exa content shown or stored.
- **User's words:** *"Emailed Exa. Assume no response from them until I come back with an actual response. We proceed with Claude's summary plus links to the sources."*
- **Date:** Oct 23, 2026
- **Log:** `BUILD_LOG.md`, "Oct 23, 2026, 17:17 CDT — Phase 1: Corpus (Exa follow-up, SCDB fields; ready for compaction)"

### P1.8 SCDB fields are used for verification only

- **Decision:** CourtListener clusters carry four SCDB fields: `scdb_id`, `scdb_decision_direction`, `scdb_votes_majority` and `scdb_votes_minority` (checked in CourtListener's `cl/search/models.py`, Oct 23, 2026). All four stay in the raw cache. **None goes into the manifest, the system prompt, a tool result, a replay, or the page.** Vote splits shown in the product come from each opinion's own lineup in the official text. In Phase 1 verification (P1.1), the scripts also compare those lineup-derived votes with SCDB's counts where they exist, and every disagreement goes to the verification agents to explain from the official text. This is internal checking, not republication, so no SCDB citation is owed; if the README mentions the check, it names SCDB in a sentence. P1.2's exclusion of `scdb_decision_direction` stands, and that field is not used even in verification.
- **Why:** SCDB asks to be cited with its release number, and the release CourtListener ingested is unknown. Coverage is uneven (the modern database starts in 1946; *Chatrie* may be absent). SCDB counts votes for the outcome, so a justice concurring in the judgment counts with the majority, which a naive lineup count might not; showing both would invite a visible contradiction.
- **User's words:** *"Let's use the SCDB fields as verification only."*
- **Date:** Oct 23, 2026
- **Log:** `BUILD_LOG.md`, "Oct 23, 2026, 17:17 CDT — Phase 1: Corpus (Exa follow-up, SCDB fields; ready for compaction)"

### P1.9 Corpus scope and inclusion rule: technology, three parts

- **Decision:** The corpus stays on the Fourth Amendment and technology, as in brief §2, which is unchanged. The inclusion rule (brief §4.1):

  > *Supreme Court opinions deciding (a) whether the government's acquisition of information through a surveillance or sensing technology, or from records held by a third party, is a Fourth Amendment search; (b) whether the Fourth Amendment requires a warrant before the government searches the data on a digital device; or (c) whether a physical intrusion to gather information is a search under the property-based test.*

  Part (b) brings in *Riley v. California*; part (c) brings in *Florida v. Jardines*. Within this scope, borderline cases lean toward inclusion (the user's "extra over missing"). The case list for the pull, 21 cases, each to be confirmed against CourtListener: *Olmstead*, *Goldman*, *On Lee*, *Silverman*, *Lopez*, *Katz*, *United States v. White*, *United States v. Miller*, *Smith v. Maryland*, *Knotts*, *Karo*, *California v. Ciraolo*, *Dow Chemical*, *Florida v. Riley*, *Kyllo*, *United States v. Jones*, *Jardines*, *Riley v. California*, *Grady v. North Carolina*, *Carpenter*, *Chatrie*.
- **Filter check (brief §4.7) runs in both directions:** later Supreme Court opinions that cite the core cases, and earlier ones the core cases cite most (foundations such as *Chimel*, *Robinson* or *Boyd*). The user decides each addition. *City of Ontario v. Quon* and *Berger v. New York* are pulled into the raw cache and decided there.
- **Scope is also enforced in the system prompt:** Claude judges whether a question is within the corpus's subject and uses the out-of-scope flag (brief §5.2) when it is not.
- **Verification:** P1.1 stands unchanged (every opinion verified by scripts and by subagents).
- **Where the index lives:** the user's Atlas cluster is the free tier, with about half its storage left. The corpus and its search index ship inside the API container; Atlas holds only spend counters and run events (brief §8.3, §8.4).
- **Considered and not taken: widening to every Fourth Amendment case.** CourtListener's search counted, on Oct 23, 2026, 984 Supreme Court cases mentioning "Fourth Amendment", 329 of them also quoting "unreasonable searches and seizures", and about 1,115 matching any of several phrasings. Discussed: a mention-based rule, programmatic verification with a seeded sample, scope enforced by the prompt, and the costs (a pull of about 6 hours, a corpus of an estimated 10 to 25 million tokens, an index too large for the free Atlas tier, P1.1 unaffordable at that size). The user chose to narrow.
- **User's words:** *"I'm considering widening the corpus to anything related to the Fourth Amendment. My take is that as a corpus, it's better to contain extra than missing something."* Then: *"Let's narrow. The goal of the project is show casing Claude Citation, and it doesn't need a huge corpus to effectively showcase that."* On the proposal: *"Thanks for incorporating my suggestions. We can lock here."*
- **Date:** Oct 23, 2026
- **Log:** `BUILD_LOG.md`, "Oct 23, 2026, 17:42 CDT — Phase 1: Corpus (inclusion rule and scope)"

### P1.10 Case-name verifier: "not in this corpus", never "does not exist"

- **Decision:** A case name the verifier (brief §5.8) cannot resolve is flagged on screen as **not in this corpus**, never as nonexistent or fabricated, since a real case outside the corpus must read differently from an invented one. The system prompt tells Claude to name only cases it cites from the corpus. Exact wording is settled in Phase 3.
- **User's words:** *"Thanks for incorporating my suggestions. We can lock here."*
- **Date:** Oct 23, 2026
- **Log:** `BUILD_LOG.md`, "Oct 23, 2026, 17:42 CDT — Phase 1: Corpus (inclusion rule and scope)"

### P1.11 Text source of record per case; official PDFs downloaded

- **Decision:** Each case's text comes from the best public-domain copy of the U.S. Reports text:
  - **1928 to 2001, plus *Goldman* and *Berger*:** CourtListener's Lawbox copy (clean text, U.S. Reports page markers only), split on the opinion headings, with CourtListener's Harvard split as a check. The Harvard scan's OCR misreadings ("evidehce", "dan riot" for "can not") cannot be fixed under brief §4.5, so it is not the text of record.
  - ***Jones* and *Quon*:** CourtListener's Harvard scan of the U.S. Reports, already split, with U.S. pages.
  - ***Jardines*, *Riley*, *Grady*, *Carpenter*:** the official GovInfo PDF of the final U.S. Reports (born-digital). CourtListener holds only the slip opinion and a scan of West's Supreme Court Reporter for these.
  - ***Chatrie*:** the Court's slip opinion (not yet on GovInfo), labelled subject to formal revision.

  CourtListener stays the source of metadata and the citation graph. Decision dates come from the official text, since CourtListener's `date_filed` is wrong for at least *Ciraolo* and *Florida v. Riley*. CourtListener copies scanned from the Lawyers' Edition or West's Supreme Court Reporter are excluded. This partly changes brief §2's corpus-source row: for four cases the official PDF is the source, not only the cross-check.
- **Official PDFs:** the user approved downloading 23 files (about 71 MB) once, with the full list: 22 from GovInfo (`USREPORTS-<vol>-<page>.pdf`) and *Chatrie*'s slip opinion `25-112_0am4.pdf` from supremecourt.gov. Kept under `data/raw/pdfs/`, gitignored.
- **User's words:** *"Approved: use the text-source plan as proposed, and download the 23 official PDFs listed."*
- **Date:** Oct 23, 2026
- **Log:** `BUILD_LOG.md`, "Oct 23, 2026, 18:26 CDT — Phase 1: Corpus (pull, first tests, text sources, cleaning)"

### P1.12 *Jones* and *Quon* take their text from the official PDF (amends P1.11)

- **Decision:** *Jones* and *Quon* use the official GovInfo PDF of the U.S. Reports, like *Jardines*, *Riley*, *Grady* and *Carpenter*, not CourtListener's Harvard scan. The Harvard copies proved to be OCR with misreadings (about 170 to 250 small differences per case against the official text, such as "HH" for the section numeral "I", "swpra", "ease" for "case"); the official PDFs for both are born-digital, with ligature characters and soft hyphens intact. The rest of P1.11 stands.
- **User's words:** *"Jones and Quon take their text from the official PDF -> This is a more reliable and authoritative way."*
- **Date:** Oct 23, 2026
- **Log:** `BUILD_LOG.md`, "Oct 23, 2026, 19:52 CDT — Phase 1: Corpus (verification round 1, filter check, rework)"

### P1.13 The syllabus is never part of the citable corpus

- **Decision:** The Reporter of Decisions' syllabus is left out of the citable corpus entirely, for every case, since it is not the Court's text ("no part of the opinion of the Court"). Only opinions (majority, plurality, concurrences, dissents, and Justices' statements) are citable. This supersedes the plan, in `docs/research/licensing.md` and the frontend brief, to keep the syllabus as a labelled passage.
- **User's words:** *"Syllabus -> Strictly leave out of the citable corpus because they aren't from the Court."*
- **Date:** Oct 23, 2026
- **Log:** `BUILD_LOG.md`, "Oct 23, 2026, 19:52 CDT — Phase 1: Corpus (verification round 1, filter check, rework)"

### P1.14 Filter-check additions

- **Decision:** From the two-way filter check (brief §4.7, P1.9; `scripts/filter_check.py`), ten cases join the corpus as core cases:
  - within the rule: *United States v. Lee*, 274 U.S. 559 (1927); *Hester v. United States*, 265 U.S. 57 (1924); *Oliver v. United States*, 466 U.S. 170 (1984); *United States v. Dunn*, 480 U.S. 294 (1987); *United States v. Jacobsen*, 466 U.S. 109 (1984);
  - borderline, included on "extra over missing": *California v. Greenwood*, 486 U.S. 35 (1988); *Ex parte Jackson*, 96 U.S. 727 (1878); *California Bankers Assn. v. Shultz*, 416 U.S. 21 (1974); *Berger v. New York*, 388 U.S. 41 (1967);
  - foundational, outside the rule's text: *Boyd v. United States*, 116 U.S. 616 (1886), cited by 17 of the 21 core cases.

  Left out: *City of Ontario v. Quon* and every other candidate (among them *Hoffa*, *Lewis*, *Keith*, *Osborn*, the dog-sniff cases *Place* and *Caballes*, *Patel*, and the exclusionary-rule, standing and general warrant cases). *Quon* stays in the raw cache only. The independent case-list agent (P1.1) also proposed *Clinton v. Virginia*, 377 U.S. 158 (1964), after this decision was offered; it is not included.
- **User's words:** *"Approve your recommended additions (the five squarely in the rule, plus Greenwood, Ex parte Jackson, Shultz, Berger and Boyd; leave out Quon and the rest)."*
- **Date:** Oct 23, 2026
- **Log:** `BUILD_LOG.md`, "Oct 23, 2026, 19:52 CDT — Phase 1: Corpus (verification round 1, filter check, rework)"

### P1.15 *Kyllo* takes its text from the official PDF (amends P1.11)

- **Decision:** *Kyllo*'s official GovInfo PDF is born-digital, so, by P1.12's reasoning, it replaces the Lawbox copy as the text of record. The Lawbox copy serves as the reference copy for repairs.
- **User's words:** *"Also switch Kyllo to its official PDF."*
- **Date:** Oct 23, 2026
- **Log:** `BUILD_LOG.md`, "Oct 23, 2026, 19:52 CDT — Phase 1: Corpus (verification round 1, filter check, rework)"

### P1.16 Lawbox wording errors are corrected where two independent scans of the print agree

- **Decision:** The P1.1 verification agents confirmed wording errors in the Lawbox copies against the page images (for example *Olmstead* "We have to chose" for "choose", *Lopez* "notwithstanding are the verdict", *Miller* "400 U. S. 322" for 409). The build corrects a Lawbox word wherever the official PDF's text layer and CourtListener's Harvard scan, two independent readings of the printed page, agree with each other against Lawbox. Every correction is logged with its page, and a second round of verification agents checks every applied correction against the page image, since two OCRs can share a misreading. Corrections an agent confirms that the two scans cannot make (punctuation, omitted rows of omission points) go in a reviewed corrections table applied by the build.
- **User's words:** *"correct Lawbox where both scans agree and have agents review every correction"*
- **Date:** Oct 23, 2026
- **Log:** `BUILD_LOG.md`, "Oct 23, 2026, 19:52 CDT — Phase 1: Corpus (verification round 1, filter check, rework)"

### P1.17 Quotation marks and apostrophes are straight throughout

- **Decision:** Every quotation mark and apostrophe in the corpus is normalised to straight ASCII (`'` and `"`), whatever the source (Lawbox's straight quotes and backticks, the fonts that encode single quotes as a backtick and `'`, and curly quotes). The page's text-status note says quotation marks are normalised.
- **User's words:** *"straight quotation marks throughout"*
- **Date:** Oct 23, 2026
- **Log:** `BUILD_LOG.md`, "Oct 23, 2026, 19:52 CDT — Phase 1: Corpus (verification round 1, filter check, rework)"

### P1.18 Majority joiners come from the Reporter's lineup where it is printed

- **Decision:** A majority opinion's heading names no joiners. Where the volume prints the Reporter's lineup paragraph (roughly the 1970s on), the majority's joiners are taken from it, partial joins noted. Where no lineup is printed, the majority's joiners are recorded as not printed, not inferred. Separate opinions keep their joiners from their own headings.
- **User's words:** *"majority joiners from the Reporter's lineup where printed"*
- **Date:** Oct 23, 2026
- **Log:** `BUILD_LOG.md`, "Oct 23, 2026, 19:52 CDT — Phase 1: Corpus (verification round 1, filter check, rework)"

### P1.19 *Goldman*: Stone and Frankfurter's statement is a concurrence in the judgment

- **Decision:** The printed heading ("MR. CHIEF JUSTICE STONE and MR. JUSTICE FRANKFURTER:") names no role. They would overrule *Olmstead* and agree with its dissents, but do not dissent; the statement is typed as a concurrence in the judgment.
- **User's words:** *"Goldman's Stone and Frankfurter statement as concurrence in the judgment."*
- **Date:** Oct 23, 2026
- **Log:** `BUILD_LOG.md`, "Oct 23, 2026, 19:52 CDT — Phase 1: Corpus (verification round 1, filter check, rework)"

### P1.20 *Clinton v. Virginia* joins the corpus

- **Decision:** *Clinton v. Virginia*, 377 U.S. 158 (1964) (per curiam: a listening device stuck into a wall is a search, under *Silverman*), proposed by the independent case-list agent (P1.1) after P1.14, joins the corpus as a core case. Its official PDF is downloaded with the user's approval, and it is verified like the other additions.
- **User's words:** *"Add Clinton v. Virginia: pull it, download its official PDF (approved), build and verify it."*
- **Date:** Oct 23, 2026
- **Log:** `BUILD_LOG.md`, "Oct 23, 2026, 20:14 CDT — Phase 1: Corpus (verification round 2; Clinton added; corrections policy changed)"

### P1.21 Only agent-confirmed corrections change the text (amends P1.16)

- **Decision:** The automatic two-scan correction of P1.16 no longer changes the corpus. Verification round 2 found about half of its corrections wrong (roughly 26 right, 22 wrong): the official text layer and the Harvard scan often share a misreading (O read as 0, A1 as Al, III as Ill, Amdt. as Arndt, accents and "œ" dropped, a paragraph-opening "I" deleted, small capitals and line-end hyphens split). The build applies only the reviewed corrections table (`scripts/corrections.json`), and every entry in it is a correction a verification agent confirmed against the page image. The two-scan check stays as a report of candidates. A scripted comma and period check (Lawbox against the official text and Harvard) is added as a report, and a final agent pass reviews what changed.
- **User's words:** *"I want to apply only agent-confirmed corrections from the reviewed table; keep the two-scan check as a report of candidates, not an automatic change. Run the comma/period check and the final agent pass you described."*
- **Date:** Oct 23, 2026
- **Log:** `BUILD_LOG.md`, "Oct 23, 2026, 20:14 CDT — Phase 1: Corpus (verification round 2; Clinton added; corrections policy changed)"

### P1.22 Corpus approved and frozen; four points settled

- **Decision:** The Phase 1 corpus is approved as built after the final agent pass: 32 core cases, 102 opinions. Four points settled with it:
  1. *Boyd*'s quoted caption on p. 618 ("The United States of America against E. A. B., 1–35, Thirty-five Cases of Plate Glass.") is included, as a quote paragraph, through the corrections table.
  2. The cleaned corpus (`data/corpus/`) is committed, with source attribution (brief default 3; `docs/research/licensing.md`). Raw API responses, the PDFs and the verification output stay uncommitted.
  3. Printed typos: a misspelled word stays as printed ("dislosures", "throroughfares"); a stray printed mark that Lawbox omits stays omitted ("273 U S. 28" kept as "U. S.", "of.crime" as "of crime").
  4. In the older (Lawbox) cases, an en dash printed between numbers or in section numbers may appear as a hyphen ("§ 813-a"), as in page ranges; the source does not distinguish them and they cannot be restored reliably.
- Recorded with it, the main session's convention for page breaks (no user decision needed): a word divided across a page turn is on the page where it begins.
- **User's words:** *"Approved. Include Boyd's p.618 caption as a quote paragraph, commit the cleaned corpus with attribution (default 3), and accept the two smaller points as recommended. Go ahead with the freeze."*
- **Date:** Oct 23, 2026
- **Log:** `BUILD_LOG.md`, "Oct 23, 2026, 21:17 CDT — Phase 1: Corpus (final pass; approved and frozen)"

---

## Phase 2: Research

### P2.1 Model: Sonnet 5.5 at high effort

- **Decision:** The model is `claude-sonnet-5-5` at high effort (brief §2, Model row). Raising the effort or considering Opus happens only on evidence that Sonnet 5.5 at high effort cannot do what the product needs, and only with the user. Phase 2 confirms how effort is set for this model in the current API.
- **User's words:** *"For model check, let's lock Sonnet 5.5 at high effort and only increase the effort or ponder Opus if we see evidence that Sonnet 5.5 at high cannot handle what we want. My rationale being the demo has tight scope and machinery tasks, so we don't need too much frontier intelligence. (And also my wallet is not that deep as well.)"*
- **Date:** Oct 24, 2026
- **Log:** `BUILD_LOG.md`, "Oct 24, 2026, 13:59 CDT — Phase 2: Research"

### P2.2 Exa plan and prices come from the user's console

- **Decision:** The project is on Exa's free tier, with $10 of credits a month. The prices, read from the user's Exa console on Oct 24, 2026, are authoritative and are not re-checked: search $4 (Lite), $7 (Auto) or $12 (Deep) per 1,000 requests, plus $1 per 1,000 additional results beyond 10; content $1 per 1,000 pages; answer $5 per 1,000 answers. This replaces brief §6.5's figures. Phase 2 still checks which of these charges a search through Exa's MCP server incurs, and what happens when the monthly credit runs out.
- **User's words:** *"For Exa, screenshotted is our current plan and pricing. It's from my console so it's authoritative. (I. e. no double checking needed for these exact numbers.)"*
- **Date:** Oct 24, 2026
- **Log:** `BUILD_LOG.md`, "Oct 24, 2026, 13:59 CDT — Phase 2: Research"

### P2.3 Keep-only triage: Claude records only what it keeps, with a reason

- **Decision:** Claude's triage tool records only the passages it keeps, each with a reason. Every passage it does not keep is discarded with no reason and no call. This replaces brief §5.2's `review_passages` (keep or discard, each with a reason) and drops the discard reasons of brief §1 and §3. How passages are surfaced to Claude and how Claude queries the corpus stay open for the Phase 3 architecture conversation, where the user reviews them in full and gives the green light before anything is locked.
- **Why:** The corpus search will return more false positives than true positives, so asking Claude to account for each rejection would burden the loop.
- **User's words:** *"Instead we should expose only keep tool, with sources not acted on by Claude simply discarded. This will save a round and arguably make the pipeline more accurate now that it doesn't have to taint its history with meaningless not keep tool calls."* Then: *"On not keeping passage without providing a reason, it's attuned for the nature of this task. Claude is searching thru a search feature, and the search feature (not yet fully designed nor implemented) will by nature return more false positives than true positives. Thus, we don't want to burden the system with what not to keep, only what is kept would want a reason. Everything else discarded."*
- **Date:** Oct 24, 2026
- **Log:** `BUILD_LOG.md`, "Oct 24, 2026, 13:59 CDT — Phase 2: Research"

### P2.4 Claude cites the Phase 1 corpus text, not the official PDFs

- **Decision:** The citable source given to Claude is the cleaned, verified corpus text from Phase 1 (P1.22), not the official PDFs handed to the Citations feature for the server to parse and chunk. The reasons, from Phase 1's findings: the PDFs' text layers carry OCR misreadings, line-break hyphens and running heads that would appear inside quotations; a PDF mixes the syllabus (excluded, P1.13) with several opinions that begin mid-page, so opinion type, author and joiners would not attach to a citation; and PDF pages are billed as text and image. Each passage keeps its official page numbers. Whether a citable unit is a paragraph or a sentence is settled in Phase 3.
- **User's words:** *"On sticking with Phase's 1 work and finding, you have my green light here."*
- **Date:** Oct 24, 2026
- **Log:** `BUILD_LOG.md`, "Oct 24, 2026, 13:59 CDT — Phase 2: Research"

### P2.5 Research plan approved; agents run on Sonnet 5.5 at high effort or above, never max

- **Decision:** The Phase 2 research plan is approved as laid out: six read-only research agents in parallel, paid checks run by the main session from committed `scripts/probe_*.py` (Anthropic ceiling $2, on the product's model and effort, P2.1; Exa at most 20 requests from the free credit), every quoted source re-checked by `scripts/verify_quotes.py` and an agent not told the conclusions, findings in `docs/research/phase2-findings.md`. Subagents run on Sonnet 5.5 at high effort at the least; extra-high effort is allowed for parts that need it; max effort is never used. Opus is not used for subagents in this phase.
- **User's words:** *"I don't want us to default to Opus always in the plan here, already I saw that more machinery parts of the plan would only need Sonnet."* Then: *"The research plan looks good to me. One note though, use Sonnet 5.5 at high effort in the minimum. You're allowed to set extra high effort for certain parts of the plan. However, you're barred from using Sonnet 5.5 at max effort."*
- **Date:** Oct 24, 2026
- **Log:** `BUILD_LOG.md`, "Oct 24, 2026, 13:59 CDT — Phase 2: Research"

### P2.6 No per-visitor run limit; spend is capped by cost only

- **Decision:** The per-visitor limit of brief §8.2 ("3 a day, by client IP") is removed. Live research is limited only by the global daily cost cap and the monthly cost cap. Consequences recorded with it: brief §8.5's "counts as one of the visitor's daily runs" for an abandoned run no longer applies (its spend still counts toward the cost caps), and one visitor can use the whole day's budget, after which live research pauses for everyone until the next day while replays stay available (brief §7.2).
- **User's words:** *"On cap on runs per visitor, uncap it. We will control with daily cost cap and monthly cost cap only. I don't want a focused visitor getting blocked from trying out the demo."*
- **Date:** Oct 24, 2026
- **Log:** `BUILD_LOG.md`, "Oct 24, 2026, 13:59 CDT — Phase 2: Research"

### P2.7 Run limits kept from brief §8.2

- **Decision:** The remaining starting values of brief §8.2 stand after Phase 2's measurements (`docs/research/phase2-findings.md` §3: two runs of 4 and 6 steps, $0.14 and $0.24 of Claude): a step limit of 12 tool rounds plus the final composition call; a per-run ceiling of 400K input and 20K output tokens; at most 3 update searches per run, results clamped to 10; a global daily cap of $10; a monthly cap of $60. Every counter persists in Atlas. P2.6 removed the per-visitor limit.
- **User's words:** *"Stick with these limits: 12 steps, 400K input and 20K output tokens per run, 3 update searches, the $10 daily cap and the $60 monthly cap."*
- **Date:** Oct 24, 2026
- **Log:** `BUILD_LOG.md`, "Oct 24, 2026, 13:59 CDT — Phase 2: Research"

### P2.8 Exa's server-side retries are accepted

- **Decision:** Exa's hosted MCP server retries Exa's own 500, 502, 503 and 504 responses twice, and this cannot be turned off (`docs/research/phase2-findings.md` §4). That is accepted as an exception to brief §10.7's "a paid request is never retried automatically", which still binds our own code: our backend never retries a Claude or Exa call itself.
- **User's words:** *"Exa's server-side retries are allowed."*
- **Date:** Oct 24, 2026
- **Log:** `BUILD_LOG.md`, "Oct 24, 2026, 13:59 CDT — Phase 2: Research"

### P2.9 The name Probable Clause is kept

- **Decision:** The name stays (brief §2). The research found no product, company or repository by that name, and the main domains look unregistered; the trademark registry could not be read by the research and is the user's to check by hand. The user holds the GitHub repository `NguyenTran2002/probable-clause` (empty, reserved), and the frontend will be served at `nguyennhattran.com/probable-clause`, so no separate domain is needed.
- **User's words:** *"Probable Clause as a name is fine. I already reserved an empty github repo at https://github.com/NguyenTran2002/probable-clause. Additionally, the final front end will be served at nguyennhattran.com/probable-clause so there's no conflict in domain naming there."*
- **Date:** Oct 24, 2026
- **Log:** `BUILD_LOG.md`, "Oct 24, 2026, 13:59 CDT — Phase 2: Research"

### P2.10 Disconnect detection is a Phase 3 topic

- **Decision:** Cloud Run does not pass a browser's disconnect to the container over HTTP/1.1 (`docs/research/phase2-findings.md` §6), so the §2 Browser disconnect rule needs an explicit way to know a browser is still connected (for example a heartbeat from the page, or end-to-end HTTP/2). The rule stands; the mechanism is settled in the Phase 3 architecture conversation.
- **User's words:** *"I'm open to carrying the disconnect detection into Phase 3, unless you'd want to discuss it now."*
- **Date:** Oct 24, 2026
- **Log:** `BUILD_LOG.md`, "Oct 24, 2026, 13:59 CDT — Phase 2: Research"

### P2.11 No keyless fallback when the Exa credit runs out

- **Decision:** When the monthly Exa credit is exhausted (HTTP 402, `NO_MORE_CREDITS`), the update check shows as unavailable (brief §6.4) until the credit resets on the 1st of the month. The backend never falls back to keyless calls to the hosted server to get past the account's limit (Exa's Terms §4.2(i) and (n); the keyless tier is also limited per IP, which Cloud Run's shared outbound addresses make unreliable).
- **User's words:** *"Agreed: no keyless fallback. When the credit runs out the update check shows as unavailable until the 1st."*
- **Date:** Oct 24, 2026
- **Log:** `BUILD_LOG.md`, "Oct 24, 2026, 13:59 CDT — Phase 2: Research"

### P2.12 BUILD_LOG.md is the authoritative record; this file is its index

- **Decision:** `BUILD_LOG.md` is the authoritative record of every decision. This file stays as the index of decisions in force, ranked under the log and above the brief: the log wins on any conflict, and this file wins over the brief. Each entry names the log entry that records it (entries P0.1 to P2.11 were given a **Log** line when this was decided). A conflict is fixed by a superseding entry here, never by editing the log, and a new decision is written to both files in the same commit. Decided after the `phase-2-done` tag, before Phase 3.
- **User's words:** *"BUILD LOG is our authoritative and final source of updating decision now that the front end parallel conversation has concluded. Make sure it's up to date."* Then: *"Keep locked-decisions.md as the index of decisions in force, under BUILD_LOG: the log wins on any conflict, and each entry names its log entry. Lock it."*
- **Date:** Oct 24, 2026
- **Log:** `BUILD_LOG.md`, "Oct 24, 2026, 14:02 CDT — Records: BUILD_LOG first, locked-decisions as its index"

---

## Phase 3: Architecture

### T1.1 Retrieval: two search tools in parallel, semantic (Voyage) and keyword

- **Decision:** Claude searches the corpus with **two tools it chooses between** during the loop: a **semantic search** and a **keyword search**. The semantic stack embeds with Voyage **`voyage-law-2`** and reranks with Voyage **`rerank-3`**. Its vectors are not held in the user's free MongoDB cluster. Both tools get filtering options for Claude (Area 1, topic 2). This replaces brief §5.2's single `search_corpus` and settles brief §5.3's open choice of retrieval method; the brief was treated as a starting point only.
- **Left open:** how keyword queries combine terms, the filters, and how results reach Claude (Area 1, topics 2 and 3); where the vectors are held (proposed: in memory in the API container).
- **User's words:** *"Currently, I'm thinking of 2 parallel search stacks: 1. RAG with Reranker supported by Voyage AI. Vector search preferably not handled by our free MongoDB cluster. 2. Keyword based search. 3. Both with filtering optionalities for Claude."* Then: *"I'm thinking 2 tools in parallel is the right choice here. For model on the RAG stack, lock voyage-law-2 and rerank-3."*
- **Date:** Oct 24, 2026
- **Log:** `BUILD_LOG.md`, "Oct 24, 2026, 14:48 CDT — Phase 3: Architecture, Area 1 (retrieval, T1.1)"
