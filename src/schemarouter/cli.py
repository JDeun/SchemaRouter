from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from .inspection import (
    RegistryInspection,
    ToolInspection,
    TraceInspection,
    inspect_registry,
    inspect_tool,
    inspect_traces,
    tool_spec_document,
)
from .registry import SQLiteRegistry
from .traces import SQLiteRunTraceStore


def _json_dump(value: Any) -> str:
    if hasattr(value, "model_dump"):
        value = value.model_dump(mode="json")
    return json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True)


def _short_fingerprint(value: str) -> str:
    return value[:12]


def _render_registry(snapshot: RegistryInspection) -> str:
    lines = [
        (
            f"Registry v{snapshot.version}: {snapshot.tool_count} tools, "
            f"{snapshot.endpoint_count} endpoints "
            f"({snapshot.read_only_endpoints} read-only, "
            f"{snapshot.mutating_endpoints} mutating, "
            f"{snapshot.unclassified_endpoints} unclassified)"
        )
    ]
    for tool in snapshot.tools:
        source = (
            tool.provenance.get("source_url")
            or tool.provenance.get("resolved_schema_url")
            or tool.provenance.get("versioned_base_url")
        )
        adapter = tool.provenance.get("adapter") or tool.source_type
        origin = ""
        if adapter:
            origin += f" · {adapter}"
        if source:
            origin += f" · {source}"
        lines.append(
            f"- {tool.key}: {tool.endpoint_count} endpoints "
            f"[{_short_fingerprint(tool.fingerprint)}]{origin}"
        )
        for endpoint in tool.endpoints:
            method = endpoint.method or "-"
            path = endpoint.path or "-"
            if endpoint.read_only is True:
                mode = "read-only"
            elif endpoint.read_only is False:
                mode = "mutating"
            else:
                mode = "unclassified"
            destructive = ", destructive" if endpoint.destructive is True else ""
            lines.append(
                f"  - {endpoint.name}: {method} {path} · {mode}{destructive} · "
                f"{endpoint.parameter_count} params/{endpoint.output_field_count} fields "
                f"[{_short_fingerprint(endpoint.fingerprint)}]"
            )
    return "\n".join(lines)


def _render_tool(tool: ToolInspection, *, document: dict[str, Any]) -> str:
    lines = [
        f"Tool {tool.key}",
        f"fingerprint: {tool.fingerprint}",
        f"description: {tool.description or '-'}",
        f"source_type: {tool.source_type or '-'}",
        f"license: {tool.license or '-'}",
        f"endpoints: {tool.endpoint_count}",
    ]
    if tool.provenance:
        lines.append("provenance:")
        for key, value in tool.provenance.items():
            lines.append(f"  - {key}: {value}")
    raw_endpoints = {
        str(endpoint.get("name")): endpoint
        for endpoint in document.get("endpoints", [])
        if isinstance(endpoint, dict)
    }
    for endpoint in tool.endpoints:
        raw = raw_endpoints.get(endpoint.name, {})
        parameters = raw.get("parameters", [])
        fields = raw.get("output_fields", [])
        lines.append("")
        lines.append(f"[{endpoint.name}]")
        lines.append(f"fingerprint: {endpoint.fingerprint}")
        lines.append(f"method/path: {endpoint.method or '-'} {endpoint.path or '-'}")
        lines.append(
            "classification: "
            + (
                "read-only"
                if endpoint.read_only is True
                else "mutating"
                if endpoint.read_only is False
                else "unclassified"
            )
            + (", destructive" if endpoint.destructive is True else "")
        )
        if parameters:
            lines.append("parameters:")
            for parameter in parameters:
                if not isinstance(parameter, dict):
                    continue
                required = "required" if parameter.get("required") else "optional"
                location = parameter.get("location") or "argument"
                lines.append(
                    f"  - {parameter.get('name')}: {location}, {required}"
                )
        else:
            lines.append("parameters: -")
        if fields:
            lines.append("output_fields:")
            for field in fields:
                if not isinstance(field, dict):
                    continue
                path = field.get("path") or [field.get("name")]
                rendered_path = ".".join(str(part) for part in path if part)
                suffix = " identifier" if field.get("identifier") else ""
                lines.append(f"  - {field.get('name')}: {rendered_path}{suffix}")
        else:
            lines.append("output_fields: -")
    return "\n".join(lines)


def _render_traces(traces: Sequence[TraceInspection]) -> str:
    if not traces:
        return "No run traces."
    lines = []
    for trace in traces:
        state = "complete" if trace.complete else "incomplete"
        terminal = trace.terminal_event or "-"
        endpoints = ", ".join(trace.endpoints) or "-"
        lines.append(
            f"- {trace.run_id}: {state}, {trace.event_count} events, "
            f"terminal={terminal}, errors={trace.error_count}, endpoints={endpoints}"
        )
    return "\n".join(lines)


def _render_trace_detail(
    store: SQLiteRunTraceStore,
    run_id: str,
) -> str:
    trace = store.trace(run_id)
    lines = [
        f"Run {trace.run_id}",
        f"complete: {trace.complete}",
        f"events: {len(trace.events)}",
    ]
    for event in trace.events:
        target = (
            f" {event.tool}.{event.endpoint}"
            if event.tool and event.endpoint
            else f" {event.tool}"
            if event.tool
            else ""
        )
        lines.append(
            f"{event.sequence:04d} {event.timestamp.isoformat()} "
            f"{event.event}{target}"
        )
    return "\n".join(lines)


def _existing_db(path: Path) -> Path:
    if not path.exists():
        raise FileNotFoundError(f"database does not exist: {path}")
    if not path.is_file():
        raise ValueError(f"database path is not a file: {path}")
    return path


def _add_json_flag(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit stable JSON instead of human-readable text.",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="schemarouter",
        description="SchemaRouter operational inspection CLI.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    inspect_parser = subparsers.add_parser(
        "inspect",
        help="Inspect persisted registries and run traces without executing tools.",
    )
    inspect_subparsers = inspect_parser.add_subparsers(dest="surface", required=True)

    registry = inspect_subparsers.add_parser(
        "registry",
        help="Summarize a persisted SQLite tool registry.",
    )
    registry.add_argument("--db", required=True, type=Path, help="SQLite registry path.")
    _add_json_flag(registry)

    tool = inspect_subparsers.add_parser(
        "tool",
        help="Inspect one registered tool and its endpoints.",
    )
    tool.add_argument("key", help="Registry tool key, including namespace when present.")
    tool.add_argument("--db", required=True, type=Path, help="SQLite registry path.")
    _add_json_flag(tool)

    traces = inspect_subparsers.add_parser(
        "traces",
        help="List persisted run traces.",
    )
    traces.add_argument("--db", required=True, type=Path, help="SQLite trace-store path.")
    trace_state = traces.add_mutually_exclusive_group()
    trace_state.add_argument(
        "--complete",
        action="store_true",
        help="Show only terminal traces.",
    )
    trace_state.add_argument(
        "--incomplete",
        action="store_true",
        help="Show only non-terminal traces.",
    )
    _add_json_flag(traces)

    trace = inspect_subparsers.add_parser(
        "trace",
        help="Inspect one persisted run trace.",
    )
    trace.add_argument("run_id", help="Run ID.")
    trace.add_argument("--db", required=True, type=Path, help="SQLite trace-store path.")
    _add_json_flag(trace)

    return parser


def _run(args: argparse.Namespace) -> str:
    if args.command != "inspect":
        raise ValueError(f"unsupported command: {args.command}")

    if args.surface == "registry":
        with SQLiteRegistry(_existing_db(args.db)) as registry:
            snapshot = inspect_registry(registry)
        return _json_dump(snapshot) if args.json else _render_registry(snapshot)

    if args.surface == "tool":
        with SQLiteRegistry(args.db) as registry:
            tool = inspect_tool(registry, args.key)
            document = tool_spec_document(registry.get(args.key))
        return (
            _json_dump(document)
            if args.json
            else _render_tool(tool, document=document)
        )

    if args.surface == "traces":
        complete: bool | None = None
        if args.complete:
            complete = True
        elif args.incomplete:
            complete = False
        with SQLiteRunTraceStore(_existing_db(args.db)) as store:
            traces = inspect_traces(store, complete=complete)
        if args.json:
            return _json_dump(
                [trace.model_dump(mode="json") for trace in traces]
            )
        return _render_traces(traces)

    if args.surface == "trace":
        with SQLiteRunTraceStore(args.db) as store:
            if args.json:
                return _json_dump(
                    store.trace(args.run_id).model_dump(mode="json")
                )
            return _render_trace_detail(store, args.run_id)

    raise ValueError(f"unsupported inspection surface: {args.surface}")


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        output = _run(args)
    except (KeyError, OSError, ValueError, RuntimeError) as exc:
        parser.exit(2, f"schemarouter: {type(exc).__name__}: {exc}\n")
    sys.stdout.write(output + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
