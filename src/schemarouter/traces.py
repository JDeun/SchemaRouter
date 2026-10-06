from __future__ import annotations

import sqlite3
from collections.abc import AsyncIterator, Iterator
from pathlib import Path
from threading import RLock
from typing import Protocol

from pydantic import Field, ValidationError, model_validator

from .errors import StorageFormatError, TraceError
from .models import StrictModel
from .runs import RunEvent
from .storage import (
    PersistedDocumentLimits,
    _decode_persisted_json,
    component_presence,
    component_versions,
    stamp_current_component_format,
    validate_component_openable,
)

_TERMINAL_EVENTS = {"run.end", "run.error"}


class RunTrace(StrictModel):
    """Validated replayable snapshot of one SchemaRouter run event stream."""

    run_id: str = Field(min_length=1)
    events: list[RunEvent] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_trace(self) -> RunTrace:
        if self.events[0].event != "run.start":
            raise ValueError("run trace must start with run.start")

        terminal_seen = False
        for expected_sequence, event in enumerate(self.events):
            if event.run_id != self.run_id:
                raise ValueError("run trace contains a mismatched run_id")
            if event.sequence != expected_sequence:
                raise ValueError(
                    "run trace sequence must be contiguous from zero: "
                    f"expected {expected_sequence}, got {event.sequence}"
                )
            if terminal_seen:
                raise ValueError("run trace cannot contain events after a terminal event")
            if event.event in _TERMINAL_EVENTS:
                terminal_seen = True
        return self

    @property
    def complete(self) -> bool:
        return self.events[-1].event in _TERMINAL_EVENTS

    @property
    def terminal_event(self) -> RunEvent | None:
        if not self.complete:
            return None
        return self.events[-1].model_copy(deep=True)

    def replay(self) -> tuple[RunEvent, ...]:
        """Return detached events in their original validated order."""
        return tuple(event.model_copy(deep=True) for event in self.events)


class RunTraceStore(Protocol):
    """Structural contract for append-only run-event persistence."""

    def append(self, event: RunEvent) -> None: ...

    def trace(self, run_id: str) -> RunTrace: ...

    def run_ids(self, *, complete: bool | None = None) -> tuple[str, ...]: ...


def _validate_legacy_trace_storage(
    connection: sqlite3.Connection,
    *,
    document_limits: PersistedDocumentLimits | None = None,
) -> None:
    limits = (
        document_limits.model_copy(deep=True)
        if document_limits is not None
        else PersistedDocumentLimits()
    )
    try:
        summaries = connection.execute(
            """
            SELECT run_id, created_at, last_sequence, last_timestamp, terminal
            FROM schemarouter_trace_runs
            ORDER BY created_at, run_id
            """
        ).fetchall()
    except sqlite3.DatabaseError as exc:
        raise StorageFormatError(
            "legacy trace table shape is not compatible with migration"
        ) from exc

    for summary in summaries:
        run_id = str(summary["run_id"])
        try:
            rows = connection.execute(
                """
                SELECT sequence, document
                FROM schemarouter_trace_events
                WHERE run_id = ?
                ORDER BY sequence
                """,
                (run_id,),
            ).fetchall()
        except sqlite3.DatabaseError as exc:
            raise StorageFormatError(
                "legacy trace event table shape is not compatible with migration"
            ) from exc
        if not rows:
            raise StorageFormatError(
                f"legacy run trace {run_id!r} has no persisted events"
            )

        events: list[RunEvent] = []
        for row in rows:
            try:
                sequence = int(row["sequence"])
            except (TypeError, ValueError) as exc:
                raise StorageFormatError(
                    f"legacy run trace {run_id!r} contains an invalid sequence"
                ) from exc
            try:
                payload = _decode_persisted_json(
                    str(row["document"]),
                    limits=limits,
                )
                event = RunEvent.model_validate(payload)
            except (ValidationError, ValueError, TypeError) as exc:
                raise StorageFormatError(
                    f"legacy run event {run_id}:{sequence} "
                    "cannot be migrated safely"
                ) from exc
            if event.run_id != run_id or event.sequence != sequence:
                raise StorageFormatError(
                    f"legacy run event identity mismatch at "
                    f"{run_id}:{sequence}"
                )
            events.append(event)

        try:
            trace = RunTrace(run_id=run_id, events=events)
        except ValidationError as exc:
            raise StorageFormatError(
                f"legacy run trace {run_id!r} violates replay invariants"
            ) from exc

        first_timestamp = trace.events[0].timestamp.timestamp()
        last_timestamp = trace.events[-1].timestamp.timestamp()
        try:
            created_at = float(summary["created_at"])
            last_sequence = int(summary["last_sequence"])
            stored_last_timestamp = float(summary["last_timestamp"])
            terminal_raw = int(summary["terminal"])
        except (TypeError, ValueError) as exc:
            raise StorageFormatError(
                f"legacy run trace {run_id!r} summary contains invalid values"
            ) from exc
        if terminal_raw not in {0, 1}:
            raise StorageFormatError(
                f"legacy run trace {run_id!r} terminal summary is invalid"
            )
        if abs(created_at - first_timestamp) > 1e-6:
            raise StorageFormatError(
                f"legacy run trace {run_id!r} created_at summary is invalid"
            )
        if last_sequence != trace.events[-1].sequence:
            raise StorageFormatError(
                f"legacy run trace {run_id!r} sequence summary is invalid"
            )
        if abs(stored_last_timestamp - last_timestamp) > 1e-6:
            raise StorageFormatError(
                f"legacy run trace {run_id!r} timestamp summary is invalid"
            )
        if bool(terminal_raw) != trace.complete:
            raise StorageFormatError(
                f"legacy run trace {run_id!r} terminal summary is invalid"
            )

    try:
        orphan = connection.execute(
            """
            SELECT event.run_id
            FROM schemarouter_trace_events AS event
            LEFT JOIN schemarouter_trace_runs AS run
              ON run.run_id = event.run_id
            WHERE run.run_id IS NULL
            LIMIT 1
            """
        ).fetchone()
    except sqlite3.DatabaseError as exc:
        raise StorageFormatError(
            "legacy trace table shape is not compatible with migration"
        ) from exc
    if orphan is not None:
        raise StorageFormatError(
            f"legacy trace event references missing run {str(orphan[0])!r}"
        )


class SQLiteRunTraceStore:
    """Append-only SQLite store for replayable RunEvent streams.

    The store persists the exact RunEvent envelope it receives. Payloads are therefore redacted
    when the source stream uses the default RunConfig, but explicit include_payloads=True data will
    also be persisted and must be protected by the application.
    """

    def __init__(
        self,
        path: str | Path,
        *,
        timeout: float = 5.0,
        document_limits: PersistedDocumentLimits | None = None,
    ) -> None:
        if timeout <= 0:
            raise ValueError("timeout must be > 0")
        self.path = str(path)
        self._document_limits = (
            document_limits.model_copy(deep=True)
            if document_limits is not None
            else PersistedDocumentLimits()
        )
        self._lock = RLock()
        self._closed = False
        self._connection = sqlite3.connect(
            self.path,
            timeout=timeout,
            check_same_thread=False,
        )
        self._connection.row_factory = sqlite3.Row
        self._connection.execute("PRAGMA foreign_keys = ON")
        busy_timeout_ms = int(timeout * 1000)
        self._connection.execute(f"PRAGMA busy_timeout = {busy_timeout_ms}")
        if self.path != ":memory:":
            self._connection.execute("PRAGMA journal_mode = WAL")
        try:
            self._initialize()
        except Exception:
            self._connection.close()
            self._closed = True
            raise

    def _create_component_tables(self) -> None:
        self._connection.execute(
            """
            CREATE TABLE IF NOT EXISTS schemarouter_trace_runs (
                run_id TEXT PRIMARY KEY,
                created_at REAL NOT NULL,
                last_sequence INTEGER NOT NULL,
                last_timestamp REAL NOT NULL,
                terminal INTEGER NOT NULL CHECK (terminal IN (0, 1))
            )
            """
        )
        self._connection.execute(
            """
            CREATE TABLE IF NOT EXISTS schemarouter_trace_events (
                run_id TEXT NOT NULL,
                sequence INTEGER NOT NULL,
                document TEXT NOT NULL,
                PRIMARY KEY (run_id, sequence),
                FOREIGN KEY (run_id)
                    REFERENCES schemarouter_trace_runs(run_id)
                    ON DELETE CASCADE
            )
            """
        )

    def _validate_legacy_storage(self) -> None:
        _validate_legacy_trace_storage(
            self._connection,
            document_limits=self._document_limits,
        )

    def _initialize(self) -> None:
        with self._lock:
            presence = component_presence(self._connection, "trace")
            if presence == "partial":
                raise StorageFormatError(
                    "trace SQLite storage is incomplete; required tables are missing"
                )

            if presence == "absent":
                self._connection.execute("BEGIN IMMEDIATE")
                try:
                    self._create_component_tables()
                    stamp_current_component_format(
                        self._connection,
                        "trace",
                    )
                except Exception:
                    self._connection.rollback()
                    raise
                else:
                    self._connection.commit()
                return

            status = validate_component_openable(
                self._connection,
                "trace",
            )
            if status == "current":
                return

            self._connection.execute("BEGIN IMMEDIATE")
            try:
                self._validate_legacy_storage()
                stamp_current_component_format(
                    self._connection,
                    "trace",
                    from_version=0,
                )
            except Exception:
                self._connection.rollback()
                raise
            else:
                self._connection.commit()

    def _ensure_open(self) -> None:
        if self._closed:
            raise RuntimeError("SQLiteRunTraceStore is closed")

    @property
    def storage_format_version(self) -> int:
        with self._lock:
            self._ensure_open()
            storage_version, _ = component_versions(
                self._connection,
                "trace",
            )
            if storage_version is None:
                raise StorageFormatError(
                    "trace storage format metadata is missing"
                )
            return storage_version

    @property
    def document_format_version(self) -> int:
        with self._lock:
            self._ensure_open()
            _, document_version = component_versions(
                self._connection,
                "trace",
            )
            if document_version is None:
                raise StorageFormatError(
                    "trace document format metadata is missing"
                )
            return document_version

    def _begin_write(self) -> None:
        self._ensure_open()
        self._connection.execute("BEGIN IMMEDIATE")

    def _serialize(self, event: RunEvent) -> str:
        try:
            document = event.model_dump_json()
            _decode_persisted_json(
                document,
                limits=self._document_limits,
            )
            return document
        except (ValueError, TypeError) as exc:
            raise TraceError(
                "run event exceeds persistent JSON safety limits"
            ) from exc
        except Exception as exc:
            raise TraceError("run event cannot be serialized as persistent JSON") from exc

    def _deserialize(
        self,
        run_id: str,
        sequence: int,
        document: str,
    ) -> RunEvent:
        try:
            payload = _decode_persisted_json(
                document,
                limits=self._document_limits,
            )
            event = RunEvent.model_validate(payload)
        except (ValidationError, ValueError, TypeError) as exc:
            raise TraceError(
                f"stored run event {run_id}:{sequence} is invalid within persistent document limits"
            ) from exc
        if event.run_id != run_id or event.sequence != sequence:
            raise TraceError(
                f"stored run event identity mismatch at {run_id}:{sequence}"
            )
        return event

    def append(self, event: RunEvent) -> None:
        if not event.run_id.strip():
            raise TraceError("run event requires a non-empty run_id")
        document = self._serialize(event)
        event_timestamp = event.timestamp.timestamp()

        with self._lock:
            self._begin_write()
            try:
                row = self._connection.execute(
                    """
                    SELECT last_sequence, terminal
                    FROM schemarouter_trace_runs
                    WHERE run_id = ?
                    """,
                    (event.run_id,),
                ).fetchone()

                if row is None:
                    if event.sequence != 0 or event.event != "run.start":
                        raise TraceError(
                            "the first persisted event for a run must be run.start sequence 0"
                        )
                    self._connection.execute(
                        """
                        INSERT INTO schemarouter_trace_runs (
                            run_id,
                            created_at,
                            last_sequence,
                            last_timestamp,
                            terminal
                        )
                        VALUES (?, ?, ?, ?, 0)
                        """,
                        (event.run_id, event_timestamp, -1, event_timestamp),
                    )
                    last_sequence = -1
                    terminal = False
                else:
                    last_sequence = int(row["last_sequence"])
                    terminal = bool(row["terminal"])

                if terminal:
                    raise TraceError("cannot append events after a terminal run event")
                expected_sequence = last_sequence + 1
                if event.sequence != expected_sequence:
                    raise TraceError(
                        "run event sequence must be contiguous: "
                        f"expected {expected_sequence}, got {event.sequence}"
                    )
                if event.sequence > 0 and event.event == "run.start":
                    raise TraceError("run.start can only appear at sequence 0")
                self._connection.execute(
                    """
                    INSERT INTO schemarouter_trace_events (run_id, sequence, document)
                    VALUES (?, ?, ?)
                    """,
                    (event.run_id, event.sequence, document),
                )
                self._connection.execute(
                    """
                    UPDATE schemarouter_trace_runs
                    SET last_sequence = ?, last_timestamp = ?, terminal = ?
                    WHERE run_id = ?
                    """,
                    (
                        event.sequence,
                        event_timestamp,
                        1 if event.event in _TERMINAL_EVENTS else 0,
                        event.run_id,
                    ),
                )
            except Exception:
                self._connection.rollback()
                raise
            else:
                self._connection.commit()

    def trace(self, run_id: str) -> RunTrace:
        with self._lock:
            self._ensure_open()
            summary = self._connection.execute(
                """
                SELECT last_sequence, terminal
                FROM schemarouter_trace_runs
                WHERE run_id = ?
                """,
                (run_id,),
            ).fetchone()
            rows = self._connection.execute(
                """
                SELECT sequence, document
                FROM schemarouter_trace_events
                WHERE run_id = ?
                ORDER BY sequence
                """,
                (run_id,),
            ).fetchall()
            if summary is None or not rows:
                raise KeyError(run_id)
            events = [
                self._deserialize(
                    run_id,
                    int(row["sequence"]),
                    str(row["document"]),
                )
                for row in rows
            ]
        try:
            trace = RunTrace(run_id=run_id, events=events)
        except ValidationError as exc:
            raise TraceError(f"stored run trace {run_id!r} is invalid") from exc

        if int(summary["last_sequence"]) != trace.events[-1].sequence:
            raise TraceError(f"stored run trace {run_id!r} summary sequence is invalid")
        if bool(summary["terminal"]) != trace.complete:
            raise TraceError(f"stored run trace {run_id!r} terminal summary is invalid")
        return trace

    def run_ids(self, *, complete: bool | None = None) -> tuple[str, ...]:
        with self._lock:
            self._ensure_open()
            if complete is None:
                rows = self._connection.execute(
                    """
                    SELECT run_id
                    FROM schemarouter_trace_runs
                    ORDER BY created_at, run_id
                    """
                ).fetchall()
            else:
                rows = self._connection.execute(
                    """
                    SELECT run_id
                    FROM schemarouter_trace_runs
                    WHERE terminal = ?
                    ORDER BY created_at, run_id
                    """,
                    (1 if complete else 0,),
                ).fetchall()
            return tuple(str(row["run_id"]) for row in rows)

    def delete(self, run_id: str) -> None:
        with self._lock:
            self._begin_write()
            try:
                cursor = self._connection.execute(
                    "DELETE FROM schemarouter_trace_runs WHERE run_id = ?",
                    (run_id,),
                )
                if cursor.rowcount == 0:
                    raise KeyError(run_id)
            except Exception:
                self._connection.rollback()
                raise
            else:
                self._connection.commit()

    def close(self) -> None:
        with self._lock:
            if self._closed:
                return
            self._connection.close()
            self._closed = True

    def __enter__(self) -> SQLiteRunTraceStore:
        self._ensure_open()
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        self.close()


async def record_run_events(
    events: AsyncIterator[RunEvent],
    *,
    store: RunTraceStore,
) -> AsyncIterator[RunEvent]:
    """Persist an event stream before yielding each event to downstream consumers."""
    async for event in events:
        store.append(event)
        yield event


def replay_run_events(
    store: RunTraceStore,
    run_id: str,
) -> Iterator[RunEvent]:
    """Replay detached historical events without re-executing any tool call."""
    yield from store.trace(run_id).replay()
