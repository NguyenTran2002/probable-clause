"""The streams this code emits, written in the replay format (contract §11.2) and held to the very tests the
frontend's fixtures pass (tests/contract/test_fixtures.py, as of contract v1.3), so the main session can regenerate
the fixtures from this code."""

import json

import pytest

from api import settings
from api.loop.streamer import StreamFailed
from api.state.prices import price_sources
from tests.contract import test_fixtures as contract
from tests.loop import test_run_answered as answered
from tests.loop.support import FakeCtx, cite_block, composition, loop_usage, run_loop, stop_on, tu, turn, web_reply

pytestmark = pytest.mark.anyio

SKIP = "The question asks what Katz held, so a search for later developments was not needed."
COPY_LEAD = ("In a ruling this week the court of appeals held that police must obtain a warrant before using a "
             "thermal imaging device to scan the exterior of a home from a public street.")
COPIED = ("The court of appeals held that police must obtain a warrant before using a thermal imaging device to scan "
          "the exterior of a home from a public street.")
PER_PATH = ["test_top_level_fields", "test_envelopes_and_order_rules", "test_tool_calls_precede_their_results",
            "test_passages_come_before_anything_naming_them", "test_fragments_and_paid_calls_are_ordered",
            "test_loop_fragments_point_at_what_was_sent_and_returned", "test_loop_usage_is_cold_then_cached",
            "test_answer_blocks_are_numbered_and_follow_composition", "test_totals_are_the_sum_of_the_paid_calls",
            "test_citations_are_exact_slices_of_their_passages",
            "test_checks_are_check_answer_run_on_the_streams_own_blocks", "test_web_pages_are_synthetic_and_carry_no_text",
            "test_the_band_matches_what_the_run_did", "test_run_ended_is_consistent",
            "test_refused_submits_withhold_flagged_statements", "test_warnings_come_once_each"]


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
    return composition(cite_block("The Court said the Amendment protects people. ", world.corpus, ["katz-1-p6"],
                                  "katz-1-p6", 4, 4), **kw)


def scenarios(world):
    page = ("tr", "Thermal ruling", "2026-09-17", COPY_LEAD + " Synthetic filler for a sample page, invented here.")
    return {
        "g-answered": (answered.script(world), [web_reply(("later", "Later ruling", "2026-09-12", answered.PAGE_TEXT))], {}),
        "g-out-of-scope": ([turn(tu("submit_answer", out_of_scope=True, note="Outside the corpus's subject.",
                                    update_skip_reason="Out of scope."), usage=loop_usage(0, first=True))], [], {}),
        "g-step-limit": ([turn(tu("read_passages", target=f"katz-1-p{i}"),
                               *([tu("keep_passages", keep=[{"id": "katz-1-p2", "reason": "r"}])] if i == 3 else []),
                               usage=loop_usage(i, first=i == 2)) for i in range(2, 14)]
                         + [composition(cite_block("Text. ", world.corpus, ["katz-1-p2"], "katz-1-p2", 0, 0))], [], {}),
        "g-copy-guard": ([*research(), turn(tu("search_web_updates", query="thermal", start_published_date="2026-06-30"),
                                            usage=loop_usage(3)),
                          submit(4, update_findings=[{"statement": COPIED, "sources": ["web-1-1"]}]),
                          submit(5, update_findings=[{"statement": "A sample page reports an appeals ruling.",
                                                      "sources": ["web-1-1"]}]), answer(world)], [web_reply(page)], {}),
        "g-incomplete": ([*research(), submit(3, update_skip_reason=SKIP),
                          composition(cite_block("First. ", world.corpus, ["katz-1-p6"], "katz-1-p6", 0, 0),
                                      cite_block("Second. ", world.corpus, ["katz-1-p6"], "katz-1-p6", 1, 1),
                                      break_after=1)], [], {}),
        "g-abandoned": ([*research()], [], {"stop": stop_on("loop", "abandoned", at=3)}),
        "g-spend-limit": ([*research(), StreamFailed("spend_limit", 400, "x")], [], {}),
        "g-error-stopped": ([*research(), *[StreamFailed("overloaded", 529, "x")] * 3, answer(world)], [], {}),
        "g-declined": ([*research(), submit(3), submit(4), answer(world)], [], {}),
        "g-unavailable": ([*research(), submit(3), answer(world)], [], {"update_check_available": False}),
        "g-findings-withheld": ([*research(), turn(tu("search_web_updates", query="thermal", start_published_date="2026-06-30"),
                                                   usage=loop_usage(3)),
                                 submit(4, update_findings=[{"statement": COPIED, "sources": ["web-1-1"]},
                                                            {"statement": "No source here.", "sources": []}]),
                                 submit(5, update_findings=[]), answer(world)], [web_reply(page)], {}),
        "g-step-limit-cut-off": ([turn(tu("read_passages", target=f"katz-1-p{i}"),
                                       *([tu("search_exact", any_of=["booth"], max_results=1),
                                          tu("keep_passages", keep=[{"id": "katz-1-p2", "reason": "r"}])] if i == 3 else []),
                                       usage=loop_usage(i, first=i == 2)) for i in range(2, 14)]
                                 + [composition(cite_block("Text. ", world.corpus, ["katz-1-p2"], "katz-1-p2", 0, 0),
                                                stop_reason="max_tokens", usage=__import__("api.loop.streamer", fromlist=["raw_usage"]).raw_usage(9_000, output=12_000))], [], {}),
        "g-error-incomplete": ([*research(), *[StreamFailed("overloaded", 529, "x")] * 3,
                                composition(cite_block("A. ", world.corpus, ["katz-1-p6"], "katz-1-p6", 0, 0),
                                            cite_block("B. ", world.corpus, ["katz-1-p6"], "katz-1-p6", 1, 1),
                                            break_after=1)], [], {}),
    }


async def test_streams_pass_the_fixture_rules(world, tmp_path):
    for slug, (script, exa, ctx_kw) in scenarios(world).items():
        ctx = FakeCtx(run_id=f"run-{slug}-0000000000", **ctx_kw)
        ctx, _ = await run_loop(world, script, ctx=ctx, exa=exa)
        doc = {"format": 1, "slug": slug, "question": ctx.question,
               "recorded_at": ctx._start.isoformat(timespec="seconds"), "commit": "fixture",
               "models": {"loop": settings.LOOP_MODEL.value, "composition": settings.COMPOSITION_MODEL.value},
               "prices": price_sources(), "corpus_label": ctx.corpus_label, "events": ctx.events}
        path = tmp_path / f"{slug}.json"
        path.write_text(json.dumps(doc, ensure_ascii=False))
        for name in PER_PATH:
            try:
                getattr(contract, name)(path)
            except pytest.skip.Exception:
                pass
            except AssertionError as e:
                raise AssertionError(f"{slug}: {name}: {e}") from e
