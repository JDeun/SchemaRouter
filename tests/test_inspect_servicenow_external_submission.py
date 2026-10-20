"""Mock publisher submission input only: no independent gold or provider calls."""
from __future__ import annotations

import hashlib
import json
from copy import deepcopy

import pytest

from scripts.inspect_servicenow_external_submission import (
    inspect_submitted_bytes,
)


def _package():
    tools = [{
        "name": "query", "description": "read-only native rows",
        "inputSchema": {"type": "object", "properties": {
            "table": {"type": "string"}, "limit": {"type": "integer"},
        }},
    }, {
        "name": "describe", "description": "read-only native schema",
        "inputSchema": {"type": "object", "properties": {
            "table": {"type": "string"},
        }},
    }]
    digest = hashlib.sha256(json.dumps(
        tools, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
    ).encode("utf-8")).hexdigest()
    manifest = {
        "package_id": "synthetic-service-dev-not-external",
        "status": "development_unfrozen",
        "source_revisions": {"servicenow_platform_mcp": "a" * 40},
        "upstream_runtime": {
            "tool_package": "readonly",
            "expected_public_tool_count": 2,
            "expected_readonly_tools_sha256": digest,
            "servicenow_platform_mcp_version": "test-2.1.2",
            "servicenow_environment": "prod",
        },
        "governance": {"heldout_scoring_allowed": False},
        "comparison": {
            "primary_conditions": [
                "static_readonly", "readonly_plus_schemarouter_preselection",
            ],
            "development_top_k_sensitivity": [3, 5],
        },
        "counts": {"cases": 2, "supported": 1, "unsupported": 1},
    }
    dev = {
        "case_set_id": manifest["package_id"],
        "cases": [{
            "id": "sn-dev-001", "query": "Read incident records for today",
            "label": "supported", "required_tools": ["query"],
            "required_fields": {"query": ["table"]},
        }, {
            "id": "sn-dev-002", "query": "Make a blueberry smoothie",
            "label": "unsupported", "required_tools": [], "required_fields": {},
        }],
    }
    snapshot = {
        "schema_version": 1,
        "source": {
            "repository": "Xerrion/servicenow-platform-mcp",
            "commit": "a" * 40,
            "package_version": "test-2.1.2",
        },
        "mcp_tool_package": "readonly",
        "servicenow_environment": "prod",
        "tool_count": 2, "tools_sha256": digest, "tools": tools,
    }
    return manifest, dev, snapshot


def _submission(manifest, snapshot):
    # Only validation scaffolding; these strings are NOT external authoring.
    tasks = [
        ("en", "Audit equipment intake queue at depot alpha",
         "Compare ocean currents off the far coastline"),
        ("ko", "기록된 자산 변경 추적 검토",
         "은하계 바깥의 별자리 여행 계획"),
        ("ja", "管理帳票の一覧を確認する",
         "火山帯の旅程と観光列車を計画"),
    ]
    cases = []
    for i, (language, positive, negative) in enumerate(tasks):
        cases.extend([{
            "id": f"sn-ext-example-{language}-pos",
            "language": language, "label": "supported",
            "query": positive, "required_tools": ["query"],
            "required_fields": {"query": ["table"]},
        }, {
            "id": f"sn-ext-example-{language}-ood",
            "language": language, "label": "unsupported",
            "query": negative, "required_tools": [], "required_fields": {},
        }])
    return {
        "schema_version": 1, "split": "proposed_external_unscored",
        "source": {
            "repository": "Xerrion/servicenow-platform-mcp",
            "revision": manifest["source_revisions"]["servicenow_platform_mcp"],
            "package": "readonly",
            "tools_sha256": snapshot["tools_sha256"],
        },
        "author_claim": {
            "authorship_type": "external_publisher_claimed",
            "review_requested": True,
            "organization": "Unverified synthetic example, never a publisher",
            "verified_by_schemarouter": False,
        },
        "cases": cases,
    }


def _inspect(data, *, manifest=None, dev=None, snapshot=None):
    original = _package()
    manifest = original[0] if manifest is None else manifest
    dev = original[1] if dev is None else dev
    snapshot = original[2] if snapshot is None else snapshot
    raw = json.dumps(data, ensure_ascii=False).encode("utf-8")
    return inspect_submitted_bytes(
        raw,
        declared_sha256=hashlib.sha256(raw).hexdigest(),
        manifest=manifest, dev_cases=dev, snapshot=snapshot,
    )


def test_mock_intake_never_grants_independence_or_scores_public_cases():
    manifest, dev, snapshot = _package()
    data = _submission(manifest, snapshot)
    result = _inspect(data, manifest=manifest, dev=dev, snapshot=snapshot)
    assert result["status"] == "BLOCKED_EXTERNAL_REVIEW_UNSCORED"
    assert result["evidence_tier"] == (
        "PROVISIONAL_EXTERNAL_AUTHORSHIP_CLAIM_NOT_ATTESTED"
    )
    assert result["case_count"] == 6
    assert result["missing_minimum_language_strata"] == []
    assert result["native_snapshot_sha256"] == snapshot["tools_sha256"]
    assert all(result["language_stratum_counts"][lang] == {
        "supported": 1, "unsupported": 1, "forbidden": 0,
    } for lang in ("en", "ko", "ja"))
    assert result["author_identity_verified"] is False
    assert result["source_originality_semantically_verified"] is False
    assert result["heldout_scoring_allowed"] is False
    assert result["independent_e2_qualified"] is False
    assert result["calibrated_no_fit"] is False
    assert result["provider_native_tool_execution_measured"] is False
    emitted = json.dumps(result, ensure_ascii=False)
    assert "Unverified synthetic example" not in emitted
    assert "Audit equipment" not in emitted
    assert "기록된 자산" not in emitted
    assert "管理帳票" not in emitted
    assert "sn-ext-example" not in emitted


@pytest.mark.parametrize("mutation,pattern", [
    (lambda d: d.update(split="independent_confirmed"), "proposed"),
    (lambda d: d.update(scoring_authorized=True), "cannot attest"),
    (lambda d: d.update(independent_qualified=True), "cannot attest"),
    (lambda d: d["source"].update(revision="b" * 40), "source pin"),
    (lambda d: d["source"].update(tools_sha256="f" * 64), "source pin"),
    (lambda d: d["author_claim"].update(
        verified_by_schemarouter=True,
    ), "independent review"),
    (lambda d: d["cases"][0].update(id="sn-dev-001"), "case ID"),
    (lambda d: d["cases"][0].update(label="accepted"), "language/stratum"),
    (lambda d: d["cases"][0].update(language="fr"), "language/stratum"),
    (lambda d: d["cases"][0].update(required_tools=["invented"]), "gold"),
    (lambda d: d["cases"][0].update(
        required_fields={"query": ["unavailable"]},
    ), "not present"),
    (lambda d: d["cases"][1].update(required_tools=["query"]), "gold"),
    (lambda d: d["cases"][0].update(
        query="Read incident records for today please",
    ), "overlaps public DEV"),
    (lambda d: d["cases"][0].update(query="Read incident records for today"),
     "overlaps public DEV"),
    (lambda d: d["cases"][2].update(query="Audit equipment intake queue at depot alpha"),
     "overlaps public DEV"),
])
def test_mock_external_intake_rejects_source_gold_or_dev_leak(mutation, pattern):
    manifest, _, snapshot = _package()
    data = _submission(manifest, snapshot)
    mutation(data)
    with pytest.raises(ValueError, match=pattern):
        _inspect(data)


def test_exact_bytes_duplicate_json_keys_and_raw_sha_are_nonnegotiable():
    manifest, dev, snapshot = _package()
    data = _submission(manifest, snapshot)
    original = json.dumps(data, ensure_ascii=False).encode()
    with pytest.raises(ValueError, match="SHA-256 mismatch"):
        inspect_submitted_bytes(
            original + b" ",
            declared_sha256=hashlib.sha256(original).hexdigest(),
            manifest=manifest, dev_cases=dev, snapshot=snapshot,
        )
    duplicate = b'{"schema_version":1,"schema_version":1}'
    with pytest.raises(ValueError, match="invalid strict external"):
        inspect_submitted_bytes(
            duplicate, declared_sha256=hashlib.sha256(duplicate).hexdigest(),
            manifest=manifest, dev_cases=dev, snapshot=snapshot,
        )
    with pytest.raises(ValueError, match="empty, oversized"):
        inspect_submitted_bytes(
            b" " * (512 * 1024 + 1),
            declared_sha256="0" * 64,
            manifest=manifest, dev_cases=dev, snapshot=snapshot,
        )


def test_missing_strata_are_disclosed_not_silently_scored():
    m, _, sn = _package()
    d = _submission(m, sn)
    d["cases"] = [row for row in d["cases"] if row["language"] == "en"]
    report = _inspect(d)
    assert report["status"] == "BLOCKED_EXTERNAL_REVIEW_UNSCORED"
    assert set(report["missing_minimum_language_strata"]) == {
        "ko:supported", "ko:unsupported", "ja:supported", "ja:unsupported",
    }


def test_pinned_native_snapshot_digest_mismatch_rejected_even_if_self_rehashed():
    m, dev, sn = _package()
    data = _submission(m, sn)
    changed = deepcopy(sn)
    changed["tools"][0]["description"] = "new upstream unrelated schema"
    digest = hashlib.sha256(json.dumps(
        changed["tools"], ensure_ascii=False, sort_keys=True,
        separators=(",", ":"),
    ).encode()).hexdigest()
    changed["tools_sha256"] = digest
    data["source"]["tools_sha256"] = digest
    with pytest.raises(ValueError, match="independently pinned digest"):
        _inspect(data, manifest=m, dev=dev, snapshot=changed)
