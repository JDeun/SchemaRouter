"""Behavioral contract for CrewAI-compatible bounded filter bridge."""
import importlib.util
import sys
from pathlib import Path

import pytest

PATH = (
    Path(__file__).resolve().parents[1]
    / "examples/external_validation/crewai_mcp_filter/crewai_filter_bridge.py"
)
spec = importlib.util.spec_from_file_location("crewai_filter_bridge", PATH)
assert spec is not None and spec.loader is not None
bridge = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = bridge
spec.loader.exec_module(bridge)


def test_shortlist_intersects_native_policy_and_never_bypasses_denial() -> None:
    calls: list[str] = []

    def policy(context: object, tool: dict[str, object]) -> bool:
        calls.append(str(tool["name"]))
        return tool["name"] != "write_secret"

    filt = bridge.compose_bounded_filter(
        ["weather_lookup", "write_secret"], native_filter=policy
    )
    assert filt(None, {"name": "weather_lookup"})
    assert not filt(None, {"name": "write_secret"})
    assert not filt(None, {"name": "unlisted"})
    assert not filt(None, {})
    assert calls == ["weather_lookup", "write_secret"]


def test_empty_shortlist_abstains_without_invoking_policy() -> None:
    def forbidden(context: object, tool: dict[str, object]) -> bool:
        raise AssertionError("native filter should not be called")

    filt = bridge.compose_bounded_filter([], native_filter=forbidden)
    assert not filt(None, {"name": "weather_lookup"})


def test_selector_rejects_stale_and_duplicate_names() -> None:
    tools = [{"name": "weather_lookup"}]
    with pytest.raises(ValueError):
        bridge.select_names("weather", tools, selector=lambda q, t: ["stale"])
    with pytest.raises(ValueError):
        bridge.select_names("weather", tools, selector=lambda q, t: ["weather_lookup"] * 2)


def test_selector_bounds_current_catalog() -> None:
    tools = [{"name": "weather_lookup"}, {"name": "read_catalog"}]
    names = bridge.select_names(
        "weather", tools, selector=lambda q, t: ["weather_lookup"], limit=1
    )
    assert names == frozenset({"weather_lookup"})
