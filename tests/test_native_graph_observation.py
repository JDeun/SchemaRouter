"""Negative original-contract controls for nonexecuting G5 value validation (E0)."""

from __future__ import annotations

from dataclasses import replace

import pytest

from schemarouter import (
    AuthorizationPolicy,
    AuthorizationRule,
    DataScopeRule,
    EndpointSpec,
    FieldSpec,
    ParameterSpec,
    PrincipalContext,
    ResultFieldContract,
    SchemaRouter,
    ToolResult,
    ToolSpec,
)
from schemarouter.capability_contracts import CapabilityFieldContract
from schemarouter.errors import PolicyViolationError, SchemaValidationError
from schemarouter.field_group_retrieval import NativeDeclaredFieldGroup
from schemarouter.native_graph_index import NativeSchemaGraphIndex
from schemarouter.native_graph_observation import materialize_native_observed_arguments
from schemarouter.native_semantic_index import NativeSchemaPostingIndex

ACTOR = PrincipalContext(subject="analyst", roles=("reader",))
MASKED = PrincipalContext(subject="viewer", roles=("viewer",))
GROUP = NativeDeclaredFieldGroup(
    aliases=("case status", "문의 상태", "問い合わせ状態"),
    required_fields=(CapabilityFieldContract(
        semantic_id="crm.status", json_schema={"type": "string"},
    ),),
    source_type="crm", license="owner-reviewed",
)


def _setup() -> tuple[SchemaRouter, NativeSchemaGraphIndex]:
    router = SchemaRouter(authorization_policy=AuthorizationPolicy(
        default_effect="deny",
        rules=(AuthorizationRule(
            effect="allow", operation="*.*",
            roles_any=("reader", "viewer"),
        ),),
        data_rules=(DataScopeRule(
            operation="contacts.read", roles_any=("viewer",),
            hidden_fields=("region_id",),
        ),),
    ))
    router.add_tool(ToolSpec(
        name="contacts", source_type="crm", license="owner-reviewed",
        endpoints=[EndpointSpec(
            name="read", read_only=True,
            output_fields=[
                FieldSpec(
                    name=name, semantic_id=f"crm.{name}", identifier=True,
                    json_schema={"type": "string"},
                )
                for name in ("contact_id", "region_id")
            ],
            output_schema={
                "type": "object",
                "properties": {
                    "contact_id": {"type": "string"},
                    "region_id": {"type": "string"},
                },
                "required": ["contact_id", "region_id"],
            },
        )],
    ))
    router.add_tool(ToolSpec(
        name="cases", source_type="crm", license="owner-reviewed",
        endpoints=[EndpointSpec(
            name="read", read_only=True,
            parameters=[
                ParameterSpec(
                    name=name, semantic_id=f"crm.{name}", required=True,
                    json_schema={"type": "string"},
                )
                for name in ("contact_id", "region_id")
            ],
            input_schema={
                "type": "object",
                "properties": {
                    "contact_id": {"type": "string"},
                    "region_id": {"type": "string"},
                },
                "required": ["contact_id", "region_id"],
            },
            output_fields=[
                FieldSpec(
                    name="status", semantic_id="crm.status",
                    json_schema={"type": "string"},
                ),
            ],
        )],
    ))
    graph = NativeSchemaGraphIndex.build(
        NativeSchemaPostingIndex.build(router.registry),
    )
    return router, graph


def _observed() -> ToolResult:
    return ToolResult(
        tool="contacts", endpoint="read",
        data={"contact_id": "c-1", "region_id": "r-2"},
        projected_fields=["contact_id", "region_id"],
        field_contracts={
            name: ResultFieldContract(
                semantic_id=f"crm.{name}",
                json_schema={"type": "string"},
                has_observed_value=True,
            )
            for name in ("contact_id", "region_id")
        },
    )


def _validate(
    router: SchemaRouter,
    index: NativeSchemaGraphIndex,
    observation: ToolResult,
    *,
    principal: PrincipalContext = ACTOR,
    candidate=None,
):
    if candidate is None:
        candidate = index.lookup(
            router, GROUP.aliases[0], group=GROUP, principal=ACTOR,
        ).candidates[0]
    return materialize_native_observed_arguments(
        index, router, query=GROUP.aliases[0], group=GROUP,
        principal=principal, candidate=candidate, observation=observation,
    )


@pytest.mark.parametrize("query", GROUP.aliases)
def test_complete_nonexecuting_observed_argument_values(query: str) -> None:
    router, index = _setup()
    edge = index.lookup(router, query, group=GROUP, principal=ACTOR).candidates[0]
    evidence = materialize_native_observed_arguments(
        index, router, query=query, group=GROUP, principal=ACTOR,
        candidate=edge, observation=_observed(),
    )
    assert evidence.arguments == {"contact_id": "c-1", "region_id": "r-2"}
    args = evidence.arguments
    args["contact_id"] = "not-the-original"
    assert evidence.arguments["contact_id"] == "c-1"
    assert evidence.provider_provenance_verified is False
    assert evidence.executable_authority is False
    assert evidence.independent_e2 is False


@pytest.mark.parametrize(("mutation", "expected_error"), [
    ({"tool": "cases"}, "route does not match"),
    ({"projected_fields": ["contact_id"]}, "explicitly projected"),
    ({"data": {"contact_id": "c-1"}}, "field presence"),
    ({"data": {"contact_id": "c-1", "region_id": None}}, "not a JSON scalar"),
    ({"data": {"contact_id": "c-1", "region_id": 7}}, "produced field"),
    ({"data": {"contact_id": "c-1", "region_id": ["r-2"]}}, "not a JSON scalar"),
    ({"data": [{"contact_id": "c-1", "region_id": "r-2"}]}, "single projected"),
    ({"field_contracts": {}}, "field presence"),
])
def test_missing_wrong_typed_spoofed_observation_fails_closed(
    mutation: dict, expected_error: str,
) -> None:
    router, index = _setup()
    observed = _observed().model_copy(update=mutation)
    with pytest.raises(SchemaValidationError, match=expected_error):
        _validate(router, index, observed)


def test_null_presence_metadata_cannot_create_a_real_scalar() -> None:
    router, index = _setup()
    observed = _observed()
    observed.field_contracts["region_id"].has_observed_value = False
    with pytest.raises(SchemaValidationError, match="field presence"):
        _validate(router, index, observed)


def test_scope_hidden_root_value_is_not_bindable_even_if_observed() -> None:
    router, index = _setup()
    with pytest.raises(PolicyViolationError, match="current permitted graph"):
        _validate(router, index, _observed(), principal=MASKED)


def test_changed_source_and_candidate_not_in_current_graph_fail_closed() -> None:
    router, index = _setup()
    edge = index.lookup(
        router, GROUP.aliases[0], group=GROUP, principal=ACTOR,
    ).candidates[0]
    with pytest.raises(PolicyViolationError, match="current permitted graph"):
        _validate(router, index, _observed(), candidate=replace(
            edge, producer_identifier_field="unknown",
        ))
    new = router.registry.get("contacts")
    new.endpoint("read").output_schema["required"].remove("region_id")
    router.registry.register(new, replace=True)
    with pytest.raises((PolicyViolationError, ValueError), match="changed|stale|revision"):
        _validate(router, index, _observed(), candidate=edge)


def test_result_cannot_gain_executable_authority_from_forged_presence_flags() -> None:
    router, index = _setup()
    # Even a caller-constructed ToolResult that perfectly spoofs metadata
    # produces only validation evidence and never a permitted ToolCall.
    evidence = _validate(router, index, _observed())
    assert evidence.provider_provenance_verified is False
    assert evidence.executable_authority is False
    assert not hasattr(evidence, "call")
