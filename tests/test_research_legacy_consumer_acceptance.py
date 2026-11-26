"""Run the preserved historical scenarios only from a source checkout."""
from __future__ import annotations

import asyncio

import pytest

from scripts.research_legacy_consumer_acceptance import LEGACY_SCENARIOS


@pytest.mark.parametrize(("name", "scenario"), LEGACY_SCENARIOS)
def test_historical_lexical_consumer_scenario(name, scenario):
    assert name
    assert asyncio.run(scenario())
