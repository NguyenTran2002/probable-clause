"""api/state/budget.py: the documented worst case of one run (P4.21, contract §4.E). A figure, never a gate."""

import pytest

from api import settings
from api.state import budget
from api.state.budget import worst_case_components, worst_case_usd

DAILY_CAP = settings.DAILY_CAP_USD     # the live value, read before tests/state/conftest.py pins $10 for E's tests


def test_the_documented_worst_case_is_eleven_dollars_one_sixty_one():
    assert worst_case_usd() == pytest.approx(11.161, abs=1e-9)
    assert round(worst_case_usd(), 3) == 11.161


def test_each_component_of_the_worst_case():
    c = worst_case_components()
    assert c["research_input"] == pytest.approx(5.0, abs=1e-9)          # 2,000,000 at the 5-minute write price, $2.50/M
    assert c["research_output"] == pytest.approx(0.16, abs=1e-9)        # 16,000 at $10/M
    assert c["update_input"] == pytest.approx(5.0, abs=1e-9)
    assert c["update_output"] == pytest.approx(0.06, abs=1e-9)          # 6,000 at $10/M
    assert c["composition_input"] == pytest.approx(0.396, abs=1e-9)     # 3 x 66,000 uncached, $2/M
    assert c["composition_output"] == pytest.approx(0.48, abs=1e-9)     # 3 x 16,000 at $10/M
    assert c["exa"] == pytest.approx(0.035, abs=1e-9)                   # 5 x $0.007
    assert c["voyage"] == pytest.approx(0.03, abs=1e-9)
    assert set(c) == {"research_input", "research_output", "update_input", "update_output", "composition_input",
                      "composition_output", "exa", "voyage"}


def test_the_total_is_the_sum_of_the_components():
    assert worst_case_usd() == pytest.approx(sum(worst_case_components().values()), abs=1e-9)


def test_the_figures_come_from_settings_and_prices_not_from_the_code():
    # Sonnet 5.5: $2 input, $10 output, $2.50 five-minute write (contract §10)
    s = settings
    assert worst_case_components()["research_input"] == pytest.approx(s.LOOP_INPUT_BUDGET.value * 2.5 / 1e6, abs=1e-9)
    assert worst_case_components()["update_input"] == pytest.approx(s.UPDATE_INPUT_BUDGET.value * 2.5 / 1e6, abs=1e-9)
    assert worst_case_components()["composition_input"] == pytest.approx(
        3 * s.WORST_CASE_COMPOSITION_INPUT.value * 2.0 / 1e6, abs=1e-9)
    assert worst_case_components()["composition_output"] == pytest.approx(
        3 * s.COMPOSITION_MAX_TOKENS.value * 10.0 / 1e6, abs=1e-9)
    assert budget.composition_attempts() == 3 == 1 + s.ANTHROPIC_RETRIES.value


def test_the_worst_case_follows_the_settings(monkeypatch):
    monkeypatch.setattr(settings, "UPDATE_SEARCHES_PER_RUN", settings.Setting(8, "test"))
    assert worst_case_components()["exa"] == pytest.approx(8 * 0.007, abs=1e-9)
    monkeypatch.setattr(settings, "VOYAGE_RUN_BOUND_USD", settings.Setting(0.05, "test"))
    assert worst_case_components()["voyage"] == pytest.approx(0.05, abs=1e-9)
    monkeypatch.setattr(settings, "UPDATE_INPUT_BUDGET", settings.Setting(1_200_000, "test"))
    assert worst_case_components()["update_input"] == pytest.approx(3.0, abs=1e-9)
    monkeypatch.setattr(settings, "ANTHROPIC_RETRIES", settings.Setting(1, "test"))
    assert worst_case_components()["composition_output"] == pytest.approx(2 * 16_000 * 10.0 / 1e6, abs=1e-9)


def test_each_step_is_priced_at_its_own_model(monkeypatch):
    monkeypatch.setattr(settings, "COMPOSITION_MODEL", settings.Setting("claude-opus-5-5", "test"))
    c = worst_case_components()
    assert c["composition_input"] == pytest.approx(3 * 66_000 * 4.0 / 1e6, abs=1e-9)       # Opus: $4/M uncached
    assert c["composition_output"] == pytest.approx(3 * 16_000 * 20.0 / 1e6, abs=1e-9)     # Opus: $20/M
    assert c["research_input"] == pytest.approx(5.0, abs=1e-9)                              # research still Sonnet


def test_the_overrun_past_a_cap_is_the_concurrent_runs_times_the_worst_case():
    # five runs in progress when a cap is reached: about $55.81 before they finish (contract §4.E)
    assert settings.MAX_CONCURRENT_RUNS.value == 5
    assert budget.concurrent_overrun_usd() == pytest.approx(55.805, abs=1e-9)


def test_the_live_daily_cap_is_fifteen_dollars():
    assert DAILY_CAP.value == 15.0 and settings.MONTHLY_CAP_USD.value == 60.0


def test_the_worst_case_is_not_a_gate():
    # nothing in the store takes a worst case: admission looks only at the spend so far
    import inspect
    from api.protocols import Store
    assert list(inspect.signature(Store.admit).parameters) == ["self", "run_id", "now"]
    assert not hasattr(budget, "reserve")
