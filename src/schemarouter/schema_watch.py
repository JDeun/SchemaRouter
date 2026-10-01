from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable, Mapping
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Literal

from .adapters.base import AdapterRegistry, RefreshProfile
from .errors import SchemaSourceError
from .models import ToolSpec
from .registry import ToolRegistry
from .schema_diff import SchemaRefreshResult
from .source_identity import StructuredSourceIdentity, structured_source_identity

SchemaWatchStatus = Literal[
    "idle",
    "unchanged",
    "applied",
    "report_only",
    "pending_review",
    "rejected",
    "error",
    "stale",
    "stale_contract",
    "stale_source",
]

RefreshCallable = Callable[..., Awaitable[SchemaRefreshResult]]


@dataclass(frozen=True)
class SchemaWatchSnapshot:
    """Privacy-safe state for one periodically refreshed remote schema."""

    tool: str
    status: SchemaWatchStatus
    interval_seconds: float
    apply_compatible: bool
    last_checked_at: datetime | None = None
    last_applied_at: datetime | None = None
    last_compatibility: str | None = None
    pending_review: bool = False
    pending_change_count: int = 0
    pending_reviewed_current_fingerprint: str | None = None
    pending_candidate_fingerprint: str | None = None
    pending_candidate_source_identity: str | None = None
    last_error_type: str | None = None


@dataclass
class _WatchRecord:
    tool_fingerprint: str
    source_identity: StructuredSourceIdentity
    interval_seconds: float
    apply_compatible: bool
    schema_headers: dict[str, str] | None
    trusted_headers: dict[str, str] | None
    mcp_client_factory: Any | None
    timeout_seconds: float
    status: SchemaWatchStatus = "idle"
    last_checked_at: datetime | None = None
    last_applied_at: datetime | None = None
    last_compatibility: str | None = None
    last_error_type: str | None = None
    pending_result: SchemaRefreshResult | None = None
    next_due: float = 0.0


class SchemaWatchManager:
    """Optional periodic schema refresh for registered remote structured sources.

    The manager stores trusted transport credentials only in process-local private records.
    Snapshots never expose header values, factories, or other transport state.
    """

    def __init__(
        self,
        registry: ToolRegistry,
        refresh: RefreshCallable,
        adapters: AdapterRegistry | None = None,
    ) -> None:
        self.registry = registry
        self._refresh = refresh
        if adapters is None:
            # Preserve direct SchemaWatchManager construction while keeping
            # refresh capability knowledge in the adapter registry.
            from .ingestion import default_adapter_registry

            adapters = default_adapter_registry()
        self.adapters = adapters
        self._records: dict[str, _WatchRecord] = {}
        self._task: asyncio.Task[None] | None = None
        self._run_lock = asyncio.Lock()
        self._wake = asyncio.Event()
        self._max_concurrency = 4

    @property
    def running(self) -> bool:
        return self._task is not None and not self._task.done()

    @asynccontextmanager
    async def lifecycle_guard(self):
        """Quiesce schema refresh while a router lifecycle mutation runs."""

        async with self._run_lock:
            yield

    @staticmethod
    def _adapter(tool: Any) -> str | None:
        adapter = tool.execution_metadata.get("adapter")
        if not isinstance(adapter, str):
            adapter = tool.metadata.get("adapter")
        return adapter if isinstance(adapter, str) else None

    def _refresh_profile(self, tool: ToolSpec) -> RefreshProfile:
        adapter = self._adapter(tool)
        if adapter is None:
            raise SchemaSourceError(
                f"tool {tool.key!r} does not have a refreshable structured-source adapter; "
                "no structured-source adapter is declared"
            )
        try:
            profile = self.adapters.refresh_profile(adapter)
        except KeyError as exc:
            raise SchemaSourceError(
                f"tool {tool.key!r} references an unavailable source adapter"
            ) from exc
        if not profile.supported:
            raise SchemaSourceError(
                f"tool {tool.key!r} does not have a refreshable structured-source adapter"
            )
        return profile

    def _assert_refreshable(self, tool_key: str) -> ToolSpec:
        try:
            tool = self.registry.get(tool_key)
        except KeyError as exc:
            raise KeyError(f"unknown tool: {tool_key}") from exc
        self._refresh_profile(tool)
        return tool

    def _watch_identity(self, tool: ToolSpec) -> StructuredSourceIdentity:
        profile = self._refresh_profile(tool)
        identity = structured_source_identity(tool, profile)
        if identity is None:
            raise SchemaSourceError(
                f"tool {tool.key!r} is missing structured-source identity"
            )
        if profile.mode == "url" and identity.source_url is None:
            raise SchemaSourceError(
                f"tool {tool.key!r} is missing source identity for schema watch"
            )
        if (
            profile.mode == "url_or_bound_mcp"
            and identity.source_url is None
            and identity.transport_fingerprint is None
        ):
            raise SchemaSourceError(
                f"tool {tool.key!r} is missing source/transport identity for schema watch"
            )
        return identity

    def _contract_status(
        self,
        tool_key: str,
        record: _WatchRecord,
    ) -> tuple[bool, SchemaWatchStatus | None, str | None]:
        try:
            current = self._assert_refreshable(tool_key)
        except KeyError:
            return False, "stale", "CapabilityRemoved"
        except SchemaSourceError:
            return False, "stale", "AdapterNotRefreshable"

        try:
            current_identity = self._watch_identity(current)
        except SchemaSourceError:
            return False, "stale_source", "SourceIdentityMissing"

        if current_identity != record.source_identity:
            return False, "stale_source", "SourceIdentityChanged"
        if current.fingerprint != record.tool_fingerprint:
            return False, "stale_contract", "ToolContractChanged"
        return True, None, None

    def register(
        self,
        tool_key: str,
        *,
        interval_seconds: float = 300.0,
        apply_compatible: bool = True,
        schema_headers: Mapping[str, str] | None = None,
        trusted_headers: Mapping[str, str] | None = None,
        mcp_client_factory: Any | None = None,
        timeout_seconds: float = 20.0,
    ) -> None:
        tool = self._assert_refreshable(tool_key)
        identity = self._watch_identity(tool)
        interval = float(interval_seconds)
        timeout = float(timeout_seconds)
        if interval <= 0:
            raise ValueError("interval_seconds must be > 0")
        if timeout <= 0:
            raise ValueError("timeout_seconds must be > 0")

        self._records[tool_key] = _WatchRecord(
            tool_fingerprint=tool.fingerprint,
            source_identity=identity,
            interval_seconds=interval,
            apply_compatible=bool(apply_compatible),
            schema_headers=(
                dict(schema_headers)
                if schema_headers is not None
                else None
            ),
            trusted_headers=(
                dict(trusted_headers)
                if trusted_headers is not None
                else None
            ),
            mcp_client_factory=mcp_client_factory,
            timeout_seconds=timeout,
            next_due=time.monotonic(),
        )
        self._wake.set()

    def unregister(self, tool_key: str) -> None:
        self._records.pop(tool_key, None)
        self._wake.set()

    def snapshots(self) -> tuple[SchemaWatchSnapshot, ...]:
        return tuple(
            SchemaWatchSnapshot(
                tool=tool_key,
                status=record.status,
                interval_seconds=record.interval_seconds,
                apply_compatible=record.apply_compatible,
                last_checked_at=record.last_checked_at,
                last_applied_at=record.last_applied_at,
                last_compatibility=record.last_compatibility,
                pending_review=record.pending_result is not None,
                pending_change_count=(
                    len(record.pending_result.report.changes)
                    if record.pending_result is not None
                    else 0
                ),
                pending_reviewed_current_fingerprint=(
                    record.pending_result.reviewed_current_fingerprint
                    if record.pending_result is not None
                    else None
                ),
                pending_candidate_fingerprint=(
                    record.pending_result.candidate_fingerprint
                    if record.pending_result is not None
                    else None
                ),
                pending_candidate_source_identity=(
                    record.pending_result.candidate_source_identity
                    if record.pending_result is not None
                    else None
                ),
                last_error_type=record.last_error_type,
            )
            for tool_key, record in sorted(self._records.items())
        )

    def pending_review(self, tool_key: str) -> SchemaRefreshResult | None:
        record = self._records.get(tool_key)
        if record is None or record.pending_result is None:
            return None
        return record.pending_result.model_copy(deep=True)

    @staticmethod
    def _expected_pending_candidate(
        tool_key: str,
        record: _WatchRecord,
        expected_candidate_fingerprint: str,
    ) -> SchemaRefreshResult:
        pending = record.pending_result
        if pending is None:
            raise SchemaSourceError(
                f"tool {tool_key!r} has no pending schema candidate to review"
            )
        candidate_fingerprint = pending.candidate_fingerprint
        if candidate_fingerprint is None:
            raise SchemaSourceError(
                f"tool {tool_key!r} pending review has no pinned candidate fingerprint"
            )
        if candidate_fingerprint != expected_candidate_fingerprint:
            raise SchemaSourceError(
                f"tool {tool_key!r} pending candidate fingerprint does not match "
                "the reviewed candidate"
            )
        if (
            pending.reviewed_current_fingerprint is None
            or pending.reviewed_current_fingerprint != record.tool_fingerprint
        ):
            raise SchemaSourceError(
                f"tool {tool_key!r} pending review no longer matches the watched contract"
            )
        if pending.candidate_source_identity is None:
            raise SchemaSourceError(
                f"tool {tool_key!r} pending review has no pinned candidate source identity"
            )
        return pending

    async def accept_pending(
        self,
        tool_key: str,
        *,
        expected_candidate_fingerprint: str,
    ) -> SchemaRefreshResult:
        """Refetch and accept only the exact candidate reviewed by trusted local code."""

        async with self._run_lock:
            record = self._records.get(tool_key)
            if record is None:
                raise SchemaSourceError(
                    f"tool {tool_key!r} has no registered schema watch"
                )
            pending = self._expected_pending_candidate(
                tool_key,
                record,
                expected_candidate_fingerprint,
            )
            current, stale_status, stale_reason = self._contract_status(
                tool_key,
                record,
            )
            if not current:
                record.status = stale_status or "stale"
                record.last_error_type = stale_reason
                record.pending_result = None
                raise SchemaSourceError(
                    f"tool {tool_key!r} changed before pending schema approval"
                )

            result = await asyncio.wait_for(
                self._refresh(
                    tool_key,
                    apply_compatible=False,
                    schema_headers=record.schema_headers,
                    trusted_headers=record.trusted_headers,
                    mcp_client_factory=record.mcp_client_factory,
                    timeout=record.timeout_seconds,
                    _expected_fingerprint=record.tool_fingerprint,
                    _expected_source_identity=record.source_identity,
                    _accept_candidate_fingerprint=expected_candidate_fingerprint,
                    _accept_candidate_source_identity=(
                        pending.candidate_source_identity
                    ),
                ),
                timeout=record.timeout_seconds,
            )
            checked_at = datetime.now(timezone.utc)
            record.last_checked_at = checked_at
            record.last_compatibility = result.compatibility
            record.last_error_type = None

            if result.action == "pending_review":
                record.pending_result = result.model_copy(deep=True)
                record.status = "pending_review"
                record.next_due = time.monotonic() + record.interval_seconds
                return result.model_copy(deep=True)

            if result.action != "applied":
                raise SchemaSourceError(
                    f"tool {tool_key!r} pending approval returned unexpected "
                    f"refresh action {result.action!r}"
                )

            applied_tool = self.registry.get(tool_key)
            applied_identity = self._watch_identity(applied_tool)
            if applied_identity != record.source_identity:
                record.status = "stale_source"
                record.last_error_type = "SourceIdentityChanged"
                record.pending_result = None
                raise SchemaSourceError(
                    f"tool {tool_key!r} source identity changed during pending approval"
                )
            if (
                result.candidate_fingerprint is None
                or applied_tool.fingerprint != result.candidate_fingerprint
            ):
                record.status = "stale_contract"
                record.last_error_type = "AppliedContractChanged"
                record.pending_result = None
                raise SchemaSourceError(
                    f"tool {tool_key!r} accepted contract does not match reviewed candidate"
                )

            record.tool_fingerprint = applied_tool.fingerprint
            record.pending_result = None
            record.status = "applied"
            record.last_applied_at = checked_at
            record.next_due = time.monotonic() + record.interval_seconds
            return result.model_copy(deep=True)

    async def reject_pending(
        self,
        tool_key: str,
        *,
        expected_candidate_fingerprint: str,
    ) -> SchemaRefreshResult:
        """Clear only the exact pending candidate reviewed by trusted local code."""

        async with self._run_lock:
            record = self._records.get(tool_key)
            if record is None:
                raise SchemaSourceError(
                    f"tool {tool_key!r} has no registered schema watch"
                )
            pending = self._expected_pending_candidate(
                tool_key,
                record,
                expected_candidate_fingerprint,
            )
            current, stale_status, stale_reason = self._contract_status(
                tool_key,
                record,
            )
            if not current:
                record.status = stale_status or "stale"
                record.last_error_type = stale_reason
                record.pending_result = None
                raise SchemaSourceError(
                    f"tool {tool_key!r} changed before pending schema rejection"
                )

            record.pending_result = None
            record.status = "rejected"
            record.last_error_type = None
            record.next_due = time.monotonic() + record.interval_seconds
            return pending.model_copy(deep=True)

    async def _run_record(
        self,
        tool_key: str,
        record: _WatchRecord,
        *,
        semaphore: asyncio.Semaphore,
    ) -> None:
        async with semaphore:
            now = datetime.now(timezone.utc)
            current, stale_status, stale_reason = self._contract_status(
                tool_key,
                record,
            )
            if not current:
                record.status = stale_status or "stale"
                record.last_checked_at = now
                record.last_error_type = stale_reason
                record.pending_result = None
                record.next_due = time.monotonic() + record.interval_seconds
                return

            try:
                result = await asyncio.wait_for(
                    self._refresh(
                        tool_key,
                        apply_compatible=record.apply_compatible,
                        schema_headers=record.schema_headers,
                        trusted_headers=record.trusted_headers,
                        mcp_client_factory=record.mcp_client_factory,
                        timeout=record.timeout_seconds,
                        _expected_fingerprint=record.tool_fingerprint,
                        _expected_source_identity=record.source_identity,
                    ),
                    timeout=record.timeout_seconds,
                )
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                current, stale_status, stale_reason = self._contract_status(
                    tool_key,
                    record,
                )
                if not current:
                    record.status = stale_status or "stale"
                    record.last_error_type = stale_reason
                    record.pending_result = None
                else:
                    record.status = "error"
                    record.last_error_type = type(exc).__name__
                record.last_checked_at = datetime.now(timezone.utc)
                record.next_due = time.monotonic() + record.interval_seconds
                return

            checked_at = datetime.now(timezone.utc)
            record.last_checked_at = checked_at
            record.last_compatibility = result.compatibility
            record.last_error_type = None

            if result.action == "applied":
                try:
                    applied_tool = self.registry.get(tool_key)
                    applied_identity = self._watch_identity(applied_tool)
                except (KeyError, SchemaSourceError):
                    record.status = "stale"
                    record.last_error_type = "AppliedContractMissing"
                    record.pending_result = None
                    record.next_due = time.monotonic() + record.interval_seconds
                    return
                if applied_identity != record.source_identity:
                    record.status = "stale_source"
                    record.last_error_type = "SourceIdentityChanged"
                    record.pending_result = None
                    record.next_due = time.monotonic() + record.interval_seconds
                    return
                if applied_tool.fingerprint != result.report.new_fingerprint:
                    record.status = "stale_contract"
                    record.last_error_type = "AppliedContractChanged"
                    record.pending_result = None
                    record.next_due = time.monotonic() + record.interval_seconds
                    return
                record.tool_fingerprint = applied_tool.fingerprint
            else:
                current, stale_status, stale_reason = self._contract_status(
                    tool_key,
                    record,
                )
                if not current:
                    record.status = stale_status or "stale"
                    record.last_error_type = stale_reason
                    record.pending_result = None
                    record.next_due = time.monotonic() + record.interval_seconds
                    return
            if result.action == "pending_review":
                record.status = "pending_review"
                record.pending_result = result.model_copy(deep=True)
            else:
                record.pending_result = None
                if result.action == "applied":
                    record.status = "applied"
                    record.last_applied_at = checked_at
                elif result.action == "report_only":
                    record.status = "report_only"
                else:
                    record.status = "unchanged"

            record.next_due = time.monotonic() + record.interval_seconds

    async def run_once(
        self,
        *,
        force: bool = True,
        max_concurrency: int | None = None,
    ) -> tuple[SchemaWatchSnapshot, ...]:
        concurrency = (
            self._max_concurrency
            if max_concurrency is None
            else int(max_concurrency)
        )
        if concurrency < 1:
            raise ValueError("max_concurrency must be >= 1")

        async with self._run_lock:
            now = time.monotonic()
            due = [
                (tool_key, record)
                for tool_key, record in tuple(self._records.items())
                if force or record.next_due <= now
            ]
            if not due:
                return self.snapshots()

            semaphore = asyncio.Semaphore(concurrency)
            await asyncio.gather(
                *(
                    self._run_record(
                        tool_key,
                        record,
                        semaphore=semaphore,
                    )
                    for tool_key, record in due
                )
            )
            return self.snapshots()

    def _next_delay(self) -> float:
        if not self._records:
            return 60.0
        now = time.monotonic()
        return max(
            0.05,
            min(
                max(0.0, record.next_due - now)
                for record in self._records.values()
            ),
        )

    async def _loop(self) -> None:
        try:
            while True:
                await self.run_once(force=False)
                self._wake.clear()
                try:
                    await asyncio.wait_for(
                        self._wake.wait(),
                        timeout=self._next_delay(),
                    )
                except TimeoutError:
                    pass
        except asyncio.CancelledError:
            raise

    async def start(self, *, max_concurrency: int = 4) -> None:
        if self.running:
            raise RuntimeError("schema watcher is already running")
        if max_concurrency < 1:
            raise ValueError("max_concurrency must be >= 1")
        self._max_concurrency = int(max_concurrency)
        self._task = asyncio.create_task(self._loop())

    async def stop(self) -> None:
        task = self._task
        self._task = None
        if task is None:
            return
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
