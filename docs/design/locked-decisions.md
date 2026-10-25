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

### P0.3 A second Claude Code session for the mock frontend, in the same checkout — AMENDED by P4.28 (the main session builds and stands up the real frontend)

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

### P1.3 The update check shows Claude's synthesis plus source links, never Exa's content — AMENDED by T2.3 (Claude names each statement's sources, checked by our code; no Citations on web results)

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

### P1.6 Art-direction look tests start now, in a second session the user starts — AMENDED by P4.28 (the second session's work ends with the prototype)

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

### P1.10 Case-name verifier: "not in this corpus", never "does not exist" — AMENDED by T1.12 (the general verifier is dropped; the wording applies to the full-citation check)

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

### P2.1 Model: Sonnet 5.5 at high effort — AMENDED by T1.8 (the composition call runs on Opus 5.5 at high effort; the loop stays on Sonnet)

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

### P2.7 Run limits kept from brief §8.2 — AMENDED by P4.6 (the run's input limit is 436,000) and P4.11 (the daily cap is $15); AMENDED by P4.18 (looser per-step limits) and P4.21 (the caps admit runs; nothing reserved)

- **Decision:** The remaining starting values of brief §8.2 stand after Phase 2's measurements (`docs/research/phase2-findings.md` §3: two runs of 4 and 6 steps, $0.14 and $0.24 of Claude): a step limit of 12 tool rounds plus the final composition call; a per-run ceiling of 400K input and 20K output tokens; at most 3 update searches per run, results clamped to 10; a global daily cap of $10; a monthly cap of $60. Every counter persists in Atlas. P2.6 removed the per-visitor limit.
- **User's words:** *"Stick with these limits: 12 steps, 400K input and 20K output tokens per run, 3 update searches, the $10 daily cap and the $60 monthly cap."*
- **Date:** Oct 24, 2026
- **Log:** `BUILD_LOG.md`, "Oct 24, 2026, 13:59 CDT — Phase 2: Research"

### P2.8 Exa's server-side retries are accepted — AMENDED by T3.3 (our code retries Anthropic and Voyage calls, visibly; Exa still never)

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

### T1.1 Retrieval: two search tools in parallel, semantic (Voyage) and keyword — open points settled by T3.6 (vectors in memory; a header on the embedded text)

- **Decision:** Claude searches the corpus with **two tools it chooses between** during the loop: a **semantic search** and a **keyword search**. The semantic stack embeds with Voyage **`voyage-law-2`** and reranks with Voyage **`rerank-3`**. Its vectors are not held in the user's free MongoDB cluster. Both tools get filtering options for Claude (Area 1, topic 2). This replaces brief §5.2's single `search_corpus` and settles brief §5.3's open choice of retrieval method; the brief was treated as a starting point only.
- **Left open:** how keyword queries combine terms, the filters, and how results reach Claude (Area 1, topics 2 and 3); where the vectors are held (proposed: in memory in the API container).
- **User's words:** *"Currently, I'm thinking of 2 parallel search stacks: 1. RAG with Reranker supported by Voyage AI. Vector search preferably not handled by our free MongoDB cluster. 2. Keyword based search. 3. Both with filtering optionalities for Claude."* Then: *"I'm thinking 2 tools in parallel is the right choice here. For model on the RAG stack, lock voyage-law-2 and rerank-3."*
- **Date:** Oct 24, 2026
- **Log:** `BUILD_LOG.md`, "Oct 24, 2026, 14:48 CDT — Phase 3: Architecture, Area 1 (retrieval, T1.1)"

### T1.2 Keyword search takes structured fields; our code builds the query

- **Decision:** Claude's keyword search takes three lists, **`all_of`** (every item must appear: narrowing), **`any_of`** (at least one must appear: widening) and **`none_of`** (no item may appear). Our code compiles them into the SQLite FTS5 query; Claude never writes search syntax. Matching a quoted item as a phrase was proposed and is confirmed with topic 2. The filters both search tools share are Area 1, topic 2.
- **User's words:** *"On keyword searches, I'd want us to offer Claude flexibilities here, including searching for sources that contain multiple keywords only (for more narrowing) or searching for sources that contain any of the set of potential keywords."* Then: *"I'd decide to go with Claude writing structured fields. This would be easier on the model as well. all_of, any_of, then none_of would be suitable. Our code will build the query."*
- **Date:** Oct 24, 2026
- **Log:** `BUILD_LOG.md`, "Oct 24, 2026, 14:54 CDT — Phase 3: Architecture, Area 1 (keyword fields T1.2, read-around T1.3)"

### T1.3 Read-around on demand returns one unified block, the passage already read included

- **Decision:** Claude can ask for more context around a passage on demand. The result is the **whole requested span as one unified block, including the passage Claude has already read**, so Claude sees the passage in place rather than having to fit it into the surrounding text. The user accepts the extra tokens and time for quality and accuracy.
- **Left open (Area 1, topic 3):** how many units before and after; staying within one opinion; whether the passage's cited footnotes come with it; how units in the block carry IDs for keeping; neighbours Claude has already seen elsewhere.
- **User's words:** *"I'm also considering giving Claude an option to request more context around any given passage on demand."* Then: *"On reading around a passage on demand, I'm thinking we should return the full requested content WITH the passage Claude has already read as well so Claude see a unified block instead of having to make the mental connection that the block it already saw is fitting into the middle of this somewhere. This is a trade off to gain more quality and accuracy while incurring a bit more cost and time."*
- **Date:** Oct 24, 2026
- **Log:** `BUILD_LOG.md`, "Oct 24, 2026, 14:54 CDT — Phase 3: Architecture, Area 1 (keyword fields T1.2, read-around T1.3)"

### T1.4 Query inputs and filters for both search tools

- **Decision:** Area 1, topic 2, as reviewed by the user:
  - **Shared filters, all optional,** inside one optional `filters` object on both tools; nothing in it is required: `cases` (case keys), `decided_from` and `decided_to` (a year or a full date), `opinion_types`, `authors` (surnames, or per curiam), `none_of` (words or quoted phrases to exclude, on **both** tools; for the semantic tool our code drops matching passages before ranking), `include_footnotes` (default true). Our code treats an empty list, or a filter set to every value, as unset.
  - **`max_results`** at the top level, 1 to 10, default 8, clamped by our code.
  - **Semantic tool:** one `query`, a plain-language description of the passage sought. Our code filters, takes the closest units by vector (50, a placeholder until measured), reranks them with `rerank-3`, and returns the top `max_results`.
  - **Keyword tool:** `all_of`, `any_of`, `none_of` (T1.2) plus the filters; at least one item in `all_of` or `any_of`; a quoted item matches as an exact phrase; word forms match (porter); about 10 items per list, a placeholder. Ranked by relevance.
  - **Bad input** (an unknown case key, a bad date, both lists empty) returns an error result saying what was wrong; **no match** returns "no passages matched" with the filters repeated. The step log shows every filter Claude set.
  - **Opinion-type groups,** four instead of the eight exact types: majority; plurality; concurrence (concurring, concurring in the judgment, concurring in part, concurring in part and in the judgment); dissent. An opinion concurring in part and dissenting in part matches both concurrence and dissent. **Because this departs from the standard labels, Claude is told so:** in the filter's description; in the corpus catalog, which lists each opinion's exact type with a line saying the filter groups types; and in every result, which shows the exact type. The guidance tells Claude to describe opinions by their exact type, never by the group.
  - **Filters are presented as optional,** in the schema (one optional object), the tool description, each filter's description ("Optional. … Leave unset to …") and the system prompt. Draft tool-description wording, final text written in the build: *"Filters are optional. Use none, one, or several, as the search calls for. Each filter you set narrows the results; any filter you leave out does not restrict them. Set a filter when you know the restriction you want, such as particular cases, a span of years, or only dissents."* Build tests and Phase 5 count Claude's filter use; over-filtering is fixed in the wording.
  - **A corpus catalog in the system prompt:** each case's key, name, citation and date, and each opinion's exact type and author (contents settled with the system prompt, topic 10).
  - **Considered and left out:** sorting results by date.
- **User's words:** *"Use four groups HOWEVER, Claude must be aware of this because it's a deviation from standards."* *"with this many filter options, which is good, I want us to clearly present them as optional to Claude, so that Claude does not mistaken and try to fill every filters for all requests."* Then: *"Lock topic 2 as T1.4 with the revised wording and the four groups stated to Claude."*
- **Date:** Oct 24, 2026
- **Log:** `BUILD_LOG.md`, "Oct 24, 2026, 15:07 CDT — Phase 3: Architecture, Area 1 (query inputs and filters, T1.4)"

### T1.5 Oliver's missing "II" fixed at the start of Phase 4, confirmed by the main session (amends P1.21 for this entry)

- **Decision:** *Oliver*'s majority lacks its Part "II" heading before "The rule announced in Hester…" (p. 176); the official PDF, CourtListener's `html` copy and Harvard's scan have it, and Lawbox (the build's source) drops it. **At the start of Phase 4** the heading is added through `scripts/corrections.json`, confirmed against the page image, then the Phase 1 checks and `scripts/check_structure.py` are re-run and the change is logged (brief §4.10). **No subagent:** the main session confirms the page image itself, since this is one targeted fix and the user wants to conserve usage. This amends P1.21 ("every entry in it is a correction a verification agent confirmed against the page image") for this entry only.
- **Why not pushed back:** the entry adds a heading, not citable text, and three independent readings of the print (the official PDF's text layer, the `html` copy, Harvard's scan) already agree.
- **User's words:** *"Fix Oliver's missing II through the corrections table at the start of Phase 4, confirmed against the page image, with the Phase 1 checks and the structure check re-run and logged. However, don't send any subagent out again because this is a targeted fix. I also want to conserve usage as well. Push back otherwise."*
- **Date:** Oct 24, 2026
- **Log:** `BUILD_LOG.md`, "Oct 24, 2026, 15:47 CDT — Phase 3: Architecture, Area 1 (structure check; Oliver's heading, T1.5)"

### T1.6 How passages reach Claude (clarifies T1.3) — AMENDED by T1.9 (the composition call receives custom content documents, not search result blocks)

- **Decision:** Area 1, topic 3, as reviewed by the user:
  - **Result format:** loop tool results are text blocks, **one block per passage**, each starting with a header; not `search_result` blocks, since a tool result holding search results may hold nothing else (no "matched again" line, no read label, no no-match note). The composition call still receives `search_result` blocks. Untested in Phase 2; checked in build tests.
  - **Header:** passage ID, case, citation, decision date, exact opinion type and author, page, section label, position in the opinion. Joiners are in the corpus catalog.
  - **IDs counted from 1:** opinions (`katz-3`), paragraphs (`katz-3-p1`), footnotes numbered in order within the opinion (`katz-3-n1`). A marker links to its footnote **by order, not label** (labels repeat within an opinion, as in *Boyd*).
  - **Footnotes attached inside every passage that cites them,** after the paragraph's text, each marked with its printed label and its own ID; a `[n. <label>]` marker where it is cited, in loop text only (composition text has no markers, so citations quote the corpus exactly). Footnotes stay searchable alone; a footnote match names the paragraph that cites it. Footnotes are kept and cited separately from their paragraphs.
  - **Section headings are not passages:** search never returns them; each passage's header carries its section label, taken only from numbered headings and appendix titles; omission rows and letterhead lines typed as sections stay in reading order but never become labels. Paragraph IDs count content paragraphs only. A build-time check fails on a missing or out-of-order heading.
  - **Passages already seen** come back in searches as one "matched again" line of IDs, not resent; the result is topped up with new passages to `max_results`.
  - **`read_passages(target, before, after)`** merges direct reads with read-around (T1.3): **one target per call** (several calls may go in one turn), a passage ID or a case and U.S. Reports page (every passage on that page, each marked with its opinion); `before` and `after` 0 to 10, default 0, within the target's opinion. A read **always returns what was asked**, even if seen before. The result is one result in reading order, **each passage its own marked block** with its footnotes, the requested passage marked; this is what T1.3's "unified block" means. An unknown ID or page returns an error result giving the valid range.
  - **The corpus catalog in the system prompt** carries each opinion's ID, exact type, author, joiners, paragraph and footnote counts with ID ranges, and page range, so first and last IDs follow from the counts (7,257 tokens as drafted, `count_tokens`; cached).
  - **Cost:** under about 100K tokens of passages in the worst case T1.4 allows (estimate), against the 400K ceiling.
- **User's words:** *"Read around reach, I want to give Claude flexibility here and we trust Claude's judgement. Give it 0 to 10."* *"Also, read around wouldn't just return a blob of text, we should return all the requested passages with clear markings."* *"The intuitive way would be for us to automatically attaching footnotes to any passage that cites them, right within it"*. *"A read always returns what Claude asked for, even if it was seen before. Claude asked deliberately."* *"An unknown ID or page comes back as an error result giving the valid range."* *"just one target per call"*. *"ID counting from 1 for more natural IDs is good."* Then: *"Lock."*
- **Date:** Oct 24, 2026
- **Log:** `BUILD_LOG.md`, "Oct 24, 2026, 15:50 CDT — Phase 3: Architecture, Area 1 (how passages reach Claude, T1.6)"

### T1.7 The keep tool: batched keeps with reasons, no withdraw list — AMENDED by T1.9 (the keep reason goes in the composition document's `context`)

- **Decision:** Area 1, topic 4, as reviewed by the user:
  - **`keep_passages(keep: [{id, reason}])`,** batched. The system prompt asks Claude to keep passages as soon as it has judged them, in the same turn as its next searches, so the sources panel fills in during the run.
  - **No withdraw list.** The composition call does not cite passages it doesn't need; the sources panel shows every kept passage, some of them uncited. **Re-keeping a passage replaces its reason,** and **each kept passage's reason goes to the composition call** (in its search result's header), so a correction Claude makes in the loop reaches the writer.
  - **Only passages already shown** in an earlier search or read result can be kept; an unseen or guessed ID is refused.
  - **Reasons:** one sentence on why the passage bears on the question; over 300 characters (a placeholder) is refused with an error, never cut short.
  - **Result:** a short confirmation with the running kept count; valid items applied, invalid IDs listed with what was wrong; an error result only if nothing could be applied.
  - **A cap of 40 kept passages** at a time (a placeholder, measured in Phase 5); a keep beyond it is refused with a message saying so.
  - **Footnotes are kept on their own:** keeping a paragraph does not keep its attached footnotes (T1.6).
  - **Handed on:** whether `submit_answer` still lists kept IDs (topic 6); whether composition sees a kept paragraph's footnotes as uncitable context (topic 7); how the panel shows kept and cited, kept and not cited, and shown but never kept (Area 4).
- **User's words:** *"On withdrawal, I'm thinking the synthesis call will simply not cite passages it doesn't need. So we will see everything in the source panel, but some of them won't be cited. Would that be a good design?"* Then: *"Lock topic 4 as T1.7: no withdraw list; re-keeping replaces the reason; each kept passage's reason goes to the composition call; the rest as proposed."*
- **Date:** Oct 24, 2026
- **Log:** `BUILD_LOG.md`, "Oct 24, 2026, 16:06 CDT — Phase 3: Architecture, Area 1 (the keep tool, T1.7)"

### T1.8 The composition call runs on Opus 5.5 at high effort (amends P2.1 for composition) — AMENDED by P4.20 (composition on Sonnet 5.5 at high effort)

- **Decision:** The final composition call runs on **`claude-opus-5-5` at high effort**, for the quality of the answer the visitor reads. The research loop stays on `claude-sonnet-5-5` at high effort (P2.1). The composition model is its own setting, and **Sonnet 5.5 at high effort is compared against it later** (Phase 5, with the real composition prompt; the paid calls with the user's approval). Citations, adaptive thinking and the effort setting on Opus 5.5 are confirmed in build tests.
- **Cost, priced from Phase 2's tokens:** a run rises about 30%, to roughly $0.19 to $0.31; the $10 daily cap then covers roughly 32 to 53 runs of that kind. P2.7's limits are unchanged.
- **User's words:** *"since the composition call is pretty independent and does not get fed the same context, so caching doesn't matter, should swap to Opus at high effort?"* Then: *"Let's switch to Opus 5.5 at high for quality and we will compare again with Sonnet 5.5 at high effort later as well."*
- **Date:** Oct 24, 2026
- **Log:** `BUILD_LOG.md`, "Oct 24, 2026, 16:09 CDT — Phase 3: Architecture, Area 1 (composition on Opus, T1.8)"

### T1.9 Citation granularity: Claude cites any run of our sentences, sent as custom content documents (amends T1.6 and T1.7 for the composition call)

- **Decision:** Area 1, topic 5, the user's addition:
  - **Claude decides how much to cite:** any run of whole sentences of a kept passage, from one sentence to the whole paragraph; one answer sentence may carry several citations. Nothing finer than a sentence (the Citations feature's smallest unit is a block).
  - **Our conservative splitter makes the sentences,** not Anthropic's automatic chunking: it splits only where a sentence plainly ends (after a lowercase word that is not an abbreviation, a number, a closing bracket or quotation mark, or a capitalised word of five or more letters not on a legal-abbreviation list), erring towards leaving two sentences together. Deterministic, run once when the search index is built, boundaries stored so the composition call and the page agree; a build check asserts the sentences join back into exactly the passage; a script reports suspicious splits and the main session reviews a sample (no subagent), logged. Footnotes are split the same way.
  - **Each kept passage goes to the composition call as a custom content document** (its sentence blocks, "used as-is"), with the passage's metadata and its keep reason (T1.7) in the document's **`context`**, the documented slot passed to Claude and never cited. Citations come back as block ranges. This replaces "search result blocks" for the composition call (T1.6) and "in its search result's header" for the keep reason (T1.7). Custom-content citation ranges are confirmed in build tests (Phase 2 tested search results).
  - **The sources panel always shows cited sentences highlighted inside their full paragraph.**
- **Evidence:** `scripts/probe_chunking.py` (Oct 24, 2026, one call, $0.1422): Anthropic's plain-text chunking broke legal citations in 133 of 200 pieces on the ten hardest passages; the conservative splitter, none of 54.
- **User's words:** *"Thus, I want us to explore giving Claude flexibility in deciding not only what to cite but also how much to cite. Then, in the source panel, we always show the sentence within a paragraph."* *"Consider whether we can feed whole passage, and let Claude cite within them however much or however little Claude wants?"* *"Send the diagnostic calls with the hardest passage."* Then: *"Lock topic 5 as T1.9: our conservative splitter, sentence blocks sent as custom content documents with metadata and the keep reason in context, the rest as proposed."*
- **Date:** Oct 24, 2026
- **Log:** `BUILD_LOG.md`, "Oct 24, 2026, 16:23 CDT — Phase 3: Architecture, Area 1 (citation granularity, T1.9)"

### T1.10 `submit_answer` and the rejection rules (supersedes brief §2's "its input lists the kept passage IDs") — AMENDED by T2.3 (adds `update_findings` and `update_overview`, checked after rule 1); by P4.6 (the note is capped at 1,000 characters); by P4.7 (rule 4 waived when out of scope); by P4.16 (rule 1: a submit must be alone in its turn, and sent once; a keep in the same turn no longer counts); AMENDED by P4.19 (the update fields and rule 4 leave `submit_answer` for the update step)

- **Decision:** Area 1, topic 6:
  - **`submit_answer(out_of_scope, note?, update_skip_reason?)`.** No list of kept IDs: the composition call uses the kept set as it stands when the submit is accepted (T1.7). This supersedes brief §2's Termination row ("Its input lists the kept passage IDs"); the invariant stands (every citation points to a passage the viewer watched Claude keep).
  - **`note`** is a reply **written to the visitor**, in plain language, two or three sentences. **Required** when the question is out of scope or nothing was kept; then no composition call runs and the page shows the note in the answer's place, labelled as Claude's reply with no sources, with the standard out-of-scope or nothing-found message. For an out-of-scope question it says what the corpus covers, why the question falls outside it, and where natural a related question it can answer; greetings and chit-chat are handled the same way. **On a normal answer it is an optional scope note** for a question partly outside the corpus (for example state law), shown above the answer and passed to the composition call.
  - **`update_skip_reason`:** optional; why no update check was needed; shown as "Update check skipped: <reason>".
  - **Rejection rules,** checked in this order, each an error result shown in the step log:
    1. A submit **in the same turn as a search or a read** is refused (its results are unseen); the other calls run. A keep in the same turn is fine.
    2. **No corpus search yet and not out of scope:** refused, repeatable (brief §5.4). Either search tool counts; a read alone does not.
    3. **Nothing kept, in scope, and no `note`:** refused, asking Claude to keep the passages its answer rests on or explain in `note` why none bear on the question.
    4. **No update check and no `update_skip_reason`:** refused once (brief §5.4); a resubmit with neither is accepted and labelled "Update check declined after reminder". A failed update attempt counts as run; the rule is waived while the update check is unavailable (P2.11; Area 2).
  - **Questions about a person's own situation are in scope:** researched and answered with what the Court held and the factors it weighed, stopping short of applying them (brief §5.6); the system prompt says so, so the out-of-scope flag is never used to sidestep them.
  - On acceptance the loop ends and the composition call runs over the kept set; the step limit and the token ceiling lead to the fallback (Area 1, topic 7). Every rule is triggered on purpose in Phase 5.
- **User's words:** *"Would a person asking an out of scope question get a natural response back with the current design?"* Then: *"Lock topic 6 as T1.10 as proposed, with the out-of-scope additions: note written to the visitor, a scope note for mixed questions, personal-situation questions kept in scope."*
- **Date:** Oct 24, 2026
- **Log:** `BUILD_LOG.md`, "Oct 24, 2026, 16:32 CDT — Phase 3: Architecture, Area 1 (submit_answer and the rejection rules, T1.10)"

### T1.11 The composition call — AMENDED by T3.3 (a composition that fails before its first block is retried up to twice); AMENDED by P4.18 (`max_tokens` 16,000) and P4.20 (Sonnet)

- **Decision:** Area 1, topic 7 (model and inputs also under T1.8 and T1.9):
  - **Inputs:** the question; the scope note if any (T1.10); the three coverage dates; the kept passages, one custom content document each (T1.9), **in order of decision date, then opinion, then position**, each titled with a short label ("Katz v. United States (1967), Harlan, concurring") and carrying in `context` its ID, citation, date, exact opinion type, author, joiners, section, pages and keep reason. **Left out:** footnotes that were not kept (Claude saw them in the loop and could keep them or name them in a keep reason), and the web results.
  - **The update check stays out of composition.** It is shown in its own band, separate from the corpus evidence (brief §6.4, P1.3); the band's synthesis is written in the loop by the Claude that read the results (mechanics in Area 2); when the check found something, our code adds one fixed line under the answer pointing to the band.
  - **The composition prompt covers,** in outline (text written in the build): cite every statement drawn from a passage, synthesis uncited; research, not advice; describe, never evaluate; exact opinion types, never a dissent or concurrence as the holding; dates and treatment; name only cases cited from the passages (P1.10); use each keep reason.
  - **Format: Claude writes naturally in Markdown, and the page renders it** (paragraphs, headings, lists, bold, italics; each text block's inline Markdown inside its citation underline). **Straddle fallback:** a citation that ever crosses Markdown structure is shown as plain text with its underline and link intact (a frontend test fixture). Headings and lead labels are not marked as synthesis (Area 4). Checked on Phase 2's Sonnet answers; Opus checked in build tests.
  - **No length target.** **`max_tokens` 12,000** is the backstop; an answer stopped by it is shown with a label that it was cut off at the length limit. Answer length is recorded per run for review in Phase 5.
  - **Synthesis** is any text without a citation, worked out mechanically. **The answer streams** to the page (transport in Area 3); where the checks run is topic 8.
  - **Budget:** the loop stops while room for one composition call remains in the per-run ceiling (P2.7): about 30,000 input and 12,000 output tokens held back, a placeholder until measured.
  - **Fallbacks:** at the step limit or the token ceiling, the answer is composed from what was kept so far and labelled "Stopped at step limit. Answer built from the evidence gathered so far." (brief §5.7) or its token-ceiling equivalent; with nothing kept, no composition and the page says so. An abandoned run composes nothing (brief §5.1); a composition already running when the browser leaves finishes. A failed composition is shown as an error with the kept passages still on screen and is never retried automatically (brief §10.7).
- **User's words:** *"Set the max tokens to 12000 just in case."* *"On the update check, I agree with your suggestions there."* *"I'm thinking of not suggesting Claude with a length target and see how it goes first. We already had max token as the hard backstop."* *"Why do we want to keep it to prose only? We can let Claude write naturally and render accordingly?"* Then: *"Lock topic 7 as T1.11: Claude writes naturally in Markdown and the page renders it, with the straddle fallback; no length target; max_tokens 12,000 with a cut-off label; the update check kept out of composition; the rest as proposed."*
- **Date:** Oct 24, 2026
- **Log:** `BUILD_LOG.md`, "Oct 24, 2026, 16:46 CDT — Phase 3: Architecture, Area 1 (the composition call, T1.11)"

### T1.12 Answer checks: a quotation check and a narrow full-citation check; the general case-name verifier dropped (supersedes brief §2's Case-name verifier row and §5.8; amends P1.10) — AMENDED by T5.2 (the line under the answer is reworded: quotations are found in the passages Claude kept); by P4.17 (the quotation comparison ignores letter case)

- **Decision:** Area 1, topic 8 (the user's addition):
  - **The general case-name verifier is dropped.** Brief §2 ("Every case name in the answer must resolve to a document in the corpus, or it is flagged on screen"; "In the minimum demo") and §5.8 are superseded: a case name outside the corpus cannot be found reliably in free text without structured output, which Citations rules out, and a check that claimed it would give false confidence.
  - **Quotation check:** every quotation of four or more words in the answer (a placeholder minimum) must appear in the kept passages, allowing standard legal quoting conventions (punctuation inside the closing quote mark, nested quotes changed between double and single, ellipses for omitted words, bracketed alterations, including those already in the source); otherwise it is flagged on screen. It closes a gap the API leaves: `cited_text` is verbatim, but Claude's own quoted words are not guaranteed.
  - **Full-citation check:** every full "X v. Y" case name and every U.S. Reports citation ("389 U. S. 347") in the answer must resolve to the corpus manifest, or it is flagged **"not in this corpus"** (P1.10), never as fabricated. It does not catch short-form names, and says so. A real case named in a passage (for example *Entick v. Carrington*) is flagged "not in this corpus", which is accurate.
  - **Each check is worded exactly as what it checks.** Both run when the answer finishes streaming; the results appear in one line under the answer (for example "Checked: 12 quotations found word for word in the cited passages · 4 full case names and citations found in the corpus · 1 not in this corpus: *Entick v. Carrington*"), and each flag marks its spot in the answer. Tested in Phase 5 with fabricated names and citations, near-misses, real cases outside the corpus, and altered quotations.
  - **P1.10 amended:** its "not in this corpus" wording now applies to the full-citation check; the system prompt still tells Claude to name only cases it cites from the corpus.
- **User's words:** *"I'm considering not offering this if it's something we cannot check reliably. The response is covered under the AI disclosure already, and adding a check that isn't reliable might give false confidence to user."* Then: *"Drop the general case-name verifier. Keep the quotation check and the narrow full-citation check, each worded exactly. Lock topic 8."*
- **Date:** Oct 24, 2026
- **Log:** `BUILD_LOG.md`, "Oct 24, 2026, 16:51 CDT — Phase 3: Architecture, Area 1 (answer checks, T1.12)"

### T1.13 The citing-cases lookup is cut; Claude uses keyword search on the citation string

- **Decision:** The citing-cases lookup of brief §5.2 is not built (brief §3 lists it second among the cuts). To find later corpus passages citing a case, Claude uses the keyword search (T1.2, T1.4) on that case's citation, for example `any_of: ["\"389 U. S. 347\"", "\"389 U. S., at\""]` with a `decided_from` filter; the corpus catalog in the system prompt gives every case's citation (T1.6). The system prompt (Area 1, topic 10) describes this technique, and that date order alone is not treatment. No citation index is built.
- **Recorded with it:** the text holds 805 citations between corpus cases in 524 passages; a short pinpoint citation identifies a case only together with its page range (a volume can hold other cases, e.g. *Leon* beside *Karo* in 468 U. S.), which the system prompt's guidance accounts for.
- **User's words:** *"The idea of the tool find_citing(case, filters?) is sound on the consumption end (Claude), but I'm reading that we'd need to build the underlying infrastructure?"* Then: *"Cut the citing lookup; Claude uses keyword search on the citation string. Lock topic 9."*
- **Date:** Oct 24, 2026
- **Log:** `BUILD_LOG.md`, "Oct 24, 2026, 17:00 CDT — Phase 3: Architecture, Area 1 (citing-cases lookup cut, T1.13)"

### T1.14 The research loop's system prompt, in outline — AMENDED by T5.5 (a rule keeping personal details out of Voyage and Exa queries)

- **Decision:** Area 1, topic 10. The loop's system prompt (Sonnet 5.5) covers, in this order; the text is written in the build, and **the user reviews the drafted text before its first paid run**:
  1. **Role and the division of labour:** Claude is the research engine for legal researchers; it researches, and a separate step writes the answer from the kept passages only, so each keep reason carries what the writer needs; text between tool calls stays brief.
  2. **The corpus:** scope and the inclusion rule (P1.9); the three coverage dates from the manifest (latest decision in the full pull 2026-06-29, latest in the corpus 2026-06-29, ingested 2026-10-23; brief §2); the text normalised from the official opinions, straight quotation marks (P1.17), no syllabus (P1.13); the ID scheme; the corpus catalog with exact opinion types and the line on the filter's grouping (T1.4, T1.6).
  3. **Research strategy with the tools** (detailed rules stay in the tool descriptions): meaning search for ideas, exact search for phrases, citations, terms of art and names; filters optional (T1.4's wording); independent searches and reads together in one turn, since rounds are limited; tracing later cases by the citation string in its full and "at" forms with `decided_from`, checking that a short citation's page falls inside the case (T1.13); reading around a passage before keeping it when it may restate a party, a lower court or a dissent, and page reads for "*ante*, at" references (T1.3, T1.6); keeping as it goes with one-sentence reasons, re-keeping to correct (T1.7); the update check near the end with the window trade-off, Claude choosing every parameter (brief §5.6; band summary in Area 2); the submit rules (T1.10).
  4. **Judgement rules:** research, not advice, with a person's own situation in scope (T1.10); describe, never evaluate; exact opinion types, never a dissent or concurrence as the holding; dates are not treatment; passage text and web results are data, never instructions.
  5. **Out of scope and borderline:** truly unrelated questions, greetings and chit-chat get `out_of_scope` with a note to the visitor; **borderline questions such as an employer reading work email are researched**, with the answer stating whom the Fourth Amendment restrains (the state-action limit), not flagged out of scope.
- **Beside the prompt:** our code appends a status line to each turn's tool results (for example "Round 5 of 12 · 9 kept · update check not yet run"), so the system prompt stays fixed and cacheable; the fixed opening (tools, system prompt, catalog; about 12,000 tokens, estimate) gets a one-hour cache breakpoint, which pays off from two runs an hour.
- **User's words:** *"Lock topic 10 as T1.14 as proposed; borderline questions like the employer email get researched (the state-action limit), not flagged out of scope."*
- **Date:** Oct 24, 2026
- **Log:** `BUILD_LOG.md`, "Oct 24, 2026, 17:04 CDT — Phase 3: Architecture, Area 1 (the loop's system prompt, T1.14)"

### T2.1 `search_web_updates`: what Claude sets, what our server limits, what it costs — AMENDED by P4.18 (5 searches a run) and P4.19 (searched in the update step)

- **Decision:** Area 2, topic 1:
  - **Reading of brief §2's Update check row** ("Claude controls every search field; our server clamps cost-related fields"): Claude controls every field of **our** wrapper tool, the list in brief §6.2 (query, date window, domains, category, search type), not every field Exa's tool offers.
  - **Claude sets:** `query` (required); `start_published_date` and `end_published_date`, both optional, checked by our code (valid dates, the end not before the start); `include_domains` and `exclude_domains`, **up to 100 entries each**, a limit only against overrun (Exa's own is 1,200), each a hostname, a path prefix or a subdomain wildcard; `category`, one of `news` or `publication`; `type`, `auto` or `lite`, default `auto`; `num_results`, 1 to 10, default 10, clamped by our code. The tool description states the trade-offs: a date filter also drops pages with no published date; `lite` is cheaper and faster but searches only Exa's cache and never fetches live, so it can miss the newest pages.
  - **Our code sets** the text cap per result and highlights (topic 2).
  - **Left out:** Exa-written summaries (`enableSummary`, `summaryQuery`: the band shows Claude's own synthesis, P1.3); crawl dates (ignored by the API); `includeText` and `excludeText` (deprecated); `additionalQueries` (deep types only); `subpages` and `subpageTarget`; `maxAgeHours` and `livecrawlTimeout` (Exa's default kept); `userLocation`; `moderation`; the categories `company`, `people`, `financial report`, `pdf` and `github` (no use here or being deprecated; this also removes the known failing date-filter combinations, brief §6.2); the legacy types `fast` and `instant`. The deep types cannot be sent through Exa's tool at all (Phase 2 findings §4).
  - **Limits:** 3 update searches per run (P2.7); a fourth is refused with an error result. A call our code refuses before it reaches Exa does not count; a call that reached Exa counts, even if Exa returned an error. The per-turn status line (T1.14) shows "update searches <n> of 3".
  - **Shown:** the step log shows every value Claude chose and one line of our fixed settings, so every parameter is shown (brief §2, Update-check honesty).
  - **Cost:** at most 3 × $0.007 = $0.021 a run. Exa's reported cost (`costDollars`) is recorded per call and **counts toward the $10 daily and $60 monthly caps** (P2.7).
- **User's words:** *"I only have 1 correction here, for include and exclude domains, set a high limit (100) to prevent overrun only and give Claude flexibilities."* Then: *"Lock topic 1 as T2.1: reading B, domains up to 100 each, the rest as proposed."*
- **Date:** Oct 24, 2026
- **Log:** `BUILD_LOG.md`, "Oct 24, 2026, 17:18 CDT — Phase 3: Architecture, Area 2 (the update-check tool's inputs, T2.1)"

### T2.2 What an update-check result looks like to Claude

- **Decision:** Area 2, topic 2:
  - **Format:** plain-text blocks, one per page, as for corpus results (T1.6); not `search_result` blocks.
  - **IDs:** our own, `web-<search>-<n>`, so the band's summary can tie each statement to its source (topic 3).
  - **Opening line:** the search exactly as sent, our fixed settings included; how many pages came back and how many had no published date.
  - **Header per page:** title; domain and URL; "published <YYYY-MM-DD> (Exa's estimate)" or "no published date"; author when Exa gives one.
  - **Dates taken as written, no conversion:** our code keeps the date part of whatever Exa sends (`2026-06-29T14:17:34Z` → 2026-06-29), the same for Claude and every visitor; no time-zone handling. Most of Exa's values are a printed date stored as midnight UTC, which converting would move back a day in every U.S. zone. **An exception to brief §10.7** for these values: a page published at a real moment in a U.S. evening may show the next (UTC) day; the "Exa's estimate" label covers it.
  - **Text:** the opening **4,000 characters** of Exa's cleaned page text (a placeholder, measured in Phase 5), marked when cut; inside fixed markers labelling it as data from the page, not instructions, with any copy of the closing marker inside the text escaped by our code. **No highlights** (model-chosen excerpts) and no summaries (T2.1).
  - **Repeats:** a page an earlier search returned is listed under its first ID, not sent again.
  - **Dropped:** image, favicon, Exa's own IDs and scores; Exa's cost is recorded (T2.1), not shown to Claude.
  - **The page and the stored run events** carry only each page's title, URL and date, never its text (P1.3, P1.7). What replays keep is topic 3.
- **User's words:** *"I'm leaning not trusting Exa's highlight here."* *"Let's keep 4000"*. *"I mean take Exa's date as written, with no conversion"*. Then: *"Lock topic 2 as T2.2 as restated."*
- **Date:** Oct 24, 2026
- **Log:** `BUILD_LOG.md`, "Oct 24, 2026, 17:33 CDT — Phase 3: Architecture, Area 2 (what a web result looks like to Claude, T2.2)"

### T2.3 The update-check band: structured findings in `submit_answer` (amends P1.3 and T1.10) — AMENDED by P4.8 (the no-sources note guarded) and P4.9 (corpus words exempt); AMENDED by P4.19 (findings in the update step's `submit_update`; `declined` removed)

- **Decision:** Area 2, topic 3, option A:
  1. **Fields** added to `submit_answer` (amends T1.10): `update_findings`, a list of `{statement, sources}` (source IDs `web-<search>-<n>`, T2.2), an empty list meaning nothing relevant was found; `update_overview`, optional. Caps, placeholders against overrun only: 20 findings, 600 characters a statement, 10 sources a statement, 600 characters for the overview. Statements describe what a page reports, attributed to its source, never whether the law has changed (system prompt).
  2. **Checked after rejection rule 1 and before rules 2 to 4** (T1.10): an unknown source ID, a statement with no source, or findings when no update search ran refuse the submit with an error naming each problem; repeatable.
  3. **Copy guard:** a statement or the overview that repeats 10 or more consecutive words (a placeholder, tested in Phase 5) of any page returned in the run, compared ignoring case, punctuation and spacing, refuses the submit with a request to paraphrase. Accepted: each refusal uses a round, and repeating a Court quotation found in an article trips it.
  4. **The outcome is worked out by our code,** never set by Claude: found (at least one finding); nothing relevant (an update search ran, findings empty); skipped (`update_skip_reason`); declined after reminder (rule 4); unavailable (topic 4). The pointer line under the answer (T1.11) appears only on "found".
  5. **Out-of-scope and nothing-kept runs:** no answer is composed, but the band still shows if an update search ran.
  6. **Fallbacks:** at the step limit or the token ceiling there is no submit, so the band shows each search's parameters and returned pages, labelled as not summarised because the run stopped first.
  7. **The band shows** the outcome, each search's parameters (T2.1), each finding linked to its sources (title, domain, date as written, T2.2), the overview marked as Claude's synthesis, a collapsed list of every page returned, and the honesty label. Layout in Area 4, wording in Area 5.
  8. **Replays store** the parameters, findings, overview and link details, never page text (P1.7), labelled with the recording date.
- **P1.3 amended:** its "Internally, Citations still mark which sentences are grounded in a web result; on screen, such a sentence links to its source" becomes: Claude names the sources for each statement and our code checks that they were returned in the run. The page must not call this verified (wording in Area 5). Brief §6.4's guarantee sentence for the band ("text as fetched from that page") no longer fits, since no web text is shown; its replacement is Area 5's.
- **Why not a Citations call (option B):** no web text reaches the page either way (P1.3), and a Citations pointer shows only that the cited span exists, not that it supports the statement; B would add a call (estimate +$0.02 to $0.08 a run) written by a second Claude that did not do the research.
- **User's words:** *"Go with option A, structured findings in submit_answer. Let's go through the details."* Then: *"Lock topic 3 as T2.3: option A with the eight details as proposed."*
- **Date:** Oct 24, 2026
- **Log:** `BUILD_LOG.md`, "Oct 24, 2026, 17:40 CDT — Phase 3: Architecture, Area 2 (the band's summary and links, T2.3)"

### T2.4 Update-check errors and unavailability

- **Decision:** Area 2, topic 4:
  - **Four kinds of failure:**
    - **Refused by our code** (a bad date, over 100 domains, a fourth search): an error result saying what to fix; not counted toward the 3 searches (T2.1); no cost.
    - **Refused by Exa** (a 4xx other than 401 and 402): Exa's own message passed to Claude, which may change the search and retry; counted; no cost recorded.
    - **Failed** (a 5xx after Exa's own retries, a protocol or connection error, a timeout, a reply our code cannot read): a plain "the search did not complete" message; counted; Claude may search again if searches remain; recorded at Exa's list price for the type, since it may have been billed without a report.
    - **Unavailable** (402 `NO_MORE_CREDITS`, or 401): no search runs; "Update check unavailable: <reason>"; not counted; no cost.
  - **Out of credit across runs:** the first 402 sets a flag in Atlas, unavailable until the 1st of the next month (P2.11). Every run checks it before starting; while it is set, a line in the run's first user message tells Claude, and any update search returns "unavailable" without calling Exa. After the 1st the next run tries again; a further 402 sets the flag again at no cost. The tool stays listed, since the tools and system prompt are fixed and cached (T1.14).
  - **A 401** makes the check unavailable for that run only and is logged as our configuration fault.
  - **Rejection rule 4** (T1.10) is waived only while the check is unavailable; a failed search counts as the check having run.
  - **Timeout:** 30 s per update search, a placeholder until measured (brief §10.7); Exa's own server time was 0.3 to 1.9 s in Phase 2, and its tool's 300 s limit would leave a run waiting five minutes. An abandoned call is recorded at list price.
  - **No retries by our code** (brief §10.7); Exa's server-side retries stand (P2.8).
  - **The band** never shows a raw error (brief §6.4): with nothing run, "Update check unavailable" and the reason in plain words; with some searches incomplete, the band as usual, each incomplete search listed with its parameters and "did not complete" (T2.3).
- **User's words:** *"Lock topic 4 as T2.4 as proposed."*
- **Date:** Oct 24, 2026
- **Log:** `BUILD_LOG.md`, "Oct 24, 2026, 17:43 CDT — Phase 3: Architecture, Area 2 (errors and unavailability, T2.4)"

### T2.5 The connection to Exa's MCP server: a session per search

- **Decision:** Area 2, topic 5:
  - **A session per update search:** our backend opens an MCP session to Exa's hosted server, initializes it, calls the tool once and closes it. Nothing is held open between searches or between runs. The official `mcp` Python package (2.3.0, already in `uv.lock`) is the client.
  - **Address and key:** `https://mcp.exa.ai/mcp?tools=web_search_advanced_exa`; the key only in the `x-api-key` header, never in a URL or a log (brief §6.1). How the key reaches Cloud Run is Area 3.
  - **The 30 s timeout** (T2.4) covers the whole search, handshake included.
  - **The out-of-credit flag** (T2.4) is checked before a session is opened.
  - **Schema check:** our code lists Exa's tool (free) on an instance's first update search, in the Phase 5 tests and in the check after each deploy, and compares it with every field and value we send (T2.1); a mismatch is logged as a warning and does not block, since the failures it causes are handled by T2.4.
  - **Considered:** a session per run (saves a handshake only for runs with 2 or 3 searches; a break mid-run needs reopening); one session for the instance (can go stale while the instance idles or its CPU is limited between requests; concurrent runs would share its failures). The handshake's time is measured in Phase 5.
- **User's words:** *"Lock topic 5 as T2.5: a session per search, the rest as proposed."*
- **Date:** Oct 24, 2026
- **Log:** `BUILD_LOG.md`, "Oct 24, 2026, 17:46 CDT — Phase 3: Architecture, Area 2 (the MCP connection, T2.5)"

### T3.1 Starting a run and streaming it to the page — AMENDED by T4.3 (the source reader fetches whole opinions as static files from the web service); AMENDED by P4.3 (a submit refused by the copy guard is stored with its flagged statements withheld)

- **Decision:** Area 3, topic 1:
  - **Transport: Server-Sent Events.** `POST /runs` with the question creates a run and returns its ID; `GET /runs/{id}/events` streams it. The browser's EventSource reconnects on its own, one attempt at a time, sending the last event ID it received (brief §8.5). How the server learns the page is gone is topic 2 (P2.10).
  - **The loop starts when the first stream attaches**, not on the POST; a run no stream attaches to expires with no spend. The run lives in a task on the instance, not in a request, so a reconnect picks up the same run.
  - **Events** are numbered 1, 2, 3 within a run and carry the time since the run started (replays play at the recorded pace); stored timestamps carry their zone (brief §10.7).
  - **Event kinds:** run started (question, limits, coverage dates, update-check availability); round started (with the status line, T1.14); tool call (exactly what Claude sent); tool result (passages; keeps with reasons; web results as title, URL and date only, T2.2; submits accepted or refused with the rule); a paid call that failed; each paid call's tokens and cost (shown or not, Area 4); composition started; answer blocks; the two checks (T1.12); the update-check band (T2.3); run ended (answered, a reply with no sources, step limit, token ceiling, abandoned, failed, with totals).
  - **The answer streams one text block at a time with its citations**, not token by token, so everything shown is stored and a reconnect or replay shows the same thing.
  - **No thinking summaries**: thinking display stays at its default (omitted), as in Phase 2; the tool calls show the research.
  - **Passage text is sent in the events**, the first time a passage appears in a run, with its sentence offsets (the panel shows a cited sentence inside its paragraph, T1.9); later mentions carry the ID only. The page does not fetch a separate corpus.
  - **Storage:** events are held in the instance's memory first and copied to Atlas in order without holding up the stream; a failed Atlas write is logged and the run continues. A reconnect to the same instance replays from memory; one that reaches another instance replays from Atlas and ends "interrupted" (brief §8.5). How long Atlas keeps them is topic 7.
  - **Replays** are static files in the same event format, played by the same code on the page (brief §7.4).
  - **The run ID is random and unguessable** (anyone holding it could read the question). **One stream per run**: a new connection replaces the old one.
  - **A comment line every 15 s** (placeholder until measured) keeps an idle stream open through the gateway; not an event, not stored.
  - **Considered:** one streaming POST plus a reconnect GET (two code paths for the stream, a hand-written reconnect); WebSocket (Cloud Run passes its disconnects, but it needs a goodnight change and a hand-written resume, and a suspended page still needs a liveness signal); token-by-token answer streaming (what is stored would differ from what was shown); thinking summaries (untested here); the page fetching a static corpus (2.4 MB; two copies to keep in step).
- **User's words:** *"Your recommendations work here. Lock and proceed."*
- **Date:** Oct 24, 2026
- **Log:** `BUILD_LOG.md`, "Oct 24, 2026, 17:55 CDT — Phase 3: Architecture, Area 3 (starting a run and streaming it, T3.1)"

### T3.2 Disconnect detection: a heartbeat from the page, checked before every paid call

- **Decision:** Area 3, topic 2 (settles P2.10's mechanism; brief §2's Browser disconnect rule stands):
  - **Heartbeat:** while its stream is open, the page sends `POST /runs/{id}/alive` every 10 s, carrying the last event ID it holds. The run counts as attended while the last heartbeat is under 25 s old.
  - **Checked before every paid call:** each loop call to Claude, each Exa search, each Voyage embed and rerank, and the composition call. A call already running finishes, a composition included (an abandoned request is still charged, Anthropic support page).
  - **Pause and resume:** when a paid call is due and the run is not attended, the run pauses (a stored event) and resumes on the next heartbeat (a stored event).
  - **Abandoned:** 60 s after the last heartbeat the run is abandoned: no answer composed, its actual spend recorded (topic 4), and our code closes its stream, since Cloud Run does not end the request when the browser leaves (INFERRED from the troubleshooting page).
  - **Page watchdog:** the page reconnects when nothing, neither an event nor a keep-alive line (T3.1), has arrived for 45 s.
  - **Reload:** the page keeps the run ID in sessionStorage and reattaches after a reload (iOS Safari may reload a suspended page).
  - **Another instance:** a heartbeat that reaches an instance not holding the run is written to Atlas; the holding instance reads Atlas before it pauses.
  - **A run that finished while the page was away** stays readable on reconnect until its events expire (topic 7).
  - **Every figure** (10 s, 25 s, 60 s, 45 s) is a placeholder until measured against real drops on the iPhone in Phase 5 (brief §8.5, §10.7).
  - **Considered:** end-to-end HTTP/2 (`--use-http2` and h2c on goodnight and the API, nginx 1.29.4 or later proxying HTTP/2; two goodnight changes, uvicorn's HTTP/2 experimental, still blind to a half-open connection); WebSocket (set aside by T3.1). Edge noted, untested: Chrome slows chained timers in a tab hidden over 5 minutes to about once a minute, longer than any measured run.
- **User's words:** *"Lock option A. Proceed."*
- **Date:** Oct 24, 2026
- **Log:** `BUILD_LOG.md`, "Oct 24, 2026, 17:58 CDT — Phase 3: Architecture, Area 3 (disconnect detection and the grace window, T3.2)"

### T3.3 The paid calls during a run: streamed, visible retries for Anthropic and Voyage (supersedes brief §10.7's no-retry rule for these calls; amends P2.8 and T1.11) — AMENDED by P4.18 (per-step token budgets; no run-wide limit)

- **Decision:** Area 3, topic 3:
  - **Claude calls are streamed** (the SDK's stream, the final message assembled), with the SDK's own retries off (`max_retries=0`, so no hidden retry sits inside a measured time, brief §10.7) and our own deadline per call: 120 s for a loop call, 300 s for composition (placeholders until measured).
  - **Budget:** the per-run ceiling (P2.7) counts every kind of input token (uncached, cache writes, cache reads), as it was measured in Phase 2. With T1.11's reserve held back, the loop has 370,000 input and 8,000 output tokens. Before each loop call our code estimates its input and, if it would cross 370,000, goes to composition with the token-ceiling label; each loop call's `max_tokens` is what remains of the 8,000; a loop call stopped by `max_tokens` goes to composition with the same label.
  - **Caching** as T1.14 (a one-hour breakpoint on tools, system prompt and catalog; automatic caching for the growing conversation); composition uncached (T1.11).
  - **Retries by our own code**, each shown as a step, logged and counted:
    - **Anthropic:** up to 2 retries on a rate-limit 429, 500, 504, 529, a connection failure, or an error after a loop call's stream began; waits honour `retry-after`, else 2 s then 8 s (placeholders). **Never retried:** 400, 401, 403, 404, 413, the usage tier's spend-cap 429, a `refusal` stop reason, or our own deadline (the call may still be generating and billed, Anthropic support page). A failed loop call appends nothing to the history, so its retry is the same request (cache and thinking blocks unaffected).
    - **Composition** is retried only if it fails before its first block arrives; after that, the blocks already shown stay, labelled incomplete, and the two checks (T1.12) run on what arrived.
    - **Before every attempt**, the heartbeat (T3.2) and the spend caps (topic 4) are checked; every attempt's usage counts toward the caps.
  - **Errors after retries:** our fault or the account's (400, 401, 403, 404, 413, a spend-limit 400) ends the run with no further calls and is logged; a spend limit also pauses live research (topic 4). **Transient failures in the loop, once retries run out, go to composition from what was kept, labelled as stopped by an error**; with nothing kept the run ends failed. A `refusal` ends the run like a failure, with its own message.
  - **Spend for a failed attempt** is the usage its stream reported, or an estimate of its input at the uncached price when none was reported (how it counts, topic 4).
  - **Voyage** (embed the query, then rerank, per meaning search): 10 s per request (placeholder), up to 2 retries at 1 s then 3 s (placeholders), client retries off. If the rerank still fails, the search returns the embedding order, marked "not reranked" for Claude; if the embed fails, Claude gets an error result saying keyword search still works; a 401 marks meaning search unavailable for the run and is logged as our configuration fault. **Either failure flags the run, and the page warns that meaning search was degraded or unavailable for part of this research** (wording Area 5; not "quality is affected", since the effect on the answer is not measured).
  - **Unchanged:** Exa keeps T2.4 (no retries by our code; Exa's own, P2.8). The live-run request to our API is never retried (brief §8.5 rule 2).
- **User's words:** *"I'm leaning allowing retries for both Anthropic and Voyage. Especially when Voyage fails, I want to display a warning to user that quality of this response is affected due to this."* Then: *"Lock topic 3 as T3.3 with retries as revised; compose from what was kept after retries run out."*
- **Date:** Oct 24, 2026
- **Log:** `BUILD_LOG.md`, "Oct 24, 2026, 18:04 CDT — Phase 3: Architecture, Area 3 (the paid calls during a run, T3.3)"

### T3.4 Spend counters and caps: the worst case reserved atomically at the start; every budget stop recorded — AMENDED by P4.6 (the worst case is $2.11); AMENDED by P4.21 (no reservation: admission under the caps, spend recorded per call, a cap on runs at once)

- **Decision:** Area 3, topic 4:
  - **Reservation (B1):** a run starts only if, in one conditional update of one Atlas document per Chicago month (holding the month's and each day's spent and reserved), spent plus reserved plus the run's worst case stays within $10 for the Chicago day and $60 for the Chicago month (P2.7). The caps are therefore never overshot, however many instances run (brief §8.1). Up to one worst case of a day may go unused.
  - **The worst case** is computed by our code from the per-run ceilings (T3.3) and the price table: about $1.67 today (loop input $0.943, loop output $0.08, composition $0.36, two composition attempts failing before their first block $0.24, Exa $0.021, Voyage under $0.03). Every attempt counts toward the run's token ceiling, so retries never raise it.
  - **Settling:** each paid call's cost moves from reserved to spent as it completes; the remainder is released when the run ends; a reservation never settled (an instance lost mid-run) stays counted. Spend counts toward the Chicago day and month the run started in.
  - **Pricing:** Claude from the usage fields (uncached input, 5-minute and 1-hour cache writes, cache reads, output) by a price table in our code naming its source and date (Anthropic's pricing page, Oct 24, 2026: Sonnet 5.5 $2, $10, $2.50, $4, $0.10; Opus 5.5 $4, $20, $5, $8, $0.20 per million tokens); Exa from `costDollars`, list price when unreported (T2.4); Voyage at list price from the tokens it reports, its free tokens ignored; a failed attempt as T3.3.
  - **Atlas unreachable at the start:** the run is refused (fail closed).
  - **What the page knows:** `/health` carries whether live research is open, paused for the day or paused for the month, and whether the update check is available, read from Atlas with a short timeout ("unknown" if it does not answer); the refusal of `POST /runs` is authoritative. Paused states as brief §7.2; wording Area 5.
  - **Every budget stop is recorded**, at the user's direction, whatever its cause: counts per Chicago day in the monthly document, and one small record per refusal or stop (Chicago date and time, the run ID where there is one, which limit, spent and reserved at that moment; no question text). Recorded kinds: refused by the daily cap; refused by the monthly cap; stopped by the step limit; stopped by the per-run token ceiling (input or output); an answer cut off by composition's `max_tokens`; ended by the Console's spend limit (a 400) or the usage tier's spend cap (a 429); the update check unavailable because the Exa credit ran out (402, T2.4). Runs started are counted beside them, and a refusal because Atlas could not be reached is recorded too, marked as not a budget stop. A read-only `scripts/spend_report.py` prints a day or a month. Retention in topic 7.
  - **Console backstop:** the live service's Anthropic key in its own workspace with a $60 monthly limit (the user's action in the Console; findings §7); a workspace limit is a 400, ended and paused by T3.3.
  - **Local and test runs** use a separate database, so they never spend the live caps. **Phase 5** reconciles our counters against the Console's usage.
  - **Considered:** checking the caps only at the start (overshoot up to every run in flight times its cost); a typical reservation extended during the run (fuller use of the budget, more moving parts, a run may stop early).
- **User's words:** *"B1 is good, but I'd also want it logged in our database how many times have a run failed due to budget as well. This is for me to keep an eye on usage and refusal just in case."* Then: *"Record everything stopped due to budget regardless of how as long as it's a budget concern. Lock otherwise."*
- **Date:** Oct 24, 2026
- **Log:** `BUILD_LOG.md`, "Oct 24, 2026, 18:13 CDT — Phase 3: Architecture, Area 3 (spend counters and caps, T3.4)"

### T3.5 Cloud Run and the gateway

- **Decision:** Area 3, topic 5:
  - **Project and region:** both services in the GCP project `probable-clause` (number 1066460440617, created by the user), region us-central1, both min 0, request-based billing.
  - **Web service:** the frontend and the replay files, static, max 2 instances (placeholder).
  - **API:** max 1 instance, concurrency 80, 1 vCPU, 512 MiB (until measured), startup boost passed explicitly; the deploy script passes `--scaling=auto` and every limit explicitly (brief §8.5).
  - **API request timeout 900 s** (placeholder). It bounds one stream connection, not a run: a cut stream reconnects and resumes (T3.1). Through goodnight a stream is cut at goodnight's own 300 s timeout anyway, so a run longer than 5 minutes reconnects once; goodnight's timeout is not changed.
  - **Run deadline: 10 minutes** (placeholder), after which the loop goes to composition with a time-limit label; recorded as a limit stop (T3.4).
  - **Concurrent runs** are bounded by the reservation (about five at once at $1.67 within $10, T3.4); no separate run limit.
  - **Both services through goodnight on the one domain:** `/probable-clause/` to the web service, `/probable-clause/api/` to the API, so same origin and no CORS. The API sends `X-Accel-Buffering: no` and the 15 s keep-alive (T3.1).
  - **The one goodnight change:** a new probable-clause block inside its own delimiters (the API location with the prefix stripped, buffering and caching off, a read timeout well above the keep-alive; the page location with the prefix stripped; a bare-path redirect), **forwarding no `X-Forwarded-For`**. Written in goodnight's repository, shown to the user first, deployed only on the user's green light (brief §8.1). No goodnight code is copied into this repository.
  - **No client IP** is used or stored by our services (P2.6 removed its only use). Visitors' IPs remain in goodnight's own Cloud Run request logs in the framedbytran project, as for every app on the domain; the privacy note says so (topic 7, Area 5).
  - **Secrets in Secret Manager**, referenced as environment variables, readable only by the API's own service account: the Anthropic key from the live workspace (T3.4), the Voyage key, the Exa key, the Atlas connection string. How the values get there is settled with the user in Phase 4.
  - **Atlas:** the user's cluster in GCP us-central1, open to all addresses; the URI's user has readWrite on `Probable_Clause` (live) and `Probable_Clause_test` (local and test runs, T3.4) only (brief §8.4).
  - **Deploys** only when no run holds a reservation (checked in Atlas), and only on the user's green light.
  - **Considered:** the page calling the API's run.app address directly (avoids goodnight's timeout, but cross-origin and against brief §8.1); raising goodnight's timeout (unneeded given T3.1's resume).
- **User's words:** *"You're clear to read goodnight's nginx.conf and its Cloud Run settings. Don't bring any of its code over here though--contamination."* *"Atlas cluster is opened to all IPs, so with the URI you're covered."* *"Cluster is in GCP / Iowa (us-central1). I already set up a new empty database in the cluster for you, named Probable_Clause"* *"Good on both notes."* *"URI is limited to readWrite only on Probable_Clause."* *"I've added a new db Probable_Clause_test to the MongoDB cluster, and your URI now also has readWrite against that db too for you to test."* *"probable-clause (id) project created on GCP. Project number 1066460440617."* Then: *"Lock otherwise."*
- **Date:** Oct 24, 2026
- **Log:** `BUILD_LOG.md`, "Oct 24, 2026, 18:26 CDT — Phase 3: Architecture, Area 3 (Cloud Run and the gateway, T3.5)"

### T3.6 Start-up and the wake protocol (settles T1.1's open points) — COUNT CORRECTED by P4.2 (2,462 passages, not 2,748 units; vectors about 10.1 MB)

- **Decision:** Area 3, topic 6:
  - **Vectors in memory** in the API container: the 2,748 units' voyage-law-2 vectors (1,024 dimensions, 11.3 MB as float32), scored by brute-force dot product, with the T1.4 filters applied in memory. No vector search in Atlas.
  - **The vectors file** is built once in Phase 4 by script and **committed beside the corpus**, with a manifest (model, dimension, date, and a hash of each unit's embedded text), checked at start. The image build makes no Voyage call. The one-time embedding paces its requests under Voyage's Tier 1 limits.
  - **A one-line header is prepended to the text Voyage embeds** (case, year, exact opinion type and author, section), never to the citable text.
  - **The keyword index** (FTS5) is built at start from the corpus (0.04 s measured in Phase 2); no index file. FTS5's presence in the image's Python is checked in the build.
  - **Everything loads before the port opens** (corpus, catalog, sentence offsets, vectors, index), each step timed and logged with the time since the process started, so the app's start is read apart from the container's in Cloud Run's logs (brief §8.1).
  - **`/health`** answers 200 JSON only when the app is ready, carrying T3.4's status (live research open or paused, update check available; Atlas read with a short timeout).
  - **The page follows brief §8.5's wake protocol:** one check on landing (wake on landing, brief §2); any response that is not our JSON, whether Cloud Run's plain text or goodnight's HTML, means still starting and leads to the next serial check; a fresh `/health` right before `POST /runs` (instant when warm; catches an instance that shut down since landing); a stream that cannot reconnect runs the wake protocol before reattaching (T3.1).
  - **The long wait** (placeholders): the page shows the time elapsed since the wake began; after 90 s (about twice the longest start measured by the previous build) it says this is taking longer than usual and points to the recorded runs; after 5 minutes it stops checking and offers a button to try again, which starts a fresh check, never a run. A typical range is stated only after this build has measured one (brief §7.2). Wording Area 5; layout Area 4.
  - **Measurement** as brief §8.5: a first sample after the first deploy (Phase 4); in Phase 5 the wake protocol against a cold API and a sample after hours of quiet, with idle time, caller-side time and Cloud Run's logged times recorded together; every scaling change on the user's green light.
- **User's words:** *"Lock topic 6 as T3.6: vectors in memory, the vectors file committed, the header on embedded text, the rest as proposed."*
- **Date:** Oct 24, 2026
- **Log:** `BUILD_LOG.md`, "Oct 24, 2026, 18:28 CDT — Phase 3: Architecture, Area 3 (start-up and the wake protocol, T3.6)"

### T3.7 Protections and retention

- **Decision:** Area 3, topic 7 (brief §8.3):
  - **Question cap:** 2,000 characters (placeholder; about 500 to 660 tokens); empty or whitespace-only questions refused; control characters stripped; checked before any paid call. `POST /runs` and heartbeat bodies are size-capped. One question per run; a follow-up is a new run with no carried context (to confirm in Area 4).
  - **Tool inputs:** our code validates every field of every tool call (types, ranges, lengths, ID formats and the per-tool rules already locked); a failure returns an error tool result, shown as a step. Strict tool use is added only on tools whose schemas fit its limits (at most 24 optional parameters across strict schemas; no numeric or length constraints), counted in the build.
  - **Rendering:** Markdown rendered with raw HTML disabled; links only `http` and `https`, and only from Exa results (T2.3), opened with `noopener noreferrer`; text from the visitor, Claude, the corpus or the web inserted as text, never as HTML.
  - **Injection:** passage and web text stay data (T1.14, T2.2); Claude reaches nothing beyond its six tools, so a hostile question can at worst spend one bounded run (T3.4).
  - **Retention:**
    - **Run events** (question, Claude's queries, passages, keeps, web titles and URLs, the answer): Atlas, **TTL 24 hours**. Replays are exported from them by script when recorded (Phase 5).
    - **Per-run records** (run ID, Chicago times, end state, steps, searches, keeps, tokens and spend by service, retries, answer length, check flags, the Voyage warning), with no question or answer text: no expiry.
    - **Monthly spend documents and budget-stop records** (T3.4): no expiry.
    - **Heartbeat records** (T3.2): TTL 10 minutes. **The Exa flag** (T2.4): until the 1st.
  - **Logs:** our application logs never hold the question, Claude's queries, or any answer or page text; only run IDs, states, timings, costs and error kinds. No personal data in any URL. Cloud Logging's default retention applies to request logs (to check).
  - **No cookies and no analytics** in this app; sessionStorage holds only the run ID (T3.2).
  - **The privacy note** (wording Area 5) states: what is kept and for how long; that the question and Claude's searches go to Anthropic, and Claude's searches to Voyage and Exa, under their own retention (read and cited when the note is written); that this app neither uses nor stores IP addresses, while the domain's gateway keeps standard request logs (T3.5).
- **User's words:** *"Lock topic 7 as T3.7 with run events kept 24 hours, the rest as proposed."*
- **Date:** Oct 24, 2026
- **Log:** `BUILD_LOG.md`, "Oct 24, 2026, 18:38 CDT — Phase 3: Architecture, Area 3 (protections and retention, T3.7)"

### T4.1 Art direction: the machinery prototype in Evergreen (brief §7.3, P1.6) — AMENDED by T5.5 (the fonts are served by our own web service, not Google Fonts)

- **Decision:** Area 4, topic 1. The prototype at `web/looktests/machinery/` as of commit badc05f is the art direction and **the baseline for the build**: what it shows stays, except where Area 4's topic 3 changes it to match Areas 1 to 3 or topic 4 adds to it.
  - **Character:** a tech demo first, legal in flavour, for a technical visitor who came to see Claude and Citations.
  - **Flow:** the landing page's question box glides down into a chat-style conversation that grows from the bottom; a recorded-run chip starts a replay the same way.
  - **Sources:** a column beside the conversation, each card showing its state.
  - **The answer:** plain prose; cited sentences underlined in their passage's colour; hovering or tapping one scrolls its source into view and lights the cited text inside its paragraph, with a connecting line; sentences without a line are Claude's synthesis, explained by a key under the Answer heading.
  - **"View API calls":** a modal of every Messages API exchange that touched the passage, one row each that opens on click, opening at the response behind the citation; capped at 36rem tall on desktop, full screen on a phone.
  - **"View source":** a reader with the whole opinion, U.S. Reports page numbers in the margin, opening with the excerpt centred and the cited sentences lit, with "Back to the excerpt"; full screen on a phone, each page number above its paragraph.
  - **Wordmark:** *Probable C**l**ause*, the "l" in the project's accent colour (brief §2).
  - **Palette Evergreen**, in OKLCH: green-grey neutrals, a deep green accent, four source hues at equal lightness and chroma, red reserved for flags. **Dark mode follows the system.**
  - **Type:** Instrument Sans (interface), Newsreader (the Court's text), JetBrains Mono (API traffic), from Google Fonts under the SIL Open Font License.
  - **One reading width, 51.25rem**, shared by the landing page and the conversation.
  - **The AI-disclosure sentence always starts its own line.**
  - **Sizes:** every view checked at 1440×900, 393×852 and 852×393 (the iPhone 15 Pro upright and sideways), with no horizontal scroll, measured by element rectangles (brief §7.3).
  - **Dropped in the real build:** the palette (Cobalt, Violet) and theme switcher banner, the scripted run, the mock opinion text, the version query strings.
  - **Placeholders:** every piece of wording shown (notices, the not-legal-advice line, the answer key, the update-check label), settled in Area 5.
  - **Not settled here:** the frontend stack (topic 2); the prototype's contract assumptions, such as citations as `search_result` block ranges, which T1.9 replaced with custom content documents (topic 3).
- **User's words:** *"Yes. This prototype, in Evergreen, is the chosen direction. Log it and get it ready for the main session to fold in."* (Oct 23, 2026, frontend session.) *"Wait, the frontend prototype is done and locked. What will that change about this area?"* Then: *"Lock topic 1 as T4.1 as drafted."*
- **Date:** Oct 24, 2026
- **Log:** `BUILD_LOG.md`, "Oct 24, 2026, 18:50 CDT — Phase 3: Architecture, Area 4 (art direction, T4.1)"

### T4.2 The frontend stack: plain JavaScript modules, no build step (settles brief §2 default 1)

- **Decision:** Area 4, topic 2, option A:
  - **Plain JavaScript as ES modules, no build step**, carried forward from the prototype (T4.1) and split by concern (for example the stream client, the renderer, the panels, the modals). What is committed under `web/` is exactly what is served.
  - **One dependency: markdown-it**, vendored into `web/` at an exact version with its licence file; raw HTML off and links off in the answer (T3.7: links only from Exa results, built by our code).
  - **Text inserted as text:** the build creates elements and sets their text, instead of the prototype's markup strings with an escape helper (T3.7).
  - **The web service** (T3.5) is an nginx container on an exact pinned version, written here from scratch (no goodnight code, T3.5). Every response carries `Cache-Control: no-cache`, so each load revalidates by ETag; this replaces the prototype's `?v=` query strings.
  - **Tests:** Node's built-in test runner, no dependencies, for the renderer and the straddle-fallback fixture (T1.11); mock fixtures checked against the event schema by the Python tests (P0.3); layout measured in the browser by element rectangles (brief §7.3).
  - **Considered:** Vite with TypeScript (types against the contract and a dev server, for a build step and a Node toolchain in `web/`); a component framework (good with streaming state, but a rewrite of the locked prototype).
- **User's words:** *"Lock topic 2 as T4.2: option A as proposed."*
- **Date:** Oct 24, 2026
- **Log:** `BUILD_LOG.md`, "Oct 24, 2026, 18:52 CDT — Phase 3: Architecture, Area 4 (the frontend stack, T4.2)"

### T4.3 Where Areas 1 to 3 change the prototype (amends T3.1: the reader fetches whole opinions from the web service)

- **Decision:** Area 4, topic 3. The prototype (T4.1) keeps its look; only these change:
  1. **Source cards (P2.3: no discards).** A card starts **Found** and becomes **Kept** with Claude's reason; a re-keep replaces the reason (T1.7). When the answer is done each card ends **kept and cited** (its hue), **kept, not cited** (its hue, labelled) or **not kept** (grey, folded to one line, no reason). The count reads "N found, K kept". Real IDs (`katz-3-p12`, T1.6). "Found by" lists every search or read that returned the passage; a passage matched again gets no new card. A paragraph's footnotes sit folded inside its card; a footnote gets its own card only when a search matches it alone or it is kept (T1.6). Passages from reads get cards too, folded like the rest.
  2. **No syllabus card or syllabus reader** (P1.13). The slip-opinion note for *Chatrie* stays.
  3. **Hues:** the four Evergreen source hues repeat in keep order (up to 40 kept, T1.7); the passage-ID pill after each citation tells same-hued passages apart.
  4. **The update-check band** takes T2.3's shape in the prototype's style: the outcome line; each finding with its source links (title, domain, "published … (Exa's estimate)", T2.2); the overview styled as the prototype's "Claude's summary"; one parameter list per search (up to 3) with our fixed settings on one line (T2.1); incomplete searches (T2.4); a folded list of every page returned. Links open with `noopener noreferrer` (T3.7).
  5. **The checks** (T1.12): the step is "Checking the answer"; the wavy red underline marks each flag (a quotation not found word for word in the kept passages; a full citation not in this corpus); one summary line under the answer. Composition citations are T1.9's document block ranges, and `submit_answer` has no `kept` list (T1.10).
  6. **"View source" (6a):** the web service serves **one file per opinion**, generated by script from the committed `data/corpus/` when its image is built; the reader fetches one when it opens. Replays stay off the API (brief §7.4). Opinions carry page starts and page breaks per paragraph. The reader's credit line names each case's actual text source from the manifest. **Amends T3.1**'s "the page does not fetch a separate corpus" for the reader; passage text still travels in the events, and both copies come from the same commit.
  7. **"View API calls" (7b):** the events carry the **exact fragments** for each passage, each tagged with its request or response number and its path in the message (for example `messages[4].content[2]`): Claude's search or read call; the passage's block in the tool result, header included; Claude's keep call; its document in the composition request, `context` included; the answer blocks that cite it. About 100 to 200 KB more events a run (estimate). Web results never appear (P1.3). A passage never kept ends with a note that it was not sent to the composition call.
- **Considered:** for the reader, an API endpoint (wakes the API for replays) or whole opinions in the events (heavy, mostly unread); for the API window, rebuilding the JSON on the page from the events (could show something other than what was sent).
- **User's words:** *"Lock topic 3 as T4.3: the seven changes as proposed, 6(a) and 7(b)."*
- **Date:** Oct 24, 2026
- **Log:** `BUILD_LOG.md`, "Oct 24, 2026, 18:54 CDT — Phase 3: Architecture, Area 4 (where Areas 1 to 3 change the prototype, T4.3)"

### T4.4 New pieces in the prototype's style (settles T3.7's follow-up question)

- **Decision:** Area 4, topic 4. Every piece goes in an element the prototype already has (the status line above the composer, the step list, the answer section, the landing chips), styled like what is there; all wording is a placeholder for Area 5.
  1. **Waking (T3.6):** the landing check shows nothing. Pressing Research before the server is ready still glides the question into the chat; the first step reads "Starting the research server" and the status line shows the seconds elapsed. After 90 s the step says it is taking longer than usual and offers the recorded runs as chips in place; after 5 minutes it stops and shows "Try again", which starts a fresh check, never a run.
  2. **Paused by a cap (T3.4):** when `/health` reports live research paused, the landing input is disabled with the brief §7.2 message beneath it and the chips still work; when `POST /runs` refuses, the refusal is the run's last step. Atlas unreachable is shown the same way, with its own message.
  3. **Reconnecting (T3.1, T3.2):** "Reconnecting…" in the status line; the missed steps then arrive as usual; a pause and a resume are each a step.
  4. **Retries (T3.3):** a line inside the step (for example "Claude call failed (overloaded); retrying, attempt 2 of 3"); a call that still fails marks its step failed.
  5. **Interrupted and abandoned (T3.1, T3.2):** a last step under the stored steps, with what was gathered still on screen.
  6. **Reload:** goes straight back into the run, from the run ID in sessionStorage (T3.2).
  7. **The Voyage warning (T3.3)** sits above the answer, styled like the scope note (T1.10), not in red (red is for check flags only).
  8. **Stop labels:** at the top of the answer for the step limit, token ceiling, time limit or an error (T1.11, T3.3, T3.5); at the end for cut off at the length limit or incomplete.
  9. **A failed composition** is shown as an error with the kept passages still in the panel; no try-again button (it would be a new paid call); the visitor can ask again.
  10. **No-sources replies** (out of scope, nothing found) take the answer's place, labelled as Claude's reply with no sources (T1.10).
  11. **Replays (brief §7.4):** "Recorded run, <Chicago date>" at the top of the conversation and in the status line; played at the recorded pace; "Skip to the end" for replays only.
  12. **One question per run (T3.7):** "Ask another question" starts a fresh run screen, conversation and sources cleared, rather than adding to the chat, since a growing chat would suggest memory of the earlier question; a short line by the composer says each question is researched from scratch.
- **User's words:** *"Lock topic 4 as T4.4 as proposed."*
- **Date:** Oct 24, 2026
- **Log:** `BUILD_LOG.md`, "Oct 24, 2026, 18:56 CDT — Phase 3: Architecture, Area 4 (new pieces in the prototype's style, T4.4)"

### T4.5 Costs on the page: a run total for Claude and Exa, and each response's exact usage

- **Decision:** Area 4, topic 5 (left open by T3.1):
  - **(B) One total line when a run ends**, for Claude (the research loop and the answer) and Exa, **labelled as covering those two**, for example "14 calls · 186,000 input tokens, 142,000 from cache · 6,300 output · about $0.24 at list prices (Claude and Exa)"; expanding it splits the total into the loop, the answer and Exa.
  - **(D) "View API calls"** shows each Claude response's exact `usage` object, part of T4.3's exact fragments.
  - **Voyage is not shown**, since its use is very likely within its free tokens. **T3.4 is unchanged:** the caps still count Voyage at list price.
  - **No per-step figures** in the step log. Replays show their recorded figures, labelled with the prices of their recording date. Wording Area 5, including that these are list prices computed by our code.
- **User's words:** *"Voyage is very likely free because we make so few requests that it'd still be within free tier even tho I added money to the account and am at Tier 1. So just total up Claude and Exa code with option B and D?"* Then: *"This matches what I wanted. Lock area 4."*
- **Date:** Oct 24, 2026
- **Log:** `BUILD_LOG.md`, "Oct 24, 2026, 19:00 CDT — Phase 3: Architecture, Area 4 (costs shown, T4.5)"

### T5.1 The standing lines (settles brief defaults 2 and 6)

- **Decision:** Area 5, topic 1. The page's standing wording, final text:
  1. **Landing pitch:** *"Ask about the Fourth Amendment and surveillance technology, from wiretaps to phone location data. Claude searches 32 Supreme Court cases, keeps the passages that bear on your question, and writes an answer whose every citation leads to the exact sentences it rests on."*
  2. **The trace figure's caption:** *"Each cited sentence carries a citation the Claude API returned: which kept passage it rests on, and exactly which of that passage's sentences. Follow one from the answer, to those sentences in the passage, to the part of the API response that links them."* The figure's JSON shows the custom-content citation shape (T1.9), confirmed in build tests.
  3. **Not-legal-advice line:** *"Research, not legal advice: it shows what the Court said and never applies it to your situation. It does not tell you whether a case is still good law, and it can miss relevant passages."*
  4. **AI disclosure,** always starting its own line (T4.1): *"This is AI. Claude, Anthropic's AI model, does the research and writes the answers through the Claude API. Check what it says against the opinions and linked sources before relying on it."* It meets the Usage Policy's disclosure and the Commercial Terms' checking notice (licensing.md §5). Model names go in the credits and the API window, not this line.
  5. **Affiliation and the repository:** *"Independent project. Not affiliated with Anthropic. Source code on GitHub."*, the last sentence linking to https://github.com/NguyenTran2002/probable-clause. The author's name does not appear on the page.
  6. **Sources and credits** (folded): *"Opinion text: 25 cases from CourtListener (Free Law Project), 6 from the official U.S. Reports on GovInfo (U.S. Government Publishing Office), and* Chatrie *from the Court's slip opinion (supremecourt.gov). Free Law Project did not produce, review or endorse this analysis."* *"Built with the Claude API (research on Claude Sonnet 5.5, answers on Claude Opus 5.5), Voyage AI for meaning search (voyage-law-2, rerank-3), and Exa's MCP server for the update check."* *"Code under the Apache License 2.0. The opinion text is public domain and not covered by that licence."* No logos (P1.5; licensing.md §2, §4), no font credit. The counts are the corpus README's; the model names follow T1.8 and change with it.
  7. **The reader's credit line,** one per source type (T4.3): *"Text from CourtListener (Free Law Project), checked against the official U.S. Reports. Unofficial."*; *"Text from the official U.S. Reports (GovInfo), normalised. Unofficial."*; *"Text from the Court's slip opinion (supremecourt.gov), subject to formal revision. Unofficial."*
  8. **"Live"** (brief default 6, settled): the site and the API may be called "live" once they are actually up on Cloud Run, never before; "live research" stays a feature name; "production", "deployed" and "shipped" stay off as status claims (brief §10.6).
  9. **Code licence** (brief default 2, settled): Apache 2.0. The `LICENSE` file is added at the start of Phase 4 with the scaffold.
- **User's words:** *"1. We can link to the repo, which is https://github.com/NguyenTran2002/probable-clause. No need to mention my name though. 2. Leave out it is. 3. I'll give it Apache 2.0. 4. We're going with 2b anyway. 5. Live wording is correct."* Then: *"Lock."*
- **Date:** Oct 24, 2026
- **Log:** `BUILD_LOG.md`, "Oct 24, 2026, 19:14 CDT — Phase 3: Architecture, Area 5 (the standing lines, T5.1)"

### T5.2 The guarantee, coverage, checks, cost label and text-status note (rewords T1.12's example line)

- **Decision:** Area 5, topic 2, every recommended draft. Final text; figures in angle brackets or shown as examples are filled by code (counts and dates from the manifest and the run):
  1. **The guarantee, on every passage card:** *"This passage appears word for word in this opinion, as normalised from the official text."* (replaces brief §7.2's "This passage appears verbatim in this opinion.", since the corpus copy is normalised).
  2. **The coverage line:** *"The corpus holds 32 Supreme Court cases decided from 1878 to June 29, 2026, pulled from its sources Oct 23, 2026."* The folded credits list all three dates of brief §2: *"Latest decision in everything pulled: June 29, 2026. Latest in the corpus: June 29, 2026. Pulled: Oct 23, 2026."*
  3. **The answer key:** *"Underlined sentences cite a passage Claude kept; hover or tap one to see the exact sentences it cites. A citation shows where the words are, not that they prove the point, so read the passage. Sentences without a line are Claude's own synthesis and have no source."*
  4. **The checks** (T1.12): the line under the answer, for example *"Checked by this site's code, not by AI: 12 quotations found in the passages Claude kept · 4 full case names and U.S. Reports citations found in the corpus · 1 not in this corpus:* Entick v. Carrington*. Short case names, such as "Katz", are not checked."*; the quotation flag *"Quotation not found in the passages Claude kept. Check it against the opinions before relying on it."*; the citation flag *"Not in this corpus. This check knows only the 32 cases here, so a real case outside them is flagged too."* (P1.10); a check with nothing to check says so (*"No quotations to check."*). This replaces T1.12's example line ("found word for word in the cited passages"), since the quotation check compares against the kept passages and allows standard quoting edits.
  5. **The cost line** (T4.5): *"This run: 14 calls · 186,000 input tokens, 142,000 from cache · 6,300 output · about $0.24 at list prices (Claude and Exa)."* Expanded: research, answer and Exa, then *"Computed by this site from each response's token counts and the providers' list prices; not an invoice. Voyage AI, used for meaning search, is not included."* Replays add *"Recorded <date>, priced at that date's list prices."*
  6. **The text-status note,** in the reader and the folded credits: *"The opinion text is unofficial; only the U.S. Reports are authoritative. It was normalised from the sources above: page numbers and running heads were removed (U.S. Reports pages are shown in the margin instead), words broken across lines were rejoined, and every quotation mark was made straight. The syllabus, counsel listings and lineup are left out, since they are not the Court's words. A few misreadings in the sources were corrected against the printed page."* *Chatrie*'s slip-opinion notice is T5.1's reader credit line.
- **User's words:** *"Lock topic 2 as T5.2 with the recommended drafts."*
- **Date:** Oct 24, 2026
- **Log:** `BUILD_LOG.md`, "Oct 24, 2026, 19:18 CDT — Phase 3: Architecture, Area 5 (the guarantee, coverage and checks, T5.2)"

### T5.3 The update-check band's wording (replaces brief §6.4's draft label and guarantee sentence)

- **Decision:** Area 5, topic 3, every recommended draft. Final text; angle brackets are filled by code from the run:
  1. **Honesty label,** under the heading "Update check": *"A convenience, kept apart from the evidence above. Claude searched the web for later developments, with the settings listed below. Finding nothing does not mean nothing has changed: a web search can miss pages, and a date filter skips pages with no published date."*
  2. **Guarantee sentence** (replaces §6.4's "text as fetched from that page", T2.3): *"Each statement is Claude's own summary, linked to the pages it names. This site's code confirms only that those pages came back from the search in this run, not that they say what the statement reports. Open the links to check."* The page never calls the links or statements verified.
  3. **The band's parts:** findings headed *"What the search found, in Claude's words"*; the overview labelled *"Claude's overview (its own synthesis)"*; each link *"<title> · <domain> · published <date> (Exa's estimate)"* or *"no published date"*; *"Settings Claude chose"*, every field listed, unset ones *"not set"*; the fixed line *"Set by this site: up to 10 results a search, at most 3 searches a run, each page's text cut at 4,000 characters before Claude reads it, no Exa highlights or summaries."*; the folded list *"Every page the search returned (<n>), including those Claude did not mention"*.
  4. **Outcome lines** (worked out by code, T2.3): found shows the findings with no extra line; nothing relevant *"Nothing relevant found. That does not mean nothing has changed."*; skipped and declined keep *"Update check skipped: <reason>"* (T1.10) and *"Update check declined after reminder"* (brief §5.4), each with *"Claude's reason: <reason>"*; unavailable *"Update check unavailable: this month's web search credit is used up. It returns on the 1st."* (402) or *"Update check unavailable: the web search service refused this site's key."* (401); an incomplete search *"This search did not complete; nothing came back."*; not summarised *"Not summarised: the run stopped before Claude summarised these searches. The pages they returned are listed below."*
  5. **The pointer under the answer,** only on "found" (T1.11): *"The update check found later material that may bear on this. It is not part of the evidence for this answer; see the update check above."*
  6. **The update step in the step log:** *"Searching the web for later developments"*; done, *"Searched the web: <n> pages returned, <k> with no published date. Linked in the update check, never quoted."*
- **User's words:** *"Lock topic 3 as T5.3 with the recommended drafts."*
- **Date:** Oct 24, 2026
- **Log:** `BUILD_LOG.md`, "Oct 24, 2026, 19:21 CDT — Phase 3: Architecture, Area 5 (the update-check band, T5.3)"

### T5.4 Run states and stop labels

- **Decision:** Area 5, topic 4, every recommended draft. Final text for the states placed by T4.4; angle brackets are filled by code, and figures that are placeholders (90 s, 5 minutes, 60 s, 10 minutes, 3 attempts, 24 hours) follow their settings when measured:
  1. **Waking (T3.6):** step *"Starting the research server"*, status line *"<s> s"*; after 90 s *"This is taking longer than usual. After a quiet spell the server starts from cold. While you wait, you can watch a recorded run:"* with the chips; after 5 minutes *"The research server did not start. Try again, or watch a recorded run."* with a **Try again** button. Only after this build has measured starts (brief §7.2): *"Usually <a> to <b> s to start (measured <dates>; Google does not guarantee it)."*
  2. **Paused and unavailable (T3.4, T3.3):** daily *"Live research is paused for today. Recorded runs are still available. It reopens at midnight, Chicago time."* (brief §7.2 plus the reopening); monthly *"Live research is paused for the rest of this month. Recorded runs are still available. It reopens on the 1st."*; Atlas unreachable *"Live research is unavailable right now: this site cannot reach its spending records, so it will not start a paid run. Recorded runs are still available."*; a spend limit mid-run *"The run ended: this site's monthly API spending limit was reached. Live research is paused; recorded runs are still available."*
  3. **Connection (T3.1, T3.2, T3.7):** *"Reconnecting…"* (T4.4); paused *"Paused while this page was away. No new calls were made."*; resumed *"Resumed."*; abandoned *"This run stopped because the page was away for over a minute. No answer was written, and nothing more was spent. What was gathered is shown above."*; interrupted *"This run was interrupted: the server that held it is no longer running. The steps it recorded are shown above. Ask again to start a new run."*; expired *"This run is no longer stored. Runs are kept for 24 hours."*
  4. **Retries and failures in a step (T3.3):** *"Claude call failed (<overloaded / rate limited / server error / connection lost>); retrying, attempt 2 of 3"*; *"Meaning search call failed (<reason>); retrying, attempt 2 of 3"*; out of retries *"Failed after 3 attempts."*; not reranked *"Results in embedding order: reranking failed."*; a refusal *"The run ended: Claude declined to continue with this question."*
  5. **The Voyage warning (T3.3),** above the answer: degraded *"Meaning search was degraded for part of this research: some results were not reranked."*; unavailable *"Meaning search was unavailable for part of this research, so Claude searched by keyword only for that part."*
  6. **Stop labels (T1.11, T3.3, T3.5):** at the top: *"Stopped at step limit. Answer built from the evidence gathered so far."* (brief §5.7); *"Stopped at this run's token limit. Answer built from the evidence gathered so far."*; *"Stopped at this run's <10>-minute time limit. Answer built from the evidence gathered so far."*; *"Stopped by an error after retries. Answer built from the evidence gathered so far."*; with nothing kept, *"Stopped at <the limit> before Claude kept any passages, so no answer was written."* At the end: *"Cut off at the answer's length limit."*; *"Incomplete: the answer stopped partway because of an error. The checks ran on the part shown."* A failed composition: *"The answer could not be written: <reason>. The passages Claude kept are still in the sources panel. Asking again starts a new run."* A failed run with nothing kept: *"The run failed: <reason>. Nothing was kept, so no answer was written."*
  7. **No-sources replies (T1.10),** labelled *"Claude's reply · no sources"*: out of scope *"This question is outside what the corpus covers: Supreme Court opinions on the Fourth Amendment and surveillance technology."*; nothing found *"Claude found no passages in the corpus that bear on this question."*
  8. **Replays and one question per run (T4.4):** the banner *"Recorded run, <date>. A real run, replayed at its recorded pace. It makes no new calls."*; by the composer *"Each question is researched from scratch; Claude does not see your earlier questions."*
  9. **Rejections and the finish line:** a rejected submit is a step titled *"Submission refused by this site's rules"* showing the exact text sent to Claude (written with the prompts in the build, brief §5.4); the status line when done *"Finished: <n> tool rounds and the answer, <s> s."*
- **User's words:** *"Lock topic 4 as T5.4 with the recommended drafts."*
- **Date:** Oct 24, 2026
- **Log:** `BUILD_LOG.md`, "Oct 24, 2026, 19:25 CDT — Phase 3: Architecture, Area 5 (run states and stop labels, T5.4)"

### T5.5 The privacy note (amends T1.14: a rule on personal details in queries; amends T4.1: fonts served by our own web service)

- **Decision:** Area 5, topic 5 (T3.7's privacy note), facts in `docs/research/retention.md`:
  1. **The note, final text,** each provider's name linking to the page its claim comes from:
     > **Privacy.** Your question is sent to Anthropic, whose Claude model researches and answers it; Anthropic deletes it within 30 days, unless its safety systems flag it (up to 2 years) or the law requires otherwise. Claude's searches go to Voyage AI (meaning search; opted out of training Voyage's future models) and, for the update check, to Exa, which may keep and use search queries to improve its services; Claude is told to leave personal details out of them. Avoid putting anything in a question you would not want stored.
     >
     > This site keeps each run's steps, your question and the answer for 24 hours, so a dropped connection can resume, then deletes them. It keeps a record of each run without the question or answer (times, steps, tokens and cost) to track spending. No accounts, no cookies, no analytics; your browser holds only the current run's ID, until you close the tab. This site does not use or store IP addresses; the gateway in front of it and Google Cloud keep standard request logs, which include them, for 30 days. Recorded runs use questions chosen by the site's author; no visitor's run is ever recorded.
  2. **The query rule (amends T1.14, judgement rules):** the loop's system prompt tells Claude never to put names or other personal details from the question into meaning-search (Voyage) or web (Exa) queries, so the question itself reaches only Anthropic. Build tests check it with a question that carries a name.
  3. **Fonts served by our own web service (amends T4.1):** Instrument Sans, Newsreader and JetBrains Mono are served as `.woff2` files from the web service, with the SIL Open Font License text shipped beside them; no request goes to Google Fonts, so the page contacts no third party. No font credit on the page (T5.1).
  4. **Voyage's opt-out:** done by the user on the Voyage AI dashboard (Terms of Service, Section 3(iii)), Oct 24, 2026. MongoDB's docs describe a separate Atlas toggle; which applies depends on where the project's key was created, checked in Phase 4 from the key's endpoint, and if it is an Atlas key the Atlas toggle is turned off as well (the user's action).
  5. **The figures follow the settings:** 24 hours (T3.7), 30 days (Cloud Logging's default, the user's check for goodnight); a change to either changes the note.
- **User's words:** *"I checked myself, and goodnight keeps request logs for 30 days, the default, so your note's "30 days by default" is correct. Voyage AI is also dropped out as well."* Then: *"Add the query rule and self-host the fonts (amending T4.1). Lock the privacy note as T5.5."*
- **Date:** Oct 24, 2026
- **Log:** `BUILD_LOG.md`, "Oct 24, 2026, 19:36 CDT — Phase 3: Architecture, Area 5 (the privacy note, T5.5)"

### T5.6 The replays: five recorded runs, one on a corpus that ends before *Chatrie*

- **Decision:** Area 5, topic 6 (brief §2 Replay mode, §7.4):
  1. **Four replays on the full corpus,** the questions as the chips' text:
     - *"Can police search my phone when they arrest me?"* (a personal situation, research not advice; *Riley*)
     - *"Is getting someone's location history from Google with a geofence warrant a Fourth Amendment search?"* (*Smith* and *Miller* to *Carpenter* to *Chatrie*; the likeliest to make the update check find something)
     - *"Can police attach a GPS tracker to a car without a warrant?"* (*Knotts*, *Karo*, *Katz*, *Jones*; opinion types and dates)
     - *"Is it a search for police to fly a drone over someone's backyard?"* (no drone case in the corpus; *Ciraolo* and *Florida v. Riley*; the honest edges and the update check)
  2. **A fifth replay on a corpus that ends before *Chatrie*** (brief §7.4, taken): the geofence question recorded against the corpus without *Chatrie* (latest case *Carpenter*, 2018), so the update check can be seen finding it; labelled *"Recorded with a corpus that ends before* Chatrie v. United States *(June 29, 2026), to show the update check finding it. Live research uses the full corpus."* Built as a recording-only switch that drops the one case from the index, the vectors, the catalog and the coverage dates; never available to the live API; tested like the rest.
  3. **Recording rules:** a replay is a real run exported from its events and never edited; the user reviews each recording before it is published, and a run that went wrong is either published as it is, with its flags, or re-recorded, the user's call each time; each file carries its recording date, the commit, the models and that date's prices (T4.5); a replay is re-recorded only deliberately, with the user (for example after the prompts change).
  4. **Spend:** about $2 to $3 in Phase 5 (estimate), approved by the user then. The five chips are measured at phone width (T4.1).
- **User's words:** *"Lock topic 6 as T5.6: the four recommended questions, the pre-Chatrie replay as the fifth, and the recording rules as proposed."*
- **Date:** Oct 24, 2026
- **Log:** `BUILD_LOG.md`, "Oct 24, 2026, 19:39 CDT — Phase 3: Architecture, Area 5 (the replays, T5.6)"

## Phase 4: Build (decided in advance)

### P4.1 The build plan: contract first, two waves of subagents, a local review before any deploy — AMENDED by P4.28 (item 5: the main session builds the frontend); clarified 16:38, Oct 25 (the local review)

- **Decision:** The Phase 4 build plan (brief §3, §12), proposed by Claude and locked by the user:
  1. **Step 0, the main session only:** the scaffold (`LICENSE` Apache 2.0, `api/`, `tests/`, `contracts/`; every dependency added at once, since only the main session touches `pyproject.toml`); T1.5 (no subagent); **interfaces contract v1** (`docs/design/contract.md` and `contracts/events.schema.json`: endpoints, run states, Atlas collections, a settings table with each value's basis, the price table, the per-opinion and replay formats, every module's signatures), checked against T1.1 to T5.6 by an **Opus 5.5 xhigh** subagent not shown the main session's reasoning; the prompt drafts for the user's review (T1.14), written while Wave 1 runs.
  2. **Wave 1, six subagents in parallel,** each on its own paths, tests first, against fakes, no paid calls and no keys: A, the sentence splitter and its check (T1.9), **Opus xhigh**; B, the corpus index (loader, FTS5 keyword search, `read_passages`, filters, reader-file generator, the pre-*Chatrie* switch), Sonnet high; C, meaning search (the paced embedding script, vectors file, in-memory search, rerank, degraded mode), Sonnet high; D, the Exa wrapper (T2.1 to T2.5), Sonnet xhigh; E, money and state (Atlas layer, atomic reservation, ledger, budget stops, price table, retry wrapper, `spend_report.py`), Sonnet xhigh; F, the answer checks (T1.12, T2.3), Sonnet xhigh.
  3. **Wave 2, after Wave 1 is merged:** G, the research loop and composition, **Opus xhigh**; H, the API and run lifecycle, **Opus high**; I, the images and the deploy script (written, never run), Sonnet high. The goodnight block stays with the main session, on the user's green light.
  4. **Checks:** a Sonnet high review of each builder's work against its contract section, including `git status` for writes outside its paths; the main session runs the tests and commits each agent's paths by name (agents never commit); one **Opus xhigh** review at the end of the honesty-critical paths (citation mapping to kept passages, the two checks, the spend reservation, the heartbeat gate before paid calls).
  5. **The frontend** is built by the frontend session (P0.3), from the locked prototype against contract v1, not by a subagent.
  6. **Integration:** the offline suite; the paid build tests, with an **Anthropic ceiling of $3 for Phase 4**, the corpus embedding on Voyage and at most 10 Exa searches, each priced before it runs; the user's review of the prompts before their first paid run; **then the whole stack run locally for the user's review** (the API on 8000 and the web service on its own port, the deploy images if Docker is available here, live runs recorded in `Probable_Clause_test`, the hard-to-reach states walked through, fixes shown locally again); **only after the user's sign-off, and a separate green light,** the deploy and the first cold-start sample.
  7. **Subagent models:** Sonnet 5.5 or Opus 5.5, at high or xhigh effort only, never below high and never max, for either model. Extends P2.5 (Phase 2, Sonnet only) to Phase 4 and replaces brief §3's "Subagents run on Opus".
- **User's words:** *"You're allowed to use both Sonnet 5.5 and Opus 5.5 subagents. Never use any effort level below high, and you're also barred from ever using max effort level as well (for both models)."* Then: *"Plan looks right, but I want to add that we have to spin things up locally for review first before any deploy."* Then: *"Lock. Proceed."*
- **Date:** Oct 24, 2026
- **Log:** `BUILD_LOG.md`, "Oct 24, 2026, 19:58 CDT — Phase 3: Architecture, the Phase 4 build plan (P4.1)"

### P4.2 The corpus has 2,462 passages (corrects T3.6's "2,748 units")

- **Decision:** The searchable units, and so the rows of the vectors file, are **2,462 passages**: 1,964 content paragraphs and 498 footnotes, counted by script on Oct 24, 2026 after T1.5. T3.6's "the 2,748 units' voyage-law-2 vectors (1,024 dimensions, 11.3 MB as float32)" also counted the 286 section headings, which T1.6 says are never passages. The vectors file is therefore about 10.1 MB (2,462 × 1,024 × 4 bytes). Nothing else in T3.6 changes. Found while writing contract v1 and confirmed by the Opus review (contract §3).
- **User's words:** *"On the 2,462 passages count, record the correction as its own decisions entry."*
- **Date:** Oct 24, 2026
- **Log:** `BUILD_LOG.md`, "Oct 24, 2026, 20:50 CDT — Phase 4: Build, the passage count corrected (P4.2)"

### P4.3 A submit refused by the copy guard is stored with its flagged statements withheld (amends T3.1)

- **Decision:** When the copy guard (T2.3) refuses a `submit_answer`, the `tool_call` event stored and streamed for it (and so Atlas and any replay) carries Claude's input exactly, **except that each statement the guard flagged** (in `update_findings` or `update_overview`) is replaced by *"[statement withheld: it repeated a page's words]"*. Claude's own conversation keeps its input unchanged; it goes only to Anthropic and is never stored by this site. The refusal message to Claude names the statement by number and the page by its ID and never quotes the page (contract §4.F). This amends T3.1's "tool call (exactly what Claude sent)" for this one case, so that no web page text is stored or shown (T2.2, P1.3, P1.7). The step log still shows that the submit was refused, by which rule, and which statement was withheld.
- **Considered:** withholding all findings of a refused submit (hides statements that passed the guard); keeping the input exact (page text in Atlas and published replays, against P1.7).
- **User's words:** *"On copy guard, can you give me more context here?"* Then: *"Lock option A: redact only the flagged statements in the stored and streamed event."*
- **Date:** Oct 24, 2026
- **Log:** `BUILD_LOG.md`, "Oct 24, 2026, 20:52 CDT — Phase 4: Build, the copy guard and stored events (P4.3)"

### P4.4 No spend tripwire: every run finishes gracefully

- **Decision:** No tripwire stops a run when its recorded spend reaches its reservation. Spend stays bounded by the run's own limits (T3.3's token budgets, the composition bound, Voyage's per-run bound, Exa's three searches), and every run ends through one of its normal end states, never cut off by a spend check.
- **Considered:** a backstop in H's `record_usage` refusing further loop and search calls once spent plus the composition's reserve reached the reservation, ending the run as a logged fault (raised by the cross-part review, Oct 25, 2026).
- **User's words:** *"No trip wire for a run. I want every run to finish gracefully."*
- **Date:** Oct 25, 2026
- **Log:** `BUILD_LOG.md`, "Oct 25, 2026, 00:41 CDT — Phase 4: Build, no spend tripwire (P4.4)"

### P4.5 A broken loop attempt is counted from what it streamed and reported — AMENDED by P4.10 (composition attempts too)

- **Decision:** When a loop call's stream breaks partway, the attempt is priced and counted against the run's output budget from what the stream reported and what it visibly streamed, as built (G's estimate from the streamed characters, at a ratio that errs high). It is not counted at its full `max_tokens`. Thinking tokens billed but never streamed (`display: "omitted"`, T3.1) can therefore go uncounted, up to about $0.08 for a loop attempt, and the run's spend may pass its reservation by that much. Every completed call is priced from Anthropic's final reported usage, which includes all thinking tokens.
- **Considered:** counting a broken attempt at its full `max_tokens` (safe, but one break would spend the loop's remaining output budget and end research).
- **User's words:** *"Broken stream, counting at full max tokens is too much compared to what could have been. Rely on what we have so far is fine. It's only a round."*
- **Date:** Oct 25, 2026
- **Log:** `BUILD_LOG.md`, "Oct 25, 2026, 00:46 CDT — Phase 4: Build, broken loop attempts counted as streamed (P4.5)"

### P4.6 The composition's room raised to its worst case; the run's input limit 436,000; the note capped (amends P2.7, T1.10, T3.4) — SUPERSEDED by P4.18 and P4.21 (no composition reserve, no run-wide input limit; the note cap stands)

- **Decision:** `COMPOSITION_RESERVE_INPUT` is 66,000 tokens. That is the composition's worst case by the loop's own estimator, 64,945 tokens (the 40 longest passages, each with a 300-character keep reason, a 2,000-character question and a 1,000-character note), plus a small margin. The loop keeps its 370,000 (`LOOP_INPUT_BUDGET`), so the run's input limit (`RUN_INPUT_TOKENS`, P2.7's 400,000) becomes **436,000**. The visitor's `note` (and so the scope note) is capped at **1,000 characters**, with a refusal text drafted for the user's review (T1.14). The worst case reserved per run (T3.4's $1.674) becomes about **$2.11**. A test recomputes the composition's worst case from the corpus and the settings, so the figure cannot fall behind the code.
- **Considered:** a keep budget refusing keeps past a 30,000 reserve; keeping 400,000 with the loop at 335,000 (about $2.01); no note cap (about 448,000 and $2.25); a lower `KEEP_CAP`.
- **User's words:** *"Increase the budget to accommodate the worst case, which is rare anyway."* Then: *"Keep the loop at 370,000 and raise the run's limit to about 435,000."* Then, on the list of five (the margin and the cap included): *"Confirm."*
- **Date:** Oct 25, 2026
- **Log:** `BUILD_LOG.md`, "Oct 25, 2026, 01:01 CDT — Phase 4: Build, five decisions after the cross-part review (P4.6 to P4.10)"

### P4.7 An out-of-scope reply needs no update check (amends T1.10) — SUPERSEDED by P4.19 (no rule 4)

- **Decision:** T1.10's rule 4 (no update check and no skip reason: refused once) is waived when `out_of_scope` is true, so a greeting or an off-topic question is never pushed toward a paid Exa search. This matches the system prompt's "No search is needed."
- **Considered:** keeping rule 4 for every submit, as T1.10 has it.
- **User's words:** *"Scope refusal should not trigger update search."* Then: *"Confirm."*
- **Date:** Oct 25, 2026
- **Log:** `BUILD_LOG.md`, "Oct 25, 2026, 01:01 CDT — Phase 4: Build, five decisions after the cross-part review (P4.6 to P4.10)"

### P4.8 The copy guard covers a no-sources reply's note once a page was returned (amends T2.3) — AMENDED by P4.13 (`update_skip_reason` is guarded too); SUPERSEDED by P4.19 (research never sees a page; its note is not guarded)

- **Decision:** On a no-sources reply (out of scope or nothing found), when any update search has returned a page in the run, the `note` gets T2.3's copy guard: `COPY_GUARD_WORDS` or more consecutive words of a returned page refuse the submit, with a refusal asking for it to be reworded, and the flagged note is withheld in the stored `tool_call` as P4.3 does. Keep reasons, the scope note of an answered run and `update_skip_reason` stay unguarded.
- **Considered:** guarding keep reasons, every note and the skip reason too (the cross-part review's suggestion); leaving T2.3 as it was.
- **User's words:** *"keep reason has nothing to do with Exa, don't extend the guard here … no-source reply maybe, and only then do we extend. Update skip reason also has no Exa content because the update is skipped so we shouldn't extend it here."* Then: *"Confirm."*
- **Date:** Oct 25, 2026
- **Log:** `BUILD_LOG.md`, "Oct 25, 2026, 01:01 CDT — Phase 4: Build, five decisions after the cross-part review (P4.6 to P4.10)"

### P4.9 The copy guard ignores words that are also the corpus's (amends T2.3)

- **Decision:** Every copy-guard check, the update statements' and overview's included, ignores a run of words that also appears in the corpus. A page quoting the Supreme Court, and Claude quoting the same Court words, is not a copy of the page.
- **Considered:** the guard as T2.3 has it, which would refuse a statement or note quoting the Court whenever a returned page quotes the same words.
- **User's words:** *"Your recommendations on handling false match is sound."* Then: *"Confirm."*
- **Date:** Oct 25, 2026
- **Log:** `BUILD_LOG.md`, "Oct 25, 2026, 01:01 CDT — Phase 4: Build, five decisions after the cross-part review (P4.6 to P4.10)"

### P4.10 A broken composition attempt is counted as streamed too (amends P4.5)

- **Decision:** A composition attempt whose stream breaks before its first block is priced and counted from what it streamed and reported, as P4.5 does for loop attempts, never at its full `max_tokens`: counting 12,000 would spend the run's output ceiling and stop the retry T3.3 allows, so the run would end with no answer (against P4.4). Retries bound it to two such attempts, and most such failures (429, 500, 529) come before anything is generated; hidden thinking on a stream broken mid-thinking can go uncounted, up to about $0.24 an attempt, $0.48 a run.
- **Considered:** counting at `max_tokens`.
- **User's words:** *"Don't count as stream because we have our max retries guards working here right? Push back?"* The main session read it as "counted as streamed", and said so. Then: *"Confirm."*
- **Date:** Oct 25, 2026
- **Log:** `BUILD_LOG.md`, "Oct 25, 2026, 01:01 CDT — Phase 4: Build, five decisions after the cross-part review (P4.6 to P4.10)"

### P4.11 The daily cap is $15 (amends P2.7)

- **Decision:** `DAILY_CAP_USD` is $15, up from $10. At P4.6's $2.106 worst case, seven runs can hold a reservation at once (at $10 it would have been four; T3.5 had about five at $1.67). The monthly cap stays $60.
- **Considered:** keeping $10, with four reservations at once.
- **User's words:** *"Raise daily cap to $15."*
- **Date:** Oct 25, 2026
- **Log:** `BUILD_LOG.md`, "Oct 25, 2026, 12:09 CDT — Phase 4: Build, five decisions on the overnight report (P4.11 to P4.15)"

### P4.12 A run's spend may pass its reservation through failed composition attempts — SUPERSEDED by P4.21 (no reservation)

- **Decision:** The worst case stays $2.106. It reserves input only for the two failed composition attempts, while P4.10 also prices their streamed output, so a run's recorded spend can pass its reservation: typically by cents, by $0.48 at most. The caps stay correct, because every cost is settled as spent.
- **Considered:** reserving that output too ($2.586 a run).
- **User's words:** *"Retried answers can pass the reservation is fine."*
- **Date:** Oct 25, 2026
- **Log:** `BUILD_LOG.md`, "Oct 25, 2026, 12:09 CDT — Phase 4: Build, five decisions on the overnight report (P4.11 to P4.15)"

### P4.13 The copy guard covers `update_skip_reason` too (amends P4.8) — AMENDED by P4.19 (the skip reason is guarded in `submit_update`)

- **Decision:** Once an update search has returned a page in the run, `update_skip_reason` gets T2.3's copy guard on every submit. A skip reason repeating `COPY_GUARD_WORDS` or more consecutive words of a returned page refuses the submit (rule `copy_guard`) and is withheld in the stored and streamed `tool_call`, as P4.3 does. Its refusal text mirrors the approved `copy_guard_note`. Keep reasons and an answered run's scope note stay unguarded (P4.8).
- **Considered:** leaving it unguarded, as P4.8 did ("because the update is skipped"); refusing or dropping a skip reason once a search counted.
- **User's words:** *"update_skip_reason: give it the guard."*
- **Date:** Oct 25, 2026
- **Log:** `BUILD_LOG.md`, "Oct 25, 2026, 12:09 CDT — Phase 4: Build, five decisions on the overnight report (P4.11 to P4.15)"

### P4.14 The composition's worst case is counted by the loop's estimator — SUPERSEDED by P4.21 (no reserve to count against)

- **Decision:** `COMPOSITION_RESERVE_INPUT` (P4.6) bounds the composition's input as the loop's estimator counts it (characters over the corpus's characters-per-token ratio), not as the tokenizer does. Text that tokenizes densely can run past it by about $0.04 a run; that is logged and never stopped (P4.4).
- **Considered:** a larger margin.
- **User's words:** *"Accept the limit of our estimator."*
- **Date:** Oct 25, 2026
- **Log:** `BUILD_LOG.md`, "Oct 25, 2026, 12:09 CDT — Phase 4: Build, five decisions on the overnight report (P4.11 to P4.15)"

### P4.15 The prompt and refusal drafts are approved (T1.14)

- **Decision:** The drafts written for the user's review are approved as written:
  - `loop_messages.json`'s `unknown_tool`, `submit_accepted_note`, `submit_accepted_answer`, `composition_scope_note` and `composition_coverage`;
  - `rejections.json`'s `submit.out_of_scope_no_note`, `submit.note_too_long`, `submit.copy_guard_note` and `submit.copy_guard`;
  - `tools.json`'s note length line.
- **User's words:** *"Wording look goods to me."*
- **Date:** Oct 25, 2026
- **Log:** `BUILD_LOG.md`, "Oct 25, 2026, 12:09 CDT — Phase 4: Build, five decisions on the overnight report (P4.11 to P4.15)"

### P4.16 `submit_answer` alone in its turn, once (amends T1.10 rule 1)

- **Decision:**
  - `submit_answer` must be the only call in its turn, and sent once. A turn holding two or more submits, or a submit with any other tool (`keep_passages` included), has every submit refused; the turn's other tools still run and their results go back with the refusal. The rule name stays `same_turn`. This replaces T1.10 rule 1's "A keep in the same turn is fine" and contract v1.3's "a keep in the same turn counts".
  - **Three texts, as drafted:** `rejections.json`'s `submit.rule_1_same_turn`; `tools.json`'s `submit_answer` description (submitting ends research at once; alone, once, every field in one call); `loop_system.md`'s "Submitting" item ("Submitting ends the research"). The exact texts are in the log entry.
  - **Why:** in the paid build tests Claude split its submit into two calls in one turn twice in three answered runs; the last accepted won, losing a relevant update finding (test 3) and a scope note and overview (test 4).
- **User's words:** *"Refuse 2 or more submission in a turn. I'd also add that a submission tool call must be its own turn with no extra tool accompanying it."* Then: *"Lock P4.16: submit_answer alone in its turn, once; other tools in that turn still run; keep the rule name same_turn; the three prompt texts as drafted. Then build it, contract v1.8."*
- **Date:** Oct 25, 2026
- **Log:** `BUILD_LOG.md`, "Oct 25, 2026, 12:42 CDT — Phase 4: Build, `submit_answer` alone in its turn (P4.16)"

### P4.17 The quotation check ignores letter case (amends T1.12)

- **Decision:** the quotation check compares a quotation with the kept passages without regard to letter case, throughout. The answer keeps the quotation exactly as Claude wrote it. Every other rule of T1.12 and contract §4.F stands (ellipses, brackets, the negation guards, the four-word minimum). It gives up the strict convention of bracketing a re-cased letter and the rare reading carried by a capital alone.
- **Why:** in the paid build tests a real *Kyllo* quotation, capitalised at the start of a lead-in, was flagged as not found; a visitor would read that as an invented quotation.
- **User's words:** *"I think we should decapitalize everything before comparison check as best practice?"* Then: *"Lock P4.17: the quotation check compares without regard to letter case throughout; the answer keeps the quotation as written. Then build it."*
- **Date:** Oct 25, 2026
- **Log:** `BUILD_LOG.md`, "Oct 25, 2026, 12:55 CDT — Phase 4: Build, the quotation check ignores letter case (P4.17)"

### P4.18 Looser limits, each a backstop that almost never fires (amends P2.7, T1.11, T2.1, T3.3; supersedes P4.6's limits)

- **Decision:** `LOOP_INPUT_BUDGET` 2,000,000 (input only, over every research call); `UPDATE_INPUT_BUDGET` 2,000,000; `LOOP_OUTPUT_BUDGET` 16,000; `COMPOSITION_MAX_TOKENS` 16,000; `UPDATE_SEARCHES_PER_RUN` 5; `UPDATE_MAX_ROUNDS` 8 and `UPDATE_OUTPUT_BUDGET` 6,000 (placeholders); `MAX_ROUNDS` 12, `KEEP_CAP` 40 and the deadlines unchanged; `RUN_INPUT_TOKENS`, `RUN_OUTPUT_TOKENS`, `COMPOSITION_RESERVE_INPUT` and `FIXED_PREFIX_TOKENS_ESTIMATE` removed. The daily ($15) and monthly ($60) caps stand. Detail: `docs/design/wave3-design.md` §3 and §4.
- **User's words:** *"The goal here is to let all runs pass smoothly while having a sure back stop that will almost never be triggered unless something catastrophic has gone wrong. The daily budget and monthly budget stands though, however."*; *"2M for the loop's input."*; *"Update searches loosen to 5"*; *"UPDATE_INPUT_BUDGET 2M."*
- **Date:** Oct 25, 2026
- **Log:** `BUILD_LOG.md`, "Oct 25, 2026, 13:47 CDT — Phase 4: Build, looser limits (P4.18)"

### P4.19 The update check is its own step, beside the composition, continuing the research conversation (amends T1.10, T2.1, T2.3, P4.13; supersedes P4.7, P4.8)

- **Decision:** research ends with `submit_answer(out_of_scope, note?)` (no rule 4, no copy guard on the note; research never sees a page). The update step then runs beside the composition, continuing the research conversation for its cache (one tool list of seven and one system prompt; each step's tools refused in the other). It decides whether to search (up to 5) and ends with `submit_update` (rules `same_turn`, `no_check`, the findings checks, the copy guard). Our code turns it off when research never searched the corpus, or when Exa is unavailable. The band loses `declined`; the events gain `step`, `update_started` and `update_ended` (contract v2.0). Detail: design §2, §3, §5, §6.
- **User's words:** *"Untangling update from the research loop."*; *"we will let this step decide whether to call Exa or not. Specifically, we can enforce by code such as if a response from the research loop doesn't search the corpus at all, we will turn off update by code automatically (because it's an out of scope response)."*; *"Update step's input should take advantage of the cached research conversation at maximum. We're just separating them so that we have finer control."*
- **Date:** Oct 25, 2026
- **Log:** `BUILD_LOG.md`, "Oct 25, 2026, 13:47 CDT — Phase 4: Build, the update check as its own step (P4.19)"

### P4.20 Composition on Sonnet 5.5 at high effort (amends T1.8, T1.11)

- **Decision:** `COMPOSITION_MODEL` is `claude-sonnet-5-5` at high effort; uncached; only the kept passages as sources; the approved prompt unchanged. The user judges the quality in the next paid runs.
- **User's words:** *"Change composition to Sonnet at high effort and I'd judge the quality first. (No comparison run needed.) After all, this project is a tech demo of the citation feature, not a demo of how much smarter and more capable is Opus than Sonnet in constitutional laws."*; *"Keep composition uncached and passing it only kept passages."*
- **Date:** Oct 25, 2026
- **Log:** `BUILD_LOG.md`, "Oct 25, 2026, 13:47 CDT — Phase 4: Build, composition on Sonnet 5.5 at high effort (P4.20)"
- **Confirmed** after Wave 3's paid tests: *"I checked the answers, and quality is surprisingly good."* Log: `BUILD_LOG.md`, "Oct 25, 2026, 16:23 CDT — Phase 4: Build, composition on Sonnet confirmed after the paid tests (P4.20)".

### P4.21 No reservation: admission under the caps, spend recorded per call, at most 5 runs at once (amends T3.4, P2.7; supersedes P4.12, P4.14)

- **Decision:** a run starts only while today's and the month's spend are under the caps, the spend-limit flag is clear, and fewer than `MAX_CONCURRENT_RUNS` (5) runs are in progress; otherwise it is refused (`daily_cap`, `monthly_cap`, `spend_limit_paused`, `atlas_unreachable`, `busy`). Each paid call's cost is recorded as it happens; runs in progress always finish; it fails closed on Atlas. Reservations and the worst case as a gate go. The refusal texts are the main session's (design §5).
- **User's words:** *"I'd get rid of the reserve system. I'm willing to trade more cost overrun here because the cost is small and the budget still disable further runs once it's hit or overran."*; *"I also want to up maximum parallel runs to 5."*; *"you can write the polished version."*
- **Date:** Oct 25, 2026
- **Log:** `BUILD_LOG.md`, "Oct 25, 2026, 13:47 CDT — Phase 4: Build, no reservation (P4.21)"

### P4.22 Wave 3's development allowance

- **Decision:** Wave 3's paid tests start a fresh tally at $0 in `data/verification/wave3/spend.jsonl`, with $3.00 of Anthropic and 20 Exa searches; each paid test only on the user's go. The Phase 4 ledger closes at $1.6729 and 8 Exa searches. Production never counts development spend (its own Atlas database, its own Console workspace and key, T3.4).
- **User's words:** *"Reset the limit to 0 for our development. Additionally, Development cost should not count once we deploy production."* Then: *"Development allowance as you restated it: a fresh tally at $0, $3 Anthropic and 20 Exa searches."*
- **Date:** Oct 25, 2026
- **Log:** `BUILD_LOG.md`, "Oct 25, 2026, 13:47 CDT — Phase 4: Build, Wave 3's development allowance (P4.22)"

### P4.23 Wave 3's prompt drafts are approved (T1.14)

- **Decision:** The v2.0 drafts are approved as written: `loop_system.md` (one prompt for research and the update step), `tools.json` (seven tools, `submit_update`), `loop_messages.json` (`status_line`, `status_line_update`, `update_start`, `update_start_note`, `submit_update_accepted`), `rejections.json` (`submit_update`, `wrong_step`), and the refusal texts of contract §5.
- **User's words:** *"The prompt drafts are approved. Run the four Wave 3 paid tests under P4.22's allowance."*
- **Date:** Oct 25, 2026
- **Log:** `BUILD_LOG.md`, "Oct 25, 2026, 16:15 CDT — Phase 4: Build, Wave 3's prompt drafts approved (P4.23)"

### P4.24 The live Anthropic workspace and its key (T3.4)

- **Decision:** The user set up the live site's Console workspace with a $60 monthly limit and alerts at several break points. Its key goes into `.env` under its own name; a deployment script creates the GCP secret from `.env` without the session ever reading or printing the key.
- **User's words:** *"A separate Anthropic workspace for the live site with $60 monthly limit and alerts at multiple break points has been set up. I can put the new API key to .env, then you can have a deployment script programmatically create the secret in GCP without reading the key."*
- **Date:** Oct 25, 2026
- **Log:** `BUILD_LOG.md`, "Oct 25, 2026, 16:38 CDT — Phase 4: Build, the live Anthropic workspace and its key (P4.24)"

### P4.25 The cloud setup's credentials (T3.5)

- **Decision:** Project `probable-clause` (reserved by the user); Anthropic a separate live key (P4.24); Voyage and Exa the development keys; Atlas the same URI, production writing to `Probable_Clause` (`PC_ENV=live`).
- **User's words:** *"For cloud set up, I already reserved us a project probable-clause. Anthropic API key is separtae per item 1. Voyage and Exa reuse the same key is fine since the spend is so low. For Atlas, use a separate Probable_Clause database for production, same URI."*
- **Date:** Oct 25, 2026
- **Log:** `BUILD_LOG.md`, "Oct 25, 2026, 16:38 CDT — Phase 4: Build, the cloud setup's credentials (P4.25)"

### P4.26 Green light to modify goodnight (T3.5)

- **Decision:** The main session may modify goodnight's repository to add this site's block (T3.5's routing). What the green light covers and when the block goes live: see the log's follow-up.
- **User's words:** *"Green light to modify goodnight to incorporate this site."*
- **Date:** Oct 25, 2026
- **Log:** `BUILD_LOG.md`, "Oct 25, 2026, 16:38 CDT — Phase 4: Build, green light to modify goodnight (P4.26)"

### P4.27 Exa's terms: the risk accepted without a reply (P1.3)

- **Decision:** Exa has not replied to the request for written permission; the project proceeds, with P1.3's synthesis-and-links band and the copy guard as the mitigation.
- **User's words:** *"Exa didn't respond to us yet. The risk is small because it's their literal service plus we already had guards to catch most cases."*
- **Date:** Oct 25, 2026
- **Log:** `BUILD_LOG.md`, "Oct 25, 2026, 16:38 CDT — Phase 4: Build, Exa's terms: the risk accepted without a reply (P4.27)"

### P4.28 The main session builds and stands up the frontend (amends P0.3, P1.6, P4.1)

- **Decision:** The main session takes over `web/` and `webdev/` and builds the real page itself, no parallel builders (fresh subagents only review). `docs/sessions/frontend-log.md` stays as the record; the old frontend session is retired, so `web/` has one writer.
- **User's words:** *"The previous arrangements are only meant to develop the frontend prototype in parallel, the merge and final stand up are always meant to be in the main thread. I agree with you building the frontend yourself without parallel builders."*
- **Date:** Oct 25, 2026
- **Log:** `BUILD_LOG.md`, "Oct 25, 2026, 16:38 CDT — Phase 4: Build, the main session builds and stands up the frontend (P4.28)"
