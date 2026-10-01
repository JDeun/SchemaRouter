from __future__ import annotations

import json
from copy import deepcopy
from html import escape
from pathlib import Path
from typing import Any, Literal

from pydantic import Field

from .errors import RegistrationError
from .inspection import RouterInspection, inspect_tool_spec
from .models import StrictModel, ToolSpec
from .registry import ToolRegistry

SideEffectMode = Literal["read-only", "mutating", "destructive", "unclassified"]


class ExplorerAuthScheme(StrictModel):
    name: str
    kind: str
    location: str | None = None
    parameter_name: str | None = None
    http_scheme: str | None = None
    scopes: list[str] = Field(default_factory=list)
    declared_type: str | None = None


class ExplorerParameter(StrictModel):
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
    scale: float
    offset: float


class ExplorerField(StrictModel):
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


class ExplorerProjection(StrictModel):
    parameter: str
    separator: str
    field_map: dict[str, str] = Field(default_factory=dict)


class ExplorerEndpointStatus(StrictModel):
    binding_state: str | None = None
    health_status: str | None = None
    health_error_type: str | None = None
    unavailable: bool = False


class ExplorerEndpoint(StrictModel):
    route_id: str
    name: str
    description: str = ""
    operation_aliases: list[str] = Field(default_factory=list)
    method: str | None = None
    path: str | None = None
    mode: SideEffectMode
    read_only: bool | None = None
    destructive: bool | None = None
    deprecated: bool | None = None
    auth_required: bool = False
    auth_alternatives: list[list[ExplorerAuthScheme]] = Field(default_factory=list)
    parameters: list[ExplorerParameter] = Field(default_factory=list)
    input_schema: dict[str, Any] = Field(default_factory=dict)
    output_fields: list[ExplorerField] = Field(default_factory=list)
    output_schema: dict[str, Any] = Field(default_factory=dict)
    server_projection: ExplorerProjection | None = None
    fingerprint: str
    status: ExplorerEndpointStatus | None = None


class ExplorerWatchStatus(StrictModel):
    status: str
    pending_review: bool = False
    pending_change_count: int = 0
    last_compatibility: str | None = None
    pending_candidate_fingerprint: str | None = None
    pending_candidate_source_identity: str | None = None
    last_error_type: str | None = None


class ExplorerTool(StrictModel):
    key: str
    name: str
    namespace: str | None = None
    description: str = ""
    provider: str | None = None
    access_mode: str | None = None
    source_type: str | None = None
    license: str | None = None
    remote: bool = False
    adapter: str | None = None
    provenance: dict[str, object] = Field(default_factory=dict)
    fingerprint: str
    binding_state: str | None = None
    watch: ExplorerWatchStatus | None = None
    endpoints: list[ExplorerEndpoint] = Field(default_factory=list)


class CapabilityExplorerDocument(StrictModel):
    registry_version: int
    tool_count: int
    endpoint_count: int
    live: bool = False
    tools: list[ExplorerTool] = Field(default_factory=list)


_SCHEMA_EXCLUDED_KEYS = {
    "const",
    "default",
    "example",
    "examples",
}


def _safe_schema(value: Any) -> Any:
    """Return a JSON-safe schema view without embedded example/default values."""

    if isinstance(value, dict):
        return {
            str(key): _safe_schema(item)
            for key, item in value.items()
            if str(key).casefold() not in _SCHEMA_EXCLUDED_KEYS
        }
    if isinstance(value, list):
        return [_safe_schema(item) for item in value]
    return deepcopy(value)


def _mode(read_only: bool | None, destructive: bool | None) -> SideEffectMode:
    if destructive is True:
        return "destructive"
    if read_only is True:
        return "read-only"
    if read_only is False:
        return "mutating"
    return "unclassified"


def _health_key(tool_key: str, endpoint_name: str) -> tuple[str, str]:
    return tool_key, endpoint_name


def _unavailable_keys(values: list[str]) -> set[str]:
    return {value.strip() for value in values if value.strip()}


def _stable_registry_snapshot(
    registry: ToolRegistry,
    *,
    attempts: int = 3,
) -> tuple[int, tuple[ToolSpec, ...]]:
    for _ in range(attempts):
        before = registry.version
        tools = registry.tools()
        after = registry.version
        if before == after:
            return before, tools
    raise RegistrationError(
        "registry changed repeatedly while building the Capability Explorer"
    )


def _validate_live_snapshot(
    live: RouterInspection,
    *,
    registry_version: int,
    tools: tuple[ToolSpec, ...],
) -> None:
    if live.registry.version != registry_version:
        raise RegistrationError(
            "live inspection registry version does not match explorer snapshot"
        )

    expected = {
        tool.key: tool.fingerprint
        for tool in tools
    }
    observed = {
        tool.key: tool.fingerprint
        for tool in live.registry.tools
    }
    if observed != expected:
        raise RegistrationError(
            "live inspection capability fingerprints do not match explorer snapshot"
        )


def build_capability_explorer_document(
    registry: ToolRegistry,
    *,
    live: RouterInspection | None = None,
) -> CapabilityExplorerDocument:
    """Build a complete allowlisted capability document for human inspection."""

    registry_version, tool_specs = _stable_registry_snapshot(registry)

    live_health: dict[tuple[str, str], Any] = {}
    live_watches: dict[str, Any] = {}
    binding_states: dict[str, str] = {}
    unavailable: set[str] = set()

    if live is not None:
        _validate_live_snapshot(
            live,
            registry_version=registry_version,
            tools=tool_specs,
        )
        binding_states = dict(live.execution.binding_states)
        unavailable = _unavailable_keys(live.execution.unavailable_access_paths)
        live_health = {
            _health_key(item.tool, item.endpoint): item
            for item in live.execution.health_probes
        }
        live_watches = {
            item.tool: item
            for item in live.execution.schema_watches
        }

    tools: list[ExplorerTool] = []
    endpoint_count = 0

    for tool in tool_specs:
        summary = inspect_tool_spec(tool)
        adapter_value = summary.provenance.get("adapter")
        adapter = adapter_value if isinstance(adapter_value, str) else tool.source_type
        tool_binding = binding_states.get(tool.key)
        watch_snapshot = live_watches.get(tool.key)
        watch = None
        if watch_snapshot is not None:
            watch = ExplorerWatchStatus(
                status=watch_snapshot.status,
                pending_review=watch_snapshot.pending_review,
                pending_change_count=watch_snapshot.pending_change_count,
                last_compatibility=watch_snapshot.last_compatibility,
                pending_candidate_fingerprint=watch_snapshot.pending_candidate_fingerprint,
                pending_candidate_source_identity=(
                    watch_snapshot.pending_candidate_source_identity
                ),
                last_error_type=watch_snapshot.last_error_type,
            )

        endpoints: list[ExplorerEndpoint] = []
        for endpoint in tool.endpoints:
            route_id = f"{tool.key}:{endpoint.name}"
            health = live_health.get(_health_key(tool.key, endpoint.name))
            unavailable_candidates = {
                route_id,
                f"{tool.key}.{endpoint.name}",
                f"{tool.key}/{endpoint.name}",
            }
            status = None
            if live is not None:
                status = ExplorerEndpointStatus(
                    binding_state=tool_binding,
                    health_status=health.status if health is not None else None,
                    health_error_type=(
                        health.last_error_type if health is not None else None
                    ),
                    unavailable=bool(unavailable_candidates & unavailable),
                )

            auth_alternatives = [
                [
                    ExplorerAuthScheme(
                        name=scheme.name,
                        kind=scheme.kind,
                        location=scheme.location,
                        parameter_name=scheme.parameter_name,
                        http_scheme=scheme.http_scheme,
                        scopes=list(scheme.scopes),
                        declared_type=scheme.declared_type,
                    )
                    for scheme in requirement.schemes
                ]
                for requirement in endpoint.auth_requirements
            ]

            projection = None
            if endpoint.server_projection is not None:
                projection = ExplorerProjection(
                    parameter=endpoint.server_projection.parameter,
                    separator=endpoint.server_projection.separator,
                    field_map=dict(endpoint.server_projection.field_map),
                )

            endpoints.append(
                ExplorerEndpoint(
                    route_id=route_id,
                    name=endpoint.name,
                    description=endpoint.description,
                    operation_aliases=list(endpoint.operation_aliases),
                    method=endpoint.method,
                    path=endpoint.path,
                    mode=_mode(endpoint.read_only, endpoint.destructive),
                    read_only=endpoint.read_only,
                    destructive=endpoint.destructive,
                    deprecated=None,
                    auth_required=endpoint.auth_required,
                    auth_alternatives=auth_alternatives,
                    parameters=[
                        ExplorerParameter(
                            name=parameter.name,
                            wire_name=parameter.wire_name,
                            description=parameter.description,
                            required=parameter.required,
                            location=parameter.location,
                            style=parameter.style,
                            explode=parameter.explode,
                            allow_reserved=parameter.allow_reserved,
                            json_schema=_safe_schema(parameter.json_schema),
                            aliases=list(parameter.aliases),
                        )
                        for parameter in endpoint.parameters
                    ],
                    input_schema=_safe_schema(endpoint.input_schema),
                    output_fields=[
                        ExplorerField(
                            name=field.name,
                            semantic_id=field.semantic_id,
                            description=field.description,
                            json_schema=_safe_schema(field.json_schema),
                            aliases=list(field.aliases),
                            path=list(field.path),
                            result_path=list(field.result_path),
                            unit=field.unit,
                            unit_normalization=(
                                ExplorerUnitNormalization(
                                    dimension=field.unit_normalization.dimension,
                                    canonical_unit=(
                                        field.unit_normalization.canonical_unit
                                    ),
                                    scale=field.unit_normalization.scale,
                                    offset=field.unit_normalization.offset,
                                )
                                if field.unit_normalization is not None
                                else None
                            ),
                            qualifiers=dict(field.qualifiers),
                            identifier=field.identifier,
                            source_type=field.source_type,
                            license=field.license,
                        )
                        for field in endpoint.output_fields
                    ],
                    output_schema=_safe_schema(endpoint.output_schema),
                    server_projection=projection,
                    fingerprint=endpoint.fingerprint,
                    status=status,
                )
            )

        endpoint_count += len(endpoints)
        tools.append(
            ExplorerTool(
                key=tool.key,
                name=tool.name,
                namespace=tool.namespace,
                description=tool.description,
                provider=tool.provider,
                access_mode=tool.access_mode,
                source_type=tool.source_type,
                license=tool.license,
                remote=tool.remote,
                adapter=adapter,
                provenance=dict(summary.provenance),
                fingerprint=tool.fingerprint,
                binding_state=tool_binding,
                watch=watch,
                endpoints=endpoints,
            )
        )

    return CapabilityExplorerDocument(
        registry_version=registry_version,
        tool_count=len(tools),
        endpoint_count=endpoint_count,
        live=live is not None,
        tools=tools,
    )


def _json_text(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
    )


def _embedded_json(value: Any) -> str:
    """Serialize JSON safely inside a script[type=application/json] element."""

    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).replace("<", "\\u003c")


def _badge(label: str, kind: str = "") -> str:
    class_name = f"badge {kind}".strip()
    return f'<span class="{class_name}">{escape(label)}</span>'


def _schema_block(title: str, schema: dict[str, Any]) -> str:
    if not schema:
        return (
            '<section class="subsection">'
            f"<h5>{escape(title)}</h5>"
            '<p class="muted">—</p>'
            "</section>"
        )
    payload = escape(_json_text(schema))
    return (
        '<section class="subsection">'
        f"<h5>{escape(title)}</h5>"
        f"<pre><code>{payload}</code></pre>"
        "</section>"
    )


def _render_parameter_rows(parameters: list[ExplorerParameter]) -> str:
    if not parameters:
        return '<tr><td colspan="8" class="muted">No declared parameters.</td></tr>'
    rows: list[str] = []
    for parameter in parameters:
        schema = escape(_json_text(parameter.json_schema))
        rows.append(
            "<tr>"
            f"<td><code>{escape(parameter.name)}</code></td>"
            f"<td>{escape(parameter.wire_name or '—')}</td>"
            f"<td>{escape(parameter.location)}</td>"
            f"<td>{'yes' if parameter.required else 'no'}</td>"
            f"<td>{escape(parameter.style or '—')}</td>"
            f"<td>{escape(str(parameter.explode) if parameter.explode is not None else '—')}</td>"
            f"<td>{escape(', '.join(parameter.aliases) or '—')}</td>"
            f"<td><details><summary>schema</summary><pre><code>{schema}</code></pre></details></td>"
            "</tr>"
        )
    return "".join(rows)


def _render_field_rows(fields: list[ExplorerField]) -> str:
    if not fields:
        return '<tr><td colspan="9" class="muted">No declared output fields.</td></tr>'
    rows: list[str] = []
    for field in fields:
        normalization = "—"
        if field.unit_normalization is not None:
            normalization = (
                f"{field.unit_normalization.dimension}: "
                f"x×{field.unit_normalization.scale:g}"
                f"{field.unit_normalization.offset:+g} → "
                f"{field.unit_normalization.canonical_unit}"
            )
        schema = escape(_json_text(field.json_schema))
        rows.append(
            "<tr>"
            f"<td><code>{escape(field.name)}</code></td>"
            f"<td>{escape(field.semantic_id or '—')}</td>"
            f"<td>{escape(field.unit or '—')}</td>"
            f"<td>{escape(normalization)}</td>"
            f"<td>{escape('.'.join(field.path) or '—')}</td>"
            f"<td>{escape('.'.join(field.result_path) or '—')}</td>"
            f"<td>{'yes' if field.identifier else 'no'}</td>"
            "<td>"
            + escape(
                ", ".join(
                    f"{key}={value}"
                    for key, value in sorted(field.qualifiers.items())
                )
                or "—"
            )
            + "</td>"
            f"<td><details><summary>schema</summary><pre><code>{schema}</code></pre></details></td>"
            "</tr>"
        )
    return "".join(rows)


def _render_endpoint(endpoint: ExplorerEndpoint, *, index: int) -> str:
    method_or_protocol = endpoint.method or "CAPABILITY"
    mode_kind = {
        "read-only": "good",
        "mutating": "warn",
        "destructive": "danger",
        "unclassified": "muted-badge",
    }[endpoint.mode]

    status_badges: list[str] = []
    if endpoint.status is not None:
        if endpoint.status.binding_state:
            status_badges.append(
                _badge(f"binding:{endpoint.status.binding_state}")
            )
        if endpoint.status.health_status:
            status_badges.append(
                _badge(f"health:{endpoint.status.health_status}")
            )
        if endpoint.status.unavailable:
            status_badges.append(_badge("unavailable", "danger"))

    auth = "public"
    if endpoint.auth_required:
        auth = "auth required"

    auth_html = ""
    if endpoint.auth_alternatives:
        alternatives: list[str] = []
        for auth_index, alternative in enumerate(
            endpoint.auth_alternatives,
            start=1,
        ):
            rendered_schemes: list[str] = []
            for scheme in alternative:
                details = [scheme.kind]
                if scheme.location is not None:
                    details.append(scheme.location)
                if scheme.parameter_name is not None:
                    details.append(scheme.parameter_name)
                if scheme.http_scheme is not None:
                    details.append(scheme.http_scheme)
                if scheme.scopes:
                    details.append("scopes=" + ",".join(scheme.scopes))
                if scheme.declared_type is not None:
                    details.append("declared=" + scheme.declared_type)
                rendered_schemes.append(
                    f"{scheme.name}:" + " · ".join(details)
                )
            schemes = ", ".join(rendered_schemes) or "anonymous"
            alternatives.append(
                f"<li>alternative {auth_index}: {escape(schemes)}</li>"
            )
        auth_html = (
            "<details><summary>Authentication contract</summary>"
            f"<ul>{''.join(alternatives)}</ul></details>"
        )

    contract_json = escape(endpoint.model_dump_json(indent=2))
    route_copy_id = f"route-{index}"
    contract_copy_id = f"contract-{index}"
    projection_html = ""
    if endpoint.server_projection is not None:
        projection_map = escape(
            _json_text(endpoint.server_projection.field_map)
        )
        projection_html = (
            "<details><summary>Server projection</summary>"
            "<p>"
            f"parameter=<code>{escape(endpoint.server_projection.parameter)}</code> "
            f"separator=<code>{escape(endpoint.server_projection.separator)}</code>"
            "</p>"
            f"<pre><code>{projection_map}</code></pre>"
            "</details>"
        )
    deprecated_text = (
        str(endpoint.deprecated)
        if endpoint.deprecated is not None
        else "unknown"
    )
    search_text = " ".join(
        [
            endpoint.route_id,
            endpoint.name,
            endpoint.description,
            endpoint.method or "",
            endpoint.path or "",
            endpoint.mode,
            " ".join(parameter.name for parameter in endpoint.parameters),
            " ".join(field.name for field in endpoint.output_fields),
            " ".join(
                field.semantic_id or ""
                for field in endpoint.output_fields
            ),
            " ".join(field.unit or "" for field in endpoint.output_fields),
        ]
    ).lower()
    return f"""
<article
  class="endpoint"
  data-search="{escape(search_text)}"
  data-mode="{escape(endpoint.mode)}"
  data-method="{escape((endpoint.method or '').lower())}"
>
<details>
<summary>
<span class="method">{escape(method_or_protocol)}</span>
<code id="{route_copy_id}">{escape(endpoint.route_id)}</code>
<button type="button" data-copy-target="{route_copy_id}">Copy route</button>
{_badge(endpoint.mode, mode_kind)}
{_badge(auth, "warn" if endpoint.auth_required else "good")}
{''.join(status_badges)}
<span class="summary-text">{escape(endpoint.description or endpoint.name)}</span>
</summary>
<div class="endpoint-body">
<div class="meta-grid">
<div><strong>Path</strong><br><code>{escape(endpoint.path or '—')}</code></div>
<div><strong>Fingerprint</strong><br><code>{escape(endpoint.fingerprint)}</code></div>
<div><strong>Aliases</strong><br>{escape(', '.join(endpoint.operation_aliases) or '—')}</div>
<div><strong>Deprecated</strong><br>{escape(deprecated_text)}</div>
</div>
{auth_html}
{projection_html}
<h4>Parameters</h4>
<div class="table-wrap"><table>
<thead><tr>
<th>Name</th><th>Wire name</th><th>Location</th><th>Required</th>
<th>Style</th><th>Explode</th><th>Aliases</th><th>Schema</th>
</tr></thead>
<tbody>{_render_parameter_rows(endpoint.parameters)}</tbody>
</table></div>
{_schema_block("Input schema", endpoint.input_schema)}
<h4>Output fields</h4>
<div class="table-wrap"><table>
<thead><tr>
<th>Name</th><th>Semantic ID</th><th>Unit</th><th>Normalization</th>
<th>Source path</th><th>Result path</th><th>ID</th>
<th>Qualifiers</th><th>Schema</th>
</tr></thead>
<tbody>{_render_field_rows(endpoint.output_fields)}</tbody>
</table></div>
{_schema_block("Output schema", endpoint.output_schema)}
<details>
<summary>Copyable JSON contract</summary>
<button type="button" data-copy-target="{contract_copy_id}">Copy JSON</button>
<pre><code id="{contract_copy_id}">{contract_json}</code></pre>
</details>
</div>
</details>
</article>
"""


def render_schema_explorer(document: CapabilityExplorerDocument) -> str:
    """Render a self-contained, read-only protocol-neutral capability explorer."""

    providers = sorted(
        {tool.provider for tool in document.tools if tool.provider}
    )
    adapter_values = {
        value
        for tool in document.tools
        if (value := tool.adapter or tool.source_type) is not None
    }
    adapters = sorted(adapter_values)
    methods = sorted(
        {
            endpoint.method.upper()
            for tool in document.tools
            for endpoint in tool.endpoints
            if endpoint.method
        }
    )
    provider_options = "".join(
        f'<option value="{escape(value.lower())}">{escape(value)}</option>'
        for value in providers
    )
    adapter_options = "".join(
        f'<option value="{escape(value.lower())}">{escape(value)}</option>'
        for value in adapters
    )
    method_options = "".join(
        f'<option value="{escape(value.lower())}">{escape(value)}</option>'
        for value in methods
    )

    tools_html: list[str] = []
    endpoint_index = 0
    for tool in document.tools:
        source = (
            tool.provenance.get("source_url")
            or tool.provenance.get("resolved_schema_url")
            or tool.provenance.get("versioned_base_url")
            or "—"
        )
        watch_badges = ""
        if tool.watch is not None:
            watch_badges += _badge(f"watch:{tool.watch.status}")
            if tool.watch.pending_review:
                watch_badges += _badge(
                    f"pending review ({tool.watch.pending_change_count})",
                    "warn",
                )

        rendered_endpoints: list[str] = []
        for endpoint in tool.endpoints:
            endpoint_index += 1
            rendered_endpoints.append(
                _render_endpoint(endpoint, index=endpoint_index)
            )
        endpoints = "".join(rendered_endpoints)
        tool_search = " ".join(
            [
                tool.key,
                tool.name,
                tool.description,
                tool.provider or "",
                tool.adapter or "",
                tool.access_mode or "",
                tool.source_type or "",
                str(source),
            ]
        ).lower()
        tools_html.append(
            f"""
<section
  class="tool"
  data-search="{escape(tool_search)}"
  data-provider="{escape((tool.provider or '').lower())}"
  data-adapter="{escape((tool.adapter or tool.source_type or '').lower())}"
>
<details open>
<summary class="tool-summary">
<code>{escape(tool.key)}</code>
{_badge(tool.adapter or tool.source_type or 'generic')}
{_badge(tool.access_mode or 'unspecified')}
{_badge(f"binding:{tool.binding_state}") if tool.binding_state else ''}
{watch_badges}
<span>{escape(tool.description or tool.name)}</span>
</summary>
<div class="tool-body">
<div class="meta-grid">
<div><strong>Provider</strong><br>{escape(tool.provider or '—')}</div>
<div><strong>Source</strong><br><code>{escape(str(source))}</code></div>
<div><strong>Fingerprint</strong><br><code>{escape(tool.fingerprint)}</code></div>
<div><strong>Remote</strong><br>{'yes' if tool.remote else 'no'}</div>
</div>
<div class="endpoints">{endpoints}</div>
</div>
</details>
</section>
"""
        )

    embedded = _embedded_json(document.model_dump(mode="json"))
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>SchemaRouter Capability Explorer</title>
<style>
:root {{
  color-scheme: light dark;
  --bg: #111318;
  --panel: #191c23;
  --panel-2: #20242d;
  --text: #eceff4;
  --muted: #9aa3b2;
  --border: #333947;
}}
* {{ box-sizing: border-box; }}
body {{
  margin: 0;
  font: 14px/1.5 system-ui, sans-serif;
  background: var(--bg);
  color: var(--text);
}}
main {{ max-width: 1500px; margin: 0 auto; padding: 28px; }}
h1 {{ margin: 0 0 4px; }}
h4, h5 {{ margin-bottom: 8px; }}
code, pre {{ font-family: ui-monospace, SFMono-Regular, Menlo, monospace; }}
pre {{
  white-space: pre-wrap;
  word-break: break-word;
  background: #0d0f13;
  padding: 12px;
  border-radius: 8px;
  overflow: auto;
}}
.toolbar {{
  position: sticky;
  top: 0;
  z-index: 5;
  display: grid;
  grid-template-columns: minmax(260px, 2fr) repeat(4, minmax(120px, 1fr));
  gap: 8px;
  background: color-mix(in srgb, var(--bg) 92%, transparent);
  padding: 14px 0;
}}
input, select, button {{
  padding: 11px 13px;
  border: 1px solid var(--border);
  border-radius: 8px;
  background: var(--panel);
  color: inherit;
}}
input {{
  width: 100%;
}}
button {{ cursor: pointer; }}
.metrics {{ display: flex; gap: 12px; flex-wrap: wrap; margin: 16px 0; }}
.metric {{
  background: var(--panel);
  padding: 10px 14px;
  border-radius: 8px;
  border: 1px solid var(--border);
}}
.tool {{
  margin: 14px 0;
  border: 1px solid var(--border);
  background: var(--panel);
  border-radius: 10px;
  overflow: hidden;
}}
.tool-summary, .endpoint summary {{
  cursor: pointer;
  display: flex;
  gap: 8px;
  align-items: center;
  flex-wrap: wrap;
  padding: 13px 15px;
}}
.tool-body {{ padding: 0 15px 15px; }}
.endpoint {{
  background: var(--panel-2);
  margin: 10px 0;
  border-radius: 8px;
  border: 1px solid var(--border);
}}
.endpoint-body {{ padding: 0 14px 14px; }}
.badge, .method {{ padding: 2px 7px; border-radius: 999px; background: #394150; font-size: 12px; }}
.badge.good {{ background: #205a3c; }}
.badge.warn {{ background: #75561b; }}
.badge.danger {{ background: #782c35; }}
.badge.muted-badge {{ background: #4a4f5a; }}
.method {{ font-weight: 700; }}
.summary-text {{ color: var(--muted); }}
.meta-grid {{
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(210px, 1fr));
  gap: 10px;
  margin: 12px 0;
}}
.meta-grid > div {{
  background: color-mix(in srgb, var(--panel) 70%, black);
  padding: 9px;
  border-radius: 7px;
}}
.table-wrap {{ overflow-x: auto; }}
table {{ width: 100%; border-collapse: collapse; }}
th, td {{
  padding: 8px;
  text-align: left;
  vertical-align: top;
  border-bottom: 1px solid var(--border);
}}
th {{ color: var(--muted); }}
.muted {{ color: var(--muted); }}
.hidden {{ display: none !important; }}
</style>
</head>
<body>
<main>
<h1>SchemaRouter Capability Explorer</h1>
<p class="muted">
Read-only protocol-neutral documentation generated from privacy-safe contract data.
</p>
<div class="metrics">
<div class="metric">Registry v{document.registry_version}</div>
<div class="metric">{document.tool_count} tools</div>
<div class="metric">{document.endpoint_count} endpoints</div>
<div class="metric">
{'live statuses included' if document.live else 'static registry snapshot'}
</div>
</div>
<div class="toolbar">
<input
  id="filter"
  type="search"
  placeholder="Search tool, endpoint, provider, field, semantic ID, unit, method, mode…"
>
<select id="provider-filter" aria-label="Filter by provider">
<option value="">All providers</option>{provider_options}
</select>
<select id="adapter-filter" aria-label="Filter by adapter">
<option value="">All adapters</option>{adapter_options}
</select>
<select id="method-filter" aria-label="Filter by method">
<option value="">All methods</option>{method_options}
</select>
<select id="mode-filter" aria-label="Filter by mode">
<option value="">All modes</option>
<option value="read-only">Read-only</option>
<option value="mutating">Mutating</option>
<option value="destructive">Destructive</option>
<option value="unclassified">Unclassified</option>
</select>
</div>
<div id="tools">{''.join(tools_html)}</div>
<script id="schemarouter-document" type="application/json">{embedded}</script>
<script>
const filter = document.getElementById("filter");
const providerFilter = document.getElementById("provider-filter");
const adapterFilter = document.getElementById("adapter-filter");
const methodFilter = document.getElementById("method-filter");
const modeFilter = document.getElementById("mode-filter");

function applyFilters() {{
  const q = filter.value.trim().toLowerCase();
  const provider = providerFilter.value;
  const adapter = adapterFilter.value;
  const method = methodFilter.value;
  const mode = modeFilter.value;

  for (const tool of document.querySelectorAll(".tool")) {{
    const toolMatch =
      (!provider || tool.dataset.provider === provider) &&
      (!adapter || tool.dataset.adapter === adapter);
    let visible = false;
    for (const endpoint of tool.querySelectorAll(".endpoint")) {{
      const searchMatch =
        !q ||
        endpoint.dataset.search.includes(q) ||
        tool.dataset.search.includes(q);
      const methodMatch =
        !method || endpoint.dataset.method === method;
      const modeMatch =
        !mode || endpoint.dataset.mode === mode;
      const match = toolMatch && searchMatch && methodMatch && modeMatch;
      endpoint.classList.toggle("hidden", !match);
      visible = visible || match;
    }}
    tool.classList.toggle("hidden", !visible);
  }}
}}

for (const control of [
  filter,
  providerFilter,
  adapterFilter,
  methodFilter,
  modeFilter,
]) {{
  control.addEventListener("input", applyFilters);
  control.addEventListener("change", applyFilters);
}}

document.addEventListener("click", async (event) => {{
  const button = event.target.closest("[data-copy-target]");
  if (!button) return;
  const target = document.getElementById(button.dataset.copyTarget);
  if (!target) return;
  const value = target.textContent || "";
  try {{
    await navigator.clipboard.writeText(value);
    const original = button.textContent;
    button.textContent = "Copied";
    setTimeout(() => {{ button.textContent = original; }}, 900);
  }} catch (_) {{
    const selection = window.getSelection();
    const range = document.createRange();
    range.selectNodeContents(target);
    selection.removeAllRanges();
    selection.addRange(range);
  }}
}});

applyFilters();
</script>
</main>
</body>
</html>
"""


def write_schema_explorer(
    document: CapabilityExplorerDocument,
    output: str | Path,
) -> Path:
    destination = Path(output)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(render_schema_explorer(document), encoding="utf-8")
    return destination
