"""What a run record and a stop detail may hold (T3.7; contract §8). Allowlists: anything not listed is refused.

The run record, `runs` collection, no expiry. Written by H at the end of a run through `Store.upsert_run_record`,
replacing any earlier record of the same `run`. It never holds the question, Claude's queries, the answer, a
note, or any page text. Only the keys below are accepted, at every depth (names are case-sensitive); every key
but `run` is optional. Strings are accepted only as the run ID, an ISO date or time, or a value of a fixed enum.

    `run`              run ID, 1 to 128 characters of A-Z a-z 0-9 _ -        (required)
    `started_date`     Chicago start date, "YYYY-MM-DD"
    `started_time`     Chicago start time, "HH:MM:SS"
    `state`            the end state: one of `RUN_STATES` (the events schema's run_ended.state)
    `stop_kind`        a `StopKind` or null
    `rounds`           integer >= 0
    `answer_chars`     integer >= 0
    `searches`         {`meaning`, `exact`, `web`}: integers >= 0
    `keeps`            integer >= 0
    `tokens`           Claude's tokens {`input`, `cache_read`, `cache_write`, `output`}: integers >= 0
    `cost_usd`         {`claude_loop`, `claude_composition`, `exa`, `voyage`}: numbers >= 0
    `calls`            billed attempts {`claude`, `exa`, `voyage`}: integers >= 0
    `retries`          {`claude`, `voyage`}: integers >= 0
    `checks`           counts {`quotations_checked`, `quotations_found`, `citations_checked`, `citations_found`,
                       `not_in_corpus`, `flags`}: integers >= 0
    `voyage_warning`   null, "degraded" or "unavailable"
    `corpus_label`     "full" or "before_chatrie"

A stop's `detail` (`Store.record_stop`) is a flat dict of at most 20 entries. Keys look like names (a lowercase
letter, then lowercase letters, digits and underscores, 40 characters at most). Values are numbers (finite),
booleans, or a string from `DETAIL_STRINGS` (stop kinds, run states, purposes, services, corpus labels,
Voyage-warning words). No null, list, nested dict or other string.

Error messages name the offending key path and never the value.
"""

import math
import re
from datetime import date
from typing import get_args

from api.protocols import StopKind

RUN_ID = re.compile(r"^[A-Za-z0-9_-]{1,128}$")   # becomes part of a dotted path in Atlas, so no "." or "$"
STOP_KINDS = frozenset(get_args(StopKind))

# The events schema's run_ended.state (contracts/events.schema.json).
RUN_STATES = ("answered", "no_sources", "step_limit", "token_ceiling", "time_limit", "error_stopped", "abandoned",
              "interrupted", "failed", "refusal", "spend_limit")

# A second check behind the allowlists: key names that could carry the question or the answer, in any case.
FORBIDDEN_KEYS = frozenset({"question", "answer", "answer_text", "answer_blocks", "queries", "query", "note", "scope_note",
                            "text", "q", "prompt", "content", "summary", "reason", "title", "statement", "message", "body"})

# The strings a stop detail may carry (T3.7): a fixed, small set of words, none of them free text.
DETAIL_STRINGS = frozenset(STOP_KINDS | set(RUN_STATES) | {
    "loop", "composition", "embed", "rerank", "update_search",       # purposes
    "anthropic", "exa", "voyage",                                    # services
    "full", "before_chatrie",                                        # corpus labels
    "degraded", "unavailable",                                       # Voyage-warning words
})
DETAIL_KEY = re.compile(r"^[a-z][a-z0-9_]{0,39}$")
DETAIL_MAX_KEYS = 20

_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_TIME = re.compile(r"^\d{2}:\d{2}:\d{2}$")


# --- the denylist (second check) --------------------------------------------------------------------------------------

def find_forbidden_keys(obj, path: str = "") -> list[str]:
    """Paths of keys that would hold the question or the answer (T3.7), at any depth, in any case."""
    found: list[str] = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            p = f"{path}.{k}" if path else str(k)
            if isinstance(k, str) and k.lower() in FORBIDDEN_KEYS:
                found.append(p)
            found.extend(find_forbidden_keys(v, p))
    elif isinstance(obj, (list, tuple)):
        for i, v in enumerate(obj):
            found.extend(find_forbidden_keys(v, f"{path}[{i}]"))
    return found


def check_no_text(obj, where: str) -> None:
    bad = find_forbidden_keys(obj)
    if bad:
        raise ValueError(f"a {where} never holds the question or the answer (T3.7); remove: {', '.join(_short(b) for b in bad)}")


# --- validators -------------------------------------------------------------------------------------------------------------

def _short(key) -> str:
    """A key as it may appear in a message: only if it looks like a name, so a key that is really text is not echoed."""
    text = key if isinstance(key, str) else ""
    return text if re.fullmatch(r"[A-Za-z0-9_]{1,40}", text) else "(a key that is not a name)"


def _int(v) -> bool:
    return isinstance(v, int) and not isinstance(v, bool) and 0 <= v < 2 ** 53


def _num(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) and v >= 0


def _enum(*values):
    allowed = frozenset(values)

    def check(v) -> bool:
        return (v is None or isinstance(v, str)) and v in allowed
    return check


def _run_id(v) -> bool:
    return isinstance(v, str) and bool(RUN_ID.match(v))


def _date_str(v) -> bool:
    if not isinstance(v, str) or not _DATE.match(v):
        return False
    try:
        date.fromisoformat(v)
    except ValueError:
        return False
    return True


def _time_str(v) -> bool:
    if not isinstance(v, str) or not _TIME.match(v):
        return False
    h, m, s = (int(x) for x in v.split(":"))
    return h < 24 and m < 60 and s < 60


def _counts(*keys: str) -> dict:
    return {k: _int for k in keys}


RUN_RECORD_SPEC = {
    "run": _run_id,
    "started_date": _date_str,
    "started_time": _time_str,
    "state": _enum(*RUN_STATES),
    "stop_kind": _enum(None, *STOP_KINDS),
    "rounds": _int,
    "answer_chars": _int,
    "searches": _counts("meaning", "exact", "web"),
    "keeps": _int,
    "tokens": _counts("input", "cache_read", "cache_write", "output"),
    "cost_usd": {k: _num for k in ("claude_loop", "claude_composition", "exa", "voyage")},
    "calls": _counts("claude", "exa", "voyage"),
    "retries": _counts("claude", "voyage"),
    "checks": _counts("quotations_checked", "quotations_found", "citations_checked", "citations_found", "not_in_corpus", "flags"),
    "voyage_warning": _enum(None, "degraded", "unavailable"),
    "corpus_label": _enum("full", "before_chatrie"),
}


def _walk(value, spec, path: str, problems: list[str]) -> None:
    if isinstance(spec, dict):
        if not isinstance(value, dict):
            problems.append(f"{path}: must be an object")
            return
        for k, v in value.items():
            if not isinstance(k, str) or k not in spec:
                problems.append(f"{path}.{_short(k)}: not an allowed key")
            else:
                _walk(v, spec[k], f"{path}.{k}", problems)
    elif not spec(value):
        problems.append(f"{path}: not an allowed value")


def check_run_record(record) -> str:
    """Refuse a run record that is not exactly the shape in this module's docstring; return its run ID.

    Raises ValueError naming the key paths at fault (never a value). The allowed shape is the module docstring.
    """
    if not isinstance(record, dict):
        raise ValueError("a run record is an object")
    problems: list[str] = []
    _walk(record, RUN_RECORD_SPEC, "run record", problems)
    if "run" not in record:
        problems.append("run record.run: required")
    if problems:
        raise ValueError("; ".join(problems[:8]))
    check_no_text(record, "run record")
    return record["run"]


def check_stop_detail(detail) -> dict:
    """Refuse a stop detail that is not a flat dict of names to numbers, booleans and `DETAIL_STRINGS` words."""
    if not isinstance(detail, dict):
        raise ValueError("a stop detail is an object")
    problems: list[str] = []
    if len(detail) > DETAIL_MAX_KEYS:
        problems.append(f"stop detail: at most {DETAIL_MAX_KEYS} entries")
    for k, v in detail.items():
        if not isinstance(k, str) or not DETAIL_KEY.match(k):
            problems.append(f"stop detail.{_short(k)}: a key is a lowercase name of at most 40 characters")
        elif isinstance(v, bool):
            pass
        elif isinstance(v, (int, float)):
            if not math.isfinite(v):
                problems.append(f"stop detail.{k}: a number must be finite")
        elif isinstance(v, str) and v in DETAIL_STRINGS:
            pass
        else:
            problems.append(f"stop detail.{k}: only numbers, booleans and the fixed enum words are allowed")
    if problems:
        raise ValueError("; ".join(problems[:8]))
    check_no_text(detail, "stop detail")
    return detail
