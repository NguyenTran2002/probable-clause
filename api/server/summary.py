"""What H derives from a run's events: the counts of `run_ended` and the per-run record (T3.7; contract §8).

The record has the shape of `api/state/records.py`'s docstring and never holds the question, a query,
the answer, a note or any page text: every value below is a count, a sum, an enum word or a date.

v2.0 adds the update step's cost (`cost_usd.claude_update`) and, when an `update_ended` was emitted, its `update_rounds`
and `update_end`; E's allowlist (`records.py`) accepts them.
"""

from datetime import datetime

from api.server.totals import Totals
from api.state.clock import chicago_day, chicago_time


def _data(e: dict) -> dict:
    return e.get("data") or {}


def rounds_of(events: list[dict]) -> int:
    """Research's rounds: the `round_started` events with `step: research` (contract §4.H, v2.0). The update step's
    rounds come from its `update_ended`. An event with no step is research's, as every v1 recording is."""
    return sum(1 for e in events if e.get("kind") == "round_started" and _data(e).get("step", "research") == "research")


def answer_chars_of(events: list[dict]) -> int:
    return sum(len(_data(e).get("text") or "") for e in events if e.get("kind") == "answer_block")


def _int(v) -> int | None:
    return v if isinstance(v, int) and not isinstance(v, bool) and v >= 0 else None


def update_ended_of(events: list[dict]) -> dict | None:
    """The data of the update step's `update_ended`, if one was emitted (the last, should there be more)."""
    found = [_data(e) for e in events if e.get("kind") == "update_ended"]
    return found[-1] if found else None


def update_stop_kind_of(events: list[dict]) -> str | None:
    d = update_ended_of(events)
    return d.get("stop_kind") if d and isinstance(d.get("stop_kind"), str) else None


def _wrong_step_ids(events: list[dict]) -> set[str]:
    """The `tool_use_id`s of calls a step refused for being the other step's tools: never counted (contract §4.H)."""
    return {_data(e).get("tool_use_id") for e in events
            if e.get("kind") == "tool_result" and _data(e).get("wrong_step") is True}


def _tool_calls(events: list[dict], name: str) -> int:
    wrong = _wrong_step_ids(events)
    return sum(1 for e in events if e.get("kind") == "tool_call" and _data(e).get("name") == name
               and _data(e).get("tool_use_id") not in wrong)


def update_searches_of(events: list[dict]) -> int:
    """The update searches that were counted: the `tool_result`s carrying `search_no` (contract §4.H, v2.0)."""
    return sum(1 for e in events if e.get("kind") == "tool_result" and _int(_data(e).get("search_no")) is not None
               and _data(e).get("wrong_step") is not True)


def _retries(events: list[dict], service: str) -> int:
    return sum(1 for e in events if e.get("kind") == "paid_call"
               and _data(e).get("service") == service and _data(e).get("outcome") == "retrying")


def _keeps(events: list[dict]) -> int:
    counts = [_int(_data(e).get("kept_count")) for e in events
              if e.get("kind") == "tool_result" and _data(e).get("name") == "keep_passages"
              and _data(e).get("wrong_step") is not True]
    counts = [c for c in counts if c is not None]
    return counts[-1] if counts else 0


def _voyage_warning(events: list[dict]) -> str | None:
    codes = {_data(e).get("code") for e in events if e.get("kind") == "warning"}
    if "meaning_search_unavailable" in codes:          # the more severe of the two, when both were shown
        return "unavailable"
    if "meaning_search_degraded" in codes:
        return "degraded"
    return None


def _checks(events: list[dict]) -> dict | None:
    found = [_data(e) for e in events if e.get("kind") == "checks"]
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
                     "web": update_searches_of(events)},
        "keeps": _keeps(events),
        "tokens": {"input": t.input_tokens, "cache_read": t.cache_read, "cache_write": t.cache_write,
                   "output": t.output_tokens},
        "cost_usd": {"claude_loop": round(t.cost["loop"], 10), "claude_update": round(t.cost["update"], 10),
                     "claude_composition": round(t.cost["composition"], 10), "exa": round(t.exa_cost, 10),
                     "voyage": round(t.voyage_cost, 10)},
        "calls": {"claude": t.claude_calls, "exa": t.exa_searches, "voyage": t.voyage_requests},
        "retries": {"claude": _retries(events, "anthropic"), "voyage": _retries(events, "voyage")},
        "voyage_warning": _voyage_warning(events),
        "corpus_label": corpus_label,
    }
    ended = update_ended_of(events)
    if ended is not None:                  # only when an update_ended was emitted (contract §4.H, v2.0)
        record["update_rounds"] = _int(ended.get("rounds")) or 0
        record["update_end"] = ended.get("end") if isinstance(ended.get("end"), str) else None
    elif any(e.get("kind") == "update_started" for e in events):
        # the update step began and never reported its end (cancelled, failed, interrupted): its end is unknown
        record["update_rounds"] = sum(1 for e in events if e.get("kind") == "round_started"
                                      and _data(e).get("step") == "update")
        record["update_end"] = None
    if started is not None:
        record["started_date"] = chicago_day(started)
        record["started_time"] = chicago_time(started)
    checks = _checks(events)
    if checks is not None:
        record["checks"] = checks
    return record

