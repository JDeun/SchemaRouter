"""E0 true registered-invoker executions, not provider identity or E2."""

from __future__ import annotations

from typing import Any

import pytest

from schemarouter import (
    AuthorizationPolicy,
    AuthorizationRule,
    DataScopeRule,
    EndpointSpec,
    FieldSpec,
    ParameterSpec,
    PolicyRule,
    PrincipalContext,
    SchemaRouter,
    ToolSpec,
)
from schemarouter.capability_contracts import CapabilityFieldContract
from schemarouter.errors import PolicyViolationError, SchemaValidationError
from schemarouter.field_group_retrieval import NativeDeclaredFieldGroup
from schemarouter.native_graph_execution import execute_native_graph_one_hop
from schemarouter.native_graph_index import NativeSchemaGraphIndex
from schemarouter.native_semantic_index import NativeSchemaPostingIndex

ACTOR = PrincipalContext(subject="analyst", roles=("reader",))
MASKED = PrincipalContext(subject="limited", roles=("limited",))
GROUP = NativeDeclaredFieldGroup(
    aliases=("case status", "문의 상태", "問い合わせ状態"),
    required_fields=(CapabilityFieldContract(
        semantic_id="crm.status", json_schema={"type": "string"},
    ),),
    source_type="crm",
    license="owner-reviewed",
)


def _fixture(
    *,
    produced: dict[str, Any] | None = None,
    deny_consumer: bool = False,
) -> tuple[SchemaRouter, NativeSchemaGraphIndex, list[tuple[str, dict]]]:
    out = (
        {"contact_id": "c-1", "region_id": "r-2"}
        if produced is None
        else produced
    )
    seen: list[tuple[str, dict]] = []
    router = SchemaRouter(
        authorization_policy=AuthorizationPolicy(
            default_effect="deny",
            rules=(AuthorizationRule(
                effect="allow",
                operation="*.*",
                roles_any=("reader", "limited"),
            ),),
            data_rules=(DataScopeRule(
                operation="contacts.read",
                roles_any=("limited",),
                hidden_fields=("region_id",),
            ),),
        ),
    )
    if deny_consumer:
        router.policy.rules = (
            *router.policy.rules,
            PolicyRule(
                effect="deny", operation="cases.read",
                name="explicit-downstream-denial",
            ),
        )

    source = ToolSpec(
        name="contacts", source_type="crm", license="owner-reviewed",
        endpoints=[EndpointSpec(
            name="read", read_only=True,
            output_fields=[
                FieldSpec(
                    name=n, identifier=True, semantic_id=f"crm.{n}",
                    json_schema={"type": "string"},
                ) for n in ("contact_id", "region_id")
            ],
            output_schema={
                "type": "object",
                "properties": {
                    "contact_id": {"type": "string"},
                    "region_id": {"type": "string"},
                    "secret": {"type": "string"},
                },
                "required": ["contact_id", "region_id"],
            },
        )],
    )
    target = ToolSpec(
        name="cases", source_type="crm", license="owner-reviewed",
        endpoints=[EndpointSpec(
            name="read", read_only=True,
            parameters=[
                ParameterSpec(
                    name=n, semantic_id=f"crm.{n}", required=True,
                    json_schema={"type": "string"},
                ) for n in ("contact_id", "region_id")
            ],
            input_schema={
                "type": "object",
                "properties": {
                    "contact_id": {"type": "string"},
                    "region_id": {"type": "string"},
                },
                "required": ["contact_id", "region_id"],
                "additionalProperties": False,
            },
            output_fields=[FieldSpec(
                name="status", semantic_id="crm.status",
                json_schema={"type": "string"},
            )],
            output_schema={
                "type": "object",
                "properties": {"status": {"type": "string"}},
                "required": ["status"],
            },
        )],
    )

    def source_invoker(endpoint: str, arguments: dict) -> dict:
        assert endpoint == "read"
        seen.append(("source", dict(arguments)))
        return dict(out)

    def dest_invoker(endpoint: str, arguments: dict) -> dict:
        assert endpoint == "read"
        seen.append(("destination", dict(arguments)))
        return {"status": "active"}

    router.add_bound_tool(source, source_invoker)
    router.add_bound_tool(target, dest_invoker)
    index = NativeSchemaGraphIndex.build(
        NativeSchemaPostingIndex.build(router.registry),
    )
    return router, index, seen


@pytest.mark.asyncio
@pytest.mark.parametrize("query", GROUP.aliases)
async def test_real_bound_executor_two_hop_g5_chain(query: str) -> None:
    router, idx, seen = _fixture(produced={
        "contact_id": "c-1",
        "region_id": "r-2",
        "secret": "must-not-leak",
    })
    edge = idx.lookup(router, query, group=GROUP, principal=ACTOR).candidates[0]
    result = await execute_native_graph_one_hop(
        idx, router, query=query, group=GROUP, principal=ACTOR,
        candidate=edge,
    )
    assert seen == [
        ("source", {}),
        ("destination", {"contact_id": "c-1", "region_id": "r-2"}),
    ]
    assert result.producer.data == {
        "contact_id": "c-1", "region_id": "r-2",
    }
    assert result.consumer.data == {"status": "active"}
    assert "must-not-leak" not in repr(result)
    assert result.producer_via_registered_executor
    assert result.consumer_via_registered_executor
    assert not result.independent_provider_identity_verified
    assert not result.independent_agent_e2


@pytest.mark.asyncio
@pytest.mark.parametrize("outcome", [
    {"contact_id": "c-1"},
    {"contact_id": "c-1", "region_id": None},
    {"contact_id": "c-1", "region_id": ["r-2"]},
    {"contact_id": "c-1", "region_id": 17},
])
async def test_malformed_root_never_invokes_downstream(outcome: dict) -> None:
    router, index, seen = _fixture(produced=outcome)
    edge = index.lookup(
        router, GROUP.aliases[0], group=GROUP, principal=ACTOR,
    ).candidates[0]
    with pytest.raises((SchemaValidationError, ValueError)):
        await execute_native_graph_one_hop(
            index, router, query=GROUP.aliases[0], group=GROUP,
            principal=ACTOR, candidate=edge,
        )
    assert seen == [("source", {})]


@pytest.mark.asyncio
async def test_hidden_required_source_field_blocks_before_any_invocation() -> None:
    router, idx, seen = _fixture()
    edge = idx.lookup(
        router, GROUP.aliases[0], group=GROUP, principal=ACTOR,
    ).candidates[0]
    with pytest.raises(PolicyViolationError, match="no longer source-authorized"):
        await execute_native_graph_one_hop(
            idx, router, query=GROUP.aliases[0], group=GROUP,
            principal=MASKED, candidate=edge,
        )
    assert seen == []


@pytest.mark.asyncio
async def test_runtime_execution_policy_denial_blocks_second_call() -> None:
    router, idx, seen = _fixture(deny_consumer=True)
    edge = idx.lookup(
        router, GROUP.aliases[0], group=GROUP, principal=ACTOR,
    ).candidates[0]
    with pytest.raises(PolicyViolationError):
        await execute_native_graph_one_hop(
            idx, router, query=GROUP.aliases[0], group=GROUP,
            principal=ACTOR, candidate=edge,
        )
    assert seen == [("source", {})]


@pytest.mark.asyncio
async def test_stale_source_schema_denied_before_any_provider_call() -> None:
    router, idx, seen = _fixture()
    edge = idx.lookup(
        router, GROUP.aliases[0], group=GROUP, principal=ACTOR,
    ).candidates[0]
    replacement = router.registry.get("contacts")
    replacement.endpoint("read").description = "changed original source"
    router.registry.register(replacement, replace=True)
    with pytest.raises(PolicyViolationError):
        await execute_native_graph_one_hop(
            idx, router, query=GROUP.aliases[0], group=GROUP,
            principal=ACTOR, candidate=edge,
        )
    assert seen == []
