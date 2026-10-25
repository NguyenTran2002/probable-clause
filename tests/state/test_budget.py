"""api/state/budget.py: the worst case a run reserves (T3.4, contract §4.E)."""

import pytest

from api import settings
from api.state import budget
from api.state.budget import worst_case_components, worst_case_usd


def test_worst_case_is_one_dollar_sixty_seven_four_to_the_tenth_of_a_cent():
    assert round(worst_case_usd(), 3) == 1.674
    assert worst_case_usd() == pytest.approx(1.674, abs=1e-9)


def test_each_component_of_the_worst_case():
    c = worst_case_components()
    assert c["loop_input"] == pytest.approx(0.943, abs=1e-9)
    assert c["loop_output"] == pytest.approx(0.08, abs=1e-9)
    assert c["composition"] == pytest.approx(0.36, abs=1e-9)
    assert c["composition_retries"] == pytest.approx(0.24, abs=1e-9)
    assert c["exa"] == pytest.approx(0.021, abs=1e-9)
    assert c["voyage"] == pytest.approx(0.03, abs=1e-9)
    assert set(c) == {"loop_input", "loop_output", "composition", "composition_retries", "exa", "voyage"}


def test_the_total_is_the_sum_of_the_components():
    assert worst_case_usd() == pytest.approx(sum(worst_case_components().values()), abs=1e-9)


def test_loop_input_is_the_fixed_prefix_at_the_1h_write_price_and_the_rest_at_the_5m_write_price():
    # Sonnet: $4 and $2.50 per million
    prefix = settings.FIXED_PREFIX_TOKENS_ESTIMATE.value
    rest = settings.LOOP_INPUT_BUDGET.value - prefix
    assert worst_case_components()["loop_input"] == pytest.approx((prefix * 4.0 + rest * 2.5) / 1e6, abs=1e-9)


def test_composition_is_opus_uncached_input_plus_max_tokens_of_output():
    r, m = settings.COMPOSITION_RESERVE_INPUT.value, settings.COMPOSITION_MAX_TOKENS.value
    assert worst_case_components()["composition"] == pytest.approx((r * 4.0 + m * 20.0) / 1e6, abs=1e-9)
    assert worst_case_components()["composition_retries"] == pytest.approx(2 * r * 4.0 / 1e6, abs=1e-9)


def test_the_worst_case_follows_the_settings(monkeypatch):
    monkeypatch.setattr(settings, "UPDATE_SEARCHES_PER_RUN", settings.Setting(5, "test"))
    assert worst_case_components()["exa"] == pytest.approx(5 * 0.007, abs=1e-9)
    monkeypatch.setattr(settings, "VOYAGE_RUN_BOUND_USD", settings.Setting(0.05, "test"))
    assert worst_case_components()["voyage"] == pytest.approx(0.05, abs=1e-9)


def test_five_runs_fit_in_a_day_and_the_sixth_does_not():
    w = worst_case_usd()
    assert 5 * w <= settings.DAILY_CAP_USD.value < 6 * w   # T3.5: "about five at once at $1.67 within $10"


def test_module_exposes_only_what_the_contract_names():
    assert callable(budget.worst_case_usd)
