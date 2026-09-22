from __future__ import annotations

import inspect
import re
from collections.abc import Awaitable
from dataclasses import dataclass
from typing import Protocol

from .decision_policy import DecisionPolicy
from .decisions import DecisionBackend, DecisionOption, DecisionRequest, choose_async, choose_sync
from .errors import PlanningError
from .models import (
    EndpointSpec,
    EvidenceRequirements,
    ExecutionPlan,
    FieldSpec,
    PlanRequest,
    QueryIntent,
    ToolCall,
    ToolSpec,
)
from .registry import ToolRegistry

_TOKEN_RE = re.compile(r"[A-Za-z0-9_]+|[가-힣]+")


def _normalize(text: str) -> str:
    return "".join(ch.lower() for ch in text if ch.isalnum())


def _tokens(text: str) -> set[str]:
    return {token.lower() for token in _TOKEN_RE.findall(text)}


class QueryAnalyzer(Protocol):
    def analyze(
        self,
        request: PlanRequest,
        registry: ToolRegistry,
    ) -> QueryIntent | Awaitable[QueryIntent]: ...


class KeywordAnalyzer:
    """Offline default analyzer. It never invents values or tool names."""

    def analyze(self, request: PlanRequest, registry: ToolRegistry) -> QueryIntent:
        concepts = list(dict.fromkeys([*request.concepts, *_tokens(request.query)]))
        return QueryIntent(
            concepts=concepts,
            preferred_tools=request.preferred_tools,
            arguments=request.arguments,
            evidence=request.evidence,
        )


@dataclass(frozen=True)
class _Candidate:
    tool: ToolSpec
    endpoint: EndpointSpec
    score: float
    matched_fields: tuple[str, ...]


class SchemaPlanner:
    """Schema-aware planner with sync and async query-analysis paths."""

    def __init__(
        self,
        registry: ToolRegistry,
        analyzer: QueryAnalyzer | None = None,
        *,
        decision_backend: DecisionBackend | None = None,
        decision_policy: DecisionPolicy | None = None,
    ) -> None:
        self.registry = registry
        self.analyzer = analyzer or KeywordAnalyzer()
        self.decision_backend = decision_backend
        self.decision_policy = decision_policy or DecisionPolicy()
        if self.decision_policy.enabled and self.decision_backend is None:
            raise PlanningError("decision policy is enabled but no decision backend is configured")

    def plan(self, request: PlanRequest | str) -> ExecutionPlan:
        request = self._prepare_request(request)
        intent = self.analyzer.analyze(request, self.registry)
        if inspect.isawaitable(intent):
            if inspect.iscoroutine(intent):
                intent.close()
            raise PlanningError(
                "the configured analyzer is asynchronous; use await planner.aplan(...)"
            )
        return self._build_plan(request, intent, async_decision=False)

    async def aplan(self, request: PlanRequest | str) -> ExecutionPlan:
        request = self._prepare_request(request)
        intent = self.analyzer.analyze(request, self.registry)
        if inspect.isawaitable(intent):
            intent = await intent
        return await self._abuild_plan(request, intent)

    def _prepare_request(self, request: PlanRequest | str) -> PlanRequest:
        if isinstance(request, str):
            request = PlanRequest(query=request)
        if not self.registry.tools():
            raise PlanningError("cannot plan with an empty registry")
        return request

    def _candidates(self, request: PlanRequest, intent: QueryIntent) -> list[_Candidate]:
        candidates = [
            self._score_endpoint(tool, endpoint, request.query, intent)
            for tool in self.registry.tools()
            for endpoint in tool.endpoints
        ]
        candidates = [candidate for candidate in candidates if candidate.score > 0]
        candidates.sort(
            key=lambda candidate: (
                -candidate.score,
                candidate.tool.key,
                candidate.endpoint.name,
            )
        )
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
                    description=candidate.endpoint.description,
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
        try:
            result = choose_sync(
                self.decision_backend,
                self._decision_request(request, candidates),
            )
        except Exception as exc:
            if self.decision_policy.fallback == "deterministic":
                return candidates, [f"decision backend fallback: {type(exc).__name__}"]
            raise
        if result.abstained or not result.selections:
            if self.decision_policy.fallback == "deterministic":
                return candidates, ["decision backend abstained; used deterministic ranking"]
            raise PlanningError("decision backend abstained")
        return [candidates[int(item.option_id.split(":", 1)[1])] for item in result.selections], []

    async def _select_candidates_async(
        self,
        request: PlanRequest,
        candidates: list[_Candidate],
    ) -> tuple[list[_Candidate], list[str]]:
        if not candidates or not self.decision_policy.candidate_selection_enabled:
            return candidates, []
        assert self.decision_backend is not None
        try:
            result = await choose_async(
                self.decision_backend,
                self._decision_request(request, candidates),
            )
        except Exception as exc:
            if self.decision_policy.fallback == "deterministic":
                return candidates, [f"decision backend fallback: {type(exc).__name__}"]
            raise
        if result.abstained or not result.selections:
            if self.decision_policy.fallback == "deterministic":
                return candidates, ["decision backend abstained; used deterministic ranking"]
            raise PlanningError("decision backend abstained")
        return [candidates[int(item.option_id.split(":", 1)[1])] for item in result.selections], []


    @staticmethod
    def _field_decision_request(
        request: PlanRequest,
        candidate: _Candidate,
        deterministic_fields: list[str],
    ) -> DecisionRequest | None:
        endpoint = candidate.endpoint
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
        endpoint = candidate.endpoint
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
    def _evidence_request_active(requested: EvidenceRequirements) -> bool:
        return bool(
            requested.provenance
            or requested.license
            or requested.units
            or requested.source_type
        )

    @staticmethod
    def _local_evidence_status(
        candidate: _Candidate,
        selected_fields: list[str],
        requested: EvidenceRequirements,
    ) -> tuple[bool, dict[str, object], list[str]]:
        endpoint = candidate.endpoint
        field_map = {field.name: field for field in endpoint.output_fields}
        selected = [
            field_map[name]
            for name in selected_fields
            if name in field_map
        ]
        answer_fields = [field for field in selected if not field.identifier]

        provenance_available = bool(
            candidate.tool.source_type
            or any(field.source_type for field in selected)
        )
        license_available = bool(candidate.tool.license) or bool(selected) and all(
            field.license for field in selected
        )
        units_available = bool(answer_fields) and all(
            field.unit for field in answer_fields
        )
        requested_source_type = requested.source_type
        source_type_available = (
            requested_source_type is None
            or candidate.tool.source_type == requested_source_type
            or (
                bool(answer_fields)
                and all(
                    field.source_type == requested_source_type
                    for field in answer_fields
                )
            )
        )

        missing: list[str] = []
        if requested.provenance and not provenance_available:
            missing.append("provenance")
        if requested.license and not license_available:
            missing.append("license")
        if requested.units and not units_available:
            missing.append("units")
        if requested_source_type is not None and not source_type_available:
            missing.append(f"source_type={requested_source_type}")

        context: dict[str, object] = {
            "surface": "evidence_sufficiency",
            "tool": candidate.tool.key,
            "endpoint": endpoint.name,
            "selected_fields": list(selected_fields),
            "requested": requested.model_dump(mode="json"),
            "available": {
                "provenance": provenance_available,
                "license": license_available,
                "units": units_available,
                "source_type": source_type_available,
            },
        }
        return not missing, context, missing

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
    ) -> tuple[bool, list[str]]:
        if not self.decision_policy.evidence_sufficiency_enabled:
            return True, []
        if not self._evidence_request_active(requested):
            return True, []

        prefix = f"{candidate.tool.key}.{candidate.endpoint.name}"
        locally_sufficient, context, missing = self._local_evidence_status(
            candidate,
            selected_fields,
            requested,
        )
        if not locally_sufficient:
            message = (
                f"{prefix}: local evidence insufficient: " + ", ".join(missing)
            )
            if self.decision_policy.fallback == "error":
                raise PlanningError(message)
            return False, [message]

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
    ) -> tuple[bool, list[str]]:
        if not self.decision_policy.evidence_sufficiency_enabled:
            return True, []
        if not self._evidence_request_active(requested):
            return True, []

        prefix = f"{candidate.tool.key}.{candidate.endpoint.name}"
        locally_sufficient, context, missing = self._local_evidence_status(
            candidate,
            selected_fields,
            requested,
        )
        if not locally_sufficient:
            message = (
                f"{prefix}: local evidence insufficient: " + ", ".join(missing)
            )
            if self.decision_policy.fallback == "error":
                raise PlanningError(message)
            return False, [message]

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

    def _build_plan(
        self,
        request: PlanRequest,
        intent: QueryIntent,
        *,
        async_decision: bool,
    ) -> ExecutionPlan:
        del async_decision
        candidates = self._candidates(request, intent)
        candidates, decision_warnings = self._select_candidates_sync(request, candidates)

        warnings: list[str] = list(decision_warnings)
        if not candidates:
            return ExecutionPlan(
                query=request.query,
                registry_version=self.registry.version,
                calls=[],
                warnings=["no schema candidate matched the request"],
            )

        calls: list[ToolCall] = []
        for candidate in candidates[: request.max_calls]:
            endpoint = candidate.endpoint
            declared = {parameter.name: parameter for parameter in endpoint.parameters}
            arguments = {
                name: value
                for name, value in intent.arguments.items()
                if name in declared
            }
            dropped = sorted(set(intent.arguments) - set(arguments))
            if dropped:
                warnings.append(
                    f"{candidate.tool.key}.{endpoint.name}: ignored undeclared arguments: "
                    + ", ".join(dropped)
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
                intent.evidence,
            )
            evidence_ok, evidence_warnings = self._assess_evidence_sync(
                request,
                candidate,
                fields,
                intent.evidence,
            )
            warnings.extend(evidence_warnings)
            if not evidence_ok:
                continue

            calls.append(
                ToolCall(
                    tool=candidate.tool.key,
                    endpoint=endpoint.name,
                    arguments=arguments,
                    fields=fields,
                    evidence=evidence,
                    schema_fingerprint=endpoint.fingerprint,
                    missing_required_arguments=missing,
                    score=candidate.score,
                )
            )

        return ExecutionPlan(
            query=request.query,
            registry_version=self.registry.version,
            calls=calls,
            warnings=warnings,
        )

    async def _abuild_plan(
        self,
        request: PlanRequest,
        intent: QueryIntent,
    ) -> ExecutionPlan:
        candidates = self._candidates(request, intent)
        candidates, decision_warnings = await self._select_candidates_async(request, candidates)
        if not candidates:
            return ExecutionPlan(
                query=request.query,
                registry_version=self.registry.version,
                calls=[],
                warnings=[*decision_warnings, "no schema candidate matched the request"],
            )

        calls: list[ToolCall] = []
        warnings = list(decision_warnings)
        for candidate in candidates[: request.max_calls]:
            endpoint = candidate.endpoint
            declared = {parameter.name: parameter for parameter in endpoint.parameters}
            arguments = {
                name: value
                for name, value in intent.arguments.items()
                if name in declared
            }
            dropped = sorted(set(intent.arguments) - set(arguments))
            if dropped:
                warnings.append(
                    f"{candidate.tool.key}.{endpoint.name}: ignored undeclared arguments: "
                    + ", ".join(dropped)
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
                intent.evidence,
            )
            evidence_ok, evidence_warnings = await self._assess_evidence_async(
                request,
                candidate,
                fields,
                intent.evidence,
            )
            warnings.extend(evidence_warnings)
            if not evidence_ok:
                continue

            calls.append(
                ToolCall(
                    tool=candidate.tool.key,
                    endpoint=endpoint.name,
                    arguments=arguments,
                    fields=fields,
                    evidence=evidence,
                    schema_fingerprint=endpoint.fingerprint,
                    missing_required_arguments=missing,
                    score=candidate.score,
                )
            )
        return ExecutionPlan(
            query=request.query,
            registry_version=self.registry.version,
            calls=calls,
            warnings=warnings,
        )

    def _score_endpoint(
        self,
        tool: ToolSpec,
        endpoint: EndpointSpec,
        query: str,
        intent: QueryIntent,
    ) -> _Candidate:
        query_tokens = _tokens(query)
        concept_norms = {_normalize(concept) for concept in intent.concepts if concept}
        preferred_tools = set(intent.preferred_tools)
        preferred_endpoints = set(intent.preferred_endpoints)

        score = 0.0
        if tool.key in preferred_tools or tool.name in preferred_tools:
            score += 100.0

        endpoint_key = f"{tool.key}.{endpoint.name}"
        if endpoint_key in preferred_endpoints:
            score += 250.0

        tool_text = " ".join([tool.name, tool.description, endpoint.name, endpoint.description])
        score += 1.5 * len(query_tokens & _tokens(tool_text))

        matched_fields: list[str] = []
        for field in endpoint.output_fields:
            names = [
                field.name,
                *field.aliases,
                ".".join(field.projection_path),
            ]
            norms = {_normalize(name) for name in names if name}
            exact = bool(norms & concept_norms)
            lexical = any(query_tokens & _tokens(name) for name in names)
            substring = any(
                concept and norm and (concept in norm or norm in concept)
                for concept in concept_norms
                for norm in norms
            )
            if exact:
                score += 6.0
                matched_fields.append(field.name)
            elif lexical:
                score += 3.0
                matched_fields.append(field.name)
            elif substring:
                score += 1.0
                matched_fields.append(field.name)

        for parameter in endpoint.parameters:
            if parameter.name in intent.arguments:
                score += 2.0

        return _Candidate(
            tool,
            endpoint,
            score,
            tuple(dict.fromkeys(matched_fields)),
        )

    @staticmethod
    def _project_fields(
        endpoint: EndpointSpec,
        intent: QueryIntent,
        matched_fields: tuple[str, ...],
    ) -> list[str]:
        if not endpoint.output_fields:
            return []

        identifiers = [field.name for field in endpoint.output_fields if field.identifier]
        selected = list(dict.fromkeys([*identifiers, *matched_fields]))

        # Recall-first fallback: if we could not identify an answer field, do not silently
        # prune a typed response to identifiers only. The executor may later apply a cost policy.
        answer_fields = [name for name in selected if name not in set(identifiers)]
        if not answer_fields:
            return [field.name for field in endpoint.output_fields]
        return selected

    @staticmethod
    def _evidence(
        tool: ToolSpec,
        endpoint: EndpointSpec,
        selected_fields: list[str],
        requested: EvidenceRequirements,
    ) -> EvidenceRequirements:
        field_map: dict[str, FieldSpec] = {
            field.name: field
            for field in endpoint.output_fields
        }
        return EvidenceRequirements(
            provenance=requested.provenance or bool(tool.source_type),
            license=requested.license or bool(tool.license),
            units=requested.units
            or any(
                field_map.get(name) and field_map[name].unit
                for name in selected_fields
            ),
            source_type=requested.source_type or tool.source_type,
        )
