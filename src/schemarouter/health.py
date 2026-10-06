from __future__ import annotations

import asyncio
import inspect
from collections.abc import Awaitable, Callable, Iterator
from contextlib import asynccontextmanager, contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from threading import RLock
from typing import Literal

from ._loop_affinity import LoopAffinityGuard
from .errors import PlanValidationError, RegistrationError
from .executor import RegistryExecutor
from .models import ToolSpec

HealthProbe = Callable[[], bool | Awaitable[bool]]
HealthStatus = Literal["unknown", "healthy", "unhealthy", "stale"]


@dataclass(frozen=True)
class HealthProbeSnapshot:
    tool: str
    endpoint: str
    status: HealthStatus
    last_checked_at: datetime | None = None
    last_error_type: str | None = None


@dataclass
class _ProbeRecord:
    probe: HealthProbe
    tool_fingerprint: str
    generation: int = 0
    invalidated_reason: str | None = None
    status: HealthStatus = "unknown"
    last_checked_at: datetime | None = None
    last_error_type: str | None = None


@dataclass(frozen=True)
class _ProbeContractTransitionEntry:
    endpoint: str
    record: _ProbeRecord
    invalidated_reason: str | None


@dataclass(frozen=True)
class _ToolContractTransition:
    tool_key: str
    expected_old_fingerprint: str
    expected_new_fingerprint: str
    entries: tuple[_ProbeContractTransitionEntry, ...]


class AccessHealthMonitor:
    """Explicit background health checks for registered read-only access paths.

    Probes are trusted local callbacks. The monitor never invents probes from remote metadata and
    never invokes a registered data endpoint on its own. Probe success reopens an access path;
    probe failure extends only the bounded availability cooldown.
    """

    def __init__(self, executor: RegistryExecutor) -> None:
        self.executor = executor
        self._probes: dict[tuple[str, str], _ProbeRecord] = {}
        self._probe_lock = RLock()
        self._task: asyncio.Task[None] | None = None
        self._interval_seconds = 30.0
        self._probe_timeout_seconds = 5.0
        self._max_concurrency = 4
        self._run_lock = asyncio.Lock()
        self._lifecycle_condition = asyncio.Condition(self._run_lock)
        self._loop_affinity = LoopAffinityGuard("health monitor")
        self._active_probe_tasks: set[asyncio.Task] = set()
        self._quiesce_requests = 0

    @property
    def running(self) -> bool:
        return self._task is not None and not self._task.done()

    def register(
        self,
        tool_key: str,
        endpoint: str,
        probe: HealthProbe,
    ) -> None:
        with self._probe_lock:
            tool = self.executor.registry.get(tool_key)
            endpoint_spec = tool.endpoint(endpoint)
            if endpoint_spec.read_only is not True:
                raise PlanValidationError(
                    "background health probes may be attached only to explicitly read-only "
                    f"access paths; got {tool_key}.{endpoint}"
                )
            if not callable(probe):
                raise TypeError("health probe must be callable")
            self._probes[(tool_key, endpoint)] = _ProbeRecord(
                probe=probe,
                tool_fingerprint=tool.fingerprint,
            )

    def unregister(self, tool_key: str, endpoint: str) -> None:
        with self._probe_lock:
            self._probes.pop((tool_key, endpoint), None)

    def unregister_tool(self, tool_key: str) -> None:
        with self._probe_lock:
            stale = [
                key
                for key in self._probes
                if key[0] == tool_key
            ]
            for key in stale:
                self._probes.pop(key, None)

    @contextmanager
    def contract_transition_guard(self) -> Iterator[None]:
        """Serialize probe registration with contract snapshot/publication/restamping."""

        with self._probe_lock:
            yield

    def _prepare_tool_contract_transition(
        self,
        tool_key: str,
        *,
        expected_old_fingerprint: str,
        expected_new_fingerprint: str,
        new_tool: ToolSpec,
    ) -> _ToolContractTransition:
        """Validate and capture a health-probe transition before publishing a contract."""

        if new_tool.key != tool_key:
            raise RegistrationError(
                "health probe transition tool key does not match the candidate contract"
            )
        if new_tool.fingerprint != expected_new_fingerprint:
            raise RegistrationError(
                "health probe transition fingerprint does not match the candidate contract"
            )

        entries: list[_ProbeContractTransitionEntry] = []
        with self._probe_lock:
            for (registered_tool, endpoint), record in self._probes.items():
                if (
                    registered_tool != tool_key
                    or record.tool_fingerprint != expected_old_fingerprint
                ):
                    continue

                invalidated_reason: str | None = None
                try:
                    endpoint_spec = new_tool.endpoint(endpoint)
                except KeyError:
                    invalidated_reason = "EndpointRemoved"
                else:
                    if endpoint_spec.read_only is not True:
                        invalidated_reason = "EndpointNoLongerReadOnly"

                entries.append(
                    _ProbeContractTransitionEntry(
                        endpoint=endpoint,
                        record=record,
                        invalidated_reason=invalidated_reason,
                    )
                )

        return _ToolContractTransition(
            tool_key=tool_key,
            expected_old_fingerprint=expected_old_fingerprint,
            expected_new_fingerprint=expected_new_fingerprint,
            entries=tuple(entries),
        )

    def _apply_tool_contract_transition(
        self,
        transition: _ToolContractTransition,
    ) -> None:
        """Apply a prevalidated probe transition without rereading mutable registry state."""

        with self._probe_lock:
            for entry in transition.entries:
                key = (transition.tool_key, entry.endpoint)
                record = self._probes.get(key)
                if (
                    record is not entry.record
                    or record.tool_fingerprint != transition.expected_old_fingerprint
                ):
                    continue

                record.generation += 1
                record.tool_fingerprint = transition.expected_new_fingerprint
                if entry.invalidated_reason is not None:
                    record.invalidated_reason = entry.invalidated_reason
                    record.status = "stale"
                    record.last_error_type = entry.invalidated_reason
                    continue

                record.invalidated_reason = None
                record.status = "unknown"
                record.last_error_type = None

    def transition_tool_contract(
        self,
        tool_key: str,
        *,
        expected_old_fingerprint: str,
        expected_new_fingerprint: str,
    ) -> None:
        """Carry trusted probes across one accepted contract transition."""

        with self.contract_transition_guard():
            if not any(
                registered_tool == tool_key
                and record.tool_fingerprint == expected_old_fingerprint
                for (registered_tool, _), record in self._probes.items()
            ):
                return

            current = self.executor.registry.get(tool_key)
            if current.fingerprint != expected_new_fingerprint:
                raise RegistrationError(
                    f"tool {tool_key!r} changed before health probes could be restamped"
                )

            transition = self._prepare_tool_contract_transition(
                tool_key,
                expected_old_fingerprint=expected_old_fingerprint,
                expected_new_fingerprint=expected_new_fingerprint,
                new_tool=current,
            )
            self._apply_tool_contract_transition(transition)

    @asynccontextmanager
    async def lifecycle_guard(self, *, wait_for_inflight: bool = False):
        """Serialize lifecycle commits without running probe callbacks under the lock.

        Normal lifecycle transitions may invalidate an in-flight probe generation and let
        its result be discarded at commit time. Destructive operations can request
        wait_for_inflight to drain already-started probes while preventing new ones from
        starting. A probe that re-enters a destructive lifecycle operation never waits
        for itself.
        """

        self._loop_affinity.claim()
        current_task = asyncio.current_task()
        async with self._lifecycle_condition:
            if wait_for_inflight:
                self._quiesce_requests += 1
                if current_task not in self._active_probe_tasks:
                    while self._active_probe_tasks:
                        await self._lifecycle_condition.wait()
            try:
                yield
            finally:
                if wait_for_inflight:
                    self._quiesce_requests -= 1
                    self._lifecycle_condition.notify_all()

    def _contract_status(
        self,
        tool_key: str,
        endpoint: str,
        record: _ProbeRecord,
    ) -> tuple[bool, str | None]:
        if record.invalidated_reason is not None:
            return False, record.invalidated_reason
        try:
            current_tool = self.executor.registry.get(tool_key)
            current_tool.endpoint(endpoint)
        except KeyError:
            return False, "CapabilityRemoved"
        if current_tool.fingerprint != record.tool_fingerprint:
            return False, "ToolContractChanged"
        return True, None

    def snapshots(self) -> tuple[HealthProbeSnapshot, ...]:
        with self._probe_lock:
            return tuple(
                HealthProbeSnapshot(
                    tool=tool,
                    endpoint=endpoint,
                    status=record.status,
                    last_checked_at=record.last_checked_at,
                    last_error_type=record.last_error_type,
                )
                for (tool, endpoint), record in sorted(self._probes.items())
            )

    async def _run_probe(
        self,
        tool_key: str,
        endpoint: str,
        record: _ProbeRecord,
        *,
        semaphore: asyncio.Semaphore,
        probe_timeout_seconds: float,
        unavailable_cooldown_seconds: float,
    ) -> None:
        async with semaphore:
            current_task = asyncio.current_task()
            registered_active = False

            async with self._lifecycle_condition:
                while self._quiesce_requests:
                    await self._lifecycle_condition.wait()
                if self._probes.get((tool_key, endpoint)) is not record:
                    return
                generation = record.generation
                current, stale_reason = self._contract_status(
                    tool_key,
                    endpoint,
                    record,
                )
                if not current:
                    record.status = "stale"
                    record.last_checked_at = datetime.now(timezone.utc)
                    record.last_error_type = stale_reason
                    return
                if current_task is not None:
                    self._active_probe_tasks.add(current_task)
                    registered_active = True

            try:
                status: HealthStatus = "unhealthy"
                error_type: str | None = None
                healthy = False
                try:
                    async_probe = (
                        inspect.iscoroutinefunction(record.probe)
                        or inspect.iscoroutinefunction(record.probe.__call__)
                    )
                    if async_probe:
                        outcome = record.probe()
                    else:
                        outcome = await asyncio.wait_for(
                            asyncio.to_thread(record.probe),
                            timeout=probe_timeout_seconds,
                        )
                    if inspect.isawaitable(outcome):
                        outcome = await asyncio.wait_for(
                            outcome,
                            timeout=probe_timeout_seconds,
                        )
                    healthy = outcome is True
                except asyncio.CancelledError:
                    raise
                except Exception as exc:
                    error_type = type(exc).__name__

                async with self._lifecycle_condition:
                    if (
                        self._probes.get((tool_key, endpoint)) is not record
                        or record.generation != generation
                    ):
                        return

                    current, stale_reason = self._contract_status(
                        tool_key,
                        endpoint,
                        record,
                    )
                    if not current:
                        record.status = "stale"
                        record.last_checked_at = datetime.now(timezone.utc)
                        record.last_error_type = stale_reason
                        return

                    if healthy and error_type is None:
                        self.executor.mark_access_available(tool_key, endpoint)
                        status = "healthy"
                    else:
                        self.executor.mark_access_unavailable(
                            tool_key,
                            endpoint,
                            cooldown_seconds=unavailable_cooldown_seconds,
                        )

                    record.status = status
                    record.last_checked_at = datetime.now(timezone.utc)
                    record.last_error_type = error_type
            finally:
                if registered_active and current_task is not None:
                    async with self._lifecycle_condition:
                        self._active_probe_tasks.discard(current_task)
                        self._lifecycle_condition.notify_all()

    async def run_once(
        self,
        *,
        probe_timeout_seconds: float | None = None,
        unavailable_cooldown_seconds: float | None = None,
        max_concurrency: int | None = None,
    ) -> tuple[HealthProbeSnapshot, ...]:
        self._loop_affinity.claim()
        return await self._run_once_unlocked(
            probe_timeout_seconds=probe_timeout_seconds,
            unavailable_cooldown_seconds=unavailable_cooldown_seconds,
            max_concurrency=max_concurrency,
        )

    async def _run_once_unlocked(
        self,
        *,
        probe_timeout_seconds: float | None = None,
        unavailable_cooldown_seconds: float | None = None,
        max_concurrency: int | None = None,
    ) -> tuple[HealthProbeSnapshot, ...]:
        timeout = (
            self._probe_timeout_seconds
            if probe_timeout_seconds is None
            else float(probe_timeout_seconds)
        )
        cooldown = (
            max(
                self.executor.unavailable_cooldown_seconds,
                self._interval_seconds * 2,
            )
            if unavailable_cooldown_seconds is None
            else float(unavailable_cooldown_seconds)
        )
        concurrency = self._max_concurrency if max_concurrency is None else max_concurrency

        if timeout <= 0:
            raise ValueError("probe_timeout_seconds must be > 0")
        if cooldown < 0:
            raise ValueError("unavailable_cooldown_seconds must be >= 0")
        if concurrency < 1:
            raise ValueError("max_concurrency must be >= 1")

        semaphore = asyncio.Semaphore(concurrency)
        async with self._lifecycle_condition:
            with self._probe_lock:
                probes = tuple(self._probes.items())

        await asyncio.gather(
            *(
                self._run_probe(
                    tool_key,
                    endpoint,
                    record,
                    semaphore=semaphore,
                    probe_timeout_seconds=timeout,
                    unavailable_cooldown_seconds=cooldown,
                )
                for (tool_key, endpoint), record in probes
            )
        )
        async with self._lifecycle_condition:
            return self.snapshots()

    async def _loop(self) -> None:
        try:
            while True:
                await self.run_once()
                await asyncio.sleep(self._interval_seconds)
        except asyncio.CancelledError:
            raise

    async def start(
        self,
        *,
        interval_seconds: float = 30.0,
        probe_timeout_seconds: float = 5.0,
        max_concurrency: int = 4,
    ) -> None:
        self._loop_affinity.claim()
        if self.running:
            raise RuntimeError("health monitor is already running")
        if interval_seconds <= 0:
            raise ValueError("interval_seconds must be > 0")
        if probe_timeout_seconds <= 0:
            raise ValueError("probe_timeout_seconds must be > 0")
        if max_concurrency < 1:
            raise ValueError("max_concurrency must be >= 1")

        self._interval_seconds = float(interval_seconds)
        self._probe_timeout_seconds = float(probe_timeout_seconds)
        self._max_concurrency = int(max_concurrency)
        self._task = asyncio.create_task(self._loop())

    async def stop(self) -> None:
        task = self._task
        self._task = None
        if task is None:
            return
        self._loop_affinity.claim()
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
