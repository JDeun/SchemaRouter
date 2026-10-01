import asyncio

import pytest

from schemarouter import (
    AccessHealthMonitor,
    EndpointSpec,
    FieldSpec,
    PlanRequest,
    PlanValidationError,
    RegistrationError,
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



@pytest.mark.asyncio
async def test_all_unavailable_paths_reenter_planning_after_cooldown() -> None:
    router = SchemaRouter(unavailable_cooldown_seconds=0.01)
    for name, provider, access_mode in (
        ("provider_a_rest", "provider_a", "openapi"),
        ("provider_b_optimade", "provider_b", "optimade"),
    ):
        router.add_tool(
            ToolSpec(
                name=name,
                provider=provider,
                access_mode=access_mode,
                endpoints=[
                    EndpointSpec(
                        name="search",
                        read_only=True,
                        output_fields=[
                            FieldSpec(
                                name="elastic_modulus",
                                semantic_id="elastic_modulus",
                                aliases=["탄성계수", "elastic modulus"],
                            )
                        ],
                    )
                ],
            )
        )
        router.mark_access_unavailable(name, "search")

    request = PlanRequest(
        query="탄성계수를 알려줘",
        fallback_scope="cross_provider",
    )

    blocked = router.plan(request)
    assert blocked.calls == []
    assert set(router.unavailable_access_paths()) == {
        ("provider_a_rest", "search"),
        ("provider_b_optimade", "search"),
    }

    await asyncio.sleep(0.02)

    recovered = router.plan(request)
    assert recovered.calls
    assert recovered.calls[0].fields == ["elastic_modulus"]
    assert router.unavailable_access_paths() == ()


@pytest.mark.asyncio
async def test_background_probe_reintroduces_route_into_planner_before_cooldown_expiry() -> None:
    router = SchemaRouter(unavailable_cooldown_seconds=60)
    router.add_tool(
        ToolSpec(
            name="provider_a_rest",
            provider="provider_a",
            access_mode="openapi",
            endpoints=[
                EndpointSpec(
                    name="search",
                    read_only=True,
                    output_fields=[
                        FieldSpec(
                            name="elastic_modulus",
                            semantic_id="elastic_modulus",
                            aliases=["탄성계수", "elastic modulus"],
                        )
                    ],
                )
            ],
        )
    )
    router.mark_access_unavailable("provider_a_rest", "search")

    recovered = asyncio.Event()
    probe_calls = 0

    async def probe() -> bool:
        nonlocal probe_calls
        probe_calls += 1
        if probe_calls >= 2:
            recovered.set()
            return True
        return False

    router.register_health_probe("provider_a_rest", "search", probe)
    await router.start_health_monitor(
        interval_seconds=0.01,
        probe_timeout_seconds=0.1,
        max_concurrency=1,
    )
    try:
        await asyncio.wait_for(recovered.wait(), timeout=1)
        for _ in range(20):
            plan = router.plan(
                PlanRequest(
                    query="탄성계수",
                    fallback_scope="cross_provider",
                )
            )
            if plan.calls:
                break
            await asyncio.sleep(0.01)
    finally:
        await router.stop_health_monitor()

    assert probe_calls >= 2
    assert plan.calls[0].tool == "provider_a_rest"
    assert plan.calls[0].fields == ["elastic_modulus"]
    assert router.unavailable_access_paths() == ()



@pytest.mark.asyncio
async def test_trusted_amendment_restamps_existing_health_probe() -> None:
    router = _router()
    calls = 0

    def probe() -> bool:
        nonlocal calls
        calls += 1
        return True

    router.register_health_probe("provider_api", "read", probe)
    current = router.registry.get("provider_api")
    amended = current.model_copy(deep=True)
    amended.endpoints[0].description = "trusted annotation"

    router.amend_capability(current.key, amended)

    before = router.health_snapshots()[0]
    assert before.status == "unknown"
    assert before.last_error_type is None

    after = await router.check_health_once()
    assert after[0].status == "healthy"
    assert calls == 1


@pytest.mark.asyncio
async def test_background_probe_from_old_generation_is_discarded_after_restamp() -> None:
    router = _router(cooldown=60)
    calls = 0
    first_started = asyncio.Event()
    second_started = asyncio.Event()
    release_first = asyncio.Event()
    release_second = asyncio.Event()

    async def probe() -> bool:
        nonlocal calls
        calls += 1
        if calls == 1:
            first_started.set()
            await release_first.wait()
            return False
        second_started.set()
        await release_second.wait()
        return True

    router.register_health_probe("provider_api", "read", probe)
    await router.start_health_monitor(
        interval_seconds=0.01,
        probe_timeout_seconds=1,
        max_concurrency=1,
    )
    try:
        await asyncio.wait_for(first_started.wait(), timeout=1)
        current = router.registry.get("provider_api")
        updated = current.model_copy(deep=True)
        updated.description = "accepted compatible transition"
        router.registry.register(updated, replace=True)
        router.health_monitor.transition_tool_contract(
            current.key,
            expected_old_fingerprint=current.fingerprint,
            expected_new_fingerprint=updated.fingerprint,
        )

        release_first.set()
        await asyncio.wait_for(second_started.wait(), timeout=1)

        assert router.unavailable_access_paths() == ()
        assert router.health_snapshots()[0].status == "unknown"

        release_second.set()
        for _ in range(50):
            if router.health_snapshots()[0].status == "healthy":
                break
            await asyncio.sleep(0.01)
    finally:
        release_first.set()
        release_second.set()
        await router.stop_health_monitor()

    assert router.health_snapshots()[0].status == "healthy"


@pytest.mark.parametrize(
    ("replacement", "reason"),
    [
        (
            ToolSpec(
                name="provider_api",
                provider="provider",
                access_mode="openapi",
                endpoints=[EndpointSpec(name="renamed", read_only=True)],
            ),
            "EndpointRemoved",
        ),
        (
            ToolSpec(
                name="provider_api",
                provider="provider",
                access_mode="openapi",
                endpoints=[EndpointSpec(name="read", read_only=False)],
            ),
            "EndpointNoLongerReadOnly",
        ),
    ],
)
@pytest.mark.asyncio
async def test_accepted_transition_invalidates_incompatible_probe_target(
    replacement: ToolSpec,
    reason: str,
) -> None:
    router = _router()
    router.register_health_probe("provider_api", "read", lambda: True)
    current = router.registry.get("provider_api")
    router.registry.register(replacement, replace=True)

    router.health_monitor.transition_tool_contract(
        current.key,
        expected_old_fingerprint=current.fingerprint,
        expected_new_fingerprint=replacement.fingerprint,
    )
    snapshots = await router.check_health_once()

    assert snapshots[0].status == "stale"
    assert snapshots[0].last_error_type == reason


@pytest.mark.asyncio
async def test_probe_restamp_fails_closed_after_concurrent_registry_change() -> None:
    router = _router()
    router.register_health_probe("provider_api", "read", lambda: True)
    current = router.registry.get("provider_api")

    intended = current.model_copy(deep=True)
    intended.description = "intended transition"
    concurrent = current.model_copy(deep=True)
    concurrent.description = "concurrent transition"
    router.registry.register(concurrent, replace=True)

    with pytest.raises(RegistrationError, match="changed before health probes"):
        router.health_monitor.transition_tool_contract(
            current.key,
            expected_old_fingerprint=current.fingerprint,
            expected_new_fingerprint=intended.fingerprint,
        )

    snapshots = await router.check_health_once()
    assert snapshots[0].status == "stale"
    assert snapshots[0].last_error_type == "ToolContractChanged"
