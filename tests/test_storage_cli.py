from __future__ import annotations

import json
import sqlite3

import pytest

from schemarouter import EndpointSpec, SQLiteRegistry, ToolSpec
from schemarouter.cli import main


def _legacy_registry(path) -> None:
    with SQLiteRegistry(path) as registry:
        registry.register(
            ToolSpec(
                name="alpha",
                endpoints=[
                    EndpointSpec(
                        name="read",
                        read_only=True,
                    )
                ],
            )
        )

    connection = sqlite3.connect(path)
    try:
        connection.execute(
            "DROP TABLE schemarouter_storage_migrations"
        )
        connection.execute(
            "DROP TABLE schemarouter_storage_meta"
        )
        connection.commit()
    finally:
        connection.close()


def test_storage_inspect_cli_json_reports_legacy_without_mutation(
    tmp_path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    path = tmp_path / "legacy.sqlite3"
    _legacy_registry(path)

    assert main(["storage", "inspect", str(path), "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)

    assert payload["path"] == str(path)
    assert payload["migration_required"] is True
    assert payload["components"][0]["component"] == "registry"
    assert payload["components"][0]["status"] == "legacy"

    connection = sqlite3.connect(path)
    try:
        tables = {
            str(row[0])
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }
    finally:
        connection.close()

    assert "schemarouter_storage_meta" not in tables


def test_storage_migrate_cli_creates_backup_and_reports_current_state(
    tmp_path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    path = tmp_path / "legacy.sqlite3"
    _legacy_registry(path)

    assert main(["storage", "migrate", str(path), "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)

    backup = tmp_path / "legacy.sqlite3.schemarouter.bak"
    assert backup.exists()
    assert payload["backup_path"] == str(backup)
    assert payload["before"]["migration_required"] is True
    assert payload["after"]["migration_required"] is False
    assert payload["after"]["components"][0]["status"] == "current"

    assert main(["storage", "inspect", str(path)]) == 0
    output = capsys.readouterr().out
    assert "registry: current" in output
    assert "migration required: no" in output


def test_storage_migrate_cli_no_backup_requires_no_backup_path(
    tmp_path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    path = tmp_path / "legacy.sqlite3"
    _legacy_registry(path)

    with pytest.raises(SystemExit) as excinfo:
        main(
            [
                "storage",
                "migrate",
                str(path),
                "--no-backup",
                "--backup-path",
                str(tmp_path / "unused.sqlite3"),
            ]
        )

    assert excinfo.value.code == 2
    error = capsys.readouterr().err
    assert "backup_path cannot be supplied when backup=False" in error


def test_storage_migrate_cli_can_explicitly_disable_backup(
    tmp_path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    path = tmp_path / "legacy.sqlite3"
    _legacy_registry(path)

    assert (
        main(
            [
                "storage",
                "migrate",
                str(path),
                "--no-backup",
                "--json",
            ]
        )
        == 0
    )
    payload = json.loads(capsys.readouterr().out)

    assert payload["backup_path"] is None
    assert payload["after"]["migration_required"] is False
    assert not (tmp_path / "legacy.sqlite3.schemarouter.bak").exists()


def test_storage_cli_rejects_missing_database(
    tmp_path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    missing = tmp_path / "missing.sqlite3"

    with pytest.raises(SystemExit) as excinfo:
        main(["storage", "inspect", str(missing)])

    assert excinfo.value.code == 2
    assert "database does not exist" in capsys.readouterr().err
