"""The documented worst case of one run (P4.21; contract §4.E): every figure from api/settings.py and the price table.

A documented figure, never a gate. Nothing here admits, refuses or stops a run: `MongoStore.admit` looks only at the
spend so far (the caps), and runs in progress always finish. The worst case exists so that the overrun past a cap is
a number that can be read and tested: `MAX_CONCURRENT_RUNS` runs in progress when a cap is reached can take at most
`MAX_CONCURRENT_RUNS * worst_case_usd()` more before they finish (about $55.81). The figure assumes one instance
(`API_MAX_INSTANCES` 1; a revision rollover can briefly run two). The outer backstop is the Console's monthly limit on
the live workspace (T3.4), outside our code.

Every input token is priced as a fresh 5-minute cache write, except the composition's, which is uncached, and every
limit is reached. Two things are not modelled: the system prompt's single 1-hour write (about $0.02 more), and
thinking that a broken research or update attempt never streamed (billed, but not counted against the budgets, P4.5).
"""

from api import settings
from api.state.prices import PRICE_TABLE, list_price_exa

_PER_M = 1_000_000


def _prices(model_setting: settings.Setting) -> dict:
    return PRICE_TABLE["anthropic"]["models"][str(model_setting.value)]


def composition_attempts() -> int:
    """One attempt and `ANTHROPIC_RETRIES` more. An attempt that breaks before its first block is retried (T3.3) and its
    thinking is billed as output (P4.10), so every attempt can bill both its input and its output."""
    return 1 + int(settings.ANTHROPIC_RETRIES.value)


def worst_case_components() -> dict[str, float]:
    """The eight parts of the documented worst case, in dollars: 5.00, 0.16, 5.00, 0.06, 0.396, 0.48, 0.035, 0.03."""
    research = _prices(settings.LOOP_MODEL)
    update = _prices(settings.UPDATE_MODEL)
    comp = _prices(settings.COMPOSITION_MODEL)
    attempts = composition_attempts()
    parts = {
        "research_input": int(settings.LOOP_INPUT_BUDGET.value) * research["cache_write_5m"] / _PER_M,
        "research_output": int(settings.LOOP_OUTPUT_BUDGET.value) * research["output"] / _PER_M,
        "update_input": int(settings.UPDATE_INPUT_BUDGET.value) * update["cache_write_5m"] / _PER_M,
        "update_output": int(settings.UPDATE_OUTPUT_BUDGET.value) * update["output"] / _PER_M,
        "composition_input": attempts * int(settings.WORST_CASE_COMPOSITION_INPUT.value) * comp["input"] / _PER_M,
        "composition_output": attempts * int(settings.COMPOSITION_MAX_TOKENS.value) * comp["output"] / _PER_M,
        "exa": int(settings.UPDATE_SEARCHES_PER_RUN.value) * list_price_exa("auto"),
        "voyage": float(settings.VOYAGE_RUN_BOUND_USD.value),
    }
    return {k: round(v, 9) for k, v in parts.items()}


def worst_case_usd() -> float:
    """What one run could cost with every limit reached: $11.161 (P4.21, contract §4.E). A documented figure only."""
    return round(sum(worst_case_components().values()), 6)


def concurrent_overrun_usd() -> float:
    """The most `MAX_CONCURRENT_RUNS` runs in progress could take past a cap before they finish: about $55.81."""
    return round(int(settings.MAX_CONCURRENT_RUNS.value) * worst_case_usd(), 6)
