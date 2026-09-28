from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "analyze_laya_direct_routing_v4.py"


def _module():
    spec = importlib.util.spec_from_file_location(
        "analyze_laya_direct_routing_v4",
        SCRIPT,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load Laya direct routing diagnostic")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_direct_laya_threshold_grid_is_frozen() -> None:
    module = _module()
    assert module.ACCEPTANCE_THRESHOLDS == (
        0.50,
        0.70,
        0.80,
        0.90,
        0.95,
        0.98,
        0.99,
        0.995,
    )


def test_direct_laya_exposes_exactly_registered_routes() -> None:
    module = _module()
    options = module.build_options()
    assert len(options) == 16
    assert len({option.id for option in options}) == 16
    assert "weather.current" in {option.id for option in options}
    assert "users.update" in {option.id for option in options}
    assert all(module.SCOPE_RULE in option.description for option in options)


def test_threshold_evaluation_uses_full_supported_and_unsupported_denominators() -> None:
    module = _module()
    rows = [
        {
            "expected": "weather.current",
            "predicted": "weather.current",
            "confidence": 0.99,
            "category": "v4_supported_natural",
            "language": "en",
        },
        {
            "expected": "weather.forecast",
            "predicted": "weather.current",
            "confidence": 0.99,
            "category": "v4_supported_natural",
            "language": "en",
        },
        {
            "expected": None,
            "predicted": "weather.current",
            "confidence": 0.10,
            "category": "near_domain_unsupported_operation",
            "language": "en",
        },
        {
            "expected": None,
            "predicted": "weather.current",
            "confidence": 0.10,
            "category": "out_of_domain",
            "language": "en",
        },
    ]

    result = module._evaluate_threshold(rows, 0.90)

    assert result["supported_exact_route_accuracy"] == 0.5
    assert result["wrong_supported_accepted"] == 1
    assert result["near_domain_unsupported_rejection"] == 1.0
    assert result["out_of_domain_rejection"] == 1.0
    assert result["false_routes"] == 0
