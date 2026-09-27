from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "analyze_bge_m3_zero_false_rescue_v4.py"


def _module():
    spec = importlib.util.spec_from_file_location(
        "analyze_bge_m3_zero_false_rescue_v4",
        SCRIPT,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load zero-false rescue diagnostic")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _row(
    case_id: str,
    *,
    expected: str | None,
    route: str,
    accepted: bool,
    score: float,
    category: str,
) -> dict[str, object]:
    return {
        "case_id": case_id,
        "expected": expected,
        "top_route": route,
        "base_accepted": accepted,
        "validator_score": score,
        "category": category,
    }


def test_frozen_base_contract_is_exact() -> None:
    module = _module()
    assert module.RANKER_MODEL_NAME == "BAAI/bge-m3"
    assert (
        module.RANKER_MODEL_REVISION
        == "5617a9f61b028005a4858fdac845db406aefb181"
    )
    assert module.SCHEMA_WEIGHT == 0.55
    assert module.ACTION_WEIGHT == 0.45
    assert len(module.BASE_THRESHOLDS) == 16
    assert module.BASE_THRESHOLDS["finance.quote"]["min_margin"] == 0.02
    assert module.BASE_THRESHOLDS["weather.current"]["min_margin"] == 0.02


def test_zero_false_route_local_rescue_recovers_supported_only() -> None:
    module = _module()
    rows = [
        _row(
            "base-correct",
            expected="tool.a",
            route="tool.a",
            accepted=True,
            score=0.0,
            category="v4_supported_natural",
        ),
        _row(
            "rescue-correct",
            expected="tool.a",
            route="tool.a",
            accepted=False,
            score=0.9,
            category="v4_supported_natural",
        ),
        _row(
            "unsupported",
            expected=None,
            route="tool.a",
            accepted=False,
            score=0.2,
            category="near_domain_unsupported_operation",
        ),
        _row(
            "ood",
            expected=None,
            route="tool.b",
            accepted=False,
            score=0.1,
            category="out_of_domain",
        ),
    ]

    solution = module._route_local_frontier(
        rows,
        ["tool.a", "tool.b"],
        false_budget=0,
    )
    assert solution["additional_supported_correct"] == 1
    assert solution["additional_false_routes"] == 0

    metrics = module._compose_metrics(
        rows,
        route_thresholds=solution["thresholds"],
    )
    assert metrics["supported_exact_route_accuracy"] == 1.0
    assert metrics["near_domain_unsupported_rejection"] == 1.0
    assert metrics["out_of_domain_rejection"] == 1.0
    assert metrics["false_routes"] == 0


def test_rescue_never_changes_base_accepted_decision() -> None:
    module = _module()
    rows = [
        _row(
            "accepted-wrong",
            expected="tool.b",
            route="tool.a",
            accepted=True,
            score=0.0,
            category="v4_supported_natural",
        ),
        _row(
            "rejected-correct",
            expected="tool.b",
            route="tool.b",
            accepted=False,
            score=0.9,
            category="v4_supported_natural",
        ),
        _row(
            "near",
            expected=None,
            route="tool.b",
            accepted=False,
            score=0.1,
            category="near_domain_unsupported_operation",
        ),
    ]

    metrics = module._compose_metrics(
        rows,
        global_threshold=0.5,
    )
    assert metrics["supported_correct"] == 1
    assert metrics["wrong_supported"] == 1
    assert metrics["false_routes"] == 0


def test_global_frontier_respects_zero_additional_false_budget() -> None:
    module = _module()
    rows = [
        _row(
            "true",
            expected="tool.a",
            route="tool.a",
            accepted=False,
            score=0.8,
            category="v4_supported_natural",
        ),
        _row(
            "false",
            expected=None,
            route="tool.a",
            accepted=False,
            score=0.7,
            category="near_domain_unsupported_operation",
        ),
    ]
    zero = module._global_frontier(rows, false_budget=0)
    assert zero["additional_supported_correct"] == 1
    assert zero["additional_false_routes"] == 0
    assert zero["threshold"] > 0.7
