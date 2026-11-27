"""Provider-neutral Algorithm 1 field discovery; no network or data execution.

Run from an editable checkout: python examples/schema_only_field_routing.py
"""
import asyncio

from schemarouter import (
    AuthorizationPolicy,
    AuthorizationRule,
    CapabilityFieldContract,
    EndpointSpec,
    FieldSpec,
    NativeConceptCatalog,
    NativeDeclaredConcept,
    PaperIntentDeclaration,
    PaperIntentRegistry,
    PaperNativeRankPolicy,
    PaperUnderstanding,
    ParameterSpec,
    PolicyViolationError,
    PrincipalContext,
    SchemaRouter,
    ToolSpec,
)


def main() -> None:
    # In a real application, these reviewed schemas can come from ANY
    # user-registered API/MCP/SQL/plugin. No provider adapter is needed here.
    router = SchemaRouter(authorization_policy=AuthorizationPolicy(
        default_effect="deny",
        rules=(AuthorizationRule(
            effect="allow", operation="*.lookup", roles_any=("reader",),
        ),),
    ))
    router.add_tool(ToolSpec(
        name="directory", source_type="host-owned", license="internal",
        endpoints=[EndpointSpec(
            name="lookup", read_only=True,
            parameters=[ParameterSpec(
                name="customer_id", semantic_id="customer.id",
                required=True, location="query",
                json_schema={"type": "string"},
            )],
            input_schema={
                "type": "object",
                "properties": {"customer_id": {"type": "string"}},
                "required": ["customer_id"],
                "additionalProperties": False,
            },
            output_fields=[
                FieldSpec(name="status", semantic_id="customer.status",
                          json_schema={"type": "string"}),
                FieldSpec(name="owner", semantic_id="customer.owner",
                          json_schema={"type": "string"}),
            ],
        )],
    ))

    session = router.prepare_field_routing()
    # No root is approved before the human sees the native parameter shape.
    principal = PrincipalContext(subject="example-reader", roles=("reader",))
    cursor = None
    while True:
        reviewed_fields = session.inspect_visible_fields(
            principal=principal, after_route=cursor, limit=1,
        )
        for route in reviewed_fields.routes:
            print("visible source field candidate:", route.route_id,
                  [(field.name, field.semantic_id) for field in route.fields])
            print("safe source input shapes:", route.route_id, route.parameters_meta)
            # The pinned reverse schema index seeks each authorized page,
            # but the route still passes current principal/source checks.
            if route.route_id == "directory.lookup":
                assert tuple((item.name, item.required, item.location, item.json_types)
                             for item in route.parameters_meta) == (
                    ("customer_id", True, "query", ("string",)),
                )
        assert not reviewed_fields.executable_authority
        cursor = reviewed_fields.next_after_route
        if cursor is None:
            break
    # The host can use this CURRENT scoped inventory to review concepts;
    # no aliases are inferred and no provider data is fetched.

    # The owner now explicitly reviews/declares the meanings to route.
    catalog = NativeConceptCatalog(concepts=(NativeDeclaredConcept(
        concept_id="customer.overview",
        aliases=("customer overview", "고객 상태와 담당자"),
        required_fields=(
            CapabilityFieldContract(
                semantic_id="customer.status", json_schema={"type": "string"},
            ),
            CapabilityFieldContract(
                semantic_id="customer.owner", json_schema={"type": "string"},
            ),
        ),
        source_type="host-owned", license="internal",
    ), *(
        NativeDeclaredConcept(
            concept_id=f"customer.{name}", aliases=(f"customer {name}",),
            required_fields=(CapabilityFieldContract(
                semantic_id=f"customer.{name}", json_schema={"type": "string"},
            ),), source_type="host-owned", license="internal",
        ) for name in ("status", "owner")
    )))
    active = session.revise_catalog(
        catalog=catalog,
        approved_host_roots=frozenset({"directory.lookup"}),
    )  # owner explicitly approves the reviewed scalar input source
    assert active.snapshot_id == session.snapshot_id  # same index; no rescan
    assert active.catalog_revision_id != session.revise_catalog(
        catalog=catalog,
    ).catalog_revision_id  # root approval is part of semantic cache identity
    # Compile structured Understand(q) hints against the reviewed catalog.
    reviewed_intents = PaperIntentRegistry(intents=(PaperIntentDeclaration(
        intent_id="customer.lookup",
        required_concept_ids=("customer.overview",),
    ),))
    hints = PaperUnderstanding(intent_id="customer.lookup")
    fields = active.compile_understood(
        hints, principal=principal, intent_registry=reviewed_intents,
    )
    assert fields.status == "requires_arguments" and not fields.executable_authority
    print("status:", fields.status)
    for route in fields.calls:
        print("route / selected schema fields:", route.route_id, route.call.fields)

    # Optional host-approved arguments, never model-proposed values.
    host_arguments = {
        "directory.lookup": {"customer_id": "host-supplied-customer-1"},
    }
    plan = active.compile_understood(
        hints, principal=principal, intent_registry=reviewed_intents,
        host_source_arguments=host_arguments,
    )
    assert plan.status == "ready" and not plan.executable_authority
    print("plan status:", plan.status, "executable:", plan.executable_authority)
    for route in plan.calls:
        print("field metadata:", route.route_id, route.fields_meta)
        print("input parameter shapes:", route.route_id, route.parameters_meta)

    # Revoking root approval removes the ability to bind host values under
    # that approval, not the ability to describe a missing-input receipt.
    revoked = active.revise_catalog(
        catalog=catalog, approved_host_roots=frozenset(),
    )
    assert revoked.catalog_revision_id != active.catalog_revision_id
    assert revoked.compile_understood(
        hints, principal=principal, intent_registry=reviewed_intents,
    ).status == "requires_arguments"
    try:
        revoked.compile_understood(
            hints, principal=principal, intent_registry=reviewed_intents,
            host_source_arguments=host_arguments,
        )
    except PolicyViolationError:
        pass
    else:
        raise AssertionError("revoked source approval accepted host inputs")
    assert active.compile_understood(
        hints, principal=principal, intent_registry=reviewed_intents,
        host_source_arguments=host_arguments,
    ).status == "ready"

    # Owner vocabulary updates reuse the same registered-source index.
    updated_catalog = NativeConceptCatalog(concepts=(NativeDeclaredConcept(
        concept_id="customer.overview",
        aliases=("account status and owner", "계정 상태와 담당자"),
        required_fields=catalog.concepts[0].required_fields,
        source_type="host-owned", license="internal",
    ),))
    reviewed_session = active.revise_catalog(catalog=updated_catalog)
    assert reviewed_session.snapshot_id == active.snapshot_id
    assert reviewed_session.catalog_revision_id != active.catalog_revision_id
    print("reviewed fields:", reviewed_session.compile_understood(
        hints, principal=principal, intent_registry=reviewed_intents,
    ).status)

    # A model hint is not an argument; only the explicit host value is bound.
    understood = active.compile_understood(
        PaperUnderstanding(
            intent_id="customer.lookup", named_tools=("directory",),
            parameter_hints={"customer_id": "untrusted-model-value"},
        ),
        principal=principal, intent_registry=reviewed_intents,
        host_source_arguments={
            "directory.lookup": {"customer_id": "host-supplied-customer-1"},
        },
    )
    print("structured understanding plan:", understood.status,
          "executable:", understood.executable_authority)
    for call in understood.calls:
        print("understood fields / inputs:", call.route_id,
              call.call.fields, call.call.arguments)

    # Opt-in original Algorithm 1 Rank: source-pinned host policy, after
    # principal-scoped typed proof. This toy catalog has just one candidate;
    # unnamed discovery focuses on a single source after the original score.
    # A ranked receipt NEVER grants execution authority.
    ranked = active.compile_understood(
        PaperUnderstanding(intent_id="customer.lookup", raw_rank_concepts=("customer overview",)),
        principal=principal, intent_registry=reviewed_intents,
        rank_policy=PaperNativeRankPolicy(snapshot_id=active.snapshot_id),
    )
    print("paper Rank:", ranked.status,
          "ranked_unverified:", ranked.ranked_unverified,
          "executable:", ranked.executable_authority)

    # A second source may have a compatible identifier. Algorithm 1 does
    # not infer a producer-to-consumer dependency from that compatibility.
    # Reprepare after editing the registry; no host root is approved here.
    router.add_tool(ToolSpec(
        name="directory_keys", source_type="host-owned", license="internal",
        endpoints=[EndpointSpec(
            name="lookup", read_only=True,
            output_fields=[FieldSpec(
                name="customer_id", semantic_id="customer.id",
                identifier=True, json_schema={"type": "string"},
            )],
            output_schema={
                "type": "object",
                "properties": {"customer_id": {"type": "string"}},
                "required": ["customer_id"],
            },
        )],
    ))
    graph_session = router.prepare_field_routing(catalog=catalog)
    graph_plan = graph_session.compile_understood(
        PaperUnderstanding(
            intent_id="customer.lookup", named_tools=("directory",),
        ), principal=principal, intent_registry=reviewed_intents,
    )
    assert not graph_plan.bindings
    assert all(call.call.tool != "directory_keys" for call in graph_plan.calls)
    print("independent named source plan:", graph_plan.status,
          tuple(call.route_id for call in graph_plan.calls))

    # Natural-language Understand(q) through the APPLICATION's own model.
    # This deterministic callback emulates the JSON contract. Swap the
    # callback for an actual host-controlled model; the router stays offline.
    async def owner_model(payload):
        assert "offered_concepts" not in payload  # no schema or alias inventory
        return {
            "intent_id": "customer.lookup",
            "needs": [{"concept": "customer owner"}, {"concept": "customer status"}],
            "parameter_hints": {"customer_id": "MODEL_VALUE_IS_NOT_USED"},
        }

    natural_plan = asyncio.run(graph_session.acompile_query(
        "この顧客の担当者とステータスは？",
        principal=principal,
        model=owner_model,
        intent_registry=reviewed_intents,
        model_visible_intent_ids=("customer.lookup",),
        rank_policy=PaperNativeRankPolicy(snapshot_id=graph_session.snapshot_id),
    ))
    print("model-assisted schema-only path:", natural_plan.status,
          tuple(call.route_id for call in natural_plan.calls))
    print("source-validated parameter values bound:",
          any(call.call.arguments for call in natural_plan.calls))


if __name__ == "__main__":
    main()
