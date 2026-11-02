"""Tests for the dependency-free CrewAI benchmark control."""
import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1] / "examples/external_validation/crewai_mcp_filter"
sys.path.insert(0, str(ROOT))
spec = importlib.util.spec_from_file_location(
    "crewai_benchmark_baselines", ROOT / "benchmark_baselines.py"
)
assert spec is not None and spec.loader is not None
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)


@pytest.mark.parametrize("size", [32, 128, 512])
def test_lexical_baseline_retrieves_required_tool_and_bounds_exposure(size: int) -> None:
    metrics = module.measure(size, repeats=3, limit=8)
    assert metrics["baseline"] == "lexical_control_not_crewai_or_schemarouter"
    assert metrics["required_tool_recall"] == 1
    assert metrics["bounded_exposed_schema_bytes"] < metrics["full_exposed_schema_bytes"]
    assert metrics["selection_latency_p50_ms"] >= 0


def test_unsupported_query_abstains() -> None:
    tools = module.public_catalog(32)
    assert module.lexical_select("unrelated quantum banana", tools, limit=8) == []


def test_nonpositive_limit_is_rejected() -> None:
    with pytest.raises(ValueError):
        module.lexical_select("weather", module.public_catalog(32), limit=0)
