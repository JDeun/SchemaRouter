import asyncio
import contextvars
import threading

import pytest

from schemarouter import (
    AccessHealthMonitor,
    EndpointSpec,
    ExecutionBudget,
    ExecutionBudgetExceededError,
    InMemoryRegistry,
    InvocationUnavailableError,
    NonRetryableInvocationError,
    RegistryExecutor,
    RetryPolicy,
    SchemaRouter,
    ToolCall,
    ToolSpec,
)


def _read_call(tool: ToolSpec) -> ToolCall:
    return ToolCall(
        tool=tool.key,
        endpoint="read",
        arguments={},
        schema_fingerprint=tool.endpoint("read").fingerprint,
        tool_fingerprint=tool.fingerprint,
    )


@pytest.mark.asyncio
async def test_bounded_sync_offload_preserves_contextvars() -> None:
    registry = InMemoryRegistry()
    executor = RegistryExecutor(registry, max_offloaded_sync_workers=1)
    marker: contextvars.ContextVar[str] = contextvars.ContextVar("marker")
    token = marker.set("scoped")

    try:
        future = executor._submit_offloaded_sync(marker.get)
        assert await future == "scoped"
    finally:
        marker.reset(token)
        executor.shutdown_offloaded_sync()


@pytest.mark.asyncio
async def test_read_only_timeout_cannot_grow_offloaded_worker_pressure_unbounded() -> None:
    registry = InMemoryRegistry()
    tool = ToolSpec(
        name="bounded_reader",
        endpoints=[EndpointSpec(name="read", read_only=True)],
    )
    registry.register(tool)

    started = threading.Event()
    release = threading.Event()
    finished = threading.Event()
    attempts = 0

    def invoker(endpoint: str, arguments: dict[str, object]) -> dict[str, bool]:
        nonlocal attempts
        del endpoint, arguments
        attempts += 1
        started.set()
        release.wait()
        finished.set()
        return {"ok": True}

    executor = RegistryExecutor(registry, max_offloaded_sync_workers=1)
    executor.bind(
        tool.key,
        invoker,
        expected_fingerprint=tool.fingerprint,
        offload_sync=True,
    )
    call = _read_call(tool)

    try:
        with pytest.raises(ExecutionBudgetExceededError, match="during invocation"):
            await executor.execute_call(
                call,
                retry=RetryPolicy(max_attempts=1),
                budget=ExecutionBudget(max_elapsed_seconds=0.02),
            )

        assert started.is_set()
        assert attempts == 1
        assert executor._sync_offload_pool.in_flight == 1

        with pytest.raises(InvocationUnavailableError, match="capacity is exhausted"):
            await executor.execute_call(
                call,
                retry=RetryPolicy(max_attempts=1),
            )

        assert attempts == 1
        assert executor.is_access_available(tool.key, "read") is True
    finally:
        release.set()

    assert await asyncio.to_thread(finished.wait, 0.5)
    for _ in range(50):
        if executor._sync_offload_pool.in_flight == 0:
            break
        await asyncio.sleep(0.01)

    try:
        result = await executor.execute_call(
            call,
            retry=RetryPolicy(max_attempts=1),
        )
        assert result.data == {"ok": True}
        assert attempts == 2
    finally:
        executor.shutdown_offloaded_sync()


@pytest.mark.asyncio
async def test_sync_health_probe_timeouts_share_the_same_bounded_pool() -> None:
    registry = InMemoryRegistry()
    tool = ToolSpec(
        name="health_reader",
        endpoints=[EndpointSpec(name="read", read_only=True)],
    )
    registry.register(tool)
    executor = RegistryExecutor(registry, max_offloaded_sync_workers=1)
    monitor = AccessHealthMonitor(executor)

    started = threading.Event()
    release = threading.Event()
    calls = 0

    def probe() -> bool:
        nonlocal calls
        calls += 1
        started.set()
        release.wait()
        return True

    monitor.register(tool.key, "read", probe)

    try:
        first = await monitor.run_once(
            probe_timeout_seconds=0.02,
            max_concurrency=1,
        )
        assert first[0].status == "unhealthy"
        assert first[0].last_error_type == "TimeoutError"
        assert started.is_set()
        assert calls == 1
        assert executor._sync_offload_pool.in_flight == 1

        second = await monitor.run_once(
            probe_timeout_seconds=0.02,
            max_concurrency=1,
        )
        assert second[0].status == "unhealthy"
        assert calls == 1
        assert executor._sync_offload_pool.in_flight == 1
    finally:
        release.set()
        executor.shutdown_offloaded_sync()


@pytest.mark.asyncio
async def test_router_aclose_closes_router_owned_sync_offload_pool() -> None:
    router = SchemaRouter()
    await router.aclose()

    with pytest.raises(NonRetryableInvocationError, match="worker pool is closed"):
        router.executor._submit_offloaded_sync(lambda: True)
