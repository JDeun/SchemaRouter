from __future__ import annotations

from pathlib import Path

from scripts.external_validation_hope_agent import (
    build_template,
    load_package,
    score,
    validate_package,
)

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "benchmarks" / "external-validation-hope-agent-v1"


def test_hope_agent_offline_package_is_frozen_and_field_labeled() -> None:
    manifest, catalog, cases = load_package(PACKAGE)
    validate_package(manifest, catalog, cases)

    assert manifest["source_revisions"]["hope_agent"] == (
        "2784abba5823922dba06a3c722eba0ca91f69fd6"
    )
    assert manifest["comparison_boundary"]["top_k"] == 3
    assert manifest["comparison_boundary"]["execution"] == "disabled"
    assert manifest["frozen_counts"] == {
        "tools": 12,
        "cases": 16,
        "supported": 10,
        "unsupported": 3,
        "ambiguous": 3,
    }
    supported = [case for case in cases["cases"] if case["label"] == "supported"]
    assert supported
    assert all(case["required_fields"] for case in supported)


def test_hope_agent_offline_scorer_separates_candidate_activation_and_schema() -> None:
    manifest, catalog, cases = load_package(PACKAGE)
    validate_package(manifest, catalog, cases)
    tool_map = {tool["name"]: tool for tool in catalog["tools"]}
    submitted = build_template(manifest, cases)
    submitted["implementation"] = {
        "name": "perfect-fixture",
        "commit": "fixture-only",
        "configuration": {},
    }

    rows = {row["id"]: row for row in submitted["results"]}
    for case in cases["cases"]:
        row = rows[case["id"]]
        row["cold_start_ms"] = 10.0
        row["hot_path_ms"] = 1.0
        if case["label"] != "supported":
            continue
        required = list(case["required_tools"])
        row["candidate_tools"] = required
        row["activated_tools"] = required
        row["exposed_schemas"] = []
        for tool_name in required:
            canonical = tool_map[tool_name]
            required_fields = set(case["required_fields"][tool_name])
            row["exposed_schemas"].append(
                {
                    "name": tool_name,
                    "description": canonical["description"],
                    "input_schema": canonical["input_schema"],
                    "output_fields": [
                        field
                        for field in canonical["output_fields"]
                        if field["name"] in required_fields
                    ],
                    "read_only": canonical["read_only"],
                    "destructive": canonical["destructive"],
                }
            )

    result = score(manifest, catalog, cases, submitted)
    summary = result["summary"]
    assert summary["supported_candidate_tool_recall"] == 1.0
    assert summary["supported_activation_tool_recall"] == 1.0
    assert summary["supported_required_field_recall"] == 1.0
    assert summary["unsupported_false_activation_rate"] == 0.0
    assert summary["ambiguous_false_activation_rate"] == 0.0
    assert summary["schema_budget_compliance_rate"] == 1.0
