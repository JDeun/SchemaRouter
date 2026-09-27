from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

from schemarouter import PairwiseDecisionBackend, SchemaPlanner

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "benchmark_decision_routing.py"


def _module():
    spec = importlib.util.spec_from_file_location(
        "benchmark_decision_routing_v4",
        SCRIPT,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load decision-routing benchmark")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.mark.asyncio
async def test_benchmark_records_operation_fit_score_geometry() -> None:
    module = _module()

    def score(pairs: list[tuple[str, str]]) -> list[float]:
        return [
            0.85 if option_text.splitlines()[0] == "search" else 0.20
            for _query, option_text in pairs
        ]

    recorder = module.RecordingDecisionBackend(
        PairwiseDecisionBackend(
            score,
            min_score=0.10,
            min_margin=0.05,
        )
    )
    registry = module.reference_registry()
    planner = SchemaPlanner(
        registry,
        operation_fit_backend=recorder,
    )
    case = module.BenchmarkCase(
        id="telemetry-inventory",
        query="inventory quantity for SKU-101",
        expected="inventory.search",
        category="supported",
        language="en",
    )

    rows = await module.benchmark_planner(
        "operation-fit-test",
        planner,
        [case],
        allowed_routes={
            f"{tool.key}.{endpoint.name}"
            for tool in registry.tools()
            for endpoint in tool.endpoints
        },
        operation_fit_recorder=recorder,
    )

    row = rows[0]
    assert row.operation_fit_invoked is True
    assert row.operation_fit_surface == "operation_capability_fit"
    assert row.operation_fit_top_option_id == "inventory.search"
    assert row.operation_fit_top_score == pytest.approx(0.85)
    assert row.operation_fit_second_score == pytest.approx(0.20)
    assert row.operation_fit_top_margin == pytest.approx(0.65)
    assert row.operation_fit_effective_min_score == pytest.approx(0.10)
    assert row.operation_fit_effective_min_margin == pytest.approx(0.05)
    assert row.operation_fit_abstained is False
    assert row.operation_fit_reason is None


@pytest.mark.asyncio
async def test_benchmark_records_operation_fit_abstention_reason() -> None:
    module = _module()
    recorder = module.RecordingDecisionBackend(
        PairwiseDecisionBackend(
            lambda pairs: [0.05 for _ in pairs],
            min_score=0.10,
        )
    )
    registry = module.reference_registry()
    planner = SchemaPlanner(registry, operation_fit_backend=recorder)
    case = module.BenchmarkCase(
        id="telemetry-unsupported",
        query="delete inventory SKU-101",
        expected=None,
        category="near_domain_unsupported_operation",
        expect_abstain=True,
        language="en",
    )

    rows = await module.benchmark_planner(
        "operation-fit-test",
        planner,
        [case],
        allowed_routes={
            f"{tool.key}.{endpoint.name}"
            for tool in registry.tools()
            for endpoint in tool.endpoints
        },
        operation_fit_recorder=recorder,
    )

    row = rows[0]
    assert row.operation_fit_invoked is True
    assert row.operation_fit_abstained is True
    assert row.operation_fit_reason == "below_min_score"
    assert row.predicted is None
    assert row.correct is True
