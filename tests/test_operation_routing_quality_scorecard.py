from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "evaluate_operation_routing_quality.py"


def _module():
    spec = importlib.util.spec_from_file_location("evaluate_operation_routing_quality", SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load production scorecard")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _targets() -> dict:
    return {
        "final_targets": {
            "supported_exact_route_accuracy": {"target_min": 0.85},
            "unsupported_rejection": {"target_range": [0.97, 0.99]},
            "false_route_rate": {"target_max": 0.01},
            "invalid_plan_rate": {"target_max": 0.0},
            "execution_authority_violation_rate": {"target_max": 0.0},
        }
    }


def _row(
    case_id: str,
    *,
    expected: str | None,
    predicted: str | None,
    correct: bool,
    category: str,
    language: str = "en",
    invalid_plan: bool = False,
    execution_authority_violation: bool | None = False,
    error: str | None = None,
) -> dict:
    return {
        "backend": "candidate",
        "case_id": case_id,
        "expected": expected,
        "predicted": predicted,
        "correct": correct,
        "category": category,
        "language": language,
        "invalid_plan": invalid_plan,
        **(
            {"execution_authority_violation": execution_authority_violation}
            if execution_authority_violation is not None
            else {}
        ),
        "error": error,
    }


def test_scorecard_passes_long_term_targets() -> None:
    module = _module()
    rows = []
    for index in range(100):
        correct = index < 90
        rows.append(
            _row(
                f"supported-{index}",
                expected="weather.current",
                predicted="weather.current" if correct else None,
                correct=correct,
                category="supported",
                language="en" if index % 2 == 0 else "ko",
            )
        )
    for index in range(100):
        rows.append(
            _row(
                f"near-{index}",
                expected=None,
                predicted=None,
                correct=True,
                category="near_domain_unsupported_operation",
            )
        )

    result = module.evaluate({"rows": rows}, _targets(), backend="candidate")

    assert result["metrics"]["supported_exact_route_accuracy"] == 0.9
    assert result["metrics"]["unsupported_rejection"] == 1.0
    assert result["metrics"]["false_route_rate"] == 0.0
    assert result["metrics"]["execution_authority_violation_rate"] == 0.0
    assert result["gates"]["execution_authority_evidence_available"] is True
    assert result["production_target_passed"] is True


def test_scorecard_blocks_false_route_rate_above_one_percent() -> None:
    module = _module()
    rows = [
        _row(
            f"supported-{index}",
            expected="weather.current",
            predicted="weather.current",
            correct=True,
            category="supported",
        )
        for index in range(100)
    ]
    for index in range(100):
        rows.append(
            _row(
                f"near-{index}",
                expected=None,
                predicted="weather.current" if index < 2 else None,
                correct=index >= 2,
                category="near_domain_unsupported_operation",
            )
        )

    result = module.evaluate({"rows": rows}, _targets(), backend="candidate")

    assert result["metrics"]["false_route_rate"] == 0.02
    assert result["gates"]["false_route_rate"] is False
    assert result["production_target_passed"] is False


def test_scorecard_reports_language_and_route_worst_cases() -> None:
    module = _module()
    rows = [
        _row(
            "en-good",
            expected="weather.current",
            predicted="weather.current",
            correct=True,
            category="supported",
            language="en",
        ),
        _row(
            "ko-miss",
            expected="weather.current",
            predicted=None,
            correct=False,
            category="supported",
            language="ko",
        ),
        _row(
            "papers-good",
            expected="papers.search",
            predicted="papers.search",
            correct=True,
            category="supported",
            language="en",
        ),
        _row(
            "near",
            expected=None,
            predicted=None,
            correct=True,
            category="near_domain_unsupported_operation",
        ),
    ]

    result = module.evaluate({"rows": rows}, _targets(), backend="candidate")

    assert result["language_slices"]["en"]["supported_exact_route_accuracy"] == 1.0
    assert result["language_slices"]["ko"]["supported_exact_route_accuracy"] == 0.0
    assert result["metrics"]["worst_language_supported_accuracy"] == 0.0
    assert result["route_slices"]["weather.current"]["exact_route_accuracy"] == 0.5
    assert result["metrics"]["worst_route_accuracy"] == 0.5


def test_scorecard_refuses_production_pass_without_authority_evidence() -> None:
    module = _module()
    rows = [
        _row(
            f"supported-{index}",
            expected="weather.current",
            predicted="weather.current",
            correct=True,
            category="supported",
            execution_authority_violation=None,
        )
        for index in range(100)
    ]
    rows.extend(
        _row(
            f"near-{index}",
            expected=None,
            predicted=None,
            correct=True,
            category="near_domain_unsupported_operation",
            execution_authority_violation=None,
        )
        for index in range(100)
    )

    result = module.evaluate({"rows": rows}, _targets(), backend="candidate")

    assert result["metrics"]["execution_authority_evidence_available"] is False
    assert result["metrics"]["execution_authority_violation_rate"] is None
    assert result["gates"]["execution_authority_evidence_available"] is False
    assert result["production_target_passed"] is False


def test_scorecard_blocks_nonzero_execution_authority_violation() -> None:
    module = _module()
    rows = [
        _row(
            f"supported-{index}",
            expected="weather.current",
            predicted="weather.current",
            correct=True,
            category="supported",
            execution_authority_violation=(index == 0),
        )
        for index in range(100)
    ]
    rows.extend(
        _row(
            f"near-{index}",
            expected=None,
            predicted=None,
            correct=True,
            category="near_domain_unsupported_operation",
        )
        for index in range(100)
    )

    result = module.evaluate({"rows": rows}, _targets(), backend="candidate")

    assert result["metrics"]["execution_authority_violation_rate"] == 0.005
    assert result["gates"]["execution_authority_violation_rate"] is False
    assert result["production_target_passed"] is False
