from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "analyze_typed_two_view_gate_v4.py"


def _module():
    spec = importlib.util.spec_from_file_location(
        "analyze_typed_two_view_gate_v4",
        SCRIPT,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load typed two-view diagnostic")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_project_keeps_full_population_denominators() -> None:
    module = _module()
    rows = [
        {
            "expected": "tool.a",
            "category": "supported",
            "selected_route": "tool.a",
            "schema_score": 0.9,
            "action_score": 0.9,
            "fused_margin": 0.1,
        },
        {
            "expected": "tool.a",
            "category": "supported",
            "selected_route": "tool.a",
            "schema_score": 0.2,
            "action_score": 0.2,
            "fused_margin": 0.1,
        },
        {
            "expected": None,
            "category": "near_domain_unsupported_operation",
            "selected_route": "tool.a",
            "schema_score": 0.3,
            "action_score": 0.3,
            "fused_margin": 0.1,
        },
        {
            "expected": None,
            "category": "out_of_domain",
            "selected_route": "tool.a",
            "schema_score": 0.1,
            "action_score": 0.1,
            "fused_margin": 0.1,
        },
    ]
    solution = {
        "margin_guard": 0.0,
        "thresholds": {
            "tool.a": {
                "min_schema_score": 0.5,
                "min_action_score": 0.5,
            }
        },
    }
    result = module._project(rows, solution=solution)
    assert result["supported_exact_route_accuracy"] == 0.5
    assert result["near_domain_unsupported_rejection"] == 1.0
    assert result["out_of_domain_rejection"] == 1.0
    assert result["false_routes"] == 0


def test_typed_and_requires_both_views() -> None:
    module = _module()
    rows = [
        {
            "expected": "tool.a",
            "selected_route": "tool.a",
            "schema_score": 0.8,
            "action_score": 0.8,
            "fused_margin": 0.1,
        },
        {
            "expected": None,
            "selected_route": "tool.a",
            "schema_score": 0.8,
            "action_score": 0.2,
            "fused_margin": 0.1,
        },
    ]
    options = module._route_options(
        rows,
        route="tool.a",
        gate_family="typed-and",
        margin_guard=0.0,
    )
    assert any(
        option["supported_correct"] == 1
        and option["false_routes"] == 0
        for option in options
    )


def test_fixed_ranker_weights_match_preregistration() -> None:
    module = _module()
    assert module.SCHEMA_WEIGHT == 0.25
    assert module.ACTION_WEIGHT == 0.75
    assert module.GATE_FAMILIES == (
        "action-only",
        "schema-only",
        "typed-and",
    )
    assert module.MARGIN_GUARDS == (0.0, 0.01, 0.02, 0.05)
