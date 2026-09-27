from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "analyze_gte_winner_bge_rejector_v4.py"


def _module():
    spec = importlib.util.spec_from_file_location(
        "analyze_gte_winner_bge_rejector_v4",
        SCRIPT,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load GTE winner BGE rejector diagnostic")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_sigmoid_is_bounded() -> None:
    module = _module()
    assert 0.0 < module._sigmoid(-100.0) < 0.5
    assert module._sigmoid(0.0) == 0.5
    assert 0.5 < module._sigmoid(100.0) < 1.0


def test_project_preserves_full_population_denominators() -> None:
    module = _module()
    rows = [
        {
            "expected": "tool.a",
            "category": "supported",
            "selected_route": "tool.a",
            "gte_margin": 0.1,
            "bge_score": 0.9,
        },
        {
            "expected": "tool.a",
            "category": "supported",
            "selected_route": "tool.a",
            "gte_margin": 0.01,
            "bge_score": 0.9,
        },
        {
            "expected": None,
            "category": "near_domain_unsupported_operation",
            "selected_route": "tool.a",
            "gte_margin": 0.1,
            "bge_score": 0.2,
        },
        {
            "expected": None,
            "category": "out_of_domain",
            "selected_route": "tool.a",
            "gte_margin": 0.1,
            "bge_score": 0.2,
        },
    ]
    projected = module._project(
        rows,
        margin_guard=0.05,
        thresholds={"tool.a": 0.5},
    )
    assert projected["supported_exact_route_accuracy"] == 0.5
    assert projected["near_domain_unsupported_rejection"] == 1.0
    assert projected["out_of_domain_rejection"] == 1.0
    assert projected["false_routes"] == 0


def test_optimizer_respects_false_budget() -> None:
    module = _module()
    rows = [
        {
            "expected": "tool.a",
            "selected_route": "tool.a",
            "gte_margin": 0.1,
            "bge_score": 0.9,
        },
        {
            "expected": None,
            "selected_route": "tool.a",
            "gte_margin": 0.1,
            "bge_score": 0.7,
        },
        {
            "expected": "tool.b",
            "selected_route": "tool.b",
            "gte_margin": 0.1,
            "bge_score": 0.8,
        },
    ]
    solution = module._optimize(
        rows,
        routes=["tool.a", "tool.b"],
        margin_guard=0.0,
        false_budget=0,
    )
    assert solution["false_routes"] == 0
    assert solution["supported_correct"] == 2
