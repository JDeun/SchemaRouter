"""Fail-closed tests for current-checkout baseline intake and honest claim scope."""
from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from scripts.research_current_main_baseline import (
    AMBIGUITIES,
    LIMITS,
    METHODS,
    SIZES,
    _registered_runner,
    build_report,
    validate_break_even,
    validate_hot_path,
)


def fixture_break_even() -> dict:
    metrics = {
        "required_tool_recall": 0.75,
        "unsupported_rejection": 0.25,
        "false_route_rate": 0.75,
        "mean_selected_contract_bytes": 256.0,
        "p50_ms": 0.6,
        "p95_ms": 2.0,
    }
    return {
        "schema_version": 1,
        "benchmark": "realistic-catalog-break-even",
        "sizes": list(SIZES),
        "ambiguities": list(AMBIGUITIES),
        "matrix": [
            {
                "catalog_size": size,
                "ambiguity": ambiguity,
                "supported_cases": 12,
                "unsupported_cases": 4,
                "auto_full_selection_mismatches": 0,
                "methods": {name: metrics.copy() for name in METHODS},
            }
            for size in SIZES for ambiguity in AMBIGUITIES
        ],
    }


def fixture_hot_path() -> dict:
    timing = {
        "sample_count": 8,
        "median_ms": 0.3,
        "p95_ms": 0.5,
        "mean_ms": 0.4,
    }
    return {
        "schema_version": 2,
        "benchmark": "retrieval-hot-path-gearlynx-e1",
        "case_count": 4,
        "semantic_mismatches": [],
        "lightweight_semantic_mismatches": [],
        "optimized_typed": timing.copy(),
        "optimized_route_refs": timing.copy(),
        "legacy_typed_snapshot_copy": timing.copy(),
        "legacy_route_refs_snapshot_copy": timing.copy(),
    }


def test_valid_current_main_development_report_never_claims_agent_success() -> None:
    a, b = fixture_break_even(), fixture_hot_path()
    head = {"git_commit": "a" * 40}
    result = build_report(a, b, head)
    assert len(result["comparison"]) == 15
    assert result["scope"] == LIMITS
    assert result["scope"]["independent_validation"] is False
    assert result["scope"]["agent_task_success_measured"] is False
    assert result["scope"]["authorization_or_execution_measured"] is False
    assert result["scope"]["may_promote"] is False
    assert result["scope"]["may_release"] is False
    assert result["comparison"][0]["sr_unsupported_nonempty_shortlist_rate"] == 0.75
    assert "independent_agent_task_success_full_sr_k_progressive_oracle" in (
        result["unmeasured_requirements"]
    )
    assert len(json.dumps(result["raw_sha256"])) > 100


@pytest.mark.parametrize("change", [
    "missing_cell",
    "duplicate_cell",
    "indexed_drift",
    "nan",
    "negative_latency",
    "inconsistent_rejection",
    "missing_method",
    "wrong_denominator",
    "unsupported_route_mislabel",
])
def test_matrix_scoring_rejects_tampered_evidence(change: str) -> None:
    result = copy.deepcopy(fixture_break_even())
    cell = result["matrix"][0]
    metrics = cell["methods"]["schemarouter_auto"]
    if change == "missing_cell":
        result["matrix"].pop()
    elif change == "duplicate_cell":
        result["matrix"][1] = copy.deepcopy(cell)
    elif change == "indexed_drift":
        cell["auto_full_selection_mismatches"] = 1
    elif change == "nan":
        metrics["p95_ms"] = float("nan")
    elif change == "negative_latency":
        metrics["p95_ms"] = -0.5
    elif change == "inconsistent_rejection":
        metrics["unsupported_rejection"] = 0.9
    elif change == "missing_method":
        del cell["methods"]["schema_lexical_baseline"]
    elif change == "wrong_denominator":
        cell["supported_cases"] = 0
    elif change == "unsupported_route_mislabel":
        metrics["required_tool_recall"] = 1.0
    with pytest.raises(ValueError):
        validate_break_even(result)


@pytest.mark.parametrize("change", [
    "missing_case", "drift", "fake_p95", "bad_samples", "missing_arm",
])
def test_hot_path_rejects_missing_or_forged_data(change: str) -> None:
    result = fixture_hot_path()
    if change == "missing_case":
        result["case_count"] = 0
    elif change == "drift":
        result["semantic_mismatches"] = ["forged"]
    elif change == "fake_p95":
        result["optimized_typed"]["p95_ms"] = float("inf")
    elif change == "bad_samples":
        result["optimized_typed"]["sample_count"] = 0
    elif change == "missing_arm":
        del result["legacy_route_refs_snapshot_copy"]
    with pytest.raises(ValueError):
        validate_hot_path(result)


def test_registered_runner_refuses_arbitrary_execution_and_unbounded_budget(
    tmp_path: Path,
) -> None:
    with pytest.raises(ValueError):
        _registered_runner("scripts/random_shell.py", tmp_path / "x", 1)
    with pytest.raises(ValueError):
        _registered_runner("scripts/benchmark_realistic_break_even.py", tmp_path / "x", 0)
    with pytest.raises(ValueError):
        _registered_runner("scripts/benchmark_realistic_break_even.py", tmp_path / "x", 11)
