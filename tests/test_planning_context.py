from dataclasses import FrozenInstanceError

import pytest

from schemarouter.models import EndpointSpec, PlanRequest, QueryIntent, ToolSpec
from schemarouter.planning_context import (
    PlanningContext,
    RegistrySnapshot,
    SnapshotToolRegistry,
)


def _tool() -> ToolSpec:
    return ToolSpec(
        name="catalog",
        endpoints=[
            EndpointSpec(
                name="lookup",
                method="GET",
                path="/lookup",
                read_only=True,
                output_schema={"type": "object"},
            )
        ],
    )


def test_registry_snapshot_exposes_frozen_endpoint_pairs() -> None:
    tool = _tool()
    snapshot = RegistrySnapshot(version=7, tools=(tool,))

    assert snapshot.version == 7
    assert snapshot.all_endpoint_pairs() == ((tool, tool.endpoints[0]),)
    assert snapshot.tool_fingerprint(tool) is None


def test_planning_context_binds_request_intent_and_registry_version() -> None:
    tool = _tool()
    request = PlanRequest(query="lookup catalog")
    intent = QueryIntent(concepts=["catalog"])
    context = PlanningContext(
        request=request,
        intent=intent,
        registry=RegistrySnapshot(version=11, tools=(tool,)),
    )

    assert context.request is request
    assert context.intent is intent
    assert context.registry.version == 11

    with pytest.raises(FrozenInstanceError):
        context.registry = RegistrySnapshot(version=12, tools=(tool,))  # type: ignore[misc]


def test_snapshot_tool_registry_is_read_only_and_detached() -> None:
    tool = _tool()
    snapshot = RegistrySnapshot(version=13, tools=(tool,))
    registry = SnapshotToolRegistry(snapshot)

    assert registry.version == 13
    assert registry.keys() == ("catalog",)
    assert registry.endpoint("catalog", "lookup").name == "lookup"

    detached = registry.get("catalog")
    detached.description = "mutated outside snapshot"
    assert registry.get("catalog").description != "mutated outside snapshot"

    with pytest.raises(TypeError, match="read-only"):
        registry.register(_tool())
