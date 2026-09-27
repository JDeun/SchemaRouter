from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "analyze_robust_2d_rescue_v4.py"


def _module():
    spec = importlib.util.spec_from_file_location(
        "analyze_robust_2d_rescue_v4",
        SCRIPT,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load 2D rescue diagnostic")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _row(
    case_id: str,
    *,
    expected: str | None,
    route: str,
    accepted: bool,
    validator: float,
    top_score: float,
    category: str,
) -> dict[str, object]:
    return {
        "case_id": case_id,
        "expected": expected,
        "top_route": route,
        "base_accepted": accepted,
        "validator_score": validator,
        "base_top_score": top_score,
        "base_top_margin": 0.1,
        "category": category,
    }


def test_score_deficit_is_runtime_feature_only() -> None:
    module = _module()
    rows = [
        _row(
            "a",
            expected="calendar.create",
            route="calendar.create",
            accepted=False,
            validator=0.5,
            top_score=0.50,
            category="v4_supported_natural",
        )
    ]
    module._decorate_score_deficit(rows)
    assert rows[0]["score_deficit"] > 0.0
    assert rows[0]["base_min_score"] > rows[0]["base_top_score"]


def test_2d_zero_false_rule_can_separate_close_supported_case() -> None:
    module = _module()
    rows = [
        {
            "case_id": "true",
            "expected": "calendar.create",
            "top_route": "calendar.create",
            "base_accepted": False,
            "validator_score": 0.9,
            "score_deficit": 0.01,
            "category": "v4_supported_natural",
        },
        {
            "case_id": "false",
            "expected": None,
            "top_route": "calendar.create",
            "base_accepted": False,
            "validator_score": 0.95,
            "score_deficit": 0.10,
            "category": "near_domain_unsupported_operation",
        },
    ]
    options = module._route_2d_options(rows, "calendar.create")
    assert any(
        option["additional_supported_correct"] == 1
        and option["additional_false_routes"] == 0
        for option in options
    )


def test_composed_2d_rescue_never_changes_base_accepts() -> None:
    module = _module()
    rows = [
        {
            "case_id": "base-wrong",
            "expected": "calendar.list",
            "top_route": "calendar.create",
            "base_accepted": True,
            "validator_score": None,
            "score_deficit": 0.0,
            "category": "v4_supported_natural",
        },
        {
            "case_id": "rescue-correct",
            "expected": "calendar.create",
            "top_route": "calendar.create",
            "base_accepted": False,
            "validator_score": 0.9,
            "score_deficit": 0.01,
            "category": "v4_supported_natural",
        },
        {
            "case_id": "near",
            "expected": None,
            "top_route": "calendar.create",
            "base_accepted": False,
            "validator_score": 0.8,
            "score_deficit": 0.20,
            "category": "near_domain_unsupported_operation",
        },
    ]
    metrics = module._compose_2d_metrics(
        rows,
        {
            "calendar.create": {
                "min_validator_score": 0.85,
                "max_score_deficit": 0.05,
            }
        },
    )
    assert metrics["supported_correct"] == 1
    assert metrics["wrong_supported"] == 1
    assert metrics["false_routes"] == 0
