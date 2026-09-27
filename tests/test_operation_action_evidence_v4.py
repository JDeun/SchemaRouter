from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "analyze_operation_action_evidence_v4.py"


def _module():
    spec = importlib.util.spec_from_file_location(
        "analyze_operation_action_evidence_v4",
        SCRIPT,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load action evidence analyzer")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_action_text_uses_only_endpoint_action_and_aliases() -> None:
    module = _module()
    text = module.action_text(
        "create_ticket",
        ["create support ticket", "open support case"],
    )
    assert text == "create ticket ; create support ticket ; open support case"


def test_fast_accept_frontier_counts_false_accepts_and_coverage() -> None:
    module = _module()
    rows = [
        {
            "expected": "tool.a",
            "top_route": "tool.a",
            "top_score": 0.9,
            "top_margin": 0.3,
        },
        {
            "expected": "tool.b",
            "top_route": "tool.a",
            "top_score": 0.8,
            "top_margin": 0.2,
        },
        {
            "expected": None,
            "top_route": "tool.a",
            "top_score": 0.7,
            "top_margin": 0.1,
        },
    ]
    frontier = module.fast_accept_frontier(rows)
    point = next(
        item
        for item in frontier["points"]
        if item["score_threshold"] == 0.80
        and item["margin_threshold"] == 0.10
    )
    assert point["accepted"] == 2
    assert point["true_accepts"] == 1
    assert point["false_accepts"] == 1
    assert point["precision"] == 0.5
    assert point["supported_correct_coverage"] == 0.5


def test_summary_reports_supported_exact_and_family_slices() -> None:
    module = _module()
    rows = [
        {
            "category": "v4_supported_natural",
            "language": "en",
            "unsupported_family": None,
            "expected": "tool.a",
            "expected_score": 0.8,
            "top_route": "tool.a",
            "top_score": 0.8,
            "top_margin": 0.4,
            "latency_ms": 2.0,
        },
        {
            "category": "near_domain_unsupported_operation",
            "language": "en",
            "unsupported_family": "tool.family_1",
            "expected": None,
            "expected_score": None,
            "top_route": "tool.a",
            "top_score": 0.4,
            "top_margin": 0.1,
            "latency_ms": 3.0,
        },
        {
            "category": "out_of_domain",
            "language": "en",
            "unsupported_family": None,
            "expected": None,
            "expected_score": None,
            "top_route": "tool.b",
            "top_score": 0.2,
            "top_margin": 0.05,
            "latency_ms": 4.0,
        },
    ]
    summary = module.summarize_rows(rows)
    assert summary["supported_raw_top_exact"] == 1.0
    assert summary["false_family_slices"]["tool.family_1"]["cases"] == 1
    assert summary["query_embedding_plus_cosine_latency_ms"]["p50"] == 3.0
