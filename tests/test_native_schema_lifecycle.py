from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from schemarouter.errors import SchemaSourceError
from schemarouter.native_schema_lifecycle import NativeSchemaLifecycleManager
from schemarouter.registry import InMemoryRegistry


ROOT = Path(__file__).resolve().parents[1]


async def _unexpected_apply(**kwargs: Any) -> None:
    raise AssertionError(f"apply callback should not run: {kwargs!r}")


@pytest.mark.asyncio
async def test_native_schema_lifecycle_isolates_failures_and_forgets_state() -> None:
    manager = NativeSchemaLifecycleManager(
        InMemoryRegistry(),
        _unexpected_apply,
    )

    async def refresh_missing() -> Any:
        raise AssertionError("refresh binding should not run for a missing tool")

    manager.remember("missing", refresh_missing)

    assert await manager.check_once() == ()
    assert manager.snapshots() == (
        manager.snapshots()[0],
    )
    snapshot = manager.snapshots()[0]
    assert snapshot.tool_key == "missing"
    assert snapshot.consecutive_failures == 1
    assert snapshot.error_kind == "registration_error"

    manager.forget("missing")
    assert manager.snapshots() == ()
    with pytest.raises(SchemaSourceError, match="no process-local native schema"):
        await manager.refresh("missing")


@pytest.mark.asyncio
async def test_native_schema_lifecycle_owns_watcher_task() -> None:
    manager = NativeSchemaLifecycleManager(
        InMemoryRegistry(),
        _unexpected_apply,
    )

    await manager.start(interval_seconds=3600.0)
    with pytest.raises(RuntimeError, match="already running"):
        await manager.start(interval_seconds=3600.0)
    await manager.stop()
    await manager.stop()


def test_runtime_delegates_native_schema_state_to_lifecycle_manager() -> None:
    runtime = (ROOT / "src" / "schemarouter" / "runtime.py").read_text(
        encoding="utf-8"
    )

    for legacy_state in (
        "self._native_schema_refreshers",
        "self._native_schema_pending",
        "self._native_schema_watch_task",
        "self._native_schema_watch_failures",
    ):
        assert legacy_state not in runtime

    assert "NativeSchemaLifecycleManager(" in runtime
