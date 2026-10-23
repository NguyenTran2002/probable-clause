# Licensing and terms of every source

*Researched Oct 23, 2026 (America/Chicago), before Phase 1's pull, at the user's direction: "Let's confirm license of all sources we want to pull and see what we're allowed to do with them first, because this also affects the frontend design as well." Three research subagents read the sources; the main session then re-fetched every cited page and string-matched every quote (method at the end). Nothing here is legal advice; it is a reading of published terms, for the user to decide on.*

Labels: **DOC** the page says it; **INF** our reading; **CONTRA** sources disagree.

---

## 1. Supreme Court opinions (the corpus text)

| Finding | Label | Source |
|---|---|---|
| Works of the U.S. Government are not protected by copyright: "Copyright protection under this title is not available for any work of the United States Government" | DOC | https://www.law.cornell.edu/uscode/text/17/105 |
| Judges are not "authors" under the government edicts doctrine (*Georgia v. Public.Resource.Org*, 2020), covering "whatever work they perform in their capacity as judges" | DOC | https://www.law.cornell.edu/supremecourt/text/18-1150 |
| That holding reads *Banks* as denying copyright to opinions "without excepting concurrences and dissents that carry no legal force" | DOC | same |
| The syllabus "constitutes no part of the opinion of the Court but has been prepared by the Reporter of Decisions" | DOC | https://www.law.cornell.edu/supremecourt/text/25-112 |
| The Reporter is appointed by the Court (28 U.S.C. § 673), so the syllabus is a work of the U.S. Government and uncopyrighted under § 105. No page states this directly | INF | https://www.law.cornell.edu/uscode/text/28/673 |
| Star pagination and parallel citations are not protected (*Matthew Bender v. West*, 2d Cir. 1998): "will not infringe West's copyright by inserting star pagination" | DOC | https://law.resource.org/pub/us/case/reporter/F3/158/158.F3d.693.97-7430.html |
| The Eighth Circuit held the opposite in 1986 (*West v. Mead*), in a preliminary-injunction posture: "the LEXIS Star Pagination feature infringes West's copyright in the arrangement" | CONTRA | https://law.resource.org/pub/us/case/reporter/F2/799/799.F2d.1219.85-5399.html |
| West headnotes are copyrightable (*Thomson Reuters v. ROSS*, 3d Cir., Sept. 29, 2026; read through a secondary source only) | DOC (secondary) | https://www.lawnext.com/2026/10/no-more-than-an-ordinary-copyright-case-3rd-circuit-unseals-its-opinion-in-thomson-reuters-case-against-ross.html |
| supremecourt.gov has no copyright or reuse statement; its only copyright sentence concerns linked third-party sites | DOC (absence) | https://www.supremecourt.gov/policies/web_policies_and_notices.aspx |
| GovInfo: "public documents can generally be reprinted without legal restriction", but they "may contain copyrighted material which was used with permission" | DOC | https://www.govinfo.gov/about/policies |
| An altered GPO-certified PDF loses its certification, so normalised text is unofficial | DOC + INF | https://www.govinfo.gov/about/authentication |
| **The Court's Term 2025 table lists *Chatrie* as "609 U.S. 605"**, while CourtListener's cluster has no citation (probe, Oct 23). The brief calls it a slip opinion | CONTRA | https://www.supremecourt.gov/opinions/slipopinion/25 |

**What this means:**
- Every opinion type, and the Reporter's syllabus, may be reproduced verbatim, served in the app, and committed to the public repo.
- U.S. Reports page numbers and parallel citations (S. Ct., L. Ed.) are fine to carry as metadata.
- **Never carry over** West or Lexis headnotes, synopses, key numbers or editorial matter. **Do not embed S. Ct. or L. Ed. star-paging markers in the text** (the Eighth Circuit risk). Pinpoints use U.S. Reports pages only.
- **The syllabus is labelled as the Reporter's summary**, kept separate from the opinion, and never presented as the Court's words or holding.
- The text is labelled normalised and unofficial, with the U.S. Reports named as the official text. Any opinion still in slip form carries the Court's revision notice.

## 2. CourtListener (Free Law Project)

| Finding | Label | Source |
|---|---|---|
| Terms of Service, updated Aug 5, 2026; the live courtlistener.com text matches the wiki copy on every quote below | DOC | https://www.courtlistener.com/terms/ |
| "judicial opinions, motions, and other filings are generally in the public domain" | DOC | same |
| Bulk data files are "free of known copyright restrictions" (Public Domain Mark). No licence is stated for API output | DOC + absence | https://wiki.free.law/c/courtlistener/help/api/bulk-data/bulk-legal-data |
| Membership API access is "intended for personal, educational, research, journalistic, and exploratory use" | DOC | https://free.law/membership/allowed-api-usage/ |
| It "may not be used to power a revenue-positive commercial product, service, or feature", nor "to build tools for for-profit or non-profit organizations" | DOC | same |
| "If you need access for a product or a team, talk to us about a commercial agreement." Whether a free portfolio demo is a "product" is undefined | DOC + INF | https://www.courtlistener.com/terms/ |
| "Calls made with your credentials are treated as yours, including calls an agent makes"; no sharing, reselling or pooling of tokens | DOC | same |
| "If you republish or display our data, do not present it in a way that suggests Free Law Project … produced, endorsed, or verified an AI-generated analysis of it" | DOC | same |
| No required attribution line or link-back. The name is "Free Law Project", never "The Free Law Project" | DOC (absence) + DOC | https://wiki.free.law/c/courtlistener/help/general/how-can-i-cite-courtlistener-in-an-academic-paper |
| Logos are CC BY-ND 4.0, offered "for use in articles, blog posts, or printed material" | DOC | https://free.law/press-assets/ |
| Upstream text sources (Harvard CAP, Lawbox, resource.org): none found to impose conditions; CAP's limits expired in March 2024, "without restriction on access or use" | DOC + INF | https://lil.law.harvard.edu/blog/2024/03/26/transitions-for-the-caselaw-access-project |
| EDU memberships are free and renew every 6 months; EDU rate limits are not published (the user's account shows 20 a minute, 1,000 an hour) | DOC | https://wiki.free.law/c/courtlistener/help/memberships/individual-memberships/individual-memberships-faqs |

**What this means:**
- The brief's design already fits: **CourtListener is called once, in Phase 1, under the user's own token, and the deployed app never calls it** (§2). Anonymous visitors never use the token, so the token-sharing and "product" questions do not arise for the live app.
- Committing the cleaned public-domain text is supported (default 3), with attribution as a courtesy.
- **The page must not suggest that Free Law Project produced, endorsed or verified Claude's analysis.** Credit it as the source of the opinion text, in plain text, with no FLP logo.
- Each case's `source` code is recorded in Phase 1, so the provenance of each text is known.

## 3. Supreme Court Database (SCDB)

- No licence or terms found on https://scdb.la.psu.edu/. A citation with the release number is requested (DOC per the agent; that page renders by JavaScript and **could not be re-verified**).
- CourtListener's SCDB fields come from an unknown release.
- **INF:** if the manifest uses no SCDB-derived field (vote counts come from each opinion's own lineup instead), no SCDB citation is owed. P1.2 already keeps `scdb_decision_direction` out.

## 4. Exa (the update check)

| Finding | Label | Source |
|---|---|---|
| The Terms of Service are a PDF with no revision date; its metadata date is Mar 4, 2025 | DOC + INF | https://exa.ai/terms |
| §4.2(a): without written permission, users may not "copy, distribute, transmit, display, perform, reproduce, duplicate, publish" any information "obtained from or through, the Services, except for temporary files that are automatically cached by your web browser for display purposes, or as otherwise expressly permitted in these Terms or by us in writing" | DOC | same |
| §4.1's display licence is "personal, non-assignable, non-sublicensable" | DOC | same |
| No clause expressly permits showing results to third parties; no attribution requirement; no retention limit stated | INF / absence | same; https://exa.ai/docs/reference/exa-mcp |
| §4.2(e): no "resell, lease or sublicense the Services to any third party without our prior consent" | DOC | https://exa.ai/terms |
| §7.1.2: "You should not rely on the Services or any Output for advice of any kind", including legal advice. This is a disclaimer, not a ban on legal apps | DOC | same |
| Exa's logos are its trademarks; do not use them | DOC | same |
| The hosted MCP server has no separate terms; it works without a key at a rate limit | DOC | https://exa.ai/docs/reference/exa-mcp |

**What this means:** **read literally, the terms do not permit what §2 and §6 plan**: showing Exa results on a public page, and storing them indefinitely in replays. Building apps is plainly what the API is for, so the likely answer is yes. But the only text that says so would be **written permission from Exa**, and this project's standard is to claim nothing it cannot back up. See the decision list below.

## 5. Anthropic

| Finding | Label | Source |
|---|---|---|
| **The Usage Policy page already shows a version "Effective Nov 12, 2026"**, announced Oct 8, 2026 | DOC | https://www.anthropic.com/legal/aup ; https://www.anthropic.com/news/2026-usage-policy-update |
| From Nov 12: the legal high-risk area is "advising an individual on their legal rights, obligations, or liability" on a specific matter; such advice requires that "A qualified person must meaningfully review" it, and that the person be "clearly told that AI was used to produce it" | DOC | https://www.anthropic.com/legal/aup |
| From Nov 12, these rules do not apply to "General information or educational content, including explaining what a law says" … "without applying it to the individual's circumstances" | DOC | same |
| **In force today (since Sep 15, 2025):** the high-risk requirements cover "legal, financial, and employment-related use of Claude", with "human-in-the-loop oversight and AI disclosure", and "apply specifically when models' outputs are consumer-facing" | DOC (announcement; full policy text not found) | https://www.anthropic.com/news/usage-policy-update |
| Consumer-facing chatbots and agents "must disclose to users that they are interacting with AI rather than a human" | DOC | https://www.anthropic.com/legal/aup |
| Commercial Terms: the customer must notify users "that factual assertions in Outputs should not be relied upon" without independent checking | DOC | https://www.anthropic.com/legal/commercial-terms |
| Commercial Terms: Anthropic "hereby assigns to Customer its right, title and interest (if any) in and to Outputs" | DOC | same |
| No official "Built with Claude" badge or wording found. The trademark guidelines require prior approval for use of Anthropic's marks, with no implied "sponsorship or endorsement" and no altered marks | DOC (absence) + DOC | https://www.anthropic.com/legal/trademark-guidelines |
| Citations are "guaranteed to contain valid pointers to the provided documents"; no display rule for Citations. The display rule ("citations must be included to the original source") belongs to Anthropic's own web search tool, which we do not use | DOC | https://platform.claude.com/docs/en/build-with-claude/citations ; https://platform.claude.com/docs/en/agents-and-tools/tool-use/web-search-tool |

**What this means:**
- **Required on the page:** that the visitor is using AI, and that its factual assertions should be checked independently. Both fit the narrow guarantee the page already states.
- **From Nov 12**, the research-not-advice rule in brief §2 matches the policy's exclusion almost word for word ("explaining what a law says … without applying it to the individual's circumstances").
- **Until Nov 12, the policy in force names "legal" use in consumer-facing outputs as high-risk, requiring human-in-the-loop oversight.** The project goes public before Nov 12. The full text of the in-force version, which would define "legal" use, was not found.
- **Credit line:** no Anthropic or Claude logo, no badge, nothing implying endorsement. A plain descriptive sentence plus the affiliation line (default 4). Even "Built with Claude" is not an approved phrase.

---

## Decisions for the user

1. **Exa.** (a) Email Exa for written permission covering public display and stored replays; (b) keep Exa but show only titles, URLs and dates, which reduces copyright exposure but not the ToS issue; or (c) switch the update check to Anthropic's own web search tool, which changes a §2 decision and the "MCP client" story.
2. **Anthropic Usage Policy before Nov 12.** Rely on the published Nov 12 scope, ask Anthropic, or keep live research limited until Nov 12.
3. **SCDB.** Keep every SCDB-derived field out of the manifest (no citation owed), or use some and cite the release.
4. **Free Law Project.** Optionally email to confirm a free public portfolio demo built on a frozen corpus is in scope. The design already keeps the token out of the deployed app.
5. **Credit and disclosure wording** for the page (the user's to write, §12): AI disclosure, the independent-checking notice, the Free Law Project non-endorsement credit, the Reporter's-syllabus label, the unofficial-text note, and the Anthropic non-affiliation line.

## Method

- Three research subagents read the sources on Oct 23, 2026 and returned short verbatim quotes with URLs.
- The main session re-fetched every cited page (HTML stripped, entities and curly quotes normalised) and string-matched every quote. Results:
  - Official sources: 22 of 22 matched.
  - Anthropic and Exa docs: 16 of 16 matched.
  - CourtListener: 17 of 18 matched; the remaining one differs only by a space at a link boundary.
  - Exa's terms PDF: text extracted with `pdftotext`; all 8 clauses quoted above matched.
  - SCDB's citation page renders by JavaScript, so it could not be checked.
- courtlistener.com/terms was blocked to the subagent but fetched directly for the check. Its text matches the Free Law Project wiki copy on all six quotes.
