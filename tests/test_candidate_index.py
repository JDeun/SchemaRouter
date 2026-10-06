from __future__ import annotations

import threading

from schemarouter import (
    EndpointSpec,
    EvidenceRequirements,
    FieldSpec,
    InMemoryRegistry,
    ParameterSpec,
    PlanningError,
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



def test_candidate_index_semantic_substring_trigrams_preserve_recall() -> None:
    cases = [
        ("ascii_concept_in_field", "thermal_conductivity", "conductivity", True),
        ("ascii_field_in_concept", "elastic", "elasticmodulus", True),
        ("korean_concept_in_field", "상온열전도도값", "열전도도", True),
        ("korean_field_in_concept", "열전도도", "상온열전도도값", True),
        ("short_ascii_collision", "density", "Si", False),
        ("short_non_ascii_collision", "열값", "열", False),
    ]

    for index, (name, field_name, concept, expected) in enumerate(cases):
        registry = InMemoryRegistry()
        registry.register(
            ToolSpec(
                name=name,
                endpoints=[
                    EndpointSpec(
                        name="lookup",
                        output_fields=[FieldSpec(name=field_name)],
                        read_only=True,
                    )
                ],
            )
        )
        analyzer = StaticAnalyzer(QueryIntent(concepts=[concept]))

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

        assert indexed.model_dump() == exhaustive.model_dump(), index
        assert bool(indexed.calls) is expected, index

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


def test_retrieval_reuses_versioned_catalog_snapshot() -> None:
    registry = CountingRegistry()
    registry.update_many(
        [
            make_tool(0, keyword="first"),
            make_tool(1, keyword="second"),
        ]
    )
    planner = SchemaPlanner(registry, candidate_index=True)

    first = planner.retrieve("first", k=2)
    second = planner.retrieve("second", k=2)

    assert first.total_ranked == 2
    assert second.total_ranked == 2
    assert registry.tools_calls == 1

    registry.register(make_tool(2, keyword="third"))
    third = planner.retrieve("third", k=3)

    assert third.total_ranked == 3
    assert registry.tools_calls == 2


def test_candidate_index_reduces_retrieval_scoring_work() -> None:
    registry = make_registry(size=250)

    indexed = CountingPlanner(registry, candidate_index=True)
    indexed_result = indexed.retrieve("needle", k=5)

    exhaustive = CountingPlanner(registry, candidate_index=False)
    exhaustive_result = exhaustive.retrieve("needle", k=5)

    assert indexed_result.model_dump() == exhaustive_result.model_dump()
    assert indexed.score_calls == 1
    assert exhaustive.score_calls == 250


def test_candidate_index_preserves_zero_score_retrieval_tiebreaks() -> None:
    registry = InMemoryRegistry()
    registry.update_many(
        [
            ToolSpec(
                name="z_destructive",
                endpoints=[
                    EndpointSpec(
                        name="run",
                        read_only=False,
                        destructive=True,
                    )
                ],
            ),
            ToolSpec(
                name="a_read_only",
                endpoints=[
                    EndpointSpec(
                        name="read",
                        read_only=True,
                    )
                ],
            ),
        ]
    )

    indexed = SchemaPlanner(registry, candidate_index=True).retrieve(
        "absent-token",
        k=5,
    )
    exhaustive = SchemaPlanner(registry, candidate_index=False).retrieve(
        "absent-token",
        k=5,
    )

    assert indexed.model_dump() == exhaustive.model_dump()
    assert [item.route_id for item in indexed.candidates] == [
        "a_read_only.read",
        "z_destructive.run",
    ]



def test_field_evidence_validation_reuses_candidate_index_snapshot() -> None:
    registry = CountingRegistry()
    registry.register(
        ToolSpec(
            name="materials",
            endpoints=[
                EndpointSpec(
                    name="lookup",
                    output_fields=[
                        FieldSpec(
                            name="band_gap",
                            semantic_id="materials.band_gap",
                            json_schema={"type": "number"},
                            unit="eV",
                        )
                    ],
                    read_only=True,
                )
            ],
        )
    )
    planner = SchemaPlanner(registry, candidate_index=True)
    request = PlanRequest(
        query="band gap",
        concepts=["band_gap"],
        field_evidence={
            "materials.band_gap": EvidenceRequirements(units=True),
        },
    )

    planner.retrieve(request, k=1)
    planner.retrieve(request, k=1)

    assert registry.tools_calls == 1

    registry.register(
        ToolSpec(
            name="thermo",
            endpoints=[
                EndpointSpec(
                    name="lookup",
                    output_fields=[
                        FieldSpec(
                            name="temperature",
                            semantic_id="thermo.temperature",
                            json_schema={"type": "number"},
                            unit="K",
                        )
                    ],
                    read_only=True,
                )
            ],
        )
    )
    updated = PlanRequest(
        query="temperature",
        concepts=["temperature"],
        field_evidence={
            "thermo.temperature": EvidenceRequirements(units=True),
        },
    )

    planner.retrieve(updated, k=1)

    assert registry.tools_calls == 2


class BlockingAfterRankPlanner(SchemaPlanner):
    def __init__(self, *args, **kwargs) -> None:
        self.ranked = threading.Event()
        self.resume = threading.Event()
        self._blocked_once = False
        super().__init__(*args, **kwargs)

    def _sort_candidates(self, candidates, *, catalog_snapshot) -> None:
        super()._sort_candidates(
            candidates,
            catalog_snapshot=catalog_snapshot,
        )
        if not self._blocked_once:
            self._blocked_once = True
            self.ranked.set()
            if not self.resume.wait(timeout=2.0):
                raise AssertionError("test did not resume planner after ranking")


def _run_with_registry_mutation_after_ranking(planner, registry, operation):
    outcome = {}

    def run() -> None:
        try:
            outcome["result"] = operation()
        except BaseException as exc:  # noqa: BLE001
            outcome["error"] = exc

    worker = threading.Thread(target=run)
    worker.start()
    assert planner.ranked.wait(timeout=2.0)
    ranked_version = registry.version
    registry.register(make_tool(1, keyword="later"))
    planner.resume.set()
    worker.join(timeout=2.0)
    assert not worker.is_alive()
    if "error" in outcome:
        raise outcome["error"]
    return ranked_version, outcome["result"]


def test_retrieval_registry_version_is_the_catalog_snapshot_ranked_under_concurrency() -> None:
    for candidate_index in (False, True):
        registry = InMemoryRegistry()
        registry.register(make_tool(0, keyword="first"))
        planner = BlockingAfterRankPlanner(
            registry,
            candidate_index=candidate_index,
        )

        ranked_version, retrieval = _run_with_registry_mutation_after_ranking(
            planner,
            registry,
            lambda planner=planner: planner.retrieve("first", k=1),
        )

        assert retrieval.registry_version == ranked_version
        assert registry.version == ranked_version + 1
        assert [item.route_id for item in retrieval.candidates] == ["tool_0.search"]


def test_plan_registry_version_is_the_catalog_snapshot_ranked_under_concurrency() -> None:
    registry = InMemoryRegistry()
    registry.register(make_tool(0, keyword="first"))
    planner = BlockingAfterRankPlanner(registry, candidate_index=True)

    ranked_version, plan = _run_with_registry_mutation_after_ranking(
        planner,
        registry,
        lambda: planner.plan("first"),
    )

    assert plan.registry_version == ranked_version
    assert registry.version == ranked_version + 1
    assert [call.tool for call in plan.calls] == ["tool_0"]


class AlwaysChurningRegistry(InMemoryRegistry):
    def __init__(self) -> None:
        super().__init__()
        self._churn_index = 0

    def tools(self) -> tuple[ToolSpec, ...]:
        snapshot = super().tools()
        self._churn_index += 1
        self.register(make_tool(1000 + self._churn_index))
        return snapshot


def test_non_index_catalog_capture_fails_closed_under_repeated_churn() -> None:
    registry = AlwaysChurningRegistry()
    registry.register(make_tool(0, keyword="first"))
    planner = SchemaPlanner(registry, candidate_index=False)

    try:
        planner.retrieve("first", k=1)
    except PlanningError as exc:
        assert "changed repeatedly while capturing the planning catalog" in str(exc)
    else:
        raise AssertionError("expected unstable non-index catalog capture to fail closed")
