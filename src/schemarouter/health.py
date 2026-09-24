from __future__ import annotations

import asyncio
import inspect
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal

from .errors import PlanValidationError
from .executor import RegistryExecutor

HealthProbe = Callable[[], bool | Awaitable[bool]]
HealthStatus = Literal["unknown", "healthy", "unhealthy"]


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
    status: HealthStatus = "unknown"
    last_checked_at: datetime | None = None
    last_error_type: str | None = None


class AccessHealthMonitor:
    """Explicit background health checks for registered read-only access paths.

    Probes are trusted local callbacks. The monitor never invents probes from remote metadata and
    never invokes a registered data endpoint on its own. Probe success reopens an access path;
    probe failure extends only the bounded availability cooldown.
    """

    def __init__(self, executor: RegistryExecutor) -> None:
        self.executor = executor
        self._probes: dict[tuple[str, str], _ProbeRecord] = {}
        self._task: asyncio.Task[None] | None = None
        self._interval_seconds = 30.0
        self._probe_timeout_seconds = 5.0
        self._max_concurrency = 4

    @property
    def running(self) -> bool:
        return self._task is not None and not self._task.done()

    def register(
        self,
        tool_key: str,
        endpoint: str,
        probe: HealthProbe,
    ) -> None:
        endpoint_spec = self.executor.registry.endpoint(tool_key, endpoint)
        if endpoint_spec.read_only is not True:
            raise PlanValidationError(
                "background health probes may be attached only to explicitly read-only "
                f"access paths; got {tool_key}.{endpoint}"
            )
        if not callable(probe):
            raise TypeError("health probe must be callable")
        self._probes[(tool_key, endpoint)] = _ProbeRecord(probe=probe)

    def unregister(self, tool_key: str, endpoint: str) -> None:
        self._probes.pop((tool_key, endpoint), None)

    def snapshots(self) -> tuple[HealthProbeSnapshot, ...]:
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
            status: HealthStatus = "unhealthy"
            error_type: str | None = None
            try:
                outcome = record.probe()
                if inspect.isawaitable(outcome):
                    outcome = await asyncio.wait_for(
                        outcome,
                        timeout=probe_timeout_seconds,
                    )
                healthy = outcome is True
                if healthy:
                    self.executor.mark_access_available(tool_key, endpoint)
                    status = "healthy"
                else:
                    self.executor.mark_access_unavailable(
                        tool_key,
                        endpoint,
                        cooldown_seconds=unavailable_cooldown_seconds,
                    )
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                error_type = type(exc).__name__
                self.executor.mark_access_unavailable(
                    tool_key,
                    endpoint,
                    cooldown_seconds=unavailable_cooldown_seconds,
                )

            record.status = status
            record.last_checked_at = datetime.now(UTC)
            record.last_error_type = error_type

    async def run_once(
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
                for (tool_key, endpoint), record in tuple(self._probes.items())
            )
        )
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
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
