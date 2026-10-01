"""Offline example: compare a full tool-schema dump with Top-K capability retrieval."""

from __future__ import annotations

import json

from schemarouter import EndpointSpec, FieldSpec, SchemaRouter, ToolSpec


def _tool(name: str, description: str, field_name: str, aliases: list[str]) -> ToolSpec:
    return ToolSpec(
        name=name,
        description=description,
        provider=f"example-{name}",
        access_mode="api",
        endpoints=[
            EndpointSpec(
                name="lookup",
                description=description,
                read_only=True,
                output_fields=[
                    FieldSpec(
                        name=field_name,
                        aliases=aliases,
                        json_schema={"type": "string"},
                    )
                ],
            )
        ],
    )


def main() -> None:
    router = SchemaRouter()
    specs = [
        _tool(
            "weather",
            "Current city weather and temperature.",
            "temperature",
            ["weather temperature"],
        ),
        _tool(
            "calendar",
            "Calendar events and meeting schedules.",
            "event",
            ["calendar event"],
        ),
        _tool(
            "crm",
            "Customer relationship records and contacts.",
            "contact",
            ["customer contact"],
        ),
        _tool(
            "inventory",
            "Warehouse stock and inventory availability.",
            "stock",
            ["inventory stock"],
        ),
        _tool(
            "billing",
            "Invoices, account balances, and payments.",
            "invoice",
            ["billing invoice"],
        ),
        _tool(
            "tickets",
            "Support tickets, incidents, and case status.",
            "ticket",
            ["support ticket"],
        ),
    ]
    for spec in specs:
        router.add_tool(spec)

    query = "weather temperature for a city"
    full_payload = [tool.model_dump(mode="json") for tool in router.registry.tools()]
    retrieved = router.retrieve(query, k=2)
    shortlist_payload = [
        candidate.model_dump(mode="json")
        for candidate in retrieved.candidates
    ]

    full_text = json.dumps(full_payload, sort_keys=True, separators=(",", ":"))
    shortlist_text = json.dumps(
        shortlist_payload,
        sort_keys=True,
        separators=(",", ":"),
    )

    assert len(retrieved.candidates) == 2
    assert len(shortlist_text) < len(full_text)

    print(f"registered routes: {len(specs)}")
    print(f"full schema context chars: {len(full_text)}")
    print(f"retrieved routes: {[candidate.route_id for candidate in retrieved.candidates]}")
    print(f"shortlist context chars: {len(shortlist_text)}")


if __name__ == "__main__":
    main()
