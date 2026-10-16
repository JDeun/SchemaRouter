"""Fail-closed cooldown semantics and real current public retrieval parity.

The original eager implementation is instrumented as the baseline without
changing either authorization or any scoring/query behavior.
"""
from __future__ import annotations

from unittest.mock import Mock, patch

import pytest

from benchmarks.current_adapter_field_scope_dev_v1 import principal
from benchmarks.current_adapter_scaled_authorized_dev_v1 import (
    DENIED_VIEWER,
    build_fixture,
)
from schemarouter import PlanRequest


def eager_baseline(router, query: str, role: str, k: int):
    def callback(tool, endpoint):
        return router.executor.is_access_available_for_contract(
            tool.key, endpoint.name,
            router.planner._snapshot_tool_fingerprint(tool),
        )
    with patch.object(router.planner, "availability_predicate", callback):
        return router.retrieve_authorized(
            PlanRequest(query=query), principal=principal(role), k=k,
        )


def paired(router, query: str, role: str, k: int):
    old = eager_baseline(router, query, role, k)
    new = router.retrieve_authorized(
        PlanRequest(query=query), principal=principal(role), k=k,
    )
    assert old.model_dump(mode="json") == new.model_dump(mode="json")
    return new


def test_no_cooldown_skips_expensive_tool_fingerprint() -> None:
    router, _ = build_fixture(100)
    fingerprint = Mock(side_effect=AssertionError("unnecessary fingerprint"))
    assert router.executor.is_access_available_for_contract_lazy(
        "benchdb", "probe_db_0005", fingerprint,
    )
    fingerprint.assert_not_called()
    with patch.object(
        router.planner, "_snapshot_tool_fingerprint",
        side_effect=AssertionError("fingerprint during clear access check"),
    ):
        result = router.retrieve_authorized(
            PlanRequest(query="parcel ledger payload"),
            principal=principal("viewer"), k=24,
        )
        assert result.candidates


def test_active_cooldown_deny_expired_cooldown_allow() -> None:
    router, _ = build_fixture(100)
    name = "benchdb"
    operation = "probe_db_0005"
    tool = router.registry.get(name)
    router.executor.mark_access_unavailable(
        name, operation, cooldown_seconds=60.0,
    )
    fingerprint = Mock(return_value=tool.fingerprint)
    assert not router.executor.is_access_available_for_contract_lazy(
        name, operation, fingerprint,
    )
    fingerprint.assert_called_once_with()

    other = Mock(side_effect=AssertionError("wrong operation fingerprint"))
    assert router.executor.is_access_available_for_contract_lazy(
        name, "probe_db_0000", other,
    )
    other.assert_not_called()
    result = paired(router, "parcel ledger database", "editor", 100)
    assert f"{name}.{operation}" not in {
        x.route_id for x in result.candidates
    }

    router.executor.mark_access_unavailable(
        name, operation, cooldown_seconds=0.0,
    )
    assert router.executor.is_access_available_for_contract_lazy(
        name, operation, lambda: tool.fingerprint,
    )
    reopened = paired(router, "parcel ledger database", "editor", 100)
    assert f"{name}.{operation}" in {
        x.route_id for x in reopened.candidates
    }


def test_stale_cooldown_fingerprint_does_not_block_new_tool_version() -> None:
    router, _ = build_fixture(100)
    name, endpoint = "benchdb", "probe_db_0005"
    old = router.registry.get(name)
    router.executor.mark_access_unavailable(
        name, endpoint, cooldown_seconds=60.0,
    )
    assert not router.executor.is_access_available_for_contract(
        name, endpoint, old.fingerprint,
    )
    changed = old.model_copy(deep=True)
    changed.description = changed.description + " source-version-changed"
    router.registry.register(changed, replace=True)
    current = router.registry.get(name)
    assert current.fingerprint != old.fingerprint
    assert router.executor.is_access_available_for_contract_lazy(
        name, endpoint, lambda: current.fingerprint,
    )
    matched = paired(router, "database parcel ledger", "editor", 100)
    assert f"{name}.{endpoint}" in {x.route_id for x in matched.candidates}


@pytest.mark.parametrize("k", (5, 24, 56))
@pytest.mark.parametrize("role", ("viewer", "editor"))
@pytest.mark.parametrize("query", (
    "Get invoice total and invoice identifier",
    "청구서의 합계와 식별자를 조회하세요",
    "請求金額と請求書番号を確認してください",
    "Read parcel ledger payload and audit_tag",
    "Pay the invoice and verify payment",
    "Predict airplane delays without provider",
))
def test_full_authorized_result_equals_old_eager_api(
    query: str, role: str, k: int,
) -> None:
    router, _ = build_fixture(100)
    result = paired(router, query, role, k)
    if role == "viewer":
        assert not set(x.route_id for x in result.candidates).intersection(
            DENIED_VIEWER,
        )
        assert all(
            "audit_tag" not in {f.name for f in c.output_fields}
            for c in result.candidates if c.tool.startswith("bench")
        )


def test_role_alternation_does_not_share_access_or_fingerprint_scope() -> None:
    router, _ = build_fixture(100)
    for role in ("editor", "viewer", "editor", "viewer"):
        paired(router, "parcel ledger payload audit_tag", role, 56)


@pytest.mark.asyncio
async def test_async_authorized_cooldown_and_full_output_parity() -> None:
    router, _ = build_fixture(100)
    who = principal("viewer")
    query = PlanRequest(query="청구서 합계와 데이터 페이로드를 조회하세요")
    router.executor.mark_access_unavailable(
        "benchdb", "probe_db_0005", cooldown_seconds=60.0,
    )
    def eager(tool, endpoint):
        return router.executor.is_access_available_for_contract(
            tool.key, endpoint.name,
            router.planner._snapshot_tool_fingerprint(tool),
        )

    with patch.object(router.planner, "availability_predicate", eager):
        old = await router.aretrieve_authorized(
            query, principal=who, k=56,
        )
    current = await router.aretrieve_authorized(
        query, principal=who, k=56,
    )
    assert current.model_dump(mode="json") == old.model_dump(mode="json")
    assert "benchdb.probe_db_0005" not in {
        item.route_id for item in current.candidates
    }
