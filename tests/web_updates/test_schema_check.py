"""UpdateSearch.schema_check (contract §4.D, T2.5): compares the free tool listing with every field and value we send.
It returns warnings and never raises. The schema below is a synthetic stand-in modelled on the argument names Exa's
tool lists (docs: https://exa.ai/docs/reference/search.md)."""

import copy
import logging

import pytest

from api.web_updates.exa import FakeExaTransport, UpdateSearch

pytestmark = pytest.mark.anyio


def good_schema():
    s = {"type": "string"}
    return {
        "type": "object",
        "properties": {
            "query": {"type": "string", "minLength": 1},
            "numResults": {"type": "number", "description": "Number of results (1-100, default: 10)"},
            "type": {"type": "string", "enum": ["auto", "lite", "fast", "instant"]},
            "category": {"type": "string", "enum": ["company", "publication", "news", "pdf", "github", "personal site", "people",
                                                    "financial report"]},
            "includeDomains": {"type": "array", "items": s},
            "excludeDomains": {"type": "array", "items": s},
            "startPublishedDate": s,
            "endPublishedDate": s,
            "textMaxCharacters": {"type": "number", "minimum": 1},
            "enableHighlights": {"type": "boolean"},
            "subpages": {"type": "number"},
        },
        "required": ["query"],
        "additionalProperties": False,
    }


async def warnings_for(schema, store=None):
    return await UpdateSearch(FakeExaTransport(tool_schema=schema), store or object()).schema_check()


async def test_a_matching_schema_has_no_warnings():
    assert await warnings_for(good_schema()) == []


async def test_a_tool_dict_with_an_input_schema_key_is_read_too():
    assert await warnings_for({"name": "web_search_advanced_exa", "inputSchema": good_schema()}) == []
    assert await warnings_for({"name": "web_search_advanced_exa", "input_schema": good_schema()}) == []


@pytest.mark.parametrize("field", ["query", "numResults", "type", "category", "includeDomains", "excludeDomains",
                                   "startPublishedDate", "endPublishedDate", "textMaxCharacters"])
async def test_a_field_we_send_that_the_tool_no_longer_lists_is_a_warning(field):
    s = good_schema()
    del s["properties"][field]
    w = await warnings_for(s)
    assert len(w) == 1 and field in w[0]


@pytest.mark.parametrize("field,value", [("type", "lite"), ("type", "auto"), ("category", "news"), ("category", "publication")])
async def test_a_value_we_send_that_the_enum_lacks_is_a_warning(field, value):
    s = good_schema()
    s["properties"][field]["enum"].remove(value)
    w = await warnings_for(s)
    assert len(w) == 1 and field in w[0] and value in w[0]


@pytest.mark.parametrize("field,wrong", [("includeDomains", "string"), ("excludeDomains", "string"), ("numResults", "string"),
                                         ("startPublishedDate", "number"), ("query", "array"), ("textMaxCharacters", "string")])
async def test_a_changed_type_is_a_warning(field, wrong):
    s = good_schema()
    s["properties"][field] = {"type": wrong}
    w = await warnings_for(s)
    assert len(w) == 1 and field in w[0]


async def test_a_new_required_field_we_do_not_send_is_a_warning():
    s = good_schema()
    s["properties"]["region"] = {"type": "string"}
    s["required"] = ["query", "region"]
    w = await warnings_for(s)
    assert len(w) == 1 and "region" in w[0]


async def test_a_text_minimum_above_our_cap_is_a_warning():
    s = good_schema()
    s["properties"]["textMaxCharacters"]["minimum"] = 10_000
    w = await warnings_for(s)
    assert len(w) == 1 and "textMaxCharacters" in w[0]


async def test_a_num_results_maximum_below_what_we_send_is_a_warning():
    s = good_schema()
    s["properties"]["numResults"]["maximum"] = 5
    w = await warnings_for(s)
    assert len(w) == 1 and "numResults" in w[0]


async def test_extra_fields_we_do_not_use_are_fine():
    s = good_schema()
    s["properties"]["brandNewThing"] = {"type": "string"}
    assert await warnings_for(s) == []


async def test_several_problems_give_several_warnings():
    s = good_schema()
    del s["properties"]["category"]
    s["properties"]["type"]["enum"].remove("lite")
    assert len(await warnings_for(s)) == 2


@pytest.mark.parametrize("schema", [{}, {"properties": {}}, [], "x", 5, None])
async def test_an_empty_or_odd_listing_warns_and_never_raises(schema):
    w = await warnings_for(schema)
    assert w and all(isinstance(x, str) for x in w)


@pytest.mark.parametrize("exc", [FakeExaTransport.failure("timeout"), FakeExaTransport.failure("auth"),
                                 FakeExaTransport.failure("protocol"), RuntimeError("boom")])
async def test_a_listing_that_fails_is_a_warning_not_an_error(exc):
    w = await warnings_for(exc)
    assert len(w) == 1 and "list" in w[0].lower()


async def test_the_check_is_free_it_calls_no_search_and_no_store():
    t = FakeExaTransport(tool_schema=good_schema())

    class NoStore:
        def __getattr__(self, name):
            raise AssertionError(f"schema_check must not touch the store ({name})")

    await UpdateSearch(t, NoStore()).schema_check()
    assert t.calls == []


async def test_warnings_are_logged_without_secrets_or_queries(caplog):
    s = good_schema()
    del s["properties"]["category"]
    with caplog.at_level(logging.WARNING):
        w = await warnings_for(s)
    assert any("category" in r.getMessage() for r in caplog.records if r.levelno == logging.WARNING)
    assert w and "x-api-key" not in caplog.text


async def test_the_listing_is_not_modified():
    s = good_schema()
    before = copy.deepcopy(s)
    await warnings_for(s)
    assert s == before
