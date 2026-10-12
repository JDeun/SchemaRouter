"""Synthetic-only prospective no-match evaluation audit tests; not external data."""
from __future__ import annotations

import hashlib

import pytest

from schemarouter import EndpointSpec, SchemaRouter, ToolSpec
from scripts.audit_prospective_no_match import audit, canonical_sha


def query_sha(text: str) -> str:
    return hashlib.sha256(text.strip().casefold().encode("utf-8")).hexdigest()


def fixture():
    router = SchemaRouter()
    router.add_tool(ToolSpec(
        name="paper", description="Synthetic paper catalog",
        endpoints=[
            EndpointSpec(name="search", description="Search papers", read_only=True),
            EndpointSpec(name="get", description="Get paper", read_only=True),
        ],
    ))
    queries = ["search research papers", "reserve an airplane ticket"]
    ranks = [router.retrieve(query, k=2) for query in queries]
    raw_top = max(retrieval.candidates[0].score for retrieval in ranks)
    cohorts = {"schema_version": 1, "role": "prospective_unreviewed", "cases": [
        {
            "id": "synthetic-supported-01", "label": "supported",
            "query_sha256": query_sha(queries[0]),
            "expected_routes": [ranks[0].candidates[0].route_id],
            "forbidden_routes": [],
        },
        {
            "id": "synthetic-unsupported-02", "label": "unsupported",
            "query_sha256": query_sha(queries[1]),
            "expected_routes": [], "forbidden_routes": [],
        },
    ]}
    plan = {
        "schema_version": 1, "status": "unscored_prospective_draft",
        "approved": False, "source_sha": "a" * 40,
        "scorer_sha": "b" * 40, "registry_sha256": "c" * 64,
        "case_sha256": canonical_sha(cohorts),
        "policy": {"min_score": raw_top + 1.0},
        "top_k": 2,
    }
    obs = {
        "schema_version": 1, "plan_sha256": canonical_sha(plan),
        "case_sha256": plan["case_sha256"],
        "rows": [{
            "id": row["id"], "retrieval": ranking.model_dump(mode="json"),
            "retrieval_ms": 1.0 + i,
        } for i, (row, ranking) in enumerate(
            zip(cohorts["cases"], ranks, strict=True)
        )],
    }
    old = [
        {"cases": [{"id": "old-dev-01", "query": "past historical prompt"}]},
        {"cases": [{"id": "new-dev-01", "query": "new visible development query"}]},
    ]
    return plan, cohorts, obs, old


def test_approved_gate_cannot_be_faked_by_unscored_report():
    plan, cases, obs, excluded = fixture()
    result = audit(plan, cases, obs, excluded)
    assert result["status"] == "UNSCORED_NOT_INDEPENDENTLY_VERIFIED"
    assert result["approved"] is False
    assert result["count"] == 2
    assert result["counts"]["supported_raw_hit"] == 1
    assert result["counts"]["supported_false_refusal"] == 1
    assert result["counts"]["supported_selected_hit"] == 0
    assert result["counts"]["unsupported_raw_nonempty"] == 1
    assert result["counts"]["unsupported_selected_nonempty"] == 0
    assert result["counts"]["abstained"] == 2
    assert result["mean_candidate_metadata_bytes_after"] <= (
        result["mean_candidate_metadata_bytes_before"]
    )


def test_frozen_plan_policy_edit_invalidates_observations():
    plan, cases, obs, old = fixture()
    plan["policy"]["min_score"] = -100000.0
    with pytest.raises(ValueError, match="not pinned"):
        audit(plan, cases, obs, old)


@pytest.mark.parametrize("mutation,match", [
    ("approved", "unapproved"),
    ("unknown_plan", "unknown or missing"),
    ("stale_case_hash", "digest mismatch"),
    ("missing_result", "missing or extra"),
    ("duplicated_result", "unknown or duplicate"),
    ("added_result_score", "unknown or missing"),
    ("tampered_query", "not identical"),
    ("old_dev_id", "reused known"),
    ("old_dev_query", "reused known"),
    ("bad_latency", "latency"),
    ("bad_policy", "validation|threshold|finite"),
    ("bad_label", "unknown open-set"),
])
def test_prospective_evidence_guard_rejects_invalid_inputs(
    mutation, match,
):
    plan, cases, obs, old = fixture()
    if mutation == "approved":
        plan["approved"] = True
    elif mutation == "unknown_plan":
        plan["hidden_gold"] = True
    elif mutation == "stale_case_hash":
        cases["cases"][0]["expected_routes"] = ["unsupported.tool"]
    elif mutation == "missing_result":
        obs["rows"].pop()
    elif mutation == "duplicated_result":
        obs["rows"][1]["id"] = obs["rows"][0]["id"]
    elif mutation == "added_result_score":
        obs["rows"][0]["task_success"] = True
    elif mutation == "tampered_query":
        obs["rows"][0]["retrieval"]["query"] = "different query"
    elif mutation == "old_dev_id":
        cases["cases"][0]["id"] = "old-dev-01"
        plan["case_sha256"] = canonical_sha(cases)
    elif mutation == "old_dev_query":
        cases["cases"][0]["query_sha256"] = query_sha("past historical prompt")
        plan["case_sha256"] = canonical_sha(cases)
    elif mutation == "bad_latency":
        obs["rows"][0]["retrieval_ms"] = -1.0
    elif mutation == "bad_policy":
        plan["policy"] = {"min_score": float("inf")}
    elif mutation == "bad_label":
        cases["cases"][0]["label"] = "posthoc_pass"
        plan["case_sha256"] = canonical_sha(cases)
    if mutation in {"old_dev_id", "old_dev_query", "bad_label"}:
        obs["case_sha256"] = plan["case_sha256"]
        obs["plan_sha256"] = canonical_sha(plan)
    with pytest.raises((ValueError, TypeError), match=match):
        audit(plan, cases, obs, old)


def test_forbidden_exposure_and_supported_miss_are_reported_not_hidden():
    plan, cases, obs, old = fixture()
    plan["policy"] = {"min_score": -1e8}
    cases["cases"][1]["label"] = "forbidden"
    cases["cases"][1]["forbidden_routes"] = [
        obs["rows"][1]["retrieval"]["candidates"][0]["route_id"],
    ]
    plan["case_sha256"] = canonical_sha(cases)
    obs["plan_sha256"] = canonical_sha(plan)
    obs["case_sha256"] = plan["case_sha256"]
    result = audit(plan, cases, obs, old)
    assert result["counts"]["forbidden"] == 1
    assert result["counts"]["forbidden_selected_exposure"] == 1
    assert result["counts"]["supported_selected_hit"] == 1
    assert result["counts"]["abstained"] == 0
