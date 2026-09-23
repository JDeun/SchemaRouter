"""Render a self-contained comparison dashboard from SchemaRouter benchmark JSON reports."""

from __future__ import annotations

import argparse
import json
from html import escape
from pathlib import Path
from typing import Any


def load_report(path: str | Path) -> dict[str, Any]:
    source = Path(path)
    value = json.loads(source.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{source}: benchmark report must be a JSON object")
    summary = value.get("summary")
    if not isinstance(summary, dict) or not summary:
        raise ValueError(f"{source}: benchmark report summary must be a non-empty object")
    environment = value.get("environment", {})
    if not isinstance(environment, dict):
        raise ValueError(f"{source}: benchmark environment must be an object")
    return value


def _pct(value: Any) -> str:
    if value is None:
        return "—"
    return f"{float(value) * 100:.2f}%"


def _number(value: Any) -> str:
    if value is None:
        return "—"
    if isinstance(value, float):
        return f"{value:.3f}"
    return str(value)


def _joined(value: Any) -> str:
    if not isinstance(value, list) or not value:
        return "—"
    return ", ".join(str(item) for item in value)


def render_history(reports: list[tuple[str, dict[str, Any]]]) -> str:
    if not reports:
        raise ValueError("at least one benchmark report is required")

    rows: list[str] = []
    for label, report in reports:
        summary = report["summary"]
        environment = report.get("environment", {})
        if not isinstance(summary, dict) or not isinstance(environment, dict):
            raise ValueError(f"{label}: malformed benchmark report")
        for backend, raw in sorted(summary.items()):
            if not isinstance(raw, dict):
                raise ValueError(f"{label}: summary for {backend!r} must be an object")
            values = (
                label,
                report.get("generated_at") or "—",
                report.get("schemarouter_version") or "—",
                report.get("corpus") or "—",
                environment.get("hardware_label") or environment.get("machine") or "—",
                backend,
                _number(raw.get("cases")),
                _pct(raw.get("accuracy")),
                _pct(raw.get("invalid_plan_rate")),
                _number(raw.get("errors")),
                _pct(raw.get("backend_invocation_rate")),
                _number(raw.get("mean_confidence")),
                _pct(raw.get("abstention_rate")),
                _number(raw.get("p50_latency_ms")),
                _number(raw.get("p95_latency_ms")),
                _number(raw.get("estimated_cost")),
                _joined(raw.get("models")),
                _joined(raw.get("actual_devices")),
            )
            rows.append(
                "<tr>" + "".join(f"<td>{escape(str(value))}</td>" for value in values) + "</tr>"
            )

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>SchemaRouter benchmark history</title>
<style>
:root {{ color-scheme: light dark; font-family: Inter, ui-sans-serif, system-ui, sans-serif; }}
body {{ max-width: 1800px; margin: 0 auto; padding: 32px; line-height: 1.45; }}
h1 {{ letter-spacing: -0.025em; }}
.muted {{ opacity: .68; }}
.table-wrap {{ overflow-x: auto; }}
table {{ width: 100%; border-collapse: collapse; font-size: .88rem; }}
th, td {{
  text-align: left;
  padding: 9px 8px;
  border-bottom: 1px solid #8884;
  vertical-align: top;
}}
th {{ white-space: nowrap; }}
</style>
</head>
<body>
<h1>SchemaRouter benchmark history</h1>
<p class="muted">
Each row preserves its run metadata. Compare quality or latency only when corpus, model/runtime,
hardware, and measurement conditions are equivalent.
</p>
<div class="table-wrap">
<table>
<thead>
<tr>
<th>Run</th><th>Generated</th><th>SchemaRouter</th><th>Corpus</th><th>Hardware</th>
<th>Backend</th><th>Cases</th><th>Accuracy</th><th>Invalid</th><th>Errors</th>
<th>Invoked</th><th>Mean confidence</th><th>Abstention</th><th>P50 ms</th>
<th>P95 ms</th><th>Cost</th><th>Models</th>
<th>Actual device</th>
</tr>
</thead>
<tbody>{"".join(rows)}</tbody>
</table>
</div>
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Render multiple decision benchmark JSON reports into one HTML comparison."
    )
    parser.add_argument("reports", nargs="+", help="Benchmark JSON report paths in display order.")
    parser.add_argument("--output", required=True, type=Path, help="Destination HTML path.")
    args = parser.parse_args()

    reports = [(Path(path).name, load_report(path)) for path in args.reports]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(render_history(reports), encoding="utf-8")
    print(args.output)


if __name__ == "__main__":
    main()
