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
    PaperUnderstanding,
    ParameterSpec,
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

    # Semantic IDs/aliases express the fields the host wants discovered.
    # They are a reviewed declaration, not inferred from provider replies.
    catalog = NativeConceptCatalog(concepts=(NativeDeclaredConcept(
        concept_id="customer.overview",
        aliases=("customer status and owner", "고객 상태와 담당자"),
        required_fields=(
            CapabilityFieldContract(
                semantic_id="customer.status", json_schema={"type": "string"},
            ),
            CapabilityFieldContract(
                semantic_id="customer.owner", json_schema={"type": "string"},
            ),
        ),
        source_type="host-owned", license="internal",
    ),))

    session = router.prepare_field_routing(
        catalog=catalog,
        approved_host_roots=frozenset({"directory.lookup"}),
    )  # index once, only this explicit host input route is approved
    principal = PrincipalContext(subject="example-reader", roles=("reader",))
    fields = session.discover("고객 상태와 담당자", principal=principal)
    print("status:", fields.status)
    for alternative in fields.alternatives:
        for route in alternative.routes:
            print("route / selected schema fields:", route.route_id, route.output_fields)

    # Optional metadata and argument-shape inspection, not data fetching.
    plan = session.compile(
        "customer status and owner", principal=principal,
        host_source_arguments={
            "directory.lookup": {"customer_id": "host-supplied-customer-1"},
        },
    )
    print("plan status:", plan.status, "executable:", plan.executable_authority)
    for route in plan.calls:
        print("field metadata:", route.route_id, route.fields_meta)
        print("input parameter shapes:", route.route_id, route.parameters_meta)

    # Owner vocabulary updates do not change the registered source schemas.
    # Reuse the exact pinned graph while reviewing a NEW semantic catalog.
    updated_catalog = NativeConceptCatalog(concepts=(NativeDeclaredConcept(
        concept_id="customer.overview",
        aliases=("account status and owner", "계정 상태와 담당자"),
        required_fields=catalog.concepts[0].required_fields,
        source_type="host-owned", license="internal",
    ),))
    reviewed_session = session.revise_catalog(catalog=updated_catalog)
    assert reviewed_session.snapshot_id == session.snapshot_id
    assert reviewed_session.catalog_revision_id != session.catalog_revision_id
    print("reviewed fields:", reviewed_session.discover(
        "계정 상태와 담당자", principal=principal,
    ).status)
    # The host replaces its live handle with reviewed_session once approved;
    # any old handle retained elsewhere still uses its original meanings.

    # Optional structured Understand(q) is host/model SUPPLIED; the router
    # verifies it against reviewed concepts and current source permissions.
    # A model hint is not an argument. Only the explicit host value is bound.
    reviewed_intents = PaperIntentRegistry(intents=(PaperIntentDeclaration(
        intent_id="customer.lookup",
        required_concept_ids=("customer.overview",),
    ),))
    understood = session.compile_understood(
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

    # A second, independently reviewed source schema can establish the
    # dependency without executing either endpoint. Reprepare after editing
    # the registry; this session does not approve a parameterized host root.
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
    print("one-hop schema-only graph:", graph_plan.status,
          tuple(call.route_id for call in graph_plan.calls))
    print("typed dependency bindings:", graph_plan.bindings)

    # Natural-language Understand(q) through the APPLICATION's own model.
    # This deterministic callback emulates the JSON contract. Swap the
    # callback for an actual host-controlled model; the router stays offline.
    async def owner_model(payload):
        assert "output_fields" not in payload  # no raw provider schemas
        return {
            "intent_id": "customer.lookup",
            "concept_ids": ["customer.overview"],
            "named_tools": ["directory"],
            "parameter_hints": {"customer_id": "MODEL_VALUE_IS_NOT_USED"},
        }

    natural_plan = asyncio.run(graph_session.acompile_query(
        "この顧客の担当者とステータスは？",
        principal=principal,
        model=owner_model,
        intent_registry=reviewed_intents,
        model_visible_intent_ids=("customer.lookup",),
        model_visible_concept_ids=("customer.overview",),
        model_visible_tool_keys=("directory",),
    ))
    print("model-assisted schema-only path:", natural_plan.status,
          tuple(call.route_id for call in natural_plan.calls))
    print("model-derived values bound:",
          any(call.call.arguments for call in natural_plan.calls))


if __name__ == "__main__":
    main()
