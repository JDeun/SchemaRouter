"""Compare a source-proven field route receipt with the entire tool catalog."""

from __future__ import annotations

import json
from dataclasses import asdict

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
    PrincipalContext,
    SchemaRouter,
    ToolSpec,
)


def tool_for_domain(domain: str, *, aliases: list[str] | None = None) -> ToolSpec:
    return ToolSpec(
        name=f"{domain}_lookup",
        provider=f"example-{domain}",
        source_type="synthetic",
        license="example-only",
        access_mode="api",
        description=f"Read-only {domain} lookup capability.",
        endpoints=[
            EndpointSpec(
                name="lookup",
                description=f"Look up one {domain} value.",
                read_only=True,
                output_fields=[
                    FieldSpec(
                        name="value",
                        semantic_id=f"{domain}.value",
                        aliases=aliases or [domain],
                        json_schema={"type": "number"},
                    )
                ],
            )
        ],
    )


def compact_json_size(value: object) -> int:
    return len(
        json.dumps(
            value,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    )


def main() -> None:
    principal = PrincipalContext(subject="example", roles=("reader",))
    router = SchemaRouter(authorization_policy=AuthorizationPolicy(
        default_effect="deny", rules=(AuthorizationRule(
            effect="allow", operation="*.lookup", roles_any=("reader",),
        ),),
    ))
    distractors = [
        "finance",
        "calendar",
        "inventory",
        "shipping",
        "music",
        "movies",
        "sports",
        "legal",
        "geology",
        "astronomy",
        "chemistry",
        "biology",
        "traffic",
        "hotel",
        "flights",
        "books",
        "news",
        "commerce",
        "support",
        "analytics",
        "security",
        "network",
        "storage",
        "database",
        "identity",
        "email",
        "messaging",
        "maps",
        "jobs",
        "education",
        "energy",
        "agriculture",
        "manufacturing",
        "research",
        "patents",
        "clinical",
        "insurance",
        "realestate",
        "gaming",
    ]
    for domain in distractors:
        router.add_tool(tool_for_domain(domain))
    router.add_tool(
        tool_for_domain(
            "weather",
            aliases=["weather", "temperature", "current temperature"],
        )
    )

    catalog = NativeConceptCatalog(concepts=(NativeDeclaredConcept(
        concept_id="weather.value", aliases=("current weather temperature",),
        source_type="synthetic", license="example-only",
        required_fields=(CapabilityFieldContract(
            semantic_id="weather.value", json_schema={"type": "number"},
        ),),
    ),))
    session = router.prepare_field_routing(catalog=catalog)
    receipt = session.compile_understood(
        PaperUnderstanding(intent_id="weather.read"), principal=principal,
        intent_registry=PaperIntentRegistry(intents=(PaperIntentDeclaration(
            intent_id="weather.read", required_concept_ids=("weather.value",),
        ),)),
    )
    assert receipt.status == "ready" and not receipt.executable_authority
    routes = receipt.calls
    assert [route.route_id for route in routes] == ["weather_lookup.lookup"]

    full_catalog_payload = [
        tool.model_dump(mode="json")
        for tool in router.registry.tools()
    ]
    bounded_payload = [
        {"route_id": route.route_id, "call": route.call.model_dump(mode="json"),
         "fields_meta": [asdict(field) for field in route.fields_meta]}
        for route in routes
    ]

    full_bytes = compact_json_size(full_catalog_payload)
    bounded_bytes = compact_json_size(bounded_payload)

    assert bounded_bytes < full_bytes
    print(f"full catalog: {len(full_catalog_payload)} tools / {full_bytes} bytes")
    print(
        f"SchemaRouter field routes: {len(bounded_payload)} routes / "
        f"{bounded_bytes} bytes"
    )
    print("routes:", [route.route_id for route in routes])


if __name__ == "__main__":
    main()
