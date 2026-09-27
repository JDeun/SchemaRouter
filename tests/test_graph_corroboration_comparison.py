from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "compare_graph_corroboration.py"


def _module():
    spec = importlib.util.spec_from_file_location("compare_graph_corroboration", SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load corroboration comparison")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _write_report(
    path: Path,
    *,
    scope: str,
    candidate_supported_correct: int = 12,
    candidate_near_rejected: int = 20,
    candidate_false_routes: int = 0,
    candidate_mean: float = 80.0,
    candidate_p95: float = 108.0,
    baseline_mean: float = 100.0,
    baseline_p95: float = 120.0,
    corroboration_correct: int = 4,
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
            corroborated = (
                backend == module.CANDIDATE
                and 2 <= index < 2 + corroboration_correct
            )
            rows.append(
                {
                    "backend": backend,
                    "case_id": f"supported-{index}",
                    "category": "graph_dev_supported_action",
                    "expected": "weather.current",
                    "predicted": "weather.current" if correct else None,
                    "correct": correct,
                    "latency_ms": mean + (index % 3),
                    "error": None,
                    "graph_semantic_seed_decision": (
                        "propagate" if backend == module.CANDIDATE else None
                    ),
                    "graph_propagation_decision": (
                        "accept"
                        if backend == module.CANDIDATE and index < 2
                        else "reject"
                        if backend == module.CANDIDATE
                        else None
                    ),
                    "graph_corroboration_decision": (
                        "accept" if corroborated else None
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
                    "latency_ms": mean + 2 + (index % 3),
                    "error": None,
                    "graph_semantic_seed_decision": (
                        "abstain" if backend == module.CANDIDATE else None
                    ),
                    "graph_propagation_decision": None,
                    "graph_corroboration_decision": None,
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
                    "latency_ms": mean + 1,
                    "error": None,
                    "graph_semantic_seed_decision": (
                        "abstain" if backend == module.CANDIDATE else None
                    ),
                    "graph_propagation_decision": None,
                    "graph_corroboration_decision": None,
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
            "scope": scope,
            "ranked_limit": 2,
            "on_abstain": "reject",
            "corroborate_abstain": True,
        },
        "measurement": {
            "mode": "counterbalanced",
            "warmup_cases": 8,
        },
        "reproducibility": {
            "source_revision": "test",
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


def test_corroboration_evaluator_requires_preregistered_geometry(tmp_path: Path) -> None:
    module = _module()
    report = tmp_path / "report.json"
    _write_report(report, scope="ranked")
    value = json.loads(report.read_text(encoding="utf-8"))
    value["graph_semantic_seed"]["min_similarity"] = 0.40
    report.write_text(json.dumps(value), encoding="utf-8")

    with pytest.raises(ValueError, match="unexpected graph semantic geometry"):
        module.evaluate(report)


def test_corroboration_candidate_can_pass_all_gates(tmp_path: Path) -> None:
    module = _module()
    report = tmp_path / "report.json"
    _write_report(report, scope="ranked_only")

    result = module.evaluate(report)

    assert result["all_gates_passed"] is True
    assert result["profile"]["supported_operation_routed_accuracy"] == 0.6
    assert result["profile"]["corroboration_accepts"] == 4
    assert result["profile"]["corroboration_accept_precision"] == 1.0
    assert result["paired"]["mean_delta_ms"] < 0


def test_corroboration_false_route_regression_blocks_promotion(tmp_path: Path) -> None:
    module = _module()
    report = tmp_path / "report.json"
    _write_report(
        report,
        scope="ranked",
        candidate_near_rejected=19,
        candidate_false_routes=1,
    )

    result = module.evaluate(report)

    assert result["all_gates_passed"] is False
    assert result["gates"]["false_route_non_regression"] is False


def test_corroboration_selection_prefers_higher_quality_gate_passer(
    tmp_path: Path,
) -> None:
    module = _module()
    ranked = tmp_path / "ranked.json"
    ranked_only = tmp_path / "ranked-only.json"
    _write_report(
        ranked,
        scope="ranked",
        candidate_supported_correct=12,
        candidate_mean=70.0,
    )
    _write_report(
        ranked_only,
        scope="ranked_only",
        candidate_supported_correct=14,
        candidate_mean=78.0,
    )

    result = module.compare([ranked, ranked_only])

    assert result["status"] == "development_corroboration_candidate_selected"
    assert result["winner"] == {"propagation_scope": "ranked_only"}
    assert result["freeze_allowed"] is True
    assert result["calibration_allowed"] is False
    assert result["blind_v15_allowed"] is False
