"""G4 DEV: discover *targets* in an approved native schema graph, then reuse G3.

The host approves a bounded source catalog, query aliases and output
FieldGroup, but does NOT select the target endpoint. This is not a new
planner/ranker or an all-tools production graph index.
"""
from __future__ import annotations

from schemarouter import (
    NativeConceptCatalog,
    PrincipalContext,
    SchemaRouter,
)
from schemarouter.capability_contracts import CapabilityFieldContract
from schemarouter.concept_retrieval import resolve_native_concepts
from scripts.research_authorized_native_graph_edges_g1 import _safe_routes
from scripts.research_native_semantic_graph_g3 import (
    MAX_APPROVED_ROUTES,
    ApprovedNativeRouteG3,
    NativeGraphGoalG3,
    retrieve_native_semantic_paths_g3,
)
from scripts.research_verified_graph_paths_g2 import (
    NonExecutableGraphPathG2,
    _full_target_outputs,
    _native_required_param,
    _proved_empty_root_envelope,
    _valid_edge_field,
)

STRICT_K = 5


def discover_authorized_native_graph_paths_g4(
    router: SchemaRouter,
    query: str,
    *,
    principal: PrincipalContext,
    catalog: NativeConceptCatalog,
    approved_routes: tuple[ApprovedNativeRouteG3, ...],
    k: int = STRICT_K,
) -> tuple[NonExecutableGraphPathG2, ...]:
    """Return only native source-attested, non-executable one-hop paths.

    No explicit target_route_id is input. Discover eligible field-complete
    consumer endpoints from the *current authorized native schema*, then
    source its required identifier using existing canonical G3/G2.
    More than K5 verified paths is UNSUPPORTED for E0: do not fabricate
    rank ordering or silently clip a recall-relevant candidate.
    """
    if type(k) is not int or k != STRICT_K:
        raise ValueError("G4 requires exactly fixed K5")
    if not isinstance(router, SchemaRouter) or not isinstance(principal, PrincipalContext):
        raise ValueError("G4 requires native router and trusted principal")
    if (
        type(approved_routes) is not tuple
        or not 2 <= len(approved_routes) <= MAX_APPROVED_ROUTES
        or any(type(item) is not ApprovedNativeRouteG3 for item in approved_routes)
        or len({item.route_id for item in approved_routes}) != len(approved_routes)
    ):
        raise ValueError("G4 requires unique bounded host-approved native routes")

    resolved = resolve_native_concepts(query, catalog=catalog)
    demand = resolved.field_group
    witness = router._retrieval_authority_witness()
    approvals = {item.route_id: item for item in approved_routes}
    # This native source view first honors principal/field scope, availability,
    # and the exact local-host catalog approval set BEFORE graph budgets.
    visible = _safe_routes(
        router, principal, allowed_route_ids=frozenset(approvals),
    )
    for route_id in visible:
        tool, endpoint = visible[route_id]
        source = router.registry.get(tool.key)
        original = source.endpoint(endpoint.name)
        approved = approvals[route_id]
        if (source.fingerprint != approved.expected_tool_fingerprint
                or original.fingerprint != approved.expected_endpoint_fingerprint):
            raise ValueError("G4 approved native source revision is stale")

    # Semantic-ID adjacency index is an exact prefilter, not an independent
    # type/permission verifier. G3/G2 still decides every surviving edge.
    roots_by_semantic: dict[str, list[str]] = {}
    for route_id, (tool, endpoint) in sorted(visible.items()):
        if (
            tool.source_type is not None
            and tool.license is not None
            and not endpoint.parameters
            and not endpoint.auth_requirements
            and _proved_empty_root_envelope(endpoint)
        ):
            for field in endpoint.output_fields:
                if field.identifier is True and field.semantic_id is not None:
                    roots_by_semantic.setdefault(field.semantic_id, []).append(route_id)

    found: dict[tuple[str, ...], NonExecutableGraphPathG2] = {}
    for target_id, (target_tool, target_ep) in sorted(visible.items()):
        if (
            target_tool.source_type != demand.source_type
            or target_tool.license != demand.license
            or _full_target_outputs(target_ep, demand.required_fields) is None
        ):
            continue
        required = _native_required_param(target_ep)
        if (
            required is None or len(target_ep.parameters) != 1
            or target_ep.parameters[0].semantic_id is None
        ):
            continue
        parameter = target_ep.parameters[0]
        param_name, param_schema = required
        if parameter.name != param_name:
            continue
        required_input = CapabilityFieldContract(
            semantic_id=parameter.semantic_id,
            json_schema=param_schema,
        )
        for root_id in roots_by_semantic.get(required_input.semantic_id, ()):
            if root_id == target_id:
                continue
            _root_tool, root_ep = visible[root_id]
            if _valid_edge_field(root_ep, required_input) is None:
                continue
            # Only these two already-approved current native endpoints are
            # needed. Reuse the SAME conservative G3 -> G2 graph engine.
            goal = NativeGraphGoalG3(
                aliases=(query,),
                target_route_id=target_id,
                required_outputs=demand.required_fields,
                approved_routes=(approvals[root_id], approvals[target_id]),
            )
            verified = retrieve_native_semantic_paths_g3(
                router, query, principal=principal, goal=goal,
                k=STRICT_K, max_hops=1,
            )
            for path in verified:
                if len(path.route_ids) != 2 or path.route_ids != (root_id, target_id):
                    raise ValueError("G4 canonical graph returned an unapproved path")
                found[path.route_ids] = path
                if len(found) > STRICT_K:
                    raise ValueError("G4 verified paths exceed K5; ranking not proven")
    router._check_retrieval_authority_witness(witness)
    return tuple(found[key] for key in sorted(found))
