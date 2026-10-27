"""Provider-neutral Algorithm 1 field discovery; no network or data execution.

Run from an editable checkout: python examples/schema_only_field_routing.py
"""
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
                name="customer_id", required=True, location="query",
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


if __name__ == "__main__":
    main()
