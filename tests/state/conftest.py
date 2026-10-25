"""E's money tests were written around a $10 daily cap: five runs at $1.674, a $10.074 refusal, and so on. They test
how the caps work, not the cap's value, so they keep that figure. The live value ($15, P4.11) is asserted in
test_budget.py."""

import pytest

from api import settings


@pytest.fixture(autouse=True)
def the_daily_cap_these_tests_were_written_for(monkeypatch):
    monkeypatch.setattr(settings, "DAILY_CAP_USD", settings.Setting(10.0, "test: the cap E's tests were written for"))
