from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Awaitable, Callable, Iterator, Mapping, Sequence
from contextlib import nullcontext
from typing import Any, TypeVar
from urllib.parse import urlparse
from uuid import uuid4

import httpx
from pydantic import TypeAdapter

from ._loop_affinity import SyncLoopRunner
from .adapters.base import AdapterRegistry, SourceAdapter
from .adapters.mcp import (
    MCPBoundClientFactory,
    MCPBoundInvoker,
    MCPClientFactory,
    MCPDiscoveryLimits,
    MCPStdioClientFactory,
    MCPStdioConfig,
    inspect_mcp_client_factory,
    inspect_mcp_stdio,
)
from .adapters.openapi import OpenAPIRemoteInvoker
from .adapters.plugins import load_adapter_plugins as _load_adapter_plugins
from .adapters.python import PythonCallableInvoker, callable_options, tool_from_callable
from .adaptive_context import (
    SessionSchemaExposure,
    SuccessfulCapabilityHistory,
    apply_success_prior,
    filter_unexposed_schemas,
)
from .amendment_overlay import (
    amendment_overlay,
    prepare_amended_capability,
    reapply_amendment_overlay,
    strip_amendment_overlay,
)
from .authorization import (
    AuthorizationPolicy,
    PrincipalContext,
    _current_principal_context,
    _principal_execution_context,
)
from .authorization_audit import (
    AuthorizationAuditDeliveryMode,
    AuthorizationAuditDeliveryMonitor,
    AuthorizationAuditDeliveryStatus,
    AuthorizationAuditEvent,
    AuthorizationAuditHook,
    AuthorizationAuditPhase,
)
from .binding_reconciliation import (
    BindingReconciliationError,
    BindingReconciliationItem,
    BindingReconciliationReport,
    BindingResolver,
    TrustedBindingConfig,
)
from .capability_contracts import CapabilityFieldContract, CapabilityPrecondition
from .capability_decision_trace import CapabilityDecisionTrace
from .errors import (
    AuthorizationAuditDeliveryError,
    BindingDriftError,
    ContractAmendmentError,
    ExecutionInvariantError,
    InvocationUnavailableError,
    PolicyViolationError,
    PostInvocationHookError,
    ProposalApprovalError,
    RegistrationError,
    SchemaNotModifiedError,
    SchemaSourceError,
    TracePersistenceError,
)
from .execution_state import TypedExecutionState
from .executor import BoundEndpointInvoker, ExecutionBudgetTracker, RegistryExecutor
from .health import AccessHealthMonitor, HealthProbe, HealthProbeSnapshot
from .hooks import ExecutionHooks
from .ingestion import SourceKind, SourceProbeResult, URLSchemaLoader
from .inspection import RouterInspection, inspect_router
from .models import (
    CapabilityRetrieval,
    CapabilityRouteRetrieval,
    EndpointSpec,
    ExecutionPlan,
    PlanRequest,
    ToolCall,
    ToolResult,
    ToolSpec,
)
from .native_schema_lifecycle import (
    NativeSchemaLifecycleManager,
    NativeSchemaWatchSnapshot,
)
from .network_policy import NetworkPolicy
from .planner import QueryAnalyzer, SchemaPlanner
from .policy import ApprovalCallback, ExecutionPolicy
from .proposals import DocumentationModelCallable, SchemaProposal, inspect_documentation_url
from .provider_profiles import (
    ProviderDiscoveryBackend,
    ProviderDiscoveryCandidate,
    ProviderDiscoveryProposal,
    ProviderMethodRegistration,
    ProviderProfile,
    ProviderProfileRegistry,
    ProviderRegistrationResult,
    ProviderResolution,
    built_in_provider_profile_registry,
)
from .provider_profiles import (
    load_provider_profile_plugins as _load_provider_profile_plugins,
)
from .rebinding import (
    RebindingContext,
    persisted_adapter,
)
from .rebinding import (
    build_existing_invoker as build_persisted_invoker,
)
from .registry import (
    InMemoryRegistry,
    ToolRegistry,
    replace_if_current,
    restore_many_if_current,
    unregister_if_current,
    update_many_if_current,
)
from .runs import RunConfig, RunEvent
from .runtime_defaults import RUNTIME_DEFAULTS
from .schema_diff import (
    SchemaChange,
    SchemaDiffReport,
    SchemaRefreshResult,
    compare_tool_specs,
)
from .schema_watch import SchemaWatchManager, SchemaWatchSnapshot
from .source_identity import (
    StructuredSourceIdentity,
    structured_source_identity,
    structured_source_identity_digest_for,
)
from .state_retrieval import (
    StateAwareCapabilityRetrieval,
    StateConditionedCapabilityRetrieval,
    backfill_ranked_candidates_by_state,
    filter_retrieval_by_state,
)
from .trace_redaction import TraceRedactor
from .traces import RunTraceStore, append_run_event_async
from .validation import projected_output_schema

_T = TypeVar("_T")
_SYNC_LOOP_RUNNER = SyncLoopRunner()


def _require_execution_event_exception(
    payload: Any,
    *,
    event_kind: str,
    expected_type: type[Exception] = Exception,
) -> Exception:
    if not isinstance(payload, expected_type):
        raise ExecutionInvariantError(
            "parallel execution event payload violated the internal contract: "
            f"{event_kind!r} expected {expected_type.__name__}, "
            f"got {type(payload).__name__}"
        )
    return payload


def _require_unavailable_event_payload(
    payload: Any,
) -> tuple[InvocationUnavailableError, ToolCall | None, int]:
    if not isinstance(payload, tuple) or len(payload) != 3:
        raise ExecutionInvariantError(
            "parallel execution event payload violated the internal contract: "
            "'unavailable' expected a 3-item tuple"
        )

    exc, next_call, candidate_index = payload
    if not isinstance(exc, InvocationUnavailableError):
        raise ExecutionInvariantError(
            "parallel execution event payload violated the internal contract: "
            "'unavailable' expected InvocationUnavailableError, "
            f"got {type(exc).__name__}"
        )
    if next_call is not None and not isinstance(next_call, ToolCall):
        raise ExecutionInvariantError(
            "parallel execution event payload violated the internal contract: "
            "'unavailable' expected ToolCall or None for next_call, "
            f"got {type(next_call).__name__}"
        )
    if (
        isinstance(candidate_index, bool)
        or not isinstance(candidate_index, int)
        or candidate_index < 0
    ):
        raise ExecutionInvariantError(
            "parallel execution event payload violated the internal contract: "
            "'unavailable' expected a non-negative integer candidate index"
        )
    return exc, next_call, candidate_index


def _coerce_config(config: RunConfig | dict[str, Any] | None) -> RunConfig:
    if config is None:
        return RunConfig()
    if isinstance(config, RunConfig):
        return config
    return RunConfig.model_validate(config)


def _coerce_run_config(config: RunConfig | dict[str, Any] | None) -> RunConfig:
    run_config = _coerce_config(config)
    if run_config.run_id is not None:
        return run_config
    return run_config.model_copy(update={"run_id": uuid4().hex})


def _run_sync(factory: Callable[[], Awaitable[_T]]) -> _T:
    return _SYNC_LOOP_RUNNER.run(factory)


def _stream_sync(factory: Callable[[], AsyncIterator[_T]]) -> Iterator[_T]:
    yield from _SYNC_LOOP_RUNNER.stream(factory)


class SchemaRouter:
    """High-level facade for schema-aware planning and execution."""

    def __init__(
        self,
        *,
        analyzer: QueryAnalyzer | None = None,
        http_client: httpx.AsyncClient | None = None,
        policy: ExecutionPolicy | None = None,
        authorization_policy: AuthorizationPolicy | None = None,
        authorization_audit_hook: AuthorizationAuditHook | None = None,
        authorization_audit_delivery_mode: AuthorizationAuditDeliveryMode = "best_effort",
        approval_callback: ApprovalCallback | None = None,
        execution_hooks: ExecutionHooks | None = None,
        registry: ToolRegistry | None = None,
        adapter_registry: AdapterRegistry | None = None,
        network_policy: NetworkPolicy | None = None,
        structural_retrieval: bool = False,
        unavailable_cooldown_seconds: float = 30.0,
    ) -> None:
        self.registry = registry if registry is not None else InMemoryRegistry()
        self.authorization_policy = authorization_policy
        self.authorization_audit_hook = authorization_audit_hook
        self._authorization_audit_delivery = AuthorizationAuditDeliveryMonitor(
            mode=authorization_audit_delivery_mode,
            sink_configured=authorization_audit_hook is not None,
        )
        self.authorization_audit_delivery_mode = authorization_audit_delivery_mode
        if (
            authorization_audit_delivery_mode == "strict"
            and authorization_audit_hook is None
        ):
            raise ValueError(
                "strict authorization audit delivery requires "
                "authorization_audit_hook"
            )
        self.executor = RegistryExecutor(
            self.registry,
            policy=policy,
            authorization_policy=authorization_policy,
            approval_callback=approval_callback,
            hooks=execution_hooks,
            unavailable_cooldown_seconds=unavailable_cooldown_seconds,
        )
        self.planner = SchemaPlanner(
            self.registry,
            analyzer=analyzer,
            structural_retrieval=structural_retrieval,
            availability_predicate=self._is_snapshot_access_available,
        )
        self.health_monitor = AccessHealthMonitor(self.executor)
        self.loader = URLSchemaLoader(
            self.registry,
            self.executor,
            http_client=http_client,
            adapters=adapter_registry,
            network_policy=network_policy,
        )
        self.schema_watcher = SchemaWatchManager(
            self.registry,
            self.arefresh_schema,
            self.loader.adapters,
        )
        self.provider_profiles = built_in_provider_profile_registry()
        self._native_schema_lifecycle = NativeSchemaLifecycleManager(
            self.registry,
            self._apply_native_schema_binding,
        )
    def _is_snapshot_access_available(self, tool: ToolSpec, endpoint: Any) -> bool:
        return self.executor.is_access_available_for_contract(
            tool.key,
            endpoint.name,
            self.planner._snapshot_tool_fingerprint(tool),
        )

    def _authorization_predicate(
        self,
        principal: PrincipalContext | None,
    ) -> Callable[[ToolSpec, Any], bool] | None:
        policy = self.authorization_policy
        if policy is None:
            return None
        if principal is None:
            raise PolicyViolationError(
                "principal context is required when authorization_policy is configured"
            )
        return lambda tool, endpoint: policy.visible(
            principal,
            tool,
            endpoint,
        )

    def _data_scope_endpoint_view(
        self,
        principal: PrincipalContext,
        tool: ToolSpec,
        endpoint: EndpointSpec,
    ) -> EndpointSpec | None:
        policy = self.authorization_policy
        if policy is None or not policy.data_rules:
            return endpoint
        scope = policy.data_scope(principal, tool, endpoint)
        if scope.visible_fields is None:
            return endpoint

        visible_fields = [
            field.model_copy(deep=True)
            for field in endpoint.output_fields
            if field.name in scope.visible_fields
        ]
        if endpoint.output_fields and not visible_fields:
            return None

        hidden_field_names = {
            field.name
            for field in endpoint.output_fields
            if field.name not in scope.visible_fields
        }
        parameters = []
        for parameter in endpoint.parameters:
            mapped_field = (
                parameter.name.split("filter__", 1)[1]
                if parameter.name.startswith("filter__")
                else parameter.name
            )
            if mapped_field in hidden_field_names:
                continue
            clone = parameter.model_copy(deep=True)
            if (
                parameter.name == "relationship_types"
                and scope.allowed_relationships is not None
            ):
                schema = dict(clone.json_schema)
                items = dict(schema.get("items", {}))
                items["enum"] = sorted(scope.allowed_relationships)
                schema["items"] = items
                clone.json_schema = schema
            if parameter.name == "max_hops" and scope.max_hops is not None:
                schema = dict(clone.json_schema)
                current_max = schema.get("maximum")
                schema["maximum"] = (
                    scope.max_hops
                    if current_max is None
                    else min(int(current_max), scope.max_hops)
                )
                clone.json_schema = schema
            parameters.append(clone)

        selected_names = [field.name for field in visible_fields]
        server_projection = endpoint.server_projection
        if server_projection is not None:
            server_projection = server_projection.model_copy(
                deep=True,
                update={
                    "field_map": {
                        name: selector
                        for name, selector in server_projection.field_map.items()
                        if name in selected_names
                    }
                },
            )
        return endpoint.model_copy(
            deep=True,
            update={
                "parameters": parameters,
                "output_fields": visible_fields,
                "output_schema": projected_output_schema(
                    endpoint,
                    selected_names,
                ),
                "server_projection": server_projection,
            },
        )

    def _scoped_analysis_registry(
        self,
        principal: PrincipalContext,
        predicate: Callable[[ToolSpec, Any], bool],
    ) -> ToolRegistry:
        """Build the authorization-bounded schema catalog supplied to analyzers."""

        scoped = InMemoryRegistry()
        for tool in self.registry.tools():
            endpoints: list[EndpointSpec] = []
            for endpoint in tool.endpoints:
                if not predicate(tool, endpoint):
                    continue
                visible_endpoint = self._data_scope_endpoint_view(
                    principal,
                    tool,
                    endpoint,
                )
                if visible_endpoint is not None:
                    endpoints.append(visible_endpoint)
            if not endpoints:
                continue
            scoped.register(
                tool.model_copy(
                    deep=True,
                    update={"endpoints": endpoints},
                )
            )
        return scoped

    def _project_retrieval_data_scope(
        self,
        retrieval: CapabilityRetrieval,
        principal: PrincipalContext | None,
    ) -> CapabilityRetrieval:
        policy = self.authorization_policy
        if policy is None or not policy.data_rules:
            return retrieval
        if principal is None:
            raise PolicyViolationError(
                "principal context is required when authorization_policy is configured"
            )

        projected_candidates = []
        for candidate in retrieval.candidates:
            tool = self.registry.get(candidate.tool)
            endpoint = tool.endpoint(candidate.endpoint)
            scope = policy.data_scope(principal, tool, endpoint)
            if scope.visible_fields is None:
                projected_candidates.append(candidate)
                continue

            visible_fields = [
                field
                for field in endpoint.output_fields
                if field.name in scope.visible_fields
            ]
            if endpoint.output_fields and not visible_fields:
                continue

            visible_names: set[str] = set()
            for field in visible_fields:
                visible_names.add(field.name.casefold())
                if field.semantic_id:
                    visible_names.add(field.semantic_id.casefold())
                visible_names.update(alias.casefold() for alias in field.aliases)

            hidden_field_names = {
                field.name
                for field in endpoint.output_fields
                if field.name not in scope.visible_fields
            }
            parameters = []
            for parameter in candidate.parameters:
                mapped_field = (
                    parameter.name.split("filter__", 1)[1]
                    if parameter.name.startswith("filter__")
                    else parameter.name
                )
                if mapped_field in hidden_field_names:
                    continue
                clone = parameter.model_copy(deep=True)
                if (
                    parameter.name == "relationship_types"
                    and scope.allowed_relationships is not None
                ):
                    schema = dict(clone.json_schema)
                    items = dict(schema.get("items", {}))
                    items["enum"] = sorted(scope.allowed_relationships)
                    schema["items"] = items
                    clone.json_schema = schema
                if parameter.name == "max_hops" and scope.max_hops is not None:
                    schema = dict(clone.json_schema)
                    current_max = schema.get("maximum")
                    schema["maximum"] = (
                        scope.max_hops
                        if current_max is None
                        else min(int(current_max), scope.max_hops)
                    )
                    clone.json_schema = schema
                parameters.append(clone)

            input_schema = dict(candidate.input_schema)
            properties = dict(input_schema.get("properties", {}))
            allowed_parameter_names = {parameter.name for parameter in parameters}
            if properties:
                input_schema["properties"] = {
                    name: value
                    for name, value in properties.items()
                    if name in allowed_parameter_names
                }
            if isinstance(input_schema.get("required"), list):
                input_schema["required"] = [
                    name
                    for name in input_schema["required"]
                    if name in allowed_parameter_names
                ]

            selected_names = [field.name for field in visible_fields]
            matched_fields = [
                value
                for value in candidate.matched_fields
                if value.casefold() in visible_names
            ]
            score_components = [
                component
                for component in candidate.score_components
                if component.matched is None
                or component.matched.casefold() in visible_names
                or component.matched.casefold()
                not in {field.name.casefold() for field in endpoint.output_fields}
            ]
            projected_candidates.append(
                candidate.model_copy(
                    deep=True,
                    update={
                        "parameters": parameters,
                        "input_schema": input_schema,
                        "output_fields": [
                            field.model_copy(deep=True)
                            for field in visible_fields
                        ],
                        "output_schema": projected_output_schema(
                            endpoint,
                            selected_names,
                        ),
                        "matched_fields": matched_fields,
                        "score_components": score_components,
                    },
                )
            )

        ranked = [
            candidate.model_copy(update={"rank": index})
            for index, candidate in enumerate(projected_candidates, start=1)
        ]
        return retrieval.model_copy(
            deep=True,
            update={
                "total_ranked": len(ranked),
                "candidates": ranked,
            },
        )

    def _combined_availability_predicate(
        self,
        principal: PrincipalContext | None,
        predicate: Callable[[ToolSpec, Any], bool] | None = None,
    ) -> Callable[[ToolSpec, Any], bool] | None:
        authorization = self._authorization_predicate(principal)
        if authorization is None:
            return predicate
        if predicate is None:
            return authorization
        return lambda tool, endpoint: (
            authorization(tool, endpoint) and predicate(tool, endpoint)
        )

    def authorization_audit_delivery_status(
        self,
    ) -> AuthorizationAuditDeliveryStatus:
        """Return privacy-safe health counters for the configured audit sink."""

        return self._authorization_audit_delivery.snapshot()

    def _emit_authorization_audit(
        self,
        event: AuthorizationAuditEvent,
        *,
        authorization_error: PolicyViolationError | None = None,
    ) -> None:
        hook = self.authorization_audit_hook
        if hook is None:
            return
        try:
            hook(event)
        except Exception as exc:  # noqa: BLE001
            self._authorization_audit_delivery.record_failure(event, exc)
            if self.authorization_audit_delivery_mode == "strict":
                raise AuthorizationAuditDeliveryError(
                    "mandatory authorization audit delivery failed",
                    event=event,
                    authorization_error=authorization_error,
                ) from exc
            return
        self._authorization_audit_delivery.record_success()

    def _audit_export_authorization(
        self,
        principal: PrincipalContext | None,
        tool: ToolSpec,
        endpoint: EndpointSpec,
        *,
        run_id: str | None = None,
        principal_audit_id: str | None = None,
    ) -> bool:
        """Emit one privacy-safe authorization decision for a framework export."""

        policy = self.authorization_policy
        if policy is None:
            return True
        audit_run_id = run_id or uuid4().hex
        operation = f"{tool.key}.{endpoint.name}"
        if principal is None:
            self._emit_authorization_audit(
                AuthorizationAuditEvent(
                    effect="deny",
                    operation=operation,
                    decision_source="missing_principal",
                    run_id=audit_run_id,
                    phase="export",
                    principal_audit_id=principal_audit_id,
                    tool=tool.key,
                    endpoint=endpoint.name,
                )
            )
            return False

        decision = policy.evaluate(principal, tool, endpoint)
        if decision.effect != "allow":
            self._emit_authorization_audit(
                AuthorizationAuditEvent(
                    effect="deny",
                    operation=decision.operation,
                    decision_source=decision.source,
                    run_id=audit_run_id,
                    phase="export",
                    principal_audit_id=principal_audit_id,
                    rule_name=decision.rule_name,
                    tool=tool.key,
                    endpoint=endpoint.name,
                )
            )
            return False

        try:
            scope = policy.data_scope(principal, tool, endpoint)
        except PolicyViolationError as authorization_error:
            self._emit_authorization_audit(
                AuthorizationAuditEvent(
                    effect="deny",
                    operation=decision.operation,
                    decision_source=decision.source,
                    run_id=audit_run_id,
                    phase="export",
                    principal_audit_id=principal_audit_id,
                    rule_name=decision.rule_name,
                    tool=tool.key,
                    endpoint=endpoint.name,
                ),
                authorization_error=authorization_error,
            )
            raise

        self._emit_authorization_audit(
            AuthorizationAuditEvent(
                effect="allow",
                operation=decision.operation,
                decision_source=decision.source,
                run_id=audit_run_id,
                phase="export",
                principal_audit_id=principal_audit_id,
                rule_name=decision.rule_name,
                data_scope_rule_name=scope.rule_name,
                visible_field_count=(
                    None if scope.visible_fields is None else len(scope.visible_fields)
                ),
                trusted_filter_fields=tuple(
                    field for field, _value in scope.trusted_filters
                ),
                allowed_relationship_count=(
                    None
                    if scope.allowed_relationships is None
                    else len(scope.allowed_relationships)
                ),
                max_hops=scope.max_hops,
                tool=tool.key,
                endpoint=endpoint.name,
            )
        )
        return True

    def _validate_plan_authorization(
        self,
        plan: ExecutionPlan,
        principal: PrincipalContext | None,
        *,
        run_id: str | None = None,
        principal_audit_id: str | None = None,
        phase: AuthorizationAuditPhase = "execution",
    ) -> None:
        policy = self.authorization_policy
        if policy is None:
            return
        audit_run_id = run_id or uuid4().hex
        if principal is None:
            authorization_error = PolicyViolationError(
                "principal context is required when authorization_policy is configured"
            )
            for call in plan.calls:
                self._emit_authorization_audit(
                    AuthorizationAuditEvent(
                        effect="deny",
                        operation=f"{call.tool}.{call.endpoint}",
                        decision_source="missing_principal",
                        run_id=audit_run_id,
                        phase=phase,
                        principal_audit_id=principal_audit_id,
                        tool=call.tool,
                        endpoint=call.endpoint,
                    ),
                    authorization_error=authorization_error,
                )
            raise authorization_error

        for call in plan.calls:
            try:
                tool = self.registry.get(call.tool)
                endpoint = tool.endpoint(call.endpoint)
            except KeyError as exc:
                authorization_error = PolicyViolationError(
                    "authorization denied for requested capability"
                )
                self._emit_authorization_audit(
                    AuthorizationAuditEvent(
                        effect="deny",
                        operation=f"{call.tool}.{call.endpoint}",
                        decision_source="missing_capability",
                        run_id=audit_run_id,
                        phase=phase,
                        principal_audit_id=principal_audit_id,
                        tool=call.tool,
                        endpoint=call.endpoint,
                    ),
                    authorization_error=authorization_error,
                )
                raise authorization_error from exc

            decision = policy.evaluate(principal, tool, endpoint, call)
            if decision.effect != "allow":
                authorization_error = PolicyViolationError(
                    "authorization denied for requested capability"
                )
                self._emit_authorization_audit(
                    AuthorizationAuditEvent(
                        effect="deny",
                        operation=decision.operation,
                        decision_source=decision.source,
                        run_id=audit_run_id,
                        phase=phase,
                        principal_audit_id=principal_audit_id,
                        rule_name=decision.rule_name,
                        tool=tool.key,
                        endpoint=endpoint.name,
                    ),
                    authorization_error=authorization_error,
                )
                raise authorization_error

            scope = policy.data_scope(principal, tool, endpoint)
            try:
                policy.validate_data_scope(principal, tool, endpoint, call)
            except PolicyViolationError as authorization_error:
                self._emit_authorization_audit(
                    AuthorizationAuditEvent(
                        effect="deny",
                        operation=decision.operation,
                        decision_source=decision.source,
                        run_id=audit_run_id,
                        phase=phase,
                        principal_audit_id=principal_audit_id,
                        rule_name=decision.rule_name,
                        data_scope_rule_name=scope.rule_name,
                        visible_field_count=(
                            None
                            if scope.visible_fields is None
                            else len(scope.visible_fields)
                        ),
                        trusted_filter_fields=tuple(
                            field for field, _value in scope.trusted_filters
                        ),
                        allowed_relationship_count=(
                            None
                            if scope.allowed_relationships is None
                            else len(scope.allowed_relationships)
                        ),
                        max_hops=scope.max_hops,
                        tool=tool.key,
                        endpoint=endpoint.name,
                    ),
                    authorization_error=authorization_error,
                )
                raise

            self._emit_authorization_audit(
                AuthorizationAuditEvent(
                    effect="allow",
                    operation=decision.operation,
                    decision_source=decision.source,
                    run_id=audit_run_id,
                    phase=phase,
                    principal_audit_id=principal_audit_id,
                    rule_name=decision.rule_name,
                    data_scope_rule_name=scope.rule_name,
                    visible_field_count=(
                        None if scope.visible_fields is None else len(scope.visible_fields)
                    ),
                    trusted_filter_fields=tuple(
                        field for field, _value in scope.trusted_filters
                    ),
                    allowed_relationship_count=(
                        None
                        if scope.allowed_relationships is None
                        else len(scope.allowed_relationships)
                    ),
                    max_hops=scope.max_hops,
                    tool=tool.key,
                    endpoint=endpoint.name,
                )
            )

    async def __aenter__(self) -> SchemaRouter:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: Any | None,
    ) -> bool:
        del exc_type, exc, traceback
        await self.aclose()
        return False

    async def aclose(self) -> None:
        """Stop router-owned background tasks without closing caller-owned resources."""

        results = await asyncio.gather(
            self.schema_watcher.stop(),
            self.health_monitor.stop(),
            self.stop_native_schema_watcher(),
            return_exceptions=True,
        )
        self.executor.shutdown_offloaded_sync()
        errors = [result for result in results if isinstance(result, BaseException)]
        if not errors:
            return

        cancellation = next(
            (
                error
                for error in errors
                if isinstance(error, asyncio.CancelledError)
            ),
            None,
        )
        if cancellation is not None:
            raise cancellation

        first = errors[0]
        raise RuntimeError(
            "SchemaRouter shutdown encountered an error after attempting all "
            "router-owned background tasks"
        ) from first

    @property
    def input_schema(self) -> dict[str, Any]:
        return PlanRequest.model_json_schema()

    @property
    def output_schema(self) -> dict[str, Any]:
        return TypeAdapter(list[ToolResult]).json_schema()

    @property
    def config_schema(self) -> dict[str, Any]:
        return RunConfig.model_json_schema()

    def inspect(
        self,
        *,
        decision_traces: Sequence[CapabilityDecisionTrace] = (),
    ) -> RouterInspection:
        """Return a privacy-safe live operational snapshot."""

        return inspect_router(
            self,
            decision_traces=decision_traces,
        )

    def mark_access_unavailable(
        self,
        tool_key: str,
        endpoint: str,
        *,
        cooldown_seconds: float | None = None,
    ) -> None:
        """Mark one trusted access path temporarily unavailable."""

        self.executor.mark_access_unavailable(
            tool_key,
            endpoint,
            cooldown_seconds=cooldown_seconds,
        )

    def mark_access_available(self, tool_key: str, endpoint: str) -> None:
        """Clear temporary unavailability for one trusted access path."""

        self.executor.mark_access_available(tool_key, endpoint)

    def unavailable_access_paths(self) -> tuple[tuple[str, str], ...]:
        """Return access paths currently held in the bounded cooldown window."""

        return self.executor.unavailable_access_paths()

    def register_health_probe(
        self,
        tool_key: str,
        endpoint: str,
        probe: HealthProbe,
    ) -> None:
        """Register a trusted local health probe for one read-only access path."""

        self.health_monitor.register(tool_key, endpoint, probe)

    def unregister_health_probe(self, tool_key: str, endpoint: str) -> None:
        self.health_monitor.unregister(tool_key, endpoint)

    def health_snapshots(self) -> tuple[HealthProbeSnapshot, ...]:
        return self.health_monitor.snapshots()

    async def check_health_once(
        self,
        *,
        probe_timeout_seconds: float | None = None,
        unavailable_cooldown_seconds: float | None = None,
        max_concurrency: int | None = None,
    ) -> tuple[HealthProbeSnapshot, ...]:
        return await self.health_monitor.run_once(
            probe_timeout_seconds=probe_timeout_seconds,
            unavailable_cooldown_seconds=unavailable_cooldown_seconds,
            max_concurrency=max_concurrency,
        )


    async def start_health_monitor(
        self,
        *,
        interval_seconds: float = 30.0,
        probe_timeout_seconds: float = 5.0,
        max_concurrency: int = 4,
    ) -> None:
        await self.health_monitor.start(
            interval_seconds=interval_seconds,
            probe_timeout_seconds=probe_timeout_seconds,
            max_concurrency=max_concurrency,
        )

    async def stop_health_monitor(self) -> None:
        await self.health_monitor.stop()

    def register_schema_watch(
        self,
        tool_key: str,
        *,
        interval_seconds: float = 300.0,
        apply_compatible: bool = True,
        schema_headers: dict[str, str] | None = None,
        trusted_headers: dict[str, str] | None = None,
        mcp_client_factory: MCPClientFactory | None = None,
        timeout_seconds: float = RUNTIME_DEFAULTS.transport_timeout_seconds,
    ) -> None:
        """Register one remote structured source for periodic schema refresh."""

        self.schema_watcher.register(
            tool_key,
            interval_seconds=interval_seconds,
            apply_compatible=apply_compatible,
            schema_headers=schema_headers,
            trusted_headers=trusted_headers,
            mcp_client_factory=mcp_client_factory,
            timeout_seconds=timeout_seconds,
        )

    def unregister_schema_watch(self, tool_key: str) -> None:
        self.schema_watcher.unregister(tool_key)

    def schema_watch_snapshots(self) -> tuple[SchemaWatchSnapshot, ...]:
        return self.schema_watcher.snapshots()

    def schema_watch_pending_review(
        self,
        tool_key: str,
    ) -> SchemaRefreshResult | None:
        return self.schema_watcher.pending_review(tool_key)

    async def aaccept_schema_watch_pending(
        self,
        tool_key: str,
        *,
        expected_candidate_fingerprint: str,
    ) -> SchemaRefreshResult:
        return await self.schema_watcher.accept_pending(
            tool_key,
            expected_candidate_fingerprint=expected_candidate_fingerprint,
        )

    def accept_schema_watch_pending(
        self,
        tool_key: str,
        *,
        expected_candidate_fingerprint: str,
    ) -> SchemaRefreshResult:
        return _run_sync(
            lambda: self.aaccept_schema_watch_pending(
                tool_key,
                expected_candidate_fingerprint=expected_candidate_fingerprint,
            )
        )

    async def areject_schema_watch_pending(
        self,
        tool_key: str,
        *,
        expected_candidate_fingerprint: str,
    ) -> SchemaRefreshResult:
        return await self.schema_watcher.reject_pending(
            tool_key,
            expected_candidate_fingerprint=expected_candidate_fingerprint,
        )

    def reject_schema_watch_pending(
        self,
        tool_key: str,
        *,
        expected_candidate_fingerprint: str,
    ) -> SchemaRefreshResult:
        return _run_sync(
            lambda: self.areject_schema_watch_pending(
                tool_key,
                expected_candidate_fingerprint=expected_candidate_fingerprint,
            )
        )

    async def check_schema_watches_once(
        self,
        *,
        force: bool = True,
        max_concurrency: int | None = None,
    ) -> tuple[SchemaWatchSnapshot, ...]:
        return await self.schema_watcher.run_once(
            force=force,
            max_concurrency=max_concurrency,
        )

    async def start_schema_watcher(
        self,
        *,
        max_concurrency: int = 4,
    ) -> None:
        await self.schema_watcher.start(max_concurrency=max_concurrency)

    async def stop_schema_watcher(self) -> None:
        await self.schema_watcher.stop()

    def with_config(
        self,
        config: RunConfig | dict[str, Any],
    ) -> ConfiguredSchemaRouter:
        return ConfiguredSchemaRouter(self, _coerce_config(config))

    @classmethod
    async def from_url(
        cls,
        url: str,
        *,
        kind: SourceKind = "auto",
        name: str | None = None,
        namespace: str | None = None,
        provider: str | None = None,
        access_mode: str | None = None,
        analyzer: QueryAnalyzer | None = None,
        http_client: httpx.AsyncClient | None = None,
        policy: ExecutionPolicy | None = None,
        authorization_policy: AuthorizationPolicy | None = None,
        approval_callback: ApprovalCallback | None = None,
        execution_hooks: ExecutionHooks | None = None,
        registry: ToolRegistry | None = None,
        adapter_registry: AdapterRegistry | None = None,
        network_policy: NetworkPolicy | None = None,
        unavailable_cooldown_seconds: float = 30.0,
        base_url: str | None = None,
        schema_headers: dict[str, str] | None = None,
        trusted_headers: dict[str, str] | None = None,
        mcp_client_factory: MCPClientFactory | None = None,
        mcp_discovery_limits: MCPDiscoveryLimits | None = None,
        allow_active_probes: bool = False,
        openapi_external_refs: bool = False,
        openapi_ref_max_depth: int = RUNTIME_DEFAULTS.openapi_ref_max_depth,
        openapi_ref_max_documents: int = RUNTIME_DEFAULTS.openapi_ref_max_documents,
        openapi_ref_max_bytes: int = RUNTIME_DEFAULTS.openapi_ref_max_bytes,
    ) -> SchemaRouter:
        router = cls(
            analyzer=analyzer,
            http_client=http_client,
            policy=policy,
            authorization_policy=authorization_policy,
            approval_callback=approval_callback,
            execution_hooks=execution_hooks,
            registry=registry,
            adapter_registry=adapter_registry,
            network_policy=network_policy,
            unavailable_cooldown_seconds=unavailable_cooldown_seconds,
        )
        await router.add_url(
            url,
            kind=kind,
            name=name,
            namespace=namespace,
            provider=provider,
            access_mode=access_mode,
            base_url=base_url,
            schema_headers=schema_headers,
            trusted_headers=trusted_headers,
            mcp_client_factory=mcp_client_factory,
            mcp_discovery_limits=mcp_discovery_limits,
            allow_active_probes=allow_active_probes,
            openapi_external_refs=openapi_external_refs,
            openapi_ref_max_depth=openapi_ref_max_depth,
            openapi_ref_max_documents=openapi_ref_max_documents,
            openapi_ref_max_bytes=openapi_ref_max_bytes,
        )
        return router

    def add_tool(self, tool: ToolSpec, *, replace: bool = False) -> str:
        if not replace:
            return self.registry.register(tool)

        try:
            current = self.registry.get(tool.key)
        except KeyError:
            return self.registry.register(tool)

        key = self.registry.register(tool, replace=True)
        if current.fingerprint != tool.fingerprint:
            # A direct ToolSpec replacement has not validated that the old trusted
            # transport/probes remain valid for the new contract. Fail closed rather
            # than silently carrying process-local runtime state across the boundary.
            self.executor.purge_tool_runtime_state(key)
            self.health_monitor.unregister_tool(key)
            self.schema_watcher.unregister(key)
            self.loader.forget_schema_http_validators(key)
            self._native_schema_lifecycle.forget(key)
        return key

    async def aremove_tool(self, tool_key: str) -> ToolSpec:
        """Atomically remove one capability and all router-owned runtime state."""

        async with self.schema_watcher.lifecycle_guard():
            async with self.health_monitor.lifecycle_guard(wait_for_inflight=True):
                expected_version = self.registry.version
                try:
                    current = self.registry.get(tool_key)
                except KeyError as exc:
                    raise RegistrationError(f"unknown tool: {tool_key}") from exc

                unregister_if_current(
                    self.registry,
                    tool_key,
                    expected_fingerprint=current.fingerprint,
                    expected_version=expected_version,
                )

                self.schema_watcher.unregister(tool_key)
                self.health_monitor.unregister_tool(tool_key)
                self.executor.purge_tool_runtime_state(tool_key)
                self.loader.forget_schema_http_validators(tool_key)
                self._native_schema_lifecycle.forget(tool_key)
                return current

    def remove_tool(self, tool_key: str) -> ToolSpec:
        """Synchronous wrapper for :meth:`aremove_tool`."""

        return _run_sync(lambda: self.aremove_tool(tool_key))

    def add_bound_tool(
        self,
        tool: ToolSpec,
        invoker: BoundEndpointInvoker,
        *,
        replace: bool = False,
        offload_sync: bool = False,
    ) -> str:
        """Register a canonical ToolSpec and bind one trusted invoker.

        This is the explicit escape hatch for SDKs and protocol clients that do not expose a
        safely introspectable Python signature. The ToolSpec remains the complete model-visible
        contract; client objects, credentials, and transport state stay inside trusted invoker
        state.
        """

        return self.executor.publish_bound_tool(
            tool,
            invoker,
            replace=replace,
            offload_sync=offload_sync,
        )

    def _register_bound_batch(
        self,
        bindings: Any,
        *,
        expected_version: int,
        offload_sync: bool = False,
    ) -> tuple[str, ...]:
        staged = tuple(bindings)
        rollback = getattr(self.registry, "unregister_many_if_version", None)
        if not callable(rollback):
            raise RegistrationError(
                "atomic bound batch registration requires version-guarded batch rollback"
            )

        staged_keys = tuple(binding.tool.key for binding in staged)
        self.executor.ensure_tool_runtime_state_empty(staged_keys)

        keys = update_many_if_current(
            self.registry,
            (binding.tool for binding in staged),
            expected_version=expected_version,
        )
        published_version = expected_version + 1
        published_generations: dict[str, int] = {}
        try:
            for key, binding in zip(keys, staged, strict=True):
                published_generations[key] = self.executor.bind(
                    key,
                    binding.invoker,
                    expected_fingerprint=binding.tool.fingerprint,
                    offload_sync=offload_sync,
                    require_empty_runtime_state=True,
                )
            if self.registry.version != published_version:
                raise BindingDriftError(
                    "registry changed concurrently while publishing a bound tool batch"
                )
        except Exception as exc:
            runtime_rollback_conflict = False
            for key, generation in published_generations.items():
                if not self.executor._remove_binding_if_generation(key, generation):
                    runtime_rollback_conflict = True
                    continue
                if self.executor.has_tool_runtime_state(key):
                    runtime_rollback_conflict = True
            try:
                rollback(
                    {
                        key: binding.tool.fingerprint
                        for key, binding in zip(keys, staged, strict=True)
                    },
                    expected_version=published_version,
                )
            except Exception as rollback_exc:
                raise BindingDriftError(
                    "bound tool batch failed and registry rollback could not be completed "
                    "without overwriting concurrent state"
                ) from rollback_exc
            if runtime_rollback_conflict:
                raise BindingDriftError(
                    "bound tool batch failed and executor rollback detected newer "
                    "runtime state; concurrent state was preserved"
                ) from exc
            raise
        return keys

    def _register_refreshable_bound_batch(
        self,
        bindings: Any,
        *,
        refresh_binding: Callable[
            [str],
            Awaitable[tuple[ToolSpec, BoundEndpointInvoker, bool]],
        ],
        offload_sync: bool = False,
    ) -> tuple[str, ...]:
        """Publish one discovered batch and attach schema refresh callbacks."""

        expected_version = self.registry.version
        keys = self._register_bound_batch(
            bindings,
            expected_version=expected_version,
            offload_sync=offload_sync,
        )
        for key in keys:
            async def refresh_one(
                tool_key: str = key,
            ) -> tuple[ToolSpec, BoundEndpointInvoker, bool]:
                return await refresh_binding(tool_key)

            self._remember_native_schema_refresh(key, refresh_one)
        return keys

    def _remember_native_schema_refresh(
        self,
        tool_key: str,
        refresh: Any,
    ) -> None:
        self._native_schema_lifecycle.remember(tool_key, refresh)

    def native_schema_watch_snapshots(self) -> tuple[NativeSchemaWatchSnapshot, ...]:
        """Return bounded watcher degradation state without exception messages."""

        return self._native_schema_lifecycle.snapshots()

    def _prepare_health_contract_transition(
        self,
        current: ToolSpec,
        candidate: ToolSpec,
    ) -> Any | None:
        if current.fingerprint == candidate.fingerprint:
            return None
        return self.health_monitor._prepare_tool_contract_transition(
            current.key,
            expected_old_fingerprint=current.fingerprint,
            expected_new_fingerprint=candidate.fingerprint,
            new_tool=candidate,
        )

    def _apply_health_contract_transition(self, transition: Any | None) -> None:
        if transition is not None:
            self.health_monitor._apply_tool_contract_transition(transition)

    async def _apply_native_schema_binding(
        self,
        *,
        current: ToolSpec,
        candidate_tool: ToolSpec,
        candidate_invoker: BoundEndpointInvoker,
        offload_sync: bool,
        expected_version: int,
    ) -> None:
        """Atomically move a native contract, trusted binding, and probe generation."""

        async with self.health_monitor.lifecycle_guard():
            with self.health_monitor.contract_transition_guard():
                health_transition = self._prepare_health_contract_transition(
                    current,
                    candidate_tool,
                )
                self.executor.publish_bound_tool(
                    candidate_tool,
                    candidate_invoker,
                    replace=True,
                    expected_fingerprint=current.fingerprint,
                    expected_version=expected_version,
                    offload_sync=offload_sync,
                )
                self._apply_health_contract_transition(health_transition)

    async def arefresh_native_schema(
        self,
        tool_key: str,
        *,
        apply_compatible: bool = True,
    ) -> SchemaRefreshResult:
        """Re-introspect one caller-owned native data source."""

        return await self._native_schema_lifecycle.refresh(
            tool_key,
            apply_compatible=apply_compatible,
        )

    async def aaccept_native_schema_pending(
        self,
        tool_key: str,
        *,
        expected_candidate_fingerprint: str,
    ) -> SchemaRefreshResult:
        return await self._native_schema_lifecycle.accept_pending(
            tool_key,
            expected_candidate_fingerprint=expected_candidate_fingerprint,
        )

    async def check_native_schema_watches_once(
        self,
        *,
        apply_compatible: bool = True,
    ) -> tuple[SchemaRefreshResult, ...]:
        return await self._native_schema_lifecycle.check_once(
            apply_compatible=apply_compatible,
        )

    async def start_native_schema_watcher(
        self,
        *,
        interval_seconds: float = 300.0,
        apply_compatible: bool = True,
    ) -> None:
        await self._native_schema_lifecycle.start(
            interval_seconds=interval_seconds,
            apply_compatible=apply_compatible,
        )

    async def stop_native_schema_watcher(self) -> None:
        await self._native_schema_lifecycle.stop()

    def add_sqlite_database(
        self,
        connection: Any,
        *,
        database_name: str = "sqlite",
        namespace: str | None = None,
        tables: set[str] | tuple[str, ...] | list[str] | None = None,
        max_default_rows: int = 100,
        max_discovery_relations: int = 128,
        max_columns_per_relation: int = 256,
        max_generated_bytes: int = RUNTIME_DEFAULTS.max_generated_bytes,
    ) -> tuple[str, ...]:
        """Introspect and register a caller-owned SQLite database as read-only capabilities.

        The live connection remains in trusted process-local invokers and is never persisted
        or copied into ToolSpec metadata. One ToolSpec is registered per selected table/view.
        The generated invokers support bounded projected SELECT operations only; callers cannot
        supply arbitrary SQL text through the model-visible contract.
        """

        from .adapters.sqlite_database import introspect_sqlite_database

        # Capture the catalog generation before introspection so a concurrent
        # writer cannot land between discovery and publication unnoticed.
        expected_version = self.registry.version
        bindings = introspect_sqlite_database(
            connection,
            database_name=database_name,
            namespace=namespace,
            tables=tables,
            max_default_rows=max_default_rows,
            max_discovery_relations=max_discovery_relations,
            max_columns_per_relation=max_columns_per_relation,
            max_generated_bytes=max_generated_bytes,
        )
        return self._register_bound_batch(
            bindings,
            expected_version=expected_version,
        )

    def add_sqlalchemy_database(
        self,
        engine: Any,
        *,
        database_name: str,
        namespace: str | None = None,
        schemas: tuple[str | None, ...] | list[str | None] | None = None,
        tables: set[str] | tuple[str, ...] | list[str] | None = None,
        include_views: bool = True,
        max_default_rows: int = 100,
        remote: bool = True,
        max_discovery_relations: int = 128,
        max_columns_per_relation: int = 256,
        max_generated_bytes: int = RUNTIME_DEFAULTS.max_generated_bytes,
    ) -> tuple[str, ...]:
        """Introspect and register a caller-owned SQLAlchemy Engine.

        SQLAlchemy performs dialect-specific schema discovery and parameter binding while the live
        Engine, connection URL, credentials, pools, and driver state remain process-local. The
        generated model-visible contract contains only relation/column metadata and bounded
        projected read operations.
        """

        from .adapters.sqlalchemy_database import introspect_sqlalchemy_engine

        bindings = introspect_sqlalchemy_engine(
            engine,
            database_name=database_name,
            namespace=namespace,
            schemas=schemas,
            tables=tables,
            include_views=include_views,
            max_default_rows=max_default_rows,
            remote=remote,
            max_discovery_relations=max_discovery_relations,
            max_columns_per_relation=max_columns_per_relation,
            max_generated_bytes=max_generated_bytes,
        )
        async def refresh_binding(
            tool_key: str,
        ) -> tuple[ToolSpec, BoundEndpointInvoker, bool]:
            if remote:
                refreshed = await asyncio.to_thread(
                    introspect_sqlalchemy_engine,
                    engine,
                    database_name=database_name,
                    namespace=namespace,
                    schemas=schemas,
                    tables=tables,
                    include_views=include_views,
                    max_default_rows=max_default_rows,
                    remote=remote,
                    max_discovery_relations=max_discovery_relations,
                    max_columns_per_relation=max_columns_per_relation,
                    max_generated_bytes=max_generated_bytes,
                )
            else:
                refreshed = introspect_sqlalchemy_engine(
                    engine,
                    database_name=database_name,
                    namespace=namespace,
                    schemas=schemas,
                    tables=tables,
                    include_views=include_views,
                    max_default_rows=max_default_rows,
                    remote=remote,
                    max_discovery_relations=max_discovery_relations,
                    max_columns_per_relation=max_columns_per_relation,
                    max_generated_bytes=max_generated_bytes,
                )
            match = next((item for item in refreshed if item.tool.key == tool_key), None)
            if match is None:
                raise SchemaSourceError(
                    f"native database capability {tool_key!r} disappeared during refresh"
                )
            return match.tool, match.invoker, remote
        return self._register_refreshable_bound_batch(
            bindings,
            refresh_binding=refresh_binding,
            offload_sync=remote,
        )

    async def aadd_vector_store(
        self,
        backend: Any,
        embed_query: Any,
        *,
        database_name: str,
        namespace: str | None = None,
        collections: set[str] | tuple[str, ...] | list[str] | None = None,
        default_top_k: int = RUNTIME_DEFAULTS.vector_top_k,
        remote: bool = True,
        max_discovery_sources: int = RUNTIME_DEFAULTS.max_discovery_sources,
        max_fields_per_collection: int = RUNTIME_DEFAULTS.max_fields_per_collection,
        max_generated_bytes: int = RUNTIME_DEFAULTS.max_generated_bytes,
    ) -> tuple[str, ...]:
        """Discover and register a caller-owned vector store as bounded search capabilities."""

        from .adapters.vector_store import introspect_vector_backend

        bindings = await introspect_vector_backend(
            backend,
            embed_query,
            database_name=database_name,
            namespace=namespace,
            collections=collections,
            default_top_k=default_top_k,
            remote=remote,
            offload_sync_backend=remote,
            max_discovery_sources=max_discovery_sources,
            max_fields_per_collection=max_fields_per_collection,
            max_generated_bytes=max_generated_bytes,
        )
        async def refresh_binding(
            tool_key: str,
        ) -> tuple[ToolSpec, BoundEndpointInvoker, bool]:
            refreshed = await introspect_vector_backend(
                backend,
                embed_query,
                database_name=database_name,
                namespace=namespace,
                collections=collections,
                default_top_k=default_top_k,
                remote=remote,
                max_discovery_sources=max_discovery_sources,
                max_fields_per_collection=max_fields_per_collection,
                max_generated_bytes=max_generated_bytes,
            )
            match = next((item for item in refreshed if item.tool.key == tool_key), None)
            if match is None:
                raise SchemaSourceError(
                    f"native vector capability {tool_key!r} disappeared during refresh"
                )
            return match.tool, match.invoker, False
        return self._register_refreshable_bound_batch(
            bindings,
            refresh_binding=refresh_binding,
        )

    def add_vector_store(
        self,
        backend: Any,
        embed_query: Any,
        *,
        database_name: str,
        namespace: str | None = None,
        collections: set[str] | tuple[str, ...] | list[str] | None = None,
        default_top_k: int = RUNTIME_DEFAULTS.vector_top_k,
        remote: bool = True,
        max_discovery_sources: int = RUNTIME_DEFAULTS.max_discovery_sources,
        max_fields_per_collection: int = RUNTIME_DEFAULTS.max_fields_per_collection,
        max_generated_bytes: int = RUNTIME_DEFAULTS.max_generated_bytes,
    ) -> tuple[str, ...]:
        """Synchronous wrapper for :meth:`aadd_vector_store`."""

        return _run_sync(
            lambda: self.aadd_vector_store(
                backend,
                embed_query,
                database_name=database_name,
                namespace=namespace,
                collections=collections,
                default_top_k=default_top_k,
                remote=remote,
                max_discovery_sources=max_discovery_sources,
                max_fields_per_collection=max_fields_per_collection,
                max_generated_bytes=max_generated_bytes,
            )
        )

    async def aadd_native_vector_store(
        self,
        backend_name: str,
        resource: Any,
        embed_query: Any,
        *,
        database_name: str,
        namespace: str | None = None,
        collections: set[str] | tuple[str, ...] | list[str] | None = None,
        backend_options: Mapping[str, Any] | None = None,
        default_top_k: int = RUNTIME_DEFAULTS.vector_top_k,
        remote: bool = True,
        max_discovery_sources: int = RUNTIME_DEFAULTS.max_discovery_sources,
        max_fields_per_collection: int = RUNTIME_DEFAULTS.max_fields_per_collection,
        max_generated_bytes: int = RUNTIME_DEFAULTS.max_generated_bytes,
    ) -> tuple[str, ...]:
        """Register a native vector backend through the descriptor registry."""

        from .native_registration import build_native_vector_backend

        backend = build_native_vector_backend(
            backend_name,
            resource,
            **dict(backend_options or {}),
        )
        return await self.aadd_vector_store(
            backend,
            embed_query,
            database_name=database_name,
            namespace=namespace,
            collections=collections,
            default_top_k=default_top_k,
            remote=remote,
            max_discovery_sources=max_discovery_sources,
            max_fields_per_collection=max_fields_per_collection,
            max_generated_bytes=max_generated_bytes,
        )

    def add_native_vector_store(
        self,
        backend_name: str,
        resource: Any,
        embed_query: Any,
        *,
        database_name: str,
        namespace: str | None = None,
        collections: set[str] | tuple[str, ...] | list[str] | None = None,
        backend_options: Mapping[str, Any] | None = None,
        default_top_k: int = RUNTIME_DEFAULTS.vector_top_k,
        remote: bool = True,
        max_discovery_sources: int = RUNTIME_DEFAULTS.max_discovery_sources,
        max_fields_per_collection: int = RUNTIME_DEFAULTS.max_fields_per_collection,
        max_generated_bytes: int = RUNTIME_DEFAULTS.max_generated_bytes,
    ) -> tuple[str, ...]:
        """Synchronous wrapper for :meth:`aadd_native_vector_store`."""

        return _run_sync(
            lambda: self.aadd_native_vector_store(
                backend_name,
                resource,
                embed_query,
                database_name=database_name,
                namespace=namespace,
                collections=collections,
                backend_options=backend_options,
                default_top_k=default_top_k,
                remote=remote,
                max_discovery_sources=max_discovery_sources,
                max_fields_per_collection=max_fields_per_collection,
                max_generated_bytes=max_generated_bytes,
            )
        )

    async def aadd_qdrant_vector_store(
        self,
        client: Any,
        embed_query: Any,
        *,
        database_name: str = "qdrant",
        namespace: str | None = None,
        collections: set[str] | tuple[str, ...] | list[str] | None = None,
        vector_name_by_collection: Mapping[str, str] | None = None,
        metadata_fields_by_collection: Mapping[str, Sequence[Any]] | None = None,
        filter_builder: Callable[[Mapping[str, Any]], Any] | None = None,
        default_top_k: int = RUNTIME_DEFAULTS.vector_top_k,
        max_discovery_sources: int = RUNTIME_DEFAULTS.max_discovery_sources,
        max_fields_per_collection: int = RUNTIME_DEFAULTS.max_fields_per_collection,
        remote: bool = True,
    ) -> tuple[str, ...]:
        """Register a caller-owned Qdrant client through the vector capability contract."""

        return await self.aadd_native_vector_store(
            "qdrant",
            client,
            embed_query,
            database_name=database_name,
            namespace=namespace,
            collections=collections,
            backend_options={
                "vector_name_by_collection": vector_name_by_collection,
                "metadata_fields_by_collection": metadata_fields_by_collection,
                "filter_builder": filter_builder,
                "collections": (
                    None if collections is None else tuple(sorted(collections))
                ),
                "max_discovery_sources": max_discovery_sources,
                "max_fields_per_collection": max_fields_per_collection,
            },
            default_top_k=default_top_k,
            remote=remote,
            max_discovery_sources=max_discovery_sources,
            max_fields_per_collection=max_fields_per_collection,
        )

    def add_qdrant_vector_store(
        self,
        client: Any,
        embed_query: Any,
        *,
        database_name: str = "qdrant",
        namespace: str | None = None,
        collections: set[str] | tuple[str, ...] | list[str] | None = None,
        vector_name_by_collection: Mapping[str, str] | None = None,
        metadata_fields_by_collection: Mapping[str, Sequence[Any]] | None = None,
        filter_builder: Callable[[Mapping[str, Any]], Any] | None = None,
        default_top_k: int = RUNTIME_DEFAULTS.vector_top_k,
        max_discovery_sources: int = RUNTIME_DEFAULTS.max_discovery_sources,
        max_fields_per_collection: int = RUNTIME_DEFAULTS.max_fields_per_collection,
        remote: bool = True,
    ) -> tuple[str, ...]:
        """Synchronous wrapper for :meth:`aadd_qdrant_vector_store`."""

        return _run_sync(
            lambda: self.aadd_qdrant_vector_store(
                client,
                embed_query,
                database_name=database_name,
                namespace=namespace,
                collections=collections,
                vector_name_by_collection=vector_name_by_collection,
                metadata_fields_by_collection=metadata_fields_by_collection,
                filter_builder=filter_builder,
                default_top_k=default_top_k,
                max_discovery_sources=max_discovery_sources,
                max_fields_per_collection=max_fields_per_collection,
                remote=remote,
            )
        )

    async def aadd_milvus_vector_store(
        self,
        client: Any,
        embed_query: Any,
        *,
        database_name: str = "milvus",
        namespace: str | None = None,
        collections: set[str] | tuple[str, ...] | list[str] | None = None,
        vector_field_by_collection: Mapping[str, str] | None = None,
        metric_by_collection: Mapping[str, str] | None = None,
        default_top_k: int = RUNTIME_DEFAULTS.vector_top_k,
        max_discovery_sources: int = RUNTIME_DEFAULTS.max_discovery_sources,
        max_fields_per_collection: int = RUNTIME_DEFAULTS.max_fields_per_collection,
        remote: bool = True,
    ) -> tuple[str, ...]:
        """Register a caller-owned MilvusClient through the vector capability contract."""

        return await self.aadd_native_vector_store(
            "milvus",
            client,
            embed_query,
            database_name=database_name,
            namespace=namespace,
            collections=collections,
            backend_options={
                "vector_field_by_collection": vector_field_by_collection,
                "metric_by_collection": metric_by_collection,
                "collections": (
                    None if collections is None else tuple(sorted(collections))
                ),
                "max_discovery_sources": max_discovery_sources,
                "max_fields_per_collection": max_fields_per_collection,
            },
            default_top_k=default_top_k,
            remote=remote,
            max_discovery_sources=max_discovery_sources,
            max_fields_per_collection=max_fields_per_collection,
        )

    def add_milvus_vector_store(
        self,
        client: Any,
        embed_query: Any,
        *,
        database_name: str = "milvus",
        namespace: str | None = None,
        collections: set[str] | tuple[str, ...] | list[str] | None = None,
        vector_field_by_collection: Mapping[str, str] | None = None,
        metric_by_collection: Mapping[str, str] | None = None,
        default_top_k: int = RUNTIME_DEFAULTS.vector_top_k,
        max_discovery_sources: int = RUNTIME_DEFAULTS.max_discovery_sources,
        max_fields_per_collection: int = RUNTIME_DEFAULTS.max_fields_per_collection,
        remote: bool = True,
    ) -> tuple[str, ...]:
        """Synchronous wrapper for :meth:`aadd_milvus_vector_store`."""

        return _run_sync(
            lambda: self.aadd_milvus_vector_store(
                client,
                embed_query,
                database_name=database_name,
                namespace=namespace,
                collections=collections,
                vector_field_by_collection=vector_field_by_collection,
                metric_by_collection=metric_by_collection,
                default_top_k=default_top_k,
                max_discovery_sources=max_discovery_sources,
                max_fields_per_collection=max_fields_per_collection,
                remote=remote,
            )
        )

    async def aadd_pinecone_vector_store(
        self,
        client: Any,
        embed_query: Any,
        *,
        database_name: str = "pinecone",
        namespace: str | None = None,
        collections: set[str] | tuple[str, ...] | list[str] | None = None,
        metadata_fields_by_index: Mapping[str, Sequence[Any]] | None = None,
        default_top_k: int = RUNTIME_DEFAULTS.vector_top_k,
        max_discovery_sources: int = RUNTIME_DEFAULTS.max_discovery_sources,
        max_fields_per_collection: int = RUNTIME_DEFAULTS.max_fields_per_collection,
        remote: bool = True,
    ) -> tuple[str, ...]:
        """Register a caller-owned Pinecone client."""

        return await self.aadd_native_vector_store(
            "pinecone",
            client,
            embed_query,
            database_name=database_name,
            namespace=namespace,
            collections=collections,
            backend_options={
                "metadata_fields_by_index": metadata_fields_by_index,
                "collections": (
                    None if collections is None else tuple(sorted(collections))
                ),
                "max_discovery_sources": max_discovery_sources,
                "max_fields_per_collection": max_fields_per_collection,
            },
            default_top_k=default_top_k,
            remote=remote,
            max_discovery_sources=max_discovery_sources,
            max_fields_per_collection=max_fields_per_collection,
        )

    def add_pinecone_vector_store(
        self,
        client: Any,
        embed_query: Any,
        *,
        database_name: str = "pinecone",
        namespace: str | None = None,
        collections: set[str] | tuple[str, ...] | list[str] | None = None,
        metadata_fields_by_index: Mapping[str, Sequence[Any]] | None = None,
        default_top_k: int = RUNTIME_DEFAULTS.vector_top_k,
        max_discovery_sources: int = RUNTIME_DEFAULTS.max_discovery_sources,
        max_fields_per_collection: int = RUNTIME_DEFAULTS.max_fields_per_collection,
        remote: bool = True,
    ) -> tuple[str, ...]:
        return _run_sync(
            lambda: self.aadd_pinecone_vector_store(
                client,
                embed_query,
                database_name=database_name,
                namespace=namespace,
                collections=collections,
                metadata_fields_by_index=metadata_fields_by_index,
                default_top_k=default_top_k,
                max_discovery_sources=max_discovery_sources,
                max_fields_per_collection=max_fields_per_collection,
                remote=remote,
            )
        )

    async def aadd_chroma_vector_store(
        self,
        client: Any,
        embed_query: Any,
        *,
        database_name: str = "chroma",
        namespace: str | None = None,
        collections: set[str] | tuple[str, ...] | list[str] | None = None,
        dimension_by_collection: Mapping[str, int] | None = None,
        metadata_fields_by_collection: Mapping[str, Sequence[Any]] | None = None,
        metric_by_collection: Mapping[str, str] | None = None,
        default_top_k: int = RUNTIME_DEFAULTS.vector_top_k,
        max_discovery_sources: int = RUNTIME_DEFAULTS.max_discovery_sources,
        max_fields_per_collection: int = RUNTIME_DEFAULTS.max_fields_per_collection,
        remote: bool = False,
    ) -> tuple[str, ...]:
        """Register a caller-owned Chroma client."""

        return await self.aadd_native_vector_store(
            "chroma",
            client,
            embed_query,
            database_name=database_name,
            namespace=namespace,
            collections=collections,
            backend_options={
                "dimension_by_collection": dimension_by_collection,
                "metadata_fields_by_collection": metadata_fields_by_collection,
                "metric_by_collection": metric_by_collection,
                "collections": (
                    None if collections is None else tuple(sorted(collections))
                ),
                "max_discovery_sources": max_discovery_sources,
                "max_fields_per_collection": max_fields_per_collection,
            },
            default_top_k=default_top_k,
            remote=remote,
            max_discovery_sources=max_discovery_sources,
            max_fields_per_collection=max_fields_per_collection,
        )

    def add_chroma_vector_store(
        self,
        client: Any,
        embed_query: Any,
        *,
        database_name: str = "chroma",
        namespace: str | None = None,
        collections: set[str] | tuple[str, ...] | list[str] | None = None,
        dimension_by_collection: Mapping[str, int] | None = None,
        metadata_fields_by_collection: Mapping[str, Sequence[Any]] | None = None,
        metric_by_collection: Mapping[str, str] | None = None,
        default_top_k: int = RUNTIME_DEFAULTS.vector_top_k,
        max_discovery_sources: int = RUNTIME_DEFAULTS.max_discovery_sources,
        max_fields_per_collection: int = RUNTIME_DEFAULTS.max_fields_per_collection,
        remote: bool = False,
    ) -> tuple[str, ...]:
        return _run_sync(
            lambda: self.aadd_chroma_vector_store(
                client,
                embed_query,
                database_name=database_name,
                namespace=namespace,
                collections=collections,
                dimension_by_collection=dimension_by_collection,
                metadata_fields_by_collection=metadata_fields_by_collection,
                metric_by_collection=metric_by_collection,
                default_top_k=default_top_k,
                max_discovery_sources=max_discovery_sources,
                max_fields_per_collection=max_fields_per_collection,
                remote=remote,
            )
        )

    async def aadd_weaviate_vector_store(
        self,
        client: Any,
        embed_query: Any,
        *,
        dimension_by_collection: Mapping[str, int],
        database_name: str = "weaviate",
        namespace: str | None = None,
        collections: set[str] | tuple[str, ...] | list[str] | None = None,
        vector_name_by_collection: Mapping[str, str] | None = None,
        metric_by_collection: Mapping[str, str] | None = None,
        filter_builder: Callable[[Mapping[str, Any]], Any] | None = None,
        default_top_k: int = RUNTIME_DEFAULTS.vector_top_k,
        max_discovery_sources: int = RUNTIME_DEFAULTS.max_discovery_sources,
        max_fields_per_collection: int = RUNTIME_DEFAULTS.max_fields_per_collection,
        remote: bool = True,
    ) -> tuple[str, ...]:
        """Register a caller-owned Weaviate v4 client."""

        return await self.aadd_native_vector_store(
            "weaviate",
            client,
            embed_query,
            database_name=database_name,
            namespace=namespace,
            collections=collections,
            backend_options={
                "dimension_by_collection": dimension_by_collection,
                "vector_name_by_collection": vector_name_by_collection,
                "metric_by_collection": metric_by_collection,
                "filter_builder": filter_builder,
                "collections": (
                    None if collections is None else tuple(sorted(collections))
                ),
                "max_discovery_sources": max_discovery_sources,
                "max_fields_per_collection": max_fields_per_collection,
            },
            default_top_k=default_top_k,
            remote=remote,
            max_discovery_sources=max_discovery_sources,
            max_fields_per_collection=max_fields_per_collection,
        )

    def add_weaviate_vector_store(
        self,
        client: Any,
        embed_query: Any,
        *,
        dimension_by_collection: Mapping[str, int],
        database_name: str = "weaviate",
        namespace: str | None = None,
        collections: set[str] | tuple[str, ...] | list[str] | None = None,
        vector_name_by_collection: Mapping[str, str] | None = None,
        metric_by_collection: Mapping[str, str] | None = None,
        filter_builder: Callable[[Mapping[str, Any]], Any] | None = None,
        default_top_k: int = RUNTIME_DEFAULTS.vector_top_k,
        max_discovery_sources: int = RUNTIME_DEFAULTS.max_discovery_sources,
        max_fields_per_collection: int = RUNTIME_DEFAULTS.max_fields_per_collection,
        remote: bool = True,
    ) -> tuple[str, ...]:
        return _run_sync(
            lambda: self.aadd_weaviate_vector_store(
                client,
                embed_query,
                dimension_by_collection=dimension_by_collection,
                database_name=database_name,
                namespace=namespace,
                collections=collections,
                vector_name_by_collection=vector_name_by_collection,
                metric_by_collection=metric_by_collection,
                filter_builder=filter_builder,
                default_top_k=default_top_k,
                max_discovery_sources=max_discovery_sources,
                max_fields_per_collection=max_fields_per_collection,
                remote=remote,
            )
        )

    async def aadd_pgvector_store(
        self,
        engine: Any,
        embed_query: Any,
        *,
        database_name: str = "pgvector",
        namespace: str | None = None,
        collections: set[str] | tuple[str, ...] | list[str] | None = None,
        tables: Sequence[str] | None = None,
        vector_field_by_table: Mapping[str, str] | None = None,
        metric_by_table: Mapping[str, str] | None = None,
        schema: str | None = None,
        default_top_k: int = RUNTIME_DEFAULTS.vector_top_k,
        max_discovery_sources: int = RUNTIME_DEFAULTS.max_discovery_sources,
        max_fields_per_collection: int = RUNTIME_DEFAULTS.max_fields_per_collection,
        remote: bool = True,
    ) -> tuple[str, ...]:
        """Register caller-owned PostgreSQL/pgvector Engine."""

        return await self.aadd_native_vector_store(
            "pgvector",
            engine,
            embed_query,
            database_name=database_name,
            namespace=namespace,
            collections=collections,
            backend_options={
                "tables": (
                    tables
                    if tables is not None
                    else (
                        None
                        if collections is None
                        else tuple(sorted(collections))
                    )
                ),
                "vector_field_by_table": vector_field_by_table,
                "metric_by_table": metric_by_table,
                "schema": schema,
                "max_discovery_sources": max_discovery_sources,
                "max_fields_per_collection": max_fields_per_collection,
            },
            default_top_k=default_top_k,
            remote=remote,
            max_discovery_sources=max_discovery_sources,
            max_fields_per_collection=max_fields_per_collection,
        )

    def add_pgvector_store(
        self,
        engine: Any,
        embed_query: Any,
        *,
        database_name: str = "pgvector",
        namespace: str | None = None,
        collections: set[str] | tuple[str, ...] | list[str] | None = None,
        tables: Sequence[str] | None = None,
        vector_field_by_table: Mapping[str, str] | None = None,
        metric_by_table: Mapping[str, str] | None = None,
        schema: str | None = None,
        default_top_k: int = RUNTIME_DEFAULTS.vector_top_k,
        max_discovery_sources: int = RUNTIME_DEFAULTS.max_discovery_sources,
        max_fields_per_collection: int = RUNTIME_DEFAULTS.max_fields_per_collection,
        remote: bool = True,
    ) -> tuple[str, ...]:
        return _run_sync(
            lambda: self.aadd_pgvector_store(
                engine,
                embed_query,
                database_name=database_name,
                namespace=namespace,
                collections=collections,
                tables=tables,
                vector_field_by_table=vector_field_by_table,
                metric_by_table=metric_by_table,
                schema=schema,
                default_top_k=default_top_k,
                max_discovery_sources=max_discovery_sources,
                max_fields_per_collection=max_fields_per_collection,
                remote=remote,
            )
        )

    async def aadd_graph_store(
        self,
        backend: Any,
        *,
        database_name: str,
        namespace: str | None = None,
        graphs: set[str] | tuple[str, ...] | list[str] | None = None,
        default_limit: int = RUNTIME_DEFAULTS.collection_limit,
        default_max_hops: int = RUNTIME_DEFAULTS.graph_max_hops,
        remote: bool = True,
        max_discovery_sources: int = RUNTIME_DEFAULTS.max_discovery_sources,
        max_schema_items_per_graph: int = 256,
        max_generated_bytes: int = RUNTIME_DEFAULTS.max_generated_bytes,
    ) -> tuple[str, ...]:
        """Discover and register a caller-owned property-graph or RDF backend."""

        from .adapters.graph_store import introspect_graph_backend

        bindings = await introspect_graph_backend(
            backend,
            database_name=database_name,
            namespace=namespace,
            graphs=graphs,
            default_limit=default_limit,
            default_max_hops=default_max_hops,
            remote=remote,
            offload_sync_backend=remote,
            max_discovery_sources=max_discovery_sources,
            max_schema_items_per_graph=max_schema_items_per_graph,
            max_generated_bytes=max_generated_bytes,
        )
        async def refresh_binding(
            tool_key: str,
        ) -> tuple[ToolSpec, BoundEndpointInvoker, bool]:
            refreshed = await introspect_graph_backend(
                backend,
                database_name=database_name,
                namespace=namespace,
                graphs=graphs,
                default_limit=default_limit,
                default_max_hops=default_max_hops,
                remote=remote,
                max_discovery_sources=max_discovery_sources,
                max_schema_items_per_graph=max_schema_items_per_graph,
                max_generated_bytes=max_generated_bytes,
            )
            match = next((item for item in refreshed if item.tool.key == tool_key), None)
            if match is None:
                raise SchemaSourceError(
                    f"native graph capability {tool_key!r} disappeared during refresh"
                )
            return match.tool, match.invoker, False
        return self._register_refreshable_bound_batch(
            bindings,
            refresh_binding=refresh_binding,
        )

    def add_graph_store(
        self,
        backend: Any,
        *,
        database_name: str,
        namespace: str | None = None,
        graphs: set[str] | tuple[str, ...] | list[str] | None = None,
        default_limit: int = RUNTIME_DEFAULTS.collection_limit,
        default_max_hops: int = RUNTIME_DEFAULTS.graph_max_hops,
        remote: bool = True,
        max_discovery_sources: int = RUNTIME_DEFAULTS.max_discovery_sources,
        max_schema_items_per_graph: int = 256,
        max_generated_bytes: int = RUNTIME_DEFAULTS.max_generated_bytes,
    ) -> tuple[str, ...]:
        """Synchronous wrapper for :meth:`aadd_graph_store`."""

        return _run_sync(
            lambda: self.aadd_graph_store(
                backend,
                database_name=database_name,
                namespace=namespace,
                graphs=graphs,
                default_limit=default_limit,
                default_max_hops=default_max_hops,
                remote=remote,
                max_discovery_sources=max_discovery_sources,
                max_schema_items_per_graph=max_schema_items_per_graph,
                max_generated_bytes=max_generated_bytes,
            )
        )

    async def aadd_record_store(
        self,
        backend: Any,
        *,
        database_name: str,
        namespace: str | None = None,
        sources: set[str] | tuple[str, ...] | list[str] | None = None,
        default_limit: int = RUNTIME_DEFAULTS.collection_limit,
        remote: bool = True,
        max_discovery_sources: int = RUNTIME_DEFAULTS.max_discovery_sources,
        max_fields_per_source: int = 256,
        max_generated_bytes: int = RUNTIME_DEFAULTS.max_generated_bytes,
    ) -> tuple[str, ...]:
        """Discover and register document/search/key-value/time-series sources."""

        from .adapters.record_store import introspect_record_backend

        bindings = await introspect_record_backend(
            backend,
            database_name=database_name,
            namespace=namespace,
            sources=sources,
            default_limit=default_limit,
            remote=remote,
            offload_sync_backend=remote,
            max_discovery_sources=max_discovery_sources,
            max_fields_per_source=max_fields_per_source,
            max_generated_bytes=max_generated_bytes,
        )
        async def refresh_binding(
            tool_key: str,
        ) -> tuple[ToolSpec, BoundEndpointInvoker, bool]:
            refreshed = await introspect_record_backend(
                backend,
                database_name=database_name,
                namespace=namespace,
                sources=sources,
                default_limit=default_limit,
                remote=remote,
                max_discovery_sources=max_discovery_sources,
                max_fields_per_source=max_fields_per_source,
                max_generated_bytes=max_generated_bytes,
            )
            match = next((item for item in refreshed if item.tool.key == tool_key), None)
            if match is None:
                raise SchemaSourceError(
                    f"native record capability {tool_key!r} disappeared during refresh"
                )
            return match.tool, match.invoker, False
        return self._register_refreshable_bound_batch(
            bindings,
            refresh_binding=refresh_binding,
        )

    def add_record_store(
        self,
        backend: Any,
        *,
        database_name: str,
        namespace: str | None = None,
        sources: set[str] | tuple[str, ...] | list[str] | None = None,
        default_limit: int = RUNTIME_DEFAULTS.collection_limit,
        remote: bool = True,
        max_discovery_sources: int = RUNTIME_DEFAULTS.max_discovery_sources,
        max_fields_per_source: int = 256,
        max_generated_bytes: int = RUNTIME_DEFAULTS.max_generated_bytes,
    ) -> tuple[str, ...]:
        """Synchronous wrapper for :meth:`aadd_record_store`."""

        return _run_sync(
            lambda: self.aadd_record_store(
                backend,
                database_name=database_name,
                namespace=namespace,
                sources=sources,
                default_limit=default_limit,
                remote=remote,
                max_discovery_sources=max_discovery_sources,
                max_fields_per_source=max_fields_per_source,
                max_generated_bytes=max_generated_bytes,
            )
        )

    async def aadd_native_graph_store(
        self,
        backend_name: str,
        resource: Any,
        *,
        database_name: str,
        namespace: str | None = None,
        graphs: set[str] | tuple[str, ...] | list[str] | None = None,
        backend_options: Mapping[str, Any] | None = None,
        default_limit: int = RUNTIME_DEFAULTS.collection_limit,
        default_max_hops: int = RUNTIME_DEFAULTS.graph_max_hops,
        remote: bool = True,
        max_discovery_sources: int = RUNTIME_DEFAULTS.max_discovery_sources,
        max_schema_items_per_graph: int = 256,
        max_generated_bytes: int = RUNTIME_DEFAULTS.max_generated_bytes,
    ) -> tuple[str, ...]:
        """Register a native graph backend through the descriptor registry."""

        from .native_registration import build_native_graph_backend

        backend = build_native_graph_backend(
            backend_name,
            resource,
            **dict(backend_options or {}),
        )
        return await self.aadd_graph_store(
            backend,
            database_name=database_name,
            namespace=namespace,
            graphs=graphs,
            default_limit=default_limit,
            default_max_hops=default_max_hops,
            remote=remote,
            max_discovery_sources=max_discovery_sources,
            max_schema_items_per_graph=max_schema_items_per_graph,
            max_generated_bytes=max_generated_bytes,
        )

    def add_native_graph_store(
        self,
        backend_name: str,
        resource: Any,
        *,
        database_name: str,
        namespace: str | None = None,
        graphs: set[str] | tuple[str, ...] | list[str] | None = None,
        backend_options: Mapping[str, Any] | None = None,
        default_limit: int = RUNTIME_DEFAULTS.collection_limit,
        default_max_hops: int = RUNTIME_DEFAULTS.graph_max_hops,
        remote: bool = True,
        max_discovery_sources: int = RUNTIME_DEFAULTS.max_discovery_sources,
        max_schema_items_per_graph: int = 256,
        max_generated_bytes: int = RUNTIME_DEFAULTS.max_generated_bytes,
    ) -> tuple[str, ...]:
        """Synchronous wrapper for :meth:`aadd_native_graph_store`."""

        return _run_sync(
            lambda: self.aadd_native_graph_store(
                backend_name,
                resource,
                database_name=database_name,
                namespace=namespace,
                graphs=graphs,
                backend_options=backend_options,
                default_limit=default_limit,
                default_max_hops=default_max_hops,
                remote=remote,
                max_discovery_sources=max_discovery_sources,
                max_schema_items_per_graph=max_schema_items_per_graph,
                max_generated_bytes=max_generated_bytes,
            )
        )

    async def aadd_neo4j_graph(
        self,
        driver: Any,
        *,
        database: str,
        graph_name: str | None = None,
        namespace: str | None = None,
        graphs: set[str] | tuple[str, ...] | list[str] | None = None,
        default_limit: int = RUNTIME_DEFAULTS.collection_limit,
        default_max_hops: int = RUNTIME_DEFAULTS.graph_max_hops,
        remote: bool = True,
    ) -> tuple[str, ...]:
        """Register a caller-owned Neo4j driver through the bounded graph contract."""

        return await self.aadd_native_graph_store(
            "neo4j",
            driver,
            database_name=database,
            namespace=namespace,
            graphs=graphs,
            backend_options={
                "database": database,
                "graph_name": graph_name,
            },
            default_limit=default_limit,
            default_max_hops=default_max_hops,
            remote=remote,
        )

    def add_neo4j_graph(
        self,
        driver: Any,
        *,
        database: str,
        graph_name: str | None = None,
        namespace: str | None = None,
        graphs: set[str] | tuple[str, ...] | list[str] | None = None,
        default_limit: int = RUNTIME_DEFAULTS.collection_limit,
        default_max_hops: int = RUNTIME_DEFAULTS.graph_max_hops,
        remote: bool = True,
    ) -> tuple[str, ...]:
        """Synchronous wrapper for :meth:`aadd_neo4j_graph`."""

        return _run_sync(
            lambda: self.aadd_neo4j_graph(
                driver,
                database=database,
                graph_name=graph_name,
                namespace=namespace,
                graphs=graphs,
                default_limit=default_limit,
                default_max_hops=default_max_hops,
                remote=remote,
            )
        )

    async def aadd_falkordb_graph(
        self,
        client: Any,
        *,
        database_name: str = "falkordb",
        namespace: str | None = None,
        graphs: set[str] | tuple[str, ...] | list[str] | None = None,
        default_limit: int = RUNTIME_DEFAULTS.collection_limit,
        default_max_hops: int = RUNTIME_DEFAULTS.graph_max_hops,
        remote: bool = True,
    ) -> tuple[str, ...]:
        """Register a caller-owned FalkorDB client through the bounded graph contract."""

        graph_names = None if graphs is None else tuple(sorted(graphs))
        return await self.aadd_native_graph_store(
            "falkordb",
            client,
            database_name=database_name,
            namespace=namespace,
            graphs=graphs,
            backend_options={"graphs": graph_names},
            default_limit=default_limit,
            default_max_hops=default_max_hops,
            remote=remote,
        )

    def add_falkordb_graph(
        self,
        client: Any,
        *,
        database_name: str = "falkordb",
        namespace: str | None = None,
        graphs: set[str] | tuple[str, ...] | list[str] | None = None,
        default_limit: int = RUNTIME_DEFAULTS.collection_limit,
        default_max_hops: int = RUNTIME_DEFAULTS.graph_max_hops,
        remote: bool = True,
    ) -> tuple[str, ...]:
        """Synchronous wrapper for :meth:`aadd_falkordb_graph`."""

        return _run_sync(
            lambda: self.aadd_falkordb_graph(
                client,
                database_name=database_name,
                namespace=namespace,
                graphs=graphs,
                default_limit=default_limit,
                default_max_hops=default_max_hops,
                remote=remote,
            )
        )

    async def aadd_neptune_graph(
        self,
        client: Any,
        *,
        graph_name: str = "neptune",
        graph_identifier: str | None = None,
        database_name: str = "neptune",
        namespace: str | None = None,
        default_limit: int = RUNTIME_DEFAULTS.collection_limit,
        default_max_hops: int = RUNTIME_DEFAULTS.graph_max_hops,
        remote: bool = True,
    ) -> tuple[str, ...]:
        """Register a caller-owned Neptune Database/Analytics client."""

        return await self.aadd_native_graph_store(
            "neptune",
            client,
            database_name=database_name,
            namespace=namespace,
            graphs={graph_name},
            backend_options={
                "graph_name": graph_name,
                "graph_identifier": graph_identifier,
            },
            default_limit=default_limit,
            default_max_hops=default_max_hops,
            remote=remote,
        )

    def add_neptune_graph(
        self,
        client: Any,
        *,
        graph_name: str = "neptune",
        graph_identifier: str | None = None,
        database_name: str = "neptune",
        namespace: str | None = None,
        default_limit: int = RUNTIME_DEFAULTS.collection_limit,
        default_max_hops: int = RUNTIME_DEFAULTS.graph_max_hops,
        remote: bool = True,
    ) -> tuple[str, ...]:
        """Synchronous wrapper for :meth:`aadd_neptune_graph`."""

        return _run_sync(
            lambda: self.aadd_neptune_graph(
                client,
                graph_name=graph_name,
                graph_identifier=graph_identifier,
                database_name=database_name,
                namespace=namespace,
                default_limit=default_limit,
                default_max_hops=default_max_hops,
                remote=remote,
            )
        )

    async def aadd_arango_graph(
        self,
        database: Any,
        *,
        database_name: str = "arangodb",
        namespace: str | None = None,
        graphs: set[str] | tuple[str, ...] | list[str] | None = None,
        default_limit: int = RUNTIME_DEFAULTS.collection_limit,
        default_max_hops: int = RUNTIME_DEFAULTS.graph_max_hops,
        remote: bool = True,
    ) -> tuple[str, ...]:
        """Register a caller-owned python-arango Database wrapper."""

        return await self.aadd_native_graph_store(
            "arangodb",
            database,
            database_name=database_name,
            namespace=namespace,
            graphs=graphs,
            default_limit=default_limit,
            default_max_hops=default_max_hops,
            remote=remote,
        )

    def add_arango_graph(
        self,
        database: Any,
        *,
        database_name: str = "arangodb",
        namespace: str | None = None,
        graphs: set[str] | tuple[str, ...] | list[str] | None = None,
        default_limit: int = RUNTIME_DEFAULTS.collection_limit,
        default_max_hops: int = RUNTIME_DEFAULTS.graph_max_hops,
        remote: bool = True,
    ) -> tuple[str, ...]:
        """Synchronous wrapper for :meth:`aadd_arango_graph`."""

        return _run_sync(
            lambda: self.aadd_arango_graph(
                database,
                database_name=database_name,
                namespace=namespace,
                graphs=graphs,
                default_limit=default_limit,
                default_max_hops=default_max_hops,
                remote=remote,
            )
        )

    async def aadd_sparql_graph(
        self,
        client: Any,
        *,
        endpoint: str,
        graph_name: str = "sparql",
        database_name: str = "sparql",
        namespace: str | None = None,
        default_limit: int = RUNTIME_DEFAULTS.collection_limit,
        remote: bool = True,
    ) -> tuple[str, ...]:
        """Register a caller-owned HTTP client for a SPARQL 1.1 query endpoint."""

        return await self.aadd_native_graph_store(
            "sparql",
            client,
            database_name=database_name,
            namespace=namespace,
            graphs={graph_name},
            backend_options={
                "endpoint": endpoint,
                "graph_name": graph_name,
            },
            default_limit=default_limit,
            default_max_hops=RUNTIME_DEFAULTS.graph_max_hops,
            remote=remote,
        )

    def add_sparql_graph(
        self,
        client: Any,
        *,
        endpoint: str,
        graph_name: str = "sparql",
        database_name: str = "sparql",
        namespace: str | None = None,
        default_limit: int = RUNTIME_DEFAULTS.collection_limit,
        remote: bool = True,
    ) -> tuple[str, ...]:
        """Synchronous wrapper for :meth:`aadd_sparql_graph`."""

        return _run_sync(
            lambda: self.aadd_sparql_graph(
                client,
                endpoint=endpoint,
                graph_name=graph_name,
                database_name=database_name,
                namespace=namespace,
                default_limit=default_limit,
                remote=remote,
            )
        )

    async def aadd_native_record_store(
        self,
        backend_name: str,
        resource: Any,
        *,
        database_name: str,
        namespace: str | None = None,
        sources: set[str] | tuple[str, ...] | list[str] | None = None,
        backend_options: Mapping[str, Any] | None = None,
        default_limit: int = RUNTIME_DEFAULTS.collection_limit,
        remote: bool = True,
        max_discovery_sources: int = RUNTIME_DEFAULTS.max_discovery_sources,
        max_fields_per_source: int = 256,
        max_generated_bytes: int = RUNTIME_DEFAULTS.max_generated_bytes,
    ) -> tuple[str, ...]:
        """Register a native record backend through the descriptor registry."""

        from .native_registration import build_native_record_backend

        backend = build_native_record_backend(
            backend_name,
            resource,
            **dict(backend_options or {}),
        )
        return await self.aadd_record_store(
            backend,
            database_name=database_name,
            namespace=namespace,
            sources=sources,
            default_limit=default_limit,
            remote=remote,
            max_discovery_sources=max_discovery_sources,
            max_fields_per_source=max_fields_per_source,
            max_generated_bytes=max_generated_bytes,
        )

    def add_native_record_store(
        self,
        backend_name: str,
        resource: Any,
        *,
        database_name: str,
        namespace: str | None = None,
        sources: set[str] | tuple[str, ...] | list[str] | None = None,
        backend_options: Mapping[str, Any] | None = None,
        default_limit: int = RUNTIME_DEFAULTS.collection_limit,
        remote: bool = True,
        max_discovery_sources: int = RUNTIME_DEFAULTS.max_discovery_sources,
        max_fields_per_source: int = 256,
        max_generated_bytes: int = RUNTIME_DEFAULTS.max_generated_bytes,
    ) -> tuple[str, ...]:
        """Synchronous wrapper for :meth:`aadd_native_record_store`."""

        return _run_sync(
            lambda: self.aadd_native_record_store(
                backend_name,
                resource,
                database_name=database_name,
                namespace=namespace,
                sources=sources,
                backend_options=backend_options,
                default_limit=default_limit,
                remote=remote,
                max_discovery_sources=max_discovery_sources,
                max_fields_per_source=max_fields_per_source,
                max_generated_bytes=max_generated_bytes,
            )
        )

    async def aadd_mongodb_record_store(
        self,
        database: Any,
        *,
        database_name: str = "mongodb",
        namespace: str | None = None,
        collections: tuple[str, ...] | list[str] | None = None,
        text_search_collections: tuple[str, ...] | list[str] = (),
        time_field_by_collection: Mapping[str, str] | None = None,
        default_limit: int = RUNTIME_DEFAULTS.collection_limit,
        remote: bool = True,
    ) -> tuple[str, ...]:
        """Register a caller-owned PyMongo Database through the bounded record contract."""

        return await self.aadd_native_record_store(
            "mongodb",
            database,
            database_name=database_name,
            namespace=namespace,
            sources=None if collections is None else set(collections),
            backend_options={
                "collections": collections,
                "text_search_collections": text_search_collections,
                "time_field_by_collection": time_field_by_collection,
            },
            default_limit=default_limit,
            remote=remote,
        )

    def add_mongodb_record_store(
        self,
        database: Any,
        *,
        database_name: str = "mongodb",
        namespace: str | None = None,
        collections: tuple[str, ...] | list[str] | None = None,
        text_search_collections: tuple[str, ...] | list[str] = (),
        time_field_by_collection: Mapping[str, str] | None = None,
        default_limit: int = RUNTIME_DEFAULTS.collection_limit,
        remote: bool = True,
    ) -> tuple[str, ...]:
        """Synchronous wrapper for :meth:`aadd_mongodb_record_store`."""

        return _run_sync(
            lambda: self.aadd_mongodb_record_store(
                database,
                database_name=database_name,
                namespace=namespace,
                collections=collections,
                text_search_collections=text_search_collections,
                time_field_by_collection=time_field_by_collection,
                default_limit=default_limit,
                remote=remote,
            )
        )

    async def aadd_elasticsearch_record_store(
        self,
        client: Any,
        *,
        database_name: str = "elasticsearch",
        namespace: str | None = None,
        indices: tuple[str, ...] | list[str] | None = None,
        time_field_by_index: Mapping[str, str] | None = None,
        default_limit: int = RUNTIME_DEFAULTS.collection_limit,
        remote: bool = True,
    ) -> tuple[str, ...]:
        """Register a caller-owned Elasticsearch client."""

        return await self.aadd_native_record_store(
            "elasticsearch",
            client,
            database_name=database_name,
            namespace=namespace,
            sources=None if indices is None else set(indices),
            backend_options={
                "indices": indices,
                "time_field_by_index": time_field_by_index,
                "vendor": "elasticsearch",
            },
            default_limit=default_limit,
            remote=remote,
        )

    def add_elasticsearch_record_store(
        self,
        client: Any,
        **kwargs: Any,
    ) -> tuple[str, ...]:
        """Synchronous wrapper for :meth:`aadd_elasticsearch_record_store`."""

        return _run_sync(lambda: self.aadd_elasticsearch_record_store(client, **kwargs))

    async def aadd_opensearch_record_store(
        self,
        client: Any,
        *,
        database_name: str = "opensearch",
        namespace: str | None = None,
        indices: tuple[str, ...] | list[str] | None = None,
        time_field_by_index: Mapping[str, str] | None = None,
        default_limit: int = RUNTIME_DEFAULTS.collection_limit,
        remote: bool = True,
    ) -> tuple[str, ...]:
        """Register a caller-owned OpenSearch client."""

        return await self.aadd_native_record_store(
            "opensearch",
            client,
            database_name=database_name,
            namespace=namespace,
            sources=None if indices is None else set(indices),
            backend_options={
                "indices": indices,
                "time_field_by_index": time_field_by_index,
                "vendor": "opensearch",
            },
            default_limit=default_limit,
            remote=remote,
        )

    def add_opensearch_record_store(
        self,
        client: Any,
        **kwargs: Any,
    ) -> tuple[str, ...]:
        """Synchronous wrapper for :meth:`aadd_opensearch_record_store`."""

        return _run_sync(lambda: self.aadd_opensearch_record_store(client, **kwargs))

    async def aadd_dynamodb_record_store(
        self,
        client: Any,
        *,
        database_name: str = "dynamodb",
        namespace: str | None = None,
        tables: tuple[str, ...] | list[str] | None = None,
        time_field_by_table: Mapping[str, str] | None = None,
        default_limit: int = RUNTIME_DEFAULTS.collection_limit,
        remote: bool = True,
    ) -> tuple[str, ...]:
        """Register a caller-owned low-level boto3 DynamoDB client."""

        return await self.aadd_native_record_store(
            "dynamodb",
            client,
            database_name=database_name,
            namespace=namespace,
            sources=None if tables is None else set(tables),
            backend_options={
                "tables": tables,
                "time_field_by_table": time_field_by_table,
            },
            default_limit=default_limit,
            remote=remote,
        )

    def add_dynamodb_record_store(
        self,
        client: Any,
        **kwargs: Any,
    ) -> tuple[str, ...]:
        """Synchronous wrapper for :meth:`aadd_dynamodb_record_store`."""

        return _run_sync(lambda: self.aadd_dynamodb_record_store(client, **kwargs))

    async def aadd_cosmos_record_store(
        self,
        database: Any,
        *,
        database_name: str = "cosmos",
        namespace: str | None = None,
        containers: tuple[str, ...] | list[str] | None = None,
        time_field_by_container: Mapping[str, str] | None = None,
        default_limit: int = RUNTIME_DEFAULTS.collection_limit,
        remote: bool = True,
    ) -> tuple[str, ...]:
        """Register a caller-owned Azure Cosmos DB DatabaseProxy."""

        return await self.aadd_native_record_store(
            "cosmos",
            database,
            database_name=database_name,
            namespace=namespace,
            sources=None if containers is None else set(containers),
            backend_options={
                "containers": containers,
                "time_field_by_container": time_field_by_container,
            },
            default_limit=default_limit,
            remote=remote,
        )

    def add_cosmos_record_store(
        self,
        database: Any,
        **kwargs: Any,
    ) -> tuple[str, ...]:
        """Synchronous wrapper for :meth:`aadd_cosmos_record_store`."""

        return _run_sync(lambda: self.aadd_cosmos_record_store(database, **kwargs))

    async def aadd_couchbase_record_store(
        self,
        cluster: Any,
        *,
        database_name: str = "couchbase",
        namespace: str | None = None,
        keyspaces: tuple[str, ...] | list[str] | None = None,
        time_field_by_source: Mapping[str, str] | None = None,
        default_limit: int = RUNTIME_DEFAULTS.collection_limit,
        remote: bool = True,
    ) -> tuple[str, ...]:
        """Register a caller-owned Couchbase Cluster."""

        return await self.aadd_native_record_store(
            "couchbase",
            cluster,
            database_name=database_name,
            namespace=namespace,
            sources=None if keyspaces is None else set(keyspaces),
            backend_options={
                "keyspaces": keyspaces,
                "time_field_by_source": time_field_by_source,
            },
            default_limit=default_limit,
            remote=remote,
        )

    def add_couchbase_record_store(
        self,
        cluster: Any,
        **kwargs: Any,
    ) -> tuple[str, ...]:
        """Synchronous wrapper for :meth:`aadd_couchbase_record_store`."""

        return _run_sync(lambda: self.aadd_couchbase_record_store(cluster, **kwargs))

    async def aadd_clickhouse_record_store(
        self,
        client: Any,
        *,
        database_name: str = "clickhouse",
        namespace: str | None = None,
        tables: tuple[str, ...] | list[str] | None = None,
        time_field_by_table: Mapping[str, str] | None = None,
        default_limit: int = RUNTIME_DEFAULTS.collection_limit,
        remote: bool = True,
    ) -> tuple[str, ...]:
        """Register a caller-owned clickhouse-connect client."""

        return await self.aadd_native_record_store(
            "clickhouse",
            client,
            database_name=database_name,
            namespace=namespace,
            sources=None if tables is None else set(tables),
            backend_options={
                "tables": tables,
                "time_field_by_table": time_field_by_table,
            },
            default_limit=default_limit,
            remote=remote,
        )

    def add_clickhouse_record_store(
        self,
        client: Any,
        **kwargs: Any,
    ) -> tuple[str, ...]:
        """Synchronous wrapper for :meth:`aadd_clickhouse_record_store`."""

        return _run_sync(lambda: self.aadd_clickhouse_record_store(client, **kwargs))

    async def aadd_influxdb_record_store(
        self,
        query_api: Any,
        *,
        bucket: str,
        org: str,
        database_name: str = "influxdb",
        namespace: str | None = None,
        measurements: tuple[str, ...] | list[str] | None = None,
        default_start: str = "-30d",
        default_limit: int = RUNTIME_DEFAULTS.collection_limit,
        remote: bool = True,
    ) -> tuple[str, ...]:
        """Register a caller-owned InfluxDB QueryApi."""

        return await self.aadd_native_record_store(
            "influxdb",
            query_api,
            database_name=database_name,
            namespace=namespace,
            sources=None if measurements is None else set(measurements),
            backend_options={
                "bucket": bucket,
                "org": org,
                "measurements": measurements,
                "default_start": default_start,
            },
            default_limit=default_limit,
            remote=remote,
        )

    def add_influxdb_record_store(
        self,
        query_api: Any,
        **kwargs: Any,
    ) -> tuple[str, ...]:
        """Synchronous wrapper for :meth:`aadd_influxdb_record_store`."""

        return _run_sync(lambda: self.aadd_influxdb_record_store(query_api, **kwargs))

    def amend_capability(self, tool_key: str, amended: ToolSpec) -> str:
        """Declare or annotate the result contract of an already registered capability.

        Trusted local code may add output-field declarations and annotate their
        meaning: semantic IDs, aliases, paths, units, normalization, qualifiers,
        identifier flags, provenance and licence. It may not change execution
        identity or validation shape; see `amendment.validate_amendment`.

        This is more than cosmetic annotation. Accepted aspects can change what
        the caller receives and which routes are reachable:

        - `path` / `result_path` on an existing field re-point which value a
          sanctioned field name resolves to. Projection is the redaction
          boundary for a field-selecting call, so amending these can move
          previously unprojected response content into the answer under the
          same field name.
        - `unit` and `unit_normalization` change how a numeric value is
          rescaled before it reaches the caller, on the result path (see
          `RegistryExecutor._normalize_projected_units` in `executor.py`).
        - `source_type`, `license`, and `unit` feed evidence availability
          (`evidence.py`), which the executor enforces as a hard gate. An
          amendment can unblock an evidence-gated route by declaration alone,
          with no change to what the underlying source actually returns.
        - Declaring a semantic ID or unit can also change routing outright: it
          may make a cross-provider fallback compatible that previously was
          not.

        Because of this, `amend_capability` is trusted local code, at the same
        grade as `RegistryExecutor.bind()`. It must never be reachable from a
        decision backend, remote content, or model output.

        The execution binding is carried across the amendment, so a capability
        SchemaRouter imported on the application's behalf stays executable. The
        invoker is never exposed to the caller.

        If the capability was already bound and re-stamping the binding fails
        — only possible if another writer replaced the registered spec between
        validation and this call, e.g. a concurrent thread or another process
        on a shared registry — this raises `BindingDriftError` immediately
        instead of returning a key whose binding will only be discovered stale
        at execution time. The amendment itself is still registered; call
        `RegistryExecutor.bind()` again to recover.
        """
        expected_version = self.registry.version
        current = self.registry.get(tool_key)
        amended = prepare_amended_capability(current, amended)
        was_bound = tool_key in self.executor.bound_keys()
        key = replace_if_current(
            self.registry,
            amended,
            expected_fingerprint=current.fingerprint,
            expected_version=expected_version,
        )
        restamped = self.executor.restamp_binding(key, amended.fingerprint)
        if was_bound and not restamped:
            raise BindingDriftError(
                f"amendment of {key!r} was registered, but its existing binding "
                "could not be re-stamped because the registered contract changed "
                "concurrently; the binding is stale until it is bound again"
            )
        self.health_monitor.transition_tool_contract(
            key,
            expected_old_fingerprint=current.fingerprint,
            expected_new_fingerprint=amended.fingerprint,
        )
        return key

    @staticmethod
    def _persisted_adapter(tool: ToolSpec) -> str | None:
        return persisted_adapter(tool)

    def _build_existing_invoker(
        self,
        tool: ToolSpec,
        config: TrustedBindingConfig,
    ) -> BoundEndpointInvoker:
        return build_persisted_invoker(
            tool,
            config,
            RebindingContext(
                http_client=self.loader.http_client,
                network_policy=self.loader.network_policy,
            ),
        )

    def bind_existing(
        self,
        tool_key: str,
        config: TrustedBindingConfig,
        *,
        expected_fingerprint: str | None = None,
    ) -> BindingReconciliationItem:
        """Bind one persisted capability without mutating its schema document."""

        tool = self.registry.get(tool_key)
        adapter = self._persisted_adapter(tool)
        if (
            expected_fingerprint is not None
            and tool.fingerprint != expected_fingerprint
        ):
            return BindingReconciliationItem(
                tool=tool_key,
                adapter=adapter,
                fingerprint=tool.fingerprint,
                status="incompatible",
                error_type="BindingDriftError",
            )

        if config.intentionally_unbound:
            current = self.registry.get(tool_key)
            if current.fingerprint != tool.fingerprint:
                return BindingReconciliationItem(
                    tool=tool_key,
                    adapter=adapter,
                    fingerprint=tool.fingerprint,
                    status="incompatible",
                    error_type="BindingDriftError",
                )
            if (
                self.executor.binding_status_for_contract(
                    tool_key,
                    tool.fingerprint,
                )
                == "stale"
            ):
                return BindingReconciliationItem(
                    tool=tool_key,
                    adapter=adapter,
                    fingerprint=tool.fingerprint,
                    status="incompatible",
                    error_type="BindingDriftError",
                )
            self.executor.unbind(tool_key)
            return BindingReconciliationItem(
                tool=tool_key,
                adapter=adapter,
                fingerprint=tool.fingerprint,
                status="intentionally_unbound",
            )

        try:
            invoker = self._build_existing_invoker(tool, config)
        except LookupError:
            return BindingReconciliationItem(
                tool=tool_key,
                adapter=adapter,
                fingerprint=tool.fingerprint,
                status="missing_trusted_config",
            )
        except (TypeError, ValueError) as exc:
            return BindingReconciliationItem(
                tool=tool_key,
                adapter=adapter,
                fingerprint=tool.fingerprint,
                status="incompatible",
                error_type=type(exc).__name__,
            )
        except Exception as exc:
            return BindingReconciliationItem(
                tool=tool_key,
                adapter=adapter,
                fingerprint=tool.fingerprint,
                status="failed",
                error_type=type(exc).__name__,
            )

        try:
            self.executor.bind(
                tool_key,
                invoker,
                expected_fingerprint=tool.fingerprint,
            )
        except BindingDriftError:
            return BindingReconciliationItem(
                tool=tool_key,
                adapter=adapter,
                fingerprint=tool.fingerprint,
                status="incompatible",
                error_type="BindingDriftError",
            )
        except Exception as exc:
            return BindingReconciliationItem(
                tool=tool_key,
                adapter=adapter,
                fingerprint=tool.fingerprint,
                status="failed",
                error_type=type(exc).__name__,
            )

        return BindingReconciliationItem(
            tool=tool_key,
            adapter=adapter,
            fingerprint=tool.fingerprint,
            status="ready",
        )

    def rehydrate_bindings(
        self,
        resolver: BindingResolver,
        *,
        required_tools: Sequence[str] | None = None,
        strict: bool = False,
    ) -> BindingReconciliationReport:
        """Re-establish trusted process-local bindings for persisted registry state."""

        snapshots = self.registry.tools()
        known = {tool.key for tool in snapshots}
        required = set(known if required_tools is None else required_tools)
        unknown_required = sorted(required - known)
        if unknown_required:
            raise RegistrationError(
                "required persisted capabilities are not registered: "
                + ", ".join(unknown_required)
            )

        items: list[BindingReconciliationItem] = []
        for tool in snapshots:
            if self.executor.is_binding_ready_for_contract(
                tool.key,
                tool.fingerprint,
            ):
                items.append(
                    BindingReconciliationItem(
                        tool=tool.key,
                        adapter=self._persisted_adapter(tool),
                        fingerprint=tool.fingerprint,
                        status="ready",
                    )
                )
                continue
            try:
                config = resolver(tool.model_copy(deep=True))
            except Exception as exc:
                items.append(
                    BindingReconciliationItem(
                        tool=tool.key,
                        adapter=self._persisted_adapter(tool),
                        fingerprint=tool.fingerprint,
                        status="failed",
                        error_type=type(exc).__name__,
                    )
                )
                continue

            if config is None:
                if self.executor.is_binding_ready_for_contract(
                    tool.key,
                    tool.fingerprint,
                ):
                    item = BindingReconciliationItem(
                        tool=tool.key,
                        adapter=self._persisted_adapter(tool),
                        fingerprint=tool.fingerprint,
                        status="ready",
                    )
                else:
                    item = BindingReconciliationItem(
                        tool=tool.key,
                        adapter=self._persisted_adapter(tool),
                        fingerprint=tool.fingerprint,
                        status="missing_trusted_config",
                    )
            elif not isinstance(config, TrustedBindingConfig):
                item = BindingReconciliationItem(
                    tool=tool.key,
                    adapter=self._persisted_adapter(tool),
                    fingerprint=tool.fingerprint,
                    status="incompatible",
                    error_type="InvalidBindingConfig",
                )
            else:
                item = self.bind_existing(
                    tool.key,
                    config,
                    expected_fingerprint=tool.fingerprint,
                )
            items.append(item)

        report = BindingReconciliationReport(items=items)
        if strict:
            failed_required = [
                item
                for item in items
                if item.tool in required and item.status != "ready"
            ]
            if failed_required:
                details = ", ".join(
                    f"{item.tool}={item.status}"
                    for item in failed_required
                )
                raise BindingReconciliationError(
                    "startup binding reconciliation left required capabilities "
                    f"unready: {details}",
                    report,
                )
        return report

    def register_adapter(
        self,
        adapter: SourceAdapter,
        *,
        replace: bool = False,
    ) -> None:
        self.loader.register_adapter(adapter, replace=replace)

    @property
    def adapter_registry(self) -> AdapterRegistry:
        return self.loader.adapters

    @property
    def provider_profile_registry(self) -> ProviderProfileRegistry:
        """Return the process-local provider profile registry."""

        return self.provider_profiles

    def register_provider_profile(
        self,
        profile: ProviderProfile,
        *,
        replace: bool = False,
    ) -> str:
        """Register declarative provider identity metadata.

        Provider profiles contain no credentials or executable authority. Access methods
        still compile through the existing source adapters or explicit trusted bindings.
        """

        return self.provider_profiles.register(profile, replace=replace)

    def resolve_provider(
        self,
        provider: str,
        *,
        methods: set[str] | list[str] | tuple[str, ...] | None = None,
    ) -> ProviderResolution:
        """Resolve one provider identity into known access methods without network I/O."""

        return self.provider_profiles.resolve(provider, methods=methods)

    def discover_provider(
        self,
        provider: str,
        *,
        backend: ProviderDiscoveryBackend | None = None,
        limit: int = 8,
    ) -> ProviderDiscoveryProposal:
        """Propose provider identities without registering or granting authority.

        Built-in discovery is deterministic and local. A caller may supply a trusted
        discovery backend (for example one backed by an internal catalog or web search),
        but its candidates remain inert until explicitly approved or registered.
        """

        external = tuple(backend(provider)) if backend is not None else ()
        return self.provider_profiles.discover(
            provider,
            external_candidates=external,
            limit=limit,
        )

    def approve_provider_candidate(
        self,
        candidate: ProviderDiscoveryCandidate,
        *,
        expected_digest: str,
        replace: bool = False,
    ) -> str:
        """Register one reviewed discovery candidate after a digest check."""

        return self.provider_profiles.approve_discovery_candidate(
            candidate,
            expected_digest=expected_digest,
            replace=replace,
        )

    def load_provider_profile_plugins(
        self,
        *,
        allowlist: set[str] | list[str] | tuple[str, ...],
        replace: bool = False,
    ) -> tuple[str, ...]:
        """Load explicitly trusted installed provider-profile plugins."""

        return _load_provider_profile_plugins(
            self.provider_profiles,
            allowlist=allowlist,
            replace=replace,
        )

    async def _add_provider_require_all(
        self,
        provider: str,
        *,
        methods: set[str] | list[str] | tuple[str, ...] | None,
        trusted_headers_by_method: Mapping[str, Mapping[str, str]] | None,
        replace: bool,
        timeout: float,
    ) -> ProviderRegistrationResult:
        """Stage and publish one provider topology as an all-or-nothing batch."""

        resolution = self.resolve_provider(provider, methods=methods)
        profile = self.provider_profiles.get(provider)
        profile_methods = {item.method_id: item for item in profile.methods}
        headers_by_method = trusted_headers_by_method or {}
        expected_version = self.registry.version

        staged: dict[str, tuple[ToolSpec, BoundEndpointInvoker]] = {}
        outcomes: dict[str, ProviderMethodRegistration] = {}
        blocked = False

        for method in resolution.methods:
            if method.status != "available":
                outcomes[method.method_id] = ProviderMethodRegistration(
                    method_id=method.method_id,
                    kind=method.kind,
                    access_mode=method.access_mode,
                    status=method.status,
                    detail=method.detail,
                )
                blocked = True
                continue

            trusted_headers = dict(headers_by_method.get(method.method_id, {}))
            provided_header_names = {name.lower() for name in trusted_headers}
            missing_credentials = tuple(
                name
                for name in method.credential_names
                if name.lower() not in provided_header_names
            )
            if missing_credentials:
                outcomes[method.method_id] = ProviderMethodRegistration(
                    method_id=method.method_id,
                    kind=method.kind,
                    access_mode=method.access_mode,
                    status="auth_required",
                    detail=(
                        "credential header(s) required: "
                        + ", ".join(missing_credentials)
                    ),
                )
                blocked = True
                continue

            if method.url is None:
                outcomes[method.method_id] = ProviderMethodRegistration(
                    method_id=method.method_id,
                    kind=method.kind,
                    access_mode=method.access_mode,
                    status="manual_binding_required",
                    detail="method has no declarative URL source",
                )
                blocked = True
                continue

            profile_method = profile_methods[method.method_id]
            try:
                if method.kind == "http_json":
                    if profile_method.tool is None:
                        raise RegistrationError(
                            "http_json provider method has no trusted ToolSpec"
                        )
                    from .adapters.http_json import (
                        build_http_json_invoker,
                        prepare_http_json_tool,
                    )

                    tool = prepare_http_json_tool(
                        profile_method.tool,
                        base_url=method.url,
                        provider=resolution.provider_id,
                        access_mode=method.access_mode,
                    )
                    invoker = build_http_json_invoker(
                        tool,
                        base_url=method.url,
                        trusted_headers=trusted_headers or None,
                        timeout=timeout,
                        http_client=self.loader.http_client,
                        network_policy=self.loader.network_policy,
                    )
                else:
                    inspected = await self.loader.inspect(
                        method.url,
                        kind=method.kind,
                        provider=resolution.provider_id,
                        access_mode=method.access_mode,
                        trusted_headers=trusted_headers or None,
                        timeout=timeout,
                    )
                    tool = inspected.tool
                    invoker = inspected.invoker
                    if invoker is None:
                        raise RegistrationError(
                            "provider access method has no executable binding"
                        )
                staged[method.method_id] = (tool, invoker)
            except Exception as exc:  # noqa: BLE001
                outcomes[method.method_id] = ProviderMethodRegistration(
                    method_id=method.method_id,
                    kind=method.kind,
                    access_mode=method.access_mode,
                    status="unavailable",
                    error_type=type(exc).__name__,
                    detail="provider access method could not be prepared atomically",
                )
                blocked = True

        if blocked:
            for method in resolution.methods:
                if method.method_id not in outcomes:
                    outcomes[method.method_id] = ProviderMethodRegistration(
                        method_id=method.method_id,
                        kind=method.kind,
                        access_mode=method.access_mode,
                        status="aborted",
                        detail=(
                            "atomic provider registration aborted because another "
                            "requested method could not be prepared"
                        ),
                    )
            return ProviderRegistrationResult(
                provider_id=resolution.provider_id,
                registered_tool_keys=(),
                methods=tuple(outcomes[item.method_id] for item in resolution.methods),
            )

        staged_items = tuple(
            (method, *staged[method.method_id])
            for method in resolution.methods
        )
        tool_keys = tuple(tool.key for _, tool, _ in staged_items)
        if len(tool_keys) != len(set(tool_keys)):
            raise RegistrationError(
                "atomic provider registration produced duplicate tool keys"
            )

        if self.registry.version != expected_version:
            raise RegistrationError(
                "registry changed concurrently while provider methods were staged"
            )

        previous_tools: dict[str, ToolSpec | None] = {}
        previous_bindings: dict[str, Any] = {}
        for _, tool, _ in staged_items:
            try:
                previous = self.registry.get(tool.key)
            except KeyError:
                previous = None
            if previous is not None and not replace:
                outcomes = {
                    method.method_id: ProviderMethodRegistration(
                        method_id=method.method_id,
                        kind=method.kind,
                        access_mode=method.access_mode,
                        status="unavailable",
                        error_type="RegistrationError",
                        detail=(
                            "atomic provider registration requires replace=True "
                            f"for existing tool {tool.key!r}"
                        ),
                    )
                    for method, staged_tool, _ in staged_items
                    if staged_tool.key == tool.key
                }
                for method, _staged_tool, _ in staged_items:
                    if method.method_id not in outcomes:
                        outcomes[method.method_id] = ProviderMethodRegistration(
                            method_id=method.method_id,
                            kind=method.kind,
                            access_mode=method.access_mode,
                            status="aborted",
                            detail=(
                                "atomic provider registration aborted because another "
                                "requested method collided with an existing tool"
                            ),
                        )
                return ProviderRegistrationResult(
                    provider_id=resolution.provider_id,
                    registered_tool_keys=(),
                    methods=tuple(
                        outcomes[item.method_id] for item in resolution.methods
                    ),
                )
            previous_tools[tool.key] = previous
            previous_bindings[tool.key] = self.executor._binding_snapshot(tool.key)

        if self.registry.version != expected_version:
            raise RegistrationError(
                "registry changed concurrently before provider batch publication"
            )

        new_keys = tuple(
            key for key, previous in previous_tools.items() if previous is None
        )
        self.executor.ensure_tool_runtime_state_empty(new_keys)

        keys = update_many_if_current(
            self.registry,
            (tool for _, tool, _ in staged_items),
            expected_version=expected_version,
            replace=replace,
        )
        published_version = expected_version + (1 if keys else 0)
        expected_current = {
            tool.key: tool.fingerprint for _, tool, _ in staged_items
        }
        published_generations: dict[str, int] = {}

        try:
            for _, tool, invoker in staged_items:
                published_generations[tool.key] = self.executor.bind(
                    tool.key,
                    invoker,
                    expected_fingerprint=tool.fingerprint,
                )

            if self.registry.version != published_version:
                raise BindingDriftError(
                    "registry changed concurrently while publishing provider bindings"
                )
            for _, tool, _ in staged_items:
                if self.registry.get(tool.key).fingerprint != tool.fingerprint:
                    raise BindingDriftError(
                        f"tool {tool.key!r} changed during atomic provider publication"
                    )
        except Exception as exc:
            try:
                restore_many_if_current(
                    self.registry,
                    previous_tools,
                    expected_current=expected_current,
                    expected_version=published_version,
                )
            except Exception as rollback_exc:
                for key, generation in published_generations.items():
                    self.executor._remove_binding_if_generation(key, generation)
                raise BindingDriftError(
                    "atomic provider registration failed and registry rollback "
                    "could not preserve concurrent state"
                ) from rollback_exc

            runtime_conflict = False
            for key, generation in published_generations.items():
                if not self.executor._restore_binding_if_generation(
                    key,
                    generation,
                    previous_bindings[key],
                ):
                    runtime_conflict = True
            if runtime_conflict:
                raise BindingDriftError(
                    "atomic provider registration rolled back registry state but "
                    "newer executor state prevented binding rollback"
                ) from exc
            raise

        registrations = tuple(
            ProviderMethodRegistration(
                method_id=method.method_id,
                kind=method.kind,
                access_mode=method.access_mode,
                status="registered",
                tool_key=tool.key,
            )
            for method, tool, _ in staged_items
        )
        for key in keys:
            self.loader.remember_tool_schema_http_validators(
                self.registry.get(key)
            )
        return ProviderRegistrationResult(
            provider_id=resolution.provider_id,
            registered_tool_keys=keys,
            methods=registrations,
        )

    async def add_provider(
        self,
        provider: str,
        *,
        methods: set[str] | list[str] | tuple[str, ...] | None = None,
        trusted_headers_by_method: Mapping[str, Mapping[str, str]] | None = None,
        replace: bool = False,
        timeout: float = RUNTIME_DEFAULTS.transport_timeout_seconds,
        require_all: bool = False,
    ) -> ProviderRegistrationResult:
        """Register every safely usable declarative access method for one provider.

        This is an onboarding layer over the existing adapters, not a second schema
        compiler. Methods that need credentials, optional dependencies, or an explicit
        trusted SDK binding are reported and skipped rather than guessed or auto-installed.

        By default registration remains best-effort for backward compatibility. Set
        require_all=True to stage every requested method first and publish the resulting
        provider topology as one version-guarded all-or-nothing batch.
        """

        if not isinstance(require_all, bool):
            raise TypeError("require_all must be a bool")
        if require_all:
            return await self._add_provider_require_all(
                provider,
                methods=methods,
                trusted_headers_by_method=trusted_headers_by_method,
                replace=replace,
                timeout=timeout,
            )

        resolution = self.resolve_provider(provider, methods=methods)
        profile = self.provider_profiles.get(provider)
        profile_methods = {item.method_id: item for item in profile.methods}
        headers_by_method = trusted_headers_by_method or {}
        registrations: list[ProviderMethodRegistration] = []
        registered_keys: list[str] = []

        for method in resolution.methods:
            if method.status != "available":
                registrations.append(
                    ProviderMethodRegistration(
                        method_id=method.method_id,
                        kind=method.kind,
                        access_mode=method.access_mode,
                        status=method.status,
                        detail=method.detail,
                    )
                )
                continue

            trusted_headers = dict(headers_by_method.get(method.method_id, {}))
            provided_header_names = {name.lower() for name in trusted_headers}
            missing_credentials = tuple(
                name
                for name in method.credential_names
                if name.lower() not in provided_header_names
            )
            if missing_credentials:
                registrations.append(
                    ProviderMethodRegistration(
                        method_id=method.method_id,
                        kind=method.kind,
                        access_mode=method.access_mode,
                        status="auth_required",
                        detail=(
                            "credential header(s) required: "
                            + ", ".join(missing_credentials)
                        ),
                    )
                )
                continue

            if method.url is None:
                registrations.append(
                    ProviderMethodRegistration(
                        method_id=method.method_id,
                        kind=method.kind,
                        access_mode=method.access_mode,
                        status="manual_binding_required",
                        detail="method has no declarative URL source",
                    )
                )
                continue

            profile_method = profile_methods[method.method_id]
            try:
                if method.kind == "http_json":
                    if profile_method.tool is None:
                        raise RegistrationError(
                            "http_json provider method has no trusted ToolSpec"
                        )
                    tool_key = self.add_http_tool(
                        profile_method.tool,
                        base_url=method.url,
                        provider=resolution.provider_id,
                        access_mode=method.access_mode,
                        trusted_headers=trusted_headers or None,
                        timeout=timeout,
                        replace=replace,
                    )
                    tool = self.registry.get(tool_key)
                else:
                    tool = await self.add_url(
                        method.url,
                        kind=method.kind,
                        provider=resolution.provider_id,
                        access_mode=method.access_mode,
                        trusted_headers=trusted_headers or None,
                        replace=replace,
                        timeout=timeout,
                    )
            except Exception as exc:  # noqa: BLE001
                registrations.append(
                    ProviderMethodRegistration(
                        method_id=method.method_id,
                        kind=method.kind,
                        access_mode=method.access_mode,
                        status="unavailable",
                        error_type=type(exc).__name__,
                        detail="provider access method could not be registered",
                    )
                )
                continue

            registered_keys.append(tool.key)
            registrations.append(
                ProviderMethodRegistration(
                    method_id=method.method_id,
                    kind=method.kind,
                    access_mode=method.access_mode,
                    status="registered",
                    tool_key=tool.key,
                )
            )

        return ProviderRegistrationResult(
            provider_id=resolution.provider_id,
            registered_tool_keys=tuple(registered_keys),
            methods=tuple(registrations),
        )

    def load_adapter_plugins(
        self,
        *,
        allowlist: set[str] | list[str] | tuple[str, ...],
        replace: bool = False,
    ) -> tuple[str, ...]:
        return _load_adapter_plugins(
            self.loader.adapters,
            allowlist=allowlist,
            replace=replace,
        )

    def add_callable(
        self,
        function: Callable[..., Any],
        *,
        name: str | None = None,
        namespace: str | None = None,
        provider: str | None = None,
        access_mode: str | None = None,
        description: str | None = None,
        read_only: bool | None = None,
        destructive: bool | None = None,
        replace: bool = False,
    ) -> str:
        decorated = callable_options(function)
        tool = tool_from_callable(
            function,
            name=name if name is not None else decorated.get("name"),
            namespace=(
                namespace if namespace is not None else decorated.get("namespace")
            ),
            provider=(
                provider if provider is not None else decorated.get("provider")
            ),
            access_mode=(
                access_mode if access_mode is not None else decorated.get("access_mode")
            ),
            description=(
                description if description is not None else decorated.get("description")
            ),
            read_only=(
                read_only if read_only is not None else decorated.get("read_only")
            ),
            destructive=(
                destructive if destructive is not None else decorated.get("destructive")
            ),
        )
        invoker = PythonCallableInvoker(function)
        return self.executor.publish_bound_tool(
            tool,
            invoker,
            replace=replace,
        )

    def add_langchain_tool(
        self,
        tool: Any,
        *,
        name: str | None = None,
        namespace: str | None = None,
        provider: str | None = None,
        access_mode: str | None = None,
        read_only: bool | None = None,
        destructive: bool | None = None,
        remote: bool = True,
        replace: bool = False,
    ) -> str:
        """Import and bind one LangChain BaseTool-like object.

        SchemaRouter trusts only the tool's declared input/output schemas plus the explicit
        local authority classification supplied here. Descriptions and foreign metadata do not
        grant read/write permission.
        """

        from .integrations.langchain import LangChainToolInvoker, tool_from_langchain

        spec = tool_from_langchain(
            tool,
            name=name,
            namespace=namespace,
            provider=provider,
            access_mode=access_mode,
            read_only=read_only,
            destructive=destructive,
            remote=remote,
        )
        invoker = LangChainToolInvoker(tool)
        return self.executor.publish_bound_tool(
            spec,
            invoker,
            replace=replace,
        )

    def add_llamaindex_tool(
        self,
        tool: Any,
        *,
        name: str | None = None,
        namespace: str | None = None,
        provider: str | None = None,
        access_mode: str | None = None,
        read_only: bool | None = None,
        destructive: bool | None = None,
        remote: bool = True,
        replace: bool = False,
    ) -> str:
        """Import and bind one LlamaIndex BaseTool-like object."""

        from .integrations.llamaindex import (
            LlamaIndexToolInvoker,
            tool_from_llamaindex,
        )

        spec = tool_from_llamaindex(
            tool,
            name=name,
            namespace=namespace,
            provider=provider,
            access_mode=access_mode,
            read_only=read_only,
            destructive=destructive,
            remote=remote,
        )
        invoker = LlamaIndexToolInvoker(tool)
        return self.executor.publish_bound_tool(
            spec,
            invoker,
            replace=replace,
        )

    def add_http_tool(
        self,
        tool: ToolSpec,
        *,
        base_url: str,
        provider: str | None = None,
        access_mode: str | None = None,
        trusted_headers: dict[str, str] | None = None,
        timeout: float = RUNTIME_DEFAULTS.transport_timeout_seconds,
        max_response_bytes: int = RUNTIME_DEFAULTS.max_response_bytes,
        replace: bool = False,
    ) -> str:
        """Register and bind a trusted declarative HTTP/JSON ToolSpec.

        The supplied ToolSpec is the machine-readable manifest. Authentication remains only in
        trusted_headers and is never copied into model-visible schema metadata.
        """

        from .adapters.http_json import (
            build_http_json_invoker,
            prepare_http_json_tool,
        )

        prepared = prepare_http_json_tool(
            tool,
            base_url=base_url,
            provider=provider,
            access_mode=access_mode,
        )
        invoker = build_http_json_invoker(
            prepared,
            base_url=base_url,
            trusted_headers=trusted_headers,
            timeout=timeout,
            max_response_bytes=max_response_bytes,
            http_client=self.loader.http_client,
            network_policy=self.loader.network_policy,
        )

        return self.executor.publish_bound_tool(
            prepared,
            invoker,
            replace=replace,
        )

    async def inspect_url(
        self,
        url: str,
        *,
        model: DocumentationModelCallable,
        timeout: float = RUNTIME_DEFAULTS.transport_timeout_seconds,
        max_document_chars: int = RUNTIME_DEFAULTS.documentation_max_chars,
    ) -> SchemaProposal:
        return await inspect_documentation_url(
            url,
            model=model,
            http_client=self.loader.http_client,
            timeout=timeout,
            max_document_chars=max_document_chars,
        )

    def bind_openapi(
        self,
        tool_key: str,
        *,
        base_url: str,
        trusted_headers: dict[str, str] | None = None,
        timeout: float = RUNTIME_DEFAULTS.transport_timeout_seconds,
    ) -> None:
        expected_version = self.registry.version
        tool = self.registry.get(tool_key)
        if tool.execution_metadata.get("adapter") != "openapi":
            raise RegistrationError(
                f"tool {tool_key!r} was not imported from OpenAPI"
            )
        try:
            invoker = OpenAPIRemoteInvoker(
                tool,
                base_url,
                trusted_headers=trusted_headers,
                timeout=timeout,
                network_policy=self.loader.network_policy,
            )
        except ValueError as exc:
            raise RegistrationError("invalid OpenAPI execution binding") from exc
        updated = tool.model_copy(deep=True)
        updated.execution_metadata.update(
            {
                "execution_bound": True,
                "approved_base_url": base_url,
                "requires_explicit_base_url": False,
            }
        )
        updated.metadata.update(
            {
                "execution_bound": True,
                "approved_base_url": base_url,
                "requires_explicit_base_url": False,
            }
        )
        self.executor.publish_bound_tool(
            updated,
            invoker,
            replace=True,
            expected_fingerprint=tool.fingerprint,
            expected_version=expected_version,
        )

    def approve_proposal(
        self,
        proposal: SchemaProposal,
        *,
        base_url: str,
        min_grounding_score: float = 0.8,
        allow_mutations: bool = False,
        replace: bool = False,
        trusted_headers: dict[str, str] | None = None,
        timeout: float = RUNTIME_DEFAULTS.transport_timeout_seconds,
    ) -> str:
        if proposal.status != "grounded" or proposal.tool is None:
            raise ProposalApprovalError("proposal has no grounded tool to approve")
        if proposal.grounding_score < min_grounding_score:
            raise ProposalApprovalError(
                "proposal grounding score is below the required threshold"
            )

        parsed = urlparse(base_url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ProposalApprovalError("base_url must be an absolute http(s) URL")
        if parsed.username or parsed.password:
            raise ProposalApprovalError(
                "credentials must not be embedded in base_url; use trusted runtime auth"
            )

        mutating = [
            endpoint.name
            for endpoint in proposal.tool.endpoints
            if endpoint.method not in {"GET", "HEAD", "OPTIONS"}
        ]
        if mutating and not allow_mutations:
            raise ProposalApprovalError(
                "proposal contains mutating endpoints; set allow_mutations=True "
                "after explicit review"
            )

        tool = proposal.tool.model_copy(deep=True)
        tool.execution_metadata.update(
            {
                "executable": True,
                "approved_base_url": base_url,
            }
        )
        tool.metadata.update(
            {
                "approved_from_proposal": True,
                "executable": True,
                "grounding_score": proposal.grounding_score,
                "approved_base_url": base_url,
            }
        )
        try:
            invoker = OpenAPIRemoteInvoker(
                tool,
                base_url,
                trusted_headers=trusted_headers,
                timeout=timeout,
                network_policy=self.loader.network_policy,
            )
        except ValueError as exc:
            raise ProposalApprovalError("invalid proposal execution binding") from exc
        return self.executor.publish_bound_tool(
            tool,
            invoker,
            replace=replace,
        )

    async def add_mcp_client_factory(
        self,
        client_factory: MCPBoundClientFactory,
        *,
        name: str | None = None,
        namespace: str | None = None,
        provider: str | None = None,
        access_mode: str | None = None,
        transport: str = "custom",
        transport_fingerprint: str | None = None,
        replace: bool = False,
        timeout: float = RUNTIME_DEFAULTS.transport_timeout_seconds,
        discovery_limits: MCPDiscoveryLimits | None = None,
    ) -> ToolSpec:
        """Import MCP tools through a trusted transport-neutral client factory.

        The factory owns transport, credentials, subprocesses, sockets, or in-process state.
        None of that trusted state is copied into the model-visible ToolSpec.
        """

        if not isinstance(transport, str) or not transport.strip():
            raise ValueError("MCP transport label must be a non-empty string")
        if transport_fingerprint is not None and (
            not isinstance(transport_fingerprint, str)
            or not transport_fingerprint.strip()
        ):
            raise ValueError(
                "MCP transport_fingerprint must be a non-empty string when provided"
            )

        tool = await inspect_mcp_client_factory(
            client_factory,
            server_name=name,
            namespace=namespace,
            timeout=timeout,
            transport=transport.strip(),
            transport_fingerprint=(
                transport_fingerprint.strip()
                if transport_fingerprint is not None
                else None
            ),
            discovery_limits=discovery_limits,
        )
        if provider is not None:
            tool.provider = provider
        if access_mode is not None:
            tool.access_mode = access_mode
        elif tool.access_mode is None:
            tool.access_mode = f"mcp_{transport.strip()}"

        invoker = MCPBoundInvoker(
            client_factory,
            timeout=timeout,
            discovery_limits=discovery_limits,
        )
        key = self.executor.publish_bound_tool(
            tool,
            invoker,
            replace=replace,
        )
        return self.registry.get(key)


    async def add_mcp_stdio(
        self,
        command: str,
        *,
        args: Sequence[str] = (),
        env: Mapping[str, str] | None = None,
        cwd: str | None = None,
        allowed_commands: Sequence[str] = (),
        name: str | None = None,
        namespace: str | None = None,
        provider: str | None = None,
        access_mode: str | None = None,
        replace: bool = False,
        timeout: float = RUNTIME_DEFAULTS.transport_timeout_seconds,
        discovery_limits: MCPDiscoveryLimits | None = None,
    ) -> ToolSpec:
        """Spawn a trusted local MCP stdio server and register its advertised tools."""

        config = MCPStdioConfig(
            command=command,
            args=tuple(args),
            env=dict(env) if env is not None else None,
            cwd=cwd,
            allowed_commands=tuple(allowed_commands),
        )
        tool = await inspect_mcp_stdio(
            config,
            server_name=name,
            namespace=namespace,
            timeout=timeout,
            discovery_limits=discovery_limits,
        )
        if provider is not None:
            tool.provider = provider
        if access_mode is not None:
            tool.access_mode = access_mode
        elif tool.access_mode is None:
            tool.access_mode = "mcp_stdio"

        invoker = MCPBoundInvoker(
            MCPStdioClientFactory(config),
            timeout=timeout,
            discovery_limits=discovery_limits,
        )
        key = self.executor.publish_bound_tool(
            tool,
            invoker,
            replace=replace,
        )
        return self.registry.get(key)


    async def probe_url(
        self,
        url: str,
        *,
        kind: SourceKind = "auto",
        name: str | None = None,
        namespace: str | None = None,
        provider: str | None = None,
        base_url: str | None = None,
        schema_headers: dict[str, str] | None = None,
        trusted_headers: dict[str, str] | None = None,
        mcp_client_factory: MCPClientFactory | None = None,
        mcp_discovery_limits: MCPDiscoveryLimits | None = None,
        allow_active_probes: bool = False,
        openapi_external_refs: bool = False,
        openapi_ref_max_depth: int = RUNTIME_DEFAULTS.openapi_ref_max_depth,
        openapi_ref_max_documents: int = RUNTIME_DEFAULTS.openapi_ref_max_documents,
        openapi_ref_max_bytes: int = RUNTIME_DEFAULTS.openapi_ref_max_bytes,
        timeout: float = RUNTIME_DEFAULTS.transport_timeout_seconds,
    ) -> SourceProbeResult:
        """Diagnose a structured URL source without mutating the registry or bindings."""

        return await self.loader.probe(
            url,
            kind=kind,
            name=name,
            namespace=namespace,
            provider=provider,
            base_url=base_url,
            schema_headers=schema_headers,
            trusted_headers=trusted_headers,
            mcp_client_factory=mcp_client_factory,
            mcp_discovery_limits=mcp_discovery_limits,
            allow_active_probes=allow_active_probes,
            openapi_external_refs=openapi_external_refs,
            openapi_ref_max_depth=openapi_ref_max_depth,
            openapi_ref_max_documents=openapi_ref_max_documents,
            openapi_ref_max_bytes=openapi_ref_max_bytes,
            timeout=timeout,
        )


    async def add_url(
        self,
        url: str,
        *,
        kind: SourceKind = "auto",
        name: str | None = None,
        namespace: str | None = None,
        provider: str | None = None,
        access_mode: str | None = None,
        replace: bool = False,
        base_url: str | None = None,
        schema_headers: dict[str, str] | None = None,
        trusted_headers: dict[str, str] | None = None,
        mcp_client_factory: MCPClientFactory | None = None,
        mcp_discovery_limits: MCPDiscoveryLimits | None = None,
        allow_active_probes: bool = False,
        openapi_external_refs: bool = False,
        openapi_ref_max_depth: int = RUNTIME_DEFAULTS.openapi_ref_max_depth,
        openapi_ref_max_documents: int = RUNTIME_DEFAULTS.openapi_ref_max_documents,
        openapi_ref_max_bytes: int = RUNTIME_DEFAULTS.openapi_ref_max_bytes,
        timeout: float = RUNTIME_DEFAULTS.transport_timeout_seconds,
    ) -> ToolSpec:
        return await self.loader.load(
            url,
            kind=kind,
            name=name,
            namespace=namespace,
            provider=provider,
            access_mode=access_mode,
            replace=replace,
            base_url=base_url,
            schema_headers=schema_headers,
            trusted_headers=trusted_headers,
            mcp_client_factory=mcp_client_factory,
            mcp_discovery_limits=mcp_discovery_limits,
            allow_active_probes=allow_active_probes,
            openapi_external_refs=openapi_external_refs,
            openapi_ref_max_depth=openapi_ref_max_depth,
            openapi_ref_max_documents=openapi_ref_max_documents,
            openapi_ref_max_bytes=openapi_ref_max_bytes,
            timeout=timeout,
        )

    async def arefresh_schema(
        self,
        tool_key: str,
        *,
        apply_compatible: bool = True,
        schema_headers: dict[str, str] | None = None,
        trusted_headers: dict[str, str] | None = None,
        mcp_client_factory: MCPClientFactory | None = None,
        mcp_discovery_limits: MCPDiscoveryLimits | None = None,
        timeout: float = RUNTIME_DEFAULTS.transport_timeout_seconds,
        _expected_fingerprint: str | None = None,
        _expected_source_identity: StructuredSourceIdentity | None = None,
        _accept_candidate_fingerprint: str | None = None,
        _accept_candidate_source_identity: str | None = None,
        _apply_guard: Callable[[], Any] | None = None,
    ) -> SchemaRefreshResult:
        """Reinspect a registered remote schema and apply only proven-compatible drift."""

        expected_version = self.registry.version
        try:
            current = self.registry.get(tool_key)
        except KeyError as exc:
            raise RegistrationError(f"unknown tool: {tool_key}") from exc

        adapter = current.execution_metadata.get("adapter")
        if not isinstance(adapter, str):
            adapter = current.metadata.get("adapter")
        if not isinstance(adapter, str):
            raise SchemaSourceError(
                f"tool {tool_key!r} does not have a refreshable structured-source adapter; "
                "no structured-source adapter is declared"
            )
        try:
            refresh_profile = self.loader.adapters.refresh_profile(adapter)
        except KeyError as exc:
            raise SchemaSourceError(
                f"tool {tool_key!r} references an unavailable source adapter"
            ) from exc
        if not refresh_profile.supported:
            raise SchemaSourceError(
                f"tool {tool_key!r} does not have a refreshable structured-source adapter"
            )

        if _expected_source_identity is not None:
            current_source_identity = structured_source_identity(
                current,
                refresh_profile,
            )
            if current_source_identity != _expected_source_identity:
                raise SchemaSourceError(
                    f"tool {tool_key!r} source identity changed before schema refresh"
                )
        if (
            _expected_fingerprint is not None
            and current.fingerprint != _expected_fingerprint
        ):
            raise SchemaSourceError(
                f"tool {tool_key!r} contract changed before schema refresh"
            )

        if (
            _accept_candidate_fingerprint is not None
            or _accept_candidate_source_identity is not None
        ) and (
            _accept_candidate_fingerprint is None
            or _accept_candidate_source_identity is None
            or _expected_fingerprint is None
            or _expected_source_identity is None
        ):
            raise SchemaSourceError(
                "pending schema acceptance requires pinned current fingerprint, "
                "candidate fingerprint, current source identity, and candidate "
                "source identity"
            )

        source_url = refresh_profile.source_url(current)
        base_url: str | None = None
        openapi_external_refs = False
        openapi_ref_max_depth = 3
        openapi_ref_max_documents = 8
        openapi_ref_max_bytes = 10 * 1024 * 1024

        if adapter in {"openapi", "openrpc"}:
            approved_base = current.execution_metadata.get("approved_base_url")
            if isinstance(approved_base, str) and approved_base:
                base_url = approved_base

        if adapter == "openapi":
            openapi_external_refs = bool(
                current.metadata.get("external_refs_enabled", False)
            )
            limits = current.metadata.get("external_ref_limits")
            if isinstance(limits, dict):
                depth = limits.get("max_depth")
                documents = limits.get("max_documents")
                byte_limit = limits.get("max_bytes")
                if isinstance(depth, int) and not isinstance(depth, bool) and depth > 0:
                    openapi_ref_max_depth = depth
                if (
                    isinstance(documents, int)
                    and not isinstance(documents, bool)
                    and documents > 0
                ):
                    openapi_ref_max_documents = documents
                if (
                    isinstance(byte_limit, int)
                    and not isinstance(byte_limit, bool)
                    and byte_limit > 0
                ):
                    openapi_ref_max_bytes = byte_limit

        use_bound_mcp_transport = (
            refresh_profile.mode == "url_or_bound_mcp"
            and source_url is None
        )
        use_http_validators = refresh_profile.http_validators
        schema_validators: dict[str, str] = {}
        candidate: Any | None = None
        candidate_invoker: BoundEndpointInvoker | None = None

        if use_bound_mcp_transport:
            bound = self.executor._bound_invoker_for_contract(
                tool_key,
                current.fingerprint,
            )
            if not isinstance(bound, MCPBoundInvoker):
                raise SchemaSourceError(
                    f"tool {tool_key!r} has no current trusted MCP transport binding "
                    "available for schema refresh"
                )

            raw_transport = current.execution_metadata.get("transport")
            transport = (
                raw_transport
                if isinstance(raw_transport, str) and raw_transport
                else "custom"
            )
            raw_transport_fingerprint = current.execution_metadata.get(
                "transport_fingerprint"
            )
            transport_fingerprint = (
                raw_transport_fingerprint
                if isinstance(raw_transport_fingerprint, str)
                and raw_transport_fingerprint
                else None
            )

            effective_mcp_discovery_limits = (
                mcp_discovery_limits
                if mcp_discovery_limits is not None
                else bound.discovery_limits
            )
            candidate_tool = await inspect_mcp_client_factory(
                bound.factory,
                server_name=current.name,
                namespace=current.namespace,
                timeout=timeout,
                transport=transport,
                transport_fingerprint=transport_fingerprint,
                discovery_limits=effective_mcp_discovery_limits,
            )
            candidate_tool.provider = current.provider
            candidate_tool.access_mode = current.access_mode
            candidate_invoker = MCPBoundInvoker(
                bound.factory,
                timeout=timeout,
                discovery_limits=effective_mcp_discovery_limits,
            )
        else:
            if source_url is None:
                raise SchemaSourceError(
                    f"tool {tool_key!r} is missing persisted source provenance for refresh"
                )

            if adapter == "openapi" and openapi_external_refs:
                use_http_validators = False

            schema_validators = (
                self.loader.schema_http_validators_for(tool_key, current)
                if use_http_validators
                else {}
            )
            try:
                candidate = await self.loader.inspect(
                    source_url,
                    kind=adapter,
                    name=current.name,
                    namespace=current.namespace,
                    provider=current.provider,
                    access_mode=current.access_mode,
                    base_url=base_url,
                    schema_headers=schema_headers,
                    schema_validators=schema_validators,
                    trusted_headers=trusted_headers,
                    mcp_client_factory=mcp_client_factory,
                    mcp_discovery_limits=mcp_discovery_limits,
                    openapi_external_refs=openapi_external_refs,
                    openapi_ref_max_depth=openapi_ref_max_depth,
                    openapi_ref_max_documents=openapi_ref_max_documents,
                    openapi_ref_max_bytes=openapi_ref_max_bytes,
                    timeout=timeout,
                )
            except SchemaNotModifiedError as exc:
                self.loader.remember_schema_http_validators(
                    current,
                    exc.validators or schema_validators,
                )
                return SchemaRefreshResult(
                    tool_key=tool_key,
                    action="unchanged",
                    applied=False,
                    report=compare_tool_specs(current, current),
                )
            candidate_tool = candidate.tool
            candidate_invoker = candidate.invoker

        if candidate_tool.key != tool_key:
            raise SchemaSourceError(
                "refreshed schema changed the registered tool key unexpectedly"
            )

        overlay = amendment_overlay(current)
        raw_current = strip_amendment_overlay(current) if overlay is not None else current
        raw_report = compare_tool_specs(raw_current, candidate_tool)

        effective_candidate = candidate_tool
        if overlay is not None:
            try:
                effective_candidate = reapply_amendment_overlay(
                    candidate_tool,
                    overlay,
                )
            except ContractAmendmentError as exc:
                changes = list(raw_report.changes)
                changes.append(
                    SchemaChange(
                        path="trusted_amendment_overlay",
                        kind="amendment_overlay_conflict",
                        severity="breaking",
                        old="trusted local amendment",
                        new="provider contract no longer accepts amendment target",
                        message=str(exc),
                    )
                )
                return SchemaRefreshResult(
                    tool_key=tool_key,
                    action="pending_review",
                    applied=False,
                    report=SchemaDiffReport(
                        compatibility="breaking",
                        old_fingerprint=current.fingerprint,
                        new_fingerprint=candidate_tool.fingerprint,
                        changes=changes,
                    ),
                    reviewed_current_fingerprint=current.fingerprint,
                    candidate_fingerprint=candidate_tool.fingerprint,
                    candidate_source_identity=structured_source_identity_digest_for(
                        candidate_tool,
                        refresh_profile,
                    ),
                )

        effective_report = compare_tool_specs(current, effective_candidate)
        if raw_report.compatibility in {"breaking", "security_review"}:
            report = SchemaDiffReport(
                compatibility=raw_report.compatibility,
                old_fingerprint=current.fingerprint,
                new_fingerprint=effective_candidate.fingerprint,
                changes=list(raw_report.changes),
            )
        else:
            report = effective_report

        raw_changed_under_overlay = (
            overlay is not None
            and raw_report.changed
            and effective_report.compatibility == "identical"
        )

        candidate_fingerprint = effective_candidate.fingerprint
        candidate_source_identity = structured_source_identity_digest_for(
            effective_candidate,
            refresh_profile,
        )

        if _accept_candidate_fingerprint is not None:
            if _accept_candidate_source_identity is None:
                raise SchemaSourceError(
                    "pending schema acceptance invariant failed: candidate source "
                    "identity pin is missing"
                )
            if candidate_source_identity != _accept_candidate_source_identity:
                changes = list(report.changes)
                changes.append(
                    SchemaChange(
                        path="candidate_source_identity",
                        kind="candidate_source_changed_before_approval",
                        severity="security",
                        old=_accept_candidate_source_identity,
                        new=candidate_source_identity,
                        message=(
                            "remote candidate source identity changed after review; "
                            "the new candidate must be reviewed explicitly"
                        ),
                    )
                )
                return SchemaRefreshResult(
                    tool_key=tool_key,
                    action="pending_review",
                    applied=False,
                    report=SchemaDiffReport(
                        compatibility="security_review",
                        old_fingerprint=current.fingerprint,
                        new_fingerprint=candidate_fingerprint,
                        changes=changes,
                    ),
                    reviewed_current_fingerprint=current.fingerprint,
                    candidate_fingerprint=candidate_fingerprint,
                    candidate_source_identity=candidate_source_identity,
                )

            if candidate_fingerprint != _accept_candidate_fingerprint:
                changes = list(report.changes)
                changes.append(
                    SchemaChange(
                        path="candidate_fingerprint",
                        kind="candidate_changed_before_approval",
                        severity="breaking",
                        old=_accept_candidate_fingerprint,
                        new=candidate_fingerprint,
                        message=(
                            "remote schema changed after review; the new candidate "
                            "must be reviewed explicitly"
                        ),
                    )
                )
                compatibility = (
                    "security_review"
                    if report.compatibility == "security_review"
                    else "breaking"
                )
                return SchemaRefreshResult(
                    tool_key=tool_key,
                    action="pending_review",
                    applied=False,
                    report=SchemaDiffReport(
                        compatibility=compatibility,
                        old_fingerprint=current.fingerprint,
                        new_fingerprint=candidate_fingerprint,
                        changes=changes,
                    ),
                    reviewed_current_fingerprint=current.fingerprint,
                    candidate_fingerprint=candidate_fingerprint,
                    candidate_source_identity=candidate_source_identity,
                )

            apply_guard = (
                _apply_guard() if _apply_guard is not None else nullcontext()
            )
            async with self.health_monitor.lifecycle_guard():
                with self.health_monitor.contract_transition_guard():
                    health_transition = self._prepare_health_contract_transition(
                        current,
                        effective_candidate,
                    )
                    with apply_guard:
                        if overlay is None and candidate is not None:
                            self.loader.commit_candidate_if_current(
                                candidate,
                                expected_fingerprint=current.fingerprint,
                                expected_version=expected_version,
                            )
                        else:
                            if candidate_invoker is not None:
                                self.executor.publish_bound_tool(
                                    effective_candidate,
                                    candidate_invoker,
                                    replace=True,
                                    expected_fingerprint=current.fingerprint,
                                    expected_version=expected_version,
                                )
                            else:
                                replace_if_current(
                                    self.registry,
                                    effective_candidate,
                                    expected_fingerprint=current.fingerprint,
                                    expected_version=expected_version,
                                )
                            if not use_bound_mcp_transport and use_http_validators:
                                self.loader.remember_tool_schema_http_validators(
                                    effective_candidate
                                )

                        self._apply_health_contract_transition(health_transition)
            return SchemaRefreshResult(
                tool_key=tool_key,
                action="applied",
                applied=True,
                report=report,
                reviewed_current_fingerprint=current.fingerprint,
                candidate_fingerprint=candidate_fingerprint,
                candidate_source_identity=candidate_source_identity,
            )

        if report.compatibility == "identical" and not raw_changed_under_overlay:
            if not use_bound_mcp_transport and use_http_validators:
                self.loader.remember_tool_schema_http_validators(candidate_tool)
            return SchemaRefreshResult(
                tool_key=tool_key,
                action="unchanged",
                applied=False,
                report=report,
            )

        if (
            report.compatibility == "compatible" or raw_changed_under_overlay
        ) and apply_compatible:
            apply_guard = (
                _apply_guard() if _apply_guard is not None else nullcontext()
            )
            async with self.health_monitor.lifecycle_guard():
                with self.health_monitor.contract_transition_guard():
                    health_transition = self._prepare_health_contract_transition(
                        current,
                        effective_candidate,
                    )
                    with apply_guard:
                        if overlay is None and candidate is not None:
                            self.loader.commit_candidate_if_current(
                                candidate,
                                expected_fingerprint=current.fingerprint,
                                expected_version=expected_version,
                            )
                        else:
                            if candidate_invoker is not None:
                                self.executor.publish_bound_tool(
                                    effective_candidate,
                                    candidate_invoker,
                                    replace=True,
                                    expected_fingerprint=current.fingerprint,
                                    expected_version=expected_version,
                                )
                            else:
                                replace_if_current(
                                    self.registry,
                                    effective_candidate,
                                    expected_fingerprint=current.fingerprint,
                                    expected_version=expected_version,
                                )
                            if not use_bound_mcp_transport and use_http_validators:
                                self.loader.remember_tool_schema_http_validators(
                                    effective_candidate
                                )

                        self._apply_health_contract_transition(health_transition)

            applied_report = report
            if raw_changed_under_overlay:
                applied_report = SchemaDiffReport(
                    compatibility="compatible",
                    old_fingerprint=current.fingerprint,
                    new_fingerprint=effective_candidate.fingerprint,
                    changes=list(raw_report.changes),
                )
            return SchemaRefreshResult(
                tool_key=tool_key,
                action="applied",
                applied=True,
                report=applied_report,
            )

        action = (
            "report_only"
            if report.compatibility == "compatible"
            else "pending_review"
        )
        return SchemaRefreshResult(
            tool_key=tool_key,
            action=action,
            applied=False,
            report=report,
            reviewed_current_fingerprint=(
                current.fingerprint if action == "pending_review" else None
            ),
            candidate_fingerprint=(
                candidate_fingerprint if action == "pending_review" else None
            ),
            candidate_source_identity=(
                candidate_source_identity if action == "pending_review" else None
            ),
        )

    def refresh_schema(
        self,
        tool_key: str,
        *,
        apply_compatible: bool = True,
        schema_headers: dict[str, str] | None = None,
        trusted_headers: dict[str, str] | None = None,
        mcp_client_factory: MCPClientFactory | None = None,
        mcp_discovery_limits: MCPDiscoveryLimits | None = None,
        timeout: float = RUNTIME_DEFAULTS.transport_timeout_seconds,
    ) -> SchemaRefreshResult:
        """Synchronous wrapper for :meth:`arefresh_schema`."""

        return _run_sync(
            lambda: self.arefresh_schema(
                tool_key,
                apply_compatible=apply_compatible,
                schema_headers=schema_headers,
                trusted_headers=trusted_headers,
                mcp_client_factory=mcp_client_factory,
                mcp_discovery_limits=mcp_discovery_limits,
                timeout=timeout,
            )
        )

    def plan(self, request: PlanRequest | str) -> ExecutionPlan:
        """Schema-aware planning under any active trusted principal context."""

        principal = _current_principal_context()
        predicate = self._authorization_predicate(principal)
        if predicate is None:
            plan = self.planner.plan(request)
        elif (
            self.authorization_policy is not None
            and self.authorization_policy.data_rules
            and principal is not None
        ):
            plan = self.planner.plan_with_scoped_schema(
                request,
                predicate,
                lambda tool, endpoint: self._data_scope_endpoint_view(
                    principal,
                    tool,
                    endpoint,
                ),
                analysis_registry=self._scoped_analysis_registry(
                    principal,
                    predicate,
                ),
            )
        else:
            plan = self.planner.plan_with_additional_availability(request, predicate)
        if self.authorization_policy is not None:
            self._validate_plan_authorization(plan, principal, phase="plan")
        return plan

    async def aplan(self, request: PlanRequest | str) -> ExecutionPlan:
        """Async schema-aware planning under any active trusted principal context."""

        principal = _current_principal_context()
        predicate = self._authorization_predicate(principal)
        if predicate is None:
            plan = await self.planner.aplan(request)
        elif (
            self.authorization_policy is not None
            and self.authorization_policy.data_rules
            and principal is not None
        ):
            plan = await self.planner.aplan_with_scoped_schema(
                request,
                predicate,
                lambda tool, endpoint: self._data_scope_endpoint_view(
                    principal,
                    tool,
                    endpoint,
                ),
                analysis_registry=self._scoped_analysis_registry(
                    principal,
                    predicate,
                ),
            )
        else:
            plan = await self.planner.aplan_with_additional_availability(
                request,
                predicate,
            )
        if self.authorization_policy is not None:
            self._validate_plan_authorization(plan, principal, phase="plan")
        return plan

    def plan_authorized(
        self,
        request: PlanRequest | str,
        *,
        principal: PrincipalContext,
    ) -> ExecutionPlan:
        """Plan with one explicitly supplied trusted principal."""

        with _principal_execution_context(principal):
            return self.plan(request)

    async def aplan_authorized(
        self,
        request: PlanRequest | str,
        *,
        principal: PrincipalContext,
    ) -> ExecutionPlan:
        """Async counterpart to :meth:`plan_authorized`."""

        with _principal_execution_context(principal):
            return await self.aplan(request)

    def retrieve_routes(
        self,
        request: PlanRequest | str,
        *,
        k: int = 5,
    ) -> CapabilityRouteRetrieval:
        """Return lightweight Top-K route references under active authorization."""

        predicate = self._authorization_predicate(_current_principal_context())
        if predicate is None:
            return self.planner.retrieve_routes(request, k=k)
        return self.planner.retrieve_routes_with_additional_availability(
            request,
            predicate,
            k=k,
        )

    async def aretrieve_routes(
        self,
        request: PlanRequest | str,
        *,
        k: int = 5,
    ) -> CapabilityRouteRetrieval:
        """Async counterpart to :meth:`retrieve_routes`."""

        predicate = self._authorization_predicate(_current_principal_context())
        if predicate is None:
            return await self.planner.aretrieve_routes(request, k=k)
        return await self.planner.aretrieve_routes_with_additional_availability(
            request,
            predicate,
            k=k,
        )

    def retrieve_routes_authorized(
        self,
        request: PlanRequest | str,
        *,
        principal: PrincipalContext,
        k: int = 5,
    ) -> CapabilityRouteRetrieval:
        """Retrieve route references for one explicitly supplied principal."""

        with _principal_execution_context(principal):
            return self.retrieve_routes(request, k=k)

    async def aretrieve_routes_authorized(
        self,
        request: PlanRequest | str,
        *,
        principal: PrincipalContext,
        k: int = 5,
    ) -> CapabilityRouteRetrieval:
        """Async counterpart to :meth:`retrieve_routes_authorized`."""

        with _principal_execution_context(principal):
            return await self.aretrieve_routes(request, k=k)

    def retrieve(
        self,
        request: PlanRequest | str,
        *,
        k: int = 5,
    ) -> CapabilityRetrieval:
        """Return Top-K typed capabilities under any active principal context."""

        principal = _current_principal_context()
        predicate = self._authorization_predicate(principal)
        if predicate is None:
            retrieval = self.planner.retrieve(request, k=k)
        elif (
            self.authorization_policy is not None
            and self.authorization_policy.data_rules
            and principal is not None
        ):
            retrieval = self.planner.retrieve_with_scoped_schema(
                request,
                predicate,
                lambda tool, endpoint: self._data_scope_endpoint_view(
                    principal,
                    tool,
                    endpoint,
                ),
                k=k,
                analysis_registry=self._scoped_analysis_registry(
                    principal,
                    predicate,
                ),
            )
        else:
            retrieval = self.planner.retrieve_with_additional_availability(
                request,
                predicate,
                k=k,
            )
        return self._project_retrieval_data_scope(retrieval, principal)

    async def aretrieve(
        self,
        request: PlanRequest | str,
        *,
        k: int = 5,
    ) -> CapabilityRetrieval:
        """Async counterpart to :meth:`retrieve`."""

        principal = _current_principal_context()
        predicate = self._authorization_predicate(principal)
        if predicate is None:
            retrieval = await self.planner.aretrieve(request, k=k)
        elif (
            self.authorization_policy is not None
            and self.authorization_policy.data_rules
            and principal is not None
        ):
            retrieval = await self.planner.aretrieve_with_scoped_schema(
                request,
                predicate,
                lambda tool, endpoint: self._data_scope_endpoint_view(
                    principal,
                    tool,
                    endpoint,
                ),
                k=k,
                analysis_registry=self._scoped_analysis_registry(
                    principal,
                    predicate,
                ),
            )
        else:
            retrieval = await self.planner.aretrieve_with_additional_availability(
                request,
                predicate,
                k=k,
            )
        return self._project_retrieval_data_scope(retrieval, principal)

    def retrieve_authorized(
        self,
        request: PlanRequest | str,
        *,
        principal: PrincipalContext,
        k: int = 5,
    ) -> CapabilityRetrieval:
        """Retrieve capabilities for one explicitly supplied trusted principal."""

        with _principal_execution_context(principal):
            return self.retrieve(request, k=k)

    def retrieve_adaptive(
        self,
        request: PlanRequest | str,
        *,
        history: SuccessfulCapabilityHistory | None = None,
        history_weight: float = 0.0,
        exposure: SessionSchemaExposure | None = None,
        k: int = 5,
    ) -> CapabilityRetrieval:
        """Retrieve with optional post-authorization history/context transforms."""

        retrieval = self.retrieve(request, k=k)
        if history is not None:
            retrieval = apply_success_prior(
                retrieval,
                history,
                weight=history_weight,
            )
        if exposure is not None:
            retrieval = filter_unexposed_schemas(retrieval, exposure)
        return retrieval

    async def aretrieve_adaptive(
        self,
        request: PlanRequest | str,
        *,
        history: SuccessfulCapabilityHistory | None = None,
        history_weight: float = 0.0,
        exposure: SessionSchemaExposure | None = None,
        k: int = 5,
    ) -> CapabilityRetrieval:
        """Async counterpart to :meth:`retrieve_adaptive`."""

        retrieval = await self.aretrieve(request, k=k)
        if history is not None:
            retrieval = apply_success_prior(
                retrieval,
                history,
                weight=history_weight,
            )
        if exposure is not None:
            retrieval = filter_unexposed_schemas(retrieval, exposure)
        return retrieval

    async def aretrieve_authorized(
        self,
        request: PlanRequest | str,
        *,
        principal: PrincipalContext,
        k: int = 5,
    ) -> CapabilityRetrieval:
        """Async counterpart to :meth:`retrieve_authorized`."""

        with _principal_execution_context(principal):
            return await self.aretrieve(request, k=k)

    def _state_aware_full_retrieval_k(self, requested_k: int) -> int:
        """Materialize the complete currently visible ranking for state backfill."""

        route_count = sum(len(tool.endpoints) for tool in self.registry.tools())
        return max(requested_k, route_count)

    def reretrieve_state_aware(
        self,
        request: PlanRequest | str,
        *,
        execution_state: TypedExecutionState,
        k: int = 5,
        state_requirements: dict[str, list[CapabilityFieldContract]] | None = None,
        state_preconditions: dict[str, list[CapabilityPrecondition]] | None = None,
    ) -> StateConditionedCapabilityRetrieval:
        """Backfill over the same authorization-scoped surface as normal retrieval."""

        retrieval = self.retrieve(
            request,
            k=self._state_aware_full_retrieval_k(k),
        )
        return backfill_ranked_candidates_by_state(
            query=retrieval.query,
            registry_version=retrieval.registry_version,
            requested_k=k,
            ranked_candidates=retrieval.candidates,
            state=execution_state,
            requirements_by_route=state_requirements,
            preconditions_by_route=state_preconditions,
        )

    async def areretrieve_state_aware(
        self,
        request: PlanRequest | str,
        *,
        execution_state: TypedExecutionState,
        k: int = 5,
        state_requirements: dict[str, list[CapabilityFieldContract]] | None = None,
        state_preconditions: dict[str, list[CapabilityPrecondition]] | None = None,
    ) -> StateConditionedCapabilityRetrieval:
        """Async counterpart to :meth:`reretrieve_state_aware`."""

        retrieval = await self.aretrieve(
            request,
            k=self._state_aware_full_retrieval_k(k),
        )
        return backfill_ranked_candidates_by_state(
            query=retrieval.query,
            registry_version=retrieval.registry_version,
            requested_k=k,
            ranked_candidates=retrieval.candidates,
            state=execution_state,
            requirements_by_route=state_requirements,
            preconditions_by_route=state_preconditions,
        )

    def retrieve_state_aware(
        self,
        request: PlanRequest | str,
        *,
        execution_state: TypedExecutionState,
        k: int = 5,
        state_requirements: dict[str, list[CapabilityFieldContract]] | None = None,
        state_preconditions: dict[str, list[CapabilityPrecondition]] | None = None,
    ) -> StateAwareCapabilityRetrieval:
        """Retrieve from the same authorization-scoped surface as normal retrieval."""

        retrieval = self.retrieve(request, k=k)
        return filter_retrieval_by_state(
            retrieval,
            execution_state,
            requirements_by_route=state_requirements,
            preconditions_by_route=state_preconditions,
        )

    async def aretrieve_state_aware(
        self,
        request: PlanRequest | str,
        *,
        execution_state: TypedExecutionState,
        k: int = 5,
        state_requirements: dict[str, list[CapabilityFieldContract]] | None = None,
        state_preconditions: dict[str, list[CapabilityPrecondition]] | None = None,
    ) -> StateAwareCapabilityRetrieval:
        """Async counterpart to :meth:`retrieve_state_aware`."""

        retrieval = await self.aretrieve(request, k=k)
        return filter_retrieval_by_state(
            retrieval,
            execution_state,
            requirements_by_route=state_requirements,
            preconditions_by_route=state_preconditions,
        )

    def _binding_ready(self, tool: ToolSpec, endpoint: Any) -> bool:
        del endpoint
        return self.executor.is_binding_ready_for_contract(
            tool.key,
            tool.fingerprint,
        )

    def plan_executable(self, request: PlanRequest | str) -> ExecutionPlan:
        """Plan only across authorized routes with a ready local binding."""

        principal = _current_principal_context()
        predicate = self._combined_availability_predicate(
            principal,
            self._binding_ready,
        )
        if predicate is None:
            raise RuntimeError("executable planning requires an availability predicate")
        if (
            self.authorization_policy is not None
            and self.authorization_policy.data_rules
            and principal is not None
        ):
            plan = self.planner.plan_with_scoped_schema(
                request,
                predicate,
                lambda tool, endpoint: self._data_scope_endpoint_view(
                    principal,
                    tool,
                    endpoint,
                ),
                analysis_registry=self._scoped_analysis_registry(
                    principal,
                    predicate,
                ),
            )
        else:
            plan = self.planner.plan_with_additional_availability(request, predicate)
        return plan

    async def aplan_executable(self, request: PlanRequest | str) -> ExecutionPlan:
        """Async counterpart to :meth:`plan_executable`."""

        principal = _current_principal_context()
        predicate = self._combined_availability_predicate(
            principal,
            self._binding_ready,
        )
        if predicate is None:
            raise RuntimeError("executable planning requires an availability predicate")
        if (
            self.authorization_policy is not None
            and self.authorization_policy.data_rules
            and principal is not None
        ):
            plan = await self.planner.aplan_with_scoped_schema(
                request,
                predicate,
                lambda tool, endpoint: self._data_scope_endpoint_view(
                    principal,
                    tool,
                    endpoint,
                ),
                analysis_registry=self._scoped_analysis_registry(
                    principal,
                    predicate,
                ),
            )
        else:
            plan = await self.planner.aplan_with_additional_availability(
                request,
                predicate,
            )
        return plan

    def plan_executable_authorized(
        self,
        request: PlanRequest | str,
        *,
        principal: PrincipalContext,
    ) -> ExecutionPlan:
        """Plan executable routes for one explicitly supplied principal."""

        with _principal_execution_context(principal):
            return self.plan_executable(request)

    async def aplan_executable_authorized(
        self,
        request: PlanRequest | str,
        *,
        principal: PrincipalContext,
    ) -> ExecutionPlan:
        """Async counterpart to :meth:`plan_executable_authorized`."""

        with _principal_execution_context(principal):
            return await self.aplan_executable(request)

    def retrieve_executable(
        self,
        request: PlanRequest | str,
        *,
        k: int = 5,
    ) -> CapabilityRetrieval:
        """Return Top-K authorized capabilities with a ready local binding."""

        principal = _current_principal_context()
        predicate = self._combined_availability_predicate(
            principal,
            self._binding_ready,
        )
        if predicate is None:
            raise RuntimeError("executable retrieval requires an availability predicate")
        if (
            self.authorization_policy is not None
            and self.authorization_policy.data_rules
            and principal is not None
        ):
            retrieval = self.planner.retrieve_with_scoped_schema(
                request,
                predicate,
                lambda tool, endpoint: self._data_scope_endpoint_view(
                    principal,
                    tool,
                    endpoint,
                ),
                k=k,
                executable_only=True,
                analysis_registry=self._scoped_analysis_registry(
                    principal,
                    predicate,
                ),
            )
        else:
            retrieval = self.planner.retrieve_with_additional_availability(
                request,
                predicate,
                k=k,
                executable_only=True,
            )
        return self._project_retrieval_data_scope(retrieval, principal)

    async def aretrieve_executable(
        self,
        request: PlanRequest | str,
        *,
        k: int = 5,
    ) -> CapabilityRetrieval:
        """Async counterpart to :meth:`retrieve_executable`."""

        principal = _current_principal_context()
        predicate = self._combined_availability_predicate(
            principal,
            self._binding_ready,
        )
        if predicate is None:
            raise RuntimeError("executable retrieval requires an availability predicate")
        if (
            self.authorization_policy is not None
            and self.authorization_policy.data_rules
            and principal is not None
        ):
            retrieval = await self.planner.aretrieve_with_scoped_schema(
                request,
                predicate,
                lambda tool, endpoint: self._data_scope_endpoint_view(
                    principal,
                    tool,
                    endpoint,
                ),
                k=k,
                executable_only=True,
                analysis_registry=self._scoped_analysis_registry(
                    principal,
                    predicate,
                ),
            )
        else:
            retrieval = await self.planner.aretrieve_with_additional_availability(
                request,
                predicate,
                k=k,
                executable_only=True,
            )
        return self._project_retrieval_data_scope(retrieval, principal)

    def retrieve_executable_authorized(
        self,
        request: PlanRequest | str,
        *,
        principal: PrincipalContext,
        k: int = 5,
    ) -> CapabilityRetrieval:
        """Retrieve executable capabilities for one explicitly supplied principal."""

        with _principal_execution_context(principal):
            return self.retrieve_executable(request, k=k)

    async def aretrieve_executable_authorized(
        self,
        request: PlanRequest | str,
        *,
        principal: PrincipalContext,
        k: int = 5,
    ) -> CapabilityRetrieval:
        """Async counterpart to :meth:`retrieve_executable_authorized`."""

        with _principal_execution_context(principal):
            return await self.aretrieve_executable(request, k=k)

    async def _execute_plan(
        self,
        plan: ExecutionPlan,
        run_config: RunConfig,
    ) -> list[ToolResult]:
        self._validate_plan_authorization(
            plan,
            run_config.principal,
            run_id=run_config.run_id,
            principal_audit_id=run_config.principal_audit_id,
            phase="execution",
        )
        with _principal_execution_context(run_config.principal):
            if run_config.execution_mode == "parallel_read_only":
                return await self.executor.execute_parallel_read_only(
                    plan,
                    retry=run_config.retry,
                    budget=run_config.budget,
                    max_concurrency=run_config.max_parallel_calls,
                )
            return await self.executor.execute(
                plan,
                retry=run_config.retry,
                budget=run_config.budget,
            )

    async def execute(
        self,
        plan: ExecutionPlan,
        *,
        config: RunConfig | dict[str, Any] | None = None,
    ) -> list[ToolResult]:
        run_config = _coerce_run_config(config)
        return await self._execute_plan(plan, run_config)

    async def ainvoke(
        self,
        request: PlanRequest | str,
        *,
        config: RunConfig | dict[str, Any] | None = None,
    ) -> list[ToolResult]:
        run_config = _coerce_run_config(config)
        with _principal_execution_context(run_config.principal):
            plan = await self.aplan_executable(request)
        return await self._execute_plan(plan, run_config)

    def invoke(
        self,
        request: PlanRequest | str,
        *,
        config: RunConfig | dict[str, Any] | None = None,
    ) -> list[ToolResult]:
        return _run_sync(lambda: self.ainvoke(request, config=config))

    async def abatch(
        self,
        requests: Sequence[PlanRequest | str],
        *,
        config: RunConfig | dict[str, Any] | None = None,
        return_exceptions: bool = False,
    ) -> list[list[ToolResult] | BaseException]:
        run_config = _coerce_config(config)
        request_count = len(requests)
        if request_count > run_config.max_batch_size:
            raise ValueError(
                "batch request count exceeds RunConfig.max_batch_size "
                f"({request_count} > {run_config.max_batch_size})"
            )
        if request_count == 0:
            return []

        results: list[list[ToolResult] | BaseException | None] = [
            None
        ] * request_count
        next_index = 0

        async def worker() -> None:
            nonlocal next_index
            while next_index < request_count:
                index = next_index
                next_index += 1
                try:
                    results[index] = await self.ainvoke(
                        requests[index],
                        config=run_config,
                    )
                except Exception as exc:
                    if not return_exceptions:
                        raise
                    results[index] = exc

        worker_count = min(run_config.max_concurrency, request_count)
        workers = [
            asyncio.create_task(worker())
            for _ in range(worker_count)
        ]
        try:
            await asyncio.gather(*workers)
        finally:
            for task in workers:
                if not task.done():
                    task.cancel()
            if workers:
                await asyncio.gather(*workers, return_exceptions=True)

        if any(item is None for item in results):
            raise ExecutionInvariantError(
                "bounded batch workers completed without producing every result"
            )
        return [
            item
            for item in results
            if item is not None
        ]

    def batch(
        self,
        requests: Sequence[PlanRequest | str],
        *,
        config: RunConfig | dict[str, Any] | None = None,
        return_exceptions: bool = False,
    ) -> list[list[ToolResult] | BaseException]:
        return _run_sync(
            lambda: self.abatch(
                requests,
                config=config,
                return_exceptions=return_exceptions,
            )
        )

    async def abatch_as_completed(
        self,
        requests: Sequence[PlanRequest | str],
        *,
        config: RunConfig | dict[str, Any] | None = None,
        return_exceptions: bool = False,
    ) -> AsyncIterator[tuple[int, list[ToolResult] | Exception]]:
        run_config = _coerce_config(config)
        request_count = len(requests)
        if request_count > run_config.max_batch_size:
            raise ValueError(
                "batch request count exceeds RunConfig.max_batch_size "
                f"({request_count} > {run_config.max_batch_size})"
            )
        if request_count == 0:
            return

        completed_queue: asyncio.Queue[
            tuple[int, list[ToolResult] | Exception]
        ] = asyncio.Queue(maxsize=run_config.max_concurrency)
        next_index = 0

        async def worker() -> None:
            nonlocal next_index
            while next_index < request_count:
                index = next_index
                next_index += 1
                try:
                    outcome: list[ToolResult] | Exception = await self.ainvoke(
                        requests[index],
                        config=run_config,
                    )
                except Exception as exc:
                    outcome = exc
                await completed_queue.put((index, outcome))

        worker_count = min(run_config.max_concurrency, request_count)
        workers = [
            asyncio.create_task(worker())
            for _ in range(worker_count)
        ]
        try:
            for _ in range(request_count):
                index, outcome = await completed_queue.get()
                if isinstance(outcome, Exception) and not return_exceptions:
                    raise outcome
                yield index, outcome
        finally:
            for task in workers:
                if not task.done():
                    task.cancel()
            if workers:
                await asyncio.gather(*workers, return_exceptions=True)

    def batch_as_completed(
        self,
        requests: Sequence[PlanRequest | str],
        *,
        config: RunConfig | dict[str, Any] | None = None,
        return_exceptions: bool = False,
    ) -> Iterator[tuple[int, list[ToolResult] | Exception]]:
        return _stream_sync(
            lambda: self.abatch_as_completed(
                requests,
                config=config,
                return_exceptions=return_exceptions,
            )
        )

    async def astream(
        self,
        request: PlanRequest | str,
        *,
        config: RunConfig | dict[str, Any] | None = None,
    ) -> AsyncIterator[ToolResult]:
        run_config = _coerce_run_config(config)
        with _principal_execution_context(run_config.principal):
            plan = await self.aplan_executable(request)

        self._validate_plan_authorization(
            plan,
            run_config.principal,
            run_id=run_config.run_id,
            principal_audit_id=run_config.principal_audit_id,
            phase="execution",
        )

        if run_config.execution_mode == "parallel_read_only":
            iterator = self.executor.execute_parallel_read_only_iter(
                plan,
                retry=run_config.retry,
                budget=run_config.budget,
                max_concurrency=run_config.max_parallel_calls,
            )
            while True:
                try:
                    with _principal_execution_context(run_config.principal):
                        _, result = await anext(iterator)
                except StopAsyncIteration:
                    break
                yield result
            return

        iterator = self.executor.execute_iter(
            plan,
            retry=run_config.retry,
            budget=run_config.budget,
        )
        while True:
            try:
                with _principal_execution_context(run_config.principal):
                    result = await anext(iterator)
            except StopAsyncIteration:
                break
            yield result

    def stream(
        self,
        request: PlanRequest | str,
        *,
        config: RunConfig | dict[str, Any] | None = None,
    ) -> Iterator[ToolResult]:
        return _stream_sync(lambda: self.astream(request, config=config))

    async def astream_events(
        self,
        request: PlanRequest | str,
        *,
        config: RunConfig | dict[str, Any] | None = None,
        trace_store: RunTraceStore | None = None,
    ) -> AsyncIterator[RunEvent]:
        run_config = _coerce_run_config(config)
        trace_redactor = TraceRedactor(run_config.trace_redaction)

        async def emit(event: RunEvent) -> RunEvent:
            emitted = (
                event.model_copy(deep=True)
                if run_config.raw_trace_payloads
                else trace_redactor.redact_event(event)
            )
            if trace_store is not None:
                try:
                    await append_run_event_async(trace_store, emitted)
                except Exception as exc:
                    raise TracePersistenceError(
                        (
                            "run event persistence failed after runtime event "
                            f"{emitted.event!r} sequence={emitted.sequence}"
                        ),
                        event=emitted.model_copy(deep=True),
                        execution_succeeded=emitted.event in {"tool.end", "run.end"},
                    ) from exc
            return emitted
        run_id = run_config.run_id or uuid4().hex
        sequence = 0

        request_payload: dict[str, Any] = {
            "input_type": type(request).__name__,
        }
        if run_config.include_payloads:
            request_payload["input"] = (
                request.model_dump(mode="json")
                if isinstance(request, PlanRequest)
                else request
            )

        yield await emit(RunEvent.create(
            event="run.start",
            run_id=run_id,
            sequence=sequence,
            config=run_config,
            data=request_payload,
        ))
        sequence += 1

        try:
            with _principal_execution_context(run_config.principal):
                plan = await self.aplan_executable(request)
        except Exception as exc:
            data: dict[str, Any] = {"error_type": type(exc).__name__, "stage": "planning"}
            if isinstance(exc, AuthorizationAuditDeliveryError):
                data["audit_delivery_failed"] = True
                data["authorization_effect"] = exc.decision_effect
                data["authorization_denied"] = exc.authorization_denied
            if run_config.include_payloads:
                data["message"] = str(exc)
            yield await emit(RunEvent.create(
                event="run.error",
                run_id=run_id,
                sequence=sequence,
                config=run_config,
                data=data,
            ))
            raise

        try:
            self._validate_plan_authorization(
                plan,
                run_config.principal,
                run_id=run_id,
                principal_audit_id=run_config.principal_audit_id,
                phase="execution",
            )
        except Exception as exc:
            data: dict[str, Any] = {"error_type": type(exc).__name__, "stage": "authorization"}
            if isinstance(exc, AuthorizationAuditDeliveryError):
                data["audit_delivery_failed"] = True
                data["authorization_effect"] = exc.decision_effect
                data["authorization_denied"] = exc.authorization_denied
            if run_config.include_payloads:
                data["message"] = str(exc)
            yield await emit(RunEvent.create(
                event="run.error",
                run_id=run_id,
                sequence=sequence,
                config=run_config,
                data=data,
            ))
            raise

        plan_data: dict[str, Any] = {
            "call_count": len(plan.calls),
            "fallback_route_count": len(plan.fallback_routes),
            "warnings": list(plan.warnings),
            "execution_mode": run_config.execution_mode,
        }
        if run_config.include_payloads:
            plan_data["plan"] = plan.model_dump(mode="json")
        yield await emit(RunEvent.create(
            event="plan.end",
            run_id=run_id,
            sequence=sequence,
            config=run_config,
            data=plan_data,
        ))
        sequence += 1

        if run_config.execution_mode == "parallel_read_only":
            try:
                with _principal_execution_context(run_config.principal):
                    self.executor.validate_parallel_read_only(plan)
            except Exception as exc:
                error_data: dict[str, Any] = {
                    "error_type": type(exc).__name__,
                    "stage": "execution",
                    "phase": "parallel_preflight",
                }
                if run_config.include_payloads:
                    error_data["message"] = str(exc)
                yield await emit(RunEvent.create(
                    event="run.error",
                    run_id=run_id,
                    sequence=sequence,
                    config=run_config,
                    data=error_data,
                ))
                raise

            budget_tracker = ExecutionBudgetTracker(run_config.budget)
            semaphore = asyncio.Semaphore(run_config.max_parallel_calls)
            event_queue: asyncio.Queue[
                tuple[str, int, Any, Any]
            ] = asyncio.Queue(
                maxsize=max(1, run_config.max_parallel_calls * 4)
            )

            async def run_parallel_call(
                index: int,
                primary_call: Any,
            ) -> None:
                async with semaphore:
                    route = plan.fallback_route(index)
                    alternatives = route.alternatives if route is not None else []
                    original_chain = [primary_call, *alternatives]
                    try:
                        chain = (
                            self.executor.ordered_available_fallback_chain(
                                primary_call,
                                alternatives,
                            )
                            if alternatives
                            else [primary_call]
                        )
                    except Exception as exc:
                        await event_queue.put(
                            ("preflight_error", index, primary_call, exc)
                        )
                        return

                    if chain and chain[0] is not primary_call:
                        await event_queue.put(
                            (
                                "cooldown_fallback",
                                index,
                                primary_call,
                                (chain[0], original_chain, chain),
                            )
                        )

                    for candidate_index, call in enumerate(chain):
                        original_candidate_index = next(
                            position
                            for position, candidate in enumerate(original_chain)
                            if candidate is call
                        )
                        await event_queue.put(
                            ("start", index, call, original_candidate_index)
                        )
                        try:
                            with _principal_execution_context(run_config.principal):
                                result = await self.executor.execute_call(
                                    call,
                                    retry=run_config.retry,
                                    budget=run_config.budget,
                                    _tracker=budget_tracker,
                                )
                        except InvocationUnavailableError as exc:
                            has_next = candidate_index + 1 < len(chain)
                            next_call = (
                                chain[candidate_index + 1]
                                if has_next
                                else None
                            )
                            await event_queue.put(
                                (
                                    "unavailable",
                                    index,
                                    call,
                                    (exc, next_call, original_candidate_index),
                                )
                            )
                            if has_next:
                                continue
                            return
                        except PostInvocationHookError as exc:
                            await event_queue.put(
                                (
                                    "post_invocation_error",
                                    index,
                                    call,
                                    (exc, original_candidate_index),
                                )
                            )
                            return
                        except Exception as exc:
                            await event_queue.put(("error", index, call, exc))
                            return
                        await event_queue.put(
                            ("end", index, call, (result, original_candidate_index))
                        )
                        return

            next_parallel_index = 0

            async def parallel_worker() -> None:
                nonlocal next_parallel_index
                while next_parallel_index < len(plan.calls):
                    index = next_parallel_index
                    next_parallel_index += 1
                    await run_parallel_call(index, plan.calls[index])

            worker_count = min(
                run_config.max_parallel_calls,
                len(plan.calls),
            )
            tasks = [
                asyncio.create_task(parallel_worker())
                for _ in range(worker_count)
            ]

            result_count = 0
            fallback_count = 0
            terminal_count = 0
            started_parallel_calls: dict[tuple[int, int], Any] = {}
            started_parallel_call_keys: dict[
                tuple[int, int], tuple[int, int]
            ] = {}
            terminal_parallel_calls: set[tuple[int, int]] = set()
            started_primary_indexes: set[int] = set()

            async def abort_parallel_siblings(
                *,
                cause_error_type: str,
            ) -> tuple[list[RunEvent], list[int], int]:
                nonlocal sequence, result_count

                for task in tasks:
                    if not task.done():
                        task.cancel()
                if tasks:
                    await asyncio.gather(*tasks, return_exceptions=True)

                pending_events: list[tuple[str, int, Any, Any]] = []
                while True:
                    try:
                        pending_events.append(event_queue.get_nowait())
                    except asyncio.QueueEmpty:
                        break

                emitted_events: list[RunEvent] = []
                for pending_kind, pending_index, pending_call, pending_payload in pending_events:
                    parallel_key: tuple[int, int] | None = None

                    if pending_kind == "start":
                        candidate_index = int(pending_payload)
                        parallel_key = (pending_index, candidate_index)
                        if parallel_key in started_parallel_calls:
                            continue
                        start_data: dict[str, Any] = {
                            "argument_names": sorted(pending_call.arguments),
                            "fields": list(pending_call.fields),
                            "fallback_candidate_index": candidate_index,
                            "primary_call_index": pending_index,
                        }
                        if run_config.include_payloads:
                            start_data["arguments"] = dict(pending_call.arguments)
                        emitted_events.append(
                            await emit(
                                RunEvent.create(
                                    event="tool.start",
                                    run_id=run_id,
                                    sequence=sequence,
                                    config=run_config,
                                    tool=pending_call.tool,
                                    endpoint=pending_call.endpoint,
                                    data=start_data,
                                )
                            )
                        )
                        sequence += 1
                        started_parallel_calls[parallel_key] = pending_call
                        started_parallel_call_keys[
                            (pending_index, id(pending_call))
                        ] = parallel_key
                        started_primary_indexes.add(pending_index)
                        continue

                    if pending_kind == "end":
                        pending_result, candidate_index = pending_payload
                        if not isinstance(pending_result, ToolResult):
                            raise ExecutionInvariantError(
                                "parallel execution result did not preserve a ToolResult"
                            )
                        parallel_key = (pending_index, int(candidate_index))
                        if (
                            parallel_key not in started_parallel_calls
                            or parallel_key in terminal_parallel_calls
                        ):
                            continue
                        end_data: dict[str, Any] = {
                            "projected_fields": list(pending_result.projected_fields),
                            "fallback_used": int(candidate_index) > 0,
                            "primary_call_index": pending_index,
                            "fallback_candidate_index": int(candidate_index),
                        }
                        if run_config.include_payloads:
                            end_data["result"] = pending_result.model_dump(mode="json")
                        emitted_events.append(
                            await emit(
                                RunEvent.create(
                                    event="tool.end",
                                    run_id=run_id,
                                    sequence=sequence,
                                    config=run_config,
                                    tool=pending_result.tool,
                                    endpoint=pending_result.endpoint,
                                    data=end_data,
                                )
                            )
                        )
                        sequence += 1
                        result_count += 1
                        terminal_parallel_calls.add(parallel_key)
                        continue

                    if pending_kind == "post_invocation_error":
                        if (
                            not isinstance(pending_payload, tuple)
                            or len(pending_payload) != 2
                        ):
                            raise ExecutionInvariantError(
                                "parallel execution event payload violated the internal "
                                "contract: 'post_invocation_error' expected a 2-item tuple"
                            )
                        post_error, candidate_index = pending_payload
                        if not isinstance(post_error, PostInvocationHookError):
                            raise ExecutionInvariantError(
                                "parallel execution event payload violated the internal "
                                "contract: 'post_invocation_error' expected "
                                "PostInvocationHookError"
                            )
                        post_result = post_error.result
                        if not isinstance(post_result, ToolResult):
                            raise ExecutionInvariantError(
                                "post-invocation hook error did not preserve a ToolResult"
                            )
                        parallel_key = (pending_index, int(candidate_index))
                        if (
                            parallel_key not in started_parallel_calls
                            or parallel_key in terminal_parallel_calls
                        ):
                            continue
                        end_data = {
                            "projected_fields": list(post_result.projected_fields),
                            "fallback_used": int(candidate_index) > 0,
                            "primary_call_index": pending_index,
                            "fallback_candidate_index": int(candidate_index),
                            "execution_succeeded": True,
                            "post_invocation_stage": "after_hook",
                            "post_invocation_error_type": type(post_error).__name__,
                        }
                        if run_config.include_payloads:
                            end_data["result"] = post_result.model_dump(mode="json")
                        emitted_events.append(
                            await emit(
                                RunEvent.create(
                                    event="tool.end",
                                    run_id=run_id,
                                    sequence=sequence,
                                    config=run_config,
                                    tool=post_result.tool,
                                    endpoint=post_result.endpoint,
                                    data=end_data,
                                )
                            )
                        )
                        sequence += 1
                        result_count += 1
                        terminal_parallel_calls.add(parallel_key)
                        continue

                    if pending_kind == "unavailable":
                        exc, next_call, candidate_index = (
                            _require_unavailable_event_payload(pending_payload)
                        )
                        parallel_key = (pending_index, candidate_index)
                        if (
                            parallel_key not in started_parallel_calls
                            or parallel_key in terminal_parallel_calls
                        ):
                            continue
                        error_data: dict[str, Any] = {
                            "error_type": type(exc).__name__,
                            "fallback_eligible": next_call is not None,
                            "fallback_aborted_by_sibling": next_call is not None,
                            "primary_call_index": pending_index,
                            "fallback_candidate_index": candidate_index,
                        }
                        if run_config.include_payloads:
                            error_data["message"] = str(exc)
                        emitted_events.append(
                            await emit(
                                RunEvent.create(
                                    event="tool.error",
                                    run_id=run_id,
                                    sequence=sequence,
                                    config=run_config,
                                    tool=pending_call.tool,
                                    endpoint=pending_call.endpoint,
                                    data=error_data,
                                )
                            )
                        )
                        sequence += 1
                        terminal_parallel_calls.add(parallel_key)
                        continue

                    if pending_kind == "error":
                        pending_error = _require_execution_event_exception(
                            pending_payload,
                            event_kind=pending_kind,
                        )
                        parallel_key = started_parallel_call_keys.get(
                            (pending_index, id(pending_call))
                        )
                        if (
                            parallel_key is None
                            or parallel_key in terminal_parallel_calls
                        ):
                            continue
                        error_data = {
                            "error_type": type(pending_error).__name__,
                            "primary_call_index": pending_index,
                            "fallback_candidate_index": parallel_key[1],
                        }
                        if run_config.include_payloads:
                            error_data["message"] = str(pending_error)
                        emitted_events.append(
                            await emit(
                                RunEvent.create(
                                    event="tool.error",
                                    run_id=run_id,
                                    sequence=sequence,
                                    config=run_config,
                                    tool=pending_call.tool,
                                    endpoint=pending_call.endpoint,
                                    data=error_data,
                                )
                            )
                        )
                        sequence += 1
                        terminal_parallel_calls.add(parallel_key)

                indeterminate_count = 0
                for parallel_key in sorted(started_parallel_calls):
                    if parallel_key in terminal_parallel_calls:
                        continue
                    pending_call = started_parallel_calls[parallel_key]
                    emitted_events.append(
                        await emit(
                            RunEvent.create(
                                event="tool.error",
                                run_id=run_id,
                                sequence=sequence,
                                config=run_config,
                                tool=pending_call.tool,
                                endpoint=pending_call.endpoint,
                                data={
                                    "error_type": "ParallelSiblingFailureAbort",
                                    "termination_reason": "sibling_failure",
                                    "execution_state": "indeterminate",
                                    "sibling_error_type": cause_error_type,
                                    "primary_call_index": parallel_key[0],
                                    "fallback_candidate_index": parallel_key[1],
                                },
                            )
                        )
                    )
                    sequence += 1
                    indeterminate_count += 1
                    terminal_parallel_calls.add(parallel_key)

                cancelled_before_start = sorted(
                    set(range(len(plan.calls))) - started_primary_indexes
                )
                return emitted_events, cancelled_before_start, indeterminate_count

            try:
                while terminal_count < len(plan.calls):
                    kind, index, call, payload = await event_queue.get()

                    if kind == "preflight_error":
                        terminal_count += 1
                        payload = _require_execution_event_exception(
                            payload,
                            event_kind=kind,
                        )
                        error_data: dict[str, Any] = {
                            "error_type": type(payload).__name__,
                            "stage": "execution",
                            "phase": "fallback_preflight",
                        }
                        if run_config.include_payloads:
                            error_data["message"] = str(payload)
                        (
                            aborted_events,
                            cancelled_before_start,
                            indeterminate_count,
                        ) = await abort_parallel_siblings(
                            cause_error_type=type(payload).__name__,
                        )
                        for aborted_event in aborted_events:
                            yield aborted_event
                        error_data[
                            "cancelled_before_start_primary_call_indexes"
                        ] = cancelled_before_start
                        error_data["indeterminate_in_flight_count"] = indeterminate_count
                        yield await emit(RunEvent.create(
                            event="run.error",
                            run_id=run_id,
                            sequence=sequence,
                            config=run_config,
                            data=error_data,
                        ))
                        raise payload

                    if kind == "cooldown_fallback":
                        next_call, original_chain, available_chain = payload
                        current_tool = self.registry.get(call.tool)
                        next_tool = self.registry.get(next_call.tool)
                        scope = (
                            "same_provider"
                            if current_tool.provider is not None
                            and current_tool.provider == next_tool.provider
                            else "cross_provider"
                        )
                        skipped = [
                            f"{candidate.tool}.{candidate.endpoint}"
                            for candidate in original_chain
                            if candidate not in available_chain
                        ]
                        reason = (
                            "binding_unavailable"
                            if call.tool_fingerprint is not None
                            and not self.executor.is_binding_ready_for_contract(
                                call.tool,
                                call.tool_fingerprint,
                            )
                            else "cooldown"
                        )
                        yield await emit(RunEvent.create(
                            event="tool.fallback",
                            run_id=run_id,
                            sequence=sequence,
                            config=run_config,
                            tool=next_call.tool,
                            endpoint=next_call.endpoint,
                            data={
                                "from_tool": call.tool,
                                "from_endpoint": call.endpoint,
                                "to_tool": next_call.tool,
                                "to_endpoint": next_call.endpoint,
                                "scope": scope,
                                "provider": next_tool.provider,
                                "access_mode": next_tool.access_mode,
                                "reason": reason,
                                "skipped_unavailable": skipped,
                            },
                        ))
                        sequence += 1
                        fallback_count += 1
                        continue

                    if kind == "start":
                        candidate_index = int(payload)
                        start_data: dict[str, Any] = {
                            "argument_names": sorted(call.arguments),
                            "fields": list(call.fields),
                            "fallback_candidate_index": candidate_index,
                            "primary_call_index": index,
                        }
                        if run_config.include_payloads:
                            start_data["arguments"] = dict(call.arguments)
                        yield await emit(RunEvent.create(
                            event="tool.start",
                            run_id=run_id,
                            sequence=sequence,
                            config=run_config,
                            tool=call.tool,
                            endpoint=call.endpoint,
                            data=start_data,
                        ))
                        sequence += 1
                        parallel_key = (index, candidate_index)
                        started_parallel_calls[parallel_key] = call
                        started_parallel_call_keys[(index, id(call))] = parallel_key
                        started_primary_indexes.add(index)
                        continue

                    if kind == "unavailable":
                        exc, next_call, candidate_index = (
                            _require_unavailable_event_payload(payload)
                        )
                        error_data: dict[str, Any] = {
                            "error_type": type(exc).__name__,
                            "fallback_eligible": next_call is not None,
                            "primary_call_index": index,
                            "fallback_candidate_index": candidate_index,
                        }
                        if run_config.include_payloads:
                            error_data["message"] = str(exc)
                        yield await emit(RunEvent.create(
                            event="tool.error",
                            run_id=run_id,
                            sequence=sequence,
                            config=run_config,
                            tool=call.tool,
                            endpoint=call.endpoint,
                            data=error_data,
                        ))
                        sequence += 1
                        terminal_parallel_calls.add((index, candidate_index))

                        if next_call is None:
                            terminal_count += 1
                            (
                                aborted_events,
                                cancelled_before_start,
                                indeterminate_count,
                            ) = await abort_parallel_siblings(
                                cause_error_type=type(exc).__name__,
                            )
                            for aborted_event in aborted_events:
                                yield aborted_event
                            yield await emit(RunEvent.create(
                                event="run.error",
                                run_id=run_id,
                                sequence=sequence,
                                config=run_config,
                                data={
                                    "error_type": type(exc).__name__,
                                    "stage": "execution",
                                    "cancelled_before_start_primary_call_indexes": (
                                        cancelled_before_start
                                    ),
                                    "indeterminate_in_flight_count": indeterminate_count,
                                },
                            ))
                            raise exc

                        current_tool = self.registry.get(call.tool)
                        next_tool = self.registry.get(next_call.tool)
                        scope = (
                            "same_provider"
                            if current_tool.provider is not None
                            and current_tool.provider == next_tool.provider
                            else "cross_provider"
                        )
                        yield await emit(RunEvent.create(
                            event="tool.fallback",
                            run_id=run_id,
                            sequence=sequence,
                            config=run_config,
                            tool=next_call.tool,
                            endpoint=next_call.endpoint,
                            data={
                                "from_tool": call.tool,
                                "from_endpoint": call.endpoint,
                                "to_tool": next_call.tool,
                                "to_endpoint": next_call.endpoint,
                                "scope": scope,
                                "provider": next_tool.provider,
                                "access_mode": next_tool.access_mode,
                                "fallback_candidate_index": candidate_index + 1,
                            },
                        ))
                        sequence += 1
                        fallback_count += 1
                        continue

                    if kind == "post_invocation_error":
                        terminal_count += 1
                        if not isinstance(payload, tuple) or len(payload) != 2:
                            raise ExecutionInvariantError(
                                "parallel execution event payload violated the internal contract: "
                                "'post_invocation_error' expected a 2-item tuple"
                            )
                        post_error, candidate_index = payload
                        if not isinstance(post_error, PostInvocationHookError):
                            raise ExecutionInvariantError(
                                "parallel execution event payload violated the internal contract: "
                                "'post_invocation_error' expected PostInvocationHookError"
                            )
                        if (
                            isinstance(candidate_index, bool)
                            or not isinstance(candidate_index, int)
                            or candidate_index < 0
                        ):
                            raise ExecutionInvariantError(
                                "parallel execution event payload violated the internal contract: "
                                "'post_invocation_error' expected a non-negative candidate index"
                            )
                        post_result = post_error.result
                        if not isinstance(post_result, ToolResult):
                            raise ExecutionInvariantError(
                                "post-invocation hook error did not preserve a ToolResult"
                            )
                        end_data: dict[str, Any] = {
                            "projected_fields": list(post_result.projected_fields),
                            "fallback_used": candidate_index > 0,
                            "primary_call_index": index,
                            "fallback_candidate_index": candidate_index,
                            "execution_succeeded": True,
                            "post_invocation_stage": "after_hook",
                            "post_invocation_error_type": type(post_error).__name__,
                        }
                        if run_config.include_payloads:
                            end_data["result"] = post_result.model_dump(mode="json")
                        yield await emit(RunEvent.create(
                            event="tool.end",
                            run_id=run_id,
                            sequence=sequence,
                            config=run_config,
                            tool=post_result.tool,
                            endpoint=post_result.endpoint,
                            data=end_data,
                        ))
                        sequence += 1
                        result_count += 1
                        terminal_parallel_calls.add((index, candidate_index))
                        (
                            aborted_events,
                            cancelled_before_start,
                            indeterminate_count,
                        ) = await abort_parallel_siblings(
                            cause_error_type=type(post_error).__name__,
                        )
                        for aborted_event in aborted_events:
                            yield aborted_event
                        run_error_data: dict[str, Any] = {
                            "error_type": type(post_error).__name__,
                            "stage": "post_invocation_hook",
                            "execution_succeeded": True,
                            "cancelled_before_start_primary_call_indexes": (
                                cancelled_before_start
                            ),
                            "indeterminate_in_flight_count": indeterminate_count,
                        }
                        if run_config.include_payloads:
                            run_error_data["message"] = str(post_error)
                        yield await emit(RunEvent.create(
                            event="run.error",
                            run_id=run_id,
                            sequence=sequence,
                            config=run_config,
                            data=run_error_data,
                        ))
                        raise post_error

                    if kind == "error":
                        terminal_count += 1
                        payload = _require_execution_event_exception(
                            payload,
                            event_kind=kind,
                        )
                        parallel_key = started_parallel_call_keys.get(
                            (index, id(call))
                        )
                        if parallel_key is None:
                            raise ExecutionInvariantError(
                                "parallel tool error did not have a matching tool.start"
                            )
                        error_data = {
                            "error_type": type(payload).__name__,
                            "primary_call_index": index,
                            "fallback_candidate_index": parallel_key[1],
                        }
                        if run_config.include_payloads:
                            error_data["message"] = str(payload)
                        yield await emit(RunEvent.create(
                            event="tool.error",
                            run_id=run_id,
                            sequence=sequence,
                            config=run_config,
                            tool=call.tool,
                            endpoint=call.endpoint,
                            data=error_data,
                        ))
                        sequence += 1
                        terminal_parallel_calls.add(parallel_key)
                        (
                            aborted_events,
                            cancelled_before_start,
                            indeterminate_count,
                        ) = await abort_parallel_siblings(
                            cause_error_type=type(payload).__name__,
                        )
                        for aborted_event in aborted_events:
                            yield aborted_event
                        yield await emit(RunEvent.create(
                            event="run.error",
                            run_id=run_id,
                            sequence=sequence,
                            config=run_config,
                            data={
                                "error_type": type(payload).__name__,
                                "stage": "execution",
                                "cancelled_before_start_primary_call_indexes": (
                                    cancelled_before_start
                                ),
                                "indeterminate_in_flight_count": indeterminate_count,
                            },
                        ))
                        raise payload

                    if kind != "end":
                        raise RuntimeError("invalid parallel execution event")

                    terminal_count += 1
                    result, candidate_index = payload
                    if not isinstance(result, ToolResult):
                        raise RuntimeError("invalid parallel execution result")
                    end_data: dict[str, Any] = {
                        "projected_fields": list(result.projected_fields),
                        "fallback_used": candidate_index > 0,
                        "primary_call_index": index,
                        "fallback_candidate_index": candidate_index,
                    }
                    if run_config.include_payloads:
                        end_data["result"] = result.model_dump(mode="json")
                    yield await emit(RunEvent.create(
                        event="tool.end",
                        run_id=run_id,
                        sequence=sequence,
                        config=run_config,
                        tool=result.tool,
                        endpoint=result.endpoint,
                        data=end_data,
                    ))
                    sequence += 1
                    result_count += 1
                    terminal_parallel_calls.add((index, int(candidate_index)))
            finally:
                for task in tasks:
                    if not task.done():
                        task.cancel()
                if tasks:
                    await asyncio.gather(*tasks, return_exceptions=True)

            yield await emit(RunEvent.create(
                event="run.end",
                run_id=run_id,
                sequence=sequence,
                config=run_config,
                data={
                    "result_count": result_count,
                    "fallback_count": fallback_count,
                },
            ))
            return

        result_count = 0
        fallback_count = 0
        budget_tracker = ExecutionBudgetTracker(run_config.budget)
        for primary_index, primary_call in enumerate(plan.calls):
            route = plan.fallback_route(primary_index)
            alternatives = route.alternatives if route is not None else []
            original_chain = [primary_call, *alternatives]
            result: ToolResult | None = None

            try:
                chain = (
                    self.executor.ordered_available_fallback_chain(
                        primary_call,
                        alternatives,
                    )
                    if alternatives
                    else [primary_call]
                )
            except Exception as exc:
                error_data: dict[str, Any] = {
                    "error_type": type(exc).__name__,
                    "stage": "execution",
                    "phase": "fallback_preflight",
                }
                if run_config.include_payloads:
                    error_data["message"] = str(exc)
                yield await emit(RunEvent.create(
                    event="run.error",
                    run_id=run_id,
                    sequence=sequence,
                    config=run_config,
                    data=error_data,
                ))
                raise

            if chain and chain[0] is not primary_call:
                next_call = chain[0]
                next_tool = self.registry.get(next_call.tool)
                current_tool = self.registry.get(primary_call.tool)
                scope = (
                    "same_provider"
                    if current_tool.provider is not None
                    and current_tool.provider == next_tool.provider
                    else "cross_provider"
                )
                skipped = [
                    f"{call.tool}.{call.endpoint}"
                    for call in original_chain
                    if call not in chain
                ]
                reason = (
                    "binding_unavailable"
                    if primary_call.tool_fingerprint is not None
                    and not self.executor.is_binding_ready_for_contract(
                        primary_call.tool,
                        primary_call.tool_fingerprint,
                    )
                    else "cooldown"
                )
                yield await emit(RunEvent.create(
                    event="tool.fallback",
                    run_id=run_id,
                    sequence=sequence,
                    config=run_config,
                    tool=next_call.tool,
                    endpoint=next_call.endpoint,
                    data={
                        "from_tool": primary_call.tool,
                        "from_endpoint": primary_call.endpoint,
                        "to_tool": next_call.tool,
                        "to_endpoint": next_call.endpoint,
                        "scope": scope,
                        "provider": next_tool.provider,
                        "access_mode": next_tool.access_mode,
                        "reason": reason,
                        "skipped_unavailable": skipped,
                    },
                ))
                sequence += 1
                fallback_count += 1

            for candidate_index, call in enumerate(chain):
                original_candidate_index = next(
                    index
                    for index, candidate in enumerate(original_chain)
                    if candidate is call
                )
                start_data: dict[str, Any] = {
                    "argument_names": sorted(call.arguments),
                    "fields": list(call.fields),
                    "fallback_candidate_index": original_candidate_index,
                    "primary_call_index": primary_index,
                }
                if run_config.include_payloads:
                    start_data["arguments"] = dict(call.arguments)
                yield await emit(RunEvent.create(
                    event="tool.start",
                    run_id=run_id,
                    sequence=sequence,
                    config=run_config,
                    tool=call.tool,
                    endpoint=call.endpoint,
                    data=start_data,
                ))
                sequence += 1

                try:
                    with _principal_execution_context(run_config.principal):
                        result = await self.executor.execute_call(
                            call,
                            retry=run_config.retry,
                            budget=run_config.budget,
                            _tracker=budget_tracker,
                        )
                except InvocationUnavailableError as exc:
                    has_next = candidate_index + 1 < len(chain)
                    error_data: dict[str, Any] = {
                        "error_type": type(exc).__name__,
                        "fallback_eligible": has_next,
                        "primary_call_index": primary_index,
                        "fallback_candidate_index": original_candidate_index,
                    }
                    if run_config.include_payloads:
                        error_data["message"] = str(exc)
                    yield await emit(RunEvent.create(
                        event="tool.error",
                        run_id=run_id,
                        sequence=sequence,
                        config=run_config,
                        tool=call.tool,
                        endpoint=call.endpoint,
                        data=error_data,
                    ))
                    sequence += 1

                    if not has_next:
                        yield await emit(RunEvent.create(
                            event="run.error",
                            run_id=run_id,
                            sequence=sequence,
                            config=run_config,
                            data={
                                "error_type": type(exc).__name__,
                                "stage": "execution",
                            },
                        ))
                        raise

                    next_call = chain[candidate_index + 1]
                    current_tool = self.registry.get(call.tool)
                    next_tool = self.registry.get(next_call.tool)
                    scope = (
                        "same_provider"
                        if current_tool.provider is not None
                        and current_tool.provider == next_tool.provider
                        else "cross_provider"
                    )
                    yield await emit(RunEvent.create(
                        event="tool.fallback",
                        run_id=run_id,
                        sequence=sequence,
                        config=run_config,
                        tool=next_call.tool,
                        endpoint=next_call.endpoint,
                        data={
                            "from_tool": call.tool,
                            "from_endpoint": call.endpoint,
                            "to_tool": next_call.tool,
                            "to_endpoint": next_call.endpoint,
                            "scope": scope,
                            "provider": next_tool.provider,
                            "access_mode": next_tool.access_mode,
                        },
                    ))
                    sequence += 1
                    fallback_count += 1
                    continue
                except PostInvocationHookError as exc:
                    post_result = exc.result
                    if not isinstance(post_result, ToolResult):
                        raise ExecutionInvariantError(
                            "post-invocation hook error did not preserve a ToolResult"
                        ) from exc
                    end_data: dict[str, Any] = {
                        "projected_fields": list(post_result.projected_fields),
                        "fallback_used": candidate_index > 0,
                        "primary_call_index": primary_index,
                        "fallback_candidate_index": original_candidate_index,
                        "execution_succeeded": True,
                        "post_invocation_stage": "after_hook",
                        "post_invocation_error_type": type(exc).__name__,
                    }
                    if run_config.include_payloads:
                        end_data["result"] = post_result.model_dump(mode="json")
                    yield await emit(RunEvent.create(
                        event="tool.end",
                        run_id=run_id,
                        sequence=sequence,
                        config=run_config,
                        tool=post_result.tool,
                        endpoint=post_result.endpoint,
                        data=end_data,
                    ))
                    sequence += 1
                    result_count += 1
                    run_error_data: dict[str, Any] = {
                        "error_type": type(exc).__name__,
                        "stage": "post_invocation_hook",
                        "execution_succeeded": True,
                    }
                    if run_config.include_payloads:
                        run_error_data["message"] = str(exc)
                    yield await emit(RunEvent.create(
                        event="run.error",
                        run_id=run_id,
                        sequence=sequence,
                        config=run_config,
                        data=run_error_data,
                    ))
                    raise
                except Exception as exc:
                    error_data = {
                        "error_type": type(exc).__name__,
                        "primary_call_index": primary_index,
                        "fallback_candidate_index": original_candidate_index,
                    }
                    if run_config.include_payloads:
                        error_data["message"] = str(exc)
                    yield await emit(RunEvent.create(
                        event="tool.error",
                        run_id=run_id,
                        sequence=sequence,
                        config=run_config,
                        tool=call.tool,
                        endpoint=call.endpoint,
                        data=error_data,
                    ))
                    sequence += 1
                    yield await emit(RunEvent.create(
                        event="run.error",
                        run_id=run_id,
                        sequence=sequence,
                        config=run_config,
                        data={
                            "error_type": type(exc).__name__,
                            "stage": "execution",
                        },
                    ))
                    raise

                end_data: dict[str, Any] = {
                    "projected_fields": list(result.projected_fields),
                    "fallback_used": candidate_index > 0,
                    "primary_call_index": primary_index,
                    "fallback_candidate_index": original_candidate_index,
                }
                if run_config.include_payloads:
                    end_data["result"] = result.model_dump(mode="json")
                yield await emit(RunEvent.create(
                    event="tool.end",
                    run_id=run_id,
                    sequence=sequence,
                    config=run_config,
                    tool=result.tool,
                    endpoint=result.endpoint,
                    data=end_data,
                ))
                sequence += 1
                result_count += 1
                break

            if result is None:
                raise RuntimeError("fallback chain produced no terminal result")

        yield await emit(RunEvent.create(
            event="run.end",
            run_id=run_id,
            sequence=sequence,
            config=run_config,
            data={
                "result_count": result_count,
                "fallback_count": fallback_count,
            },
        ))

    async def run(
        self,
        request: PlanRequest | str,
        *,
        config: RunConfig | dict[str, Any] | None = None,
    ) -> list[ToolResult]:
        return await self.ainvoke(request, config=config)

    async def arun(
        self,
        request: PlanRequest | str,
        *,
        config: RunConfig | dict[str, Any] | None = None,
    ) -> list[ToolResult]:
        return await self.ainvoke(request, config=config)


class ConfiguredSchemaRouter:
    """SchemaRouter with an immutable default RunConfig."""

    def __init__(self, router: SchemaRouter, config: RunConfig) -> None:
        self.router = router
        self.config = config

    def retrieve_routes(
        self,
        request: PlanRequest | str,
        *,
        k: int = 5,
    ) -> CapabilityRouteRetrieval:
        with _principal_execution_context(self.config.principal):
            return self.router.retrieve_routes(request, k=k)

    async def aretrieve_routes(
        self,
        request: PlanRequest | str,
        *,
        k: int = 5,
    ) -> CapabilityRouteRetrieval:
        with _principal_execution_context(self.config.principal):
            return await self.router.aretrieve_routes(request, k=k)

    def retrieve(
        self,
        request: PlanRequest | str,
        *,
        k: int = 5,
    ) -> CapabilityRetrieval:
        with _principal_execution_context(self.config.principal):
            return self.router.retrieve(request, k=k)

    async def aretrieve(
        self,
        request: PlanRequest | str,
        *,
        k: int = 5,
    ) -> CapabilityRetrieval:
        with _principal_execution_context(self.config.principal):
            return await self.router.aretrieve(request, k=k)

    def reretrieve_state_aware(
        self,
        request: PlanRequest | str,
        *,
        execution_state: TypedExecutionState,
        k: int = 5,
        state_requirements: dict[str, list[CapabilityFieldContract]] | None = None,
        state_preconditions: dict[str, list[CapabilityPrecondition]] | None = None,
    ) -> StateConditionedCapabilityRetrieval:
        with _principal_execution_context(self.config.principal):
            return self.router.reretrieve_state_aware(
                request,
                execution_state=execution_state,
                k=k,
                state_requirements=state_requirements,
                state_preconditions=state_preconditions,
            )

    async def areretrieve_state_aware(
        self,
        request: PlanRequest | str,
        *,
        execution_state: TypedExecutionState,
        k: int = 5,
        state_requirements: dict[str, list[CapabilityFieldContract]] | None = None,
        state_preconditions: dict[str, list[CapabilityPrecondition]] | None = None,
    ) -> StateConditionedCapabilityRetrieval:
        with _principal_execution_context(self.config.principal):
            return await self.router.areretrieve_state_aware(
                request,
                execution_state=execution_state,
                k=k,
                state_requirements=state_requirements,
                state_preconditions=state_preconditions,
            )

    def retrieve_state_aware(
        self,
        request: PlanRequest | str,
        *,
        execution_state: TypedExecutionState,
        k: int = 5,
        state_requirements: dict[str, list[CapabilityFieldContract]] | None = None,
        state_preconditions: dict[str, list[CapabilityPrecondition]] | None = None,
    ) -> StateAwareCapabilityRetrieval:
        with _principal_execution_context(self.config.principal):
            return self.router.retrieve_state_aware(
                request,
                execution_state=execution_state,
                k=k,
                state_requirements=state_requirements,
                state_preconditions=state_preconditions,
            )

    async def aretrieve_state_aware(
        self,
        request: PlanRequest | str,
        *,
        execution_state: TypedExecutionState,
        k: int = 5,
        state_requirements: dict[str, list[CapabilityFieldContract]] | None = None,
        state_preconditions: dict[str, list[CapabilityPrecondition]] | None = None,
    ) -> StateAwareCapabilityRetrieval:
        with _principal_execution_context(self.config.principal):
            return await self.router.aretrieve_state_aware(
                request,
                execution_state=execution_state,
                k=k,
                state_requirements=state_requirements,
                state_preconditions=state_preconditions,
            )

    def retrieve_executable(
        self,
        request: PlanRequest | str,
        *,
        k: int = 5,
    ) -> CapabilityRetrieval:
        with _principal_execution_context(self.config.principal):
            return self.router.retrieve_executable(request, k=k)

    async def aretrieve_executable(
        self,
        request: PlanRequest | str,
        *,
        k: int = 5,
    ) -> CapabilityRetrieval:
        with _principal_execution_context(self.config.principal):
            return await self.router.aretrieve_executable(request, k=k)

    def invoke(self, request: PlanRequest | str) -> list[ToolResult]:
        return self.router.invoke(request, config=self.config)

    async def ainvoke(self, request: PlanRequest | str) -> list[ToolResult]:
        return await self.router.ainvoke(request, config=self.config)

    def batch(
        self,
        requests: Sequence[PlanRequest | str],
        *,
        return_exceptions: bool = False,
    ) -> list[list[ToolResult] | BaseException]:
        return self.router.batch(
            requests,
            config=self.config,
            return_exceptions=return_exceptions,
        )

    async def abatch(
        self,
        requests: Sequence[PlanRequest | str],
        *,
        return_exceptions: bool = False,
    ) -> list[list[ToolResult] | BaseException]:
        return await self.router.abatch(
            requests,
            config=self.config,
            return_exceptions=return_exceptions,
        )

    def batch_as_completed(
        self,
        requests: Sequence[PlanRequest | str],
        *,
        return_exceptions: bool = False,
    ) -> Iterator[tuple[int, list[ToolResult] | Exception]]:
        return self.router.batch_as_completed(
            requests,
            config=self.config,
            return_exceptions=return_exceptions,
        )

    def abatch_as_completed(
        self,
        requests: Sequence[PlanRequest | str],
        *,
        return_exceptions: bool = False,
    ) -> AsyncIterator[tuple[int, list[ToolResult] | Exception]]:
        return self.router.abatch_as_completed(
            requests,
            config=self.config,
            return_exceptions=return_exceptions,
        )

    def stream(self, request: PlanRequest | str) -> Iterator[ToolResult]:
        return self.router.stream(request, config=self.config)

    def astream(self, request: PlanRequest | str) -> AsyncIterator[ToolResult]:
        return self.router.astream(request, config=self.config)

    def astream_events(
        self,
        request: PlanRequest | str,
        *,
        trace_store: RunTraceStore | None = None,
    ) -> AsyncIterator[RunEvent]:
        return self.router.astream_events(
            request,
            config=self.config,
            trace_store=trace_store,
        )
