import asyncio

import pytest

from schemarouter import (
    ApprovalDeniedError,
    EndpointSpec,
    ExecutionBudget,
    ExecutionBudgetExceededError,
    ExecutionHookError,
    ExecutionHooks,
    ExecutionPlan,
    ExecutionPolicy,
    FieldSpec,
    InMemoryRegistry,
    ParameterSpec,
    RegistryExecutor,
    RetryPolicy,
    SchemaDriftError,
    SchemaRouter,
    ToolCall,
    ToolSpec,
)


def build_registry() -> tuple[InMemoryRegistry, ToolCall]:
    registry = InMemoryRegistry()
    registry.register(
        ToolSpec(
            name="demo",
            description="demo tool",
            endpoints=[
                EndpointSpec(
                    name="run",
                    parameters=[
                        ParameterSpec(
                            name="x",
                            required=True,
                            json_schema={"type": "integer"},
                        )
                    ],
                    output_fields=[FieldSpec(name="value")],
                    output_schema={
                        "type": "object",
                        "properties": {
                            "value": {"type": "integer"},
                            "secret": {"type": "string"},
                        },
                        "required": ["value"],
                    },
                    read_only=True,
                )
            ],
        )
    )
    endpoint = registry.endpoint("demo", "run")
    call = ToolCall(
        tool="demo",
        endpoint="run",
        arguments={"x": 1},
        fields=["value"],
        schema_fingerprint=endpoint.fingerprint,
    )
    return registry, call


@pytest.mark.asyncio
async def test_execution_hooks_are_ordered_and_receive_detached_snapshots() -> None:
    registry, call = build_registry()
    seen: list[tuple[str, object]] = []

    def before_one(tool, endpoint, hook_call):
        seen.append(("before-1", hook_call.arguments["x"]))
        tool.description = "mutated"
        endpoint.description = "mutated"
        hook_call.arguments["x"] = 99

    def before_two(tool, endpoint, hook_call):
        seen.append(("before-2", hook_call.arguments["x"]))

    def after_one(tool, endpoint, hook_call, result):
        seen.append(("after-1", result.data["value"]))
        result.data["value"] = 999

    def after_two(tool, endpoint, hook_call, result):
        seen.append(("after-2", result.data["value"]))

    executor = RegistryExecutor(
        registry,
        hooks=ExecutionHooks(
            before_call=[before_one, before_two],
            after_call=[after_one, after_two],
        ),
    )
    invoked: list[dict] = []

    def invoke(endpoint_name, arguments):
        invoked.append(dict(arguments))
        return {"value": arguments["x"] + 1, "secret": "hidden"}

    executor.bind("demo", invoke)
    result = await executor.execute_call(call)

    assert invoked == [{"x": 1}]
    assert result.data == {"value": 2}
    assert call.arguments == {"x": 1}
    assert registry.get("demo").description == "demo tool"
    assert seen == [
        ("before-1", 1),
        ("before-2", 1),
        ("after-1", 2),
        ("after-2", 2),
    ]


@pytest.mark.asyncio
async def test_after_hook_receives_projected_result_not_raw_output() -> None:
    registry, call = build_registry()
    seen = {}

    def after(tool, endpoint, hook_call, result):
        seen["data"] = result.data

    executor = RegistryExecutor(
        registry,
        hooks=ExecutionHooks(after_call=[after]),
    )
    executor.bind(
        "demo",
        lambda endpoint_name, arguments: {
            "value": 2,
            "secret": "must-not-reach-hook",
        },
    )

    result = await executor.execute_call(call)

    assert result.data == {"value": 2}
    assert seen["data"] == {"value": 2}


@pytest.mark.asyncio
async def test_async_execution_hooks_are_supported_in_order() -> None:
    registry, call = build_registry()
    seen: list[str] = []

    async def before(tool, endpoint, hook_call):
        await asyncio.sleep(0)
        seen.append("before")

    async def after(tool, endpoint, hook_call, result):
        await asyncio.sleep(0)
        seen.append("after")

    executor = RegistryExecutor(
        registry,
        hooks=ExecutionHooks(
            before_call=[before],
            after_call=[after],
        ),
    )
    executor.bind(
        "demo",
        lambda endpoint_name, arguments: {"value": 2},
    )

    await executor.execute_call(call)

    assert seen == ["before", "after"]


@pytest.mark.asyncio
async def test_before_hook_failure_blocks_invocation() -> None:
    registry, call = build_registry()
    calls = 0

    def before(tool, endpoint, hook_call):
        raise RuntimeError("blocked")

    def invoke(endpoint_name, arguments):
        nonlocal calls
        calls += 1
        return {"value": 2}

    executor = RegistryExecutor(
        registry,
        hooks=ExecutionHooks(
            before_call=[before],  # type: ignore[list-item]
        ),
    )
    executor.bind("demo", invoke)

    with pytest.raises(ExecutionHookError, match="before execution hook failed"):
        await executor.execute_call(call)

    assert calls == 0


@pytest.mark.asyncio
async def test_hook_return_values_are_rejected() -> None:
    registry, call = build_registry()

    def before(tool, endpoint, hook_call):
        return True

    executor = RegistryExecutor(
        registry,
        hooks=ExecutionHooks(before_call=[before]),
    )
    executor.bind(
        "demo",
        lambda endpoint_name, arguments: {"value": 2},
    )

    with pytest.raises(ExecutionHookError, match="must return None"):
        await executor.execute_call(call)



@pytest.mark.asyncio
async def test_after_hook_return_values_are_rejected() -> None:
    registry, call = build_registry()

    def after(tool, endpoint, hook_call, result):
        return {"replace": "forbidden"}

    executor = RegistryExecutor(
        registry,
        hooks=ExecutionHooks(
            after_call=[after],  # type: ignore[list-item]
        ),
    )
    executor.bind(
        "demo",
        lambda endpoint_name, arguments: {"value": 2},
    )

    with pytest.raises(ExecutionHookError, match="must return None"):
        await executor.execute_call(call)


@pytest.mark.asyncio
async def test_approval_denial_happens_before_execution_hooks() -> None:
    registry, call = build_registry()
    seen: list[str] = []
    invoked = False

    def before(tool, endpoint, hook_call):
        seen.append("before")

    def invoke(endpoint_name, arguments):
        nonlocal invoked
        invoked = True
        return {"value": 2}

    executor = RegistryExecutor(
        registry,
        policy=ExecutionPolicy(approval_mode="all"),
        approval_callback=lambda tool, endpoint, hook_call: False,
        hooks=ExecutionHooks(before_call=[before]),
    )
    executor.bind("demo", invoke)

    with pytest.raises(ApprovalDeniedError, match="not approved"):
        await executor.execute_call(call)

    assert seen == []
    assert invoked is False


@pytest.mark.asyncio
async def test_before_hook_time_counts_against_elapsed_budget() -> None:
    registry, call = build_registry()
    invoked = False

    async def before(tool, endpoint, hook_call):
        await asyncio.sleep(0.02)

    def invoke(endpoint_name, arguments):
        nonlocal invoked
        invoked = True
        return {"value": 2}

    executor = RegistryExecutor(
        registry,
        hooks=ExecutionHooks(before_call=[before]),
    )
    executor.bind("demo", invoke)

    with pytest.raises(
        ExecutionBudgetExceededError,
        match="max_elapsed_seconds",
    ):
        await executor.execute_call(
            call,
            budget=ExecutionBudget(max_elapsed_seconds=0.01),
        )

    assert invoked is False


@pytest.mark.asyncio
async def test_after_hook_time_counts_against_elapsed_budget() -> None:
    registry, call = build_registry()

    async def after(tool, endpoint, hook_call, result):
        await asyncio.sleep(0.02)

    executor = RegistryExecutor(
        registry,
        hooks=ExecutionHooks(after_call=[after]),
    )
    executor.bind(
        "demo",
        lambda endpoint_name, arguments: {"value": 2},
    )

    with pytest.raises(
        ExecutionBudgetExceededError,
        match="max_elapsed_seconds",
    ):
        await executor.execute_call(
            call,
            budget=ExecutionBudget(max_elapsed_seconds=0.01),
        )

@pytest.mark.asyncio
async def test_after_hook_failure_is_never_retried() -> None:
    registry, call = build_registry()
    attempts = 0

    def invoke(endpoint_name, arguments):
        nonlocal attempts
        attempts += 1
        return {"value": 2}

    def after(tool, endpoint, hook_call, result):
        raise RuntimeError("sink unavailable")

    executor = RegistryExecutor(
        registry,
        hooks=ExecutionHooks(after_call=[after]),
    )
    executor.bind("demo", invoke)

    with pytest.raises(ExecutionHookError, match="after execution hook failed"):
        await executor.execute_call(
            call,
            retry=RetryPolicy(max_attempts=3),
        )

    assert attempts == 1


@pytest.mark.asyncio
async def test_registry_drift_during_async_before_hook_fails_closed() -> None:
    registry, call = build_registry()
    invoked = False

    async def before(tool, endpoint, hook_call):
        replacement = ToolSpec(
            name="demo",
            endpoints=[
                EndpointSpec(
                    name="run",
                    parameters=[
                        ParameterSpec(
                            name="x",
                            required=True,
                            json_schema={"type": "integer"},
                        )
                    ],
                    output_fields=[FieldSpec(name="value")],
                    metadata={"revision": 2},
                    read_only=True,
                )
            ],
        )
        registry.register(replacement, replace=True)
        await asyncio.sleep(0)

    def invoke(endpoint_name, arguments):
        nonlocal invoked
        invoked = True
        return {"value": 2}

    executor = RegistryExecutor(
        registry,
        hooks=ExecutionHooks(before_call=[before]),
    )
    executor.bind("demo", invoke)

    with pytest.raises(SchemaDriftError):
        await executor.execute_call(call)

    assert invoked is False


@pytest.mark.asyncio
async def test_rebind_during_before_hook_uses_latest_invoker() -> None:
    registry, call = build_registry()
    seen: list[str] = []

    executor: RegistryExecutor

    def old_invoker(endpoint_name, arguments):
        seen.append("old")
        return {"value": 1}

    def new_invoker(endpoint_name, arguments):
        seen.append("new")
        return {"value": 2}

    def before(tool, endpoint, hook_call):
        executor.bind("demo", new_invoker)

    executor = RegistryExecutor(
        registry,
        hooks=ExecutionHooks(before_call=[before]),
    )
    executor.bind("demo", old_invoker)

    result = await executor.execute_call(call)

    assert seen == ["new"]
    assert result.data == {"value": 2}


def test_execution_hooks_reject_non_callable_entries() -> None:
    with pytest.raises(TypeError, match="before_call hooks"):
        ExecutionHooks(before_call=[object()])  # type: ignore[list-item]

    with pytest.raises(TypeError, match="after_call hooks"):
        ExecutionHooks(after_call=[object()])  # type: ignore[list-item]


@pytest.mark.asyncio
async def test_schemarouter_exposes_execution_hooks() -> None:
    seen: list[str] = []

    def before(tool, endpoint, hook_call):
        seen.append("before")

    def after(tool, endpoint, hook_call, result):
        seen.append("after")

    router = SchemaRouter(
        execution_hooks=ExecutionHooks(
            before_call=[before],
            after_call=[after],
        )
    )
    registry_tool = ToolSpec(
        name="demo",
        endpoints=[
            EndpointSpec(
                name="run",
                parameters=[
                    ParameterSpec(
                        name="x",
                        required=True,
                        json_schema={"type": "integer"},
                    )
                ],
                output_fields=[FieldSpec(name="value")],
                read_only=True,
            )
        ],
    )
    router.add_tool(registry_tool)
    router.executor.bind(
        "demo",
        lambda endpoint_name, arguments: {"value": arguments["x"] + 1},
    )
    endpoint = router.registry.endpoint("demo", "run")
    result = await router.execute(
        ExecutionPlan(
            query="run",
            registry_version=router.registry.version,
            calls=[
                ToolCall(
                    tool="demo",
                    endpoint="run",
                    arguments={"x": 1},
                    fields=["value"],
                    schema_fingerprint=endpoint.fingerprint,
                )
            ],
        )
    )

    assert result[0].data == {"value": 2}
    assert seen == ["before", "after"]
