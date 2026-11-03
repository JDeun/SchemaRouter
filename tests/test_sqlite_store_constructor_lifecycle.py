"""SQLite stores must close owned handles on every initialization failure.

Both stores own their connection as soon as sqlite3.connect returns. These
regressions deliberately fail in each PRAGMA stage, before _initialize is run.
No warnings are suppressed and no unrelated garbage collection is required.
"""
from __future__ import annotations

import sqlite3

import pytest

from schemarouter import SQLiteRegistry, SQLiteRunTraceStore


@pytest.mark.parametrize("store_class", (SQLiteRegistry, SQLiteRunTraceStore))
@pytest.mark.parametrize(
    "failing_sql",
    ("PRAGMA foreign_keys", "PRAGMA busy_timeout", "PRAGMA journal_mode"),
)
def test_sqlite_store_closes_owned_connection_on_pragma_failure(
    store_class, failing_sql: str, tmp_path, monkeypatch,
) -> None:
    opened: list[sqlite3.Connection] = []
    closed: list[sqlite3.Connection] = []
    real_connect = sqlite3.connect

    class FailingPragmaConnection(sqlite3.Connection):
        def execute(self, sql, parameters=(), /):
            if sql.startswith(failing_sql):
                raise sqlite3.OperationalError("injected PRAGMA failure")
            return super().execute(sql, parameters)

        def close(self) -> None:
            closed.append(self)
            super().close()

    def traced_connect(*args, **kwargs):
        connection = real_connect(
            *args, factory=FailingPragmaConnection, **kwargs,
        )
        opened.append(connection)
        return connection

    with monkeypatch.context() as patch:
        patch.setattr(sqlite3, "connect", traced_connect)
        with pytest.raises(sqlite3.OperationalError, match="injected PRAGMA failure"):
            store_class(tmp_path / "failed-initialization.sqlite3")

    assert len(opened) == 1
    assert closed == opened, "The failing constructor must close its owned handle"
    with pytest.raises(sqlite3.ProgrammingError, match="closed"):
        opened[0].execute("SELECT 1")


@pytest.mark.parametrize("store_class", (SQLiteRegistry, SQLiteRunTraceStore))
def test_sqlite_store_normal_context_exit_releases_connection(
    store_class, tmp_path,
) -> None:
    with store_class(tmp_path / "normal.sqlite3") as store:
        connection = store._connection
        assert connection.execute("SELECT 1").fetchone()[0] == 1

    with pytest.raises(sqlite3.ProgrammingError, match="closed"):
        connection.execute("SELECT 1")
