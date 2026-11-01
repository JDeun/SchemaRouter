"""Contract tests for deterministic CrewAI MCP catalog fixture."""
import importlib.util
from pathlib import Path

import pytest

FIXTURE = (
    Path(__file__).resolve().parents[1]
    / "examples/external_validation/crewai_mcp_filter/catalog_fixture.py"
)
spec = importlib.util.spec_from_file_location("crewai_catalog_fixture", FIXTURE)
assert spec is not None and spec.loader is not None
import sys
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)


@pytest.mark.parametrize("size", [32, 128, 512])
def test_catalog_is_deterministic_and_has_unique_names(size: int) -> None:
    first = module.make_catalog(size, seed=17)
    second = module.make_catalog(size, seed=17)
    assert first == second
    assert len(first) == size
    assert len({tool.name for tool in first}) == size
    assert sum(tool.name == "weather_lookup" for tool in first) == 1


@pytest.mark.parametrize("size", [32, 128, 512])
def test_catalog_excludes_denied_and_unavailable_tools(size: int) -> None:
    exposed = module.public_catalog(size)
    names = {tool["name"] for tool in exposed}
    assert len(exposed) == size - 2
    assert "weather_lookup" in names
    assert "private_payroll" not in names
    assert "offline_inventory" not in names
    weather = next(tool for tool in exposed if tool["name"] == "weather_lookup")
    assert weather["inputSchema"]["required"] == ["city"]


@pytest.mark.parametrize("size", [0, 31, 513])
def test_catalog_rejects_unapproved_sizes(size: int) -> None:
    with pytest.raises(ValueError):
        module.make_catalog(size)
