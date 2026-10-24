# Locked decisions

Every decision made after the kickoff brief (`PROBABLE_CLAUSE_KICKOFF.md`, frozen at the first commit) lives here. **This file wins over the brief on any conflict.**

Numbering: `P<phase>.<n>` for decisions made in Phases 0 to 2 and 4 to 5; `T<topic>.<n>` for the Phase 3 architecture conversation. A superseded decision stays in place, marked superseded, with its replacement entered below it. Dates are America/Chicago.

---

## Phase 0: Bootstrap

### P0.1 Stack: Python 3.13 via uv, FastAPI on uvicorn

- **Decision:** Brief §2, Claude's default 1, is locked: Python 3.13 managed with uv, FastAPI served by uvicorn. The frontend stack is still chosen in Phase 3.
- **User's words:** *"On the default stack, I want Python 3.13 with uv and fast api. Lock this. (Open to future adjustment in case something goes wrong, but that would be highly unlikely.)"*
- **Note:** Locked, with the user open to adjusting it only if something goes wrong. Any change goes through the user and is entered here as a superseding decision.
- **Date:** Oct 23, 2026

### P0.2 No screenshots or images committed to the repo — SUPERSEDED by P0.4

- **Decision:** Brief §2, Claude's default 7, carries over in the user's wording: no screenshots or images are ever committed to this repository. `.gitignore` excludes common image formats to enforce it.
- **User's words:** *"On screenshots or images, we will never commit any to the repo, lock that too."*
- **Open for Phase 3:** whether a favicon or a wordmark file counts as an image under this rule. Until the user says otherwise, none is committed, and the wordmark is set in text and CSS.
- **Date:** Oct 23, 2026

### P0.3 A second Claude Code session for the mock frontend, in the same checkout

- **Decision:** In Phase 4, the frontend is built by a **second Claude Code session** working on a mock frontend, instead of the frontend subagent named in brief §3. Both sessions work in the same folder and on the same branch (no worktree). The organization, as proposed by Claude and approved by the user:
  1. **File ownership, one writer per file.** The main session owns the backend, corpus, `scripts/`, `tests/`, deploy, `pyproject.toml`/`uv.lock`, and every shared document. The frontend session writes only under `web/` and its own notes file. The interfaces contract, CLAUDE.md, the brief and this file are read-only to it.
  2. **The mock is built against the interfaces contract only**, with a machine-checkable event schema (`contracts/events.schema.json` or similar) that both the backend's event tests and the frontend's mock fixtures validate against. Contract changes have one writer, the main session, which versions them and tells the frontend session. Mock fixtures share the replay format, and cover waking, disconnect and reconnect, abandoned and interrupted runs, rejections, the step limit, verifier flags and the daily cap.
  3. **Shared documents have one writer, the main session.** The frontend session keeps its own append-only `docs/sessions/frontend-log.md` (same entry format, headings from `date`, user decisions marked `DECISION (user)` with the user's words). The main session folds those into `BUILD_LOG.md` and this file under its own timestamped entries.
  4. **Git in a shared working tree:** each session commits only its own paths by name (`git commit -- <paths>`), never `git add -A` or `git add .`; never `git stash`, `reset`, `checkout -- .`, or a branch switch; on `index.lock`, wait and retry, never delete it; only the main session tags phase ends, after the frontend session is idle and committed; separate dev-server ports; only the main session touches `.venv`.
  5. **Start condition:** after art direction is locked (Phase 3) and contract v1 is committed (start of Phase 4). The details go in the Phase 4 build plan, which the user approves before the build starts.
- **User's words:** *"In a future phase where decisions on the backend are settled and this claude code session is on implementation, I'd want to be iterating on a mock frontend with a second claude code session to cut time and be more efficient."* On the proposal: *"The plan looks sound to me."*
- **Date:** Oct 23, 2026

### P0.4 Image block narrowed to PNG and JPEG (supersedes P0.2)

- **Decision:** The no-images rule covers `.png`, `.jpg` and `.jpeg` files only; those are never committed. The project's own `.svg` and `.ico` files (for example a favicon or wordmark) may be committed. This also settles the favicon and wordmark question P0.2 left open for Phase 3. `.gitignore` blocks exactly those three formats.
- **User's words:** *"Correction: for image blocking, only count jpeg, jpg, and png. I wouldn't have any image in any other format. The project itself might use svg and ico."*
- **Date:** Oct 23, 2026

### P0.5 Transcript retention left at the default

- **Decision:** `cleanupPeriodDays` stays unset (Claude Code's default cleanup, about 30 days). The agent does not change it.
- **User's words:** *"Transcript retention, leave cleanupPeriodDays alone for now. This project will be done in 2 days."*
- **Date:** Oct 23, 2026

---

## Phase 1: Corpus

### P1.1 Exhaustive corpus verification, scripts plus independent subagents

- **Decision:** Phase 1 ends with exhaustive verification, not the spot check brief §4.5 asks for. Scripts check everything mechanically: every cleaned opinion aligned word by word against the official PDF text with every difference listed; every opinion in the Court's lineup present after splitting, with correct boundaries; every metadata field compared against the official text. Opus subagents, each given a batch of cases and none told the main session's conclusions, judge every listed difference (cleaning artifact, real difference, or OCR noise in the official PDF) and check opinion type, author and joiners. One further subagent builds its own case list from scratch and compares it with the corpus, alongside the citation-graph filter check (§4.7).
- **User's words:** *"At the end of Phase 1, subagents to verify the corpus exhaustively will be crucial here. We also want to pull all relevant metadata for each corpus item."* On the design: *"Verification design with subagents looks good to me."*
- **Date:** Oct 23, 2026

### P1.2 Pull all metadata; keep `scdb_decision_direction` out of the manifest and the prompt

- **Decision:** Every field CourtListener holds for each docket, cluster and opinion is cached raw (gitignored). A curated manifest carries what the app uses. The Supreme Court Database's `scdb_decision_direction` (a liberal or conservative coding of each outcome) stays in the raw cache only: never in the manifest, the system prompt, a tool result, or the page, because it would break the political-heat guardrail (brief §2, "never says whether the Court was right").
- **User's words:** *"We also want to pull all relevant metadata for each corpus item."* On the exclusion: *"Keeping scdb_decision_direction out is a good catch."*
- **Date:** Oct 23, 2026

### P1.3 The update check shows Claude's synthesis plus source links, never Exa's content

- **Decision:** Exa stays as the update-check search (brief §2 unchanged). On the page and in replays, the update-check band shows **Claude's own synthesis** of what the search found, plus a **link to each source** (title, URL, published date). It never shows page text, highlights, or Citations `cited_text` drawn from web results. Internally, Citations still mark which sentences are grounded in a web result; on screen, such a sentence links to its source instead of quoting it. This changes how brief §6.3 and §6.4 display results. Every parameter Claude chose is still shown, and the honesty label still applies.
- **Why:** Exa's Terms §4.2(a), read literally, require written permission to display, copy or publish information obtained through the service (`docs/research/licensing.md` §4). Synthesis plus links removes any republication of third-party web text. It does not by itself satisfy the literal clause ("modify", "create derivative works from" are also listed), so the user is emailing Exa (hello@exa.ai, the address named in the terms) for written permission covering public display and stored replays. If no answer arrives before launch, the project proceeds with this design and the remaining risk is logged as accepted by the user.
- **User's words:** *"Exa, can we only display what Claude synthesize after doing the search? This will avoid directly copying and pasting Exa's returning content."* Then: *"Draft the Exa email and give me an email address to send it to. Hopefully we'll get a response back soon. Otherwise, we proceed as normal."* and *"I lock all three decisions here with you"*.
- **Date:** Oct 23, 2026

### P1.4 Anthropic Usage Policy: the case rests on what the tool does

- **Decision:** Probable Clause proceeds as planned under Anthropic's Usage Policy. The basis, as recorded:
  - The tool does not do the high-risk activity. It explains what the Court held and shows verbatim evidence, and never applies the law to a person's own facts (brief §2). The policy published for Nov 12, 2026 excludes exactly this: "explaining what a law says … without applying it to the individual's circumstances".
  - The page discloses AI use, and tells visitors to check factual assertions independently (Commercial Terms §D.3).
  - The README and page do **not** claim that the visitor is the "human in the loop".
- **Gap, recorded:** the policy in force until Nov 12 (since Sep 15, 2025) treats consumer-facing "legal" use as high-risk, and its full text was not found. Describing a holding could be read as legal interpretation under that wording. The user accepts this reading.
- **User's words:** *"On Anthropic's Usage Policy, we have AI disclosure and we don't provide legal advice. It's a research and citation tool, with the user is the human review piece because the project only ever present up evidence."* Then: *"I lock all three decisions here with you"*.
- **Date:** Oct 23, 2026

### P1.5 Crediting Claude: plain descriptive sentences, as in the previous build

- **Decision:** Claude, Claude Code and Anthropic are named only in plain, factual sentences, following the previous build's README. Examples:
  - a README section headed "How this was built with Claude Code"
  - on the page, a sentence such as "Answers are written by Claude, Anthropic's model, through the Claude API"
  - the non-affiliation line near the name (brief default 4)

  No logos, no badge or tagline-style credit, no Claude brand colours, nothing implying endorsement. This replaces default 4's "Built with Claude" footer idea. The README's licence section says the opinion text is public domain and not covered by the code licence. Exact page wording is settled in Phase 3.
- **User's words:** *"On "Built with Claude" wording, I used this phrase in the past that is not trade marked and was just a literal sentence "How this was built with Claude Code" in the README."* Then: *"I lock all three decisions here with you"*.
- **Date:** Oct 23, 2026

### P1.6 Art-direction look tests start now, in a second session the user starts

- **Decision:** The Phase 3 art-direction look tests (brief §7.3) move forward to run alongside Phase 1, in a second Claude Code session that **the user starts**, in this same folder and branch (not a worktree), under P0.3's rules. Its brief is `docs/sessions/frontend-brief.md`. This changes P0.3's start condition for look tests only. The contract-bound mock frontend still waits for contract v1 (start of Phase 4). The art direction the user picks is locked by the main session in Phase 3 as a T-entry, from the frontend session's log.
- **User's words:** *"Starting the look test in parallel with phase 1 would be nice?"* Then: *"I want to start the look test session myself, so prep the ground for that session, and let me know where to point that session to kick start it."*
- **Date:** Oct 23, 2026

### P1.7 Exa emailed; build on P1.3 without waiting

- **Decision:** The user has emailed Exa for written permission (P1.3). Until the user reports an actual reply, assume none: build the update check as Claude's synthesis plus links to the sources, with no Exa content shown or stored.
- **User's words:** *"Emailed Exa. Assume no response from them until I come back with an actual response. We proceed with Claude's summary plus links to the sources."*
- **Date:** Oct 23, 2026

### P1.8 SCDB fields are used for verification only

- **Decision:** CourtListener clusters carry four SCDB fields: `scdb_id`, `scdb_decision_direction`, `scdb_votes_majority` and `scdb_votes_minority` (checked in CourtListener's `cl/search/models.py`, Oct 23, 2026). All four stay in the raw cache. **None goes into the manifest, the system prompt, a tool result, a replay, or the page.** Vote splits shown in the product come from each opinion's own lineup in the official text. In Phase 1 verification (P1.1), the scripts also compare those lineup-derived votes with SCDB's counts where they exist, and every disagreement goes to the verification agents to explain from the official text. This is internal checking, not republication, so no SCDB citation is owed; if the README mentions the check, it names SCDB in a sentence. P1.2's exclusion of `scdb_decision_direction` stands, and that field is not used even in verification.
- **Why:** SCDB asks to be cited with its release number, and the release CourtListener ingested is unknown. Coverage is uneven (the modern database starts in 1946; *Chatrie* may be absent). SCDB counts votes for the outcome, so a justice concurring in the judgment counts with the majority, which a naive lineup count might not; showing both would invite a visible contradiction.
- **User's words:** *"Let's use the SCDB fields as verification only."*
- **Date:** Oct 23, 2026

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

### P1.10 Case-name verifier: "not in this corpus", never "does not exist"

- **Decision:** A case name the verifier (brief §5.8) cannot resolve is flagged on screen as **not in this corpus**, never as nonexistent or fabricated, since a real case outside the corpus must read differently from an invented one. The system prompt tells Claude to name only cases it cites from the corpus. Exact wording is settled in Phase 3.
- **User's words:** *"Thanks for incorporating my suggestions. We can lock here."*
- **Date:** Oct 23, 2026

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

### P1.12 *Jones* and *Quon* take their text from the official PDF (amends P1.11)

- **Decision:** *Jones* and *Quon* use the official GovInfo PDF of the U.S. Reports, like *Jardines*, *Riley*, *Grady* and *Carpenter*, not CourtListener's Harvard scan. The Harvard copies proved to be OCR with misreadings (about 170 to 250 small differences per case against the official text, such as "HH" for the section numeral "I", "swpra", "ease" for "case"); the official PDFs for both are born-digital, with ligature characters and soft hyphens intact. The rest of P1.11 stands.
- **User's words:** *"Jones and Quon take their text from the official PDF -> This is a more reliable and authoritative way."*
- **Date:** Oct 23, 2026

### P1.13 The syllabus is never part of the citable corpus

- **Decision:** The Reporter of Decisions' syllabus is left out of the citable corpus entirely, for every case, since it is not the Court's text ("no part of the opinion of the Court"). Only opinions (majority, plurality, concurrences, dissents, and Justices' statements) are citable. This supersedes the plan, in `docs/research/licensing.md` and the frontend brief, to keep the syllabus as a labelled passage.
- **User's words:** *"Syllabus -> Strictly leave out of the citable corpus because they aren't from the Court."*
- **Date:** Oct 23, 2026

### P1.14 Filter-check additions

- **Decision:** From the two-way filter check (brief §4.7, P1.9; `scripts/filter_check.py`), ten cases join the corpus as core cases:
  - within the rule: *United States v. Lee*, 274 U.S. 559 (1927); *Hester v. United States*, 265 U.S. 57 (1924); *Oliver v. United States*, 466 U.S. 170 (1984); *United States v. Dunn*, 480 U.S. 294 (1987); *United States v. Jacobsen*, 466 U.S. 109 (1984);
  - borderline, included on "extra over missing": *California v. Greenwood*, 486 U.S. 35 (1988); *Ex parte Jackson*, 96 U.S. 727 (1878); *California Bankers Assn. v. Shultz*, 416 U.S. 21 (1974); *Berger v. New York*, 388 U.S. 41 (1967);
  - foundational, outside the rule's text: *Boyd v. United States*, 116 U.S. 616 (1886), cited by 17 of the 21 core cases.

  Left out: *City of Ontario v. Quon* and every other candidate (among them *Hoffa*, *Lewis*, *Keith*, *Osborn*, the dog-sniff cases *Place* and *Caballes*, *Patel*, and the exclusionary-rule, standing and general warrant cases). *Quon* stays in the raw cache only. The independent case-list agent (P1.1) also proposed *Clinton v. Virginia*, 377 U.S. 158 (1964), after this decision was offered; it is not included.
- **User's words:** *"Approve your recommended additions (the five squarely in the rule, plus Greenwood, Ex parte Jackson, Shultz, Berger and Boyd; leave out Quon and the rest)."*
- **Date:** Oct 23, 2026

### P1.15 *Kyllo* takes its text from the official PDF (amends P1.11)

- **Decision:** *Kyllo*'s official GovInfo PDF is born-digital, so, by P1.12's reasoning, it replaces the Lawbox copy as the text of record. The Lawbox copy serves as the reference copy for repairs.
- **User's words:** *"Also switch Kyllo to its official PDF."*
- **Date:** Oct 23, 2026

### P1.16 Lawbox wording errors are corrected where two independent scans of the print agree

- **Decision:** The P1.1 verification agents confirmed wording errors in the Lawbox copies against the page images (for example *Olmstead* "We have to chose" for "choose", *Lopez* "notwithstanding are the verdict", *Miller* "400 U. S. 322" for 409). The build corrects a Lawbox word wherever the official PDF's text layer and CourtListener's Harvard scan, two independent readings of the printed page, agree with each other against Lawbox. Every correction is logged with its page, and a second round of verification agents checks every applied correction against the page image, since two OCRs can share a misreading. Corrections an agent confirms that the two scans cannot make (punctuation, omitted rows of omission points) go in a reviewed corrections table applied by the build.
- **User's words:** *"correct Lawbox where both scans agree and have agents review every correction"*
- **Date:** Oct 23, 2026

### P1.17 Quotation marks and apostrophes are straight throughout

- **Decision:** Every quotation mark and apostrophe in the corpus is normalised to straight ASCII (`'` and `"`), whatever the source (Lawbox's straight quotes and backticks, the fonts that encode single quotes as a backtick and `'`, and curly quotes). The page's text-status note says quotation marks are normalised.
- **User's words:** *"straight quotation marks throughout"*
- **Date:** Oct 23, 2026

### P1.18 Majority joiners come from the Reporter's lineup where it is printed

- **Decision:** A majority opinion's heading names no joiners. Where the volume prints the Reporter's lineup paragraph (roughly the 1970s on), the majority's joiners are taken from it, partial joins noted. Where no lineup is printed, the majority's joiners are recorded as not printed, not inferred. Separate opinions keep their joiners from their own headings.
- **User's words:** *"majority joiners from the Reporter's lineup where printed"*
- **Date:** Oct 23, 2026

### P1.19 *Goldman*: Stone and Frankfurter's statement is a concurrence in the judgment

- **Decision:** The printed heading ("MR. CHIEF JUSTICE STONE and MR. JUSTICE FRANKFURTER:") names no role. They would overrule *Olmstead* and agree with its dissents, but do not dissent; the statement is typed as a concurrence in the judgment.
- **User's words:** *"Goldman's Stone and Frankfurter statement as concurrence in the judgment."*
- **Date:** Oct 23, 2026
