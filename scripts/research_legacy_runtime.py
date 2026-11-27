"""Source-only historical lexical runtime.

The copied compatibility methods preserve the pre-cutover authorization,
data-scope, source-witness and binding checks. This class is not part of
the wheel or the public product API. It must never be a fallback for the
configured Algorithm 1 product. Historical lexical dispatch is implemented here and no longer in the
installed runtime.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any, cast

from schemarouter._schema_identity import _tokens
from schemarouter.authorization import (
    PrincipalContext,
    _current_principal_context,
    _principal_execution_context,
)
from schemarouter.capability_contracts import CapabilityFieldContract, CapabilityPrecondition
from schemarouter.errors import PolicyViolationError
from schemarouter.execution_state import TypedExecutionState
from schemarouter.models import (
    EndpointSpec,
    ExecutionPlan,
    FieldSpec,
    PaperPlanRequest,
    ScoreComponent,
    ToolSpec,
)
from schemarouter.runs import RunConfig
from schemarouter.runtime import (
    ConfiguredSchemaRouter,
    SchemaRouter,
    _coerce_config,
    _scoped_denied_field_markers,
    _scoped_echoes_denied_label,
    _scoped_public_input_schema,
    _scoped_public_output_field,
    _scoped_public_output_schema,
    _scoped_public_parameter,
    _validated_explicit_retrieval_principal,
)
from scripts.research_legacy_planning.candidate_models import CapabilityRetrieval
from scripts.research_legacy_planning.planner import QueryAnalyzer, SchemaPlanner
from scripts.research_legacy_planning.requests import PlanRequest
from scripts.research_legacy_planning.route_models import CapabilityRouteRetrieval
from scripts.research_legacy_planning.source_availability import _LegacySourceAvailability
from scripts.research_legacy_planning.state_retrieval import (
    StateAwareCapabilityRetrieval,
    filter_retrieval_by_state,
)

if TYPE_CHECKING:
    from schemarouter.field_routing_session import SchemaFieldRoutingSession
    from schemarouter.paper_planning import _PreparedPaperPlanning


def _scoped_public_score_components(
    components: list[ScoreComponent],
    *,
    visible_names: set[str],
    source_fields: list[FieldSpec],
    public_tool_identifiers: set[str],
    public_endpoint_identifiers: set[str],
    public_operation_names: set[str],
    public_tool_tokens: set[str],
    public_parameter_names: set[str],
) -> list[ScoreComponent]:
    """Publish only recognized, principal-visible score explanation labels.

    Actual planner scores, ordering, source schema and execution authority
    remain unchanged. Treat unknown/stale decision-produced score kinds as
    unreviewed metadata rather than allowing them into scoped traces.
    """
    disallowed_names = {
        label.casefold()
        for field in source_fields
        for label in (field.name, *field.aliases)
        if label.casefold() not in visible_names
    }
    allowed_matches = {
        "preferred_tool": public_tool_identifiers,
        "preferred_endpoint": public_endpoint_identifiers,
        "tool_identifier": public_tool_identifiers,
        "endpoint_identifier": public_operation_names,
        "operation_family": public_operation_names,
        "tool_token": public_tool_tokens,
        "argument_match": public_parameter_names,
        "field_exact": visible_names,
        "field_lexical": visible_names,
        "field_substring": visible_names,
    }
    safe: list[ScoreComponent] = []
    for component in components:
        # Field qualifiers, argument aliases, and any future unreviewed kinds
        # may echo source-owned descriptors not authorized for this principal.
        allowed = allowed_matches.get(component.kind)
        matched = component.matched
        if allowed is None or matched is None:
            continue
        label = matched.casefold()
        if label in disallowed_names or label not in allowed:
            continue
        safe.append(component)
    return safe



class LegacySchemaRouter(SchemaRouter):
    """Research-owned historical dispatch, using the canonical product executor."""

    def __init__(
        self,
        *,
        analyzer: QueryAnalyzer | None = None,
        structural_retrieval: bool = False,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self._source_availability = _LegacySourceAvailability(self._source_availability.predicate)
        self.planner = SchemaPlanner(
            self.registry, analyzer=analyzer, structural_retrieval=structural_retrieval,
        )
        self.planner._source_availability = self._source_availability
        self._legacy_routing = True

    def _planning_analyzer_name(self) -> str:
        if self._paper_planning is None and self._legacy_routing and self.planner is not None:
            return type(self.planner.analyzer).__name__
        return super()._planning_analyzer_name()

    @property
    def input_schema(self) -> dict[str, Any]:
        request_type = (
            PlanRequest if self._legacy_routing and self._paper_planning is None
            else PaperPlanRequest
        )
        return request_type.model_json_schema()

    def configure_field_routing(self, session: SchemaFieldRoutingSession, **kwargs: Any) -> None:
        super().configure_field_routing(session, **kwargs)
        # In-flight historical requests must not publish after paper cutover.
        self._legacy_routing = False
        self.planner = None
        self._source_availability.snapshot = None

    def _source_availability_predicate(
        self,
    ) -> Callable[[ToolSpec, EndpointSpec], bool] | None:
        """Return the shared source authority, not a lexical scoring decision."""
        authority = self._source_availability
        # During compatibility migration a replaced planner must not silently
        # introduce another registry or availability authority.
        planner = self.planner
        if (
            self._source_registry is not self.registry
            or self.executor.registry is not self.registry
            or type(authority) is not _LegacySourceAvailability
            or (not self._legacy_routing and authority.snapshot is not None)
            or (planner is not None and (
                not self._legacy_routing or planner.registry is not self.registry
                or planner._source_availability is not authority
                or planner.availability_predicate is not authority.predicate
            ))
            or (self._legacy_routing and planner is None)
        ):
            raise PolicyViolationError("retrieval authority changed: source availability mismatch")
        return authority.predicate

    def with_config(
        self, config: RunConfig | dict[str, Any],
    ) -> ConfiguredSchemaRouter:
        if self._paper_planning is not None:
            return super().with_config(config)
        return LegacyConfiguredSchemaRouter(self, _coerce_config(config))

    def _request_trace_input(self, request: PlanRequest | PaperPlanRequest | str) -> Any:
        if isinstance(request, PlanRequest):
            return request.model_dump(mode="json")
        return super()._request_trace_input(request)

    def _paper_configuration_for(
        self, request: PlanRequest | PaperPlanRequest | str,
    ) -> _PreparedPaperPlanning | None:
        configured = self._paper_planning
        if configured is None and isinstance(request, PaperPlanRequest):
            raise ValueError(
                "PaperPlanRequest requires configure_field_routing; no lexical fallback",
            )
        if configured is not None and isinstance(request, PlanRequest):
            raise ValueError(
                "configured paper planning requires str or PaperPlanRequest, not PlanRequest",
            )
        if configured is None and not self._legacy_routing:
            raise PolicyViolationError(
                "configure_field_routing is required; lexical planning is unavailable",
            )
        return configured

    def _require_legacy_planning_mode(self) -> SchemaPlanner:
        planner = self.planner
        if self._paper_planning is not None or not self._legacy_routing or planner is None:
            raise PolicyViolationError(
                "paper routing uses Algorithm 1; lexical planning is unavailable",
            )
        self._source_availability_predicate()
        return planner

    def _legacy_plan(
        self, request: PlanRequest | str, principal: PrincipalContext | None,
        *, executable_only: bool,
    ) -> ExecutionPlan:
        """Temporary compatibility dispatch; never publish after paper configuration."""
        planner = self._require_legacy_planning_mode()
        predicate = self._combined_availability_predicate(
            principal, self._binding_ready if executable_only else None,
        )
        if predicate is None:
            if executable_only:
                raise RuntimeError("executable planning requires an availability predicate")
            plan = planner.plan(request)
        elif (
            self.authorization_policy is not None
            and self.authorization_policy.data_rules
            and principal is not None
        ):
            plan = planner.plan_with_scoped_schema(
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
            plan = planner.plan_with_additional_availability(request, predicate)
        self._require_legacy_planning_mode()
        if self.authorization_policy is not None and not executable_only:
            self._validate_plan_authorization(plan, principal, phase="plan")
        self._require_legacy_planning_mode()
        return plan

    async def _alegacy_plan(
        self, request: PlanRequest | str, principal: PrincipalContext | None,
        *, executable_only: bool,
    ) -> ExecutionPlan:
        """Temporary compatibility dispatch; never publish after paper configuration."""
        planner = self._require_legacy_planning_mode()
        predicate = self._combined_availability_predicate(
            principal, self._binding_ready if executable_only else None,
        )
        if predicate is None:
            if executable_only:
                raise RuntimeError("executable planning requires an availability predicate")
            plan = await planner.aplan(request)
        elif (
            self.authorization_policy is not None
            and self.authorization_policy.data_rules
            and principal is not None
        ):
            plan = await planner.aplan_with_scoped_schema(
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
            plan = await planner.aplan_with_additional_availability(
                request,
                predicate,
            )
        self._require_legacy_planning_mode()
        if self.authorization_policy is not None and not executable_only:
            self._validate_plan_authorization(plan, principal, phase="plan")
        self._require_legacy_planning_mode()
        return plan

    def plan(self, request: PlanRequest | PaperPlanRequest | str) -> ExecutionPlan:
        """Schema-aware planning under any active trusted principal context."""

        principal = _current_principal_context()
        configured = self._paper_configuration_for(request)
        if configured is not None:
            plan = self._run_sync_call(
                lambda: configured.aplan(
                    request, principal=principal, executable_only=False,
                ),
            )
            self._validate_plan_authorization(plan, principal, phase="plan")
            return plan
        return self._legacy_plan(
            cast(PlanRequest | str, request), principal, executable_only=False,
        )

    async def aplan(self, request: PlanRequest | PaperPlanRequest | str) -> ExecutionPlan:
        """Async schema-aware planning under any active trusted principal context."""

        principal = _current_principal_context()
        configured = self._paper_configuration_for(request)
        if configured is not None:
            plan = await configured.aplan(request, principal=principal, executable_only=False)
            self._validate_plan_authorization(plan, principal, phase="plan")
            return plan
        return await self._alegacy_plan(
            cast(PlanRequest | str, request), principal, executable_only=False,
        )

    def plan_authorized(
        self,
        request: PlanRequest | PaperPlanRequest | str,
        *,
        principal: PrincipalContext,
    ) -> ExecutionPlan:
        """Plan with one explicitly supplied trusted principal."""

        with _principal_execution_context(principal):
            return self.plan(request)

    async def aplan_authorized(
        self,
        request: PlanRequest | PaperPlanRequest | str,
        *,
        principal: PrincipalContext,
    ) -> ExecutionPlan:
        """Async counterpart to :meth:`plan_authorized`."""

        with _principal_execution_context(principal):
            return await self.aplan(request)

    def _require_legacy_retrieval_mode(self) -> SchemaPlanner:
        planner = self.planner
        if self._paper_planning is not None or not self._legacy_routing or planner is None:
            raise PolicyViolationError(
                "paper routing uses plan/aplan; lexical retrieval is unavailable",
            )
        self._source_availability_predicate()
        return planner

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

            denied_markers = _scoped_denied_field_markers(
                endpoint.output_fields, set(scope.visible_fields),
            )
            public_fields = [
                _scoped_public_output_field(field, denied_markers=denied_markers)
                for field in visible_fields
            ]
            visible_names: set[str] = set()
            for field in public_fields:
                visible_names.add(field.name.casefold())
                if field.semantic_id:
                    visible_names.add(field.semantic_id.casefold())

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
                if (
                    mapped_field in hidden_field_names
                    or _scoped_echoes_denied_label(parameter.name, denied_markers)
                    or (
                        parameter.name.startswith("filter__")
                        and mapped_field not in scope.visible_fields
                    )
                ):
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

            # Public scoped descriptors cannot inherit unreviewed nested
            # input metadata even when the output field list is already safe.
            parameters = [
                _scoped_public_parameter(
                    param,
                    allowed_relationships=scope.allowed_relationships,
                    max_hops=scope.max_hops,
                )
                for param in parameters
            ]
            input_schema = _scoped_public_input_schema(parameters)

            matched_fields = [
                value
                for value in candidate.matched_fields
                if value.casefold() in visible_names
            ]
            score_components = _scoped_public_score_components(
                candidate.score_components,
                visible_names=visible_names,
                source_fields=endpoint.output_fields,
                public_tool_identifiers={tool.key.casefold()},
                public_endpoint_identifiers={
                    f"{tool.key}.{endpoint.name}".casefold()
                },
                public_operation_names={endpoint.name.casefold()},
                public_tool_tokens={
                    token.casefold()
                    for token in _tokens(f"{tool.name} {endpoint.name}")
                },
                public_parameter_names={
                    parameter.name.casefold() for parameter in parameters
                },
            )
            projected_candidates.append(
                candidate.model_copy(
                    deep=True,
                    update={
                        "tool_description": "",
                        "endpoint_description": "",
                        # Candidate source labels originate from the raw
                        # registered tool, not the principal's scoped view.
                        "source_type": None,
                        "license": None,
                        "provider": None,
                        "access_mode": None,
                        "parameters": parameters,
                        "input_schema": input_schema,
                        "output_fields": public_fields,
                        "output_schema": _scoped_public_output_schema(public_fields),
                        "matched_fields": matched_fields,
                        "score_components": score_components,
                    },
                )
            )

        # The planner already ranked only policy-allowed, data-visible
        # endpoint views before applying Top-K. Post-Top-K field projection
        # must not overwrite that full ranked count with the shortlist size.
        # If a concurrent scope change makes a previously visible route
        # disappear here, its pre-Top-K count is no longer trustworthy:
        # refuse a partial/inconsistent result instead of understating
        # completeness or leaking a stale authorization count.
        if (
            len(projected_candidates) != len(retrieval.candidates)
            or retrieval.total_ranked < len(projected_candidates)
        ):
            raise PolicyViolationError(
                "authorized retrieval scope changed during projection"
            )
        ranked = [
            candidate.model_copy(update={"rank": index})
            for index, candidate in enumerate(projected_candidates, start=1)
        ]
        return retrieval.model_copy(
            deep=True,
            update={"candidates": ranked},
        )

    def _project_route_retrieval_data_scope(
        self,
        retrieval: CapabilityRouteRetrieval,
        principal: PrincipalContext | None,
    ) -> CapabilityRouteRetrieval:
        """Remove raw source sidecars after schema-free, scoped route ranking."""
        policy = self.authorization_policy
        if policy is None or not policy.data_rules:
            return retrieval
        if principal is None:
            raise PolicyViolationError(
                "principal context is required when authorization_policy is configured"
            )
        projected = []
        for candidate in retrieval.candidates:
            tool = self.registry.get(candidate.tool)
            endpoint = tool.endpoint(candidate.endpoint)
            scope = policy.data_scope(principal, tool, endpoint)
            if scope.visible_fields is None:
                projected.append(candidate)
                continue
            visible_endpoint = self._data_scope_endpoint_view(
                principal, tool, endpoint,
            )
            if visible_endpoint is None:
                raise PolicyViolationError(
                    "authorized route scope changed during projection"
                )
            visible_names = {
                name.casefold()
                for field in visible_endpoint.output_fields
                for name in (field.name, field.semantic_id)
                if name is not None
            }
            components = _scoped_public_score_components(
                candidate.score_components,
                visible_names=visible_names,
                source_fields=endpoint.output_fields,
                public_tool_identifiers={tool.key.casefold()},
                public_endpoint_identifiers={
                    f"{tool.key}.{endpoint.name}".casefold()
                },
                public_operation_names={endpoint.name.casefold()},
                public_tool_tokens={
                    token.casefold()
                    for token in _tokens(f"{tool.name} {endpoint.name}")
                },
                public_parameter_names={
                    parameter.name.casefold()
                    for parameter in visible_endpoint.parameters
                },
            )
            projected.append(candidate.model_copy(
                deep=True,
                update={
                    "provider": None,
                    "access_mode": None,
                    "matched_fields": [
                        name for name in candidate.matched_fields
                        if name.casefold() in visible_names
                    ],
                    "score_components": components,
                },
            ))
        if len(projected) != len(retrieval.candidates):
            raise PolicyViolationError(
                "authorized route scope changed during projection"
            )
        return retrieval.model_copy(
            deep=True, update={"candidates": projected},
        )

    def retrieve_routes(
        self,
        request: PlanRequest | str,
        *,
        k: int = 5,
    ) -> CapabilityRouteRetrieval:
        """Return lightweight Top-K route references under active authorization."""
        planner = self._require_legacy_retrieval_mode()
        witness = self._retrieval_authority_witness()
        principal = _current_principal_context()
        predicate = self._authorization_predicate(principal)
        if predicate is None:
            result = planner.retrieve_routes(request, k=k)
        elif (
            self.authorization_policy is not None
            and self.authorization_policy.data_rules
            and principal is not None
        ):
            result = planner.retrieve_routes_with_scoped_schema(
                request,
                predicate,
                lambda tool, endpoint: self._data_scope_endpoint_view(
                    principal, tool, endpoint,
                ),
                k=k,
                analysis_registry=self._scoped_analysis_registry(
                    principal, predicate,
                ),
            )
        else:
            result = planner.retrieve_routes_with_additional_availability(
                request, predicate, k=k,
            )
        result = self._project_route_retrieval_data_scope(result, principal)
        self._check_retrieval_authority_witness(witness)
        self._require_legacy_retrieval_mode()
        return result

    async def aretrieve_routes(
        self,
        request: PlanRequest | str,
        *,
        k: int = 5,
    ) -> CapabilityRouteRetrieval:
        """Async counterpart to :meth:`retrieve_routes`."""
        planner = self._require_legacy_retrieval_mode()
        witness = self._retrieval_authority_witness()
        principal = _current_principal_context()
        predicate = self._authorization_predicate(principal)
        if predicate is None:
            result = await planner.aretrieve_routes(request, k=k)
        elif (
            self.authorization_policy is not None
            and self.authorization_policy.data_rules
            and principal is not None
        ):
            result = await planner.aretrieve_routes_with_scoped_schema(
                request,
                predicate,
                lambda tool, endpoint: self._data_scope_endpoint_view(
                    principal, tool, endpoint,
                ),
                k=k,
                analysis_registry=self._scoped_analysis_registry(
                    principal, predicate,
                ),
            )
        else:
            result = await planner.aretrieve_routes_with_additional_availability(
                request, predicate, k=k,
            )
        result = self._project_route_retrieval_data_scope(result, principal)
        self._check_retrieval_authority_witness(witness)
        self._require_legacy_retrieval_mode()
        return result

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
        planner = self._require_legacy_retrieval_mode()

        witness = self._retrieval_authority_witness()
        principal = _current_principal_context()
        predicate = self._authorization_predicate(principal)
        if predicate is None:
            retrieval = planner.retrieve(request, k=k)
        elif (
            self.authorization_policy is not None
            and self.authorization_policy.data_rules
            and principal is not None
        ):
            retrieval = planner.retrieve_with_scoped_schema(
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
            retrieval = planner.retrieve_with_additional_availability(
                request,
                predicate,
                k=k,
            )
        projected = self._project_retrieval_data_scope(retrieval, principal)
        self._check_retrieval_authority_witness(witness)
        self._require_legacy_retrieval_mode()
        return projected

    async def aretrieve(
        self,
        request: PlanRequest | str,
        *,
        k: int = 5,
    ) -> CapabilityRetrieval:
        """Async counterpart to :meth:`retrieve`."""
        planner = self._require_legacy_retrieval_mode()

        witness = self._retrieval_authority_witness()
        principal = _current_principal_context()
        predicate = self._authorization_predicate(principal)
        if predicate is None:
            retrieval = await planner.aretrieve(request, k=k)
        elif (
            self.authorization_policy is not None
            and self.authorization_policy.data_rules
            and principal is not None
        ):
            retrieval = await planner.aretrieve_with_scoped_schema(
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
            retrieval = await planner.aretrieve_with_additional_availability(
                request,
                predicate,
                k=k,
            )
        projected = self._project_retrieval_data_scope(retrieval, principal)
        self._check_retrieval_authority_witness(witness)
        self._require_legacy_retrieval_mode()
        return projected

    def retrieve_authorized(
        self,
        request: PlanRequest | str,
        *,
        principal: PrincipalContext,
        k: int = 5,
    ) -> CapabilityRetrieval:
        """Retrieve capabilities for one explicitly supplied trusted principal."""

        with _principal_execution_context(
            _validated_explicit_retrieval_principal(principal)
        ):
            return self.retrieve(request, k=k)

    async def aretrieve_authorized(
        self,
        request: PlanRequest | str,
        *,
        principal: PrincipalContext,
        k: int = 5,
    ) -> CapabilityRetrieval:
        """Async counterpart to :meth:`retrieve_authorized`."""

        with _principal_execution_context(
            _validated_explicit_retrieval_principal(principal)
        ):
            return await self.aretrieve(request, k=k)

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

    def plan_executable(self, request: PlanRequest | PaperPlanRequest | str) -> ExecutionPlan:
        """Plan only across authorized routes with a ready local binding."""

        principal = _current_principal_context()
        configured = self._paper_configuration_for(request)
        if configured is not None:
            plan = self._run_sync_call(
                lambda: configured.aplan(
                    request, principal=principal, executable_only=True,
                ),
            )
            self._validate_plan_authorization(plan, principal, phase="plan")
            return plan
        return self._legacy_plan(
            cast(PlanRequest | str, request), principal, executable_only=True,
        )

    async def aplan_executable(
        self, request: PlanRequest | PaperPlanRequest | str,
    ) -> ExecutionPlan:
        """Async counterpart to :meth:`plan_executable`."""

        principal = _current_principal_context()
        configured = self._paper_configuration_for(request)
        if configured is not None:
            plan = await configured.aplan(request, principal=principal, executable_only=True)
            self._validate_plan_authorization(plan, principal, phase="plan")
            return plan
        return await self._alegacy_plan(
            cast(PlanRequest | str, request), principal, executable_only=True,
        )

    def plan_executable_authorized(
        self,
        request: PlanRequest | PaperPlanRequest | str,
        *,
        principal: PrincipalContext,
    ) -> ExecutionPlan:
        """Plan executable routes for one explicitly supplied principal."""

        with _principal_execution_context(principal):
            return self.plan_executable(request)

    async def aplan_executable_authorized(
        self,
        request: PlanRequest | PaperPlanRequest | str,
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
        planner = self._require_legacy_retrieval_mode()

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
            retrieval = planner.retrieve_with_scoped_schema(
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
            retrieval = planner.retrieve_with_additional_availability(
                request,
                predicate,
                k=k,
                executable_only=True,
            )
        projected = self._project_retrieval_data_scope(retrieval, principal)
        self._require_legacy_retrieval_mode()
        return projected

    async def aretrieve_executable(
        self,
        request: PlanRequest | str,
        *,
        k: int = 5,
    ) -> CapabilityRetrieval:
        """Async counterpart to :meth:`retrieve_executable`."""
        planner = self._require_legacy_retrieval_mode()

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
            retrieval = await planner.aretrieve_with_scoped_schema(
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
            retrieval = await planner.aretrieve_with_additional_availability(
                request,
                predicate,
                k=k,
                executable_only=True,
            )
        projected = self._project_retrieval_data_scope(retrieval, principal)
        self._require_legacy_retrieval_mode()
        return projected

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


class LegacyConfiguredSchemaRouter(ConfiguredSchemaRouter):
    """Research-only configured lexical retrieval facade."""

    router: LegacySchemaRouter

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
