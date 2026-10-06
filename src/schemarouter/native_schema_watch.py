"""Privacy-safe health tracking for router-owned native schema refreshers."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from threading import RLock
from typing import Literal

from .schema_diff import SchemaRefreshResult

NativeSchemaWatchStatus = Literal[
    "idle",
    "unchanged",
    "applied",
    "report_only",
    "pending_review",
    "error",
]


@dataclass(frozen=True)
class NativeSchemaWatchSnapshot:
    """Bounded process-local health for one native schema refresh source."""

    tool: str
    status: NativeSchemaWatchStatus = "idle"
    last_checked_at: datetime | None = None
    last_success_at: datetime | None = None
    last_action: str | None = None
    last_error_type: str | None = None
    failure_count: int = 0
    consecutive_failures: int = 0


@dataclass
class _NativeSchemaWatchRecord:
    status: NativeSchemaWatchStatus = "idle"
    last_checked_at: datetime | None = None
    last_success_at: datetime | None = None
    last_action: str | None = None
    last_error_type: str | None = None
    failure_count: int = 0
    consecutive_failures: int = 0


class NativeSchemaWatchHealth:
    """Track refresh health without retaining exceptions, credentials, or payloads."""

    def __init__(self) -> None:
        self._records: dict[str, _NativeSchemaWatchRecord] = {}
        self._lock = RLock()

    def remember(self, tool_key: str) -> None:
        with self._lock:
            self._records[tool_key] = _NativeSchemaWatchRecord()

    def forget(self, tool_key: str) -> None:
        with self._lock:
            self._records.pop(tool_key, None)

    def record_result(self, tool_key: str, result: SchemaRefreshResult) -> None:
        checked_at = datetime.now(timezone.utc)
        action = result.action
        status: NativeSchemaWatchStatus
        if action == "applied":
            status = "applied"
        elif action == "report_only":
            status = "report_only"
        elif action == "pending_review":
            status = "pending_review"
        else:
            status = "unchanged"

        with self._lock:
            record = self._records.setdefault(tool_key, _NativeSchemaWatchRecord())
            record.status = status
            record.last_checked_at = checked_at
            record.last_success_at = checked_at
            record.last_action = action
            record.last_error_type = None
            record.consecutive_failures = 0

    def record_error(self, tool_key: str, exc: BaseException) -> None:
        with self._lock:
            record = self._records.setdefault(tool_key, _NativeSchemaWatchRecord())
            record.status = "error"
            record.last_checked_at = datetime.now(timezone.utc)
            record.last_error_type = type(exc).__name__
            record.failure_count += 1
            record.consecutive_failures += 1

    def snapshots(self) -> tuple[NativeSchemaWatchSnapshot, ...]:
        with self._lock:
            return tuple(
                NativeSchemaWatchSnapshot(
                    tool=tool_key,
                    status=record.status,
                    last_checked_at=record.last_checked_at,
                    last_success_at=record.last_success_at,
                    last_action=record.last_action,
                    last_error_type=record.last_error_type,
                    failure_count=record.failure_count,
                    consecutive_failures=record.consecutive_failures,
                )
                for tool_key, record in sorted(self._records.items())
            )
