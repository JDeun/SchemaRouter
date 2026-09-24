import asyncio

import pytest

from schemarouter import (
    EndpointSpec,
    ExecutionBudget,
    ExecutionBudgetExceededError,
    ExecutionError,
    ExecutionPlan,
    ExecutionPolicy,
    FieldSpec,
    ParameterSpec,
    PlanRequest,
    PlanValidationError,
    RetryPolicy,
    RunConfig,
    SchemaRouter,
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


def test_input_output_and_config_schemas_are_introspectable() -> None:
    router = make_router()

    assert router.input_schema["title"] == "PlanRequest"
    assert router.output_schema["type"] == "array"
    assert "max_concurrency" in router.config_schema["properties"]
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

    original_aplan = router.aplan

    async def fixed_plan(request):
        return plan

    router.aplan = fixed_plan  # type: ignore[method-assign]
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
        router.aplan = original_aplan  # type: ignore[method-assign]

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

    async def invoker(endpoint: str, arguments: dict) -> dict:
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


@pytest.mark.asyncio
async def test_parallel_read_only_event_stream_reports_completion_order() -> None:
    router, plan = make_parallel_plan_router()

    async def invoker(endpoint: str, arguments: dict) -> dict:
        if endpoint == "slow":
            await asyncio.sleep(0.03)
        return {"value": endpoint}

    router.executor.bind("fanout", invoker)
    original_aplan = router.aplan

    async def fixed_plan(request):
        return plan

    router.aplan = fixed_plan  # type: ignore[method-assign]
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
        router.aplan = original_aplan  # type: ignore[method-assign]

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
