from __future__ import annotations

from datetime import datetime, timezone

from schemarouter import (
    EndpointSpec,
    FieldSpec,
    InMemoryRegistry,
    ParameterSpec,
    RunEvent,
    SQLiteRegistry,
    SQLiteRunTraceStore,
    ToolSpec,
    inspect_registry,
    inspect_trace,
    inspect_traces,
)
from schemarouter.cli import main


def sample_tool() -> ToolSpec:
    return ToolSpec(
        name="weather",
        namespace="demo",
        description="Weather API",
        source_type="openapi",
        license="MIT",
        metadata={
            "adapter": "openapi",
            "source_url": "https://example.test/openapi.json",
            "execution_bound": True,
            "secretish_custom_metadata": "must-not-render",
        },
        endpoints=[
            EndpointSpec(
                name="current",
                method="GET",
                path="/weather/current",
                read_only=True,
                parameters=[
                    ParameterSpec(
                        name="city",
                        location="query",
                        required=True,
                    )
                ],
                output_fields=[
                    FieldSpec(name="city", identifier=True),
                    FieldSpec(name="temperature", unit="celsius"),
                ],
            ),
            EndpointSpec(
                name="refresh",
                method="POST",
                path="/weather/refresh",
                read_only=False,
                destructive=False,
            ),
            EndpointSpec(
                name="mystery",
                method="POST",
                path="/weather/mystery",
                read_only=None,
            ),
        ],
    )


def event(
    run_id: str,
    sequence: int,
    name: str,
    *,
    tool: str | None = None,
    endpoint: str | None = None,
) -> RunEvent:
    return RunEvent(
        event=name,
        run_id=run_id,
        sequence=sequence,
        timestamp=datetime(2026, 9, 23, 4, sequence, tzinfo=timezone.utc),
        tool=tool,
        endpoint=endpoint,
    )


def test_inspect_registry_derives_operational_counts() -> None:
    registry = InMemoryRegistry()
    registry.register(sample_tool())

    snapshot = inspect_registry(registry)

    assert snapshot.version == 1
    assert snapshot.tool_count == 1
    assert snapshot.endpoint_count == 3
    assert snapshot.read_only_endpoints == 1
    assert snapshot.mutating_endpoints == 1
    assert snapshot.unclassified_endpoints == 1
    assert snapshot.tools[0].key == "demo.weather"
    assert snapshot.tools[0].provenance == {
        "adapter": "openapi",
        "source_url": "https://example.test/openapi.json",
        "execution_bound": True,
    }
    assert len(snapshot.tools[0].fingerprint) == 64
    assert len(snapshot.tools[0].endpoints[0].fingerprint) == 64


def test_inspect_trace_summarizes_targets_and_errors(tmp_path) -> None:
    path = tmp_path / "traces.sqlite3"
    with SQLiteRunTraceStore(path) as store:
        store.append(event("run-1", 0, "run.start"))
        store.append(
            event(
                "run-1",
                1,
                "tool.start",
                tool="demo.weather",
                endpoint="current",
            )
        )
        store.append(
            event(
                "run-1",
                2,
                "tool.error",
                tool="demo.weather",
                endpoint="current",
            )
        )
        store.append(event("run-1", 3, "run.error"))

        summary = inspect_trace(store, "run-1")
        assert summary.complete is True
        assert summary.event_count == 4
        assert summary.tools == ["demo.weather"]
        assert summary.endpoints == ["demo.weather.current"]
        assert summary.error_count == 2
        assert summary.terminal_event == "run.error"

        assert inspect_traces(store, complete=True) == (summary,)
        assert inspect_traces(store, complete=False) == ()


def test_cli_registry_and_tool_json_are_read_only(tmp_path, capsys) -> None:
    path = tmp_path / "registry.sqlite3"
    with SQLiteRegistry(path) as registry:
        registry.register(sample_tool())
        version = registry.version

    assert main(["inspect", "registry", "--db", str(path)]) == 0
    output = capsys.readouterr().out
    assert "Registry v1: 1 tools, 3 endpoints" in output
    assert "demo.weather" in output
    assert "openapi" in output
    assert "https://example.test/openapi.json" in output
    assert "secretish_custom_metadata" not in output
    assert "GET /weather/current" in output
    assert "mutating" in output
    assert "unclassified" in output

    assert main(
        ["inspect", "tool", "demo.weather", "--db", str(path), "--json"]
    ) == 0
    output = capsys.readouterr().out
    assert '"key": "demo.weather"' in output
    assert '"fingerprint"' in output
    assert '"wire_name": null' in output
    assert '"source_url": "https://example.test/openapi.json"' in output
    assert "secretish_custom_metadata" not in output

    with SQLiteRegistry(path) as reopened:
        assert reopened.version == version
        assert reopened.keys() == ("demo.weather",)


def test_cli_missing_database_does_not_create_file(tmp_path) -> None:
    path = tmp_path / "missing.sqlite3"

    try:
        main(["inspect", "registry", "--db", str(path)])
    except SystemExit as exc:
        assert exc.code == 2
    else:
        raise AssertionError("missing inspection database must fail")

    assert not path.exists()


def test_cli_trace_list_and_detail(tmp_path, capsys) -> None:
    path = tmp_path / "traces.sqlite3"
    with SQLiteRunTraceStore(path) as store:
        store.append(event("run-1", 0, "run.start"))
        store.append(
            event(
                "run-1",
                1,
                "tool.start",
                tool="demo.weather",
                endpoint="current",
            )
        )
        store.append(
            event(
                "run-1",
                2,
                "tool.end",
                tool="demo.weather",
                endpoint="current",
            )
        )
        store.append(event("run-1", 3, "run.end"))
        store.append(event("partial", 0, "run.start"))

    assert main(
        ["inspect", "traces", "--db", str(path), "--complete"]
    ) == 0
    output = capsys.readouterr().out
    assert "run-1" in output
    assert "partial" not in output
    assert "demo.weather.current" in output

    assert main(
        ["inspect", "trace", "run-1", "--db", str(path)]
    ) == 0
    output = capsys.readouterr().out
    assert "Run run-1" in output
    assert "tool.start demo.weather.current" in output
    assert "run.end" in output

    assert main(
        ["inspect", "traces", "--db", str(path), "--json"]
    ) == 0
    output = capsys.readouterr().out
    assert '"run_id": "run-1"' in output
    assert '"run_id": "partial"' in output
