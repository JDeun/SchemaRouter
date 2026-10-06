from __future__ import annotations

import sqlite3
from datetime import datetime, timezone

import pytest

from schemarouter import (
    EndpointSpec,
    FieldSpec,
    PersistedDocumentLimits,
    RegistrationError,
    SQLiteRegistry,
    SQLiteRunTraceStore,
    StorageFormatError,
    ToolSpec,
    TraceError,
    inspect_sqlite_storage,
    migrate_sqlite_storage,
)
from schemarouter.persistence_limits import (
    PersistedDocumentLimitError,
    validate_persisted_json_document,
)
from schemarouter.runs import RunEvent


def _tool(name: str = "alpha", *, description: str = "") -> ToolSpec:
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
    )


def _event(*, payload_size: int = 0) -> RunEvent:
    return RunEvent(
        event="run.start",
        run_id="run-1",
        sequence=0,
        timestamp=datetime(2026, 10, 6, tzinfo=timezone.utc),
        data={"payload": "x" * payload_size},
    )


def _low_limits() -> PersistedDocumentLimits:
    return PersistedDocumentLimits(
        max_bytes=512,
        max_depth=32,
        max_nodes=1_000,
    )


def _create_legacy_registry(path, tool: ToolSpec) -> None:
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
            VALUES ('version', 1)
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
        connection.execute(
            """
            INSERT INTO schemarouter_registry_tools (key, position, document)
            VALUES (?, 0, ?)
            """,
            (tool.key, tool.model_dump_json()),
        )
        connection.commit()
    finally:
        connection.close()


def test_persisted_document_scanner_bounds_encoded_bytes_depth_and_nodes() -> None:
    with pytest.raises(PersistedDocumentLimitError, match="byte limit"):
        validate_persisted_json_document(
            '"é"',
            PersistedDocumentLimits(max_bytes=3, max_depth=8, max_nodes=8),
        )

    with pytest.raises(PersistedDocumentLimitError, match="nesting depth"):
        validate_persisted_json_document(
            "[[[0]]]",
            PersistedDocumentLimits(max_bytes=128, max_depth=2, max_nodes=16),
        )

    with pytest.raises(PersistedDocumentLimitError, match="node limit"):
        validate_persisted_json_document(
            "[0,0,0]",
            PersistedDocumentLimits(max_bytes=128, max_depth=8, max_nodes=3),
        )


def test_registry_rejects_document_that_cannot_be_read_under_same_limits(tmp_path) -> None:
    path = tmp_path / "registry.sqlite3"
    large = _tool(description="x" * 2_048)

    with SQLiteRegistry(path, document_limits=_low_limits()) as registry:
        with pytest.raises(RegistrationError, match="document safety limits"):
            registry.register(large)

    with SQLiteRegistry(path) as registry:
        registry.register(large)

    with SQLiteRegistry(path, document_limits=_low_limits()) as reopened:
        with pytest.raises(RegistrationError, match="document safety limits"):
            reopened.get(large.key)


def test_trace_store_enforces_document_limits_on_write_and_replay(tmp_path) -> None:
    write_path = tmp_path / "trace-write.sqlite3"
    event = _event(payload_size=2_048)

    with SQLiteRunTraceStore(
        write_path,
        document_limits=_low_limits(),
    ) as store:
        with pytest.raises(TraceError, match="document safety limits"):
            store.append(event)

    read_path = tmp_path / "trace-read.sqlite3"
    with SQLiteRunTraceStore(read_path) as store:
        store.append(event)

    with SQLiteRunTraceStore(
        read_path,
        document_limits=_low_limits(),
    ) as reopened:
        with pytest.raises(TraceError, match="document safety limits"):
            reopened.trace("run-1")


def test_storage_inspection_uses_the_same_document_safety_envelope(tmp_path) -> None:
    path = tmp_path / "registry.sqlite3"
    with SQLiteRegistry(path) as registry:
        registry.register(_tool(description="x" * 2_048))

    inspection = inspect_sqlite_storage(
        path,
        document_limits=_low_limits(),
    )

    assert len(inspection.components) == 1
    assert inspection.components[0].component == "registry"
    assert inspection.components[0].status == "corrupt"


def test_legacy_migration_refuses_documents_over_the_configured_budget(tmp_path) -> None:
    path = tmp_path / "legacy.sqlite3"
    _create_legacy_registry(path, _tool(description="x" * 2_048))

    with pytest.raises(StorageFormatError, match="not safely migratable"):
        migrate_sqlite_storage(
            path,
            backup=False,
            document_limits=_low_limits(),
        )


def test_trusted_deployment_can_raise_persisted_document_limits(tmp_path) -> None:
    path = tmp_path / "registry.sqlite3"
    large = _tool(description="x" * 2_048)
    permissive = PersistedDocumentLimits(
        max_bytes=16_384,
        max_depth=128,
        max_nodes=10_000,
    )

    with SQLiteRegistry(path, document_limits=permissive) as registry:
        registry.register(large)
        assert registry.get(large.key).description == large.description
