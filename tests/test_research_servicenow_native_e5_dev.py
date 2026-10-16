"""Offline provenance/metric integrity controls; not a model-quality claim."""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import pytest

from scripts.research_servicenow_native_e5_dev import (
    MODEL_REVISION,
    case_metrics,
    evaluate,
    strict_permutation,
    summarize,
)


@pytest.mark.parametrize("ranked", [
    ["read", "read"], ["read"], ["read", "foreign"], ["read", 8],
])
def test_full_semantic_rank_must_be_exact_native_source_permutation(
    ranked: list[str],
) -> None:
    with pytest.raises(ValueError, match="permutation"):
        strict_permutation(ranked, {"read", "describe"})


def test_valid_source_only_permutation() -> None:
    strict_permutation(["describe", "read"], {"read", "describe"})


def test_no_source_native_field_fabrication() -> None:
    source = {
        "read": {
            "name": "read",
            "inputSchema": {"type": "object", "properties": {
                "table": {"type": "string"},
                "fields": {"type": "array"},
            }},
        },
        "describe": {
            "name": "describe",
            "inputSchema": {"type": "object", "properties": {}},
        },
    }
    case = {
        "id": "visible-dev-positive",
        "label": "supported",
        "required_tools": ["read"],
        "required_fields": {"read": ["table", "fields"]},
    }
    hit = case_metrics(case, ["read"], source)
    assert hit["route_hits"] == hit["route_required"] == 1
    assert hit["field_hits"] == hit["field_required"] == 2
    miss = case_metrics(case, ["describe"], source)
    assert miss["route_hits"] == 0
    assert miss["field_hits"] == 0
    with pytest.raises(ValueError, match="not native"):
        case_metrics(case, ["stolen"], source)
    with pytest.raises(ValueError, match="not native"):
        case_metrics(case, ["read", "read"], source)


def test_unsupported_nonempty_is_exposure_not_no_fit() -> None:
    source = {
        "read": {
            "name": "read",
            "inputSchema": {"properties": {"table": {"type": "string"}}},
        }
    }
    case = {
        "id": "visible-dev-negative", "label": "unsupported",
        "required_tools": [], "required_fields": {},
    }
    item = case_metrics(case, ["read"], source)
    assert item["unsupported_nonempty_not_no_fit"] is True
    assert item["route_required"] == item["field_required"] == 0
    tampered = deepcopy(case)
    tampered["required_tools"] = ["read"]
    with pytest.raises(ValueError, match="forbidden gold"):
        case_metrics(tampered, ["read"], source)


def test_summary_refuses_duplicate_or_missing_measurement() -> None:
    cases = [
        {"id": f"case-{i}", "label": (
            "supported" if i < 20 else "unsupported"
        )}
        for i in range(24)
    ]
    sample = {
        "route_hits": 1, "route_required": 1,
        "field_hits": 1, "field_required": 1,
        "visible_native_bytes": 42,
        "unsupported_nonempty_not_no_fit": None,
    }
    rows = []
    for case in cases:
        metric = dict(sample)
        if case["label"] == "unsupported":
            metric.update(
                route_hits=0, route_required=0,
                field_hits=0, field_required=0,
                unsupported_nonempty_not_no_fit=True,
            )
        rows.append({
            "id": case["id"],
            "metrics": {
                name: dict(metric) for name in (
                    "static_full", "lexical_k3", "lexical_k5",
                    "e5_k3", "e5_k5",
                )
            },
        })
    valid = summarize(rows, cases)
    assert valid["e5_k5"]["required_tool_recall_macro"] == 1.0
    assert valid["e5_k5"]["native_input_field_recall_micro"] == 1.0
    assert valid["e5_k5"]["unsupported_nonempty_exposure_count_not_no_fit"] == 4
    with pytest.raises(ValueError, match="missing or duplicate"):
        summarize(rows[:-1], cases)
    duplicate = deepcopy(rows)
    duplicate[1]["id"] = "case-0"
    with pytest.raises(ValueError, match="duplicate"):
        summarize(duplicate, cases)


@pytest.mark.parametrize("revision", ["main", "", "0" * 40])
def test_model_identity_must_be_pinned_before_source_load(
    revision: str, tmp_path: Path,
) -> None:
    with pytest.raises(ValueError, match="unpinned"):
        evaluate(
            tmp_path, tmp_path / "fake.json",
            lambda texts: [[0.0, 1.0] for _ in texts],
            model_revision=revision,
        )
    assert revision != MODEL_REVISION
