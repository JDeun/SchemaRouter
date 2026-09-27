from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "compare_graph_calibration.py"


def _module():
    spec = importlib.util.spec_from_file_location("compare_graph_calibration", SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load graph calibration comparator")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _write_report(
    path: Path,
    *,
    candidate_supported_correct: int = 12,
    candidate_near_rejected: int = 20,
    candidate_false_routes: int = 0,
    candidate_mean: float = 80.0,
    candidate_p95: float = 108.0,
    baseline_mean: float = 100.0,
    baseline_p95: float = 120.0,
) -> None:
    module = _module()
    rows: list[dict[str, object]] = []
    for backend, supported_correct, near_rejected, mean in (
        (module.BASELINE, 11, 20, baseline_mean),
        (
            module.CANDIDATE,
            candidate_supported_correct,
            candidate_near_rejected,
            candidate_mean,
        ),
    ):
        for index in range(20):
            correct = index < supported_correct
            rows.append(
                {
                    "backend": backend,
                    "case_id": f"supported-{index}",
                    "category": "graph_cal_supported_natural",
                    "expected": "weather.current",
                    "predicted": "weather.current" if correct else None,
                    "correct": correct,
                    "invalid_plan": False,
                    "latency_ms": mean + (index % 3),
                    "error": None,
                }
            )
        for index in range(20):
            rejected = index < near_rejected
            rows.append(
                {
                    "backend": backend,
                    "case_id": f"near-{index}",
                    "category": "near_domain_unsupported_operation",
                    "expected": None,
                    "predicted": None if rejected else "weather.current",
                    "correct": rejected,
                    "invalid_plan": False,
                    "latency_ms": mean + 2 + (index % 3),
                    "error": None,
                }
            )
        for index in range(4):
            rows.append(
                {
                    "backend": backend,
                    "case_id": f"ood-{index}",
                    "category": "out_of_domain",
                    "expected": None,
                    "predicted": None,
                    "correct": True,
                    "invalid_plan": False,
                    "latency_ms": mean + 1,
                    "error": None,
                }
            )

    report = {
        "graph_semantic_seed": {
            "enabled": True,
            "min_similarity": 0.45,
            "min_margin": 0.10,
            "direct_min_similarity": 0.55,
            "direct_min_margin": 0.15,
        },
        "graph_propagation": {
            "enabled": True,
            "scope": "ranked_only",
            "ranked_limit": 2,
            "on_abstain": "reject",
            "corroborate_abstain": True,
        },
        "graph_static_option_embedding_cache": {
            "enabled": True,
            "surfaces": [
                "candidate_recall",
                "candidate_fit",
                "endpoint_disambiguation",
            ],
        },
        "measurement": {
            "mode": "counterbalanced",
            "warmup_cases": 24,
        },
        "reproducibility": {
            "source_revision": "test",
            "corpus_sha256": "fresh-calibration",
        },
        "rows": rows,
        "summary": {
            module.BASELINE: {
                "error_taxonomy": {
                    "false_route": 0,
                    "missed_route": 9,
                    "wrong_tool": 0,
                    "wrong_endpoint": 0,
                },
                "invalid_plan_rate": 0.0,
                "errors": 0,
                "mean_latency_ms": baseline_mean,
                "p50_latency_ms": baseline_mean,
                "p95_latency_ms": baseline_p95,
            },
            module.CANDIDATE: {
                "error_taxonomy": {
                    "false_route": candidate_false_routes,
                    "missed_route": 20 - candidate_supported_correct,
                    "wrong_tool": 0,
                    "wrong_endpoint": 0,
                },
                "invalid_plan_rate": 0.0,
                "errors": 0,
                "mean_latency_ms": candidate_mean,
                "p50_latency_ms": candidate_mean,
                "p95_latency_ms": candidate_p95,
            },
        },
    }
    path.write_text(json.dumps(report), encoding="utf-8")


def test_frozen_calibration_can_pass_all_gates(tmp_path: Path) -> None:
    module = _module()
    report = tmp_path / "report.json"
    _write_report(report)

    result = module.evaluate(report)

    assert result["calibration_passed"] is True
    assert result["blind_v15_allowed"] is True
    assert result["profile"]["supported_operation_routed_accuracy"] == 0.6
    assert result["profile"]["near_domain_unsupported_operation_rejection"] == 1.0
    assert result["paired"]["mean_delta_ms"] < 0
    assert result["paired"]["p95_delta_ms"] < 0


def test_frozen_configuration_change_is_rejected(tmp_path: Path) -> None:
    module = _module()
    report = tmp_path / "report.json"
    _write_report(report)
    value = json.loads(report.read_text(encoding="utf-8"))
    value["graph_propagation"]["ranked_limit"] = 3
    report.write_text(json.dumps(value), encoding="utf-8")

    with pytest.raises(ValueError, match="frozen graph propagation setting changed"):
        module.evaluate(report)


def test_calibration_p95_regression_closes_candidate(tmp_path: Path) -> None:
    module = _module()
    report = tmp_path / "report.json"
    _write_report(
        report,
        candidate_mean=80.0,
        candidate_p95=125.0,
        baseline_mean=100.0,
        baseline_p95=120.0,
    )

    result = module.evaluate(report)

    assert result["gates"]["paired_mean_latency_improvement"] is True
    assert result["gates"]["paired_p95_latency_non_regression"] is False
    assert result["calibration_passed"] is False
    assert result["blind_v15_allowed"] is False
    assert result["status"] == "fresh_calibration_rejected_cycle_closed"


def test_calibration_false_route_regression_closes_candidate(tmp_path: Path) -> None:
    module = _module()
    report = tmp_path / "report.json"
    _write_report(
        report,
        candidate_near_rejected=19,
        candidate_false_routes=1,
    )

    result = module.evaluate(report)

    assert result["gates"]["false_route_non_regression"] is False
    assert result["calibration_passed"] is False
    assert result["blind_v15_allowed"] is False
