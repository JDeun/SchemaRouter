from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "calibrate_decision_threshold.py"


def _module():
    spec = importlib.util.spec_from_file_location("calibrate_decision_threshold", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _report() -> dict:
    return {
        "generated_at": "2026-09-23T00:00:00+00:00",
        "schemarouter_version": "0.7.0.dev0",
        "corpus": "benchmarks/decision-routing-v1.json",
        "environment": {"machine": "x86_64"},
        "rows": [
            {
                "backend": "keyword",
                "case_id": "route",
                "category": "normal",
                "expected": "materials.search",
                "predicted": "weather.current",
            },
            {
                "backend": "keyword",
                "case_id": "abstain",
                "category": "adversarial",
                "expected": None,
                "predicted": None,
            },
            {
                "backend": "laya:auto",
                "case_id": "route",
                "category": "normal",
                "expected": "materials.search",
                "predicted": "materials.search",
                "backend_invoked": True,
                "recall_expanded": False,
                "confidence": 0.8,
            },
            {
                "backend": "laya:auto",
                "case_id": "abstain",
                "category": "adversarial",
                "expected": None,
                "predicted": "users.lookup",
                "backend_invoked": True,
                "recall_expanded": True,
                "confidence": 0.4,
            },
        ],
    }


def test_threshold_calibration_replays_deterministic_fallback() -> None:
    module = _module()
    result = module.calibrate(
        _report(),
        backend="laya:auto",
        thresholds=[0.0, 0.5, 0.9],
    )

    by_threshold = {row["threshold"]: row for row in result["results"]}

    assert by_threshold[0.0]["accuracy"] == 0.5
    assert by_threshold[0.0]["expected_no_route_recall"] == 0.0

    assert by_threshold[0.5]["accuracy"] == 1.0
    assert by_threshold[0.5]["backend_abstention_rate"] == 0.5
    assert by_threshold[0.5]["expected_no_route_recall"] == 1.0
    assert by_threshold[0.5]["category_accuracy"]["normal"] == 1.0
    assert by_threshold[0.5]["category_accuracy"]["adversarial"] == 1.0

    assert by_threshold[0.9]["accuracy"] == 0.5
    assert by_threshold[0.9]["backend_abstention_rate"] == 1.0
    assert by_threshold[0.9]["expected_no_route_recall"] == 1.0


def test_threshold_parser_validates_bounds_and_deduplicates() -> None:
    module = _module()

    assert module.parse_thresholds("0.5,0.0,0.5") == [0.0, 0.5]

    for invalid in ("", "-0.1", "1.1"):
        try:
            module.parse_thresholds(invalid)
        except ValueError:
            pass
        else:
            raise AssertionError(f"{invalid!r} must fail")


def test_threshold_calibration_rejects_mismatched_case_sets() -> None:
    module = _module()
    report = _report()
    report["rows"] = [
        row
        for row in report["rows"]
        if not (row["backend"] == "keyword" and row["case_id"] == "abstain")
    ]

    try:
        module.calibrate(report, backend="laya:auto", thresholds=[0.5])
    except ValueError as exc:
        assert "same case IDs" in str(exc)
    else:
        raise AssertionError("mismatched case sets must fail closed")


def test_threshold_calibration_outputs_are_self_contained(tmp_path) -> None:
    module = _module()
    calibrated = module.calibrate(
        _report(),
        backend="laya:auto",
        thresholds=[0.0, 0.5],
    )
    json_out = tmp_path / "calibration.json"
    csv_out = tmp_path / "calibration.csv"
    html_out = tmp_path / "calibration.html"

    module.write_outputs(
        calibrated,
        json_out=json_out,
        csv_out=csv_out,
        html_out=html_out,
    )

    loaded = json.loads(json_out.read_text(encoding="utf-8"))
    assert loaded["backend"] == "laya:auto"
    assert "category:normal" in csv_out.read_text(encoding="utf-8")
    html = html_out.read_text(encoding="utf-8")
    assert "SchemaRouter confidence threshold calibration" in html
    assert "https://" not in html



def test_threshold_calibration_prefers_explicit_recall_expansion_marker() -> None:
    module = _module()
    report = _report()
    keyword_abstain = next(
        row
        for row in report["rows"]
        if row["backend"] == "keyword" and row["case_id"] == "abstain"
    )
    keyword_abstain["predicted"] = "weather.current"

    result = module.calibrate(
        report,
        backend="laya:auto",
        thresholds=[0.5],
    )
    row = result["results"][0]

    assert row["expanded_candidate_cases"] == 1
    assert row["expanded_selection_rate"] == 0.0



def test_threshold_calibration_can_turn_low_confidence_into_no_route() -> None:
    module = _module()
    result = module.calibrate(
        _report(),
        backend="laya:auto",
        thresholds=[0.5],
        abstention_mode="no_route",
    )

    row = result["results"][0]

    assert result["abstention_mode"] == "no_route"
    assert row["accuracy"] == 1.0
    assert row["expected_no_route_recall"] == 1.0
    assert row["final_no_route_rate"] == 0.5


def test_threshold_calibration_rejects_unknown_abstention_mode() -> None:
    module = _module()

    try:
        module.calibrate(
            _report(),
            backend="laya:auto",
            thresholds=[0.5],
            abstention_mode="unknown",
        )
    except ValueError as exc:
        assert "abstention_mode" in str(exc)
    else:
        raise AssertionError("unknown abstention mode must fail closed")



def test_threshold_calibration_preserves_explicit_model_no_route() -> None:
    module = _module()
    report = _report()
    backend_row = next(
        row
        for row in report["rows"]
        if row["backend"] == "laya:auto" and row["case_id"] == "abstain"
    )
    backend_row["predicted"] = None
    backend_row["explicit_no_route"] = True
    backend_row["confidence"] = 0.85

    result = module.calibrate(
        report,
        backend="laya:auto",
        thresholds=[0.0, 0.8, 0.9],
    )
    by_threshold = {row["threshold"]: row for row in result["results"]}

    assert by_threshold[0.0]["expected_no_route_recall"] == 1.0
    assert by_threshold[0.8]["expected_no_route_recall"] == 1.0
    assert by_threshold[0.9]["expected_no_route_recall"] == 1.0
