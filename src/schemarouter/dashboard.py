from __future__ import annotations

from collections.abc import Sequence
from html import escape
from pathlib import Path

from .inspection import RegistryInspection, RouterInspection, TraceInspection


def _text(value: object | None) -> str:
    if value is None:
        return "—"
    if isinstance(value, bool):
        return "yes" if value else "no"
    return str(value)


def _field_contract_text(field: object) -> str:
    name = str(getattr(field, "name", ""))
    json_types = getattr(field, "json_types", [])
    type_text = "|".join(str(value) for value in json_types) if json_types else "?"
    unit = getattr(field, "unit", None)
    unit_text = f" [{unit}]" if unit else ""
    return f"{name}:{type_text}{unit_text}"


def _mode(read_only: bool | None, destructive: bool | None) -> str:
    if destructive is True:
        return "destructive"
    if read_only is True:
        return "read-only"
    if read_only is False:
        return "mutating"
    return "unclassified"


def render_dashboard(
    registry: RegistryInspection,
    *,
    traces: Sequence[TraceInspection] = (),
    live: RouterInspection | None = None,
) -> str:
    """Render a self-contained read-only HTML dashboard from inspection models."""

    cards = (
        ("Registry version", registry.version),
        ("Tools", registry.tool_count),
        ("Endpoints", registry.endpoint_count),
        ("Read-only", registry.read_only_endpoints),
        ("Mutating", registry.mutating_endpoints),
        ("Unclassified", registry.unclassified_endpoints),
        ("Runs", len(traces)),
        ("Error events", sum(trace.error_count for trace in traces)),
    )
    card_html = "".join(
        (
            '<div class="card">'
            f'<div class="metric">{escape(_text(value))}</div>'
            f'<div class="label">{escape(label)}</div>'
            "</div>"
        )
        for label, value in cards
    )

    tool_rows: list[str] = []
    for tool in registry.tools:
        adapter = tool.provenance.get("adapter") or tool.source_type or "—"
        source = (
            tool.provenance.get("source_url")
            or tool.provenance.get("resolved_schema_url")
            or tool.provenance.get("versioned_base_url")
            or "—"
        )
        execution_bound = tool.provenance.get("execution_bound")
        for endpoint in tool.endpoints:
            field_summary = ", ".join(
                _field_contract_text(field)
                for field in endpoint.fields
            )
            search = " ".join(
                (
                    tool.key,
                    str(adapter),
                    endpoint.name,
                    endpoint.method or "",
                    endpoint.path or "",
                    field_summary,
                )
            ).lower()
            tool_rows.append(
                "<tr "
                f'data-search="{escape(search, quote=True)}">'
                f"<td>{escape(tool.key)}</td>"
                f"<td>{escape(str(adapter))}</td>"
                f"<td>{escape(str(source))}</td>"
                f"<td>{escape(endpoint.name)}</td>"
                f"<td>{escape(endpoint.method or '—')}</td>"
                f"<td>{escape(endpoint.path or '—')}</td>"
                f"<td>{escape(_mode(endpoint.read_only, endpoint.destructive))}</td>"
                f"<td>{endpoint.parameter_count}</td>"
                f"<td>{endpoint.output_field_count}</td>"
                f"<td>{escape(field_summary or '—')}</td>"
                f"<td>{escape(_text(execution_bound))}</td>"
                f"<td><code>{escape(endpoint.fingerprint[:12])}</code></td>"
                "</tr>"
            )

    trace_rows = "".join(
        (
            "<tr>"
            f"<td><code>{escape(trace.run_id)}</code></td>"
            f"<td>{escape(_text(trace.complete))}</td>"
            f"<td>{trace.event_count}</td>"
            f"<td>{trace.error_count}</td>"
            f"<td>{escape(trace.terminal_event or '—')}</td>"
            f"<td>{escape(', '.join(trace.endpoints) or '—')}</td>"
            f"<td>{escape(trace.started_at.isoformat())}</td>"
            f"<td>{escape(trace.ended_at.isoformat() if trace.ended_at else '—')}</td>"
            "</tr>"
        )
        for trace in traces
    )

    live_html = ""
    if live is not None:
        policy = ", ".join(
            f"{key}={value}" for key, value in sorted(live.execution.policy.items())
        )
        decision = ", ".join(
            f"{key}={value}" for key, value in sorted(live.planner.decision_policy.items())
        )
        binding_states = ", ".join(
            f"{key}={value}" for key, value in sorted(live.execution.binding_states.items())
        )
        unavailable = ", ".join(live.execution.unavailable_access_paths)
        health_monitor = "running" if live.execution.health_monitor_running else "stopped"
        live_html = f"""
<section>
<h2>Live router</h2>
<div class="live-grid">
<div><strong>Analyzer</strong><br>{escape(live.planner.analyzer)}</div>
<div><strong>Decision backend</strong><br>{escape(live.planner.decision_backend or "none")}</div>
<div><strong>Bound tools</strong><br>{escape(", ".join(live.execution.bound_tools) or "none")}</div>
<div><strong>Binding states</strong><br><code>{escape(binding_states or "none")}</code></div>
<div><strong>Unavailable paths</strong><br>{escape(unavailable or "none")}</div>
<div><strong>Health monitor</strong><br>{escape(health_monitor)}</div>
<div><strong>Execution policy</strong><br><code>{escape(policy)}</code></div>
<div><strong>Decision policy</strong><br><code>{escape(decision)}</code></div>
</div>
</section>
"""

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>SchemaRouter inspection dashboard</title>
<style>
:root {{
  color-scheme: light dark;
  font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, sans-serif;
}}
body {{ max-width: 1600px; margin: 0 auto; padding: 32px; line-height: 1.45; }}
h1, h2 {{ letter-spacing: -0.025em; }}
.muted {{ opacity: .68; }}
.grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(130px, 1fr)); gap: 12px; }}
.card {{ border: 1px solid #8885; border-radius: 12px; padding: 16px; }}
.metric {{ font-size: 1.8rem; font-weight: 700; }}
.label {{ opacity: .7; }}
.live-grid {{
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
  gap: 12px;
}}
.live-grid > div {{ border: 1px solid #8884; border-radius: 10px; padding: 12px; }}
section {{ margin-top: 32px; }}
.table-wrap {{ overflow-x: auto; }}
table {{ width: 100%; border-collapse: collapse; font-size: .9rem; }}
th, td {{
  text-align: left;
  padding: 9px 8px;
  border-bottom: 1px solid #8884;
  vertical-align: top;
}}
th {{ white-space: nowrap; }}
input {{
  width: min(560px, 100%);
  box-sizing: border-box;
  padding: 10px 12px;
  border: 1px solid #8886;
  border-radius: 8px;
  margin: 0 0 12px;
}}
code {{ overflow-wrap: anywhere; }}
</style>
</head>
<body>
<h1>SchemaRouter inspection dashboard</h1>
<p class="muted">
Read-only operational view generated from SchemaRouter inspection models.
No tool execution, credentials, arbitrary metadata, or trace payload values are embedded.
</p>
<div class="grid">{card_html}</div>
{live_html}
<section>
<h2>Capabilities</h2>
<input id="filter" type="search"
       placeholder="Filter tool, endpoint, adapter, method, path…"
       autocomplete="off">
<div class="table-wrap">
<table id="capabilities">
<thead><tr>
<th>Tool</th><th>Adapter</th><th>Source</th><th>Endpoint</th><th>Method</th><th>Path</th>
<th>Mode</th><th>Params</th><th>Fields</th><th>Field contracts</th><th>Bound</th><th>Fingerprint</th>
</tr></thead>
<tbody>{"".join(tool_rows)}</tbody>
</table>
</div>
</section>
<section>
<h2>Run traces</h2>
<div class="table-wrap">
<table>
<thead><tr>
<th>Run ID</th><th>Complete</th><th>Events</th><th>Errors</th><th>Terminal</th>
<th>Endpoints</th><th>Started</th><th>Ended</th>
</tr></thead>
<tbody>{trace_rows}</tbody>
</table>
</div>
</section>
<script>
const filter = document.getElementById("filter");
filter.addEventListener("input", () => {{
  const q = filter.value.trim().toLowerCase();
  for (const row of document.querySelectorAll("#capabilities tbody tr")) {{
    row.hidden = Boolean(q) && !row.dataset.search.includes(q);
  }}
}});
</script>
</body>
</html>
"""


def write_dashboard(
    registry: RegistryInspection,
    output: str | Path,
    *,
    traces: Sequence[TraceInspection] = (),
    live: RouterInspection | None = None,
) -> Path:
    """Write a self-contained dashboard and return the destination path."""

    destination = Path(output)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        render_dashboard(registry, traces=traces, live=live),
        encoding="utf-8",
    )
    return destination
