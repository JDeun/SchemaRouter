from __future__ import annotations

import argparse
import asyncio
import json
import platform
import time
from collections.abc import Awaitable, Callable
from pathlib import Path
from tempfile import TemporaryDirectory

from pydantic import BaseModel

from schemarouter import (
    ApprovalDeniedError,
    BindingDriftError,
    EndpointSpec,
    ExecutionBudget,
    ExecutionBudgetExceededError,
    ExecutionPlan,
    ExecutionPolicy,
    FallbackRoute,
    FieldSpec,
    ParameterSpec,
    PlanRequest,
    QuantityArgument,
    PolicyRule,
    PolicyViolationError,
    RetryPolicy,
    RunConfig,
    SchemaDriftError,
    SchemaRouter,
    SchemaValidationError,
    SQLiteRegistry,
    SQLiteRunTraceStore,
    ToolCall,
    ToolSpec,
    UnitNormalizationSpec,
    __version__,
    compare_endpoint_specs,
    inspect_registry,
    inspect_traces,
    schema_tool,
    write_dashboard,
)


class Weather(BaseModel):
    city: str
    temperature: float


@schema_tool(read_only=True)
def current_weather(city: str) -> Weather:
    """Return a deterministic observation for consumer acceptance validation."""
    return Weather(city=city, temperature=20.5)


@schema_tool(read_only=False)
def update_profile(value: int) -> int:
    """Represent a local mutating operation."""
    return value + 1


@schema_tool(read_only=True)
def lookup_value(key: str) -> str:
    """Return a deterministic lookup value."""
    return f"value:{key}"


@schema_tool(read_only=True)
def invalid_output(value: int) -> int:
    """Return a deliberately invalid runtime value for schema enforcement validation."""
    return "not-an-int"  # type: ignore[return-value]


async def _expect(
    error_type: type[BaseException],
    awaitable: Awaitable[object],
) -> BaseException:
    try:
        await awaitable
    except error_type as exc:
        return exc
    raise AssertionError(f"expected {error_type.__name__}")


async def scenario_happy_path() -> dict[str, object]:
    router = SchemaRouter()
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


async def scenario_policy_and_approval() -> dict[str, object]:
    denied_router = SchemaRouter()
    denied_key = denied_router.add_callable(update_profile)
    denied_request = PlanRequest(
        query="update profile value",
        preferred_tools=[denied_key],
        arguments={"value": 2},
    )
    await _expect(PolicyViolationError, denied_router.ainvoke(denied_request))

    approval_required = SchemaRouter(
        policy=ExecutionPolicy(
            allow_mutations=True,
            approval_mode="non_read_only",
        )
    )
    required_key = approval_required.add_callable(update_profile)
    required_request = PlanRequest(
        query="update profile value",
        preferred_tools=[required_key],
        arguments={"value": 3},
    )
    await _expect(ApprovalDeniedError, approval_required.ainvoke(required_request))

    approvals: list[str] = []

    def approve(tool, endpoint, call) -> bool:
        approvals.append(f"{tool.key}.{endpoint.name}")
        assert call.arguments == {"value": 4}
        return True

    approved_router = SchemaRouter(
        policy=ExecutionPolicy(
            allow_mutations=True,
            approval_mode="non_read_only",
        ),
        approval_callback=approve,
    )
    approved_key = approved_router.add_callable(update_profile)
    approved = await approved_router.ainvoke(
        PlanRequest(
            query="update profile value",
            preferred_tools=[approved_key],
            arguments={"value": 4},
        )
    )
    assert approved[0].data == 5
    assert approvals == [f"{approved_key}.call"]
    return {
        "default_policy": "denied",
        "missing_approval": "denied",
        "trusted_approval": "executed",
    }


async def scenario_scoped_policy_rule() -> dict[str, object]:
    approvals: list[str] = []

    def approve(tool, endpoint, call) -> bool:
        approvals.append(f"{tool.key}.{endpoint.name}")
        return True

    router = SchemaRouter(
        policy=ExecutionPolicy(
            rules=(
                PolicyRule(
                    operation="update_profile.call",
                    effect="require_approval",
                    name="review-profile-update",
                ),
            ),
        ),
        approval_callback=approve,
    )
    key = router.add_callable(update_profile)
    assert key == "update_profile"

    result = await router.ainvoke(
        PlanRequest(
            query="update profile value",
            preferred_tools=[key],
            arguments={"value": 10},
        )
    )
    assert result[0].data == 11
    assert approvals == ["update_profile.call"]
    return {"scoped_rule": "approved_and_executed"}


async def scenario_schema_drift() -> dict[str, object]:
    router = SchemaRouter()
    key = router.add_callable(lookup_value)
    plan = await router.aplan(
        PlanRequest(
            query="lookup value key",
            preferred_tools=[key],
            arguments={"key": "alpha"},
        )
    )
    assert plan.executable

    original = router.registry.get(key)
    changed_endpoint = original.endpoints[0].model_copy(
        update={"description": "changed after planning"},
        deep=True,
    )
    changed = original.model_copy(
        update={"endpoints": [changed_endpoint]},
        deep=True,
    )
    report = compare_endpoint_specs(original.endpoints[0], changed_endpoint)
    assert report.compatibility == "compatible"
    assert report.changed

    router.registry.register(changed, replace=True)

    await _expect(SchemaDriftError, router.execute(plan))
    return {
        "stale_plan": "blocked",
        "diagnostic_compatibility": report.compatibility,
    }


async def scenario_binding_drift() -> dict[str, object]:
    router = SchemaRouter()
    key = router.add_callable(lookup_value)

    original = router.registry.get(key)
    changed = original.model_copy(
        update={"description": "tool contract changed without rebinding"},
        deep=True,
    )
    router.registry.register(changed, replace=True)

    # Replan against the new contract but intentionally keep the old invoker binding.
    plan = await router.aplan(
        PlanRequest(
            query="lookup value key",
            preferred_tools=[key],
            arguments={"key": "beta"},
        )
    )
    assert plan.executable

    await _expect(BindingDriftError, router.execute(plan))
    return {"stale_binding": "blocked"}


async def scenario_tool_execution_contract_drift() -> dict[str, object]:
    router = SchemaRouter()
    original = ToolSpec(
        name="remote_contract",
        remote=True,
        execution_metadata={
            "adapter": "test",
            "approved_base_url": "https://a.example/api",
        },
        endpoints=[EndpointSpec(name="run", read_only=True)],
    )
    router.add_tool(original)
    router.executor.bind(
        "remote_contract",
        lambda endpoint, arguments: {"origin": "a"},
    )
    plan = await router.aplan(
        PlanRequest(
            query="remote contract run",
            preferred_tools=["remote_contract"],
        )
    )

    changed = original.model_copy(deep=True)
    changed.execution_metadata["approved_base_url"] = "https://b.example/api"
    router.registry.register(changed, replace=True)
    router.executor.bind(
        "remote_contract",
        lambda endpoint, arguments: {"origin": "b"},
    )

    await _expect(SchemaDriftError, router.execute(plan))
    return {"stale_tool_contract": "blocked"}


async def scenario_output_validation() -> dict[str, object]:
    router = SchemaRouter()
    key = router.add_callable(invalid_output)
    await _expect(
        SchemaValidationError,
        router.ainvoke(
            PlanRequest(
                query="invalid output value",
                preferred_tools=[key],
                arguments={"value": 7},
            )
        ),
    )
    return {"invalid_runtime_output": "blocked"}


async def scenario_retry_and_budget() -> dict[str, object]:
    attempts = 0

    @schema_tool(read_only=True)
    async def flaky(value: int) -> int:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise RuntimeError("transient")
        return value

    retry_router = SchemaRouter()
    retry_key = retry_router.add_callable(flaky)
    result = await retry_router.ainvoke(
        PlanRequest(
            query="flaky value",
            preferred_tools=[retry_key],
            arguments={"value": 9},
        ),
        config=RunConfig(
            retry=RetryPolicy(
                max_attempts=2,
                initial_backoff_seconds=0,
            )
        ),
    )
    assert result[0].data == 9
    assert attempts == 2

    @schema_tool(read_only=True)
    async def slow(value: int) -> int:
        await asyncio.sleep(0.05)
        return value

    budget_router = SchemaRouter()
    budget_key = budget_router.add_callable(slow)
    await _expect(
        ExecutionBudgetExceededError,
        budget_router.ainvoke(
            PlanRequest(
                query="slow value",
                preferred_tools=[budget_key],
                arguments={"value": 1},
            ),
            config=RunConfig(
                budget=ExecutionBudget(max_elapsed_seconds=0.01),
            ),
        ),
    )
    return {"retry_attempts": attempts, "elapsed_budget": "enforced"}


async def scenario_parallel_read_only() -> dict[str, object]:
    active = 0
    peak = 0

    @schema_tool(read_only=True)
    async def first(value: int) -> int:
        nonlocal active, peak
        active += 1
        peak = max(peak, active)
        try:
            await asyncio.sleep(0.01)
            return value + 1
        finally:
            active -= 1

    @schema_tool(read_only=True)
    async def second(value: int) -> int:
        nonlocal active, peak
        active += 1
        peak = max(peak, active)
        try:
            await asyncio.sleep(0.01)
            return value + 2
        finally:
            active -= 1

    router = SchemaRouter()
    first_key = router.add_callable(first)
    second_key = router.add_callable(second)

    results = await router.ainvoke(
        PlanRequest(
            query="first second value",
            preferred_tools=[first_key, second_key],
            arguments={"value": 5},
            max_calls=2,
        ),
        config=RunConfig(
            execution_mode="parallel_read_only",
            max_parallel_calls=2,
        ),
    )

    assert {result.data for result in results} == {6, 7}
    assert peak == 2
    return {"result_count": len(results), "peak_concurrency": peak}


async def scenario_typed_quantity_argument() -> dict[str, object]:
    router = SchemaRouter()
    tool = ToolSpec(
        name="particle_filter",
        endpoints=[
            EndpointSpec(
                name="search",
                read_only=True,
                parameters=[
                    ParameterSpec(
                        name="max_size",
                        json_schema={"type": "number"},
                        unit="m",
                        unit_normalization=UnitNormalizationSpec(
                            dimension="length",
                            canonical_unit="nm",
                            scale=1e9,
                        ),
                    )
                ],
                output_fields=[FieldSpec(name="particle_size")],
            )
        ],
    )
    router.add_tool(tool)

    seen: dict[str, object] = {}

    def invoke(endpoint_name: str, arguments: dict[str, object]) -> dict[str, object]:
        seen.update(arguments)
        return {"particle_size": 90.0}

    router.executor.bind("particle_filter", invoke)

    result = await router.ainvoke(
        PlanRequest(
            query="particle size",
            arguments={
                "max_size": QuantityArgument(value=100.0, unit="nm"),
            },
        )
    )

    converted = seen["max_size"]
    assert isinstance(converted, float)
    assert abs(converted - 1e-7) < 1e-15
    assert result[0].data == {"particle_size": 90.0}
    return {
        "provider_argument": converted,
        "source_unit": "nm",
        "provider_unit": "m",
    }


async def scenario_scientific_unit_contract() -> dict[str, object]:
    router = SchemaRouter()
    field = FieldSpec(
        name="elastic_modulus",
        semantic_id="elastic_modulus",
        aliases=["elastic modulus"],
        json_schema={"type": "number"},
        unit="GPa",
        unit_normalization=UnitNormalizationSpec(
            dimension="pressure",
            canonical_unit="Pa",
            scale=1e9,
        ),
    )
    endpoint = EndpointSpec(
        name="read",
        read_only=True,
        output_fields=[field],
    )
    tool = ToolSpec(name="scientific_materials", endpoints=[endpoint])
    router.add_tool(tool)
    router.executor.bind(
        "scientific_materials",
        lambda endpoint_name, arguments: {"elastic_modulus": 130.0},
    )

    result = await router.ainvoke(
        PlanRequest(
            query="elastic modulus",
            preferred_tools=["scientific_materials"],
        )
    )

    assert result[0].data == {"elastic_modulus": 130_000_000_000.0}
    contract = result[0].field_contracts["elastic_modulus"]
    assert contract.json_schema == {"type": "number"}
    assert contract.source_unit == "GPa"
    assert contract.unit == "Pa"
    assert contract.dimension == "pressure"
    return {
        "value": result[0].data["elastic_modulus"],
        "source_unit": contract.source_unit,
        "canonical_unit": contract.unit,
        "dimension": contract.dimension,
    }


async def scenario_execution_ready_planning() -> dict[str, object]:
    router = SchemaRouter()
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


async def scenario_binding_aware_fallback() -> dict[str, object]:
    router = SchemaRouter()
    primary = ToolSpec(
        name="primary_route",
        provider="provider",
        access_mode="openapi",
        endpoints=[
            EndpointSpec(
                name="read",
                read_only=True,
                output_fields=[FieldSpec(name="value")],
            )
        ],
    )
    fallback = ToolSpec(
        name="fallback_route",
        provider="provider",
        access_mode="python",
        endpoints=[
            EndpointSpec(
                name="read",
                read_only=True,
                output_fields=[FieldSpec(name="value")],
            )
        ],
    )
    router.add_tool(primary)
    router.add_tool(fallback)
    router.executor.bind(
        "fallback_route",
        lambda endpoint, arguments: {"value": "fallback"},
    )

    primary_endpoint = primary.endpoint("read")
    fallback_endpoint = fallback.endpoint("read")
    plan = ExecutionPlan(
        query="value",
        registry_version=router.registry.version,
        calls=[
            ToolCall(
                tool="primary_route",
                endpoint="read",
                fields=["value"],
                schema_fingerprint=primary_endpoint.fingerprint,
                tool_fingerprint=primary.fingerprint,
            )
        ],
        fallback_routes=[
            FallbackRoute(
                primary_call_index=0,
                alternatives=[
                    ToolCall(
                        tool="fallback_route",
                        endpoint="read",
                        fields=["value"],
                        schema_fingerprint=fallback_endpoint.fingerprint,
                        tool_fingerprint=fallback.fingerprint,
                    )
                ],
            )
        ],
    )

    result = (await router.execute(plan))[0]
    snapshot = router.inspect()

    assert result.tool == "fallback_route"
    assert result.data == {"value": "fallback"}
    assert snapshot.execution.binding_states["primary_route"] == "unbound"
    assert snapshot.execution.binding_states["fallback_route"] == "ready"
    return {
        "binding_fallback": result.tool,
        "binding_states": snapshot.execution.binding_states,
    }


async def scenario_inspection_redaction() -> dict[str, object]:
    router = SchemaRouter()
    tool = ToolSpec(
        name="redaction_probe",
        remote=True,
        execution_metadata={
            "adapter": "openapi",
            "source_url": (
                "https://user:password@example.test/openapi.json"
                "?token=secret#fragment"
            ),
            "approved_base_url": "https://api.example.test/v1?tenant=secret",
        },
        endpoints=[EndpointSpec(name="read", read_only=True)],
    )
    router.add_tool(tool)

    snapshot = inspect_registry(router.registry)
    provenance = snapshot.tools[0].provenance
    assert provenance["source_url"] == "https://example.test/openapi.json"
    assert provenance["approved_base_url"] == "https://api.example.test/v1"
    serialized = snapshot.model_dump_json()
    assert "user:password" not in serialized
    assert "token=secret" not in serialized
    assert "tenant=secret" not in serialized
    return {"inspection_url_secrets": "redacted"}


async def scenario_persistence_traces_and_dashboard() -> dict[str, object]:
    with TemporaryDirectory(prefix="schemarouter-acceptance-") as temp:
        root = Path(temp)
        registry_path = root / "registry.sqlite3"
        trace_path = root / "traces.sqlite3"
        dashboard_path = root / "dashboard.html"

        with SQLiteRegistry(registry_path) as registry:
            router = SchemaRouter(registry=registry)
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


Scenario = Callable[[], Awaitable[dict[str, object]]]

SCENARIOS: tuple[tuple[str, Scenario], ...] = (
    ("happy_path", scenario_happy_path),
    ("policy_and_approval", scenario_policy_and_approval),
    ("scoped_policy_rule", scenario_scoped_policy_rule),
    ("schema_drift", scenario_schema_drift),
    ("binding_drift", scenario_binding_drift),
    ("tool_execution_contract_drift", scenario_tool_execution_contract_drift),
    ("output_validation", scenario_output_validation),
    ("retry_and_budget", scenario_retry_and_budget),
    ("parallel_read_only", scenario_parallel_read_only),
    ("scientific_unit_contract", scenario_scientific_unit_contract),
    ("typed_quantity_argument", scenario_typed_quantity_argument),
    ("execution_ready_planning", scenario_execution_ready_planning),
    ("binding_aware_fallback", scenario_binding_aware_fallback),
    ("inspection_redaction", scenario_inspection_redaction),
    ("persistence_traces_dashboard", scenario_persistence_traces_and_dashboard),
)


async def run_all() -> dict[str, object]:
    report: dict[str, object] = {
        "schema_version": 1,
        "schemarouter_version": __version__,
        "python_version": platform.python_version(),
        "platform": platform.platform(),
        "scenarios": [],
    }
    scenarios: list[dict[str, object]] = []

    for name, scenario in SCENARIOS:
        started = time.perf_counter()
        details = await scenario()
        scenarios.append(
            {
                "name": name,
                "status": "success",
                "duration_ms": round((time.perf_counter() - started) * 1000, 3),
                "details": details,
            }
        )

    report["scenarios"] = scenarios
    report["status"] = "success"
    report["scenario_count"] = len(scenarios)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Run dependency-free consumer acceptance scenarios against an installed "
            "SchemaRouter."
        )
    )
    parser.add_argument("--json-out", type=Path, default=None)
    args = parser.parse_args()

    report = asyncio.run(run_all())
    document = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True)
    if args.json_out is not None:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(document + "\n", encoding="utf-8")
    print(document)


if __name__ == "__main__":
    main()
