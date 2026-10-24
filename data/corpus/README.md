# Probable Clause corpus

The cleaned text of 32 U.S. Supreme Court cases on surveillance technology and the Fourth Amendment (102 opinions), frozen at the end of Phase 1 (locked decisions P1.9 to P1.22). One JSON file per case in `cases/`; `manifest.json` lists every case and opinion with its citation, decision date, opinion type, author, joiners, coverage dates and token counts.

This text is unofficial. It was normalised from the sources below and checked against the official printed pages, but only the U.S. Reports are authoritative.

## Sources and attribution

Judicial opinions are in the public domain. The sources, with thanks:

- **CourtListener, a project of Free Law Project** (courtlistener.com): the text of 25 cases (their Lawbox copies), case metadata, and the independent Harvard Caselaw Access Project scan used to check wording and page numbers. Cases: *Berger*, *Boyd*, *Ciraolo*, *Clinton*, *Dow*, *Dunn*, *Ex parte Jackson*, *Florida v. Riley*, *Goldman*, *Greenwood*, *Hester*, *Jacobsen*, *Karo*, *Katz*, *Knotts*, *Lee*, *Lopez*, *Miller*, *Oliver*, *Olmstead*, *On Lee*, *Shultz*, *Silverman*, *Smith*, *White*.
- **GovInfo, U.S. Government Publishing Office** (govinfo.gov): the official U.S. Reports. These supply the text of 6 cases (*Carpenter*, *Grady*, *Jardines*, *Jones*, *Kyllo*, *Riley*), the page breaks of every case, and the pages that every check was made against.
- **Supreme Court of the United States** (supremecourt.gov): the slip opinion of *Chatrie* (2026), the source of its text and pages. A slip opinion is subject to formal revision before publication in the U.S. Reports.

## What was changed

Cleaning removed HTML, page numbers, running heads and footnote markers (recording their positions), rejoined words broken across lines, restored letters a PDF font dropped, and normalised whitespace. Quotation marks are straight throughout (P1.17). The syllabus, counsel listings and the Reporter's lineup are not included (P1.13). Beyond that, the only changes to the source words are the entries of `scripts/corrections.json`, each confirmed by a verification agent against the page image (P1.21); each case's `cleaning` record lists what was applied. The pipeline that builds this folder is in `scripts/` (see `CLAUDE.md`).
