"""Shared test settings (contract §1): async tests run on anyio's asyncio backend."""

import pytest


@pytest.fixture
def anyio_backend():
    return "asyncio"
