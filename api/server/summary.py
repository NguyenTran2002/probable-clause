"""What H derives from a run's events: the counts of `run_ended` and the per-run record (T3.7; contract §8).

The record has exactly the shape of `api/state/records.py`'s docstring and never holds the question, a query,
the answer, a note or any page text: every value below is a count, a sum, an enum word or a date.
"""

from datetime import datetime

from api.server.totals import Totals
from api.state.clock import chicago_day, chicago_time


def rounds_of(events: list[dict]) -> int:
    return sum(1 for e in events if e.get("kind") == "round_started")


def answer_chars_of(events: list[dict]) -> int:
    return sum(len((e.get("data") or {}).get("text") or "") for e in events if e.get("kind") == "answer_block")


def _tool_calls(events: list[dict], name: str) -> int:
    return sum(1 for e in events if e.get("kind") == "tool_call" and (e.get("data") or {}).get("name") == name)


def _retries(events: list[dict], service: str) -> int:
    return sum(1 for e in events if e.get("kind") == "paid_call"
               and (e.get("data") or {}).get("service") == service and (e.get("data") or {}).get("outcome") == "retrying")


def _keeps(events: list[dict]) -> int:
    counts = [(e.get("data") or {}).get("kept_count") for e in events
              if e.get("kind") == "tool_result" and (e.get("data") or {}).get("name") == "keep_passages"]
    counts = [c for c in counts if isinstance(c, int) and not isinstance(c, bool) and c >= 0]
    return counts[-1] if counts else 0


def _voyage_warning(events: list[dict]) -> str | None:
    codes = {(e.get("data") or {}).get("code") for e in events if e.get("kind") == "warning"}
    if "meaning_search_unavailable" in codes:          # the more severe of the two, when both were shown
        return "unavailable"
    if "meaning_search_degraded" in codes:
        return "degraded"
    return None


def _checks(events: list[dict]) -> dict | None:
    found = [e.get("data") or {} for e in events if e.get("kind") == "checks"]
    if not found:
        return None
    c = found[-1]
    n = lambda k: c.get(k) if isinstance(c.get(k), int) and not isinstance(c.get(k), bool) and c.get(k) >= 0 else 0  # noqa: E731
    return {"quotations_checked": n("quotations_checked"), "quotations_found": n("quotations_found"),
            "citations_checked": n("citations_checked"), "citations_found": n("citations_found"),
            "not_in_corpus": len(c.get("not_in_corpus") or []), "flags": len(c.get("flags") or [])}


def run_record(run_id: str, started: datetime | None, state: str, stop_kind: str | None, events: list[dict],
               totals: Totals, corpus_label: str) -> dict:
    t = totals
    record = {
        "run": run_id,
        "state": state,
        "stop_kind": stop_kind,
        "rounds": rounds_of(events),
        "answer_chars": answer_chars_of(events),
        "searches": {"meaning": _tool_calls(events, "search_meaning"), "exact": _tool_calls(events, "search_exact"),
                     "web": _tool_calls(events, "search_web_updates")},
        "keeps": _keeps(events),
        "tokens": {"input": t.input_tokens, "cache_read": t.cache_read, "cache_write": t.cache_write,
                   "output": t.output_tokens},
        "cost_usd": {"claude_loop": round(t.cost["loop"], 10), "claude_composition": round(t.cost["composition"], 10),
                     "exa": round(t.exa_cost, 10), "voyage": round(t.voyage_cost, 10)},
        "calls": {"claude": t.claude_calls, "exa": t.exa_searches, "voyage": t.voyage_requests},
        "retries": {"claude": _retries(events, "anthropic"), "voyage": _retries(events, "voyage")},
        "voyage_warning": _voyage_warning(events),
        "corpus_label": corpus_label,
    }
    if started is not None:
        record["started_date"] = chicago_day(started)
        record["started_time"] = chicago_time(started)
    checks = _checks(events)
    if checks is not None:
        record["checks"] = checks
    return record
