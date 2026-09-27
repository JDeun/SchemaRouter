from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "analyze_operation_routing_v4_bounded_rerank.py"


def _module():
    spec = importlib.util.spec_from_file_location(
        "analyze_operation_routing_v4_bounded_rerank",
        SCRIPT,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load bounded rerank analyzer")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _row(
    case_id: str,
    *,
    category: str,
    expected: str | None,
    top: str,
    score: float,
    margin: float,
    language: str = "en",
) -> dict:
    return {
        "backend": "keyword+semantic-recall+operation-fit-all-candidates+accepted-selector",
        "case_id": case_id,
        "category": category,
        "language": language,
        "expected": expected,
        "predicted": top,
        "operation_fit_invoked": True,
        "operation_fit_top_option_id": top,
        "operation_fit_top_score": score,
        "operation_fit_top_margin": margin,
    }


def test_analyzer_computes_raw_ceiling_and_winner_only_frontier() -> None:
    module = _module()
    planner = "keyword+semantic-recall+operation-fit-all-candidates+accepted-selector"
    report = {
        "rows": [
            _row(
                "supported-a",
                category="v4_supported_natural",
                expected="tool.a",
                top="tool.a",
                score=0.8,
                margin=0.4,
            ),
            _row(
                "supported-b-wrong",
                category="v4_supported_natural",
                expected="tool.b",
                top="tool.a",
                score=0.3,
                margin=0.1,
            ),
            _row(
                "near",
                category="near_domain_unsupported_operation",
                expected=None,
                top="tool.a",
                score=0.2,
                margin=0.05,
            ),
            _row(
                "ood",
                category="out_of_domain",
                expected=None,
                top="tool.b",
                score=0.1,
                margin=0.02,
            ),
        ],
        "summary": {
            planner: {
                "category_accuracy": {
                    "v4_supported_natural": 0.5,
                    "near_domain_unsupported_operation": 0.0,
                    "out_of_domain": 0.0,
                },
                "error_taxonomy": {
                    "false_route": 2,
                    "wrong_tool": 1,
                    "wrong_endpoint": 0,
                    "missed_route": 0,
                },
                "invalid_plan_rate": 0.0,
                "errors": 0,
                "mean_latency_ms": 10.0,
                "p95_latency_ms": 12.0,
            }
        },
        "reproducibility": {
            "source_revision": "abc",
            "corpus_sha256": "def",
        },
    }

    result = module.analyze(report)

    assert result["supported_raw_top_correct"] == 1
    assert result["supported_raw_top_exact_rate"] == 0.5
    assert result["zero_threshold_observed"]["false_routes"] == 2
    assert result["zero_threshold_observed"]["canonical_false_route_rate"] == 1.0

    zero_budget = result["winner_only_route_local_frontier"][0]
    assert zero_budget["false_routes"] == 0
    assert zero_budget["supported_correct"] == 1
    assert zero_budget["supported_exact_route_accuracy"] == 0.5
    assert zero_budget["thresholds"]["tool.a"] > 0.2
