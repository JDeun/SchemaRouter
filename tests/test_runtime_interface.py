import asyncio

import pytest

import schemarouter.runtime as runtime_module
from schemarouter import (
    EndpointSpec,
    ExecutionBudget,
    ExecutionBudgetExceededError,
    ExecutionError,
    ExecutionHooks,
    ExecutionPlan,
    ExecutionPolicy,
    FallbackRoute,
    FieldSpec,
    InvocationUnavailableError,
    ParameterSpec,
    PlanRequest,
    PlanValidationError,
    PostInvocationHookError,
    RetryPolicy,
    RunConfig,
    SchemaDriftError,
    SchemaRouter,
    SessionSchemaExposure,
    SuccessfulCapabilityHistory,
    ToolCall,
    ToolSpec,
)


def make_router(*, read_only: bool | None = True) -> SchemaRouter:
    router = SchemaRouter(
        policy=ExecutionPolicy(
            allow_mutations=True,
            allow_destructive=True,
            allow_unclassified_remote=True,
        )
    )
    router.add_tool(
        ToolSpec(
            name="weather",
            endpoints=[
                EndpointSpec(
                    name="current",
                    parameters=[ParameterSpec(name="city", required=True)],
                    output_fields=[
                        FieldSpec(name="city"),
                        FieldSpec(name="temperature"),
                    ],
                    read_only=read_only,
                )
            ],
        )
    )
    router.executor.bind(
        "weather",
        lambda endpoint, arguments: {
            "city": arguments["city"],
            "temperature": 20,
        },
    )
    return router


def request(city: str = "Seoul") -> PlanRequest:
    return PlanRequest(
        query="city temperature",
        arguments={"city": city},
    )


def test_invoke_exposes_sync_framework_surface() -> None:
    router = make_router()
    result = router.invoke(request())
    assert result[0].data == {"city": "Seoul", "temperature": 20}


@pytest.mark.asyncio
async def test_ainvoke_exposes_async_framework_surface() -> None:
    router = make_router()
    result = await router.ainvoke(request("Busan"))
    assert result[0].data["city"] == "Busan"



def test_add_tool_replace_purges_runtime_state_for_changed_contract() -> None:
    router = make_router()
    router.mark_access_unavailable("weather", "current", cooldown_seconds=60)
    router.register_health_probe("weather", "current", lambda: True)

    replacement = ToolSpec(
        name="weather",
        endpoints=[
            EndpointSpec(
                name="current",
                parameters=[ParameterSpec(name="city", required=True)],
                output_fields=[
                    FieldSpec(name="city"),
                    FieldSpec(name="temperature"),
                    FieldSpec(name="humidity"),
                ],
                read_only=True,
            )
        ],
    )

    router.add_tool(replacement, replace=True)

    assert router.executor.binding_status_for_contract(
        "weather",
        replacement.fingerprint,
    ) == "unbound"
    assert router.unavailable_access_paths() == ()
    assert router.health_snapshots() == ()


def test_add_tool_identical_replace_preserves_runtime_state() -> None:
    router = make_router()
    current = router.registry.get("weather")
    router.register_health_probe("weather", "current", lambda: True)

    router.add_tool(current.model_copy(deep=True), replace=True)

    assert router.executor.binding_status_for_contract(
        "weather",
        current.fingerprint,
    ) == "ready"
    assert len(router.health_snapshots()) == 1

def test_input_output_and_config_schemas_are_introspectable() -> None:
    router = make_router()

    assert router.input_schema["title"] == "PlanRequest"
    assert router.output_schema["type"] == "array"
    assert "max_concurrency" in router.config_schema["properties"]
    assert "max_batch_size" in router.config_schema["properties"]
    assert "execution_mode" in router.config_schema["properties"]
    assert "max_parallel_calls" in router.config_schema["properties"]
    assert "retry" in router.config_schema["properties"]


@pytest.mark.asyncio
async def test_abatch_preserves_input_order() -> None:
    router = make_router()

    async def invoker(endpoint: str, arguments: dict) -> dict:
        if arguments["city"] == "first":
            await asyncio.sleep(0.02)
        return {
            "city": arguments["city"],
            "temperature": 20,
        }

    router.executor.bind("weather", invoker)
    results = await router.abatch(
        [
            request("first"),
            request("second"),
        ],
        config=RunConfig(max_concurrency=2),
    )

    assert results[0][0].data["city"] == "first"
    assert results[1][0].data["city"] == "second"


@pytest.mark.asyncio
async def test_abatch_can_return_exceptions_per_input() -> None:
    router = make_router()

    async def invoker(endpoint: str, arguments: dict) -> dict:
        if arguments["city"] == "bad":
            raise RuntimeError("boom")
        return {
            "city": arguments["city"],
            "temperature": 20,
        }

    router.executor.bind("weather", invoker)
    results = await router.abatch(
        [
            request("good"),
            request("bad"),
        ],
        return_exceptions=True,
    )

    assert results[0][0].data["city"] == "good"
    assert isinstance(results[1], Exception)


@pytest.mark.asyncio
async def test_astream_yields_tool_results_incrementally() -> None:
    router = make_router()
    results = [
        result
        async for result in router.astream(request())
    ]

    assert len(results) == 1
    assert results[0].tool == "weather"


def test_stream_yields_tool_results_synchronously() -> None:
    router = make_router()
    results = list(router.stream(request()))

    assert len(results) == 1
    assert results[0].endpoint == "current"


@pytest.mark.asyncio
async def test_astream_events_are_typed_ordered_and_redacted_by_default() -> None:
    router = make_router()
    events = [
        event
        async for event in router.astream_events(
            request(),
            config=RunConfig(
                tags=["prod", "smoke"],
                metadata={"tenant": "example"},
            ),
        )
    ]

    assert [event.event for event in events] == [
        "run.start",
        "plan.end",
        "tool.start",
        "tool.end",
        "run.end",
    ]
    assert [event.sequence for event in events] == list(range(len(events)))
    assert len({event.run_id for event in events}) == 1
    assert events[0].tags == ["prod", "smoke"]
    assert events[0].metadata == {"tenant": "example"}

    tool_start = next(event for event in events if event.event == "tool.start")
    tool_end = next(event for event in events if event.event == "tool.end")
    assert tool_start.data["argument_names"] == ["city"]
    assert "arguments" not in tool_start.data
    assert "result" not in tool_end.data


@pytest.mark.asyncio
async def test_astream_events_can_opt_into_payloads() -> None:
    router = make_router()
    events = [
        event
        async for event in router.astream_events(
            request(),
            config=RunConfig(include_payloads=True),
        )
    ]

    tool_start = next(event for event in events if event.event == "tool.start")
    tool_end = next(event for event in events if event.event == "tool.end")
    assert tool_start.data["arguments"] == {"city": "Seoul"}
    assert tool_end.data["result"]["data"]["temperature"] == 20



@pytest.mark.asyncio
async def test_event_stream_success_matches_ainvoke_result_payload() -> None:
    invoke_router = make_router()
    event_router = make_router()

    expected = await invoke_router.ainvoke(request())
    events = [
        event
        async for event in event_router.astream_events(
            request(),
            config=RunConfig(include_payloads=True),
        )
    ]

    terminal_results = [
        event.data["result"]
        for event in events
        if event.event == "tool.end"
    ]
    assert terminal_results == [result.model_dump(mode="json") for result in expected]
    assert events[-1].event == "run.end"


@pytest.mark.asyncio
async def test_event_stream_failure_matches_ainvoke_exception_type() -> None:
    async def failing(endpoint: str, arguments: dict) -> dict:
        raise RuntimeError("same failure")

    invoke_router = make_router()
    event_router = make_router()
    invoke_router.executor.bind("weather", failing)
    event_router.executor.bind("weather", failing)

    with pytest.raises(ExecutionError) as invoke_error:
        await invoke_router.ainvoke(request())

    seen = []
    with pytest.raises(type(invoke_error.value)):
        async for event in event_router.astream_events(request()):
            seen.append(event)

    assert seen[-1].event == "run.error"
    assert seen[-1].data["error_type"] == type(invoke_error.value).__name__

@pytest.mark.asyncio
async def test_event_stream_records_tool_success_before_post_invocation_hook_error() -> None:
    def failing_after(tool, endpoint, hook_call, result) -> None:
        raise RuntimeError("audit sink unavailable")

    router = SchemaRouter(
        policy=ExecutionPolicy(
            allow_mutations=True,
            allow_destructive=True,
            allow_unclassified_remote=True,
        ),
        execution_hooks=ExecutionHooks(after_call=[failing_after]),
    )
    router.add_tool(
        ToolSpec(
            name="weather",
            endpoints=[
                EndpointSpec(
                    name="current",
                    parameters=[ParameterSpec(name="city", required=True)],
                    output_fields=[
                        FieldSpec(name="city"),
                        FieldSpec(name="temperature"),
                    ],
                    read_only=False,
                )
            ],
        )
    )
    router.executor.bind(
        "weather",
        lambda endpoint, arguments: {
            "city": arguments["city"],
            "temperature": 20,
        },
    )

    seen = []
    with pytest.raises(PostInvocationHookError) as exc_info:
        async for event in router.astream_events(
            request(),
            config=RunConfig(include_payloads=True),
        ):
            seen.append(event)

    assert [event.event for event in seen] == [
        "run.start",
        "plan.end",
        "tool.start",
        "tool.end",
        "run.error",
    ]
    assert all(event.event != "tool.error" for event in seen)

    tool_end = next(event for event in seen if event.event == "tool.end")
    assert tool_end.data["execution_succeeded"] is True
    assert tool_end.data["post_invocation_stage"] == "after_hook"
    assert tool_end.data["post_invocation_error_type"] == "PostInvocationHookError"
    assert tool_end.data["result"]["data"] == {
        "city": "Seoul",
        "temperature": 20,
    }

    run_error = seen[-1]
    assert run_error.data["stage"] == "post_invocation_hook"
    assert run_error.data["execution_succeeded"] is True
    assert exc_info.value.execution_succeeded is True
    assert exc_info.value.result.data == {
        "city": "Seoul",
        "temperature": 20,
    }


@pytest.mark.asyncio
async def test_read_only_retry_can_recover() -> None:
    router = make_router(read_only=True)
    attempts = 0

    async def flaky(endpoint: str, arguments: dict) -> dict:
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            raise RuntimeError("transient")
        return {
            "city": arguments["city"],
            "temperature": 20,
        }

    router.executor.bind("weather", flaky)
    result = await router.ainvoke(
        request(),
        config=RunConfig(
            retry=RetryPolicy(
                max_attempts=3,
                initial_backoff_seconds=0,
            )
        ),
    )

    assert attempts == 3
    assert result[0].data["temperature"] == 20


@pytest.mark.asyncio
async def test_non_read_only_is_not_retried_by_default() -> None:
    router = make_router(read_only=False)
    attempts = 0

    async def failing(endpoint: str, arguments: dict) -> dict:
        nonlocal attempts
        attempts += 1
        raise RuntimeError("write failed")

    router.executor.bind("weather", failing)
    with pytest.raises(ExecutionError, match="after 1 attempt"):
        await router.ainvoke(
            request(),
            config=RunConfig(
                retry=RetryPolicy(max_attempts=3)
            ),
        )

    assert attempts == 1


@pytest.mark.asyncio
async def test_sync_invoke_rejects_active_event_loop_without_coroutine_warning() -> None:
    router = make_router()

    with pytest.raises(RuntimeError, match="active event loop"):
        router.invoke(request())


def test_with_config_binds_default_runtime_configuration() -> None:
    router = make_router()
    configured = router.with_config(
        RunConfig(
            tags=["bound"],
            metadata={"source": "test"},
        )
    )

    result = configured.invoke(request())
    assert result[0].data["city"] == "Seoul"


@pytest.mark.asyncio
async def test_abatch_as_completed_yields_completion_order_with_input_indexes() -> None:
    router = make_router()

    async def invoker(endpoint: str, arguments: dict) -> dict:
        if arguments["city"] == "slow":
            await asyncio.sleep(0.02)
        return {
            "city": arguments["city"],
            "temperature": 20,
        }

    router.executor.bind("weather", invoker)
    completed = [
        item
        async for item in router.abatch_as_completed(
            [request("slow"), request("fast")],
            config=RunConfig(max_concurrency=2),
        )
    ]

    assert [index for index, _ in completed] == [1, 0]
    assert completed[0][1][0].data["city"] == "fast"


def test_batch_as_completed_has_sync_surface() -> None:
    router = make_router()
    completed = list(
        router.batch_as_completed(
            [request("Seoul"), request("Busan")],
        )
    )

    assert sorted(index for index, _ in completed) == [0, 1]



def make_parallel_plan_router(*, second_read_only: bool | None = True):
    router = SchemaRouter(
        policy=ExecutionPolicy(
            allow_mutations=True,
            allow_unclassified_remote=True,
        )
    )
    tool = ToolSpec(
        name="fanout",
        endpoints=[
            EndpointSpec(
                name="slow",
                read_only=True,
                output_fields=[FieldSpec(name="value")],
            ),
            EndpointSpec(
                name="fast",
                read_only=second_read_only,
                output_fields=[FieldSpec(name="value")],
            ),
        ],
    )
    router.add_tool(tool)
    calls = [
        ToolCall(
            tool="fanout",
            endpoint=name,
            fields=["value"],
            schema_fingerprint=router.registry.endpoint("fanout", name).fingerprint,
        )
        for name in ("slow", "fast")
    ]
    return router, ExecutionPlan(
        query="fan out",
        registry_version=router.registry.version,
        calls=calls,
    )


@pytest.mark.asyncio
async def test_parallel_read_only_execute_preserves_plan_order() -> None:
    router, plan = make_parallel_plan_router()

    async def invoker(endpoint: str, arguments: dict) -> dict:
        if endpoint == "slow":
            await asyncio.sleep(0.03)
        return {"value": endpoint}

    router.executor.bind("fanout", invoker)

    results = await router.execute(
        plan,
        config=RunConfig(
            execution_mode="parallel_read_only",
            max_concurrency=2,
        ),
    )

    assert [result.data["value"] for result in results] == ["slow", "fast"]


@pytest.mark.asyncio
async def test_parallel_read_only_stream_yields_completion_order() -> None:
    router, plan = make_parallel_plan_router()

    async def invoker(endpoint: str, arguments: dict) -> dict:
        if endpoint == "slow":
            await asyncio.sleep(0.03)
        return {"value": endpoint}

    router.executor.bind("fanout", invoker)

    original_aplan = router.aplan_executable

    async def fixed_plan(request):
        return plan

    router.aplan_executable = fixed_plan  # type: ignore[method-assign]
    try:
        results = [
            result
            async for result in router.astream(
                "fan out",
                config=RunConfig(
                    execution_mode="parallel_read_only",
                    max_concurrency=2,
                ),
            )
        ]
    finally:
        router.aplan_executable = original_aplan  # type: ignore[method-assign]

    assert [result.data["value"] for result in results] == ["fast", "slow"]


@pytest.mark.asyncio
async def test_parallel_read_only_fails_before_invocation_for_mutating_call() -> None:
    router, plan = make_parallel_plan_router(second_read_only=False)
    invoked = []

    async def invoker(endpoint: str, arguments: dict) -> dict:
        invoked.append(endpoint)
        return {"value": endpoint}

    router.executor.bind("fanout", invoker)

    with pytest.raises(PlanValidationError, match="explicitly read-only"):
        await router.execute(
            plan,
            config=RunConfig(execution_mode="parallel_read_only"),
        )

    assert invoked == []


@pytest.mark.asyncio
async def test_parallel_read_only_shares_execution_budget() -> None:
    router, plan = make_parallel_plan_router()
    invoked: list[str] = []

    async def invoker(endpoint: str, arguments: dict) -> dict:
        invoked.append(endpoint)
        await asyncio.sleep(0)
        return {"value": endpoint}

    router.executor.bind("fanout", invoker)

    with pytest.raises(ExecutionBudgetExceededError, match="max_tool_calls=1"):
        await router.execute(
            plan,
            config=RunConfig(
                execution_mode="parallel_read_only",
                max_concurrency=2,
                budget=ExecutionBudget(max_tool_calls=1),
            ),
        )

    assert len(invoked) == 1


@pytest.mark.asyncio
async def test_parallel_event_stream_cannot_oversubscribe_shared_budget() -> None:
    router, plan = make_parallel_plan_router()
    invoked: list[str] = []

    async def invoker(endpoint: str, arguments: dict) -> dict:
        invoked.append(endpoint)
        await asyncio.sleep(0)
        return {"value": endpoint}

    router.executor.bind("fanout", invoker)
    original_aplan = router.aplan_executable

    async def fixed_plan(request):
        return plan

    router.aplan_executable = fixed_plan  # type: ignore[method-assign]
    events = []
    try:
        with pytest.raises(
            ExecutionBudgetExceededError,
            match="max_tool_calls=1",
        ):
            async for event in router.astream_events(
                "fan out",
                config=RunConfig(
                    execution_mode="parallel_read_only",
                    max_parallel_calls=2,
                    budget=ExecutionBudget(max_tool_calls=1),
                ),
            ):
                events.append(event)
    finally:
        router.aplan_executable = original_aplan  # type: ignore[method-assign]

    assert len(invoked) == 1
    assert any(event.event == "run.error" for event in events)


@pytest.mark.asyncio
async def test_parallel_read_only_event_stream_reports_completion_order() -> None:
    router, plan = make_parallel_plan_router()

    async def invoker(endpoint: str, arguments: dict) -> dict:
        if endpoint == "slow":
            await asyncio.sleep(0.03)
        return {"value": endpoint}

    router.executor.bind("fanout", invoker)
    original_aplan = router.aplan_executable

    async def fixed_plan(request):
        return plan

    router.aplan_executable = fixed_plan  # type: ignore[method-assign]
    try:
        events = [
            event
            async for event in router.astream_events(
                "fan out",
                config=RunConfig(
                    execution_mode="parallel_read_only",
                    max_concurrency=2,
                ),
            )
        ]
    finally:
        router.aplan_executable = original_aplan  # type: ignore[method-assign]

    starts = [event.endpoint for event in events if event.event == "tool.start"]
    ends = [event.endpoint for event in events if event.event == "tool.end"]
    assert starts == ["slow", "fast"]
    assert ends == ["fast", "slow"]
    assert events[-1].event == "run.end"


@pytest.mark.asyncio
async def test_max_parallel_calls_is_independent_from_batch_concurrency() -> None:
    router, plan = make_parallel_plan_router()
    active = 0
    max_active = 0

    async def invoker(endpoint: str, arguments: dict) -> dict:
        nonlocal active, max_active
        active += 1
        max_active = max(max_active, active)
        try:
            await asyncio.sleep(0.02)
            return {"value": endpoint}
        finally:
            active -= 1

    router.executor.bind("fanout", invoker)

    results = await router.execute(
        plan,
        config=RunConfig(
            execution_mode="parallel_read_only",
            max_concurrency=32,
            max_parallel_calls=1,
        ),
    )

    assert [result.data["value"] for result in results] == ["slow", "fast"]
    assert max_active == 1


@pytest.mark.asyncio
async def test_parallel_preflight_failure_emits_terminal_run_error() -> None:
    router, plan = make_parallel_plan_router(second_read_only=False)
    router.executor.bind(
        "fanout",
        lambda endpoint, arguments: {"value": endpoint},
    )
    original_aplan = router.aplan_executable

    async def fixed_plan(request):
        return plan

    router.aplan_executable = fixed_plan  # type: ignore[method-assign]
    events = []
    try:
        with pytest.raises(PlanValidationError, match="explicitly read-only"):
            async for event in router.astream_events(
                "fan out",
                config=RunConfig(execution_mode="parallel_read_only"),
            ):
                events.append(event)
    finally:
        router.aplan_executable = original_aplan  # type: ignore[method-assign]

    assert [event.event for event in events] == [
        "run.start",
        "plan.end",
        "run.error",
    ]
    assert events[-1].data["stage"] == "execution"
    assert events[-1].data["phase"] == "parallel_preflight"


@pytest.mark.asyncio
async def test_parallel_event_tool_start_tracks_actual_concurrency_slot() -> None:
    router, plan = make_parallel_plan_router()

    async def invoker(endpoint: str, arguments: dict) -> dict:
        await asyncio.sleep(0.01)
        return {"value": endpoint}

    router.executor.bind("fanout", invoker)
    original_aplan = router.aplan_executable

    async def fixed_plan(request):
        return plan

    router.aplan_executable = fixed_plan  # type: ignore[method-assign]
    try:
        events = [
            event
            async for event in router.astream_events(
                "fan out",
                config=RunConfig(
                    execution_mode="parallel_read_only",
                    max_parallel_calls=1,
                ),
            )
        ]
    finally:
        router.aplan_executable = original_aplan  # type: ignore[method-assign]

    tool_events = [
        event.event
        for event in events
        if event.event.startswith("tool.")
    ]
    assert tool_events == [
        "tool.start",
        "tool.end",
        "tool.start",
        "tool.end",
    ]



@pytest.mark.asyncio
async def test_tool_origin_drift_invalidates_planned_call_even_after_rebind() -> None:
    router = SchemaRouter(
        policy=ExecutionPolicy(allow_unclassified_remote=True)
    )
    remote_tool = ToolSpec(
        name="origin",
        endpoints=[EndpointSpec(name="run", read_only=None)],
        metadata={"adapter": "mcp"},
    )
    router.add_tool(remote_tool)
    router.executor.bind("origin", lambda endpoint, arguments: {"ok": True})

    plan = await router.aplan(
        PlanRequest(
            query="origin run",
            preferred_tools=["origin"],
        )
    )
    assert plan.calls[0].tool_fingerprint == remote_tool.fingerprint

    local_tool = ToolSpec(
        name="origin",
        endpoints=[EndpointSpec(name="run", read_only=None)],
    )
    router.registry.register(local_tool, replace=True)
    router.executor.bind("origin", lambda endpoint, arguments: {"ok": True})

    with pytest.raises(SchemaDriftError, match="tool contract changed"):
        await router.execute(plan)



def make_provider_fallback_router() -> tuple[SchemaRouter, ExecutionPlan]:
    router = SchemaRouter()
    tools = [
        ToolSpec(
            name="mp_api",
            provider="materials_project",
            access_mode="openapi",
            endpoints=[
                EndpointSpec(
                    name="search",
                    read_only=True,
                    output_fields=[FieldSpec(name="value")],
                )
            ],
        ),
        ToolSpec(
            name="mp_optimade",
            provider="materials_project",
            access_mode="optimade",
            endpoints=[
                EndpointSpec(
                    name="search",
                    read_only=True,
                    output_fields=[FieldSpec(name="value")],
                )
            ],
        ),
        ToolSpec(
            name="oqmd_api",
            provider="oqmd",
            access_mode="openapi",
            endpoints=[
                EndpointSpec(
                    name="search",
                    read_only=True,
                    output_fields=[FieldSpec(name="value")],
                )
            ],
        ),
    ]
    for tool in tools:
        router.add_tool(tool)

    calls = []
    for tool in tools:
        endpoint = tool.endpoint("search")
        calls.append(
            ToolCall(
                tool=tool.name,
                endpoint="search",
                fields=["value"],
                schema_fingerprint=endpoint.fingerprint,
                tool_fingerprint=tool.fingerprint,
            )
        )

    plan = ExecutionPlan(
        query="value",
        registry_version=router.registry.version,
        calls=[calls[0]],
        fallback_routes=[
            FallbackRoute(
                primary_call_index=0,
                alternatives=[calls[1], calls[2]],
            )
        ],
    )
    return router, plan


@pytest.mark.asyncio
async def test_fallback_event_stream_records_same_then_cross_provider() -> None:
    router, plan = make_provider_fallback_router()

    router.executor.bind(
        "mp_api",
        lambda endpoint, arguments: (_ for _ in ()).throw(
            InvocationUnavailableError("mp api down")
        ),
    )
    router.executor.bind(
        "mp_optimade",
        lambda endpoint, arguments: (_ for _ in ()).throw(
            InvocationUnavailableError("mp optimade down")
        ),
    )
    router.executor.bind(
        "oqmd_api",
        lambda endpoint, arguments: {"value": "from-oqmd"},
    )

    original_aplan = router.aplan_executable

    async def fixed_plan(request):
        return plan

    router.aplan_executable = fixed_plan  # type: ignore[method-assign]
    try:
        events = [
            event
            async for event in router.astream_events("value")
        ]
    finally:
        router.aplan_executable = original_aplan  # type: ignore[method-assign]

    assert [event.event for event in events] == [
        "run.start",
        "plan.end",
        "tool.start",
        "tool.error",
        "tool.fallback",
        "tool.start",
        "tool.error",
        "tool.fallback",
        "tool.start",
        "tool.end",
        "run.end",
    ]
    fallbacks = [event for event in events if event.event == "tool.fallback"]
    assert [event.data["scope"] for event in fallbacks] == [
        "same_provider",
        "cross_provider",
    ]
    assert fallbacks[0].data["access_mode"] == "optimade"
    assert fallbacks[1].data["provider"] == "oqmd"
    assert events[-1].data["fallback_count"] == 2


@pytest.mark.asyncio
async def test_parallel_event_stream_preserves_provider_fallback_trace() -> None:
    router, plan = make_provider_fallback_router()
    router.executor.bind(
        "mp_api",
        lambda endpoint, arguments: (_ for _ in ()).throw(
            InvocationUnavailableError("mp api down")
        ),
    )
    router.executor.bind(
        "mp_optimade",
        lambda endpoint, arguments: {"value": "from-optimade"},
    )
    router.executor.bind(
        "oqmd_api",
        lambda endpoint, arguments: {"value": "from-oqmd"},
    )

    original_aplan = router.aplan_executable

    async def fixed_plan(request):
        return plan

    router.aplan_executable = fixed_plan  # type: ignore[method-assign]
    try:
        events = [
            event
            async for event in router.astream_events(
                "value",
                config=RunConfig(execution_mode="parallel_read_only"),
            )
        ]
    finally:
        router.aplan_executable = original_aplan  # type: ignore[method-assign]

    fallback = next(event for event in events if event.event == "tool.fallback")
    assert fallback.data["scope"] == "same_provider"
    assert fallback.tool == "mp_optimade"
    end = next(event for event in events if event.event == "tool.end")
    assert end.tool == "mp_optimade"
    assert end.data["fallback_used"] is True
    assert events[-1].event == "run.end"
    assert events[-1].data["fallback_count"] == 1



@pytest.mark.asyncio
async def test_event_stream_reports_binding_unavailable_fallback_reason() -> None:
    router, plan = make_provider_fallback_router()

    # Primary intentionally remains unbound.
    router.executor.bind(
        "mp_optimade",
        lambda endpoint, arguments: {"value": "from-optimade"},
    )
    router.executor.bind(
        "oqmd_api",
        lambda endpoint, arguments: {"value": "from-oqmd"},
    )

    original_aplan = router.aplan_executable

    async def fixed_plan(request):
        return plan

    router.aplan_executable = fixed_plan  # type: ignore[method-assign]
    try:
        events = [
            event
            async for event in router.astream_events("value")
        ]
    finally:
        router.aplan_executable = original_aplan  # type: ignore[method-assign]

    fallback = next(event for event in events if event.event == "tool.fallback")
    assert fallback.data["reason"] == "binding_unavailable"
    assert fallback.data["scope"] == "same_provider"
    assert fallback.tool == "mp_optimade"

    starts = [event.tool for event in events if event.event == "tool.start"]
    assert starts == ["mp_optimade"]
    end = next(event for event in events if event.event == "tool.end")
    assert end.tool == "mp_optimade"



def _make_execution_ready_router() -> SchemaRouter:
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
    return router


def test_schema_plan_can_still_describe_unbound_preferred_route() -> None:
    router = _make_execution_ready_router()
    request = PlanRequest(
        query="value",
        preferred_tools=["preferred_unbound"],
    )

    plan = router.plan(request)

    assert plan.calls[0].tool == "preferred_unbound"


def test_plan_executable_filters_unbound_preferred_route() -> None:
    router = _make_execution_ready_router()
    request = PlanRequest(
        query="value",
        preferred_tools=["preferred_unbound"],
    )

    plan = router.plan_executable(request)

    assert plan.calls[0].tool == "bound_route"


@pytest.mark.asyncio
async def test_ainvoke_selects_bound_route_even_when_unbound_route_is_preferred() -> None:
    router = _make_execution_ready_router()
    request = PlanRequest(
        query="value",
        preferred_tools=["preferred_unbound"],
    )

    result = await router.ainvoke(request)

    assert result[0].tool == "bound_route"
    assert result[0].data == {"value": "bound"}


@pytest.mark.asyncio
async def test_event_plan_payload_reflects_execution_ready_route() -> None:
    router = _make_execution_ready_router()
    request = PlanRequest(
        query="value",
        preferred_tools=["preferred_unbound"],
    )

    events = [
        event
        async for event in router.astream_events(
            request,
            config=RunConfig(include_payloads=True),
        )
    ]

    plan_event = next(event for event in events if event.event == "plan.end")
    assert plan_event.data["plan"]["calls"][0]["tool"] == "bound_route"
    assert next(event for event in events if event.event == "tool.end").tool == "bound_route"



def test_retrieve_adaptive_suppresses_already_exposed_schema() -> None:
    router = make_router()
    exposure = SessionSchemaExposure()
    exposure.mark_exposed("weather", "current")

    result = router.retrieve_adaptive(request(), exposure=exposure, k=5)
    assert result.candidates == []

    exposure.compacted()
    restored = router.retrieve_adaptive(request(), exposure=exposure, k=5)
    assert [candidate.route_id for candidate in restored.candidates] == [
        "weather.current"
    ]


@pytest.mark.asyncio
async def test_aretrieve_adaptive_accepts_success_history_without_changing_default() -> None:
    router = make_router()
    history = SuccessfulCapabilityHistory()
    history.record_success("weather", "current")

    baseline = await router.aretrieve(request(), k=5)
    adaptive = await router.aretrieve_adaptive(
        request(),
        history=history,
        history_weight=1.0,
        k=5,
    )
    assert [candidate.route_id for candidate in adaptive.candidates] == [
        candidate.route_id for candidate in baseline.candidates
    ]


def test_execution_plan_rejects_direct_cardinality_bypass() -> None:
    router, plan = make_parallel_plan_router()
    call = plan.calls[0]

    with pytest.raises(ValueError):
        ExecutionPlan(
            query="too many calls",
            registry_version=router.registry.version,
            calls=[call] * 33,
        )

    with pytest.raises(ValueError):
        FallbackRoute(
            primary_call_index=0,
            alternatives=[call] * 9,
        )


@pytest.mark.asyncio
async def test_batch_rejects_request_count_above_configured_limit() -> None:
    router = make_router()

    with pytest.raises(ValueError, match="max_batch_size"):
        await router.abatch(
            [request(str(index)) for index in range(4)],
            config=RunConfig(max_batch_size=3),
        )


@pytest.mark.asyncio
async def test_abatch_creates_only_bounded_worker_tasks(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    router = make_router()
    real_create_task = asyncio.create_task
    created = 0

    def counting_create_task(coro, *args, **kwargs):
        nonlocal created
        created += 1
        return real_create_task(coro, *args, **kwargs)

    monkeypatch.setattr(
        runtime_module.asyncio,
        "create_task",
        counting_create_task,
    )

    results = await router.abatch(
        [request(str(index)) for index in range(20)],
        config=RunConfig(
            max_concurrency=3,
            max_batch_size=20,
        ),
    )

    assert len(results) == 20
    assert created == 3


@pytest.mark.asyncio
async def test_abatch_as_completed_creates_only_bounded_worker_tasks(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    router = make_router()
    real_create_task = asyncio.create_task
    created = 0

    def counting_create_task(coro, *args, **kwargs):
        nonlocal created
        created += 1
        return real_create_task(coro, *args, **kwargs)

    monkeypatch.setattr(
        runtime_module.asyncio,
        "create_task",
        counting_create_task,
    )

    completed = [
        item
        async for item in router.abatch_as_completed(
            [request(str(index)) for index in range(20)],
            config=RunConfig(
                max_concurrency=4,
                max_batch_size=20,
            ),
        )
    ]

    assert sorted(index for index, _ in completed) == list(range(20))
    assert created == 4


@pytest.mark.asyncio
async def test_parallel_event_stream_creates_only_bounded_worker_tasks(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    router, small_plan = make_parallel_plan_router()
    call = small_plan.calls[0]
    plan = ExecutionPlan(
        query="bounded fanout",
        registry_version=router.registry.version,
        calls=[call.model_copy(deep=True) for _ in range(20)],
    )

    async def fake_plan(request):
        del request
        return plan

    async def invoker(endpoint: str, arguments: dict) -> dict:
        del arguments
        return {"value": endpoint}

    router.executor.bind("fanout", invoker)
    monkeypatch.setattr(router, "aplan_executable", fake_plan)

    real_create_task = asyncio.create_task
    created = 0

    def counting_create_task(coro, *args, **kwargs):
        nonlocal created
        created += 1
        return real_create_task(coro, *args, **kwargs)

    monkeypatch.setattr(
        runtime_module.asyncio,
        "create_task",
        counting_create_task,
    )

    events = [
        event
        async for event in router.astream_events(
            "bounded",
            config=RunConfig(
                execution_mode="parallel_read_only",
                max_parallel_calls=3,
            ),
        )
    ]

    assert sum(event.event == "tool.end" for event in events) == 20
    assert created == 3
