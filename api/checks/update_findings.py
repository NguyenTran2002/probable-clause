"""The update band's checks on Claude's structured findings (T2.3 items 2 and 3, P4.3).

Every returned string is written to Claude and stored in events. A message names a statement by its number
(from 1, in the order Claude wrote them) and a page by its ID, and never quotes a page or a statement.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field

from api.settings import (UPDATE_FINDINGS_MAX, UPDATE_OVERVIEW_MAX_CHARS, UPDATE_SOURCES_PER_STATEMENT,
                          UPDATE_STATEMENT_MAX_CHARS)

_SOURCE_ID = re.compile(r"web-\d{1,3}-\d{1,3}", re.ASCII)
_WORD = re.compile(r"[^\W_]+")
_APOSTROPHE = re.compile(r"(?<=\w)['’](?=\w)")


def check_update_findings(findings: list[dict], overview: str | None, returned_ids: set[str],
                          searches_run: int) -> list[str]:
    """T2.3 item 2: an unknown source ID, a statement with no source, findings with no search run, and the caps.
    An empty list of findings is fine: it means nothing relevant was found."""
    problems: list[str] = []
    if findings is None:
        findings = []
    if not isinstance(findings, list):
        return ["update_findings must be a list of statements, each with its statement text and a list of sources."]
    if overview is not None and not isinstance(overview, str):
        problems.append("update_overview must be text.")
        overview = None
    no_search = searches_run <= 0
    if no_search and findings:
        problems.append("update_findings was given, but no update search ran in this run, so there is nothing for "
                        "findings to rest on. Run search_web_updates first, or leave update_findings and "
                        "update_overview out and give update_skip_reason.")
    if no_search and overview and overview.strip():
        problems.append("update_overview was given, but no update search ran in this run. Run search_web_updates "
                        "first, or leave update_overview out.")
    if len(findings) > UPDATE_FINDINGS_MAX.value:
        problems.append(f"update_findings has {len(findings)} statements; the most allowed is "
                        f"{UPDATE_FINDINGS_MAX.value}. Merge or drop some.")
    for n, finding in enumerate(findings, start=1):
        problems.extend(_check_finding(n, finding, returned_ids, no_search))
    if overview and len(overview) > UPDATE_OVERVIEW_MAX_CHARS.value:
        problems.append(f"update_overview is {len(overview)} characters long; the most allowed is "
                        f"{UPDATE_OVERVIEW_MAX_CHARS.value}. Shorten it.")
    return problems


def _check_finding(n: int, finding, returned_ids: set[str], no_search: bool) -> list[str]:
    if not isinstance(finding, Mapping):
        return [f"Statement {n} is not an object with a statement and a list of sources."]
    problems = []
    statement = finding.get("statement")
    if not isinstance(statement, str) or not statement.strip():
        problems.append(f"Statement {n} has no statement text.")
    elif len(statement) > UPDATE_STATEMENT_MAX_CHARS.value:
        problems.append(f"Statement {n} is {len(statement)} characters long; the most allowed is "
                        f"{UPDATE_STATEMENT_MAX_CHARS.value}. Shorten it.")
    sources = finding.get("sources")
    if sources is None:
        sources = []
    if not isinstance(sources, list):
        problems.append(f"Statement {n}: sources must be a list of source IDs.")
        return problems
    if not sources:
        problems.append(f"Statement {n} has no source. Give each statement at least one source ID "
                        f"(web-<search>-<n>) from a page an update search returned.")
        return problems
    if len(sources) > UPDATE_SOURCES_PER_STATEMENT.value:
        problems.append(f"Statement {n} lists {len(sources)} sources; the most allowed is "
                        f"{UPDATE_SOURCES_PER_STATEMENT.value}. Keep the ones that support it.")
    if any(not isinstance(s, str) for s in sources):
        problems.append(f"Statement {n} lists a source that is not a source ID string.")
    if not no_search:    # with no search run every ID is unknown; the first problem already says so
        unknown = []
        for s in sources:
            if isinstance(s, str) and s not in returned_ids and s not in unknown:
                unknown.append(s)
        shown = [s for s in unknown if _SOURCE_ID.fullmatch(s)]
        odd = len(unknown) - len(shown)     # never echo Claude's text back unless it has the shape of an ID
        if shown:
            problems.append(f"Statement {n} names {_list(shown)}, which no update search in this run returned. "
                            f"Use only the IDs of pages the searches returned.")
        if odd:
            problems.append(f"Statement {n} lists {odd} source{'s' if odd != 1 else ''} that "
                            f"{'are' if odd != 1 else 'is'} not of the form web-<search>-<n>. "
                            f"Use only the IDs of pages the searches returned.")
    return problems


def _list(items: list[str]) -> str:
    if len(items) == 1:
        return f"source {items[0]}"
    return "sources " + ", ".join(items[:-1]) + " and " + items[-1]


# --- the copy guard

@dataclass
class CopyGuardReport:
    """What the copy guard found, for the refusal (`problems`) and for P4.3 (which texts to withhold)."""
    problems: list[str] = field(default_factory=list)
    flagged_statements: set[int] = field(default_factory=set)    # 0-based indexes into the statements given
    overview_flagged: bool = False


def _words(text: str) -> list[str]:
    """Lower case, punctuation and spacing gone; an apostrophe inside a word joins it (T2.3 item 3)."""
    return _WORD.findall(_APOSTROPHE.sub("", text.lower()))


def _grams(words: list[str], n: int) -> set[tuple[str, ...]]:
    return {tuple(words[i:i + n]) for i in range(len(words) - n + 1)}


def copy_guard_report(statements: Sequence[str], overview: str | None, pages: Mapping[str, str],
                      n_words: int) -> CopyGuardReport:
    """T2.3 item 3: a statement or the overview that repeats `n_words` or more consecutive words of any returned
    page, ignoring case, punctuation and spacing. `pages` maps a page ID to its text. Statements are numbered
    from 1 in the messages; `flagged_statements` holds 0-based indexes."""
    if n_words < 1:
        raise ValueError("n_words must be at least 1")
    if not isinstance(pages, Mapping):
        pages = {f"#{i}": t for i, t in enumerate(pages, start=1)}
    page_grams = {pid: _grams(_words(text if isinstance(text, str) else ""), n_words) for pid, text in pages.items()}
    report = CopyGuardReport()

    def copied_from(text: str) -> list[str]:
        grams = _grams(_words(text if isinstance(text, str) else ""), n_words)
        return [pid for pid, g in page_grams.items() if grams & g] if grams else []

    for index, statement in enumerate(statements):
        ids = copied_from(statement)
        if ids:
            report.flagged_statements.add(index)
            report.problems.append(_message(f"Statement {index + 1}", ids, n_words))
    if overview:
        ids = copied_from(overview)
        if ids:
            report.overview_flagged = True
            report.problems.append(_message("The overview", ids, n_words))
    return report


def _message(who: str, ids: list[str], n_words: int) -> str:
    pages = f"page {ids[0]}" if len(ids) == 1 else "pages " + ", ".join(ids[:-1]) + " and " + ids[-1]
    return (f"{who} repeats {n_words} or more consecutive words of {pages}. Paraphrase it in your own words, "
            f"attributed to its source, and submit again.")


def copy_guard(texts: list[str], page_texts: list[str], n_words: int) -> list[str]:
    """The binding signature (contract §4.F). `texts` are statements, numbered from 1. It cannot say which text is
    the overview or name a page by its real ID, so pages are named by position ("page #2"); `copy_guard_report` is
    what G calls: it takes the overview and a page-ID mapping and says which texts were flagged."""
    pages = {f"#{i}": t for i, t in enumerate(page_texts, start=1)}
    return copy_guard_report(texts, None, pages, n_words).problems
