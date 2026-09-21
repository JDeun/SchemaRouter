import asyncio

import pytest

from schemarouter import (
    ApprovalDeniedError,
    BindingDriftError,
    EndpointSpec,
    ExecutionBudget,
    ExecutionBudgetExceededError,
    ExecutionPlan,
    ExecutionPolicy,
    InMemoryRegistry,
    RegistryExecutor,
    RetryPolicy,
    ToolCall,
    ToolSpec,
)


def _setup(
    *,
    read_only: bool | None = True,
    remote: bool = False,
    policy: ExecutionPolicy | None = None,
    approval_callback=None,
):
    registry = InMemoryRegistry()
    tool = ToolSpec(
        name="demo",
        endpoints=[
            EndpointSpec(
                name="run",
                read_only=read_only,
            )
        ],
        metadata={"adapter": "openapi"} if remote else {},
    )
    registry.register(tool)
    endpoint = registry.endpoint("demo", "run")
    call = ToolCall(
        tool="demo",
        endpoint="run",
        schema_fingerprint=endpoint.fingerprint,
    )
    plan = ExecutionPlan(
        query="run",
        registry_version=registry.version,
        calls=[call],
    )
    executor = RegistryExecutor(
        registry,
        policy=policy,
        approval_callback=approval_callback,
    )
    return registry, executor, call, plan


@pytest.mark.asyncio
async def test_required_approval_fails_closed_without_callback() -> None:
    _, executor, _, plan = _setup(
        read_only=False,
        policy=ExecutionPolicy(
            allow_mutations=True,
            approval_mode="non_read_only",
        ),
    )
    executor.bind("demo", lambda endpoint, arguments: {"ok": True})

    with pytest.raises(ApprovalDeniedError, match="requires trusted local approval"):
        await executor.execute(plan)


@pytest.mark.asyncio
async def test_sync_approval_callback_can_allow_mutation() -> None:
    seen = []

    def approve(tool, endpoint, call):
        seen.append((tool.name, endpoint.name, call.tool))
        return True

    _, executor, _, plan = _setup(
        read_only=False,
        policy=ExecutionPolicy(
            allow_mutations=True,
            approval_mode="non_read_only",
        ),
        approval_callback=approve,
    )
    executor.bind("demo", lambda endpoint, arguments: {"ok": True})

    result = await executor.execute(plan)

    assert result[0].data == {"ok": True}
    assert seen == [("demo", "run", "demo")]


@pytest.mark.asyncio
async def test_async_approval_callback_can_deny() -> None:
    async def deny(tool, endpoint, call):
        await asyncio.sleep(0)
        return False

    _, executor, _, plan = _setup(
        policy=ExecutionPolicy(approval_mode="all"),
        approval_callback=deny,
    )
    executor.bind("demo", lambda endpoint, arguments: {"ok": True})

    with pytest.raises(ApprovalDeniedError, match="was not approved"):
        await executor.execute(plan)


@pytest.mark.asyncio
async def test_approval_callback_exception_fails_closed() -> None:
    def explode(tool, endpoint, call):
        raise RuntimeError("approval service unavailable")

    _, executor, _, plan = _setup(
        policy=ExecutionPolicy(approval_mode="all"),
        approval_callback=explode,
    )
    executor.bind("demo", lambda endpoint, arguments: {"ok": True})

    with pytest.raises(ApprovalDeniedError, match="failed closed"):
        await executor.execute(plan)


@pytest.mark.asyncio
async def test_budget_limits_logical_tool_calls_across_plan() -> None:
    registry = InMemoryRegistry()
    tool = ToolSpec(
        name="demo",
        endpoints=[
            EndpointSpec(name="one", read_only=True),
            EndpointSpec(name="two", read_only=True),
        ],
    )
    registry.register(tool)
    calls = [
        ToolCall(
            tool="demo",
            endpoint=name,
            schema_fingerprint=registry.endpoint("demo", name).fingerprint,
        )
        for name in ("one", "two")
    ]
    plan = ExecutionPlan(query="two", registry_version=registry.version, calls=calls)
    executor = RegistryExecutor(registry)
    executor.bind("demo", lambda endpoint, arguments: {"endpoint": endpoint})

    with pytest.raises(ExecutionBudgetExceededError, match="max_tool_calls=1"):
        await executor.execute(plan, budget=ExecutionBudget(max_tool_calls=1))


@pytest.mark.asyncio
async def test_retry_attempts_consume_attempt_budget() -> None:
    _, executor, call, _ = _setup(read_only=True)
    attempts = 0

    async def flaky(endpoint, arguments):
        nonlocal attempts
        attempts += 1
        raise RuntimeError("transient")

    executor.bind("demo", flaky)

    with pytest.raises(ExecutionBudgetExceededError, match="max_attempts=2"):
        await executor.execute_call(
            call,
            retry=RetryPolicy(max_attempts=3),
            budget=ExecutionBudget(max_attempts=2),
        )

    assert attempts == 2


@pytest.mark.asyncio
async def test_remote_retry_attempts_consume_remote_budget() -> None:
    _, executor, call, _ = _setup(
        read_only=True,
        remote=True,
        policy=ExecutionPolicy(),
    )
    attempts = 0

    async def flaky(endpoint, arguments):
        nonlocal attempts
        attempts += 1
        raise RuntimeError("transient")

    executor.bind("demo", flaky)

    with pytest.raises(ExecutionBudgetExceededError, match="max_remote_attempts=1"):
        await executor.execute_call(
            call,
            retry=RetryPolicy(max_attempts=3),
            budget=ExecutionBudget(max_remote_attempts=1),
        )

    assert attempts == 1


@pytest.mark.asyncio
async def test_per_tool_quota_is_enforced() -> None:
    _, executor, _, plan = _setup()
    executor.bind("demo", lambda endpoint, arguments: {"ok": True})

    with pytest.raises(ExecutionBudgetExceededError, match="per_tool_calls"):
        await executor.execute(
            plan,
            budget=ExecutionBudget(per_tool_calls={"demo": 0}),
        )


@pytest.mark.asyncio
async def test_cost_units_are_charged_per_attempt() -> None:
    _, executor, call, _ = _setup(read_only=True)
    attempts = 0

    async def flaky(endpoint, arguments):
        nonlocal attempts
        attempts += 1
        raise RuntimeError("transient")

    executor.bind("demo", flaky)

    with pytest.raises(ExecutionBudgetExceededError, match="max_cost_units=1.5"):
        await executor.execute_call(
            call,
            retry=RetryPolicy(max_attempts=3),
            budget=ExecutionBudget(
                max_cost_units=1.5,
                cost_units={"demo.run": 1.0},
            ),
        )

    assert attempts == 1


@pytest.mark.asyncio
async def test_wall_clock_budget_interrupts_async_invocation() -> None:
    _, executor, _, plan = _setup(read_only=True)

    async def slow(endpoint, arguments):
        await asyncio.sleep(0.1)
        return {"ok": True}

    executor.bind("demo", slow)

    with pytest.raises(ExecutionBudgetExceededError, match="during invocation"):
        await executor.execute(
            plan,
            budget=ExecutionBudget(max_elapsed_seconds=0.01),
        )


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
def test_budget_rejects_non_finite_costs(value: float) -> None:
    with pytest.raises(ValueError):
        ExecutionBudget(max_cost_units=value)

    with pytest.raises(ValueError):
        ExecutionBudget(cost_units={"demo.run": value})


@pytest.mark.asyncio
async def test_approval_callback_receives_detached_call_snapshot() -> None:
    seen_arguments = []

    def approve(tool, endpoint, call):
        call.arguments["injected"] = "attacker"
        seen_arguments.append(dict(call.arguments))
        return True

    registry = InMemoryRegistry()
    tool = ToolSpec(
        name="demo",
        endpoints=[EndpointSpec(name="run", read_only=True)],
    )
    registry.register(tool)
    endpoint = registry.endpoint("demo", "run")
    call = ToolCall(
        tool="demo",
        endpoint="run",
        schema_fingerprint=endpoint.fingerprint,
    )
    plan = ExecutionPlan(
        query="run",
        registry_version=registry.version,
        calls=[call],
    )
    executor = RegistryExecutor(
        registry,
        policy=ExecutionPolicy(approval_mode="all"),
        approval_callback=approve,
    )
    invoked_arguments = []

    def invoke(endpoint_name, arguments):
        invoked_arguments.append(dict(arguments))
        return {"ok": True}

    executor.bind("demo", invoke)
    result = await executor.execute(plan)

    assert result[0].data == {"ok": True}
    assert seen_arguments == [{"injected": "attacker"}]
    assert invoked_arguments == [{}]
    assert call.arguments == {}


@pytest.mark.asyncio
async def test_registry_drift_during_async_approval_fails_closed() -> None:
    registry = InMemoryRegistry()
    original = ToolSpec(
        name="demo",
        endpoints=[EndpointSpec(name="run", read_only=True)],
    )
    registry.register(original)
    endpoint = registry.endpoint("demo", "run")
    call = ToolCall(
        tool="demo",
        endpoint="run",
        schema_fingerprint=endpoint.fingerprint,
    )
    plan = ExecutionPlan(
        query="run",
        registry_version=registry.version,
        calls=[call],
    )

    async def approve(tool, approved_endpoint, approved_call):
        replacement = ToolSpec(
            name="demo",
            endpoints=[
                EndpointSpec(
                    name="run",
                    read_only=True,
                    metadata={"revision": 2},
                )
            ],
        )
        registry.register(replacement, replace=True)
        return True

    executor = RegistryExecutor(
        registry,
        policy=ExecutionPolicy(approval_mode="all"),
        approval_callback=approve,
    )
    executor.bind("demo", lambda endpoint_name, arguments: {"ok": True})

    with pytest.raises(BindingDriftError):
        await executor.execute(plan)
