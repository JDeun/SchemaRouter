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
            fields = self._project_fields(endpoint, intent, candidate.matched_fields)
            calls.append(
                ToolCall(
                    tool=candidate.tool.key,
                    endpoint=endpoint.name,
                    arguments=arguments,
                    fields=fields,
                    evidence=self._evidence(candidate.tool, fields, intent.evidence),
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
            arguments = {name: value for name, value in intent.arguments.items() if name in declared}
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
            fields = self._project_fields(endpoint, intent, candidate.matched_fields)
            calls.append(
                ToolCall(
                    tool=candidate.tool.key,
                    endpoint=endpoint.name,
                    arguments=arguments,
                    fields=fields,
                    evidence=self._evidence(candidate.tool, fields, intent.evidence),
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
            names = [field.name, *field.aliases]
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
        selected_fields: list[str],
        requested: EvidenceRequirements,
    ) -> EvidenceRequirements:
        field_map: dict[str, FieldSpec] = {
            field.name: field
            for endpoint in tool.endpoints
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
