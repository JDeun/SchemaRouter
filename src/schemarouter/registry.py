from __future__ import annotations

import sqlite3
from collections.abc import Iterable
from pathlib import Path
from threading import RLock
from typing import Protocol

from pydantic import ValidationError

from .errors import RegistrationError, StorageFormatError
from .models import EndpointSpec, ToolSpec
from .persistence_limits import (
    PersistedDocumentLimitError,
    PersistedDocumentLimits,
    validate_persisted_json_document,
)
from .storage import (
    component_presence,
    component_versions,
    stamp_current_component_format,
    validate_component_openable,
)


def _validated_tool_snapshot(tool: ToolSpec) -> ToolSpec:
    """Revalidate mutable nested model state at the registry write boundary."""

    try:
        return ToolSpec.model_validate(tool.model_dump(mode="python"))
    except (ValidationError, ValueError, TypeError) as exc:
        raise RegistrationError(
            f"tool {tool.key!r} is not a valid ToolSpec at registration time"
        ) from exc


class ToolRegistry(Protocol):
    """Structural contract for pluggable tool registries.

    Read methods must return detached snapshots (or immutable equivalents) so callers cannot
    mutate registry state without going through a versioned write operation.
    """

    @property
    def version(self) -> int: ...

    def register(self, tool: ToolSpec, *, replace: bool = False) -> str: ...

    def get(self, key: str) -> ToolSpec: ...

    def tools(self) -> tuple[ToolSpec, ...]: ...

    def keys(self) -> tuple[str, ...]: ...

    def endpoint(self, tool_key: str, endpoint_name: str) -> EndpointSpec: ...


class BatchToolRegistry(ToolRegistry, Protocol):
    """Optional registry capability for atomic version-guarded batch registration."""

    def update_many_if_version(
        self,
        tools: Iterable[ToolSpec],
        *,
        expected_version: int,
        replace: bool = False,
    ) -> tuple[str, ...]: ...


def update_many_if_current(
    registry: ToolRegistry,
    tools: Iterable[ToolSpec],
    *,
    expected_version: int,
    replace: bool = False,
) -> tuple[str, ...]:
    """Atomically apply a staged tool batch only to the captured registry version."""

    update = getattr(registry, "update_many_if_version", None)
    if not callable(update):
        raise RegistrationError(
            "registry does not support atomic version-guarded batch registration; "
            "this operation requires BatchToolRegistry semantics"
        )
    result = update(
        tools,
        expected_version=expected_version,
        replace=replace,
    )
    if not isinstance(result, tuple) or not all(
        isinstance(key, str) for key in result
    ):
        raise RegistrationError(
            "atomic version-guarded batch registration returned invalid tool keys"
        )
    return result


class MutableToolRegistry(ToolRegistry, Protocol):
    """Optional registry capability for atomic remove-if-current semantics."""

    def unregister_if_fingerprint(
        self,
        key: str,
        *,
        expected_fingerprint: str,
        expected_version: int,
    ) -> None: ...


def unregister_if_current(
    registry: ToolRegistry,
    key: str,
    *,
    expected_fingerprint: str,
    expected_version: int,
) -> None:
    """Atomically remove a tool only while the caller still owns its snapshot."""

    unregister = getattr(registry, "unregister_if_fingerprint", None)
    if not callable(unregister):
        raise RegistrationError(
            "registry does not support atomic unregister-if-fingerprint; "
            "this operation requires MutableToolRegistry semantics"
        )
    unregister(
        key,
        expected_fingerprint=expected_fingerprint,
        expected_version=expected_version,
    )


class CompareAndSwapToolRegistry(ToolRegistry, Protocol):
    """Optional registry capability for atomic replace-if-current semantics."""

    def replace_if_fingerprint(
        self,
        tool: ToolSpec,
        *,
        expected_fingerprint: str,
        expected_version: int,
    ) -> str: ...


def replace_if_current(
    registry: ToolRegistry,
    tool: ToolSpec,
    *,
    expected_fingerprint: str,
    expected_version: int,
) -> str:
    """Use a registry's atomic CAS capability or fail closed.

    The base ToolRegistry protocol remains backward compatible for planning and
    ordinary registration. Operations that require lost-update protection must
    opt into this stronger capability instead of silently falling back to a
    non-atomic read-then-write sequence. The caller supplies both the exact
    tool fingerprint and the registry version captured before its snapshot read,
    so metadata-only or unrelated concurrent writes also fail closed.
    """
    replace = getattr(registry, "replace_if_fingerprint", None)
    if not callable(replace):
        raise RegistrationError(
            "registry does not support atomic replace-if-fingerprint; "
            "this operation requires CompareAndSwapToolRegistry semantics"
        )
    result = replace(
        tool,
        expected_fingerprint=expected_fingerprint,
        expected_version=expected_version,
    )
    if not isinstance(result, str):
        raise RegistrationError(
            "atomic replace-if-fingerprint returned a non-string tool key"
        )
    return result


class InMemoryRegistry:
    """Versioned, collision-safe in-memory tool catalog with snapshot reads."""

    def __init__(self) -> None:
        self._tools: dict[str, ToolSpec] = {}
        self._version = 0
        self._lock = RLock()

    @property
    def version(self) -> int:
        with self._lock:
            return self._version

    @staticmethod
    def _snapshot(tool: ToolSpec) -> ToolSpec:
        return tool.model_copy(deep=True)

    def register(self, tool: ToolSpec, *, replace: bool = False) -> str:
        validated = _validated_tool_snapshot(tool)
        key = validated.key
        with self._lock:
            if key in self._tools and not replace:
                raise RegistrationError(f"tool {key!r} is already registered")
            self._tools[key] = self._snapshot(validated)
            self._version += 1
        return key

    def replace_if_fingerprint(
        self,
        tool: ToolSpec,
        *,
        expected_fingerprint: str,
        expected_version: int,
    ) -> str:
        """Atomically replace one tool only if the caller still owns its snapshot."""
        validated = _validated_tool_snapshot(tool)
        key = validated.key
        with self._lock:
            if self._version != expected_version:
                raise RegistrationError(
                    f"registry changed concurrently; expected version "
                    f"{expected_version}, found {self._version}"
                )
            current = self._tools.get(key)
            if current is None:
                raise KeyError(key)
            if current.fingerprint != expected_fingerprint:
                raise RegistrationError(
                    f"tool {key!r} changed concurrently; expected fingerprint "
                    f"{expected_fingerprint!r}, found {current.fingerprint!r}"
                )
            self._tools[key] = self._snapshot(validated)
            self._version += 1
        return key

    def unregister_if_fingerprint(
        self,
        key: str,
        *,
        expected_fingerprint: str,
        expected_version: int,
    ) -> None:
        with self._lock:
            if self._version != expected_version:
                raise RegistrationError(
                    f"registry changed concurrently; expected version "
                    f"{expected_version}, found {self._version}"
                )
            current = self._tools.get(key)
            if current is None:
                raise KeyError(key)
            if current.fingerprint != expected_fingerprint:
                raise RegistrationError(
                    f"tool {key!r} changed concurrently; expected fingerprint "
                    f"{expected_fingerprint!r}, found {current.fingerprint!r}"
                )
            del self._tools[key]
            self._version += 1

    def unregister(self, key: str) -> None:
        with self._lock:
            if key not in self._tools:
                raise KeyError(key)
            del self._tools[key]
            self._version += 1

    def get(self, key: str) -> ToolSpec:
        with self._lock:
            return self._snapshot(self._tools[key])

    def tools(self) -> tuple[ToolSpec, ...]:
        with self._lock:
            return tuple(self._snapshot(tool) for tool in self._tools.values())

    def keys(self) -> tuple[str, ...]:
        with self._lock:
            return tuple(self._tools)

    def endpoint(self, tool_key: str, endpoint_name: str) -> EndpointSpec:
        return self.get(tool_key).endpoint(endpoint_name)

    def unregister_many_if_version(
        self,
        expected: dict[str, str],
        *,
        expected_version: int,
    ) -> None:
        with self._lock:
            if self._version != expected_version:
                raise RegistrationError(
                    f"registry changed concurrently; expected version "
                    f"{expected_version}, found {self._version}"
                )
            for key, fingerprint in expected.items():
                current = self._tools.get(key)
                if current is None or current.fingerprint != fingerprint:
                    raise RegistrationError(
                        f"tool {key!r} changed before atomic batch rollback"
                    )
            for key in expected:
                del self._tools[key]
            if expected:
                self._version += 1

    def update_many_if_version(
        self,
        tools: Iterable[ToolSpec],
        *,
        expected_version: int,
        replace: bool = False,
    ) -> tuple[str, ...]:
        staged = [_validated_tool_snapshot(tool) for tool in tools]
        staged_keys = [tool.key for tool in staged]
        if len(staged_keys) != len(set(staged_keys)):
            raise RegistrationError("duplicate tool keys in batch")
        with self._lock:
            if self._version != expected_version:
                raise RegistrationError(
                    f"registry changed concurrently; expected version "
                    f"{expected_version}, found {self._version}"
                )
            if not replace:
                collisions = sorted(set(staged_keys) & set(self._tools))
                if collisions:
                    raise RegistrationError(
                        f"tools already registered: {', '.join(collisions)}"
                    )
            for tool in staged:
                self._tools[tool.key] = self._snapshot(tool)
            if staged:
                self._version += 1
        return tuple(staged_keys)

    def update_many(self, tools: Iterable[ToolSpec], *, replace: bool = False) -> None:
        staged = [_validated_tool_snapshot(tool) for tool in tools]
        staged_keys = [tool.key for tool in staged]
        if len(staged_keys) != len(set(staged_keys)):
            raise RegistrationError("duplicate tool keys in batch")
        with self._lock:
            if not replace:
                collisions = sorted(set(staged_keys) & set(self._tools))
                if collisions:
                    raise RegistrationError(
                        f"tools already registered: {', '.join(collisions)}"
                    )
            for tool in staged:
                self._tools[tool.key] = self._snapshot(tool)
            if staged:
                self._version += 1


def _validate_legacy_registry_storage(
    connection: sqlite3.Connection,
    *,
    document_limits: PersistedDocumentLimits | None = None,
) -> None:
    limits = document_limits or PersistedDocumentLimits()
    try:
        row = connection.execute(
            "SELECT value FROM schemarouter_registry_meta WHERE key = 'version'"
        ).fetchone()
    except sqlite3.DatabaseError as exc:
        raise StorageFormatError(
            "legacy registry metadata table shape is not compatible with migration"
        ) from exc
    if row is None:
        raise StorageFormatError("registry logical version metadata is missing")
    try:
        version = int(row["value"])
    except (TypeError, ValueError) as exc:
        raise StorageFormatError(
            "registry logical version metadata is not an integer"
        ) from exc
    if version < 0:
        raise StorageFormatError(
            "registry logical version metadata must be non-negative"
        )

    try:
        rows = connection.execute(
            """
            SELECT key, position, document
            FROM schemarouter_registry_tools
            ORDER BY position
            """
        ).fetchall()
    except sqlite3.DatabaseError as exc:
        raise StorageFormatError(
            "legacy registry table shape is not compatible with migration"
        ) from exc

    seen_positions: set[int] = set()
    for stored in rows:
        key = str(stored["key"])
        try:
            position = int(stored["position"])
        except (TypeError, ValueError) as exc:
            raise StorageFormatError(
                f"stored tool {key!r} has an invalid registry position"
            ) from exc
        if position < 0 or position in seen_positions:
            raise StorageFormatError(
                f"stored tool {key!r} has an invalid registry position"
            )
        seen_positions.add(position)

        document = str(stored["document"])
        try:
            validate_persisted_json_document(document, limits)
        except PersistedDocumentLimitError as exc:
            raise StorageFormatError(
                f"legacy stored tool {key!r} exceeds persisted document safety limits"
            ) from exc
        try:
            tool = ToolSpec.model_validate_json(document)
        except (ValidationError, ValueError) as exc:
            raise StorageFormatError(
                f"legacy stored tool {key!r} cannot be migrated safely"
            ) from exc
        if tool.key != key:
            raise StorageFormatError(
                f"legacy stored tool key mismatch: row={key!r}, "
                f"document={tool.key!r}"
            )


class SQLiteRegistry:
    """Persistent versioned tool catalog backed by SQLite.

    Tool specifications are stored as Pydantic JSON rather than pickle so reopening a registry
    never imports or executes arbitrary Python objects. Writes use BEGIN IMMEDIATE transactions and
    bump the registry version exactly once per successful logical mutation.
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
        self._document_limits = document_limits or PersistedDocumentLimits()
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
            CREATE TABLE IF NOT EXISTS schemarouter_registry_meta (
                key TEXT PRIMARY KEY,
                value INTEGER NOT NULL
            )
            """
        )
        self._connection.execute(
            """
            INSERT OR IGNORE INTO schemarouter_registry_meta (key, value)
            VALUES ('version', 0)
            """
        )
        self._connection.execute(
            """
            CREATE TABLE IF NOT EXISTS schemarouter_registry_tools (
                key TEXT PRIMARY KEY,
                position INTEGER NOT NULL UNIQUE,
                document TEXT NOT NULL
            )
            """
        )

    def _validated_logical_version(self) -> int:
        row = self._connection.execute(
            "SELECT value FROM schemarouter_registry_meta WHERE key = 'version'"
        ).fetchone()
        if row is None:
            raise StorageFormatError(
                "registry logical version metadata is missing"
            )
        try:
            version = int(row["value"])
        except (TypeError, ValueError) as exc:
            raise StorageFormatError(
                "registry logical version metadata is not an integer"
            ) from exc
        if version < 0:
            raise StorageFormatError(
                "registry logical version metadata must be non-negative"
            )
        return version

    def _validate_legacy_storage(self) -> None:
        _validate_legacy_registry_storage(
            self._connection,
            document_limits=self._document_limits,
        )

    def _initialize(self) -> None:
        with self._lock:
            presence = component_presence(self._connection, "registry")
            if presence == "partial":
                raise StorageFormatError(
                    "registry SQLite storage is incomplete; required tables are missing"
                )

            if presence == "absent":
                self._connection.execute("BEGIN IMMEDIATE")
                try:
                    self._create_component_tables()
                    stamp_current_component_format(
                        self._connection,
                        "registry",
                    )
                except Exception:
                    self._connection.rollback()
                    raise
                else:
                    self._connection.commit()
                return

            status = validate_component_openable(
                self._connection,
                "registry",
            )
            if status == "current":
                self._validated_logical_version()
                return

            # v0 -> v1 only stamps compatibility metadata after every stored
            # ToolSpec has been validated. Logical registry version/order and
            # serialized documents remain untouched.
            self._connection.execute("BEGIN IMMEDIATE")
            try:
                self._validate_legacy_storage()
                stamp_current_component_format(
                    self._connection,
                    "registry",
                    from_version=0,
                )
            except Exception:
                self._connection.rollback()
                raise
            else:
                self._connection.commit()

    def _ensure_open(self) -> None:
        if self._closed:
            raise RuntimeError("SQLiteRegistry is closed")

    def _serialize(self, tool: ToolSpec) -> str:
        try:
            document = tool.model_dump_json()
        except Exception as exc:
            raise RegistrationError(
                f"tool {tool.key!r} cannot be serialized as persistent JSON"
            ) from exc
        try:
            validate_persisted_json_document(document, self._document_limits)
        except PersistedDocumentLimitError as exc:
            raise RegistrationError(
                f"tool {tool.key!r} exceeds persisted document safety limits"
            ) from exc
        return document

    def _deserialize(self, key: str, document: str) -> ToolSpec:
        try:
            validate_persisted_json_document(document, self._document_limits)
        except PersistedDocumentLimitError as exc:
            raise RegistrationError(
                f"stored tool {key!r} exceeds persisted document safety limits"
            ) from exc
        try:
            tool = ToolSpec.model_validate_json(document)
        except (ValidationError, ValueError) as exc:
            raise RegistrationError(
                f"stored tool {key!r} is not a valid ToolSpec"
            ) from exc
        if tool.key != key:
            raise RegistrationError(
                f"stored tool key mismatch: row={key!r}, document={tool.key!r}"
            )
        return tool

    def _begin_write(self) -> None:
        self._ensure_open()
        self._connection.execute("BEGIN IMMEDIATE")

    def _bump_version(self) -> None:
        self._connection.execute(
            """
            UPDATE schemarouter_registry_meta
            SET value = value + 1
            WHERE key = 'version'
            """
        )

    def _next_position(self) -> int:
        row = self._connection.execute(
            "SELECT COALESCE(MAX(position), -1) + 1 AS next_position "
            "FROM schemarouter_registry_tools"
        ).fetchone()
        return int(row["next_position"])

    @property
    def version(self) -> int:
        with self._lock:
            self._ensure_open()
            return self._validated_logical_version()

    @property
    def storage_format_version(self) -> int:
        with self._lock:
            self._ensure_open()
            storage_version, _ = component_versions(
                self._connection,
                "registry",
            )
            if storage_version is None:
                raise StorageFormatError(
                    "registry storage format metadata is missing"
                )
            return storage_version

    @property
    def document_format_version(self) -> int:
        with self._lock:
            self._ensure_open()
            _, document_version = component_versions(
                self._connection,
                "registry",
            )
            if document_version is None:
                raise StorageFormatError(
                    "registry document format metadata is missing"
                )
            return document_version

    def register(self, tool: ToolSpec, *, replace: bool = False) -> str:
        validated = _validated_tool_snapshot(tool)
        document = self._serialize(validated)
        with self._lock:
            self._begin_write()
            try:
                existing = self._connection.execute(
                    "SELECT position FROM schemarouter_registry_tools WHERE key = ?",
                    (validated.key,),
                ).fetchone()
                if existing is not None and not replace:
                    raise RegistrationError(f"tool {validated.key!r} is already registered")
                if existing is None:
                    self._connection.execute(
                        """
                        INSERT INTO schemarouter_registry_tools (key, position, document)
                        VALUES (?, ?, ?)
                        """,
                        (validated.key, self._next_position(), document),
                    )
                else:
                    self._connection.execute(
                        """
                        UPDATE schemarouter_registry_tools
                        SET document = ?
                        WHERE key = ?
                        """,
                        (document, validated.key),
                    )
                self._bump_version()
            except Exception:
                self._connection.rollback()
                raise
            else:
                self._connection.commit()
        return validated.key

    def replace_if_fingerprint(
        self,
        tool: ToolSpec,
        *,
        expected_fingerprint: str,
        expected_version: int,
    ) -> str:
        """Atomically replace one persisted tool if its fingerprint and version match."""
        validated = _validated_tool_snapshot(tool)
        document = self._serialize(validated)
        with self._lock:
            self._begin_write()
            try:
                version_row = self._connection.execute(
                    "SELECT value FROM schemarouter_registry_meta WHERE key = 'version'"
                ).fetchone()
                if version_row is None:
                    raise RegistrationError("registry version metadata is missing")
                current_version = int(version_row["value"])
                if current_version != expected_version:
                    raise RegistrationError(
                        f"registry changed concurrently; expected version "
                        f"{expected_version}, found {current_version}"
                    )
                row = self._connection.execute(
                    "SELECT document FROM schemarouter_registry_tools WHERE key = ?",
                    (validated.key,),
                ).fetchone()
                if row is None:
                    raise KeyError(validated.key)
                current = self._deserialize(validated.key, str(row["document"]))
                if current.fingerprint != expected_fingerprint:
                    raise RegistrationError(
                        f"tool {validated.key!r} changed concurrently; expected "
                        f"fingerprint {expected_fingerprint!r}, found "
                        f"{current.fingerprint!r}"
                    )
                self._connection.execute(
                    """
                    UPDATE schemarouter_registry_tools
                    SET document = ?
                    WHERE key = ?
                    """,
                    (document, validated.key),
                )
                self._bump_version()
            except Exception:
                self._connection.rollback()
                raise
            else:
                self._connection.commit()
        return validated.key

    def unregister_if_fingerprint(
        self,
        key: str,
        *,
        expected_fingerprint: str,
        expected_version: int,
    ) -> None:
        with self._lock:
            self._begin_write()
            try:
                version_row = self._connection.execute(
                    "SELECT value FROM schemarouter_registry_meta WHERE key = 'version'"
                ).fetchone()
                if version_row is None:
                    raise RegistrationError("registry version metadata is missing")
                current_version = int(version_row["value"])
                if current_version != expected_version:
                    raise RegistrationError(
                        f"registry changed concurrently; expected version "
                        f"{expected_version}, found {current_version}"
                    )
                row = self._connection.execute(
                    "SELECT document FROM schemarouter_registry_tools WHERE key = ?",
                    (key,),
                ).fetchone()
                if row is None:
                    raise KeyError(key)
                current = self._deserialize(key, str(row["document"]))
                if current.fingerprint != expected_fingerprint:
                    raise RegistrationError(
                        f"tool {key!r} changed concurrently; expected fingerprint "
                        f"{expected_fingerprint!r}, found {current.fingerprint!r}"
                    )
                self._connection.execute(
                    "DELETE FROM schemarouter_registry_tools WHERE key = ?",
                    (key,),
                )
                self._bump_version()
            except Exception:
                self._connection.rollback()
                raise
            else:
                self._connection.commit()

    def unregister(self, key: str) -> None:
        with self._lock:
            self._begin_write()
            try:
                cursor = self._connection.execute(
                    "DELETE FROM schemarouter_registry_tools WHERE key = ?",
                    (key,),
                )
                if cursor.rowcount == 0:
                    raise KeyError(key)
                self._bump_version()
            except Exception:
                self._connection.rollback()
                raise
            else:
                self._connection.commit()

    def get(self, key: str) -> ToolSpec:
        with self._lock:
            self._ensure_open()
            row = self._connection.execute(
                "SELECT document FROM schemarouter_registry_tools WHERE key = ?",
                (key,),
            ).fetchone()
            if row is None:
                raise KeyError(key)
            return self._deserialize(key, str(row["document"]))

    def tools(self) -> tuple[ToolSpec, ...]:
        with self._lock:
            self._ensure_open()
            rows = self._connection.execute(
                """
                SELECT key, document
                FROM schemarouter_registry_tools
                ORDER BY position
                """
            ).fetchall()
            return tuple(
                self._deserialize(str(row["key"]), str(row["document"]))
                for row in rows
            )

    def keys(self) -> tuple[str, ...]:
        with self._lock:
            self._ensure_open()
            rows = self._connection.execute(
                "SELECT key FROM schemarouter_registry_tools ORDER BY position"
            ).fetchall()
            return tuple(str(row["key"]) for row in rows)

    def endpoint(self, tool_key: str, endpoint_name: str) -> EndpointSpec:
        return self.get(tool_key).endpoint(endpoint_name)

    def unregister_many_if_version(
        self,
        expected: dict[str, str],
        *,
        expected_version: int,
    ) -> None:
        if not expected:
            return
        with self._lock:
            self._begin_write()
            try:
                current_version = self._validated_logical_version()
                if current_version != expected_version:
                    raise RegistrationError(
                        f"registry changed concurrently; expected version "
                        f"{expected_version}, found {current_version}"
                    )
                for key, fingerprint in expected.items():
                    row = self._connection.execute(
                        "SELECT document FROM schemarouter_registry_tools WHERE key = ?",
                        (key,),
                    ).fetchone()
                    if row is None:
                        raise RegistrationError(
                            f"tool {key!r} disappeared before atomic batch rollback"
                        )
                    current = self._deserialize(key, str(row["document"]))
                    if current.fingerprint != fingerprint:
                        raise RegistrationError(
                            f"tool {key!r} changed before atomic batch rollback"
                        )
                placeholders = ",".join("?" for _ in expected)
                self._connection.execute(
                    f"DELETE FROM schemarouter_registry_tools WHERE key IN ({placeholders})",
                    tuple(expected),
                )
                self._bump_version()
            except Exception:
                self._connection.rollback()
                raise
            else:
                self._connection.commit()

    def update_many_if_version(
        self,
        tools: Iterable[ToolSpec],
        *,
        expected_version: int,
        replace: bool = False,
    ) -> tuple[str, ...]:
        staged = [_validated_tool_snapshot(tool) for tool in tools]
        staged_keys = [tool.key for tool in staged]
        if len(staged_keys) != len(set(staged_keys)):
            raise RegistrationError("duplicate tool keys in batch")
        if not staged:
            return ()
        documents = [(tool, self._serialize(tool)) for tool in staged]

        with self._lock:
            self._begin_write()
            try:
                current_version = self._validated_logical_version()
                if current_version != expected_version:
                    raise RegistrationError(
                        f"registry changed concurrently; expected version "
                        f"{expected_version}, found {current_version}"
                    )
                placeholders = ",".join("?" for _ in staged_keys)
                existing_rows = self._connection.execute(
                    f"""
                    SELECT key, position
                    FROM schemarouter_registry_tools
                    WHERE key IN ({placeholders})
                    """,
                    staged_keys,
                ).fetchall()
                existing = {
                    str(row["key"]): int(row["position"])
                    for row in existing_rows
                }
                if existing and not replace:
                    collisions = sorted(existing)
                    raise RegistrationError(
                        f"tools already registered: {', '.join(collisions)}"
                    )
                next_position = self._next_position()
                for tool, document in documents:
                    position = existing.get(tool.key)
                    if position is None:
                        self._connection.execute(
                            """
                            INSERT INTO schemarouter_registry_tools (key, position, document)
                            VALUES (?, ?, ?)
                            """,
                            (tool.key, next_position, document),
                        )
                        next_position += 1
                    else:
                        self._connection.execute(
                            """
                            UPDATE schemarouter_registry_tools
                            SET document = ?
                            WHERE key = ?
                            """,
                            (document, tool.key),
                        )
                self._bump_version()
            except Exception:
                self._connection.rollback()
                raise
            else:
                self._connection.commit()
        return tuple(staged_keys)

    def update_many(self, tools: Iterable[ToolSpec], *, replace: bool = False) -> None:
        staged = [_validated_tool_snapshot(tool) for tool in tools]
        staged_keys = [tool.key for tool in staged]
        if len(staged_keys) != len(set(staged_keys)):
            raise RegistrationError("duplicate tool keys in batch")
        if not staged:
            return
        documents = [(tool, self._serialize(tool)) for tool in staged]

        with self._lock:
            self._begin_write()
            try:
                placeholders = ",".join("?" for _ in staged_keys)
                existing_rows = self._connection.execute(
                    f"""
                    SELECT key, position
                    FROM schemarouter_registry_tools
                    WHERE key IN ({placeholders})
                    """,
                    staged_keys,
                ).fetchall()
                existing = {
                    str(row["key"]): int(row["position"])
                    for row in existing_rows
                }
                if existing and not replace:
                    collisions = sorted(existing)
                    raise RegistrationError(
                        f"tools already registered: {', '.join(collisions)}"
                    )

                next_position = self._next_position()
                for tool, document in documents:
                    position = existing.get(tool.key)
                    if position is None:
                        self._connection.execute(
                            """
                            INSERT INTO schemarouter_registry_tools (key, position, document)
                            VALUES (?, ?, ?)
                            """,
                            (tool.key, next_position, document),
                        )
                        next_position += 1
                    else:
                        self._connection.execute(
                            """
                            UPDATE schemarouter_registry_tools
                            SET document = ?
                            WHERE key = ?
                            """,
                            (document, tool.key),
                        )
                self._bump_version()
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

    def __enter__(self) -> SQLiteRegistry:
        self._ensure_open()
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        self.close()
