from __future__ import annotations

from dataclasses import dataclass

import pytest

from schemarouter import (
    EndpointSpec,
    FieldSpec,
    InMemoryRegistry,
    PlanRequest,
    QueryIntent,
    ToolSpec,
)
from schemarouter.decisions import DecisionRequest, DecisionResult, DecisionSelection
from schemarouter.graph_routing import CompiledSchemaGraph, GraphOperationGate
from schemarouter.planner import SchemaPlanner


def _registry(*, conflicts: bool = False) -> InMemoryRegistry:
    registry = InMemoryRegistry()
    registry.register(
        ToolSpec(
            name="weather",
            description="Weather observations and forecasts",
            source_type="observational",
            license="example-license",
            unsupported_operation_aliases=(
                ["weather alerts"]
                if conflicts
                else []
            ),
            endpoints=[
                EndpointSpec(
                    name="current",
                    description="Get current city weather",
                    operation_aliases=["current weather", "weather right now"],
                    parameters=[],
                    output_fields=[
                        FieldSpec(name="city", identifier=True),
                        FieldSpec(
                            name="temperature",
                            semantic_id="temperature",
                            aliases=["air temperature"],
                            json_schema={"type": "number"},
                            unit="C",
                            qualifiers={"phase": "ambient"},
                            source_type="observational",
                            license="field-license",
                        ),
                    ],
                    read_only=True,
                ),
                EndpointSpec(
                    name="forecast",
                    description="Get future weather forecast",
                    operation_aliases=["weather forecast", "future weather"],
                    parameters=[],
                    output_fields=[
                        FieldSpec(name="city", identifier=True),
                        FieldSpec(
                            name="forecast",
                            semantic_id="forecast",
                            aliases=["weather prediction"],
                        ),
                    ],
                    read_only=True,
                ),
            ],
        )
    )
    return registry


def test_unsupported_operation_aliases_are_typed_and_fingerprinted() -> None:
    base = ToolSpec(
        name="weather",
        endpoints=[EndpointSpec(name="current")],
    )
    guarded = ToolSpec(
        name="weather",
        unsupported_operation_aliases=["weather alerts"],
        endpoints=[EndpointSpec(name="current")],
    )

    assert base.fingerprint != guarded.fingerprint

    with pytest.raises(ValueError, match="surrounding whitespace"):
        ToolSpec(
            name="weather",
            unsupported_operation_aliases=[" weather alerts "],
            endpoints=[EndpointSpec(name="current")],
        )

    with pytest.raises(ValueError, match="duplicate unsupported operation alias"):
        ToolSpec(
            name="weather",
            unsupported_operation_aliases=["weather alerts", "Weather   Alerts"],
            endpoints=[EndpointSpec(name="current")],
        )


def test_compiled_graph_exposes_typed_schema_paths() -> None:
    graph = CompiledSchemaGraph.from_registry(_registry(conflicts=True))

    assert graph.version == 1
    assert {node.label for node in graph.nodes(kind="tool")} == {"weather"}
    assert {node.label for node in graph.nodes(kind="operation")} == {
        "current",
        "forecast",
    }
    assert graph.has_path(
        "tool:weather",
        "operation:weather.forecast",
        edge_kinds=frozenset({"HAS_ENDPOINT", "HAS_OPERATION"}),
        max_depth=2,
    )
    assert not graph.has_path(
        "tool:weather",
        "operation:weather.forecast",
        edge_kinds=frozenset({"RETURNS_FIELD"}),
        max_depth=2,
    )

    current_edges = graph.edges(source="endpoint:weather.current")
    assert {edge.kind for edge in current_edges} >= {
        "HAS_OPERATION",
        "RETURNS_FIELD",
    }
    assert graph.operation_aliases("weather", "forecast") == (
        "weather forecast",
        "future weather",
    )
    assert graph.field_concepts("weather", "current") == (
        "temperature",
        "air temperature",
    )
    assert graph.unsupported_operation_aliases("weather") == ("weather alerts",)

    field_edges = graph.edges(source="field:weather.current:temperature")
    assert {edge.kind for edge in field_edges} >= {
        "MAPS_TO_CONCEPT",
        "HAS_UNIT",
        "HAS_QUALIFIER",
        "HAS_SOURCE_TYPE",
        "LICENSED_AS",
    }


def test_graph_path_validation_rejects_invalid_depth() -> None:
    graph = CompiledSchemaGraph.from_registry(_registry())

    with pytest.raises(ValueError, match="max_depth"):
        graph.has_path("tool:weather", "operation:weather.current", max_depth=-1)

    assert graph.has_path("tool:weather", "tool:weather", max_depth=0)
    assert not graph.has_path("missing", "missing", max_depth=0)


def test_unique_operation_alias_is_a_graph_accept() -> None:
    graph = CompiledSchemaGraph.from_registry(_registry())
    gate = GraphOperationGate()

    assessment = gate.assess(
        query="Please use the weather forecast for Seoul.",
        graph=graph,
        tool_key="weather",
        endpoint_names=("current", "forecast"),
    )

    assert assessment.decision == "accept"
    assert assessment.endpoint_name == "forecast"
    assert assessment.evidence[0].operation_aliases == ("weather forecast",)


def test_global_graph_resolves_unique_registered_operation() -> None:
    graph = CompiledSchemaGraph.from_registry(_registry())

    assessment = GraphOperationGate().assess_global(
        query="Please use the weather forecast for Seoul.",
        graph=graph,
    )

    assert assessment.decision == "accept"
    assert assessment.tool_key == "weather"
    assert assessment.endpoint_name == "forecast"


def test_global_graph_ambiguity_escalates() -> None:
    registry = InMemoryRegistry()
    registry.register(
        ToolSpec(
            name="alpha",
            endpoints=[
                EndpointSpec(name="one", operation_aliases=["shared action"]),
            ],
        )
    )
    registry.register(
        ToolSpec(
            name="beta",
            endpoints=[
                EndpointSpec(name="two", operation_aliases=["shared action"]),
            ],
        )
    )

    assessment = GraphOperationGate().assess_global(
        query="Perform the shared action.",
        graph=CompiledSchemaGraph.from_registry(registry),
    )

    assert assessment.decision == "escalate"
    assert assessment.tool_key == ""
    assert "multiple" in assessment.reason


def test_multiple_alias_paths_escalate_instead_of_guessing() -> None:
    registry = InMemoryRegistry()
    registry.register(
        ToolSpec(
            name="demo",
            endpoints=[
                EndpointSpec(name="one", operation_aliases=["shared action"]),
                EndpointSpec(name="two", operation_aliases=["shared action"]),
            ],
        )
    )
    graph = CompiledSchemaGraph.from_registry(registry)

    assessment = GraphOperationGate().assess(
        query="Please perform the shared action now.",
        graph=graph,
        tool_key="demo",
        endpoint_names=("one", "two"),
    )

    assert assessment.decision == "escalate"
    assert assessment.endpoint_name is None
    assert "multiple" in assessment.reason


def test_missing_graph_evidence_escalates() -> None:
    graph = CompiledSchemaGraph.from_registry(_registry())

    assessment = GraphOperationGate().assess(
        query="Show severe conditions around Seoul.",
        graph=graph,
        tool_key="weather",
        endpoint_names=("current", "forecast"),
    )

    assert assessment.decision == "escalate"
    assert "insufficient" in assessment.reason


def test_explicit_graph_conflict_fails_closed() -> None:
    graph = CompiledSchemaGraph.from_registry(_registry(conflicts=True))

    assessment = GraphOperationGate().assess(
        query="Show weather alerts for Seoul.",
        graph=graph,
        tool_key="weather",
        endpoint_names=("current", "forecast"),
    )

    assert assessment.decision == "reject"
    assert assessment.endpoint_name is None
    assert "unsupported" in assessment.reason


def test_global_conflict_overrides_supported_alias_path() -> None:
    graph = CompiledSchemaGraph.from_registry(_registry(conflicts=True))

    assessment = GraphOperationGate().assess_global(
        query="Show the weather forecast and weather alerts for Seoul.",
        graph=graph,
    )

    assert assessment.decision == "reject"
    assert assessment.tool_key == "weather"
    assert assessment.endpoint_name is None
    assert any(
        evidence.operation_aliases == ("weather alerts",)
        for evidence in assessment.evidence
    )


def test_conflict_rejection_can_be_disabled_for_ablation() -> None:
    graph = CompiledSchemaGraph.from_registry(_registry(conflicts=True))

    assessment = GraphOperationGate(reject_explicit_conflicts=False).assess(
        query="Show weather alerts for Seoul.",
        graph=graph,
        tool_key="weather",
        endpoint_names=("current", "forecast"),
    )

    assert assessment.decision == "escalate"


def test_field_concept_accept_is_opt_in() -> None:
    graph = CompiledSchemaGraph.from_registry(_registry())
    default = GraphOperationGate().assess(
        query="I need the air temperature for Seoul.",
        graph=graph,
        tool_key="weather",
        endpoint_names=("current", "forecast"),
    )
    projected = GraphOperationGate(accept_unique_field_path=True).assess(
        query="I need the air temperature for Seoul.",
        graph=graph,
        tool_key="weather",
        endpoint_names=("current", "forecast"),
    )

    assert default.decision == "escalate"
    assert projected.decision == "accept"
    assert projected.endpoint_name == "current"
    assert "air temperature" in projected.evidence[0].field_concepts
    assert "temperature" in projected.evidence[0].field_concepts


def test_empty_or_unknown_candidate_surface_escalates() -> None:
    graph = CompiledSchemaGraph.from_registry(_registry())
    gate = GraphOperationGate()

    assert gate.assess(
        query="",
        graph=graph,
        tool_key="weather",
        endpoint_names=("current",),
    ).decision == "escalate"
    assert gate.assess(
        query="weather forecast",
        graph=graph,
        tool_key="weather",
        endpoint_names=(),
    ).decision == "escalate"
    assert gate.assess(
        query="weather forecast",
        graph=graph,
        tool_key="weather",
        endpoint_names=("not_registered",),
    ).decision == "escalate"


@dataclass
class _ExplodingBackend:
    calls: int = 0

    def decide(self, request: DecisionRequest) -> DecisionResult:
        self.calls += 1
        raise AssertionError("semantic backend must not run for graph-resolved operation")


@dataclass
class _AbstainingBackend:
    calls: int = 0

    def decide(self, request: DecisionRequest) -> DecisionResult:
        self.calls += 1
        return DecisionResult(abstained=True)


class _EndpointPreferringAnalyzer:
    def analyze(self, request: PlanRequest, registry: object) -> QueryIntent:
        del registry
        return QueryIntent(
            concepts=request.concepts,
            preferred_tools=request.preferred_tools,
            preferred_endpoints=["weather.forecast"],
            arguments=request.arguments,
            evidence=request.evidence,
            field_evidence=request.field_evidence,
        )


@dataclass
class _RouteSelectingBackend:
    route_id: str
    calls: int = 0
    offered_ids: tuple[str, ...] = ()

    def decide(self, request: DecisionRequest) -> DecisionResult:
        self.calls += 1
        self.offered_ids = tuple(option.id for option in request.options)
        if self.route_id not in self.offered_ids:
            return DecisionResult(abstained=True, metadata={"reason": "target_not_offered"})
        return DecisionResult(
            selections=[DecisionSelection(option_id=self.route_id, score=0.95)],
            metadata={"provider": "test-semantic-seed"},
        )


def test_planner_skips_operation_backend_when_graph_resolves_alias() -> None:
    backend = _ExplodingBackend()
    planner = SchemaPlanner(
        _registry(),
        graph_operation_gate=GraphOperationGate(),
        operation_fit_backend=backend,
    )

    plan = planner.plan(
        PlanRequest(
            query="Please use the weather forecast for Seoul.",
            preferred_tools=["weather"],
        )
    )

    assert backend.calls == 0
    assert len(plan.calls) == 1
    assert plan.calls[0].endpoint == "forecast"
    assert plan.calls[0].explanation is not None
    assert plan.calls[0].explanation.candidate_selection == "graph_operation"
    assert any("graph operation gate accepted" in warning for warning in plan.warnings)


def test_graph_resolution_skips_all_semantic_routing_backends() -> None:
    backend = _ExplodingBackend()
    planner = SchemaPlanner(
        _registry(),
        graph_operation_gate=GraphOperationGate(),
        candidate_recall_backend=backend,
        candidate_fit_backend=backend,
        operation_fit_backend=backend,
        endpoint_disambiguation_backend=backend,
    )

    plan = planner.plan(PlanRequest(query="Get the weather forecast for Seoul."))

    assert backend.calls == 0
    assert len(plan.calls) == 1
    assert plan.calls[0].endpoint == "forecast"


def test_semantic_seed_can_resolve_only_registered_graph_route() -> None:
    seed = _RouteSelectingBackend("weather.forecast")
    downstream = _ExplodingBackend()
    planner = SchemaPlanner(
        _registry(),
        graph_operation_gate=GraphOperationGate(),
        graph_semantic_seed_backend=seed,
        candidate_recall_backend=downstream,
        candidate_fit_backend=downstream,
        operation_fit_backend=downstream,
        endpoint_disambiguation_backend=downstream,
    )

    plan = planner.plan(PlanRequest(query="Show future conditions around Seoul."))

    assert seed.calls == 1
    assert set(seed.offered_ids) == {"weather.current", "weather.forecast"}
    assert downstream.calls == 0
    assert len(plan.calls) == 1
    assert plan.calls[0].tool == "weather"
    assert plan.calls[0].endpoint == "forecast"
    assert plan.calls[0].explanation is not None
    assert plan.calls[0].explanation.candidate_selection == "graph_semantic_seed"
    assert any("graph semantic seed accepted" in warning for warning in plan.warnings)


def test_semantic_seed_respects_preferred_tool_and_endpoint_constraints() -> None:
    seed = _RouteSelectingBackend("weather.forecast")
    planner = SchemaPlanner(
        _registry(),
        analyzer=_EndpointPreferringAnalyzer(),
        graph_operation_gate=GraphOperationGate(),
        graph_semantic_seed_backend=seed,
    )

    plan = planner.plan(
        PlanRequest(
            query="Show future conditions around Seoul.",
            preferred_tools=["weather"],
        )
    )

    assert seed.offered_ids == ("weather.forecast",)
    assert len(plan.calls) == 1
    assert plan.calls[0].endpoint == "forecast"


def test_semantic_seed_abstention_escalates_to_existing_operation_stack() -> None:
    seed = _AbstainingBackend()
    operation = _AbstainingBackend()
    planner = SchemaPlanner(
        _registry(),
        graph_operation_gate=GraphOperationGate(),
        graph_semantic_seed_backend=seed,
        operation_fit_backend=operation,
    )

    plan = planner.plan(PlanRequest(query="Show severe weather conditions around Seoul."))

    assert seed.calls == 1
    assert operation.calls == 1
    assert plan.calls == []
    assert any("graph semantic seed abstained" in warning for warning in plan.warnings)
    assert any("operation capability fit gate abstained" in warning for warning in plan.warnings)


def test_hard_graph_path_preempts_semantic_seed() -> None:
    seed = _ExplodingBackend()
    planner = SchemaPlanner(
        _registry(),
        graph_operation_gate=GraphOperationGate(),
        graph_semantic_seed_backend=seed,
    )

    plan = planner.plan(PlanRequest(query="Get the weather forecast for Seoul."))

    assert seed.calls == 0
    assert plan.calls[0].endpoint == "forecast"


@pytest.mark.asyncio
async def test_async_semantic_seed_uses_same_authority_boundary() -> None:
    seed = _RouteSelectingBackend("weather.current")
    downstream = _ExplodingBackend()
    planner = SchemaPlanner(
        _registry(),
        graph_operation_gate=GraphOperationGate(),
        graph_semantic_seed_backend=seed,
        operation_fit_backend=downstream,
    )

    plan = await planner.aplan(PlanRequest(query="Tell me the conditions in Seoul now."))

    assert seed.calls == 1
    assert downstream.calls == 0
    assert plan.calls[0].endpoint == "current"
    assert plan.calls[0].explanation is not None
    assert plan.calls[0].explanation.candidate_selection == "graph_semantic_seed"


def test_graph_feature_is_opt_in_and_default_path_is_unchanged() -> None:
    backend = _AbstainingBackend()
    planner = SchemaPlanner(
        _registry(),
        operation_fit_backend=backend,
    )

    plan = planner.plan(PlanRequest(query="Get the weather forecast for Seoul."))

    assert backend.calls == 1
    assert plan.calls == []


def test_planner_escalates_when_graph_is_uncertain() -> None:
    backend = _AbstainingBackend()
    planner = SchemaPlanner(
        _registry(),
        graph_operation_gate=GraphOperationGate(),
        operation_fit_backend=backend,
    )

    plan = planner.plan(
        PlanRequest(
            query="Show severe conditions around Seoul.",
            preferred_tools=["weather"],
        )
    )

    assert backend.calls == 1
    assert plan.calls == []
    assert any("graph operation gate escalated" in warning for warning in plan.warnings)
    assert any("operation capability fit gate abstained" in warning for warning in plan.warnings)


@pytest.mark.asyncio
async def test_async_planner_uses_same_graph_gate() -> None:
    backend = _ExplodingBackend()
    planner = SchemaPlanner(
        _registry(),
        graph_operation_gate=GraphOperationGate(),
        operation_fit_backend=backend,
    )

    plan = await planner.aplan(
        PlanRequest(
            query="I need current weather for Seoul.",
            preferred_tools=["weather"],
        )
    )

    assert backend.calls == 0
    assert plan.calls[0].endpoint == "current"
