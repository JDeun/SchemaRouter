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
            "expected_readonly_tools_sha256": digest,
            "servicenow_platform_mcp_version": "test-pinned-2.1.2",
            "servicenow_environment": "prod",
        },
        "governance": {"heldout_scoring_allowed": False},
        "comparison": {
            "primary_conditions": [
                "static_readonly",
                "readonly_plus_schemarouter_preselection",
            ],
            "development_top_k_sensitivity": [3, 5],
        },
        "counts": {"cases": 2, "supported": 1, "unsupported": 1},
    }
    cases = {"case_set_id": manifest["package_id"], "cases": [
        {"id": "supported-read", "query": "Read three incident records", "label": "supported",
         "required_tools": ["query"], "required_fields": {"query": ["table", "limit"]}},
        {"id": "ood", "query": "Make a sandwich", "label": "unsupported",
         "required_tools": [], "required_fields": {}},
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
    return {
        "package_id": manifest["package_id"],
        "index_build_ms": 0,
        "implementation": {
            "name": "SchemaRouter over ServiceNow readonly MCP tools/list",
            "fixture_reference_revision": manifest["source_revisions"]["schemarouter"],
            "configuration": {
                "condition": "readonly_plus_schemarouter_preselection",
                "top_k": 3,
                "upstream_tool_package": "readonly",
                "mcp_ingestion": "schemarouter.adapters.mcp.tool_from_mcp",
                "api": "SchemaRouter.retrieve",
                "execution": "disabled",
            },
        },
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



def test_recomputed_mutated_snapshot_digest_cannot_bypass_pinned_manifest():
    manifest, cases, snapshot = _fixture()
    snapshot["tools"][0]["description"] = "new yet self-consistent counterfeit schema"
    snapshot["tools_sha256"] = hashlib.sha256(json.dumps(
        snapshot["tools"], ensure_ascii=False, sort_keys=True, separators=(",", ":"),
    ).encode("utf-8")).hexdigest()
    with pytest.raises(ValueError, match="independently pinned digest"):
        validate_package(manifest, cases, snapshot)


def test_missing_or_malformed_manifest_pinned_digest_fails_closed():
    for digest in (None, "0" * 63, "g" * 64, 42):
        manifest, cases, snapshot = _fixture()
        manifest["upstream_runtime"]["expected_readonly_tools_sha256"] = digest
        with pytest.raises(ValueError, match="independently pinned digest"):
            validate_package(manifest, cases, snapshot)



def _static_result(manifest, snapshot):
    names = [tool["name"] for tool in snapshot["tools"]]
    rows = [
        {
            "id": case_id,
            "candidate_tools": list(names),
            "visible_contracts": deepcopy(snapshot["tools"]),
            "latency_ms": 0.25,
        }
        for case_id in ("supported-read", "ood")
    ]
    return {
        "package_id": manifest["package_id"],
        "index_build_ms": 0.0,
        "implementation": {
            "name": "ServiceNow Platform MCP static readonly package",
            "commit": snapshot["source"]["commit"],
            "fixture_reference_revision": manifest["source_revisions"]["servicenow_platform_mcp"],
            "package_version": snapshot["source"]["package_version"],
            "configuration": {
                "condition": "static_readonly",
                "tool_package": "readonly",
                "tool_count": len(names),
                "repeats_per_query": 3,
                "execution": "disabled",
            },
        },
        "results": rows,
    }


def test_valid_full_native_static_baseline_succeeds_without_ranking_claim():
    manifest, cases, snapshot = _fixture()
    report = score(manifest, cases, snapshot, _static_result(manifest, snapshot))
    assert report["summary"]["supported_required_tool_recall"] == 1.0
    assert report["summary"]["unsupported_nonempty_candidate_rate"] == 1.0
    assert report["summary"]["mean_active_tool_count"] == 2


@pytest.mark.parametrize("mutation,reason", [
    (
        lambda submitted: submitted["implementation"]["configuration"].update(
            condition="static_readonly"
        ),
        "static package",
    ),
    (
        lambda submitted: submitted["implementation"]["configuration"].update(
            top_k=True
        ),
        "Top-K",
    ),
    (
        lambda submitted: submitted["implementation"]["configuration"].update(
            top_k=500
        ),
        "Top-K",
    ),
    (
        lambda submitted: submitted["implementation"]["configuration"].update(
            execution="enabled"
        ),
        "never execute",
    ),
    (
        lambda submitted: submitted["implementation"]["configuration"].update(
            upstream_tool_package="core"
        ),
        "provenance",
    ),
    (
        lambda submitted: submitted.update(implementation={}),
        "configuration",
    ),
])
def test_forged_preselection_identity_budget_or_execution_rejected(mutation, reason):
    manifest, cases, snapshot = _fixture()
    payload = _result(manifest, snapshot)
    mutation(payload)
    with pytest.raises(ValueError, match=reason):
        score(manifest, cases, snapshot, payload)


def test_preselection_cannot_expose_more_native_tools_than_declared_topk():
    manifest, cases, snapshot = _fixture()
    # Four genuinely distinct synthetic native contracts, all inside the
    # independently pinned snapshot. This tests K, not unknown-tool rejection.
    for i in range(2):
        tool = deepcopy(snapshot["tools"][0])
        tool["name"] = f"extra_read_{i}"
        snapshot["tools"].append(tool)
    digest = hashlib.sha256(json.dumps(
        snapshot["tools"], ensure_ascii=False, sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")).hexdigest()
    snapshot["tools_sha256"] = digest
    snapshot["tool_count"] = 4
    manifest["upstream_runtime"]["expected_public_tool_count"] = 4
    manifest["upstream_runtime"]["expected_readonly_tools_sha256"] = digest
    submitted = _result(manifest, snapshot)
    submitted["results"][0]["candidate_tools"] = [
        tool["name"] for tool in snapshot["tools"]
    ]
    submitted["results"][0]["visible_contracts"] = deepcopy(snapshot["tools"])
    with pytest.raises(ValueError, match="exceeds frozen Top-K"):
        score(manifest, cases, snapshot, submitted)


@pytest.mark.parametrize("field,value", [
    ("tool_count", 1),
    ("tool_count", True),
    ("tool_package", "core_readonly"),
    ("execution", "enabled"),
])
def test_static_package_identity_cannot_be_relabelled(field, value):
    manifest, cases, snapshot = _fixture()
    payload = _static_result(manifest, snapshot)
    payload["implementation"]["configuration"][field] = value
    with pytest.raises(ValueError):
        score(manifest, cases, snapshot, payload)


def test_static_must_show_entire_native_package_in_native_order():
    manifest, cases, snapshot = _fixture()
    payload = _static_result(manifest, snapshot)
    payload["results"][1]["candidate_tools"] = ["query"]
    payload["results"][1]["visible_contracts"] = [snapshot["tools"][0]]
    with pytest.raises(ValueError, match="entire native package"):
        score(manifest, cases, snapshot, payload)


@pytest.mark.parametrize("governance", [{}, {"heldout_scoring_allowed": 0},
                                         {"heldout_scoring_allowed": None}])
def test_dev_governance_requires_explicit_false_not_absence_or_zero(governance):
    manifest, cases, snapshot = _fixture()
    manifest["governance"] = governance
    with pytest.raises(ValueError, match="explicitly disable"):
        score(manifest, cases, snapshot, _result(manifest, snapshot))


def test_runners_validate_native_digest_before_any_dev_execution(tmp_path):
    from scripts import run_servicenow_schemarouter_external_validation as routing
    from scripts import run_servicenow_static_external_validation as static

    manifest, cases, snapshot = _fixture()
    manifest["files"] = {"cases": "cases.json"}
    manifest["comparison"]["latency_repeats"] = 3
    manifest["comparison"]["schemarouter_top_k"] = 3
    path = tmp_path / "snapshot.json"
    (tmp_path / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    (tmp_path / "cases.json").write_text(json.dumps(cases), encoding="utf-8")
    # A substituted tool has the correct count but a mismatching frozen digest.
    snapshot["tools"][0]["description"] = "counterfeit native MCP contract"
    path.write_text(json.dumps(snapshot), encoding="utf-8")
    with pytest.raises(ValueError, match="SHA-256"):
        static.run(package_dir=tmp_path, snapshot_path=path, repeats=1)
    with pytest.raises(ValueError, match="SHA-256"):
        routing.run(
            package_dir=tmp_path, snapshot_path=path, repeats=1,
            implementation_revision="0" * 40, top_k=3,
        )


@pytest.mark.parametrize("repeats", [True, 0, -1, 0.5, "2"])
def test_static_runner_rejects_noninteger_repeats_before_measurement(
    tmp_path, repeats,
):
    from scripts import run_servicenow_static_external_validation as static

    manifest, cases, snapshot = _fixture()
    manifest["files"] = {"cases": "cases.json"}
    manifest["comparison"]["latency_repeats"] = 2
    (tmp_path / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    (tmp_path / "cases.json").write_text(json.dumps(cases), encoding="utf-8")
    path = tmp_path / "snapshot.json"
    path.write_text(json.dumps(snapshot), encoding="utf-8")
    with pytest.raises(ValueError, match="repeats"):
        static.run(package_dir=tmp_path, snapshot_path=path, repeats=repeats)


@pytest.mark.parametrize("mutation", [
    lambda record: record.pop("fixture_reference_revision"),
    lambda record: record.update(fixture_reference_revision="0" * 40),
])
def test_result_cannot_claim_wrong_source_fixture_revision(mutation):
    manifest, cases, snapshot = _fixture()
    submitted = _result(manifest, snapshot)
    mutation(submitted["implementation"])
    with pytest.raises(ValueError, match="fixture-reference revision mismatch"):
        score(manifest, cases, snapshot, submitted)


def test_static_runner_version_cannot_disagree_with_native_package():
    manifest, cases, snapshot = _fixture()
    submitted = _static_result(manifest, snapshot)
    submitted["implementation"]["package_version"] = "unrelated-package"
    with pytest.raises(ValueError, match="static package"):
        score(manifest, cases, snapshot, submitted)
