"""Fixtures for part C's tests."""

import pytest

from tests.search.support import FakeContext, make_passage, recording_sleep


@pytest.fixture
def passages():
    return [make_passage(i) for i in range(1, 9)]


@pytest.fixture
def ctx():
    return FakeContext()


@pytest.fixture
def sleeps():
    return recording_sleep()
