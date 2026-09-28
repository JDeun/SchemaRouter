from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "analyze_bge_kev_noul_compose_v4.py"


def _module():
    spec = importlib.util.spec_from_file_location(
        "analyze_bge_kev_noul_compose_v4",
        SCRIPT,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load BGE+Kev composition diagnostic")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_bge_kev_threshold_grid_is_frozen() -> None:
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


def test_rule_uses_bge_correctness_and_kev_support_probability_only() -> None:
    module = _module()
    rows = [
        {
            "expected": "weather.current",
            "raw_correct": True,
            "supported_probability": 0.99,
            "category": "v4_supported_natural",
            "language": "en",
            "unsupported_family": None,
        },
        {
            "expected": "weather.forecast",
            "raw_correct": False,
            "supported_probability": 0.99,
            "category": "v4_supported_natural",
            "language": "en",
            "unsupported_family": None,
        },
        {
            "expected": None,
            "raw_correct": False,
            "supported_probability": 0.01,
            "category": "near_domain_unsupported_operation",
            "language": "en",
            "unsupported_family": "weather.family_1",
        },
        {
            "expected": None,
            "raw_correct": False,
            "supported_probability": 0.01,
            "category": "out_of_domain",
            "language": "en",
            "unsupported_family": None,
        },
    ]

    result = module._evaluate_rule(rows, 0.90)

    assert result["supported_exact_route_accuracy"] == 0.5
    assert result["wrong_supported_accepted"] == 1
    assert result["near_domain_unsupported_rejection"] == 1.0
    assert result["out_of_domain_rejection"] == 1.0
    assert result["false_routes"] == 0


def test_kev_artifact_requires_complete_valid_rows(tmp_path: Path) -> None:
    module = _module()
    path = tmp_path / "analysis.json"
    path.write_text(
        json.dumps(
            {
                "experiment": module.EXPECTED_KEV_EXPERIMENT,
                "rows": [
                    {
                        "case_id": f"case-{index}",
                        "supported_probability": 0.5,
                        "latency_ms": 10.0,
                        "error": None,
                    }
                    for index in range(1800)
                ],
            }
        ),
        encoding="utf-8",
    )

    rows, _ = module._load_kev_rows(path)
    assert len(rows) == 1800

    broken = json.loads(path.read_text(encoding="utf-8"))
    broken["rows"][10]["supported_probability"] = None
    path.write_text(json.dumps(broken), encoding="utf-8")
    with pytest.raises(ValueError, match="supported_probability"):
        module._load_kev_rows(path)


def test_kev_artifact_rejects_wrong_experiment(tmp_path: Path) -> None:
    module = _module()
    path = tmp_path / "analysis.json"
    path.write_text(
        json.dumps({"experiment": "other", "rows": []}),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="experiment mismatch"):
        module._load_kev_rows(path)
