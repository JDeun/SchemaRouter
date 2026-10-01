from __future__ import annotations

import datetime
import re

import pytest

from schemarouter.cli import main
from schemarouter.errors import RegistrationError
from schemarouter.explorer import (
    SchemaExplorerDocument,
    build_schema_explorer_document,
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


def _capability(
    name: str,
    adapter: str,
    *,
    provider: str | None = None,
    endpoint: EndpointSpec | None = None,
) -> ToolSpec:
    return ToolSpec(
        name=name,
        provider=provider,
        access_mode=adapter,
        description=f"{adapter} capability",
        endpoints=[
            endpoint
            or EndpointSpec(
                name="read",
                read_only=True,
            )
        ],
        execution_metadata={"adapter": adapter},
        metadata={
            "source_url": (
                "https://user:password@example.test/schema"
                "?token=must-not-render#fragment"
            ),
            "arbitrary_secret": "must-not-render",
        },
    )


def _rich_endpoint() -> EndpointSpec:
    return EndpointSpec(
        name="search",
        description='Search <script>alert("endpoint")</script>',
        operation_aliases=["find materials", "lookup composition"],
        method="GET",
        path="/materials",
        read_only=True,
        auth_requirements=[
            AuthRequirementSet(
                schemes=[
                    AuthSchemeRequirement(
                        name="ApiKey",
                        kind="api_key",
                        location="header",
                        parameter_name="X-API-Key",
                    )
                ]
            )
        ],
        parameters=[
            ParameterSpec(
                name="elements",
                wire_name="elements[]",
                description="Element filter",
                required=True,
                location="query",
                style="form",
                explode=True,
                json_schema={
                    "type": "array",
                    "items": {
                        "type": "string",
                        "enum": ["Li", "Fe", "O"],
                    },
                    "default": ["Li"],
                },
                aliases=["chemical elements"],
            )
        ],
        input_schema={
            "type": "object",
            "properties": {
                "elements": {
                    "type": "array",
                    "items": {"type": "string"},
                }
            },
        },
        output_fields=[
            FieldSpec(
                name="band_gap",
                semantic_id="materials.band_gap",
                description="Electronic band gap",
                json_schema={"type": "number"},
                aliases=["gap"],
                path=["results", "*", "band_gap"],
                result_path=["results", "*", "band_gap"],
                unit="meV",
                unit_normalization=UnitNormalizationSpec(
                    dimension="energy",
                    canonical_unit="eV",
                    scale=0.001,
                ),
                qualifiers={"temperature": "300 K"},
                identifier=False,
                source_type="measured",
                license="CC-BY-4.0",
            )
        ],
        output_schema={
            "type": "object",
            "properties": {
                "results": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "band_gap": {"type": "number"}
                        },
                    },
                }
            },
        },
    )


def test_explorer_document_covers_protocol_neutral_capability_catalog() -> None:
    registry = InMemoryRegistry()
    adapters = [
        "openapi",
        "mcp",
        "graphql",
        "odata",
        "openrpc",
        "optimade",
        "python",
        "private_sdk",
    ]
    for index, adapter in enumerate(adapters):
        registry.register(
            _capability(
                f"tool_{index}",
                adapter,
                provider=f"provider-{index}",
                endpoint=(
                    _rich_endpoint()
                    if adapter == "openapi"
                    else None
                ),
            )
        )

    document = build_schema_explorer_document(registry)

    assert isinstance(document, SchemaExplorerDocument)
    assert document.tool_count == len(adapters)
    assert document.endpoint_count == len(adapters)
    assert {tool.adapter for tool in document.tools} == set(adapters)

    openapi = next(
        tool for tool in document.tools if tool.adapter == "openapi"
    )
    endpoint = openapi.endpoints[0]
    assert endpoint.route_id == f"{openapi.key}.search"
    assert endpoint.mode == "read-only"
    assert endpoint.operation_aliases == [
        "find materials",
        "lookup composition",
    ]
    assert endpoint.auth_required is True
    assert endpoint.auth_requirements[0].schemes[0].kind == "api_key"

    parameter = endpoint.parameters[0]
    assert parameter.wire_name == "elements[]"
    assert parameter.required is True
    assert parameter.style == "form"
    assert parameter.explode is True
    assert parameter.json_schema["default"] == ["Li"]

    field = endpoint.output_fields[0]
    assert field.semantic_id == "materials.band_gap"
    assert field.path == ["results", "*", "band_gap"]
    assert field.result_path == ["results", "*", "band_gap"]
    assert field.unit == "meV"
    assert field.unit_normalization is not None
    assert field.unit_normalization.canonical_unit == "eV"
    assert field.unit_normalization.dimension == "energy"
    assert field.qualifiers == {"temperature": "300 K"}


def test_explorer_document_does_not_include_arbitrary_metadata_or_url_secrets() -> None:
    registry = InMemoryRegistry()
    registry.register(_capability("safe", "openapi"))

    document = build_schema_explorer_document(registry)
    serialized = document.model_dump_json()

    assert "arbitrary_secret" not in serialized
    assert "must-not-render" not in serialized
    assert "user:password" not in serialized
    assert "token=" not in serialized
    assert document.tools[0].provenance["source_url"] == (
        "https://example.test/schema"
    )


def test_explorer_html_is_self_contained_searchable_and_read_only() -> None:
    registry = InMemoryRegistry()
    registry.register(
        _capability(
            "materials",
            "openapi",
            provider="materials-provider",
            endpoint=_rich_endpoint(),
        )
    )
    document = build_schema_explorer_document(registry)

    html = render_schema_explorer(document)

    assert "<!doctype html>" in html
    assert "SchemaRouter Capability Explorer" in html
    assert 'id="search"' in html
    assert 'id="provider"' in html
    assert 'id="adapter"' in html
    assert 'id="method"' in html
    assert 'id="mode"' in html
    assert "Copy route ID" in html
    assert "Copy JSON" in html
    assert "materials.band_gap" in html
    assert "meV" in html
    assert "energy" in html
    assert "X-API-Key" in html
    assert "Try it out" not in html
    assert "execute" not in html.casefold()

    assert re.search(r"<script[^>]+src=", html, re.IGNORECASE) is None
    assert re.search(r"<link[^>]+href=", html, re.IGNORECASE) is None


def test_explorer_html_escapes_remote_contract_text_and_schema_values() -> None:
    endpoint = _rich_endpoint()
    endpoint.output_schema["x-malicious"] = (
        '</script><script>alert("schema")</script>'
    )
    registry = InMemoryRegistry()
    registry.register(
        ToolSpec(
            name="xss",
            description='<img src=x onerror="alert(1)">',
            endpoints=[endpoint],
            execution_metadata={"adapter": "openapi"},
        )
    )

    html = render_schema_explorer(
        build_schema_explorer_document(registry)
    )

    assert '<img src=x onerror="alert(1)">' not in html
    assert '<script>alert("endpoint")</script>' not in html
    assert '<script>alert("schema")</script>' not in html
    assert "&lt;img src=x onerror=" in html
    assert "&lt;script&gt;alert" in html


def test_explorer_live_status_is_joined_without_runtime_authority() -> None:
    registry = InMemoryRegistry()
    registry.register(
        _capability(
            "materials",
            "openapi",
            endpoint=EndpointSpec(
                name="read",
                read_only=True,
            ),
        )
    )
    snapshot = inspect_registry(registry)
    now = datetime.datetime(
        2026,
        10,
        1,
        9,
        30,
        tzinfo=datetime.timezone.utc,
    )
    live = RouterInspection(
        registry=snapshot,
        planner=PlannerInspection(analyzer="KeywordAnalyzer"),
        execution=ExecutionInspection(
            bound_tools=["materials"],
            binding_states={"materials": "ready"},
            unavailable_access_paths=["materials.read"],
            health_monitor_running=True,
            health_probes=[
                HealthProbeInspection(
                    tool="materials",
                    endpoint="read",
                    status="unavailable",
                    last_checked_at=now,
                    last_error_type="TimeoutError",
                )
            ],
            schema_watcher_running=True,
            schema_watches=[
                SchemaWatchInspection(
                    tool="materials",
                    status="pending_review",
                    interval_seconds=60,
                    apply_compatible=True,
                    last_checked_at=now,
                    last_compatibility="breaking",
                    pending_review=True,
                    pending_change_count=2,
                    pending_reviewed_current_fingerprint="a" * 64,
                    pending_candidate_fingerprint="b" * 64,
                    pending_candidate_source_identity="c" * 64,
                )
            ],
        ),
    )

    document = build_schema_explorer_document(
        registry,
        live=live,
    )

    assert document.live_status_included is True
    tool = document.tools[0]
    assert tool.live is not None
    assert tool.live.binding_state == "ready"
    assert tool.live.schema_watch_status == "pending_review"
    assert tool.live.pending_review is True
    assert tool.live.pending_change_count == 2

    endpoint = tool.endpoints[0]
    assert endpoint.live is not None
    assert endpoint.live.unavailable is True
    assert endpoint.live.health_status == "unavailable"
    assert endpoint.live.health_last_error_type == "TimeoutError"

    serialized = document.model_dump_json()
    assert "callable" not in serialized.casefold()
    assert "authorization" not in serialized.casefold()


def test_explorer_rejects_live_snapshot_from_different_registry_version() -> None:
    registry = InMemoryRegistry()
    registry.register(_capability("one", "python"))
    stale = RouterInspection(
        registry=inspect_registry(registry),
        planner=PlannerInspection(analyzer="KeywordAnalyzer"),
        execution=ExecutionInspection(),
    )

    registry.register(_capability("two", "mcp"))

    with pytest.raises(
        RegistrationError,
        match="registry version does not match",
    ):
        build_schema_explorer_document(
            registry,
            live=stale,
        )


def test_explorer_rejects_live_snapshot_with_fingerprint_mismatch() -> None:
    registry = InMemoryRegistry()
    registry.register(_capability("one", "python"))
    snapshot = inspect_registry(registry)
    changed = snapshot.model_copy(deep=True)
    changed.tools[0].fingerprint = "f" * 64
    live = RouterInspection(
        registry=changed,
        planner=PlannerInspection(analyzer="KeywordAnalyzer"),
        execution=ExecutionInspection(),
    )

    with pytest.raises(
        RegistrationError,
        match="fingerprints do not match",
    ):
        build_schema_explorer_document(
            registry,
            live=live,
        )


def test_write_schema_explorer_creates_static_html(tmp_path) -> None:
    registry = InMemoryRegistry()
    registry.register(_capability("one", "openrpc"))
    document = build_schema_explorer_document(registry)
    destination = tmp_path / "nested" / "explorer.html"

    result = write_schema_explorer(document, destination)

    assert result == destination
    html = destination.read_text(encoding="utf-8")
    assert "SchemaRouter Capability Explorer" in html
    assert "one.read" in html


def test_schema_explorer_cli_exports_persisted_registry(
    tmp_path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    registry_path = tmp_path / "registry.sqlite3"
    output = tmp_path / "explorer.html"

    with SQLiteRegistry(registry_path) as registry:
        registry.register(
            _capability(
                "materials",
                "openapi",
                endpoint=_rich_endpoint(),
            )
        )

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

    assert str(output) in capsys.readouterr().out
    html = output.read_text(encoding="utf-8")
    assert "SchemaRouter Capability Explorer" in html
    assert "materials.search" in html
    assert "band_gap" in html
    assert "Try it out" not in html
