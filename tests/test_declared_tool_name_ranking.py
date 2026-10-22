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


@pytest.mark.parametrize("indexed", [False, True])
@pytest.mark.parametrize(
    ("endpoint_name", "query"),
    [
        ("record_read", "Read the named policy rule"),
        ("resolve_choice", "List the available choices"),
    ],
)
def test_native_compound_endpoint_terminal_identifier_is_retrievable(
    indexed: bool,
    endpoint_name: str,
    query: str,
) -> None:
    """Real declared terminal identifiers outrank incidental generic prose."""
    registry = InMemoryRegistry()
    registry.register(
        ToolSpec(
            name="native-provider",
            endpoints=[
                *[
                    EndpointSpec(
                        name=f"generic_{index}",
                        description="Read records, list choices, and inspect named policies",
                        read_only=True,
                    )
                    for index in range(5)
                ],
                EndpointSpec(name=endpoint_name, read_only=True),
            ],
        )
    )

    result = SchemaPlanner(registry, candidate_index=indexed).retrieve(query, k=5)

    expected_route = f"native-provider.{endpoint_name}"
    candidate = next(
        candidate for candidate in result.candidates
        if candidate.route_id == expected_route
    )
    assert any(
        component.kind == "endpoint_identifier" and component.matched == endpoint_name
        for component in candidate.score_components
    )
    assert len(result.candidates) == 5


@pytest.mark.parametrize("indexed", [False, True])
@pytest.mark.parametrize(
    "query",
    ["Check an unreadable file", "Inspect archive records", "Show the archived list"],
)
def test_native_compound_endpoint_does_not_match_unrelated_parts_or_substrings(
    indexed: bool,
    query: str,
) -> None:
    registry = InMemoryRegistry()
    registry.register(
        ToolSpec(
            name="native-provider",
            endpoints=[EndpointSpec(name="archive_read", read_only=True)],
        )
    )

    result = SchemaPlanner(registry, candidate_index=indexed).retrieve(query, k=1)

    assert all(
        component.kind != "endpoint_identifier"
        for candidate in result.candidates
        for component in candidate.score_components
    )


@pytest.mark.parametrize("indexed", [False, True])
def test_short_compound_terminal_identifier_is_not_promoted(indexed: bool) -> None:
    registry = InMemoryRegistry()
    registry.register(
        ToolSpec(
            name="native-provider",
            endpoints=[EndpointSpec(name="inspect_id", read_only=True)],
        )
    )

    result = SchemaPlanner(registry, candidate_index=indexed).retrieve("Find the ID", k=1)

    assert all(
        component.kind != "endpoint_identifier"
        for candidate in result.candidates
        for component in candidate.score_components
    )
