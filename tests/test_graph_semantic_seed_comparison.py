from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "compare_graph_semantic_seed.py"


def _module():
    spec = importlib.util.spec_from_file_location("compare_graph_semantic_seed", SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load semantic-seed comparison")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _write_report(
    path: Path,
    *,
    similarity: float,
    margin: float,
    candidate_supported_correct: int = 12,
    candidate_near_rejected: int = 20,
    candidate_latency: float = 80.0,
    baseline_latency: float = 100.0,
    measurement_mode: str = "counterbalanced",
) -> None:
    module = _module()
    rows = []
    for backend, supported_correct, near_rejected, latency in (
        (module.BASELINE, 11, 20, baseline_latency),
        (
            module.CANDIDATE,
            candidate_supported_correct,
            candidate_near_rejected,
            candidate_latency,
        ),
    ):
        for index in range(20):
            correct = index < supported_correct
            rows.append(
                {
                    "backend": backend,
                    "case_id": f"supported-{index}",
                    "category": "graph_dev_supported_action",
                    "expected": "weather.current",
                    "predicted": "weather.current" if correct else None,
                    "correct": correct,
                    "latency_ms": latency + (index % 3),
                    "error": None,
                    "graph_operation_decision": (
                        "accept"
                        if backend == module.CANDIDATE and index < 2
                        else "escalate"
                        if backend == module.CANDIDATE
                        else None
                    ),
                    "graph_semantic_seed_decision": (
                        "accept"
                        if backend == module.CANDIDATE and 2 <= index < 8
                        else "abstain"
                        if backend == module.CANDIDATE and index >= 8
                        else None
                    ),
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
                    "latency_ms": latency + 2 + (index % 3),
                    "error": None,
                    "graph_operation_decision": (
                        "escalate" if backend == module.CANDIDATE else None
                    ),
                    "graph_semantic_seed_decision": (
                        "abstain" if backend == module.CANDIDATE else None
                    ),
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
                    "latency_ms": latency + 1,
                    "error": None,
                    "graph_operation_decision": (
                        "escalate" if backend == module.CANDIDATE else None
                    ),
                    "graph_semantic_seed_decision": (
                        "abstain" if backend == module.CANDIDATE else None
                    ),
                }
            )

    report = {
        "graph_semantic_seed": {
            "enabled": True,
            "min_similarity": similarity,
            "min_margin": margin,
        },
        "measurement": {
            "mode": measurement_mode,
            "warmup_cases": 8,
        },
        "reproducibility": {
            "source_revision": "test-revision",
            "corpus_sha256": "same-dev-corpus",
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
                "mean_latency_ms": baseline_latency,
                "p50_latency_ms": baseline_latency,
                "p95_latency_ms": baseline_latency + 4,
            },
            module.CANDIDATE: {
                "error_taxonomy": {
                    "false_route": 20 - candidate_near_rejected,
                    "missed_route": 20 - candidate_supported_correct,
                    "wrong_tool": 0,
                    "wrong_endpoint": 0,
                },
                "invalid_plan_rate": 0.0,
                "errors": 0,
                "mean_latency_ms": candidate_latency,
                "p50_latency_ms": candidate_latency,
                "p95_latency_ms": candidate_latency + 4,
            },
        },
    }
    path.write_text(json.dumps(report), encoding="utf-8")


def test_semantic_seed_evaluator_requires_counterbalanced_measurement(
    tmp_path: Path,
) -> None:
    module = _module()
    report = tmp_path / "report.json"
    _write_report(
        report,
        similarity=0.4,
        margin=0.1,
        measurement_mode="sequential",
    )

    with pytest.raises(ValueError, match="counterbalanced"):
        module.evaluate(report)


def test_semantic_seed_candidate_passes_all_preregistered_gates(
    tmp_path: Path,
) -> None:
    module = _module()
    report = tmp_path / "report.json"
    _write_report(report, similarity=0.4, margin=0.1)

    result = module.evaluate(report)

    assert result["all_gates_passed"] is True
    assert result["profile"]["supported_operation_routed_accuracy"] == 0.6
    assert result["profile"]["near_domain_unsupported_operation_rejection"] == 1.0
    assert result["profile"]["semantic_seed_accepts"] == 6
    assert result["paired_latency"]["mean_delta_ms"] < 0
    assert all(result["gates"].values())


def test_semantic_seed_false_route_regression_blocks_candidate(
    tmp_path: Path,
) -> None:
    module = _module()
    report = tmp_path / "report.json"
    _write_report(
        report,
        similarity=0.25,
        margin=0.05,
        candidate_near_rejected=19,
    )

    result = module.evaluate(report)

    assert result["all_gates_passed"] is False
    assert result["gates"]["false_route_non_regression"] is False


def test_semantic_seed_selection_prefers_higher_quality_among_gate_passers(
    tmp_path: Path,
) -> None:
    module = _module()
    first = tmp_path / "first.json"
    second = tmp_path / "second.json"
    _write_report(
        first,
        similarity=0.35,
        margin=0.10,
        candidate_supported_correct=12,
        candidate_latency=70.0,
    )
    _write_report(
        second,
        similarity=0.45,
        margin=0.15,
        candidate_supported_correct=14,
        candidate_latency=78.0,
    )

    result = module.compare([first, second])

    assert result["status"] == "development_semantic_seed_candidate_selected"
    assert result["winner"] == {
        "min_similarity": 0.45,
        "min_margin": 0.15,
    }
    assert result["freeze_allowed"] is True
    assert result["candidate_frozen"] is False
    assert result["calibration_allowed"] is False
    assert result["blind_v15_allowed"] is False
