"""Fail closed on any change from the independently computed scoped route/field output.

Baseline explicitly disables only the request-local projection reuse, not
route authorization, data scopes, entity parser, or scoring behavior.
"""
from __future__ import annotations

from unittest.mock import patch

import pytest

from benchmarks.current_adapter_field_scope_dev_v1 import principal
from benchmarks.current_adapter_scaled_authorized_dev_v1 import (
    DENIED_VIEWER,
    build_fixture,
)
from schemarouter import PlanRequest


def baseline_projection(router, who, predicate):
    registry = router._scoped_analysis_registry(who, predicate)
    return registry, lambda tool, endpoint: router._data_scope_endpoint_view(
        who, tool, endpoint,
    )


def query_pair(router, who, query, width):
    with patch.object(
        router, "_request_local_scoped_projection",
        lambda p, allowed: baseline_projection(router, p, allowed),
    ):
        before = router.retrieve_authorized(
            PlanRequest(query=query), principal=who, k=width,
        )
    after = router.retrieve_authorized(
        PlanRequest(query=query), principal=who, k=width,
    )
    assert before.model_dump(mode="json") == after.model_dump(mode="json")
    return after


@pytest.mark.parametrize("role", ("viewer", "editor"))
@pytest.mark.parametrize("width", (5, 24, 56))
@pytest.mark.parametrize("query", (
    "Show the total billed amount and invoice id",
    "청구서 총액과 식별자를 조회하세요",
    "請求書の合計金額と識別子を返してください",
    "List parcel ledger payload and hidden audit_tag",
    "Create a payment and verify the payment ID",
    "Predict future flight delays without aviation providers",
))
def test_local_projection_exact_full_result_parity(
    role: str, width: int, query: str,
) -> None:
    router, _policy = build_fixture(100)
    result = query_pair(router, principal(role), query, width)
    if role == "viewer":
        assert not set(item.route_id for item in result.candidates).intersection(
            DENIED_VIEWER
        )
        for item in result.candidates:
            if item.tool.startswith("bench"):
                assert "audit_tag" not in {f.name for f in item.output_fields}


@pytest.mark.asyncio
async def test_async_authorized_path_retains_exact_full_contract() -> None:
    router, _policy = build_fixture(100)
    who = principal("viewer")
    q = PlanRequest(query="한국어 자료의 이름과 필드를 조회하세요")
    with patch.object(
        router, "_request_local_scoped_projection",
        lambda p, allowed: baseline_projection(router, p, allowed),
    ):
        baseline = await router.aretrieve_authorized(q, principal=who, k=24)
    optimized = await router.aretrieve_authorized(q, principal=who, k=24)
    assert optimized.model_dump(mode="json") == baseline.model_dump(mode="json")


def test_visible_endpoint_transform_invoked_once_per_authorized_route() -> None:
    router, policy = build_fixture(100)
    who = principal("viewer")
    allowed = sum(
        policy.visible(who, tool, endpoint)
        for tool in router.registry.tools()
        for endpoint in tool.endpoints
    )
    original = router._data_scope_endpoint_view
    with patch.object(router, "_data_scope_endpoint_view", wraps=original) as viewed:
        result = router.retrieve_authorized(
            PlanRequest(query="payload parcel ledger record"),
            principal=who, k=24,
        )
        assert viewed.call_count == allowed
    assert len(result.candidates) <= 24
    with patch.object(router, "_data_scope_endpoint_view", wraps=original) as viewed:
        with patch.object(
            router, "_request_local_scoped_projection",
            lambda p, predicate: baseline_projection(router, p, predicate),
        ):
            baseline = router.retrieve_authorized(
                PlanRequest(query="payload parcel ledger record"),
                principal=who, k=24,
            )
        assert viewed.call_count >= allowed * 2
    assert result.model_dump(mode="json") == baseline.model_dump(mode="json")


def test_request_cache_is_not_reused_across_principal_or_policy_replacement() -> None:
    router, policy = build_fixture(100)
    for role in ("editor", "viewer", "editor", "viewer"):
        query_pair(
            router, principal(role),
            "Read synthetic parcel payload and audit_tag", 56,
        )
    from schemarouter import AuthorizationPolicy, AuthorizationRule

    router.authorization_policy = AuthorizationPolicy(
        rules=(
            AuthorizationRule(
                name="deny-everything", effect="deny", operation="*",
                roles_any=("viewer", "editor"),
            ),
        ),
        default_effect="deny",
    )
    isolated = router.retrieve_authorized(
        PlanRequest(query="Read synthetic parcel payload"),
        principal=principal("editor"), k=56,
    )
    assert isolated.candidates == []
    assert router.authorization_policy is not policy


def test_concurrent_registry_churn_invalidates_inflight_projection_reuse() -> None:
    router, policy = build_fixture(100)
    who = principal("viewer")
    predicate = router._authorization_predicate(who)
    assert predicate is not None
    scoped, view = router._request_local_scoped_projection(who, predicate)
    tool = next(t for t in router.registry.tools() if t.key == "benchdb")
    endpoint = tool.endpoints[0]
    first = view(tool, endpoint)
    assert first is not None
    assert scoped.tools()
    # Changing any registered capability forces a fresh projection rather
    # than returning the stale object from this specific in-flight closure.
    router.registry.register(tool, replace=True)
    second = view(tool, endpoint)
    assert second is not None
    assert first is not second
    assert policy.visible(who, tool, endpoint)
