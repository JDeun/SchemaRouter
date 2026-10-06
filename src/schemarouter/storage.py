from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any, Literal

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


class PersistedDocumentLimits(StrictModel):
    """Safety envelope for one persisted SQLite JSON document."""

    max_bytes: int = Field(default=8 * 1024 * 1024, ge=1)
    max_depth: int = Field(default=128, ge=1)
    max_nodes: int = Field(default=100_000, ge=1)


def _decode_persisted_json(
    document: str,
    *,
    limits: PersistedDocumentLimits,
) -> Any:
    """Decode one persisted JSON document under explicit byte/structure budgets."""

    try:
        encoded_size = len(document.encode("utf-8"))
    except UnicodeError as exc:
        raise ValueError("persisted JSON document is not valid UTF-8 text") from exc
    if encoded_size > limits.max_bytes:
        raise ValueError(
            "persisted JSON document exceeds "
            f"max_bytes={limits.max_bytes}"
        )

    try:
        payload = json.loads(document)
    except (json.JSONDecodeError, RecursionError, MemoryError) as exc:
        raise ValueError("persisted JSON document cannot be decoded safely") from exc

    stack: list[tuple[Any, int]] = [(payload, 1)]
    nodes = 0
    while stack:
        value, depth = stack.pop()
        nodes += 1
        if nodes > limits.max_nodes:
            raise ValueError(
                "persisted JSON document exceeds "
                f"max_nodes={limits.max_nodes}"
            )
        if depth > limits.max_depth:
            raise ValueError(
                "persisted JSON document exceeds "
                f"max_depth={limits.max_depth}"
            )
        if isinstance(value, dict):
            stack.extend((child, depth + 1) for child in value.values())
        elif isinstance(value, list):
            stack.extend((child, depth + 1) for child in value)

    return payload


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


def inspect_sqlite_storage(
    path: str | Path,
    *,
    document_limits: PersistedDocumentLimits | None = None,
) -> StorageInspection:
    limits = (
        document_limits.model_copy(deep=True)
        if document_limits is not None
        else PersistedDocumentLimits()
    )
    source = Path(path)
    if not source.exists():
        raise StorageFormatError(f"SQLite storage does not exist: {source}")

    connection: sqlite3.Connection | None = None
    try:
        uri = f"file:{source.resolve().as_posix()}?mode=ro"
        connection = sqlite3.connect(uri, uri=True)
        connection.row_factory = sqlite3.Row
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
                        document_limits=limits,
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
    except sqlite3.DatabaseError as exc:
        raise StorageFormatError(
            f"SQLite storage cannot be inspected safely: {source}"
        ) from exc
    finally:
        if connection is not None:
            connection.close()


def backup_sqlite_storage(
    path: str | Path,
    destination: str | Path | None = None,
) -> Path:
    source = Path(path)
    if not source.exists():
        raise StorageFormatError(f"SQLite storage does not exist: {source}")
    target = (
        Path(destination)
        if destination is not None
        else source.with_name(source.name + ".schemarouter.bak")
    )
    if target.resolve() == source.resolve():
        raise StorageFormatError("backup destination must differ from source database")
    if target.exists():
        raise StorageFormatError(
            f"backup destination already exists: {target}"
        )
    if not target.parent.exists():
        raise StorageFormatError(
            f"backup destination directory does not exist: {target.parent}"
        )

    source_connection: sqlite3.Connection | None = None
    target_connection: sqlite3.Connection | None = None
    try:
        source_connection = sqlite3.connect(
            f"file:{source.resolve().as_posix()}?mode=ro",
            uri=True,
        )
        target_connection = sqlite3.connect(target)
        source_connection.backup(target_connection)
    except sqlite3.DatabaseError as exc:
        if target.exists():
            try:
                target.unlink()
            except OSError:
                pass
        raise StorageFormatError(
            f"SQLite backup failed: {source} -> {target}"
        ) from exc
    finally:
        if target_connection is not None:
            target_connection.close()
        if source_connection is not None:
            source_connection.close()
    return target


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

    limits = (
        document_limits.model_copy(deep=True)
        if document_limits is not None
        else PersistedDocumentLimits()
    )
    before = inspect_sqlite_storage(
        path,
        document_limits=limits,
    )
    if not before.components:
        raise StorageFormatError(
            "no SchemaRouter SQLite storage components were found"
        )
    if any(component.status in {"future", "corrupt"} for component in before.components):
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
        return StorageMigrationResult(
            path=str(path),
            before=before,
            after=before,
        )

    created_backup: Path | None = None
    if backup:
        created_backup = backup_sqlite_storage(path, backup_path)

    legacy = {
        component.component
        for component in before.components
        if component.migration_required
    }

    # Explicit migration is database-atomic across all detected components:
    # first validate every legacy component, then stamp all component metadata
    # in the same BEGIN IMMEDIATE transaction.
    source = Path(path)
    connection = sqlite3.connect(source)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    try:
        connection.execute("BEGIN IMMEDIATE")

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

        for component in ("registry", "trace"):
            if component in legacy:
                stamp_current_component_format(
                    connection,
                    component,
                    from_version=0,
                )
    except Exception:
        connection.rollback()
        raise
    else:
        connection.commit()
    finally:
        connection.close()

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

