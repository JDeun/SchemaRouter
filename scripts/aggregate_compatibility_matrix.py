from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REFERENCE_EVIDENCE = {
    "pinned_reference_implementation",
    "local_reference_contract",
    "required_reference_report",
}
PUBLIC_EVIDENCE = {"live_public_provider"}


def _load_reports(
    directory: Path,
    *,
    required_reference_reports: tuple[str, ...] = (),
) -> list[dict[str, Any]]:
    reports: list[dict[str, Any]] = []
    required = set(required_reference_reports)
    seen: set[str] = set()

    for path in sorted(directory.glob("*-compatibility.json")):
        seen.add(path.name)
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            reports.append(
                {
                    "adapter": path.name.removesuffix("-compatibility.json"),
                    "source": str(path),
                    "status": "invalid_report",
                    "error_type": type(exc).__name__,
                    "details": {
                        "evidence_kind": (
                            "required_reference_report"
                            if path.name in required
                            else "unknown"
                        ),
                    },
                }
            )
            continue
        if isinstance(payload, dict):
            reports.append(payload)
        else:
            reports.append(
                {
                    "adapter": path.name.removesuffix("-compatibility.json"),
                    "source": str(path),
                    "status": "invalid_report",
                    "error_type": "NonObjectReport",
                    "details": {
                        "evidence_kind": (
                            "required_reference_report"
                            if path.name in required
                            else "unknown"
                        ),
                    },
                }
            )

    for filename in sorted(required - seen):
        reports.append(
            {
                "adapter": filename.removesuffix("-compatibility.json"),
                "source": str(directory / filename),
                "status": "missing_report",
                "error_type": "MissingReport",
                "details": {
                    "evidence_kind": "required_reference_report",
                },
            }
        )
    return reports


def _classification(
    *,
    status: str,
    evidence_kind: str,
) -> str:
    if status == "success":
        return "success"
    if status == "skipped":
        return "skipped"
    if evidence_kind in REFERENCE_EVIDENCE:
        return "contract_failure"
    if evidence_kind in PUBLIC_EVIDENCE:
        return "unavailable"
    return "failure"


def _row(report: dict[str, Any]) -> dict[str, Any]:
    details = report.get("details")
    if not isinstance(details, dict):
        details = {}
    status = str(report.get("status", "unknown"))
    evidence_kind = str(details.get("evidence_kind", "unknown"))
    return {
        "adapter": str(report.get("adapter", "unknown")),
        "status": status,
        "classification": _classification(
            status=status,
            evidence_kind=evidence_kind,
        ),
        "source": str(report.get("source", "")),
        "generated_at": str(report.get("generated_at", "")),
        "schemarouter_version": str(report.get("schemarouter_version", "")),
        "evidence_kind": evidence_kind,
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
    classifications = {
        name: sum(row["classification"] == name for row in rows)
        for name in (
            "success",
            "contract_failure",
            "unavailable",
            "skipped",
        )
    }
    unclassified_failure = sum(
        row["classification"] == "failure" for row in rows
    )
    return {
        "schema_version": 2,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "adapters": rows,
        "summary": {
            "total": len(rows),
            "success": classifications["success"],
            "failure": sum(row["status"] != "success" for row in rows),
            "reference_failures": classifications["contract_failure"],
            "contract_failure": classifications["contract_failure"],
            "unavailable": classifications["unavailable"],
            "skipped": classifications["skipped"],
            "unclassified_failure": unclassified_failure,
        },
    }


def render_markdown(matrix: dict[str, Any]) -> str:
    rows = matrix["adapters"]
    lines = [
        "# SchemaRouter compatibility matrix",
        "",
        f"Generated: {matrix['generated_at']}",
        "",
        (
            "| Adapter | Evidence | Provider/source | Discovery | Endpoints | "
            "Bound | Safe execution | Latency (discover/execute ms) | Auth | "
            "Classification | Status |"
        ),
        (
            "| --- | --- | --- | ---: | ---: | --- | --- | --- | --- | "
            "--- | --- |"
        ),
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
                    str(row["classification"]),
                    status,
                ]
            )
            + " |"
        )

    lines.extend(
        [
            "",
            (
                "Public-provider failures are classified as unavailable external "
                "compatibility evidence and do not block compatibility qualification."
            ),
            (
                "Local/pinned reference failures, invalid required reports, and "
                "missing required reports are classified as contract_failure "
                "and block qualification."
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
    parser.add_argument(
        "--required-reference-report",
        action="append",
        default=[],
        metavar="FILENAME",
    )
    args = parser.parse_args()

    matrix = build_matrix(
        _load_reports(
            args.reports_dir,
            required_reference_reports=tuple(args.required_reference_report),
        )
    )
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
