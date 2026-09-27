from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "analyze_dual_negative_openworld_v4.py"


def _module():
    spec = importlib.util.spec_from_file_location(
        "analyze_dual_negative_openworld_v4",
        SCRIPT,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load dual negative open-world diagnostic")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _row(
    *,
    expected: str | None,
    route: str,
    category: str,
    negative_score: float,
    negative_advantage: float,
    background_score: float,
    background_advantage: float,
) -> dict[str, object]:
    return {
        "expected": expected,
        "raw_top_route": route,
        "raw_correct": expected == route,
        "category": category,
        "language": "en",
        "unsupported_family": (
            "weather.family_1"
            if category == "near_domain_unsupported_operation"
            else None
        ),
        "max_negative_score": negative_score,
        "negative_advantage": negative_advantage,
        "max_background_score": background_score,
        "background_advantage": background_advantage,
    }


def test_frozen_negative_and_background_banks() -> None:
    module = _module()
    assert len(module.DOMAIN_ANCHORS) == 8
    assert set(module.DOMAIN_ANCHORS) == set(
        module.NEGATIVE_CAPABILITY_PROTOTYPES
    )
    assert all(
        len(values) == 4
        for values in module.NEGATIVE_CAPABILITY_PROTOTYPES.values()
    )
    assert len(module.BACKGROUND_PROTOTYPES) == 16
    assert len(set(module.BACKGROUND_PROTOTYPES)) == 16


def test_preregistered_grid_has_1764_rules() -> None:
    module = _module()
    count = (
        len(module.NEGATIVE_MIN_THRESHOLDS)
        * len(module.NEGATIVE_ADVANTAGE_THRESHOLDS)
        * len(module.BACKGROUND_MIN_THRESHOLDS)
        * len(module.BACKGROUND_ADVANTAGE_THRESHOLDS)
    )
    assert count == 1764


def test_near_negative_evidence_is_veto_only() -> None:
    module = _module()
    row = _row(
        expected="weather.current",
        route="weather.current",
        category="v4_supported_natural",
        negative_score=0.8,
        negative_advantage=0.2,
        background_score=0.2,
        background_advantage=-0.2,
    )
    result = module._apply_rule(
        row,
        negative_min=0.5,
        negative_advantage_min=0.1,
        background_min=0.5,
        background_advantage_min=0.1,
    )
    assert result["negative_veto"] is True
    assert result["background_veto"] is False
    assert result["predicted"] is None


def test_background_evidence_is_veto_only() -> None:
    module = _module()
    row = _row(
        expected=None,
        route="weather.current",
        category="out_of_domain",
        negative_score=0.2,
        negative_advantage=-0.2,
        background_score=0.8,
        background_advantage=0.3,
    )
    result = module._apply_rule(
        row,
        negative_min=0.5,
        negative_advantage_min=0.1,
        background_min=0.5,
        background_advantage_min=0.1,
    )
    assert result["negative_veto"] is False
    assert result["background_veto"] is True
    assert result["predicted"] is None


def test_rule_metrics_keep_complete_population_denominators() -> None:
    module = _module()
    rows = [
        _row(
            expected="weather.current",
            route="weather.current",
            category="v4_supported_natural",
            negative_score=0.1,
            negative_advantage=-0.2,
            background_score=0.1,
            background_advantage=-0.2,
        ),
        _row(
            expected="weather.current",
            route="weather.current",
            category="v4_supported_natural",
            negative_score=0.8,
            negative_advantage=0.3,
            background_score=0.1,
            background_advantage=-0.2,
        ),
        _row(
            expected=None,
            route="weather.current",
            category="near_domain_unsupported_operation",
            negative_score=0.8,
            negative_advantage=0.3,
            background_score=0.1,
            background_advantage=-0.2,
        ),
        _row(
            expected=None,
            route="weather.current",
            category="out_of_domain",
            negative_score=0.1,
            negative_advantage=-0.2,
            background_score=0.8,
            background_advantage=0.3,
        ),
    ]
    metrics = module._evaluate_rule(
        rows,
        negative_min=0.5,
        negative_advantage_min=0.1,
        background_min=0.5,
        background_advantage_min=0.1,
    )
    assert metrics["supported_exact_route_accuracy"] == 0.5
    assert metrics["near_domain_unsupported_rejection"] == 1.0
    assert metrics["out_of_domain_rejection"] == 1.0
    assert metrics["false_routes"] == 0
