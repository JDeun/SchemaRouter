"""Historical lexical consumer scenarios, for source-tree regression only.

Do not run these as installed paper-first product acceptance. The original
assertions and fixture semantics are retained until the legacy engine moves
to the research-only package.
"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from schemarouter import (
    EndpointSpec,
    FieldSpec,
    ParameterSpec,
    PlanRequest,
    RunConfig,
    SQLiteRegistry,
    SQLiteRunTraceStore,
    ToolSpec,
    inspect_registry,
    inspect_traces,
    schema_tool,
    write_dashboard,
)
from scripts.consumer_acceptance import Weather, current_weather
from scripts.research_legacy_router import legacy_router


async def scenario_happy_path() -> dict[str, object]:
    router = legacy_router()
    key = router.add_callable(current_weather)

    request = PlanRequest(
        query="city temperature",
        preferred_tools=[key],
        arguments={"city": "Seoul"},
    )
    plan = await router.aplan(request)
    assert plan.calls[0].explanation is not None
    assert plan.calls[0].explanation.candidate_selection == "deterministic"
    assert plan.calls[0].explanation.score_components
    assert plan.calls[0].tool_fingerprint == router.registry.get(key).fingerprint

    results = await router.execute(plan)

    assert len(results) == 1
    assert results[0].tool == key
    assert results[0].endpoint == "call"
    assert results[0].data == {"city": "Seoul", "temperature": 20.5}
    assert router.inspect().execution.bound_tools == [key]
    return {"tool": key, "result": results[0].data}


async def scenario_capability_retrieval() -> dict[str, object]:
    calls = 0

    @schema_tool(read_only=True)
    def retrieval_probe(city: str) -> Weather:
        """Return weather for capability-retrieval acceptance validation."""
        nonlocal calls
        calls += 1
        return Weather(city=city, temperature=21.0)

    router = legacy_router()
    key = router.add_callable(retrieval_probe)
    request = PlanRequest(
        query="current weather city",
        preferred_tools=[key],
        arguments={"city": "Seoul"},
    )

    sync_result = router.retrieve(request, k=1)
    async_result = await router.aretrieve(request, k=1)
    executable = router.retrieve_executable(request, k=1)
    async_executable = await router.aretrieve_executable(request, k=1)

    assert calls == 0
    assert sync_result.requested_k == 1
    assert sync_result.executable_only is False
    assert executable.executable_only is True
    assert async_executable.executable_only is True
    assert len(sync_result.candidates) == 1

    candidate = sync_result.candidates[0]
    assert candidate.route_id == f"{key}.call"
    assert candidate.route_id == async_result.candidates[0].route_id
    assert candidate.route_id == executable.candidates[0].route_id
    assert candidate.route_id == async_executable.candidates[0].route_id
    assert candidate.input_schema["type"] == "object"
    assert "city" in candidate.input_schema["properties"]
    assert candidate.output_schema
    assert candidate.tool_fingerprint == router.registry.get(key).fingerprint
    assert (
        candidate.endpoint_fingerprint
        == router.registry.endpoint(key, "call").fingerprint
    )

    invoked = await router.ainvoke(request)
    assert calls == 1
    assert invoked[0].tool == key
    assert invoked[0].endpoint == "call"

    return {
        "route_id": candidate.route_id,
        "retrieval_side_effects": calls - 1,
        "full_input_schema": bool(candidate.input_schema),
        "full_output_schema": bool(candidate.output_schema),
        "executable_filter": executable.executable_only,
    }


async def scenario_parameter_alias_routing() -> dict[str, object]:
    router = legacy_router()
    provider_a = ToolSpec(
        name="provider_a",
        provider="a",
        access_mode="openapi",
        endpoints=[
            EndpointSpec(
                name="search",
                read_only=True,
                parameters=[ParameterSpec(name="formula", required=True)],
                output_fields=[
                    FieldSpec(
                        name="value",
                        semantic_id="material_value",
                        json_schema={"type": "number"},
                    )
                ],
            )
        ],
    )
    provider_b = ToolSpec(
        name="provider_b",
        provider="b",
        access_mode="optimade",
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
                output_fields=[
                    FieldSpec(
                        name="alternate_value",
                        semantic_id="material_value",
                        json_schema={"type": "number"},
                    )
                ],
            )
        ],
    )
    router.add_tool(provider_a)
    router.add_tool(provider_b)

    plan = router.plan(
        PlanRequest(
            query="material value",
            preferred_tools=["provider_a"],
            arguments={"formula": "Si"},
            fallback_scope="cross_provider",
        )
    )

    route = plan.fallback_route(0)
    assert plan.calls[0].arguments == {"formula": "Si"}
    assert route is not None
    assert route.alternatives[0].tool == "provider_b"
    assert route.alternatives[0].arguments == {"chemical_formula": "Si"}
    return {
        "primary_arguments": plan.calls[0].arguments,
        "fallback_arguments": route.alternatives[0].arguments,
    }


async def scenario_execution_ready_planning() -> dict[str, object]:
    router = legacy_router()
    unbound = ToolSpec(
        name="preferred_unbound",
        provider="provider_a",
        access_mode="openapi",
        endpoints=[
            EndpointSpec(
                name="read",
                read_only=True,
                output_fields=[FieldSpec(name="value")],
            )
        ],
    )
    bound = ToolSpec(
        name="bound_route",
        provider="provider_b",
        access_mode="python",
        endpoints=[
            EndpointSpec(
                name="read",
                read_only=True,
                output_fields=[FieldSpec(name="value")],
            )
        ],
    )
    router.add_tool(unbound)
    router.add_tool(bound)
    router.executor.bind(
        "bound_route",
        lambda endpoint, arguments: {"value": "bound"},
    )

    request = PlanRequest(
        query="value",
        preferred_tools=["preferred_unbound"],
    )
    schema_plan = router.plan(request)
    executable_plan = router.plan_executable(request)
    result = await router.ainvoke(request)

    assert schema_plan.calls[0].tool == "preferred_unbound"
    assert executable_plan.calls[0].tool == "bound_route"
    assert result[0].tool == "bound_route"
    assert result[0].data == {"value": "bound"}
    return {
        "schema_plan": schema_plan.calls[0].tool,
        "execution_plan": executable_plan.calls[0].tool,
        "executed": result[0].tool,
    }


async def scenario_persistence_traces_and_dashboard() -> dict[str, object]:
    with TemporaryDirectory(prefix="schemarouter-acceptance-") as temp:
        root = Path(temp)
        registry_path = root / "registry.sqlite3"
        trace_path = root / "traces.sqlite3"
        dashboard_path = root / "dashboard.html"

        with SQLiteRegistry(registry_path) as registry:
            router = legacy_router(registry=registry)
            key = router.add_callable(current_weather)

            with SQLiteRunTraceStore(trace_path) as traces:
                events = [
                    event
                    async for event in router.astream_events(
                        PlanRequest(
                            query="city temperature",
                            preferred_tools=[key],
                            arguments={"city": "Seoul"},
                        ),
                        config=RunConfig(tags=["consumer-acceptance"]),
                        trace_store=traces,
                    )
                ]
                assert [event.event for event in events] == [
                    "run.start",
                    "plan.end",
                    "tool.start",
                    "tool.end",
                    "run.end",
                ]
                snapshots = inspect_traces(traces, complete=True)
                assert len(snapshots) == 1
                assert snapshots[0].terminal_event == "run.end"
                trace_json = snapshots[0].model_dump_json()
                assert "Seoul" not in trace_json

                dashboard = write_dashboard(
                    inspect_registry(registry),
                    dashboard_path,
                    traces=snapshots,
                    live=router.inspect(),
                )
                assert dashboard == dashboard_path
                html = dashboard_path.read_text(encoding="utf-8")
                assert "SchemaRouter inspection dashboard" in html
                assert key in html
                assert "Seoul" not in html

        with SQLiteRegistry(registry_path) as reopened:
            assert reopened.keys() == (key,)
            assert reopened.version >= 1

        return {
            "registry_reopen": "success",
            "trace_events": len(events),
            "dashboard_bytes": dashboard_path.stat().st_size,
        }


LEGACY_SCENARIOS = (
    ("happy_path", scenario_happy_path),
    ("capability_retrieval", scenario_capability_retrieval),
    ("parameter_alias_routing", scenario_parameter_alias_routing),
    ("execution_ready_planning", scenario_execution_ready_planning),
    ("persistence_traces_and_dashboard", scenario_persistence_traces_and_dashboard),
)


async def run_legacy_scenarios() -> dict[str, object]:
    return {
        "evidence_scope": "historical_lexical_source_only",
        "scenarios": {name: await scenario() for name, scenario in LEGACY_SCENARIOS},
    }


if __name__ == "__main__":
    print(json.dumps(asyncio.run(run_legacy_scenarios()), sort_keys=True))
