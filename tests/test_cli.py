import json

from schemarouter import EndpointSpec, SQLiteRegistry, ToolSpec
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
