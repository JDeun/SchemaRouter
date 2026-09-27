from __future__ import annotations

import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "compare_graph_static_cache.py"


def _module():
    spec = importlib.util.spec_from_file_location("compare_graph_static_cache", SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load static-cache comparison")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _write_report(path: Path, *, alter_prediction: bool = False) -> None:
    module = _module()
    rows: list[dict[str, object]] = []
    for backend, supported_correct, mean in (
        (module.BASELINE, 11, 100.0),
        (module.CANDIDATE, 12, 80.0),
    ):
        for index in range(20):
            correct = index < supported_correct
            predicted = "weather.current" if correct else None
            if backend == module.CANDIDATE and alter_prediction and index == 0:
                predicted = "weather.forecast"
                correct = False
            rows.append(
                {
                    "backend": backend,
                    "case_id": f"supported-{index}",
                    "category": "supported",
                    "expected": "weather.current",
                    "predicted": predicted,
                    "correct": correct,
                    "invalid_plan": False,
                    "latency_ms": mean + (index % 2),
                    "error": None,
                }
            )
        for index in range(20):
            rows.append(
                {
                    "backend": backend,
                    "case_id": f"near-{index}",
                    "category": "near_domain_unsupported_operation",
                    "expected": None,
                    "predicted": None,
                    "correct": True,
                    "invalid_plan": False,
                    "latency_ms": mean + 2 + (index % 2),
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
        "measurement": {"mode": "counterbalanced", "warmup_cases": 8},
        "graph_static_option_embedding_cache": {
            "enabled": True,
            "surfaces": [
                "candidate_recall",
                "candidate_fit",
                "endpoint_disambiguation",
            ],
        },
        "reproducibility": {
            "source_revision": "test",
            "corpus_sha256": "test-corpus",
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
                "mean_latency_ms": 100.0,
                "p50_latency_ms": 100.0,
                "p95_latency_ms": 104.0,
            },
            module.CANDIDATE: {
                "error_taxonomy": {
                    "false_route": 0,
                    "missed_route": 8,
                    "wrong_tool": 0,
                    "wrong_endpoint": 0,
                },
                "invalid_plan_rate": 0.0,
                "errors": 0,
                "mean_latency_ms": 80.0,
                "p50_latency_ms": 80.0,
                "p95_latency_ms": 84.0,
            },
        },
    }
    path.write_text(json.dumps(report), encoding="utf-8")


def test_static_cache_candidate_passes_only_with_prediction_parity(
    tmp_path: Path,
) -> None:
    module = _module()
    report = tmp_path / "report.json"
    _write_report(report)

    loaded = module._load(report)
    candidate_rows = module._rows(loaded, module.CANDIDATE)
    module.REFERENCE_PREDICTION_DIGEST = module.prediction_digest(candidate_rows)

    result = module.evaluate(report)

    assert result["gates"]["prediction_digest_parity"] is True
    assert result["all_gates_passed"] is True
    assert result["paired"]["mean_delta_ms"] < 0
    assert result["paired"]["p95_delta_ms"] < 0


def test_static_cache_prediction_change_blocks_promotion(tmp_path: Path) -> None:
    module = _module()
    reference = tmp_path / "reference.json"
    changed = tmp_path / "changed.json"
    _write_report(reference)
    _write_report(changed, alter_prediction=True)

    reference_loaded = module._load(reference)
    module.REFERENCE_PREDICTION_DIGEST = module.prediction_digest(
        module._rows(reference_loaded, module.CANDIDATE)
    )

    result = module.evaluate(changed)

    assert result["gates"]["prediction_digest_parity"] is False
    assert result["all_gates_passed"] is False
    assert result["freeze_allowed"] is False
