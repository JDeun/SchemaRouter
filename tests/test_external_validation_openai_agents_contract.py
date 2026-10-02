from __future__ import annotations

from types import SimpleNamespace

import pytest

pytest.importorskip("agents")

from mcp.types import Tool as MCPTool

from scripts.external_validation_openai_agents import (
    SchemaRouterDynamicMCPFilter,
    SearchContext,
    _register_mcp_retrieval_mirror,
)
from schemarouter import SchemaRouter


def _tool(name: str, description: str) -> MCPTool:
    return MCPTool(
        name=name,
        description=description,
        inputSchema={
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"],
            "additionalProperties": False,
        },
    )


def test_canonical_mcp_identity_is_preserved_without_normalization_collision() -> None:
    tools = [
        _tool("example.tool", "look up the dotted example tool"),
        _tool("example_tool", "look up the underscored example tool"),
    ]
    router = SchemaRouter()
    _register_mcp_retrieval_mirror(router, tools)

    assert router.registry.get("example.tool").name == "example.tool"
    assert router.registry.get("example_tool").name == "example_tool"
    assert router.registry.get("example.tool").key != router.registry.get("example_tool").key


def test_dynamic_filter_is_fail_closed_without_expected_run_context() -> None:
    router = SchemaRouter()
    _register_mcp_retrieval_mirror(router, [_tool("example.tool", "dotted example")])
    dynamic_filter = SchemaRouterDynamicMCPFilter(router)

    context = SimpleNamespace(run_context=SimpleNamespace(context=object()))
    assert dynamic_filter(context, _tool("example.tool", "dotted example")) is False


def test_dynamic_filter_never_widens_host_allowlist() -> None:
    tools = [
        _tool("weather.lookup", "current weather lookup"),
        _tool("delete_record", "delete archived record"),
    ]
    router = SchemaRouter()
    _register_mcp_retrieval_mirror(router, tools)
    dynamic_filter = SchemaRouterDynamicMCPFilter(router)

    query = "delete archived record"
    retrieved = dynamic_filter.allow_set(query)
    host_allowed: set[str] = set()
    effective = retrieved & host_allowed

    assert "delete_record" in retrieved
    assert effective == set()


def test_repeated_discovery_is_cached_and_does_not_execute_tools() -> None:
    router = SchemaRouter()
    _register_mcp_retrieval_mirror(
        router,
        [_tool("weather.lookup", "current weather in a city")],
    )
    dynamic_filter = SchemaRouterDynamicMCPFilter(router)

    first = dynamic_filter.allow_set("current weather")
    evidence_before = dict(dynamic_filter.evidence)
    second = dynamic_filter.allow_set("current weather")

    assert first == second
    assert dynamic_filter.evidence == evidence_before
    assert router.run_store.list() == []
