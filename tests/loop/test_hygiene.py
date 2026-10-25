"""What leaves the loop besides events: logs hold no question, query, answer or page text (T3.7); F's checks run off
the event loop and their flags reach the checks event (T1.12)."""

import logging

import pytest

from tests.loop import test_run_answered as answered
from tests.loop.support import composition, loop_usage, run_loop, tu, turn, web_reply

pytestmark = pytest.mark.anyio


async def test_logs_hold_no_question_query_answer_or_page_text(world, caplog):
    caplog.set_level(logging.DEBUG)
    ctx, _ = await run_loop(world, answered.script(world),
                            exa=[web_reply(("later", "Later ruling", "2026-09-12", answered.PAGE_TEXT))])
    logs = "\n".join(r.getMessage() for r in caplog.records)
    assert ctx.ended()["state"] == "answered"
    for secret in (ctx.question, "phone booth eavesdropping ruling", "telephone booth", answered.PAGE_TEXT[:40],
                   "protects people, not places", "A sample page reports", "Majority (Stewart)"):
        assert secret not in logs


async def test_checks_run_off_the_event_loop_and_flag(world, monkeypatch):
    import anyio
    calls = []
    real = anyio.to_thread.run_sync

    async def spy(fn, *args, **kw):
        calls.append(fn.__name__)
        return await real(fn, *args, **kw)

    monkeypatch.setattr("api.loop.run.anyio.to_thread.run_sync", spy)
    p = world.corpus.passages["katz-1-p6"]
    script = [turn(tu("read_passages", target="katz-1-p6"), tu("search_exact", any_of=["booth"], max_results=1),
                   usage=loop_usage(1, first=True)),
              turn(tu("keep_passages", keep=[{"id": "katz-1-p6", "reason": "r"}])),
              turn(tu("submit_answer", out_of_scope=False, update_skip_reason="Not needed.")),
              composition({"type": "text", "text": 'The Court wrote that "the Fourth Amendment protects homes, not '
                                                   'places." Compare Entick v. Carrington.'})]
    ctx, _ = await run_loop(world, script)
    assert calls == ["check_answer"]
    checks = ctx.of("checks")[0]
    assert {f["kind"] for f in checks["flags"]} == {"quotation_not_found", "not_in_corpus"}
    assert checks["not_in_corpus"] == ["Entick v. Carrington"]
