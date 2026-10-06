from __future__ import annotations

import errno
import os
import sqlite3
import tempfile
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
) -> None:
    # Local imports avoid module cycles. Future formats are never decoded by
    # this helper; callers invoke it only for current/legacy components.
    if component == "registry":
        from .registry import _validate_legacy_registry_storage

        _validate_legacy_registry_storage(connection)
        return

    from .traces import _validate_legacy_trace_storage

    _validate_legacy_trace_storage(connection)


def inspect_sqlite_storage(path: str | Path) -> StorageInspection:
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
                    _validate_component_documents(connection, component)
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


def _reserve_backup_destination(target: Path) -> tuple[int, os.stat_result]:
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    flags |= getattr(os, "O_BINARY", 0)
    flags |= getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(target, flags, 0o600)
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
            f"backup destination cannot be reserved safely: {target}"
        ) from exc
    return descriptor, os.fstat(descriptor)


def _path_matches_reserved_destination(
    target: Path,
    reserved_stat: os.stat_result,
) -> bool:
    try:
        current = os.stat(target, follow_symlinks=False)
    except OSError:
        return False
    return os.path.samestat(current, reserved_stat)


def _copy_backup_to_reserved_destination(
    backup_path: Path,
    descriptor: int,
) -> None:
    os.lseek(descriptor, 0, os.SEEK_SET)
    os.ftruncate(descriptor, 0)
    with backup_path.open("rb") as source_file:
        while True:
            chunk = source_file.read(1024 * 1024)
            if not chunk:
                break
            view = memoryview(chunk)
            while view:
                written = os.write(descriptor, view)
                if written <= 0:
                    raise OSError("failed to write reserved backup destination")
                view = view[written:]
    os.fsync(descriptor)


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
    if not target.parent.exists():
        raise StorageFormatError(
            f"backup destination directory does not exist: {target.parent}"
        )

    target_descriptor, reserved_stat = _reserve_backup_destination(target)
    source_connection: sqlite3.Connection | None = None
    temporary_connection: sqlite3.Connection | None = None
    temporary_path: Path | None = None
    completed = False
    try:
        temporary_descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{target.name}.",
            suffix=".schemarouter-backup.tmp",
            dir=target.parent,
        )
        os.close(temporary_descriptor)
        temporary_path = Path(temporary_name)

        source_connection = sqlite3.connect(
            f"file:{source.resolve().as_posix()}?mode=ro",
            uri=True,
        )
        temporary_connection = sqlite3.connect(temporary_path)
        source_connection.backup(temporary_connection)
        temporary_connection.close()
        temporary_connection = None

        _copy_backup_to_reserved_destination(
            temporary_path,
            target_descriptor,
        )
        if not _path_matches_reserved_destination(target, reserved_stat):
            raise StorageFormatError(
                "backup destination changed while the backup was being created"
            )
        completed = True
    except StorageFormatError:
        raise
    except (sqlite3.DatabaseError, OSError) as exc:
        raise StorageFormatError(
            f"SQLite backup failed: {source} -> {target}"
        ) from exc
    finally:
        if temporary_connection is not None:
            temporary_connection.close()
        if source_connection is not None:
            source_connection.close()
        if temporary_path is not None:
            try:
                temporary_path.unlink()
            except FileNotFoundError:
                pass
            except OSError:
                pass

        # Close the reservation handle before path-identity cleanup. On Windows,
        # unlinking/replacing an open file can remain pending until the last handle
        # closes; checking the pathname while our reservation handle is still open
        # can therefore misidentify a concurrently-created replacement as ours.
        os.close(target_descriptor)
        try:
            if (
                not completed
                and _path_matches_reserved_destination(target, reserved_stat)
            ):
                target.unlink()
        except OSError:
            pass

    return target


def migrate_sqlite_storage(
    path: str | Path,
    *,
    backup: bool = True,
    backup_path: str | Path | None = None,
) -> StorageMigrationResult:
    if not backup and backup_path is not None:
        raise StorageFormatError(
            "backup_path cannot be supplied when backup=False"
        )

    before = inspect_sqlite_storage(path)
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

            _validate_legacy_registry_storage(connection)
        if "trace" in legacy:
            from .traces import _validate_legacy_trace_storage

            _validate_legacy_trace_storage(connection)

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

    after = inspect_sqlite_storage(path)
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

