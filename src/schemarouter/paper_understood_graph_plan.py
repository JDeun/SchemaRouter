"""Original-paper named tool → source-proven 1-/2-hop typed plans (E0).

Only the existing canonical G5 graph may attest dependencies. This module
does not execute calls, trust a language-model parameter, or grant authority.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from .authorization import PrincipalContext
from .concept_retrieval import NativeConceptCatalog
from .errors import PolicyViolationError
from .host_field_contract import _policy_contents_digest
from .native_graph_index import NativeSchemaGraphIndex
from .paper_field_retrieval import PaperFieldRoute
from .paper_typed_tool_plan import (
    PaperPlanBinding,
    PaperPlanCall,
    PaperTypedToolPlan,
    _check_current_call_scopes,
    _compile_one_route,
)
from .paper_understood_direct_plan import (
    PaperIntentRegistry,
    PaperUnderstanding,
    _source_owned_understood_group,
    compile_paper_understood_direct_plan,
)

if TYPE_CHECKING:
    from .runtime import SchemaRouter


def compile_paper_understood_graph_plan(
    router: SchemaRouter,
    understanding: PaperUnderstanding,
    *,
    principal: PrincipalContext,
    catalog: NativeConceptCatalog,
    intent_registry: PaperIntentRegistry,
    index: NativeSchemaGraphIndex,
    k: int = 5,
    max_hops: int = 2,
    host_source_arguments: dict[str, dict[str, Any]] | None = None,
) -> PaperTypedToolPlan:
    """Compile one exact model-named target path without source execution.

    A complete ready direct route takes precedence. Only explicitly named tools
    can select a typed dependency target; several complete paths without
    independent ranking produce an empty ``ambiguous_paths`` receipt.
    """
    if type(k) is not int or k != 5:
        raise ValueError("paper named graph plan requires exact K5")
    if type(max_hops) is not int or max_hops not in (1, 2):
        raise ValueError("paper named graph plan accepts one or two edges")
    if not isinstance(index, NativeSchemaGraphIndex):
        raise ValueError("paper named graph plan requires original graph index")
    if not isinstance(principal, PrincipalContext):
        raise PolicyViolationError("paper named graph requires trusted principal")
    if not isinstance(catalog, NativeConceptCatalog):
        raise ValueError("paper named graph requires owner-reviewed catalog")
    if not isinstance(intent_registry, PaperIntentRegistry):
        raise ValueError("paper named graph requires host-approved intents")
    if not isinstance(understanding, PaperUnderstanding):
        raise ValueError("paper named graph requires structured hints")
    if host_source_arguments is not None and (
        type(host_source_arguments) is not dict
        or any(
            type(route) is not str or type(values) is not dict
            for route, values in host_source_arguments.items()
        )
    ):
        raise ValueError("invalid explicit paper host root inputs")
    host_inputs = {
        route: dict(values) for route, values in (host_source_arguments or {}).items()
    }

    approved, group = _source_owned_understood_group(
        understanding, catalog, intent_registry,
    )
    try:
        original_understanding = understanding.model_dump_json()
        original_intents = intent_registry.model_dump_json()
        original_catalog = catalog.model_dump_json()
        original_principal = principal.model_dump_json()
    except (ValueError, TypeError, OverflowError, AttributeError) as exc:
        raise ValueError("paper named graph declarations are invalid") from exc

    # A source type suggestion may only NARROW an already owner-reviewed type.
    direct = compile_paper_understood_direct_plan(
        router, understanding, principal=principal, catalog=catalog,
        intent_registry=intent_registry, index=index, k=k,
    )
    direct_routes = {call.route_id for call in direct.calls}
    if host_inputs and host_inputs.keys() <= direct_routes:
        # A declared scalar root is a direct tool, not a graph dependency.
        # Reuse the same exact original-source host-input validator, only
        # after proving the complete principal-visible direct route.
        direct = compile_paper_understood_direct_plan(
            router, understanding, principal=principal, catalog=catalog,
            intent_registry=intent_registry, index=index, k=k,
            host_source_arguments=host_source_arguments,
        )
    elif host_inputs and direct.status == "ready":
        raise ValueError("paper graph host arguments do not match direct proof")
    if (
        direct.status not in {"no_proven_hit", "requires_arguments"}
        or not approved.named_tools
        or approved.source_type is not None
        and approved.source_type != group.source_type
    ):
        return direct

    witness = router._retrieval_authority_witness()
    index.field_index._assert_source(router)
    policy = router.authorization_policy
    if policy is None:
        raise PolicyViolationError("paper named graph requires explicit source policy")
    policy_digest = _policy_contents_digest(policy)

    def verify_current() -> None:
        index.field_index._assert_source(router)
        router._check_retrieval_authority_witness(witness)
        if (
            router.authorization_policy is None
            or _policy_contents_digest(router.authorization_policy) != policy_digest
            or principal.model_dump_json() != original_principal
            or catalog.model_dump_json() != original_catalog
            or intent_registry.model_dump_json() != original_intents
            or understanding.model_dump_json() != original_understanding
        ):
            raise PolicyViolationError("paper named graph source or declaration changed")

    def empty(status: str) -> PaperTypedToolPlan:
        verify_current()
        return PaperTypedToolPlan(
            status=status,  # type: ignore[arg-type]
            snapshot_id=index.field_index.snapshot_id,
            registry_version=witness[1], requested_k=k,
        )

    # Source structure is only a prefilter, not proof or visibility. All
    # named targets must pass the ordinary principal-scoped G5 lookup.
    target_routes = frozenset(
        route_id for route_id, (tool_key, _) in index.field_index.route_locations.items()
        if tool_key in approved.named_tools
    )
    if not target_routes:
        return empty("no_proven_hit")
    # Do not expose the cardinality of registry-only/denied named tools via
    # the structural target budget. Project current principal eligibility
    # BEFORE the 32-route G5 prefilter cap; the G5 lookup still independently
    # verifies its original typed graph proof and all route permissions.
    permitted_targets = router._authorization_predicate(principal)
    if permitted_targets is None:
        raise PolicyViolationError("paper named graph lacks current source policy")
    available = router.planner.availability_predicate
    scoped_targets: set[str] = set()
    for route_id in sorted(target_routes):
        tool_key, endpoint_name = index.field_index.route_locations[route_id]
        tool = router.registry.get(tool_key)
        endpoint = tool.endpoint(endpoint_name)
        if (
            tool.source_type != group.source_type
            or tool.license != group.license
            or not permitted_targets(tool, endpoint)
            or endpoint.read_only is not True
            or endpoint.destructive is True
            or available is not None and not available(tool, endpoint)
            or router._data_scope_endpoint_view(principal, tool, endpoint) is None
        ):
            continue
        scoped_targets.add(route_id)
        if len(scoped_targets) > 32:
            return empty("budget_unsatisfied")
    target_routes = frozenset(scoped_targets)
    if not target_routes:
        return empty("no_proven_hit")

    def lookup(hops: int) -> Any:
        if hops == 1:
            return index.lookup(
                router, group.aliases[0], group=group, principal=principal,
                k=k, allowed_target_routes=target_routes,
            )
        return index.lookup_two_hop(
            router, group.aliases[0], group=group, principal=principal,
            k=k, allowed_target_routes=target_routes,
        )

    hops = 1
    result = lookup(hops)
    if result.status == "no_proven_hit" and max_hops == 2:
        hops = 2
        result = lookup(hops)
    if result.status != "complete":
        if result.status not in {"no_proven_hit", "over_k_unranked"}:
            raise PolicyViolationError("paper named graph returned unverified status")
        return empty(result.status)

    # PaperTypedToolPlan expresses a SINGLE dependency DAG, not a bag of
    # unrelated alternative paths whose bindings could be mixed accidentally.
    if len(result.candidates) != 1:
        route_sets = [
            (c.producer_route_id, c.consumer_route_id) if hops == 1
            else c.route_ids for c in result.candidates
        ]
        if len(set(route for path in route_sets for route in path)) > k:
            return empty("over_k_unranked")
        return empty("ambiguous_paths")

    candidate = result.candidates[0]
    if hops == 1:
        route_ids = (candidate.producer_route_id, candidate.consumer_route_id)
        binding_maps = (
            (),
            tuple((param, route_ids[0], source_field)
                  for param, source_field in candidate.parameter_bindings),
        )
        visible_fields = (
            tuple(field for _, field in candidate.parameter_bindings),
            candidate.consumer_output_fields,
        )
        pinned = (
            (candidate.producer_tool_fingerprint,
             candidate.producer_endpoint_fingerprint),
            (candidate.consumer_tool_fingerprint,
             candidate.consumer_endpoint_fingerprint),
        )
    else:
        route_ids = candidate.route_ids
        binding_maps = (
            (),
            tuple((param, route_ids[0], field)
                  for param, field in candidate.root_to_intermediate),
            tuple((param, route_ids[1], field)
                  for param, field in candidate.intermediate_to_target),
        )
        visible_fields = (
            tuple(field for _, field in candidate.root_to_intermediate),
            tuple(field for _, field in candidate.intermediate_to_target),
            candidate.target_output_fields,
        )
        pinned = candidate.route_fingerprints

    if (
        len(route_ids) != len(set(route_ids))
        or len(route_ids) > k
        or len(route_ids) != len(binding_maps)
    ):
        raise PolicyViolationError("paper named graph produced invalid typed routes")
    if host_source_arguments is not None and set(host_inputs) != {route_ids[0]}:
        raise PolicyViolationError("paper named graph host inputs are not its source root")
    # G5 proves typed links, but its target FieldGroup qualifier does not
    # constrain upstream source/license. Do not weaken an explicit model
    # source constraint or the owner-reviewed license along dependencies.
    for route_id in route_ids:
        location = index.field_index.route_locations.get(route_id)
        if location is None:
            raise PolicyViolationError("paper named graph original route missing")
        source_tool = router.registry.get(location[0])
        if (
            source_tool.license != group.license
            or approved.source_type is not None
            and source_tool.source_type != approved.source_type
        ):
            return empty("no_proven_hit")
    route_receipts = tuple(PaperFieldRoute(
        route_id=route_id, tool_fingerprint=fingerprints[0],
        endpoint_fingerprint=fingerprints[1],
        output_fields=tuple(dict.fromkeys(names)),
        covered_semantic_ids=(
            tuple(field.semantic_id for field in group.required_fields)
            if pos == len(route_ids) - 1 else ()
        ),
        input_bindings=tuple(binding_maps[pos]),
    ) for pos, (route_id, fingerprints, names) in enumerate(
        zip(route_ids, pinned, visible_fields, strict=True)
    ))

    permitted = router._authorization_predicate(principal)
    if permitted is None:
        raise PolicyViolationError("paper named graph lacks current source policy")

    def materialize() -> tuple[tuple[PaperPlanCall, ...], tuple[PaperPlanBinding, ...]]:
        positions = {route.route_id: i for i, route in enumerate(route_receipts)}
        by_route = {route.route_id: route for route in route_receipts}
        edges: list[PaperPlanBinding] = []
        calls = tuple(_compile_one_route(
            router, principal, index, route, pos, positions, by_route,
            edges, permitted,
            host_inputs.get(route.route_id) if pos == 0 else None,
        ) for pos, route in enumerate(route_receipts))
        _check_current_call_scopes(router, principal, list(calls))
        if len(edges) != len(tuple(b for pairs in binding_maps for b in pairs)):
            raise PolicyViolationError("paper named graph original bindings incomplete")
        return calls, tuple(edges)

    try:
        first_calls, first_edges = materialize()
        if lookup(hops) != result or materialize() != (first_calls, first_edges):
            raise PolicyViolationError("paper named graph source proof changed")
        _check_current_call_scopes(router, principal, list(first_calls))
    except Exception:
        raise PolicyViolationError("paper named graph source eligibility changed") from None
    verify_current()
    return PaperTypedToolPlan(
        status="requires_observation", snapshot_id=result.index_snapshot_id,
        registry_version=result.registry_version, requested_k=k,
        calls=first_calls, bindings=first_edges,
    )
