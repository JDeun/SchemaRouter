"""Ranking checks for provider-declared tool names against verbose generic docs."""

from __future__ import annotations

import pytest

from schemarouter import EndpointSpec, InMemoryRegistry, SchemaPlanner, ToolSpec


@pytest.mark.parametrize("indexed", [False, True])
def test_explicit_inflected_tool_name_survives_fixed_k_generic_descriptions(
    indexed: bool,
) -> None:
    registry = InMemoryRegistry()
    for index in range(5):
        registry.register(
            ToolSpec(
                name=f"generic_records_{index}",
                description="Read incident records by table",
                endpoints=[
                    EndpointSpec(
                        name="inspect",
                        description="Read incident records by table",
                        read_only=True,
                    )
                ],
            )
        )
    registry.register(
        ToolSpec(
            name="flow",
            description="Inspect flows by table",
            endpoints=[
                EndpointSpec(
                    name="inspect",
                    description="Inspect flows by table",
                    read_only=True,
                )
            ],
        )
    )

    retrieved = SchemaPlanner(registry, candidate_index=indexed).retrieve(
        "Find flows triggered by records on the incident table.",
        k=5,
    )

    assert "flow.inspect" in [candidate.route_id for candidate in retrieved.candidates]
    assert len(retrieved.candidates) == 5


@pytest.mark.parametrize("indexed", [False, True])
def test_native_mcp_endpoint_name_survives_fixed_k_generic_descriptions(
    indexed: bool,
) -> None:
    """MCP ingests native tools as endpoints beneath one source ToolSpec."""
    registry = InMemoryRegistry()
    registry.register(
        ToolSpec(
            name="provider-mcp",
            endpoints=[
                *[
                    EndpointSpec(
                        name=f"generic_records_{index}",
                        description="Read incident records by table",
                        read_only=True,
                    )
                    for index in range(5)
                ],
                EndpointSpec(
                    name="flow",
                    description="Inspect flows by table",
                    read_only=True,
                ),
            ],
        )
    )

    result = SchemaPlanner(registry, candidate_index=indexed).retrieve(
        "Find flows triggered by records on the incident table.",
        k=5,
    )

    assert "provider-mcp.flow" in [candidate.route_id for candidate in result.candidates]
    assert len(result.candidates) == 5


@pytest.mark.parametrize("indexed", [False, True])
def test_tool_name_is_not_matched_inside_unrelated_word(indexed: bool) -> None:
    registry = InMemoryRegistry()
    registry.register(
        ToolSpec(
            name="flow",
            endpoints=[EndpointSpec(name="inspect", read_only=True)],
        )
    )
    result = SchemaPlanner(registry, candidate_index=indexed).retrieve(
        "Review workflow metadata",
        k=1,
    )
    assert all(candidate.score == 0 for candidate in result.candidates)
    assert all(
        component.kind != "tool_identifier"
        for candidate in result.candidates
        for component in candidate.score_components
    )


@pytest.mark.parametrize("indexed", [False, True])
def test_endpoint_name_is_not_matched_inside_unrelated_word(indexed: bool) -> None:
    registry = InMemoryRegistry()
    registry.register(
        ToolSpec(
            name="provider-mcp",
            endpoints=[EndpointSpec(name="flow", read_only=True)],
        )
    )
    result = SchemaPlanner(registry, candidate_index=indexed).retrieve(
        "Review workflow metadata", k=1,
    )
    assert all(candidate.score == 0 for candidate in result.candidates)
    assert all(
        component.kind != "endpoint_identifier"
        for candidate in result.candidates
        for component in candidate.score_components
    )
