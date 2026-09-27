from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "analyze_oof_learned_verifier_v4.py"


def _module():
    spec = importlib.util.spec_from_file_location(
        "analyze_oof_learned_verifier_v4",
        SCRIPT,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load OOF learned verifier diagnostic")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _row(
    *,
    expected: str | None,
    route: str,
    category: str,
    language: str = "en",
    family: str | None = None,
    raw_correct: bool | None = None,
    feature_latency_ms: float = 1.0,
) -> dict[str, object]:
    correct = (
        expected is not None and route == expected
        if raw_correct is None
        else raw_correct
    )
    return {
        "case_id": "case",
        "expected": expected,
        "raw_top_route": route,
        "raw_correct": correct,
        "category": category,
        "language": language,
        "unsupported_family": family,
        "feature_latency_ms": feature_latency_ms,
    }


def test_feature_schema_excludes_labels_and_query_text() -> None:
    module = _module()
    assert len(module.CONTINUOUS_FEATURES) == 19
    assert module.CATEGORICAL_FEATURES == ("raw_top_route",)
    forbidden = {
        "query",
        "case_id",
        "expected",
        "category",
        "language",
        "unsupported_family",
        "verifier_target",
    }
    assert forbidden.isdisjoint(module.CONTINUOUS_FEATURES)
    assert forbidden.isdisjoint(module.CATEGORICAL_FEATURES)


def test_preregistered_rule_grid_has_24_rules() -> None:
    module = _module()
    assert module.CLASSIFIER_NAMES == ("logistic", "hgb")
    assert len(module.ACCEPTANCE_THRESHOLDS) == 12
    assert (
        len(module.CLASSIFIER_NAMES)
        * len(module.ACCEPTANCE_THRESHOLDS)
        == 24
    )


def test_language_groups_are_fixed_and_not_features() -> None:
    module = _module()
    assert module.EXPECTED_LANGUAGES == (
        "de",
        "en",
        "es",
        "ja",
        "ko",
        "mixed",
    )
    assert "language" not in module.CONTINUOUS_FEATURES
    assert "language" not in module.CATEGORICAL_FEATURES


def test_verifier_target_judges_raw_winner_only() -> None:
    module = _module()
    assert module._target("weather.current", "weather.current") == 1
    assert module._target("weather.forecast", "weather.current") == 0
    assert module._target(None, "weather.current") == 0


def test_typed_state_is_match_no_match_or_unknown() -> None:
    module = _module()
    assert module._typed_state(0.95, 0.90) == "match"
    assert module._typed_state(0.05, 0.90) == "no_match"
    assert module._typed_state(0.50, 0.90) == "unknown"


def test_threshold_metrics_preserve_population_denominators() -> None:
    module = _module()
    rows = [
        _row(
            expected="weather.current",
            route="weather.current",
            category="v4_supported_natural",
        ),
        _row(
            expected="weather.forecast",
            route="weather.current",
            category="v4_supported_natural",
            raw_correct=False,
        ),
        _row(
            expected=None,
            route="weather.current",
            category="near_domain_unsupported_operation",
            family="weather.family_1",
        ),
        _row(
            expected=None,
            route="weather.current",
            category="out_of_domain",
        ),
    ]
    probabilities = [0.99, 0.99, 0.01, 0.01]
    prediction_latencies = [0.1, 0.1, 0.1, 0.1]
    metrics = module._evaluate_threshold(
        rows,
        probabilities,
        prediction_latencies,
        classifier_name="logistic",
        threshold=0.90,
    )
    assert metrics["supported_exact_route_accuracy"] == 0.5
    assert metrics["wrong_supported_accepted"] == 1
    assert metrics["near_domain_unsupported_rejection"] == 1.0
    assert metrics["out_of_domain_rejection"] == 1.0
    assert metrics["false_routes"] == 0
    assert metrics["typed_state_counts"] == {
        "match": 2,
        "no_match": 2,
        "unknown": 0,
    }


def test_quality_gate_requires_all_safety_conditions() -> None:
    module = _module()
    rows = []
    probabilities = []
    for index in range(100):
        rows.append(
            _row(
                expected="weather.current",
                route="weather.current",
                category="v4_supported_natural",
            )
        )
        probabilities.append(0.99)
    for index in range(97):
        rows.append(
            _row(
                expected=None,
                route="weather.current",
                category="near_domain_unsupported_operation",
                family="weather.family_1",
            )
        )
        probabilities.append(0.01)
    for index in range(3):
        rows.append(
            _row(
                expected=None,
                route="weather.current",
                category="near_domain_unsupported_operation",
                family="weather.family_1",
            )
        )
        probabilities.append(0.99)
    for index in range(10):
        rows.append(
            _row(
                expected=None,
                route="weather.current",
                category="out_of_domain",
            )
        )
        probabilities.append(0.01)
    prediction_latencies = [0.1] * len(rows)
    metrics = module._evaluate_threshold(
        rows,
        probabilities,
        prediction_latencies,
        classifier_name="logistic",
        threshold=0.90,
    )
    assert metrics["supported_exact_route_accuracy"] == 1.0
    assert metrics["near_domain_unsupported_rejection"] == 0.97
    assert metrics["out_of_domain_rejection"] == 1.0
    assert metrics["false_route_rate"] == 0.03
    assert metrics["quality_gate_pass"] is False
