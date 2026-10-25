"""The streams this code emits, one per kind of run the fixtures cover (contract v2.0 §12), written in the replay
format (§11.2) and held to v2.0's schema and order rules, so the main session can regenerate the fixtures from this
code. (tests/contract/test_fixtures.py is still v1's until the main session's step 4; these streams are checked by
tests/loop/support.check_stream, which holds v2.0's rules.)"""

import json

import pytest

from api import settings
from api.loop.streamer import StreamFailed, raw_usage
from api.state.prices import price_sources
from tests.loop import test_run_answered as answered
from tests.loop.support import (FakeCtx, check_stream, cite_block, composition, loop_usage, run_loop, skip_update,
                                stop_on, tu, turn, update_usage, web_reply)

pytestmark = pytest.mark.anyio

SKIP = "The question asks what Katz held, so a search for later developments was not needed."
COPY_LEAD = ("In a ruling this week the court of appeals held that police must obtain a warrant before using a "
             "thermal imaging device to scan the exterior of a home from a public street.")
COPIED = ("The court of appeals held that police must obtain a warrant before using a thermal imaging device to scan "
          "the exterior of a home from a public street.")


def research():
    return [turn(tu("search_exact", any_of=['"telephone booth"'], filters={"cases": ["katz"]}, max_results=2),
                 tu("read_passages", target="katz-1-p6"), usage=loop_usage(1, first=True)),
            turn(tu("keep_passages", keep=[{"id": "katz-1-p6", "reason": "Majority (Stewart): people, not places."}]),
                 usage=loop_usage(2))]


def submit(n, **kw):
    inp = {"out_of_scope": False}
    inp.update(kw)
    return turn(tu("submit_answer", **inp), usage=loop_usage(n))


def answer(world, **kw):
    return [composition(cite_block("The Court said the Amendment protects people. ", world.corpus, ["katz-1-p6"],
                                   "katz-1-p6", 4, 4), **kw)]


def web(n=0):
    return turn(tu("search_web_updates", query="thermal", start_published_date="2026-06-30"), usage=update_usage(n))


def scenarios(world):
    """slug: (research, update, composition, Exa replies, FakeCtx's keywords)."""
    page = ("tr", "Thermal ruling", "2026-09-17", COPY_LEAD + " Synthetic filler for a sample page, invented here.")
    step_limit = [turn(tu("read_passages", target=f"katz-1-p{i}"),
                       *([tu("search_exact", any_of=["booth"], max_results=1),
                          tu("keep_passages", keep=[{"id": "katz-1-p2", "reason": "r"}])] if i == 3 else []),
                       usage=loop_usage(i, first=i == 2)) for i in range(2, 14)]
    p2 = [composition(cite_block("Text. ", world.corpus, ["katz-1-p2"], "katz-1-p2", 0, 0))]
    a = answered.scripts(world)
    return {
        "g-answered": (a["script"], a["update"], a["comp"],
                       [web_reply(("later", "Later ruling", "2026-09-12", answered.PAGE_TEXT))], {}),
        "g-skipped": ([*research(), submit(3)], [skip_update(SKIP)], answer(world), [], {}),
        "g-out-of-scope": ([turn(tu("submit_answer", out_of_scope=True, note="Outside the corpus's subject."),
                                 usage=loop_usage(0, first=True))], [], [], [], {}),
        "g-nothing-found": ([research()[0], submit(2, note="No passage bears on this question.")],
                            [web(0), turn(tu("submit_update", update_findings=[]), usage=update_usage(1))], [],
                            [web_reply(page)], {}),
        "g-step-limit": (step_limit, [], p2, [], {}),
        "g-copy-guard": ([*research(), submit(3)],
                         [web(0), turn(tu("submit_update", update_findings=[{"statement": COPIED, "sources": ["web-1-1"]}]),
                                       usage=update_usage(1)),
                          turn(tu("submit_update", update_findings=[{"statement": "A sample page reports an appeals "
                                                                                  "ruling.", "sources": ["web-1-1"]}]),
                               usage=update_usage(2))], answer(world), [web_reply(page)], {}),
        "g-wrong-step": ([research()[0], turn(tu("search_web_updates", query="later"), usage=loop_usage(2)),
                          research()[1], submit(4)],
                         [turn(tu("keep_passages", keep=[{"id": "katz-1-n9", "reason": "late"}]), usage=update_usage(0)),
                          skip_update(SKIP)], answer(world), [], {}),
        "g-incomplete": ([*research(), submit(3)], [skip_update(SKIP)],
                         [composition(cite_block("First. ", world.corpus, ["katz-1-p6"], "katz-1-p6", 0, 0),
                                      cite_block("Second. ", world.corpus, ["katz-1-p6"], "katz-1-p6", 1, 1),
                                      break_after=1)], [], {}),
        "g-abandoned": (research(), [], [], [], {"stop": stop_on("loop", "abandoned", at=3)}),
        "g-spend-limit": ([*research(), StreamFailed("spend_limit", 400, "x")], [], [], [], {}),
        "g-error-stopped": ([*research(), *[StreamFailed("overloaded", 529, "x")] * 3], [], answer(world), [], {}),
        "g-unavailable": ([*research(), submit(3)], [], answer(world), [], {"update_check_available": False}),
        "g-update-step-limit": ([*research(), submit(3)],
                                [turn(text="Weighing it.", stop_reason="end_turn", usage=update_usage(i))
                                 for i in range(int(settings.UPDATE_MAX_ROUNDS.value))], answer(world), [], {}),
        "g-update-failed": ([*research(), submit(3)], [StreamFailed("overloaded", 529, "x")] * 3, answer(world), [], {}),
        "g-update-spend-limit": ([*research(), submit(3)], [StreamFailed("spend_cap", 429, "x")], answer(world), [], {}),
        "g-step-limit-cut-off": (step_limit, [], [composition(cite_block("Text. ", world.corpus, ["katz-1-p2"],
                                                                          "katz-1-p2", 0, 0), stop_reason="max_tokens",
                                                               usage=raw_usage(9_000, output=16_000))], [], {}),
        "g-error-incomplete": ([*research(), *[StreamFailed("overloaded", 529, "x")] * 3], [],
                               [composition(cite_block("A. ", world.corpus, ["katz-1-p6"], "katz-1-p6", 0, 0),
                                            cite_block("B. ", world.corpus, ["katz-1-p6"], "katz-1-p6", 1, 1),
                                            break_after=1)], [], {}),
    }


EXPECTED = {
    "g-answered": ("answered", "found"), "g-skipped": ("answered", "skipped"),
    "g-out-of-scope": ("no_sources", "not_run"), "g-nothing-found": ("no_sources", "nothing_relevant"),
    "g-step-limit": ("step_limit", "not_run"), "g-copy-guard": ("answered", "found"),
    "g-wrong-step": ("answered", "skipped"), "g-incomplete": ("answered", "skipped"),
    "g-abandoned": ("abandoned", "not_run"), "g-spend-limit": ("spend_limit", "not_run"),
    "g-error-stopped": ("error_stopped", "not_run"), "g-unavailable": ("answered", "unavailable"),
    "g-update-step-limit": ("answered", "unavailable"), "g-update-failed": ("answered", "unavailable"),
    "g-update-spend-limit": ("answered", "unavailable"), "g-step-limit-cut-off": ("step_limit", "not_run"),
    "g-error-incomplete": ("error_stopped", "not_run"),
}


async def test_streams_pass_the_v2_rules_in_the_replay_format(world, tmp_path):
    outcomes = set()
    for slug, (script, update, comp, exa, ctx_kw) in scenarios(world).items():
        ctx = FakeCtx(run_id=f"run-{slug}-0000000000", **ctx_kw)
        ctx, _ = await run_loop(world, script, update=update, comp=comp, ctx=ctx, exa=exa)
        doc = {"format": 1, "slug": slug, "question": ctx.question,
               "recorded_at": ctx._start.isoformat(timespec="seconds"), "commit": "fixture",
               "models": {"loop": settings.LOOP_MODEL.value, "update": settings.UPDATE_MODEL.value,
                          "composition": settings.COMPOSITION_MODEL.value},
               "prices": price_sources(), "corpus_label": ctx.corpus_label, "events": ctx.events}
        path = tmp_path / f"{slug}.json"
        path.write_text(json.dumps(doc, ensure_ascii=False))
        events = json.loads(path.read_text())["events"]
        try:
            check_stream(events, world.corpus, page_texts=[COPY_LEAD, COPIED, answered.PAGE_TEXT[:80]])
        except AssertionError as e:
            raise AssertionError(f"{slug}: {e}") from e
        state = events[-1]["data"]["state"]
        band = next(e["data"]["outcome"] for e in events if e["kind"] == "update_band")
        assert (state, band) == EXPECTED[slug], slug
        outcomes.add(band)
    # every outcome but not_summarised is among these; not_summarised is in test_update_step's limit tests
    assert outcomes == {"found", "nothing_relevant", "skipped", "unavailable", "not_run"}
