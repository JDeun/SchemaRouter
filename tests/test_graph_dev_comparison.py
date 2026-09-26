from __future__ import annotations

import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "compare_graph_development.py"


def _module():
    spec = importlib.util.spec_from_file_location("compare_graph_development", SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load graph development comparison")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _report(
    path: Path,
    *,
    candidate_supported: int = 6,
    candidate_near_rejected: int = 10,
    candidate_false_routes: int = 0,
    candidate_mean: float = 80.0,
    candidate_p95: float = 110.0,
) -> None:
    module = _module()
    rows = []
    for backend, supported_correct, near_rejected in (
        (module.BASELINE, 6, 10),
        (module.GRAPH, candidate_supported, candidate_near_rejected),
    ):
        for index in range(10):
            rows.append(
                {
                    "backend": backend,
                    "category": "graph_dev_supported_action",
                    "expected": "weather.current",
                    "predicted": (
                        "weather.current"
                        if index < supported_correct
                        else None
                    ),
                    "correct": index < supported_correct,
                }
            )
        for index in range(10):
            predicted = None if index < near_rejected else "weather.current"
            rows.append(
                {
                    "backend": backend,
                    "category": "near_domain_unsupported_operation",
                    "expected": None,
                    "predicted": predicted,
                    "correct": predicted is None,
                }
            )
        rows.append(
            {
                "backend": backend,
                "category": "out_of_domain",
                "expected": None,
                "predicted": None,
                "correct": True,
            }
        )

    report = {
        "reproducibility": {"corpus_sha256": "same-corpus"},
        "rows": rows,
        "summary": {
            module.BASELINE: {
                "error_taxonomy": {
                    "false_route": 0,
                    "missed_route": 4,
                    "wrong_tool": 0,
                    "wrong_endpoint": 0,
                },
                "invalid_plan_rate": 0.0,
                "errors": 0,
                "mean_latency_ms": 100.0,
                "p50_latency_ms": 95.0,
                "p95_latency_ms": 120.0,
                "graph_operation_counts": {},
                "graph_operation_resolution_rate": 0.0,
            },
            module.GRAPH: {
                "error_taxonomy": {
                    "false_route": candidate_false_routes,
                    "missed_route": 10 - candidate_supported,
                    "wrong_tool": 0,
                    "wrong_endpoint": 0,
                },
                "invalid_plan_rate": 0.0,
                "errors": 0,
                "mean_latency_ms": candidate_mean,
                "p50_latency_ms": candidate_mean,
                "p95_latency_ms": candidate_p95,
                "graph_operation_counts": {
                    "accept": 5,
                    "reject": 1,
                    "escalate": 15,
                },
                "graph_operation_resolution_rate": 6 / 21,
            },
        },
    }
    path.write_text(json.dumps(report), encoding="utf-8")


def test_compare_selects_only_candidate_passing_all_gates(tmp_path: Path) -> None:
    module = _module()
    alias = tmp_path / "alias.json"
    field = tmp_path / "field.json"

    _report(alias, candidate_mean=80.0, candidate_p95=110.0)
    _report(field, candidate_mean=70.0, candidate_p95=130.0)

    result = module.compare(alias, field)

    assert result["status"] == "development_candidate_selected"
    assert result["winner"] == "graph-alias-only"
    assert result["calibration_allowed"] is True
    assert result["blind_v15_allowed"] is False
    assert all(result["candidates"][0]["gates"].values())
    assert result["candidates"][1]["gates"]["paired_p95_latency_non_regression"] is False


def test_compare_rejects_false_route_regression(tmp_path: Path) -> None:
    module = _module()
    alias = tmp_path / "alias.json"
    field = tmp_path / "field.json"

    _report(alias, candidate_false_routes=1)
    _report(field, candidate_false_routes=1)

    result = module.compare(alias, field)

    assert result["status"] == "development_no_candidate_passed"
    assert result["winner"] is None
    assert result["calibration_allowed"] is False
    assert all(
        item["gates"]["false_route_non_regression"] is False
        for item in result["candidates"]
    )
