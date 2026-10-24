"""Opt-in original-paper required-field *union* before bounded K5 disclosure.

Composes the existing source-attested concept/field group retriever and
existing typed shared-root graph proof. It does NOT add a new index,
agent loop, inferred alias, executable call or default routing mode.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

from .authorization import PrincipalContext
from .concept_graph_retrieval import retrieve_authorized_concept_graph
from .concept_retrieval import NativeConceptCatalog, resolve_native_concepts
from .errors import PolicyViolationError
from .field_group_retrieval import _complete_fields
from .host_field_contract import _policy_contents_digest
from .native_graph_index import NativeSchemaGraphIndex

if TYPE_CHECKING:
    from .runtime import SchemaRouter


@dataclass(frozen=True, slots=True)
class PaperFieldRoute:
    """Read-only discovery receipt: necessary original field names for a route."""

    route_id: str
    tool_fingerprint: str
    endpoint_fingerprint: str
    output_fields: tuple[str, ...]
    covered_semantic_ids: tuple[str, ...]
    # Each bound input has explicit original producer route and output field.
    input_bindings: tuple[tuple[str, str, str], ...] = ()


@dataclass(frozen=True, slots=True)
class PaperFieldAlternative:
    """One complete source-attested direct, one-hop or two-consumer fork."""

    routes: tuple[PaperFieldRoute, ...]
    required_semantic_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class PaperFieldCoverage:
    """Opt-in, non-executing field-complete alternatives, never partial hits."""

    status: Literal[
        "complete", "no_proven_hit", "over_k_unranked", "budget_unsatisfied",
    ]
    snapshot_id: str
    registry_version: int
    requested_k: int
    alternatives: tuple[PaperFieldAlternative, ...] = ()
    independent_quality_evidence: bool = False
    executable_authority: bool = False


def retrieve_paper_field_coverage(
    router: SchemaRouter,
    query: str,
    *,
    principal: PrincipalContext,
    catalog: NativeConceptCatalog,
    index: NativeSchemaGraphIndex,
    k: int = 5,
) -> PaperFieldCoverage:
    """Prove required response fields BEFORE exposing any K5 route menu.

    Direct field-complete endpoints and attested one-hop routes reuse the
    existing concept/G5 implementation. Field splits require 2–4 qualified
    consumers of ONE original source-owned record ID; arbitrary tools
    cannot be merged based on field-name similarity or shared query text.

    An outcome of no_proven_hit is **not calibrated unsupported**.
    """
    if type(k) is not int or k != 5:
        raise ValueError("paper field proof requires exact K5")
    if not isinstance(principal, PrincipalContext):
        raise PolicyViolationError("paper field proof requires trusted principal")
    if not isinstance(catalog, NativeConceptCatalog):
        raise ValueError("paper field proof requires owner-reviewed concept catalog")
    if not isinstance(index, NativeSchemaGraphIndex):
        raise ValueError("paper field proof requires original typed graph index")

    witness = router._retrieval_authority_witness()
    policy = router.authorization_policy
    if policy is None:
        raise PolicyViolationError("paper field proof requires explicit source policy")
    policy_digest = _policy_contents_digest(policy)
    try:
        principal_digest = principal.model_dump_json()
        catalog_digest = catalog.model_dump_json()
    except (TypeError, ValueError, OverflowError, AttributeError) as exc:
        raise ValueError("paper field proof cannot freeze declaration") from exc

    # Exact owner-declared aliases only; no guessed/translated semantic ID.
    declared = resolve_native_concepts(query, catalog=catalog)
    group = declared.field_group
    required = tuple(field.semantic_id for field in group.required_fields)
    if not required or len(set(required)) != len(required):
        raise ValueError("ambiguous original required semantic fields")

    current = retrieve_authorized_concept_graph(
        router, query, principal=principal, catalog=catalog, index=index, k=k,
    )
    if current.status == "complete":
        raw_alternatives = []
        for route_set in current.route_sets:
            inputs = {}
            if len(route_set.route_ids) == 2:
                for parameter, source_field in route_set.parameter_bindings:
                    inputs.setdefault(route_set.route_ids[1], []).append(
                        (parameter, route_set.route_ids[0], source_field)
                    )
            raw_alternatives.append((
                route_set.route_ids,
                route_set.route_fingerprints,
                inputs,
            ))
        status = "complete"
    elif current.status in ("over_k_unranked", "budget_unsatisfied"):
        raw_alternatives = []
        status = current.status
    elif 2 <= len(group.required_fields) <= k - 1:
        fork = index.lookup_shared_root_forks(
            router, query, principal=principal, group=group, k=k,
        )
        if (
            fork.registry_version != witness[1]
            or fork.index_snapshot_id != index.field_index.snapshot_id
            or fork.requested_k != k
            or fork.executable_authority
        ):
            raise PolicyViolationError("original shared-root proof changed")
        status = fork.status
        raw_alternatives = []
        if status == "complete":
            for candidate in fork.candidates:
                root = candidate.root_route_id
                branches = candidate.branch_route_ids
                raw_alternatives.append((
                    (root, *branches),
                    (
                        (root, *candidate.root_fingerprints),
                        *(
                            (branch, *fingerprint)
                            for branch, fingerprint in zip(
                                branches, candidate.branch_fingerprints, strict=True,
                            )
                        ),
                    ),
                    {
                        branch: [(
                            parameter, root, candidate.root_identifier_field,
                        )]
                        for branch, parameter in zip(
                            branches, candidate.branch_input_parameters, strict=True,
                        )
                    },
                ))
    else:
        status = "no_proven_hit"
        raw_alternatives = []

    permitted = router._authorization_predicate(principal)
    if permitted is None:
        raise PolicyViolationError("original source visibility missing")

    # Reuse the SAME current-source projection in the final safety pass.
    # Live health/data scope can change without an endpoint fingerprint or
    # callable identity change while another branch is being inspected.
    def project_route(route_id, pinned, bindings) -> PaperFieldRoute:
        location = index.field_index.route_locations.get(route_id)
        if location is None or route_id not in pinned:
            raise PolicyViolationError("required-field route not in original index")
        tool = router.registry.get(location[0])
        endpoint = tool.endpoint(location[1])
        if (
            (tool.fingerprint, endpoint.fingerprint) != pinned[route_id]
            or index.field_index.route_fingerprints.get(route_id) != pinned[route_id]
            or not permitted(tool, endpoint)
            or endpoint.read_only is not True
            or endpoint.destructive is True
        ):
            raise PolicyViolationError("original required-field route invalid")
        availability = router.planner.availability_predicate
        if availability is not None and not availability(tool, endpoint):
            raise PolicyViolationError("original required-field route revoked")
        visible = router._data_scope_endpoint_view(principal, tool, endpoint)
        if visible is None:
            raise PolicyViolationError("original required-field route hidden")
        matched = {
            f.name for f in visible.output_fields
            if any(
                _complete_fields([f], (demand,))
                for demand in group.required_fields
            )
        }
        semantic_hits = {
            demand.semantic_id for demand in group.required_fields
            if _complete_fields(visible.output_fields, (demand,))
        }
        required_source = {
            source_field
            for pairs in bindings.values()
            for _parameter, from_route, source_field in pairs
            if from_route == route_id
        }
        visible_names = {field.name for field in visible.output_fields}
        if not required_source.issubset(visible_names):
            raise PolicyViolationError("required producer identifier now hidden")
        selected = tuple(
            field.name for field in visible.output_fields
            if field.identifier or field.name in matched
            or field.name in required_source
        )
        if not selected:
            raise PolicyViolationError("no source-visible required output")
        return PaperFieldRoute(
            route_id=route_id,
            tool_fingerprint=tool.fingerprint,
            endpoint_fingerprint=endpoint.fingerprint,
            output_fields=selected,
            covered_semantic_ids=tuple(
                demand for demand in required if demand in semantic_hits
            ),
            input_bindings=tuple(bindings.get(route_id, ())),
        )

    # Pre-publication projection is computed from CURRENT scoped originals,
    # not public aliases, planner score or detached benchmark fixture gold.
    projected_alternatives: list[PaperFieldAlternative] = []
    published_routes: set[str] = set()
    try:
        for route_ids, fingerprints, bindings in raw_alternatives:
            if len(route_ids) != len(set(route_ids)):
                raise PolicyViolationError("duplicate original route in required-field set")
            pinned = {route: (tool_fp, endpoint_fp)
                      for route, tool_fp, endpoint_fp in fingerprints}
            routes = [project_route(route_id, pinned, bindings) for route_id in route_ids]
            covered = {
                semantic_id for route in routes for semantic_id in route.covered_semantic_ids
            }
            if set(required) != covered:
                raise PolicyViolationError("incomplete source-visible required field union")
            projected_alternatives.append(PaperFieldAlternative(
                routes=tuple(routes), required_semantic_ids=required,
            ))
            published_routes.update(route_ids)

        # A second observation, not an atomic transaction with the provider.
        # Abort rather than publish a stale original field projection.
        for (_ids, fingerprints, bindings), alternative in zip(
            raw_alternatives, projected_alternatives, strict=True,
        ):
            pinned = {route: (tool_fp, endpoint_fp)
                      for route, tool_fp, endpoint_fp in fingerprints}
            for receipt in alternative.routes:
                if project_route(receipt.route_id, pinned, bindings) != receipt:
                    raise PolicyViolationError("original required-field projection changed")
    except Exception:
        # Host callbacks can raise messages containing private route details.
        raise PolicyViolationError(
            "original required-field source eligibility changed"
        ) from None

    # A route repeated by alternatives still consumes only one budget slot.
    # No lexicographic truncation of valid alternatives or backfilling.
    if len(published_routes) > k:
        status = "over_k_unranked"
        projected_alternatives = []
    if status != "complete":
        projected_alternatives = []
    index.field_index._assert_source(router)
    router._check_retrieval_authority_witness(witness)
    if (
        router.authorization_policy is None
        or _policy_contents_digest(router.authorization_policy) != policy_digest
        or principal.model_dump_json() != principal_digest
        or catalog.model_dump_json() != catalog_digest
    ):
        raise PolicyViolationError("required-field source or owner declaration changed")

    return PaperFieldCoverage(
        status=status,
        snapshot_id=index.field_index.snapshot_id,
        registry_version=witness[1],
        requested_k=k,
        alternatives=tuple(projected_alternatives),
    )
