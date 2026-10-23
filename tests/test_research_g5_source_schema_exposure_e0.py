"""G5 original-source menu cost is not a new model/token/quality claim."""
from __future__ import annotations

import pytest

from scripts.research_g5_source_schema_exposure_e0 import (
    MAX_K,
    SCHEMA_VERSION,
    _visible_original_contract_bytes,
    authorized_source_contract_budget,
    evaluate_fixture,
)
from scripts.benchmark_native_fork_fieldgroup_e0 import build_fixture


def test_g5_actual_500_route_three_language_oracle_and_scope():
    report = evaluate_fixture(registered_routes=500, mixed_scope=True)
    assert report["schema_version"] == SCHEMA_VERSION
    assert report["registered_native_routes"] == 500
    assert report["strict_k"] == MAX_K == 5
    assert report["mixed_source_scope_and_contract_decoys"] is True
    assert report["independent_e2_qualified"] is False
    assert report["all_model_tokens_measured"] is False
    assert report["unbounded_full_is_matched_k5_agent_control"] is False
    assert report["same_snapshot_health_revocation_denied"] is True
    assert len(report["frozen_original_source_budget_digest"]) == 64
    assert [row["language"] for row in report["rows"]] == ["en", "ko", "ja"]
    for row in report["rows"]:
        assert row["qualified_distinct_native_routes"] == 3
        assert row["qualified_g5_fork_count"] == 1
        assert row["source_oracle_exact_match"] is True
        assert row["typed_producer_consumer_binding"] is True
        assert row["scope_approved_k5"] is True
        assert row["g5_original_source_schema_bytes"] > 0
        assert (
            row["g5_original_source_schema_bytes"]
            == row["same_success_oracle_schema_bytes"]
        )
        assert (
            row["unbounded_full_principal_source_schema_bytes"]
            > row["g5_original_source_schema_bytes"]
        )


@pytest.mark.parametrize("wrong", [0, 1, 499, 501, 1000, 5001, True, 500.0])
def test_rejects_unregistered_g5_catalog_size(wrong):
    with pytest.raises(ValueError, match="preregistered"):
        evaluate_fixture(registered_routes=wrong)


def test_invalid_mixed_scope_type_fails_closed_without_source_build():
    with pytest.raises(ValueError, match="boolean"):
        evaluate_fixture(registered_routes=500, mixed_scope="allow")


def test_source_budget_is_original_principal_scoped_not_untrusted_tool_ids():
    router = build_fixture(500, mixed_scope=True)
    a, digest_a = authorized_source_contract_budget(router)
    b, digest_b = authorized_source_contract_budget(router)
    assert a == b and digest_a == digest_b
    assert "fork_origin.read" in a
    assert "fork_status.read" in a
    assert "fork_owner.read" in a
    assert "fork_status_denied.read" not in a
    assert all(type(v) is int and v > 0 for v in a.values())


def test_contract_serializer_requires_source_owned_objects():
    with pytest.raises(ValueError):
        _visible_original_contract_bytes({}, {})
