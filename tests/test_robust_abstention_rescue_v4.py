from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "analyze_robust_abstention_rescue_v4.py"


def _module():
    spec = importlib.util.spec_from_file_location(
        "analyze_robust_abstention_rescue_v4",
        SCRIPT,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load rescue diagnostic")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_compose_keeps_base_accepts_immutable() -> None:
    module = _module()
    rows = [
        {
            "case_id": "base-ok",
            "expected": "tool.a",
            "category": "supported",
            "base_raw_route": "tool.a",
            "base_accepted": True,
            "gte_agrees": False,
            "gte_top_score": 0.0,
            "gte_margin": 0.0,
            "base_score_deficit": 0.0,
            "base_margin_deficit": 0.0,
            "reranker_score": None,
        },
        {
            "case_id": "rescue-ok",
            "expected": "tool.a",
            "category": "supported",
            "base_raw_route": "tool.a",
            "base_accepted": False,
            "gte_agrees": True,
            "gte_top_score": 0.8,
            "gte_margin": 0.1,
            "base_score_deficit": 0.001,
            "base_margin_deficit": 0.0,
            "reranker_score": None,
        },
        {
            "case_id": "near",
            "expected": None,
            "category": "near_domain_unsupported_operation",
            "base_raw_route": "tool.a",
            "base_accepted": False,
            "gte_agrees": False,
            "gte_top_score": 0.8,
            "gte_margin": 0.1,
            "base_score_deficit": 0.001,
            "base_margin_deficit": 0.0,
            "reranker_score": None,
        },
        {
            "case_id": "ood",
            "expected": None,
            "category": "out_of_domain",
            "base_raw_route": "tool.a",
            "base_accepted": False,
            "gte_agrees": False,
            "gte_top_score": 0.8,
            "gte_margin": 0.1,
            "base_score_deficit": 0.001,
            "base_margin_deficit": 0.0,
            "reranker_score": None,
        },
    ]
    solution = {
        "variant": "gte-agreement",
        "rules": {
            "tool.a": {
                "min_gte_score": 0.7,
                "min_gte_margin": 0.05,
                "max_base_score_deficit": 0.005,
                "max_base_margin_deficit": 0.0,
                "min_reranker_score": None,
            }
        },
    }
    result = module._compose(rows, solution=solution)
    assert result["supported_exact_route_accuracy"] == 1.0
    assert result["near_domain_unsupported_rejection"] == 1.0
    assert result["out_of_domain_rejection"] == 1.0
    assert result["false_routes"] == 0


def test_rule_never_rescues_without_gte_winner_agreement() -> None:
    module = _module()
    row = {
        "gte_agrees": False,
        "base_accepted": False,
        "gte_top_score": 1.0,
        "gte_margin": 1.0,
        "base_score_deficit": 0.0,
        "base_margin_deficit": 0.0,
        "reranker_score": 1.0,
    }
    rule = {
        "min_gte_score": -1.0,
        "min_gte_margin": 0.0,
        "max_base_score_deficit": 1.0,
        "max_base_margin_deficit": 1.0,
        "min_reranker_score": -1.0,
    }
    assert not module._passes_rule(row, rule, "gte-agreement-bge")


def test_optimizer_respects_zero_additional_false_budget() -> None:
    module = _module()
    rows = [
        {
            "base_raw_route": "tool.a",
            "base_accepted": False,
            "gte_agrees": True,
            "gte_top_score": 0.9,
            "gte_margin": 0.1,
            "base_score_deficit": 0.001,
            "base_margin_deficit": 0.0,
            "reranker_score": None,
            "expected": "tool.a",
        },
        {
            "base_raw_route": "tool.a",
            "base_accepted": False,
            "gte_agrees": True,
            "gte_top_score": 0.5,
            "gte_margin": 0.01,
            "base_score_deficit": 0.02,
            "base_margin_deficit": 0.0,
            "reranker_score": None,
            "expected": None,
        },
    ]
    solution = module._optimize(
        rows,
        routes=["tool.a"],
        variant="gte-agreement",
        false_budget=0,
    )
    assert solution["additional_false_routes"] == 0
    assert solution["rescued_correct"] == 1
