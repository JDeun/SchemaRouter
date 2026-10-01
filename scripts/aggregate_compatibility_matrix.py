from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REFERENCE_EVIDENCE = {
    "pinned_reference_implementation",
}


def _load_reports(directory: Path) -> list[dict[str, Any]]:
    reports: list[dict[str, Any]] = []
    for path in sorted(directory.glob("*-compatibility.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            reports.append(
                {
                    "adapter": path.name.removesuffix("-compatibility.json"),
                    "source": str(path),
                    "status": "invalid_report",
                    "error_type": type(exc).__name__,
                    "details": {},
                }
            )
            continue
        if isinstance(payload, dict):
            reports.append(payload)
    return reports


def _row(report: dict[str, Any]) -> dict[str, Any]:
    details = report.get("details")
    if not isinstance(details, dict):
        details = {}
    return {
        "adapter": str(report.get("adapter", "unknown")),
        "status": str(report.get("status", "unknown")),
        "source": str(report.get("source", "")),
        "generated_at": str(report.get("generated_at", "")),
        "schemarouter_version": str(report.get("schemarouter_version", "")),
        "evidence_kind": str(details.get("evidence_kind", "unknown")),
        "provider": str(details.get("provider", "")),
        "discovery_success": bool(details.get("discovery_success", False)),
        "tool_count": details.get("tool_count"),
        "endpoint_count": details.get("endpoint_count"),
        "execution_bound": details.get("execution_bound"),
        "execution_success": bool(details.get("execution_success", False)),
        "safe_endpoint": details.get("safe_endpoint"),
        "returned_shape": details.get("returned_shape"),
        "discovery_latency_ms": details.get("discovery_latency_ms"),
        "execution_latency_ms": details.get("execution_latency_ms"),
        "auth_required": details.get("auth_required"),
        "known_quirks": details.get("known_quirks", []),
        "error_type": report.get("error_type"),
    }


def build_matrix(reports: list[dict[str, Any]]) -> dict[str, Any]:
    rows = sorted((_row(report) for report in reports), key=lambda row: row["adapter"])
    return {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "adapters": rows,
        "summary": {
            "total": len(rows),
            "success": sum(row["status"] == "success" for row in rows),
            "failure": sum(row["status"] != "success" for row in rows),
            "reference_failures": sum(
                row["status"] != "success"
                and row["evidence_kind"] in REFERENCE_EVIDENCE
                for row in rows
            ),
        },
    }


def render_markdown(matrix: dict[str, Any]) -> str:
    rows = matrix["adapters"]
    lines = [
        "# SchemaRouter live compatibility matrix",
        "",
        f"Generated: {matrix['generated_at']}",
        "",
        (
            "| Adapter | Evidence | Provider/source | Discovery | Endpoints | "
            "Bound | Safe execution | Latency (discover/execute ms) | Auth | Status |"
        ),
        "| --- | --- | --- | ---: | ---: | --- | --- | --- | --- | --- |",
    ]
    for row in rows:
        discovery = "yes" if row["discovery_success"] else "no"
        bound = (
            "yes"
            if row["execution_bound"] is True
            else "no"
            if row["execution_bound"] is False
            else "—"
        )
        execution = "yes" if row["execution_success"] else "no"
        auth = (
            "yes"
            if row["auth_required"] is True
            else "no"
            if row["auth_required"] is False
            else "unknown"
        )
        provider = row["provider"] or row["source"]
        latency = (
            f"{row['discovery_latency_ms'] or '—'}/"
            f"{row['execution_latency_ms'] or '—'}"
        )
        status = row["status"]
        if row.get("error_type"):
            status += f" ({row['error_type']})"
        lines.append(
            "| "
            + " | ".join(
                [
                    str(row["adapter"]),
                    str(row["evidence_kind"]),
                    str(provider).replace("|", "\\|"),
                    discovery,
                    str(row["endpoint_count"] or "—"),
                    bound,
                    execution,
                    latency,
                    auth,
                    status,
                ]
            )
            + " |"
        )

    lines.extend(
        [
            "",
            (
                "Public-provider failures are external compatibility evidence and are not, "
                "by themselves, classified as SchemaRouter regressions."
            ),
            (
                "Pinned-reference failures indicate a local compatibility regression and "
                "should be investigated."
            ),
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--reports-dir", required=True, type=Path)
    parser.add_argument("--json-out", required=True, type=Path)
    parser.add_argument("--markdown-out", required=True, type=Path)
    parser.add_argument("--require-reference-success", action="store_true")
    args = parser.parse_args()

    matrix = build_matrix(_load_reports(args.reports_dir))
    args.json_out.parent.mkdir(parents=True, exist_ok=True)
    args.markdown_out.parent.mkdir(parents=True, exist_ok=True)
    args.json_out.write_text(
        json.dumps(matrix, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    args.markdown_out.write_text(render_markdown(matrix), encoding="utf-8")

    if args.require_reference_success and matrix["summary"]["reference_failures"]:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
