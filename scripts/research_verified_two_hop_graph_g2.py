"""G2 opt-in: a verified two-edge graph candidate, NOT an execution plan.

All nodes derive from one current principal-scoped native registry snapshot.
Two host-declared required-parameter→semantic bindings are pinned to native
endpoint fingerprints. This research control proves only adjacency and
declared output-field coverage; it never constructs values or runs tools.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from schemarouter import PrincipalContext, SchemaRouter
from schemarouter.capability_contracts import (
    CapabilityContract,
    CapabilityFieldContract,
    compare_capability_fields,
)
from schemarouter.capability_snapshot import (
    CapabilitySourceRevision,
    build_capability_snapshot,
    validate_capability_snapshot,
)
from schemarouter.models import EndpointSpec, ToolSpec
from scripts.research_authorized_native_graph_edges_g1 import (
    MAX_VISIBLE_ROUTES,
    DeclaredQueryInputLink,
    NonExecutableDependencyHint,
    _norm,
    _produced_fields,
    _safe_routes,
    _simple_scalar_schema,
    _target_requirement,
)

MAX_GRAPH_EDGES = 1024
STRICT_K = 5
STRICT_HOPS = 2


@dataclass(frozen=True)
class DeclaredTwoHopGraphIntent:
    """Host-authored pinned source contract, not a semantic inference."""

    first: DeclaredQueryInputLink
    second: DeclaredQueryInputLink
    required_final_fields: tuple[CapabilityFieldContract, ...]
    first_consumer_fingerprint: str
    second_consumer_fingerprint: str

    def __post_init__(self) -> None:
        if (
            type(self.required_final_fields) is not tuple
            or not 1 <= len(self.required_final_fields) <= 4
            or any(type(field) is not CapabilityFieldContract
                   for field in self.required_final_fields)
            or len({field.semantic_id for field in self.required_final_fields})
            != len(self.required_final_fields)
            or self.second.target_output_semantic_id not in {
                field.semantic_id for field in self.required_final_fields
            }
            or self.first.target_route_id == self.second.target_route_id
            or self.first.target_output_semantic_id != self.second.input_semantic_id
            or self.first.query_aliases != self.second.query_aliases
            or any(
                type(value) is not str or re.fullmatch(r"[0-9a-f]{64}", value) is None
                for value in (
                    self.first_consumer_fingerprint,
                    self.second_consumer_fingerprint,
                )
            )
        ):
            raise ValueError("invalid pinned two-hop ontology declaration")


@dataclass(frozen=True)
class NonExecutableTwoHopHint:
    """A typed read-only graph path; this is not an agent execution schedule."""

    source_to_intermediate: NonExecutableDependencyHint
    intermediate_to_target: NonExecutableDependencyHint
    verified_final_semantics: tuple[str, ...]
    authorized_snapshot_id: str


def _recorded_native_fingerprints(
    router: SchemaRouter,
    eligible_routes: dict[str, tuple[ToolSpec, EndpointSpec]],
) -> dict[str, str]:
    """Compare trusted native fingerprints only for already-visible routes."""
    permitted = set(eligible_routes)
    recorded = {}
    for tool in router.registry.tools():
        for endpoint in tool.endpoints:
            key = f"{tool.key}.{endpoint.name}"
            if key in permitted:
                recorded[key] = endpoint.fingerprint
    if set(recorded) != permitted:
        raise ValueError("authorized graph source identity is incomplete")
    return recorded


def _compatible_field_name(
    endpoint: EndpointSpec,
    required: CapabilityFieldContract,
) -> str | None:
    compatible = []
    for field in endpoint.output_fields:
        if field.semantic_id is None or field.unit_normalization is not None:
            continue
        if not _simple_scalar_schema(field.json_schema):
            continue
        contract = CapabilityFieldContract.from_field(field)
        if contract is not None and compare_capability_fields(
            required, contract,
        ).status in {"exact", "compatible"}:
            compatible.append(field.name)
    return min(compatible) if compatible else None


def _has_all_final_fields(
    endpoint: EndpointSpec, required: tuple[CapabilityFieldContract, ...],
) -> bool:
    # Reuse the same canonical typed comparator as the graph edges.
    return all(
        _compatible_field_name(endpoint, field) is not None
        for field in required
    )


def _no_native_required_inputs(endpoint: EndpointSpec) -> bool:
    return not any(parameter.required for parameter in endpoint.parameters) and not (
        endpoint.input_schema.get("required")
    )


def retrieve_authorized_two_hop_hints_g2(
    router: SchemaRouter,
    query: str,
    *,
    principal: PrincipalContext,
    declaration: DeclaredTwoHopGraphIntent,
    k: int = STRICT_K,
    max_hops: int = STRICT_HOPS,
) -> tuple[NonExecutableTwoHopHint, ...]:
    """Return verified source→intermediate→target graph references only.

    The intermediate endpoint is explicitly declared. Compatible terminal
    predecessors are discovered with the native graph. There is no inference
    of a two-hop plan, upstream argument values or downstream state.
    """
    if type(k) is not int or k != STRICT_K:
        raise ValueError("G2 requires strict K5")
    if type(max_hops) is not int or max_hops != STRICT_HOPS:
        raise ValueError("G2 supports exactly two graph edges")
    if type(query) is not str or _norm(query) not in {
        _norm(a) for a in declaration.first.query_aliases
    }:
        raise ValueError("G2 query has no declared intent")
    if not isinstance(principal, PrincipalContext):
        raise ValueError("G2 requires explicit principal")
    witness = router._retrieval_authority_witness()
    routes = _safe_routes(router, principal)
    one, two = declaration.first, declaration.second
    if one.target_route_id not in routes or two.target_route_id not in routes:
        router._check_retrieval_authority_witness(witness)
        return ()
    native_fingerprints = _recorded_native_fingerprints(router, routes)
    if (
        native_fingerprints[one.target_route_id]
        != declaration.first_consumer_fingerprint
        or native_fingerprints[two.target_route_id]
        != declaration.second_consumer_fingerprint
    ):
        raise ValueError("stale declared graph source fingerprint")

    intermediate_endpoint = routes[one.target_route_id][1]
    final_endpoint = routes[two.target_route_id][1]
    if not _has_all_final_fields(
        final_endpoint, declaration.required_final_fields,
    ):
        router._check_retrieval_authority_witness(witness)
        return ()

    first_requirement = _target_requirement(one, routes)
    second_requirement = _target_requirement(two, routes)
    if first_requirement is None or second_requirement is None:
        router._check_retrieval_authority_witness(witness)
        return ()

    # All input bindings and graph vertices must originate in the SAME
    # authorized source view. Never union graph evidence across principals.
    contracts = []
    sources = []
    for route_id, (tool, endpoint) in sorted(routes.items()):
        if (
            not tool.source_type or not tool.license
            or not tool.provider
        ):
            # Keep unproven source/licensing identity out of this G2 proof.
            continue
        requirements = (
            [first_requirement] if route_id == one.target_route_id
            else [second_requirement] if route_id == two.target_route_id
            else []
        )
        contracts.append(CapabilityContract(
            capability_id=route_id,
            requires=requirements,
            produces=_produced_fields(endpoint),
        ))
        sources.append(CapabilitySourceRevision(
            provider=route_id,
            access_method="principal_scoped_native_g2",
            schema_fingerprint=endpoint.fingerprint,
        ))
    visible_ids = {c.capability_id for c in contracts}
    if not {one.target_route_id, two.target_route_id}.issubset(visible_ids):
        router._check_retrieval_authority_witness(witness)
        return ()
    snapshot = build_capability_snapshot(
        contracts,
        sources=sources,
        builder_version="authorized_native_two_hop_g2",
    )
    validate_capability_snapshot(snapshot)
    graph = snapshot.build_graph()
    if len(graph.capability_ids) > MAX_VISIBLE_ROUTES or len(graph.edges) > MAX_GRAPH_EDGES:
        raise ValueError("G2 authorized graph budget exceeded")
    # Only two declared nodes can consume graph fields. If the final tool
    # also feeds the intermediate, the graph is cyclic, not a safe path.
    if two.target_route_id in graph.predecessors(one.target_route_id):
        raise ValueError("G2 declared path participates in a dependency cycle")
    if one.target_route_id not in graph.predecessors(two.target_route_id):
        router._check_retrieval_authority_witness(witness)
        return ()

    edge_to_target_field = _compatible_field_name(
        intermediate_endpoint, second_requirement,
    )
    if edge_to_target_field is None:
        raise ValueError("G2 canonical graph edge lacks visible intermediate field")

    hints = []
    for source_id in sorted(graph.predecessors(one.target_route_id)):
        if source_id in {one.target_route_id, two.target_route_id}:
            continue
        source_tool, source_endpoint = routes[source_id]
        if (
            not source_tool.source_type or not source_tool.license
            or not source_tool.provider
            or not _no_native_required_inputs(source_endpoint)
        ):
            continue
        first_field = _compatible_field_name(
            source_endpoint, first_requirement,
        )
        if first_field is None:
            raise ValueError("G2 graph predecessor lacks typed visible source field")
        hints.append(NonExecutableTwoHopHint(
            source_to_intermediate=NonExecutableDependencyHint(
                producer_route_id=source_id,
                consumer_route_id=one.target_route_id,
                producer_output_field=first_field,
                consumer_input_parameter=one.parameter_name,
                semantic_id=one.input_semantic_id,
            ),
            intermediate_to_target=NonExecutableDependencyHint(
                producer_route_id=one.target_route_id,
                consumer_route_id=two.target_route_id,
                producer_output_field=edge_to_target_field,
                consumer_input_parameter=two.parameter_name,
                semantic_id=two.input_semantic_id,
            ),
            verified_final_semantics=tuple(
                field.semantic_id for field in declaration.required_final_fields
            ),
            authorized_snapshot_id=snapshot.snapshot_id,
        ))
    if len(hints) > k:
        raise ValueError("G2 complete graph path K budget exceeded")
    router._check_retrieval_authority_witness(witness)
    return tuple(hints)
