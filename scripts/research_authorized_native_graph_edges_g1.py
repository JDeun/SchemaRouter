"""G1 research-only query→trusted input semantic→graph predecessor retrieval.

Native registry and policy, not names or an LLM, establish all visible routes.
The trusted host explicitly binds a *required* consumer parameter to one
semantic field. The canonical dependency graph verifies producer compatibility.
Returned references are neither an executable plan nor an authorization grant.
"""
from __future__ import annotations

import unicodedata
from dataclasses import dataclass

from schemarouter import PrincipalContext, SchemaRouter
from schemarouter.capability_contracts import (
    CapabilityContract,
    CapabilityFieldContract,
    compare_capability_fields,
)
from schemarouter.capability_graph import build_capability_dependency_graph
from schemarouter.models import EndpointSpec, FieldSpec, ToolSpec

MAX_VISIBLE_ROUTES = 512
MAX_VISIBLE_FIELDS = 4096
STRICT_K = 5


def _simple_scalar_schema(schema: dict) -> bool:
    """Canonical comparator checks scalar types, not arbitrary JSON constraints."""
    return (
        type(schema) is dict
        and set(schema) == {"type"}
        and schema["type"] in {"string", "integer", "number", "boolean"}
    )


def _norm(value: str) -> str:
    return unicodedata.normalize("NFC", value).strip().casefold()


@dataclass(frozen=True)
class DeclaredQueryInputLink:
    """Host-authored relationship; it is NOT inferred from parameter names."""

    query_aliases: tuple[str, ...]
    target_route_id: str
    target_output_semantic_id: str
    parameter_name: str
    input_semantic_id: str

    def __post_init__(self) -> None:
        if (
            type(self.query_aliases) is not tuple
            or not 1 <= len(self.query_aliases) <= 16
            or any(type(a) is not str or not 1 <= len(a) <= 160 or not _norm(a)
                   for a in self.query_aliases)
            or len({_norm(a) for a in self.query_aliases}) != len(self.query_aliases)
            or any(
                type(v) is not str
                or not v.strip()
                or v != v.strip()
                or len(v) > 160
                for v in (
                    self.target_route_id, self.target_output_semantic_id,
                    self.parameter_name, self.input_semantic_id,
                )
            )
        ):
            raise ValueError("invalid declared native graph input link")


@dataclass(frozen=True)
class NonExecutableDependencyHint:
    producer_route_id: str
    consumer_route_id: str
    producer_output_field: str
    consumer_input_parameter: str
    semantic_id: str


def _produced_fields(endpoint: EndpointSpec) -> list[CapabilityFieldContract]:
    fields = []
    for field in endpoint.output_fields:
        if (
            field.semantic_id is None
            or field.unit_normalization is not None
            or not _simple_scalar_schema(field.json_schema)
        ):
            continue
        contract = CapabilityFieldContract.from_field(field)
        if contract is not None:
            fields.append(contract)
    return fields


def _safe_routes(
    router: SchemaRouter, principal: PrincipalContext,
) -> dict[str, tuple[ToolSpec, EndpointSpec]]:
    allowed = router._authorization_predicate(principal)
    if allowed is None:
        raise ValueError("G1 requires explicit principal authorization")
    visible = router._scoped_analysis_registry(principal, allowed)
    entries: dict[str, tuple[ToolSpec, EndpointSpec]] = {}
    availability = router.planner.availability_predicate
    visible_field_count = 0
    for tool in visible.tools():
        for endpoint in tool.endpoints:
            if endpoint.read_only is not True or endpoint.destructive is True:
                continue
            if not allowed(tool, endpoint):
                continue
            if availability is not None and not availability(tool, endpoint):
                continue
            visible_field_count += len(endpoint.output_fields)
            if visible_field_count > MAX_VISIBLE_FIELDS:
                raise ValueError("authorized graph field budget exceeded")
            route_id = f"{tool.key}.{endpoint.name}"
            if route_id in entries or len(entries) >= MAX_VISIBLE_ROUTES:
                raise ValueError("invalid or over-budget authorized graph source")
            entries[route_id] = (tool, endpoint)
    return entries


def _target_requirement(
    link: DeclaredQueryInputLink,
    routes: dict[str, tuple[ToolSpec, EndpointSpec]],
) -> CapabilityFieldContract | None:
    source = routes.get(link.target_route_id)
    if source is None:
        return None
    _, endpoint = source
    # The target must actually produce the claimed answer semantic.
    if not any(
        field.semantic_id == link.target_output_semantic_id
        and _simple_scalar_schema(field.json_schema)
        for field in endpoint.output_fields
    ):
        return None
    required_params = [p for p in endpoint.parameters if p.required]
    if (
        len(required_params) != 1
        or required_params[0].name != link.parameter_name
        or required_params[0].location in {"header", "body_root"}
        or not _simple_scalar_schema(required_params[0].json_schema)
        or any(
            name != link.parameter_name
            for name in endpoint.input_schema.get("required", [])
        )
    ):
        # No silently ignored extra required arguments or guessed inputs.
        return None
    return CapabilityFieldContract(
        semantic_id=link.input_semantic_id,
        json_schema=required_params[0].json_schema,
    )


def retrieve_authorized_dependency_hints_g1(
    router: SchemaRouter,
    query: str,
    *,
    principal: PrincipalContext,
    link: DeclaredQueryInputLink,
    k: int = STRICT_K,
) -> tuple[NonExecutableDependencyHint, ...]:
    """Only one typed producer→consumer edge. Never plan or invoke.

    If more than K eligible predecessors exist, refuse rather than invent
    a semantic rank or silently claim that the truncated K are best.
    """
    if type(k) is not int or k != STRICT_K:
        raise ValueError("G1 supports only strict fixed K5")
    if type(query) is not str or _norm(query) not in {
        _norm(alias) for alias in link.query_aliases
    }:
        raise ValueError("query has no declared route intent")
    if not isinstance(principal, PrincipalContext):
        raise ValueError("G1 requires explicit principal")
    witness = router._retrieval_authority_witness()
    routes = _safe_routes(router, principal)
    target = _target_requirement(link, routes)
    if target is None:
        router._check_retrieval_authority_witness(witness)
        return ()

    contracts = [
        CapabilityContract(
            capability_id=route_id,
            requires=[target] if route_id == link.target_route_id else [],
            produces=_produced_fields(endpoint),
        )
        for route_id, (_tool, endpoint) in sorted(routes.items())
    ]
    graph = build_capability_dependency_graph(contracts)
    refs = graph.predecessors(link.target_route_id)
    if len(refs) > k:
        raise ValueError("authorized graph predecessor K budget exceeded")
    hints: list[NonExecutableDependencyHint] = []
    for route_id in refs:
        _, endpoint = routes[route_id]
        compatible = [
            field for field in endpoint.output_fields
            if field.semantic_id is not None
            and field.unit_normalization is None
            and _simple_scalar_schema(field.json_schema)
            and (contract := CapabilityFieldContract.from_field(field)) is not None
            and compare_capability_fields(target, contract).satisfies
        ]
        if not compatible:
            # The same typed comparator produced this dependency edge.
            raise ValueError("authorized graph edge lacks a visible typed field")
        chosen: FieldSpec = sorted(compatible, key=lambda f: f.name)[0]
        hints.append(NonExecutableDependencyHint(
            producer_route_id=route_id,
            consumer_route_id=link.target_route_id,
            producer_output_field=chosen.name,
            consumer_input_parameter=link.parameter_name,
            semantic_id=link.input_semantic_id,
        ))
    router._check_retrieval_authority_witness(witness)
    return tuple(hints)
