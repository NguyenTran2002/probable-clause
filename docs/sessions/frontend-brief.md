# Frontend session brief: art-direction look tests

*Written Oct 23, 2026 by the main session, for a second Claude Code session the user starts in this same folder (locked-decisions P1.6). If you are that session, read this file in full, then the files it names, before doing anything.*

---

## 1. Who you are and what you are for

You are the **frontend session** of Probable Clause. Another Claude Code session, the **main session**, is working in this same folder and branch at the same time: it runs Phase 1 (building the case-law corpus) and owns every shared document.

Your job now is the **art-direction look tests** from brief §7.3: several distinct visual directions for the page, rendered locally for the user to compare at desktop and phone sizes. **You are done when the user picks a direction** (or a combination) and that choice is in your log in the user's words. The contract-bound mock frontend comes later, after interfaces contract v1 (start of Phase 4), and is not part of this job.

## 2. Read first

1. `PROBABLE_CLAUSE_KICKOFF.md` in full, the frozen brief. Most relevant to you: §1 (what this is), §2 (binding decisions), **§7 (the interface)**, §6.4 (the update-check band), §5.5 and §5.8 (how the answer and the verifier show), §8.5 (waking, reconnecting), §10.6 (wording rules).
2. `docs/design/locked-decisions.md`. It **wins over the brief.** Most relevant to you: P0.3 (two-session rules), P0.4 (images), P1.2, P1.3 (update-check display), P1.4 and P1.5 (disclosure and credit), P1.6 (this session).
3. `docs/research/licensing.md`, which drives the notices and credits the page must carry.
4. `CLAUDE.md`, including its "If you are the frontend session" section.

Load the **frontend-design** skill before designing.

## 3. Rules for sharing this folder (P0.3)

- **Write only under `web/looktests/`** and your own log, `docs/sessions/frontend-log.md`. Never edit `BUILD_LOG.md`, `CLAUDE.md`, `docs/design/`, `docs/research/`, the brief, `pyproject.toml`, `uv.lock`, `scripts/`, `data/` or `.claude/`. If one of those needs a change, tell the user, and the main session makes it.
- **Commit only your own paths, by name:** `git add web/looktests docs/sessions/frontend-log.md && git commit -m "..." -- web/looktests docs/sessions/frontend-log.md`. Never `git add -A` or `git add .`.
- **Never** `git stash`, `git reset`, `git checkout -- .`, `git restore` on paths you don't own, `git switch` or `git checkout <branch>`, `git rebase`, `git commit --amend`, or any tag. If git reports `index.lock`, wait a few seconds and retry; never delete the lock.
- End every commit message with: `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>` (or your own model's line, as your session's attribution reminder gives it).
- Don't touch `.venv` or run `uv sync` or `uv add`. Never read or edit `.env`.
- **Never call CourtListener.** The main session is pulling from it under the user's rate limit, and every call counts against it.
- **No `.png`, `.jpg` or `.jpeg` file is ever committed**, screenshots included (P0.4). `.svg` and `.ico` are allowed. You may take screenshots in the browser pane for your own checking, but never save them into the repo or publish them.
- No absolute local paths in any committed file.

## 4. Your log

`docs/sessions/frontend-log.md`, append-only, in the same entry format as `BUILD_LOG.md` (brief §10.2):

```
## <date and time> — Look tests: <short name>
**Asked:** <what the user asked for, in your summary>
**Came back:** <what was produced or found>
**Failures:** <what broke and how it was fixed, if anything>
**DECISION (user):** <the user's decisions and directions, quoting the user>
```

- Run `TZ=America/Chicago date "+%b %-d, %Y, %H:%M %Z"` **immediately before** writing each heading. Never estimate a time. Commit right after appending.
- Write an entry at the end of each sitting and whenever the user decides something. The DECISION line records only the user's judgement, never yours.
- The main session copies your entries' decisions into `BUILD_LOG.md` and `locked-decisions.md`. Do not number decisions yourself.

## 5. What the look tests must show

**Format.** Static HTML and CSS, with as little JavaScript as possible and no build step, so nothing pre-decides the frontend stack (chosen in Phase 3). One folder per look: `web/looktests/<look-name>/index.html`, with any assets alongside. A plain `web/looktests/index.html` links to all of them. Propose how many looks before building; the previous build compared three. If you want to build looks in parallel with subagents, propose that to the user first.

**Every look renders the same mock run**, so the user compares style rather than content. Everything shown must be clearly sample content.

**Layout** (brief §2 and §7.1):
- **Left column:** the question box; the conversation; each step as it happens; the update-check band; the final answer.
  - Steps to show: a corpus search with its query; a review of passages; an update search with every parameter Claude chose; a **rejected `submit_answer`** shown as a visible step.
- **Right column:** the corpus panel. Passages appear as considered, then are marked **kept** or **discarded**, each with a short reason. Each passage carries:
  - case name and U.S. Reports citation
  - **decision date**
  - opinion type (majority, plurality, concurrence, dissent), author, and who joined
  - the query that retrieved it
- **The final answer:**
  - Cited sentences link to their passages.
  - **Uncited synthesis has no link** and is visibly marked as Claude's own synthesis.
  - A **case-name verifier flag** shows on one name that does not resolve.
- **The update-check band (P1.3):** sits in the left column, separate from the corpus evidence. It shows:
  - Claude's own short synthesis of what the web search found
  - a link per source (title, URL, published date), **never quoted page text**
  - every parameter Claude chose
  - the draft honesty label: *"Update check, a convenience: searched the web for material published since [date]. Finding nothing does not mean nothing has changed."* (placeholder, final wording is the user's)

**Wordmark** (brief §2): *Probable C**l**ause*. The "l" is set in an accent colour from **this project's own palette**. Never Claude's brand colour, never Anthropic's styling, never "Claude" in the name. It may be text and CSS, or an `.svg`.

**Labels and notices that must have a place in the layout** (brief §7.2, licensing notes, P1.4, P1.5). Treat their wording as placeholder; the final wording of the disclaimer, the not-legal-advice line and the update-check label is the user's (brief §12).
- The narrow guarantee, on each passage: **"This passage appears verbatim in this opinion."**
- Coverage: *"Corpus covers decisions through [date], pulled [date]."*
- Not legal advice; not a citator; not exhaustive. Stated plainly, not buried.
- **AI disclosure:** the visitor is using AI.
- **Independent checking:** factual assertions should be checked against the opinions.
- **Opinion-text credit:** text from the U.S. Reports and Supreme Court opinions via CourtListener (Free Law Project), with a note that Free Law Project did not produce, review or endorse this analysis. Always "Free Law Project", never "The Free Law Project". No Free Law Project logo.
- **Text status:** normalised from the official opinion and unofficial; the official text is the U.S. Reports.
- ~~**Syllabus label:** when a passage comes from a syllabus, it is labelled the Reporter of Decisions' summary, "no part of the opinion of the Court", and styled apart from opinion text.~~ *Dropped Oct 23, 2026 (locked-decisions P1.13): the syllabus is never in the corpus, so no passage comes from one and no syllabus label is needed.*
- **Slip-opinion note**, for a case not yet final in the U.S. Reports: subject to formal revision.
- **Credit and affiliation (P1.5):** a plain sentence such as "Answers are written by Claude, Anthropic's model, through the Claude API", and *"Independent project. Not affiliated with Anthropic."* No Anthropic, Claude or Exa logos, and no badge.

**States** (brief §7.2, §8.5). Show each, at least as a toggled panel or a second page per look:
- **Waking up:** the server is starting, with how long it has been waiting. It **promises no duration.**
- **Reconnecting:** after a dropped connection, then catching up on missed steps. **Interrupted:** a run the server no longer holds.
- **Cap reached:** *"Live research is paused for today. Recorded runs are still available."*
- **Stopped at the step limit:** *"Stopped at step limit. Answer built from the evidence gathered so far."*
- **Update check declined after reminder,** with Claude's stated reason; and **"Update check unavailable."**
- **Replay:** clearly labelled as a recording, with its date.

**Wording rules** (brief §10.6): the status word is "working"; never "exhaustive", "comprehensive", "settled law", "guaranteed accurate", "citator" (except in "not a citator"), "no hallucinations"; keep em dashes rare.

**Sample content.** Use clearly marked sample text: no invented quotation presented as real, and no real-looking citation attached to invented text. When Phase 1 has cleaned passages, the user will tell you where they are, and you may swap them in.

## 6. How to build and check

- **Fonts and libraries:** stylesheets from Google Fonts only; scripts only from a pinned CDN version, if any. Note each font's and library's licence in your log.
- **Serve from a background shell**, for example `python3 -m http.server 8765 --directory web/looktests`, because `preview_start` failed with `EPERM` in the previous build. Use a port other than 8000, which the main session may use.
- **Check every look at desktop size and at the user's iPhone 15 Pro, upright (393 px wide) and sideways.** The previous build's late fixes were phone layouts: a 10 px overflow at 393 px, and side panels overlapping sideways.
- **Measure layout with element rectangles** (`getBoundingClientRect`, `scrollWidth` against `clientWidth`), not by eye from a screenshot. **Bring the tab to the front first:** background tabs throttle animation frames and show stale content.
- No horizontal page scroll at any size.

## 7. Stop and ask the user when

- You are ready to propose how many looks to build, and their directions (before building).
- The looks are ready to compare.
- Any wording that is the user's to write comes up.
- Anything would touch a file outside `web/looktests/` and your log.
- An instruction can be read two ways: say in one line how you read it, and wait (brief §0).

At the end, when the user picks a direction: write a log entry quoting the user's choice, commit your own paths, and tell the user it is ready for the main session to fold in.
