from __future__ import annotations

import datetime
import json
from html import escape
from pathlib import Path
from typing import Any, Literal, Sequence

from pydantic import Field

from .errors import RegistrationError
from .inspection import RouterInspection, tool_spec_document
from .models import StrictModel
from .registry import ToolRegistry

ExplorerMode = Literal[
    "read-only",
    "mutating",
    "destructive",
    "unclassified",
]


class ExplorerParameter(StrictModel):
    """Allowlisted parameter contract rendered by the Schema Explorer."""

    name: str
    wire_name: str | None = None
    description: str = ""
    required: bool = False
    location: str
    style: str | None = None
    explode: bool | None = None
    allow_reserved: bool = False
    json_schema: dict[str, Any] = Field(default_factory=dict)
    aliases: list[str] = Field(default_factory=list)


class ExplorerUnitNormalization(StrictModel):
    dimension: str
    canonical_unit: str
    scale: float = 1.0
    offset: float = 0.0


class ExplorerField(StrictModel):
    """Allowlisted output-field contract rendered by the Schema Explorer."""

    name: str
    semantic_id: str | None = None
    description: str = ""
    json_schema: dict[str, Any] = Field(default_factory=dict)
    aliases: list[str] = Field(default_factory=list)
    path: list[str] = Field(default_factory=list)
    result_path: list[str] = Field(default_factory=list)
    unit: str | None = None
    unit_normalization: ExplorerUnitNormalization | None = None
    qualifiers: dict[str, str] = Field(default_factory=dict)
    identifier: bool = False
    source_type: str | None = None
    license: str | None = None


class ExplorerAuthScheme(StrictModel):
    """Secret-free identity of one declared authentication requirement."""

    name: str
    kind: str
    location: str | None = None
    parameter_name: str | None = None
    http_scheme: str | None = None
    scopes: list[str] = Field(default_factory=list)
    declared_type: str | None = None


class ExplorerAuthRequirement(StrictModel):
    schemes: list[ExplorerAuthScheme] = Field(default_factory=list)


class ExplorerEndpointLiveStatus(StrictModel):
    unavailable: bool = False
    health_status: str | None = None
    health_last_checked_at: datetime.datetime | None = None
    health_last_error_type: str | None = None


class ExplorerToolLiveStatus(StrictModel):
    binding_state: str | None = None
    schema_watch_status: str | None = None
    schema_watch_last_checked_at: datetime.datetime | None = None
    schema_watch_last_applied_at: datetime.datetime | None = None
    schema_watch_last_compatibility: str | None = None
    pending_review: bool = False
    pending_change_count: int = Field(default=0, ge=0)
    pending_reviewed_current_fingerprint: str | None = None
    pending_candidate_fingerprint: str | None = None
    pending_candidate_source_identity: str | None = None
    schema_watch_last_error_type: str | None = None


class ExplorerEndpoint(StrictModel):
    route_id: str
    name: str
    description: str = ""
    method: str | None = None
    path: str | None = None
    mode: ExplorerMode
    read_only: bool | None = None
    destructive: bool | None = None
    operation_aliases: list[str] = Field(default_factory=list)
    auth_requirements: list[ExplorerAuthRequirement] = Field(
        default_factory=list
    )
    parameters: list[ExplorerParameter] = Field(default_factory=list)
    input_schema: dict[str, Any] = Field(default_factory=dict)
    output_fields: list[ExplorerField] = Field(default_factory=list)
    output_schema: dict[str, Any] = Field(default_factory=dict)
    fingerprint: str
    live: ExplorerEndpointLiveStatus | None = None

    @property
    def auth_required(self) -> bool:
        return bool(self.auth_requirements)


class ExplorerTool(StrictModel):
    key: str
    name: str
    namespace: str | None = None
    description: str = ""
    source_type: str | None = None
    license: str | None = None
    provider: str | None = None
    access_mode: str | None = None
    adapter: str | None = None
    fingerprint: str
    provenance: dict[str, object] = Field(default_factory=dict)
    endpoints: list[ExplorerEndpoint] = Field(default_factory=list)
    live: ExplorerToolLiveStatus | None = None


class SchemaExplorerDocument(StrictModel):
    """Stable, privacy-safe capability documentation model."""

    registry_version: int = Field(ge=0)
    tool_count: int = Field(ge=0)
    endpoint_count: int = Field(ge=0)
    live_status_included: bool = False
    tools: list[ExplorerTool] = Field(default_factory=list)


def _mode(
    read_only: bool | None,
    destructive: bool | None,
) -> ExplorerMode:
    if destructive is True:
        return "destructive"
    if read_only is True:
        return "read-only"
    if read_only is False:
        return "mutating"
    return "unclassified"


def _stable_registry_snapshot(
    registry: ToolRegistry,
    *,
    attempts: int = 3,
):
    for _ in range(attempts):
        before = registry.version
        tools = registry.tools()
        after = registry.version
        if before == after:
            return before, tools
    raise RegistrationError(
        "registry changed repeatedly while building the Schema Explorer"
    )


def _live_status_maps(
    live: RouterInspection | None,
    *,
    registry_version: int,
    tool_fingerprints: dict[str, str],
):
    if live is None:
        return {}, {}, {}

    if live.registry.version != registry_version:
        raise RegistrationError(
            "live inspection registry version does not match explorer snapshot"
        )

    live_fingerprints = {
        tool.key: tool.fingerprint
        for tool in live.registry.tools
    }
    if live_fingerprints != tool_fingerprints:
        raise RegistrationError(
            "live inspection capability fingerprints do not match explorer snapshot"
        )

    health = {
        (probe.tool, probe.endpoint): probe
        for probe in live.execution.health_probes
    }
    watches = {
        watch.tool: watch
        for watch in live.execution.schema_watches
    }
    unavailable = set(live.execution.unavailable_access_paths)
    return health, watches, {
        "binding_states": dict(live.execution.binding_states),
        "unavailable": unavailable,
    }


def build_schema_explorer_document(
    registry: ToolRegistry,
    *,
    live: RouterInspection | None = None,
) -> SchemaExplorerDocument:
    """Build a complete allowlisted explorer document from one registry snapshot."""

    version, tool_specs = _stable_registry_snapshot(registry)
    safe_documents = [
        tool_spec_document(tool)
        for tool in tool_specs
    ]
    fingerprints = {
        str(document["key"]): str(document["fingerprint"])
        for document in safe_documents
    }
    health, watches, execution = _live_status_maps(
        live,
        registry_version=version,
        tool_fingerprints=fingerprints,
    )
    binding_states = execution.get("binding_states", {})
    unavailable = execution.get("unavailable", set())

    tools: list[ExplorerTool] = []
    for document in safe_documents:
        key = str(document["key"])
        provenance = dict(document.get("provenance") or {})
        adapter_value = provenance.get("adapter")
        adapter = (
            str(adapter_value)
            if isinstance(adapter_value, str)
            else None
        )

        watch = watches.get(key)
        tool_live = None
        if live is not None:
            tool_live = ExplorerToolLiveStatus(
                binding_state=binding_states.get(key),
                schema_watch_status=(
                    watch.status
                    if watch is not None
                    else None
                ),
                schema_watch_last_checked_at=(
                    watch.last_checked_at
                    if watch is not None
                    else None
                ),
                schema_watch_last_applied_at=(
                    watch.last_applied_at
                    if watch is not None
                    else None
                ),
                schema_watch_last_compatibility=(
                    watch.last_compatibility
                    if watch is not None
                    else None
                ),
                pending_review=(
                    watch.pending_review
                    if watch is not None
                    else False
                ),
                pending_change_count=(
                    watch.pending_change_count
                    if watch is not None
                    else 0
                ),
                pending_reviewed_current_fingerprint=(
                    watch.pending_reviewed_current_fingerprint
                    if watch is not None
                    else None
                ),
                pending_candidate_fingerprint=(
                    watch.pending_candidate_fingerprint
                    if watch is not None
                    else None
                ),
                pending_candidate_source_identity=(
                    watch.pending_candidate_source_identity
                    if watch is not None
                    else None
                ),
                schema_watch_last_error_type=(
                    watch.last_error_type
                    if watch is not None
                    else None
                ),
            )

        endpoints: list[ExplorerEndpoint] = []
        for raw_endpoint in document.get("endpoints", []):
            endpoint = dict(raw_endpoint)
            endpoint_name = str(endpoint["name"])
            route_id = f"{key}.{endpoint_name}"
            probe = health.get((key, endpoint_name))
            endpoint_live = None
            if live is not None:
                endpoint_live = ExplorerEndpointLiveStatus(
                    unavailable=route_id in unavailable,
                    health_status=(
                        probe.status
                        if probe is not None
                        else None
                    ),
                    health_last_checked_at=(
                        probe.last_checked_at
                        if probe is not None
                        else None
                    ),
                    health_last_error_type=(
                        probe.last_error_type
                        if probe is not None
                        else None
                    ),
                )

            read_only = endpoint.get("read_only")
            destructive = endpoint.get("destructive")
            endpoints.append(
                ExplorerEndpoint(
                    route_id=route_id,
                    name=endpoint_name,
                    description=str(endpoint.get("description") or ""),
                    method=(
                        str(endpoint["method"])
                        if endpoint.get("method") is not None
                        else None
                    ),
                    path=(
                        str(endpoint["path"])
                        if endpoint.get("path") is not None
                        else None
                    ),
                    mode=_mode(read_only, destructive),
                    read_only=read_only,
                    destructive=destructive,
                    operation_aliases=[
                        str(value)
                        for value in endpoint.get(
                            "operation_aliases",
                            [],
                        )
                    ],
                    auth_requirements=[
                        ExplorerAuthRequirement.model_validate(value)
                        for value in endpoint.get(
                            "auth_requirements",
                            [],
                        )
                    ],
                    parameters=[
                        ExplorerParameter.model_validate(value)
                        for value in endpoint.get("parameters", [])
                    ],
                    input_schema=dict(endpoint.get("input_schema") or {}),
                    output_fields=[
                        ExplorerField.model_validate(value)
                        for value in endpoint.get(
                            "output_fields",
                            [],
                        )
                    ],
                    output_schema=dict(
                        endpoint.get("output_schema") or {}
                    ),
                    fingerprint=str(endpoint["fingerprint"]),
                    live=endpoint_live,
                )
            )

        tools.append(
            ExplorerTool(
                key=key,
                name=str(document["name"]),
                namespace=(
                    str(document["namespace"])
                    if document.get("namespace") is not None
                    else None
                ),
                description=str(document.get("description") or ""),
                source_type=(
                    str(document["source_type"])
                    if document.get("source_type") is not None
                    else None
                ),
                license=(
                    str(document["license"])
                    if document.get("license") is not None
                    else None
                ),
                provider=(
                    str(document["provider"])
                    if document.get("provider") is not None
                    else None
                ),
                access_mode=(
                    str(document["access_mode"])
                    if document.get("access_mode") is not None
                    else None
                ),
                adapter=adapter,
                fingerprint=str(document["fingerprint"]),
                provenance=provenance,
                endpoints=endpoints,
                live=tool_live,
            )
        )

    return SchemaExplorerDocument(
        registry_version=version,
        tool_count=len(tools),
        endpoint_count=sum(len(tool.endpoints) for tool in tools),
        live_status_included=live is not None,
        tools=tools,
    )


def _json(value: object) -> str:
    return json.dumps(
        value,
        indent=2,
        sort_keys=True,
        ensure_ascii=False,
    )


def _text(value: object | None) -> str:
    if value is None:
        return "—"
    if isinstance(value, datetime.datetime):
        return value.isoformat()
    return str(value)


def _badge(label: str, kind: str = "neutral") -> str:
    return (
        f'<span class="badge badge-{escape(kind)}">'
        f"{escape(label)}</span>"
    )


def _short(value: str | None) -> str:
    if not value:
        return "—"
    return value[:12]


def _schema_pre(
    title: str,
    schema: dict[str, Any],
    *,
    element_id: str | None = None,
) -> str:
    body = escape(_json(schema or {}))
    id_attr = (
        f' id="{escape(element_id)}"'
        if element_id is not None
        else ""
    )
    return (
        '<div class="schema-block">'
        f"<h5>{escape(title)}</h5>"
        f"<pre{id_attr}>{body}</pre>"
        "</div>"
    )


def _render_auth(
    requirements: Sequence[ExplorerAuthRequirement],
) -> str:
    if not requirements:
        return '<p class="muted">No authentication requirement declared.</p>'

    alternatives = []
    for index, requirement in enumerate(requirements, start=1):
        schemes = []
        for scheme in requirement.schemes:
            details = [scheme.kind]
            if scheme.location:
                details.append(scheme.location)
            if scheme.parameter_name:
                details.append(scheme.parameter_name)
            if scheme.http_scheme:
                details.append(scheme.http_scheme)
            if scheme.scopes:
                details.append("scopes=" + ",".join(scheme.scopes))
            if scheme.declared_type:
                details.append("declared=" + scheme.declared_type)
            schemes.append(
                "<li>"
                f"<strong>{escape(scheme.name)}</strong> "
                f"<code>{escape(' · '.join(details))}</code>"
                "</li>"
            )
        alternatives.append(
            '<div class="auth-alt">'
            f"<strong>Alternative {index}</strong>"
            f"<ul>{''.join(schemes)}</ul>"
            "</div>"
        )
    return "".join(alternatives)


def _render_parameters(
    parameters: Sequence[ExplorerParameter],
) -> str:
    if not parameters:
        return '<p class="muted">No declared parameters.</p>'

    rows = []
    for parameter in parameters:
        aliases = ", ".join(parameter.aliases) or "—"
        wire = parameter.wire_name or parameter.name
        serialization = []
        if parameter.style:
            serialization.append(f"style={parameter.style}")
        if parameter.explode is not None:
            serialization.append(f"explode={parameter.explode}")
        if parameter.allow_reserved:
            serialization.append("allowReserved=true")
        schema = escape(_json(parameter.json_schema or {}))
        rows.append(
            "<tr>"
            f"<td><code>{escape(parameter.name)}</code></td>"
            f"<td><code>{escape(wire)}</code></td>"
            f"<td>{escape(parameter.location)}</td>"
            f"<td>{'yes' if parameter.required else 'no'}</td>"
            f"<td>{escape(aliases)}</td>"
            f"<td>{escape(', '.join(serialization) or '—')}</td>"
            f"<td>{escape(parameter.description or '—')}</td>"
            f"<td><details><summary>schema</summary><pre>{schema}</pre></details></td>"
            "</tr>"
        )
    return (
        '<div class="table-wrap"><table>'
        "<thead><tr>"
        "<th>Name</th><th>Wire</th><th>Location</th><th>Required</th>"
        "<th>Aliases</th><th>Serialization</th><th>Description</th><th>Schema</th>"
        "</tr></thead>"
        f"<tbody>{''.join(rows)}</tbody></table></div>"
    )


def _render_fields(
    fields: Sequence[ExplorerField],
) -> str:
    if not fields:
        return '<p class="muted">No declared output fields.</p>'

    rows = []
    for field in fields:
        normalization = field.unit_normalization
        normalized = "—"
        if normalization is not None:
            normalized = (
                f"{field.unit or '?'} → {normalization.canonical_unit} "
                f"({normalization.dimension}; "
                f"x{normalization.scale:g}"
                f"{normalization.offset:+g})"
            )
        path = ".".join(field.path or [field.name])
        result_path = ".".join(
            field.result_path
            or field.path
            or [field.name]
        )
        qualifiers = ", ".join(
            f"{key}={value}"
            for key, value in sorted(field.qualifiers.items())
        ) or "—"
        schema = escape(_json(field.json_schema or {}))
        rows.append(
            "<tr>"
            f"<td><code>{escape(field.name)}</code></td>"
            f"<td>{escape(field.semantic_id or '—')}</td>"
            f"<td>{escape(field.unit or '—')}</td>"
            f"<td>{escape(normalized)}</td>"
            f"<td><code>{escape(path)}</code></td>"
            f"<td><code>{escape(result_path)}</code></td>"
            f"<td>{escape(qualifiers)}</td>"
            f"<td>{'yes' if field.identifier else 'no'}</td>"
            f"<td>{escape(', '.join(field.aliases) or '—')}</td>"
            f"<td><details><summary>schema</summary><pre>{schema}</pre></details></td>"
            "</tr>"
        )
    return (
        '<div class="table-wrap"><table>'
        "<thead><tr>"
        "<th>Field</th><th>Semantic ID</th><th>Unit</th><th>Normalization</th>"
        "<th>Source path</th><th>Result path</th><th>Qualifiers</th>"
        "<th>ID</th><th>Aliases</th><th>Schema</th>"
        "</tr></thead>"
        f"<tbody>{''.join(rows)}</tbody></table></div>"
    )


def _render_live_tool(status: ExplorerToolLiveStatus | None) -> str:
    if status is None:
        return ""

    pending = (
        _badge("pending review", "warning")
        if status.pending_review
        else ""
    )
    return (
        '<div class="live-strip">'
        f"{_badge('binding: ' + (status.binding_state or 'unknown'))}"
        f"{_badge('watch: ' + (status.schema_watch_status or 'none'))}"
        f"{pending}"
        '<span class="muted">'
        f"watch checked: {escape(_text(status.schema_watch_last_checked_at))} · "
        f"applied: {escape(_text(status.schema_watch_last_applied_at))} · "
        f"compatibility: {escape(status.schema_watch_last_compatibility or '—')} · "
        f"changes: {status.pending_change_count}"
        "</span>"
        "</div>"
    )


def _render_live_endpoint(
    status: ExplorerEndpointLiveStatus | None,
) -> str:
    if status is None:
        return ""

    availability = (
        _badge("unavailable", "danger")
        if status.unavailable
        else _badge("available", "ok")
    )
    health = _badge(
        "health: " + (status.health_status or "unprobed")
    )
    return (
        '<div class="live-strip">'
        f"{availability}{health}"
        '<span class="muted">'
        f"checked: {escape(_text(status.health_last_checked_at))} · "
        f"error: {escape(status.health_last_error_type or '—')}"
        "</span>"
        "</div>"
    )


def _render_endpoint(
    tool: ExplorerTool,
    endpoint: ExplorerEndpoint,
    *,
    index: int,
) -> str:
    method = endpoint.method or tool.access_mode or tool.adapter or "capability"
    method_kind = (
        "ok"
        if endpoint.method and endpoint.method.upper() == "GET"
        else "neutral"
    )
    mode_kind = {
        "read-only": "ok",
        "mutating": "warning",
        "destructive": "danger",
        "unclassified": "neutral",
    }[endpoint.mode]
    contract_id = f"contract-{index}"
    route_id = endpoint.route_id
    aliases = ", ".join(endpoint.operation_aliases) or "—"
    location = endpoint.path or "non-HTTP capability"
    contract_json = escape(
        endpoint.model_dump_json(
            indent=2,
            exclude={"live"},
        )
    )

    search_parts = [
        tool.key,
        tool.name,
        tool.provider or "",
        tool.adapter or "",
        tool.access_mode or "",
        endpoint.name,
        endpoint.method or "",
        endpoint.path or "",
        endpoint.mode,
        *endpoint.operation_aliases,
    ]
    for parameter in endpoint.parameters:
        search_parts.extend(
            [
                parameter.name,
                parameter.wire_name or "",
                parameter.location,
                *parameter.aliases,
            ]
        )
    for field in endpoint.output_fields:
        search_parts.extend(
            [
                field.name,
                field.semantic_id or "",
                field.unit or "",
                *field.aliases,
            ]
        )
        if field.unit_normalization is not None:
            search_parts.extend(
                [
                    field.unit_normalization.dimension,
                    field.unit_normalization.canonical_unit,
                ]
            )
    search_text = " ".join(search_parts).casefold()

    return f"""
<details class="endpoint"
  data-search="{escape(search_text, quote=True)}"
  data-mode="{escape(endpoint.mode, quote=True)}"
  data-method="{escape((endpoint.method or '').casefold(), quote=True)}">
  <summary>
    <span class="endpoint-title">{escape(endpoint.name)}</span>
    {_badge(method, method_kind)}
    {_badge(endpoint.mode, mode_kind)}
    {(_badge('auth required', 'warning') if endpoint.auth_required else '')}
    <code>{escape(location)}</code>
  </summary>
  <div class="endpoint-body">
    <div class="route-row">
      <code id="route-{index}">{escape(route_id)}</code>
      <button type="button" data-copy-target="route-{index}">Copy route ID</button>
    </div>
    <p>{escape(endpoint.description or 'No description.')}</p>
    <p><strong>Aliases:</strong> {escape(aliases)}</p>
    <p><strong>Fingerprint:</strong> <code>{escape(endpoint.fingerprint)}</code></p>
    {_render_live_endpoint(endpoint.live)}
    <section class="contract-section">
      <h4>Authentication</h4>
      {_render_auth(endpoint.auth_requirements)}
    </section>
    <section class="contract-section">
      <h4>Parameters</h4>
      {_render_parameters(endpoint.parameters)}
    </section>
    <section class="schema-grid">
      {_schema_pre('Input schema', endpoint.input_schema)}
      {_schema_pre('Output schema', endpoint.output_schema)}
    </section>
    <section class="contract-section">
      <h4>Output fields</h4>
      {_render_fields(endpoint.output_fields)}
    </section>
    <section class="contract-section">
      <div class="route-row">
        <h4>Safe contract JSON</h4>
        <button type="button" data-copy-target="{contract_id}">Copy JSON</button>
      </div>
      <pre id="{contract_id}">{contract_json}</pre>
    </section>
  </div>
</details>
"""


def render_schema_explorer(document: SchemaExplorerDocument) -> str:
    """Render a self-contained, read-only capability explorer."""

    providers = sorted(
        {
            tool.provider
            for tool in document.tools
            if tool.provider
        }
    )
    adapters = sorted(
        {
            tool.adapter
            for tool in document.tools
            if tool.adapter
        }
    )
    methods = sorted(
        {
            endpoint.method.upper()
            for tool in document.tools
            for endpoint in tool.endpoints
            if endpoint.method
        }
    )

    provider_options = "".join(
        f'<option value="{escape(value.casefold(), quote=True)}">'
        f"{escape(value)}</option>"
        for value in providers
    )
    adapter_options = "".join(
        f'<option value="{escape(value.casefold(), quote=True)}">'
        f"{escape(value)}</option>"
        for value in adapters
    )
    method_options = "".join(
        f'<option value="{escape(value.casefold(), quote=True)}">'
        f"{escape(value)}</option>"
        for value in methods
    )

    endpoint_index = 0
    tool_sections = []
    for tool in document.tools:
        endpoint_html = []
        for endpoint in tool.endpoints:
            endpoint_index += 1
            endpoint_html.append(
                _render_endpoint(
                    tool,
                    endpoint,
                    index=endpoint_index,
                )
            )

        provenance = escape(_json(tool.provenance))
        tool_search = " ".join(
            [
                tool.key,
                tool.name,
                tool.provider or "",
                tool.adapter or "",
                tool.access_mode or "",
                tool.source_type or "",
            ]
        ).casefold()
        tool_sections.append(
            f"""
<section class="tool"
  data-tool-search="{escape(tool_search, quote=True)}"
  data-provider="{escape((tool.provider or '').casefold(), quote=True)}"
  data-adapter="{escape((tool.adapter or '').casefold(), quote=True)}">
  <details open>
    <summary class="tool-summary">
      <span>
        <strong>{escape(tool.key)}</strong>
        {_badge(tool.adapter or tool.access_mode or tool.source_type or 'tool')}
      </span>
      <span class="muted">{len(tool.endpoints)} endpoints</span>
    </summary>
    <div class="tool-body">
      <p>{escape(tool.description or 'No description.')}</p>
      <div class="meta-grid">
        <div><strong>Provider</strong><br>{escape(tool.provider or '—')}</div>
        <div><strong>Access mode</strong><br>{escape(tool.access_mode or '—')}</div>
        <div><strong>Source type</strong><br>{escape(tool.source_type or '—')}</div>
        <div><strong>License</strong><br>{escape(tool.license or '—')}</div>
      </div>
      <p><strong>Fingerprint:</strong> <code>{escape(tool.fingerprint)}</code></p>
      {_render_live_tool(tool.live)}
      <details class="provenance">
        <summary>Safe provenance</summary>
        <pre>{provenance}</pre>
      </details>
      <div class="endpoint-list">{''.join(endpoint_html)}</div>
    </div>
  </details>
</section>
"""
        )

    live_badge = (
        _badge("live status included", "ok")
        if document.live_status_included
        else _badge("static registry snapshot")
    )

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>SchemaRouter Capability Explorer</title>
<style>
:root {{
  color-scheme: light dark;
  font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, sans-serif;
}}
* {{ box-sizing: border-box; }}
body {{
  margin: 0;
  background: Canvas;
  color: CanvasText;
}}
header {{
  position: sticky;
  top: 0;
  z-index: 5;
  padding: 20px clamp(18px, 4vw, 52px);
  border-bottom: 1px solid color-mix(in srgb, CanvasText 18%, transparent);
  background: color-mix(in srgb, Canvas 94%, transparent);
  backdrop-filter: blur(12px);
}}
h1 {{ margin: 0 0 6px; font-size: 1.5rem; }}
h2, h3, h4, h5 {{ margin-top: 0; }}
main {{ max-width: 1500px; margin: 0 auto; padding: 26px clamp(18px, 4vw, 52px) 60px; }}
.toolbar {{
  display: grid;
  grid-template-columns: minmax(240px, 2fr) repeat(4, minmax(120px, 1fr));
  gap: 10px;
  margin-top: 16px;
}}
input, select, button {{
  font: inherit;
  border: 1px solid color-mix(in srgb, CanvasText 22%, transparent);
  border-radius: 8px;
  background: Canvas;
  color: CanvasText;
  padding: 9px 11px;
}}
button {{ cursor: pointer; }}
.summary-grid, .meta-grid {{
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(145px, 1fr));
  gap: 10px;
}}
.metric, .meta-grid > div {{
  border: 1px solid color-mix(in srgb, CanvasText 14%, transparent);
  border-radius: 10px;
  padding: 12px;
}}
.metric strong {{ font-size: 1.35rem; }}
.tool {{
  margin: 18px 0;
  border: 1px solid color-mix(in srgb, CanvasText 18%, transparent);
  border-radius: 12px;
  overflow: clip;
}}
.tool-summary {{
  display: flex;
  justify-content: space-between;
  gap: 12px;
  padding: 16px;
  cursor: pointer;
}}
.tool-body {{ padding: 0 16px 16px; }}
.endpoint {{
  margin-top: 12px;
  border: 1px solid color-mix(in srgb, CanvasText 14%, transparent);
  border-radius: 10px;
}}
.endpoint > summary {{
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 9px;
  padding: 13px;
  cursor: pointer;
}}
.endpoint-title {{ font-weight: 700; }}
.endpoint-body {{ padding: 0 13px 15px; }}
.badge {{
  display: inline-flex;
  align-items: center;
  border-radius: 999px;
  padding: 3px 8px;
  margin-right: 6px;
  font-size: .78rem;
  border: 1px solid currentColor;
}}
.badge-ok {{ color: #198754; }}
.badge-warning {{ color: #b7791f; }}
.badge-danger {{ color: #c0392b; }}
.badge-neutral {{ opacity: .82; }}
.muted {{ opacity: .68; }}
.live-strip {{
  margin: 10px 0;
  padding: 10px;
  border-radius: 9px;
  background: color-mix(in srgb, CanvasText 6%, transparent);
}}
.route-row {{
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}}
.contract-section {{ margin-top: 20px; }}
.schema-grid {{
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(340px, 1fr));
  gap: 12px;
  margin-top: 20px;
}}
.schema-block {{
  min-width: 0;
}}
pre {{
  overflow: auto;
  padding: 12px;
  border-radius: 8px;
  background: color-mix(in srgb, CanvasText 7%, transparent);
  font-size: .82rem;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}}
code {{ overflow-wrap: anywhere; }}
.table-wrap {{ overflow-x: auto; }}
table {{ width: 100%; border-collapse: collapse; font-size: .86rem; }}
th, td {{
  border-bottom: 1px solid color-mix(in srgb, CanvasText 12%, transparent);
  padding: 8px;
  text-align: left;
  vertical-align: top;
}}
.auth-alt {{
  margin: 8px 0;
  padding: 10px;
  border-radius: 8px;
  background: color-mix(in srgb, CanvasText 5%, transparent);
}}
.provenance {{ margin-top: 14px; }}
.empty {{
  padding: 32px;
  text-align: center;
  opacity: .65;
}}
[hidden] {{ display: none !important; }}
@media (max-width: 900px) {{
  .toolbar {{ grid-template-columns: 1fr 1fr; }}
  .toolbar input {{ grid-column: 1 / -1; }}
}}
</style>
</head>
<body>
<header>
  <h1>SchemaRouter Capability Explorer</h1>
  <div class="muted">
    Registry v{document.registry_version} · {document.tool_count} tools ·
    {document.endpoint_count} endpoints · {live_badge}
  </div>
  <div class="toolbar">
    <input id="search" type="search"
      placeholder="Search tools, endpoints, fields, units, paths…"
      aria-label="Search capability contracts">
    <select id="provider" aria-label="Filter by provider">
      <option value="">All providers</option>{provider_options}
    </select>
    <select id="adapter" aria-label="Filter by adapter">
      <option value="">All adapters</option>{adapter_options}
    </select>
    <select id="method" aria-label="Filter by method">
      <option value="">All methods</option>{method_options}
    </select>
    <select id="mode" aria-label="Filter by side-effect mode">
      <option value="">All modes</option>
      <option value="read-only">Read-only</option>
      <option value="mutating">Mutating</option>
      <option value="destructive">Destructive</option>
      <option value="unclassified">Unclassified</option>
    </select>
  </div>
</header>
<main>
  <div class="summary-grid">
    <div class="metric">
      <strong>{document.tool_count}</strong><br><span class="muted">tools</span>
    </div>
    <div class="metric">
      <strong>{document.endpoint_count}</strong><br><span class="muted">endpoints</span>
    </div>
    <div class="metric">
      <strong>{len(providers)}</strong><br><span class="muted">providers</span>
    </div>
    <div class="metric">
      <strong>{len(adapters)}</strong><br><span class="muted">adapters</span>
    </div>
  </div>
  <div id="tools">{''.join(tool_sections)}</div>
  <div id="empty" class="empty" hidden>No capability contracts match the current filters.</div>
</main>
<script>
(() => {{
  const search = document.getElementById("search");
  const provider = document.getElementById("provider");
  const adapter = document.getElementById("adapter");
  const method = document.getElementById("method");
  const mode = document.getElementById("mode");
  const empty = document.getElementById("empty");

  function applyFilters() {{
    const query = search.value.trim().toLowerCase();
    const providerValue = provider.value;
    const adapterValue = adapter.value;
    const methodValue = method.value;
    const modeValue = mode.value;
    let visibleTools = 0;

    for (const tool of document.querySelectorAll(".tool")) {{
      const toolMatches =
        (!providerValue || tool.dataset.provider === providerValue) &&
        (!adapterValue || tool.dataset.adapter === adapterValue);
      let visibleEndpoints = 0;

      for (const endpoint of tool.querySelectorAll(".endpoint")) {{
        const queryMatch =
          !query ||
          endpoint.dataset.search.includes(query) ||
          tool.dataset.toolSearch.includes(query);
        const methodMatch =
          !methodValue || endpoint.dataset.method === methodValue;
        const modeMatch =
          !modeValue || endpoint.dataset.mode === modeValue;
        endpoint.hidden = !(toolMatches && queryMatch && methodMatch && modeMatch);
        if (!endpoint.hidden) visibleEndpoints += 1;
      }}

      tool.hidden = !toolMatches || visibleEndpoints === 0;
      if (!tool.hidden) visibleTools += 1;
    }}
    empty.hidden = visibleTools !== 0;
  }}

  for (const control of [search, provider, adapter, method, mode]) {{
    control.addEventListener("input", applyFilters);
    control.addEventListener("change", applyFilters);
  }}

  document.addEventListener("click", async (event) => {{
    const button = event.target.closest("[data-copy-target]");
    if (!button) return;
    const target = document.getElementById(button.dataset.copyTarget);
    if (!target) return;
    const text = target.textContent || "";
    try {{
      await navigator.clipboard.writeText(text);
      const original = button.textContent;
      button.textContent = "Copied";
      setTimeout(() => {{ button.textContent = original; }}, 900);
    }} catch (_) {{
      const range = document.createRange();
      range.selectNodeContents(target);
      const selection = window.getSelection();
      selection.removeAllRanges();
      selection.addRange(range);
    }}
  }});

  applyFilters();
}})();
</script>
</body>
</html>
"""


def write_schema_explorer(
    document: SchemaExplorerDocument,
    output: str | Path,
) -> Path:
    """Write one self-contained capability explorer HTML artifact."""

    destination = Path(output)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        render_schema_explorer(document),
        encoding="utf-8",
    )
    return destination
