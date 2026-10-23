# Probable Clause: Kickoff Brief for Claude Code (v4)

*Prepared Oct 23, 2026, from a planning session between Nguyen (the user) and Claude that ran from the evening of Oct 22 into Oct 23. This file is the spec for a new repository. Read it in full before doing anything. It is not CLAUDE.md: create a separate, agent-facing CLAUDE.md in Phase 0 (§10).*

*v2, revised later on Oct 23, 2026, before the first commit, at the user's direction. It carries the lessons of the user's previous build, the Haiku Decision API (public at github.com/NguyenTran2002/haiku-decision-api), drawn from every failure recorded in its build log, so this build does not repeat them. §13 records what changed from v1.*

*v3, revised in the afternoon of Oct 23, 2026, still before the first commit, at the user's direction. After v2 was written, the previous build had a patch sitting (Oct 23, 15:10 to 15:52 CDT): a public live run waited 85.6 s to wake, the logs showed two cold starts back to back, and the cause was the build's own wake loop. v3 carries what that sitting learned: a wake protocol (§8.5), measured cold-start figures (§7.2, §8.5), an off switch and a measurement procedure, and rules on timeouts and retries (§10.7). §13 records what changed from v1 and v2.*

*v4, later the same afternoon, still before the first commit. The user made two decisions that v3 had left open: wake on landing carries over, and how a run behaves when the browser disconnects (§2, §8.5). **v4 is the version committed as the first commit.** §13 records what changed from v3.*

---

## 0. How to use this file

- **§2 is binding.** Those decisions were made deliberately. Do not reopen them, and do not "improve" them silently. If something in §2 turns out to be impossible or wrong, stop and ask the user.
- **This file is frozen.** It is committed unchanged as the repository's first commit and **never edited afterwards, not even with dated notes.** Every later decision goes in `docs/design/locked-decisions.md` (§10.4), which **wins over this file on any conflict**. CLAUDE.md says so.
- **Items marked "Claude's default, awaiting the user's veto"** are not binding. Raise each one with the user at the phase where it first matters, and record the answer in `locked-decisions.md`.
- **The phase order (§3) is designed so nothing needs to be pulled forward.** If a step must move anyway, stop and ask, then log the change.
- **Facts tagged "verified Oct 22–23, 2026"** were checked against the named source during planning. **Re-verify each one** in Phase 2, or in Phase 1 for anything about CourtListener. Facts from third-party sources say so. Products in this space change weekly.
- **Stop and ask the user** whenever this file says "user decides", and in every case listed in §12.
- **Restate before acting.** When an instruction from the user can be read two ways, say in one line how you read it and wait for the answer, before designing around it or pushing back on it. The previous build misread two architecture requirements this way: one as needing an always-on frontend, and one ("following Anthropic's official styling") as copying Anthropic's identity, which the agent then argued against.
- **§13 is a change record, not instructions.** Where it quotes v1 or v2, that text is superseded.

---

## 1. What this is

**Probable Clause** is a citation and precedent finder for U.S. Supreme Court case law on **the Fourth Amendment and digital technology**, built on the Claude API.

It does the research a paralegal does. Claude searches a fixed corpus of Supreme Court opinions in an agentic loop, reads what it finds, keeps or discards each passage with a reason, optionally checks the web for later developments, and returns **verbatim passages from the opinions** plus a description of what the Court held and where the opinions disagree. **It does not give legal advice.**

**The story is grounding with a narrow, checkable guarantee.** The best-known AI failure in law is fabricated case citations. Probable Clause answers it with mechanisms the viewer can watch:
- **Every quotation is a verbatim passage from a retrieved opinion**, guaranteed by the Claude API's Citations feature.
- **Every case name in the answer resolves to the corpus**, checked deterministically by our own code.
- **The research is visible**: what Claude searched, which passages it considered, which it kept, which it discarded and why.

**The guarantee is narrow, and the product says so.** A cited passage exists verbatim in that opinion. That is all. It does not promise that the passage answers the question, that the case is still good law, or that the search found everything. Showing this limit honestly is part of the demo.

**Audience:** a public link, **designed for legal researchers** (paralegals, law students, attorneys). Members of the public will arrive too, and the research-not-advice behaviour (§5.6) handles them.

**Why this matters for the user's application:** it is build #1 of a portfolio for Anthropic's Applied AI Demo Engineer role, whose posting centres on representing model capabilities accurately and honestly. Every claim the README and page make about this system is held to that standard.

---

## 2. Binding decisions

| Area | Decision |
|---|---|
| Name | **Probable Clause.** Wordmark *Probable C**l**ause*: the "l" (the only letter separating *cause* from *clause*) set in an accent colour from **this project's own palette**. Never Claude's brand colour. Never "Claude" in the name |
| What it does | **Research, not advice.** It finds and shows passages, and describes what the Court held and where the opinions disagree. It **never applies the law to a user's own facts** and **never says whether the Court was right** (the political-heat guardrail) |
| Audience | A public link, designed for legal researchers |
| Corpus scope | **U.S. Supreme Court opinions only**, on the Fourth Amendment and digital technology. No lower courts, statutes, or regulations |
| Corpus source | **CourtListener REST API v4** (Free Law Project). The user holds an EDU membership and a token. Official PDFs are the cross-check: supremecourt.gov for volume 502 (1991) onward and slip opinions, GovInfo for volumes 2 to 501 |
| Corpus lifecycle | Built once in Phase 1, then **frozen**. The deployed app never calls CourtListener |
| Excerpt metadata | Case name, U.S. Reports citation, **decision date**, opinion type (majority, plurality, concurrence, dissent), author, who joined, and the query that retrieved the excerpt. **The date is essential**, so Claude can see which case came later |
| Coverage dates | Three dates recorded at ingestion: the latest decision date in the **full pull before filtering**, the latest decision date **in the sub-area**, and the **ingestion date**. All three go into the system prompt and onto the page |
| Model API | The Anthropic Claude API, called directly. No aggregator |
| Model | **`claude-sonnet-5-5` is the user's leaning, not locked.** Confirmed in Phase 2 with Phase 1's token counts and current prices. Never switch model without the user |
| The loop | An agentic loop **run by our backend**. It ends only when Claude calls `submit_answer` or when the step limit is reached. Claude may run several corpus searches and several update searches |
| Termination and the answer | `submit_answer` is the **stop signal, not the answer**. Its input lists the kept passage IDs. A final composition call **with no tools** then writes the answer using **only the kept passages** as citable sources, with Citations on. Invariant: **every citation in the answer points to a passage the viewer watched Claude keep** |
| Support marking | Cited sentences link to their passages. **Uncited synthesis gets no citation and no link**, and is visibly marked as Claude's own synthesis |
| Case-name verifier | **In the minimum demo.** Every case name in the answer must resolve to a document in the corpus, or it is flagged on screen |
| Premature submit | Handled by **returning an error as the tool result** for that `submit_answer` call. **Never delete the call from history.** Rules in §5.4 |
| Update check | Web search through **Exa's hosted MCP server, with our backend as the MCP client** (§6). Encouraged **through the system prompt only**, plus one reminder (§5.4). Claude controls every search field; our server clamps cost-related fields |
| Update-check honesty | Labelled as a convenience. **Finding nothing does not mean nothing has changed.** Every parameter Claude chose is shown |
| Layout | **Left:** the conversation, Claude's steps as they happen, the update-check band, and the final answer. **Right:** the corpus panel, where passages appear as they are considered, then marked kept or discarded |
| Replay mode | Several stored questions, **recorded through the built system** in Phase 5, clearly labelled as recordings, served by the static web service so **a replay never wakes the API**. At least one replay shows the update check finding something |
| Hosting | Google Cloud Run, **two services**: static web, and API. The API runs **min 0, max 1 instance**. **Cold start is accepted** by the user for cost |
| Wake on landing | **One fire-and-forget `GET /health` when the page loads**; the live-research wake joins that check if it is still open (§8.5). A replay still never depends on the API or waits for it. Decided Oct 23, 2026: *"Wake on landing decided."* |
| Browser disconnect | **Pause, wait for a reconnect, then stop. No new paid call (Claude or Exa) starts while nobody is connected.** The step in flight finishes; the run waits a grace window for the browser to reconnect and resume; if nobody does, it stops, is marked abandoned, records its actual spend, and counts as one of the visitor's daily runs. Detail in §8.5. Decided Oct 23, 2026: *"Agree with this, goes into the brief."* |
| Spend counters | Persisted in **the user's existing MongoDB Atlas cluster**, in a new database. Never in memory only (scale-to-zero would reset them) |
| Limits | Starting values in §8.2, recalibrated after Phase 1 |
| Secrets | `.env`, never read or edited by the agent. The user creates it and any database users |

**Out of scope, explicitly:** legal advice; applying law to a user's facts; judging whether the Court was right; lower-court decisions, statutes and regulations in the corpus; acting as a citator (telling whether a case is still good law); claims of exhaustive coverage; any other area of law.

### Claude's defaults, awaiting the user's veto

1. **Stack:** Python 3.13 via uv, FastAPI on uvicorn, as in the user's previous build. Frontend chosen in Phase 3 (§3).
2. **Licence:** Apache 2.0, as in the user's previous build.
3. **Committing the corpus:** commit the **cleaned opinion text** (public domain) with source attribution, and never commit raw API responses. Decided in Phase 1 after checking CourtListener's terms on redistribution.
4. **Affiliation line** near the name: *"Independent project. Not affiliated with Anthropic."* alongside a plain-text footer credit such as "Built with Claude" (check Anthropic's guidance on wording in Phase 2). The not-legal-advice line is required regardless; its wording is the user's (§12).
5. **Tool names** in §5.2 are working names.
6. **"Live" for the site and API once they are actually up on Cloud Run, never before.** The user lifted the ban on "live" for the previous build's API: *"Why do we avoid "live"? It's literally live on Cloud Run? And will be for the foreseeable future?"* Confirm in Phase 3 whether the same applies here. Until then §10.6 holds. "Live research" stays a feature name either way.
7. **No screenshots or images from the session are published anywhere** (README, prompts file, docs). The user locked this for the previous build: *"Do NOT include any screenshots or images of any kind ever. Lock."* Confirm in Phase 0 that it carries over.
8. **The prompts file.** If the user wants every prompt published again, as in the previous build, reuse its `scripts/extract_prompts.py` (§10.5). Ask in Phase 5.
9. **~~Wake on landing~~: decided by the user on Oct 23, 2026, now a §2 row.** Retained for the record: one fire-and-forget `GET /health` when the page loads, so the API is often awake by the time a visitor starts live research; the live-research wake joins that check if it is still open (§8.5). The user chose this for the previous build after its 85.6 s wake, reversing an earlier "no ping on page load": *"One fire-and-forget ping on anyone landing on the frontend."* ~~Confirm in Phase 3 whether it carries over.~~ **It does not change the Replay mode row in §2:** a replay still never depends on the API or waits for it. The cost is one instance start per visit after a quiet spell; under request-based billing, CPU is billed during startup and requests only.

---

## 3. Process: six phases

| Phase | What | Gate |
|---|---|---|
| **0. Bootstrap** | git; this brief committed unchanged as the first commit; `BUILD_LOG.md`; CLAUDE.md; uv project; `.env.example`; `.gitignore`; `.claude/settings.json` denying the agent access to `.env`; the environment check script and the transcript-retention check (§10.7) | None |
| **1. Corpus** (§4) | Inclusion rule, case list, pull, cleaning, opinion splitting, metadata, coverage dates, filter check, token counts | **The viability gate.** Stop and ask on any §4.9 condition. Corpus frozen afterwards |
| **2. Research** (§9) | Against current docs, not built-in knowledge. **Time-boxed** | Findings plus Phase 1's token counts finalize the model and the limits, with the user |
| **3. Architecture** | A conversation with the user, **topic by topic**, each topic locked with the user's words in `locked-decisions.md`. **Includes art direction, settled with look tests** (several looks rendered locally for the user to compare, at desktop and phone sizes, §7.3). Then a short design note, reviewed by the user. **The conversation starts on the user's green light** | User approval of the design note |
| **4. Build** | **Propose the build plan to the user first.** A few subagents on non-overlapping files, against an interfaces contract the agent writes first. Subagents run on Opus. The frontend subagent loads the frontend-design skill. The wake protocol (§8.5) is part of the interfaces contract. After the first deploy, **the first cold-start sample** (§8.5) | Any deploy step, and any scaling change, only on the user's explicit green light |
| **5. Verify and record** | Tests, failure paths, caps, the verifier, the rejection paths, **the wake protocol against a cold API, and a long-idle cold-start sample** (§8.5); then **the stored replays recorded through the built system**; then the README | User approval |

**At the end of every phase:** append a `BUILD_LOG.md` entry (§10.2), update CLAUDE.md's current-state section, commit, and create a git tag `phase-<n>-done`. Then propose removing any git worktrees the phase left behind (look tests, prototypes), and remove them once the user agrees. **Before any planned compaction**, update CLAUDE.md's current-state section the same way; the previous build went through six compactions.

**Why this order.** The corpus is the one thing that decides whether the project works at all, as a benchmark did in the user's previous build, and its token counts feed the limits and the model choice. Research then has real numbers to work with. The full repo scaffold folds into Bootstrap and Build.

**If time runs short,** cut in this order: discard reasons shown on screen, then the citing-cases lookup (§5.2). The loop, the triage panel, Citations, the verifier, and the update check are the demo.

---

## 4. Phase 1: The corpus

### 4.1 Inclusion rule and case list

**Start Phase 1 by settling the inclusion rule with the user.** The planning draft:

> *Supreme Court opinions deciding whether a government acquisition of information, through technology or third-party records, is a Fourth Amendment search.*

**Known tension, flagged in planning:** that wording covers whether an acquisition **is** a search, and may exclude *Riley v. California* (2014), which concerns whether a warrant is needed to search a phone incident to arrest. *Riley* is the case the public's most common question ("the police searched my phone") most needs. Propose a revised rule to the user; the user decides.

**Candidate case line, from Claude's general knowledge** (not retrieved; confirm each against CourtListener): *Olmstead* (1928), *Katz* (1967), *United States v. Miller* (1976), *Smith v. Maryland* (1979), *Knotts* (1983), *Karo* (1984), *Kyllo* (2001), *Jones* (2012), *Jardines* (2013), *Riley* (2014), *Carpenter* (2018), *Chatrie* (2026). The filter check (§4.7) may add more.

**The newest case, verified Oct 23, 2026** (SCOTUSblog and others): ***Chatrie v. United States***, No. 25-112, decided **June 29, 2026**, 6–3, opinion by Justice Kagan, held that acquiring Google Location History data through a geofence warrant is a Fourth Amendment search, without prohibiting geofence warrants outright. Concurrences by Justices Jackson and Gorsuch (the latter in the judgment), dissents by Justices Alito and Barrett. A third-party site links it on CourtListener at cluster 10881683. On June 30, 2026 the Court vacated and remanded two other geofence decisions in light of it.

**Doctrinal movement the date metadata must support** (Claude's general knowledge, verify): *Katz* displaced *Olmstead*'s trespass test; *Jones* revived trespass alongside *Katz*; *Miller* and *Smith* built the third-party doctrine; *Carpenter* narrowed it for cell-site location data.

### 4.2 Access and terms (verified Oct 23, 2026, Free Law Project)

- **Rate limits changed May 7, 2026.** The default for an authenticated account is 5 requests a minute, 50 an hour, 125 a day. Membership tiers raise this; the user's EDU tier is active. **Read the actual limits on the user's profile page** rather than assuming, and pace requests below them. Many third-party pages still quote the old 5,000 an hour, which is out of date.
- **Usage terms:** membership access is for personal, educational, research, journalistic and exploratory use, and may not power a revenue-positive commercial product. One person, one account; keys are not shared. A non-commercial portfolio demo reads as within these terms (`INFERRED`). Note the terms and anything about redistributing the text in the log. If anything is unclear, stop and ask; the user can email Free Law Project.
- **The token** is `COURTLISTENER_API_TOKEN` in `.env`, used in Phase 1 only. It is never deployed.

### 4.3 How to pull (from CourtListener's case-law API docs, verified Oct 23, 2026)

- Objects: dockets contain clusters (one per decision), and clusters contain opinions (one per majority, concurrence, dissent).
- The recommended text field is **`html_with_citations`**, "the most reliable field for most purposes". Other fields (`plain_text`, `xml_harvard`, `html`, and others) are its sources and less recommended. Strip the HTML at ingestion; keep nothing CourtListener added except what the metadata needs.
- `type` labels each opinion (lead, concurrence, dissent, and so on). **"Combined Opinion" means CourtListener could not split it**, or it holds more than one type.
- `opinions_cited` lists what each opinion cites, and the `/opinions-cited/` endpoint traverses the citation graph in both directions.
- Use **field selection** to fetch only needed fields.
- **Cache raw responses locally** (gitignored) so nothing is fetched twice.

### 4.4 Three tests to run first, before building on the data

1. **Opinion splitting.** For each case, check whether its opinions arrive as separate typed objects or as one "Combined Opinion". If combined, split deterministically on the Court's standard headings (for example "JUSTICE X, dissenting."). Report how many needed splitting, and how.
2. **Text artifacts.** Recent opinions come from PDF extraction. A snippet of the *Chatrie* slip opinion shows words broken across lines and running page headers. **Citations quotes exactly what we store**, so artifacts would appear inside "verbatim" quotations. Clean them (§4.5).
3. **Page numbers.** Check whether the text carries reporter page breaks usable for pinpoint citations. If not, pinpoints fall back to paragraph positions. Report which.

### 4.5 Cleaning rules

- Deterministic, scripted, re-runnable. **Never paraphrase or rewrite.** Allowed: rejoining words broken across lines, removing running headers and footers and page numbers that interrupt text, normalising whitespace, stripping HTML.
- Record per-opinion statistics of what cleaning changed.
- **Spot-check** several cleaned opinions against the official PDF, including at least one old and one recent case.
- The page states that the text is normalised from the official opinion.

### 4.6 Coverage dates

Record the three dates in §2 in a corpus manifest. The full-pull date is the latest decision date in **everything pulled before filtering to the sub-area**, not the latest case in the sub-area.

### 4.7 Filter check

Use the citation graph to list Supreme Court opinions that cite the corpus's core cases but are not in the corpus. Review that list for cases the inclusion rule should have caught. **The user decides each addition.**

### 4.8 Token counts

Count tokens per opinion and in total with the model's tokenizer or the API's token counting. Report a table. These numbers feed §8.2 and the model choice.

### 4.9 Stop and ask if

- Opinions cannot be split reliably by type.
- Cleaning cannot produce text clean enough to quote verbatim.
- A core case is missing or its text is incomplete.
- The terms check raises any doubt.
- The corpus is far larger or smaller than about two dozen opinions (an estimate, `INFERRED`).

### 4.10 Frozen after Phase 1

After the user approves the corpus, it is frozen. **A later change means re-running the Phase 1 checks and logging why.** Replays (§7.4) depend on it.

---

## 5. The research loop

### 5.1 Shape

Our backend runs the loop: send the conversation, receive Claude's tool calls, execute them, stream each step to the browser, repeat. It ends when Claude calls `submit_answer` (subject to §5.4), when the step limit (§8.2) is reached, or when the browser has been disconnected past the grace window (§8.5). An abandoned run composes no answer.

### 5.2 Tools (working names)

| Tool | Does |
|---|---|
| `search_corpus` | Retrieval over the corpus. Returns passage-level chunks **as search result blocks**, so Citations apply (§9). Each carries the §2 metadata |
| `review_passages` | A batch of decisions: for each passage, its ID, keep or discard, and a short reason. **This is what drives the right-hand panel.** Claude's judgements are actions, not inferences from its prose |
| `search_web_updates` | Our wrapper around Exa (§6) |
| `submit_answer` | The stop signal: kept passage IDs, an optional one-line summary, and an **out-of-scope flag** for questions the corpus cannot address (for example "what's the weather") |
| *Citing-cases lookup* | *If time allows (§3).* For a corpus case, the later corpus cases that cite it, with dates. Helps Claude notice overruling |

### 5.3 Retrieval

- **Chunk at paragraph level.** In Citations, a search result's text block is the smallest citable unit, so paragraph chunks give paragraph-level pinpoints.
- The retrieval method (keyword, embeddings, or hybrid) is chosen in Phase 3 from Phase 2's findings. At about two dozen opinions, simple methods may be enough.
- Where metadata lives matters: anything inside a search result's content is citable. Phase 2 checks whether a non-citable slot exists for tool results (§9).

### 5.4 Rejection rules

- **No corpus search yet, and not out of scope:** reject the `submit_answer` call with an error tool result saying a corpus search is required. This one is hard: repeat it if needed.
- **No update search yet:** reject **once**, with an error tool result along the lines of *"Not accepted: no update check has been run. Run one, or explain why it isn't needed, then resubmit."* If Claude resubmits without searching, **accept**, and show *"Update check declined after reminder"* with Claude's stated reason.
- **The rejection is visible** in the step log. It is evidence that the system catches its own gaps.
- Planning reasoning for this design: the API pairs every tool call with a result, there is no mid-conversation system message, and deleting a turn could drop reasoning and thinking blocks. Phase 2 verifies the thinking-block detail.

### 5.5 The final composition call

- No tools. Input: the question, the system guidance, and **only the kept passages** as citable sources.
- Output: text with citations. The UI renders cited sentences as links to their passages and uncited sentences as marked synthesis.
- **Citations and Structured Outputs cannot be used together** (verified Oct 22, 2026, Citations docs), so the answer is plain text with citation blocks, not a structured object.
- Run the case-name verifier on the result before showing it as final.

### 5.6 The system prompt must cover

- The three coverage dates.
- **Research, not advice.** For a question about someone's own situation, present what the Court held and the factors it weighed, and stop short of saying how it applies to them.
- **Describe, never evaluate**: what the Court held and where the opinions disagree, never whether it was right.
- Opinion types matter: never present a dissent or concurrence as the holding.
- Dates matter: a later case can overrule, narrow, revive, or merely cite an earlier one. Date order alone is not treatment.
- The update check is expected near the end, with the trade-off spelled out (narrow windows find new decisions; wider ones catch pending cases and their coverage), and Claude chooses the parameters.
- Out-of-scope questions get the out-of-scope flag.

### 5.7 Step-limit fallback

When the limit is reached, run the final composition call over whatever has been kept so far, and label the answer **"Stopped at step limit. Answer built from the evidence gathered so far."** If nothing was kept, say so instead of composing.

### 5.8 The case-name verifier

Deterministic. Extract case names from the answer text, resolve each against the corpus manifest (names and citations), and flag anything unresolved on screen. Test it with fabricated names, near-misses, and real cases outside the corpus.

---

## 6. The update check (Exa)

### 6.1 Integration

- **Our backend connects to Exa's hosted MCP server** at `https://mcp.exa.ai/mcp` as an MCP client, and exposes our own wrapper tool to Claude. Phrasing for the README and résumé: *"integrates a third-party MCP server as an MCP client."* Never "built an MCP server".
- **Enable the advanced tool.** `web_search_advanced_exa` is not on by default; it is enabled through the server URL's `tools` parameter (verified Oct 23, 2026, third-party listing of Exa's server). Its filters include include and exclude domains, start and end published dates, start and end crawl dates, category, and result count.
- **Send the key as the `x-api-key` header**, not in the URL. The key is `EXA_API_KEY` in `.env`.
- **Without a key** the hosted server works on a rate-limited free tier, reported by one third party as about 2 requests a second and 50 a day per IP (`UNVERIFIED`). We use the key.

### 6.2 What Claude controls and what our server clamps

- **Claude controls** the query, the date window, domains, category, and search type. **The date window is Claude's call**, informed by the coverage dates and the trade-off in §5.6.
- **Our server clamps:** result count at most 10, and the deep search types either refused or counted against the budget. These are cost controls, not judgement calls.
- **Known failing combinations** (verified Oct 23, 2026, third-party listing): with category `company`, the domain and date filters return 400 errors; the tweet category does not support text and domain filters. **Return Exa errors to Claude as tool results**, so it can retry.

### 6.3 Citations on web results

The wrapper parses Exa's results and **re-wraps each one as a search result block**, so the web results carry citations too. Third-party forks return results as JSON inside a text block, with fields including title, URL, published date, and text (`UNVERIFIED` for Exa's current official server; Phase 2 checks). If parsing proves brittle, show web results as plain links labelled as uncited.

### 6.4 Display

- The update-check band sits in the left column, **separate from the corpus evidence**, with its own guarantee sentence (text as fetched from that page).
- It shows every parameter Claude chose.
- Draft label: *"Update check, a convenience: searched the web for material published since [date]. Finding nothing does not mean nothing has changed."* Wording final in Phase 3.
- Web results never feed the answer's cited evidence. They flag; they do not rewrite.
- If the rate limit or an error stops the check: *"Update check unavailable"*, never a failed request.

### 6.5 Pricing (verified Oct 23, 2026, Exa's pricing changelog)

$7 per 1,000 requests with 10 results, text and highlights included; $1 per 1,000 additional results beyond 10. Exa Deep $12 and Deep (Reasoning) $15 per 1,000 requests.

---

## 7. The interface

### 7.1 Layout

Left: the question box, the conversation, each step as it happens (searches with their queries, reviews, update searches with their parameters, rejections), the update-check band, and the final answer. Right: the corpus panel, where passages appear as considered and are then marked kept or discarded (with reasons), each with its metadata.

### 7.2 Labels and states

- The narrow guarantee, on screen: **"This passage appears verbatim in this opinion."**
- Coverage: *"Corpus covers decisions through [full-pull date], pulled [ingestion date]."*
- Not a citator, not exhaustive, not legal advice: stated plainly, without burying it.
- A visible **"waking up" state** for live research, driven by the wake protocol (§8.5). It shows that the server is starting and how long it has been waiting. **It promises no duration until this build has measured one**, and then states the measured range with its dates and source, and that Google does not guarantee it. The previous build's page told visitors "a few seconds" before anyone had measured a start; its starts took 5 to 50 s (§8.5).
- When a spend cap is hit: *"Live research is paused for today. Recorded runs are still available."*
- **Reconnecting:** after a dropped connection, the page says it is reconnecting, then shows the steps it missed and carries on. If the reconnect reaches a server that does not hold the run (§8.5), it shows the stored steps and says the run was interrupted. Wording final in Phase 3.

### 7.3 Art direction

Settled in Phase 3 with look tests, before the build. The user's previous build redesigned its page the same night it first went up, starting about two hours after its first deploy: 23 commits, the largest rework in its log.

- **Phone from the first look test.** Render every look at desktop size and at the user's test device, an iPhone 15 Pro, both upright (393 px wide) and sideways. The previous build's late fixes were phone layouts: a 10 px overflow at 393 px, and side panels overlapping sideways.
- **Measure layout with element rectangles**, not by eye from a screenshot. Bring the tab to the front first: background browser tabs throttle animation frames and show stale canvases.

### 7.4 Replay mode

Several stored questions, chosen with the user in Phase 3 and recorded through the built system in Phase 5. Each replay is labelled as a recording with its date. Replays are static files on the web service and never wake the API. Whether one replay uses a corpus frozen before *Chatrie*, so viewers watch the update check find it, is the user's decision in Phase 3; if yes, it is labelled as such, and live research always uses the full corpus.

---

## 8. Infrastructure, limits and protections

### 8.1 Cloud Run and the domain

- Two services: the static web service and the API (min 0, max 1, request-based billing).
- **Set the API's request timeout comfortably above the longest run**: a live run streams for minutes through one long request.
- **Keep the corpus and index small enough to load fast** on cold start; measure it. Report app startup (corpus and index loading included) separately from container start, read from Cloud Run's logs, so the corpus's share of a cold start is known. The previous build's app was ready 1 to 5 s after its process started; the rest of each start was the container.
- One instance handles concurrent runs, since the work is mostly waiting on APIs. A burst beyond its concurrency is queued or rejected, and the caps cover it.
- **Max instances is not a hard limit.** The previous build's research found that Cloud Run can briefly run more instances than the maximum, including during deploys (re-verify in Phase 2). Nothing correct may depend on there being one instance: spend and visitor counters live in Atlas (§8.4), and each cap check and increment is one atomic update. How much overshoot is tolerable is settled in Phase 3; the previous build's user accepted "a few cents" for the same race, and a run here costs roughly $0.40 (§8.2).
- The domain path goes through the user's **goodnight** nginx gateway, as in the previous build, reusing its settled handling of the client IP behind the gateway. Proposed changes to goodnight are shown to the user before anything touches it.
- Known: Cloud Run may answer "Rate exceeded" while a single-instance service switches revisions. Retry **once, serially**, never with several requests in parallel (§8.5).

### 8.2 Limits: starting values, recalibrated after Phase 1

These are planning estimates (`INFERRED`), not measurements. Planning assumed about 10 steps per run, about 150,000 input tokens in total across a run and about 7,000 output tokens, which at $2 input and $10 output per million tokens (Sonnet 5.5, third-party sources; verify in Phase 2) is roughly $0.35 to $0.45 a run without caching, and perhaps $0.15 to $0.25 with caching of the growing prefix.

| Limit | Starting value |
|---|---|
| Step limit | **12 tool rounds**, plus the final composition call |
| Per-run token ceiling | **400K input, 20K output**, in total |
| Update searches per run | **3**, results clamped to 10 |
| Live runs per visitor | **3 a day**, by client IP |
| Global daily cap | **$10** |
| Monthly cap | **$60**, in our code and as a spend limit in the Anthropic Console (Phase 2 verifies how Console limits work) |
| Cloud Run | max 1 instance |

**Every counter is persisted in Atlas**, never only in memory.

### 8.3 Protections

Input caps on the question; strict handling of every tool input; per-visitor and global caps; errors from Claude, Exa, or the corpus surface as visible steps, never as silent failures. **No request bodies stored** beyond what a replay needs, and replays are recorded deliberately with the user's chosen questions. **One exception, from the disconnect rule (§8.5):** each live run's step events, which can include the visitor's question and Claude's search queries, are kept in Atlas for **about a day** so a reconnect can resume, then deleted by a TTL index. The day is a starting value; it only has to outlast the grace window, and Phase 3 may shorten it. The page's privacy note says what is kept and for how long.

### 8.4 Database

The user's existing Atlas cluster, a new database. The agent creates collections and indexes (for example with TTL for daily counters). **The user creates the readWrite-only database user** for Cloud Run in the Atlas UI; the agent then checks it without reading `.env`.

### 8.5 Cold starts and the wake protocol

**What the previous build learned** (its patch sitting, Oct 23, 2026, from Cloud Run's logs and its `BUILD_LOG.md`):

- **Measured starts,** from "Starting new instance" to ready: 12.6 to 32.4 s after deploys, 21.5 to 49.5 s after idle periods, longest after the longest idle. One sample after 17 s down took 5.47 s, and one after 3 minutes down took 7.4 s; the host very likely still had the image, so **short-idle samples understate a real cold start.** An idle instance shut down about 15 minutes after its last request (observed, not documented).
- **The double cold start.** A visitor's live run waited 85.6 s. The page's wake loop abandoned each `/health` check after 10 s and sent another. Behind max instances 1, the checks stacked up, Cloud Run refused three ("no available instance", 500 and 429), and started a second instance; the first finished starting, answered a check nobody was waiting for, and shut down. That cause is the agent's reading of the logs, not documented by Google. The 10 s timeout had been written by the agent in Phase 4, before any start was measured.
- **An abandoned request still runs.** The first instance answered the check after the browser had given up on it.
- **Cloud Run's own refusals are plain text** (429, 500 or 503), unlike the app's errors, which are JSON with a code.

**The wake protocol, for this build:**

1. **One `/health` check in flight at a time.** Each waits up to 60 s, with 1 s between checks (the previous build's fix; recalibrate from this build's measurements). Never a second check while one is open, and never parallel retries.
2. **A live run is sent only after `/health` has answered.** The run is a long, paid, streaming request: it never goes to a cold instance and is **never retried automatically**. A duplicated run request spends twice, and an abandoned one keeps spending (above).
3. **The frontend tells Cloud Run's plain-text refusals from our JSON errors.** During waking, a plain-text refusal means "still starting" and leads to the next serial check, not to a failure state.
4. **Wake on landing** (§2): the landing check and the live-research wake share one check.
5. **How the waking state reads when the wait runs long** is settled in Phase 3.

**When the browser disconnects mid-run** (decided, §2):

- **Every step's event is written to Atlas as it happens**, under a run ID, with a TTL of about a day (§8.3).
- **On disconnect, the step already in flight finishes**, since that call is already paid for. **No new Claude or Exa call starts** until a browser is connected to the run again.
- **The browser reconnects on its own**, one attempt at a time, in keeping with the wake protocol. The event stream's standard reconnect sends the ID of the last event it received; the server replays every stored event after it, then continues the run.
- **Grace window: 60 s, a placeholder until measured** (§10.7). Tune it in Phase 5 against real drops, such as switching apps on the iPhone mid-run. If nobody reconnects in time, the run stops, is marked abandoned, its actual spend is recorded, and it counts as one of the visitor's daily runs.
- **The worst case costs about the same as stopping at once:** the step in flight. Waiting makes no calls, so it spends no tokens.
- **Why not finish every run regardless:** under request-based billing, CPU is allocated only while a request is open, so a loop that carries on after the stream closes is likely throttled, and may stall or die partway (`INFERRED`, from the previous build's research). It could spend and still not finish. In this design the loop advances only while a connection is open.
- **Accepted edge case:** max instances is not a hard limit (§8.1), so a reconnect can reach a second instance that does not hold the run. That instance shows the stored steps and reports the run as interrupted. Rare, and it costs nothing.
- **Tests (Phase 5):** a drop and reconnect inside the window resumes with no step lost or repeated; a drop past the window stops before the next paid call; no paid call starts while disconnected; the spend recorded for an abandoned run matches the calls it made.

**Measuring a cold start:**

- **The off switch:** `gcloud run services update <api-service> --region us-central1 --scaling=0` shuts the API down gracefully (the previous build's uvicorn ran its normal shutdown in about 0.1 s) and creates no new revision; `/health` answers 503 while it is off. `--scaling=auto` brings it back. In the previous build, gcloud 587.0.0's help listed only "auto" or a positive integer, but 0 was accepted; re-verify in Phase 2. **Every scaling change is a cloud change: the user's green light each time.**
- **Confirm the precondition before timing anything.** Check that `/health` answers 503 while off, and that the service reports automatic scaling after turning it back on. The previous build's first attempt passed the gcloud flags through an unquoted shell variable, which zsh does not split; both commands failed, nothing changed, and the agent timed a warm instance at 0.22 s before noticing.
- **Record the idle time with every sample,** and take the caller-side time and Cloud Run's logged start time together. A sample after seconds of idle is not representative; take at least one after hours of quiet (overnight is simplest) before the page states a range.
- No warm-up call for cold-start measurements (§10.7).
- **The deploy script passes `--scaling=auto` explicitly** for each service, as the previous build's script does, so a deploy after a manual off always returns the API to automatic scaling. After each deploy, confirm both services report automatic scaling with the intended instance limits.
- **The same switch is an emergency stop** for live research beyond the code caps: the web service and its replays keep working while the API is off. Using it is the user's call.

---

## 9. Phase 2: Research checklist

Use current documentation. Claude Code's docs index is at `https://code.claude.com/docs/llms.txt`. For each item, record the source URL and retrieval date in the log. **Time-box this phase.**

1. **Citations with tool results.** Confirm that search result blocks returned from our tools get citations (planning found this documented, Oct 22). Find whether a tool result can carry a non-citable metadata slot, such as document blocks with a `context` field, which the Citations docs describe as passed to the model but not cited. Confirm `cited_text` is extracted from the source and guaranteed to point into it.
2. **Rejected tool calls.** Error tool results, and whether thinking blocks must be passed back intact in tool-use turns.
3. **Prompt caching** for a loop whose prefix grows each step. Current prices: third-party sources give Sonnet 5.5 at $2 input and $10 output per million tokens, with cache reads at $0.20, and one source says cache reads fell to $0.10 (`CONTRADICTED`; use Anthropic's pricing page).
4. **Exa:** the official server's actual output format; that the advanced tool works under our key; **how the published-date filter treats pages with no published date**; rate limits under a key.
5. **Retrieval:** options for a corpus this size, including whether Anthropic offers an embeddings model or recommends a provider.
6. **Cloud Run:** maximum request timeout, streaming (server-sent events) behaviour, concurrency per instance. Also, for §8.5: when Cloud Run may exceed max instances; what it returns to requests that arrive while the only instance is starting; how long an idle instance stays up before shutdown; whether `--scaling=0` is a documented setting in the current gcloud; and whether startup CPU boost is on by default. For the disconnect rule: whether the goodnight gateway passes a client disconnect through to Cloud Run (nginx closes the upstream connection by default; check the gateway's actual config); what happens to work on an instance after its request closes under request-based billing; and whether cancelling an in-flight Claude API call reduces what is billed (assume it does not until verified). Mark which findings are documented by Google and which are only the previous build's observations.
7. **Anthropic Console spend limits:** what exists and how it behaves when hit.
8. **Name collisions:** "Probable Clause" against existing products, domains, and marks. Report; the user decides.
9. **Crediting Claude:** Anthropic's guidance on wording such as "Built with Claude".
10. **CourtListener redistribution:** anything in its terms about publishing the cleaned text (feeds default 3 in §2).

Report findings that change §8.2 or the model choice to the user before Phase 3.

**After drafting the research notes, re-open each cited source** and confirm the claim is on that page. The previous build's recheck caught one finding attributed to the wrong page.

---

## 10. Documentation method

### 10.1 CLAUDE.md is a working file

Its audience is the agent: stack, commands, conventions, constraints, a **"Current state and next step"** section updated at **every phase end**, and these lines:

> At the end of each phase or session, append an entry to `BUILD_LOG.md`.
> This brief is frozen. `docs/design/locked-decisions.md` holds every later decision and wins over the brief.
> Every time written anywhere comes from `date`, run immediately before writing it. Never estimate a time.
> Before a planned compaction, update "Current state and next step".

Include known environment quirks from the user's previous build: `uv run uvicorn` stalled in the preview tool (launch `.venv/bin/uvicorn` directly), `preview_start` failed with `EPERM` (serve from a background shell), and **the shell is zsh, which does not split an unquoted variable**, so `gcloud` flags are written out in full, never passed through a variable (§8.5).

### 10.2 BUILD_LOG.md: the raw record

Append-only. Never edit past entries; corrections go in a later entry. Each entry:

```
## <date and time> — Phase <n>: <name>
**Asked:** <what the user asked for, in the agent's summary; never the agent's own plan>
**Came back:** <what was produced, measured, or found>
**Failures:** <what broke and how it was fixed, if anything>
**Spend:** <paid API calls made and their cost; omit the line if none>
**DECISION (user):** <the user's decisions, directions and approvals, quoting the user where useful>
```

**The agent writes the DECISION line from the conversation, from the first entry.** It records only judgement that came from the user, never the agent's own.

**Times come from the clock, never from estimates.** Run `date` immediately before writing the heading, and commit right after appending, so the heading and the commit agree. The previous build's agent estimated 46 of its first 59 heading times instead of reading them. Some were off by up to twelve hours, some were ahead of the real clock, a planning document copied them before anyone noticed, and fixing them took a one-time exception to the append-only rule. **That exception is not available here.**

### 10.3 Git

- The brief is the first commit, unchanged.
- Commit as you go, with clear messages. **Never squash, rebase, amend pushed commits, or force-push.** The history is part of the deliverable.
- **Tag each phase boundary** (`phase-0-done` through `phase-5-done`).
- Git stays local until the user says to push.
- **Never commit the Claude Code session transcript.** The user decides about it at the end.

### 10.4 locked-decisions.md

Numbered entries (for example T1.1, T1.2 by architecture topic, with earlier phases numbered by phase), each with the decision, the user's words, and the date. **A superseded decision stays in the file, marked superseded, with its replacement below it.** This file, not edits to the brief, is where the project's decisions accumulate.

### 10.5 README, written last

Drafted in Phase 5 from the log, `locked-decisions.md` and git tags, then checked by the user. It must contain:
- What this is, the not-legal-advice statement, and the affiliation line.
- **The guarantee, stated narrowly**, and everything it does not cover.
- How the loop works, with the verifier and the rejection paths.
- The corpus: scope, inclusion rule, source, cleaning, coverage dates, and its public-domain basis.
- The update check and its honesty label.
- Limits and what happens when they are hit.
- **The neighbourhood, acknowledged:** CourtListener offers citation lookup framed as a guardrail against AI hallucinations, and announced an MCP connector for Claude (verified Oct 23, 2026, Free Law Project). The pitch is how a customer would build this on Claude, not novelty.
- **How this was built:** a phase timeline from git tags, links to the real CLAUDE.md, the log and `locked-decisions.md`, and a short list of the user's decisions. **Anything that cannot be traced to the log or a commit gets cut.**

Also, from the previous build:
- **Every count is produced by a script** (prompts, commits, tests, hours, lines of code), never counted by eye (§10.7).
- **Public text never calls Nguyen "the user".** That is log vocabulary, and on this page it also means the visitor. Pick one voice for the author when drafting the README and keep it; the previous README used "the person" and still slipped once with "(the user's)".
- **Link to the page a person reads**, never a raw `.md` file or an API URL. The previous page linked a vendor's Markdown source until the user spotted it.
- **If every prompt is published** (default 8), reuse the previous build's `scripts/extract_prompts.py`. It deduplicates transcript records by ID (the first count without that was 309 prompts instead of 92) and redacts local paths outside the repo.
- **The build story stays open after the first push.** The previous build had a patch sitting after publishing, and its README gained a timeline row and two "what went wrong" items for it. Any later sitting gets its own row. **Before any later push, regenerate the prompts file (if published) and copy its figures into the README**, so the two never disagree.

### 10.6 Wording rules

- Status word: **"working."** Avoid "production", "deployed", "live" and "shipped" as status claims. ("Live research" as a feature name is fine.) "Live" may be allowed once the site is actually up, if the user confirms default 6 (§2).
- Never: "exhaustive", "comprehensive", "settled law", "guaranteed accurate", "citator", "no hallucinations". The only guarantee is the narrow one.
- No "record time" or "blazing fast". Plain, checkable facts only.
- Keep em dashes rare.

### 10.7 Hygiene rules from the previous build

Each rule names the stumble it prevents.

- **Dates are Chicago dates, computed explicitly.** Every date shown to a person (log, page, replay labels, coverage dates, README) is in America/Chicago, converted in code, never taken from a UTC timestamp. Stored timestamps carry their time zone. The previous build's summariser stamped evening Chicago runs with the next day's UTC date, and the page had to be regenerated.
- **Counts come from scripts.** The previous build's agent counted 60 log headings when there were 59, and 309 prompts when there were 92.
- **No absolute local paths in any committed file**, the log included. Use paths relative to the repo, or `~`. The previous build committed a path containing the username to its log before a redaction rule existed, and it stays in that history.
- **Check secrets without reading `.env`.** The agent cannot create `.env` (a permission rule blocks it). In Bootstrap, write `scripts/check_env.py`, which reports only whether each required variable is set, never its value. Before the first step that needs a secret, ask the user to fill `.env` and run the check. The previous build's first two probes failed on a variable that was missing or commented out.
- **Transcript retention, checked in Phase 0.** Claude Code's default cleanup removes session transcripts after about 30 days unless `cleanupPeriodDays` is set. The transcript is the only source for a prompts file. Check whether it is set and tell the user. **Never change user-level settings without asking.**
- **Timed measurements** (run durations, latencies, anything quoted on the page): one throwaway warm-up through the same code path, recorded and excluded; SDK clients created with `max_retries=0`, so a retry never hides inside a measured time. The previous build added the warm-up rule only after its first benchmark. A cold-start measurement is the one exception: it times the first request after the service has idled, with no warm-up.
- **Timeouts and retries come from measurements.** Every client timeout, retry interval and retry count names its basis (a measurement, or "placeholder until measured") in a code comment and in the interfaces contract. Retries against a single-instance service are serial, never parallel, and a paid request is never retried automatically. The previous build's agent wrote a 10 s wake timeout before any cold start was measured, and it turned one cold start into two (§8.5).
- **Read the evidence before changing anything.** When something misbehaves after a deploy, read the Cloud Run configuration and logs (read only), explain the cause to the user, and only then propose a change. The previous build's patch sitting worked this way, and a locked decision it reopened was recorded on the record rather than edited away. Here that means a superseded entry in `locked-decisions.md` (§10.4).
- **The environment quirks in §10.1** belong in CLAUDE.md from the first session.

---

## 11. Facts and sources used in planning

| Fact | Source, retrieved |
|---|---|
| Citations: `cited_text` guaranteed to point into provided documents; incompatible with Structured Outputs; `title` and `context` of document blocks not cited | Anthropic Citations docs, Oct 22, 2026 |
| Search result blocks can come from tool calls and get citations; the text block is the minimum citable unit | Anthropic search results docs, Oct 22, 2026 |
| Government edicts doctrine; *Georgia v. Public.Resource.Org* (2020) | Several legal sources, Oct 22, 2026 |
| *Chatrie v. United States* facts | SCOTUSblog case page and others, Oct 23, 2026 |
| CourtListener API structure, fields, citation graph | Free Law Project wiki, Oct 23, 2026 |
| CourtListener rate limits and membership terms | Free Law Project wiki and blog (May 7, 2026 post), Oct 23, 2026 |
| Official PDF coverage | GovInfo feature page; university law library guides, Oct 23, 2026 |
| Exa hosted server, keyless free tier, header auth | Exa docs, Oct 23, 2026; rate figures from a third party |
| Exa advanced tool parameters and failing combinations | Third-party listing of Exa's MCP server, Oct 22–23, 2026 |
| Exa pricing | Exa pricing changelog, Oct 22, 2026 |
| Sonnet 5.5 pricing | Third-party pricing pages, Oct 22, 2026 (verify) |
| Lessons from the previous build (§7.2, §7.3, §10.2, §10.5, §10.7) | The Haiku Decision API repository: every Failures line in its `BUILD_LOG.md`, its CLAUDE.md, README and git history, Oct 23, 2026 |
| Cold-start figures, the double cold start, `--scaling=0`, Cloud Run's plain-text refusals (§8.1, §8.5) | The same repository's patch sitting: `BUILD_LOG.md` entries of Oct 23, 15:28, 15:33 and 15:45 CDT, its README "Cold starts" section, and its CLAUDE.md as of 15:52 CDT. Figures read from Cloud Run's logs by that build's agent; the double-start cause is its reading, not Google's documentation |

---

## 12. Stop and ask the user when

- Phase 1 starts (the inclusion rule) and when it hits any §4.9 condition.
- Any filter-check addition (§4.7).
- Phase 2 finds anything that changes the model, the limits, or a §2 decision.
- Any item marked "Claude's default, awaiting the user's veto" first matters.
- The architecture conversation is ready to start, and when the design note is ready for review.
- Art direction look tests are ready to compare.
- The Phase 4 build plan is ready (before starting).
- Wording that is the user's to write: the disclaimer and not-legal-advice line, the update-check label, the replay questions.
- Spending real API calls beyond small checks, or anything near the caps.
- **Any deploy step**, any `gcloud` command that creates or changes cloud resources (scaling changes included, even for a measurement), and any change to goodnight: only on the user's explicit green light.
- Something misbehaves on Cloud Run: read the configuration and logs, explain the cause, then propose (§10.7). Change nothing first.
- Anything in §2 looks impossible or wrong.
- An instruction can be read two ways (§0: restate first).
- Removing git worktrees, or changing any user-level Claude Code setting.

---

## 13. Changes from v1 and v2 (record only)

*v1 was written Oct 23, 2026 and never committed. v2 replaced it the same day, after a review of the previous build's public repository, and was never committed either. v3 replaced v2 that afternoon, after the previous build's cold-start patch sitting. v4 replaced v3 later the same afternoon, after two decisions by the user; none of the four versions was committed before v4. Nothing here is an instruction; the sections above are.*

### v3 to v4

**Corrected (v3 text retained, superseded):**
- Header, v3: *"v3 is the version committed as the first commit."* v4 is.
- §8.5, v3, items 4 and 5: *"4. If default 9 (§2) is confirmed, the landing check and the live-research wake share one check. 5. Settled in Phase 3, as an architecture topic: what the backend does when the browser disconnects in the middle of a run (stop the loop, or finish and count it), and how the waking state reads when the wait runs long. The previous build's runs cost fractions of a cent; a run here costs roughly $0.40, so this is a spend question as well as an interface one."* Both questions are now decided; only the long-wait wording stays for Phase 3.

**Added:**
- §2: two rows, Wake on landing and Browser disconnect, with the user's words. Default 9 marked decided, its text retained.
- §5.1: a third way a run ends.
- §7.2: the reconnecting and interrupted states.
- §8.3: run events kept about a day for reconnects, an exception to "no request bodies stored", stated on the page.
- §8.5: the disconnect rule in full, with its Phase 5 tests.
- §9: item 6 gains three checks for the disconnect rule.

### v2 to v3

**Corrected (v2 text retained, superseded):**
- §7.2, v2: *"A visible "waking up" state for live research. The user's previous build measured 25.7 s to wake its API on the first instance of a new revision (about 22 s container start, 3.3 s app startup), and his insurance demo's API took 17.5 s. A normal cold start was never measured, and that page told visitors "a few seconds" anyway. Measure a normal cold start (after the service has idled, not after a deploy) in Phase 5, and state only a measured wake time on the page."* Starts after idle have since been measured (§8.5), the measuring moves partly into Phase 4, and the waking state now follows the wake protocol.
- §8.1, v2: *"Known: Cloud Run may answer "Rate exceeded" while a single-instance service switches revisions. Retry."* An unqualified retry is the pattern behind the double cold start. Now: once, serially.
- Header, v2: *"v2 is the version committed as the first commit."* v3 is.

**Added:**
- §2: default 9 (wake on landing), with a note that the Replay mode row is unchanged.
- §3: the wake protocol in the Phase 4 interfaces contract; the first cold-start sample after the first deploy; the wake protocol tested against a cold API and a long-idle sample in Phase 5; scaling changes behind the green light.
- §8.1: app startup reported separately from container start; max instances is not a hard limit, with atomic cap checks and overshoot tolerance left to Phase 3.
- §8.5: new. What the previous build learned, the wake protocol, the disconnect question for Phase 3, and how to measure a cold start (the `--scaling=0` off switch, checking the precondition, idle time recorded, the deploy script's explicit `--scaling=auto`, the emergency stop).
- §9: item 6 expanded for §8.5.
- §10.1: zsh does not split an unquoted variable.
- §10.5: the build story stays open after the first push; prompts and README figures regenerated before any later push.
- §10.7: timeouts and retries come from measurements; read the evidence before changing anything.
- §11: one source row.
- §12: scaling changes named under the green light; read-first when Cloud Run misbehaves.

### v1 to v2

**Corrected (v1 text retained, superseded):**
- §7.2, v1: *"The user's previous build measured about 25 seconds to wake a min-0 Cloud Run API, most of it container start."* The 25.7 s was the first instance of a new revision, not a typical cold start, and no typical one was measured.
- §7.3, v1: *"The user's previous build redesigned its page the morning after it first went up."* It was the same night, about two hours after the first deploy. The "morning" came from that build's estimated log times.
- §10.6, v1: the "live" ban stood without qualification. It now points to default 6.

**Added:**
- Header: the v2 note.
- §0: restate an ambiguous instruction before acting; §13 is a record only.
- §2: defaults 6 ("live" once actually up), 7 (no screenshots or images), 8 (the prompts file).
- §3: Bootstrap gains the environment check and the transcript-retention check; look tests at phone size; worktree cleanup at each phase end; CLAUDE.md updated before each planned compaction.
- §7.3: phone sizes from the first look test; layout measured with element rectangles.
- §9: re-open each cited source after drafting.
- §10.1: two new CLAUDE.md lines (clock times, compaction).
- §10.2: times come from `date`.
- §10.5: counts by script, public voice, readable links, the prompts extractor.
- §10.7: new, hygiene rules.
- §11: one source row.
- §12: two new stop-and-ask cases.
