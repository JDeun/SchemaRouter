"""Opt-in host-declared concept to complete, authorized native route sets.

The result is only a scoped *discovery* receipt. No source calls, tool
execution rights, learned ranking, or undeclared joins originate here.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

from .authorization import PrincipalContext
from .concept_retrieval import (
    NativeConceptCatalog,
    resolve_native_concepts,
)
from .errors import PolicyViolationError
from .field_group_retrieval import (
    _root_envelope_empty,
    retrieve_authorized_field_group,
)
from .native_graph_index import NativeSchemaGraphIndex

if TYPE_CHECKING:
    from .runtime import SchemaRouter


@dataclass(frozen=True, slots=True)
class NativeConceptRouteSet:
    """One fully proved direct endpoint or producer/consumer join."""

    route_ids: tuple[str, ...]
    route_fingerprints: tuple[tuple[str, str, str], ...]
    required_semantic_ids: tuple[str, ...]
    # Native (consumer parameter, original producer field) bindings.
    parameter_bindings: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True, slots=True)
class NativeConceptGraphSelection:
    """Safe scoped menu selection; always nonexecuting and uncalibrated."""

    status: Literal[
        "complete", "no_proven_hit", "over_k_unranked", "budget_unsatisfied",
    ]
    snapshot_id: str
    registry_version: int
    requested_k: int
    route_sets: tuple[NativeConceptRouteSet, ...]
    route_ids: tuple[str, ...]
    independent_quality_evidence: bool = False
    calibrated_no_fit: bool = False
    executable_authority: bool = False


def retrieve_authorized_concept_graph(
    router: SchemaRouter,
    query: str,
    *,
    principal: PrincipalContext,
    catalog: NativeConceptCatalog,
    index: NativeSchemaGraphIndex,
    k: int = 5,
) -> NativeConceptGraphSelection:
    """Compose current, owner-declared FieldGroup and canonical typed G5.

    A complete one-endpoint alternative takes precedence over one-hop paths.
    The public limit is the number of DISTINCT source-native route IDs in
    the whole menu, not the count of join paths. Ambiguous overflow abstains.
    """
    if type(k) is not int or k != 5:
        raise ValueError("concept graph selection requires strict K5")
    if not isinstance(index, NativeSchemaGraphIndex):
        raise ValueError("current native graph index required")
    # These validations precede *any* query against the source catalog.
    witness = router._retrieval_authority_witness()
    index.field_index._assert_source(router)
    if index.field_index.registry_version != witness[1]:
        raise PolicyViolationError("concept graph index revision mismatch")
    policy = router.authorization_policy
    if policy is None:
        raise PolicyViolationError("concept graph requires explicit authorization")
    policy_content = (
        policy.default_effect, repr(policy.rules), repr(policy.data_rules),
    )
    if not isinstance(catalog, NativeConceptCatalog):
        raise ValueError("owner-reviewed concept catalog required")
    try:
        frozen_catalog = catalog.model_dump_json()
    except (TypeError, ValueError, OverflowError, AttributeError) as exc:
        raise ValueError("concept catalog changed during validation") from exc
    resolved = resolve_native_concepts(query, catalog=catalog)
    required = tuple(field.semantic_id for field in resolved.field_group.required_fields)

    direct = retrieve_authorized_field_group(
        router, query, principal=principal, group=resolved.field_group, k=k,
        input_free_only=True,
    )
    if direct.registry_version != witness[1] or direct.requested_k != k:
        raise PolicyViolationError("concept direct source revision mismatch")
    # Lookup both existing verified paths under one principal and one source
    # witness. Never traverse internal unscoped graph postings ourselves.
    graph = index.lookup(
        router, query, principal=principal, group=resolved.field_group, k=k,
    )
    if graph.registry_version != witness[1] or graph.requested_k != k:
        raise PolicyViolationError("concept graph source revision mismatch")

    selected: tuple[NativeConceptRouteSet, ...] = ()
    status: Literal[
        "complete", "no_proven_hit", "over_k_unranked", "budget_unsatisfied",
    ] = "no_proven_hit"
    # A field-complete endpoint with required arguments is NOT a direct
    # single-call answer. FieldGroup proves outputs, not input provenance.
    # Such a consumer must instead arrive through canonical typed G5 joins.
    direct_roots = []
    for candidate in direct.candidates:
        location = index.field_index.route_locations.get(candidate.route_id)
        if location is None:
            raise PolicyViolationError("concept direct route missing from source")
        tool_key, endpoint_name = location
        endpoint = router.registry.get(tool_key).endpoint(endpoint_name)
        if _root_envelope_empty(endpoint):
            direct_roots.append(candidate)

    # A host-owned availability predicate may keep the SAME callable identity
    # while changing its live health set during graph evaluation. In that
    # case the earlier direct FieldGroup menu must not be disclosed unchanged.
    if direct_roots:
        renewed = retrieve_authorized_field_group(
            router, query, principal=principal, group=resolved.field_group, k=k,
            input_free_only=True,
        )
        eligible_now = []
        for candidate in renewed.candidates:
            location = index.field_index.route_locations.get(candidate.route_id)
            if location is None:
                raise PolicyViolationError("concept direct source changed")
            tool_key, endpoint_name = location
            if _root_envelope_empty(router.registry.get(tool_key).endpoint(endpoint_name)):
                eligible_now.append(candidate)
        original_receipts = tuple(sorted(
            (candidate.route_id, candidate.tool_fingerprint,
             candidate.endpoint_fingerprint) for candidate in direct_roots
        ))
        refreshed_receipts = tuple(sorted(
            (candidate.route_id, candidate.tool_fingerprint,
             candidate.endpoint_fingerprint) for candidate in eligible_now
        ))
        if (
            renewed.registry_version != direct.registry_version
            or renewed.total_ranked != direct.total_ranked
            or refreshed_receipts != original_receipts
        ):
            raise PolicyViolationError("concept direct eligibility changed during lookup")

    if direct.total_ranked > k:
        status = "over_k_unranked"
    elif direct_roots:
        selected = tuple(NativeConceptRouteSet(
            route_ids=(candidate.route_id,),
            route_fingerprints=((candidate.route_id,
                                 candidate.tool_fingerprint,
                                 candidate.endpoint_fingerprint),),
            required_semantic_ids=required,
        ) for candidate in direct_roots)
        status = "complete"
    elif graph.status == "over_k_unranked":
        status = "over_k_unranked"
    elif graph.status == "complete":
        selected = tuple(NativeConceptRouteSet(
            route_ids=(c.producer_route_id, c.consumer_route_id),
            route_fingerprints=(
                (c.producer_route_id, c.producer_tool_fingerprint,
                 c.producer_endpoint_fingerprint),
                (c.consumer_route_id, c.consumer_tool_fingerprint,
                 c.consumer_endpoint_fingerprint),
            ),
            required_semantic_ids=required,
            parameter_bindings=c.parameter_bindings,
        ) for c in graph.candidates)
        status = "complete" if selected else "no_proven_hit"

    # A route repeated by six paths consumes only one model menu slot; six
    # consumer alternatives, however, cannot be silently truncated at K5.
    routes = tuple(dict.fromkeys(
        route_id for route_set in selected for route_id in route_set.route_ids
    ))
    if len(routes) > k:
        selected = ()
        routes = ()
        status = "over_k_unranked"

    # The original graph/index snapshot and each exposed route fingerprint
    # must match the actual registered source, even after both lookups.
    for route_set in selected:
        for route_id, tool_fp, endpoint_fp in route_set.route_fingerprints:
            if index.field_index.route_fingerprints.get(route_id) != (
                tool_fp, endpoint_fp,
            ):
                raise PolicyViolationError("concept graph native fingerprint drift")
    index.field_index._assert_source(router)
    router._check_retrieval_authority_witness(witness)
    current_policy = router.authorization_policy
    if current_policy is None or (
        current_policy.default_effect,
        repr(current_policy.rules),
        repr(current_policy.data_rules),
    ) != policy_content:
        raise PolicyViolationError("concept graph authorization changed")
    try:
        if catalog.model_dump_json() != frozen_catalog:
            raise PolicyViolationError("concept catalog changed during lookup")
    except (TypeError, ValueError, OverflowError, AttributeError) as exc:
        raise PolicyViolationError("concept catalog changed during lookup") from exc

    return NativeConceptGraphSelection(
        status=status,
        snapshot_id=index.field_index.snapshot_id,
        registry_version=witness[1],
        requested_k=k,
        route_sets=selected,
        route_ids=routes,
    )
