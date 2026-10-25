"""Contract v1.5 (P4.6 to P4.10): the note cap and the composition's estimate as an error log; rule 4 waived for an
out-of-scope submit; the copy guard on a no-sources reply's note, with the note withheld; the corpus exemption; and a
composition attempt broken before its first block counted as streamed, so its retry still runs. Every web page here
is synthetic, on example.test."""

import json
import logging
import math

import pytest

from api import settings
from api.checks import copy_guard_report, pages_named
from api.checks.update_findings import _words
from api.loop import execute_run
from api.loop import format as fmt
from api.loop import prompts
from api.loop.prompts import rejection
from api.loop.run import _Run, band_outcome, chars_per_token, corpus_exemption, sort_documents, withhold_flagged
from api.loop.streamer import StreamFailed, raw_usage
from api.types import KeptPassage
from tests.loop.support import (WITHHELD, FakeCtx, cite_block, composition, loop_usage, make_deps, run_loop, tu, turn,
                                web_reply)

pytestmark = pytest.mark.anyio

NOTE_MAX = int(settings.NOTE_MAX_CHARS.value)
SKIP = "Not needed: the question asks what Katz held."
COPY_LEAD = ("In a ruling this week the court of appeals held that police must obtain a warrant before using a "
             "thermal imaging device to scan the exterior of a home from a public street.")
PAGE = COPY_LEAD + " Synthetic filler that stands in for the rest of a sample page, invented for this test."
COPIED = ("The court of appeals held that police must obtain a warrant before using a thermal imaging device to scan "
          "the exterior of a home from a public street.")
COPIED_NOTE = "I could not answer this from the corpus. " + COPIED
CLEAN_NOTE = ("The corpus holds the Supreme Court's Fourth Amendment opinions, and this question asks about "
              "something else.")
CLEAN_STATEMENT = "A sample page reports an appeals ruling on thermal scans of homes."

# P4.9: a sentence of Katz (katz-1-p6, the real corpus), which the synthetic page below quotes too
KATZ_Q = ("What a person knowingly exposes to the public, even in his own home or office, is not a subject of Fourth "
          "Amendment protection.")
PAGE_OWN = "Synthetic commentary follows it here, written for this test and found on no real page anywhere at all."
COURT_PAGE = "Commentators keep returning to the 1967 opinion, which said: " + KATZ_Q + " " + PAGE_OWN


def page_reply(text=PAGE):
    return web_reply(("tr", "Thermal ruling", "2026-09-17", text))


def search():
    return turn(tu("search_exact", any_of=['"telephone booth"'], filters={"cases": ["katz"]}, max_results=2),
                tu("read_passages", target="katz-1-p6"), usage=loop_usage(1, first=True))


def keep(reason="Majority: people, not places."):
    return turn(tu("keep_passages", keep=[{"id": "katz-1-p6", "reason": reason}]), usage=loop_usage(2))


def update():
    return turn(tu("search_web_updates", query="thermal imaging ruling", start_published_date="2026-06-30"),
                usage=loop_usage(3))


def keep_and_update():
    return turn(tu("keep_passages", keep=[{"id": "katz-1-p6", "reason": "Majority: people, not places."}]),
                tu("search_web_updates", query="thermal imaging ruling", start_published_date="2026-06-30"),
                usage=loop_usage(2))


def submit(**kw):
    inp = {"out_of_scope": False}
    inp.update(kw)
    return turn(tu("submit_answer", **inp), usage=loop_usage(4))


def answer(world):
    return composition(cite_block("Text. ", world.corpus, ["katz-1-p6"], "katz-1-p6", 0, 0))


def rules(ctx):
    return [d["submit"].get("rule") for d in ctx.results("submit_answer")]


def submit_calls(ctx):
    return [d["input"] for d in ctx.of("tool_call") if d["name"] == "submit_answer"]


# ---------- P4.6: the note cap ----------

async def test_a_scope_note_over_the_cap_is_refused_then_one_at_the_cap_is_accepted(world):
    over, at = "n" * (NOTE_MAX + 1), "n" * NOTE_MAX
    script = [search(), keep(), submit(note=over, update_skip_reason=SKIP), submit(note=at, update_skip_reason=SKIP),
              answer(world)]
    ctx, fakes = await run_loop(world, script)
    assert rules(ctx) == ["note_too_long", None]
    refused = ctx.results("submit_answer")[0]
    assert refused["is_error"] and refused["content"] == rejection("submit", "note_too_long", length=NOTE_MAX + 1)
    assert str(NOTE_MAX + 1) in refused["content"] and str(NOTE_MAX) in refused["content"]
    end = ctx.ended()
    assert end["state"] == "answered" and end["scope_note"] == at
    assert at in fakes["anthropic"].requests[-1]["messages"][0]["content"][-1]["text"]


@pytest.mark.parametrize("case", ["out_of_scope", "nothing_found"])
async def test_the_cap_applies_to_a_no_sources_note(world, case):
    over = "A reply to the visitor. " * (NOTE_MAX // 20)
    assert len(over) > NOTE_MAX
    if case == "out_of_scope":
        script = [turn(tu("submit_answer", out_of_scope=True, note=over), usage=loop_usage(1, first=True)),
                  turn(tu("submit_answer", out_of_scope=True, note=CLEAN_NOTE), usage=loop_usage(2))]
    else:
        script = [search(), submit(note=over, update_skip_reason=SKIP),
                  submit(note=CLEAN_NOTE, update_skip_reason=SKIP)]
    ctx, _ = await run_loop(world, script)
    assert rules(ctx) == ["note_too_long", None]
    end = ctx.ended()
    assert (end["state"], end["no_sources_reason"], end["note"]) == ("no_sources", case, CLEAN_NOTE)


async def test_the_cap_comes_after_rule_1_and_the_findings_checks_and_before_the_rest(world):
    long = "n" * (NOTE_MAX + 1)
    script = [
        turn(tu("read_passages", target="katz-1-p6"), tu("submit_answer", out_of_scope=False, note=long),
             usage=loop_usage(1, first=True)),                                                 # rule 1 first
        submit(note=long, update_findings=[{"statement": "x", "sources": []}]),                # then the findings
        submit(note=long),                                                                     # before rule 2
        search(), keep_and_update(),
        submit(note=long, update_findings=[{"statement": COPIED, "sources": ["web-1-1"]}]),   # before the copy guard
        submit(update_findings=[{"statement": CLEAN_STATEMENT, "sources": ["web-1-1"]}]),
        answer(world)]
    ctx, _ = await run_loop(world, script, exa=[page_reply()], page_texts=[COPY_LEAD, COPIED])
    assert rules(ctx) == ["same_turn", "findings", "note_too_long", "note_too_long", None]
    # the flagged statement is withheld although the note cap, not the copy guard, refused the submit (v1.3, P4.3)
    assert submit_calls(ctx)[3]["update_findings"][0]["statement"] == WITHHELD
    assert submit_calls(ctx)[3]["note"] == long


async def test_a_worst_case_composition_logs_no_error(world, caplog):
    """P4.6: the 40 largest documents with full keep reasons, a question and a scope note at their caps stay inside
    COMPOSITION_RESERVE_INPUT, so the estimate's error log is not reached."""
    reason = "r" * int(settings.KEEP_REASON_MAX_CHARS.value)
    corpus = world.corpus
    ctx = FakeCtx(question="q" * int(settings.QUESTION_MAX_CHARS.value))
    probe = _Run(ctx, make_deps(world, [])[0])
    size = {pid: probe.est_json(fmt.document_block(p, reason)) for pid, p in corpus.passages.items()}
    largest = sorted(size, key=lambda pid: (-size[pid], pid))[:int(settings.KEEP_CAP.value)]
    docs = sort_documents(largest, corpus)
    deps, fakes = make_deps(world, [composition(cite_block("Text. ", corpus, docs, docs[0], 0, 0))])
    run = _Run(ctx, deps)
    for pid in largest:
        run.kept[pid] = KeptPassage(passage_id=pid, reason=reason, kept_at_round=1)
    caplog.set_level(logging.WARNING, logger="probable_clause.loop")
    comp = await run.compose("n" * NOTE_MAX)
    assert comp.outcome == "complete"
    request = fakes["anthropic"].requests[0]
    est = run.est(request["system"]) + run.est_json(request["messages"])
    reserve = int(settings.COMPOSITION_RESERVE_INPUT.value)
    assert 0.95 * reserve < est <= reserve                     # this is the worst case, right under the reserve
    assert [r.getMessage() for r in caplog.records
            if r.name.startswith("probable_clause") and r.levelno >= logging.WARNING] == []


async def test_a_composition_estimate_past_the_reserve_is_logged_as_an_error(world, caplog, monkeypatch):
    monkeypatch.setattr("api.loop.run.COMPOSITION_RESERVE_INPUT", 100)
    caplog.set_level(logging.WARNING, logger="probable_clause.loop")
    ctx, _ = await run_loop(world, [search(), keep(), submit(update_skip_reason=SKIP), answer(world)])
    errors = [r for r in caplog.records if r.levelno == logging.ERROR and "composition input" in r.getMessage()]
    assert len(errors) == 1 and ctx.question not in errors[0].getMessage()
    assert ctx.ended()["state"] == "answered"                  # logged, never a stop


# ---------- P4.7: rule 4 waived when out of scope ----------

async def test_hello_out_of_scope_is_accepted_at_once_with_no_update_check(world):
    note = "Hello. I answer questions about the Supreme Court's Fourth Amendment opinions; ask me one."
    ctx, fakes = await run_loop(world, [turn(tu("submit_answer", out_of_scope=True, note=note),
                                             usage=loop_usage(1, first=True))], ctx=FakeCtx(question="hello"))
    assert rules(ctx) == [None]
    assert ctx.results("submit_answer")[0]["content"] == prompts.message("submit_accepted_note")
    assert not [g for g in ctx.gates if g[0] != "anthropic"] and fakes["exa"].calls == []
    band = ctx.of("update_band")[0]
    assert (band["outcome"], band["reason"], band["searches"], band["findings"]) == ("not_run", None, [], [])
    end = ctx.ended()
    assert (end["state"], end["no_sources_reason"], end["note"], end["answer_end"], end["rounds"]) == \
        ("no_sources", "out_of_scope", note, "none", 1)
    assert end["stop_kind"] is None and end["stop_kinds"] == [] and "composition_started" not in ctx.kinds()


def test_withholding_a_flagged_note():
    inp = {"out_of_scope": True, "note": "copied", "update_skip_reason": "kept as sent"}
    shown = withhold_flagged(inp, set(), False, note_flagged=True)
    assert shown == {"out_of_scope": True, "note": WITHHELD, "update_skip_reason": "kept as sent"}
    assert inp["note"] == "copied"                                       # Claude's input untouched
    assert withhold_flagged(inp, set(), False)["note"] == "copied"


def test_band_outcome_for_an_accepted_out_of_scope_reply_with_no_search():
    assert band_outcome(searches_counted=0, submitted=True, findings=[], unavailable=False, skip_reason=None,
                        declined=False) == ("not_run", None)


async def test_an_out_of_scope_submit_after_a_reminder_is_not_declined(world):
    script = [search(), keep(), submit(), turn(tu("submit_answer", out_of_scope=True, note=CLEAN_NOTE),
                                               usage=loop_usage(5))]
    ctx, _ = await run_loop(world, script)
    assert rules(ctx) == ["no_update_check", None]
    assert ctx.of("update_band")[0]["outcome"] == "not_run"
    assert ctx.ended()["no_sources_reason"] == "out_of_scope"


async def test_rule_4_still_holds_for_an_in_scope_nothing_found_reply(world):
    note = "Claude found no passages in the corpus that bear on this question."
    ctx, _ = await run_loop(world, [search(), submit(note=note), submit(note=note)])
    assert rules(ctx) == ["no_update_check", None]
    assert ctx.of("update_band")[0]["outcome"] == "declined"
    assert ctx.ended()["no_sources_reason"] == "nothing_found"


# ---------- P4.8: the note of a no-sources reply, guarded once a page was returned ----------

async def test_an_out_of_scope_note_that_repeats_a_page_is_refused_and_withheld(world):
    script = [update(), turn(tu("submit_answer", out_of_scope=True, note=COPIED_NOTE), usage=loop_usage(2)),
              turn(tu("submit_answer", out_of_scope=True, note=CLEAN_NOTE), usage=loop_usage(3))]
    ctx, fakes = await run_loop(world, script, exa=[page_reply()], page_texts=[COPY_LEAD, COPIED])
    assert rules(ctx) == ["copy_guard", None]
    refused = ctx.results("submit_answer")[0]
    assert refused["content"] == rejection("submit", "copy_guard_note", pages=pages_named(["web-1-1"]))
    assert "web-1-1" in refused["content"] and COPIED not in refused["content"]
    first, second = submit_calls(ctx)
    assert first == {"out_of_scope": True, "note": WITHHELD} and second["note"] == CLEAN_NOTE
    # Claude's own conversation keeps its input (P4.3)
    sent = [b for m in fakes["anthropic"].requests[2]["messages"] if m["role"] == "assistant" for b in m["content"]
            if b.get("name") == "submit_answer"]
    assert sent[0]["input"]["note"] == COPIED_NOTE
    end = ctx.ended()
    assert (end["state"], end["no_sources_reason"], end["note"]) == ("no_sources", "out_of_scope", CLEAN_NOTE)
    assert ctx.of("update_band")[0]["outcome"] == "nothing_relevant"
    assert COPIED not in json.dumps(ctx.events)


async def test_a_nothing_found_note_that_repeats_a_page_is_refused_and_withheld(world):
    script = [search(), update(), submit(note=COPIED_NOTE), submit(note=CLEAN_NOTE)]
    ctx, _ = await run_loop(world, script, exa=[page_reply()], page_texts=[COPY_LEAD, COPIED])
    assert rules(ctx) == ["copy_guard", None]
    assert ctx.results("submit_answer")[0]["content"] == rejection("submit", "copy_guard_note", pages="page web-1-1")
    assert submit_calls(ctx)[0]["note"] == WITHHELD
    assert ctx.ended()["no_sources_reason"] == "nothing_found" and ctx.ended()["note"] == CLEAN_NOTE


async def test_an_out_of_scope_note_is_guarded_even_with_passages_kept(world):
    script = [search(), keep_and_update(), turn(tu("submit_answer", out_of_scope=True, note=COPIED_NOTE),
                                                usage=loop_usage(3)),
              turn(tu("submit_answer", out_of_scope=True, note=CLEAN_NOTE), usage=loop_usage(4))]
    ctx, _ = await run_loop(world, script, exa=[page_reply()], page_texts=[COPY_LEAD, COPIED])
    assert rules(ctx) == ["copy_guard", None]
    assert submit_calls(ctx)[0]["note"] == WITHHELD
    assert ctx.ended()["no_sources_reason"] == "out_of_scope" and "composition_started" not in ctx.kinds()


async def test_a_note_flagged_with_a_statement_gets_every_problem(world):
    script = [search(), update(),
              submit(note=COPIED_NOTE, update_findings=[{"statement": COPIED, "sources": ["web-1-1"]}],
                     update_overview="One sample page describes a ruling."),
              submit(note=CLEAN_NOTE, update_findings=[{"statement": CLEAN_STATEMENT, "sources": ["web-1-1"]}])]
    ctx, _ = await run_loop(world, script, exa=[page_reply()], page_texts=[COPY_LEAD, COPIED])
    assert rules(ctx) == ["copy_guard", None]
    report = copy_guard_report([COPIED], "One sample page describes a ruling.", {"web-1-1": PAGE},
                               int(settings.COPY_GUARD_WORDS.value), note=COPIED_NOTE)
    content = ctx.results("submit_answer")[0]["content"]
    assert content == rejection("submit", "copy_guard", problems="\n".join(report.problems))
    assert "Statement 1" in content and "The note" in content
    shown = submit_calls(ctx)[0]
    assert shown["note"] == WITHHELD and shown["update_findings"][0]["statement"] == WITHHELD
    assert shown["update_overview"] == "One sample page describes a ruling."
    assert ctx.of("update_band")[0]["outcome"] == "found"


async def test_an_answered_run_s_scope_note_that_repeats_a_page_is_not_guarded(world):
    scope = "This answer covers federal law only. " + COPIED
    script = [search(), keep_and_update(), submit(note=scope, update_findings=[]), answer(world)]
    ctx, _ = await run_loop(world, script, exa=[page_reply()], page_texts=[COPY_LEAD])
    assert rules(ctx) == [None]
    assert submit_calls(ctx)[0]["note"] == scope
    end = ctx.ended()
    assert end["state"] == "answered" and end["scope_note"] == scope


async def test_keep_reasons_are_not_guarded(world):
    script = [search(), update(), keep(reason=COPIED), submit(update_findings=[]), answer(world)]
    ctx, fakes = await run_loop(world, script, exa=[page_reply()], page_texts=[COPY_LEAD])
    k = ctx.results("keep_passages")[0]
    assert not k["is_error"] and k["kept"] == [{"id": "katz-1-p6", "reason": COPIED, "replaced": False}]
    assert rules(ctx) == [None] and ctx.ended()["state"] == "answered"
    assert COPIED in fakes["anthropic"].requests[-1]["messages"][0]["content"][0]["context"]


async def test_the_skip_reason_is_not_guarded(world):
    script = [update(), turn(tu("submit_answer", out_of_scope=True, note=CLEAN_NOTE, update_skip_reason=COPIED),
                             usage=loop_usage(2))]
    ctx, _ = await run_loop(world, script, exa=[page_reply()], page_texts=[COPY_LEAD])
    assert rules(ctx) == [None]
    assert submit_calls(ctx)[0]["update_skip_reason"] == COPIED


async def test_a_flagged_note_never_reaches_atlas(world):
    """Through H's app and the store: Atlas's copy of the stream holds the withheld text, never the note."""
    from api.server import AppDeps, create_app
    from api.state.store import MemoryStore
    from tests.loop.support import check_stream
    from tests.server.support import Client, FakeClock, lifespan

    script = [update(), turn(tu("submit_answer", out_of_scope=True, note=COPIED_NOTE), usage=loop_usage(2)),
              turn(tu("submit_answer", out_of_scope=True, note=CLEAN_NOTE), usage=loop_usage(3))]
    clock = FakeClock()
    store = MemoryStore(clock=lambda: clock.now())
    deps, fakes = make_deps(world, script, store=store, exa=[page_reply()])

    async def factory():
        return AppDeps(store=store, execute_run=execute_run, loop_deps=deps, commit="g-v15", clock=clock)

    app = create_app(factory)
    client = Client(app)
    async with lifespan(app):
        resp = await client.post("/runs", {"question": "Can the police scan a house with a thermal camera?"})
        assert resp.status == 201
        run_id = resp.json()["run_id"]
        s = client.stream(f"/runs/{run_id}/events")
        for _ in range(50):
            await clock.settle()
            s.pump()
            if s.closed:
                break
        assert s.closed, "the run did not end"
        events = s.events()
        await clock.settle()
        stored = await store.read_events(run_id, 0)
        record = await store.get_run_record(run_id)
    assert not fakes["anthropic"].script
    check_stream(events, world.corpus, page_texts=[COPY_LEAD, COPIED])
    assert [{k: v for k, v in e.items() if k != "created"} for e in stored] == events
    calls = [e["data"]["input"] for e in stored if e["kind"] == "tool_call" and e["data"]["name"] == "submit_answer"]
    assert calls[0]["note"] == WITHHELD
    dumped = json.dumps(stored, default=str) + json.dumps(record, default=str)
    assert COPIED not in dumped and COPY_LEAD not in dumped and "court of appeals held" not in dumped


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


async def test_a_statement_quoting_the_court_that_a_page_also_quotes_is_accepted(world):
    quoting = 'A sample page discusses Katz and its line that "' + KATZ_Q + '"'
    copying = 'A sample page says: "' + KATZ_Q + '" ' + PAGE_OWN
    # without the exemption both would be flagged, so the exemption is what lets the first one through
    assert copy_guard_report([quoting, copying], None, {"web-1-1": COURT_PAGE},
                             int(settings.COPY_GUARD_WORDS.value)).flagged_statements == {0, 1}
    script = [search(), keep_and_update(),
              submit(update_findings=[{"statement": copying, "sources": ["web-1-1"]}]),
              submit(update_findings=[{"statement": quoting, "sources": ["web-1-1"]}]), answer(world)]
    ctx, _ = await run_loop(world, script, exa=[page_reply(COURT_PAGE)], page_texts=[PAGE_OWN])
    assert rules(ctx) == ["copy_guard", None]
    assert submit_calls(ctx)[0]["update_findings"][0]["statement"] == WITHHELD
    band = ctx.of("update_band")[0]
    assert band["outcome"] == "found" and band["findings"][0]["statement"] == quoting


async def test_a_note_quoting_the_court_that_a_page_also_quotes_is_accepted(world):
    quoting = 'No passage settles this beyond Katz\'s line that "' + KATZ_Q + '"'
    copying = 'No passage settles this. "' + KATZ_Q + '" ' + PAGE_OWN
    script = [search(), update(), submit(note=copying), submit(note=quoting)]
    ctx, _ = await run_loop(world, script, exa=[page_reply(COURT_PAGE)], page_texts=[PAGE_OWN])
    assert rules(ctx) == ["copy_guard", None]
    assert ctx.results("submit_answer")[0]["content"] == rejection("submit", "copy_guard_note", pages="page web-1-1")
    assert submit_calls(ctx)[0]["note"] == WITHHELD and submit_calls(ctx)[1]["note"] == quoting
    assert ctx.ended()["note"] == quoting and ctx.ended()["no_sources_reason"] == "nothing_found"


# ---------- P4.10: a composition attempt broken before its first block ----------

def read_keep_submit():
    return [turn(tu("read_passages", target="katz-1-p6"), tu("search_exact", any_of=["booth"], max_results=1),
                 usage=loop_usage(1, first=True)),
            turn(tu("keep_passages", keep=[{"id": "katz-1-p6", "reason": "r"}]), usage=loop_usage(2)),
            turn(tu("submit_answer", out_of_scope=False, update_skip_reason=SKIP), usage=loop_usage(3))]


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
    ctx, fakes = await run_loop(world, [*read_keep_submit(), BROKEN_BEFORE_FIRST_BLOCK[case](), big])
    comp = [x for x in ctx.paid if x["purpose"] == "composition"]
    assert [(x["attempt"], x["outcome"]) for x in comp] == [(1, "retrying"), (2, "ok")]
    failed = comp[0]
    expected = 0 if case == "nothing_streamed" else math.ceil(6_000 / chars_per_token(world.corpus))
    assert failed["estimated"] is True and failed["_usage"].output_tokens == expected
    assert failed["_usage"].output_tokens < int(settings.COMPOSITION_MAX_TOKENS.value)
    if case == "nothing_streamed":
        assert failed["usage"] is None and failed["_usage"].input_tokens > 0          # its input estimate
    else:
        assert failed["usage"]["output_tokens"] == expected
    # the retry runs with the composition's whole room, and the run's output stays inside its ceiling
    reqs = [r for r in fakes["anthropic"].requests if r["model"] == str(settings.COMPOSITION_MODEL.value)]
    assert len(reqs) == 2 and reqs[1]["max_tokens"] == int(settings.COMPOSITION_MAX_TOKENS.value)
    output = sum(x["_usage"].output_tokens for x in ctx.paid if x["purpose"] in ("loop", "composition"))
    assert output <= int(settings.RUN_OUTPUT_TOKENS.value)
    end = ctx.ended()
    assert (end["state"], end["answer_end"], end["failure_reason"], end["stop_kinds"]) == \
        ("answered", "complete", None, [])
