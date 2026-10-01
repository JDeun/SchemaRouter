from __future__ import annotations

import asyncio

import pytest

from schemarouter.schema_diff import SchemaDiffReport, SchemaRefreshResult
from schemarouter.schema_watch import SchemaRefreshWatcher


def _result(
    *,
    action: str = "unchanged",
    compatibility: str = "identical",
    applied: bool = False,
) -> SchemaRefreshResult:
    return SchemaRefreshResult(
        tool_key="tool",
        action=action,
        applied=applied,
        report=SchemaDiffReport(
            compatibility=compatibility,
            old_fingerprint="old",
            new_fingerprint="new",
            changes=[],
        ),
    )


@pytest.mark.asyncio
async def test_schema_watcher_passes_trusted_config_without_exposing_secrets() -> None:
    calls: list[dict] = []

    async def refresher(tool_key: str, **kwargs):
        calls.append({"tool_key": tool_key, **kwargs})
        return _result()

    watcher = SchemaRefreshWatcher(refresher)
    watcher.register(
        "tool",
        interval_seconds=60,
        schema_headers={"X-Schema-Key": "schema-secret"},
        trusted_headers={"Authorization": "Bearer runtime-secret"},
    )

    snapshots = await watcher.run_once()

    assert calls[0]["tool_key"] == "tool"
    assert calls[0]["schema_headers"] == {"X-Schema-Key": "schema-secret"}
    assert calls[0]["trusted_headers"] == {
        "Authorization": "Bearer runtime-secret"
    }
    assert snapshots[0].status == "unchanged"
    rendered = repr(snapshots)
    assert "schema-secret" not in rendered
    assert "runtime-secret" not in rendered


@pytest.mark.asyncio
async def test_schema_watcher_respects_per_tool_interval_when_not_forced() -> None:
    calls = 0

    async def refresher(tool_key: str, **kwargs):
        nonlocal calls
        del tool_key, kwargs
        calls += 1
        return _result()

    watcher = SchemaRefreshWatcher(refresher)
    watcher.register("tool", interval_seconds=3600)

    await watcher.run_once(force=False)
    await watcher.run_once(force=False)

    assert calls == 1


@pytest.mark.asyncio
async def test_schema_watcher_surfaces_pending_review_without_applying() -> None:
    async def refresher(tool_key: str, **kwargs):
        del tool_key, kwargs
        return _result(
            action="pending_review",
            compatibility="breaking",
            applied=False,
        )

    watcher = SchemaRefreshWatcher(refresher)
    watcher.register("tool", apply_compatible=True)

    snapshots = await watcher.run_once()

    assert snapshots[0].status == "pending_review"
    assert snapshots[0].last_action == "pending_review"
    assert snapshots[0].last_compatibility == "breaking"
    assert snapshots[0].last_error_type is None


@pytest.mark.asyncio
async def test_schema_watcher_records_refresh_errors_without_crashing_loop() -> None:
    async def refresher(tool_key: str, **kwargs):
        del tool_key, kwargs
        raise RuntimeError("provider unavailable")

    watcher = SchemaRefreshWatcher(refresher)
    watcher.register("tool")

    snapshots = await watcher.run_once()

    assert snapshots[0].status == "error"
    assert snapshots[0].last_error_type == "RuntimeError"


@pytest.mark.asyncio
async def test_schema_watcher_total_timeout_is_bounded() -> None:
    async def refresher(tool_key: str, **kwargs):
        del tool_key, kwargs
        await asyncio.sleep(1)
        return _result()

    watcher = SchemaRefreshWatcher(refresher)
    watcher.register(
        "tool",
        refresh_timeout_seconds=0.01,
    )

    snapshots = await watcher.run_once()

    assert snapshots[0].status == "error"
    assert snapshots[0].last_error_type == "TimeoutError"


@pytest.mark.asyncio
async def test_schema_watcher_start_stop_lifecycle() -> None:
    seen = asyncio.Event()

    async def refresher(tool_key: str, **kwargs):
        del tool_key, kwargs
        seen.set()
        return _result()

    watcher = SchemaRefreshWatcher(refresher)
    watcher.register("tool", interval_seconds=60)

    await watcher.start(
        max_concurrency=1,
        idle_sleep_seconds=0.01,
    )
    try:
        await asyncio.wait_for(seen.wait(), timeout=1)
        assert watcher.running
    finally:
        await watcher.stop()

    assert watcher.running is False


def test_schema_watcher_rejects_invalid_configuration() -> None:
    watcher = SchemaRefreshWatcher(lambda *args, **kwargs: None)  # type: ignore[arg-type]

    with pytest.raises(ValueError, match="interval_seconds"):
        watcher.register("tool", interval_seconds=0)
    with pytest.raises(ValueError, match="refresh_timeout_seconds"):
        watcher.register("tool", refresh_timeout_seconds=0)
    with pytest.raises(ValueError, match="tool_key"):
        watcher.register("")
