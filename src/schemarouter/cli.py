from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Sequence

import yaml

from .dashboard import write_dashboard
from .errors import SchemaRouterError
from .observability import (
    ObservabilitySnapshot,
    observe_registry,
    observe_trace,
    observe_trace_store,
)
from .openapi_compatibility import analyze_openapi_compatibility
from .registry import SQLiteRegistry
from .traces import SQLiteRunTraceStore


def _print_registry(snapshot: ObservabilitySnapshot) -> None:
    registry = snapshot.registry
    print(
        f"Registry v{registry.registry_version}: "
        f"{registry.tool_count} tools, {registry.endpoint_count} endpoints"
    )
    print(
        "Side effects: "
        f"{registry.read_only_endpoints} read-only, "
        f"{registry.mutation_endpoints} mutations, "
        f"{registry.destructive_endpoints} destructive, "
        f"{registry.unclassified_endpoints} unclassified"
    )
    print(
        "Adapters: "
        + (", ".join(f"{name}={count}" for name, count in registry.adapters.items()) or "none")
    )
    for tool in registry.tools:
        print(
            f"\n[{tool.key}] adapter={tool.adapter or 'unknown'} "
            f"remote={tool.remote} bound={tool.execution_bound}"
        )
        for endpoint in tool.endpoints:
            method = endpoint.method or "—"
            path = endpoint.path or "—"
            required = ",".join(endpoint.required_parameters) or "—"
            fields = ",".join(endpoint.output_fields) or "—"
            print(
                f"  {method:7} {endpoint.name} path={path} "
                f"read_only={endpoint.read_only} destructive={endpoint.destructive} "
                f"required=[{required}] fields=[{fields}]"
            )


def _print_traces(traces) -> None:
    if not traces:
        print("No run traces.")
        return
    for trace in traces:
        ended = trace.ended_at.isoformat() if trace.ended_at else "—"
        print(
            f"{trace.run_id} complete={trace.complete} events={trace.event_count} "
            f"terminal={trace.terminal_event or '—'} "
            f"started={trace.started_at.isoformat()} ended={ended}"
        )
        if trace.tools:
            print("  tools: " + ", ".join(trace.tools))
        if trace.error_types:
            print("  errors: " + ", ".join(trace.error_types))


def _load_openapi_file(path: str) -> dict:
    raw = Path(path).read_text(encoding="utf-8")
    try:
        value = json.loads(raw)
    except json.JSONDecodeError:
        value = yaml.safe_load(raw)
    if not isinstance(value, dict):
        raise ValueError("OpenAPI document must decode to an object")
    return value


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="schemarouter")
    sub = parser.add_subparsers(dest="command", required=True)

    inspect_parser = sub.add_parser("inspect", help="Inspect registry, traces, or OpenAPI compatibility")
    inspect_sub = inspect_parser.add_subparsers(dest="inspect_target", required=True)

    registry_parser = inspect_sub.add_parser("registry", help="Inspect a persistent SQLite registry")
    registry_parser.add_argument("--db", required=True, help="Path to SQLiteRegistry database")
    registry_parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON")

    traces_parser = inspect_sub.add_parser("traces", help="Inspect persistent run traces")
    traces_parser.add_argument("--db", required=True, help="Path to SQLiteRunTraceStore database")
    traces_parser.add_argument("--run-id", default=None, help="Inspect one run only")
    traces_parser.add_argument(
        "--complete",
        choices=["all", "yes", "no"],
        default="all",
        help="Filter complete/incomplete traces",
    )
    traces_parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON")

    openapi_parser = inspect_sub.add_parser(
        "openapi",
        help="Inspect a local OpenAPI JSON/YAML file without importing or executing it",
    )
    openapi_parser.add_argument("file", help="Path to OpenAPI JSON/YAML document")
    openapi_parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON")

    dashboard_parser = sub.add_parser(
        "dashboard",
        help="Export a self-contained privacy-safe HTML observability dashboard",
    )
    dashboard_parser.add_argument("--registry", required=True, help="Path to SQLiteRegistry database")
    dashboard_parser.add_argument("--traces", default=None, help="Optional SQLite run-trace database")
    dashboard_parser.add_argument("--output", required=True, help="Destination HTML file")

    return parser


def _complete_filter(value: str) -> bool | None:
    if value == "yes":
        return True
    if value == "no":
        return False
    return None


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        if args.command == "inspect" and args.inspect_target == "registry":
            with SQLiteRegistry(args.db) as registry:
                observed = observe_registry(registry)
            snapshot = ObservabilitySnapshot(registry=observed)
            if args.json:
                print(snapshot.model_dump_json(indent=2))
            else:
                _print_registry(snapshot)
            return 0

        if args.command == "inspect" and args.inspect_target == "traces":
            with SQLiteRunTraceStore(args.db) as store:
                if args.run_id:
                    traces = [observe_trace(store.trace(args.run_id))]
                else:
                    traces = observe_trace_store(
                        store,
                        complete=_complete_filter(args.complete),
                    )
            if args.json:
                print(json.dumps([trace.model_dump(mode="json") for trace in traces], indent=2))
            else:
                _print_traces(traces)
            return 0

        if args.command == "inspect" and args.inspect_target == "openapi":
            report = analyze_openapi_compatibility(_load_openapi_file(args.file))
            if args.json:
                print(report.model_dump_json(indent=2, by_alias=True))
            else:
                print(
                    f"OpenAPI {report.openapi_version or 'unknown'}: {report.status} "
                    f"({report.operations_importable}/{report.operations_total} operations importable)"
                )
                for issue in report.issues:
                    print(
                        f"  [{issue.support}] {issue.schema_construct} "
                        f"at {issue.location}: {issue.message}"
                    )
            return 0

        if args.command == "dashboard":
            with SQLiteRegistry(args.registry) as registry:
                observed_registry = observe_registry(registry)
            traces = []
            if args.traces:
                with SQLiteRunTraceStore(args.traces) as store:
                    traces = observe_trace_store(store)
            snapshot = ObservabilitySnapshot(
                registry=observed_registry,
                traces=traces,
            )
            destination = write_dashboard(snapshot, args.output)
            print(destination)
            return 0

    except (OSError, ValueError, KeyError, RuntimeError, SchemaRouterError) as exc:
        print(f"schemarouter: {exc}", file=sys.stderr)
        return 2

    parser.error("unsupported command")
    return 2
