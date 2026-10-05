from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone

import pytest

import schemarouter.storage as storage_module
from schemarouter.errors import StorageFormatError
from schemarouter.models import EndpointSpec, FieldSpec, ToolSpec
from schemarouter.registry import SQLiteRegistry
from schemarouter.runs import RunEvent
from schemarouter.storage import (
    CURRENT_REGISTRY_DOCUMENT_VERSION,
    CURRENT_STORAGE_FORMAT_VERSION,
    CURRENT_TRACE_DOCUMENT_VERSION,
    StorageComponentInspection,
    StorageInspection,
    backup_sqlite_storage,
    inspect_sqlite_storage,
    migrate_sqlite_storage,
)
from schemarouter.traces import SQLiteRunTraceStore


def _tool(name: str, *, description: str = "") -> ToolSpec:
    return ToolSpec(
        name=name,
        description=description,
        endpoints=[
            EndpointSpec(
                name="read",
                read_only=True,
                output_fields=[
                    FieldSpec(
                        name="value",
                        json_schema={"type": "string"},
                    )
                ],
                output_schema={
                    "type": "object",
                    "properties": {"value": {"type": "string"}},
                },
            )
        ],
        metadata={"legacy": True},
    )


def _event(
    run_id: str,
    sequence: int,
    event: str,
    *,
    seconds: int = 0,
) -> RunEvent:
    return RunEvent(
        event=event,
        run_id=run_id,
        sequence=sequence,
        timestamp=datetime(2026, 9, 1, tzinfo=timezone.utc)
        + timedelta(seconds=seconds),
        data={},
    )


def _create_legacy_registry(
    path,
    *,
    tools: list[tuple[int, ToolSpec]],
    logical_version: int,
) -> None:
    connection = sqlite3.connect(path)
    try:
        connection.execute(
            """
            CREATE TABLE schemarouter_registry_meta (
                key TEXT PRIMARY KEY,
                value INTEGER NOT NULL
            )
            """
        )
        connection.execute(
            """
            INSERT INTO schemarouter_registry_meta (key, value)
            VALUES ('version', ?)
            """,
            (logical_version,),
        )
        connection.execute(
            """
            CREATE TABLE schemarouter_registry_tools (
                key TEXT PRIMARY KEY,
                position INTEGER NOT NULL UNIQUE,
                document TEXT NOT NULL
            )
            """
        )
        for position, tool in tools:
            connection.execute(
                """
                INSERT INTO schemarouter_registry_tools (key, position, document)
                VALUES (?, ?, ?)
                """,
                (tool.key, position, tool.model_dump_json()),
            )
        connection.commit()
    finally:
        connection.close()


def _create_legacy_trace(
    path,
    *,
    run_id: str = "run-1",
) -> list[RunEvent]:
    events = [
        _event(run_id, 0, "run.start"),
        _event(run_id, 1, "plan.end", seconds=1),
        _event(run_id, 2, "run.end", seconds=2),
    ]
    connection = sqlite3.connect(path)
    try:
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute(
            """
            CREATE TABLE schemarouter_trace_runs (
                run_id TEXT PRIMARY KEY,
                created_at REAL NOT NULL,
                last_sequence INTEGER NOT NULL,
                last_timestamp REAL NOT NULL,
                terminal INTEGER NOT NULL CHECK (terminal IN (0, 1))
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE schemarouter_trace_events (
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
        connection.execute(
            """
            INSERT INTO schemarouter_trace_runs (
                run_id,
                created_at,
                last_sequence,
                last_timestamp,
                terminal
            )
            VALUES (?, ?, ?, ?, 1)
            """,
            (
                run_id,
                events[0].timestamp.timestamp(),
                events[-1].sequence,
                events[-1].timestamp.timestamp(),
            ),
        )
        for event in events:
            connection.execute(
                """
                INSERT INTO schemarouter_trace_events (run_id, sequence, document)
                VALUES (?, ?, ?)
                """,
                (run_id, event.sequence, event.model_dump_json()),
            )
        connection.commit()
    finally:
        connection.close()
    return events


def _meta_value(path, component: str, key: str) -> str | None:
    connection = sqlite3.connect(path)
    try:
        row = connection.execute(
            """
            SELECT value
            FROM schemarouter_storage_meta
            WHERE component = ? AND key = ?
            """,
            (component, key),
        ).fetchone()
        return None if row is None else str(row[0])
    finally:
        connection.close()


def test_storage_inspection_computed_fields_serialize_and_publish_schema() -> None:
    component = StorageComponentInspection(
        component="registry",
        status="legacy",
        current_document_format_version=CURRENT_REGISTRY_DOCUMENT_VERSION,
    )
    inspection = StorageInspection(
        path="legacy.sqlite3",
        components=[component],
    )

    assert component.model_dump()["migration_required"] is True
    assert inspection.model_dump()["migration_required"] is True

    component_schema = StorageComponentInspection.model_json_schema(
        mode="serialization"
    )
    inspection_schema = StorageInspection.model_json_schema(
        mode="serialization"
    )

    assert component_schema["properties"]["migration_required"]["type"] == "boolean"
    assert inspection_schema["properties"]["migration_required"]["type"] == "boolean"


def test_fresh_registry_and_trace_store_current_format_metadata(tmp_path) -> None:
    path = tmp_path / "combined.sqlite3"

    with SQLiteRegistry(path) as registry:
        assert registry.storage_format_version == CURRENT_STORAGE_FORMAT_VERSION
        assert (
            registry.document_format_version
            == CURRENT_REGISTRY_DOCUMENT_VERSION
        )

    with SQLiteRunTraceStore(path) as traces:
        assert traces.storage_format_version == CURRENT_STORAGE_FORMAT_VERSION
        assert traces.document_format_version == CURRENT_TRACE_DOCUMENT_VERSION

    inspection = inspect_sqlite_storage(path)
    assert {
        (component.component, component.status)
        for component in inspection.components
    } == {("registry", "current"), ("trace", "current")}


def test_legacy_registry_auto_migration_preserves_logical_state(tmp_path) -> None:
    path = tmp_path / "legacy-registry.sqlite3"
    alpha = _tool("alpha", description="first")
    beta = _tool("beta", description="second")
    expected = {
        alpha.key: alpha.fingerprint,
        beta.key: beta.fingerprint,
    }
    _create_legacy_registry(
        path,
        tools=[(2, alpha), (7, beta)],
        logical_version=19,
    )

    before = inspect_sqlite_storage(path)
    assert before.components[0].status == "legacy"
    assert before.components[0].storage_format_version is None

    with SQLiteRegistry(path) as registry:
        assert registry.version == 19
        assert registry.keys() == ("alpha", "beta")
        assert {
            tool.key: tool.fingerprint
            for tool in registry.tools()
        } == expected
        assert registry.storage_format_version == 1
        assert registry.document_format_version == 1

    after = inspect_sqlite_storage(path)
    component = next(
        item for item in after.components if item.component == "registry"
    )
    assert component.status == "current"
    assert len(component.migrations) == 1
    assert component.migrations[0].from_version == 0
    assert component.migrations[0].to_version == 1

    # Reopening is idempotent: no logical bump and no duplicate migration.
    with SQLiteRegistry(path) as reopened:
        assert reopened.version == 19
        assert reopened.keys() == ("alpha", "beta")

    final = inspect_sqlite_storage(path)
    registry_component = next(
        item for item in final.components if item.component == "registry"
    )
    assert len(registry_component.migrations) == 1


def test_legacy_trace_auto_migration_preserves_replay_invariants(tmp_path) -> None:
    path = tmp_path / "legacy-trace.sqlite3"
    expected = _create_legacy_trace(path)

    before = inspect_sqlite_storage(path)
    assert before.components[0].status == "legacy"

    with SQLiteRunTraceStore(path) as store:
        trace = store.trace("run-1")
        assert store.storage_format_version == 1
        assert store.document_format_version == 1

    assert [event.model_dump(mode="json") for event in trace.events] == [
        event.model_dump(mode="json") for event in expected
    ]
    assert trace.complete is True

    after = inspect_sqlite_storage(path)
    component = next(
        item for item in after.components if item.component == "trace"
    )
    assert component.status == "current"
    assert len(component.migrations) == 1
    assert component.migrations[0].from_version == 0


def test_registry_migration_rolls_back_if_legacy_document_is_invalid(tmp_path) -> None:
    path = tmp_path / "bad-legacy.sqlite3"
    _create_legacy_registry(
        path,
        tools=[(0, _tool("valid"))],
        logical_version=4,
    )
    connection = sqlite3.connect(path)
    try:
        connection.execute(
            """
            INSERT INTO schemarouter_registry_tools (key, position, document)
            VALUES ('broken', 1, ?)
            """,
            ('{"name":"broken","endpoints":"not-a-list"}',),
        )
        connection.commit()
    finally:
        connection.close()

    with pytest.raises(StorageFormatError, match="cannot be migrated safely"):
        SQLiteRegistry(path)

    # No v1 stamp was committed, and inspection identifies the invalid
    # legacy document as corrupt rather than merely old.
    inspection = inspect_sqlite_storage(path)
    component = next(
        item for item in inspection.components if item.component == "registry"
    )
    assert component.status == "corrupt"

    connection = sqlite3.connect(path)
    try:
        row = connection.execute(
            "SELECT value FROM schemarouter_registry_meta WHERE key = 'version'"
        ).fetchone()
        assert row is not None and int(row[0]) == 4
    finally:
        connection.close()


def test_trace_migration_rolls_back_on_summary_corruption(tmp_path) -> None:
    path = tmp_path / "bad-trace.sqlite3"
    _create_legacy_trace(path)
    connection = sqlite3.connect(path)
    try:
        connection.execute(
            """
            UPDATE schemarouter_trace_runs
            SET last_sequence = 99
            WHERE run_id = 'run-1'
            """
        )
        connection.commit()
    finally:
        connection.close()

    with pytest.raises(StorageFormatError, match="sequence summary"):
        SQLiteRunTraceStore(path)

    inspection = inspect_sqlite_storage(path)
    component = next(
        item for item in inspection.components if item.component == "trace"
    )
    assert component.status == "corrupt"


@pytest.mark.parametrize(
    ("key", "value", "message"),
    [
        ("storage_format_version", "999", "newer than supported"),
        ("document_format_version", "999", "newer than supported"),
    ],
)
def test_future_storage_or_document_format_is_rejected(
    tmp_path,
    key: str,
    value: str,
    message: str,
) -> None:
    path = tmp_path / f"future-{key}.sqlite3"
    with SQLiteRegistry(path):
        pass

    connection = sqlite3.connect(path)
    try:
        connection.execute(
            """
            UPDATE schemarouter_storage_meta
            SET value = ?
            WHERE component = 'registry' AND key = ?
            """,
            (value, key),
        )
        connection.commit()
    finally:
        connection.close()

    with pytest.raises(StorageFormatError, match=message):
        SQLiteRegistry(path)


def test_incomplete_current_format_metadata_fails_closed(tmp_path) -> None:
    path = tmp_path / "missing-format.sqlite3"
    with SQLiteRegistry(path):
        pass

    connection = sqlite3.connect(path)
    try:
        connection.execute(
            """
            DELETE FROM schemarouter_storage_meta
            WHERE component = 'registry'
              AND key = 'document_format_version'
            """
        )
        connection.commit()
    finally:
        connection.close()

    inspection = inspect_sqlite_storage(path)
    assert inspection.components[0].status == "corrupt"

    with pytest.raises(StorageFormatError, match="incomplete format metadata"):
        SQLiteRegistry(path)


def test_storage_migrate_creates_pre_migration_backup_and_is_idempotent(
    tmp_path,
) -> None:
    path = tmp_path / "legacy.sqlite3"
    backup = tmp_path / "legacy.backup.sqlite3"
    tool = _tool("alpha")
    _create_legacy_registry(
        path,
        tools=[(0, tool)],
        logical_version=3,
    )

    migrated = migrate_sqlite_storage(
        path,
        backup=True,
        backup_path=backup,
    )
    assert backup.exists()
    assert migrated.backup_path == str(backup)
    assert migrated.before.migration_required is True
    assert migrated.after.migration_required is False

    # Backup is an exact pre-migration database and remains legacy.
    backup_inspection = inspect_sqlite_storage(backup)
    assert backup_inspection.components[0].status == "legacy"

    second = migrate_sqlite_storage(path, backup=True, backup_path=backup)
    assert second.backup_path is None
    assert second.after.migration_required is False
    assert next(
        item
        for item in second.after.components
        if item.component == "registry"
    ).status == "current"


def test_backup_api_refuses_to_overwrite_source_path(tmp_path) -> None:
    path = tmp_path / "registry.sqlite3"
    with SQLiteRegistry(path):
        pass

    with pytest.raises(StorageFormatError, match="must differ"):
        backup_sqlite_storage(path, path)


def test_explicit_migration_is_atomic_across_registry_and_trace_components(
    tmp_path,
) -> None:
    path = tmp_path / "combined-legacy.sqlite3"
    _create_legacy_registry(
        path,
        tools=[(0, _tool("alpha"))],
        logical_version=7,
    )
    _create_legacy_trace(path)

    connection = sqlite3.connect(path)
    try:
        connection.execute(
            """
            UPDATE schemarouter_trace_runs
            SET terminal = 0
            WHERE run_id = 'run-1'
            """
        )
        connection.commit()
    finally:
        connection.close()

    with pytest.raises(
        StorageFormatError,
        match="not safely migratable.*trace=corrupt",
    ):
        migrate_sqlite_storage(path, backup=False)

    inspection = inspect_sqlite_storage(path)
    assert {
        (component.component, component.status)
        for component in inspection.components
    } == {
        ("registry", "legacy"),
        ("trace", "corrupt"),
    }

    connection = sqlite3.connect(path)
    try:
        tables = {
            str(row[0])
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }
        row = connection.execute(
            "SELECT value FROM schemarouter_registry_meta WHERE key = 'version'"
        ).fetchone()
    finally:
        connection.close()

    assert "schemarouter_storage_meta" not in tables
    assert row is not None and int(row[0]) == 7


def test_malformed_legacy_registry_meta_shape_fails_as_storage_error(
    tmp_path,
) -> None:
    path = tmp_path / "malformed-registry-meta.sqlite3"
    connection = sqlite3.connect(path)
    try:
        connection.execute(
            """
            CREATE TABLE schemarouter_registry_meta (
                key TEXT PRIMARY KEY,
                wrong_value_column INTEGER NOT NULL
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE schemarouter_registry_tools (
                key TEXT PRIMARY KEY,
                position INTEGER NOT NULL UNIQUE,
                document TEXT NOT NULL
            )
            """
        )
        connection.commit()
    finally:
        connection.close()

    with pytest.raises(
        StorageFormatError,
        match="metadata table shape",
    ):
        SQLiteRegistry(path)


def test_malformed_legacy_trace_summary_values_fail_closed(tmp_path) -> None:
    path = tmp_path / "malformed-trace-summary.sqlite3"
    _create_legacy_trace(path)

    connection = sqlite3.connect(path)
    try:
        connection.execute(
            """
            UPDATE schemarouter_trace_runs
            SET last_timestamp = 'not-a-number'
            WHERE run_id = 'run-1'
            """
        )
        connection.commit()
    finally:
        connection.close()

    with pytest.raises(
        StorageFormatError,
        match="summary contains invalid values",
    ):
        SQLiteRunTraceStore(path)


def test_backup_refuses_existing_destination_without_overwrite(tmp_path) -> None:
    path = tmp_path / "registry-source.sqlite3"
    backup = tmp_path / "existing-backup.sqlite3"

    with SQLiteRegistry(path):
        pass
    backup.write_bytes(b"do-not-overwrite")

    with pytest.raises(
        StorageFormatError,
        match="backup destination already exists",
    ):
        backup_sqlite_storage(path, backup)

    assert backup.read_bytes() == b"do-not-overwrite"


def test_backup_refuses_symlink_destination_without_touching_target(tmp_path) -> None:
    path = tmp_path / "registry-source.sqlite3"
    victim = tmp_path / "victim.sqlite3"
    backup = tmp_path / "backup.sqlite3"

    with SQLiteRegistry(path):
        pass
    victim.write_bytes(b"victim-data")
    try:
        backup.symlink_to(victim)
    except OSError:
        pytest.skip("symlink creation is unavailable on this platform")

    with pytest.raises(StorageFormatError, match="already exists|unsafe"):
        backup_sqlite_storage(path, backup)

    assert backup.is_symlink()
    assert victim.read_bytes() == b"victim-data"


def test_backup_failure_cleanup_does_not_unlink_replaced_destination(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = tmp_path / "registry-source.sqlite3"
    backup = tmp_path / "reserved-backup.sqlite3"

    with SQLiteRegistry(path):
        pass

    def replace_reserved_path_then_fail(
        backup_path,
        descriptor,
    ) -> None:
        del backup_path, descriptor
        backup.unlink()
        backup.write_bytes(b"concurrent-owner")
        raise OSError("synthetic copy failure")

    monkeypatch.setattr(
        storage_module,
        "_copy_backup_to_reserved_destination",
        replace_reserved_path_then_fail,
    )

    with pytest.raises(StorageFormatError, match="SQLite backup failed"):
        backup_sqlite_storage(path, backup)

    assert backup.read_bytes() == b"concurrent-owner"


def test_current_format_corrupt_document_is_reported_by_storage_inspect(
    tmp_path,
) -> None:
    path = tmp_path / "current-corrupt.sqlite3"
    with SQLiteRegistry(path) as registry:
        registry.register(_tool("alpha"))

    connection = sqlite3.connect(path)
    try:
        connection.execute(
            """
            UPDATE schemarouter_registry_tools
            SET document = ?
            WHERE key = 'alpha'
            """,
            ('{"name":"alpha","endpoints":"broken"}',),
        )
        connection.commit()
    finally:
        connection.close()

    inspection = inspect_sqlite_storage(path)
    component = next(
        item for item in inspection.components if item.component == "registry"
    )
    assert component.status == "corrupt"
    assert component.storage_format_version == CURRENT_STORAGE_FORMAT_VERSION
    assert (
        component.document_format_version
        == CURRENT_REGISTRY_DOCUMENT_VERSION
    )

    with pytest.raises(
        StorageFormatError,
        match="registry=corrupt",
    ):
        migrate_sqlite_storage(path, backup=False)
