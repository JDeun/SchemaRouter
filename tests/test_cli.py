import json

import pytest

from schemarouter import (
    CAPABILITY_SNAPSHOT_DOCUMENT_VERSION,
    EndpointSpec,
    SQLiteRegistry,
    ToolSpec,
    build_capability_artifact,
    build_capability_snapshot,
    serialize_capability_artifact,
)
from schemarouter.cli import _run, build_parser


def _write_registry(path, *, read_only: bool) -> None:
    with SQLiteRegistry(path) as registry:
        registry.register(
            ToolSpec(
                name="demo",
                endpoints=[
                    EndpointSpec(
                        name="run",
                        method="GET" if read_only else "POST",
                        path="/run",
                        read_only=read_only,
                        destructive=False,
                    )
                ],
            )
        )


def test_cli_schema_diff_human_output(tmp_path) -> None:
    old_db = tmp_path / "old.sqlite3"
    new_db = tmp_path / "new.sqlite3"
    _write_registry(old_db, read_only=True)
    _write_registry(new_db, read_only=False)

    args = build_parser().parse_args(
        [
            "inspect",
            "diff",
            "demo",
            "--old-db",
            str(old_db),
            "--new-db",
            str(new_db),
        ]
    )

    output = _run(args)

    assert "Schema diff demo" in output
    assert "compatibility: security_review" in output
    assert "execution_semantics_changed" in output


def test_cli_schema_diff_endpoint_json_output(tmp_path) -> None:
    old_db = tmp_path / "old.sqlite3"
    new_db = tmp_path / "new.sqlite3"
    _write_registry(old_db, read_only=True)
    _write_registry(new_db, read_only=False)

    args = build_parser().parse_args(
        [
            "inspect",
            "diff",
            "demo",
            "--endpoint",
            "run",
            "--old-db",
            str(old_db),
            "--new-db",
            str(new_db),
            "--json",
        ]
    )

    payload = json.loads(_run(args))

    assert payload["compatibility"] == "security_review"
    assert payload["old_fingerprint"] != payload["new_fingerprint"]
    assert any(
        change["kind"] == "execution_semantics_changed"
        for change in payload["changes"]
    )


def test_cli_artifact_inspect_and_migrate_current_document(tmp_path) -> None:
    source = tmp_path / "graph.json"
    artifact = build_capability_artifact(
        graph_digest="g",
        capabilities=[],
    )
    source.write_text(
        serialize_capability_artifact(artifact),
        encoding="utf-8",
    )

    inspect_args = build_parser().parse_args(
        ["artifact", "inspect", str(source), "--json"]
    )
    inspection = json.loads(_run(inspect_args))

    assert inspection["kind"] == "capability_artifact"
    assert inspection["migration_required"] is False
    assert source.read_text(encoding="utf-8") == serialize_capability_artifact(artifact)

    migrate_args = build_parser().parse_args(
        ["artifact", "migrate", str(source), "--json"]
    )
    migrated = json.loads(_run(migrate_args))
    destination = tmp_path / "graph.json.migrated.json"

    assert migrated["output"] == str(destination)
    assert destination.exists()
    assert source.exists()


def test_cli_snapshot_migrates_raw_public_snapshot_without_overwrite(tmp_path) -> None:
    source = tmp_path / "snapshot.json"
    snapshot = build_capability_snapshot([])
    source.write_text(
        json.dumps(snapshot.model_dump(mode="json")),
        encoding="utf-8",
    )

    args = build_parser().parse_args(
        ["snapshot", "migrate", str(source), "--json"]
    )
    migrated = json.loads(_run(args))
    destination = tmp_path / "snapshot.json.migrated.json"

    assert migrated["migration_required"] is True
    assert destination.exists()
    payload = json.loads(destination.read_text(encoding="utf-8"))
    assert payload["format_version"] == CAPABILITY_SNAPSHOT_DOCUMENT_VERSION
    assert payload["snapshot"]["snapshot_id"] == snapshot.snapshot_id


def test_cli_format_migration_refuses_existing_destination_without_overwrite(
    tmp_path,
) -> None:
    source = tmp_path / "snapshot.json"
    output = tmp_path / "existing.json"
    snapshot = build_capability_snapshot([])
    source.write_text(
        json.dumps(snapshot.model_dump(mode="json")),
        encoding="utf-8",
    )
    output.write_text("keep", encoding="utf-8")

    args = build_parser().parse_args(
        [
            "snapshot",
            "migrate",
            str(source),
            "--output",
            str(output),
        ]
    )

    with pytest.raises(FileExistsError, match="already exists"):
        _run(args)

    assert output.read_text(encoding="utf-8") == "keep"


def test_cli_artifact_read_rejects_oversized_file_before_json_parse(tmp_path) -> None:
    source = tmp_path / "oversized.json"
    source.write_bytes(b"x" * (2 * 1024 * 1024 + 1))
    args = build_parser().parse_args(
        ["artifact", "inspect", str(source), "--json"]
    )

    with pytest.raises(ValueError, match="byte limit"):
        _run(args)
