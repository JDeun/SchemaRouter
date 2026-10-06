from __future__ import annotations

import argparse
import asyncio
import json
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from ._document_loading import read_bounded_text
from .capability_artifact import (
    migrate_capability_artifact,
    serialize_capability_artifact,
)
from .capability_decision_trace import (
    CapabilityDecisionTrace,
    render_capability_decision_trace,
)
from .capability_snapshot import (
    migrate_capability_snapshot,
    serialize_capability_snapshot,
)
from .dashboard import write_dashboard
from .errors import (
    SchemaSourceError,
    SourceProbeDiagnosticError,
    StorageFormatError,
    UnsupportedSchemaSourceError,
)
from .explorer import (
    build_capability_explorer_document,
    write_schema_explorer,
)
from .ingestion import (
    SourceProbeFailureReport,
    SourceProbeResult,
    default_adapter_registry,
)
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
from .runtime import SchemaRouter
from .schema_diff import SchemaDiffReport, compare_endpoint_specs, compare_tool_specs
from .storage import (
    StorageInspection,
    StorageMigrationResult,
    inspect_sqlite_storage,
    migrate_sqlite_storage,
)
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
            auth = (
                "public"
                if not endpoint.auth_required
                else "auth=" + ",".join(endpoint.auth_kinds or ["unknown"])
            )
            lines.append(
                f"  - {endpoint.name}: {method} {path} · {mode}{destructive} · {auth} · "
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
            "authentication: "
            + (
                "public"
                if not endpoint.auth_required
                else "required ("
                + ", ".join(endpoint.auth_kinds or ["unknown"])
                + ")"
            )
        )
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


def _render_schema_diff(
    report: SchemaDiffReport,
    *,
    label: str,
) -> str:
    lines = [
        f"Schema diff {label}",
        f"compatibility: {report.compatibility}",
        (
            "fingerprint: "
            f"{_short_fingerprint(report.old_fingerprint)} -> "
            f"{_short_fingerprint(report.new_fingerprint)}"
        ),
        f"changes: {len(report.changes)}",
    ]
    for change in report.changes:
        detail = f"{change.severity} {change.path}: {change.kind}"
        if change.message:
            detail += f" · {change.message}"
        lines.append(f"- {detail}")
    return "\n".join(lines)


def _render_source_probe(probe: SourceProbeResult) -> str:
    lines = [
        f"Structured source: {probe.source_url}",
        f"adapter: {probe.adapter_kind}",
        f"probe activity: {probe.probe_activity or '-'}",
        f"tool: {probe.tool_key}",
        f"provider: {probe.provider or '-'}",
        f"access_mode: {probe.access_mode or '-'}",
        f"endpoints: {probe.endpoint_count}",
        f"execution binding: {'available' if probe.execution_bindable else 'not available'}",
    ]
    if probe.adapters_considered:
        lines.append("adapters considered:")
        lines.extend(
            (
                f"  - {item.adapter_kind} ({item.activity}): "
                f"{item.outcome}"
            )
            for item in probe.adapters_considered
        )
    if probe.warnings:
        lines.append("warnings:")
        lines.extend(f"  - {warning}" for warning in probe.warnings)
    else:
        lines.append("warnings: none")
    return "\n".join(lines)


def _render_source_probe_failure(report: SourceProbeFailureReport) -> str:
    lines = [
        f"Structured source probe failed: {report.source_url}",
        f"failure category: {report.failure_category}",
    ]
    if report.adapters_considered:
        lines.append("adapters considered:")
        for item in report.adapters_considered:
            detail = (
                f"  - {item.adapter_kind} ({item.activity}): "
                f"{item.outcome}"
            )
            if item.error_type:
                detail += f" [{item.error_type}]"
            lines.append(detail)
    if report.skipped_active_adapters:
        lines.append(
            "active adapters skipped: "
            + ", ".join(report.skipped_active_adapters)
        )
    return "\n".join(lines)


def _render_decision_trace(document: dict[str, object]) -> str:
    lines = [
        f"Capability decision trace {document['trace_id']}",
        f"snapshot: {document.get('snapshot_id') or '-'}",
        (
            "registry_version: "
            + (
                str(document.get("registry_version"))
                if document.get("registry_version") is not None
                else "-"
            )
        ),
    ]
    candidates = document.get("candidates")
    if not isinstance(candidates, list) or not candidates:
        lines.append("candidates: none")
        return "\n".join(lines)
    lines.append("candidates:")
    for candidate in candidates:
        if not isinstance(candidate, dict):
            continue
        reason_items = candidate.get("reasons")
        reason_codes = []
        if isinstance(reason_items, list):
            reason_codes = [
                str(item.get("code"))
                for item in reason_items
                if isinstance(item, dict) and item.get("code")
            ]
        lines.append(
            "  - "
            + str(candidate.get("capability_id"))
            + ": "
            + str(candidate.get("final_disposition"))
            + (
                " [" + ", ".join(reason_codes) + "]"
                if reason_codes
                else ""
            )
        )
    return "\n".join(lines)


def _render_storage_inspection(snapshot: StorageInspection) -> str:
    lines = [f"SQLite storage: {snapshot.path}"]
    if not snapshot.components:
        lines.append("components: none")
        return "\n".join(lines)

    for component in snapshot.components:
        storage_version = (
            str(component.storage_format_version)
            if component.storage_format_version is not None
            else "legacy-v0"
        )
        document_version = (
            str(component.document_format_version)
            if component.document_format_version is not None
            else "legacy-v0"
        )
        lines.append(
            f"- {component.component}: {component.status}; "
            f"storage={storage_version}/"
            f"{component.current_storage_format_version}, "
            f"document={document_version}/"
            f"{component.current_document_format_version}, "
            f"documents={component.document_count}"
        )
        if component.migrations:
            lines.append("  migrations:")
            lines.extend(
                (
                    f"    - {item.from_version} -> {item.to_version} "
                    f"at {item.applied_at}"
                )
                for item in component.migrations
            )
    lines.append(
        "migration required: "
        + ("yes" if snapshot.migration_required else "no")
    )
    return "\n".join(lines)


def _render_storage_migration(result: StorageMigrationResult) -> str:
    lines = [
        f"SQLite storage migration: {result.path}",
        (
            f"backup: {result.backup_path}"
            if result.backup_path is not None
            else "backup: not created"
        ),
        "before:",
    ]
    lines.extend(
        f"  - {item.component}: {item.status}"
        for item in result.before.components
    )
    lines.append("after:")
    lines.extend(
        f"  - {item.component}: {item.status}"
        for item in result.after.components
    )
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


def _existing_document(path: Path) -> Path:
    if not path.exists():
        raise FileNotFoundError(f"document does not exist: {path}")
    if not path.is_file():
        raise ValueError(f"document path is not a file: {path}")
    return path


def _migration_destination(
    source: Path,
    output: Path | None,
    *,
    overwrite: bool,
) -> Path:
    destination = output or source.with_name(source.name + ".migrated.json")
    if destination == source and not overwrite:
        raise ValueError("refusing to overwrite source document without --overwrite")
    if destination.exists() and not overwrite:
        raise FileExistsError(
            f"migration destination already exists: {destination}; use --overwrite"
        )
    destination.parent.mkdir(parents=True, exist_ok=True)
    return destination


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

    decision_trace = inspect_subparsers.add_parser(
        "decision-trace",
        help="Inspect a serialized privacy-safe capability decision trace.",
    )
    decision_trace.add_argument("document", type=Path)
    decision_trace.add_argument(
        "--detailed",
        action="store_true",
        help="Include structured component results in addition to compact reasons.",
    )
    _add_json_flag(decision_trace)

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

    diff = inspect_subparsers.add_parser(
        "diff",
        help="Compare one tool or endpoint across two persisted SQLite registries.",
    )
    diff.add_argument("key", help="Registry tool key, including namespace when present.")
    diff.add_argument("--old-db", required=True, type=Path, help="Previous SQLite registry path.")
    diff.add_argument("--new-db", required=True, type=Path, help="Current SQLite registry path.")
    diff.add_argument(
        "--endpoint",
        default=None,
        help="Optional endpoint name. Omit to compare the complete ToolSpec.",
    )
    _add_json_flag(diff)

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

    source = subparsers.add_parser(
        "source",
        help="Diagnose structured source URLs without registering or executing tools.",
    )
    source_subparsers = source.add_subparsers(dest="surface", required=True)
    source_probe = source_subparsers.add_parser(
        "probe",
        help="Probe a URL with the same bounded structured-source adapters used by ingestion.",
    )
    source_probe.add_argument("url", help="Absolute http(s) structured-source URL.")
    source_probe.add_argument(
        "--kind",
        default="auto",
        choices=("auto", *default_adapter_registry().kinds()),
        help="Structured source kind. Defaults to bounded automatic detection.",
    )
    source_probe.add_argument("--name", default=None, help="Optional tool name override.")
    source_probe.add_argument(
        "--namespace",
        default=None,
        help="Optional tool namespace override.",
    )
    source_probe.add_argument(
        "--provider",
        default=None,
        help="Optional provider identity override.",
    )
    source_probe.add_argument(
        "--base-url",
        default=None,
        help="Optional trusted execution base URL for adapters that require one.",
    )
    source_probe.add_argument(
        "--allow-active-probes",
        action="store_true",
        help=(
            "Opt into active auto-discovery such as GraphQL POST introspection "
            "and MCP protocol handshakes. Explicit --kind does not require this flag."
        ),
    )
    source_probe.add_argument(
        "--timeout",
        type=float,
        default=20.0,
        help="Bounded source probe timeout in seconds.",
    )
    _add_json_flag(source_probe)

    storage = subparsers.add_parser(
        "storage",
        help="Inspect or migrate versioned SchemaRouter SQLite storage.",
    )
    storage_subparsers = storage.add_subparsers(
        dest="surface",
        required=True,
    )

    storage_inspect = storage_subparsers.add_parser(
        "inspect",
        help="Inspect SQLite storage/document format versions without mutating the database.",
    )
    storage_inspect.add_argument(
        "db",
        type=Path,
        help="SchemaRouter SQLite database path.",
    )
    _add_json_flag(storage_inspect)

    storage_migrate = storage_subparsers.add_parser(
        "migrate",
        help="Migrate supported legacy SQLite formats after a full preflight.",
    )
    storage_migrate.add_argument(
        "db",
        type=Path,
        help="SchemaRouter SQLite database path.",
    )
    storage_migrate.add_argument(
        "--backup-path",
        type=Path,
        default=None,
        help=(
            "Optional explicit backup destination. By default a "
            ".schemarouter.bak file is created beside the database."
        ),
    )
    storage_migrate.add_argument(
        "--no-backup",
        action="store_true",
        help="Explicitly disable the pre-migration SQLite backup.",
    )
    _add_json_flag(storage_migrate)

    artifact = subparsers.add_parser(
        "artifact",
        help="Inspect or migrate portable capability graph artifacts.",
    )
    artifact_subparsers = artifact.add_subparsers(dest="surface", required=True)
    artifact_inspect = artifact_subparsers.add_parser(
        "inspect",
        help="Validate and inspect a capability graph artifact without rewriting it.",
    )
    artifact_inspect.add_argument("document", type=Path)
    _add_json_flag(artifact_inspect)
    artifact_migrate = artifact_subparsers.add_parser(
        "migrate",
        help="Migrate a supported older capability graph artifact to the current format.",
    )
    artifact_migrate.add_argument("document", type=Path)
    artifact_migrate.add_argument("--output", type=Path, default=None)
    artifact_migrate.add_argument("--overwrite", action="store_true")
    _add_json_flag(artifact_migrate)

    snapshot = subparsers.add_parser(
        "snapshot",
        help="Inspect or migrate capability snapshot documents.",
    )
    snapshot_subparsers = snapshot.add_subparsers(dest="surface", required=True)
    snapshot_inspect = snapshot_subparsers.add_parser(
        "inspect",
        help="Validate and inspect a capability snapshot document.",
    )
    snapshot_inspect.add_argument("document", type=Path)
    _add_json_flag(snapshot_inspect)
    snapshot_migrate = snapshot_subparsers.add_parser(
        "migrate",
        help="Wrap/migrate a supported older capability snapshot representation.",
    )
    snapshot_migrate.add_argument("document", type=Path)
    snapshot_migrate.add_argument("--output", type=Path, default=None)
    snapshot_migrate.add_argument("--overwrite", action="store_true")
    _add_json_flag(snapshot_migrate)

    explorer = subparsers.add_parser(
        "explorer",
        help="Export a self-contained Swagger-style capability explorer.",
    )
    explorer.add_argument(
        "--registry",
        required=True,
        type=Path,
        help="SQLite registry path.",
    )
    explorer.add_argument(
        "--output",
        required=True,
        type=Path,
        help="Destination HTML path.",
    )

    dashboard = subparsers.add_parser(
        "dashboard",
        help="Export a self-contained read-only HTML inspection dashboard.",
    )
    dashboard.add_argument(
        "--registry",
        required=True,
        type=Path,
        help="SQLite registry path.",
    )
    dashboard.add_argument(
        "--traces",
        type=Path,
        default=None,
        help="Optional SQLite trace-store path.",
    )
    dashboard.add_argument(
        "--output",
        required=True,
        type=Path,
        help="Destination HTML path.",
    )

    return parser


def _run(args: argparse.Namespace) -> str:
    if args.command == "source":
        if args.surface != "probe":
            raise ValueError(f"unsupported source surface: {args.surface}")
        router = SchemaRouter()
        probe = asyncio.run(
            router.probe_url(
                args.url,
                kind=args.kind,
                name=args.name,
                namespace=args.namespace,
                provider=args.provider,
                base_url=args.base_url,
                allow_active_probes=args.allow_active_probes,
                timeout=args.timeout,
            )
        )
        return _json_dump(probe) if args.json else _render_source_probe(probe)

    if args.command == "storage":
        database = _existing_db(args.db)
        if args.surface == "inspect":
            snapshot = inspect_sqlite_storage(database)
            return (
                _json_dump(snapshot)
                if args.json
                else _render_storage_inspection(snapshot)
            )
        if args.surface == "migrate":
            result = migrate_sqlite_storage(
                database,
                backup=not args.no_backup,
                backup_path=args.backup_path,
            )
            return (
                _json_dump(result)
                if args.json
                else _render_storage_migration(result)
            )
        raise ValueError(f"unsupported storage surface: {args.surface}")

    if args.command == "artifact":
        source = _existing_document(args.document)
        result = migrate_capability_artifact(
            read_bounded_text(source, label="capability artifact document")
        )
        inspection = {
            "kind": "capability_artifact",
            "source": str(source),
            "from_format": result.migration.from_format,
            "current_format": result.migration.to_format,
            "migration_required": result.migration.migrated,
            "source_digest": result.migration.source_digest,
            "result_digest": result.migration.result_digest,
            "capabilities": len(result.artifact.capabilities),
            "sources": len(result.artifact.sources),
            "edges": len(result.artifact.edges),
        }
        if args.surface == "inspect":
            return _json_dump(inspection)
        if args.surface == "migrate":
            destination = _migration_destination(
                source,
                args.output,
                overwrite=args.overwrite,
            )
            destination.write_text(
                serialize_capability_artifact(result.artifact) + "\n",
                encoding="utf-8",
            )
            inspection["output"] = str(destination)
            return _json_dump(inspection)
        raise ValueError(f"unsupported artifact surface: {args.surface}")

    if args.command == "snapshot":
        source = _existing_document(args.document)
        result = migrate_capability_snapshot(
            read_bounded_text(source, label="capability snapshot document")
        )
        inspection = {
            "kind": "capability_snapshot",
            "source": str(source),
            "from_format": result.migration.from_format,
            "current_format": result.migration.to_format,
            "migration_required": result.migration.migrated,
            "source_digest": result.migration.source_digest,
            "result_digest": result.migration.result_digest,
            "snapshot_id": result.document.snapshot.snapshot_id,
            "capabilities": len(result.document.snapshot.contracts),
            "sources": len(result.document.snapshot.sources),
        }
        if args.surface == "inspect":
            return _json_dump(inspection)
        if args.surface == "migrate":
            destination = _migration_destination(
                source,
                args.output,
                overwrite=args.overwrite,
            )
            destination.write_text(
                serialize_capability_snapshot(result.document) + "\n",
                encoding="utf-8",
            )
            inspection["output"] = str(destination)
            return _json_dump(inspection)
        raise ValueError(f"unsupported snapshot surface: {args.surface}")

    if args.command == "explorer":
        with SQLiteRegistry(_existing_db(args.registry)) as registry:
            document = build_capability_explorer_document(registry)
        destination = write_schema_explorer(
            document,
            args.output,
        )
        return str(destination)

    if args.command == "dashboard":
        with SQLiteRegistry(_existing_db(args.registry)) as registry:
            snapshot = inspect_registry(registry)
        traces: Sequence[TraceInspection] = ()
        if args.traces is not None:
            with SQLiteRunTraceStore(_existing_db(args.traces)) as store:
                traces = inspect_traces(store)
        destination = write_dashboard(
            snapshot,
            args.output,
            traces=traces,
        )
        return str(destination)

    if args.command != "inspect":
        raise ValueError(f"unsupported command: {args.command}")

    if args.surface == "decision-trace":
        source = _existing_document(args.document)
        trace = CapabilityDecisionTrace.model_validate_json(
            source.read_text(encoding="utf-8")
        )
        document = render_capability_decision_trace(
            trace,
            detailed=args.detailed,
        )
        return _json_dump(document) if args.json else _render_decision_trace(document)

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

    if args.surface == "diff":
        with SQLiteRegistry(_existing_db(args.old_db)) as old_registry:
            old_tool = old_registry.get(args.key)
        with SQLiteRegistry(_existing_db(args.new_db)) as new_registry:
            new_tool = new_registry.get(args.key)

        if args.endpoint is not None:
            report = compare_endpoint_specs(
                old_tool.endpoint(args.endpoint),
                new_tool.endpoint(args.endpoint),
            )
            label = f"{args.key}.{args.endpoint}"
        else:
            report = compare_tool_specs(old_tool, new_tool)
            label = args.key
        return _json_dump(report) if args.json else _render_schema_diff(report, label=label)

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
    except UnsupportedSchemaSourceError as exc:
        if args.command == "source":
            report = getattr(exc, "probe_report", None)
            if args.json and isinstance(report, SourceProbeFailureReport):
                parser.exit(2, _json_dump(report) + "\n")
            supported = ", ".join(default_adapter_registry().kinds())
            diagnostic = (
                _render_source_probe_failure(report) + "\n"
                if isinstance(report, SourceProbeFailureReport)
                else ""
            )
            parser.exit(
                2,
                (
                    diagnostic
                    + "schemarouter: source is not a supported structured source. "
                    + f"{exc}\n"
                    + f"supported source kinds: {supported}\n"
                    + "A normal HTML website is not auto-converted into an executable tool. "
                    + "For human-readable API documentation, use SchemaRouter.inspect_url() "
                    + "followed by explicit proposal approval; for a trusted manual contract, "
                    + "use SchemaRouter.add_http_tool().\n"
                ),
            )
        parser.exit(2, f"schemarouter: {type(exc).__name__}: {exc}\n")
    except SourceProbeDiagnosticError as exc:
        if args.command == "source":
            report = getattr(exc, "probe_report", None)
            if isinstance(report, SourceProbeFailureReport):
                output = (
                    _json_dump(report)
                    if args.json
                    else _render_source_probe_failure(report)
                )
                parser.exit(2, output + "\n")
        parser.exit(2, f"schemarouter: {type(exc).__name__}: {exc}\n")
    except (
        KeyError,
        OSError,
        ValueError,
        RuntimeError,
        SchemaSourceError,
        StorageFormatError,
    ) as exc:
        parser.exit(2, f"schemarouter: {type(exc).__name__}: {exc}\n")
    sys.stdout.write(output + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
