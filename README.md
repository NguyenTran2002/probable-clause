# Probable Clause

**Claude's Citations, on Supreme Court opinions about the Fourth Amendment and surveillance.** Ask a question; Claude searches 32 cases, keeps the passages that bear on it with a reason for each, and writes an answer whose citations carry the cited sentences, copied from the opinions by the Claude API, not retyped by the model.

**Live at [nguyennhattran.com/probable-clause](https://nguyennhattran.com/probable-clause/).** Four recorded runs play on the page without calling anything; live research runs a real, paid run.

> Independent project. Not affiliated with Anthropic.
>
> Research, not legal advice: it shows what the Court said and never applies it to your situation. It does not tell you whether a case is still good law, and it can miss relevant passages.

Built by Nguyen Tran with Claude Code. Every prompt is published in [docs/PROMPTS.md](docs/PROMPTS.md); [how this was built](#how-this-was-built-with-claude-code) is at the end.

## Contents

- [What it does](#what-it-does)
- [The guarantee, and what it does not cover](#the-guarantee-and-what-it-does-not-cover)
- [How a run works](#how-a-run-works)
- [The corpus](#the-corpus)
- [Later developments: the web search](#later-developments-the-web-search)
- [Limits, and what happens when one is hit](#limits-and-what-happens-when-one-is-hit)
- [Cost](#cost)
- [Privacy](#privacy)
- [The neighbourhood](#the-neighbourhood)
- [How it runs](#how-it-runs)
- [How this was built with Claude Code](#how-this-was-built-with-claude-code)
- [Licence and credits](#licence-and-credits)

## What it does

It does the research a paralegal does on a narrow body of law. Claude runs an agentic loop over a fixed corpus of Supreme Court opinions: it searches, reads around what it finds, and keeps or passes over each passage, giving a one-sentence reason for each one it keeps. A second call then writes the answer from the kept passages only, with the Claude API's [Citations](https://platform.claude.com/docs/en/build-with-claude/citations) feature. A third step may search the web for anything newer than the opinions, shown apart from the evidence.

The research is visible: each search and its results, each passage kept and why, every Messages API exchange that touched a passage (the "View API calls" button), and the run's tokens and cost.

It is designed for legal researchers (paralegals, law students, attorneys). Members of the public will arrive too: a question about a person's own situation is researched and answered with what the Court held and the factors it weighed, stopping short of applying them.

## The guarantee, and what it does not cover

The page states one guarantee, on each cited passage:

> This passage appears word for word in this opinion, as normalised from the official text.

That is all it promises. The quoted words come back from the Citations feature as the exact sentences of a passage Claude kept, so they are the corpus's words, not the model's. **It does not promise that:**

- the passage supports the sentence that cites it (a citation shows where the words are, not that they prove the point; the page says so beside every answer);
- the case is still good law;
- the search found every relevant passage;
- the corpus text matches the official U.S. Reports character for character (it is normalised: see [the corpus](#the-corpus));
- anything Claude writes without a citation is correct. Uncited sentences are Claude's own synthesis and are shown without an underline.

**Two checks by this site's code run on each answer as an add-on, not as part of the guarantee** (decision P4.34). They only flag:

- **Quotations:** any quotation of four or more words in the answer that cannot be found in the passages Claude kept is flagged, allowing ordinary legal quoting conventions (ellipses, bracketed alterations, changed quotation marks, letter case).
- **Full case names and U.S. Reports citations** ("*Katz v. United States*", "389 U. S. 347") that do not resolve to the corpus are flagged **"Not in this corpus"**, never "fabricated": the check knows only these 32 cases, so a real case outside them is flagged too. Short-form names are not checked.

A broader check that every case name resolves to the corpus was planned and dropped (T1.12): a case name cannot be found reliably in free text, and a check that claimed to would give false confidence.

## How a run works

1. **Research** (Claude Sonnet 5.5, high effort). Claude has five tools:
   - `search_meaning`: meaning search, embedded with Voyage AI's `voyage-law-2` and reranked with `rerank-3`;
   - `search_exact`: keyword search on exact words, phrases, citations and names, with optional filters (case, opinion type, author, dates);
   - `read_passages`: read around a passage or a page of an opinion;
   - `keep_passages`: keep passages, each with a one-sentence reason (a re-keep replaces the reason);
   - `submit_answer`: end the research.

   Claude can make several searches and reads in one turn. After each turn our code appends a status line ("Round 5 of 12 · 9 kept"). To find later cases citing a case, Claude searches the citation string ("389 U. S. 347") with a date filter; there is no separate citing-cases lookup.

2. **The rejection paths.** `submit_answer` is refused, with the refusal shown in the step log, when:
   - it shares its turn with any other call, or is sent twice in one turn (its results would be unseen);
   - no corpus search has been made and the question is in scope;
   - nothing was kept, the question is in scope, and no note explains why;
   - the question is marked out of scope with no note for the visitor, or the note runs over 1,000 characters.

   A keep is refused in the same way for a passage not shown to Claude before that turn, an empty reason or one over 300 characters, or a keep past 40 passages. A question outside the corpus (or a greeting) gets a short reply written to the visitor, labelled as having no sources, instead of an answer.

3. **The answer** (Claude Sonnet 5.5, high effort). The kept passages, in order of decision date, go to one call as custom content documents. Each is split into sentences by this project's own conservative splitter, with the passage's citation, lineup and keep reason in the document's `context`. Claude cites any run of whole sentences, from one sentence to the whole paragraph. The answer streams to the page as Markdown, each cited sentence underlined; hovering or tapping one shows the exact sentences it cites, lit inside their paragraph.

   Why our own sentences: in a paid check, Anthropic's automatic plain-text chunking broke legal citations ("205 F. Supp. 692", "Code Crim. Proc.") in 133 of 200 pieces on the ten hardest passages; the conservative splitter broke none of 54 (`scripts/probe_chunking.py`, T1.9).

4. **Later developments** runs beside the answer, continuing the research conversation (below).

5. **Streaming and disconnects.** A run streams its events over one connection and survives drops: the page reconnects and resumes from the last event it holds. While its stream is open, the page sends a heartbeat every 10 s, checked before every paid call. A run whose page has been away pauses before its next paid call, resumes when the page returns, and is abandoned after 60 s with no answer written and nothing more spent. A run's events are kept 24 hours.

Each question is researched from scratch; Claude does not see the visitor's earlier questions.

The prompts are in [`api/prompts/`](api/prompts/): the research and update system prompt, the answer's system prompt, the tool descriptions and every refusal's text.

## The corpus

**32 Supreme Court cases, 102 opinions** (majority, plurality, concurrences and dissents), decided from 1878 to June 29, 2026, 2,462 passages (1,964 paragraphs and 498 footnotes) and 11,005 sentences, 599,096 tokens by Claude's token counter. Pulled Oct 23, 2026, then frozen.

**Inclusion rule** (P1.9): Supreme Court opinions deciding (a) whether the government's acquisition of information through a surveillance or sensing technology, or from records held by a third party, is a Fourth Amendment search; (b) whether the Fourth Amendment requires a warrant before the government searches the data on a digital device; or (c) whether a physical intrusion to gather information is a search under the property-based test. Borderline cases lean toward inclusion, and one foundational case outside the rule's text, *Boyd v. United States*, was added in the filter check. A wider corpus of every Fourth Amendment case was considered and set aside: the project shows Claude's Citations, which does not need a huge corpus.

**Sources** (the text is in the public domain):

- **CourtListener**, a project of Free Law Project: the text of 25 cases (its Lawbox copies), checked against an independent Harvard Caselaw Access Project scan;
- **GovInfo** (U.S. Government Publishing Office): the official U.S. Reports, the text of 6 cases, and the printed pages every check was made against;
- **supremecourt.gov**: the slip opinion of *Chatrie v. United States* (2026), not yet final in the U.S. Reports.

**Cleaning:** HTML, page numbers, running heads and footnote markers removed (positions recorded), words broken across lines rejoined, letters a PDF font dropped restored, quotation marks made straight, whitespace normalised. The syllabus, counsel listings and the Reporter's lineup are left out, since they are not the Court's words. Beyond that, the only changes to the source words are corrections confirmed against the page image (each by a verification agent, except one missing heading checked by the main conversation), all listed in `scripts/corrections.json`. Every opinion was verified by scripts and by independent subagents. The text is unofficial; only the U.S. Reports are authoritative.

Details: [data/corpus/README.md](data/corpus/README.md). Licences and terms of every source: [docs/research/licensing.md](docs/research/licensing.md).

**Coverage dates** shown on the page: latest decision in everything pulled and in the corpus, June 29, 2026; pulled Oct 23, 2026.

## Later developments: the web search

The corpus stops at its pull date, so a separate step lets Claude search the web for anything newer, through Exa's hosted MCP server. It continues the research conversation (for its cache), decides whether to search at all (up to 5 searches), and writes short findings, each naming the pages it draws on. It does not run when research ended without submitting (at a limit or after an error), when the question was out of scope, or when research never searched the corpus; it shows as unavailable when Exa is.

The box sits under the answer, apart from the evidence, and carries its own honesty label:

> Claude searched the web for anything newer than these opinions. Kept apart from the evidence above. If it finds nothing, that doesn't mean nothing has changed: web searches miss pages.
>
> Each point is Claude's summary of the pages it links. This site checks only that the pages came from this search, not what they say. Open them to check.

Only Claude's summary is shown, with links; no page text from Exa is shown or stored. A copy guard refuses a finding that repeats ten or more words of a page in a row. Every page the search returned is listed, including those Claude did not mention. When Claude decides not to search, the box says so and gives its reason.

## Limits, and what happens when one is hit

Each limit is a backstop meant almost never to fire.

| Limit | Value | When it is hit |
|---|---|---|
| Research rounds | 12 | The answer is written from what was kept so far, labelled "Stopped at step limit." |
| Research tokens | 2,000,000 input, 16,000 output | The same, labelled with the token limit |
| A run's time | 10 minutes | No research or web-search call starts after it; the answer is still written, labelled with the time limit |
| Kept passages | 40 at a time | A further keep is refused, with a message to Claude |
| Answer length | 16,000 output tokens | The answer is shown, labelled "Cut off at the answer's length limit." |
| Web searches | 5 a run; 8 rounds, 2,000,000 input and 6,000 output tokens | A sixth search is refused, with a message to Claude. At the round, token or time limit, the box says the search stopped, or lists the pages it could not summarise |
| Runs at once | 5 | A new question is refused: "Please try again in a minute." |
| Spend | $15 a day, $60 a month, at list prices | Live research pauses until midnight Chicago time, or the 1st; recorded runs still play |
| Question | 2,000 characters | The question box stops there, and the API refuses a longer one |

If research stops with nothing kept, no answer is written and the page says so. Anthropic and Voyage calls that fail on a transient error are retried up to twice, each retry shown as a step; Exa searches are never retried by this site. A transient error that persists after the retries ends research, and the answer is written from what was kept, labelled as stopped by an error.

**Cold starts.** The API scales to zero when idle, so the first question after a quiet spell waits for it to start; the landing page starts health checks on load, one at a time, until the API answers, so it is often awake by the time a question is asked; the page shows "Starting the research server" with a counter while it waits. Starts measured on Oct 26, 2026, from Cloud Run's logs ("Starting new instance" to the startup probe succeeding): 15.3 s at the first deploy and 44.4 s at the redeploy; 30.7 s for a visitor after about 48 minutes idle; and 31.5 s after 7 h 24 min idle, which a request through the domain saw as 32.5 s. In that last sample about 4.5 s was the container starting and 27 s the app loading its corpus, index and clients. A long idle gave no longer start than a short one in these two samples, which is too few to call a trend. Google does not guarantee these times.

## Cost

The page shows each run's cost, computed from each response's token counts and the providers' list prices, plus this site's estimate for any failed attempt that reported no usage; it is not an invoice. A recorded run shows the prices of its recording date.

| Run | Rounds | Claude and Exa |
|---|---|---|
| Recorded: searching a phone after an arrest | 5 | $0.20 |
| Recorded: tracking a car with GPS | 4 | $0.21 |
| Recorded: Google location history without a warrant | 5 | $0.21 |
| Recorded: watching a backyard from the air | 6 | $0.24 |
| The first live run (Oct 26, 2026): "What does the police need to enter a house?" | 5 | $0.20 |

Voyage AI's meaning search adds under a cent a run and is not in the page's total. The first live run used no Exa search (Claude decided the question needed none). Spend is recorded per call in MongoDB Atlas and checked against the caps before a run starts.

## Privacy

A question goes to Anthropic (the research and the answer), and Claude's searches go to Voyage AI and, for the web search, to Exa; Claude is told to leave personal details out of search queries. The site keeps each run's steps, question and answer for 24 hours so a dropped connection can resume, then deletes them, and keeps a record of each run without the question or answer (times, steps, tokens, cost) to track spending. No accounts, no cookies, no analytics, and the site does not use or store IP addresses; the gateway in front of it and Google Cloud keep standard request logs, which include them, for 30 days. The page's privacy note links each provider's retention terms; the research behind it is in [docs/research/retention.md](docs/research/retention.md).

## The neighbourhood

This is not a new idea, and it isn't pitched as one. Free Law Project's CourtListener offers a [Citation Lookup and Verification API](https://free.law/2024/04/16/citation-lookup-api/) (April 2024), framed as a guardrail against hallucinated case citations and built on their database of nearly ten million citations, and an [MCP connector that brings CourtListener into Claude](https://free.law/2026/05/12/courtlistener-is-now-available-inside-claude/) (May 2026), with citation verification among its features (both checked Oct 26, 2026).

What this project shows is how a customer would build grounded research on Claude: an agentic loop over their own documents, answers cited with the Citations feature, the research made visible, and a narrow guarantee stated as narrowly as it is.

## How it runs

- **API:** Python 3.13, FastAPI on uvicorn, the Anthropic SDK, on Google Cloud Run (us-central1; scales to zero, one instance). The corpus and its vectors (`data/vectors/`) ship inside the container; the keyword index is built at start, and vectors are searched in memory.
- **Page:** plain JavaScript modules, no build step, markdown-it vendored, served by a pinned nginx image on Cloud Run. The four recorded runs are static files in [`replays/`](replays/), played by the page's own code.
- **State:** MongoDB Atlas holds spend counters and run events (24-hour expiry). Keys live in Secret Manager, readable only by the API's service account.
- **Web search:** Exa's hosted MCP server, which our backend connects to as an MCP client.
- **Gateway:** the site sits under the author's domain, behind an nginx gateway on Cloud Run that routes `/probable-clause/` to the page and its API.

**Running it locally:**

```bash
uv sync
.venv/bin/pytest -q
```

2,967 tests pass and 54 are skipped (45 need the live test database, 2 an nginx binary, and 7 don't apply to the reconnect fixtures); the page's 86 Node tests run with `node --test webdev/test/`. To see the page without any keys, build its data files and start the mock server, which plays recorded event streams from `tests/fixtures/`:

```bash
uv run python scripts/build_web_data.py --out web/_generated
.venv/bin/python webdev/serve.py
```

Then open http://localhost:8765. A real run needs the keys named in [`.env.example`](.env.example); `deploy/local.sh` builds and runs both containers against them, and `deploy/setup.sh` and `deploy/deploy.sh` set up and deploy the cloud services.

**Layout:** `api/` the backend; `web/` the page; `webdev/` the mock server and Node tests; `scripts/` the corpus pipeline and the tools behind the paid tests, replays and this README's figures; `data/corpus/` the frozen corpus; `contracts/` the event schema; `deploy/` images, nginx configs and scripts; `docs/` the design record.

## How this was built with Claude Code

One person and Claude Code (Claude Opus 5.5), from the first prompt to this README. The author planned, decided and approved; Claude researched, wrote the code, ran the paid tests and deployed only on an explicit green light. Two Claude Code conversations worked in the same folder: the **main** one ran every phase, and a **frontend** one built the art-direction look tests on Oct 23, 2026. Claude started 75 subagents along the way (Opus 5.5 and Sonnet 5.5) for research, corpus verification, building parts of the backend against a written contract, and reviews.

| | |
|---|---|
| Time | built part time over about two and a half days (Oct 23 to 26, 2026): four sittings, 35.1 hours in all from each sitting's first prompt to its last activity, up to the first push to GitHub. A prompt more than two hours after the one before starts a new sitting; shorter breaks are counted, so this is not time at the desk. Work after the push, such as the cold-start measurement below, is not counted. |
| Prompts typed | 304 in the build (289 main, 15 frontend), 12,062 words, median 22 words a prompt. Prompts after the build are listed in [docs/PROMPTS.md](docs/PROMPTS.md) and not counted here |
| Context compactions | 32 |
| Code | about 9,300 lines of Python in `api/`, 5,500 in `scripts/`, 21,100 in `tests/`; about 4,200 lines of JavaScript, CSS and HTML in `web/` (the look tests aside) |
| Tests | 2,967 Python tests passing (54 skipped), 86 Node tests |

Every figure comes from a script: the prompts, hours and subagents from the transcripts by [`scripts/extract_prompts.py`](scripts/extract_prompts.py) (its full figures are at the top of [docs/PROMPTS.md](docs/PROMPTS.md)), the rest from git and the test runs.

### Timeline

Each phase ends with a git tag. Times are Chicago time (CDT).

| Phase | Ended | Commits | What happened |
|---|---|---|---|
| 0. Bootstrap | Oct 23, 16:23 | 3 | The brief committed unchanged as the first commit; the build log, CLAUDE.md and the rules |
| 1. Corpus | Oct 23, 21:17 | 48 | The inclusion rule, the pull, cleaning, verification by scripts and subagents, frozen; look tests in the frontend conversation |
| 2. Research | Oct 24, 13:59 | 11 | Current documentation and small paid checks: models, prices, Citations, Exa, limits |
| 3. Architecture | Oct 24, 20:03 | 121 | Five areas discussed topic by topic, each topic locked in the author's words; the design note |
| 4. Build | Oct 26, 02:52 | 168 | The interfaces contract, subagent waves against it, paid build tests, the page built and reviewed in 29 rounds, the four replays |
| Deploy | Oct 26, 03:06 | | Live on Cloud Run behind the author's gateway; the first live run at 03:25 |
| After the build: a cold start | Oct 26, 11:42 | | One cold start measured after 7 h 24 min idle: 32.5 s as the caller saw it, 31.5 s on Cloud Run's side. The app was not modified, and this is not counted as build time |

### How the work was run

- **A brief, then decisions in the author's words.** The brief ([PROBABLE_CLAUSE_KICKOFF.md](PROBABLE_CLAUSE_KICKOFF.md)) was frozen at the first commit. Every later decision is an entry in [docs/design/locked-decisions.md](docs/design/locked-decisions.md), quoting the author, with a dated entry in [BUILD_LOG.md](BUILD_LOG.md), the authoritative record. A superseded decision stays, marked.
- **Green lights.** Each phase gate, every paid run beyond a small check, every deploy and every cloud change waited for an explicit go. Claude never saw a key: a permission rule blocks `.env`, keys reach programs only as environment variables, and a script reports only whether each key is set.
- **Contract first.** Before any subagent wrote backend code, the main conversation wrote [docs/design/contract.md](docs/design/contract.md) and a machine-checked event schema ([contracts/events.schema.json](contracts/events.schema.json)); each part had one owner.
- **Times from the clock, counts from scripts.** Every time in the log comes from `date`, run just before it is written; every count in this README comes from a script.

### A few of the author's decisions

- **Narrow the corpus:** *"The goal of the project is show casing Claude Citation, and it doesn't need a huge corpus to effectively showcase that."* (P1.9)
- **Let Claude choose how much to cite:** *"I want us to explore giving Claude flexibility in deciding not only what to cite but also how much to cite."* (T1.9)
- **Drop a check that can't be made reliable:** *"adding a check that isn't reliable might give false confidence to user."* (T1.12)
- **The checks are an add-on:** *"these additional checks are good quality of life add on, not guarantees."* (P4.34)
- **Answers on Sonnet:** *"this project is a tech demo of the citation feature, not a demo of how much smarter and more capable is Opus than Sonnet in constitutional laws."* (P4.20)
- **Limits as backstops:** *"let all runs pass smoothly while having a sure back stop that will almost never be triggered unless something catastrophic has gone wrong."* (P4.18)

### What went wrong

Each is recorded in the build log.

- **A verification rule that didn't hold.** Phase 1 first accepted a correction where two independent scans of the print agreed; in practice two OCRs of the same page often make the same mistake. Replaced by corrections each confirmed against the page image (P1.21).
- **A missing heading passed verification.** *Oliver v. United States*'s section "II" was missing from the source text and passed Phase 1's checks, which skipped headings by design. Found in Phase 3; a read-only structure check of every heading and footnote marker followed, and found no other.
- **Claude split its submit.** In the paid build tests Claude sent `submit_answer` twice in one turn in two of three answered runs; the later one won, losing a finding and a scope note. Fixed by refusing a submit that is not alone in its turn (P4.16).
- **A real quotation flagged.** The quotation check flagged a genuine *Kyllo* quotation whose first letter was capitalised; now it ignores letter case (P4.17).
- **False flags in the first replays.** Three of the four first recordings carried flags from two defects in the checks (Markdown italics inside a quotation; a case name followed by a parenthesis). Fixed with tests and re-recorded (P4.48).
- **An overflow at Exa.** The first Exa test lost two requests: full page text for ten results overflowed the MCP client's 1 MB event limit. Each page is now cut before Claude reads it.
- **Times written before reading the clock.** Twice in Phase 3, a time in the working notes was written before `date` was run (17:59 for 17:57, 18:08 for 18:09). Both were corrected, and from then on `date` ran in its own step.

### The record

- [BUILD_LOG.md](BUILD_LOG.md): every session, decision and failure, append-only.
- [docs/design/locked-decisions.md](docs/design/locked-decisions.md): every decision in force, with the author's words.
- [CLAUDE.md](CLAUDE.md): the working file Claude Code read at the start of every session.
- [PROBABLE_CLAUSE_KICKOFF.md](PROBABLE_CLAUSE_KICKOFF.md): the brief, unchanged since the first commit.
- [docs/design/design-note.md](docs/design/design-note.md) and [docs/design/contract.md](docs/design/contract.md): the architecture and the interfaces contract.
- [docs/PROMPTS.md](docs/PROMPTS.md): every prompt.

## Licence and credits

Code under the [Apache License 2.0](LICENSE). The opinion text in `data/corpus/` is public domain and not covered by that licence.

Opinion text from CourtListener (Free Law Project), the official U.S. Reports on GovInfo (U.S. Government Publishing Office), and the Court's slip opinion (supremecourt.gov). Free Law Project did not produce, review or endorse this analysis. Built with the Claude API (research and answers on Claude Sonnet 5.5), Voyage AI for meaning search (`voyage-law-2`, `rerank-3`), and Exa's MCP server for the web search.
