from __future__ import annotations

import re
from collections import deque
from dataclasses import dataclass
from typing import Literal

from .models import ToolSpec
from .registry import ToolRegistry

GraphNodeKind = Literal[
    "tool",
    "endpoint",
    "operation",
    "parameter",
    "field",
    "concept",
    "unit",
    "qualifier",
    "source_type",
    "license",
    "health",
]
GraphEdgeKind = Literal[
    "HAS_ENDPOINT",
    "HAS_OPERATION",
    "ACCEPTS_PARAMETER",
    "RETURNS_FIELD",
    "MAPS_TO_CONCEPT",
    "HAS_UNIT",
    "HAS_QUALIFIER",
    "HAS_SOURCE_TYPE",
    "LICENSED_AS",
    "REQUIRES",
    "ALIASED_AS",
    "NORMALIZED_TO",
    "FALLBACK_TO",
    "CONFLICTS_WITH",
]
GraphOperationDecision = Literal["accept", "reject", "escalate"]

_TOKEN_RE = re.compile(r"[A-Za-z0-9_]+|[가-힣]+")
_SPACE_RE = re.compile(r"[^\w가-힣]+", re.UNICODE)


def _normalize_phrase(text: str) -> str:
    return " ".join(part for part in _SPACE_RE.sub(" ", text.casefold()).split() if part)


def _tokens(text: str) -> tuple[str, ...]:
    values: list[str] = []
    for raw in _TOKEN_RE.findall(text.casefold()):
        values.extend(part for part in raw.replace("_", " ").split() if part)
    return tuple(values)


def _contains_token_phrase(query: str, phrase: str) -> bool:
    query_tokens = _tokens(query)
    phrase_tokens = _tokens(phrase)
    if not query_tokens or not phrase_tokens or len(phrase_tokens) > len(query_tokens):
        return False
    width = len(phrase_tokens)
    return any(
        query_tokens[index : index + width] == phrase_tokens
        for index in range(len(query_tokens) - width + 1)
    )


def _metadata_strings(value: object) -> tuple[str, ...]:
    if not isinstance(value, (list, tuple)):
        return ()
    cleaned: list[str] = []
    for item in value:
        if isinstance(item, str) and item.strip():
            cleaned.append(item.strip())
    return tuple(dict.fromkeys(cleaned))


@dataclass(frozen=True, slots=True)
class SchemaGraphNode:
    id: str
    kind: GraphNodeKind
    label: str
    metadata: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True, slots=True)
class SchemaGraphEdge:
    source: str
    target: str
    kind: GraphEdgeKind


@dataclass(frozen=True, slots=True)
class GraphOperationEvidence:
    endpoint_name: str
    operation_aliases: tuple[str, ...] = ()
    field_concepts: tuple[str, ...] = ()
    graph_paths: tuple[tuple[str, ...], ...] = ()

    @property
    def has_operation_alias(self) -> bool:
        return bool(self.operation_aliases)

    @property
    def has_field_concept(self) -> bool:
        return bool(self.field_concepts)


@dataclass(frozen=True, slots=True)
class GraphOperationAssessment:
    decision: GraphOperationDecision
    tool_key: str
    endpoint_name: str | None = None
    reason: str = ""
    evidence: tuple[GraphOperationEvidence, ...] = ()


class CompiledSchemaGraph:
    """Typed graph compiled exclusively from the locally registered schema.

    The graph is the authority surface. Semantic systems may attach evidence to
    existing nodes later, but they cannot create graph structure or execution authority.
    """

    def __init__(
        self,
        *,
        version: int,
        nodes: dict[str, SchemaGraphNode],
        edges: tuple[SchemaGraphEdge, ...],
        operation_aliases: dict[tuple[str, str], tuple[str, ...]],
        field_concepts: dict[tuple[str, str], tuple[str, ...]],
        unsupported_aliases: dict[str, tuple[str, ...]],
    ) -> None:
        self.version = version
        self._nodes = dict(nodes)
        self._edges = tuple(edges)
        grouped: dict[str, list[SchemaGraphEdge]] = {}
        for edge in edges:
            grouped.setdefault(edge.source, []).append(edge)
        self._outgoing = {
            source: tuple(items)
            for source, items in grouped.items()
        }
        self._operation_aliases = dict(operation_aliases)
        self._field_concepts = dict(field_concepts)
        self._unsupported_aliases = dict(unsupported_aliases)

    @classmethod
    def compile(
        cls,
        *,
        version: int,
        tools: tuple[ToolSpec, ...],
    ) -> CompiledSchemaGraph:
        nodes: dict[str, SchemaGraphNode] = {}
        edges: list[SchemaGraphEdge] = []
        operation_aliases: dict[tuple[str, str], tuple[str, ...]] = {}
        field_concepts: dict[tuple[str, str], tuple[str, ...]] = {}
        unsupported_aliases: dict[str, tuple[str, ...]] = {}

        def add_node(
            node_id: str,
            kind: GraphNodeKind,
            label: str,
            metadata: tuple[tuple[str, str], ...] = (),
        ) -> str:
            existing = nodes.get(node_id)
            if existing is None:
                nodes[node_id] = SchemaGraphNode(node_id, kind, label, metadata)
            elif existing.kind != kind:
                raise ValueError(f"schema graph node kind collision: {node_id}")
            return node_id

        def add_edge(source: str, target: str, kind: GraphEdgeKind) -> None:
            edges.append(SchemaGraphEdge(source, target, kind))

        def shared_id(kind: GraphNodeKind, label: str) -> str:
            normalized = _normalize_phrase(label).replace(" ", "_")
            return f"{kind}:{normalized}"

        for tool in tools:
            tool_id = add_node(f"tool:{tool.key}", "tool", tool.key)
            tool_unsupported = _metadata_strings(
                tool.metadata.get("unsupported_operation_aliases")
            )
            unsupported_aliases[tool.key] = tool_unsupported
            for alias in tool_unsupported:
                conflict_id = add_node(
                    f"concept:unsupported:{tool.key}:{_normalize_phrase(alias)}",
                    "concept",
                    alias,
                    (("role", "unsupported_operation"),),
                )
                add_edge(tool_id, conflict_id, "CONFLICTS_WITH")

            if tool.source_type:
                source_id = add_node(
                    shared_id("source_type", tool.source_type),
                    "source_type",
                    tool.source_type,
                )
                add_edge(tool_id, source_id, "HAS_SOURCE_TYPE")
            if tool.license:
                license_id = add_node(
                    shared_id("license", tool.license),
                    "license",
                    tool.license,
                )
                add_edge(tool_id, license_id, "LICENSED_AS")

            for endpoint in tool.endpoints:
                endpoint_key = f"{tool.key}.{endpoint.name}"
                endpoint_id = add_node(
                    f"endpoint:{endpoint_key}",
                    "endpoint",
                    endpoint_key,
                    (
                        ("read_only", str(endpoint.read_only)),
                        ("destructive", str(endpoint.destructive)),
                    ),
                )
                operation_id = add_node(
                    f"operation:{endpoint_key}",
                    "operation",
                    endpoint.name,
                )
                add_edge(tool_id, endpoint_id, "HAS_ENDPOINT")
                add_edge(endpoint_id, operation_id, "HAS_OPERATION")

                aliases = tuple(
                    dict.fromkeys(
                        alias.strip()
                        for alias in endpoint.operation_aliases
                        if alias.strip()
                    )
                )
                operation_aliases[(tool.key, endpoint.name)] = aliases

                for parameter in endpoint.parameters:
                    parameter_id = add_node(
                        f"parameter:{endpoint_key}:{parameter.name}",
                        "parameter",
                        parameter.name,
                    )
                    add_edge(endpoint_id, parameter_id, "ACCEPTS_PARAMETER")
                    if parameter.required:
                        add_edge(endpoint_id, parameter_id, "REQUIRES")

                concepts: list[str] = []
                for field in endpoint.output_fields:
                    field_id = add_node(
                        f"field:{endpoint_key}:{field.name}",
                        "field",
                        field.name,
                        (("identifier", str(field.identifier)),),
                    )
                    add_edge(endpoint_id, field_id, "RETURNS_FIELD")

                    canonical = (field.semantic_id or field.name).strip()
                    if canonical and not field.identifier:
                        concepts.append(canonical)
                        concept_id = add_node(
                            shared_id("concept", canonical),
                            "concept",
                            canonical,
                        )
                        add_edge(field_id, concept_id, "MAPS_TO_CONCEPT")

                        for alias in field.aliases:
                            if not alias.strip():
                                continue
                            alias_id = add_node(
                                shared_id("concept", alias),
                                "concept",
                                alias,
                            )
                            add_edge(alias_id, concept_id, "NORMALIZED_TO")
                            add_edge(concept_id, alias_id, "ALIASED_AS")
                            concepts.append(alias)

                    if field.unit:
                        unit_id = add_node(
                            shared_id("unit", field.unit),
                            "unit",
                            field.unit,
                        )
                        add_edge(field_id, unit_id, "HAS_UNIT")
                    for key, value in sorted(field.qualifiers.items()):
                        qualifier_label = f"{key}={value}"
                        qualifier_id = add_node(
                            shared_id("qualifier", qualifier_label),
                            "qualifier",
                            qualifier_label,
                        )
                        add_edge(field_id, qualifier_id, "HAS_QUALIFIER")
                    if field.source_type:
                        source_id = add_node(
                            shared_id("source_type", field.source_type),
                            "source_type",
                            field.source_type,
                        )
                        add_edge(field_id, source_id, "HAS_SOURCE_TYPE")
                    if field.license:
                        license_id = add_node(
                            shared_id("license", field.license),
                            "license",
                            field.license,
                        )
                        add_edge(field_id, license_id, "LICENSED_AS")

                field_concepts[(tool.key, endpoint.name)] = tuple(
                    dict.fromkeys(concepts)
                )

        return cls(
            version=version,
            nodes=nodes,
            edges=tuple(dict.fromkeys(edges)),
            operation_aliases=operation_aliases,
            field_concepts=field_concepts,
            unsupported_aliases=unsupported_aliases,
        )

    @classmethod
    def from_registry(cls, registry: ToolRegistry) -> CompiledSchemaGraph:
        for _ in range(4):
            before = registry.version
            tools = registry.tools()
            after = registry.version
            if before == after:
                return cls.compile(version=after, tools=tools)
        raise RuntimeError("registry changed repeatedly while compiling schema graph")

    def nodes(self, *, kind: GraphNodeKind | None = None) -> tuple[SchemaGraphNode, ...]:
        values = tuple(self._nodes.values())
        if kind is None:
            return values
        return tuple(node for node in values if node.kind == kind)

    def edges(
        self,
        *,
        source: str | None = None,
        kind: GraphEdgeKind | None = None,
    ) -> tuple[SchemaGraphEdge, ...]:
        values = self._edges if source is None else self._outgoing.get(source, ())
        if kind is None:
            return tuple(values)
        return tuple(edge for edge in values if edge.kind == kind)

    def has_path(
        self,
        source: str,
        target: str,
        *,
        edge_kinds: frozenset[GraphEdgeKind] | None = None,
        max_depth: int = 4,
    ) -> bool:
        if max_depth < 0:
            raise ValueError("max_depth must be >= 0")
        if source == target:
            return source in self._nodes
        if source not in self._nodes or target not in self._nodes:
            return False

        queue: deque[tuple[str, int]] = deque([(source, 0)])
        seen = {source}
        while queue:
            node_id, depth = queue.popleft()
            if depth >= max_depth:
                continue
            for edge in self._outgoing.get(node_id, ()):
                if edge_kinds is not None and edge.kind not in edge_kinds:
                    continue
                if edge.target == target:
                    return True
                if edge.target in seen:
                    continue
                seen.add(edge.target)
                queue.append((edge.target, depth + 1))
        return False

    def operation_aliases(
        self,
        tool_key: str,
        endpoint_name: str,
    ) -> tuple[str, ...]:
        return self._operation_aliases.get((tool_key, endpoint_name), ())

    def field_concepts(
        self,
        tool_key: str,
        endpoint_name: str,
    ) -> tuple[str, ...]:
        return self._field_concepts.get((tool_key, endpoint_name), ())

    def unsupported_operation_aliases(self, tool_key: str) -> tuple[str, ...]:
        return self._unsupported_aliases.get(tool_key, ())


class GraphOperationGate:
    """Conservative graph-first gate for sibling operation routing.

    Trusted graph structure may resolve a unique deterministic operation. Any
    ambiguity escalates to the configured semantic/reranker backend. The default
    mode accepts only registered operation aliases. Field-concept routing is opt-in.
    """

    def __init__(
        self,
        *,
        accept_unique_field_path: bool = False,
        reject_explicit_conflicts: bool = True,
    ) -> None:
        self.accept_unique_field_path = accept_unique_field_path
        self.reject_explicit_conflicts = reject_explicit_conflicts

    def assess(
        self,
        *,
        query: str,
        graph: CompiledSchemaGraph,
        tool_key: str,
        endpoint_names: tuple[str, ...],
    ) -> GraphOperationAssessment:
        endpoints = tuple(dict.fromkeys(endpoint_names))
        if not query.strip() or not endpoints:
            return GraphOperationAssessment(
                decision="escalate",
                tool_key=tool_key,
                reason="empty query or operation candidate set",
            )

        if self.reject_explicit_conflicts:
            conflicts = tuple(
                alias
                for alias in graph.unsupported_operation_aliases(tool_key)
                if _contains_token_phrase(query, alias)
            )
            if conflicts:
                return GraphOperationAssessment(
                    decision="reject",
                    tool_key=tool_key,
                    reason="query matched an explicitly unsupported graph operation",
                    evidence=(
                        GraphOperationEvidence(
                            endpoint_name="",
                            operation_aliases=conflicts,
                            graph_paths=((f"tool:{tool_key}", "CONFLICTS_WITH"),),
                        ),
                    ),
                )

        evidence: list[GraphOperationEvidence] = []
        alias_winners: list[str] = []
        field_winners: list[str] = []

        for endpoint_name in endpoints:
            endpoint_id = f"endpoint:{tool_key}.{endpoint_name}"
            operation_id = f"operation:{tool_key}.{endpoint_name}"
            if not graph.has_path(
                f"tool:{tool_key}",
                operation_id,
                edge_kinds=frozenset({"HAS_ENDPOINT", "HAS_OPERATION"}),
                max_depth=2,
            ):
                continue

            matched_aliases = tuple(
                alias
                for alias in graph.operation_aliases(tool_key, endpoint_name)
                if _contains_token_phrase(query, alias)
            )
            if matched_aliases:
                alias_winners.append(endpoint_name)

            matched_fields: tuple[str, ...] = ()
            if self.accept_unique_field_path:
                matched_fields = tuple(
                    concept
                    for concept in graph.field_concepts(tool_key, endpoint_name)
                    if _contains_token_phrase(query, concept)
                )
                if matched_fields:
                    field_winners.append(endpoint_name)

            if matched_aliases or matched_fields:
                paths: list[tuple[str, ...]] = []
                if matched_aliases:
                    paths.append(
                        (
                            f"tool:{tool_key}",
                            endpoint_id,
                            operation_id,
                        )
                    )
                if matched_fields:
                    paths.append(
                        (
                            f"tool:{tool_key}",
                            endpoint_id,
                            "RETURNS_FIELD",
                            "MAPS_TO_CONCEPT",
                        )
                    )
                evidence.append(
                    GraphOperationEvidence(
                        endpoint_name=endpoint_name,
                        operation_aliases=matched_aliases,
                        field_concepts=matched_fields,
                        graph_paths=tuple(paths),
                    )
                )

        unique_alias_winners = tuple(dict.fromkeys(alias_winners))
        if len(unique_alias_winners) == 1:
            return GraphOperationAssessment(
                decision="accept",
                tool_key=tool_key,
                endpoint_name=unique_alias_winners[0],
                reason="unique registered operation alias path matched",
                evidence=tuple(evidence),
            )
        if len(unique_alias_winners) > 1:
            return GraphOperationAssessment(
                decision="escalate",
                tool_key=tool_key,
                reason="multiple registered operation alias paths matched",
                evidence=tuple(evidence),
            )

        unique_field_winners = tuple(dict.fromkeys(field_winners))
        if self.accept_unique_field_path and len(unique_field_winners) == 1:
            return GraphOperationAssessment(
                decision="accept",
                tool_key=tool_key,
                endpoint_name=unique_field_winners[0],
                reason="unique registered field-concept path matched",
                evidence=tuple(evidence),
            )
        if self.accept_unique_field_path and len(unique_field_winners) > 1:
            return GraphOperationAssessment(
                decision="escalate",
                tool_key=tool_key,
                reason="multiple field-concept paths matched",
                evidence=tuple(evidence),
            )

        return GraphOperationAssessment(
            decision="escalate",
            tool_key=tool_key,
            reason="graph evidence was insufficient for a deterministic operation decision",
            evidence=tuple(evidence),
        )
