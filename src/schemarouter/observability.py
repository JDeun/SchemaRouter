from __future__ import annotations

from collections import Counter
from dataclasses import asdict
from datetime import datetime
from typing import Any

from pydantic import Field

from .models import StrictModel
from .policy import ExecutionPolicy, is_remote_tool
from .registry import ToolRegistry
from .traces import RunTrace, RunTraceStore


class EndpointObservation(StrictModel):
    name: str
    operation: str
    method: str | None = None
    path: str | None = None
    read_only: bool | None = None
    destructive: bool | None = None
    parameters: list[str]
    required_parameters: list[str]
    output_fields: list[str]
    fingerprint: str


class ToolObservation(StrictModel):
    key: str
    name: str
    namespace: str | None = None
    adapter: str | None = None
    source_type: str | None = None
    license: str | None = None
    remote: bool
    execution_bound: bool
    endpoint_count: int
    fingerprint: str
    endpoints: list[EndpointObservation]


class RegistryObservation(StrictModel):
    registry_version: int
    tool_count: int
    endpoint_count: int
    read_only_endpoints: int
    mutation_endpoints: int
    destructive_endpoints: int
    unclassified_endpoints: int
    adapters: dict[str, int]
    bound_tools: list[str]
    tools: list[ToolObservation]


class PlannerObservation(StrictModel):
    analyzer: str
    decision_backend: str | None = None
    decision_policy: dict[str, Any]


class ExecutionObservation(StrictModel):
    policy: dict[str, Any]


class RouterObservation(StrictModel):
    registry: RegistryObservation
    planner: PlannerObservation
    execution: ExecutionObservation


class TraceObservation(StrictModel):
    run_id: str
    complete: bool
    event_count: int
    started_at: datetime
    ended_at: datetime | None = None
    terminal_event: str | None = None
    tools: list[str]
    error_types: list[str]


class ObservabilitySnapshot(StrictModel):
    registry: RegistryObservation
    planner: PlannerObservation | None = None
    execution: ExecutionObservation | None = None
    traces: list[TraceObservation] = Field(default_factory=list)


def _class_name(value: Any) -> str:
    return type(value).__name__


def observe_registry(
    registry: ToolRegistry,
    *,
    bound_keys: set[str] | frozenset[str] | None = None,
) -> RegistryObservation:
    bound = set(bound_keys or ())
    tools = registry.tools()

    endpoint_count = 0
    read_only_endpoints = 0
    mutation_endpoints = 0
    destructive_endpoints = 0
    unclassified_endpoints = 0
    adapter_counts: Counter[str] = Counter()
    observed_tools: list[ToolObservation] = []

    for tool in tools:
        adapter = tool.metadata.get("adapter")
        adapter_name = str(adapter) if isinstance(adapter, str) and adapter else None
        adapter_counts[adapter_name or "unknown"] += 1

        endpoints: list[EndpointObservation] = []
        for endpoint in tool.endpoints:
            endpoint_count += 1
            if endpoint.destructive is True:
                destructive_endpoints += 1
            if endpoint.read_only is True:
                read_only_endpoints += 1
            elif endpoint.read_only is False:
                mutation_endpoints += 1
            else:
                unclassified_endpoints += 1

            endpoints.append(
                EndpointObservation(
                    name=endpoint.name,
                    operation=f"{tool.key}.{endpoint.name}",
                    method=endpoint.method,
                    path=endpoint.path,
                    read_only=endpoint.read_only,
                    destructive=endpoint.destructive,
                    parameters=[parameter.name for parameter in endpoint.parameters],
                    required_parameters=[
                        parameter.name
                        for parameter in endpoint.parameters
                        if parameter.required
                    ],
                    output_fields=[field.name for field in endpoint.output_fields],
                    fingerprint=endpoint.fingerprint,
                )
            )

        metadata_bound = tool.metadata.get("execution_bound") is True
        observed_tools.append(
            ToolObservation(
                key=tool.key,
                name=tool.name,
                namespace=tool.namespace,
                adapter=adapter_name,
                source_type=tool.source_type,
                license=tool.license,
                remote=is_remote_tool(tool),
                execution_bound=tool.key in bound or metadata_bound,
                endpoint_count=len(endpoints),
                fingerprint=tool.fingerprint,
                endpoints=endpoints,
            )
        )

    return RegistryObservation(
        registry_version=registry.version,
        tool_count=len(observed_tools),
        endpoint_count=endpoint_count,
        read_only_endpoints=read_only_endpoints,
        mutation_endpoints=mutation_endpoints,
        destructive_endpoints=destructive_endpoints,
        unclassified_endpoints=unclassified_endpoints,
        adapters=dict(sorted(adapter_counts.items())),
        bound_tools=sorted(bound),
        tools=observed_tools,
    )


def observe_router(router: Any) -> RouterObservation:
    bound_keys = set(router.executor.bound_keys())
    planner = router.planner
    backend = planner.decision_backend

    policy = router.executor.policy
    execution_policy = asdict(policy) if isinstance(policy, ExecutionPolicy) else {
        "type": _class_name(policy)
    }

    return RouterObservation(
        registry=observe_registry(router.registry, bound_keys=bound_keys),
        planner=PlannerObservation(
            analyzer=_class_name(planner.analyzer),
            decision_backend=_class_name(backend) if backend is not None else None,
            decision_policy=planner.decision_policy.model_dump(mode="json"),
        ),
        execution=ExecutionObservation(policy=execution_policy),
    )


def observe_trace(trace: RunTrace) -> TraceObservation:
    tools = sorted(
        {
            f"{event.tool}.{event.endpoint}"
            for event in trace.events
            if event.tool is not None and event.endpoint is not None
        }
    )
    error_types = sorted(
        {
            str(event.data["error_type"])
            for event in trace.events
            if event.event in {"tool.error", "run.error"}
            and isinstance(event.data.get("error_type"), str)
        }
    )
    terminal = trace.terminal_event
    return TraceObservation(
        run_id=trace.run_id,
        complete=trace.complete,
        event_count=len(trace.events),
        started_at=trace.events[0].timestamp,
        ended_at=terminal.timestamp if terminal is not None else None,
        terminal_event=terminal.event if terminal is not None else None,
        tools=tools,
        error_types=error_types,
    )


def snapshot_router(
    router: Any,
    *,
    traces: list[TraceObservation] | None = None,
) -> ObservabilitySnapshot:
    observed = observe_router(router)
    return ObservabilitySnapshot(
        registry=observed.registry,
        planner=observed.planner,
        execution=observed.execution,
        traces=list(traces or []),
    )


def observe_trace_store(
    store: RunTraceStore,
    *,
    complete: bool | None = None,
) -> list[TraceObservation]:
    return [
        observe_trace(store.trace(run_id))
        for run_id in store.run_ids(complete=complete)
    ]
