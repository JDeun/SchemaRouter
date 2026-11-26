from __future__ import annotations

import argparse
import asyncio
import json
import platform
import time
from collections.abc import Awaitable, Callable
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from pydantic import BaseModel

from schemarouter import (
    ApprovalDeniedError,
    AuthorizationPolicy,
    AuthorizationRule,
    BindingDriftError,
    CapabilityFieldContract,
    EndpointSpec,
    ExecutionBudget,
    ExecutionBudgetExceededError,
    ExecutionPlan,
    ExecutionPolicy,
    FallbackRoute,
    FieldSpec,
    NativeConceptCatalog,
    NativeDeclaredConcept,
    PaperIntentDeclaration,
    PaperIntentRegistry,
    PaperNativeRankPolicy,
    PaperPlanRequest,
    ParameterSpec,
    PolicyRule,
    PolicyViolationError,
    PrincipalContext,
    RetryPolicy,
    RunConfig,
    SchemaDriftError,
    SchemaFieldRoutingSession,
    SchemaRouter,
    SchemaValidationError,
    SQLiteRegistry,
    SQLiteRunTraceStore,
    ToolCall,
    ToolSpec,
    TransientInvocationError,
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


def _host_plan(
    router: SchemaRouter,
    query: str,
    *routes: tuple[str, str, dict[str, object]],
) -> ExecutionPlan:
    """Exercise execution-only contracts with exact host-selected routes.

    This fixture performs no discovery, scoring, argument inference or
    execution authorization. The current registry and executor remain the
    source of truth for schema validation, policy, and binding checks.
    """
    calls = []
    for tool_key, endpoint_name, arguments in routes:
        tool = router.registry.get(tool_key)
        endpoint = tool.endpoint(endpoint_name)
        calls.append(ToolCall(
            tool=tool.key,
            endpoint=endpoint.name,
            arguments=arguments,
            fields=[field.name for field in endpoint.output_fields],
            schema_fingerprint=endpoint.fingerprint,
            tool_fingerprint=tool.fingerprint,
        ))
    return ExecutionPlan(
        query=query, registry_version=router.registry.version, calls=calls,
    )


_WEATHER_PRINCIPAL = PrincipalContext(subject="consumer-acceptance", roles=("reader",))
_WEATHER_ROUTE = "current_weather.call"


def _weather_invoker(callback: Callable[[str], Weather]) -> Callable[[str, dict[str, Any]], Any]:
    def invoke(endpoint: str, arguments: dict[str, Any]) -> dict[str, Any]:
        assert endpoint == "call"
        return callback(arguments["city"]).model_dump(mode="json")

    return invoke


def _paper_weather(
    router: SchemaRouter,
    callback: Callable[[str], Weather] = current_weather,
    *,
    bound: bool = True,
) -> SchemaFieldRoutingSession:
    """Register owner-reviewed weather metadata and a local Understand fixture."""
    router.authorization_policy = AuthorizationPolicy(
        default_effect="deny",
        rules=(AuthorizationRule(
            effect="allow", operation=_WEATHER_ROUTE, roles_any=("reader",),
        ),),
    )
    tool = ToolSpec(
        name="current_weather", source_type="calculated", license="CC0-1.0",
        endpoints=[EndpointSpec(
            name="call", read_only=True,
            parameters=[ParameterSpec(
                name="city", required=True, json_schema={"type": "string"},
            )],
            input_schema={
                "type": "object", "properties": {"city": {"type": "string"}},
                "required": ["city"], "additionalProperties": False,
            },
            output_fields=[
                FieldSpec(name="city", semantic_id="weather.city", identifier=True,
                          json_schema={"type": "string"}),
                FieldSpec(name="temperature", semantic_id="weather.temperature",
                          json_schema={"type": "number"}),
            ],
            output_schema={
                "type": "object", "properties": {
                    "city": {"type": "string"}, "temperature": {"type": "number"},
                }, "required": ["city", "temperature"], "additionalProperties": False,
            },
        )],
    )
    if bound:
        router.add_bound_tool(tool, _weather_invoker(callback))
    else:
        router.add_tool(tool)

    catalog = NativeConceptCatalog(concepts=(NativeDeclaredConcept(
        concept_id="weather.temperature", aliases=("city temperature",),
        required_fields=(CapabilityFieldContract(
            semantic_id="weather.temperature", json_schema={"type": "number"},
        ),), source_type="calculated", license="CC0-1.0",
    ),))
    session = router.prepare_field_routing(
        catalog=catalog, approved_host_roots=frozenset({_WEATHER_ROUTE}),
    )
    intents = PaperIntentRegistry(
        intents=(PaperIntentDeclaration(
            intent_id="weather.read", required_concept_ids=("weather.temperature",),
            recall_group_ids=("weather",),
        ),),
        projection_snapshot_id=session.snapshot_id,
        route_field_groups={_WEATHER_ROUTE: {"weather": ("temperature",)}},
        approved_direct_parameter_routes=(_WEATHER_ROUTE,),
    )

    def understand(payload: dict[str, Any]) -> dict[str, Any]:
        # This deterministic owner callback is not model-quality evidence.
        assert "schema_catalog" not in payload
        return {
            "intent_id": "weather.read",
            "needs": [{
                "concept": "city temperature", "unit": None,
                "source_type": "calculated", "qualifiers": {},
            }],
            "needs_truncated": False,
            "excluded_concepts": [],
            "named_tools": ["current_weather"],
            "parameter_hints": {},
            "source_type": "calculated",
        }

    router.configure_field_routing(
        session, model=understand, intent_registry=intents,
        rank_policy=PaperNativeRankPolicy(
            snapshot_id=session.snapshot_id, direct_score_mode="paper_v1", focus_direct=True,
        ),
        model_visible_intent_ids=("weather.read",),
    )
    return session


def _weather_request() -> PaperPlanRequest:
    return PaperPlanRequest(
        query="city temperature from current_weather",
        host_source_arguments={_WEATHER_ROUTE: {"city": "Seoul"}},
    )


async def scenario_happy_path() -> dict[str, object]:
    router = SchemaRouter()
    _paper_weather(router)
    plan = await router.aplan_authorized(
        _weather_request(), principal=_WEATHER_PRINCIPAL,
    )
    assert plan.planning_status == "ready"
    assert plan.executable
    assert len(plan.calls) == 1
    assert plan.calls[0].tool_fingerprint == router.registry.get("current_weather").fingerprint
    assert set(plan.calls[0].fields) == {"city", "temperature"}

    results = await router.execute(plan, config=RunConfig(principal=_WEATHER_PRINCIPAL))
    assert len(results) == 1
    assert results[0].tool == "current_weather"
    assert results[0].endpoint == "call"
    assert results[0].data == {"city": "Seoul", "temperature": 20.5}
    assert router.inspect().execution.bound_tools == ["current_weather"]
    return {"tool": "current_weather", "result": results[0].data}


async def scenario_capability_retrieval() -> dict[str, object]:
    calls = 0

    def retrieval_probe(city: str) -> Weather:
        nonlocal calls
        calls += 1
        return Weather(city=city, temperature=21.0)

    router = SchemaRouter()
    session = _paper_weather(router, retrieval_probe)
    receipt = session.discover("city temperature", principal=_WEATHER_PRINCIPAL)
    assert receipt.status == "complete"
    assert receipt.requested_k == 5
    assert receipt.executable_authority is False
    assert len(receipt.alternatives) == 1
    assert len(receipt.alternatives[0].routes) == 1
    route = receipt.alternatives[0].routes[0]
    assert route.route_id == _WEATHER_ROUTE
    assert "temperature" in route.output_fields
    tool = router.registry.get("current_weather")
    endpoint = tool.endpoint("call")
    assert route.tool_fingerprint == tool.fingerprint
    assert route.endpoint_fingerprint == endpoint.fingerprint
    assert endpoint.input_schema["type"] == "object"
    assert "city" in endpoint.input_schema["properties"]
    assert endpoint.output_schema

    plan = await router.aplan_executable_authorized(
        _weather_request(), principal=_WEATHER_PRINCIPAL,
    )
    assert plan.executable
    assert len(plan.calls) == 1
    assert plan.calls[0].tool == "current_weather"
    assert plan.calls[0].endpoint == "call"
    assert calls == 0
    results = await router.ainvoke(
        _weather_request(), config=RunConfig(principal=_WEATHER_PRINCIPAL),
    )
    assert calls == 1
    assert results[0].data == {"city": "Seoul", "temperature": 21.0}

    return {
        "route_id": route.route_id,
        "retrieval_side_effects": calls - 1,
        "full_input_schema": bool(endpoint.input_schema),
        "full_output_schema": bool(endpoint.output_schema),
        "discovery_executable_authority": receipt.executable_authority,
    }


async def scenario_policy_and_approval() -> dict[str, object]:
    denied_router = SchemaRouter()
    denied_key = denied_router.add_callable(update_profile)
    denied_plan = _host_plan(
        denied_router, "update profile value", (denied_key, "call", {"value": 2}),
    )
    await _expect(PolicyViolationError, denied_router.execute(denied_plan))

    approval_required = SchemaRouter(
        policy=ExecutionPolicy(
            allow_mutations=True,
            approval_mode="non_read_only",
        )
    )
    required_key = approval_required.add_callable(update_profile)
    required_plan = _host_plan(
        approval_required, "update profile value", (required_key, "call", {"value": 3}),
    )
    await _expect(ApprovalDeniedError, approval_required.execute(required_plan))

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
    approved = await approved_router.execute(_host_plan(
        approved_router, "update profile value", (approved_key, "call", {"value": 4}),
    ))
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
            allow_mutations=True,
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

    result = await router.execute(_host_plan(
        router, "update profile value", (key, "call", {"value": 10}),
    ))
    assert result[0].data == 11
    assert approvals == ["update_profile.call"]
    return {"scoped_rule": "approved_and_executed"}


async def scenario_schema_drift() -> dict[str, object]:
    router = SchemaRouter()
    key = router.add_callable(lookup_value)
    plan = _host_plan(router, "lookup value key", (key, "call", {"key": "alpha"}))
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

    # Pin the new contract but intentionally keep the old invoker binding.
    plan = _host_plan(router, "lookup value key", (key, "call", {"key": "beta"}))
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
    plan = _host_plan(router, "remote contract run", ("remote_contract", "run", {}))

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
        router.execute(_host_plan(
            router, "invalid output value", (key, "call", {"value": 7}),
        )),
    )
    return {"invalid_runtime_output": "blocked"}


async def scenario_retry_and_budget() -> dict[str, object]:
    attempts = 0

    @schema_tool(read_only=True)
    async def flaky(value: int) -> int:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise TransientInvocationError("transient")
        return value

    retry_router = SchemaRouter()
    retry_key = retry_router.add_callable(flaky)
    result = await retry_router.execute(
        _host_plan(retry_router, "flaky value", (retry_key, "call", {"value": 9})),
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
        budget_router.execute(
            _host_plan(budget_router, "slow value", (budget_key, "call", {"value": 1})),
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

    results = await router.execute(
        _host_plan(
            router, "first second value",
            (first_key, "call", {"value": 5}),
            (second_key, "call", {"value": 5}),
        ),
        config=RunConfig(
            execution_mode="parallel_read_only",
            max_parallel_calls=2,
        ),
    )

    assert {result.data for result in results} == {6, 7}
    assert peak == 2
    return {"result_count": len(results), "peak_concurrency": peak}


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

    result = await router.execute(_host_plan(
        router, "elastic modulus", ("scientific_materials", "read", {}),
    ))

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


async def scenario_source_local_arguments() -> dict[str, object]:
    router = SchemaRouter()
    _paper_weather(router)
    missing = PaperPlanRequest(query="city temperature from current_weather")
    incomplete = await router.aplan_authorized(missing, principal=_WEATHER_PRINCIPAL)
    assert not incomplete.executable
    await _expect(
        PolicyViolationError,
        router.aplan_executable_authorized(missing, principal=_WEATHER_PRINCIPAL),
    )

    plan = await router.aplan_authorized(
        _weather_request(), principal=_WEATHER_PRINCIPAL,
    )
    assert plan.planning_status == "ready"
    assert len(plan.calls) == 1
    assert plan.calls[0].arguments == {"city": "Seoul"}
    assert plan.calls[0].missing_required_arguments == []
    assert not plan.fallback_routes
    return {
        "missing_arguments_status": incomplete.planning_status,
        "source_local_arguments": plan.calls[0].arguments,
    }


async def scenario_scientific_field_qualifiers() -> dict[str, object]:
    router = SchemaRouter()
    endpoint = EndpointSpec(
        name="read",
        read_only=True,
        output_fields=[
            FieldSpec(
                name="elastic_modulus",
                semantic_id="elastic_modulus",
                json_schema={"type": "number"},
                unit="GPa",
                qualifiers={
                    "temperature": "300 K",
                    "phase": "alpha",
                },
            )
        ],
    )
    tool = ToolSpec(name="qualified_materials", endpoints=[endpoint])
    router.add_tool(tool)
    router.executor.bind(
        "qualified_materials",
        lambda endpoint_name, arguments: {"elastic_modulus": 130.0},
    )

    result = await router.execute(_host_plan(
        router, "elastic modulus", ("qualified_materials", "read", {}),
    ))

    contract = result[0].field_contracts["elastic_modulus"]
    assert contract.qualifiers == {
        "temperature": "300 K",
        "phase": "alpha",
    }
    return {
        "value": result[0].data["elastic_modulus"],
        "qualifiers": contract.qualifiers,
    }


async def scenario_execution_ready_planning() -> dict[str, object]:
    router = SchemaRouter()
    _paper_weather(router, bound=False)
    request = _weather_request()
    plan = await router.aplan_authorized(request, principal=_WEATHER_PRINCIPAL)
    assert plan.planning_status == "ready"
    assert len(plan.calls) == 1
    assert plan.calls[0].tool == "current_weather"
    await _expect(
        PolicyViolationError,
        router.aplan_executable_authorized(request, principal=_WEATHER_PRINCIPAL),
    )
    router.executor.bind("current_weather", _weather_invoker(current_weather))
    # A new binding cannot authorize the previous plan.
    await _expect(
        PolicyViolationError,
        router.execute(plan, config=RunConfig(principal=_WEATHER_PRINCIPAL)),
    )
    fresh = await router.aplan_executable_authorized(
        request, principal=_WEATHER_PRINCIPAL,
    )
    result = await router.execute(fresh, config=RunConfig(principal=_WEATHER_PRINCIPAL))
    assert result[0].tool == "current_weather"
    assert result[0].data == {"city": "Seoul", "temperature": 20.5}
    return {
        "unbound_plan_denied": True,
        "stale_plan_denied": True,
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
            _paper_weather(router)
            key = "current_weather"

            with SQLiteRunTraceStore(trace_path) as traces:
                events = [
                    event
                    async for event in router.astream_events(
                        _weather_request(),
                        config=RunConfig(
                            tags=["consumer-acceptance"], principal=_WEATHER_PRINCIPAL,
                        ),
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
    ("capability_retrieval", scenario_capability_retrieval),
    ("policy_and_approval", scenario_policy_and_approval),
    ("scoped_policy_rule", scenario_scoped_policy_rule),
    ("schema_drift", scenario_schema_drift),
    ("binding_drift", scenario_binding_drift),
    ("tool_execution_contract_drift", scenario_tool_execution_contract_drift),
    ("output_validation", scenario_output_validation),
    ("retry_and_budget", scenario_retry_and_budget),
    ("parallel_read_only", scenario_parallel_read_only),
    ("scientific_unit_contract", scenario_scientific_unit_contract),
    ("scientific_field_qualifiers", scenario_scientific_field_qualifiers),
    ("source_local_arguments", scenario_source_local_arguments),
    ("execution_ready_planning", scenario_execution_ready_planning),
    ("binding_aware_fallback", scenario_binding_aware_fallback),
    ("inspection_redaction", scenario_inspection_redaction),
    ("persistence_traces_dashboard", scenario_persistence_traces_and_dashboard),
)


async def run_all() -> dict[str, object]:
    report: dict[str, object] = {
        "schema_version": 2,
        "routing_contract": "paper_first",
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
