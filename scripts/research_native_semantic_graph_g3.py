"""G3 E0: host-attested native input semantic IDs -> authorized graph hints.

Opt-in research boundary only. No runtime joins, arguments, execution,
agent planning, inferred semantics, or product ranking change.
"""
from __future__ import annotations

from dataclasses import dataclass

from schemarouter import PrincipalContext, SchemaRouter
from schemarouter.capability_contracts import CapabilityFieldContract
from scripts.research_authorized_native_graph_edges_g1 import _norm, _safe_routes
from scripts.research_verified_graph_paths_g2 import (
    MAX_HOPS,
    STRICT_K,
    DeclaredGraphGoalG2,
    DeclaredInputBindingG2,
    NonExecutableGraphPathG2,
    _safe_declared_text,
    retrieve_verified_graph_paths_g2,
)

MAX_APPROVED_ROUTES = 32


@dataclass(frozen=True)
class ApprovedNativeRouteG3:
    """Exact local-host approval of a REGISTERED native contract revision.

    This is a trust receipt, not an approval inferred from provider text.
    Neither source nor endpoint revisions may change after attestation.
    """

    route_id: str
    expected_tool_fingerprint: str
    expected_endpoint_fingerprint: str

    def __post_init__(self) -> None:
        if any(
            not _safe_declared_text(value)
            for value in (
                self.route_id,
                self.expected_tool_fingerprint,
                self.expected_endpoint_fingerprint,
            )
        ):
            raise ValueError("G3 requires explicit bounded native source attestation")


@dataclass(frozen=True)
class NativeGraphGoalG3:
    aliases: tuple[str, ...]
    target_route_id: str
    required_outputs: tuple[CapabilityFieldContract, ...]
    approved_routes: tuple[ApprovedNativeRouteG3, ...]

    def __post_init__(self) -> None:
        if (
            type(self.aliases) is not tuple
            or not 1 <= len(self.aliases) <= 16
            or any(not _safe_declared_text(x) for x in self.aliases)
            or len({_norm(x) for x in self.aliases}) != len(self.aliases)
            or not _safe_declared_text(self.target_route_id)
            or type(self.required_outputs) is not tuple
            or not 1 <= len(self.required_outputs) <= 8
            or any(type(x) is not CapabilityFieldContract for x in self.required_outputs)
            or len({x.semantic_id for x in self.required_outputs})
            != len(self.required_outputs)
            or type(self.approved_routes) is not tuple
            or not 2 <= len(self.approved_routes) <= MAX_APPROVED_ROUTES
            or any(type(x) is not ApprovedNativeRouteG3 for x in self.approved_routes)
            or len({x.route_id for x in self.approved_routes})
            != len(self.approved_routes)
            or self.target_route_id
            not in {x.route_id for x in self.approved_routes}
        ):
            raise ValueError("invalid host-attested G3 graph goal")


def retrieve_native_semantic_paths_g3(
    router: SchemaRouter,
    query: str,
    *,
    principal: PrincipalContext,
    goal: NativeGraphGoalG3,
    k: int = STRICT_K,
    max_hops: int = MAX_HOPS,
) -> tuple[NonExecutableGraphPathG2, ...]:
    """Derive *only* native-annotated inputs for a preapproved scoped graph.

    The local owner has reviewed whole native tool/endpoint fingerprints;
    remote annotations or name coincidences never supply an approval.
    The output remains canonical nonexecutable G2 field/route references.
    """
    if not isinstance(router, SchemaRouter) or not isinstance(goal, NativeGraphGoalG3):
        raise ValueError("G3 requires native router and trusted graph goal")
    if not isinstance(principal, PrincipalContext):
        raise ValueError("G3 requires an explicit principal")
    if type(query) is not str or len(query.encode("utf-8")) > 512:
        raise ValueError("invalid bounded query")
    if _norm(query) not in {_norm(alias) for alias in goal.aliases}:
        raise ValueError("no host-declared G3 query alias")

    witness = router._retrieval_authority_witness()
    visible = _safe_routes(
        router, principal, allowed_route_ids=frozenset(
            item.route_id for item in goal.approved_routes
        ),
    )
    approvals = {item.route_id: item for item in goal.approved_routes}
    # No source information about hidden/denied/unavailable approved routes.
    if not approvals.keys() <= visible.keys():
        router._check_retrieval_authority_witness(witness)
        return ()

    bindings: list[DeclaredInputBindingG2] = []
    for approval in goal.approved_routes:
        scoped_tool, scoped_endpoint = visible[approval.route_id]
        original_tool = router.registry.get(scoped_tool.key)
        original_endpoint = original_tool.endpoint(scoped_endpoint.name)
        if (
            original_tool.fingerprint != approval.expected_tool_fingerprint
            or original_endpoint.fingerprint != approval.expected_endpoint_fingerprint
        ):
            raise ValueError("G3 approved native source revision is stale")
        # For E0 the root truly has zero native parameters. All consumers
        # have ONE required native input. Optional/unknown arguments cannot
        # be silently dropped to fabricate an apparently executable chain.
        if not scoped_endpoint.parameters:
            continue
        if len(scoped_endpoint.parameters) != 1:
            router._check_retrieval_authority_witness(witness)
            return ()
        parameter = scoped_endpoint.parameters[0]
        registered_parameter = original_endpoint.parameters[0]
        if (
            not parameter.required
            or parameter.semantic_id is None
            or parameter.semantic_id != registered_parameter.semantic_id
        ):
            router._check_retrieval_authority_witness(witness)
            return ()
        bindings.append(DeclaredInputBindingG2(
            route_id=approval.route_id,
            parameter_name=parameter.name,
            semantic_id=parameter.semantic_id,
            expected_endpoint_fingerprint=approval.expected_endpoint_fingerprint,
        ))
    if goal.target_route_id not in {item.route_id for item in bindings}:
        router._check_retrieval_authority_witness(witness)
        return ()

    declared_goal = DeclaredGraphGoalG2(
        aliases=goal.aliases,
        target_route_id=goal.target_route_id,
        required_outputs=goal.required_outputs,
        bindings=tuple(bindings),
    )
    paths = retrieve_verified_graph_paths_g2(
        router,
        query,
        principal=principal,
        goal=declared_goal,
        k=k,
        max_hops=max_hops,
        allowed_route_ids=frozenset(approvals),
    )
    # G2 checks native endpoint source/policy. G3 also pins whole-tool
    # metadata, including source/license and all registered endpoints.
    for approval in goal.approved_routes:
        scoped_tool = visible[approval.route_id][0]
        source = router.registry.get(scoped_tool.key)
        if source.fingerprint != approval.expected_tool_fingerprint:
            raise ValueError("G3 approved native tool changed during retrieval")
    router._check_retrieval_authority_witness(witness)
    return paths
