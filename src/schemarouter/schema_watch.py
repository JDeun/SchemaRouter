from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal

from .schema_diff import SchemaCompatibility, SchemaRefreshAction, SchemaRefreshResult


SchemaWatchStatus = Literal[
    "idle",
    "unchanged",
    "applied",
    "pending_review",
    "report_only",
    "error",
]


SchemaRefreshCallable = Callable[..., Awaitable[SchemaRefreshResult]]


@dataclass(frozen=True)
class SchemaWatchSnapshot:
    """Public, secret-free state for one watched provider schema."""

    tool_key: str
    interval_seconds: float
    apply_compatible: bool
    status: SchemaWatchStatus
    last_checked_at: datetime | None = None
    last_action: SchemaRefreshAction | None = None
    last_compatibility: SchemaCompatibility | None = None
    last_error_type: str | None = None


@dataclass
class _SchemaWatchRecord:
    tool_key: str
    interval_seconds: float
    apply_compatible: bool
    refresh_timeout_seconds: float
    schema_headers: Mapping[str, str] | None = field(default=None, repr=False)
    trusted_headers: Mapping[str, str] | None = field(default=None, repr=False)
    mcp_client_factory: Any | None = field(default=None, repr=False)
    status: SchemaWatchStatus = "idle"
    last_checked_at: datetime | None = None
    last_checked_monotonic: float | None = None
    last_action: SchemaRefreshAction | None = None
    last_compatibility: SchemaCompatibility | None = None
    last_error_type: str | None = None


class SchemaRefreshWatcher:
    """Periodic, bounded, fail-closed provider-schema refresh coordinator.

    The watcher owns only trusted local refresh configuration. Credentials and client factories are
    deliberately excluded from public snapshots and never copied into ToolSpec metadata.
    """

    def __init__(self, refresher: SchemaRefreshCallable) -> None:
        self._refresher = refresher
        self._records: dict[str, _SchemaWatchRecord] = {}
        self._inflight: set[str] = set()
        self._task: asyncio.Task[None] | None = None
        self._max_concurrency = 4
        self._idle_sleep_seconds = 30.0

    @property
    def running(self) -> bool:
        return self._task is not None and not self._task.done()

    def register(
        self,
        tool_key: str,
        *,
        interval_seconds: float = 300.0,
        apply_compatible: bool = True,
        refresh_timeout_seconds: float = 30.0,
        schema_headers: Mapping[str, str] | None = None,
        trusted_headers: Mapping[str, str] | None = None,
        mcp_client_factory: Any | None = None,
    ) -> None:
        if not isinstance(tool_key, str) or not tool_key.strip():
            raise ValueError("tool_key must be a non-empty string")
        interval = float(interval_seconds)
        timeout = float(refresh_timeout_seconds)
        if interval <= 0:
            raise ValueError("interval_seconds must be > 0")
        if timeout <= 0:
            raise ValueError("refresh_timeout_seconds must be > 0")
        if not isinstance(apply_compatible, bool):
            raise TypeError("apply_compatible must be a boolean")

        self._records[tool_key] = _SchemaWatchRecord(
            tool_key=tool_key,
            interval_seconds=interval,
            apply_compatible=apply_compatible,
            refresh_timeout_seconds=timeout,
            schema_headers=dict(schema_headers) if schema_headers is not None else None,
            trusted_headers=dict(trusted_headers) if trusted_headers is not None else None,
            mcp_client_factory=mcp_client_factory,
        )

    def unregister(self, tool_key: str) -> None:
        self._records.pop(tool_key, None)

    def snapshots(self) -> tuple[SchemaWatchSnapshot, ...]:
        return tuple(
            SchemaWatchSnapshot(
                tool_key=record.tool_key,
                interval_seconds=record.interval_seconds,
                apply_compatible=record.apply_compatible,
                status=record.status,
                last_checked_at=record.last_checked_at,
                last_action=record.last_action,
                last_compatibility=record.last_compatibility,
                last_error_type=record.last_error_type,
            )
            for record in sorted(self._records.values(), key=lambda item: item.tool_key)
        )

    def _due_records(
        self,
        now_monotonic: float,
        *,
        force: bool,
    ) -> tuple[_SchemaWatchRecord, ...]:
        if force:
            return tuple(self._records.values())
        return tuple(
            record
            for record in self._records.values()
            if record.last_checked_monotonic is None
            or now_monotonic - record.last_checked_monotonic >= record.interval_seconds
        )

    async def _refresh_record(
        self,
        record: _SchemaWatchRecord,
        *,
        semaphore: asyncio.Semaphore,
    ) -> None:
        if record.tool_key in self._inflight:
            return

        self._inflight.add(record.tool_key)
        try:
            async with semaphore:
                try:
                    result = await asyncio.wait_for(
                        self._refresher(
                            record.tool_key,
                            apply_compatible=record.apply_compatible,
                            schema_headers=(
                                dict(record.schema_headers)
                                if record.schema_headers is not None
                                else None
                            ),
                            trusted_headers=(
                                dict(record.trusted_headers)
                                if record.trusted_headers is not None
                                else None
                            ),
                            mcp_client_factory=record.mcp_client_factory,
                            timeout=record.refresh_timeout_seconds,
                        ),
                        timeout=record.refresh_timeout_seconds,
                    )
                except asyncio.CancelledError:
                    raise
                except Exception as exc:
                    record.status = "error"
                    record.last_action = None
                    record.last_compatibility = None
                    record.last_error_type = type(exc).__name__
                else:
                    record.status = result.action
                    record.last_action = result.action
                    record.last_compatibility = result.compatibility
                    record.last_error_type = None
                finally:
                    record.last_checked_at = datetime.now(timezone.utc)
                    record.last_checked_monotonic = time.monotonic()
        finally:
            self._inflight.discard(record.tool_key)

    async def run_once(
        self,
        *,
        force: bool = True,
        max_concurrency: int | None = None,
    ) -> tuple[SchemaWatchSnapshot, ...]:
        concurrency = self._max_concurrency if max_concurrency is None else max_concurrency
        if concurrency < 1:
            raise ValueError("max_concurrency must be >= 1")

        due = self._due_records(time.monotonic(), force=force)
        semaphore = asyncio.Semaphore(concurrency)
        await asyncio.gather(
            *(
                self._refresh_record(record, semaphore=semaphore)
                for record in due
            )
        )
        return self.snapshots()

    def _next_delay(self) -> float:
        if not self._records:
            return self._idle_sleep_seconds
        now = time.monotonic()
        delays = []
        for record in self._records.values():
            if record.last_checked_monotonic is None:
                return 0.0
            due_at = record.last_checked_monotonic + record.interval_seconds
            delays.append(max(0.0, due_at - now))
        return min(delays, default=self._idle_sleep_seconds)

    async def _loop(self) -> None:
        try:
            while True:
                await self.run_once(force=False)
                await asyncio.sleep(max(0.01, self._next_delay()))
        except asyncio.CancelledError:
            raise

    async def start(
        self,
        *,
        max_concurrency: int = 4,
        idle_sleep_seconds: float = 30.0,
    ) -> None:
        if self.running:
            raise RuntimeError("schema refresh watcher is already running")
        if max_concurrency < 1:
            raise ValueError("max_concurrency must be >= 1")
        if idle_sleep_seconds <= 0:
            raise ValueError("idle_sleep_seconds must be > 0")

        self._max_concurrency = max_concurrency
        self._idle_sleep_seconds = float(idle_sleep_seconds)
        self._task = asyncio.create_task(
            self._loop(),
            name="schemarouter-schema-refresh-watcher",
        )

    async def stop(self) -> None:
        task = self._task
        self._task = None
        if task is None:
            return
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
