from __future__ import annotations

import json
from pathlib import Path

from schemarouter import (
    EndpointSpec,
    RunConfig,
    RunEvent,
    SchemaRouter,
    SQLiteRegistry,
    SQLiteRunTraceStore,
    ToolSpec,
    schema_tool,
)
from schemarouter.cli import main
from schemarouter.dashboard import render_dashboard
from schemarouter.observability import (
    ObservabilitySnapshot,
    observe_registry,
    observe_trace_store,
)


@schema_tool(read_only=True)
def echo(value: str) -> str:
    return value


def tool_with_secret() -> ToolSpec:
    return ToolSpec(
        name="inventory",
        namespace="demo",
        description="Inventory service",
        endpoints=[
            EndpointSpec(
                name="lookup",
                method="GET",
                path="/items/{sku}",
                read_only=True,
            ),
            EndpointSpec(
                name="update",
                method="PATCH",
                path="/items/{sku}",
                read_only=False,
            ),
        ],
        metadata={
            "adapter": "openapi",
            "remote": True,
            "execution_bound": True,
            "secret": "do-not-render",
            "private_note": "internal-only",
        },
    )


def test_live_router_observation_reports_real_binding_without_invoker_details() -> None:
    router = SchemaRouter()
    key = router.add_callable(echo)

    observed = router.observe()

    assert observed.registry.bound_tools == [key]
    assert observed.registry.tools[0].execution_bound is True
    assert observed.planner.analyzer == "KeywordAnalyzer"
    assert observed.planner.decision_backend is None
    assert observed.execution.policy["allow_mutations"] is False

    document = observed.model_dump_json()
    assert "PythonCallableInvoker" not in document


def test_registry_observation_omits_arbitrary_metadata_values() -> None:
    registry = SQLiteRegistry(":memory:")
    try:
        registry.register(tool_with_secret())
        observed = observe_registry(registry)
    finally:
        registry.close()

    document = observed.model_dump_json()
    assert "do-not-render" not in document
    assert "internal-only" not in document
    assert observed.tools[0].adapter == "openapi"
    assert observed.tools[0].execution_bound is True


def test_dashboard_is_privacy_safe_and_contains_registry_summary() -> None:
    registry = SQLiteRegistry(":memory:")
    try:
        registry.register(tool_with_secret())
        snapshot = ObservabilitySnapshot(registry=observe_registry(registry))
    finally:
        registry.close()

    html = render_dashboard(snapshot)

    assert "SchemaRouter Observability" in html
    assert "demo.inventory" in html
    assert "lookup" in html
    assert "update" in html
    assert "do-not-render" not in html
    assert "internal-only" not in html


def test_trace_observation_exposes_error_types_but_not_payload_values(tmp_path: Path) -> None:
    trace_path = tmp_path / "traces.db"
    config = RunConfig(include_payloads=True)
    store = SQLiteRunTraceStore(trace_path)
    try:
        store.append(
            RunEvent.create(
                event="run.start",
                run_id="run-1",
                sequence=0,
                config=config,
                data={"input": "sensitive-query"},
            )
        )
        store.append(
            RunEvent.create(
                event="run.error",
                run_id="run-1",
                sequence=1,
                config=config,
                data={
                    "error_type": "ExampleError",
                    "message": "sensitive-error-detail",
                },
            )
        )
        observed = observe_trace_store(store)
    finally:
        store.close()

    assert observed[0].error_types == ["ExampleError"]
    html = render_dashboard(
        ObservabilitySnapshot(
            registry=observe_registry(SQLiteRegistry(":memory:")),
            traces=observed,
        )
    )
    assert "ExampleError" in html
    assert "sensitive-query" not in html
    assert "sensitive-error-detail" not in html


def test_cli_inspect_registry_and_json(tmp_path: Path, capsys) -> None:
    db = tmp_path / "registry.db"
    with SQLiteRegistry(db) as registry:
        registry.register(tool_with_secret())

    assert main(["inspect", "registry", "--db", str(db)]) == 0
    text = capsys.readouterr().out
    assert "demo.inventory" in text
    assert "2 endpoints" in text
    assert "do-not-render" not in text

    assert main(["inspect", "registry", "--db", str(db), "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["registry"]["tool_count"] == 1
    assert payload["registry"]["tools"][0]["adapter"] == "openapi"


def test_cli_inspect_traces_and_dashboard(tmp_path: Path, capsys) -> None:
    registry_db = tmp_path / "registry.db"
    trace_db = tmp_path / "traces.db"
    dashboard = tmp_path / "dashboard.html"

    with SQLiteRegistry(registry_db) as registry:
        registry.register(tool_with_secret())

    config = RunConfig()
    with SQLiteRunTraceStore(trace_db) as store:
        store.append(
            RunEvent.create(
                event="run.start",
                run_id="run-2",
                sequence=0,
                config=config,
            )
        )
        store.append(
            RunEvent.create(
                event="run.end",
                run_id="run-2",
                sequence=1,
                config=config,
                data={"result_count": 0},
            )
        )

    assert main(["inspect", "traces", "--db", str(trace_db)]) == 0
    assert "run-2" in capsys.readouterr().out

    assert main(
        [
            "dashboard",
            "--registry",
            str(registry_db),
            "--traces",
            str(trace_db),
            "--output",
            str(dashboard),
        ]
    ) == 0
    assert str(dashboard) in capsys.readouterr().out
    html = dashboard.read_text(encoding="utf-8")
    assert "run-2" in html
    assert "demo.inventory" in html


def test_cli_inspect_local_openapi_compatibility(tmp_path: Path, capsys) -> None:
    document = {
        "openapi": "3.1.0",
        "paths": {
            "/items": {
                "get": {
                    "responses": {
                        "200": {
                            "description": "ok",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "oneOf": [
                                            {"type": "object", "properties": {"a": {"type": "string"}}},
                                            {"type": "object", "properties": {"b": {"type": "string"}}},
                                        ]
                                    }
                                }
                            },
                        }
                    }
                }
            }
        },
    }
    path = tmp_path / "openapi.json"
    path.write_text(json.dumps(document), encoding="utf-8")

    assert main(["inspect", "openapi", str(path), "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)

    assert payload["status"] == "partial"
    assert payload["operations_total"] == 1
    assert any(issue["construct"] == "oneOf" for issue in payload["issues"])
