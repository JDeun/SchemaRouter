from __future__ import annotations

import asyncio
from pathlib import Path

import httpx
import pytest

from schemarouter import SchemaRouter, SQLiteRegistry


@pytest.mark.asyncio
async def test_aclose_is_safe_before_start_and_idempotent() -> None:
    router = SchemaRouter()

    await router.aclose()
    await router.aclose()

    assert router.health_monitor.running is False
    assert router.schema_watcher.running is False


@pytest.mark.asyncio
async def test_aclose_stops_all_background_managers() -> None:
    router = SchemaRouter()
    await router.start_health_monitor(interval_seconds=60)
    await router.start_schema_watcher()
    await router.start_native_schema_watcher(interval_seconds=60)

    assert router.health_monitor.running is True
    assert router.schema_watcher.running is True
    assert router._native_schema_watch_task is not None
    assert router._native_schema_watch_task.done() is False

    await router.aclose()

    assert router.health_monitor.running is False
    assert router.schema_watcher.running is False
    assert router._native_schema_watch_task is None

    await router.aclose()
    assert router._native_schema_watch_task is None


@pytest.mark.asyncio
async def test_aclose_handles_partial_startup() -> None:
    router = SchemaRouter()
    await router.start_health_monitor(interval_seconds=60)

    await router.aclose()

    assert router.health_monitor.running is False
    assert router.schema_watcher.running is False


@pytest.mark.asyncio
async def test_async_context_manager_closes_background_tasks() -> None:
    router = SchemaRouter()

    async with router as entered:
        assert entered is router
        await router.start_health_monitor(interval_seconds=60)
        await router.start_schema_watcher()
        await router.start_native_schema_watcher(interval_seconds=60)
        assert router.health_monitor.running is True
        assert router.schema_watcher.running is True
        assert router._native_schema_watch_task is not None

    assert router.health_monitor.running is False
    assert router.schema_watcher.running is False
    assert router._native_schema_watch_task is None


@pytest.mark.asyncio
async def test_context_manager_does_not_suppress_body_exception() -> None:
    router = SchemaRouter()

    with pytest.raises(RuntimeError, match="body failure"):
        async with router:
            await router.start_health_monitor(interval_seconds=60)
            raise RuntimeError("body failure")

    assert router.health_monitor.running is False


@pytest.mark.asyncio
async def test_aclose_attempts_all_components_before_reporting_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    router = SchemaRouter()
    calls: list[str] = []

    async def fail_watch() -> None:
        calls.append("watch")
        raise ValueError("watch shutdown failed")

    async def stop_health() -> None:
        calls.append("health")

    monkeypatch.setattr(router.schema_watcher, "stop", fail_watch)
    monkeypatch.setattr(router.health_monitor, "stop", stop_health)

    with pytest.raises(RuntimeError, match="shutdown encountered an error"):
        await router.aclose()

    assert set(calls) == {"watch", "health"}


@pytest.mark.asyncio
async def test_aclose_propagates_cancellation_after_attempting_all_components(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    router = SchemaRouter()
    calls: list[str] = []

    async def cancel_watch() -> None:
        calls.append("watch")
        raise asyncio.CancelledError

    async def stop_health() -> None:
        calls.append("health")

    monkeypatch.setattr(router.schema_watcher, "stop", cancel_watch)
    monkeypatch.setattr(router.health_monitor, "stop", stop_health)

    with pytest.raises(asyncio.CancelledError):
        await router.aclose()

    assert set(calls) == {"watch", "health"}


@pytest.mark.asyncio
async def test_aclose_prioritizes_cancellation_over_other_shutdown_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    router = SchemaRouter()
    calls: list[str] = []

    async def fail_watch() -> None:
        calls.append("watch")
        raise ValueError("watch shutdown failed")

    async def cancel_health() -> None:
        calls.append("health")
        raise asyncio.CancelledError

    monkeypatch.setattr(router.schema_watcher, "stop", fail_watch)
    monkeypatch.setattr(router.health_monitor, "stop", cancel_health)

    with pytest.raises(asyncio.CancelledError):
        await router.aclose()

    assert set(calls) == {"watch", "health"}


@pytest.mark.asyncio
async def test_aclose_does_not_close_injected_http_client() -> None:
    async with httpx.AsyncClient() as client:
        router = SchemaRouter(http_client=client)

        await router.aclose()

        assert client.is_closed is False


@pytest.mark.asyncio
async def test_aclose_does_not_close_injected_sqlite_registry(
    tmp_path: Path,
) -> None:
    registry = SQLiteRegistry(tmp_path / "registry.sqlite3")
    try:
        router = SchemaRouter(registry=registry)

        await router.aclose()

        assert registry.keys() == ()
    finally:
        registry.close()
