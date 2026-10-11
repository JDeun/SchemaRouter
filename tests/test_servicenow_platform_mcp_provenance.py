"""Offline source-integrity and scorer-boundary regressions for issue #1228.

Only synthetic MCP objects: zero ServiceNow requests, tool execution or model
inference. This does not independently validate maintainer tool/field labels.
"""
from __future__ import annotations

import hashlib
import json
from copy import deepcopy

import pytest

from scripts.external_validation_servicenow_platform_mcp import (
    score,
    validate_package,
)


def _fixture():
    tools = [
        {"name": "query", "description": "Read ServiceNow rows", "inputSchema": {
            "type": "object",
            "properties": {
                "table": {"type": "string"},
                "limit": {"type": "integer"},
            },
        }},
        {"name": "describe", "description": "Describe metadata", "inputSchema": {
            "type": "object", "properties": {"table": {"type": "string"}}
        }},
    ]
    digest = hashlib.sha256(json.dumps(
        tools, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")).hexdigest()
    manifest = {
        "package_id": "test-servicenow-readonly",
        "status": "development_unfrozen",
        "source_revisions": {"servicenow_platform_mcp": "a" * 40},
        "upstream_runtime": {
            "tool_package": "readonly",
            "expected_public_tool_count": 2,
            "servicenow_platform_mcp_version": "test-pinned-2.1.2",
            "servicenow_environment": "prod",
        },
        "governance": {"heldout_scoring_allowed": False},
        "counts": {"cases": 2, "supported": 1, "unsupported": 1},
    }
    cases = {"case_set_id": manifest["package_id"], "cases": [
        {"id": "supported-read", "label": "supported", "required_tools": ["query"],
         "required_fields": {"query": ["table", "limit"]}},
        {"id": "ood", "label": "unsupported", "required_tools": [], "required_fields": {}},
    ]}
    snapshot = {
        "schema_version": 1,
        "source": {
            "repository": "Xerrion/servicenow-platform-mcp",
            "commit": "a" * 40,
            "package_version": "test-pinned-2.1.2",
        },
        "mcp_tool_package": "readonly",
        "servicenow_environment": "prod",
        "tool_count": 2,
        "tools_sha256": digest,
        "tools": tools,
    }
    return manifest, cases, snapshot


def _result(manifest, snapshot):
    return {"package_id": manifest["package_id"], "index_build_ms": 0,
            "results": [
                {"id": "supported-read", "candidate_tools": ["query"],
                 "visible_contracts": [snapshot["tools"][0]], "latency_ms": 0.5},
                {"id": "ood", "candidate_tools": [], "visible_contracts": [],
                 "latency_ms": 0.2},
            ]}


def test_paired_supported_and_unsupported_scores_are_source_bound():
    manifest, cases, snapshot = _fixture()
    validate_package(manifest, cases, snapshot)
    result = score(manifest, cases, snapshot, _result(manifest, snapshot))
    assert result["summary"]["supported_required_tool_recall"] == 1.0
    assert result["summary"]["supported_required_input_field_recall"] == 1.0
    assert result["summary"]["unsupported_nonempty_candidate_rate"] == 0.0


@pytest.mark.parametrize("mutation,reason", [
    (lambda s: s["tools"][0].update(description="tampered"), "SHA-256"),
    (lambda s: s.update(tools_sha256="0" * 64), "SHA-256"),
    (lambda s: s.update(tool_count=1), "count"),
    (lambda s: s["source"].update(package_version="other"), "version"),
    (lambda s: s["source"].update(repository="unexpected/repository"), "repository"),
    (lambda s: s.update(servicenow_environment="dev"), "environment"),
    (lambda s: s.update(schema_version=2), "schema version"),
])
def test_mutated_or_relabelled_capture_fails_before_scoring(mutation, reason):
    manifest, cases, snapshot = _fixture()
    mutation(snapshot)
    with pytest.raises(ValueError, match=reason):
        validate_package(manifest, cases, snapshot)


def test_duplicate_gold_fields_cannot_inflate_field_recall():
    manifest, cases, snapshot = _fixture()
    cases["cases"][0]["required_fields"]["query"] = ["table", "table", "limit"]
    with pytest.raises(ValueError, match="duplicate required input fields"):
        validate_package(manifest, cases, snapshot)


def test_duplicate_gold_tool_cannot_change_recall_denominator():
    manifest, cases, snapshot = _fixture()
    cases["cases"][0]["required_tools"] = ["query", "query"]
    with pytest.raises(ValueError, match="duplicate required tool"):
        validate_package(manifest, cases, snapshot)


def test_gold_fields_must_cover_each_gold_tool_exactly():
    manifest, cases, snapshot = _fixture()
    cases["cases"][0]["required_fields"] = {}
    with pytest.raises(ValueError, match="cover exactly"):
        validate_package(manifest, cases, snapshot)


def test_direct_scorer_rejects_stale_snapshot_digest():
    manifest, cases, snapshot = _fixture()
    submitted = deepcopy(_result(manifest, snapshot))
    snapshot["tools"][0]["inputSchema"]["properties"]["limit"]["type"] = "string"
    with pytest.raises(ValueError, match="SHA-256"):
        score(manifest, cases, snapshot, submitted)


def test_candidate_contract_substitution_is_rejected():
    manifest, cases, snapshot = _fixture()
    result = _result(manifest, snapshot)
    result["results"][0]["visible_contracts"] = [
        {**snapshot["tools"][0], "description": "fake different native contract"}
    ]
    with pytest.raises(ValueError, match="frozen upstream snapshot"):
        score(manifest, cases, snapshot, result)


def test_unsupported_candidate_exposure_is_reported_not_hidden():
    manifest, cases, snapshot = _fixture()
    result = _result(manifest, snapshot)
    result["results"][1]["candidate_tools"] = ["describe"]
    result["results"][1]["visible_contracts"] = [snapshot["tools"][1]]
    report = score(manifest, cases, snapshot, result)
    assert report["summary"]["unsupported_nonempty_candidate_rate"] == 1.0
    assert report["per_case"][1]["nonempty_candidate"] is True



def test_reviewer_worksheet_lists_all_cases_and_marks_known_dev_misses():
    from scripts.build_servicenow_maintainer_review_packet import build

    manifest, cases, snapshot = _fixture()
    text = build(manifest, cases, snapshot)
    assert "NOT HELD-OUT" in text
    assert "supported-read" in text and "ood" in text
    assert "Native MCP input-schema parameter reference" in text
    assert snapshot["tools_sha256"] in text
    assert "No task execution" in text
    assert "development errors" in text.lower()


def test_reviewer_worksheet_rejects_mutated_native_snapshot():
    from scripts.build_servicenow_maintainer_review_packet import build

    manifest, cases, snapshot = _fixture()
    snapshot["tools"][0]["description"] = "modified after capture"
    with pytest.raises(ValueError, match="SHA-256"):
        build(manifest, cases, snapshot)
