"""#1560: original Algorithm 1 verified producer observation, deferred consumers."""
from __future__ import annotations

import pytest

from schemarouter import (
    AuthorizationPolicy,
    AuthorizationRule,
    CapabilityFieldContract,
    EndpointSpec,
    FieldSpec,
    NativeConceptCatalog,
    NativeDeclaredConcept,
    NativeDeclaredFieldGroup,
    NativeSchemaGraphIndex,
    NativeSchemaPostingIndex,
    ParameterSpec,
    PrincipalContext,
    SchemaRouter,
    ToolSpec,
    retrieve_paper_field_coverage,
)
from schemarouter.errors import (
    PolicyViolationError,
    SchemaValidationError,
    TransientInvocationError,
)
from schemarouter.paper_observed_binding import observe_and_bind_paper_plan

ALIASES = ("customer status and owner", "고객 상태와 담당자", "顧客状態と担当者")
ACTOR = PrincipalContext(subject="host-researcher", roles=("reader",))


def _fixture(*, observed_customer_id="customer-017", source_parameter=False,
             single_consumer=False, noise_count=0, on_source=None,
             allow_consumers=False, on_consumer=None, consumer_payloads=None,
             consumer_result_paths=None):
    seen: list[tuple[str, dict]] = []
    router = SchemaRouter(authorization_policy=AuthorizationPolicy(
        default_effect="deny", rules=(AuthorizationRule(
            effect="allow", operation="*.read", roles_any=("reader",),
        ),),
    ))
    source_params = ([ParameterSpec(
        name="external_id", required=True,
        json_schema={"type": "string"},
    )] if source_parameter else [])
    source_schema = ({
        "type": "object",
        "properties": {"external_id": {"type": "string"}},
        "required": ["external_id"],
    } if source_parameter else {})
    origin = ToolSpec(
        name="fork_origin", source_type="crm", license="reviewed",
        endpoints=[EndpointSpec(
            name="read", read_only=True,
            parameters=source_params, input_schema=source_schema,
            output_fields=[FieldSpec(
                name="customer_id", semantic_id="crm.customer_id",
                json_schema={"type": "string"}, identifier=True,
            )],
            output_schema={
                "type": "object",
                "properties": {"customer_id": {"type": "string"}},
                "required": ["customer_id"],
            },
        )],
    )

    def source(endpoint, args):
        seen.append(("root", dict(args)))
        if on_source is not None:
            on_source(router)
        return {"customer_id": observed_customer_id}

    router.add_bound_tool(origin, source)
    leaf_declarations = (
        ("fork_status", "crm.status", "status"),
        ("fork_owner", "crm.owner", "owner"),
    )
    for name, semantic, field in (
        leaf_declarations[:1] if single_consumer else leaf_declarations
    ):
        tool = ToolSpec(name=name, source_type="crm", license="reviewed", endpoints=[
            EndpointSpec(
                name="read", read_only=True,
                parameters=[ParameterSpec(
                    name="customer_id", semantic_id="crm.customer_id",
                    required=True, json_schema={"type": "string"},
                )],
                input_schema={
                    "type": "object", "properties": {
                        "customer_id": {"type": "string"},
                    }, "required": ["customer_id"],
                },
                output_fields=[FieldSpec(
                    name=field, semantic_id=semantic,
                    json_schema={"type": "string"},
                    result_path=(consumer_result_paths or {}).get(name, []),
                )],
            ),
        ])

        def forbidden(endpoint, args, *, consumer=name, observed_field=field):
            seen.append((consumer, dict(args)))
            if allow_consumers:
                if on_consumer is not None:
                    on_consumer(router, consumer)
                if consumer_payloads is not None:
                    return consumer_payloads[consumer]
                return {
                    observed_field: "active" if observed_field == "status" else "alice",
                }
            raise AssertionError("consumer must not execute during observed binding")

        router.add_bound_tool(tool, forbidden)

    # Same status semantic field, but every decoy has a different original
    # ID contract and NONE can share the real owner's original record root.
    for n in range(noise_count):
        decoy_id = f"noise.customer_{n}"
        router.add_bound_tool(ToolSpec(
            name=f"noise_root_{n}", source_type="crm", license="reviewed",
            endpoints=[EndpointSpec(
                name="read", read_only=True,
                output_fields=[FieldSpec(
                    name="foreign_id", semantic_id=decoy_id,
                    json_schema={"type": "string"}, identifier=True,
                )],
                output_schema={
                    "type": "object",
                    "properties": {"foreign_id": {"type": "string"}},
                    "required": ["foreign_id"],
                },
            )],
        ), lambda endpoint, args: {"foreign_id": "unrelated"})
        router.add_bound_tool(ToolSpec(
            name=f"noise_status_{n}", source_type="crm", license="reviewed",
            endpoints=[EndpointSpec(
                name="read", read_only=True,
                parameters=[ParameterSpec(
                    name="foreign_id", semantic_id=decoy_id,
                    required=True, json_schema={"type": "string"},
                )],
                input_schema={
                    "type": "object", "properties": {
                        "foreign_id": {"type": "string"},
                    }, "required": ["foreign_id"],
                },
                output_fields=[FieldSpec(
                    name="status", semantic_id="crm.status",
                    json_schema={"type": "string"},
                )],
            )],
        ), lambda endpoint, args: {"status": "unrelated"})

    catalog = NativeConceptCatalog(concepts=(NativeDeclaredConcept(
        concept_id="crm.customer_details", aliases=ALIASES,
        required_fields=tuple(
            CapabilityFieldContract(
                semantic_id=semantic, json_schema={"type": "string"},
            )
            for _name, semantic, _field in (
                leaf_declarations[:1] if single_consumer else leaf_declarations
            )
        ),
        source_type="crm", license="reviewed",
    ),))
    index = NativeSchemaGraphIndex.build(
        NativeSchemaPostingIndex.build(router.registry),
        approved_host_roots=(frozenset({"fork_origin.read"})
                             if source_parameter else frozenset()),
    )
    return router, catalog, index, seen


@pytest.mark.asyncio
@pytest.mark.parametrize("query", ALIASES)
async def test_actual_original_producer_executes_once_and_deferred_consumers_bind(query):
    """A real executor observation must bind both leaves without invoking either."""
    router, catalog, index, seen = _fixture()
    evidence = await observe_and_bind_paper_plan(
        router, query, principal=ACTOR, catalog=catalog, index=index,
    )
    assert seen == [("root", {})]
    assert evidence.producer.tool == "fork_origin"
    assert evidence.producer.data == {"customer_id": "customer-017"}
    assert evidence.producer_via_registered_executor is True
    assert evidence.independent_e2 is False
    assert evidence.executable_authority is False
    assert evidence.plan.status == "ready"
    assert evidence.plan.executable_authority is False
    assert {entry.route_id for entry in evidence.plan.calls} == {
        "fork_origin.read", "fork_status.read", "fork_owner.read",
    }
    assert evidence.plan.calls[0].call.fields == ["customer_id"]
    for leaf in evidence.plan.calls[1:]:
        assert leaf.call.arguments == {"customer_id": "customer-017"}
        assert leaf.call.missing_required_arguments == []
    assert {
        (item.parameter, item.producer_field)
        for item in evidence.plan.bindings
    } == {("customer_id", "customer_id")}


@pytest.mark.asyncio
async def test_host_required_source_input_never_executes_without_explicit_value():
    router, catalog, index, seen = _fixture(
        source_parameter=True, single_consumer=True,
    )
    with pytest.raises(SchemaValidationError, match="explicit host source inputs"):
        await observe_and_bind_paper_plan(
            router, ALIASES[0], principal=ACTOR, catalog=catalog, index=index,
        )
    assert seen == []


@pytest.mark.asyncio
async def test_approved_source_input_executes_once_and_no_consumer():
    router, catalog, index, seen = _fixture(
        source_parameter=True, single_consumer=True,
    )
    observed = await observe_and_bind_paper_plan(
        router, ALIASES[0], principal=ACTOR, catalog=catalog, index=index,
        host_source_arguments={"fork_origin.read": {"external_id": "raw-9"}},
    )
    assert seen == [("root", {"external_id": "raw-9"})]
    assert observed.plan.calls[0].call.arguments == {"external_id": "raw-9"}
    assert all(call.call.arguments == {"customer_id": "customer-017"}
               for call in observed.plan.calls[1:])


@pytest.mark.asyncio
async def test_invalid_observed_original_id_aborts_without_leaves():
    router, catalog, index, seen = _fixture(observed_customer_id=42)
    with pytest.raises(SchemaValidationError):
        await observe_and_bind_paper_plan(
            router, ALIASES[0], principal=ACTOR, catalog=catalog, index=index,
        )
    assert seen == [("root", {})]


@pytest.mark.asyncio
async def test_source_revokes_consumer_visibility_before_observation_binding():
    def revoke_owner(router):
        router.planner.availability_predicate = (
            lambda tool, endpoint: tool.key != "fork_owner"
        )

    router, catalog, index, seen = _fixture(on_source=revoke_owner)
    with pytest.raises(PolicyViolationError):
        await observe_and_bind_paper_plan(
            router, ALIASES[0], principal=ACTOR, catalog=catalog, index=index,
        )
    assert seen == [("root", {})]


@pytest.mark.asyncio
async def test_p1_complete_fork_still_binds_when_unrelated_one_hops_exceed_k5():
    """Unrelated same-field paths must not defeat the P1-proven shared root."""
    router, catalog, index, seen = _fixture(noise_count=6)
    p1 = retrieve_paper_field_coverage(
        router, ALIASES[0], principal=ACTOR, catalog=catalog, index=index,
    )
    assert p1.status == "complete"
    assert len(p1.alternatives) == 1
    assert len(p1.alternatives[0].routes) == 3
    group = NativeDeclaredFieldGroup(
        aliases=ALIASES,
        required_fields=(CapabilityFieldContract(
            semantic_id="crm.status", json_schema={"type": "string"},
        ),),
        source_type="crm", license="reviewed",
    )
    assert index.lookup(router, ALIASES[0], group=group, principal=ACTOR).status == (
        "over_k_unranked"
    )
    observed = await observe_and_bind_paper_plan(
        router, ALIASES[0], principal=ACTOR, catalog=catalog, index=index,
    )
    assert seen == [("root", {})]
    assert observed.plan.status == "ready"
    assert all(
        leaf.call.arguments == {"customer_id": "customer-017"}
        for leaf in observed.plan.calls[1:]
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("bad_id", [None, 42, ["customer-017"], "x" * 4097])
async def test_bad_observed_identifier_never_publishes_bound_leaves(bad_id):
    router, catalog, index, seen = _fixture(observed_customer_id=bad_id)
    with pytest.raises(SchemaValidationError):
        await observe_and_bind_paper_plan(
            router, ALIASES[0], principal=ACTOR, catalog=catalog, index=index,
        )
    assert seen == [("root", {})]


@pytest.mark.asyncio
async def test_policy_denial_during_producer_return_prevents_binding():
    def revoke_owner(router):
        router.authorization_policy = AuthorizationPolicy(
            default_effect="deny",
            rules=(
                AuthorizationRule(
                    effect="deny", operation="fork_owner.read",
                    roles_any=("reader",),
                ),
                AuthorizationRule(
                    effect="allow", operation="*.read",
                    roles_any=("reader",),
                ),
            ),
        )

    router, catalog, index, seen = _fixture(on_source=revoke_owner)
    with pytest.raises(PolicyViolationError):
        await observe_and_bind_paper_plan(
            router, ALIASES[0], principal=ACTOR, catalog=catalog, index=index,
        )
    assert seen == [("root", {})]


@pytest.mark.asyncio
async def test_observed_only_receipt_rejects_principal_swap_during_producer():
    """Even a non-executable bound receipt must retain its producer identity."""
    principal = PrincipalContext(subject="tenant-a", roles=("reader",))

    def change_principal(router):
        principal.subject = "tenant-b"

    router, catalog, index, seen = _fixture(on_source=change_principal)
    with pytest.raises(PolicyViolationError, match="principal claims changed"):
        await observe_and_bind_paper_plan(
            router, ALIASES[0], principal=principal, catalog=catalog, index=index,
        )
    assert seen == [("root", {})]


@pytest.mark.asyncio
async def test_original_producer_transient_failure_is_attempted_only_once():
    def fail_after_one_attempt(router):
        raise TransientInvocationError("simulated local producer transient")

    router, catalog, index, seen = _fixture(on_source=fail_after_one_attempt)
    with pytest.raises(TransientInvocationError):
        await observe_and_bind_paper_plan(
            router, ALIASES[0], principal=ACTOR, catalog=catalog, index=index,
        )
    assert seen == [("root", {})]


@pytest.mark.asyncio
async def test_unproved_host_parameterized_shared_fork_never_invokes_producer():
    router, catalog, index, seen = _fixture(source_parameter=True)
    assert retrieve_paper_field_coverage(
        router, ALIASES[0], principal=ACTOR, catalog=catalog, index=index,
    ).status == "no_proven_hit"
    with pytest.raises(PolicyViolationError):
        await observe_and_bind_paper_plan(
            router, ALIASES[0], principal=ACTOR, catalog=catalog, index=index,
        )
    assert seen == []
