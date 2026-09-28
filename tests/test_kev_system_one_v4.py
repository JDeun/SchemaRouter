from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "analyze_kev_system_one_v4.py"


def _module():
    spec = importlib.util.spec_from_file_location(
        "analyze_kev_system_one_v4",
        SCRIPT,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load Kev System One diagnostic")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_kev_threshold_grid_is_frozen() -> None:
    module = _module()
    assert module.THRESHOLDS == (
        0.50,
        0.70,
        0.80,
        0.90,
        0.95,
        0.98,
        0.99,
        0.995,
    )


def test_kev_contracts_cover_registered_routes_only() -> None:
    module = _module()
    contracts = module.endpoint_contracts()
    assert len(contracts) == 16
    assert "weather.current" in contracts
    assert "users.update" in contracts
    assert all(module.SCOPE_RULE in value for value in contracts.values())


def test_choice_and_noul_rules_use_full_denominators() -> None:
    module = _module()
    rows = [
        {
            "expected": "weather.current",
            "predicted": "weather.current",
            "choice_confidence": 0.99,
            "supported_probability": 0.99,
            "category": "v4_supported_natural",
            "language": "en",
            "unsupported_family": None,
        },
        {
            "expected": "weather.forecast",
            "predicted": "weather.current",
            "choice_confidence": 0.99,
            "supported_probability": 0.99,
            "category": "v4_supported_natural",
            "language": "en",
            "unsupported_family": None,
        },
        {
            "expected": None,
            "predicted": "weather.current",
            "choice_confidence": 0.10,
            "supported_probability": 0.10,
            "category": "near_domain_unsupported_operation",
            "language": "en",
            "unsupported_family": "weather.family_1",
        },
        {
            "expected": None,
            "predicted": "weather.current",
            "choice_confidence": 0.10,
            "supported_probability": 0.10,
            "category": "out_of_domain",
            "language": "en",
            "unsupported_family": None,
        },
    ]

    for family in ("choice_confidence", "noul_capability"):
        result = module._evaluate_rule(
            rows,
            family=family,
            threshold=0.90,
        )
        assert result["supported_exact_route_accuracy"] == 0.5
        assert result["wrong_supported_accepted"] == 1
        assert result["near_domain_unsupported_rejection"] == 1.0
        assert result["out_of_domain_rejection"] == 1.0
        assert result["false_routes"] == 0


def test_prompts_are_capability_not_similarity_instructions() -> None:
    module = _module()
    assert "Do not infer capabilities" in module.ROUTE_INSTRUCTION
    assert "fully execute" in module.SUPPORTED_INSTRUCTION
    assert "unlisted capability" in module.SUPPORTED_INSTRUCTION
