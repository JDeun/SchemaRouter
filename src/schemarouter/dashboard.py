from __future__ import annotations

from html import escape
from pathlib import Path

from .observability import ObservabilitySnapshot


def _value(value: object) -> str:
    if value is None:
        return "—"
    if isinstance(value, bool):
        return "yes" if value else "no"
    return str(value)


def render_dashboard(snapshot: ObservabilitySnapshot) -> str:
    """Render a dependency-free, self-contained observability dashboard."""

    registry = snapshot.registry
    cards = [
        ("Registry version", registry.registry_version),
        ("Tools", registry.tool_count),
        ("Endpoints", registry.endpoint_count),
        ("Read-only", registry.read_only_endpoints),
        ("Mutations", registry.mutation_endpoints),
        ("Destructive", registry.destructive_endpoints),
        ("Unclassified", registry.unclassified_endpoints),
        ("Runs", len(snapshot.traces)),
    ]

    card_html = "".join(
        (
            '<div class="card">'
            f'<div class="metric">{escape(_value(value))}</div>'
            f'<div class="label">{escape(label)}</div>'
            "</div>"
        )
        for label, value in cards
    )

    tool_rows: list[str] = []
    for tool in registry.tools:
        for endpoint in tool.endpoints:
            tool_rows.append(
                "<tr "
                f'data-search="{escape((tool.key + " " + endpoint.name + " " + (tool.adapter or "")).lower())}">'
                f"<td>{escape(tool.key)}</td>"
                f"<td>{escape(tool.adapter or 'unknown')}</td>"
                f"<td>{escape(endpoint.name)}</td>"
                f"<td>{escape(endpoint.method or '—')}</td>"
                f"<td>{escape(endpoint.path or '—')}</td>"
                f"<td>{escape(_value(endpoint.read_only))}</td>"
                f"<td>{escape(_value(endpoint.destructive))}</td>"
                f"<td>{escape(_value(tool.execution_bound))}</td>"
                f"<td>{escape(', '.join(endpoint.required_parameters) or '—')}</td>"
                f"<td>{escape(', '.join(endpoint.output_fields) or '—')}</td>"
                "</tr>"
            )

    trace_rows = "".join(
        (
            "<tr>"
            f"<td>{escape(trace.run_id)}</td>"
            f"<td>{escape(_value(trace.complete))}</td>"
            f"<td>{trace.event_count}</td>"
            f"<td>{escape(trace.started_at.isoformat())}</td>"
            f"<td>{escape(trace.ended_at.isoformat() if trace.ended_at else '—')}</td>"
            f"<td>{escape(trace.terminal_event or '—')}</td>"
            f"<td>{escape(', '.join(trace.tools) or '—')}</td>"
            f"<td>{escape(', '.join(trace.error_types) or '—')}</td>"
            "</tr>"
        )
        for trace in snapshot.traces
    )

    planner_html = ""
    if snapshot.planner is not None:
        planner_html = (
            "<section><h2>Planner</h2><dl>"
            f"<dt>Analyzer</dt><dd>{escape(snapshot.planner.analyzer)}</dd>"
            f"<dt>Decision backend</dt><dd>{escape(snapshot.planner.decision_backend or 'none')}</dd>"
            f"<dt>Decision policy</dt><dd><code>{escape(str(snapshot.planner.decision_policy))}</code></dd>"
            "</dl></section>"
        )

    execution_html = ""
    if snapshot.execution is not None:
        execution_html = (
            "<section><h2>Execution policy</h2>"
            f"<code>{escape(str(snapshot.execution.policy))}</code></section>"
        )

    adapter_summary = ", ".join(
        f"{name}: {count}" for name, count in sorted(registry.adapters.items())
    ) or "none"

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>SchemaRouter Observability</title>
<style>
:root {{ color-scheme: light dark; font-family: Inter, ui-sans-serif, system-ui, sans-serif; }}
body {{ max-width: 1500px; margin: 0 auto; padding: 32px; line-height: 1.45; }}
h1, h2 {{ letter-spacing: -0.02em; }}
.grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr)); gap: 12px; }}
.card {{ border: 1px solid #8885; border-radius: 12px; padding: 16px; }}
.metric {{ font-size: 1.8rem; font-weight: 700; }}
.label {{ opacity: .72; }}
section {{ margin-top: 32px; }}
table {{ width: 100%; border-collapse: collapse; font-size: .92rem; }}
th, td {{ text-align: left; padding: 9px 8px; border-bottom: 1px solid #8884; vertical-align: top; }}
th {{ position: sticky; top: 0; backdrop-filter: blur(8px); }}
input {{ width: min(520px, 100%); padding: 10px 12px; border-radius: 8px; border: 1px solid #8886; }}
code {{ white-space: pre-wrap; overflow-wrap: anywhere; }}
.muted {{ opacity: .7; }}
</style>
</head>
<body>
<h1>SchemaRouter Observability</h1>
<p class="muted">Privacy-safe registry and trace summary. Arbitrary metadata and trace payload values are omitted.</p>
<div class="grid">{card_html}</div>
<section>
<h2>Registry</h2>
<p>Adapters: {escape(adapter_summary)} · Bound live tools: {escape(", ".join(registry.bound_tools) or "not available")}</p>
<input id="filter" type="search" placeholder="Filter tool, endpoint, adapter…" autocomplete="off">
<table id="tools">
<thead><tr>
<th>Tool</th><th>Adapter</th><th>Endpoint</th><th>Method</th><th>Path</th>
<th>Read-only</th><th>Destructive</th><th>Bound</th><th>Required params</th><th>Output fields</th>
</tr></thead>
<tbody>{"".join(tool_rows)}</tbody>
</table>
</section>
{planner_html}
{execution_html}
<section>
<h2>Run traces</h2>
<table>
<thead><tr>
<th>Run ID</th><th>Complete</th><th>Events</th><th>Started</th><th>Ended</th>
<th>Terminal</th><th>Tools</th><th>Error types</th>
</tr></thead>
<tbody>{trace_rows}</tbody>
</table>
</section>
<script>
const filter = document.getElementById("filter");
filter.addEventListener("input", () => {{
  const q = filter.value.trim().toLowerCase();
  for (const row of document.querySelectorAll("#tools tbody tr")) {{
    row.hidden = q && !row.dataset.search.includes(q);
  }}
}});
</script>
</body>
</html>
"""


def write_dashboard(snapshot: ObservabilitySnapshot, path: str | Path) -> Path:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(render_dashboard(snapshot), encoding="utf-8")
    return destination
