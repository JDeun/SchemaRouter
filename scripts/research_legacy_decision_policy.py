"""Historical bounded decision-policy planner; never imported by the installed package.

The original optional policy and its callbacks are preserved for comparison tests.
The base planner and canonical registry/validation infrastructure are reused.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

from schemarouter.decisions import (
    DecisionBackend,
    DecisionOption,
    DecisionRequest,
    choose_async,
    choose_sync,
)
from schemarouter.errors import PlanningError
from schemarouter.models import (
    EndpointSpec,
    EvidenceRequirements,
    FieldSelectionExplanation,
    PlanExplanation,
    PlanRequest,
    QueryIntent,
    ToolCall,
    ToolSpec,
)
from schemarouter.planner import (
    SchemaPlanner,
    _Candidate,
    _scoring_tool_for_visible_endpoint,
    _visible_endpoint,
)
from schemarouter.planning_context import RegistrySnapshot

DecisionFallback = Literal["deterministic", "error"]
CandidateAbstention = Literal["inherit", "deterministic", "no_route", "error"]


class DecisionPolicy(BaseModel):
    """Opt-in controls for experimental bounded-decision assistance."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    enabled: bool = False
    tool_selection: bool = False
    endpoint_selection: bool = False
    field_selection: bool = False
    evidence_sufficiency: bool = False
    recall_on_empty: bool = False
    candidate_abstention: CandidateAbstention = "inherit"
    fallback: DecisionFallback = "deterministic"

    @property
    def candidate_selection_enabled(self) -> bool:
        return self.enabled and (self.tool_selection or self.endpoint_selection)

    @property
    def candidate_recall_on_empty_enabled(self) -> bool:
        return self.candidate_selection_enabled and self.recall_on_empty

    @property
    def candidate_abstention_mode(self) -> DecisionFallback | Literal["no_route"]:
        if self.candidate_abstention == "inherit":
            return self.fallback
        return self.candidate_abstention

    @property
    def field_selection_enabled(self) -> bool:
        return self.enabled and self.field_selection

    @property
    def evidence_sufficiency_enabled(self) -> bool:
        return self.enabled and self.evidence_sufficiency

    @property
    def reserved_surfaces_enabled(self) -> bool:
        """Backward-compatible indicator for not-yet-implemented decision surfaces."""
        return False


class LegacyDecisionPlanner(SchemaPlanner):
    """Explicit research comparison arm for the retired DecisionPolicy surfaces."""

    def __init__(
        self,
        *args: Any,
        decision_backend: DecisionBackend | None = None,
        decision_policy: DecisionPolicy | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(*args, **kwargs)
        self.decision_backend = decision_backend
        self.decision_policy = decision_policy or DecisionPolicy()
        if self.decision_policy.enabled and self.decision_backend is None:
            raise PlanningError("decision policy is enabled but no decision backend is configured")

    def _candidates(
        self,
        request: PlanRequest,
        intent: QueryIntent,
        *,
        additional_availability_predicate: Callable[
            [ToolSpec, EndpointSpec],
            bool,
        ]
        | None = None,
        scoring_endpoint_transform: Callable[
            [ToolSpec, EndpointSpec],
            EndpointSpec | None,
        ]
        | None = None,
        catalog_snapshot: RegistrySnapshot | None = None,
    ) -> list[_Candidate]:
        snapshot = catalog_snapshot or self._catalog_snapshot(
            scoring_endpoint_transform=scoring_endpoint_transform,
        )

        def is_available(tool: ToolSpec, endpoint: EndpointSpec) -> bool:
            if (
                self.availability_predicate is not None
                and not self.availability_predicate(tool, endpoint)
            ):
                return False
            if (
                additional_availability_predicate is not None
                and not additional_availability_predicate(tool, endpoint)
            ):
                return False
            return True

        if (
            snapshot.index is not None
            and not self.structural_retrieval
            and scoring_endpoint_transform is None
        ):
            endpoint_pairs = snapshot.index.endpoint_pairs(request, intent)
        else:
            endpoint_pairs = snapshot.all_endpoint_pairs()

        if (
            self.availability_predicate is not None
            or additional_availability_predicate is not None
        ):
            endpoint_pairs = tuple(
                (tool, endpoint)
                for tool, endpoint in endpoint_pairs
                if is_available(tool, endpoint)
            )

        scoring_context = self._scoring_context(request.query, intent)
        candidates: list[_Candidate] = []
        for tool, endpoint in endpoint_pairs:
            visible_endpoint = (
                endpoint
                if scoring_endpoint_transform is None
                else scoring_endpoint_transform(tool, endpoint)
            )
            if visible_endpoint is None:
                continue
            scored = self._score_endpoint(
                _scoring_tool_for_visible_endpoint(
                    tool, endpoint, visible_endpoint,
                ),
                visible_endpoint,
                request.query,
                intent,
                _context=scoring_context,
            )
            if scored.score > 0:
                candidates.append(
                    replace(
                        scored,
                        tool=tool,
                        endpoint=endpoint,
                        visible_endpoint=(
                            visible_endpoint
                            if scoring_endpoint_transform is not None
                            else None
                        ),
                    )
                )
        if (
            not candidates
            and self.decision_policy.candidate_recall_on_empty_enabled
            and self.candidate_recall_backend is None
        ):
            candidates = []
            for tool in snapshot.tools:
                for endpoint in tool.endpoints:
                    if not is_available(tool, endpoint):
                        continue
                    visible_endpoint = (
                        endpoint
                        if scoring_endpoint_transform is None
                        else scoring_endpoint_transform(tool, endpoint)
                    )
                    if visible_endpoint is None:
                        continue
                    candidates.append(
                        _Candidate(
                            tool,
                            endpoint,
                            0.0,
                            (),
                            visible_endpoint=(
                                visible_endpoint
                                if scoring_endpoint_transform is not None
                                else None
                            ),
                        )
                    )
        self._sort_candidates(candidates, catalog_snapshot=snapshot)
        return candidates

    def _decision_request(
        self,
        request: PlanRequest,
        candidates: list[_Candidate],
    ) -> DecisionRequest:
        return DecisionRequest(
            query=request.query,
            options=[
                DecisionOption(
                    id=f"candidate:{index}",
                    label=f"{candidate.tool.key}.{candidate.endpoint.name}",
                    description=_visible_endpoint(candidate).description,
                    metadata={"schema_score": candidate.score},
                )
                for index, candidate in enumerate(candidates)
            ],
            max_selections=min(request.max_calls, len(candidates)),
        )

    def _select_candidates_sync(
        self,
        request: PlanRequest,
        candidates: list[_Candidate],
    ) -> tuple[list[_Candidate], list[str]]:
        if not candidates or not self.decision_policy.candidate_selection_enabled:
            return candidates, []
        assert self.decision_backend is not None
        recall_expanded = (
            all(candidate.score <= 0 for candidate in candidates)
            and all(
                candidate.selection_source != "semantic_recall"
                for candidate in candidates
            )
        )
        try:
            result = choose_sync(
                self.decision_backend,
                self._decision_request(request, candidates),
            )
        except Exception as exc:
            if self.decision_policy.fallback == "deterministic":
                if recall_expanded:
                    return [], [
                        "decision backend fallback after empty lexical recall: "
                        f"{type(exc).__name__}; no deterministic candidate available"
                    ]
                return candidates, [f"decision backend fallback: {type(exc).__name__}"]
            raise
        if result.abstained or not result.selections:
            abstention = self.decision_policy.candidate_abstention_mode
            if abstention == "no_route":
                message = (
                    "decision backend abstained after empty lexical recall; "
                    "suppressed candidate route"
                    if recall_expanded
                    else "decision backend abstained; suppressed candidate route"
                )
                return [], [message]
            if abstention == "error":
                raise PlanningError("decision backend abstained")
            if recall_expanded:
                return [], [
                    "decision backend abstained after empty lexical recall; "
                    "no deterministic candidate available"
                ]
            return candidates, ["decision backend abstained; used deterministic ranking"]
        selection_source = "decision_recall" if recall_expanded else "decision_backend"
        selected_indexes = [
            int(item.option_id.split(":", 1)[1])
            for item in result.selections
        ]
        selected = [
            replace(
                candidates[index],
                selection_source=selection_source,
            )
            for index in selected_indexes
        ]
        warnings = (
            ["decision backend expanded an empty lexical candidate set to the registered catalog"]
            if recall_expanded
            else []
        )
        if request.max_calls > 1 and not recall_expanded:
            selected_index_set = set(selected_indexes)
            remaining = [
                candidate
                for index, candidate in enumerate(candidates)
                if index not in selected_index_set
            ]
            warnings.append(
                "decision backend prioritized candidates; retained deterministic "
                "candidate recall for multi-call field coverage"
            )
            return [*selected, *remaining], warnings
        return selected, warnings

    async def _select_candidates_async(
        self,
        request: PlanRequest,
        candidates: list[_Candidate],
    ) -> tuple[list[_Candidate], list[str]]:
        if not candidates or not self.decision_policy.candidate_selection_enabled:
            return candidates, []
        assert self.decision_backend is not None
        recall_expanded = (
            all(candidate.score <= 0 for candidate in candidates)
            and all(
                candidate.selection_source != "semantic_recall"
                for candidate in candidates
            )
        )
        try:
            result = await choose_async(
                self.decision_backend,
                self._decision_request(request, candidates),
            )
        except Exception as exc:
            if self.decision_policy.fallback == "deterministic":
                if recall_expanded:
                    return [], [
                        "decision backend fallback after empty lexical recall: "
                        f"{type(exc).__name__}; no deterministic candidate available"
                    ]
                return candidates, [f"decision backend fallback: {type(exc).__name__}"]
            raise
        if result.abstained or not result.selections:
            abstention = self.decision_policy.candidate_abstention_mode
            if abstention == "no_route":
                message = (
                    "decision backend abstained after empty lexical recall; "
                    "suppressed candidate route"
                    if recall_expanded
                    else "decision backend abstained; suppressed candidate route"
                )
                return [], [message]
            if abstention == "error":
                raise PlanningError("decision backend abstained")
            if recall_expanded:
                return [], [
                    "decision backend abstained after empty lexical recall; "
                    "no deterministic candidate available"
                ]
            return candidates, ["decision backend abstained; used deterministic ranking"]
        selection_source = "decision_recall" if recall_expanded else "decision_backend"
        selected_indexes = [
            int(item.option_id.split(":", 1)[1])
            for item in result.selections
        ]
        selected = [
            replace(
                candidates[index],
                selection_source=selection_source,
            )
            for index in selected_indexes
        ]
        warnings = (
            ["decision backend expanded an empty lexical candidate set to the registered catalog"]
            if recall_expanded
            else []
        )
        if request.max_calls > 1 and not recall_expanded:
            selected_index_set = set(selected_indexes)
            remaining = [
                candidate
                for index, candidate in enumerate(candidates)
                if index not in selected_index_set
            ]
            warnings.append(
                "decision backend prioritized candidates; retained deterministic "
                "candidate recall for multi-call field coverage"
            )
            return [*selected, *remaining], warnings
        return selected, warnings

    @staticmethod
    def _field_decision_request(
        request: PlanRequest,
        candidate: _Candidate,
        deterministic_fields: list[str],
    ) -> DecisionRequest | None:
        endpoint = _visible_endpoint(candidate)
        selectable = [field for field in endpoint.output_fields if not field.identifier]
        if not selectable:
            return None

        deterministic_answer_fields = [
            name
            for name in deterministic_fields
            if any(field.name == name and not field.identifier for field in endpoint.output_fields)
        ]
        max_selections = len(deterministic_answer_fields) or len(selectable)

        options: list[DecisionOption] = []
        for index, field in enumerate(selectable):
            detail_parts = [field.description.strip()]
            if field.aliases:
                detail_parts.append("aliases: " + ", ".join(field.aliases))
            if field.unit:
                detail_parts.append(f"unit: {field.unit}")
            if field.qualifiers:
                detail_parts.append(
                    "qualifiers: "
                    + ", ".join(
                        f"{key}={value}"
                        for key, value in sorted(field.qualifiers.items())
                    )
                )
            description = "; ".join(part for part in detail_parts if part)
            options.append(
                DecisionOption(
                    id=f"field:{index}",
                    label=field.name,
                    description=description,
                    metadata={
                        "tool": candidate.tool.key,
                        "endpoint": endpoint.name,
                    },
                )
            )

        return DecisionRequest(
            query=request.query,
            options=options,
            max_selections=min(max_selections, len(options)),
            context={
                "surface": "field_selection",
                "tool": candidate.tool.key,
                "endpoint": endpoint.name,
                "deterministic_fields": list(deterministic_fields),
            },
        )

    @staticmethod
    def _apply_field_decision(
        candidate: _Candidate,
        result_ids: list[str],
    ) -> list[str]:
        endpoint = _visible_endpoint(candidate)
        identifiers = [field.name for field in endpoint.output_fields if field.identifier]
        selectable = [field for field in endpoint.output_fields if not field.identifier]
        selected = [
            selectable[int(option_id.split(":", 1)[1])].name
            for option_id in result_ids
        ]
        return list(dict.fromkeys([*identifiers, *selected]))

    def _select_fields_sync(
        self,
        request: PlanRequest,
        candidate: _Candidate,
        deterministic_fields: list[str],
    ) -> tuple[list[str], list[str]]:
        if not self.decision_policy.field_selection_enabled:
            return deterministic_fields, []

        decision_request = self._field_decision_request(
            request,
            candidate,
            deterministic_fields,
        )
        if decision_request is None:
            return deterministic_fields, []

        assert self.decision_backend is not None
        prefix = f"{candidate.tool.key}.{candidate.endpoint.name}"
        try:
            result = choose_sync(self.decision_backend, decision_request)
        except Exception as exc:
            if self.decision_policy.fallback == "deterministic":
                return deterministic_fields, [
                    f"{prefix}: field decision fallback: {type(exc).__name__}"
                ]
            raise

        if result.abstained or not result.selections:
            if self.decision_policy.fallback == "deterministic":
                return deterministic_fields, [
                    f"{prefix}: field decision backend abstained; "
                    "used deterministic projection"
                ]
            raise PlanningError(f"{prefix}: field decision backend abstained")

        return (
            self._apply_field_decision(
                candidate,
                [item.option_id for item in result.selections],
            ),
            [],
        )

    async def _select_fields_async(
        self,
        request: PlanRequest,
        candidate: _Candidate,
        deterministic_fields: list[str],
    ) -> tuple[list[str], list[str]]:
        if not self.decision_policy.field_selection_enabled:
            return deterministic_fields, []

        decision_request = self._field_decision_request(
            request,
            candidate,
            deterministic_fields,
        )
        if decision_request is None:
            return deterministic_fields, []

        assert self.decision_backend is not None
        prefix = f"{candidate.tool.key}.{candidate.endpoint.name}"
        try:
            result = await choose_async(self.decision_backend, decision_request)
        except Exception as exc:
            if self.decision_policy.fallback == "deterministic":
                return deterministic_fields, [
                    f"{prefix}: field decision fallback: {type(exc).__name__}"
                ]
            raise

        if result.abstained or not result.selections:
            if self.decision_policy.fallback == "deterministic":
                return deterministic_fields, [
                    f"{prefix}: field decision backend abstained; "
                    "used deterministic projection"
                ]
            raise PlanningError(f"{prefix}: field decision backend abstained")

        return (
            self._apply_field_decision(
                candidate,
                [item.option_id for item in result.selections],
            ),
            [],
        )

    @staticmethod
    def _evidence_decision_request(
        request: PlanRequest,
        context: dict[str, object],
    ) -> DecisionRequest:
        return DecisionRequest(
            query=request.query,
            options=[
                DecisionOption(
                    id="evidence:sufficient",
                    label="sufficient",
                    description=(
                        "The declared local schema evidence is sufficient for this request."
                    ),
                ),
                DecisionOption(
                    id="evidence:insufficient",
                    label="insufficient",
                    description=(
                        "Treat the declared local schema evidence as insufficient for this request."
                    ),
                ),
            ],
            max_selections=1,
            context=context,
        )

    def _assess_evidence_sync(
        self,
        request: PlanRequest,
        candidate: _Candidate,
        selected_fields: list[str],
        requested: EvidenceRequirements,
        field_requested: dict[str, EvidenceRequirements],
    ) -> tuple[bool, list[str]]:
        if not (
            self._evidence_request_active(requested)
            or self._field_evidence_request_active(field_requested)
        ):
            return True, []

        prefix = f"{candidate.tool.key}.{candidate.endpoint.name}"
        locally_sufficient, context, missing, _ = (
            self._combined_local_evidence_status(
                candidate,
                selected_fields,
                requested,
                field_requested,
            )
        )
        if not locally_sufficient:
            message = (
                f"{prefix}: local evidence insufficient: " + ", ".join(missing)
            )
            if (
                self.decision_policy.evidence_sufficiency_enabled
                and self.decision_policy.fallback == "error"
            ):
                raise PlanningError(message)
            return False, [message]

        # Evidence requirements are deterministic local constraints. A decision
        # backend may veto locally sufficient evidence, but it can never upgrade
        # locally missing global or field-specific contracts.
        if not self.decision_policy.evidence_sufficiency_enabled:
            return True, []

        assert self.decision_backend is not None
        try:
            result = choose_sync(
                self.decision_backend,
                self._evidence_decision_request(request, context),
            )
        except Exception as exc:
            if self.decision_policy.fallback == "deterministic":
                return True, [
                    f"{prefix}: evidence decision fallback: {type(exc).__name__}"
                ]
            raise

        if result.abstained or not result.selections:
            if self.decision_policy.fallback == "deterministic":
                return True, [
                    f"{prefix}: evidence decision backend abstained; "
                    "used local evidence assessment"
                ]
            raise PlanningError(f"{prefix}: evidence decision backend abstained")

        option_id = result.selections[0].option_id
        if option_id == "evidence:sufficient":
            return True, []
        if option_id == "evidence:insufficient":
            return False, [f"{prefix}: evidence decision marked evidence insufficient"]
        raise PlanningError(f"{prefix}: unsupported evidence decision {option_id!r}")

    async def _assess_evidence_async(
        self,
        request: PlanRequest,
        candidate: _Candidate,
        selected_fields: list[str],
        requested: EvidenceRequirements,
        field_requested: dict[str, EvidenceRequirements],
    ) -> tuple[bool, list[str]]:
        if not (
            self._evidence_request_active(requested)
            or self._field_evidence_request_active(field_requested)
        ):
            return True, []

        prefix = f"{candidate.tool.key}.{candidate.endpoint.name}"
        locally_sufficient, context, missing, _ = (
            self._combined_local_evidence_status(
                candidate,
                selected_fields,
                requested,
                field_requested,
            )
        )
        if not locally_sufficient:
            message = (
                f"{prefix}: local evidence insufficient: " + ", ".join(missing)
            )
            if (
                self.decision_policy.evidence_sufficiency_enabled
                and self.decision_policy.fallback == "error"
            ):
                raise PlanningError(message)
            return False, [message]

        if not self.decision_policy.evidence_sufficiency_enabled:
            return True, []

        assert self.decision_backend is not None
        try:
            result = await choose_async(
                self.decision_backend,
                self._evidence_decision_request(request, context),
            )
        except Exception as exc:
            if self.decision_policy.fallback == "deterministic":
                return True, [
                    f"{prefix}: evidence decision fallback: {type(exc).__name__}"
                ]
            raise

        if result.abstained or not result.selections:
            if self.decision_policy.fallback == "deterministic":
                return True, [
                    f"{prefix}: evidence decision backend abstained; "
                    "used local evidence assessment"
                ]
            raise PlanningError(f"{prefix}: evidence decision backend abstained")

        option_id = result.selections[0].option_id
        if option_id == "evidence:sufficient":
            return True, []
        if option_id == "evidence:insufficient":
            return False, [f"{prefix}: evidence decision marked evidence insufficient"]
        raise PlanningError(f"{prefix}: unsupported evidence decision {option_id!r}")

    def _compile_candidate_sync(
        self,
        request: PlanRequest,
        intent: QueryIntent,
        candidate: _Candidate,
        warnings: list[str],
        *,
        warn_ignored_arguments: bool = True,
    ) -> ToolCall | None:
        authoritative_endpoint = candidate.endpoint
        endpoint = _visible_endpoint(candidate)
        arguments, _, dropped, ambiguous_aliases = self._bind_arguments(
            endpoint,
            intent.arguments,
        )
        if ambiguous_aliases and warn_ignored_arguments:
            warnings.append(
                f"{candidate.tool.key}.{endpoint.name}: ambiguous parameter aliases: "
                + ", ".join(ambiguous_aliases)
            )
        unambiguous_dropped = [
            name
            for name in dropped
            if name not in set(ambiguous_aliases)
        ]
        if unambiguous_dropped and warn_ignored_arguments:
            warnings.append(
                f"{candidate.tool.key}.{endpoint.name}: ignored undeclared arguments: "
                + ", ".join(unambiguous_dropped)
            )
        missing = [
            parameter.name
            for parameter in endpoint.parameters
            if parameter.required and parameter.name not in arguments
        ]
        deterministic_fields = self._project_fields(
            endpoint,
            intent,
            candidate.matched_fields,
        )
        fields, field_warnings = self._select_fields_sync(
            request,
            candidate,
            deterministic_fields,
        )
        warnings.extend(field_warnings)
        evidence = self._evidence(
            candidate.tool,
            endpoint,
            fields,
        )
        matched_field_evidence = self._matched_field_evidence(
            candidate,
            fields,
            intent.field_evidence,
        )
        call_field_evidence = {
            field_name: requirement
            for field_name, (_, requirement) in matched_field_evidence.items()
        }
        evidence_ok, evidence_warnings = self._assess_evidence_sync(
            request,
            candidate,
            fields,
            intent.evidence,
            intent.field_evidence,
        )
        warnings.extend(evidence_warnings)
        if not evidence_ok:
            return None

        return ToolCall(
            tool=candidate.tool.key,
            endpoint=endpoint.name,
            arguments=arguments,
            fields=fields,
            evidence=evidence,
            required_evidence=intent.evidence,
            field_evidence=call_field_evidence,
            schema_fingerprint=authoritative_endpoint.fingerprint,
            tool_fingerprint=candidate.tool.fingerprint,
            missing_required_arguments=missing,
            score=candidate.score,
            explanation=self._build_explanation(
                candidate,
                fields,
                dropped,
                field_decision_used=(
                    self.decision_policy.field_selection_enabled
                    and not field_warnings
                ),
            ),
        )

    async def _compile_candidate_async(
        self,
        request: PlanRequest,
        intent: QueryIntent,
        candidate: _Candidate,
        warnings: list[str],
        *,
        warn_ignored_arguments: bool = True,
    ) -> ToolCall | None:
        authoritative_endpoint = candidate.endpoint
        endpoint = _visible_endpoint(candidate)
        arguments, _, dropped, ambiguous_aliases = self._bind_arguments(
            endpoint,
            intent.arguments,
        )
        if ambiguous_aliases and warn_ignored_arguments:
            warnings.append(
                f"{candidate.tool.key}.{endpoint.name}: ambiguous parameter aliases: "
                + ", ".join(ambiguous_aliases)
            )
        unambiguous_dropped = [
            name
            for name in dropped
            if name not in set(ambiguous_aliases)
        ]
        if unambiguous_dropped and warn_ignored_arguments:
            warnings.append(
                f"{candidate.tool.key}.{endpoint.name}: ignored undeclared arguments: "
                + ", ".join(unambiguous_dropped)
            )
        missing = [
            parameter.name
            for parameter in endpoint.parameters
            if parameter.required and parameter.name not in arguments
        ]
        deterministic_fields = self._project_fields(
            endpoint,
            intent,
            candidate.matched_fields,
        )
        fields, field_warnings = await self._select_fields_async(
            request,
            candidate,
            deterministic_fields,
        )
        warnings.extend(field_warnings)
        evidence = self._evidence(
            candidate.tool,
            endpoint,
            fields,
        )
        matched_field_evidence = self._matched_field_evidence(
            candidate,
            fields,
            intent.field_evidence,
        )
        call_field_evidence = {
            field_name: requirement
            for field_name, (_, requirement) in matched_field_evidence.items()
        }
        evidence_ok, evidence_warnings = await self._assess_evidence_async(
            request,
            candidate,
            fields,
            intent.evidence,
            intent.field_evidence,
        )
        warnings.extend(evidence_warnings)
        if not evidence_ok:
            return None

        return ToolCall(
            tool=candidate.tool.key,
            endpoint=endpoint.name,
            arguments=arguments,
            fields=fields,
            evidence=evidence,
            required_evidence=intent.evidence,
            field_evidence=call_field_evidence,
            schema_fingerprint=authoritative_endpoint.fingerprint,
            tool_fingerprint=candidate.tool.fingerprint,
            missing_required_arguments=missing,
            score=candidate.score,
            explanation=self._build_explanation(
                candidate,
                fields,
                dropped,
                field_decision_used=(
                    self.decision_policy.field_selection_enabled
                    and not field_warnings
                ),
            ),
        )

    @staticmethod
    def _build_explanation(
        candidate: _Candidate,
        fields: list[str],
        ignored_arguments: list[str],
        *,
        field_decision_used: bool,
    ) -> PlanExplanation:
        reasons = dict(candidate.field_reasons)
        field_map = {field.name: field for field in _visible_endpoint(candidate).output_fields}
        selections: list[FieldSelectionExplanation] = []
        for name in fields:
            field = field_map.get(name)
            if field is None:
                continue
            if field.identifier:
                reason = "identifier"
            elif field_decision_used:
                reason = "decision_backend"
            else:
                reason = reasons.get(name, "recall_fallback")
            selections.append(
                FieldSelectionExplanation(
                    field=name,
                    reason=reason,
                )
            )

        return PlanExplanation(
            candidate_selection=candidate.selection_source,
            score_components=list(candidate.score_components),
            field_selection=selections,
            ignored_arguments=list(ignored_arguments),
        )
