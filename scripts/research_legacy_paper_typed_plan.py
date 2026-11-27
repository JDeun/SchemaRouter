"""Checkout-only historical Field Union typed-plan compilation.

The query-alias alternative selector is not an installed Algorithm 1 route.
Shared call shapes and current source/scope validation use the product contracts.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from schemarouter._authorization_witness import _policy_contents_digest
from schemarouter.authorization import PrincipalContext
from schemarouter.concept_retrieval import NativeConceptCatalog
from schemarouter.errors import PolicyViolationError
from schemarouter.native_graph_index import NativeSchemaGraphIndex
from schemarouter.paper_typed_tool_plan import (
    PaperPlanBinding,
    PaperPlanCall,
    PaperTypedToolPlan,
    _check_current_call_scopes,
    _compile_one_route,
)
from scripts.research_legacy_paper_field_retrieval import retrieve_paper_field_coverage

if TYPE_CHECKING:
    from schemarouter.runtime import SchemaRouter


def compile_paper_typed_tool_plan(
    router: SchemaRouter,
    query: str,
    *,
    principal: PrincipalContext,
    catalog: NativeConceptCatalog,
    index: NativeSchemaGraphIndex,
    alternative_index: int = 0,
    k: int = 5,
    host_source_arguments: dict[str, dict[str, Any]] | None = None,
) -> PaperTypedToolPlan:
    """Compile ONE source-proven K5 alternative without executing or binding data.

    `ready` means the typed shape has no missing arguments; it is NOT an
    authorization decision. Actual values, tool calls and evidence must still
    pass the ordinary executor's current security and validation boundaries.
    """
    if type(alternative_index) is not int or alternative_index < 0:
        raise ValueError("invalid paper alternative index")
    if host_source_arguments is not None and (
        type(host_source_arguments) is not dict
        or any(
            type(route) is not str or type(values) is not dict
            for route, values in host_source_arguments.items()
        )
    ):
        raise ValueError("invalid explicit host source argument declaration")
    host_inputs = {
        route: dict(values) for route, values in (host_source_arguments or {}).items()
    }
    proof = retrieve_paper_field_coverage(
        router, query, principal=principal, catalog=catalog, index=index, k=k,
    )
    if proof.status != "complete":
        if host_inputs:
            raise ValueError("explicit host arguments require a proven source route")
        if alternative_index:
            raise ValueError("paper alternative index is out of range")
        return PaperTypedToolPlan(
            status=proof.status,
            snapshot_id=proof.snapshot_id,
            registry_version=proof.registry_version,
            requested_k=proof.requested_k,
        )
    if alternative_index >= len(proof.alternatives):
        raise ValueError("paper alternative index is out of range")

    chosen = proof.alternatives[alternative_index]
    if len(chosen.routes) > k or len({r.route_id for r in chosen.routes}) != len(chosen.routes):
        raise PolicyViolationError("paper typed plan has invalid original routes")

    policy = router.authorization_policy
    if policy is None:
        raise PolicyViolationError("paper typed plan requires original source policy")
    witness = router._retrieval_authority_witness()
    policy_digest = _policy_contents_digest(policy)
    declared_principal = principal.model_dump_json()
    declared_catalog = catalog.model_dump_json()
    permitted = router._authorization_predicate(principal)
    if permitted is None:
        raise PolicyViolationError("paper typed plan requires original source policy")

    positions = {route.route_id: i for i, route in enumerate(chosen.routes)}
    if not host_inputs.keys() <= positions.keys():
        raise ValueError("explicit host arguments name an unproved source route")
    receipts_by_route = {route.route_id: route for route in chosen.routes}
    calls: list[PaperPlanCall] = []
    edges: list[PaperPlanBinding] = []
    try:
        for i, route in enumerate(chosen.routes):
            calls.append(_compile_one_route(
                router, principal, index, route, i, positions,
                receipts_by_route, edges, permitted, host_inputs.get(route.route_id),
            ))
        _check_current_call_scopes(router, principal, calls)
        # End-of-compilation second observation of the SAME complete proof,
        # not a substitute for atomic provider snapshots or execution checks.
        if retrieve_paper_field_coverage(
            router, query, principal=principal, catalog=catalog, index=index, k=k,
        ) != proof:
            raise PolicyViolationError("paper field proof changed during compilation")
        # The P1 proof rechecks visible OUTPUTS, not argument-specific scope.
        # Re-evaluate the actual typed calls after the final source observation.
        _check_current_call_scopes(router, principal, calls)
    except Exception:
        # A data scope / health / host callback may include private diagnostics.
        raise PolicyViolationError("paper typed plan source eligibility changed") from None

    index.field_index._assert_source(router)
    router._check_retrieval_authority_witness(witness)
    if (
        router.authorization_policy is None
        or _policy_contents_digest(router.authorization_policy) != policy_digest
        or principal.model_dump_json() != declared_principal
        or catalog.model_dump_json() != declared_catalog
    ):
        raise PolicyViolationError("paper typed plan source declaration changed")

    status = (
        "requires_observation" if edges else
        "requires_arguments" if any(
            item.call.missing_required_arguments for item in calls
        ) else "ready"
    )
    return PaperTypedToolPlan(
        status=status,
        snapshot_id=proof.snapshot_id,
        registry_version=proof.registry_version,
        requested_k=k,
        calls=tuple(calls),
        bindings=tuple(edges),
    )
