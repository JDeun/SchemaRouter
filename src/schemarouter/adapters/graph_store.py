from __future__ import annotations

import asyncio
import inspect
import re
from collections.abc import Awaitable, Iterable, Mapping
from dataclasses import dataclass
from typing import Any, Literal, Protocol, cast

from pydantic import Field, model_validator

from ..authorization import _current_data_scope
from ..errors import PolicyViolationError, RegistrationError, SchemaValidationError
from ..models import EndpointSpec, FieldSpec, ParameterSpec, StrictModel, ToolCall, ToolSpec
from .discovery_limits import (
    NativeDiscoveryBudget,
    NativeDiscoveryLimits,
    bounded_collect,
    bounded_select,
    descriptor_name,
    require_at_most,
)

_TRAVERSE_ENDPOINT = "traverse"
_MAX_HOPS = 5
_MAX_LIMIT = 500

GraphModel = Literal["property_graph", "rdf"]
GraphDirection = Literal["out", "in", "both"]


class GraphPropertySpec(StrictModel):
    """One model-visible node/edge/RDF property."""

    name: str
    description: str = ""
    json_schema: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_name(self) -> GraphPropertySpec:
        if not self.name.strip():
            raise ValueError("graph property name must be non-empty")
        return self


class GraphNodeTypeSpec(StrictModel):
    """One graph label/class/type discovered by a trusted adapter."""

    name: str
    description: str = ""
    properties: tuple[GraphPropertySpec, ...] = ()

    @model_validator(mode="after")
    def validate_node_type(self) -> GraphNodeTypeSpec:
        if not self.name.strip():
            raise ValueError("graph node type name must be non-empty")
        names = [value.name for value in self.properties]
        if len(names) != len(set(names)):
            raise ValueError("graph node property names must be unique")
        return self


class GraphRelationshipTypeSpec(StrictModel):
    """One directed edge type or RDF predicate."""

    name: str
    description: str = ""
    source_types: tuple[str, ...] = ()
    target_types: tuple[str, ...] = ()
    properties: tuple[GraphPropertySpec, ...] = ()

    @model_validator(mode="after")
    def validate_relationship(self) -> GraphRelationshipTypeSpec:
        if not self.name.strip():
            raise ValueError("graph relationship type name must be non-empty")
        names = [value.name for value in self.properties]
        if len(names) != len(set(names)):
            raise ValueError("graph relationship property names must be unique")
        return self


class GraphSourceSpec(StrictModel):
    """Provider-neutral property-graph or RDF schema descriptor."""

    name: str
    model: GraphModel = "property_graph"
    description: str = ""
    node_types: tuple[GraphNodeTypeSpec, ...] = ()
    relationship_types: tuple[GraphRelationshipTypeSpec, ...] = ()
    public_metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_graph(self) -> GraphSourceSpec:
        if not self.name.strip():
            raise ValueError("graph source name must be non-empty")
        node_names = [value.name for value in self.node_types]
        relationship_names = [value.name for value in self.relationship_types]
        if len(node_names) != len(set(node_names)):
            raise ValueError("graph node type names must be unique")
        if len(relationship_names) != len(set(relationship_names)):
            raise ValueError("graph relationship type names must be unique")
        known_nodes = set(node_names)
        for relationship in self.relationship_types:
            unknown = sorted(
                (set(relationship.source_types) | set(relationship.target_types))
                - known_nodes
            )
            if unknown:
                raise ValueError(
                    "graph relationship references unknown node types: "
                    + ", ".join(unknown)
                )
        return self


class GraphStoreBackend(Protocol):
    """Base graph traversal backend contract."""

    def list_graphs(
        self,
    ) -> Iterable[GraphSourceSpec] | Awaitable[Iterable[GraphSourceSpec]]: ...

    def traverse(
        self,
        *,
        graph: str,
        start_id: str,
        relationship_types: tuple[str, ...],
        direction: GraphDirection,
        max_hops: int,
        limit: int,
        include_fields: tuple[str, ...],
    ) -> list[dict[str, Any]] | Awaitable[list[dict[str, Any]]]: ...


class ScopedGraphStoreBackend(GraphStoreBackend, Protocol):
    """Graph backend that explicitly enforces trusted hidden predicates."""

    supports_trusted_filters: bool

    def traverse(
        self,
        *,
        graph: str,
        start_id: str,
        relationship_types: tuple[str, ...],
        direction: GraphDirection,
        max_hops: int,
        limit: int,
        include_fields: tuple[str, ...],
        trusted_filters: Mapping[str, Any] | None = None,
    ) -> list[dict[str, Any]] | Awaitable[list[dict[str, Any]]]: ...


def _slug(value: str) -> str:
    normalized = re.sub(r"[^A-Za-z0-9_]+", "_", value.strip()).strip("_").lower()
    return normalized or "graph"


async def _await_if_needed(value: Any) -> Any:
    return await value if inspect.isawaitable(value) else value


async def _call_backend(
    function: Any,
    /,
    *args: Any,
    offload_sync: bool,
    **kwargs: Any,
) -> Any:
    if offload_sync and not inspect.iscoroutinefunction(function):
        value = await asyncio.to_thread(function, *args, **kwargs)
    else:
        value = function(*args, **kwargs)
    return await _await_if_needed(value)


@dataclass(frozen=True)
class GraphSourceBinding:
    """One introspected graph plus its trusted bounded traversal invoker."""

    tool: ToolSpec
    invoker: GraphSourceInvoker


class GraphSourceInvoker:
    projects_fields = True
    supports_trusted_filters = True

    def __init__(
        self,
        backend: GraphStoreBackend,
        *,
        graph: GraphSourceSpec,
        default_limit: int,
        default_max_hops: int,
        offload_sync_backend: bool,
    ) -> None:
        self._backend = backend
        self._graph = graph
        self._default_limit = default_limit
        self._default_max_hops = default_max_hops
        self._offload_sync_backend = offload_sync_backend
        self._relationship_types = {
            relationship.name for relationship in graph.relationship_types
        }

    async def invoke_call(self, call: ToolCall) -> list[dict[str, Any]]:
        if call.endpoint != _TRAVERSE_ENDPOINT:
            raise RuntimeError(f"unknown graph endpoint: {call.endpoint!r}")

        start_id = call.arguments.get("start_id")
        if not isinstance(start_id, str) or not start_id.strip():
            raise RuntimeError("graph traversal requires a non-empty start_id")

        scope = _current_data_scope()
        allowed_relationships = (
            self._relationship_types
            if scope is None or scope.allowed_relationships is None
            else self._relationship_types.intersection(scope.allowed_relationships)
        )

        raw_relationships = call.arguments.get("relationship_types")
        if raw_relationships is None:
            relationship_types = tuple(sorted(allowed_relationships))
        elif isinstance(raw_relationships, list) and all(
            isinstance(value, str) for value in raw_relationships
        ):
            relationship_types = tuple(raw_relationships)
        else:
            raise RuntimeError("relationship_types must be a list of strings")

        unknown_relationships = sorted(
            set(relationship_types) - self._relationship_types
        )
        if unknown_relationships:
            raise RuntimeError(
                "graph traversal requested unknown relationship types: "
                + ", ".join(unknown_relationships)
            )
        if not set(relationship_types).issubset(allowed_relationships):
            raise PolicyViolationError(
                "authorization denied for requested data scope"
            )

        direction = call.arguments.get("direction", "out")
        if direction not in {"out", "in", "both"}:
            raise RuntimeError("graph direction must be out, in, or both")

        scoped_default_hops = self._default_max_hops
        if scope is not None and scope.max_hops is not None:
            scoped_default_hops = min(scoped_default_hops, scope.max_hops)
        max_hops = int(call.arguments.get("max_hops", scoped_default_hops))
        if max_hops < 1 or max_hops > _MAX_HOPS:
            raise RuntimeError(f"graph max_hops must be between 1 and {_MAX_HOPS}")
        if scope is not None and scope.max_hops is not None and max_hops > scope.max_hops:
            raise PolicyViolationError(
                "authorization denied for requested data scope"
            )

        limit = int(call.arguments.get("limit", self._default_limit))
        if limit < 1 or limit > _MAX_LIMIT:
            raise RuntimeError(f"graph limit must be between 1 and {_MAX_LIMIT}")

        traverse = self._backend.traverse
        traverse_kwargs: dict[str, Any] = {
            "graph": self._graph.name,
            "start_id": start_id,
            "relationship_types": relationship_types,
            "direction": direction,
            "max_hops": max_hops,
            "limit": limit,
            "include_fields": tuple(call.fields),
        }
        if scope is not None and scope.trusted_filters:
            if getattr(self._backend, "supports_trusted_filters", False) is not True:
                raise PolicyViolationError(
                    "authorization denied for requested data scope"
                )
            scoped_backend = cast(ScopedGraphStoreBackend, self._backend)
            traverse = scoped_backend.traverse
            traverse_kwargs["trusted_filters"] = scope.filter_dict()

        raw_results = await _call_backend(
            traverse,
            offload_sync=self._offload_sync_backend,
            **traverse_kwargs,
        )
        if not isinstance(raw_results, list):
            raise SchemaValidationError("graph backend traversal must return a list")

        selected = set(call.fields)
        rows: list[dict[str, Any]] = []
        for index, raw in enumerate(raw_results):
            if not isinstance(raw, dict):
                raise SchemaValidationError(
                    f"graph backend result {index} must be an object"
                )
            rows.append({key: value for key, value in raw.items() if key in selected})
        return rows


def _bounded_graph_type_descriptor(
    value: Any,
    *,
    limits: NativeDiscoveryLimits,
    label: str,
) -> Any:
    if not isinstance(value, Mapping):
        return value
    raw = dict(value)
    properties = raw.get("properties")
    if (
        isinstance(properties, Iterable)
        and not isinstance(properties, (str, bytes, Mapping))
    ):
        raw["properties"] = bounded_collect(
            properties,
            limit=limits.max_properties_per_type,
            label=f"{label} property count",
        )
    for endpoint_key in ("source_types", "target_types"):
        endpoint_values = raw.get(endpoint_key)
        if (
            isinstance(endpoint_values, Iterable)
            and not isinstance(endpoint_values, (str, bytes, Mapping))
        ):
            raw[endpoint_key] = bounded_collect(
                endpoint_values,
                limit=limits.max_node_types_per_source,
                label=f"{label} {endpoint_key} count",
            )
    return raw


def _bounded_graph_descriptor(
    value: Any,
    limits: NativeDiscoveryLimits,
) -> Any:
    if not isinstance(value, Mapping):
        return value
    raw = dict(value)
    name = descriptor_name(raw)

    node_types = raw.get("node_types")
    if (
        isinstance(node_types, Iterable)
        and not isinstance(node_types, (str, bytes, Mapping))
    ):
        bounded_nodes = bounded_collect(
            node_types,
            limit=limits.max_node_types_per_source,
            label=f"graph {name!r} node type count",
        )
        raw["node_types"] = tuple(
            _bounded_graph_type_descriptor(
                item,
                limits=limits,
                label=f"graph {name!r} node type",
            )
            for item in bounded_nodes
        )

    relationship_types = raw.get("relationship_types")
    if (
        isinstance(relationship_types, Iterable)
        and not isinstance(relationship_types, (str, bytes, Mapping))
    ):
        bounded_relationships = bounded_collect(
            relationship_types,
            limit=limits.max_relationship_types_per_source,
            label=f"graph {name!r} relationship type count",
        )
        raw["relationship_types"] = tuple(
            _bounded_graph_type_descriptor(
                item,
                limits=limits,
                label=f"graph {name!r} relationship type",
            )
            for item in bounded_relationships
        )
    return raw


async def introspect_graph_backend(
    backend: GraphStoreBackend,
    *,
    database_name: str,
    namespace: str | None = None,
    graphs: set[str] | tuple[str, ...] | list[str] | None = None,
    default_limit: int = 100,
    default_max_hops: int = 1,
    remote: bool = True,
    offload_sync_backend: bool | None = None,
    discovery_limits: NativeDiscoveryLimits | None = None,
) -> tuple[GraphSourceBinding, ...]:
    """Compile trusted graph/RDF schema descriptors into bounded traversal capabilities."""

    if not database_name.strip():
        raise ValueError("database_name must be non-empty")
    if default_limit < 1 or default_limit > _MAX_LIMIT:
        raise ValueError(f"default_limit must be between 1 and {_MAX_LIMIT}")
    if default_max_hops < 1 or default_max_hops > _MAX_HOPS:
        raise ValueError(f"default_max_hops must be between 1 and {_MAX_HOPS}")

    budget = NativeDiscoveryBudget(discovery_limits)
    limits = budget.limits
    selected = None if graphs is None else {str(value) for value in graphs}
    if selected is not None:
        require_at_most(
            len(selected),
            limit=limits.max_sources,
            label="graph source selected count",
        )
    offload_backend = remote if offload_sync_backend is None else offload_sync_backend
    discovered_raw = await _call_backend(
        backend.list_graphs,
        offload_sync=offload_backend,
    )
    discovered_items = (
        bounded_collect(
            discovered_raw,
            limit=limits.max_sources,
            label="graph source count",
        )
        if selected is None
        else bounded_select(
            discovered_raw,
            selected,
            limit=limits.max_sources,
            label="graph source count",
            name_of=descriptor_name,
        )
    )
    discovered_list: list[GraphSourceSpec] = []
    for value in discovered_items:
        bounded_value = _bounded_graph_descriptor(value, limits)
        graph = (
            bounded_value
            if isinstance(bounded_value, GraphSourceSpec)
            else GraphSourceSpec.model_validate(bounded_value)
        )
        require_at_most(
            len(graph.node_types),
            limit=limits.max_node_types_per_source,
            label=f"graph {graph.name!r} node type count",
        )
        require_at_most(
            len(graph.relationship_types),
            limit=limits.max_relationship_types_per_source,
            label=f"graph {graph.name!r} relationship type count",
        )
        property_count = 0
        for node in graph.node_types:
            require_at_most(
                len(node.properties),
                limit=limits.max_properties_per_type,
                label=f"graph node type {node.name!r} property count",
            )
            property_count += len(node.properties)
        for relationship in graph.relationship_types:
            require_at_most(
                len(relationship.properties),
                limit=limits.max_properties_per_type,
                label=f"graph relationship {relationship.name!r} property count",
            )
            property_count += len(relationship.properties)
        budget.consume_source(
            graph,
            nested_items=(
                len(graph.node_types)
                + len(graph.relationship_types)
                + property_count
            ),
        )
        discovered_list.append(graph)
    discovered = tuple(discovered_list)
    names = [graph.name for graph in discovered]
    if len(names) != len(set(names)):
        raise RegistrationError("graph backend returned duplicate graph names")
    if selected is not None:
        missing = sorted(selected - set(names))
        if missing:
            raise RegistrationError("unknown graphs: " + ", ".join(missing))

    bindings: list[GraphSourceBinding] = []
    used_names: set[str] = set()
    for graph in discovered:
        if selected is not None and graph.name not in selected:
            continue

        relationship_names = sorted(
            relationship.name for relationship in graph.relationship_types
        )
        output_fields = [
            FieldSpec(
                name="source_id",
                description="Traversal source node/subject identifier",
                json_schema={"type": "string"},
                source_type="database",
            ),
            FieldSpec(
                name="target_id",
                description="Traversal target node/object identifier",
                json_schema={"type": "string"},
                source_type="database",
            ),
            FieldSpec(
                name="relationship",
                description="Relationship type or RDF predicate",
                json_schema=(
                    {"type": "string", "enum": relationship_names}
                    if relationship_names
                    else {"type": "string"}
                ),
                source_type="database",
            ),
            FieldSpec(
                name="depth",
                description="Traversal depth from the start node",
                json_schema={"type": "integer", "minimum": 1, "maximum": _MAX_HOPS},
                source_type="database",
            ),
            FieldSpec(
                name="source_type",
                description="Source label/class/type",
                json_schema={"type": "string"},
                source_type="database",
            ),
            FieldSpec(
                name="target_type",
                description="Target label/class/type",
                json_schema={"type": "string"},
                source_type="database",
            ),
        ]
        output_schema = {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    field.name: field.json_schema or {}
                    for field in output_fields
                },
                "additionalProperties": False,
            },
        }
        parameters = [
            ParameterSpec(
                name="start_id",
                description="Trusted graph node/subject identifier",
                required=True,
                location="argument",
                json_schema={"type": "string", "minLength": 1},
            ),
            ParameterSpec(
                name="relationship_types",
                description="Known relationships/predicates allowed for this traversal",
                required=False,
                location="argument",
                json_schema={
                    "type": "array",
                    "items": (
                        {"type": "string", "enum": relationship_names}
                        if relationship_names
                        else {"type": "string"}
                    ),
                    "uniqueItems": True,
                },
            ),
            ParameterSpec(
                name="direction",
                description="Traversal direction",
                required=False,
                location="argument",
                json_schema={
                    "type": "string",
                    "enum": ["out", "in", "both"],
                    "default": "out",
                },
            ),
            ParameterSpec(
                name="max_hops",
                description="Maximum traversal depth",
                required=False,
                location="argument",
                json_schema={
                    "type": "integer",
                    "minimum": 1,
                    "maximum": _MAX_HOPS,
                    "default": default_max_hops,
                },
            ),
            ParameterSpec(
                name="limit",
                description="Maximum edges/triples to return",
                required=False,
                location="argument",
                json_schema={
                    "type": "integer",
                    "minimum": 1,
                    "maximum": _MAX_LIMIT,
                    "default": default_limit,
                },
            ),
        ]
        endpoint = EndpointSpec(
            name=_TRAVERSE_ENDPOINT,
            description=f"Bounded traversal over graph {graph.name}",
            parameters=parameters,
            output_fields=output_fields,
            output_schema=output_schema,
            read_only=True,
            destructive=False,
            execution_metadata={
                "database_family": "graph",
                "graph_model": graph.model,
                "graph": graph.name,
                "default_limit": default_limit,
                "default_max_hops": default_max_hops,
            },
            metadata={
                "database_family": "graph",
                "graph_model": graph.model,
                "graph": graph.name,
                "node_types": [
                    node.model_dump(mode="json")
                    for node in graph.node_types
                ],
                "relationship_types": [
                    relationship.model_dump(mode="json")
                    for relationship in graph.relationship_types
                ],
                "public_metadata": dict(graph.public_metadata),
            },
        )

        tool_name = _slug(graph.name)
        if tool_name in used_names:
            tool_name = f"{tool_name}_{len(used_names) + 1}"
        used_names.add(tool_name)
        tool = ToolSpec(
            name=tool_name,
            namespace=namespace or _slug(database_name),
            description=graph.description or f"Graph source {graph.name}",
            endpoints=[endpoint],
            source_type="database",
            provider=database_name,
            access_mode="graph",
            remote=remote,
            execution_metadata={
                "adapter": "graph_store",
                "database_family": "graph",
                "graph_model": graph.model,
                "graph": graph.name,
            },
            metadata={
                "adapter": "graph_store",
                "database_family": "graph",
                "graph_model": graph.model,
                "graph": graph.name,
            },
        )
        budget.consume_generated(tool)
        bindings.append(
            GraphSourceBinding(
                tool=tool,
                invoker=GraphSourceInvoker(
                    backend,
                    graph=graph,
                    default_limit=default_limit,
                    default_max_hops=default_max_hops,
                    offload_sync_backend=offload_backend,
                ),
            )
        )

    return tuple(bindings)
