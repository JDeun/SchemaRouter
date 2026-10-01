"""Show bounded capability retrieval versus exposing an entire tool catalog."""

from __future__ import annotations

import json

from schemarouter import EndpointSpec, FieldSpec, SchemaRouter, ToolSpec


def tool_for_domain(domain: str, *, aliases: list[str] | None = None) -> ToolSpec:
    return ToolSpec(
        name=f"{domain}_lookup",
        provider=f"example-{domain}",
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
    router = SchemaRouter()
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

    retrieval = router.retrieve("current weather temperature", k=3)
    assert retrieval.candidates
    assert retrieval.candidates[0].tool == "weather_lookup"

    full_catalog_payload = [
        tool.model_dump(mode="json")
        for tool in router.registry.tools()
    ]
    bounded_payload = [
        candidate.model_dump(mode="json")
        for candidate in retrieval.candidates
    ]

    full_bytes = compact_json_size(full_catalog_payload)
    bounded_bytes = compact_json_size(bounded_payload)

    assert bounded_bytes < full_bytes
    print(f"full catalog: {len(full_catalog_payload)} tools / {full_bytes} bytes")
    print(
        f"SchemaRouter shortlist: {len(bounded_payload)} capabilities / "
        f"{bounded_bytes} bytes"
    )
    print("routes:", [candidate.route_id for candidate in retrieval.candidates])


if __name__ == "__main__":
    main()
