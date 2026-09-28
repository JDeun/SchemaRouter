from __future__ import annotations

import importlib.util
from copy import deepcopy
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "validate_routing_runtime_parity.py"


def _module():
    spec = importlib.util.spec_from_file_location(
        "validate_routing_runtime_parity",
        SCRIPT,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load runtime parity validator")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _analysis() -> dict:
    return {
        "summary": {
            "execution_errors": 0,
            "authority_violations": 0,
        },
        "rows": [
            {
                "case_id": "a",
                "predicted": "weather.current",
                "supported_probability": 0.99,
                "error": None,
            },
            {
                "case_id": "b",
                "predicted": "weather.forecast",
                "supported_probability": 0.20,
                "error": None,
            },
        ],
    }


def test_runtime_parity_accepts_probability_drift_without_decision_drift() -> None:
    module = _module()
    reference = _analysis()
    candidate = deepcopy(reference)
    candidate["rows"][0]["supported_probability"] = 0.97
    candidate["rows"][1]["supported_probability"] = 0.10

    result = module.validate_runtime_parity(
        reference,
        candidate,
        route_field="predicted",
        score_field="supported_probability",
        threshold=0.95,
    )

    assert result["valid"] is True
    assert result["route_mismatch_count"] == 0
    assert result["decision_mismatch_count"] == 0
    assert result["probability_drift"]["max_abs"] == pytest.approx(0.10)


def test_runtime_parity_reports_threshold_crossing() -> None:
    module = _module()
    reference = _analysis()
    candidate = deepcopy(reference)
    candidate["rows"][0]["supported_probability"] = 0.94

    result = module.validate_runtime_parity(
        reference,
        candidate,
        route_field="predicted",
        score_field="supported_probability",
        threshold=0.95,
    )

    assert result["valid"] is False
    assert result["route_mismatch_count"] == 0
    assert result["decision_mismatch_count"] == 1
    assert result["decision_mismatches"][0]["case_id"] == "a"


def test_runtime_parity_reports_route_change() -> None:
    module = _module()
    reference = _analysis()
    candidate = deepcopy(reference)
    candidate["rows"][0]["predicted"] = "weather.forecast"

    result = module.validate_runtime_parity(
        reference,
        candidate,
        route_field="predicted",
        score_field="supported_probability",
        threshold=0.95,
    )

    assert result["valid"] is False
    assert result["route_mismatch_count"] == 1
    assert result["decision_mismatch_count"] == 0
    assert result["route_mismatches"][0]["case_id"] == "a"


def test_runtime_parity_rejects_case_set_change() -> None:
    module = _module()
    reference = _analysis()
    candidate = deepcopy(reference)
    candidate["rows"].pop()

    with pytest.raises(module.RuntimeParityError, match="case IDs differ"):
        module.validate_runtime_parity(
            reference,
            candidate,
            route_field="predicted",
            score_field="supported_probability",
            threshold=0.95,
        )


def test_runtime_parity_rejects_execution_or_authority_errors() -> None:
    module = _module()
    reference = _analysis()
    candidate = deepcopy(reference)
    candidate["summary"]["authority_violations"] = 1

    with pytest.raises(module.RuntimeParityError, match="authority_violations"):
        module.validate_runtime_parity(
            reference,
            candidate,
            route_field="predicted",
            score_field="supported_probability",
            threshold=0.95,
        )


def test_runtime_parity_supports_bge_kev_row_shape() -> None:
    module = _module()
    reference = {
        "summary": {"execution_errors": 0, "authority_violations": 0},
        "rows": [
            {
                "case_id": "a",
                "raw_top_route": "weather.current",
                "supported_probability": 0.99,
            },
            {
                "case_id": "b",
                "raw_top_route": "weather.forecast",
                "supported_probability": 0.05,
            },
        ],
    }
    candidate = deepcopy(reference)
    candidate["rows"][0]["supported_probability"] = 0.98

    result = module.validate_runtime_parity(
        reference,
        candidate,
        route_field="raw_top_route",
        score_field="supported_probability",
        threshold=0.95,
    )
    assert result["valid"] is True
