# Phase 1 handoff: finishing the corpus after verification round 2

*Historical. Every step below was carried out and Phase 1 was frozen on Oct 23, 2026 (BUILD_LOG.md; locked-decisions P1.22).*

*Written Oct 23, 2026, 20:13 CDT, by the main session, before a planned compaction. Read this in full before continuing Phase 1. It holds every open finding from verification rounds 1 and 2, so nothing depends on the conversation.*

The agents' full findings are on disk (gitignored): `data/verification/agents/batch1-10.json` and `r2_batch1-6.json`. The briefs are `BRIEF.md` and `BRIEF_ROUND2.md` in the same folder. Where this file names an offset or page, it was reported by an agent against the build of Oct 23 ~19:50; re-locate by the quoted text, not the offset.

## State of the code

Committed with this file, **untested**, as work in progress:
- `corpus_common.text_of`: every Windows-1252 byte decoded (0x9C "œ", 0x86 "†", not only 0x97); Lawbox's double-escaped `&amp;mdash` becomes a closed-up em dash.
- `build_corpus.lawbox_text`: Lawbox's closed "..." becomes ". . ."; a three-dot ellipsis attached to the word before it gets a space ("clear. . . that" → "clear . . . that"; four dots stay); a space after a removed footnote marker when the next word follows directly ('."Oliver' → '." Oliver').
- `build_corpus.refuse()` and `two_scan_refused`: filters on two-scan corrections (now moot, see step 1 below).
- `build_corpus.pages_from`: rewritten. It drops a far-jumping tail match, puts unmatched words at a page turn on the later page, and takes an optional `harvard` callback (not yet wired in).
- `corpus_pdf`: letter-spaced words split by the text layer are joined ("af ter" → "after"); Lawbox vocabulary from whole words only ("4th" no longer contributes "th"); no merging of a period word (keeps ". . . ”" spaced); "www." line-end join; ". . . —" keeps its space.
- `CORPUS_OUT` environment variable redirects the build's output (for testing without touching `data/corpus/`).

## Next steps, in order

1. **P1.21: make two-scan report-only.** In `two_scan_corrections`, log candidates to `cleaning.two_scan_candidates` and do not edit the text. Keep the refusal filters (they classify candidates).
2. **Move every agent-confirmed correction into `scripts/corrections.json`** (the list below). Add entry types the table lacks: `page_starts_at` (unique text where a page begins, and the page), `remove_break` (paragraph text plus page), `set_note` (case, opinion author, `joined_by_note` text). Every find must match exactly once; re-locate each by its text.
3. **Finish the generic fixes listed under "Code" below.** Test with `CORPUS_OUT=<scratch> uv run python scripts/build_corpus.py <keys>` first.
4. **Write the comma and period check.** In `verify_corpus.py` (or a new script), for Lawbox cases list every gap where the official text layer and Harvard agree on `, . ; :` and Lawbox differs. Output a report and change nothing.
5. **Rebuild everything:** `build_corpus.py`, `verify_corpus.py`, `verify_lineup.py`, `build_manifest.py`.
6. **Final agent pass (P1.1, P1.21).** A few Opus agents, each given a batch of cases and the reports. Their job:
   - confirm every table entry applied as intended
   - re-check every page break this file names
   - judge every item in the comma and period report
   - check a sample of paragraphs for anything the rebuild broke

   Fold in what they confirm through the table.
7. **Report to the user and get the corpus approved.** Then the freeze: decide with the user whether the cleaned text is committed (brief default 3), log, update CLAUDE.md, commit, tag `phase-1-done` (check `git status` for the frontend session's uncommitted `web/` work first, and ask).

## Code (generic fixes still to make)

- **Page alignment:**
  - Wire the `harvard` callback into `pages_from` for Lawbox body paragraphs, using Harvard's page markers for unmatched words at a page turn.
  - In `corpus_align.locate`, among well-supported forward candidates prefer the one nearest `near`. *Boyd* op0.p8 matched Miller's word-for-word copy of the same statute on pp. 639–640; it belongs on pp. 619–620, with the break before "business book".
  - For footnotes, try the marker's page alone first: if most words match there, the footnote is on that page with no break. Only otherwise use the page and the next.
- **PDF lines:** merge words at nearly the same height (|Δy| < 2) into one line. Justified lines with wide gaps split *Chatrie* op0.p12–p15 into four paragraphs, where print has one ("…latitude/longitude coordinate and corresponding timestamp; …").
- **PDF URLs:** join a line-end break after a period inside a URL. *Chatrie* has "https://services.google. com/…"; print has "https://services.google.com/fh/files/misc/supplemental_information_geofence_warrants_united_states.pdf".
- **PDF closing punctuation:** allow ")." and similar in the no-space rule. *Chatrie* has "(Kerr Brief )"; print has "(Kerr Brief)".
- **PDF hyphen evidence:** count a line's complete last word, unless it ends in a hyphen, and a line's first word, unless the line before ended in a hyphen. *Chatrie* has "by-product" where print has "byproduct", which is printed solid mid-line on PDF p. 70.
- **PDF nested quotes:** no space between an opening double quote and an opening single quote. *Carpenter* has `" '` 27 times.
- **Lawbox:**
  - "... ." becomes ". . . ." (*Boyd*: "description... ." → "description. . . .")
  - "1 ½" becomes "1½" (*Shultz* fn22: "1½ mills")
- **`argued_text`:** include "Reargued …" (*White*: "Reargued October 20, 1970") and "Submitted …" (*Hester*: "Submitted April 24, 1924").

## Corrections for the table (each confirmed by an agent against the page image)

Word corrections the two-scan check made correctly (they must now be table entries, since it no longer edits):
- **olmstead:**
  - "have to chose" → "have to choose" (p.470)
  - "in the future" → "in future" (p.470, op1.p0)
  - "a far slighter intrusions" → "a far slighter intrusion" (p.474)
  - "in order is to promote" → "in order to promote" (p.484)
  - "dilosures" → "dislosures" (fn11, p.478; the print's own misprint)
  - "§§ 2260, 2266" → "§§ 2260, 2262, 2266" (fn13, p.480)
- **lopez:**
  - "notwithstanding are the verdict" → "notwithstanding the verdict" (p.434)
  - "cats-paws" → "cat's-paws" (p.452)
  - "good behavior" → "good behaviour" (fn13, p.466)
  - "the waveforms forms for purposes" → "the waveforms for purposes" (fn17, p.469)
- **miller:**
  - "Couch v. United States. 400 U. S. 322" → "Couch v. United States, 409 U. S. 322" (p.442; volume and comma)
  - "(5the Cir. 1974)" → "(5th Cir. 1974)" (p.450)
  - "Kelly v. Johnson" → "Kelley v. Johnson" (p.455)
- **knotts:** "Hawkins Chemicals Co." → "Hawkins Chemical Co." (p.278, op0.p4)
- **smith:** "practical mater" → "practical matter" (p.750)
- **katz:**
  - "over-heard" → "overheard" (p.353)
  - "eaves-dropping" → "eavesdropping" (p.359, op1.p0)
- **white:**
  - "nothing" → "noting" (p.779; "and noting that '[f]ew threats to liberty")
  - "in the Federal Government. I am establishing" → "in the Federal Government, I am establishing" (Appendix II, p.768)
- **berger:**
  - "message" → "messages" (op0.p5, p.45)
  - "eaves-dropping" → "eavesdropping" (op3.p21, p.78)
  - "interest" → "interests" (op5.p5, p.109)
  - "wire-tapping" → "wiretapping" (op5.fn3, p.112)
- **jacobsen:**
  - "fork-lift" → "forklift" (op0.p1, p.111)
  - the inserted "the " at op0.p28, p.124 (print has "the the")
- **boyd:** "contemporanea" (op0.p13, p.622). The log shows Lawbox "contemporanea" changed to "contemporánea". The batch8 agent called this correction correct, and also said "the print has no accent". These conflict, so check the page image in the final pass and record the printed form.

Punctuation and other corrections:
- **berger:**
  - "set up as it was," → "set up, as it was,"
  - "by providing as the Court says," → "by providing, as the Court says,"
  - "and the public. Johnson v. United States" → "and the public, Johnson v. United States"
  - "First the Court intimates" → "First, the Court intimates"
  - 'effects." the words' → 'effects," the words'
  - "does not in so many words," → "does not, in so many words,"
  - "Jacob 'Gurrah' Shapiro. Joseph" → "Jacob 'Gurrah' Shapiro, Joseph"
  - "coordinate Federal. State," → "coordinate Federal, State,"
  - Pages: p.44 begins '"general searches"' (op0.p0); p.61 begins "(1959)." (op0.p30).
  - White's appendix (op5.p20 to p63, pp.119–129) → kind `appendix`.
- **ex_parte_jackson:**
  - "a law prohibiting under severe penalties" → "a law prohibiting, under severe penalties"
  - "through the mails. it could prevent" → "through the mails, it could prevent"
- **lee:** "the crime, a felony; was being committed" → "the crime, a felony, was being committed" (p.562)
- **karo:** "attache case" → "attaché case" (p.731)
- **shultz:**
  - "record-keeping" → "recordkeeping" (op0.p14, p.30; line-end break; solid about 60 times)
  - "the customer or both, S. Rep. No.91-1139" → "the customer, or both, S. Rep. No. 91-1139" (fn29, p.70)
  - Douglas's dissent: `joined_by_note`, Brennan joined Parts I and II-A (lineup; Brennan's opinion, p.91).
  - Unclear: "inspection . . . ." spacing at op0.p36.
- **boyd:**
  - "469-482: and see" → "469-482; and see" (footnote, p.625)
  - Missing caption on p.618 between op0.p4 and op0.p5: '"The United States of America against E. A. B., 1-35, Thirty-five Cases of Plate Glass.' Ask the user whether a quoted caption is included.
  - Miller's concurrence is printed "concurring", though he joins only in part. The corpus follows the heading.
- **dunn:** majority `joined_by_note`: Scalia joined "in all but the paragraph headed 'Third' in Part II".
- **olmstead pages:**
  - fn4 and fn6 → page 477
  - fn5 and fn8: remove the breaks to 478
  - fn13: break to 481 before "6308, 6309; Rhode Island"; fn13.2, fn13.3 and fn13.4 start on 481
  - fn13.2 "thereof,. . . the person" → "thereof, . . . the person"
- **goldman:** dissent fn4: remove the break to 140 (wholly on 139).
- **silverman:** op0.p7: page 509 begins '"still experimental' (break one word late).
- **knotts:**
  - op0.p27: remove the spurious 287 break ("…Hester v. United States, 265 U. S. 57 (1924)." is on p.285)
  - op0.p7: p.280 begins "(1981)."
- **smith:**
  - op2.p1: remove the 751 break ("(MARSHALL, J., dissenting)." is on p.749)
  - op2.p3: p.750 begins "(plurality"
- **lopez:**
  - op2.p0: p.447 begins at "equipped with a radio receiver"
  - op2.fn1: starts on p.448, with a break to 449 before "429 (1906); State v. Reyes"
  - op2.p35: p.468 begins '"bugging,"'
- **oliver:** op0.p13: p.178 begins "(1978) (POWELL, J., concurring)".
- **greenwood:** op1.p24: p.56 begins '"sanctity of [the] home'.
- **white:** op3.p9: remove the break to 759 before "Id., at 359." (p.759 begins "undercover agent").
- **katz:** fn17 and fn22: remove the spurious breaks (checked in round 1; re-check).

Two-scan corrections judged **wrong**, which must not reappear:
- olmstead "the"→"th"
- goldman "III"→"Ill"
- on_lee "Wire-Tapping"→"WireTapping"
- oliver "O."→"0." and the "&mdash" one
- dunn "in fields"→"infields"
- greenwood "A1"→"Al" (×2), "agreement"→"agree- ment", "attaché"→"atta-ch", "vis-à-vis"→"vis-a-vis"
- florida_v_riley "Amdt."→"Arndt.", "O'CONNOR"→"O'Con nor" (×2)
- smith "Amdt."→"Arndt."
- miller "relie[s]"→"reliefs]"
- katz "list"→"fist", Harlan fn* "I " deleted
- berger the two paragraph-opening "I " deletions
- boyd "Southern"→"South-em", "employés"→"employes", "subpœna"→"subpoena" (×3)
- shultz "'[S]tandards"→"'[Standards"

## Unresolvable from the print (line-end hyphen only; leave as built)

two-fold and oath-bound (olmstead), deep-seated (on_lee), peace-time (katz), counter-espionage (berger), prepaid (ex_parte_jackson), supersensitive (jardines), common-sense (carpenter).

## Open for the user

- *Boyd*'s quoted caption on p.618 (include or not).
- When Phase 1 ends: commit the cleaned corpus or not (brief default 3).
