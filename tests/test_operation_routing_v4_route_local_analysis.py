from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "analyze_operation_routing_v4_route_local.py"


def _module():
    spec = importlib.util.spec_from_file_location(
        "analyze_operation_routing_v4_route_local",
        SCRIPT,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load route-local analyzer")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _report(backend: str, supported_pred: str | None, false_pred: str | None) -> dict:
    rows = [
        {
            "backend": backend,
            "case_id": "supported",
            "category": "v4_supported_natural",
            "expected": "weather.current",
            "predicted": supported_pred,
            "correct": supported_pred == "weather.current",
        },
        {
            "backend": backend,
            "case_id": "near",
            "category": "near_domain_unsupported_operation",
            "expected": None,
            "predicted": false_pred,
            "correct": false_pred is None,
        },
    ]
    false_routes = int(false_pred is not None)
    missed = int(supported_pred is None)
    wrong_endpoint = int(
        supported_pred not in (None, "weather.current")
    )
    return {
        "rows": rows,
        "summary": {
            backend: {
                "error_taxonomy": {
                    "false_route": false_routes,
                    "missed_route": missed,
                    "wrong_tool": 0,
                    "wrong_endpoint": wrong_endpoint,
                },
                "invalid_plan_rate": 0.0,
                "errors": 0,
                "mean_latency_ms": 10.0,
                "p50_latency_ms": 10.0,
                "p95_latency_ms": 11.0,
            }
        },
        "reproducibility": {
            "source_revision": "abc",
            "corpus_sha256": "def",
        },
    }


def test_route_local_analyzer_tracks_safety_gain_and_supported_loss() -> None:
    module = _module()
    baseline = _report(module.SELECTOR, "weather.current", "weather.current")
    dev = _report(module.SELECTOR, None, None)
    prod = _report(module.SELECTOR, None, None)

    result = module.analyze(baseline, dev, prod)

    paired = result["paired_vs_accepted_selector"]["dev_safety_budget_12"]
    assert paired["candidate_losses"] == 1
    assert paired["false_routes_removed"] == 1
    assert result["profiles"]["dev_safety_budget_12"]["false_route_rate"] == 0.0
    assert result["all_gates_passed"]["dev_safety_budget_12"] is False
