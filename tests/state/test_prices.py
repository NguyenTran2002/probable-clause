"""api/state/prices.py: the price table (contract §10, T3.4) and what each service's usage costs."""

import math

import pytest

from api import settings
from api.types import Usage
from api.state.prices import (
    PRICE_TABLE,
    failed_attempt_usage,
    list_price_exa,
    price,
    price_sources,
)

SONNET = "claude-sonnet-5-5"
OPUS = "claude-opus-5-5"
M = 1_000_000


def approx(x):
    return pytest.approx(x, abs=1e-12)


# --- the table ---------------------------------------------------------------------------------------------------

def test_every_provider_has_one_source_and_one_date():
    for provider in ("anthropic", "exa", "voyage"):
        e = PRICE_TABLE[provider]
        assert e["source"] and isinstance(e["source"], str)
        assert len(e["date"]) == 10 and e["date"][4] == "-" and e["date"][7] == "-"  # YYYY-MM-DD, Chicago


def test_anthropic_prices_are_t3_4s():
    m = PRICE_TABLE["anthropic"]["models"]
    assert m[SONNET] == {"input": 2.0, "output": 10.0, "cache_write_5m": 2.5, "cache_write_1h": 4.0, "cache_read": 0.10}
    assert m[OPUS] == {"input": 4.0, "output": 20.0, "cache_write_5m": 5.0, "cache_write_1h": 8.0, "cache_read": 0.20}
    assert PRICE_TABLE["anthropic"]["date"] == "2026-10-24"


def test_exa_list_prices():
    assert list_price_exa("auto") == 0.007
    assert list_price_exa("lite") == 0.004
    assert PRICE_TABLE["exa"]["types"] == {"auto": 0.007, "lite": 0.004}


def test_voyage_prices_confirmed_from_voyages_pricing_page():
    v = PRICE_TABLE["voyage"]
    assert v["confirmed"] is True
    assert v["models"] == {"voyage-law-2": 0.12, "rerank-3": 0.05}
    assert "docs.voyageai.com/docs/pricing" in v["source"] and v["date"] == "2026-10-24"


def test_the_other_providers_are_confirmed():
    assert PRICE_TABLE["anthropic"]["confirmed"] is True
    assert PRICE_TABLE["exa"]["confirmed"] is True


def test_every_model_in_settings_has_a_price():
    for s in (settings.LOOP_MODEL, settings.COMPOSITION_MODEL):
        assert s.value in PRICE_TABLE["anthropic"]["models"]
    for s in (settings.EMBED_MODEL, settings.RERANK_MODEL):
        assert s.value in PRICE_TABLE["voyage"]["models"]


def test_price_sources_has_the_shape_of_the_totals_prices_object():
    # contract §6.2: "prices": {"anthropic": {"source", "date"}, "exa": {...}, "voyage": {...}}
    ps = price_sources()
    assert set(ps) == {"anthropic", "exa", "voyage"}
    for v in ps.values():
        assert set(v) == {"source", "date"}


# --- Anthropic ---------------------------------------------------------------------------------------------------

def test_anthropic_each_field_separately_sonnet():
    assert price(Usage("anthropic", SONNET, input_tokens=M)) == approx(2.0)
    assert price(Usage("anthropic", SONNET, cache_write_5m_tokens=M)) == approx(2.5)
    assert price(Usage("anthropic", SONNET, cache_write_1h_tokens=M)) == approx(4.0)
    assert price(Usage("anthropic", SONNET, cache_read_tokens=M)) == approx(0.10)
    assert price(Usage("anthropic", SONNET, output_tokens=M)) == approx(10.0)


def test_anthropic_each_field_separately_opus():
    assert price(Usage("anthropic", OPUS, input_tokens=M)) == approx(4.0)
    assert price(Usage("anthropic", OPUS, cache_write_5m_tokens=M)) == approx(5.0)
    assert price(Usage("anthropic", OPUS, cache_write_1h_tokens=M)) == approx(8.0)
    assert price(Usage("anthropic", OPUS, cache_read_tokens=M)) == approx(0.20)
    assert price(Usage("anthropic", OPUS, output_tokens=M)) == approx(20.0)


def test_anthropic_fields_add_up():
    u = Usage("anthropic", SONNET, input_tokens=1_000, cache_write_5m_tokens=2_000, cache_write_1h_tokens=12_000,
              cache_read_tokens=100_000, output_tokens=500)
    expected = (1_000 * 2.0 + 2_000 * 2.5 + 12_000 * 4.0 + 100_000 * 0.10 + 500 * 10.0) / M
    assert price(u) == approx(expected)


def test_anthropic_zero_usage_is_free():
    assert price(Usage("anthropic", SONNET)) == 0.0


def test_a_model_prices_only_if_its_id_is_exactly_listed():
    # no prefix matching: a dated snapshot id is priced only if PRICE_TABLE lists it, and none is known yet
    assert set(PRICE_TABLE["anthropic"]["models"]) == {SONNET, OPUS}
    assert set(PRICE_TABLE["voyage"]["models"]) == {"voyage-law-2", "rerank-3"}
    for bad in (SONNET + "-20261001", OPUS + "-20261001", SONNET + "0", SONNET.upper(), " " + SONNET, SONNET + " ",
                "claude-sonnet-5", "claude-sonnet-5-5-latest", "", "claude"):
        with pytest.raises(ValueError):
            price(Usage("anthropic", bad, input_tokens=1))
    for bad in ("voyage-law-2-lite", "voyage-law-2 ", "Voyage-Law-2", "rerank-3-lite", "rerank-3.5"):
        with pytest.raises(ValueError):
            price(Usage("voyage", bad, input_tokens=1))


def test_a_listed_dated_snapshot_would_price_as_listed():
    # when a snapshot id is ever added to the table explicitly, it prices; nothing else does
    snap = SONNET + "-20261001"
    PRICE_TABLE["anthropic"]["models"][snap] = dict(PRICE_TABLE["anthropic"]["models"][SONNET])
    try:
        assert price(Usage("anthropic", snap, input_tokens=M)) == approx(2.0)
    finally:
        del PRICE_TABLE["anthropic"]["models"][snap]
    with pytest.raises(ValueError):
        price(Usage("anthropic", snap, input_tokens=1))


def test_unknown_models_are_refused_not_priced_at_zero():
    with pytest.raises(ValueError):
        price(Usage("anthropic", "claude-unknown-1", input_tokens=1))
    with pytest.raises(ValueError):
        price(Usage("voyage", "voyage-unknown", input_tokens=1))
    with pytest.raises(ValueError):
        price(Usage("exa", "deep"))


# --- Voyage ------------------------------------------------------------------------------------------------------

def test_voyage_is_tokens_times_the_models_price():
    assert price(Usage("voyage", "voyage-law-2", input_tokens=M)) == approx(0.12)
    assert price(Usage("voyage", "rerank-3", input_tokens=M)) == approx(0.05)
    assert price(Usage("voyage", "voyage-law-2", input_tokens=599_096)) == approx(599_096 * 0.12 / M)


def test_voyage_ignores_claude_cache_fields():
    assert price(Usage("voyage", "rerank-3", input_tokens=1000, output_tokens=1000)) == approx(1000 * 0.05 / M)


# --- Exa ---------------------------------------------------------------------------------------------------------

def test_exa_uses_the_reported_cost_when_present():
    assert price(Usage("exa", "auto", exa_cost_usd=0.0123)) == approx(0.0123)
    assert price(Usage("exa", "lite", exa_cost_usd=0.0)) == 0.0   # a reported zero is a report


def test_exa_falls_back_to_list_price_when_unreported():
    assert price(Usage("exa", "auto")) == approx(0.007)
    assert price(Usage("exa", "lite")) == approx(0.004)


def test_a_failed_exa_search_is_priced_at_list_price_t2_4():
    u = failed_attempt_usage("exa", "auto")
    assert u == Usage(service="exa", model="auto", estimated=True)
    assert price(u) == approx(0.007)


def test_list_price_exa_rejects_an_unknown_type():
    with pytest.raises(ValueError):
        list_price_exa("deep")


# --- a failed attempt that reported no usage (T3.3) ----------------------------------------------------------------

def test_failed_claude_attempt_is_its_estimated_input_at_the_uncached_price():
    # T3.3: "an estimate of its input at the uncached price when none was reported"
    u = failed_attempt_usage("anthropic", SONNET, estimated_input_tokens=50_000)
    assert u == Usage("anthropic", SONNET, input_tokens=50_000, estimated=True)
    assert price(u) == approx(50_000 * 2.0 / M)
    u = failed_attempt_usage("anthropic", OPUS, estimated_input_tokens=30_000)
    assert price(u) == approx(30_000 * 4.0 / M)


def test_failed_voyage_attempt_is_its_estimated_tokens_at_the_models_price():
    u = failed_attempt_usage("voyage", "rerank-3", estimated_input_tokens=10_000)
    assert u.estimated and price(u) == approx(10_000 * 0.05 / M)


def test_a_failed_attempt_with_no_estimate_costs_zero_so_callers_must_estimate():
    # price() never invents a token count; the caller (G, C) estimates (T3.3)
    assert price(failed_attempt_usage("anthropic", SONNET)) == 0.0


def test_estimated_flag_does_not_change_the_arithmetic():
    a = Usage("anthropic", SONNET, input_tokens=1234)
    b = Usage("anthropic", SONNET, input_tokens=1234, estimated=True)
    assert price(a) == price(b)


def test_negative_tokens_are_refused():
    with pytest.raises(ValueError):
        price(Usage("anthropic", SONNET, input_tokens=-1))


def test_prices_are_finite_floats():
    p = price(Usage("anthropic", OPUS, input_tokens=3, output_tokens=7))
    assert isinstance(p, float) and math.isfinite(p)
