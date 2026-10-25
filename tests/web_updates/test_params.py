"""Contract §4.D, T2.1: what Claude sets, what our code validates, what is sent to Exa."""

import pytest

from api import settings
from api.errors import ToolInputError
from api.web_updates.params import (
    WebSearchParams,
    fixed_settings,
    params_as_dict,
    parse_params,
    to_exa_arguments,
)


def ok(**kw):
    return parse_params({"query": "geofence warrant", **kw})


# --- defaults and the happy path ------------------------------------------------------------------------------------

def test_minimal_input_takes_the_defaults():
    p = ok()
    assert p == WebSearchParams(
        query="geofence warrant", start_published_date=None, end_published_date=None,
        include_domains=(), exclude_domains=(), category=None, type="auto", num_results=10,
    )


def test_every_field_is_kept():
    p = parse_params({
        "query": "  Chatrie aftermath  ", "start_published_date": "2026-06-29", "end_published_date": "2026-10-01",
        "include_domains": ["supremecourt.gov", "*.uscourts.gov", "www.law.cornell.edu/supct"],
        "exclude_domains": ["example.com"], "category": "news", "type": "lite", "num_results": 5,
    })
    assert p.query == "Chatrie aftermath"
    assert p.start_published_date == "2026-06-29" and p.end_published_date == "2026-10-01"
    assert p.include_domains == ("supremecourt.gov", "*.uscourts.gov", "www.law.cornell.edu/supct")
    assert p.exclude_domains == ("example.com",)
    assert (p.category, p.type, p.num_results) == ("news", "lite", 5)


def test_null_means_unset():
    p = parse_params({"query": "q", "start_published_date": None, "include_domains": None, "category": None,
                      "type": None, "num_results": None})
    assert p.start_published_date is None and p.include_domains == () and p.type == "auto" and p.num_results == 10


def test_params_are_frozen_and_use_tuples():
    p = ok(include_domains=["a.com"])
    assert isinstance(p.include_domains, tuple)
    with pytest.raises(Exception):
        p.query = "other"  # type: ignore[misc]


# --- the query --------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("bad", [None, "", "   ", "\n\t", 5, ["a"]])
def test_query_is_required_and_a_nonempty_string(bad):
    with pytest.raises(ToolInputError) as e:
        parse_params({"query": bad})
    assert "query" in e.value.message


def test_missing_query_is_refused():
    with pytest.raises(ToolInputError) as e:
        parse_params({})
    assert "query" in e.value.message


def test_control_characters_in_the_query_become_spaces():
    assert ok(query="a\x00b\nc").query == "a b c"


# --- dates ------------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("bad", ["2026-6-29", "2026-02-30", "2026-13-01", "June 29, 2026", "20260629", "2026-06-29T00:00:00Z",
                                  "2026-W26-1", "", "  ", 20260629, "2026/06/29"])
@pytest.mark.parametrize("field", ["start_published_date", "end_published_date"])
def test_dates_must_be_yyyy_mm_dd(field, bad):
    with pytest.raises(ToolInputError) as e:
        ok(**{field: bad})
    assert field in e.value.message and "YYYY-MM-DD" in e.value.message


def test_end_before_start_is_refused():
    with pytest.raises(ToolInputError) as e:
        ok(start_published_date="2026-07-01", end_published_date="2026-06-30")
    assert "end_published_date" in e.value.message and "start_published_date" in e.value.message


def test_same_day_window_is_allowed():
    p = ok(start_published_date="2026-07-01", end_published_date="2026-07-01")
    assert p.start_published_date == p.end_published_date == "2026-07-01"


def test_a_leap_day_parses():
    assert ok(start_published_date="2028-02-29").start_published_date == "2028-02-29"


# --- domains ----------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("good", [
    "example.com", "sub.example.co.uk", "*.example.com", "*.gov", "example.com/news", "example.com/a/b-c_d/",
    "Example.COM", "xn--bcher-kva.example", "a-b.example.com/x%20y",
])
def test_valid_domain_forms(good):
    p = ok(include_domains=[good], exclude_domains=[good])
    host, sep, rest = good.partition("/")
    assert p.include_domains == (host.lower() + sep + rest,)


@pytest.mark.parametrize("bad", [
    "https://example.com", "http://example.com/x", "example", "", "  ", "exa mple.com", "example.com?q=1", "example.com#top",
    "example.com:8080", "-example.com", "example-.com", "exa_mple.com", "*example.com", "*.", "*.*.example.com", "a..com",
    ".example.com", "example.com.", "bücher.de", 5, None, "x" * 64 + ".com",
])
def test_invalid_domain_forms_are_refused(bad):
    with pytest.raises(ToolInputError) as e:
        ok(include_domains=["fine.com", bad])
    assert "include_domains" in e.value.message


def test_exclude_domains_are_checked_too():
    with pytest.raises(ToolInputError) as e:
        ok(exclude_domains=["https://nope.com"])
    assert "exclude_domains" in e.value.message


def test_a_bare_string_is_not_a_list():
    with pytest.raises(ToolInputError) as e:
        ok(include_domains="example.com")
    assert "list" in e.value.message and "include_domains" in e.value.message


def test_up_to_the_domain_limit_is_allowed_and_over_is_refused():
    n = int(settings.EXA_DOMAINS_MAX.value)
    names = [f"site{i}.example.com" for i in range(n)]
    assert len(ok(include_domains=names).include_domains) == n
    assert len(ok(exclude_domains=names).exclude_domains) == n
    with pytest.raises(ToolInputError) as e:
        ok(include_domains=names + ["one-more.example.com"])
    assert str(n) in e.value.message and "include_domains" in e.value.message
    with pytest.raises(ToolInputError):
        ok(exclude_domains=names + ["one-more.example.com"])


def test_the_limit_is_per_list():
    n = int(settings.EXA_DOMAINS_MAX.value)
    p = ok(include_domains=[f"a{i}.com" for i in range(n)], exclude_domains=[f"b{i}.com" for i in range(n)])
    assert len(p.include_domains) == len(p.exclude_domains) == n


# --- category and type ------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("good", ["news", "publication"])
def test_allowed_categories(good):
    assert ok(category=good).category == good


@pytest.mark.parametrize("bad", ["company", "people", "pdf", "github", "financial report", "personal site", "News", "", 3])
def test_other_categories_are_refused(bad):
    with pytest.raises(ToolInputError) as e:
        ok(category=bad)
    assert "category" in e.value.message and "news" in e.value.message and "publication" in e.value.message


@pytest.mark.parametrize("good", ["auto", "lite"])
def test_allowed_types(good):
    assert ok(type=good).type == good


@pytest.mark.parametrize("bad", ["fast", "instant", "deep", "deep-reasoning", "deep-lite", "neural", "", "Auto", 1])
def test_other_types_are_refused(bad):
    with pytest.raises(ToolInputError) as e:
        ok(type=bad)
    assert "type" in e.value.message and "auto" in e.value.message and "lite" in e.value.message


# --- num_results ------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("given,expected", [(1, 1), (5, 5), (10, 10), (11, 10), (100, 10), (0, 1), (-4, 1), (7.0, 7), (10**9, 10)])
def test_num_results_is_clamped(given, expected):
    assert ok(num_results=given).num_results == expected


@pytest.mark.parametrize("bad", ["5", 3.5, True, False, [5], float("nan"), float("inf")])
def test_num_results_must_be_a_whole_number(bad):
    with pytest.raises(ToolInputError) as e:
        ok(num_results=bad)
    assert "num_results" in e.value.message


# --- the shape of the input -------------------------------------------------------------------------------------------

def test_unknown_fields_are_refused_by_name():
    with pytest.raises(ToolInputError) as e:
        ok(numResults=5, highlights=True)
    assert "numResults" in e.value.message and "highlights" in e.value.message
    assert "num_results" in e.value.message  # the message lists the fields that exist


@pytest.mark.parametrize("raw", [None, [], "q", 5])
def test_the_input_must_be_an_object(raw):
    with pytest.raises(ToolInputError):
        parse_params(raw)  # type: ignore[arg-type]


def test_every_problem_is_named_in_one_message():
    with pytest.raises(ToolInputError) as e:
        parse_params({"query": "", "start_published_date": "soon", "category": "pdf", "num_results": "many"})
    m = e.value.message
    for name in ("query", "start_published_date", "category", "num_results"):
        assert name in m


def test_the_message_does_not_echo_long_values_in_full():
    with pytest.raises(ToolInputError) as e:
        ok(start_published_date="x" * 5000)
    assert len(e.value.message) < 1500


# --- to_exa_arguments -------------------------------------------------------------------------------------------------

def test_arguments_for_a_minimal_search():
    a = to_exa_arguments(ok())
    assert a == {"query": "geofence warrant", "type": "auto", "numResults": 10,
                 "textMaxCharacters": int(settings.EXA_TEXT_CHARS.value)}


def test_arguments_for_a_full_search_use_exas_names():
    p = parse_params({
        "query": "q", "start_published_date": "2026-06-29", "end_published_date": "2026-09-30",
        "include_domains": ["a.com"], "exclude_domains": ["b.com", "c.com"], "category": "publication", "type": "lite",
        "num_results": 3,
    })
    assert to_exa_arguments(p) == {
        "query": "q", "startPublishedDate": "2026-06-29", "endPublishedDate": "2026-09-30",
        "includeDomains": ["a.com"], "excludeDomains": ["b.com", "c.com"], "category": "publication", "type": "lite",
        "numResults": 3, "textMaxCharacters": int(settings.EXA_TEXT_CHARS.value),
    }


def test_unset_fields_are_omitted_not_sent_as_null():
    a = to_exa_arguments(ok())
    assert all(v is not None for v in a.values())
    for k in ("startPublishedDate", "endPublishedDate", "includeDomains", "excludeDomains", "category"):
        assert k not in a


def test_fixed_settings_are_applied_by_omission_except_the_text_cap():
    a = to_exa_arguments(parse_params({
        "query": "q", "start_published_date": "2026-01-01", "include_domains": ["a.com"], "exclude_domains": ["b.com"],
        "category": "news",
    }))
    forbidden = {"enableHighlights", "highlightsMaxCharacters", "highlightsQuery", "highlightsNumSentences", "highlightsPerUrl",
                 "enableSummary", "summaryQuery", "subpages", "subpageTarget", "maxAgeHours", "livecrawlTimeout", "userLocation",
                 "moderation", "additionalQueries", "includeText", "excludeText", "startCrawlDate", "endCrawlDate",
                 "contextMaxCharacters"}
    assert not (set(a) & forbidden)
    assert a["textMaxCharacters"] == int(settings.EXA_TEXT_CHARS.value)


def test_arguments_never_hold_a_key_or_url():
    assert "x-api-key" not in str(to_exa_arguments(ok()))


def test_arguments_do_not_alias_the_params_lists():
    p = ok(include_domains=["a.com"])
    a = to_exa_arguments(p)
    a["includeDomains"].append("mutated.com")
    assert p.include_domains == ("a.com",)


# --- what the band and the events show --------------------------------------------------------------------------------

def test_params_as_dict_has_every_field_with_unset_ones_null():
    d = params_as_dict(ok())
    assert d == {"query": "geofence warrant", "start_published_date": None, "end_published_date": None,
                 "include_domains": None, "exclude_domains": None, "category": None, "type": "auto", "num_results": 10}


def test_params_as_dict_lists_set_domains():
    d = params_as_dict(ok(include_domains=["a.com"], category="news"))
    assert d["include_domains"] == ["a.com"] and d["category"] == "news"


def test_fixed_settings_state_the_text_cap():
    f = fixed_settings()
    assert f["text_max_characters"] == int(settings.EXA_TEXT_CHARS.value)
    assert f["highlights"] is False and f["summaries"] is False
