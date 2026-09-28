from __future__ import annotations

from pathlib import Path

from benchmarks.registry_capability_contract import (
    ACTION_FAMILIES,
    compile_endpoint,
    compile_registry,
    counterfactual_action_texts,
    structural_action_compatible,
)
from schemarouter import EndpointSpec, InMemoryRegistry, ToolSpec
from schemarouter.adapters.mcp import tool_from_mcp
from schemarouter.adapters.openapi import tool_from_openapi


def test_compiler_has_no_canonical_benchmark_dependency() -> None:
    source = (
        Path(__file__).resolve().parents[1]
        / "benchmarks"
        / "registry_capability_contract.py"
    ).read_text(encoding="utf-8")
    assert "reference_registry" not in source
    for forbidden in (
        "weather.current",
        "materials.search",
        "papers.citations",
        "finance.quote",
        "calendar.create",
        "support.search",
        "inventory.update",
        "users.lookup",
    ):
        assert forbidden not in source


def test_native_registry_supports_variable_endpoint_counts_and_empty_aliases() -> None:
    registry = InMemoryRegistry()
    registry.register(
        ToolSpec(
            name="single",
            description="A one-operation service",
            endpoints=[
                EndpointSpec(
                    name="peek",
                    description="Fetch one record",
                    read_only=True,
                )
            ],
        )
    )
    registry.register(
        ToolSpec(
            name="triple",
            description="Three-operation service",
            endpoints=[
                EndpointSpec(name="scan", description="Search records", read_only=True),
                EndpointSpec(name="amend", description="Update a record", read_only=False),
                EndpointSpec(
                    name="purge",
                    description="Remove a record permanently",
                    read_only=False,
                    destructive=True,
                ),
            ],
        )
    )
    registry.register(
        ToolSpec(
            name="five",
            description="Five-operation service",
            endpoints=[
                EndpointSpec(name=f"op_{index}", description="Run an operation")
                for index in range(5)
            ],
        )
    )

    contracts = compile_registry(registry)
    assert len(contracts) == 9
    assert {contract.tool_key for contract in contracts} == {
        "single",
        "triple",
        "five",
    }


def test_openapi_contract_uses_imported_method_and_schema_without_manual_aliases() -> None:
    document = {
        "openapi": "3.1.0",
        "info": {"title": "Contact service", "version": "1.0.0"},
        "paths": {
            "/contacts/{contact_id}": {
                "get": {
                    "operationId": "alpha_17",
                    "summary": "Fetch one contact profile",
                    "parameters": [
                        {
                            "name": "contact_id",
                            "in": "path",
                            "required": True,
                            "schema": {"type": "string"},
                        }
                    ],
                    "responses": {
                        "200": {
                            "description": "ok",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "properties": {
                                            "contact_id": {"type": "string"},
                                            "display_name": {"type": "string"},
                                        },
                                    }
                                }
                            },
                        }
                    },
                },
                "delete": {
                    "operationId": "omega_99",
                    "summary": "Permanently remove one contact profile",
                    "parameters": [
                        {
                            "name": "contact_id",
                            "in": "path",
                            "required": True,
                            "schema": {"type": "string"},
                        }
                    ],
                    "responses": {"204": {"description": "deleted"}},
                },
            },
            "/contacts": {
                "post": {
                    "operationId": "beta_23",
                    "summary": "Register a new contact profile",
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "display_name": {"type": "string"}
                                    },
                                    "required": ["display_name"],
                                }
                            }
                        },
                    },
                    "responses": {"201": {"description": "created"}},
                }
            },
        },
    }
    tool = tool_from_openapi("contacts_api", document)
    registry = InMemoryRegistry()
    registry.register(tool)
    contracts = {item.endpoint_name: item for item in compile_registry(registry)}

    assert len(contracts) == 3
    assert contracts["alpha_17"].adapter == "openapi"
    assert contracts["alpha_17"].declared_action == "retrieve"
    assert contracts["omega_99"].declared_action == "delete"
    assert contracts["omega_99"].destructive is True
    assert contracts["beta_23"].declared_action == "create"
    assert all(not item.operation_text.isspace() for item in contracts.values())


def test_mcp_contract_uses_opaque_name_description_and_schema() -> None:
    tool = tool_from_mcp(
        "opaque_server",
        {
            "tools": [
                {
                    "name": "x17",
                    "description": "Search media assets by owner and tag",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "owner": {"type": "string"},
                            "tag": {"type": "string"},
                        },
                    },
                    "outputSchema": {
                        "type": "object",
                        "properties": {
                            "asset_id": {"type": "string"},
                            "title": {"type": "string"},
                        },
                    },
                },
                {
                    "name": "q9",
                    "description": "Update the title of an existing media asset",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "asset_id": {"type": "string"},
                            "title": {"type": "string"},
                        },
                    },
                },
            ]
        },
    )
    registry = InMemoryRegistry()
    registry.register(tool)
    contracts = {item.endpoint_name: item for item in compile_registry(registry)}

    assert contracts["x17"].adapter == "mcp"
    assert contracts["x17"].declared_action == "search"
    assert contracts["q9"].declared_action == "update"
    assert "asset id" in contracts["q9"].object_text.casefold()


def test_counterfactuals_are_generic_and_exclude_declared_action() -> None:
    tool = ToolSpec(
        name="records",
        endpoints=[
            EndpointSpec(
                name="change_record",
                description="Update an existing record",
                read_only=False,
            )
        ],
    )
    contract = compile_endpoint(tool, tool.endpoints[0])
    negatives = counterfactual_action_texts(contract)

    assert contract.declared_action == "update"
    assert "update" not in negatives
    assert set(negatives).issubset(ACTION_FAMILIES)
    assert {"delete", "create", "search"}.issubset(negatives)


def test_structural_compatibility_fails_closed_for_write_against_read_only() -> None:
    tool = ToolSpec(
        name="records",
        endpoints=[
            EndpointSpec(
                name="fetch_record",
                description="Fetch one record",
                read_only=True,
            )
        ],
    )
    contract = compile_endpoint(tool, tool.endpoints[0])

    assert structural_action_compatible(contract, "delete") is False
    assert structural_action_compatible(contract, "update") is False
    assert structural_action_compatible(contract, "retrieve") is True
    assert structural_action_compatible(contract, None) is None
