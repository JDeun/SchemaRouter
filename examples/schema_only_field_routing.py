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

    session = router.prepare_field_routing(catalog=catalog)  # index once
    principal = PrincipalContext(subject="example-reader", roles=("reader",))
    fields = session.discover("고객 상태와 담당자", principal=principal)
    print("status:", fields.status)
    for alternative in fields.alternatives:
        for route in alternative.routes:
            print("route / selected schema fields:", route.route_id, route.output_fields)

    # Optional metadata and argument-shape inspection, not data fetching.
    plan = session.compile("customer status and owner", principal=principal)
    print("plan status:", plan.status, "executable:", plan.executable_authority)
    for route in plan.calls:
        print("field metadata:", route.route_id, route.fields_meta)


if __name__ == "__main__":
    main()
