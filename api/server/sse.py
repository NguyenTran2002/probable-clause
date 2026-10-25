"""The event stream (contract §5, §6; T3.1): frames, the live stream from memory, and the replay from Atlas with
its `interrupted` ending.

A frame is `id: <n>`, `event: <kind>`, `data: <the JSON envelope on one line>`. The stream sends every event after
`Last-Event-ID`, a comment line every KEEPALIVE_S while it waits, and closes after `run_ended`.
"""

import asyncio
import json
from collections.abc import AsyncIterator
from datetime import datetime, timedelta

from api import settings
from api.server.clock import Clock, wait_event
from api.server.run import Run
from api.server.summary import answer_chars_of, rounds_of
from api.server.totals import totals_from_events
from api.state.clock import CHICAGO

KEEPALIVE = ": keep-alive\n\n"
SSE_HEADERS = {"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}   # T3.5: no buffering at the gateway
ENVELOPE_KEYS = ("v", "run", "n", "t_ms", "at", "kind", "data")


def frame(env: dict) -> str:
    text = json.dumps(env, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
    return f"id: {env['n']}\nevent: {env['kind']}\ndata: {text}\n\n"


def ascii_int(value: str | None, max_digits: int) -> int | None:
    """A non-negative integer written in ASCII digits only ("²" and "１２" are not numbers here), else None."""
    if value is None:
        return None
    v = value.strip()
    if not v or len(v) > max_digits or not (v.isascii() and v.isdigit()):
        return None
    return int(v)


def parse_last_event_id(value: str | None) -> int:
    """The last event the page holds; anything unreadable counts as none (the whole run is sent)."""
    n = ascii_int(value, 12)
    return 0 if n is None else n


async def live_stream(run: Run, token: int, last: int, clock: Clock,
                      closing: asyncio.Event | None = None) -> AsyncIterator[str]:
    """Events from memory after `last`, then each new one as it comes, until `run_ended` is sent, a newer stream
    replaces this one, the run finishes, or the instance shuts down (`closing`, contract v1.2)."""
    keepalive_s = float(settings.KEEPALIVE_S.value)
    sent = min(max(0, last), len(run.frames))
    while run.is_current_stream(token):
        if closing is not None and closing.is_set():
            return
        changed = run.changed                       # taken before reading the buffer, so no event is missed
        frames = run.frames
        if sent < len(frames):
            chunk = "".join(frames[sent:])
            sent = len(frames)
            yield chunk
            continue
        if run.ended or run.state in ("finished", "expired"):
            return
        if not await wait_event(changed, keepalive_s, clock):
            yield KEEPALIVE


def _envelope(e: dict) -> dict:
    return {k: e[k] for k in ENVELOPE_KEYS}


def interrupted_event(stored: list[dict], n: int, clock: Clock) -> dict:
    """H's `run_ended` with state `interrupted` (contract §4.H): sent on the stream only, never stored. Its totals
    are summed from the stored `paid_call` events; `t_ms` counts from the run's start, read off the first event."""
    first = stored[0]
    start = datetime.fromisoformat(first["at"]) - timedelta(milliseconds=first["t_ms"])
    now = clock.now().astimezone(CHICAGO)
    t_ms = max(stored[-1]["t_ms"], int((now - start).total_seconds() * 1000))
    return {"v": 1, "run": first["run"], "n": n, "t_ms": t_ms, "at": now.isoformat(timespec="milliseconds"),
            "kind": "run_ended",
            "data": {"state": "interrupted", "stop_kind": None, "stop_kinds": [], "no_sources_reason": None, "note": None,
                     "scope_note": None, "answer_end": "none", "failure_reason": None,
                     "rounds": rounds_of(stored), "answer_chars": answer_chars_of(stored),
                     "totals": totals_from_events(stored).as_dict()}}


def stored_frames(stored: list[dict], last: int, clock: Clock) -> list[str]:
    """A run this instance does not hold, from Atlas (T3.1, contract v1.2): the stored events after `last` while
    their numbers run on without a gap. If that reaches a stored `run_ended`, nothing more; otherwise the
    `interrupted` ending, numbered one more than the larger of the last stored event and `last`, so the page always
    receives an end."""
    events = sorted((_envelope(e) for e in stored), key=lambda e: e["n"])
    if not events:
        return []
    by_n = {e["n"]: e for e in events}
    ends = [e["n"] for e in events if e["kind"] == "run_ended"]
    if ends and last >= ends[0]:
        return []                                  # the page already has the run's end
    out = []
    n = last + 1
    while n in by_n:
        out.append(frame(by_n[n]))
        if by_n[n]["kind"] == "run_ended":
            return out
        n += 1
    out.append(frame(interrupted_event(events, max(events[-1]["n"], last) + 1, clock)))
    return out


async def replay_stream(frames: list[str]) -> AsyncIterator[str]:
    if frames:
        yield "".join(frames)
