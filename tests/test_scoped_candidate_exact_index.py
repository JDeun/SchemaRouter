"""Exact-permutation parity for a transient, per-request authorized index (#1431).

The baseline is the same current code with candidate_index=False: the former
exhaustive visible-schema scoring path, not a second scoring implementation.
"""
from __future__ import annotations

import pytest

from benchmarks.current_adapter_field_scope_dev_v1 import principal
from benchmarks.current_adapter_scaled_authorized_dev_v1 import (
    DENIED_VIEWER,
    build_fixture,
)
from schemarouter import PlanRequest


def _paired(router, *, role: str, query: str, k: int) -> tuple:
    who = principal(role)
    old = router.planner.candidate_index
    try:
        router.planner.candidate_index = False
        baseline = router.retrieve_authorized(
            PlanRequest(query=query), principal=who, k=k,
        )
        router.planner.candidate_index = True
        optimized = router.retrieve_authorized(
            PlanRequest(query=query), principal=who, k=k,
        )
    finally:
        router.planner.candidate_index = old
    return baseline, optimized


@pytest.mark.parametrize("role", ("viewer", "editor"))
@pytest.mark.parametrize("k", (5, 24, 56))
@pytest.mark.parametrize("query", (
    "Read invoice total amount and status",
    "청구서 합계 금액과 결제 상태를 알려주세요",
    "請求書の合計金額と支払い状況を取得してください",
    "Read parcel ledger payload and audit_tag 0002",
    "Find a capability to forecast aviation delays without provider",
))
def test_scoped_index_exact_matches_authorized_exhaustive(
    role: str, k: int, query: str,
) -> None:
    router, _policy = build_fixture(100)
    before, after = _paired(router, role=role, query=query, k=k)
    assert after.model_dump(mode="json") == before.model_dump(mode="json")
    assert after.registry_version == before.registry_version
    assert after.requested_k == k
    if role == "viewer":
        assert not {
            item.route_id for item in after.candidates
        }.intersection(DENIED_VIEWER)
        for item in after.candidates:
            if item.tool.startswith("bench"):
                assert "audit_tag" not in {
                    field.name for field in item.output_fields
                }
                assert "audit_tag" not in item.matched_fields


def test_alternating_roles_do_not_share_hidden_scoped_entries() -> None:
    router, _ = build_fixture(100)
    for role in ("editor", "viewer", "editor", "viewer"):
        before, after = _paired(
            router, role=role,
            query="probe parcel ledger audit_tag, update invoice",
            k=56,
        )
        assert after.model_dump(mode="json") == before.model_dump(mode="json")
        if role == "viewer":
            assert all(
                "audit_tag" not in {f.name for f in c.output_fields}
                for c in after.candidates if c.tool.startswith("bench")
            )


def test_unindexed_and_structural_retrieval_keep_exhaustive_behavior() -> None:
    router, _ = build_fixture(100)
    who = principal("viewer")
    query = PlanRequest(query="invoice account summary")
    router.planner.candidate_index = False
    before = router.retrieve_authorized(query, principal=who, k=24)
    router.planner.structural_retrieval = True
    router.planner.candidate_index = True
    structural_indexed = router.retrieve_authorized(query, principal=who, k=24)
    router.planner.candidate_index = False
    structural_exhaustive = router.retrieve_authorized(query, principal=who, k=24)
    assert structural_indexed.model_dump(mode="json") == (
        structural_exhaustive.model_dump(mode="json")
    )
    assert before.registry_version == structural_exhaustive.registry_version
