from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Protocol

from .errors import RegistrationError, SchemaSourceError
from .executor import BoundEndpointInvoker
from .models import ToolSpec
from .registry import ToolRegistry
from .schema_diff import SchemaRefreshResult, compare_tool_specs

NativeSchemaRefreshBinding = Callable[
    [],
    Awaitable[tuple[ToolSpec, BoundEndpointInvoker, bool]],
]


class NativeSchemaApplyBinding(Protocol):
    async def __call__(
        self,
        *,
        current: ToolSpec,
        candidate_tool: ToolSpec,
        candidate_invoker: BoundEndpointInvoker,
        offload_sync: bool,
        expected_version: int,
    ) -> None: ...


@dataclass(frozen=True, slots=True)
class NativeSchemaWatchSnapshot:
    """Privacy-safe health state for one native schema refresh source."""

    tool_key: str
    consecutive_failures: int
    error_kind: str


class NativeSchemaLifecycleManager:
    """Own process-local native schema refresh state and watcher lifecycle."""

    def __init__(
        self,
        registry: ToolRegistry,
        apply_binding: NativeSchemaApplyBinding,
    ) -> None:
        self._registry = registry
        self._apply_binding = apply_binding
        self._refreshers: dict[str, NativeSchemaRefreshBinding] = {}
        self._pending: dict[
            str,
            tuple[ToolSpec, BoundEndpointInvoker, bool],
        ] = {}
        self._watch_failures: dict[str, tuple[int, str]] = {}
        self._watch_task: asyncio.Task[None] | None = None

    def remember(
        self,
        tool_key: str,
        refresh: NativeSchemaRefreshBinding,
    ) -> None:
        self._refreshers[tool_key] = refresh
        self._watch_failures.pop(tool_key, None)

    def forget(self, tool_key: str) -> None:
        self._refreshers.pop(tool_key, None)
        self._pending.pop(tool_key, None)
        self._watch_failures.pop(tool_key, None)

    def _record_failure(self, tool_key: str, exc: Exception) -> None:
        previous_count = self._watch_failures.get(tool_key, (0, ""))[0]
        if isinstance(exc, KeyError):
            error_kind = "missing_tool"
        elif isinstance(exc, RegistrationError):
            error_kind = "registration_error"
        elif isinstance(exc, SchemaSourceError):
            error_kind = "schema_source_error"
        else:
            error_kind = "unexpected_error"
        self._watch_failures[tool_key] = (
            min(previous_count + 1, 2_147_483_647),
            error_kind,
        )

    def snapshots(self) -> tuple[NativeSchemaWatchSnapshot, ...]:
        """Return bounded watcher degradation state without exception messages."""

        return tuple(
            NativeSchemaWatchSnapshot(
                tool_key=tool_key,
                consecutive_failures=count,
                error_kind=error_kind,
            )
            for tool_key, (count, error_kind) in sorted(self._watch_failures.items())
        )

    async def refresh(
        self,
        tool_key: str,
        *,
        apply_compatible: bool = True,
    ) -> SchemaRefreshResult:
        """Re-introspect one caller-owned native source."""

        refresh = self._refreshers.get(tool_key)
        if refresh is None:
            raise SchemaSourceError(
                f"tool {tool_key!r} has no process-local native schema refresh binding"
            )
        expected_version = self._registry.version
        try:
            current = self._registry.get(tool_key)
        except KeyError as exc:
            raise RegistrationError(f"unknown tool: {tool_key}") from exc

        candidate_tool, candidate_invoker, offload_sync = await refresh()
        if candidate_tool.key != tool_key:
            raise SchemaSourceError(
                "native schema refresh changed the registered tool key unexpectedly"
            )

        report = compare_tool_specs(current, candidate_tool)
        if report.compatibility == "identical":
            self._pending.pop(tool_key, None)
            return SchemaRefreshResult(
                tool_key=tool_key,
                action="unchanged",
                applied=False,
                report=report,
            )

        if report.compatibility == "compatible" and apply_compatible:
            await self._apply_binding(
                current=current,
                candidate_tool=candidate_tool,
                candidate_invoker=candidate_invoker,
                offload_sync=offload_sync,
                expected_version=expected_version,
            )
            self._pending.pop(tool_key, None)
            return SchemaRefreshResult(
                tool_key=tool_key,
                action="applied",
                applied=True,
                report=report,
            )

        action = (
            "report_only"
            if report.compatibility == "compatible"
            else "pending_review"
        )
        if action == "pending_review":
            self._pending[tool_key] = (
                candidate_tool,
                candidate_invoker,
                offload_sync,
            )
        return SchemaRefreshResult(
            tool_key=tool_key,
            action=action,
            applied=False,
            report=report,
            reviewed_current_fingerprint=current.fingerprint,
            candidate_fingerprint=candidate_tool.fingerprint,
        )

    async def accept_pending(
        self,
        tool_key: str,
        *,
        expected_candidate_fingerprint: str,
    ) -> SchemaRefreshResult:
        pending = self._pending.get(tool_key)
        if pending is None:
            raise SchemaSourceError(f"tool {tool_key!r} has no pending native schema")

        candidate_tool, candidate_invoker, offload_sync = pending
        if candidate_tool.fingerprint != expected_candidate_fingerprint:
            raise SchemaSourceError("pending native schema candidate changed")

        expected_version = self._registry.version
        current = self._registry.get(tool_key)
        report = compare_tool_specs(current, candidate_tool)
        await self._apply_binding(
            current=current,
            candidate_tool=candidate_tool,
            candidate_invoker=candidate_invoker,
            offload_sync=offload_sync,
            expected_version=expected_version,
        )
        self._pending.pop(tool_key, None)
        return SchemaRefreshResult(
            tool_key=tool_key,
            action="applied",
            applied=True,
            report=report,
        )

    async def check_once(
        self,
        *,
        apply_compatible: bool = True,
    ) -> tuple[SchemaRefreshResult, ...]:
        results: list[SchemaRefreshResult] = []
        for tool_key in tuple(self._refreshers):
            try:
                result = await self.refresh(
                    tool_key,
                    apply_compatible=apply_compatible,
                )
            except Exception as exc:
                # asyncio.CancelledError derives from BaseException, so watcher
                # shutdown is never swallowed here. Ordinary source failures are
                # isolated per tool and retried on the next sweep.
                self._record_failure(tool_key, exc)
                continue
            self._watch_failures.pop(tool_key, None)
            results.append(result)
        return tuple(results)

    async def start(
        self,
        *,
        interval_seconds: float = 300.0,
        apply_compatible: bool = True,
    ) -> None:
        if interval_seconds <= 0:
            raise ValueError("interval_seconds must be > 0")
        if self._watch_task is not None and not self._watch_task.done():
            raise RuntimeError("native schema watcher is already running")

        async def watch_loop() -> None:
            while True:
                await self.check_once(apply_compatible=apply_compatible)
                await asyncio.sleep(interval_seconds)

        self._watch_task = asyncio.create_task(watch_loop())

    async def stop(self) -> None:
        task = self._watch_task
        self._watch_task = None
        if task is None:
            return
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
