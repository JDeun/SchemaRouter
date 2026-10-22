"""#1560 E0: strictly source-attested two-branch shared-root field evidence.

This is a bounded, nonexecuting AND over TWO already-authorized one-hop
native G5 results. A common source schema is not a runtime row join.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

from .authorization import PrincipalContext
from .errors import PolicyViolationError
from .field_group_retrieval import NativeDeclaredFieldGroup, _alias_key
from .native_graph_index import (
    STRICT_K,
    NativeIndexedGraphCandidate,
    _flat_same_record_source_contract,
    _native_required_inputs,
)

if TYPE_CHECKING:
    from .native_graph_index import NativeSchemaGraphIndex
    from .runtime import SchemaRouter


# Max private source-validated subqueries per arm and live-recheck pass.
# This is a computational fail-closed budget, NOT a public K or ranker.
MAX_FORK_SHARD_LOOKUPS = 64


@dataclass(frozen=True, slots=True)
class NativeIndexedSharedRootForkCandidate:
    """Both single-field consumers bind the SAME flat, source-owned root ID."""

    root_route_id: str
    branch_route_ids: tuple[str, str]
    root_fingerprints: tuple[str, str]
    branch_fingerprints: tuple[tuple[str, str], tuple[str, str]]
    root_identifier_field: str
    branch_input_parameters: tuple[str, str]
    branch_output_fields: tuple[tuple[str, ...], tuple[str, ...]]


@dataclass(frozen=True, slots=True)
class NativeIndexedSharedRootForkResult:
    status: Literal["complete", "no_proven_hit", "over_k_unranked"]
    index_snapshot_id: str
    registry_version: int
    requested_k: int
    qualified_fork_count: int
    candidates: tuple[NativeIndexedSharedRootForkCandidate, ...]
    independent_quality_evidence: bool = False
    calibrated_no_fit: bool = False
    executable_authority: bool = False


def lookup_native_shared_root_forks(
    index: NativeSchemaGraphIndex,
    router: SchemaRouter,
    query: str,
    *,
    group: NativeDeclaredFieldGroup,
    principal: PrincipalContext,
    k: int = STRICT_K,
) -> NativeIndexedSharedRootForkResult:
    """Conservative two-field, two-consumer fork evidence before strict K5.

    No inferred multi-output, concatenated rows, cross-source equality, or
    execution: both branches must have one identical original source root and
    one *same-named* scalar root identifier, required at the original root
    object schema. Each scoped leaf must independently prove ONE demanded
    field via the existing authorized/typed one-hop native G5 path.
    """
    if type(k) is not int or k != STRICT_K:
        raise ValueError("G5 fork requires fixed K5")
    if not isinstance(group, NativeDeclaredFieldGroup):
        raise ValueError("G5 fork requires approved FieldGroup")
    if not isinstance(principal, PrincipalContext):
        raise PolicyViolationError("G5 fork requires explicit principal")
    if type(query) is not str or len(query.encode("utf-8")) > 512:
        raise ValueError("G5 fork requires bounded query")
    try:
        declared = NativeDeclaredFieldGroup.model_validate(
            group.model_dump(mode="python"), strict=True,
        )
        actor = PrincipalContext.model_validate(
            principal.model_dump(mode="python"), strict=True,
        )
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError("G5 fork invalid current host declarations") from exc
    if len(declared.required_fields) != 2:
        raise ValueError("G5 fork supports exactly two declared semantic fields")
    if _alias_key(query) not in {_alias_key(a) for a in declared.aliases}:
        raise ValueError("G5 fork has no approved query-to-field edge")

    index.field_index._assert_source(router)
    policy = router.authorization_policy
    if policy is None:
        raise PolicyViolationError("G5 fork requires authorization policy")
    witness = router._retrieval_authority_witness()
    policy_snapshot = (
        policy.default_effect, repr(policy.rules), repr(policy.data_rules),
    )

    # Read only the existing indexed semantic postings and canonical typed
    # adjacency, NOT an unscoped registry scan or caller-supplied target IDs.
    # This is a conservative structural superset; source authorization,
    # field visibility, health and fingerprints are checked as before.
    def potential_roots(required_field_index: int) -> set[str]:
        targets = set(index.field_index.postings.get(
            declared.required_fields[required_field_index].semantic_id, (),
        ))
        targets.intersection_update(index.edge_consumer_routes)
        return {
            root_id
            for target_id in targets
            for root_id in index.graph.predecessors(target_id)
        }

    shared_structural_roots = frozenset(potential_roots(0) & potential_roots(1))

    def authorized_leaf(
        required_field_index: int,
    ) -> tuple[NativeIndexedGraphCandidate, ...] | None:
        sub_group = NativeDeclaredFieldGroup(
            aliases=declared.aliases,
            required_fields=(declared.required_fields[required_field_index],),
            source_type=declared.source_type,
            license=declared.license,
        )
        attempts = 0

        def collect(
            roots: frozenset[str],
        ) -> tuple[NativeIndexedGraphCandidate, ...] | None:
            nonlocal attempts
            attempts += 1
            if attempts > MAX_FORK_SHARD_LOOKUPS:
                # Never claim no-fit or release partially collected arms.
                return None
            result = index._lookup_native_paths(
                router, query, group=sub_group, principal=actor, k=k,
                _fork_arm_internal=True, _fork_root_filter=roots,
            )
            if result.status == "over_k_unranked":
                # A single private arm query remains limited to 32 verified
                # paths. Subdivide disjoint INDEXED ROOT IDs, not field
                # postings or privileged source state, until each fits.
                # One root exceeding 32 still conservatively abstains.
                if len(roots) < 2:
                    return None
                ordered = sorted(roots)
                midpoint = len(ordered) // 2
                before = collect(frozenset(ordered[:midpoint]))
                if before is None:
                    return None
                after = collect(frozenset(ordered[midpoint:]))
                return None if after is None else before + after
            if result.status == "no_proven_hit":
                return ()
            if result.status not in ("complete", "internal_fork_arm"):
                raise PolicyViolationError("G5 fork unsupported one-hop evidence")
            return result.candidates

        return collect(shared_structural_roots)

    def compatible_pair(
        left: NativeIndexedGraphCandidate,
        right: NativeIndexedGraphCandidate,
    ) -> NativeIndexedSharedRootForkCandidate | None:
        if (
            left.producer_route_id != right.producer_route_id
            or left.consumer_route_id == right.consumer_route_id
            or left.source_root_parameters
            or right.source_root_parameters
            or len(left.parameter_bindings) != 1
            or len(right.parameter_bindings) != 1
            or left.parameter_bindings[0][1]
            != right.parameter_bindings[0][1]
            or left.producer_tool_fingerprint
            != right.producer_tool_fingerprint
            or left.producer_endpoint_fingerprint
            != right.producer_endpoint_fingerprint
        ):
            return None
        root_id = left.producer_route_id
        where = index.field_index.route_locations.get(root_id)
        pinned = index.field_index.route_fingerprints.get(root_id)
        if where is None or pinned is None:
            raise PolicyViolationError("G5 fork missing pinned root")
        root_tool = router.registry.get(where[0])
        root_ep = root_tool.endpoint(where[1])
        if (root_tool.fingerprint, root_ep.fingerprint) != pinned:
            raise PolicyViolationError("G5 fork root source drift")
        # A common identifier does not authorize an unreviewed cross-owner
        # join. Even when the host leaves FieldGroup qualifiers unspecified,
        # the root and BOTH consumers must share a reviewed provenance and
        # license. Cross-publisher joins need a separate explicit contract.
        owner = (root_tool.source_type, root_tool.license)
        if (
            not all(owner)
            or declared.source_type is not None
            and owner[0] != declared.source_type
            or declared.license is not None
            and owner[1] != declared.license
        ):
            return None
        # A source field NAME is not a semantic identifier by itself.
        # Both consumers must require the same original semantic contract,
        # not two unrelated semantic IDs mapped onto an identical spelling.
        required_identifiers = []
        for leaf_id, required_parameter in (
            (left.consumer_route_id, left.parameter_bindings[0][0]),
            (right.consumer_route_id, right.parameter_bindings[0][0]),
        ):
            leaf_where = index.field_index.route_locations.get(leaf_id)
            leaf_pinned = index.field_index.route_fingerprints.get(leaf_id)
            if leaf_where is None or leaf_pinned is None:
                raise PolicyViolationError("G5 fork missing pinned consumer")
            leaf_tool = router.registry.get(leaf_where[0])
            leaf_ep = leaf_tool.endpoint(leaf_where[1])
            if (leaf_tool.fingerprint, leaf_ep.fingerprint) != leaf_pinned:
                raise PolicyViolationError("G5 fork consumer source drift")
            if (leaf_tool.source_type, leaf_tool.license) != owner:
                return None
            inputs = _native_required_inputs(leaf_ep)
            if (
                inputs is None or len(inputs) != 1
                or inputs[0][0] != required_parameter
            ):
                return None
            required_identifiers.append(inputs[0][1])
        if required_identifiers[0] != required_identifiers[1]:
            return None
        source_identifier = left.parameter_bindings[0][1]
        source_fields = [
            field for field in root_ep.output_fields
            if field.name == source_identifier
        ]
        if (
            len(source_fields) != 1
            or source_fields[0].identifier is not True
            or source_fields[0].semantic_id
            != required_identifiers[0].semantic_id
        ):
            # Two original fields with an identical JSON property name but
            # different semantic IDs are NOT one attested identifier.
            return None
        # A field declared on an array/nested/optional object is not a
        # source-owned single-record join key, even if semantic IDs match.
        if not _flat_same_record_source_contract(
            root_ep, root_ep, (source_identifier,),
        ):
            return None
        return NativeIndexedSharedRootForkCandidate(
            root_route_id=root_id,
            branch_route_ids=(
                left.consumer_route_id, right.consumer_route_id,
            ),
            root_fingerprints=pinned,
            branch_fingerprints=(
                (left.consumer_tool_fingerprint,
                 left.consumer_endpoint_fingerprint),
                (right.consumer_tool_fingerprint,
                 right.consumer_endpoint_fingerprint),
            ),
            root_identifier_field=source_identifier,
            branch_input_parameters=(
                left.parameter_bindings[0][0], right.parameter_bindings[0][0],
            ),
            branch_output_fields=(
                left.consumer_output_fields, right.consumer_output_fields,
            ),
        )

    try:
        left = authorized_leaf(0)
        right = authorized_leaf(1)
        # Each private query retains the original 32-arm cap; disjoint root
        # shards can be combined after full validation, within a bounded
        # number of source queries. Public K5 applies ONLY to joined forks.
        overflowing = left is None or right is None
        pairs: set[NativeIndexedSharedRootForkCandidate] = set()
        if left is not None and right is not None:
            right_by_root: dict[str, list[NativeIndexedGraphCandidate]] = {}
            for candidate in right:
                right_by_root.setdefault(candidate.producer_route_id, []).append(
                    candidate
                )
            for first in left:
                for second in right_by_root.get(first.producer_route_id, ()):
                    qualified = compatible_pair(first, second)
                    if qualified is not None:
                        pairs.add(qualified)
        # Two separate G5 queries may span a live health/scope mutation.
        # Repeat BOTH original projections before publishing fork identities
        # or even the count. This is conservative but not a transaction or
        # proof of linearizable provider revocation across hosts.
        fresh_left = authorized_leaf(0)
        fresh_right = authorized_leaf(1)
        if fresh_left != left or fresh_right != right:
            raise PolicyViolationError("G5 fork source eligibility changed")
    except Exception as exc:
        # TEMPORARY E0 CI diagnostic: code location only; never provider text.
        site = exc.__traceback__
        while site is not None and site.tb_next is not None:
            site = site.tb_next
        location = (
            f"{site.tb_frame.f_code.co_name}:{site.tb_lineno}"
            if site is not None else "unknown"
        )
        raise PolicyViolationError(
            f"G5 fork eligibility changed during lookup [{type(exc).__name__}:{location}]"
        ) from None

    index.field_index._assert_source(router)
    router._check_retrieval_authority_witness(witness)
    latest_policy = router.authorization_policy
    if latest_policy is None or (
        latest_policy.default_effect,
        repr(latest_policy.rules),
        repr(latest_policy.data_rules),
    ) != policy_snapshot:
        raise PolicyViolationError("G5 fork authorization rules changed")

    if overflowing:
        return NativeIndexedSharedRootForkResult(
            "over_k_unranked", index.field_index.snapshot_id,
            index.field_index.registry_version, k, 0, (),
        )
    count = len(pairs)
    ordered = tuple(sorted(
        pairs,
        key=lambda candidate: (
            candidate.root_route_id, candidate.branch_route_ids,
        ),
    ))
    return NativeIndexedSharedRootForkResult(
        "over_k_unranked" if count > k else
        "complete" if count else "no_proven_hit",
        index.field_index.snapshot_id, index.field_index.registry_version,
        k, count, ordered if count <= k else (),
    )
