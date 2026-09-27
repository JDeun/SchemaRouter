from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "analyze_operation_routing_v4_selector.py"


def _module():
    spec = importlib.util.spec_from_file_location(
        "analyze_operation_routing_v4_selector",
        SCRIPT,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load v4 selector analyzer")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _summary(*, wrong_endpoint: int = 0) -> dict:
    return {
        "error_taxonomy": {
            "false_route": 0,
            "missed_route": 0,
            "wrong_tool": 0,
            "wrong_endpoint": wrong_endpoint,
        },
        "invalid_plan_rate": 0.0,
        "errors": 0,
        "mean_latency_ms": 10.0,
        "p50_latency_ms": 10.0,
        "p95_latency_ms": 11.0,
    }


def _row(
    backend: str,
    case_id: str,
    expected: str | None,
    predicted: str | None,
    *,
    category: str,
    top: str | None,
) -> dict:
    return {
        "backend": backend,
        "case_id": case_id,
        "category": category,
        "language": "en",
        "unsupported_family": (
            "inventory.family_1" if expected is None else None
        ),
        "expected": expected,
        "predicted": predicted,
        "correct": predicted == expected,
        "invalid_plan": False,
        "latency_ms": 10.0,
        "error": None,
        "operation_fit_invoked": True,
        "operation_fit_abstained": top is None,
        "operation_fit_top_option_id": top,
    }


def test_selector_analyzer_tracks_top_driven_paired_gain() -> None:
    module = _module()
    report = {
        "rows": [
            _row(
                module.BASELINE,
                "supported",
                "inventory.update",
                "inventory.search",
                category="v4_supported_natural",
                top="inventory.update",
            ),
            _row(
                module.BASELINE,
                "near",
                None,
                None,
                category="near_domain_unsupported_operation",
                top=None,
            ),
            _row(
                module.SELECTOR,
                "supported",
                "inventory.update",
                "inventory.update",
                category="v4_supported_natural",
                top="inventory.update",
            ),
            _row(
                module.SELECTOR,
                "near",
                None,
                None,
                category="near_domain_unsupported_operation",
                top=None,
            ),
        ],
        "summary": {
            module.BASELINE: _summary(wrong_endpoint=1),
            module.SELECTOR: _summary(),
        },
        "reproducibility": {
            "source_revision": "abc",
            "corpus_sha256": "def",
        },
    }

    result = module.analyze(report)

    assert result["selector_candidate"]["supported_exact_route_accuracy"] == 1.0
    assert result["selector_candidate"]["near_domain_unsupported_rejection"] == 1.0
    assert result["selector_candidate"]["false_route_rate"] == 0.0
    assert result["paired_selector_vs_baseline"]["candidate_gains"] == 1
    assert result["paired_selector_vs_baseline"]["candidate_losses"] == 0
    assert result["paired_selector_vs_baseline"]["route_changes"] == 1
    assert result["paired_selector_vs_baseline"]["top_driven_route_changes"] == 1
    assert result["all_quality_gates_passed"] is True
