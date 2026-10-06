import asyncio
import time

import pytest

from schemarouter import (
    ApprovalDeniedError,
    EndpointSpec,
    ExecutionBudget,
    ExecutionBudgetExceededError,
    ExecutionError,
    ExecutionHooks,
    ExecutionPlan,
    ExecutionPolicy,
    InMemoryRegistry,
    PolicyRule,
    RegistryExecutor,
    RetryPolicy,
    SchemaDriftError,
    ToolCall,
    ToolSpec,
)
from schemarouter.executor import ExecutionBudgetTracker


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
        tool_fingerprint=registry.get("demo").fingerprint,
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
async def test_wall_clock_budget_interrupts_async_approval_for_direct_call() -> None:
    async def approve(tool, endpoint, call):
        await asyncio.sleep(1.0)
        return True

    _, executor, call, _ = _setup(
        policy=ExecutionPolicy(approval_mode="all"),
        approval_callback=approve,
    )
    invoked = False

    def invoke(endpoint, arguments):
        nonlocal invoked
        invoked = True
        return {"ok": True}

    executor.bind("demo", invoke)

    started = time.monotonic()
    with pytest.raises(
        ExecutionBudgetExceededError,
        match="during approval callback",
    ):
        await executor.execute_call(
            call,
            budget=ExecutionBudget(max_elapsed_seconds=0.1),
        )
    elapsed = time.monotonic() - started

    assert invoked is False
    assert elapsed < 0.75


@pytest.mark.asyncio
async def test_parallel_budget_reservations_are_atomic_at_exact_boundaries() -> None:
    registry, _, call, _ = _setup(remote=True)
    tool = registry.get("demo")
    tracker = ExecutionBudgetTracker(
        ExecutionBudget(
            max_tool_calls=1,
            per_tool_calls={"demo": 1},
            max_attempts=1,
            max_remote_attempts=1,
            max_cost_units=1.0,
            cost_units={"demo.run": 1.0},
        )
    )

    await tracker._reservation_lock.acquire()
    call_reservations = [
        asyncio.create_task(tracker.before_call(call))
        for _ in range(2)
    ]
    await asyncio.sleep(0)
    tracker._reservation_lock.release()
    call_results = await asyncio.gather(
        *call_reservations,
        return_exceptions=True,
    )

    assert sum(result is None for result in call_results) == 1
    assert sum(
        isinstance(result, ExecutionBudgetExceededError)
        for result in call_results
    ) == 1
    assert tracker.tool_calls == 1
    assert tracker.per_tool_calls == {"demo": 1}

    await tracker._reservation_lock.acquire()
    attempt_reservations = [
        asyncio.create_task(tracker.before_attempt(call, tool))
        for _ in range(2)
    ]
    await asyncio.sleep(0)
    tracker._reservation_lock.release()
    attempt_results = await asyncio.gather(
        *attempt_reservations,
        return_exceptions=True,
    )

    assert sum(result is None for result in attempt_results) == 1
    assert sum(
        isinstance(result, ExecutionBudgetExceededError)
        for result in attempt_results
    ) == 1
    assert tracker.attempts == 1
    assert tracker.remote_attempts == 1
    assert tracker.cost_units == 1.0


@pytest.mark.asyncio
async def test_failed_attempt_reservation_does_not_partially_consume_budget() -> None:
    registry, _, call, _ = _setup(remote=True)
    tool = registry.get("demo")
    tracker = ExecutionBudgetTracker(
        ExecutionBudget(
            max_attempts=2,
            max_remote_attempts=0,
            max_cost_units=2.0,
            cost_units={"demo.run": 1.0},
        )
    )

    with pytest.raises(ExecutionBudgetExceededError, match="max_remote_attempts=0"):
        await tracker.before_attempt(call, tool)

    assert tracker.attempts == 0
    assert tracker.remote_attempts == 0
    assert tracker.cost_units == 0.0


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
async def test_max_backoff_caps_the_first_retry_delay(monkeypatch) -> None:
    _, executor, call, _ = _setup(read_only=True)
    attempts = 0
    delays: list[float] = []

    async def flaky(endpoint, arguments):
        nonlocal attempts
        attempts += 1
        raise RuntimeError("transient")

    async def capture_backoff(self, delay: float) -> None:
        delays.append(delay)

    monkeypatch.setattr(ExecutionBudgetTracker, "wait_backoff", capture_backoff)
    executor.bind("demo", flaky)

    with pytest.raises(ExecutionError, match="after 3 attempt"):
        await executor.execute_call(
            call,
            retry=RetryPolicy(
                max_attempts=3,
                initial_backoff_seconds=10.0,
                backoff_multiplier=2.0,
                max_backoff_seconds=1.0,
            ),
        )

    assert attempts == 3
    assert delays == [1.0, 1.0]


@pytest.mark.asyncio
async def test_wall_clock_budget_interrupts_async_invocation() -> None:
    _, executor, _, plan = _setup(read_only=True)
    invocation_started = asyncio.Event()

    async def slow(endpoint, arguments):
        invocation_started.set()
        await asyncio.sleep(1.0)
        return {"ok": True}

    executor.bind("demo", slow)

    with pytest.raises(ExecutionBudgetExceededError, match="during invocation"):
        await executor.execute(
            plan,
            budget=ExecutionBudget(max_elapsed_seconds=0.1),
        )

    assert invocation_started.is_set()


@pytest.mark.asyncio
async def test_wall_clock_budget_interrupts_retry_backoff() -> None:
    _, executor, call, _ = _setup(read_only=True)
    attempts = 0

    async def flaky(endpoint, arguments):
        nonlocal attempts
        attempts += 1
        raise RuntimeError("transient")

    executor.bind("demo", flaky)

    started = time.monotonic()
    with pytest.raises(
        ExecutionBudgetExceededError,
        match="during retry backoff",
    ):
        await executor.execute_call(
            call,
            retry=RetryPolicy(
                max_attempts=3,
                initial_backoff_seconds=2.0,
            ),
            budget=ExecutionBudget(max_elapsed_seconds=0.2),
        )
    elapsed = time.monotonic() - started

    assert attempts == 1
    assert elapsed < 1.0


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
        tool_fingerprint=original.fingerprint,
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
                    description="changed during approval",
                    read_only=True,
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

    with pytest.raises(SchemaDriftError, match="tool contract changed"):
        await executor.execute(plan)


@pytest.mark.asyncio
async def test_policy_change_during_async_approval_fails_closed_before_invocation() -> None:
    holder: dict[str, RegistryExecutor] = {}

    async def approve(tool, endpoint, call):
        del tool, endpoint, call
        await asyncio.sleep(0)
        holder["executor"].policy = ExecutionPolicy(approval_mode="never")
        return True

    _, executor, _, plan = _setup(
        read_only=True,
        policy=ExecutionPolicy(approval_mode="all"),
        approval_callback=approve,
    )
    holder["executor"] = executor
    invoked: list[str] = []
    executor.bind(
        "demo",
        lambda endpoint, arguments: invoked.append(endpoint) or {"ok": True},
    )

    with pytest.raises(ApprovalDeniedError, match="execution policy changed"):
        await executor.execute(plan)

    assert invoked == []


@pytest.mark.asyncio
async def test_before_hook_cannot_add_approval_requirement_after_no_approval_decision() -> None:
    holder: dict[str, RegistryExecutor] = {}

    def strengthen_policy(tool, endpoint, call) -> None:
        del tool, endpoint, call
        holder["executor"].policy = ExecutionPolicy(
            rules=(
                PolicyRule(
                    operation="demo.run",
                    effect="require_approval",
                    name="late-review",
                ),
            ),
        )

    _, executor, _, plan = _setup(
        read_only=True,
        policy=ExecutionPolicy(),
    )
    holder["executor"] = executor
    executor.hooks = ExecutionHooks(before_call=(strengthen_policy,))
    invoked: list[str] = []
    executor.bind(
        "demo",
        lambda endpoint, arguments: invoked.append(endpoint) or {"ok": True},
    )

    with pytest.raises(ApprovalDeniedError, match="execution policy changed"):
        await executor.execute(plan)

    assert invoked == []


@pytest.mark.asyncio
async def test_offloaded_sync_invocation_rechecks_policy_at_worker_boundary(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, executor, _, plan = _setup(
        read_only=True,
        policy=ExecutionPolicy(),
    )
    invoked: list[str] = []
    executor.bind(
        "demo",
        lambda endpoint, arguments: invoked.append(endpoint) or {"ok": True},
        offload_sync=True,
    )

    original_submit = executor._sync_offload_pool.submit

    def delayed_submit(function, /, *args, **kwargs):
        def cross_worker_boundary():
            executor.policy = ExecutionPolicy(approval_mode="all")
            return function(*args, **kwargs)

        return original_submit(cross_worker_boundary)

    monkeypatch.setattr(executor._sync_offload_pool, "submit", delayed_submit)

    with pytest.raises(ApprovalDeniedError, match="execution policy changed"):
        await executor.execute(plan)

    assert invoked == []


@pytest.mark.asyncio
async def test_scoped_rule_can_require_approval_without_global_approval_mode() -> None:
    seen = []

    def approve(tool, endpoint, call):
        seen.append(f"{call.tool}.{call.endpoint}")
        return True

    _, executor, _, plan = _setup(
        read_only=False,
        policy=ExecutionPolicy(
            allow_mutations=True,
            rules=(
                PolicyRule(
                    operation="demo.run",
                    effect="require_approval",
                    name="review-demo-run",
                ),
            ),
        ),
        approval_callback=approve,
    )
    executor.bind("demo", lambda endpoint, arguments: {"ok": True})

    result = await executor.execute(plan)

    assert result[0].data == {"ok": True}
    assert seen == ["demo.run"]


@pytest.mark.asyncio
async def test_scoped_approval_rule_fails_closed_without_callback() -> None:
    _, executor, _, plan = _setup(
        read_only=False,
        policy=ExecutionPolicy(
            allow_mutations=True,
            rules=(PolicyRule(operation="demo.run", effect="require_approval"),),
        ),
    )
    executor.bind("demo", lambda endpoint, arguments: {"ok": True})

    with pytest.raises(ApprovalDeniedError, match="requires trusted local approval"):
        await executor.execute(plan)
