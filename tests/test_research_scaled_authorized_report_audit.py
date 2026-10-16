"""Synthetic report-contract counterexamples, without expensive retrieval/model calls."""
from __future__ import annotations

import hashlib
from copy import deepcopy

import pytest

from benchmarks.current_adapter_scaled_authorized_dev_v1 import (
    WIDTHS,
    authored_tasks,
)
from scripts.research_current_main_multilingual_dev import encoded
from scripts.research_scaled_authorized_report_audit import (
    CONDITIONS,
    _aggregate,
    audit,
)


def _report() -> dict:
    cases = []
    for task in authored_tasks():
        route = task["gold_route"]
        fields = task["gold_fields"]
        score = {
            "route_found": route is not None,
            "required_field_count": len(fields),
            "required_fields_found": list(fields),
            "all_required_fields_found": route is not None,
            "unsupported_nonempty_shortlist": False,
            "top5_ids": [route] if route is not None else [],
            "schema_bytes": 128,
            "retrieval_rerank_ms": 1.0,
            "unauthorized_count": 0,
        }
        cases.append({
            "case_id": task["id"], "language": task["language"],
            "role": task["role"], "scenario": task["scenario"],
            "catalog_size": 100, "required_route": route,
            "required_fields": list(fields),
            "authorized_full_contains_required_route": route is not None,
            "eligible_candidate_count": 95 if task["role"] == "viewer" else 100,
            "conditions": {name: deepcopy(score) for name in CONDITIONS},
        })

    def summary(items: list[dict], name: str) -> dict:
        return {
            **_aggregate(items, name),
            "p95_retrieval_rerank_ms": 1.0,
            "mean_top5_schema_bytes": 128.0,
        }

    groups = {
        f"100/{lang}/{role}": [
            case for case in cases
            if case["language"] == lang and case["role"] == role
        ]
        for lang in ("en", "ko", "ja") for role in ("viewer", "editor")
    }
    sources = {"fixture": "c" * 64}
    return {
        "schema_version": 1,
        "id": "author_visible_scaled_current_adapter_principal_field_dev",
        "source_sha256": hashlib.sha256(encoded(sources)).hexdigest(),
        "source_file_sha256": sources,
        "task_manifest_sha256": "b" * 64,
        "registered_sizes": [100], "candidate_widths": list(WIDTHS),
        "actual_authorized_router_calls": 27 * len(CONDITIONS),
        "required_router_calls_expected": 27 * len(CONDITIONS),
        "cases": cases,
        "overall": {name: summary(cases, name) for name in CONDITIONS},
        "by_scale_language_role": {
            key: {name: summary(items, name) for name in CONDITIONS}
            for key, items in groups.items()
        },
        "scope": {
            "independent_confirmation": False,
            "automatic_product_promotion": False,
            "may_release": False, "actual_agent_task_success": False,
            "model_or_external_tools_executed": False,
        },
    }


def test_complete_synthetic_receipt_remains_dev_only() -> None:
    result = audit(_report())
    assert result["paired_cases"] == 27
    assert len(result["decisions"]) == len(WIDTHS)
    assert result["automatic_product_promotion"] is False
    assert result["independent_confirmation"] is False
    assert all(not d["may_promote"] for d in result["decisions"].values())
    assert all(d["dev_diagnostic_gate"] for d in result["decisions"].values())


@pytest.mark.parametrize("mutation", (
    "duplicate_case", "missing_case", "forged_route", "forged_field",
    "forged_unauthorized", "wrong_report_count", "fake_independent",
    "wrong_source_hash", "duplicated_top5", "missing_width", "missing_group",
    "forged_aggregate", "nan_cpu",
))
def test_corrupt_evidence_is_rejected(mutation: str) -> None:
    receipt = _report()
    row = receipt["cases"][0]
    cell = row["conditions"]["v1_k24"]
    if mutation == "duplicate_case":
        receipt["cases"][1]["case_id"] = row["case_id"]
    elif mutation == "missing_case":
        receipt["cases"].pop()
    elif mutation == "forged_route":
        cell["route_found"] = False
    elif mutation == "forged_field":
        cell["required_fields_found"] = ["fabricated_secret"]
    elif mutation == "forged_unauthorized":
        cell["unauthorized_count"] = 1
    elif mutation == "wrong_report_count":
        receipt["actual_authorized_router_calls"] -= 1
    elif mutation == "fake_independent":
        receipt["scope"]["independent_confirmation"] = True
    elif mutation == "wrong_source_hash":
        receipt["source_sha256"] = "spoofed"
    elif mutation == "duplicated_top5":
        cell["top5_ids"].append(cell["top5_ids"][0])
    elif mutation == "missing_width":
        del row["conditions"]["v3_k56"]
    elif mutation == "missing_group":
        del receipt["by_scale_language_role"]["100/en/viewer"]
    elif mutation == "forged_aggregate":
        receipt["overall"]["v1_k24"]["required_routes_found"] += 1
    elif mutation == "nan_cpu":
        cell["retrieval_rerank_ms"] = float("nan")
    with pytest.raises(ValueError):
        audit(receipt)


def test_group_regression_does_not_fail_integrity_or_promote() -> None:
    receipt = _report()
    row = receipt["cases"][0]
    row["conditions"]["v3_k56"]["route_found"] = False
    row["conditions"]["v3_k56"]["required_fields_found"] = []
    row["conditions"]["v3_k56"]["all_required_fields_found"] = False
    row["conditions"]["v3_k56"]["top5_ids"] = []
    receipt["overall"]["v3_k56"] = {
        **receipt["overall"]["v3_k56"],
        **_aggregate(receipt["cases"], "v3_k56"),
    }
    key = f"100/{row['language']}/{row['role']}"
    group = [
        item for item in receipt["cases"]
        if item["language"] == row["language"] and item["role"] == row["role"]
    ]
    receipt["by_scale_language_role"][key]["v3_k56"] = {
        **receipt["by_scale_language_role"][key]["v3_k56"],
        **_aggregate(group, "v3_k56"),
    }
    result = audit(receipt)
    assert result["decisions"]["v3_k56"]["route_delta"] == -1
    assert result["decisions"]["v3_k56"]["group_regressions"]
    assert result["decisions"]["v3_k56"]["dev_diagnostic_gate"] is False
    assert result["decisions"]["v3_k56"]["may_promote"] is False
