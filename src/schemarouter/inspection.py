from __future__ import annotations

import datetime
from dataclasses import asdict
from typing import Any
from pydantic import Field

from ._url_safety import safe_provenance_url
from .models import StrictModel, ToolSpec
from .registry import ToolRegistry
from .traces import RunTrace, RunTraceStore

_EXECUTION_PROVENANCE_KEYS = (
    "adapter",
    "source_url",
    "resolved_schema_url",
    "suggested_base_url",
    "approved_base_url",
    "versioned_base_url",
    "api_version",
    "protocol_version",
    "execution_bound",
    "requires_explicit_base_url",
    "authenticated_transport",
)
_URL_PROVENANCE_KEYS = {
    "approved_base_url",
    "resolved_schema_url",
    "source_url",
    "suggested_base_url",
    "versioned_base_url",
}


def _safe_provenance_value(key: str, value: object) -> object:
    if key not in _URL_PROVENANCE_KEYS or not isinstance(value, str):
        return value
    return safe_provenance_url(value)


_DESCRIPTIVE_PROVENANCE_KEYS = (
    "source_url",
    "resolved_schema_url",
    "suggested_base_url",
    "external_refs_enabled",
    "same_document_refs_normalized",
    "external_ref_documents_resolved",
    "external_ref_bytes_fetched",
    "external_ref_limits",
)


def _provenance(tool: ToolSpec) -> dict[str, object]:
    provenance: dict[str, object] = {
        key: _safe_provenance_value(key, tool.metadata[key])
        for key in _DESCRIPTIVE_PROVENANCE_KEYS
        if key in tool.metadata
    }
    provenance.update(
        {
            key: _safe_provenance_value(key, tool.execution_metadata[key])
            for key in _EXECUTION_PROVENANCE_KEYS
            if key in tool.execution_metadata
        }
    )
    provenance["remote"] = tool.remote
    return provenance


class EndpointInspection(StrictModel):
    """Derived operational view of one registered endpoint."""

    name: str
    method: str | None = None
    path: str | None = None
    read_only: bool | None = None
    destructive: bool | None = None
    parameter_count: int = Field(ge=0)
    required_parameter_count: int = Field(ge=0)
    output_field_count: int = Field(ge=0)
    fingerprint: str


class ToolInspection(StrictModel):
    """Derived operational view of one registered tool."""

    key: str
    name: str
    namespace: str | None = None
    description: str = ""
    source_type: str | None = None
    license: str | None = None
    endpoint_count: int = Field(ge=0)
    fingerprint: str
    provenance: dict[str, object] = Field(default_factory=dict)
    endpoints: list[EndpointInspection] = Field(default_factory=list)


class RegistryInspection(StrictModel):
    """Snapshot summary of a tool registry."""

    version: int = Field(ge=0)
    tool_count: int = Field(ge=0)
    endpoint_count: int = Field(ge=0)
    read_only_endpoints: int = Field(ge=0)
    mutating_endpoints: int = Field(ge=0)
    unclassified_endpoints: int = Field(ge=0)
    tools: list[ToolInspection] = Field(default_factory=list)


class PlannerInspection(StrictModel):
    """Privacy-safe view of the live planner configuration."""

    analyzer: str
    decision_backend: str | None = None
    decision_policy: dict[str, object] = Field(default_factory=dict)


class ExecutionInspection(StrictModel):
    """Privacy-safe view of live execution authority and bindings."""

    policy: dict[str, object] = Field(default_factory=dict)
    bound_tools: list[str] = Field(default_factory=list)


class RouterInspection(StrictModel):
    """Live operational snapshot of one SchemaRouter instance."""

    registry: RegistryInspection
    planner: PlannerInspection
    execution: ExecutionInspection


class TraceInspection(StrictModel):
    """Compact operational summary of one persisted run trace."""

    run_id: str
    complete: bool
    event_count: int = Field(ge=1)
    started_at: datetime.datetime
    ended_at: datetime.datetime | None = None
    terminal_event: str | None = None
    tools: list[str] = Field(default_factory=list)
    endpoints: list[str] = Field(default_factory=list)
    error_count: int = Field(ge=0)


def inspect_tool_spec(tool: ToolSpec) -> ToolInspection:
    endpoints = [
        EndpointInspection(
            name=endpoint.name,
            method=endpoint.method,
            path=endpoint.path,
            read_only=endpoint.read_only,
            destructive=endpoint.destructive,
            parameter_count=len(endpoint.parameters),
            required_parameter_count=sum(
                parameter.required for parameter in endpoint.parameters
            ),
            output_field_count=len(endpoint.output_fields),
            fingerprint=endpoint.fingerprint,
        )
        for endpoint in tool.endpoints
    ]
    return ToolInspection(
        key=tool.key,
        name=tool.name,
        namespace=tool.namespace,
        description=tool.description,
        source_type=tool.source_type,
        license=tool.license,
        endpoint_count=len(endpoints),
        fingerprint=tool.fingerprint,
        provenance=_provenance(tool),
        endpoints=endpoints,
    )


def inspect_registry(registry: ToolRegistry) -> RegistryInspection:
    tools = [inspect_tool_spec(tool) for tool in registry.tools()]
    endpoints = [
        endpoint
        for tool in tools
        for endpoint in tool.endpoints
    ]
    return RegistryInspection(
        version=registry.version,
        tool_count=len(tools),
        endpoint_count=len(endpoints),
        read_only_endpoints=sum(endpoint.read_only is True for endpoint in endpoints),
        mutating_endpoints=sum(endpoint.read_only is False for endpoint in endpoints),
        unclassified_endpoints=sum(endpoint.read_only is None for endpoint in endpoints),
        tools=tools,
    )


def inspect_tool(registry: ToolRegistry, key: str) -> ToolInspection:
    return inspect_tool_spec(registry.get(key))


def inspect_router(router: Any) -> RouterInspection:
    """Inspect a live SchemaRouter without exposing invokers, credentials, or payload values."""

    planner = router.planner
    backend = planner.decision_backend
    return RouterInspection(
        registry=inspect_registry(router.registry),
        planner=PlannerInspection(
            analyzer=type(planner.analyzer).__name__,
            decision_backend=type(backend).__name__ if backend is not None else None,
            decision_policy=planner.decision_policy.model_dump(mode="json"),
        ),
        execution=ExecutionInspection(
            policy=asdict(router.executor.policy),
            bound_tools=list(router.executor.bound_keys()),
        ),
    )


def inspect_run_trace(trace: RunTrace) -> TraceInspection:
    tools: list[str] = []
    endpoints: list[str] = []
    seen_tools: set[str] = set()
    seen_endpoints: set[str] = set()
    error_count = 0

    for event in trace.events:
        if event.tool and event.tool not in seen_tools:
            seen_tools.add(event.tool)
            tools.append(event.tool)
        if event.tool and event.endpoint:
            endpoint_key = f"{event.tool}.{event.endpoint}"
            if endpoint_key not in seen_endpoints:
                seen_endpoints.add(endpoint_key)
                endpoints.append(endpoint_key)
        if event.event in {"tool.error", "run.error"}:
            error_count += 1

    terminal = trace.terminal_event
    return TraceInspection(
        run_id=trace.run_id,
        complete=trace.complete,
        event_count=len(trace.events),
        started_at=trace.events[0].timestamp,
        ended_at=terminal.timestamp if terminal is not None else None,
        terminal_event=terminal.event if terminal is not None else None,
        tools=tools,
        endpoints=endpoints,
        error_count=error_count,
    )


def inspect_trace(store: RunTraceStore, run_id: str) -> TraceInspection:
    return inspect_run_trace(store.trace(run_id))


def inspect_traces(
    store: RunTraceStore,
    *,
    complete: bool | None = None,
) -> tuple[TraceInspection, ...]:
    return tuple(
        inspect_trace(store, run_id)
        for run_id in store.run_ids(complete=complete)
    )


def tool_spec_document(tool: ToolSpec) -> dict[str, object]:
    """Return a safe detached inspection document plus derived fingerprints.

    Arbitrary ToolSpec/EndpointSpec metadata is intentionally omitted. Only the allowlisted
    ingestion provenance above is surfaced at tool level.
    """

    return {
        "key": tool.key,
        "name": tool.name,
        "namespace": tool.namespace,
        "description": tool.description,
        "source_type": tool.source_type,
        "license": tool.license,
        "fingerprint": tool.fingerprint,
        "provenance": _provenance(tool),
        "endpoints": [
            {
                "name": endpoint.name,
                "description": endpoint.description,
                "method": endpoint.method,
                "path": endpoint.path,
                "read_only": endpoint.read_only,
                "destructive": endpoint.destructive,
                "parameters": [
                    parameter.model_dump(mode="json")
                    for parameter in endpoint.parameters
                ],
                "output_fields": [
                    field.model_dump(mode="json")
                    for field in endpoint.output_fields
                ],
                "input_schema": endpoint.input_schema,
                "output_schema": endpoint.output_schema,
                "fingerprint": endpoint.fingerprint,
            }
            for endpoint in tool.endpoints
        ],
    }
