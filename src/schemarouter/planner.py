from __future__ import annotations

import inspect
import re
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, replace
from typing import Any, Protocol

from .decision_policy import DecisionPolicy
from .decisions import DecisionBackend, DecisionOption, DecisionRequest, choose_async, choose_sync
from .errors import PlanningError
from .evidence import available_evidence, field_evidence_status, global_evidence_status
from .graph_routing import CompiledSchemaGraph, GraphOperationGate
from .models import (
    CandidateSelectionSource,
    EndpointSpec,
    EvidenceRequirements,
    ExecutionPlan,
    FallbackRoute,
    FieldSelectionExplanation,
    FieldSelectionReason,
    FieldSpec,
    PlanCoverage,
    PlanExplanation,
    PlanRequest,
    QueryIntent,
    ScoreComponent,
    SemanticFieldRequirement,
    ToolCall,
    ToolSpec,
)
from .registry import ToolRegistry
from .validation import (
    canonical_field_value_schema,
    json_schema_types,
    json_schemas_compatible,
)

_TOKEN_RE = re.compile(r"[A-Za-z0-9_]+|[가-힣]+")


def _normalize(text: str) -> str:
    return "".join(ch.lower() for ch in text if ch.isalnum())


def _semantic_substring_match(left: str, right: str) -> bool:
    """Conservative containment for compound non-ASCII semantic labels.

    Short ASCII tokens such as chemical symbols ("Si") must never match unrelated
    field names such as "density" merely because the same letters occur inside them.
    ASCII semantic matching is already handled by exact normalization and token overlap.
    """

    if not left or not right:
        return False
    if left.isascii() and right.isascii():
        # Avoid accidental chemistry/token collisions such as "Si" inside "density"
        # while preserving useful semantic compounds such as "conductivity" inside
        # "thermalconductivity" or "elastic" inside "elasticmodulus".
        if min(len(left), len(right)) < 4:
            return False
    elif min(len(left), len(right)) < 3:
        return False
    return left in right or right in left


def _matched_field_qualifiers(query: str, field: FieldSpec) -> tuple[str, ...]:
    """Return trusted qualifier tags that are visibly present in the query.

    Matching is token-bounded for ASCII/numeric values so 300 K cannot match
    1300 K. Very short ASCII values such as K are ignored by themselves
    unless the query also contains their qualifier key. Non-ASCII values fall back
    to normalized literal containment because the lightweight tokenizer intentionally
    covers only ASCII words/numbers and Korean text.
    """

    if not field.qualifiers:
        return ()

    query_tokens = _tokens(query)
    query_norm = _normalize(query)
    if not query_tokens and not query_norm:
        return ()

    matches: list[str] = []
    for key, value in sorted(field.qualifiers.items()):
        value_tokens = _tokens(value)
        value_norm = _normalize(value)

        token_value_match = bool(
            value_tokens
            and value_tokens.issubset(query_tokens)
            and (
                len(value_tokens) > 1
                or any(len(token) >= 3 for token in value_tokens)
            )
        )
        non_ascii_value_match = bool(
            value_norm
            and not value_norm.isascii()
            and value_norm in query_norm
        )

        keyed_tokens = _tokens(f"{key} {value}")
        keyed_match = bool(
            len(keyed_tokens) > 1
            and keyed_tokens.issubset(query_tokens)
        )

        if token_value_match or non_ascii_value_match or keyed_match:
            matches.append(f"{key}={value}")
    return tuple(matches)

_KOREAN_PARTICLE_SUFFIXES = (
    "에서",
    "에게",
    "으로",
    "까지",
    "부터",
    "처럼",
    "보다",
    "을",
    "를",
    "이",
    "가",
    "은",
    "는",
    "의",
    "에",
    "로",
    "와",
    "과",
)


def _tokens(text: str) -> set[str]:
    tokens = {token.lower() for token in _TOKEN_RE.findall(text)}
    expanded = set(tokens)
    for token in tokens:
        if not token or not all("가" <= char <= "힣" for char in token):
            continue
        for suffix in _KOREAN_PARTICLE_SUFFIXES:
            if token.endswith(suffix) and len(token) > len(suffix) + 1:
                expanded.add(token[: -len(suffix)])
                break
    return expanded


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
            field_evidence=request.field_evidence,
        )


@dataclass(frozen=True)
class _FieldSemantic:
    names: frozenset[str]
    semantic_id: str | None
    json_schema: dict[str, object]
    qualifiers: tuple[tuple[str, str], ...]
    unit: str | None
    unit_dimension: str | None
    canonical_unit: str | None
    unit_scale: float | None
    unit_offset: float | None


@dataclass(frozen=True)
class _Candidate:
    tool: ToolSpec
    endpoint: EndpointSpec
    score: float
    matched_fields: tuple[str, ...]
    score_components: tuple[ScoreComponent, ...] = ()
    field_reasons: tuple[tuple[str, FieldSelectionReason], ...] = ()
    selection_source: CandidateSelectionSource = "deterministic"


@dataclass(frozen=True, order=True)
class _EndpointRef:
    tool_key: str
    endpoint_name: str


class _CandidateIndex:
    """Exact-recall lexical prefilter for the deterministic endpoint scorer."""

    def __init__(self, version: int, tools: tuple[ToolSpec, ...]) -> None:
        self.version = version
        self._entries: dict[_EndpointRef, tuple[ToolSpec, EndpointSpec]] = {}
        self._token_refs: dict[str, set[_EndpointRef]] = {}
        self._field_norm_refs: dict[str, set[_EndpointRef]] = {}
        self._parameter_refs: dict[str, set[_EndpointRef]] = {}
        self._tool_refs: dict[str, set[_EndpointRef]] = {}
        self._endpoint_refs: dict[str, set[_EndpointRef]] = {}

        for tool in tools:
            for endpoint in tool.endpoints:
                ref = _EndpointRef(tool.key, endpoint.name)
                self._entries[ref] = (tool, endpoint)
                self._add(self._tool_refs, tool.key, ref)
                self._add(self._tool_refs, tool.name, ref)
                self._add(
                    self._endpoint_refs,
                    f"{tool.key}.{endpoint.name}",
                    ref,
                )

                tool_text = " ".join(
                    [
                        tool.name,
                        tool.description,
                        endpoint.name,
                        endpoint.description,
                    ]
                )
                for token in _tokens(tool_text):
                    self._add(self._token_refs, token, ref)

                for field in endpoint.output_fields:
                    names = [
                        field.name,
                        field.semantic_id or "",
                        *field.aliases,
                        ".".join(field.projection_path),
                    ]
                    for name in names:
                        if not name:
                            continue
                        for token in _tokens(name):
                            self._add(self._token_refs, token, ref)
                        norm = _normalize(name)
                        if norm:
                            self._add(self._field_norm_refs, norm, ref)

                for parameter in endpoint.parameters:
                    self._add(self._parameter_refs, parameter.name, ref)
                    for alias in parameter.aliases:
                        self._add(self._parameter_refs, alias, ref)

    @staticmethod
    def _add(
        index: dict[str, set[_EndpointRef]],
        key: str,
        ref: _EndpointRef,
    ) -> None:
        index.setdefault(key, set()).add(ref)

    def endpoint_pairs(
        self,
        request: PlanRequest,
        intent: QueryIntent,
    ) -> tuple[tuple[ToolSpec, EndpointSpec], ...]:
        refs: set[_EndpointRef] = set()

        for preferred in intent.preferred_tools:
            refs.update(self._tool_refs.get(preferred, ()))
        for preferred in intent.preferred_endpoints:
            refs.update(self._endpoint_refs.get(preferred, ()))

        for token in _tokens(request.query):
            refs.update(self._token_refs.get(token, ()))
        for parameter_name in intent.arguments:
            refs.update(self._parameter_refs.get(parameter_name, ()))

        concept_norms = {
            _normalize(concept)
            for concept in intent.concepts
            if concept and _normalize(concept)
        }
        for concept in concept_norms:
            refs.update(self._field_norm_refs.get(concept, ()))

        if concept_norms:
            for norm, norm_refs in self._field_norm_refs.items():
                if any(
                    _semantic_substring_match(concept, norm)
                    for concept in concept_norms
                ):
                    refs.update(norm_refs)

        return tuple(self._entries[ref] for ref in sorted(refs))


class SchemaPlanner:
    """Schema-aware planner with sync and async query-analysis paths."""

    def __init__(
        self,
        registry: ToolRegistry,
        analyzer: QueryAnalyzer | None = None,
        *,
        decision_backend: DecisionBackend | None = None,
        decision_policy: DecisionPolicy | None = None,
        candidate_recall_backend: DecisionBackend | None = None,
        candidate_recall_limit: int = 4,
        candidate_fit_backend: DecisionBackend | None = None,
        operation_fit_backend: DecisionBackend | None = None,
        graph_operation_gate: GraphOperationGate | None = None,
        graph_semantic_seed_backend: DecisionBackend | None = None,
        endpoint_disambiguation_backend: DecisionBackend | None = None,
        candidate_index: bool = True,
        availability_predicate: Callable[[ToolSpec, EndpointSpec], bool] | None = None,
    ) -> None:
        if (
            not isinstance(candidate_recall_limit, int)
            or isinstance(candidate_recall_limit, bool)
            or candidate_recall_limit < 1
        ):
            raise ValueError("candidate_recall_limit must be an integer >= 1")
        self.registry = registry
        self.analyzer = analyzer or KeywordAnalyzer()
        self.decision_backend = decision_backend
        self.decision_policy = decision_policy or DecisionPolicy()
        self.candidate_recall_backend = candidate_recall_backend
        self.candidate_recall_limit = candidate_recall_limit
        self.candidate_fit_backend = candidate_fit_backend
        self.operation_fit_backend = operation_fit_backend
        self.graph_operation_gate = graph_operation_gate
        self.graph_semantic_seed_backend = graph_semantic_seed_backend
        self.endpoint_disambiguation_backend = endpoint_disambiguation_backend
        self.candidate_index = candidate_index
        self.availability_predicate = availability_predicate
        self._candidate_index: _CandidateIndex | None = None
        self._compiled_schema_graph: CompiledSchemaGraph | None = None
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

    def plan_with_additional_availability(
        self,
        request: PlanRequest | str,
        predicate: Callable[[ToolSpec, EndpointSpec], bool],
    ) -> ExecutionPlan:
        """Plan with one extra local availability predicate.

        The configured planner availability predicate still applies. This is used by
        execution-facing runtimes to add local readiness constraints (for example, current
        invoker binding state) without changing schema-only planning semantics.
        """

        request = self._prepare_request(request)
        intent = self.analyzer.analyze(request, self.registry)
        if inspect.isawaitable(intent):
            if inspect.iscoroutine(intent):
                intent.close()
            raise PlanningError(
                "the configured analyzer is asynchronous; use "
                "await planner.aplan_with_additional_availability(...)"
            )
        return self._build_plan(
            request,
            intent,
            async_decision=False,
            additional_availability_predicate=predicate,
        )

    async def aplan_with_additional_availability(
        self,
        request: PlanRequest | str,
        predicate: Callable[[ToolSpec, EndpointSpec], bool],
    ) -> ExecutionPlan:
        """Async counterpart to :meth:`plan_with_additional_availability`."""

        request = self._prepare_request(request)
        intent = self.analyzer.analyze(request, self.registry)
        if inspect.isawaitable(intent):
            intent = await intent
        return await self._abuild_plan(
            request,
            intent,
            additional_availability_predicate=predicate,
        )

    def _prepare_request(self, request: PlanRequest | str) -> PlanRequest:
        if isinstance(request, str):
            request = PlanRequest(query=request)
        if not self.registry.keys():
            raise PlanningError("cannot plan with an empty registry")

        active_field_evidence = {
            semantic_id
            for semantic_id, requirement in request.field_evidence.items()
            if self._evidence_request_active(requirement)
        }
        if active_field_evidence:
            declared_semantics = {
                _normalize(field.semantic_id or field.name)
                for tool in self.registry.tools()
                for endpoint in tool.endpoints
                for field in endpoint.output_fields
                if not field.identifier
            }
            unknown = sorted(
                semantic_id
                for semantic_id in active_field_evidence
                if _normalize(semantic_id) not in declared_semantics
            )
            if unknown:
                raise PlanningError(
                    "unknown field_evidence semantic ID(s): " + ", ".join(unknown)
                )
        return request

    def _index(self) -> _CandidateIndex:
        current_version = self.registry.version
        if (
            self._candidate_index is not None
            and self._candidate_index.version == current_version
        ):
            return self._candidate_index

        for _ in range(4):
            before = self.registry.version
            tools = self.registry.tools()
            after = self.registry.version
            if before == after:
                self._candidate_index = _CandidateIndex(after, tools)
                return self._candidate_index

        raise PlanningError(
            "registry changed repeatedly while building the candidate index"
        )

    def _graph(self) -> CompiledSchemaGraph:
        current_version = self.registry.version
        if (
            self._compiled_schema_graph is not None
            and self._compiled_schema_graph.version == current_version
        ):
            return self._compiled_schema_graph

        for _ in range(4):
            before = self.registry.version
            tools = self.registry.tools()
            after = self.registry.version
            if before == after:
                self._compiled_schema_graph = CompiledSchemaGraph.compile(
                    version=after,
                    tools=tools,
                )
                return self._compiled_schema_graph

        raise PlanningError(
            "registry changed repeatedly while compiling the schema graph"
        )

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
    ) -> list[_Candidate]:
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

        if self.candidate_index:
            endpoint_pairs = self._index().endpoint_pairs(request, intent)
        else:
            endpoint_pairs = tuple(
                (tool, endpoint)
                for tool in self.registry.tools()
                for endpoint in tool.endpoints
            )

        if (
            self.availability_predicate is not None
            or additional_availability_predicate is not None
        ):
            endpoint_pairs = tuple(
                (tool, endpoint)
                for tool, endpoint in endpoint_pairs
                if is_available(tool, endpoint)
            )

        candidates = [
            self._score_endpoint(tool, endpoint, request.query, intent)
            for tool, endpoint in endpoint_pairs
        ]
        candidates = [candidate for candidate in candidates if candidate.score > 0]
        if (
            not candidates
            and self.decision_policy.candidate_recall_on_empty_enabled
            and self.candidate_recall_backend is None
        ):
            candidates = [
                _Candidate(tool, endpoint, 0.0, ())
                for tool in self.registry.tools()
                for endpoint in tool.endpoints
                if is_available(tool, endpoint)
            ]
        candidates.sort(
            key=lambda candidate: (
                -candidate.score,
                candidate.endpoint.server_projection is None,
                candidate.tool.key,
                candidate.endpoint.name,
            )
        )
        return candidates

    def _semantic_recall_catalog(
        self,
        request: PlanRequest,
        intent: QueryIntent,
        *,
        additional_availability_predicate: Callable[
            [ToolSpec, EndpointSpec],
            bool,
        ]
        | None = None,
    ) -> list[_Candidate]:
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

        return [
            self._score_endpoint(tool, endpoint, request.query, intent)
            for tool in self.registry.tools()
            for endpoint in tool.endpoints
            if is_available(tool, endpoint)
        ]

    def _semantic_recall_request(
        self,
        request: PlanRequest,
        catalog: list[_Candidate],
    ) -> DecisionRequest:
        options: list[DecisionOption] = []
        for index, candidate in enumerate(catalog):
            field_labels = [
                field.semantic_id or field.name
                for field in candidate.endpoint.output_fields
                if not field.identifier
            ]
            parts = [
                candidate.tool.description.strip(),
                candidate.endpoint.description.strip(),
            ]
            if field_labels:
                parts.append("Fields: " + ", ".join(field_labels))
            description = "\n".join(part for part in parts if part)
            options.append(
                DecisionOption(
                    id=f"recall:{index}",
                    label=f"{candidate.tool.key}.{candidate.endpoint.name}",
                    description=description,
                    metadata={"schema_score": candidate.score},
                )
            )
        return DecisionRequest(
            query=request.query,
            options=options,
            max_selections=min(self.candidate_recall_limit, len(options)),
            context={"surface": "semantic_candidate_recall"},
        )

    @staticmethod
    def _merge_semantic_recall(
        candidates: list[_Candidate],
        catalog: list[_Candidate],
        selected_indexes: list[int],
    ) -> tuple[list[_Candidate], int]:
        existing = {
            (candidate.tool.key, candidate.endpoint.name)
            for candidate in candidates
        }
        merged = list(candidates)
        added = 0
        for index in selected_indexes:
            candidate = catalog[index]
            key = (candidate.tool.key, candidate.endpoint.name)
            if key in existing:
                continue
            merged.append(
                replace(
                    candidate,
                    selection_source="semantic_recall",
                )
            )
            existing.add(key)
            added += 1
        return merged, added

    def _augment_candidates_with_semantic_recall_sync(
        self,
        request: PlanRequest,
        intent: QueryIntent,
        candidates: list[_Candidate],
        *,
        additional_availability_predicate: Callable[
            [ToolSpec, EndpointSpec],
            bool,
        ]
        | None = None,
    ) -> tuple[list[_Candidate], list[str]]:
        if self.candidate_recall_backend is None:
            return candidates, []

        catalog = self._semantic_recall_catalog(
            request,
            intent,
            additional_availability_predicate=additional_availability_predicate,
        )
        if not catalog:
            return candidates, []

        try:
            result = choose_sync(
                self.candidate_recall_backend,
                self._semantic_recall_request(request, catalog),
            )
        except Exception as exc:
            return candidates, [
                "semantic candidate recall fallback: "
                f"{type(exc).__name__}; retained lexical candidates"
            ]

        if result.abstained or not result.selections:
            return candidates, ["semantic candidate recall abstained"]

        selected_indexes = [
            int(item.option_id.split(":", 1)[1])
            for item in result.selections
        ]
        merged, added = self._merge_semantic_recall(
            candidates,
            catalog,
            selected_indexes,
        )
        return merged, [
            f"semantic candidate recall added {added} candidate(s)"
        ]

    async def _augment_candidates_with_semantic_recall_async(
        self,
        request: PlanRequest,
        intent: QueryIntent,
        candidates: list[_Candidate],
        *,
        additional_availability_predicate: Callable[
            [ToolSpec, EndpointSpec],
            bool,
        ]
        | None = None,
    ) -> tuple[list[_Candidate], list[str]]:
        if self.candidate_recall_backend is None:
            return candidates, []

        catalog = self._semantic_recall_catalog(
            request,
            intent,
            additional_availability_predicate=additional_availability_predicate,
        )
        if not catalog:
            return candidates, []

        try:
            result = await choose_async(
                self.candidate_recall_backend,
                self._semantic_recall_request(request, catalog),
            )
        except Exception as exc:
            return candidates, [
                "semantic candidate recall fallback: "
                f"{type(exc).__name__}; retained lexical candidates"
            ]

        if result.abstained or not result.selections:
            return candidates, ["semantic candidate recall abstained"]

        selected_indexes = [
            int(item.option_id.split(":", 1)[1])
            for item in result.selections
        ]
        merged, added = self._merge_semantic_recall(
            candidates,
            catalog,
            selected_indexes,
        )
        return merged, [
            f"semantic candidate recall added {added} candidate(s)"
        ]

    @staticmethod
    def _capability_fit_request(
        request: PlanRequest,
        candidates: list[_Candidate],
    ) -> DecisionRequest:
        options: list[DecisionOption] = []
        for index, candidate in enumerate(candidates):
            field_labels = [
                field.semantic_id or field.name
                for field in candidate.endpoint.output_fields
                if not field.identifier
            ]
            parts = [
                candidate.tool.description.strip(),
                candidate.endpoint.description.strip(),
            ]
            if field_labels:
                parts.append("Fields: " + ", ".join(field_labels))
            options.append(
                DecisionOption(
                    id=f"fit:{index}",
                    label=f"{candidate.tool.key}.{candidate.endpoint.name}",
                    description="\n".join(part for part in parts if part),
                    metadata={"schema_score": candidate.score},
                )
            )
        return DecisionRequest(
            query=request.query,
            options=options,
            max_selections=1,
            context={"surface": "capability_fit"},
        )

    def _apply_capability_fit_sync(
        self,
        request: PlanRequest,
        candidates: list[_Candidate],
    ) -> tuple[list[_Candidate], list[str]]:
        if self.candidate_fit_backend is None or not candidates:
            return candidates, []
        try:
            result = choose_sync(
                self.candidate_fit_backend,
                self._capability_fit_request(request, candidates),
            )
        except Exception as exc:
            return candidates, [
                "capability fit fallback: "
                f"{type(exc).__name__}; retained authorized candidates"
            ]
        if result.abstained or not result.selections:
            return [], ["capability fit gate abstained; suppressed candidate routes"]
        accepted = result.selections[0].option_id
        return candidates, [f"capability fit gate accepted via {accepted}"]

    async def _apply_capability_fit_async(
        self,
        request: PlanRequest,
        candidates: list[_Candidate],
    ) -> tuple[list[_Candidate], list[str]]:
        if self.candidate_fit_backend is None or not candidates:
            return candidates, []
        try:
            result = await choose_async(
                self.candidate_fit_backend,
                self._capability_fit_request(request, candidates),
            )
        except Exception as exc:
            return candidates, [
                "capability fit fallback: "
                f"{type(exc).__name__}; retained authorized candidates"
            ]
        if result.abstained or not result.selections:
            return [], ["capability fit gate abstained; suppressed candidate routes"]
        accepted = result.selections[0].option_id
        return candidates, [f"capability fit gate accepted via {accepted}"]

    @staticmethod
    def _operation_fit_request(
        request: PlanRequest,
        candidates: list[_Candidate],
    ) -> DecisionRequest | None:
        """Build a narrow operation-only fit surface for the leading tool domain.

        This gate deliberately excludes the tool description and output-field labels so
        domain similarity cannot by itself turn an unsupported operation into a match.
        It can only suppress the already-authorized candidate set; it never selects,
        adds, or reorders execution candidates.
        """

        if request.max_calls > 1 or not candidates:
            return None

        primary_tool = candidates[0].tool.key
        sibling_candidates = [
            candidate
            for candidate in candidates
            if candidate.tool.key == primary_tool
        ]
        if not sibling_candidates:
            return None

        options: list[DecisionOption] = []
        for index, candidate in enumerate(sibling_candidates):
            endpoint = candidate.endpoint
            operation_name = endpoint.name.replace("_", " ").replace("-", " ")
            parts = [operation_name]
            if endpoint.operation_aliases:
                parts.extend(endpoint.operation_aliases)
            if endpoint.description.strip():
                parts.append(endpoint.description.strip())
            options.append(
                DecisionOption(
                    id=f"operation:{index}",
                    label=endpoint.name,
                    description="\n".join(part for part in parts if part),
                    metadata={"tool": primary_tool},
                )
            )

        return DecisionRequest(
            query=request.query,
            options=options,
            max_selections=1,
            context={
                "surface": "operation_capability_fit",
                "tool": primary_tool,
            },
        )

    def _graph_first_candidates(
        self,
        request: PlanRequest,
        intent: QueryIntent,
        *,
        additional_availability_predicate: Callable[
            [ToolSpec, EndpointSpec],
            bool,
        ]
        | None = None,
    ) -> tuple[list[_Candidate], list[str], bool]:
        if (
            self.graph_operation_gate is None
            or request.max_calls > 1
            or request.fallback_scope != "disabled"
        ):
            return [], [], True

        assessment = self.graph_operation_gate.assess_global(
            query=request.query,
            graph=self._graph(),
        )
        if assessment.decision == "reject":
            return [], [
                "graph operation gate rejected the route: "
                + assessment.reason
            ], False
        if assessment.decision != "accept":
            return [], [
                "graph operation gate escalated: " + assessment.reason
            ], True

        tool_key = assessment.tool_key
        endpoint_name = assessment.endpoint_name
        if not tool_key or endpoint_name is None:
            return [], [
                "graph operation gate produced an incomplete authorized path; escalated"
            ], True

        try:
            tool = self.registry.get(tool_key)
            endpoint = tool.endpoint(endpoint_name)
        except KeyError:
            return [], [
                "graph operation gate path disappeared from the registry; escalated"
            ], True

        preferred_tools = set(intent.preferred_tools)
        if preferred_tools and tool.key not in preferred_tools and tool.name not in preferred_tools:
            return [], [
                "graph operation gate path conflicted with preferred tool constraints; escalated"
            ], True
        preferred_endpoints = set(intent.preferred_endpoints)
        endpoint_key = f"{tool.key}.{endpoint.name}"
        if preferred_endpoints and endpoint_key not in preferred_endpoints:
            return [], [
                "graph operation gate path conflicted with preferred endpoint "
                "constraints; escalated"
            ], True

        if (
            self.availability_predicate is not None
            and not self.availability_predicate(tool, endpoint)
        ):
            return [], [
                "graph operation gate path is currently unavailable; escalated"
            ], True
        if (
            additional_availability_predicate is not None
            and not additional_availability_predicate(tool, endpoint)
        ):
            return [], [
                "graph operation gate path failed runtime availability; escalated"
            ], True

        candidate = replace(
            self._score_endpoint(
                tool,
                endpoint,
                request.query,
                intent,
            ),
            selection_source="graph_operation",
        )
        return [candidate], [
            "graph operation gate accepted "
            f"{tool.key}.{endpoint.name}: {assessment.reason}"
        ], False

    def _graph_semantic_seed_request(
        self,
        request: PlanRequest,
        intent: QueryIntent,
        *,
        additional_availability_predicate: Callable[
            [ToolSpec, EndpointSpec],
            bool,
        ]
        | None = None,
    ) -> tuple[
        DecisionRequest | None,
        dict[str, tuple[ToolSpec, EndpointSpec]],
    ]:
        if (
            self.graph_semantic_seed_backend is None
            or request.max_calls > 1
            or request.fallback_scope != "disabled"
        ):
            return None, {}

        graph = self._graph()
        preferred_tools = set(intent.preferred_tools)
        preferred_endpoints = set(intent.preferred_endpoints)
        authorized: dict[str, tuple[ToolSpec, EndpointSpec]] = {}
        options: list[DecisionOption] = []

        for tool_key, endpoint_name in graph.operation_routes():
            try:
                tool = self.registry.get(tool_key)
                endpoint = tool.endpoint(endpoint_name)
            except KeyError:
                continue

            if (
                preferred_tools
                and tool.key not in preferred_tools
                and tool.name not in preferred_tools
            ):
                continue
            route_id = f"{tool.key}.{endpoint.name}"
            if preferred_endpoints and route_id not in preferred_endpoints:
                continue
            if (
                self.availability_predicate is not None
                and not self.availability_predicate(tool, endpoint)
            ):
                continue
            if (
                additional_availability_predicate is not None
                and not additional_availability_predicate(tool, endpoint)
            ):
                continue

            field_terms: list[str] = []
            for field in endpoint.output_fields:
                if field.identifier:
                    continue
                field_terms.extend(
                    term
                    for term in [
                        field.semantic_id or field.name,
                        *field.aliases,
                    ]
                    if term
                )

            operation_name = endpoint.name.replace("_", " ").replace("-", " ")
            parts = [
                f"tool: {tool.name}",
                tool.description.strip(),
                f"operation: {operation_name}",
                *endpoint.operation_aliases,
                endpoint.description.strip(),
            ]
            if field_terms:
                parts.append("returns: " + ", ".join(dict.fromkeys(field_terms)))

            authorized[route_id] = (tool, endpoint)
            options.append(
                DecisionOption(
                    id=route_id,
                    label=route_id,
                    description="\n".join(part for part in parts if part),
                    metadata={
                        "tool": tool.key,
                        "endpoint": endpoint.name,
                        "surface": "graph_semantic_seed",
                    },
                )
            )

        if not options:
            return None, {}

        return (
            DecisionRequest(
                query=request.query,
                options=options,
                max_selections=1,
                context={
                    "surface": "graph_semantic_seed",
                    "authority": "registered_schema_graph_only",
                },
            ),
            authorized,
        )

    def _graph_semantic_seed_candidates_sync(
        self,
        request: PlanRequest,
        intent: QueryIntent,
        *,
        additional_availability_predicate: Callable[
            [ToolSpec, EndpointSpec],
            bool,
        ]
        | None = None,
    ) -> tuple[list[_Candidate], list[str], bool]:
        decision_request, authorized = self._graph_semantic_seed_request(
            request,
            intent,
            additional_availability_predicate=additional_availability_predicate,
        )
        if decision_request is None or self.graph_semantic_seed_backend is None:
            return [], [], True

        try:
            result = choose_sync(
                self.graph_semantic_seed_backend,
                decision_request,
            )
        except Exception as exc:
            return [], [
                "graph semantic seed fallback: "
                f"{type(exc).__name__}; escalated to semantic routing"
            ], True

        if result.abstained or not result.selections:
            reason = result.metadata.get("reason")
            suffix = f" ({reason})" if isinstance(reason, str) and reason else ""
            return [], [
                "graph semantic seed abstained"
                + suffix
                + "; escalated to semantic routing"
            ], True

        route_id = result.selections[0].option_id
        target = authorized.get(route_id)
        if target is None:
            return [], [
                "graph semantic seed returned no authorized graph node; escalated"
            ], True

        tool, endpoint = target
        candidate = replace(
            self._score_endpoint(
                tool,
                endpoint,
                request.query,
                intent,
            ),
            selection_source="graph_semantic_seed",
        )
        score = result.selections[0].score
        score_suffix = f" score={score:.6f}" if score is not None else ""
        return [candidate], [
            "graph semantic seed accepted "
            f"{route_id}{score_suffix}; path remained schema-authorized"
        ], False

    async def _graph_semantic_seed_candidates_async(
        self,
        request: PlanRequest,
        intent: QueryIntent,
        *,
        additional_availability_predicate: Callable[
            [ToolSpec, EndpointSpec],
            bool,
        ]
        | None = None,
    ) -> tuple[list[_Candidate], list[str], bool]:
        decision_request, authorized = self._graph_semantic_seed_request(
            request,
            intent,
            additional_availability_predicate=additional_availability_predicate,
        )
        if decision_request is None or self.graph_semantic_seed_backend is None:
            return [], [], True

        try:
            result = await choose_async(
                self.graph_semantic_seed_backend,
                decision_request,
            )
        except Exception as exc:
            return [], [
                "graph semantic seed fallback: "
                f"{type(exc).__name__}; escalated to semantic routing"
            ], True

        if result.abstained or not result.selections:
            reason = result.metadata.get("reason")
            suffix = f" ({reason})" if isinstance(reason, str) and reason else ""
            return [], [
                "graph semantic seed abstained"
                + suffix
                + "; escalated to semantic routing"
            ], True

        route_id = result.selections[0].option_id
        target = authorized.get(route_id)
        if target is None:
            return [], [
                "graph semantic seed returned no authorized graph node; escalated"
            ], True

        tool, endpoint = target
        candidate = replace(
            self._score_endpoint(
                tool,
                endpoint,
                request.query,
                intent,
            ),
            selection_source="graph_semantic_seed",
        )
        score = result.selections[0].score
        score_suffix = f" score={score:.6f}" if score is not None else ""
        return [candidate], [
            "graph semantic seed accepted "
            f"{route_id}{score_suffix}; path remained schema-authorized"
        ], False

    def _apply_operation_fit_sync(
        self,
        request: PlanRequest,
        candidates: list[_Candidate],
    ) -> tuple[list[_Candidate], list[str]]:
        if self.operation_fit_backend is None or not candidates:
            return candidates, []

        decision_request = self._operation_fit_request(request, candidates)
        if decision_request is None:
            return candidates, []

        try:
            result = choose_sync(
                self.operation_fit_backend,
                decision_request,
            )
        except Exception as exc:
            return candidates, [
                "operation capability fit fallback: "
                f"{type(exc).__name__}; retained authorized candidates"
            ]

        if result.abstained or not result.selections:
            return [], [
                "operation capability fit gate abstained; "
                "suppressed candidate routes"
            ]

        accepted = result.selections[0].option_id
        return candidates, [
            f"operation capability fit gate accepted via {accepted}"
        ]

    async def _apply_operation_fit_async(
        self,
        request: PlanRequest,
        candidates: list[_Candidate],
    ) -> tuple[list[_Candidate], list[str]]:
        if self.operation_fit_backend is None or not candidates:
            return candidates, []

        decision_request = self._operation_fit_request(request, candidates)
        if decision_request is None:
            return candidates, []

        try:
            result = await choose_async(
                self.operation_fit_backend,
                decision_request,
            )
        except Exception as exc:
            return candidates, [
                "operation capability fit fallback: "
                f"{type(exc).__name__}; retained authorized candidates"
            ]

        if result.abstained or not result.selections:
            return [], [
                "operation capability fit gate abstained; "
                "suppressed candidate routes"
            ]

        accepted = result.selections[0].option_id
        return candidates, [
            f"operation capability fit gate accepted via {accepted}"
        ]

    @staticmethod
    def _endpoint_disambiguation_request(
        request: PlanRequest,
        candidates: list[_Candidate],
    ) -> tuple[DecisionRequest | None, list[int]]:
        if request.max_calls > 1 or len(candidates) < 2:
            return None, []

        primary_tool = candidates[0].tool.key
        sibling_indexes = [
            index
            for index, candidate in enumerate(candidates)
            if candidate.tool.key == primary_tool
        ]
        if len(sibling_indexes) < 2:
            return None, []

        options: list[DecisionOption] = []
        for local_index, candidate_index in enumerate(sibling_indexes):
            candidate = candidates[candidate_index]
            field_labels = [
                field.semantic_id or field.name
                for field in candidate.endpoint.output_fields
                if not field.identifier
            ]
            operation = (
                "read-only retrieval"
                if candidate.endpoint.read_only is True
                else "mutating write"
                if candidate.endpoint.read_only is False
                else "unclassified operation"
            )
            parts = [
                candidate.endpoint.description.strip(),
                f"Operation class: {operation}",
            ]
            if field_labels:
                parts.append("Fields: " + ", ".join(field_labels))
            options.append(
                DecisionOption(
                    id=f"endpoint:{local_index}",
                    label=f"{candidate.tool.key}.{candidate.endpoint.name}",
                    description="\n".join(part for part in parts if part),
                    metadata={"candidate_index": candidate_index},
                )
            )

        return (
            DecisionRequest(
                query=request.query,
                options=options,
                max_selections=1,
                context={
                    "surface": "endpoint_disambiguation",
                    "tool": primary_tool,
                },
            ),
            sibling_indexes,
        )

    @staticmethod
    def _apply_endpoint_disambiguation_result(
        candidates: list[_Candidate],
        sibling_indexes: list[int],
        option_id: str,
    ) -> list[_Candidate]:
        local_index = int(option_id.split(":", 1)[1])
        chosen_index = sibling_indexes[local_index]
        chosen = replace(
            candidates[chosen_index],
            selection_source="endpoint_disambiguation",
        )
        return [
            chosen,
            *[
                candidate
                for index, candidate in enumerate(candidates)
                if index != chosen_index
            ],
        ]

    def _disambiguate_endpoints_sync(
        self,
        request: PlanRequest,
        candidates: list[_Candidate],
    ) -> tuple[list[_Candidate], list[str]]:
        if self.endpoint_disambiguation_backend is None or not candidates:
            return candidates, []

        decision_request, sibling_indexes = self._endpoint_disambiguation_request(
            request,
            candidates,
        )
        if decision_request is None:
            return candidates, []

        try:
            result = choose_sync(
                self.endpoint_disambiguation_backend,
                decision_request,
            )
        except Exception as exc:
            return candidates, [
                "endpoint disambiguation fallback: "
                f"{type(exc).__name__}; retained candidate order"
            ]

        if result.abstained or not result.selections:
            return candidates, [
                "endpoint disambiguation abstained; retained candidate order"
            ]

        selected = result.selections[0].option_id
        reordered = self._apply_endpoint_disambiguation_result(
            candidates,
            sibling_indexes,
            selected,
        )
        return reordered, [
            f"endpoint disambiguation selected {selected} within "
            f"{candidates[0].tool.key}"
        ]

    async def _disambiguate_endpoints_async(
        self,
        request: PlanRequest,
        candidates: list[_Candidate],
    ) -> tuple[list[_Candidate], list[str]]:
        if self.endpoint_disambiguation_backend is None or not candidates:
            return candidates, []

        decision_request, sibling_indexes = self._endpoint_disambiguation_request(
            request,
            candidates,
        )
        if decision_request is None:
            return candidates, []

        try:
            result = await choose_async(
                self.endpoint_disambiguation_backend,
                decision_request,
            )
        except Exception as exc:
            return candidates, [
                "endpoint disambiguation fallback: "
                f"{type(exc).__name__}; retained candidate order"
            ]

        if result.abstained or not result.selections:
            return candidates, [
                "endpoint disambiguation abstained; retained candidate order"
            ]

        selected = result.selections[0].option_id
        reordered = self._apply_endpoint_disambiguation_result(
            candidates,
            sibling_indexes,
            selected,
        )
        return reordered, [
            f"endpoint disambiguation selected {selected} within "
            f"{candidates[0].tool.key}"
        ]

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
    def _coverage_requirements_for_candidate(
        candidate: _Candidate,
        query: str,
        *,
        field_names: set[str] | None = None,
    ) -> frozenset[tuple[str, tuple[str, ...]]]:
        """Return query-matched semantic field requirements for one candidate."""

        field_map = {field.name: field for field in candidate.endpoint.output_fields}
        requirements: set[tuple[str, tuple[str, ...]]] = set()
        for field_name in candidate.matched_fields:
            if field_names is not None and field_name not in field_names:
                continue
            field = field_map.get(field_name)
            if field is None or field.identifier:
                continue
            semantic = _normalize(field.semantic_id or field.name)
            if not semantic:
                continue
            requirements.add(
                (
                    semantic,
                    _matched_field_qualifiers(query, field),
                )
            )
        return frozenset(requirements)

    @classmethod
    def _field_coverage_matrix(
        cls,
        request: PlanRequest,
        candidates: list[_Candidate],
    ) -> tuple[
        list[frozenset[tuple[str, tuple[str, ...]]]],
        frozenset[tuple[str, tuple[str, ...]]],
    ]:
        raw_requirements = [
            cls._coverage_requirements_for_candidate(candidate, request.query)
            for candidate in candidates
        ]
        qualified_semantics = {
            semantic
            for requirements in raw_requirements
            for semantic, qualifiers in requirements
            if qualifiers
        }
        coverage = [
            frozenset(
                (semantic, qualifiers)
                for semantic, qualifiers in requirements
                if not (semantic in qualified_semantics and not qualifiers)
            )
            for requirements in raw_requirements
        ]
        universe = frozenset(
            requirement
            for requirements in coverage
            for requirement in requirements
        )
        return coverage, universe

    @classmethod
    def _plan_coverage(
        cls,
        required: frozenset[tuple[str, tuple[str, ...]]],
        covered: set[tuple[str, tuple[str, ...]]],
        candidates: list[_Candidate],
    ) -> PlanCoverage | None:
        """Convert internal coverage keys into a stable public plan contract."""

        if not required:
            return None

        semantic_labels: dict[str, str] = {}
        for candidate in candidates:
            for field in candidate.endpoint.output_fields:
                if field.identifier:
                    continue
                semantic_key = _normalize(field.semantic_id or field.name)
                if semantic_key and semantic_key not in semantic_labels:
                    semantic_labels[semantic_key] = field.semantic_id or field.name

        def public(
            requirement: tuple[str, tuple[str, ...]],
        ) -> SemanticFieldRequirement:
            semantic, qualifiers = requirement
            return SemanticFieldRequirement(
                semantic_id=semantic_labels.get(semantic, semantic),
                qualifiers=list(qualifiers),
            )

        def ordered(
            requirements: set[tuple[str, tuple[str, ...]]]
            | frozenset[tuple[str, tuple[str, ...]]],
        ) -> list[SemanticFieldRequirement]:
            return [
                public(requirement)
                for requirement in sorted(
                    requirements,
                    key=lambda item: (item[0], item[1]),
                )
            ]

        covered_required = set(required) & covered
        uncovered = set(required) - covered_required
        return PlanCoverage(
            required=ordered(required),
            covered=ordered(covered_required),
            uncovered=ordered(uncovered),
            complete=not uncovered,
        )

    @staticmethod
    def _coverage_warning(coverage: PlanCoverage | None) -> str | None:
        if coverage is None or coverage.complete:
            return None

        labels = []
        for requirement in coverage.uncovered:
            label = requirement.semantic_id
            if requirement.qualifiers:
                label += "[" + ", ".join(requirement.qualifiers) + "]"
            labels.append(label)
        return "uncovered semantic field requirements: " + ", ".join(labels)

    @classmethod
    def _order_candidates_for_field_coverage(
        cls,
        request: PlanRequest,
        candidates: list[_Candidate],
    ) -> list[_Candidate]:
        """Prefer complementary semantic-field coverage for explicit multi-call plans.

        max_calls remains the hard authority boundary. This method only changes
        candidate ordering inside that existing bound; it never increases the number
        of planned calls.

        If a query visibly names an exact qualifier for one semantic field, candidates
        for the same semantic field that do not match that qualifier do not create an
        additional coverage requirement.
        """

        if request.max_calls <= 1 or len(candidates) <= 1:
            return candidates

        coverage, universe = cls._field_coverage_matrix(request, candidates)
        uncovered = set(universe)
        if not uncovered:
            return candidates

        remaining = list(range(len(candidates)))
        ordered: list[_Candidate] = []
        while remaining:
            best_index = min(
                remaining,
                key=lambda index: (
                    -len(coverage[index] & uncovered),
                    -candidates[index].score,
                    index,
                ),
            )
            remaining.remove(best_index)
            ordered.append(candidates[best_index])
            uncovered.difference_update(coverage[best_index])

        return ordered

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

    @classmethod
    def _field_evidence_request_active(
        cls,
        requested: dict[str, EvidenceRequirements],
    ) -> bool:
        return any(
            cls._evidence_request_active(requirement)
            for requirement in requested.values()
        )

    @staticmethod
    def _matched_field_evidence(
        candidate: _Candidate,
        selected_fields: list[str],
        requested: dict[str, EvidenceRequirements],
    ) -> dict[str, tuple[str, EvidenceRequirements]]:
        """Map trusted semantic evidence requirements onto selected local fields."""

        requested_by_semantic = {
            _normalize(semantic_id): (semantic_id, requirement)
            for semantic_id, requirement in requested.items()
        }
        field_map = {
            field.name: field
            for field in candidate.endpoint.output_fields
        }
        matched: dict[str, tuple[str, EvidenceRequirements]] = {}
        for field_name in selected_fields:
            field = field_map.get(field_name)
            if field is None or field.identifier:
                continue
            semantic = _normalize(field.semantic_id or field.name)
            item = requested_by_semantic.get(semantic)
            if item is not None:
                matched[field_name] = item
        return matched

    @staticmethod
    def _local_evidence_status(
        candidate: _Candidate,
        selected_fields: list[str],
        requested: EvidenceRequirements,
    ) -> tuple[bool, dict[str, object], list[str]]:
        locally_sufficient, available, missing = global_evidence_status(
            candidate.tool,
            candidate.endpoint,
            selected_fields,
            requested,
        )
        requested_source_type = requested.source_type
        context: dict[str, object] = {
            "surface": "evidence_sufficiency",
            "tool": candidate.tool.key,
            "endpoint": candidate.endpoint.name,
            "selected_fields": list(selected_fields),
            "requested": requested.model_dump(mode="json"),
            "available": {
                "provenance": available.provenance,
                "license": available.license,
                "units": available.units,
                "source_type": (
                    requested_source_type is None
                    or not any(
                        item.startswith("source_type=")
                        for item in missing
                    )
                ),
            },
        }
        return locally_sufficient, context, missing

    @classmethod
    def _local_field_evidence_status(
        cls,
        candidate: _Candidate,
        selected_fields: list[str],
        requested: dict[str, EvidenceRequirements],
    ) -> tuple[
        bool,
        dict[str, object],
        list[str],
        dict[str, tuple[str, EvidenceRequirements]],
    ]:
        matched = cls._matched_field_evidence(
            candidate,
            selected_fields,
            requested,
        )
        if not matched:
            return True, {}, [], {}

        local_required = {
            field_name: requirement
            for field_name, (_, requirement) in matched.items()
        }
        locally_sufficient, local_available, local_missing = field_evidence_status(
            candidate.tool,
            candidate.endpoint,
            selected_fields,
            local_required,
        )
        semantic_by_field = {
            field_name: semantic_id
            for field_name, (semantic_id, _) in matched.items()
        }

        missing: list[str] = []
        for item in local_missing:
            field_name, separator, suffix = item.partition(".")
            semantic_id = semantic_by_field.get(field_name, field_name)
            missing.append(
                semantic_id + (separator + suffix if separator else "")
            )

        requested_context = {
            semantic_id: requirement.model_dump(mode="json")
            for _, (semantic_id, requirement) in matched.items()
        }
        available_context = {
            semantic_by_field.get(field_name, field_name): {
                "field": field_name,
                **availability,
            }
            for field_name, availability in local_available.items()
        }
        return (
            locally_sufficient,
            {
                "field_requested": requested_context,
                "field_available": available_context,
            },
            missing,
            matched,
        )

    @classmethod
    def _combined_local_evidence_status(
        cls,
        candidate: _Candidate,
        selected_fields: list[str],
        requested: EvidenceRequirements,
        field_requested: dict[str, EvidenceRequirements],
    ) -> tuple[
        bool,
        dict[str, object],
        list[str],
        dict[str, tuple[str, EvidenceRequirements]],
    ]:
        global_ok, context, global_missing = cls._local_evidence_status(
            candidate,
            selected_fields,
            requested,
        )
        field_ok, field_context, field_missing, matched = (
            cls._local_field_evidence_status(
                candidate,
                selected_fields,
                field_requested,
            )
        )
        context.update(field_context)
        return (
            global_ok and field_ok,
            context,
            [*global_missing, *field_missing],
            matched,
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

    @staticmethod
    def _field_semantics(
        endpoint: EndpointSpec,
        field_names: list[str] | tuple[str, ...],
    ) -> tuple[_FieldSemantic, ...]:
        by_name = {field.name: field for field in endpoint.output_fields}
        semantics: list[_FieldSemantic] = []
        for name in field_names:
            field = by_name.get(name)
            if field is None or field.identifier:
                continue
            values = {
                _normalize(value)
                for value in [
                    field.name,
                    field.semantic_id or "",
                    *field.aliases,
                ]
                if value and _normalize(value)
            }
            if not values:
                continue
            unit_normalization = field.unit_normalization
            semantics.append(
                _FieldSemantic(
                    names=frozenset(values),
                    semantic_id=(
                        _normalize(field.semantic_id)
                        if field.semantic_id
                        else None
                    ),
                    json_schema=canonical_field_value_schema(endpoint, field.name),
                    qualifiers=tuple(sorted(field.qualifiers.items())),
                    unit=field.unit.strip() if field.unit else None,
                    unit_dimension=(
                        _normalize(unit_normalization.dimension)
                        if unit_normalization is not None
                        else None
                    ),
                    canonical_unit=(
                        unit_normalization.canonical_unit
                        if unit_normalization is not None
                        else None
                    ),
                    unit_scale=(
                        unit_normalization.scale
                        if unit_normalization is not None
                        else None
                    ),
                    unit_offset=(
                        unit_normalization.offset
                        if unit_normalization is not None
                        else None
                    ),
                )
            )
        return tuple(semantics)

    @classmethod
    def _corroboration_semantics_compatible(
        cls,
        selected_candidate: _Candidate,
        selected_call: ToolCall,
        candidate: _Candidate,
        candidate_call: ToolCall,
    ) -> bool:
        """Require at least one genuinely comparable answer field across providers."""

        selected = cls._field_semantics(
            selected_candidate.endpoint,
            tuple(selected_call.fields),
        )
        available = cls._field_semantics(
            candidate.endpoint,
            tuple(candidate_call.fields),
        )
        for left in selected:
            for right in available:
                if left.semantic_id is not None and right.semantic_id is not None:
                    if left.semantic_id != right.semantic_id:
                        continue
                elif left.names.isdisjoint(right.names):
                    continue
                if left.qualifiers != right.qualifiers:
                    continue
                if not json_schemas_compatible(left.json_schema, right.json_schema):
                    continue
                if (left.unit is None) != (right.unit is None):
                    continue
                if left.unit is not None:
                    if left.unit_dimension or right.unit_dimension:
                        if not left.unit_dimension or left.unit_dimension != right.unit_dimension:
                            continue
                        if not left.canonical_unit or left.canonical_unit != right.canonical_unit:
                            continue
                    elif left.unit != right.unit:
                        continue
                return True
        return False

    @classmethod
    def _fallback_semantics_compatible(
        cls,
        primary_candidate: _Candidate,
        primary_call: ToolCall,
        alternative_candidate: _Candidate,
        alternative_call: ToolCall,
    ) -> bool:
        required = cls._field_semantics(
            primary_candidate.endpoint,
            tuple(primary_call.fields),
        )
        if not required:
            return alternative_candidate.score > 0

        available = cls._field_semantics(
            alternative_candidate.endpoint,
            alternative_call.fields,
        )
        if not available:
            return False

        for requirement in required:
            matched = False
            for candidate_field in available:
                if requirement.semantic_id is not None:
                    names_match = (
                        candidate_field.semantic_id == requirement.semantic_id
                    )
                else:
                    names_match = not requirement.names.isdisjoint(
                        candidate_field.names
                    )
                if not names_match:
                    continue

                requirement_types = json_schema_types(requirement.json_schema)
                candidate_types = json_schema_types(candidate_field.json_schema)
                if bool(requirement_types) != bool(candidate_types):
                    continue
                if (
                    (requirement.unit is not None or candidate_field.unit is not None)
                    and (not requirement_types or not candidate_types)
                ):
                    # Unit-bearing cross-provider fallback must carry an explicit datatype
                    # contract on both sides.
                    continue
                if not json_schemas_compatible(
                    requirement.json_schema,
                    candidate_field.json_schema,
                ):
                    continue
                if requirement.qualifiers != candidate_field.qualifiers:
                    continue

                if (requirement.unit is None) != (candidate_field.unit is None):
                    continue
                if requirement.unit is not None:
                    if (
                        requirement.unit_dimension is not None
                        or candidate_field.unit_dimension is not None
                    ):
                        if (
                            requirement.unit_dimension is None
                            or candidate_field.unit_dimension is None
                            or requirement.canonical_unit is None
                            or candidate_field.canonical_unit is None
                            or requirement.unit_dimension
                            != candidate_field.unit_dimension
                            or requirement.canonical_unit
                            != candidate_field.canonical_unit
                        ):
                            continue
                        if (
                            requirement.unit == candidate_field.unit
                            and (
                                requirement.unit_scale != candidate_field.unit_scale
                                or requirement.unit_offset != candidate_field.unit_offset
                            )
                        ):
                            # Identical source-unit labels cannot legitimately use different
                            # affine transforms to the same canonical unit.
                            continue
                    elif candidate_field.unit != requirement.unit:
                        continue
                matched = True
                break

            if not matched:
                return False
        return True

    @staticmethod
    def _ordered_fallback_candidates(
        primary: _Candidate,
        candidates: list[_Candidate],
        *,
        scope: str,
    ) -> list[_Candidate]:
        if scope == "disabled":
            return []

        distinct = [
            candidate
            for candidate in candidates
            if (
                candidate.tool.key,
                candidate.endpoint.name,
            )
            != (
                primary.tool.key,
                primary.endpoint.name,
            )
        ]
        provider = primary.tool.provider
        if provider is None:
            return []

        same_provider = [
            candidate
            for candidate in distinct
            if candidate.tool.provider == provider
        ]
        if scope == "same_provider":
            return same_provider

        other_provider = [
            candidate
            for candidate in distinct
            if (
                candidate.tool.provider is not None
                and candidate.tool.provider != provider
            )
        ]
        return [*same_provider, *other_provider]

    @staticmethod
    def _bind_arguments(
        endpoint: EndpointSpec,
        provided: dict[str, Any],
    ) -> tuple[dict[str, Any], dict[str, str], list[str], list[str]]:
        """Bind exact parameter names first, then unambiguous trusted aliases.

        Alias routing only renames keys. Values are copied unchanged. If one supplied alias could
        target multiple parameters, or multiple supplied aliases compete for one parameter, the
        ambiguous inputs are left unbound and reported as ignored.
        """

        parameters = {parameter.name: parameter for parameter in endpoint.parameters}
        arguments: dict[str, Any] = {
            name: value
            for name, value in provided.items()
            if name in parameters
        }
        source_by_parameter: dict[str, str] = {
            name: name
            for name in arguments
        }
        consumed = set(arguments)

        unmatched_inputs = [
            name
            for name in provided
            if name not in consumed
        ]
        source_targets: dict[str, list[str]] = {}
        target_sources: dict[str, list[str]] = {}

        for source_name in unmatched_inputs:
            targets = [
                parameter.name
                for parameter in endpoint.parameters
                if parameter.name not in arguments
                and source_name in parameter.aliases
            ]
            if not targets:
                continue
            source_targets[source_name] = targets
            for target in targets:
                target_sources.setdefault(target, []).append(source_name)

        for source_name, targets in source_targets.items():
            if len(targets) != 1:
                continue
            target = targets[0]
            if len(target_sources.get(target, ())) != 1:
                continue
            arguments[target] = provided[source_name]
            source_by_parameter[target] = source_name
            consumed.add(source_name)

        ignored = sorted(set(provided) - consumed)
        ambiguous = sorted(
            source_name
            for source_name, targets in source_targets.items()
            if len(targets) != 1
            or any(
                len(target_sources.get(target, ())) != 1
                for target in targets
            )
        )
        return arguments, source_by_parameter, ignored, ambiguous

    def _compile_candidate_sync(
        self,
        request: PlanRequest,
        intent: QueryIntent,
        candidate: _Candidate,
        warnings: list[str],
        *,
        warn_ignored_arguments: bool = True,
    ) -> ToolCall | None:
        endpoint = candidate.endpoint
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
            schema_fingerprint=endpoint.fingerprint,
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
        endpoint = candidate.endpoint
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
            schema_fingerprint=endpoint.fingerprint,
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

    def _build_plan(
        self,
        request: PlanRequest,
        intent: QueryIntent,
        *,
        async_decision: bool,
        additional_availability_predicate: Callable[
            [ToolSpec, EndpointSpec],
            bool,
        ]
        | None = None,
    ) -> ExecutionPlan:
        del async_decision
        graph_candidates, graph_warnings, graph_escalates = (
            self._graph_first_candidates(
                request,
                intent,
                additional_availability_predicate=additional_availability_predicate,
            )
        )
        if graph_escalates:
            semantic_graph_candidates, semantic_graph_warnings, semantic_graph_escalates = (
                self._graph_semantic_seed_candidates_sync(
                    request,
                    intent,
                    additional_availability_predicate=additional_availability_predicate,
                )
            )
            if semantic_graph_escalates:
                lexical_candidates = self._candidates(
                    request,
                    intent,
                    additional_availability_predicate=additional_availability_predicate,
                )
                all_candidates, recall_warnings = (
                    self._augment_candidates_with_semantic_recall_sync(
                        request,
                        intent,
                        lexical_candidates,
                        additional_availability_predicate=additional_availability_predicate,
                    )
                )
                fit_candidates, fit_warnings = self._apply_capability_fit_sync(
                    request,
                    all_candidates,
                )
                operation_candidates, operation_warnings = self._apply_operation_fit_sync(
                    request,
                    fit_candidates,
                )
            else:
                all_candidates = semantic_graph_candidates
                recall_warnings = []
                fit_warnings = []
                operation_candidates = semantic_graph_candidates
                operation_warnings = []
        else:
            semantic_graph_warnings = []
            all_candidates = graph_candidates
            recall_warnings = []
            fit_warnings = []
            operation_candidates = graph_candidates
            operation_warnings = []
        _, required_coverage = self._field_coverage_matrix(request, all_candidates)
        disambiguated_candidates, disambiguation_warnings = (
            self._disambiguate_endpoints_sync(
                request,
                operation_candidates,
            )
        )
        candidates, decision_warnings = self._select_candidates_sync(
            request,
            disambiguated_candidates,
        )
        candidates = self._order_candidates_for_field_coverage(request, candidates)

        warnings: list[str] = [
            *graph_warnings,
            *semantic_graph_warnings,
            *recall_warnings,
            *fit_warnings,
            *operation_warnings,
            *disambiguation_warnings,
            *decision_warnings,
        ]
        if not candidates:
            coverage = self._plan_coverage(
                required_coverage,
                set(),
                all_candidates,
            )
            coverage_warning = self._coverage_warning(coverage)
            return ExecutionPlan(
                query=request.query,
                registry_version=self.registry.version,
                calls=[],
                warnings=[
                    *warnings,
                    "no schema candidate matched the request",
                    *([coverage_warning] if coverage_warning else []),
                ],
                coverage=coverage,
            )

        primary_pairs: list[tuple[_Candidate, ToolCall]] = []
        if request.max_calls <= 1:
            for candidate in candidates:
                call = self._compile_candidate_sync(
                    request,
                    intent,
                    candidate,
                    warnings,
                )
                if call is not None:
                    primary_pairs.append((candidate, call))
                    break
        else:
            candidate_coverage, required_coverage = self._field_coverage_matrix(
                request,
                candidates,
            )
            uncovered_coverage = set(required_coverage)
            selected_providers: set[str] = set()
            for candidate, potential_coverage in zip(
                candidates,
                candidate_coverage,
                strict=True,
            ):
                if len(primary_pairs) >= request.max_calls:
                    break
                provider_key = candidate.tool.provider or candidate.tool.key
                if request.retrieval_mode == "corroborate":
                    if required_coverage and not (potential_coverage & required_coverage):
                        continue
                    if provider_key in selected_providers:
                        continue
                elif required_coverage and not (
                    potential_coverage & uncovered_coverage
                ):
                    continue
                call = self._compile_candidate_sync(
                    request,
                    intent,
                    candidate,
                    warnings,
                )
                if call is None:
                    continue
                if (
                    request.retrieval_mode == "corroborate"
                    and primary_pairs
                    and not any(
                        self._corroboration_semantics_compatible(
                            selected_candidate,
                            selected_call,
                            candidate,
                            call,
                        )
                        for selected_candidate, selected_call in primary_pairs
                    )
                ):
                    continue
                primary_pairs.append((candidate, call))
                selected_providers.add(provider_key)
                if required_coverage:
                    selected_coverage = self._coverage_requirements_for_candidate(
                        candidate,
                        request.query,
                        field_names=set(call.fields),
                    )
                    uncovered_coverage.difference_update(
                        selected_coverage & potential_coverage
                    )
                    if (
                        request.retrieval_mode == "coverage"
                        and not uncovered_coverage
                    ):
                        break

        calls = [call for _, call in primary_pairs]
        fallback_routes: list[FallbackRoute] = []
        if request.fallback_scope != "disabled" and request.max_fallbacks > 0:
            for index, (primary_candidate, primary_call) in enumerate(primary_pairs):
                if primary_candidate.endpoint.read_only is not True:
                    continue
                alternatives: list[ToolCall] = []
                for candidate in self._ordered_fallback_candidates(
                    primary_candidate,
                    all_candidates,
                    scope=request.fallback_scope,
                ):
                    if len(alternatives) >= request.max_fallbacks:
                        break
                    if candidate.endpoint.read_only is not True:
                        continue
                    alternative = self._compile_candidate_sync(
                        request,
                        intent,
                        candidate,
                        warnings,
                        warn_ignored_arguments=False,
                    )
                    if alternative is None or not alternative.executable:
                        continue
                    if not self._fallback_semantics_compatible(
                        primary_candidate,
                        primary_call,
                        candidate,
                        alternative,
                    ):
                        continue
                    alternatives.append(alternative)
                if alternatives:
                    fallback_routes.append(
                        FallbackRoute(
                            primary_call_index=index,
                            alternatives=alternatives,
                        )
                    )

        covered_coverage: set[tuple[str, tuple[str, ...]]] = set()
        for candidate, call in primary_pairs:
            covered_coverage.update(
                self._coverage_requirements_for_candidate(
                    candidate,
                    request.query,
                    field_names=set(call.fields),
                )
                & required_coverage
            )
        coverage = self._plan_coverage(
            required_coverage,
            covered_coverage,
            all_candidates,
        )
        coverage_warning = self._coverage_warning(coverage)
        if coverage_warning:
            warnings.append(coverage_warning)

        return ExecutionPlan(
            query=request.query,
            registry_version=self.registry.version,
            calls=calls,
            fallback_routes=fallback_routes,
            warnings=warnings,
            coverage=coverage,
        )

    async def _abuild_plan(
        self,
        request: PlanRequest,
        intent: QueryIntent,
        *,
        additional_availability_predicate: Callable[
            [ToolSpec, EndpointSpec],
            bool,
        ]
        | None = None,
    ) -> ExecutionPlan:
        graph_candidates, graph_warnings, graph_escalates = (
            self._graph_first_candidates(
                request,
                intent,
                additional_availability_predicate=additional_availability_predicate,
            )
        )
        if graph_escalates:
            semantic_graph_candidates, semantic_graph_warnings, semantic_graph_escalates = (
                await self._graph_semantic_seed_candidates_async(
                    request,
                    intent,
                    additional_availability_predicate=additional_availability_predicate,
                )
            )
            if semantic_graph_escalates:
                lexical_candidates = self._candidates(
                    request,
                    intent,
                    additional_availability_predicate=additional_availability_predicate,
                )
                all_candidates, recall_warnings = (
                    await self._augment_candidates_with_semantic_recall_async(
                        request,
                        intent,
                        lexical_candidates,
                        additional_availability_predicate=additional_availability_predicate,
                    )
                )
                fit_candidates, fit_warnings = await self._apply_capability_fit_async(
                    request,
                    all_candidates,
                )
                operation_candidates, operation_warnings = (
                    await self._apply_operation_fit_async(
                        request,
                        fit_candidates,
                    )
                )
            else:
                all_candidates = semantic_graph_candidates
                recall_warnings = []
                fit_warnings = []
                operation_candidates = semantic_graph_candidates
                operation_warnings = []
        else:
            semantic_graph_warnings = []
            all_candidates = graph_candidates
            recall_warnings = []
            fit_warnings = []
            operation_candidates = graph_candidates
            operation_warnings = []
        _, required_coverage = self._field_coverage_matrix(request, all_candidates)
        disambiguated_candidates, disambiguation_warnings = (
            await self._disambiguate_endpoints_async(
                request,
                operation_candidates,
            )
        )
        candidates, decision_warnings = await self._select_candidates_async(
            request,
            disambiguated_candidates,
        )
        candidates = self._order_candidates_for_field_coverage(request, candidates)
        warnings = [
            *graph_warnings,
            *semantic_graph_warnings,
            *recall_warnings,
            *fit_warnings,
            *operation_warnings,
            *disambiguation_warnings,
            *decision_warnings,
        ]
        if not candidates:
            coverage = self._plan_coverage(
                required_coverage,
                set(),
                all_candidates,
            )
            coverage_warning = self._coverage_warning(coverage)
            return ExecutionPlan(
                query=request.query,
                registry_version=self.registry.version,
                calls=[],
                warnings=[
                    *warnings,
                    "no schema candidate matched the request",
                    *([coverage_warning] if coverage_warning else []),
                ],
                coverage=coverage,
            )

        primary_pairs: list[tuple[_Candidate, ToolCall]] = []
        if request.max_calls <= 1:
            for candidate in candidates:
                call = await self._compile_candidate_async(
                    request,
                    intent,
                    candidate,
                    warnings,
                )
                if call is not None:
                    primary_pairs.append((candidate, call))
                    break
        else:
            candidate_coverage, required_coverage = self._field_coverage_matrix(
                request,
                candidates,
            )
            uncovered_coverage = set(required_coverage)
            selected_providers: set[str] = set()
            for candidate, potential_coverage in zip(
                candidates,
                candidate_coverage,
                strict=True,
            ):
                if len(primary_pairs) >= request.max_calls:
                    break
                provider_key = candidate.tool.provider or candidate.tool.key
                if request.retrieval_mode == "corroborate":
                    if required_coverage and not (potential_coverage & required_coverage):
                        continue
                    if provider_key in selected_providers:
                        continue
                elif required_coverage and not (
                    potential_coverage & uncovered_coverage
                ):
                    continue
                call = await self._compile_candidate_async(
                    request,
                    intent,
                    candidate,
                    warnings,
                )
                if call is None:
                    continue
                if (
                    request.retrieval_mode == "corroborate"
                    and primary_pairs
                    and not any(
                        self._corroboration_semantics_compatible(
                            selected_candidate,
                            selected_call,
                            candidate,
                            call,
                        )
                        for selected_candidate, selected_call in primary_pairs
                    )
                ):
                    continue
                primary_pairs.append((candidate, call))
                selected_providers.add(provider_key)
                if required_coverage:
                    selected_coverage = self._coverage_requirements_for_candidate(
                        candidate,
                        request.query,
                        field_names=set(call.fields),
                    )
                    uncovered_coverage.difference_update(
                        selected_coverage & potential_coverage
                    )
                    if (
                        request.retrieval_mode == "coverage"
                        and not uncovered_coverage
                    ):
                        break

        calls = [call for _, call in primary_pairs]
        fallback_routes: list[FallbackRoute] = []
        if request.fallback_scope != "disabled" and request.max_fallbacks > 0:
            for index, (primary_candidate, primary_call) in enumerate(primary_pairs):
                if primary_candidate.endpoint.read_only is not True:
                    continue
                alternatives: list[ToolCall] = []
                for candidate in self._ordered_fallback_candidates(
                    primary_candidate,
                    all_candidates,
                    scope=request.fallback_scope,
                ):
                    if len(alternatives) >= request.max_fallbacks:
                        break
                    if candidate.endpoint.read_only is not True:
                        continue
                    alternative = await self._compile_candidate_async(
                        request,
                        intent,
                        candidate,
                        warnings,
                        warn_ignored_arguments=False,
                    )
                    if alternative is None or not alternative.executable:
                        continue
                    if not self._fallback_semantics_compatible(
                        primary_candidate,
                        primary_call,
                        candidate,
                        alternative,
                    ):
                        continue
                    alternatives.append(alternative)
                if alternatives:
                    fallback_routes.append(
                        FallbackRoute(
                            primary_call_index=index,
                            alternatives=alternatives,
                        )
                    )

        covered_coverage: set[tuple[str, tuple[str, ...]]] = set()
        for candidate, call in primary_pairs:
            covered_coverage.update(
                self._coverage_requirements_for_candidate(
                    candidate,
                    request.query,
                    field_names=set(call.fields),
                )
                & required_coverage
            )
        coverage = self._plan_coverage(
            required_coverage,
            covered_coverage,
            all_candidates,
        )
        coverage_warning = self._coverage_warning(coverage)
        if coverage_warning:
            warnings.append(coverage_warning)

        return ExecutionPlan(
            query=request.query,
            registry_version=self.registry.version,
            calls=calls,
            fallback_routes=fallback_routes,
            warnings=warnings,
            coverage=coverage,
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
        field_map = {field.name: field for field in candidate.endpoint.output_fields}
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
        components: list[ScoreComponent] = []
        field_reasons: dict[str, FieldSelectionReason] = {}

        if tool.key in preferred_tools or tool.name in preferred_tools:
            score += 100.0
            components.append(
                ScoreComponent(kind="preferred_tool", value=100.0, matched=tool.key)
            )

        endpoint_key = f"{tool.key}.{endpoint.name}"
        if endpoint_key in preferred_endpoints:
            score += 250.0
            components.append(
                ScoreComponent(
                    kind="preferred_endpoint",
                    value=250.0,
                    matched=endpoint_key,
                )
            )

        tool_text = " ".join([tool.name, tool.description, endpoint.name, endpoint.description])
        for token in sorted(query_tokens & _tokens(tool_text)):
            score += 1.5
            components.append(
                ScoreComponent(kind="tool_token", value=1.5, matched=token)
            )

        matched_fields: list[str] = []
        for field in endpoint.output_fields:
            names = [
                field.name,
                field.semantic_id or "",
                *field.aliases,
                ".".join(field.projection_path),
            ]
            norms = {_normalize(name) for name in names if name}
            exact = bool(norms & concept_norms)
            lexical = any(query_tokens & _tokens(name) for name in names)
            substring = any(
                _semantic_substring_match(concept, norm)
                for concept in concept_norms
                for norm in norms
            )
            if exact:
                score += 6.0
                matched_fields.append(field.name)
                field_reasons[field.name] = "field_exact"
                components.append(
                    ScoreComponent(kind="field_exact", value=6.0, matched=field.name)
                )
            elif lexical:
                score += 3.0
                matched_fields.append(field.name)
                field_reasons[field.name] = "field_lexical"
                components.append(
                    ScoreComponent(kind="field_lexical", value=3.0, matched=field.name)
                )
            elif substring:
                score += 1.0
                matched_fields.append(field.name)
                field_reasons[field.name] = "field_substring"
                components.append(
                    ScoreComponent(kind="field_substring", value=1.0, matched=field.name)
                )

            if exact or lexical or substring:
                qualifier_matches = _matched_field_qualifiers(query, field)
                if qualifier_matches:
                    score += 4.0
                    components.append(
                        ScoreComponent(
                            kind="field_qualifier",
                            value=4.0,
                            matched=f"{field.name}:" + ",".join(qualifier_matches),
                        )
                    )

        _, argument_sources, _, _ = self._bind_arguments(
            endpoint,
            intent.arguments,
        )
        for parameter_name, source_name in argument_sources.items():
            score += 2.0
            components.append(
                ScoreComponent(
                    kind=(
                        "argument_match"
                        if source_name == parameter_name
                        else "argument_alias_match"
                    ),
                    value=2.0,
                    matched=(
                        parameter_name
                        if source_name == parameter_name
                        else f"{source_name}->{parameter_name}"
                    ),
                )
            )

        return _Candidate(
            tool=tool,
            endpoint=endpoint,
            score=score,
            matched_fields=tuple(dict.fromkeys(matched_fields)),
            score_components=tuple(components),
            field_reasons=tuple(field_reasons.items()),
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
    ) -> EvidenceRequirements:
        return available_evidence(tool, endpoint, selected_fields)
