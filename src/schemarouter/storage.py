from __future__ import annotations

import errno
import os
import sqlite3
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from pydantic import Field, computed_field

from .errors import StorageFormatError
from .models import StrictModel

StorageComponent = Literal["registry", "trace"]
StorageStatus = Literal["current", "legacy", "future", "corrupt"]

CURRENT_STORAGE_FORMAT_VERSION = 1
CURRENT_REGISTRY_DOCUMENT_VERSION = 1
CURRENT_TRACE_DOCUMENT_VERSION = 1

_STORAGE_META_TABLE = "schemarouter_storage_meta"
_STORAGE_MIGRATIONS_TABLE = "schemarouter_storage_migrations"

DEFAULT_PERSISTED_DOCUMENT_MAX_BYTES = 2 * 1024 * 1024
DEFAULT_PERSISTED_DOCUMENT_MAX_DEPTH = 64
DEFAULT_PERSISTED_DOCUMENT_MAX_NODES = 100_000
DEFAULT_PERSISTED_COLLECTION_MAX_DOCUMENTS = 50_000
DEFAULT_PERSISTED_COLLECTION_MAX_BYTES = 64 * 1024 * 1024
_PERSISTED_FETCH_BATCH_SIZE = 256
_SQLITE_MIGRATION_LOCK_TIMEOUT_SECONDS = 30.0


@dataclass(frozen=True)
class PersistedDocumentLimits:
    """Resource budgets applied before persisted JSON reaches Pydantic.

    max_documents and max_total_bytes bound a single collection-style read
    such as a registry listing, trace replay, inspection, or migration.
    """

    max_bytes: int = DEFAULT_PERSISTED_DOCUMENT_MAX_BYTES
    max_depth: int = DEFAULT_PERSISTED_DOCUMENT_MAX_DEPTH
    max_nodes: int = DEFAULT_PERSISTED_DOCUMENT_MAX_NODES
    max_documents: int = DEFAULT_PERSISTED_COLLECTION_MAX_DOCUMENTS
    max_total_bytes: int = DEFAULT_PERSISTED_COLLECTION_MAX_BYTES

    def __post_init__(self) -> None:
        for name, value in (
            ("max_bytes", self.max_bytes),
            ("max_depth", self.max_depth),
            ("max_nodes", self.max_nodes),
            ("max_documents", self.max_documents),
            ("max_total_bytes", self.max_total_bytes),
        ):
            if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
                raise ValueError(f"{name} must be a positive integer")


class _PersistedDocumentLimitError(ValueError):
    pass


class _PersistedCollectionLimitError(_PersistedDocumentLimitError):
    pass


@dataclass
class _PersistedReadBudget:
    """Mutable aggregate budget for one persisted collection read."""

    limits: PersistedDocumentLimits
    documents: int = 0
    total_bytes: int = 0

    def consume(self, encoded_bytes: int) -> None:
        if encoded_bytes < 0:
            raise _PersistedDocumentLimitError(
                "persisted JSON collection has an invalid encoded size"
            )

        next_documents = self.documents + 1
        if next_documents > self.limits.max_documents:
            raise _PersistedCollectionLimitError(
                "persisted JSON collection exceeds the configured document limit"
            )

        next_total_bytes = self.total_bytes + encoded_bytes
        if next_total_bytes > self.limits.max_total_bytes:
            raise _PersistedCollectionLimitError(
                "persisted JSON collection exceeds the configured cumulative byte limit"
            )

        self.documents = next_documents
        self.total_bytes = next_total_bytes


def _resolve_persisted_document_limits(
    limits: PersistedDocumentLimits | None,
) -> PersistedDocumentLimits:
    if limits is None:
        return PersistedDocumentLimits()
    if not isinstance(limits, PersistedDocumentLimits):
        raise TypeError("document_limits must be PersistedDocumentLimits or None")
    return limits


def _validate_persisted_document_size(
    encoded_bytes: int,
    *,
    limits: PersistedDocumentLimits,
) -> None:
    if encoded_bytes < 0:
        raise _PersistedDocumentLimitError(
            "persisted JSON document has an invalid encoded size"
        )
    if encoded_bytes > limits.max_bytes:
        raise _PersistedDocumentLimitError(
            "persisted JSON document exceeds the configured byte limit"
        )


def _validate_persisted_json_document(
    document: str,
    *,
    limits: PersistedDocumentLimits,
    encoded_bytes: int | None = None,
) -> None:
    """Bound JSON size/depth/token work before a recursive model decoder runs.

    This intentionally validates only resource complexity. JSON syntax and model
    semantics remain authoritative in the downstream Pydantic decoder.
    """

    if not isinstance(document, str):
        raise _PersistedDocumentLimitError(
            "persisted JSON document is not text"
        )

    if encoded_bytes is None:
        encoded_bytes = len(document.encode("utf-8"))
    _validate_persisted_document_size(encoded_bytes, limits=limits)

    depth = 0
    nodes = 0
    index = 0
    length = len(document)
    delimiters = " \t\r\n,]}:"

    while index < length:
        char = document[index]

        if char in " \t\r\n,:":
            index += 1
            continue

        if char == '"':
            nodes += 1
            if nodes > limits.max_nodes:
                raise _PersistedDocumentLimitError(
                    "persisted JSON document exceeds the configured node limit"
                )
            index += 1
            while index < length:
                current = document[index]
                if current == "\\":
                    index += 2
                    continue
                index += 1
                if current == '"':
                    break
            continue

        if char in "[{":
            nodes += 1
            if nodes > limits.max_nodes:
                raise _PersistedDocumentLimitError(
                    "persisted JSON document exceeds the configured node limit"
                )
            depth += 1
            if depth > limits.max_depth:
                raise _PersistedDocumentLimitError(
                    "persisted JSON document exceeds the configured depth limit"
                )
            index += 1
            continue

        if char in "]}":
            if depth > 0:
                depth -= 1
            index += 1
            continue

        nodes += 1
        if nodes > limits.max_nodes:
            raise _PersistedDocumentLimitError(
                "persisted JSON document exceeds the configured node limit"
            )
        index += 1
        while index < length and document[index] not in delimiters:
            index += 1


class StorageMigrationRecord(StrictModel):
    component: StorageComponent
    from_version: int = Field(ge=0)
    to_version: int = Field(ge=0)
    applied_at: str


class StorageComponentInspection(StrictModel):
    component: StorageComponent
    status: StorageStatus
    storage_format_version: int | None = None
    document_format_version: int | None = None
    current_storage_format_version: int = CURRENT_STORAGE_FORMAT_VERSION
    current_document_format_version: int
    document_count: int = Field(default=0, ge=0)
    migrations: list[StorageMigrationRecord] = Field(default_factory=list)

    @computed_field
    @property
    def migration_required(self) -> bool:
        return self.status == "legacy"


class StorageInspection(StrictModel):
    path: str
    components: list[StorageComponentInspection] = Field(default_factory=list)

    @computed_field
    @property
    def migration_required(self) -> bool:
        return any(component.migration_required for component in self.components)


class StorageMigrationResult(StrictModel):
    path: str
    backup_path: str | None = None
    before: StorageInspection
    after: StorageInspection


def ensure_storage_metadata_tables(connection: sqlite3.Connection) -> None:
    connection.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {_STORAGE_META_TABLE} (
            component TEXT NOT NULL,
            key TEXT NOT NULL,
            value TEXT NOT NULL,
            PRIMARY KEY (component, key)
        )
        """
    )
    connection.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {_STORAGE_MIGRATIONS_TABLE} (
            component TEXT NOT NULL,
            from_version INTEGER NOT NULL,
            to_version INTEGER NOT NULL,
            applied_at TEXT NOT NULL,
            PRIMARY KEY (component, to_version)
        )
        """
    )


def _table_names(connection: sqlite3.Connection) -> set[str]:
    rows = connection.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table'"
    ).fetchall()
    return {str(row[0]) for row in rows}


def _component_tables(component: StorageComponent) -> tuple[str, ...]:
    if component == "registry":
        return (
            "schemarouter_registry_meta",
            "schemarouter_registry_tools",
        )
    return (
        "schemarouter_trace_runs",
        "schemarouter_trace_events",
    )


def component_presence(
    connection: sqlite3.Connection,
    component: StorageComponent,
) -> Literal["absent", "complete", "partial"]:
    names = _table_names(connection)
    expected = set(_component_tables(component))
    present = expected & names
    if not present:
        if _STORAGE_META_TABLE in names:
            row = connection.execute(
                f"""
                SELECT 1
                FROM {_STORAGE_META_TABLE}
                WHERE component = ?
                LIMIT 1
                """,
                (component,),
            ).fetchone()
            if row is not None:
                return "partial"
        return "absent"
    if present == expected:
        return "complete"
    return "partial"


def _read_version_value(
    connection: sqlite3.Connection,
    component: StorageComponent,
    key: str,
) -> str | None:
    if _STORAGE_META_TABLE not in _table_names(connection):
        return None
    row = connection.execute(
        f"""
        SELECT value
        FROM {_STORAGE_META_TABLE}
        WHERE component = ? AND key = ?
        """,
        (component, key),
    ).fetchone()
    return None if row is None else str(row[0])


def _parse_nonnegative_version(
    raw: str | None,
    *,
    component: StorageComponent,
    key: str,
) -> int | None:
    if raw is None:
        return None
    try:
        value = int(raw)
    except (TypeError, ValueError) as exc:
        raise StorageFormatError(
            f"{component} storage metadata {key!r} is not an integer"
        ) from exc
    if value < 0:
        raise StorageFormatError(
            f"{component} storage metadata {key!r} must be non-negative"
        )
    return value


def component_versions(
    connection: sqlite3.Connection,
    component: StorageComponent,
) -> tuple[int | None, int | None]:
    storage = _parse_nonnegative_version(
        _read_version_value(
            connection,
            component,
            "storage_format_version",
        ),
        component=component,
        key="storage_format_version",
    )
    document = _parse_nonnegative_version(
        _read_version_value(
            connection,
            component,
            "document_format_version",
        ),
        component=component,
        key="document_format_version",
    )
    return storage, document


def current_document_version(component: StorageComponent) -> int:
    if component == "registry":
        return CURRENT_REGISTRY_DOCUMENT_VERSION
    return CURRENT_TRACE_DOCUMENT_VERSION


def component_status(
    connection: sqlite3.Connection,
    component: StorageComponent,
) -> StorageStatus:
    presence = component_presence(connection, component)
    if presence == "partial":
        return "corrupt"
    if presence == "absent":
        return "corrupt"

    try:
        storage_version, document_version = component_versions(
            connection,
            component,
        )
    except StorageFormatError:
        return "corrupt"

    # Both keys missing is the only supported pre-versioning v0 shape.
    if storage_version is None and document_version is None:
        return "legacy"
    if _STORAGE_MIGRATIONS_TABLE not in _table_names(connection):
        return "corrupt"
    if storage_version is None or document_version is None:
        return "corrupt"

    expected_document = current_document_version(component)
    if (
        storage_version > CURRENT_STORAGE_FORMAT_VERSION
        or document_version > expected_document
    ):
        return "future"
    if (
        storage_version < CURRENT_STORAGE_FORMAT_VERSION
        or document_version < expected_document
    ):
        return "legacy"
    return "current"


def migration_history(
    connection: sqlite3.Connection,
    component: StorageComponent,
) -> list[StorageMigrationRecord]:
    if _STORAGE_MIGRATIONS_TABLE not in _table_names(connection):
        return []
    rows = connection.execute(
        f"""
        SELECT component, from_version, to_version, applied_at
        FROM {_STORAGE_MIGRATIONS_TABLE}
        WHERE component = ?
        ORDER BY to_version
        """,
        (component,),
    ).fetchall()
    return [
        StorageMigrationRecord(
            component=component,
            from_version=int(row[1]),
            to_version=int(row[2]),
            applied_at=str(row[3]),
        )
        for row in rows
    ]


def stamp_current_component_format(
    connection: sqlite3.Connection,
    component: StorageComponent,
    *,
    from_version: int | None = None,
) -> None:
    """Write current component metadata inside the caller-owned transaction."""

    ensure_storage_metadata_tables(connection)
    connection.execute(
        f"""
        INSERT INTO {_STORAGE_META_TABLE} (component, key, value)
        VALUES (?, 'storage_format_version', ?)
        ON CONFLICT(component, key) DO UPDATE SET value = excluded.value
        """,
        (component, str(CURRENT_STORAGE_FORMAT_VERSION)),
    )
    connection.execute(
        f"""
        INSERT INTO {_STORAGE_META_TABLE} (component, key, value)
        VALUES (?, 'document_format_version', ?)
        ON CONFLICT(component, key) DO UPDATE SET value = excluded.value
        """,
        (component, str(current_document_version(component))),
    )
    if from_version is not None and from_version != CURRENT_STORAGE_FORMAT_VERSION:
        connection.execute(
            f"""
            INSERT OR REPLACE INTO {_STORAGE_MIGRATIONS_TABLE} (
                component,
                from_version,
                to_version,
                applied_at
            )
            VALUES (?, ?, ?, strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
            """,
            (
                component,
                from_version,
                CURRENT_STORAGE_FORMAT_VERSION,
            ),
        )


def validate_component_openable(
    connection: sqlite3.Connection,
    component: StorageComponent,
) -> StorageStatus:
    presence = component_presence(connection, component)
    if presence == "partial":
        raise StorageFormatError(
            f"{component} SQLite storage is incomplete; required tables are missing"
        )
    if presence == "absent":
        raise StorageFormatError(
            f"{component} SQLite storage is not present in this database"
        )

    try:
        storage_version, document_version = component_versions(
            connection,
            component,
        )
    except StorageFormatError:
        raise

    if storage_version is None and document_version is None:
        return "legacy"
    if _STORAGE_MIGRATIONS_TABLE not in _table_names(connection):
        raise StorageFormatError(
            f"{component} SQLite storage migration history table is missing"
        )
    if storage_version is None or document_version is None:
        raise StorageFormatError(
            f"{component} SQLite storage has incomplete format metadata; "
            "both storage_format_version and document_format_version are required"
        )

    expected_document = current_document_version(component)
    if storage_version > CURRENT_STORAGE_FORMAT_VERSION:
        raise StorageFormatError(
            f"{component} SQLite storage format {storage_version} is newer than "
            f"supported format {CURRENT_STORAGE_FORMAT_VERSION}; upgrade SchemaRouter"
        )
    if document_version > expected_document:
        raise StorageFormatError(
            f"{component} document format {document_version} is newer than "
            f"supported format {expected_document}; upgrade SchemaRouter"
        )
    if storage_version < CURRENT_STORAGE_FORMAT_VERSION:
        return "legacy"
    if document_version < expected_document:
        return "legacy"
    return "current"


def _document_count(
    connection: sqlite3.Connection,
    component: StorageComponent,
) -> int:
    table = (
        "schemarouter_registry_tools"
        if component == "registry"
        else "schemarouter_trace_events"
    )
    try:
        row = connection.execute(
            f"SELECT COUNT(*) FROM {table}"
        ).fetchone()
    except sqlite3.DatabaseError:
        return 0
    return 0 if row is None else int(row[0])


def _validate_component_documents(
    connection: sqlite3.Connection,
    component: StorageComponent,
    *,
    document_limits: PersistedDocumentLimits,
) -> None:
    # Local imports avoid module cycles. Future formats are never decoded by
    # this helper; callers invoke it only for current/legacy components.
    if component == "registry":
        from .registry import _validate_legacy_registry_storage

        _validate_legacy_registry_storage(
            connection,
            document_limits=document_limits,
        )
        return

    from .traces import _validate_legacy_trace_storage

    _validate_legacy_trace_storage(
        connection,
        document_limits=document_limits,
    )


def _inspect_sqlite_connection(
    connection: sqlite3.Connection,
    source: Path,
    *,
    document_limits: PersistedDocumentLimits,
) -> StorageInspection:
    names = _table_names(connection)
    components: list[StorageComponentInspection] = []
    for component in ("registry", "trace"):
        expected = set(_component_tables(component))
        if not (expected & names):
            continue

        status = component_status(connection, component)
        try:
            storage_version, document_version = component_versions(
                connection,
                component,
            )
        except StorageFormatError:
            storage_version = None
            document_version = None

        if status in {"current", "legacy"}:
            try:
                _validate_component_documents(
                    connection,
                    component,
                    document_limits=document_limits,
                )
            except (StorageFormatError, sqlite3.DatabaseError):
                status = "corrupt"

        components.append(
            StorageComponentInspection(
                component=component,
                status=status,
                storage_format_version=storage_version,
                document_format_version=document_version,
                current_document_format_version=current_document_version(
                    component
                ),
                document_count=_document_count(connection, component),
                migrations=migration_history(connection, component),
            )
        )
    return StorageInspection(
        path=str(source),
        components=components,
    )


def inspect_sqlite_storage(
    path: str | Path,
    *,
    document_limits: PersistedDocumentLimits | None = None,
) -> StorageInspection:
    limits = _resolve_persisted_document_limits(document_limits)
    source = Path(path)
    if not source.exists():
        raise StorageFormatError(f"SQLite storage does not exist: {source}")

    connection: sqlite3.Connection | None = None
    try:
        uri = f"file:{source.resolve().as_posix()}?mode=ro"
        connection = sqlite3.connect(uri, uri=True)
        connection.row_factory = sqlite3.Row
        return _inspect_sqlite_connection(
            connection,
            source,
            document_limits=limits,
        )
    except sqlite3.DatabaseError as exc:
        raise StorageFormatError(
            f"SQLite storage cannot be inspected safely: {source}"
        ) from exc
    finally:
        if connection is not None:
            connection.close()


def _publish_backup_destination(
    backup_path: Path,
    target: Path,
) -> None:
    """Publish a completed backup atomically without clobbering an existing path."""

    try:
        os.link(backup_path, target)
    except FileExistsError as exc:
        raise StorageFormatError(
            f"backup destination already exists: {target}"
        ) from exc
    except OSError as exc:
        if exc.errno in {errno.EEXIST, errno.ELOOP}:
            raise StorageFormatError(
                f"backup destination already exists or is unsafe: {target}"
            ) from exc
        raise StorageFormatError(
            f"backup destination cannot be published atomically: {target}"
        ) from exc


def _resolve_backup_target(
    source: Path,
    destination: str | Path | None,
) -> Path:
    target = (
        Path(destination)
        if destination is not None
        else source.with_name(source.name + ".schemarouter.bak")
    )
    if target.resolve() == source.resolve():
        raise StorageFormatError("backup destination must differ from source database")
    if not target.parent.exists():
        raise StorageFormatError(
            f"backup destination directory does not exist: {target.parent}"
        )
    # Fast fail for the normal existing-path case. Atomic hard-link publication
    # remains the concurrency authority, so a path created after this check is
    # still never overwritten.
    if os.path.lexists(target):
        raise StorageFormatError(
            f"backup destination already exists: {target}"
        )
    return target


def _backup_sqlite_connection(
    source_connection: sqlite3.Connection,
    source: Path,
    target: Path,
) -> Path:
    temporary_connection: sqlite3.Connection | None = None
    temporary_path: Path | None = None
    try:
        temporary_descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{target.name}.",
            suffix=".schemarouter-backup.tmp",
            dir=target.parent,
        )
        os.close(temporary_descriptor)
        temporary_path = Path(temporary_name)

        temporary_connection = sqlite3.connect(temporary_path)
        source_connection.backup(temporary_connection)
        temporary_connection.close()
        temporary_connection = None

        # Ensure the completed temporary database reaches the filesystem before it
        # becomes visible at the caller-selected destination.
        with temporary_path.open("rb+") as backup_file:
            os.fsync(backup_file.fileno())

        _publish_backup_destination(temporary_path, target)
    except StorageFormatError:
        raise
    except (sqlite3.DatabaseError, OSError) as exc:
        raise StorageFormatError(
            f"SQLite backup failed: {source} -> {target}"
        ) from exc
    finally:
        if temporary_connection is not None:
            temporary_connection.close()
        if temporary_path is not None:
            try:
                temporary_path.unlink()
            except FileNotFoundError:
                pass
            except OSError:
                pass

    return target


def backup_sqlite_storage(
    path: str | Path,
    destination: str | Path | None = None,
) -> Path:
    source = Path(path)
    if not source.exists():
        raise StorageFormatError(f"SQLite storage does not exist: {source}")
    target = _resolve_backup_target(source, destination)

    source_connection: sqlite3.Connection | None = None
    try:
        source_connection = sqlite3.connect(
            f"file:{source.resolve().as_posix()}?mode=ro",
            uri=True,
        )
        return _backup_sqlite_connection(
            source_connection,
            source,
            target,
        )
    except StorageFormatError:
        raise
    except sqlite3.DatabaseError as exc:
        raise StorageFormatError(
            f"SQLite backup failed: {source} -> {target}"
        ) from exc
    finally:
        if source_connection is not None:
            source_connection.close()


def migrate_sqlite_storage(
    path: str | Path,
    *,
    backup: bool = True,
    backup_path: str | Path | None = None,
    document_limits: PersistedDocumentLimits | None = None,
) -> StorageMigrationResult:
    if not backup and backup_path is not None:
        raise StorageFormatError(
            "backup_path cannot be supplied when backup=False"
        )

    limits = _resolve_persisted_document_limits(document_limits)
    source = Path(path)
    if not source.exists():
        raise StorageFormatError(f"SQLite storage does not exist: {source}")

    created_backup: Path | None = None
    before: StorageInspection | None = None
    connection = sqlite3.connect(
        source,
        timeout=_SQLITE_MIGRATION_LOCK_TIMEOUT_SECONDS,
    )
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    try:
        # BEGIN IMMEDIATE is the cross-process migration exclusion boundary.
        # Once it succeeds, no other writer can commit until this transaction
        # ends. Inspection, validation, backup, and version stamping therefore
        # all describe one coherent pre-migration database state.
        try:
            connection.execute("BEGIN IMMEDIATE")
        except sqlite3.OperationalError as exc:
            message = str(exc).casefold()
            if "locked" in message or "busy" in message:
                raise StorageFormatError(
                    "SQLite storage migration could not acquire the writer lock "
                    f"within {_SQLITE_MIGRATION_LOCK_TIMEOUT_SECONDS:g} seconds: "
                    f"{source}"
                ) from exc
            raise

        before = _inspect_sqlite_connection(
            connection,
            source,
            document_limits=limits,
        )
        if not before.components:
            raise StorageFormatError(
                "no SchemaRouter SQLite storage components were found"
            )
        if any(
            component.status in {"future", "corrupt"}
            for component in before.components
        ):
            details = ", ".join(
                f"{component.component}={component.status}"
                for component in before.components
                if component.status in {"future", "corrupt"}
            )
            raise StorageFormatError(
                "storage migration refused because component metadata is not safely "
                f"migratable: {details}"
            )

        if not before.migration_required:
            connection.rollback()
            return StorageMigrationResult(
                path=str(path),
                before=before,
                after=before,
            )

        legacy = {
            component.component
            for component in before.components
            if component.migration_required
        }

        # Re-run the authoritative legacy validators while the writer lock is held.
        # The inspection above is also lock-scoped, but keeping these checks here
        # makes the validation-before-stamp invariant explicit.
        if "registry" in legacy:
            from .registry import _validate_legacy_registry_storage

            _validate_legacy_registry_storage(
                connection,
                document_limits=limits,
            )
        if "trace" in legacy:
            from .traces import _validate_legacy_trace_storage

            _validate_legacy_trace_storage(
                connection,
                document_limits=limits,
            )

        if backup:
            target = _resolve_backup_target(source, backup_path)
            backup_source_connection: sqlite3.Connection | None = None
            try:
                # Python's sqlite3 backup API cannot make progress when invoked on
                # the same connection that owns an active write transaction. A
                # second read-only source connection is therefore used while the
                # BEGIN IMMEDIATE writer lock remains held by `connection`.
                # Because no other writer can commit, this online backup is the
                # exact committed state validated above.
                backup_source_connection = sqlite3.connect(
                    f"file:{source.resolve().as_posix()}?mode=ro",
                    uri=True,
                )
                created_backup = _backup_sqlite_connection(
                    backup_source_connection,
                    source,
                    target,
                )
            finally:
                if backup_source_connection is not None:
                    backup_source_connection.close()

        for component in ("registry", "trace"):
            if component in legacy:
                stamp_current_component_format(
                    connection,
                    component,
                    from_version=0,
                )
    except Exception:
        if connection.in_transaction:
            connection.rollback()
        raise
    else:
        connection.commit()
    finally:
        connection.close()

    # before is guaranteed once BEGIN IMMEDIATE succeeds and migration reaches
    # this point; the assertion keeps that invariant visible to type checkers.
    assert before is not None
    after = inspect_sqlite_storage(
        path,
        document_limits=limits,
    )
    return StorageMigrationResult(
        path=str(path),
        backup_path=(
            str(created_backup)
            if created_backup is not None
            else None
        ),
        before=before,
        after=after,
    )
