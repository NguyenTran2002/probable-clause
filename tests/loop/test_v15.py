"""Contract v1.5's rulings (P4.6 to P4.10) as v2.0 carries them: the note cap; the composition's estimate only for
pricing, with no reserve to compare it with (P4.18); an out-of-scope "hello" accepted at once; the copy guard's corpus
exemption (P4.9) and P4.13's skip reason, now in submit_update; and a composition attempt broken before its first
block counted as streamed, so its retry still runs (P4.10). v2.0 removes rule 4 (P4.7's waiver with it) and the
copy guard on research's note (P4.8). Every web page here is synthetic, on example.test."""

import json
import logging
import math

import pytest

from api import settings
from api.checks import copy_guard_report
from api.checks.update_findings import _words
from api.loop import format as fmt
from api.loop import prompts
from api.loop.prompts import rejection
from api.loop.run import _Run, chars_per_token, corpus_exemption, sort_documents
from api.loop.streamer import StreamFailed, raw_usage
from api.types import KeptPassage
from tests.loop.support import (WITHHELD, FakeCtx, cite_block, composition, loop_usage, make_deps, run_loop,
                                skip_update, tu, turn, update_usage, web_reply)

pytestmark = pytest.mark.anyio

NOTE_MAX = int(settings.NOTE_MAX_CHARS.value)
COPY_LEAD = ("In a ruling this week the court of appeals held that police must obtain a warrant before using a "
             "thermal imaging device to scan the exterior of a home from a public street.")
PAGE = COPY_LEAD + " Synthetic filler that stands in for the rest of a sample page, invented for this test."
COPIED = ("The court of appeals held that police must obtain a warrant before using a thermal imaging device to scan "
          "the exterior of a home from a public street.")
CLEAN_NOTE = ("The corpus holds the Supreme Court's Fourth Amendment opinions, and this question asks about "
              "something else.")
CLEAN_STATEMENT = "A sample page reports an appeals ruling on thermal scans of homes."
COPIED_SKIP = "No update check was needed here. " + COPIED
CLEAN_SKIP = "A newer ruling could not change what Katz held."
# P4.9: a sentence of Katz (katz-1-p6, the real corpus), which the synthetic page below quotes too
KATZ_Q = ("What a person knowingly exposes to the public, even in his own home or office, is not a subject of Fourth "
          "Amendment protection.")
PAGE_OWN = "Synthetic commentary follows it here, written for this test and found on no real page anywhere at all."


def page_reply(text=PAGE):
    return web_reply(("tr", "Thermal ruling", "2026-09-17", text))


def search():
    return turn(tu("search_exact", any_of=['"telephone booth"'], filters={"cases": ["katz"]}, max_results=2),
                tu("read_passages", target="katz-1-p6"), usage=loop_usage(1, first=True))


def keep(reason="Majority: people, not places."):
    return turn(tu("keep_passages", keep=[{"id": "katz-1-p6", "reason": reason}]), usage=loop_usage(2))


def submit(**kw):
    inp = {"out_of_scope": False}
    inp.update(kw)
    return turn(tu("submit_answer", **inp), usage=loop_usage(4))


def update_search():
    return turn(tu("search_web_updates", query="thermal imaging ruling", start_published_date="2026-06-30"),
                usage=update_usage(0))


def submit_update(**kw):
    return turn(tu("submit_update", **kw), usage=update_usage(1))


def answer(world):
    return [composition(cite_block("Text. ", world.corpus, ["katz-1-p6"], "katz-1-p6", 0, 0))]


def rules(ctx, name="submit_answer"):
    return [d["submit"].get("rule") for d in ctx.results(name)]


def submit_calls(ctx, name="submit_update"):
    return [d["input"] for d in ctx.of("tool_call") if d["name"] == name]


# ---------- P4.6: the note cap ----------

async def test_a_scope_note_over_the_cap_is_refused_then_one_at_the_cap_is_accepted(world):
    over, at = "n" * (NOTE_MAX + 1), "n" * NOTE_MAX
    ctx, fakes = await run_loop(world, [search(), keep(), submit(note=over), submit(note=at)],
                                update=[skip_update()], comp=answer(world))
    assert rules(ctx) == ["note_too_long", None]
    refused = ctx.results("submit_answer")[0]
    assert refused["is_error"] and refused["content"] == rejection("submit", "note_too_long", length=NOTE_MAX + 1)
    assert str(NOTE_MAX + 1) in refused["content"] and str(NOTE_MAX) in refused["content"]
    end = ctx.ended()
    assert end["state"] == "answered" and end["scope_note"] == at
    assert at in fakes["anthropic"].requests_for("composition")[0]["messages"][0]["content"][-1]["text"]


@pytest.mark.parametrize("case", ["out_of_scope", "nothing_found"])
async def test_the_cap_applies_to_a_no_sources_note(world, case):
    over = "A reply to the visitor. " * (NOTE_MAX // 20)
    assert len(over) > NOTE_MAX
    if case == "out_of_scope":
        script = [turn(tu("submit_answer", out_of_scope=True, note=over), usage=loop_usage(1, first=True)),
                  turn(tu("submit_answer", out_of_scope=True, note=CLEAN_NOTE), usage=loop_usage(2))]
        update = []
    else:
        script = [search(), submit(note=over), submit(note=CLEAN_NOTE)]
        update = [skip_update()]
    ctx, _ = await run_loop(world, script, update=update)
    assert rules(ctx) == ["note_too_long", None]
    end = ctx.ended()
    assert (end["state"], end["no_sources_reason"], end["note"]) == ("no_sources", case, CLEAN_NOTE)


async def test_the_cap_comes_after_rule_1_and_the_input_check_and_before_the_rest(world):
    long = "n" * (NOTE_MAX + 1)
    script = [
        turn(tu("read_passages", target="katz-1-p6"), tu("submit_answer", out_of_scope=False, note=long),
             usage=loop_usage(1, first=True)),                                                 # rule 1 first
        submit(note=long, update_findings=[{"statement": "x", "sources": []}]),                # then the input check
        submit(note=long),                                                                     # before rule 2
        search(), keep(), submit()]
    ctx, _ = await run_loop(world, script, update=[skip_update()], comp=answer(world))
    assert rules(ctx) == ["same_turn", None, "note_too_long", None]


# ---------- P4.18: no reserve; the composition's estimate only prices a failed attempt ----------

async def test_a_worst_case_composition_logs_no_error(world, caplog):
    """The KEEP_CAP largest documents with full keep reasons, a question and a scope note at their caps: the call
    runs, nothing is compared with a reserve (there is none, P4.18), and nothing is logged as an error."""
    reason = "r" * int(settings.KEEP_REASON_MAX_CHARS.value)
    corpus = world.corpus
    ctx = FakeCtx(question="q" * int(settings.QUESTION_MAX_CHARS.value))
    probe = _Run(ctx, make_deps(world, [])[0])
    size = {pid: probe.est_json(fmt.document_block(p, reason)) for pid, p in corpus.passages.items()}
    largest = sorted(size, key=lambda pid: (-size[pid], pid))[:int(settings.KEEP_CAP.value)]
    docs = sort_documents(largest, corpus)
    deps, fakes = make_deps(world, comp=[composition(cite_block("Text. ", corpus, docs, docs[0], 0, 0))])
    run = _Run(ctx, deps)
    for pid in largest:
        run.kept[pid] = KeptPassage(passage_id=pid, reason=reason, kept_at_round=1)
    caplog.set_level(logging.WARNING, logger="probable_clause.loop")
    comp = await run.compose("n" * NOTE_MAX)
    assert comp.outcome == "complete"
    request = fakes["anthropic"].requests_for("composition")[0]
    assert request["max_tokens"] == settings.COMPOSITION_MAX_TOKENS.value == 16_000
    assert [r.getMessage() for r in caplog.records
            if r.name.startswith("probable_clause") and r.levelno >= logging.WARNING] == []


def test_the_removed_settings_are_not_read():
    import api.loop.run as run_mod
    text = open(run_mod.__file__, encoding="utf-8").read()
    for name in ("COMPOSITION_RESERVE_INPUT", "RUN_INPUT_TOKENS", "RUN_OUTPUT_TOKENS", "FIXED_PREFIX_TOKENS_ESTIMATE"):
        assert name not in text and not hasattr(settings, name)


# ---------- P4.7 carried on: an out-of-scope "hello" is accepted at once, with no update check ----------

async def test_hello_out_of_scope_is_accepted_at_once_with_no_update_check(world):
    note = "Hello. I answer questions about the Supreme Court's Fourth Amendment opinions; ask me one."
    ctx, fakes = await run_loop(world, [turn(tu("submit_answer", out_of_scope=True, note=note),
                                             usage=loop_usage(1, first=True))], ctx=FakeCtx(question="hello"))
    assert rules(ctx) == [None]
    assert ctx.results("submit_answer")[0]["content"] == prompts.message("submit_accepted_note")
    assert not [g for g in ctx.gates if g[0] != "anthropic"] and fakes["exa"].calls == []
    assert [g for g in ctx.gates if g[1] != "loop"] == []
    band = ctx.of("update_band")[0]
    assert (band["outcome"], band["reason"], band["searches"], band["findings"]) == ("not_run", None, [], [])
    end = ctx.ended()
    assert (end["state"], end["no_sources_reason"], end["note"], end["answer_end"], end["rounds"]) == \
        ("no_sources", "out_of_scope", note, "none", 1)
    assert end["stop_kind"] is None and end["stop_kinds"] == [] and "composition_started" not in ctx.kinds()


# ---------- P4.13, now in submit_update: the skip reason, guarded on every submit once a page was returned ----------

async def test_a_skip_reason_that_repeats_a_page_is_refused_and_withheld(world):
    update = [update_search(), submit_update(update_skip_reason=COPIED_SKIP), submit_update(update_skip_reason=CLEAN_SKIP)]
    ctx, fakes = await run_loop(world, [search(), keep(), submit()], update=update, comp=answer(world),
                                exa=[page_reply()], page_texts=[COPY_LEAD, COPIED])
    assert rules(ctx, "submit_update") == ["copy_guard", None]
    refused = ctx.results("submit_update")[0]
    assert refused["content"] == rejection("submit_update", "copy_guard_skip_reason", pages="page web-1-1")
    first, second = submit_calls(ctx)
    assert first == {"update_skip_reason": WITHHELD} and second == {"update_skip_reason": CLEAN_SKIP}
    # a search ran, so the band is nothing_relevant: the skip reason only matters with no counted search (§6)
    assert ctx.of("update_band")[0]["outcome"] == "nothing_relevant"
    sent = [b for r in fakes["anthropic"].requests for m in r["messages"] if m["role"] == "assistant"
            for b in m["content"] if b.get("name") == "submit_update"]
    assert any(b["input"].get("update_skip_reason") == COPIED_SKIP for b in sent)       # Claude's own input kept
    assert COPIED not in json.dumps(ctx.events)


async def test_a_skip_reason_flagged_with_a_statement_gets_every_problem(world):
    update = [update_search(),
              submit_update(update_skip_reason=COPIED_SKIP,
                            update_findings=[{"statement": COPIED, "sources": ["web-1-1"]}],
                            update_overview="One sample page describes a ruling."),
              submit_update(update_findings=[{"statement": CLEAN_STATEMENT, "sources": ["web-1-1"]}],
                            update_skip_reason=CLEAN_SKIP)]
    ctx, _ = await run_loop(world, [search(), keep(), submit()], update=update, comp=answer(world),
                            exa=[page_reply()], page_texts=[COPY_LEAD, COPIED])
    assert rules(ctx, "submit_update") == ["copy_guard", None]
    report = copy_guard_report([COPIED], "One sample page describes a ruling.", {"web-1-1": PAGE},
                               int(settings.COPY_GUARD_WORDS.value), skip_reason=COPIED_SKIP)
    content = ctx.results("submit_update")[0]["content"]
    assert content == rejection("submit_update", "copy_guard", problems="\n".join(report.problems))
    assert "Statement 1" in content and "The update skip reason" in content
    shown = submit_calls(ctx)[0]
    assert shown["update_skip_reason"] == WITHHELD and shown["update_findings"][0]["statement"] == WITHHELD
    assert shown["update_overview"] == "One sample page describes a ruling."
    assert COPIED not in json.dumps(ctx.events)


async def test_research_s_note_is_never_guarded(world):
    """P4.19: research never sees a web page, so its note is stored as sent, even words a later page repeats."""
    scope = "This answer covers federal law only. " + COPIED
    update = [update_search(), submit_update(update_findings=[])]
    ctx, _ = await run_loop(world, [search(), keep(), submit(note=scope)], update=update, comp=answer(world),
                            exa=[page_reply()], check=False)
    assert submit_calls(ctx, "submit_answer")[0]["note"] == scope and ctx.ended()["scope_note"] == scope
    # the stream holds every other rule; only this artificial note, written before any page existed, repeats one
    from tests.loop.support import check_stream
    check_stream(ctx.events, world.corpus)


# ---------- P4.9: words that are also the corpus's ----------

def test_the_corpus_sentence_is_in_the_corpus_and_the_exemption_is_built_once(world, world_before_chatrie):
    assert KATZ_Q in world.corpus.passages["katz-1-p6"].text
    exempt = corpus_exemption(world.corpus)
    assert corpus_exemption(world.corpus) is exempt                     # once per corpus (a weak-keyed cache)
    assert tuple(_words(KATZ_Q)[:10]) in exempt and tuple(_words(PAGE_OWN)[:10]) not in exempt
    # built from the corpus it is given: a Chatrie run of words is in the full corpus's only
    chatrie = next(p for p in world.corpus.passages.values()
                   if p.case_key == "chatrie" and len(_words(p.text)) > 30 and p.kind == "paragraph")
    words = _words(chatrie.text)
    gram = next(tuple(words[i:i + 10]) for i in range(len(words) - 10)
                if tuple(words[i:i + 10]) not in corpus_exemption(world_before_chatrie.corpus))
    assert gram in exempt
    assert corpus_exemption(world_before_chatrie.corpus) is not exempt


# ---------- P4.10: a composition attempt broken before its first block ----------

BROKEN_BEFORE_FIRST_BLOCK = {
    "reported_and_streamed": lambda: StreamFailed("stream_broken", None, "x", raw_usage=raw_usage(9_000, output=1),
                                                  started=True, streamed_chars=6_000),
    "streamed_only": lambda: StreamFailed("stream_broken", None, "x", started=True, streamed_chars=6_000),
    "nothing_streamed": lambda: StreamFailed("overloaded", 529, "x"),
}


@pytest.mark.parametrize("case", list(BROKEN_BEFORE_FIRST_BLOCK))
async def test_a_composition_broken_before_its_first_block_is_retried_and_counted_as_streamed(world, case):
    big = composition(cite_block("The Court said the Amendment protects people. ", world.corpus, ["katz-1-p6"],
                                 "katz-1-p6", 4, 4), usage=raw_usage(9_000, output=8_000))
    ctx, fakes = await run_loop(world, [search(), keep(), submit()], update=[skip_update()],
                                comp=[BROKEN_BEFORE_FIRST_BLOCK[case](), big])
    comp = [x for x in ctx.paid if x["purpose"] == "composition"]
    assert [(x["attempt"], x["outcome"]) for x in comp] == [(1, "retrying"), (2, "ok")]
    failed = comp[0]
    expected = 0 if case == "nothing_streamed" else math.ceil(6_000 / chars_per_token(world.corpus))
    assert failed["estimated"] is True and failed["_usage"].output_tokens == expected
    assert failed["_usage"].output_tokens < int(settings.COMPOSITION_MAX_TOKENS.value)
    assert failed["usage"] is None and failed["estimated_usage"]["output_tokens"] == expected
    if case == "nothing_streamed":
        assert failed["_usage"].input_tokens > 0          # its input estimate
    # the retry runs with the composition's whole room
    reqs = fakes["anthropic"].requests_for("composition")
    assert len(reqs) == 2 and reqs[1]["max_tokens"] == int(settings.COMPOSITION_MAX_TOKENS.value)
    end = ctx.ended()
    assert (end["state"], end["answer_end"], end["failure_reason"], end["stop_kinds"]) == \
        ("answered", "complete", None, [])
