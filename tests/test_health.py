import asyncio

import pytest

from schemarouter import (
    AccessHealthMonitor,
    EndpointSpec,
    PlanValidationError,
    SchemaRouter,
    ToolSpec,
)


def _router(*, cooldown: float = 30.0) -> SchemaRouter:
    router = SchemaRouter(unavailable_cooldown_seconds=cooldown)
    router.add_tool(
        ToolSpec(
            name="provider_api",
            provider="provider",
            access_mode="openapi",
            endpoints=[EndpointSpec(name="read", read_only=True)],
        )
    )
    return router


def test_health_probe_registration_requires_explicit_read_only() -> None:
    router = SchemaRouter()
    router.add_tool(
        ToolSpec(
            name="writer",
            endpoints=[EndpointSpec(name="write", read_only=False)],
        )
    )

    with pytest.raises(PlanValidationError, match="explicitly read-only"):
        router.register_health_probe("writer", "write", lambda: True)


@pytest.mark.asyncio
async def test_health_probe_failure_marks_unavailable_and_success_reopens() -> None:
    router = _router(cooldown=60)
    healthy = False

    def probe() -> bool:
        return healthy

    router.register_health_probe("provider_api", "read", probe)

    first = await router.check_health_once()
    assert first[0].status == "unhealthy"
    assert router.unavailable_access_paths() == (("provider_api", "read"),)

    healthy = True
    second = await router.check_health_once()
    assert second[0].status == "healthy"
    assert router.unavailable_access_paths() == ()


@pytest.mark.asyncio
async def test_health_probe_exception_never_escapes_monitor_cycle() -> None:
    router = _router(cooldown=60)

    async def probe() -> bool:
        raise ConnectionError("health endpoint down")

    router.register_health_probe("provider_api", "read", probe)
    snapshots = await router.check_health_once()

    assert snapshots[0].status == "unhealthy"
    assert snapshots[0].last_error_type == "ConnectionError"
    assert router.unavailable_access_paths() == (("provider_api", "read"),)


@pytest.mark.asyncio
async def test_cooldown_expires_without_active_monitor() -> None:
    router = _router(cooldown=0.01)
    router.mark_access_unavailable("provider_api", "read")

    assert router.unavailable_access_paths() == (("provider_api", "read"),)
    await asyncio.sleep(0.02)
    assert router.unavailable_access_paths() == ()


@pytest.mark.asyncio
async def test_background_monitor_reopens_path_after_probe_recovers() -> None:
    router = _router(cooldown=60)
    calls = 0
    recovered = asyncio.Event()

    async def probe() -> bool:
        nonlocal calls
        calls += 1
        if calls >= 2:
            recovered.set()
            return True
        return False

    router.register_health_probe("provider_api", "read", probe)
    await router.start_health_monitor(
        interval_seconds=0.01,
        probe_timeout_seconds=0.1,
        max_concurrency=1,
    )
    try:
        await asyncio.wait_for(recovered.wait(), timeout=1)
        for _ in range(20):
            if not router.unavailable_access_paths():
                break
            await asyncio.sleep(0.01)
    finally:
        await router.stop_health_monitor()

    assert calls >= 2
    assert router.unavailable_access_paths() == ()
    assert router.health_snapshots()[0].status == "healthy"
    assert router.health_monitor.running is False


@pytest.mark.asyncio
async def test_health_monitor_rejects_double_start() -> None:
    router = _router()
    router.register_health_probe("provider_api", "read", lambda: True)

    await router.start_health_monitor(interval_seconds=1)
    try:
        with pytest.raises(RuntimeError, match="already running"):
            await router.start_health_monitor(interval_seconds=1)
    finally:
        await router.stop_health_monitor()


def test_health_monitor_can_be_used_directly_with_executor() -> None:
    router = _router()
    monitor = AccessHealthMonitor(router.executor)

    monitor.register("provider_api", "read", lambda: True)

    assert monitor.snapshots()[0].status == "unknown"



def test_cooldown_does_not_leak_across_tool_contract_replacement() -> None:
    router = _router(cooldown=60)
    router.mark_access_unavailable("provider_api", "read")
    assert router.unavailable_access_paths() == (("provider_api", "read"),)

    replacement = ToolSpec(
        name="provider_api",
        provider="provider",
        access_mode="new_transport",
        endpoints=[EndpointSpec(name="read", read_only=True)],
    )
    router.registry.register(replacement, replace=True)

    assert router.unavailable_access_paths() == ()
    assert router.executor.is_access_available("provider_api", "read") is True


@pytest.mark.asyncio
async def test_health_probe_becomes_stale_after_tool_contract_replacement() -> None:
    router = _router(cooldown=60)
    called = False

    def probe() -> bool:
        nonlocal called
        called = True
        return True

    router.register_health_probe("provider_api", "read", probe)
    replacement = ToolSpec(
        name="provider_api",
        provider="provider",
        access_mode="new_transport",
        endpoints=[EndpointSpec(name="read", read_only=True)],
    )
    router.registry.register(replacement, replace=True)

    snapshots = await router.check_health_once()

    assert called is False
    assert snapshots[0].status == "stale"
    assert snapshots[0].last_error_type == "ToolContractChanged"



@pytest.mark.asyncio
async def test_health_probe_result_is_discarded_if_contract_changes_while_awaiting() -> None:
    router = _router(cooldown=60)
    started = asyncio.Event()
    release = asyncio.Event()

    async def probe() -> bool:
        started.set()
        await release.wait()
        return False

    router.register_health_probe("provider_api", "read", probe)
    task = asyncio.create_task(router.check_health_once())
    await asyncio.wait_for(started.wait(), timeout=1)

    replacement = ToolSpec(
        name="provider_api",
        provider="provider",
        access_mode="new_transport",
        endpoints=[EndpointSpec(name="read", read_only=True)],
    )
    router.registry.register(replacement, replace=True)
    release.set()

    snapshots = await asyncio.wait_for(task, timeout=1)

    assert snapshots[0].status == "stale"
    assert snapshots[0].last_error_type == "ToolContractChanged"
    assert router.unavailable_access_paths() == ()
