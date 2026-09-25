from __future__ import annotations

from schemarouter import (
    EndpointSpec,
    FieldSpec,
    InMemoryRegistry,
    ParameterSpec,
    PlanRequest,
    QueryIntent,
    SchemaPlanner,
    ToolSpec,
)


def make_tool(
    index: int,
    *,
    keyword: str | None = None,
    parameter: str | None = None,
) -> ToolSpec:
    output_fields = [
        FieldSpec(
            name=f"value_{index}",
            aliases=[keyword] if keyword else [],
        )
    ]
    parameters = (
        [ParameterSpec(name=parameter, required=False)]
        if parameter is not None
        else []
    )
    return ToolSpec(
        name=f"tool_{index}",
        description=f"synthetic tool number {index}",
        endpoints=[
            EndpointSpec(
                name="search",
                description=f"synthetic endpoint number {index}",
                parameters=parameters,
                output_fields=output_fields,
                read_only=True,
            )
        ],
    )


def make_registry(size: int = 200) -> InMemoryRegistry:
    registry = InMemoryRegistry()
    registry.update_many(
        [
            make_tool(
                index,
                keyword="needle" if index == size - 1 else None,
            )
            for index in range(size)
        ]
    )
    return registry


class CountingPlanner(SchemaPlanner):
    def __init__(self, *args, **kwargs) -> None:
        self.score_calls = 0
        super().__init__(*args, **kwargs)

    def _score_endpoint(self, *args, **kwargs):
        self.score_calls += 1
        return super()._score_endpoint(*args, **kwargs)


class CountingRegistry(InMemoryRegistry):
    def __init__(self) -> None:
        super().__init__()
        self.tools_calls = 0

    def tools(self) -> tuple[ToolSpec, ...]:
        self.tools_calls += 1
        return super().tools()


class StaticAnalyzer:
    def __init__(self, intent: QueryIntent) -> None:
        self.intent = intent

    def analyze(self, request: PlanRequest, registry: InMemoryRegistry) -> QueryIntent:
        return self.intent


def test_candidate_index_preserves_exhaustive_plan_semantics() -> None:
    registry = make_registry()

    indexed = SchemaPlanner(registry, candidate_index=True).plan("needle")
    exhaustive = SchemaPlanner(registry, candidate_index=False).plan("needle")

    assert indexed.model_dump() == exhaustive.model_dump()


def test_candidate_index_reduces_full_endpoint_scoring_work() -> None:
    registry = make_registry(size=250)

    indexed = CountingPlanner(registry, candidate_index=True)
    indexed_plan = indexed.plan("needle")

    exhaustive = CountingPlanner(registry, candidate_index=False)
    exhaustive_plan = exhaustive.plan("needle")

    assert indexed_plan.model_dump() == exhaustive_plan.model_dump()
    assert indexed.score_calls == 1
    assert exhaustive.score_calls == 250


def test_candidate_index_covers_parameter_only_positive_scores() -> None:
    registry = InMemoryRegistry()
    registry.update_many(
        [
            make_tool(0),
            make_tool(1, parameter="record_id"),
        ]
    )

    request = PlanRequest(
        query="unrelated",
        arguments={"record_id": "abc"},
    )

    indexed = SchemaPlanner(registry, candidate_index=True).plan(request)
    exhaustive = SchemaPlanner(registry, candidate_index=False).plan(request)

    assert indexed.model_dump() == exhaustive.model_dump()
    assert [call.tool for call in indexed.calls] == ["tool_1"]


def test_candidate_index_covers_preferred_tool_and_endpoint_scores() -> None:
    registry = InMemoryRegistry()
    registry.update_many([make_tool(0), make_tool(1)])

    preferred_tool = PlanRequest(
        query="unrelated",
        preferred_tools=["tool_1"],
    )
    endpoint_analyzer = StaticAnalyzer(
        QueryIntent(
            preferred_endpoints=["tool_0.search"],
        )
    )

    tool_plan = SchemaPlanner(registry).plan(preferred_tool)
    endpoint_plan = SchemaPlanner(
        registry,
        analyzer=endpoint_analyzer,
    ).plan("unrelated")

    assert [call.tool for call in tool_plan.calls] == ["tool_1"]
    assert [call.tool for call in endpoint_plan.calls] == ["tool_0"]


def test_candidate_index_covers_normalized_field_substring_matching() -> None:
    registry = InMemoryRegistry()
    registry.register(
        ToolSpec(
            name="materials",
            endpoints=[
                EndpointSpec(
                    name="lookup",
                    output_fields=[
                        FieldSpec(
                            name="thermal_conductivity",
                            aliases=["thermal conductivity"],
                        )
                    ],
                    read_only=True,
                )
            ],
        )
    )
    analyzer = StaticAnalyzer(
        QueryIntent(
            concepts=["conductivity"],
        )
    )

    indexed = SchemaPlanner(
        registry,
        analyzer=analyzer,
        candidate_index=True,
    ).plan("unrelated")
    exhaustive = SchemaPlanner(
        registry,
        analyzer=analyzer,
        candidate_index=False,
    ).plan("unrelated")

    assert indexed.model_dump() == exhaustive.model_dump()
    assert [call.tool for call in indexed.calls] == ["materials"]


def test_candidate_index_cache_is_reused_until_registry_version_changes() -> None:
    registry = CountingRegistry()
    registry.register(make_tool(0, keyword="first"))

    planner = SchemaPlanner(registry, candidate_index=True)

    planner.plan("first")
    planner.plan("first")

    assert registry.tools_calls == 1

    registry.register(make_tool(1, keyword="second"))
    second = planner.plan("second")

    assert registry.tools_calls == 2
    assert [call.tool for call in second.calls] == ["tool_1"]


def test_candidate_index_empty_lookup_matches_exhaustive_no_candidate_plan() -> None:
    registry = make_registry(size=10)

    indexed = SchemaPlanner(registry, candidate_index=True).plan("absent-token")
    exhaustive = SchemaPlanner(registry, candidate_index=False).plan("absent-token")

    assert indexed.model_dump() == exhaustive.model_dump()
    assert indexed.calls == []



def test_candidate_index_covers_parameter_alias_matches() -> None:
    registry = InMemoryRegistry()
    registry.register(
        ToolSpec(
            name="materials",
            endpoints=[
                EndpointSpec(
                    name="search",
                    read_only=True,
                    parameters=[
                        ParameterSpec(
                            name="chemical_formula",
                            aliases=["formula"],
                            required=True,
                        )
                    ],
                    output_fields=[FieldSpec(name="value")],
                )
            ],
        )
    )
    request = PlanRequest(
        query="unrelated",
        arguments={"formula": "Si"},
    )

    indexed = SchemaPlanner(registry, candidate_index=True).plan(request)
    exhaustive = SchemaPlanner(registry, candidate_index=False).plan(request)

    assert indexed.model_dump() == exhaustive.model_dump()
    assert indexed.calls[0].arguments == {"chemical_formula": "Si"}
