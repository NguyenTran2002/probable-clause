"""What Claude sees of a passage, and what the events and the composition call carry (T1.6, T1.9, T1.11, §6.1).

Loop tool results are text blocks, one per passage, each starting with a header (T1.6): the passage ID, case,
citation, decision date, the opinion's ID and exact type, author, pages, section label and position. Joiners are in
the catalog, not the header (T1.6). Footnotes a paragraph cites are attached inside its block, each with its own ID.
The composition call gets custom content documents of our sentences (T1.9) with the metadata in `context`.
"""

from api.types import Filters, Passage

PER_CURIAM = "per curiam"


def authors_text(p: Passage) -> str:
    """The author line. "per curiam" only where the manifest says so (P1.18); an empty author list otherwise is
    shown as not given, never guessed."""
    if p.authors:
        return " and ".join(p.authors)
    return PER_CURIAM if p.joined_by_source == PER_CURIAM else "author not given"


def joiners_text(p: Passage) -> str:
    """The joiners, for the composition context. Where the manifest says "not printed", an empty list means the
    joiners are unknown, never that nobody joined (P1.18)."""
    if p.joined_by:
        return "joined by " + ", ".join(p.joined_by)
    if p.joined_by_source == PER_CURIAM:
        return PER_CURIAM
    if p.joined_by_source == "not printed":
        return "joiners not printed in the source (unknown)"
    return "joined by no one"


def pages_text(p: Passage) -> str:
    """U.S. Reports pages, or slip pages for a slip opinion (Chatrie), which restart in each opinion (contract §3)."""
    kind = "slip page" if p.slip_opinion else "page"
    if p.page_start == p.page_end:
        return f"{kind} {p.page_start}"
    return f"{kind}s {p.page_start}-{p.page_end}"


def section_text(p: Passage) -> str:
    return f"section {p.section}" if p.section else "before the first section heading"


def position_text(p: Passage) -> str:
    if p.kind == "paragraph":
        return f"paragraph {p.position} of {p.of}"
    cited = ", ".join(p.cited_by) if p.cited_by else "no paragraph"
    return f"footnote {p.footnote_label} (footnote {p.position} of {p.of} in this opinion), cited in {cited}"


def header(p: Passage, mark: str | None = None) -> str:
    lines = [
        f"[{p.id}] {p.case_name}, {p.citation}, decided {p.decided}",
        f"opinion {p.opinion_id}: {p.opinion_type} · {authors_text(p)} · {pages_text(p)} · {section_text(p)} · "
        f"{position_text(p)}",
    ]
    if mark:
        lines.append(mark)
    return "\n".join(lines)


def passage_block(corpus, pid: str, mark: str | None = None) -> str:
    """One passage as a loop tool result shows it: header, loop text with "[n. <label>]" markers, attached
    footnotes (T1.6)."""
    p = corpus.passages[pid]
    parts = [header(p, mark), corpus.loop_text(pid)]
    notes = corpus.attached_footnotes(pid)
    if notes:
        parts.append("Footnotes cited in this passage (each is its own passage, kept separately):\n"
                     + "\n".join(f"[{f.id}] n. {f.footnote_label}: {f.text}" for f in notes))
    return "\n\n".join(parts)


def matched_again_line(ids: list[str]) -> str:
    return "Matched again (shown earlier in this run, not sent again): " + ", ".join(ids) + "."


def no_match_text(f: Filters) -> str:
    """T1.4: no match returns "no passages matched" with the filters repeated."""
    return "No passages matched this search. " + filters_text(f)


def filters_text(f: Filters) -> str:
    parts = []
    if f.cases:
        parts.append("cases " + ", ".join(f.cases))
    if f.decided_from:
        parts.append(f"decided_from {f.decided_from}")
    if f.decided_to:
        parts.append(f"decided_to {f.decided_to}")
    if f.opinion_types:
        parts.append("opinion_types " + ", ".join(f.opinion_types))
    if f.authors:
        parts.append("authors " + ", ".join(f.authors))
    if f.none_of:
        parts.append("none_of " + ", ".join(f.none_of))
    if not f.include_footnotes:
        parts.append("include_footnotes false")
    return ("Filters set: " + "; ".join(parts) + ".") if parts else "Filters set: none."


def passage_event(p: Passage) -> dict:
    """The §6.1 passage event: the citable text, no markers, sentences as [[start, end], ...]."""
    return {
        "id": p.id, "kind": p.kind, "case_key": p.case_key, "case_name": p.case_name, "citation": p.citation,
        "decided": p.decided, "slip_opinion": p.slip_opinion, "opinion_id": p.opinion_id,
        "opinion_type": p.opinion_type, "authors": list(p.authors), "joined_by": list(p.joined_by),
        "joined_by_source": p.joined_by_source, "section": p.section, "page_start": p.page_start,
        "page_end": p.page_end, "paragraph_kind": p.paragraph_kind, "footnote_label": p.footnote_label,
        "footnotes": list(p.footnotes), "cited_by": list(p.cited_by), "text": p.text,
        "sentences": [[a, b] for a, b in p.sentences],
    }


# ---------- the composition call (T1.9, T1.11) ----------

def document_title(p: Passage) -> str:
    """A short label (T1.11), with the exact opinion type."""
    return f"{p.case_name} ({p.decided[:4]}), {authors_text(p)}, {p.opinion_type}"


def document_context(p: Passage, reason: str) -> str:
    """ID, citation, date, exact opinion type, author, joiners, section, pages and the keep reason (T1.11)."""
    return (f"ID {p.id} · {p.case_name}, {p.citation} · decided {p.decided} · opinion {p.opinion_id}: "
            f"{p.opinion_type} · {authors_text(p)} · {joiners_text(p)} · {section_text(p)} · {pages_text(p)} · "
            f"{position_text(p)}\n"
            f"Keep reason (the research step's note, not the Court's words): {reason}")


def document_block(p: Passage, reason: str) -> dict:
    """One custom content document: one text block per sentence of ours, used as-is, no further chunking (T1.9;
    https://platform.claude.com/docs/en/build-with-claude/citations, "custom content documents", read Oct 24, 2026)."""
    return {
        "type": "document",
        "source": {"type": "content", "content": [{"type": "text", "text": p.text[a:b]} for a, b in p.sentences]},
        "title": document_title(p),
        "context": document_context(p, reason),
        "citations": {"enabled": True},
    }
