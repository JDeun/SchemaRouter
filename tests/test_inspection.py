from __future__ import annotations

from datetime import datetime, timezone

from schemarouter import (
    EndpointSpec,
    FieldSpec,
    InMemoryRegistry,
    ParameterSpec,
    RunEvent,
    SchemaRouter,
    SQLiteRegistry,
    SQLiteRunTraceStore,
    ToolSpec,
    UnitNormalizationSpec,
    inspect_registry,
    inspect_router,
    inspect_trace,
    inspect_traces,
    schema_tool,
)
from schemarouter.cli import main
from schemarouter.dashboard import render_dashboard


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
        "remote": True,
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


@schema_tool(read_only=True)
def _echo(value: str) -> str:
    return value


def test_live_router_inspection_reports_actual_binding_without_invoker_object() -> None:
    router = SchemaRouter()
    key = router.add_callable(_echo)

    snapshot = inspect_router(router)

    assert snapshot.registry.tool_count == 1
    assert snapshot.planner.analyzer == "KeywordAnalyzer"
    assert snapshot.planner.decision_backend is None
    assert snapshot.execution.bound_tools == [key]
    assert snapshot.execution.binding_states == {key: "ready"}
    assert snapshot.execution.policy["allow_mutations"] is False

    document = snapshot.model_dump_json()
    assert "PythonCallableInvoker" not in document


def test_schema_router_inspect_convenience_matches_public_helper() -> None:
    router = SchemaRouter()
    router.add_callable(_echo)

    assert router.inspect() == inspect_router(router)


def test_dashboard_uses_safe_inspection_models_only(tmp_path) -> None:
    registry_path = tmp_path / "registry.sqlite3"
    trace_path = tmp_path / "traces.sqlite3"

    with SQLiteRegistry(registry_path) as registry:
        tool = sample_tool().model_copy(deep=True)
        tool.metadata["dashboard_secret"] = "must-never-render"
        registry.register(tool)
        snapshot = inspect_registry(registry)

    with SQLiteRunTraceStore(trace_path) as store:
        secret_event = event("run-dashboard", 0, "run.start").model_copy(
            update={"data": {"input": "private-query-value"}}
        )
        store.append(secret_event)
        store.append(event("run-dashboard", 1, "run.end"))
        traces = inspect_traces(store)

    html = render_dashboard(snapshot, traces=traces)

    assert "SchemaRouter inspection dashboard" in html
    assert "demo.weather" in html
    assert "https://example.test/openapi.json" in html
    assert "run-dashboard" in html
    assert "must-never-render" not in html
    assert "private-query-value" not in html


def test_cli_dashboard_exports_self_contained_html(tmp_path, capsys) -> None:
    registry_path = tmp_path / "registry.sqlite3"
    trace_path = tmp_path / "traces.sqlite3"
    output = tmp_path / "artifacts" / "dashboard.html"

    with SQLiteRegistry(registry_path) as registry:
        registry.register(sample_tool())

    with SQLiteRunTraceStore(trace_path) as store:
        store.append(event("run-dashboard", 0, "run.start"))
        store.append(event("run-dashboard", 1, "run.end"))

    assert main(
        [
            "dashboard",
            "--registry",
            str(registry_path),
            "--traces",
            str(trace_path),
            "--output",
            str(output),
        ]
    ) == 0
    assert str(output) in capsys.readouterr().out
    html = output.read_text(encoding="utf-8")
    assert "demo.weather" in html
    assert "run-dashboard" in html
    assert "https://" not in html.split("<script>", 1)[1]



def test_inspection_uses_fingerprinted_execution_provenance_over_descriptive_metadata() -> None:
    tool = sample_tool()
    tool.execution_metadata["approved_base_url"] = "https://trusted.example/api"
    tool.metadata["approved_base_url"] = "https://spoofed.example/api"
    tool.metadata["remote"] = False

    snapshot = inspect_registry(
        _registry_with_tool(tool)
    )

    assert snapshot.tools[0].provenance["approved_base_url"] == "https://trusted.example/api"
    assert snapshot.tools[0].provenance["remote"] is True


def _registry_with_tool(tool: ToolSpec) -> InMemoryRegistry:
    registry = InMemoryRegistry()
    registry.register(tool)
    return registry



def test_inspection_redacts_url_query_and_fragment_from_provenance() -> None:
    tool = sample_tool()
    tool.execution_metadata.update(
        {
            "source_url": (
                "https://user:password@example.test/openapi.json?token=secret#fragment"
            ),
            "approved_base_url": "https://api.example.test/v1?should-not-render=yes",
        }
    )

    snapshot = inspect_registry(_registry_with_tool(tool))
    provenance = snapshot.tools[0].provenance

    assert provenance["source_url"] == "https://example.test/openapi.json"
    assert provenance["approved_base_url"] == "https://api.example.test/v1"
    serialized = snapshot.model_dump_json()
    assert "user:password" not in serialized
    assert "token=secret" not in serialized
    assert "should-not-render" not in serialized
    assert "fragment" not in serialized



def test_inspection_fail_closes_on_malformed_or_non_http_provenance_urls() -> None:
    tool = sample_tool()
    tool.execution_metadata.update(
        {
            "source_url": "https://user:password@example.test:notaport/path?token=secret",
            "approved_base_url": "ftp://user:password@example.test/private?token=secret",
        }
    )

    snapshot = inspect_registry(_registry_with_tool(tool))
    provenance = snapshot.tools[0].provenance

    assert provenance["source_url"] == "<redacted-invalid-url>"
    assert provenance["approved_base_url"] == "<redacted-invalid-url>"
    serialized = snapshot.model_dump_json()
    assert "user:password" not in serialized
    assert "token=secret" not in serialized



def test_live_inspection_reports_access_health_without_probe_callable() -> None:
    router = SchemaRouter(unavailable_cooldown_seconds=60)
    router.add_tool(
        ToolSpec(
            name="materials_api",
            provider="materials",
            access_mode="openapi",
            endpoints=[EndpointSpec(name="read", read_only=True)],
        )
    )
    router.register_health_probe("materials_api", "read", lambda: True)
    router.mark_access_unavailable("materials_api", "read")

    snapshot = router.inspect()

    assert snapshot.execution.unavailable_access_paths == ["materials_api.read"]
    assert snapshot.execution.health_monitor_running is False
    assert len(snapshot.execution.health_probes) == 1
    probe = snapshot.execution.health_probes[0]
    assert probe.tool == "materials_api"
    assert probe.endpoint == "read"
    assert probe.status == "unknown"

    serialized = snapshot.model_dump_json()
    assert "<lambda>" not in serialized



def test_live_inspection_distinguishes_unbound_and_stale_bindings() -> None:
    router = SchemaRouter()
    ready_key = router.add_callable(_echo)

    unbound_tool = ToolSpec(
        name="unbound",
        endpoints=[EndpointSpec(name="read", read_only=True)],
    )
    router.add_tool(unbound_tool)

    stale_tool = router.registry.get(ready_key).model_copy(
        update={"description": "replacement contract"},
        deep=True,
    )
    router.registry.register(stale_tool, replace=True)

    snapshot = router.inspect()

    assert snapshot.execution.binding_states[ready_key] == "stale"
    assert snapshot.execution.binding_states["unbound"] == "unbound"



def test_live_inspection_reports_orphaned_binding_after_registry_removal() -> None:
    registry = InMemoryRegistry()
    router = SchemaRouter(registry=registry)
    key = router.add_callable(_echo)

    registry.unregister(key)

    snapshot = router.inspect()

    assert snapshot.execution.bound_tools == [key]
    assert snapshot.execution.binding_states[key] == "orphaned"

    html = render_dashboard(snapshot.registry, live=snapshot)
    assert "Binding states" in html
    assert "orphaned" in html



def test_registry_inspection_exposes_typed_unit_contracts() -> None:
    registry = InMemoryRegistry()
    registry.register(
        ToolSpec(
            name="mixed_data",
            endpoints=[
                EndpointSpec(
                    name="read",
                    read_only=True,
                    output_fields=[
                        FieldSpec(
                            name="abstract",
                            semantic_id="abstract_text",
                            json_schema={"type": "string"},
                        ),
                        FieldSpec(
                            name="elastic_modulus",
                            semantic_id="elastic_modulus",
                            json_schema={"type": "number"},
                            unit="GPa",
                            unit_normalization=UnitNormalizationSpec(
                                dimension="pressure",
                                canonical_unit="Pa",
                                scale=1_000_000_000.0,
                            ),
                        ),
                        FieldSpec(
                            name="particle_sizes",
                            semantic_id="particle_size",
                            json_schema={
                                "type": "array",
                                "items": {"type": ["number", "null"]},
                            },
                            unit="nm",
                        ),
                    ],
                )
            ],
        )
    )

    snapshot = inspect_registry(registry)
    fields = {
        field.name: field
        for field in snapshot.tools[0].endpoints[0].fields
    }

    assert fields["abstract"].type_signature == "string"
    assert fields["abstract"].source_unit is None
    assert fields["elastic_modulus"].type_signature == "number"
    assert fields["elastic_modulus"].source_unit == "GPa"
    assert fields["elastic_modulus"].unit == "Pa"
    assert fields["elastic_modulus"].dimension == "pressure"
    assert fields["elastic_modulus"].normalized is True
    assert fields["elastic_modulus"].normalization_scale == 1_000_000_000.0
    assert fields["particle_sizes"].type_signature == "array<number|null>"
    assert fields["particle_sizes"].unit == "nm"


def test_dashboard_renders_typed_unit_contracts() -> None:
    registry = InMemoryRegistry()
    registry.register(
        ToolSpec(
            name="scientific",
            endpoints=[
                EndpointSpec(
                    name="read",
                    read_only=True,
                    output_fields=[
                        FieldSpec(
                            name="abstract",
                            json_schema={"type": "string"},
                        ),
                        FieldSpec(
                            name="elastic_modulus",
                            json_schema={"type": "number"},
                            unit="GPa",
                            unit_normalization=UnitNormalizationSpec(
                                dimension="pressure",
                                canonical_unit="Pa",
                                scale=1_000_000_000.0,
                            ),
                        ),
                    ],
                )
            ],
        )
    )

    html = render_dashboard(inspect_registry(registry))

    assert "Field contracts" in html
    assert "abstract:string" in html
    assert "elastic_modulus:number [GPa→Pa; pressure]" in html



def test_registry_inspection_exposes_typed_input_parameter_contracts() -> None:
    registry = InMemoryRegistry()
    registry.register(
        ToolSpec(
            name="particles",
            endpoints=[
                EndpointSpec(
                    name="search",
                    read_only=True,
                    parameters=[
                        ParameterSpec(
                            name="max_size",
                            required=True,
                            location="query",
                            json_schema={"type": "number"},
                            unit="m",
                            unit_normalization=UnitNormalizationSpec(
                                dimension="length",
                                canonical_unit="nm",
                                scale=1e9,
                            ),
                        ),
                        ParameterSpec(
                            name="limit",
                            location="query",
                            json_schema={"type": "integer"},
                        ),
                    ],
                    output_fields=[FieldSpec(name="particle_size")],
                )
            ],
        )
    )

    snapshot = inspect_registry(registry)
    parameters = {
        parameter.name: parameter
        for parameter in snapshot.tools[0].endpoints[0].parameters
    }

    assert parameters["max_size"].type_signature == "number"
    assert parameters["max_size"].source_unit == "m"
    assert parameters["max_size"].unit == "nm"
    assert parameters["max_size"].dimension == "length"
    assert parameters["max_size"].normalized is True
    assert parameters["max_size"].normalization_scale == 1e9
    assert parameters["max_size"].normalization_offset == 0.0
    assert parameters["max_size"].required is True
    assert parameters["max_size"].location == "query"

    assert parameters["limit"].type_signature == "integer"
    assert parameters["limit"].unit is None
    assert parameters["limit"].normalized is False


def test_dashboard_renders_typed_input_parameter_contracts() -> None:
    registry = InMemoryRegistry()
    registry.register(
        ToolSpec(
            name="particles",
            endpoints=[
                EndpointSpec(
                    name="search",
                    read_only=True,
                    parameters=[
                        ParameterSpec(
                            name="max_size",
                            json_schema={"type": "number"},
                            unit="m",
                            unit_normalization=UnitNormalizationSpec(
                                dimension="length",
                                canonical_unit="nm",
                                scale=1e9,
                            ),
                        )
                    ],
                    output_fields=[FieldSpec(name="particle_size")],
                )
            ],
        )
    )

    html = render_dashboard(inspect_registry(registry))

    assert "Parameter contracts" in html
    assert "max_size:number [m→nm; length]" in html
