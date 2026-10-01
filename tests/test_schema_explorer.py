from __future__ import annotations

import json

import pytest

from schemarouter.cli import main
from schemarouter.errors import RegistrationError
from schemarouter.explorer import (
    build_capability_explorer_document,
    render_schema_explorer,
    write_schema_explorer,
)
from schemarouter.inspection import (
    ExecutionInspection,
    HealthProbeInspection,
    PlannerInspection,
    RouterInspection,
    SchemaWatchInspection,
    inspect_registry,
)
from schemarouter.models import (
    AuthRequirementSet,
    AuthSchemeRequirement,
    EndpointSpec,
    FieldSpec,
    ParameterSpec,
    ToolSpec,
    UnitNormalizationSpec,
)
from schemarouter.registry import InMemoryRegistry, SQLiteRegistry


def _endpoint(name: str = "search") -> EndpointSpec:
    return EndpointSpec(
        name=name,
        description="Search typed materials data",
        operation_aliases=["find"],
        parameters=[
            ParameterSpec(
                name="chemical_formula",
                wire_name="formula",
                description="Chemical formula filter",
                required=True,
                location="query",
                style="form",
                explode=True,
                json_schema={
                    "type": "string",
                    "default": "SHOULD_NOT_RENDER",
                    "examples": ["SHOULD_NOT_RENDER"],
                },
                aliases=["formula"],
            )
        ],
        input_schema={
            "type": "object",
            "properties": {
                "chemical_formula": {
                    "type": "string",
                    "example": "SHOULD_NOT_RENDER",
                }
            },
            "required": ["chemical_formula"],
        },
        output_fields=[
            FieldSpec(
                name="band_gap",
                semantic_id="materials.band_gap",
                description="Band gap",
                json_schema={"type": "number"},
                aliases=["Eg"],
                path=["data", "*", "band_gap"],
                result_path=["results", "*", "band_gap"],
                unit="eV",
                unit_normalization=UnitNormalizationSpec(
                    dimension="energy",
                    canonical_unit="eV",
                    scale=1.0,
                    offset=0.0,
                ),
                qualifiers={"temperature": "room"},
                identifier=False,
                source_type="measured",
                license="CC-BY-4.0",
            )
        ],
        output_schema={
            "type": "object",
            "properties": {
                "data": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "band_gap": {"type": "number"},
                        },
                    },
                }
            },
            "example": {"secret": "SHOULD_NOT_RENDER"},
        },
        method="GET",
        path="/materials",
        read_only=True,
        destructive=False,
        auth_requirements=[
            AuthRequirementSet(
                schemes=[
                    AuthSchemeRequirement(
                        name="apiKey",
                        kind="api_key",
                        location="header",
                        parameter_name="X-API-Key",
                    )
                ]
            )
        ],
        metadata={
            "authorization": "Bearer SHOULD_NOT_RENDER",
        },
    )


def _tool(
    name: str,
    protocol: str,
    *,
    remote: bool = True,
    endpoint: EndpointSpec | None = None,
) -> ToolSpec:
    metadata = {
        "secret": "SHOULD_NOT_RENDER",
    }
    if name == "openapi_tool":
        metadata["source_url"] = (
            "https://user:pass@example.test/openapi.json"
            "?token=SHOULD_NOT_RENDER"
        )
    return ToolSpec(
        name=name,
        description=f"{protocol} capability",
        endpoints=[endpoint or _endpoint()],
        source_type=protocol,
        provider=f"{protocol}-provider",
        access_mode=protocol,
        remote=remote,
        metadata=metadata,
    )


def _registry() -> InMemoryRegistry:
    registry = InMemoryRegistry()
    protocols = [
        ("openapi_tool", "openapi", True),
        ("mcp_tool", "mcp", True),
        ("graphql_tool", "graphql", True),
        ("odata_tool", "odata", True),
        ("openrpc_tool", "openrpc", True),
        ("optimade_tool", "optimade", True),
        ("python_tool", "python", False),
        ("sdk_tool", "sdk", False),
    ]
    for name, protocol, remote in protocols:
        registry.register(
            _tool(
                name,
                protocol,
                remote=remote,
            )
        )
    return registry


def test_explorer_document_is_protocol_neutral_and_complete() -> None:
    registry = _registry()

    document = build_capability_explorer_document(registry)

    assert document.tool_count == 8
    assert document.endpoint_count == 8
    assert {
        tool.access_mode for tool in document.tools
    } == {
        "openapi",
        "mcp",
        "graphql",
        "odata",
        "openrpc",
        "optimade",
        "python",
        "sdk",
    }

    openapi = next(
        tool for tool in document.tools if tool.key == "openapi_tool"
    )
    endpoint = openapi.endpoints[0]

    assert endpoint.route_id == "openapi_tool:search"
    assert endpoint.mode == "read-only"
    assert endpoint.auth_required is True
    assert endpoint.auth_alternatives[0][0].parameter_name == "X-API-Key"
    assert endpoint.parameters[0].wire_name == "formula"
    assert endpoint.parameters[0].required is True
    assert endpoint.parameters[0].style == "form"
    assert endpoint.parameters[0].explode is True
    assert endpoint.output_fields[0].semantic_id == "materials.band_gap"
    assert endpoint.output_fields[0].unit == "eV"
    assert endpoint.output_fields[0].path == ["data", "*", "band_gap"]
    assert endpoint.output_fields[0].result_path == ["results", "*", "band_gap"]
    assert endpoint.output_fields[0].unit_normalization is not None
    assert (
        endpoint.output_fields[0]
        .unit_normalization.canonical_unit
        == "eV"
    )
    assert endpoint.fingerprint
    assert openapi.fingerprint


def test_explorer_document_redacts_metadata_urls_and_schema_examples() -> None:
    registry = _registry()

    document = build_capability_explorer_document(registry)
    payload = document.model_dump_json()
    html = render_schema_explorer(document)

    assert "SHOULD_NOT_RENDER" not in payload
    assert "SHOULD_NOT_RENDER" not in html
    assert "user:pass" not in payload
    assert "token=" not in payload

    openapi = next(
        tool for tool in document.tools if tool.key == "openapi_tool"
    )
    assert openapi.provenance["source_url"] == (
        "https://example.test/openapi.json"
    )
    parameter_schema = openapi.endpoints[0].parameters[0].json_schema
    assert "default" not in parameter_schema
    assert "examples" not in parameter_schema
    assert "example" not in openapi.endpoints[0].output_schema


def test_explorer_can_join_privacy_safe_live_status() -> None:
    registry = _registry()
    snapshot = RouterInspection(
        registry=inspect_registry(registry),
        planner=PlannerInspection(
            analyzer="RuleBasedQueryAnalyzer",
        ),
        execution=ExecutionInspection(
            binding_states={
                "openapi_tool": "ready",
            },
            unavailable_access_paths=[
                "openapi_tool:search",
            ],
            health_probes=[
                HealthProbeInspection(
                    tool="openapi_tool",
                    endpoint="search",
                    status="degraded",
                    last_error_type="TimeoutError",
                )
            ],
            schema_watches=[
                SchemaWatchInspection(
                    tool="openapi_tool",
                    status="pending_review",
                    interval_seconds=60,
                    apply_compatible=True,
                    pending_review=True,
                    pending_change_count=2,
                    pending_candidate_fingerprint="candidate-fingerprint",
                    pending_candidate_source_identity="source-identity",
                )
            ],
        ),
    )

    document = build_capability_explorer_document(
        registry,
        live=snapshot,
    )
    tool = next(
        item for item in document.tools if item.key == "openapi_tool"
    )
    endpoint = tool.endpoints[0]

    assert document.live is True
    assert tool.binding_state == "ready"
    assert tool.watch is not None
    assert tool.watch.pending_review is True
    assert tool.watch.pending_change_count == 2
    assert endpoint.status is not None
    assert endpoint.status.binding_state == "ready"
    assert endpoint.status.health_status == "degraded"
    assert endpoint.status.health_error_type == "TimeoutError"
    assert endpoint.status.unavailable is True


def test_schema_explorer_html_is_static_self_contained_and_searchable(
    tmp_path,
) -> None:
    document = build_capability_explorer_document(_registry())

    html = render_schema_explorer(document)
    output = write_schema_explorer(
        document,
        tmp_path / "schema-explorer.html",
    )

    assert output.read_text(encoding="utf-8") == html
    assert "<script src=" not in html
    assert "<link rel=" not in html
    assert "SchemaRouter Capability Explorer" in html
    assert "Search tool, endpoint, provider" in html
    assert "openapi_tool:search" in html
    assert "materials.band_gap" in html
    assert "eV" in html
    assert "Copyable JSON contract" in html


def test_embedded_explorer_document_is_valid_json_and_script_safe() -> None:
    registry = InMemoryRegistry()
    registry.register(
        _tool(
            "script_safe",
            "python",
            remote=False,
            endpoint=EndpointSpec(
                name="read",
                description="</script><script>alert(1)</script>",
                read_only=True,
                output_schema={"type": "object"},
            ),
        )
    )
    document = build_capability_explorer_document(registry)

    html = render_schema_explorer(document)

    marker = '<script id="schemarouter-document" type="application/json">'
    payload = html.split(marker, 1)[1].split("</script>", 1)[0]
    decoded = json.loads(payload)

    assert decoded["tools"][0]["key"] == "script_safe"
    assert "</script><script>" not in payload
    assert "\\u003c/script>" in payload


def test_schema_explorer_cli_exports_static_html(tmp_path, capsys) -> None:
    registry_path = tmp_path / "registry.sqlite3"
    output = tmp_path / "explorer.html"
    with SQLiteRegistry(registry_path) as registry:
        registry.register(_tool("openapi_tool", "openapi"))

    assert (
        main(
            [
                "explorer",
                "--registry",
                str(registry_path),
                "--output",
                str(output),
            ]
        )
        == 0
    )

    assert output.exists()
    assert "SchemaRouter Capability Explorer" in output.read_text(encoding="utf-8")
    assert str(output) in capsys.readouterr().out


def test_explorer_rejects_live_snapshot_from_stale_registry_version() -> None:
    registry = InMemoryRegistry()
    registry.register(_tool("one", "python", remote=False))
    stale = RouterInspection(
        registry=inspect_registry(registry),
        planner=PlannerInspection(analyzer="RuleBasedQueryAnalyzer"),
        execution=ExecutionInspection(),
    )

    registry.register(_tool("two", "mcp"))

    with pytest.raises(
        RegistrationError,
        match="registry version does not match",
    ):
        build_capability_explorer_document(
            registry,
            live=stale,
        )


def test_explorer_rejects_live_snapshot_with_contract_fingerprint_mismatch() -> None:
    registry = InMemoryRegistry()
    registry.register(_tool("one", "python", remote=False))
    snapshot = inspect_registry(registry)
    mismatched = snapshot.model_copy(deep=True)
    mismatched.tools[0].fingerprint = "f" * 64

    live = RouterInspection(
        registry=mismatched,
        planner=PlannerInspection(analyzer="RuleBasedQueryAnalyzer"),
        execution=ExecutionInspection(),
    )

    with pytest.raises(
        RegistrationError,
        match="fingerprints do not match",
    ):
        build_capability_explorer_document(
            registry,
            live=live,
        )


def test_explorer_copy_targets_remain_unique_with_auth_alternatives() -> None:
    registry = InMemoryRegistry()
    registry.register(_tool("first", "openapi"))
    registry.register(_tool("second", "openapi"))

    html = render_schema_explorer(
        build_capability_explorer_document(registry)
    )

    assert html.count('id="route-1"') == 1
    assert html.count('id="contract-1"') == 1
    assert html.count('id="route-2"') == 1
    assert html.count('id="contract-2"') == 1
