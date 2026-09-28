from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "analyze_laya_noul_veto_v4.py"


def _module():
    spec = importlib.util.spec_from_file_location(
        "analyze_laya_noul_veto_v4",
        SCRIPT,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load pinned Laya noul diagnostic")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_laya_noul_threshold_grid_is_frozen() -> None:
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


def test_laya_hub_revision_is_pinned() -> None:
    module = _module()
    assert module.LAYA_HUB_REPO == "convaiinnovations/laya"
    assert (
        module.LAYA_HUB_REVISION
        == "458d7563c5cab85ff9f7f6e06cf2dd166fb697e2"
    )
    assert module.LAYA_PACKAGE_VERSION == "0.3.11"


def test_noul_question_is_veto_only_capability_language() -> None:
    module = _module()
    q = module._question("Registered endpoint: weather.current")
    assert set(q) == {"supported"}
    payload = q["supported"]
    assert payload["type"] == "noul"
    assert "fully execute" in payload["instructions"]
    assert "not topical similarity" in payload["instructions"]
    assert "Do not infer capabilities" in payload["instructions"]
    assert set(payload["criteria"]) == {"true", "false"}


def test_threshold_metrics_use_full_denominators() -> None:
    module = _module()
    rows = [
        {
            "expected": "weather.current",
            "raw_correct": True,
            "category": "v4_supported_natural",
            "language": "en",
        },
        {
            "expected": "weather.forecast",
            "raw_correct": False,
            "category": "v4_supported_natural",
            "language": "en",
        },
        {
            "expected": None,
            "raw_correct": False,
            "category": "near_domain_unsupported_operation",
            "language": "en",
        },
        {
            "expected": None,
            "raw_correct": False,
            "category": "out_of_domain",
            "language": "en",
        },
    ]
    result = module._evaluate_threshold(rows, [0.99, 0.99, 0.01, 0.01], 0.90)
    assert result["supported_exact_route_accuracy"] == 0.5
    assert result["wrong_supported_accepted"] == 1
    assert result["near_domain_unsupported_rejection"] == 1.0
    assert result["out_of_domain_rejection"] == 1.0
    assert result["false_routes"] == 0
