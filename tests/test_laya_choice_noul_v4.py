from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "analyze_laya_choice_noul_v4.py"


def _module():
    spec = importlib.util.spec_from_file_location(
        "analyze_laya_choice_noul_v4",
        SCRIPT,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load Laya choice+noul diagnostic")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_choice_noul_protocol_is_frozen() -> None:
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
    assert "fully execute" in module.CHOICE_INSTRUCTIONS
    assert "Do not infer unlisted" in module.CHOICE_INSTRUCTIONS
    assert "At least one registered endpoint" in module.NOUL_INSTRUCTIONS


def test_catalog_contains_only_registered_capability_metadata() -> None:
    module = _module()
    catalog, criteria = module.build_catalog()
    assert len(catalog) == 16
    assert set(criteria) == {item["id"] for item in catalog}
    assert "weather.current" in criteria
    assert "users.update" in criteria
    for item in catalog:
        assert set(item) == {
            "id",
            "tool_scope",
            "endpoint_capability",
            "operation_aliases",
        }
    payload = repr(catalog)
    for forbidden in (
        "expected",
        "unsupported_family",
        "language",
        "case_id",
        "category",
    ):
        assert forbidden not in payload


def test_questions_keep_choice_and_noul_separate() -> None:
    module = _module()
    _, criteria = module.build_catalog()
    questions = module.build_questions(criteria)
    assert questions["selection"]["type"] == "choice"
    assert questions["selection"]["criteria"] == criteria
    assert questions["capable"]["type"] == "noul"
    assert "criteria" not in questions["capable"]


def test_noul_threshold_controls_acceptance_not_choice_confidence() -> None:
    module = _module()
    rows = [
        {
            "expected": "weather.current",
            "predicted": "weather.current",
            "choice_confidence": 0.01,
            "p_capable": 0.99,
            "category": "v4_supported_natural",
            "language": "en",
            "unsupported_family": None,
        },
        {
            "expected": "weather.forecast",
            "predicted": "weather.current",
            "choice_confidence": 0.99,
            "p_capable": 0.99,
            "category": "v4_supported_natural",
            "language": "en",
            "unsupported_family": None,
        },
        {
            "expected": None,
            "predicted": "weather.current",
            "choice_confidence": 0.99,
            "p_capable": 0.10,
            "category": "near_domain_unsupported_operation",
            "language": "en",
            "unsupported_family": "weather.family_1",
        },
        {
            "expected": None,
            "predicted": "weather.current",
            "choice_confidence": 0.99,
            "p_capable": 0.10,
            "category": "out_of_domain",
            "language": "en",
            "unsupported_family": None,
        },
    ]

    result = module._evaluate_threshold(rows, 0.90)

    assert result["supported_exact_route_accuracy"] == 0.5
    assert result["wrong_supported_accepted"] == 1
    assert result["near_domain_unsupported_rejection"] == 1.0
    assert result["out_of_domain_rejection"] == 1.0
    assert result["false_routes"] == 0
    assert result["per_language"]["en"]["unsupported_rejection"] == 1.0
    assert (
        result["unsupported_family_rejection"]["weather.family_1"][
            "rejection_rate"
        ]
        == 1.0
    )
