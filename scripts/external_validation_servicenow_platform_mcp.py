"""Validate and score the ServiceNow Platform MCP cross-project development fixture."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from statistics import mean, median
from typing import Any


def _load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _canonical_bytes(value: Any) -> int:
    return len(
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    )


def _percentile(values: list[float], p: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    position = (len(ordered) - 1) * p
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    weight = position - lower
    return ordered[lower] * (1.0 - weight) + ordered[upper] * weight


def _input_schema(contract: dict[str, Any]) -> dict[str, Any]:
    value = contract.get("inputSchema")
    if value is None:
        value = contract.get("input_schema")
    return value if isinstance(value, dict) else {}


def _input_fields(contract: dict[str, Any]) -> set[str]:
    props = _input_schema(contract).get("properties", {})
    return set(props) if isinstance(props, dict) else set()


def load_package(
    package_dir: Path,
    snapshot_path: Path,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    manifest = _load(package_dir / "manifest.json")
    cases = _load(package_dir / manifest["files"]["cases"])
    snapshot = _load(snapshot_path)
    return manifest, cases, snapshot


def validate_package(
    manifest: dict[str, Any],
    cases: dict[str, Any],
    snapshot: dict[str, Any],
) -> None:
    package_id = manifest["package_id"]
    if cases.get("case_set_id") != package_id:
        raise ValueError("manifest/case package ids do not match")
    if manifest.get("status") != "development_unfrozen":
        raise ValueError("this scorer currently expects a development_unfrozen fixture")
    if manifest["governance"].get("heldout_scoring_allowed"):
        raise ValueError("development fixture must not enable held-out scoring")

    expected_revision = manifest["source_revisions"]["servicenow_platform_mcp"]
    if snapshot.get("source", {}).get("commit") != expected_revision:
        raise ValueError("captured ServiceNow revision does not match the manifest")
    if snapshot.get("mcp_tool_package") != manifest["upstream_runtime"]["tool_package"]:
        raise ValueError("captured MCP tool package does not match the manifest")
    if snapshot.get("source", {}).get("repository") != "Xerrion/servicenow-platform-mcp":
        raise ValueError("upstream repository provenance mismatch")
    if snapshot.get("source", {}).get("package_version") != manifest["upstream_runtime"]["servicenow_platform_mcp_version"]:
        raise ValueError("upstream package version mismatch")
    if snapshot.get("servicenow_environment") != manifest["upstream_runtime"]["servicenow_environment"]:
        raise ValueError("captured ServiceNow environment mismatch")
    if snapshot.get("schema_version") != 1:
        raise ValueError("unknown upstream snapshot schema version")

    tools = snapshot.get("tools")
    if not isinstance(tools, list) or not all(isinstance(tool, dict) for tool in tools):
        raise ValueError("snapshot.tools must be an object list")
    if (len(tools) != manifest["upstream_runtime"]["expected_public_tool_count"]
            or snapshot.get("tool_count") != len(tools)):
        raise ValueError("upstream tool count disagrees with captured tools")
    # The capture script commits to the exact canonical native tool objects,
    # not merely their names/count. Mutations must fail before any scoring.
    digest = hashlib.sha256(json.dumps(
        tools, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
    ).encode("utf-8")).hexdigest()
    if snapshot.get("tools_sha256") != digest:
        raise ValueError("native MCP tool snapshot SHA-256 mismatch")
    tool_map: dict[str, dict[str, Any]] = {}
    for tool in tools:
        name = tool.get("name")
        if not isinstance(name, str) or not name:
            raise ValueError("captured tool name must be a non-empty string")
        if name in tool_map:
            raise ValueError(f"duplicate captured tool name: {name}")
        schema = tool.get("inputSchema", tool.get("input_schema"))
        if not isinstance(schema, dict) or not isinstance(schema.get("properties", {}), dict):
            raise ValueError(f"invalid native inputSchema for {name}")
        tool_map[name] = tool

    seen: set[str] = set()
    counts = {"supported": 0, "unsupported": 0}
    for case in cases.get("cases", []):
        case_id = case.get("id")
        if not isinstance(case_id, str) or not case_id or case_id in seen:
            raise ValueError(f"invalid or duplicate case id: {case_id!r}")
        seen.add(case_id)
        label = case.get("label")
        if label not in counts:
            raise ValueError(f"{case_id}: unsupported label {label!r}")
        counts[label] += 1

        required_tools = case.get("required_tools", [])
        required_fields = case.get("required_fields", {})
        if not isinstance(required_tools, list) or not all(
            isinstance(x, str) and x for x in required_tools
        ):
            raise ValueError(f"{case_id}: required_tools must be a string list")
        if len(required_tools) != len(set(required_tools)):
            raise ValueError(f"{case_id}: duplicate required tool identities")
        if not isinstance(required_fields, dict):
            raise ValueError(f"{case_id}: required_fields must be an object")
        if label == "supported" and not required_tools:
            raise ValueError(f"{case_id}: supported case requires at least one tool")
        if label == "unsupported" and (required_tools or required_fields):
            raise ValueError(f"{case_id}: unsupported case must not declare required tools/fields")

        for tool_name in required_tools:
            if tool_name not in tool_map:
                raise ValueError(f"{case_id}: unknown required tool {tool_name!r}")
            fields = required_fields.get(tool_name, [])
            if not isinstance(fields, list) or not all(isinstance(x, str) and x for x in fields):
                raise ValueError(f"{case_id}: required fields for {tool_name} must be strings")
            if len(fields) != len(set(fields)):
                raise ValueError(f"{case_id}: duplicate required input fields for {tool_name}")
            unknown_fields = set(fields) - _input_fields(tool_map[tool_name])
            if unknown_fields:
                raise ValueError(
                    f"{case_id}: required fields absent from native {tool_name} inputSchema: "
                    f"{sorted(unknown_fields)}"
                )
        if set(required_fields) != set(required_tools):
            raise ValueError(f"{case_id}: required_fields must cover exactly the required tools")

    expected = manifest["counts"]
    actual = {
        "cases": len(seen),
        "supported": counts["supported"],
        "unsupported": counts["unsupported"],
    }
    if actual != expected:
        raise ValueError(f"case counts drifted: expected={expected} actual={actual}")


def build_template(manifest: dict[str, Any], cases: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "package_id": manifest["package_id"],
        "implementation": {
            "name": "",
            "commit": None,
            "commit_source": "unavailable",
            "fixture_reference_revision": None,
            "package_version": None,
            "configuration": {},
        },
        "index_build_ms": None,
        "results": [
            {
                "id": case["id"],
                "candidate_tools": [],
                "visible_contracts": [],
                "latency_ms": None,
            }
            for case in cases["cases"]
        ],
    }


def score(
    manifest: dict[str, Any],
    cases: dict[str, Any],
    snapshot: dict[str, Any],
    submitted: dict[str, Any],
) -> dict[str, Any]:
    # Enforce immutable upstream native tool contract provenance even for
    # direct Python callers (the CLI also validates before invoking us).
    validate_package(manifest, cases, snapshot)
    if submitted.get("package_id") != manifest["package_id"]:
        raise ValueError("result package id mismatch")

    native_tools = {tool["name"]: tool for tool in snapshot["tools"]}
    case_map = {case["id"]: case for case in cases["cases"]}
    rows = submitted.get("results")
    if not isinstance(rows, list) or not all(isinstance(row, dict) for row in rows):
        raise ValueError("results must be an object list")
    if len(rows) != len({row.get("id") for row in rows}):
        raise ValueError("duplicate result ids")
    row_map = {row.get("id"): row for row in rows}
    if set(row_map) != set(case_map):
        raise ValueError("result ids must exactly match case ids")

    tool_recalls: list[float] = []
    tool_full_coverage: list[float] = []
    field_recalls: list[float] = []
    unsupported_nonempty: list[float] = []
    active_tool_counts: list[int] = []
    exposure_bytes: list[int] = []
    latencies: list[float] = []
    per_case: list[dict[str, Any]] = []

    for case_id, case in case_map.items():
        row = row_map[case_id]
        candidates = row.get("candidate_tools")
        visible = row.get("visible_contracts")
        if not isinstance(candidates, list) or not all(isinstance(x, str) for x in candidates):
            raise ValueError(f"{case_id}: candidate_tools must be a string list")
        if len(candidates) != len(set(candidates)):
            raise ValueError(f"{case_id}: duplicate candidate tools")
        if set(candidates) - set(native_tools):
            raise ValueError(f"{case_id}: candidate references an unknown upstream tool")
        if not isinstance(visible, list) or not all(isinstance(x, dict) for x in visible):
            raise ValueError(f"{case_id}: visible_contracts must be an object list")
        visible_names = [contract.get("name") for contract in visible]
        if visible_names != candidates:
            raise ValueError(
                f"{case_id}: visible_contracts must be exact upstream contracts in candidate order"
            )
        for contract in visible:
            name = contract["name"]
            if contract != native_tools[name]:
                raise ValueError(
                    f"{case_id}: visible contract for {name} differs from "
                    "frozen upstream snapshot"
                )

        latency = row.get("latency_ms")
        if latency is not None:
            if isinstance(latency, bool) or not isinstance(latency, (int, float)):
                raise ValueError(f"{case_id}: latency_ms must be numeric or null")
            latency = float(latency)
            if not math.isfinite(latency) or latency < 0:
                raise ValueError(f"{case_id}: latency_ms must be finite and non-negative")
            latencies.append(latency)

        active_tool_counts.append(len(candidates))
        bytes_visible = _canonical_bytes(visible)
        exposure_bytes.append(bytes_visible)

        metrics: dict[str, Any] = {
            "id": case_id,
            "label": case["label"],
            "stratum": case.get("stratum"),
            "active_tool_count": len(candidates),
            "visible_schema_bytes": bytes_visible,
        }

        if case["label"] == "unsupported":
            nonempty = 1.0 if candidates else 0.0
            unsupported_nonempty.append(nonempty)
            metrics["nonempty_candidate"] = bool(candidates)
        else:
            required_tools = set(case["required_tools"])
            selected = set(candidates)
            tool_recall = len(required_tools & selected) / len(required_tools)
            full = 1.0 if required_tools <= selected else 0.0
            tool_recalls.append(tool_recall)
            tool_full_coverage.append(full)
            metrics["required_tool_recall"] = tool_recall
            metrics["required_tool_full_coverage"] = bool(full)

            required_field_total = 0
            required_field_hits = 0
            visible_map = {contract["name"]: contract for contract in visible}
            for tool_name, fields in case.get("required_fields", {}).items():
                required_field_total += len(fields)
                contract = visible_map.get(tool_name)
                if contract is None:
                    continue
                present = _input_fields(contract)
                required_field_hits += len(set(fields) & present)
            field_recall = (
                required_field_hits / required_field_total
                if required_field_total
                else 1.0
            )
            field_recalls.append(field_recall)
            metrics["required_input_field_recall"] = field_recall

        per_case.append(metrics)

    index_build_ms = submitted.get("index_build_ms")
    if index_build_ms is not None:
        if isinstance(index_build_ms, bool) or not isinstance(index_build_ms, (int, float)):
            raise ValueError("index_build_ms must be numeric or null")
        index_build_ms = float(index_build_ms)
        if not math.isfinite(index_build_ms) or index_build_ms < 0:
            raise ValueError("index_build_ms must be finite and non-negative")

    return {
        "schema_version": 1,
        "package_id": manifest["package_id"],
        "implementation": submitted.get("implementation", {}),
        "summary": {
            "supported_required_tool_recall": mean(tool_recalls) if tool_recalls else None,
            "supported_required_tool_full_coverage": (
                mean(tool_full_coverage) if tool_full_coverage else None
            ),
            "supported_required_input_field_recall": (
                mean(field_recalls) if field_recalls else None
            ),
            "unsupported_nonempty_candidate_rate": (
                mean(unsupported_nonempty) if unsupported_nonempty else None
            ),
            "mean_active_tool_count": mean(active_tool_counts) if active_tool_counts else 0.0,
            "mean_visible_schema_bytes": mean(exposure_bytes) if exposure_bytes else 0.0,
            "median_selection_ms": median(latencies) if latencies else None,
            "p95_selection_ms": _percentile(latencies, 0.95),
            "index_build_ms": index_build_ms,
        },
        "per_case": per_case,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    for name in ("validate", "template", "score"):
        child = sub.add_parser(name)
        child.add_argument("--package-dir", required=True, type=Path)
        child.add_argument("--snapshot", required=True, type=Path)
        if name == "template":
            child.add_argument("--out", required=True, type=Path)
        elif name == "score":
            child.add_argument("--results", required=True, type=Path)
            child.add_argument("--out", type=Path)

    args = parser.parse_args()
    manifest, cases, snapshot = load_package(args.package_dir, args.snapshot)
    validate_package(manifest, cases, snapshot)

    if args.command == "validate":
        print(
            json.dumps(
                {
                    "package_id": manifest["package_id"],
                    "status": "valid",
                    "tool_count": snapshot["tool_count"],
                    "case_counts": manifest["counts"],
                    "tools_sha256": snapshot["tools_sha256"],
                },
                indent=2,
                sort_keys=True,
            )
        )
        return

    if args.command == "template":
        payload = build_template(manifest, cases)
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(args.out)
        return

    submitted = _load(args.results)
    payload = score(manifest, cases, snapshot, submitted)
    rendered = json.dumps(payload, indent=2, sort_keys=True)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)


if __name__ == "__main__":
    main()
