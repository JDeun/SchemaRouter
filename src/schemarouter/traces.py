from __future__ import annotations

import asyncio
import math
import sqlite3
import time
from collections.abc import AsyncIterator, Iterator
from pathlib import Path
from threading import RLock
from typing import Protocol

from pydantic import Field, ValidationError, model_validator

from .errors import StorageFormatError, TraceError
from .models import StrictModel
from .runs import RunEvent
from .storage import (
    _PERSISTED_FETCH_BATCH_SIZE,
    PersistedDocumentLimits,
    _PersistedCollectionLimitError,
    _PersistedDocumentLimitError,
    _PersistedReadBudget,
    _resolve_persisted_document_limits,
    _validate_persisted_document_size,
    _validate_persisted_json_document,
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


class TraceRetentionPolicy(StrictModel):
    """Explicit retention bounds for persistent run traces."""

    max_age_seconds: float | None = Field(default=None, gt=0)
    max_runs: int | None = Field(default=None, ge=0)
    stale_incomplete_after_seconds: float | None = Field(default=None, gt=0)
    prune_on_terminal_append: bool = True

    @model_validator(mode="after")
    def validate_bounds(self) -> TraceRetentionPolicy:
        if (
            self.max_age_seconds is None
            and self.max_runs is None
            and self.stale_incomplete_after_seconds is None
        ):
            raise ValueError("trace retention policy requires at least one bound")
        return self


class TracePruneResult(StrictModel):
    """Deterministic summary returned by SQLite trace pruning."""

    deleted_runs: int = Field(ge=0)
    deleted_events: int = Field(ge=0)
    deleted_complete_runs: int = Field(ge=0)
    deleted_stale_incomplete_runs: int = Field(ge=0)

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
    limits = _resolve_persisted_document_limits(document_limits)
    try:
        summaries_cursor = connection.execute(
            """
            SELECT run_id, created_at, last_sequence, last_timestamp, terminal
            FROM schemarouter_trace_runs
            ORDER BY created_at, run_id
            """
        )
    except sqlite3.DatabaseError as exc:
        raise StorageFormatError(
            "legacy trace table shape is not compatible with migration"
        ) from exc

    budget = _PersistedReadBudget(limits)
    while True:
        try:
            summaries = summaries_cursor.fetchmany(_PERSISTED_FETCH_BATCH_SIZE)
        except sqlite3.DatabaseError as exc:
            raise StorageFormatError(
                "legacy trace table shape is not compatible with migration"
            ) from exc
        if not summaries:
            break

        for summary in summaries:
            run_id = str(summary["run_id"])
            try:
                rows_cursor = connection.execute(
                    """
                    SELECT
                        sequence,
                        length(CAST(document AS BLOB)) AS document_bytes,
                        CASE
                            WHEN length(CAST(document AS BLOB)) <= ?
                            THEN document
                            ELSE NULL
                        END AS document
                    FROM schemarouter_trace_events
                    WHERE run_id = ?
                    ORDER BY sequence
                    """,
                    (limits.max_bytes, run_id),
                )
            except sqlite3.DatabaseError as exc:
                raise StorageFormatError(
                    "legacy trace event table shape is not compatible with migration"
                ) from exc

            events: list[RunEvent] = []
            while True:
                try:
                    rows = rows_cursor.fetchmany(_PERSISTED_FETCH_BATCH_SIZE)
                except sqlite3.DatabaseError as exc:
                    raise StorageFormatError(
                        "legacy trace event table shape is not compatible with migration"
                    ) from exc
                if not rows:
                    break
                for row in rows:
                    try:
                        sequence = int(row["sequence"])
                    except (TypeError, ValueError) as exc:
                        raise StorageFormatError(
                            f"legacy run trace {run_id!r} contains an invalid sequence"
                        ) from exc
                    try:
                        encoded_bytes = int(row["document_bytes"])
                        _validate_persisted_document_size(
                            encoded_bytes,
                            limits=limits,
                        )
                        budget.consume(encoded_bytes)
                        document = row["document"]
                        _validate_persisted_json_document(
                            document,
                            limits=limits,
                            encoded_bytes=encoded_bytes,
                        )
                    except _PersistedCollectionLimitError as exc:
                        raise StorageFormatError(
                            "legacy trace exceeds persisted JSON collection limits"
                        ) from exc
                    except (TypeError, ValueError, _PersistedDocumentLimitError) as exc:
                        raise StorageFormatError(
                            f"legacy run event {run_id}:{sequence} "
                            "exceeds persisted JSON document limits"
                        ) from exc
                    try:
                        event = RunEvent.model_validate_json(document)
                    except (ValidationError, ValueError, RecursionError) as exc:
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

            if not events:
                raise StorageFormatError(
                    f"legacy run trace {run_id!r} has no persisted events"
                )

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

    The store persists the exact RunEvent envelope it receives. SchemaRouter's runtime stream
    applies structured redaction before persistence by default, including when payload tracing is
    enabled. Only the explicit raw_trace_payloads escape hatch emits unredacted runtime events.
    External event producers remain responsible for their own redaction.
    """

    def __init__(
        self,
        path: str | Path,
        *,
        timeout: float = 5.0,
        document_limits: PersistedDocumentLimits | None = None,
        retention_policy: TraceRetentionPolicy | None = None,
    ) -> None:
        if timeout <= 0:
            raise ValueError("timeout must be > 0")
        self.path = str(path)
        self._document_limits = _resolve_persisted_document_limits(
            document_limits
        )
        self._retention_policy = retention_policy
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

    def _create_retention_indexes(self) -> None:
        self._connection.execute(
            """
            CREATE INDEX IF NOT EXISTS schemarouter_trace_runs_retention_idx
            ON schemarouter_trace_runs (terminal, last_timestamp, run_id)
            """
        )
        self._connection.execute(
            """
            CREATE INDEX IF NOT EXISTS schemarouter_trace_runs_created_idx
            ON schemarouter_trace_runs (created_at, run_id)
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
                    self._create_retention_indexes()
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
                self._connection.execute("BEGIN IMMEDIATE")
                try:
                    self._create_retention_indexes()
                except Exception:
                    self._connection.rollback()
                    raise
                else:
                    self._connection.commit()
                return

            self._connection.execute("BEGIN IMMEDIATE")
            try:
                self._validate_legacy_storage()
                self._create_retention_indexes()
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
        except Exception as exc:
            raise TraceError("run event cannot be serialized as persistent JSON") from exc
        try:
            _validate_persisted_json_document(
                document,
                limits=self._document_limits,
            )
        except _PersistedDocumentLimitError as exc:
            raise TraceError(
                "run event exceeds configured persisted JSON document limits"
            ) from exc
        return document

    def _deserialize(
        self,
        run_id: str,
        sequence: int,
        document: str,
        *,
        encoded_bytes: int | None = None,
    ) -> RunEvent:
        try:
            _validate_persisted_json_document(
                document,
                limits=self._document_limits,
                encoded_bytes=encoded_bytes,
            )
        except _PersistedDocumentLimitError as exc:
            raise TraceError(
                f"stored run event {run_id}:{sequence} exceeds configured "
                "persisted JSON document limits"
            ) from exc
        try:
            event = RunEvent.model_validate_json(document)
        except (ValidationError, ValueError, RecursionError) as exc:
            raise TraceError(
                f"stored run event {run_id}:{sequence} is invalid"
            ) from exc
        if event.run_id != run_id or event.sequence != sequence:
            raise TraceError(
                f"stored run event identity mismatch at {run_id}:{sequence}"
            )
        return event

    def _deserialize_row(
        self,
        run_id: str,
        sequence: int,
        row: sqlite3.Row,
    ) -> RunEvent:
        try:
            encoded_bytes = int(row["document_bytes"])
            _validate_persisted_document_size(
                encoded_bytes,
                limits=self._document_limits,
            )
            document = row["document"]
            _validate_persisted_json_document(
                document,
                limits=self._document_limits,
                encoded_bytes=encoded_bytes,
            )
        except (TypeError, ValueError, _PersistedDocumentLimitError) as exc:
            raise TraceError(
                f"stored run event {run_id}:{sequence} exceeds configured "
                "persisted JSON document limits"
            ) from exc
        return self._deserialize(
            run_id,
            sequence,
            document,
            encoded_bytes=encoded_bytes,
        )

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
                if (
                    event.event in _TERMINAL_EVENTS
                    and self._retention_policy is not None
                    and self._retention_policy.prune_on_terminal_append
                ):
                    self._prune_locked(
                        self._retention_policy,
                        now=time.time(),
                    )
            except Exception:
                self._connection.rollback()
                raise
            else:
                self._connection.commit()

    @staticmethod
    def _retention_predicate(
        policy: TraceRetentionPolicy,
        *,
        now: float,
    ) -> tuple[str, tuple[object, ...]]:
        if not math.isfinite(now):
            raise ValueError("now must be finite")

        clauses: list[str] = []
        params: list[object] = []
        if policy.max_age_seconds is not None:
            clauses.append("(terminal = 1 AND last_timestamp < ?)")
            params.append(now - policy.max_age_seconds)
        if policy.stale_incomplete_after_seconds is not None:
            clauses.append("(terminal = 0 AND last_timestamp < ?)")
            params.append(now - policy.stale_incomplete_after_seconds)
        if policy.max_runs is not None:
            clauses.append(
                """
                run_id IN (
                    SELECT run_id
                    FROM schemarouter_trace_runs
                    WHERE terminal = 1
                    ORDER BY last_timestamp DESC, run_id DESC
                    LIMIT -1 OFFSET ?
                )
                """
            )
            params.append(policy.max_runs)
        return " OR ".join(clauses), tuple(params)

    def _prune_locked(
        self,
        policy: TraceRetentionPolicy,
        *,
        now: float,
    ) -> TracePruneResult:
        predicate, params = self._retention_predicate(policy, now=now)
        stats = self._connection.execute(
            f"""
            SELECT
                COUNT(*) AS deleted_runs,
                COALESCE(SUM(last_sequence + 1), 0) AS deleted_events,
                COALESCE(SUM(CASE WHEN terminal = 1 THEN 1 ELSE 0 END), 0)
                    AS deleted_complete_runs,
                COALESCE(SUM(CASE WHEN terminal = 0 THEN 1 ELSE 0 END), 0)
                    AS deleted_stale_incomplete_runs
            FROM schemarouter_trace_runs
            WHERE {predicate}
            """,
            params,
        ).fetchone()
        self._connection.execute(
            f"""
            DELETE FROM schemarouter_trace_runs
            WHERE {predicate}
            """,
            params,
        )
        return TracePruneResult(
            deleted_runs=int(stats["deleted_runs"]),
            deleted_events=int(stats["deleted_events"]),
            deleted_complete_runs=int(stats["deleted_complete_runs"]),
            deleted_stale_incomplete_runs=int(
                stats["deleted_stale_incomplete_runs"]
            ),
        )

    def prune(
        self,
        *,
        policy: TraceRetentionPolicy | None = None,
        now: float | None = None,
    ) -> TracePruneResult:
        """Prune traces transactionally according to an explicit retention policy.

        Complete runs may be bounded by age and/or count. Incomplete runs are
        preserved unless stale_incomplete_after_seconds is explicitly set.
        now is an optional Unix timestamp intended for deterministic operator
        tooling and tests.
        """
        effective_policy = policy or self._retention_policy
        if effective_policy is None:
            raise ValueError("trace retention policy is not configured")
        effective_now = time.time() if now is None else float(now)
        if not math.isfinite(effective_now):
            raise ValueError("now must be finite")

        with self._lock:
            self._begin_write()
            try:
                result = self._prune_locked(
                    effective_policy,
                    now=effective_now,
                )
            except Exception:
                self._connection.rollback()
                raise
            else:
                self._connection.commit()
                return result

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
            cursor = self._connection.execute(
                """
                SELECT
                    sequence,
                    length(CAST(document AS BLOB)) AS document_bytes,
                    CASE
                        WHEN length(CAST(document AS BLOB)) <= ?
                        THEN document
                        ELSE NULL
                    END AS document
                FROM schemarouter_trace_events
                WHERE run_id = ?
                ORDER BY sequence
                """,
                (self._document_limits.max_bytes, run_id),
            )
            if summary is None:
                raise KeyError(run_id)

            budget = _PersistedReadBudget(self._document_limits)
            events: list[RunEvent] = []
            while True:
                rows = cursor.fetchmany(_PERSISTED_FETCH_BATCH_SIZE)
                if not rows:
                    break
                for row in rows:
                    sequence = int(row["sequence"])
                    try:
                        encoded_bytes = int(row["document_bytes"])
                        _validate_persisted_document_size(
                            encoded_bytes,
                            limits=self._document_limits,
                        )
                    except (TypeError, ValueError, _PersistedDocumentLimitError) as exc:
                        raise TraceError(
                            f"stored run event {run_id}:{sequence} exceeds configured "
                            "persisted JSON document limits"
                        ) from exc
                    try:
                        budget.consume(encoded_bytes)
                    except _PersistedCollectionLimitError as exc:
                        raise TraceError(
                            f"stored run trace {run_id!r} exceeds configured "
                            "persisted JSON collection limits"
                        ) from exc
                    events.append(
                        self._deserialize_row(
                            run_id,
                            sequence,
                            row,
                        )
                    )
            if not events:
                raise KeyError(run_id)

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
                cursor = self._connection.execute(
                    """
                    SELECT run_id
                    FROM schemarouter_trace_runs
                    ORDER BY created_at, run_id
                    """
                )
            else:
                cursor = self._connection.execute(
                    """
                    SELECT run_id
                    FROM schemarouter_trace_runs
                    WHERE terminal = ?
                    ORDER BY created_at, run_id
                    """,
                    (1 if complete else 0,),
                )

            budget = _PersistedReadBudget(self._document_limits)
            run_ids: list[str] = []
            while True:
                rows = cursor.fetchmany(_PERSISTED_FETCH_BATCH_SIZE)
                if not rows:
                    break
                for row in rows:
                    try:
                        budget.consume(0)
                    except _PersistedCollectionLimitError as exc:
                        raise TraceError(
                            "stored trace index exceeds configured persisted collection limits"
                        ) from exc
                    run_ids.append(str(row["run_id"]))
            return tuple(run_ids)

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


async def append_run_event_async(
    store: RunTraceStore,
    event: RunEvent,
) -> None:
    """Append one event without running a synchronous trace sink on the event loop.

    The synchronous append is serialized by the store's own contract. The offloaded
    call is shielded from task cancellation and awaited to completion before
    cancellation propagates, preventing a detached SQLite write from outliving the
    async persistence boundary.
    """

    append_task = asyncio.create_task(
        asyncio.to_thread(store.append, event)
    )
    try:
        await asyncio.shield(append_task)
    except asyncio.CancelledError:
        try:
            await append_task
        except Exception:
            pass
        raise


async def _close_upstream_events(
    events: AsyncIterator[RunEvent],
) -> None:
    close = getattr(events, "aclose", None)
    if close is None:
        return
    await close()


async def record_run_events(
    events: AsyncIterator[RunEvent],
    *,
    store: RunTraceStore,
) -> AsyncIterator[RunEvent]:
    """Persist an event stream and promptly propagate downstream closure upstream."""
    primary_error: BaseException | None = None
    try:
        async for event in events:
            await append_run_event_async(store, event)
            yield event
    except BaseException as exc:
        primary_error = exc
        raise
    finally:
        cleanup_error: BaseException | None = None
        try:
            await _close_upstream_events(events)
        except BaseException as exc:
            cleanup_error = exc
        if primary_error is None and cleanup_error is not None:
            raise cleanup_error


def replay_run_events(
    store: RunTraceStore,
    run_id: str,
) -> Iterator[RunEvent]:
    """Replay detached historical events without re-executing any tool call."""
    yield from store.trace(run_id).replay()
