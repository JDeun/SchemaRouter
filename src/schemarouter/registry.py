from __future__ import annotations

import sqlite3
from collections.abc import Iterable
from pathlib import Path
from threading import RLock
from typing import Protocol

from pydantic import ValidationError

from .errors import RegistrationError
from .models import EndpointSpec, ToolSpec


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


class InMemoryRegistry:
    """Versioned, collision-safe in-memory tool catalog with snapshot reads."""

    def __init__(self) -> None:
        self._tools: dict[str, ToolSpec] = {}
        self._version = 0

    @property
    def version(self) -> int:
        return self._version

    @staticmethod
    def _snapshot(tool: ToolSpec) -> ToolSpec:
        return tool.model_copy(deep=True)

    def register(self, tool: ToolSpec, *, replace: bool = False) -> str:
        key = tool.key
        if key in self._tools and not replace:
            raise RegistrationError(f"tool {key!r} is already registered")
        self._tools[key] = self._snapshot(tool)
        self._version += 1
        return key

    def unregister(self, key: str) -> None:
        if key not in self._tools:
            raise KeyError(key)
        del self._tools[key]
        self._version += 1

    def get(self, key: str) -> ToolSpec:
        return self._snapshot(self._tools[key])

    def tools(self) -> tuple[ToolSpec, ...]:
        return tuple(self._snapshot(tool) for tool in self._tools.values())

    def keys(self) -> tuple[str, ...]:
        return tuple(self._tools)

    def endpoint(self, tool_key: str, endpoint_name: str) -> EndpointSpec:
        return self.get(tool_key).endpoint(endpoint_name)

    def update_many(self, tools: Iterable[ToolSpec], *, replace: bool = False) -> None:
        staged = list(tools)
        staged_keys = [tool.key for tool in staged]
        if len(staged_keys) != len(set(staged_keys)):
            raise RegistrationError("duplicate tool keys in batch")
        if not replace:
            collisions = sorted(set(staged_keys) & set(self._tools))
            if collisions:
                raise RegistrationError(f"tools already registered: {', '.join(collisions)}")
        for tool in staged:
            self._tools[tool.key] = self._snapshot(tool)
        if staged:
            self._version += 1



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
    ) -> None:
        if timeout <= 0:
            raise ValueError("timeout must be > 0")
        self.path = str(path)
        self._lock = RLock()
        self._closed = False
        self._connection = sqlite3.connect(
            self.path,
            timeout=timeout,
            check_same_thread=False,
        )
        self._connection.row_factory = sqlite3.Row
        self._connection.execute("PRAGMA foreign_keys = ON")
        self._connection.execute("PRAGMA busy_timeout = ?", (int(timeout * 1000),))
        if self.path != ":memory:":
            self._connection.execute("PRAGMA journal_mode = WAL")
        self._initialize()

    def _initialize(self) -> None:
        with self._lock, self._connection:
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

    def _ensure_open(self) -> None:
        if self._closed:
            raise RuntimeError("SQLiteRegistry is closed")

    @staticmethod
    def _serialize(tool: ToolSpec) -> str:
        try:
            return tool.model_dump_json()
        except Exception as exc:
            raise RegistrationError(
                f"tool {tool.key!r} cannot be serialized as persistent JSON"
            ) from exc

    @staticmethod
    def _deserialize(key: str, document: str) -> ToolSpec:
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
            row = self._connection.execute(
                "SELECT value FROM schemarouter_registry_meta WHERE key = 'version'"
            ).fetchone()
            if row is None:
                raise RegistrationError("registry version metadata is missing")
            return int(row["value"])

    def register(self, tool: ToolSpec, *, replace: bool = False) -> str:
        document = self._serialize(tool)
        with self._lock:
            self._begin_write()
            try:
                existing = self._connection.execute(
                    "SELECT position FROM schemarouter_registry_tools WHERE key = ?",
                    (tool.key,),
                ).fetchone()
                if existing is not None and not replace:
                    raise RegistrationError(f"tool {tool.key!r} is already registered")
                if existing is None:
                    self._connection.execute(
                        """
                        INSERT INTO schemarouter_registry_tools (key, position, document)
                        VALUES (?, ?, ?)
                        """,
                        (tool.key, self._next_position(), document),
                    )
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
        return tool.key

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

    def update_many(self, tools: Iterable[ToolSpec], *, replace: bool = False) -> None:
        staged = list(tools)
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
