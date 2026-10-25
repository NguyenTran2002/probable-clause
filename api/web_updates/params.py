"""The update check's search parameters (contract §4.D; T2.1).

`parse_params` validates what Claude sent to our wrapper tool and raises `ToolInputError` for anything wrong.
That refusal is ours: the search never reaches Exa and does not count toward the three (T2.4).
`to_exa_arguments` turns the validated fields into the arguments of Exa's `web_search_advanced_exa` tool.
"""

import re
import unicodedata
from dataclasses import dataclass
from datetime import date
from typing import Literal

from api import settings
from api.errors import ToolInputError

# Exa's tool argument names, as the live server lists them (data/verification/phase2/exa_tools_list.json,
# scripts/probe_exa.py; docs: https://exa.ai/docs/reference/search.md). Our wrapper's field -> Exa's argument.
EXA_ARGUMENT_NAMES = {
    "query": "query",
    "start_published_date": "startPublishedDate",
    "end_published_date": "endPublishedDate",
    "include_domains": "includeDomains",
    "exclude_domains": "excludeDomains",
    "category": "category",
    "type": "type",
    "num_results": "numResults",
}
EXA_TEXT_ARGUMENT = "textMaxCharacters"   # the one fixed setting sent explicitly (T2.2)

CATEGORIES = ("news", "publication")      # T2.1; the other categories are left out
TYPES = ("auto", "lite")                  # T2.1; fast, instant and the deep types are left out

FIELDS = tuple(EXA_ARGUMENT_NAMES)        # the wrapper's fields, in the contract's order


@dataclass(frozen=True)
class WebSearchParams:
    """Our wrapper's fields (T2.1), validated."""
    query: str
    start_published_date: str | None      # YYYY-MM-DD
    end_published_date: str | None
    include_domains: tuple[str, ...]      # <= EXA_DOMAINS_MAX; hostname, path prefix or "*.example.com"
    exclude_domains: tuple[str, ...]
    category: Literal["news", "publication"] | None
    type: Literal["auto", "lite"]         # default "auto"
    num_results: int                      # 1..10, default 10, clamped


_DATE = re.compile(r"\d{4}-\d{2}-\d{2}")
_LABEL = re.compile(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?")
_PATH = re.compile(r"/[A-Za-z0-9._~%!$&'()+,;=:@/-]*")
# Not a tuning figure: it only cuts a rejected value where an error message to Claude repeats it back, so a huge bad
# input cannot fill the message. It decides nothing about what is accepted or sent, so it is not in api/settings.py.
_SHOW_MAX = 60


def _show(v) -> str:
    s = repr(v)
    return s if len(s) <= _SHOW_MAX else s[:_SHOW_MAX] + "...'"


def _query(v, problems: list[str]) -> str:
    if not isinstance(v, str):
        problems.append("query is required and must be a text string")
        return ""
    text = "".join(" " if unicodedata.category(c) == "Cc" else c for c in v).strip()
    if not text:
        problems.append("query is required and must not be empty")
    return text


def _date(name: str, v, problems: list[str]) -> str | None:
    if v is None:
        return None
    hint = f"{name} must be a date written YYYY-MM-DD (for example 2026-06-29), or left out"
    if not isinstance(v, str) or not _DATE.fullmatch(v):
        problems.append(f"{hint}; got {_show(v)}")
        return None
    try:
        date.fromisoformat(v)
    except ValueError:
        problems.append(f"{hint}; {_show(v)} is not a real calendar date")
        return None
    return v


def _domain(entry) -> str | None:
    """The cleaned entry, or None when it is not a hostname, a hostname with a path prefix, or "*.hostname" (T2.1)."""
    if not isinstance(entry, str):
        return None
    entry = entry.strip()
    host, slash, path = entry.partition("/")
    if slash and not _PATH.fullmatch("/" + path):
        return None
    wildcard = host.startswith("*.")
    labels = (host[2:] if wildcard else host).lower().split(".")
    if wildcard and slash:
        return None                                   # a wildcard is a whole subdomain family, with no path
    if len(labels) < (1 if wildcard else 2) or len(".".join(labels)) > 253:
        return None
    if not all(_LABEL.fullmatch(label) for label in labels):
        return None
    return ("*." if wildcard else "") + ".".join(labels) + slash + path


def _domains(name: str, v, problems: list[str]) -> tuple[str, ...]:
    if v is None:
        return ()
    limit = int(settings.EXA_DOMAINS_MAX.value)
    if not isinstance(v, (list, tuple)):
        problems.append(f"{name} must be a list of domains, or left out")
        return ()
    if len(v) > limit:
        problems.append(f"{name} may hold at most {limit} entries; got {len(v)}")
        return ()
    out, bad = [], []
    for entry in v:
        cleaned = _domain(entry)
        if cleaned is None:
            bad.append(entry)
        else:
            out.append(cleaned)
    if bad:
        shown = ", ".join(_show(b) for b in bad[:3]) + (f" and {len(bad) - 3} more" if len(bad) > 3 else "")
        problems.append(
            f"{name} entries must each be a hostname (example.com), a hostname with a path prefix (example.com/news) "
            f"or a subdomain wildcard (*.example.com), in plain ASCII, with no https:// and no port or query; "
            f"not accepted: {shown}")
    return tuple(out)


def _choice(name: str, v, allowed: tuple[str, ...], default, note: str, problems: list[str]):
    if v is None:
        return default
    if not isinstance(v, str) or v not in allowed:
        problems.append(f"{name} must be one of {', '.join(allowed)}{' (' + note + ')' if note else ''}, or left out; got {_show(v)}")
        return default
    return v


def _num_results(v, problems: list[str]) -> int:
    default, cap = int(settings.EXA_NUM_RESULTS_DEFAULT.value), int(settings.MAX_RESULTS_CAP.value)
    if v is None:
        return default
    if isinstance(v, bool) or not isinstance(v, (int, float)) or v != v or v in (float("inf"), float("-inf")) or v != int(v):
        problems.append(f"num_results must be a whole number from 1 to {cap} (default {default}), or left out; got {_show(v)}")
        return default
    return max(1, min(cap, int(v)))   # clamped, not refused (T2.1)


def parse_params(raw: dict) -> WebSearchParams:
    """Validate Claude's input (T2.1). Raises ToolInputError naming every problem and the fix; never counted (T2.4)."""
    if not isinstance(raw, dict):
        raise ToolInputError(f"The search input must be an object with the fields: {', '.join(FIELDS)}.")
    problems: list[str] = []
    unknown = [k for k in raw if k not in EXA_ARGUMENT_NAMES]
    if unknown:
        problems.append(f"unknown field(s): {', '.join(_show(k) for k in unknown)}; the fields are {', '.join(FIELDS)}")
    query = _query(raw.get("query"), problems)
    start = _date("start_published_date", raw.get("start_published_date"), problems)
    end = _date("end_published_date", raw.get("end_published_date"), problems)
    if start and end and end < start:
        problems.append(f"end_published_date ({end}) must not be before start_published_date ({start})")
    include = _domains("include_domains", raw.get("include_domains"), problems)
    exclude = _domains("exclude_domains", raw.get("exclude_domains"), problems)
    category = _choice("category", raw.get("category"), CATEGORIES, None, "other categories are not offered", problems)
    kind = _choice("type", raw.get("type"), TYPES, "auto", "fast, instant and the deep types are not offered; lite is the cheap one", problems)
    num = _num_results(raw.get("num_results"), problems)
    if problems:
        raise ToolInputError("The search was not sent: " + "; ".join(problems) + ".")
    return WebSearchParams(query, start, end, include, exclude, category, kind, num)


def to_exa_arguments(p: WebSearchParams) -> dict:
    """Exa's tool arguments (T2.1, T2.2). Fixed settings are applied by omission: highlights, summaries, subpages,
    freshness and the rest are simply not requested. Only the text cap is sent explicitly."""
    args: dict = {"query": p.query, "type": p.type, "numResults": p.num_results,
                  EXA_TEXT_ARGUMENT: int(settings.EXA_TEXT_CHARS.value)}
    if p.start_published_date:
        args[EXA_ARGUMENT_NAMES["start_published_date"]] = p.start_published_date
    if p.end_published_date:
        args[EXA_ARGUMENT_NAMES["end_published_date"]] = p.end_published_date
    if p.include_domains:
        args[EXA_ARGUMENT_NAMES["include_domains"]] = list(p.include_domains)
    if p.exclude_domains:
        args[EXA_ARGUMENT_NAMES["exclude_domains"]] = list(p.exclude_domains)
    if p.category:
        args[EXA_ARGUMENT_NAMES["category"]] = p.category
    return args


def params_as_dict(p: WebSearchParams) -> dict:
    """Every wrapper field, unset ones null: the band's `params` (contract §6, T2.1, T5.3)."""
    return {
        "query": p.query,
        "start_published_date": p.start_published_date,
        "end_published_date": p.end_published_date,
        "include_domains": list(p.include_domains) or None,
        "exclude_domains": list(p.exclude_domains) or None,
        "category": p.category,
        "type": p.type,
        "num_results": p.num_results,
    }


def fixed_settings() -> dict:
    """Our fixed settings, for the band's `fixed` and the opening line of a result (T2.1, T2.2)."""
    return {"text_max_characters": int(settings.EXA_TEXT_CHARS.value), "highlights": False, "summaries": False}
