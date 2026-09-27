from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "analyze_bounded_action_embedding_v4.py"


def _module():
    spec = importlib.util.spec_from_file_location(
        "analyze_bounded_action_embedding_v4",
        SCRIPT,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load bounded action diagnostic")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class _Option:
    label = "create_ticket"
    id = "support.create_ticket"
    description = (
        "create ticket\n"
        "create support ticket\n"
        "open support case\n"
        "Create a customer support ticket"
    )


def test_action_only_option_text_excludes_endpoint_description() -> None:
    module = _module()
    text = module.action_only_option_text(_Option())
    assert text.splitlines() == [
        "create ticket",
        "create support ticket",
        "open support case",
    ]
    assert "customer support" not in text


def test_apply_threshold_map_uses_winner_only_route_local_boundary() -> None:
    module = _module()
    rows = [
        {
            "case_id": "supported-a",
            "expected": "tool.a",
            "category": "v4_supported_natural",
            "top_route": "tool.a",
            "top_score": 0.7,
            "top_margin": 0.2,
        },
        {
            "case_id": "near-a",
            "expected": None,
            "category": "near_domain_unsupported_operation",
            "top_route": "tool.a",
            "top_score": 0.5,
            "top_margin": 0.1,
        },
        {
            "case_id": "ood-b",
            "expected": None,
            "category": "out_of_domain",
            "top_route": "tool.b",
            "top_score": 0.2,
            "top_margin": 0.05,
        },
    ]
    projected = module.apply_threshold_map(
        rows,
        {
            "tool.a": {"min_similarity": 0.6, "min_margin": 0.15},
            "tool.b": {"min_similarity": 0.3, "min_margin": 0.0},
        },
    )
    assert projected["supported_exact_route_accuracy"] == 1.0
    assert projected["near_domain_unsupported_rejection"] == 1.0
    assert projected["out_of_domain_rejection"] == 1.0
    assert projected["false_routes"] == 0


def test_optimizer_respects_false_route_budget() -> None:
    module = _module()
    rows = [
        {
            "operation_fit_invoked": True,
            "top_route": "tool.a",
            "top_score": 0.8,
            "top_margin": 0.2,
            "expected": "tool.a",
        },
        {
            "operation_fit_invoked": True,
            "top_route": "tool.a",
            "top_score": 0.7,
            "top_margin": 0.2,
            "expected": None,
        },
        {
            "operation_fit_invoked": True,
            "top_route": "tool.b",
            "top_score": 0.8,
            "top_margin": 0.2,
            "expected": "tool.b",
        },
    ]
    solution = module.optimize_route_thresholds(
        rows,
        ["tool.a", "tool.b"],
        false_budget=0,
    )
    assert solution["false_routes"] == 0
    assert solution["supported_correct"] == 2
