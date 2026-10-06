from __future__ import annotations

import asyncio

import pytest

from schemarouter import EndpointSpec, SchemaRouter, ToolSpec
from schemarouter.inspection import inspect_router


def _tool(name: str, *, endpoint: str = "read") -> ToolSpec:
    return ToolSpec(
        name=name,
        provider="test",
        access_mode="python",
        endpoints=[EndpointSpec(name=endpoint, read_only=True)],
    )


def _bind(router: SchemaRouter, tool: ToolSpec) -> None:
    router.add_bound_tool(
        tool,
        lambda endpoint, arguments: {"endpoint": endpoint, **arguments},
    )


@pytest.mark.asyncio
async def test_native_schema_watcher_isolates_one_unexpected_source_failure() -> None:
    router = SchemaRouter()
    bad = _tool("bad_source")
    good = _tool("good_source")
    _bind(router, bad)
    _bind(router, good)

    bad_calls = 0
    good_calls = 0
    good_retried = asyncio.Event()

    async def bad_refresh():
        nonlocal bad_calls
        bad_calls += 1
        raise RuntimeError("credential=must-not-leak")

    async def good_refresh():
        nonlocal good_calls
        good_calls += 1
        if good_calls >= 2:
            good_retried.set()
        return good, (lambda endpoint, arguments: {}), False

    router._remember_native_schema_refresh(bad.key, bad_refresh)
    router._remember_native_schema_refresh(good.key, good_refresh)

    await router.start_native_schema_watcher(interval_seconds=0.01)
    try:
        await asyncio.wait_for(good_retried.wait(), timeout=1)
        assert router.native_schema_watcher_running is True
    finally:
        await router.stop_native_schema_watcher()

    assert bad_calls >= 2
    assert good_calls >= 2

    snapshots = {item.tool: item for item in router.native_schema_watch_snapshots()}
    assert snapshots[bad.key].status == "error"
    assert snapshots[bad.key].last_error_type == "RuntimeError"
    assert snapshots[bad.key].failure_count >= 2
    assert snapshots[bad.key].consecutive_failures >= 2
    assert "credential=must-not-leak" not in repr(snapshots[bad.key])

    assert snapshots[good.key].status == "unchanged"
    assert snapshots[good.key].last_error_type is None
    assert snapshots[good.key].consecutive_failures == 0
    assert snapshots[good.key].last_success_at is not None


@pytest.mark.asyncio
async def test_native_schema_watcher_preserves_cancellation_during_refresh() -> None:
    router = SchemaRouter()
    tool = _tool("blocking_source")
    _bind(router, tool)

    started = asyncio.Event()
    cancelled = asyncio.Event()

    async def blocking_refresh():
        started.set()
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            cancelled.set()
            raise

    router._remember_native_schema_refresh(tool.key, blocking_refresh)

    await router.start_native_schema_watcher(interval_seconds=60)
    await asyncio.wait_for(started.wait(), timeout=1)
    await asyncio.wait_for(router.stop_native_schema_watcher(), timeout=0.5)

    assert cancelled.is_set()
    assert router.native_schema_watcher_running is False
    snapshot = router.native_schema_watch_snapshots()[0]
    assert snapshot.status == "idle"
    assert snapshot.failure_count == 0


@pytest.mark.asyncio
async def test_native_schema_watch_marks_pending_review_as_result_not_failure() -> None:
    router = SchemaRouter()
    current = _tool("changing_source", endpoint="read")
    candidate = _tool("changing_source", endpoint="renamed")
    _bind(router, current)

    async def incompatible_refresh():
        return candidate, (lambda endpoint, arguments: {}), False

    router._remember_native_schema_refresh(current.key, incompatible_refresh)

    results = await router.check_native_schema_watches_once()

    assert len(results) == 1
    assert results[0].action == "pending_review"
    snapshot = router.native_schema_watch_snapshots()[0]
    assert snapshot.status == "pending_review"
    assert snapshot.last_action == "pending_review"
    assert snapshot.last_error_type is None
    assert snapshot.failure_count == 0
    assert snapshot.consecutive_failures == 0


@pytest.mark.asyncio
async def test_native_schema_watch_health_is_bounded_to_active_refreshers_and_inspected() -> None:
    router = SchemaRouter()
    tool = _tool("observable_source")
    _bind(router, tool)

    async def refresh():
        return tool, (lambda endpoint, arguments: {}), False

    router._remember_native_schema_refresh(tool.key, refresh)
    await router.check_native_schema_watches_once()

    inspected = inspect_router(router)
    assert inspected.execution.native_schema_watcher_running is False
    assert len(inspected.execution.native_schema_watches) == 1
    observed = inspected.execution.native_schema_watches[0]
    assert observed.tool == tool.key
    assert observed.status == "unchanged"
    assert observed.last_error_type is None

    await router.aremove_tool(tool.key)

    assert router.native_schema_watch_snapshots() == ()
    assert inspect_router(router).execution.native_schema_watches == []


@pytest.mark.asyncio
async def test_native_schema_watcher_does_not_hot_loop_persistent_failure() -> None:
    router = SchemaRouter()
    tool = _tool("persistent_failure")
    _bind(router, tool)

    calls = 0
    first_failure = asyncio.Event()

    async def failing_refresh():
        nonlocal calls
        calls += 1
        first_failure.set()
        raise ValueError("persistent failure")

    router._remember_native_schema_refresh(tool.key, failing_refresh)

    await router.start_native_schema_watcher(interval_seconds=0.2)
    try:
        await asyncio.wait_for(first_failure.wait(), timeout=1)
        await asyncio.sleep(0.03)
        assert calls == 1
    finally:
        await router.stop_native_schema_watcher()



@pytest.mark.asyncio
async def test_native_schema_watch_late_completion_does_not_recreate_removed_state() -> None:
    router = SchemaRouter()
    tool = _tool("removed_while_refreshing")
    _bind(router, tool)

    started = asyncio.Event()
    release = asyncio.Event()

    async def delayed_refresh():
        started.set()
        await release.wait()
        return tool, (lambda endpoint, arguments: {}), False

    router._remember_native_schema_refresh(tool.key, delayed_refresh)

    checking = asyncio.create_task(router.check_native_schema_watches_once())
    await asyncio.wait_for(started.wait(), timeout=1)

    await router.aremove_tool(tool.key)
    assert router.native_schema_watch_snapshots() == ()

    release.set()
    results = await asyncio.wait_for(checking, timeout=1)

    assert len(results) == 1
    assert results[0].action == "unchanged"
    assert router.native_schema_watch_snapshots() == ()
