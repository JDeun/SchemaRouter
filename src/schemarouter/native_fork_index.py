"""#1560 E0: strictly source-attested shared-root field evidence.

This is a bounded, nonexecuting AND over 2–4 already-authorized one-hop
native G5 results. A common source schema is not a runtime row join.
"""
from __future__ import annotations

from dataclasses import dataclass
from itertools import product
from typing import TYPE_CHECKING, Literal

from .authorization import PrincipalContext
from .errors import PolicyViolationError
from .field_group_retrieval import NativeDeclaredFieldGroup, _alias_key
from .native_graph_index import (
    MAX_RESEARCH_RANKABLE_PATHS,
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
# Structural-only prepartitioning is worthwhile for bounded dense ROOT
# cohorts; it does not attest a single route or replace scoped validation.
MAX_FORK_PREFORK_TARGETS = 128
MIN_FORK_PREFORK_BUDGET = 16
# Never enumerate an unbounded Cartesian product of individually attested
# consumers. Exhaustion is an unranked abstention, NOT a negative result.
MAX_FORK_COMBINATIONS = 4096


@dataclass(frozen=True, slots=True)
class NativeIndexedSharedRootForkCandidate:
    """All single-field consumers bind the SAME flat, source-owned root ID."""

    root_route_id: str
    branch_route_ids: tuple[str, ...]
    root_fingerprints: tuple[str, str]
    branch_fingerprints: tuple[tuple[str, str], ...]
    root_identifier_field: str
    branch_input_parameters: tuple[str, ...]
    branch_output_fields: tuple[tuple[str, ...], ...]


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
    """Conservative 2–4-field same-record fork evidence before strict K5.

    No inferred multi-output, concatenated rows, cross-source equality, or
    execution: all branches must have one identical original source root and
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
    if not 2 <= len(declared.required_fields) <= k - 1:
        raise ValueError("G5 fork supports two to four declared semantic fields")
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

    shared_structural_roots = frozenset(set.intersection(*(
        potential_roots(i) for i in range(len(declared.required_fields))
    )))

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
            targets: frozenset[str] | None = None,
        ) -> tuple[NativeIndexedGraphCandidate, ...] | None:
            nonlocal attempts
            # Index-only private scheduling optimization: a single original
            # root with a bounded number of structurally attached consumers
            # may be split BEFORE the first >32 verified witness scan.
            # Split nodes count against the same private attempt budget.
            # Every leaf is still checked by the ORIGINAL authorized path;
            # no grant/count/candidate is inferred from these postings.
            if (
                len(roots) == 1
                and MAX_FORK_SHARD_LOOKUPS >= MIN_FORK_PREFORK_BUDGET
            ):
                if targets is None:
                    posting = index.field_index.postings.get(
                        declared.required_fields[required_field_index].semantic_id,
                        (),
                    )
                    matched = sorted(
                        route for route in posting
                        if route in index.edge_consumer_routes
                        and any(
                            root in roots for root in index.graph.predecessors(route)
                        )
                    )
                else:
                    matched = sorted(targets)
                if (
                    MAX_RESEARCH_RANKABLE_PATHS < len(matched)
                    <= MAX_FORK_PREFORK_TARGETS
                ):
                    attempts += 1
                    if attempts > MAX_FORK_SHARD_LOOKUPS:
                        return None
                    midpoint = len(matched) // 2
                    first_shard = collect(
                        roots, frozenset(matched[:midpoint]),
                    )
                    if first_shard is None:
                        return None
                    second_shard = collect(
                        roots, frozenset(matched[midpoint:]),
                    )
                    return (
                        None if second_shard is None
                        else first_shard + second_shard
                    )

            attempts += 1
            if attempts > MAX_FORK_SHARD_LOOKUPS:
                # Never claim no-fit or release partially collected arms.
                return None
            result = index._lookup_native_paths(
                router, query, group=sub_group, principal=actor, k=k,
                _fork_arm_internal=True, _fork_root_filter=roots,
                _fork_target_filter=targets,
            )
            if result.status == "over_k_unranked":
                # First split disjoint source-root IDs, preserving original
                # source-scoped lookup and the 32-path per-query budget.
                if len(roots) >= 2:
                    ordered = sorted(roots)
                    midpoint = len(ordered) // 2
                    before = collect(frozenset(ordered[:midpoint]), targets)
                    if before is None:
                        return None
                    after = collect(frozenset(ordered[midpoint:]), targets)
                    return None if after is None else before + after

                # A SINGLE source root may feed >32 one-hop consumers via
                # *different typed identifiers*. Subdivide only existing
                # source-indexed consumer route IDs, not public candidates.
                # The target postings form a structural SUPerset; all of
                # source versions, permission, scope, health and typed
                # bindings are rechecked inside every private query.
                if targets is None:
                    indexed = index.field_index.postings.get(
                        declared.required_fields[required_field_index].semantic_id,
                        (),
                    )
                    candidates = frozenset(
                        target_id for target_id in indexed
                        if target_id in index.edge_consumer_routes
                        and any(
                            root_id in roots for root_id in
                            index.graph.predecessors(target_id)
                        )
                    )
                else:
                    candidates = targets
                if len(candidates) < 2:
                    return None
                ordered = sorted(candidates)
                midpoint = len(ordered) // 2
                before = collect(roots, frozenset(ordered[:midpoint]))
                if before is None:
                    return None
                after = collect(roots, frozenset(ordered[midpoint:]))
                return None if after is None else before + after

            if result.status == "no_proven_hit":
                return ()
            if result.status not in ("complete", "internal_fork_arm"):
                raise PolicyViolationError("G5 fork unsupported one-hop evidence")
            return result.candidates

        return collect(shared_structural_roots)

    def compatible_group(
        branches: tuple[NativeIndexedGraphCandidate, ...],
    ) -> NativeIndexedSharedRootForkCandidate | None:
        first = branches[0]
        if (
            len({item.consumer_route_id for item in branches}) != len(branches)
            or any(
                item.producer_route_id != first.producer_route_id
                or item.source_root_parameters
                or len(item.parameter_bindings) != 1
                or item.parameter_bindings[0][1] != first.parameter_bindings[0][1]
                or item.producer_tool_fingerprint != first.producer_tool_fingerprint
                or item.producer_endpoint_fingerprint
                != first.producer_endpoint_fingerprint
                for item in branches
            )
        ):
            return None
        root_id = first.producer_route_id
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
        # the root and ALL consumers must share reviewed provenance and
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
        # All consumers must require the same original semantic contract,
        # not two unrelated semantic IDs mapped onto an identical spelling.
        required_identifiers = []
        for branch in branches:
            leaf_id = branch.consumer_route_id
            required_parameter = branch.parameter_bindings[0][0]
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
        if any(value != required_identifiers[0] for value in required_identifiers[1:]):
            return None
        source_identifier = first.parameter_bindings[0][1]
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
            branch_route_ids=tuple(branch.consumer_route_id for branch in branches),
            root_fingerprints=pinned,
            branch_fingerprints=tuple(
                (branch.consumer_tool_fingerprint,
                 branch.consumer_endpoint_fingerprint)
                for branch in branches
            ),
            root_identifier_field=source_identifier,
            branch_input_parameters=tuple(
                branch.parameter_bindings[0][0] for branch in branches
            ),
            branch_output_fields=tuple(
                branch.consumer_output_fields for branch in branches
            ),
        )

    try:
        arms = tuple(authorized_leaf(i) for i in range(len(declared.required_fields)))
        # Each private query retains the original 32-arm cap; disjoint root
        # shards can be combined after full validation, within a bounded
        # number of source queries. Public K5 applies ONLY to joined forks.
        overflowing = any(arm is None for arm in arms)
        pairs: set[NativeIndexedSharedRootForkCandidate] = set()
        if not overflowing:
            by_root: list[dict[str, list[NativeIndexedGraphCandidate]]] = []
            for arm in arms:
                current: dict[str, list[NativeIndexedGraphCandidate]] = {}
                assert arm is not None
                for candidate in arm:
                    current.setdefault(candidate.producer_route_id, []).append(candidate)
                by_root.append(current)
            attempted = 0
            shared_roots = set.intersection(*(set(arm) for arm in by_root))
            for root in sorted(shared_roots):
                for joined in product(*(arm[root] for arm in by_root)):
                    attempted += 1
                    if attempted > MAX_FORK_COMBINATIONS:
                        overflowing = True
                        break
                    qualified = compatible_group(joined)
                    if qualified is not None:
                        pairs.add(qualified)
                if overflowing:
                    break
        # Separate G5 queries may span a live health/scope mutation.
        # Repeat ALL original projections before publishing fork identities
        # or even the count. This is conservative but not a transaction or
        # proof of linearizable provider revocation across hosts.
        refreshed = tuple(authorized_leaf(i) for i in range(len(arms)))
        if refreshed != arms:
            raise PolicyViolationError("G5 fork source eligibility changed")
    except Exception:
        raise PolicyViolationError(
            "G5 fork eligibility changed during lookup"
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
