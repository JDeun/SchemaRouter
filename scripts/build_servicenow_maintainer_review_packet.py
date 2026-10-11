"""Produce a zero-scoring, source-backed ServiceNow #192 maintainer review sheet.

This is a DEV contract inspection only. No canonical labels, access rights,
tool executability or independent evidence are inferred from input schemas.
"""
from __future__ import annotations

import argparse
from pathlib import Path

from scripts.external_validation_servicenow_platform_mcp import (
    load_package,
    validate_package,
)

# Previously disclosed visible DEV misses, NOT posthoc gold corrections.
REVIEW_FLAGS = {
    "sn-dev-006": "record_read mapping; confirm intended tool",
    "sn-dev-007": "resolve_choice mapping; confirm intended tool",
    "sn-dev-015": "flow find_by_table mapping; confirm intended tool",
}


def _safe(value: object) -> str:
    return str(value).replace("|", r"\|").replace("\n", " ").replace("\r", " ").strip()


def build(manifest: dict, cases: dict, snapshot: dict) -> str:
    validate_package(manifest, cases, snapshot)
    native = {tool["name"]: tool for tool in snapshot["tools"]}
    tick = chr(96)
    lines = [
        "# ServiceNow Platform MCP readonly — visible DEV label review",
        "",
        "**NOT HELD-OUT. No task execution, model, credentials or gold-label changes.**",
        "",
        f"- Upstream revision: {tick}{manifest['source_revisions']['servicenow_platform_mcp']}{tick}",
        f"- Captured tool-schema SHA-256: {tick}{snapshot['tools_sha256']}{tick}",
        f"- MCP package: {tick}{snapshot['mcp_tool_package']}{tick}; actual tools/list count: {len(native)}",
        f"- Visible development tasks: {len(cases['cases'])}; do NOT reuse as hidden confirmation cases",
        "- Both conditions use the same original readonly MCP contracts; selection differs only",
        "- The required fields are top-level MCP inputSchema parameters, NOT domain output fields",
        "- No static package baseline ranking quality or end-to-end agent quality is claimed",
        "",
        "## All disclosed synthetic tasks and proposed labels",
        "",
        "| ID | Type | Query | Proposed tool(s) | Proposed input fields | Review question |",
        "|---|---|---|---|---|---|",
    ]
    for case in cases["cases"]:
        tools = ", ".join(tick + x + tick for x in case["required_tools"]) or "(none)"
        field_spec = "; ".join(
            name + ": " + ", ".join(tick + item + tick for item in fields)
            for name, fields in case["required_fields"].items()
        ) or "(none)"
        lines.append(
            f"| {_safe(case['id'])} | {_safe(case['label'])} "
            f"| {_safe(case['query'])} | {tools} | {_safe(field_spec)} "
            f"| {_safe(REVIEW_FLAGS.get(case['id'], ''))} |"
        )
    lines += ["", "## Native MCP input-schema parameter reference", ""]
    for name in sorted(native):
        tool = native[name]
        schema = tool.get("inputSchema") or tool.get("input_schema") or {}
        properties = schema.get("properties") or {}
        required = schema.get("required") or []
        lines += [
            "### " + tick + _safe(name) + tick,
            "",
            "Description: " + _safe(tool.get("description", "")),
            "",
            "Native input properties: " + (
                ", ".join(tick + _safe(x) + tick for x in sorted(properties)) or "(none)"
            ),
            "Native required inputs: " + (
                ", ".join(tick + _safe(x) + tick for x in required) or "(none)"
            ),
            "",
        ]
    lines += [
        "## Review requested (no implied upstream endorsement)",
        "",
        "1. Is readonly the correct package rather than core_readonly?",
        "2. Are the proposed task-to-tool mappings semantically correct?",
        "3. Especially review disclosed misses sn-dev-006, sn-dev-007, sn-dev-015;",
        "   do not silently change the existing gold labels.",
        "4. Does MCPServer.list_tools() reflect the appropriate visibility boundary?",
        "5. Freeze a future selection budget prospectively: K=3, K=5 or another K?",
        "6. Are canonical JSON tool-schema bytes an acceptable context-size measure?",
        "   They are not model tokens, full agent latency or task success.",
        "7. Are readonly-negative and unrelated OOD cases correctly classified?",
        "",
        "Independent authoring/review and frozen new task digests are needed before",
        "a confirmatory benchmark. Development errors cannot choose future labels.",
        "",
    ]
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--package-dir", type=Path, required=True)
    parser.add_argument("--snapshot", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    manifest, cases, snapshot = load_package(args.package_dir, args.snapshot)
    report = build(manifest, cases, snapshot)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(report, encoding="utf-8")
    print(f"Created zero-scoring maintainer review sheet: {args.out}")


if __name__ == "__main__":
    main()
