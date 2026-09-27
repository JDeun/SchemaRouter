from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "analyze_operation_routing_quality_v4_dev.py"


def _module():
    spec = importlib.util.spec_from_file_location(
        "analyze_operation_routing_quality_v4_dev",
        SCRIPT,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load v4 development analyzer")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _rows(backend: str, *, improved: bool) -> list[dict]:
    return [
        {
            "backend": backend,
            "case_id": "supported-en",
            "category": "v4_supported_natural",
            "language": "en",
            "unsupported_family": None,
            "expected": "weather.current",
            "predicted": "weather.current",
            "correct": True,
            "invalid_plan": False,
            "latency_ms": 10.0 if improved else 12.0,
            "error": None,
        },
        {
            "backend": backend,
            "case_id": "supported-ko",
            "category": "v4_supported_natural",
            "language": "ko",
            "unsupported_family": None,
            "expected": "weather.forecast",
            "predicted": (
                "weather.forecast" if improved else None
            ),
            "correct": improved,
            "invalid_plan": False,
            "latency_ms": 11.0 if improved else 13.0,
            "error": None,
        },
        {
            "backend": backend,
            "case_id": "near-weather",
            "category": "near_domain_unsupported_operation",
            "language": "en",
            "unsupported_family": "weather.family_1",
            "expected": None,
            "predicted": None,
            "correct": True,
            "invalid_plan": False,
            "latency_ms": 8.0 if improved else 9.0,
            "error": None,
        },
        {
            "backend": backend,
            "case_id": "near-finance",
            "category": "near_domain_unsupported_operation",
            "language": "ko",
            "unsupported_family": "finance.family_1",
            "expected": None,
            "predicted": (
                None if improved else "finance.quote"
            ),
            "correct": improved,
            "invalid_plan": False,
            "latency_ms": 9.0 if improved else 10.0,
            "error": None,
        },
        {
            "backend": backend,
            "case_id": "ood",
            "category": "out_of_domain",
            "language": "en",
            "unsupported_family": None,
            "expected": None,
            "predicted": None,
            "correct": True,
            "invalid_plan": False,
            "latency_ms": 7.0,
            "error": None,
        },
    ]


def _summary(improved: bool) -> dict:
    return {
        "error_taxonomy": {
            "false_route": 0 if improved else 1,
            "missed_route": 0 if improved else 1,
            "wrong_tool": 0,
            "wrong_endpoint": 0,
        },
        "invalid_plan_rate": 0.0,
        "errors": 0,
        "mean_latency_ms": 9.0 if improved else 10.2,
        "p50_latency_ms": 9.0 if improved else 10.0,
        "p95_latency_ms": 10.8 if improved else 12.8,
    }


def test_v4_analyzer_reports_family_and_language_slices() -> None:
    module = _module()
    report = {
        "rows": [
            *_rows(module.BASELINE, improved=False),
            *_rows(module.HISTORICAL_GRAPH, improved=True),
        ],
        "summary": {
            module.BASELINE: _summary(False),
            module.HISTORICAL_GRAPH: _summary(True),
        },
        "reproducibility": {
            "source_revision": "abc",
            "corpus_sha256": "def",
        },
    }

    result = module.analyze(report)
    historical = result["historical_graph_candidate"]

    assert historical["supported_exact_route_accuracy"] == 1.0
    assert historical["near_domain_unsupported_rejection"] == 1.0
    assert historical["false_route_rate"] == 0.0
    assert historical["language_slices"]["ko"]["exact_route_accuracy"] == 1.0
    assert historical["route_slices"]["weather.forecast"]["exact_route_accuracy"] == 1.0
    assert historical["unsupported_family_slices"]["finance.family_1"]["rejection"] == 1.0
    assert result["paired_historical_vs_baseline"]["candidate_gains"] == 2
    assert result["paired_historical_vs_baseline"]["candidate_losses"] == 0


def test_v4_analyzer_records_false_route_destination_by_family() -> None:
    module = _module()
    report = {
        "rows": [
            *_rows(module.BASELINE, improved=False),
            *_rows(module.HISTORICAL_GRAPH, improved=False),
        ],
        "summary": {
            module.BASELINE: _summary(False),
            module.HISTORICAL_GRAPH: _summary(False),
        },
    }

    result = module.analyze(report)
    family = result["historical_graph_candidate"][
        "unsupported_family_slices"
    ]["finance.family_1"]

    assert family["rejection"] == 0.0
    assert family["false_routes"] == 1
    assert family["false_route_destinations"] == {"finance.quote": 1}
