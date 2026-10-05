from __future__ import annotations

import pytest

from schemarouter.adapters.mcp import tool_from_mcp
from schemarouter.adapters.openapi import _resolve_local_ref
from schemarouter.errors import SchemaSourceError
from schemarouter.schema_complexity import validate_schema_complexity


def _deep_schema(depth: int) -> dict:
    root: dict = {}
    current = root
    for _ in range(depth):
        child: dict = {}
        current["items"] = child
        current = child
    current["type"] = "string"
    return root


def _ref_chain(length: int, *, prefix: str) -> tuple[dict, dict]:
    definitions: dict[str, dict] = {}
    for index in range(length):
        target = (
            {"type": "object", "properties": {"value": {"type": "string"}}}
            if index == length - 1
            else {"$ref": f"#/{prefix}/S{index + 1}"}
        )
        definitions[f"S{index}"] = target
    document = {prefix: definitions}
    return document, {"$ref": f"#/{prefix}/S0"}


def test_schema_complexity_rejects_deep_structure() -> None:
    with pytest.raises(SchemaSourceError, match="depth exceeds"):
        validate_schema_complexity(_deep_schema(70), source="test schema")


def test_schema_complexity_rejects_combinator_branch_explosion() -> None:
    schema = {
        "anyOf": [{"type": "string"} for _ in range(4_097)],
    }

    with pytest.raises(SchemaSourceError, match="branch count"):
        validate_schema_complexity(schema, source="test schema")


def test_schema_complexity_rejects_cyclic_container_graph() -> None:
    schema: dict = {"type": "object"}
    schema["properties"] = {"self": schema}

    with pytest.raises(SchemaSourceError, match="cyclic container"):
        validate_schema_complexity(schema, source="test schema")


def test_schema_complexity_accepts_normal_nested_schema() -> None:
    validate_schema_complexity(
        {
            "type": "object",
            "properties": {
                "items": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "id": {"type": "string"},
                            "score": {"type": "number"},
                        },
                    },
                }
            },
        },
        source="test schema",
    )


def test_openapi_local_ref_chain_has_independent_hop_budget() -> None:
    definitions: dict[str, dict] = {}
    for index in range(130):
        definitions[f"S{index}"] = (
            {"type": "object", "properties": {"value": {"type": "string"}}}
            if index == 129
            else {"$ref": f"#/components/schemas/S{index + 1}"}
        )
    document = {"components": {"schemas": definitions}}
    schema = {"$ref": "#/components/schemas/S0"}

    with pytest.raises(SchemaSourceError, match="local reference chain"):
        _resolve_local_ref(document, schema)


def test_mcp_schema_complexity_is_checked_before_field_discovery() -> None:
    with pytest.raises(SchemaSourceError, match="depth exceeds"):
        tool_from_mcp(
            "server",
            {
                "tools": [
                    {
                        "name": "deep",
                        "inputSchema": {"type": "object"},
                        "outputSchema": _deep_schema(70),
                    }
                ]
            },
        )


def test_mcp_local_ref_chain_has_independent_hop_budget() -> None:
    definitions: dict[str, dict] = {}
    for index in range(130):
        definitions[f"S{index}"] = (
            {"type": "object", "properties": {"value": {"type": "string"}}}
            if index == 129
            else {"$ref": f"#/$defs/S{index + 1}"}
        )
    output_schema = {
        "$ref": "#/$defs/S0",
        "$defs": definitions,
    }

    with pytest.raises(SchemaSourceError, match="local reference chain"):
        tool_from_mcp(
            "server",
            {
                "tools": [
                    {
                        "name": "chain",
                        "inputSchema": {"type": "object"},
                        "outputSchema": output_schema,
                    }
                ]
            },
        )
