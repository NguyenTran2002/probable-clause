"""UpdateSearch.search (contract §4.D; T2.2, T2.4, T2.5, P2.8, P2.11): the flow, the four failure kinds, no retries."""

import asyncio
import logging
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from api import settings
from api.errors import ServiceError
from api.types import RunStopped, Usage
from api.web_updates.exa import FakeExaTransport, UpdateSearch, WebSearchOutcome, exa_response, exa_result
from api.web_updates.params import parse_params, to_exa_arguments

pytestmark = pytest.mark.anyio

TEXT_CAP = int(settings.EXA_TEXT_CHARS.value)
P = parse_params({"query": "synthetic query about a made-up case"})
LITE = parse_params({"query": "synthetic query", "type": "lite"})


def r(n, **kw):
    kw.setdefault("url", f"https://example.test/page-{n}")
    kw.setdefault("title", f"Synthetic title {n}")
    kw.setdefault("published", "2026-07-01T00:00:00.000Z")
    kw.setdefault("text", f"Synthetic text of page {n}.")
    return exa_result(**kw)


async def run(searcher, ctx, p=P, no=1, seen=None):
    seen = {} if seen is None else seen
    return await searcher.search(p, no, seen, ctx), seen


# --- a completed search -----------------------------------------------------------------------------------------------

async def test_a_completed_search_returns_pages_in_exas_order(transport, searcher, ctx):
    transport.push(exa_response([r(1), r(2), r(3)], cost_total=0.007))
    o, seen = await run(searcher, ctx, no=2)
    assert isinstance(o, WebSearchOutcome)
    assert o.kind == "ok" and o.unavailable_reason is None and o.exa_message is None
    assert [p.id for p in o.pages] == ["web-2-1", "web-2-2", "web-2-3"]
    assert [p.title for p in o.pages] == ["Synthetic title 1", "Synthetic title 2", "Synthetic title 3"]
    assert o.pages[0].url == "https://example.test/page-1" and o.pages[0].domain == "example.test"
    assert o.pages[0].published == "2026-07-01" and o.pages[0].text == "Synthetic text of page 1."
    assert o.pages[0].truncated is False and o.repeats == [] and o.undated == 0
    assert seen == {"https://example.test/page-1": "web-2-1", "https://example.test/page-2": "web-2-2",
                    "https://example.test/page-3": "web-2-3"}


async def test_the_search_is_sent_once_with_our_arguments_and_the_timeout(transport, searcher, ctx):
    transport.push(exa_response([r(1)]))
    await run(searcher, ctx)
    assert transport.calls == [(to_exa_arguments(P), float(settings.EXA_TIMEOUT_S.value))]


async def test_one_before_paid_call_and_one_record_usage_in_that_order(transport, searcher, ctx):
    transport.push(exa_response([r(1)], cost_total=0.007))
    o, _ = await run(searcher, ctx)
    assert ctx.before == [("exa", "update_search")]
    assert ctx.order == ["before_paid_call", "record_usage"]
    [u] = ctx.usages
    assert u["usage"] == Usage(service="exa", model="auto", exa_cost_usd=0.007)
    assert (u["purpose"], u["attempt"], u["max_attempts"], u["outcome"], u["error_kind"]) == ("update_search", 1, 1, "ok", None)
    assert isinstance(u["duration_ms"], int) and u["duration_ms"] >= 0
    assert o.cost_usd == 0.007


async def test_the_model_field_is_the_search_type(transport, searcher, ctx):
    transport.push(exa_response([r(1)], cost_total=0.004))
    await run(searcher, ctx, p=LITE)
    assert ctx.usages[0]["usage"] == Usage(service="exa", model="lite", exa_cost_usd=0.004)


async def test_a_missing_cost_is_recorded_as_estimated_so_it_is_charged_at_list_price(transport, searcher, ctx):
    transport.push(exa_response([r(1)], cost_total=None))
    o, _ = await run(searcher, ctx)
    assert ctx.usages[0]["usage"] == Usage(service="exa", model="auto", exa_cost_usd=None, estimated=True)
    assert ctx.usages[0]["outcome"] == "ok" and o.cost_usd == 0.007


@pytest.mark.parametrize("cost", ["0.007", {"search": 1}, True, -1.0, float("nan")])
async def test_a_nonsense_cost_is_treated_as_not_reported(transport, searcher, ctx, cost):
    resp = exa_response([r(1)])
    resp["costDollars"] = {"total": cost}
    transport.push(resp)
    o, _ = await run(searcher, ctx)
    assert o.kind == "ok"
    assert ctx.usages[0]["usage"] == Usage(service="exa", model="auto", exa_cost_usd=None, estimated=True)


async def test_an_empty_result_list_is_a_completed_search(transport, searcher, ctx):
    transport.push(exa_response([]))
    o, _ = await run(searcher, ctx)
    assert o.kind == "ok" and o.pages == [] and o.repeats == [] and o.undated == 0


# --- the results ------------------------------------------------------------------------------------------------------

async def test_repeats_are_reported_by_the_first_id_and_not_returned_again(transport, searcher, ctx):
    seen = {"https://example.test/page-2": "web-1-4"}
    transport.push(exa_response([r(1), r(2), r(3)]))
    o, seen = await run(searcher, ctx, no=2, seen=seen)
    assert o.repeats == ["web-1-4"]
    assert [p.url for p in o.pages] == ["https://example.test/page-1", "https://example.test/page-3"]
    assert [p.id for p in o.pages] == ["web-2-1", "web-2-2"]      # numbered over the new pages, no gaps
    assert seen["https://example.test/page-2"] == "web-1-4"        # the first ID stays


async def test_a_page_listed_twice_in_one_result_is_a_repeat_of_its_first_listing(transport, searcher, ctx):
    transport.push(exa_response([r(1), r(2, url="https://example.test/page-1")]))
    o, _ = await run(searcher, ctx)
    assert [p.id for p in o.pages] == ["web-1-1"] and o.repeats == ["web-1-1"]


async def test_repeats_are_matched_ignoring_a_fragment_a_trailing_slash_and_host_case(transport, searcher, ctx):
    seen = {}
    transport.push(exa_response([r(1, url="https://Example.test/a/b/")]))
    await run(searcher, ctx, seen=seen)
    transport.push(exa_response([r(2, url="https://example.TEST/a/b#section")]))
    o, _ = await run(searcher, ctx, no=2, seen=seen)
    assert o.pages == [] and o.repeats == ["web-1-1"]


async def test_different_queries_in_the_url_are_different_pages(transport, searcher, ctx):
    transport.push(exa_response([r(1, url="https://example.test/a?id=1"), r(2, url="https://example.test/a?id=2")]))
    o, _ = await run(searcher, ctx)
    assert len(o.pages) == 2 and o.repeats == []


async def test_repeats_do_not_list_an_id_twice(transport, searcher, ctx):
    seen = {"https://example.test/page-1": "web-1-1"}
    transport.push(exa_response([r(1), r(1)]))
    o, _ = await run(searcher, ctx, no=2, seen=seen)
    assert o.repeats == ["web-1-1"]


@pytest.mark.parametrize("raw,expected", [
    ("2026-06-29T14:17:34.000Z", "2026-06-29"),
    ("2026-06-29T00:00:00.000Z", "2026-06-29"),
    ("2026-06-29", "2026-06-29"),
    ("2026-06-29 23:59:59", "2026-06-29"),
    ("2026-13-45T00:00:00Z", None),
    ("2026-02-30T00:00:00Z", None),
    ("June 29, 2026", None),
    ("26-06-29", None),
    ("20260629", None),
    ("2026-06-2", None),
    ("", None),
    (None, None),
    (20260629, None),
    ("not a date", None),
])
async def test_published_date_keeps_the_date_part_or_becomes_none(transport, searcher, ctx, raw, expected):
    transport.push(exa_response([r(1, published=raw)]))
    o, _ = await run(searcher, ctx)
    assert o.pages[0].published == expected
    assert o.undated == (0 if expected else 1)


async def test_a_missing_published_field_counts_as_undated(transport, searcher, ctx):
    res = r(1)
    del res["publishedDate"]
    transport.push(exa_response([res, r(2), r(3, published=None)]))
    o, _ = await run(searcher, ctx)
    assert [p.published for p in o.pages] == [None, "2026-07-01", None] and o.undated == 2


async def test_undated_counts_repeats_too(transport, searcher, ctx):
    seen = {"https://example.test/page-1": "web-1-1"}
    transport.push(exa_response([r(1, published=None), r(2, published=None)]))
    o, _ = await run(searcher, ctx, no=2, seen=seen)
    assert len(o.pages) == 1 and o.repeats == ["web-1-1"] and o.undated == 2


@pytest.mark.parametrize("url", ["ftp://example.test/x", "javascript:alert(1)", "file:///etc/passwd", "mailto:a@b.test",
                                  "data:text/html,hi", "//example.test/x", "example.test/x", "", None, 5, "http://", "https:///x"])
async def test_a_result_that_is_not_http_or_https_is_dropped(transport, searcher, ctx, url):
    transport.push(exa_response([r(1, url=url), r(2)]))
    o, seen = await run(searcher, ctx)
    assert [p.url for p in o.pages] == ["https://example.test/page-2"]
    assert o.pages[0].id == "web-1-1"            # dropped results leave no gap
    assert len(seen) == 1


async def test_http_and_https_are_both_kept_and_the_scheme_is_case_insensitive(transport, searcher, ctx):
    transport.push(exa_response([r(1, url="http://example.test/a"), r(2, url="HTTPS://example.test/b")]))
    o, _ = await run(searcher, ctx)
    assert [p.url for p in o.pages] == ["http://example.test/a", "https://example.test/b"]   # scheme in lower case


async def test_text_is_capped_and_marked(transport, searcher, ctx):
    transport.push(exa_response([r(1, text="x" * (TEXT_CAP + 500)), r(2, text="y" * (TEXT_CAP - 1)), r(3, text="")]))
    o, _ = await run(searcher, ctx)
    assert len(o.pages[0].text) == TEXT_CAP and o.pages[0].truncated is True
    assert len(o.pages[1].text) == TEXT_CAP - 1 and o.pages[1].truncated is False
    assert o.pages[2].text == "" and o.pages[2].truncated is False


async def test_text_at_exactly_the_cap_counts_as_cut(transport, searcher, ctx):
    # We send the cap to Exa, which cuts to it and does not say so (observed: capped results came back at exactly the
    # cap), so a page of exactly the cap's length is marked as possibly cut.
    transport.push(exa_response([r(1, text="x" * TEXT_CAP)]))
    o, _ = await run(searcher, ctx)
    assert o.pages[0].truncated is True


async def test_missing_fields_get_safe_values(transport, searcher, ctx):
    transport.push(exa_response([{"url": "https://example.test/bare"}]))
    o, _ = await run(searcher, ctx)
    [pg] = o.pages
    assert pg.title and pg.text == "" and pg.author is None and pg.published is None and pg.truncated is False


async def test_author_is_kept_when_given_and_none_when_blank(transport, searcher, ctx):
    transport.push(exa_response([r(1, author="A. Writer"), r(2, author="  "), r(3, author=None)]))
    o, _ = await run(searcher, ctx)
    assert [p.author for p in o.pages] == ["A. Writer", None, None]


async def test_more_results_than_asked_are_cut_to_num_results(transport, searcher, ctx):
    p = parse_params({"query": "q", "num_results": 2})
    transport.push(exa_response([r(i) for i in range(1, 6)]))
    o, _ = await run(searcher, ctx, p=p)
    assert len(o.pages) == 2


@pytest.mark.parametrize("bad", [{}, {"results": None}, {"results": "x"}, {"results": {"a": 1}}, [], "text", None])
async def test_a_reply_we_cannot_read_is_a_failed_search(transport, searcher, ctx, bad):
    transport.push(bad)
    o, _ = await run(searcher, ctx)
    assert o.kind == "failed"
    assert ctx.usages[0]["usage"] == Usage(service="exa", model="auto", estimated=True)
    assert ctx.usages[0]["error_kind"] == "unreadable"


async def test_a_result_entry_that_is_not_an_object_is_skipped(transport, searcher, ctx):
    transport.push(exa_response([r(1), "junk", 7, None, r(2)]))
    o, _ = await run(searcher, ctx)
    assert [p.id for p in o.pages] == ["web-1-1", "web-1-2"]


# --- Exa refused it (a 4xx other than 401 and 402) -------------------------------------------------------------------

@pytest.mark.parametrize("kind,status", [("bad_request", 400), ("permission", 403), ("not_found", 404), ("too_large", 413),
                                          ("rate_limited", 429)])
async def test_refused_by_exa_passes_exas_message_and_records_an_explicit_zero(transport, searcher, ctx, kind, status):
    transport.push(ServiceError("exa", kind, status, "Invalid request body | The company category does not support dates"))
    o, _ = await run(searcher, ctx)
    assert o.kind == "refused_by_exa" and o.unavailable_reason is None
    assert o.exa_message == "Invalid request body | The company category does not support dates"
    assert o.pages == [] and o.cost_usd == 0.0
    [u] = ctx.usages
    assert u["usage"] == Usage(service="exa", model="auto", exa_cost_usd=0.0)        # counted, no cost (T2.4)
    assert u["usage"].estimated is False
    assert u["outcome"] == "failed" and u["error_kind"] == kind and (u["attempt"], u["max_attempts"]) == (1, 1)
    assert ctx.flags.exa_unavailable is None and ctx.before == [("exa", "update_search")]


async def test_a_refusal_sets_no_flag_and_records_no_stop(transport, searcher, ctx, store):
    transport.push(FakeExaTransport.failure("bad_request"))
    await run(searcher, ctx)
    assert "set_flag" not in store.names() and "record_stop" not in store.names()


# --- failed (5xx after Exa's retries, protocol, connection, timeout, unreadable) -------------------------------------

@pytest.mark.parametrize("kind", ["server_error", "gateway_timeout", "connection", "timeout", "protocol", "unreadable"])
async def test_a_failed_search_is_recorded_at_list_price_and_never_retried(transport, searcher, ctx, kind):
    transport.push(FakeExaTransport.failure(kind))
    o, _ = await run(searcher, ctx)
    assert o.kind == "failed" and o.unavailable_reason is None and o.exa_message is None and o.pages == []
    assert len(transport.calls) == 1                                     # T2.4, P2.8: never retried by us
    assert ctx.before == [("exa", "update_search")]
    [u] = ctx.usages
    assert u["usage"] == Usage(service="exa", model="auto", estimated=True)
    assert (u["outcome"], u["error_kind"], u["attempt"], u["max_attempts"]) == ("failed", kind, 1, 1)
    assert o.cost_usd == 0.007


async def test_a_failed_lite_search_is_priced_as_lite(transport, searcher, ctx):
    transport.push(FakeExaTransport.failure("timeout"))
    o, _ = await run(searcher, ctx, p=LITE)
    assert ctx.usages[0]["usage"] == Usage(service="exa", model="lite", estimated=True) and o.cost_usd == 0.004


async def test_a_5xx_with_a_status_is_failed_not_refused(transport, searcher, ctx):
    transport.push(ServiceError("exa", "server_error", 503, "Service unavailable"))
    o, _ = await run(searcher, ctx)
    assert o.kind == "failed" and o.exa_message is None


async def test_a_transport_that_raises_something_else_is_a_failed_search(transport, searcher, ctx):
    transport.push(RuntimeError("boom"))
    o, _ = await run(searcher, ctx)
    assert o.kind == "failed" and ctx.usages[0]["usage"].estimated is True and len(ctx.usages) == 1


async def test_a_builtin_timeout_is_a_failed_search(transport, searcher, ctx):
    transport.push(TimeoutError())
    o, _ = await run(searcher, ctx)
    assert o.kind == "failed" and ctx.usages[0]["error_kind"] == "timeout"


async def test_a_run_of_failures_never_retries(transport, searcher, ctx):
    for _ in range(3):
        transport.push(FakeExaTransport.failure("server_error"))
    for no in (1, 2, 3):
        await run(searcher, ctx, no=no)
    assert len(transport.calls) == 3 and len(ctx.usages) == 3


# --- unavailable: 402 and 401 -----------------------------------------------------------------------------------------

async def test_the_first_402_sets_the_flag_records_the_stop_and_marks_the_run(transport, searcher, ctx, store):
    transport.push(FakeExaTransport.failure("no_credit"))
    o, _ = await run(searcher, ctx)
    assert o.kind == "unavailable" and o.unavailable_reason == "no_credit" and o.pages == [] and o.cost_usd == 0.0
    assert ctx.flags.exa_unavailable == "no_credit"
    assert store.calls[0] == ("flag_until", "exa_out_of_credit")
    assert ("set_flag", "exa_out_of_credit") in store.calls
    [stop] = [c for c in store.calls if c[0] == "record_stop"]
    assert stop[1] == "exa_no_credit" and stop[2] == "run-test-1"
    assert "query" not in str(stop[3]).lower() and "synthetic query" not in str(stop[3])      # T3.7
    assert ctx.usages == []                                          # not counted, no cost: no paid_call event
    assert ctx.before == [("exa", "update_search")]
    assert ctx.order == ["before_paid_call", "call_not_billed"]      # the gate is undone: nothing billed (v1.4)


async def test_a_402_identified_by_status_alone_is_out_of_credit(transport, searcher, ctx):
    transport.push(ServiceError("exa", "bad_request", 402, "x"))
    o, _ = await run(searcher, ctx)
    assert o.kind == "unavailable" and o.unavailable_reason == "no_credit"


async def test_a_401_is_key_refused_for_this_run_only(transport, searcher, ctx, store):
    transport.push(FakeExaTransport.failure("auth"))
    o, _ = await run(searcher, ctx)
    assert o.kind == "unavailable" and o.unavailable_reason == "key_refused" and o.cost_usd == 0.0
    assert ctx.flags.exa_unavailable == "key_refused"
    assert "set_flag" not in store.names() and "record_stop" not in store.names()
    assert ctx.usages == [] and ctx.order == ["before_paid_call", "call_not_billed"]   # no paid_call event (v1.4)


async def test_a_401_identified_by_status_alone(transport, searcher, ctx):
    transport.push(ServiceError("exa", "protocol", 401, "x"))
    o, _ = await run(searcher, ctx)
    assert o.unavailable_reason == "key_refused"


async def test_after_a_402_later_searches_in_the_run_do_not_open_a_session(transport, searcher, ctx, store):
    transport.push(FakeExaTransport.failure("no_credit"))
    await run(searcher, ctx, no=1)
    reads_before = store.names().count("flag_until")
    o, _ = await run(searcher, ctx, no=2)
    assert o.kind == "unavailable" and o.unavailable_reason == "no_credit"
    assert len(transport.calls) == 1 and len(ctx.usages) == 0 and len(ctx.before) == 1
    assert store.names().count("flag_until") == reads_before        # decided from the run's flag, no Atlas read


async def test_after_a_401_later_searches_are_unavailable_too(transport, searcher, ctx):
    transport.push(FakeExaTransport.failure("auth"))
    await run(searcher, ctx, no=1)
    o, _ = await run(searcher, ctx, no=2)
    assert o.kind == "unavailable" and o.unavailable_reason == "key_refused" and len(transport.calls) == 1


async def test_a_run_flag_set_before_the_search_means_no_session_no_store_read_no_spend(transport, searcher, ctx, store):
    ctx.flags.exa_unavailable = "key_refused"
    o, _ = await run(searcher, ctx)
    assert o.kind == "unavailable" and o.unavailable_reason == "key_refused"
    assert transport.calls == [] and ctx.before == [] and ctx.usages == [] and store.calls == []


async def test_the_atlas_flag_means_unavailable_without_calling_exa(transport, make_store, make_ctx):
    store = make_store(flag_until=datetime(2026, 11, 1, tzinfo=ZoneInfo("America/Chicago")))
    ctx = make_ctx()
    o, _ = await run(UpdateSearch(transport, store), ctx)
    assert o.kind == "unavailable" and o.unavailable_reason == "no_credit"
    assert ctx.flags.exa_unavailable == "no_credit"
    assert transport.calls == [] and ctx.before == [] and ctx.usages == []
    assert store.names() == ["flag_until"]                           # nothing set again, nothing recorded


async def test_with_the_flag_clear_the_atlas_flag_is_read_before_the_session(transport, searcher, ctx, store):
    transport.push(exa_response([r(1)]))
    await run(searcher, ctx)
    assert store.calls == [("flag_until", "exa_out_of_credit")]


async def test_an_unreadable_flag_does_not_block_the_search(transport, make_store, make_ctx, caplog):
    store = make_store(read_fails=True)
    ctx = make_ctx()
    transport.push(exa_response([r(1)]))
    with caplog.at_level(logging.DEBUG):
        o, _ = await run(UpdateSearch(transport, store), ctx)
    assert o.kind == "ok" and len(transport.calls) == 1


async def test_a_402_still_ends_cleanly_when_atlas_cannot_be_written(transport, make_store, make_ctx):
    store = make_store(writes_fail=True)
    ctx = make_ctx()
    transport.push(FakeExaTransport.failure("no_credit"))
    o, _ = await run(UpdateSearch(transport, store), ctx)
    assert o.kind == "unavailable" and o.unavailable_reason == "no_credit"
    assert ctx.flags.exa_unavailable == "no_credit" and ctx.usages == []


async def test_a_run_stop_before_the_paid_call_propagates_with_nothing_spent(transport, store, make_ctx):
    ctx = make_ctx(stop=RunStopped("abandoned"))
    with pytest.raises(RunStopped):
        await run(UpdateSearch(transport, store), ctx)
    assert transport.calls == [] and ctx.usages == []


# --- logs and secrets -------------------------------------------------------------------------------------------------

async def test_logs_never_hold_the_query_or_page_text(transport, searcher, ctx, caplog):
    secret_query = parse_params({"query": "SECRETQUERYWORDS about nothing"})
    transport.push(exa_response([r(1, text="SECRETPAGETEXT lorem ipsum", title="SECRETTITLE")]))
    transport.push(FakeExaTransport.failure("server_error"))
    transport.push(ServiceError("exa", "bad_request", 400, "SECRETEXAMESSAGE in the message"))
    with caplog.at_level(logging.DEBUG):
        await run(searcher, ctx, p=secret_query, no=1)
        await run(searcher, ctx, p=secret_query, no=2)
        await run(searcher, ctx, p=secret_query, no=3)
    for word in ("SECRETQUERYWORDS", "SECRETPAGETEXT", "SECRETTITLE", "SECRETEXAMESSAGE"):
        assert word not in caplog.text


async def test_the_search_number_names_the_ids(transport, searcher, ctx):
    transport.push(exa_response([r(1)]))
    o, _ = await run(searcher, ctx, no=3)
    assert o.pages[0].id == "web-3-1"


# --- what the events schema accepts -----------------------------------------------------------------------------------

async def test_pages_and_ids_fit_the_events_schema(transport, searcher, ctx):
    import json
    from dataclasses import asdict
    from pathlib import Path

    from jsonschema import Draft202012Validator

    schema = json.loads((Path(__file__).resolve().parents[2] / "contracts" / "events.schema.json").read_text())
    defs = {"$defs": schema["$defs"]}
    page_schema = Draft202012Validator({**defs, "$ref": "#/$defs/web_page"})
    id_schema = Draft202012Validator({**defs, "$ref": "#/$defs/web_id"})
    seen = {"https://example.test/page-9": "web-1-4"}
    transport.push(exa_response([r(1), r(2, published=None, author="A. Writer"), r(9)]))
    o, _ = await run(searcher, ctx, no=2, seen=seen)
    for pg in o.pages:
        d = asdict(pg)
        d.pop("text"), d.pop("truncated")                      # never in events
        page_schema.validate(d)
    for rid in o.repeats:
        id_schema.validate(rid)


# --- Exa's message (T2.4) ---------------------------------------------------------------------------------------------

async def test_exas_message_is_flattened_to_one_line_and_cut(transport, searcher, ctx):
    limit = int(settings.EXA_MESSAGE_MAX_CHARS.value)
    long = "Invalid request body |\n\n  " + "word  " * 400 + "\r\nTail"
    transport.push(ServiceError("exa", "bad_request", 400, long))
    o, _ = await run(searcher, ctx)
    assert o.kind == "refused_by_exa"
    assert "\n" not in o.exa_message and "\r" not in o.exa_message and "  " not in o.exa_message
    assert len(o.exa_message) == limit and o.exa_message.startswith("Invalid request body | word word")
    assert "Tail" not in o.exa_message


async def test_a_short_message_is_kept_as_it_is(transport, searcher, ctx):
    transport.push(ServiceError("exa", "bad_request", 400, "Invalid request body | short"))
    o, _ = await run(searcher, ctx)
    assert o.exa_message == "Invalid request body | short"


async def test_titles_and_authors_are_cut_to_the_header_limit(transport, searcher, ctx):
    limit = int(settings.EXA_HEADER_FIELD_MAX_CHARS.value)
    transport.push(exa_response([r(1, title="t" * 1000, author="a\nb " * 500), r(2, title="x" * limit)]))
    o, _ = await run(searcher, ctx)
    assert len(o.pages[0].title) == limit and o.pages[0].title.endswith("…")
    assert len(o.pages[0].author) == limit and "\n" not in o.pages[0].author
    assert o.pages[1].title == "x" * limit                            # exactly the limit is not cut


# --- cancellation and a failing ledger --------------------------------------------------------------------------------

@pytest.mark.parametrize("make", [
    lambda: asyncio.CancelledError(),
    lambda: BaseExceptionGroup("tasks", [asyncio.CancelledError()]),
    lambda: BaseExceptionGroup("tasks", [asyncio.CancelledError(), RuntimeError("also failed")]),
])
async def test_a_cancellation_during_the_search_propagates_and_records_a_failed_search(transport, searcher, ctx, store, make):
    # contract v2.0: the update branch can be cancelled mid-search; a search that was sent is recorded at list price
    # before the cancellation goes on, so no billed search is left out of the spend (v1.x's reservation covered it)
    transport.push(make())
    seen = {}
    with pytest.raises(BaseException) as e:
        await searcher.search(P, 1, seen, ctx)
    assert isinstance(e.value, (asyncio.CancelledError, BaseExceptionGroup))
    [u] = ctx.usages
    assert u["usage"] == Usage(service="exa", model="auto", estimated=True) and u["outcome"] == "failed"
    assert ctx.flags.exa_unavailable is None and seen == {}
    assert store.names() == ["flag_until"]                           # no flag set, no stop recorded
    assert len(transport.calls) == 1                                 # and nothing retried


async def test_cancelling_the_task_while_exa_is_slow_records_a_failed_search(transport, searcher, ctx, store):
    started = asyncio.Event()

    async def hang(_args):
        started.set()
        await asyncio.Event().wait()

    transport.push(hang)
    task = asyncio.ensure_future(searcher.search(P, 1, {}, ctx))
    await started.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    [u] = ctx.usages
    assert u["usage"] == Usage(service="exa", model="auto", estimated=True)
    assert (u["outcome"], u["attempt"], u["max_attempts"]) == ("failed", 1, 1)
    assert ctx.flags.exa_unavailable is None and store.names() == ["flag_until"]


async def test_a_failing_ledger_after_a_good_search_propagates_and_leaves_seen_urls_alone(transport, searcher, ctx):
    # The pages never reach Claude when record_usage raises, so their URLs must not be marked as seen: a later search
    # would otherwise report them as repeats of IDs Claude never saw.
    async def broken(*a, **k):
        raise RuntimeError("ledger down")

    ctx.record_usage = broken
    transport.push(exa_response([r(1), r(2)]))
    seen = {"https://example.test/earlier": "web-1-1"}
    with pytest.raises(RuntimeError, match="ledger down"):
        await searcher.search(P, 2, seen, ctx)
    assert seen == {"https://example.test/earlier": "web-1-1"}
    assert len(transport.calls) == 1


async def test_a_failing_ledger_after_a_failed_search_propagates_too(transport, searcher, ctx):
    async def broken(*a, **k):
        raise RuntimeError("ledger down")

    ctx.record_usage = broken
    transport.push(FakeExaTransport.failure("server_error"))
    with pytest.raises(RuntimeError, match="ledger down"):
        await searcher.search(P, 1, {}, ctx)
