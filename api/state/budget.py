"""The worst case one run reserves (T3.4; contract §4.E): every figure from api/settings.py and the price table."""

from api import settings
from api.state.prices import PRICE_TABLE, list_price_exa

_PER_M = 1_000_000


def worst_case_components() -> dict[str, float]:
    """The six parts of the worst case, in dollars (T3.4: 0.943, 0.08, 0.36, 0.24, 0.021, 0.03).

    Every attempt counts toward the run's token ceiling (T3.3), so retries never raise the loop's parts.
    """
    loop = PRICE_TABLE["anthropic"]["models"][str(settings.LOOP_MODEL.value)]
    comp = PRICE_TABLE["anthropic"]["models"][str(settings.COMPOSITION_MODEL.value)]
    prefix = int(settings.FIXED_PREFIX_TOKENS_ESTIMATE.value)
    loop_in = int(settings.LOOP_INPUT_BUDGET.value)
    reserve_in = int(settings.COMPOSITION_RESERVE_INPUT.value)
    parts = {
        # the fixed prefix at the 1-hour cache-write price, the rest of the loop's input at the 5-minute one
        "loop_input": (prefix * loop["cache_write_1h"] + (loop_in - prefix) * loop["cache_write_5m"]) / _PER_M,
        "loop_output": int(settings.LOOP_OUTPUT_BUDGET.value) * loop["output"] / _PER_M,
        # composition: uncached input plus the most it may write
        "composition": (reserve_in * comp["input"] + int(settings.COMPOSITION_MAX_TOKENS.value) * comp["output"]) / _PER_M,
        # two composition attempts that fail before their first block still bill their input (T1.11, T3.3)
        "composition_retries": 2 * reserve_in * comp["input"] / _PER_M,
        "exa": int(settings.UPDATE_SEARCHES_PER_RUN.value) * list_price_exa("auto"),
        "voyage": float(settings.VOYAGE_RUN_BOUND_USD.value),
    }
    return {k: round(v, 9) for k, v in parts.items()}


def worst_case_usd() -> float:
    """What a run reserves before it starts: about $1.674 (T3.4)."""
    return round(sum(worst_case_components().values()), 6)
