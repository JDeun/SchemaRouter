from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import pytest

from scripts.external_validation_provenance import implementation_provenance
from scripts.external_validation_smart_mcp import (
    build_template,
    load_package,
    score,
    validate_package,
)

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "benchmarks" / "external-validation-smart-mcp-dev-v1"


def test_smartmcp_cross_project_dev_fixture_is_consistent() -> None:
    manifest, catalog, cases = load_package(PACKAGE)
    validate_package(manifest, catalog, cases)

    assert manifest["status"] == "development_unfrozen"
    assert manifest["governance"]["heldout_scoring_allowed"] is False
    assert manifest["source_revisions"]["smartmcp"] == (
        "c4d6602cfabb6f514bf06a1d1ae10b610ff7d573"
    )
    assert manifest["counts"] == {
        "tools": 21,
        "cases": 33,
        "supported": 27,
        "ambiguous": 3,
        "unsupported": 3,
        "multi_tool": 3,
    }
    assert manifest["comparison"]["top_k_values"] == [1, 3, 5]


def test_smartmcp_snapshot_is_exact_projection_of_shared_catalog() -> None:
    manifest, catalog, _ = load_package(PACKAGE)
    import json

    snapshot = json.loads(
        (PACKAGE / manifest["files"]["smartmcp_snapshot"]).read_text(encoding="utf-8")
    )
    canonical = {
        tool["name"]: {
            "description": tool["description"],
            "inputSchema": tool["input_schema"],
        }
        for tool in catalog["tools"]
    }
    observed = {
        tool["name"]: {
            "description": tool["description"],
            "inputSchema": tool["inputSchema"],
        }
        for tool in snapshot
    }
    assert observed == canonical


def test_shared_scorer_rewards_complete_ranked_retrieval() -> None:
    manifest, catalog, cases = load_package(PACKAGE)
    validate_package(manifest, catalog, cases)
    tool_map = {tool["name"]: tool for tool in catalog["tools"]}
    submitted = build_template(manifest, cases)
    submitted["implementation"] = {
        "name": "perfect-fixture",
        "commit": "fixture-only",
        "configuration": {},
    }
    submitted["index_build_ms"] = 10.0

    rows = {row["id"]: row for row in submitted["results"]}
    for case in cases["cases"]:
        row = rows[case["id"]]
        row["latency_ms"] = 1.0
        if case["label"] == "supported":
            row["candidate_tools"] = list(case["required_tools"])
        elif case["label"] == "ambiguous":
            row["candidate_tools"] = [case["acceptable_candidate_tools"][0]]
        else:
            row["candidate_tools"] = []

        row["exposed_contracts"] = [
            {
                "target": name,
                "description": tool_map[name]["description"],
                "input_schema": tool_map[name]["input_schema"],
            }
            for name in row["candidate_tools"]
        ]

    result = score(manifest, catalog, cases, submitted)
    summary = result["summary"]
    assert summary["supported_recall_at_1"] < 1.0  # multi-tool cases need K > 1
    assert summary["supported_recall_at_3"] == 1.0
    assert summary["supported_full_coverage_at_3"] == 1.0
    assert summary["supported_ndcg_at_3"] == 1.0
    assert summary["supported_mrr"] == 1.0
    assert summary["unsupported_nonempty_candidate_rate"] == 0.0
    assert summary["ambiguous_top1_acceptable_rate"] == 1.0
    assert summary["median_retrieval_ms"] == 1.0
    assert summary["p95_retrieval_ms"] == 1.0


def test_shared_scorer_rejects_candidate_duplicates() -> None:
    manifest, catalog, cases = load_package(PACKAGE)
    submitted = build_template(manifest, cases)
    first = cases["cases"][0]
    target = first["required_tools"][0]
    submitted["results"][0]["candidate_tools"] = [target, target]

    with pytest.raises(ValueError, match="must not contain duplicates"):
        score(manifest, catalog, cases, submitted)


def test_explicit_execution_revision_is_not_replaced_by_fixture_revision() -> None:
    provenance = implementation_provenance(
        fixture_reference_revision="fixture-old-sha",
        explicit_revision="executed-new-sha",
    )

    assert provenance == {
        "commit": "executed-new-sha",
        "commit_source": "explicit",
        "fixture_reference_revision": "fixture-old-sha",
        "package_version": None,
    }


def test_heldout_scoring_requires_actual_execution_revision() -> None:
    manifest, catalog, cases = load_package(PACKAGE)
    heldout = deepcopy(manifest)
    heldout["status"] = "heldout_frozen"
    heldout["governance"] = {
        **heldout["governance"],
        "heldout_scoring_allowed": True,
    }
    submitted = build_template(heldout, cases)

    with pytest.raises(
        ValueError,
        match="held-out scoring requires the actual implementation.commit",
    ):
        score(heldout, catalog, cases, submitted)
