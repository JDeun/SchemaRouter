"""Historical owner-ranked G5 lookups and comparators, checkout only.

Preserves ranked one-/two-hop proof, budget, and mixed-depth ordering.
Installed graph lookups retain unranked source evidence, never this policy.
"""
from __future__ import annotations

import heapq
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

from schemarouter.authorization import PrincipalContext
from schemarouter.errors import PolicyViolationError
from schemarouter.field_group_retrieval import (
    NativeDeclaredFieldGroup,
    _alias_key,
    _complete_fields,
    _root_envelope_empty,
)
from schemarouter.models import EndpointSpec, ToolSpec
from schemarouter.native_graph_index import (
    MAX_RESEARCH_RANKABLE_PATHS,
    STRICT_K,
    NativeIndexedGraphCandidate,
    NativeIndexedTwoHopCandidate,
    NativeSchemaGraphIndex,
    _flat_same_record_source_contract,
    _host_source_input_names,
    _native_required_inputs,
    _root_field,
)
from schemarouter.native_semantic_index import _NativeSourcePass
from scripts.research_legacy_direct_rank import PaperNativeRankPolicy

if TYPE_CHECKING:
    from schemarouter.runtime import SchemaRouter

MAX_OWNER_RANKABLE_PATHS = 5_000


@dataclass(frozen=True, slots=True)
class NativeIndexedGraphResult:
    status: Literal[
        "complete", "no_proven_hit", "over_k_unranked",
        "ranked_unverified",
        "budget_unsatisfied",
    ]
    index_snapshot_id: str
    registry_version: int
    requested_k: int
    qualified_path_count: int
    candidates: tuple[NativeIndexedGraphCandidate, ...]
    independent_quality_evidence: bool = False
    calibrated_no_fit: bool = False
    executable_authority: bool = False
    deterministic_paper_ranked: bool = False


@dataclass(frozen=True, slots=True)
class NativeIndexedTwoHopResult:
    status: Literal[
        "complete", "no_proven_hit", "over_k_unranked",
        "ranked_unverified", "budget_unsatisfied",
    ]
    index_snapshot_id: str
    registry_version: int
    requested_k: int
    qualified_path_count: int
    candidates: tuple[NativeIndexedTwoHopCandidate, ...]
    independent_quality_evidence: bool = False
    calibrated_no_fit: bool = False
    executable_authority: bool = False
    deterministic_paper_ranked: bool = False


def _concept_match_strength(
    visible_names: tuple[str, ...], concept_aliases: tuple[tuple[str, ...], ...],
) -> tuple[int, int]:
    names = tuple(_alias_key(name) for name in visible_names)
    exact = 0
    partial = 0
    for aliases in concept_aliases:
        best = 0
        for alias in aliases:
            normalized = _alias_key(alias)
            if not normalized:
                continue
            for name in names:
                if name == normalized:
                    best = 2
                    break
                if name in normalized or normalized in name:
                    best = max(best, 1)
            if best == 2:
                break
        exact += best == 2
        partial += best == 1
    # Strengthened typed comparator: exact matches dominate any partial count.
    # The historical paper comparator instead adds 2*exact + partial.
    return exact, partial


_MAX_RANKABLE_GRAPH_PATHS = 5_000


def _rank_verified_graph_paths(
    paths: tuple[tuple[tuple[str, ...], tuple[str, ...], int], ...],
    *,
    concept_aliases: tuple[tuple[str, ...], ...],
    policy: PaperNativeRankPolicy,
    k: int,
) -> tuple[int, ...]:
    """Rank complete, already authorized dependency DAGs, not isolated nodes."""
    if type(k) is not int or k != 5 or not isinstance(policy, PaperNativeRankPolicy):
        raise ValueError("G5 paper Rank requires K5 and reviewed owner policy")
    if len(paths) > _MAX_RANKABLE_GRAPH_PATHS:
        raise ValueError("G5 paper Rank exceeds 5000 qualified paths")
    identifiers = tuple(route_ids for route_ids, _, _ in paths)
    if len(set(identifiers)) != len(identifiers) or any(
        not route_ids or len(set(route_ids)) != len(route_ids)
        or breadth < 1
        for route_ids, _names, breadth in paths
    ):
        raise ValueError("G5 paper Rank requires distinct complete paths")

    web = set(policy.web_route_ids)

    def key(index: int) -> tuple[int, int, bool, int, int, int, tuple[str, ...]]:
        route_ids, names, breadth = paths[index]
        exact, partial = _concept_match_strength(names, concept_aliases)
        return (
            -exact, -partial, bool(web.intersection(route_ids)),
            -policy.route_priorities.get(route_ids[-1], 0),
            breadth, len(route_ids), route_ids,
        )

    return tuple(heapq.nsmallest(k, range(len(paths)), key=key))


def _one_hop_rank_receipt(
    candidate: NativeIndexedGraphCandidate,
) -> tuple[tuple[str, ...], tuple[str, ...], int]:
    return (
        (candidate.producer_route_id, candidate.consumer_route_id),
        candidate.consumer_output_fields,
        (
            candidate.producer_visible_field_count
            if candidate.producer_visible_field_count is not None
            else len(candidate.parameter_bindings)
        ) + (
            candidate.consumer_visible_field_count
            if candidate.consumer_visible_field_count is not None
            else len(candidate.consumer_output_fields)
        ) + len(candidate.parameter_bindings),
    )


def _two_hop_rank_receipt(
    candidate: NativeIndexedTwoHopCandidate,
) -> tuple[tuple[str, ...], tuple[str, ...], int]:
    return (
        candidate.route_ids, candidate.target_output_fields,
        (
            sum(candidate.visible_field_counts)
            if candidate.visible_field_counts is not None
            else (
                len(candidate.root_to_intermediate)
                + len(candidate.intermediate_to_target)
                + len(candidate.target_output_fields)
            )
        ) + len(candidate.root_to_intermediate)
        + len(candidate.intermediate_to_target),
    )


def rank_authorized_paper_graph_one_hop(
    candidates: tuple[NativeIndexedGraphCandidate, ...],
    *,
    concept_aliases: tuple[tuple[str, ...], ...],
    policy: PaperNativeRankPolicy,
    k: int = 5,
) -> tuple[int, ...]:
    """Rank only complete source-authorized one-hop DAG receipts."""
    return _rank_verified_graph_paths(
        tuple(_one_hop_rank_receipt(candidate) for candidate in candidates),
        concept_aliases=concept_aliases, policy=policy, k=k,
    )


def rank_authorized_paper_graph_two_hop(
    candidates: tuple[NativeIndexedTwoHopCandidate, ...],
    *,
    concept_aliases: tuple[tuple[str, ...], ...],
    policy: PaperNativeRankPolicy,
    k: int = 5,
) -> tuple[int, ...]:
    """Rank only complete source-authorized two-hop DAG receipts."""
    return _rank_verified_graph_paths(
        tuple(_two_hop_rank_receipt(candidate) for candidate in candidates),
        concept_aliases=concept_aliases, policy=policy, k=k,
    )


def rank_authorized_paper_graph_mixed(
    one_hop: tuple[NativeIndexedGraphCandidate, ...],
    two_hop: tuple[NativeIndexedTwoHopCandidate, ...],
    *,
    concept_aliases: tuple[tuple[str, ...], ...],
    policy: PaperNativeRankPolicy,
    k: int = 5,
) -> tuple[tuple[int, int], ...]:
    """Global Top-K across fully verified DAGs; depth is a final tie-breaker.

    The full qualified counts and the combined 5,000-path budget are checked
    by the calling canonical G5 index planner BEFORE invoking this function.
    Either cohort's exact K5 is sufficient for a global K5, because no route
    beyond a local K5 can enter the combined K5. Paths are never mixed.
    """
    paths = (
        tuple(_one_hop_rank_receipt(candidate) for candidate in one_hop)
        + tuple(_two_hop_rank_receipt(candidate) for candidate in two_hop)
    )
    positions = _rank_verified_graph_paths(
        paths, concept_aliases=concept_aliases, policy=policy, k=k,
    )
    first_len = len(one_hop)
    return tuple(
        (1, pos) if pos < first_len else (2, pos - first_len)
        for pos in positions
    )


def lookup_ranked_graph_one_hop(
    self: NativeSchemaGraphIndex,
    router: SchemaRouter,
    query: str,
    *,
    group: NativeDeclaredFieldGroup,
    principal: PrincipalContext,
    k: int = STRICT_K,
    allowed_target_routes: frozenset[str] | None = None,
    _paper_rank_policy: PaperNativeRankPolicy | None = None,
    _paper_rank_aliases: tuple[tuple[str, ...], ...] = (),
) -> NativeIndexedGraphResult:
    """Discover source-proven typed paths with reviewed owner Rank.

    Without owner Rank, results abstain above K. All typed evidence is
    nonexecuting and source-scoped.
    """
    if type(k) is not int or k != STRICT_K:
        raise ValueError("G5 strict fixed K5 required")
    if allowed_target_routes is not None and (
        type(allowed_target_routes) is not frozenset
        or len(allowed_target_routes) > (
            MAX_OWNER_RANKABLE_PATHS if _paper_rank_policy is not None
            else MAX_RESEARCH_RANKABLE_PATHS
        )
        or any(
            type(route) is not str or not 1 <= len(route) <= 320
            for route in allowed_target_routes
        )
    ):
        raise ValueError("G5 invalid bounded target route prefilter")
    if _paper_rank_policy is not None and not isinstance(
        _paper_rank_policy, PaperNativeRankPolicy,
    ):
        raise ValueError("G5 owner Rank must be exclusive and source-reviewed")
    if type(query) is not str or len(query.encode("utf-8")) > 512:
        raise ValueError("G5 invalid bounded query")
    if not isinstance(principal, PrincipalContext):
        raise PolicyViolationError("G5 explicit principal required")
    if not isinstance(group, NativeDeclaredFieldGroup):
        raise ValueError("G5 approved FieldGroup required")
    try:
        demand = NativeDeclaredFieldGroup.model_validate(
            group.model_dump(mode="python"), strict=True,
        )
        actor = PrincipalContext.model_validate(
            principal.model_dump(mode="python"), strict=True,
        )
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError("G5 invalid current host declarations") from exc
    if _alias_key(query) not in {_alias_key(a) for a in demand.aliases}:
        raise ValueError("G5 query lacks approved semantic edge")
    self.field_index._assert_source(router)
    owner_rank: PaperNativeRankPolicy | None = None
    original_owner_rank: str | None = None
    if _paper_rank_policy is not None:
        try:
            original_owner_rank = _paper_rank_policy.model_dump_json()
            owner_rank = PaperNativeRankPolicy.model_validate(
                _paper_rank_policy.model_dump(mode="python"), strict=True,
            )
        except Exception:
            raise PolicyViolationError("G5 invalid owner Rank policy") from None
        if owner_rank.snapshot_id != self.field_index.snapshot_id or not (
            set(owner_rank.route_domains) | set(owner_rank.route_priorities)
            | set(owner_rank.web_route_ids)
        ) <= self.field_index.route_locations.keys():
            raise PolicyViolationError("G5 owner Rank source mismatch")
    if router.authorization_policy is None:
        raise PolicyViolationError("G5 explicit policy required")
    witness = router._retrieval_authority_witness()
    original_policy = (
        router.authorization_policy.default_effect,
        repr(router.authorization_policy.rules),
        repr(router.authorization_policy.data_rules),
    )
    # This graph is not authorization-scoped and must never be surfaced
    # directly. All native endpoints are reloaded and checked at lookup.
    source_pass = _NativeSourcePass(self.field_index, router)
    permitted = router._authorization_predicate(actor)
    if permitted is None:
        raise PolicyViolationError("G5 explicit authorization required")
    availability = router._source_availability_predicate()
    wanted = [set(self.field_index.postings.get(x.semantic_id, ()))
              for x in demand.required_fields]
    targets = set.intersection(*wanted) if wanted else set()
    # Structural prefilter only; this set is not a permission grant.
    # Every surviving target AND its original source root still gets
    # current authorization, hidden-field and availability checks.
    targets.intersection_update(self.edge_consumer_routes)
    if allowed_target_routes is not None:
        # Model/host target IDs only NARROW graph structure before K;
        # normal principal, scope, source and typed checks still apply.
        targets.intersection_update(allowed_target_routes)

    def authorized(route_id: str) -> tuple[ToolSpec, EndpointSpec] | None:
        where = self.field_index.route_locations.get(route_id)
        pinned = self.field_index.route_fingerprints.get(route_id)
        if where is None or pinned is None:
            raise PolicyViolationError("G5 missing pinned native route")
        tool, endpoint, fingerprint = source_pass.get(*where)
        if (fingerprint, endpoint.fingerprint) != pinned:
            raise PolicyViolationError("G5 native route source drift")
        if (
            not tool.source_type or not tool.license
            or endpoint.read_only is not True
            or endpoint.destructive is True
            or not permitted(tool, endpoint)
        ):
            return None
        # The first pass must be as private as the final recheck: an
        # untrusted health callback may throw or return a value whose
        # truthiness evaluation raises with provider-owned information.
        if availability is not None:
            try:
                available_now = bool(source_pass.available(tool, endpoint, availability))
            except Exception:
                raise PolicyViolationError(
                    "G5 availability check failed during lookup"
                ) from None
            if not available_now:
                return None
        scoped = router._data_scope_endpoint_view(actor, tool, endpoint)
        return (tool, scoped) if scoped is not None else None

    found: list[NativeIndexedGraphCandidate] = []
    for target_id in sorted(targets):
        target = authorized(target_id)
        if target is None:
            continue
        target_tool, endpoint = target
        if (demand.source_type is not None
                and target_tool.source_type != demand.source_type
                or demand.license is not None
                and target_tool.license != demand.license
                or not _complete_fields(
                    endpoint.output_fields, demand.required_fields,
                )):
            continue
        required_inputs = _native_required_inputs(endpoint)
        if required_inputs is None:
            continue
        for root_id in self.graph.predecessors(target_id):
            root = authorized(root_id)
            if root is None:
                continue
            _root_tool, root_endpoint = root
            if owner_rank is not None and (
                demand.source_type is not None
                and _root_tool.source_type != demand.source_type
                or demand.license is not None
                and _root_tool.license != demand.license
            ):
                continue
            root_required: tuple[str, ...] = ()
            if not _root_envelope_empty(root_endpoint):
                if root_id not in self.approved_host_roots:
                    continue
                declared = _host_source_input_names(
                    _root_tool.endpoint(root_endpoint.name)
                )
                if declared is None:
                    continue
                root_required = declared
            bindings: list[tuple[str, str]] = []
            for parameter, required in required_inputs:
                field = _root_field(root_endpoint, required)
                if field is None or field.name in {
                    producer for _, producer in bindings
                }:
                    break
                bindings.append((parameter, field.name))
            if len(bindings) != len(required_inputs):
                continue
            # All scalars must be jointly present on a single source
            # record. Different nested arrays or optional root properties
            # are not an executable multi-input binding proof.
            if len(bindings) > 1 and not _flat_same_record_source_contract(
                _root_tool.endpoint(root_endpoint.name),
                root_endpoint,
                tuple(source_field for _, source_field in bindings),
            ):
                continue
            source = self.field_index.route_fingerprints[root_id]
            dest = self.field_index.route_fingerprints[target_id]
            names = tuple(sorted({
                f.name for f in endpoint.output_fields
                if any(_complete_fields([f], (req,))
                       for req in demand.required_fields)
            }))
            single = len(bindings) == 1
            found.append(NativeIndexedGraphCandidate(
                producer_route_id=root_id,
                consumer_route_id=target_id,
                producer_tool_fingerprint=source[0],
                producer_endpoint_fingerprint=source[1],
                consumer_tool_fingerprint=dest[0],
                consumer_endpoint_fingerprint=dest[1],
                producer_identifier_field=bindings[0][1] if single else None,
                consumer_required_parameter=bindings[0][0] if single else None,
                consumer_output_fields=names,
                parameter_bindings=tuple(bindings),
                source_root_parameters=root_required,
                producer_visible_field_count=(
                    len(root_endpoint.output_fields) if owner_rank is not None
                    else None
                ),
                consumer_visible_field_count=(
                    len(endpoint.output_fields) if owner_rank is not None
                    else None
                ),
            ))
            if owner_rank is not None and len(found) > MAX_OWNER_RANKABLE_PATHS:
                # No partial count or source names leave an oversized cohort.
                # Bound expansion before any 5001+ path memory growth.
                return NativeIndexedGraphResult(
                    "budget_unsatisfied", self.field_index.snapshot_id,
                    self.field_index.registry_version, k, 0, (),
                )
    # The availability predicate can be the SAME callable while its
    # underlying live health set changes during a multi-route lookup.
    # Revalidate *all* qualified paths before publishing either a
    # candidate OR the qualified count, including over-K abstention.
    # A registry version/authorization witness alone cannot detect
    # closure-state revocation from another candidate's callback.
    source_pass.reset()
    try:
        for candidate in found:
            root_now = authorized(candidate.producer_route_id)
            target_now = authorized(candidate.consumer_route_id)
            if root_now is None or target_now is None:
                raise PolicyViolationError("G5 candidate no longer available")
            _root_tool_now, root_ep_now = root_now
            _target_tool_now, target_ep_now = target_now
            if not _complete_fields(
                target_ep_now.output_fields, demand.required_fields,
            ):
                raise PolicyViolationError("G5 candidate scope changed")
            visible_names = tuple(sorted({
                field.name for field in target_ep_now.output_fields
                if any(
                    _complete_fields([field], (required,))
                    for required in demand.required_fields
                )
            }))
            if visible_names != candidate.consumer_output_fields:
                raise PolicyViolationError("G5 candidate projection changed")
            if owner_rank is not None and (
                candidate.producer_visible_field_count
                != len(root_ep_now.output_fields)
                or candidate.consumer_visible_field_count
                != len(target_ep_now.output_fields)
            ):
                raise PolicyViolationError("G5 candidate visible breadth changed")
            # A later health/scope callback may keep source identities
            # stable while withdrawing a previously proven typed join.
            # The default (unranked) K5 path requires the same binding proof.
            current_inputs = _native_required_inputs(target_ep_now)
            if (
                current_inputs is None
                or len(current_inputs) != len(candidate.parameter_bindings)
                or any(
                    required_name != bound_name
                    or (field := _root_field(root_ep_now, contract))
                    is None or field.name != bound_field
                    for (required_name, contract), (bound_name, bound_field)
                    in zip(
                        current_inputs, candidate.parameter_bindings,
                        strict=True,
                    )
                )
            ):
                raise PolicyViolationError("G5 candidate binding changed")
            if len(candidate.parameter_bindings) > 1 and not (
                _flat_same_record_source_contract(
                    _root_tool_now.endpoint(root_ep_now.name),
                    root_ep_now,
                    tuple(field for _, field in candidate.parameter_bindings),
                )
            ):
                raise PolicyViolationError("G5 candidate record contract changed")
    except Exception:
        # A native provider callback may embed private field names or
        # endpoint IDs in exceptions. Never forward that message.
        raise PolicyViolationError(
            "G5 candidate eligibility changed during lookup"
        ) from None
    self.field_index._assert_source(router)
    router._check_retrieval_authority_witness(witness)
    policy = router.authorization_policy
    if policy is None or (
        policy.default_effect, repr(policy.rules), repr(policy.data_rules),
    ) != original_policy:
        raise PolicyViolationError("G5 authorization rules changed during lookup")
    if original_owner_rank is not None:
        try:
            if (
                _paper_rank_policy is None
                or _paper_rank_policy.model_dump_json() != original_owner_rank
            ):
                raise PolicyViolationError("G5 Rank owner declaration changed")
        except Exception:
            raise PolicyViolationError("G5 Rank owner declaration changed") from None
    if owner_rank is not None:
        positions = rank_authorized_paper_graph_one_hop(
            tuple(found), concept_aliases=_paper_rank_aliases,
            policy=owner_rank, k=k,
        )
        return NativeIndexedGraphResult(
            "ranked_unverified" if len(found) > k
            else "complete" if found else "no_proven_hit",
            self.field_index.snapshot_id, self.field_index.registry_version,
            k, len(found), tuple(found[i] for i in positions),
            deterministic_paper_ranked=bool(found),
        )
    if len(found) > k:
        return NativeIndexedGraphResult(
            "over_k_unranked", self.field_index.snapshot_id,
            self.field_index.registry_version, k, len(found), (),
        )
    return NativeIndexedGraphResult(
        "complete" if found else "no_proven_hit",
        self.field_index.snapshot_id,
        self.field_index.registry_version, k, len(found), tuple(found),
    )


def lookup_ranked_graph_two_hop(
    self: NativeSchemaGraphIndex,
    router: SchemaRouter,
    query: str,
    *,
    group: NativeDeclaredFieldGroup,
    principal: PrincipalContext,
    k: int = STRICT_K,
    allowed_target_routes: frozenset[str] | None = None,
    _paper_rank_policy: PaperNativeRankPolicy | None = None,
    _paper_rank_aliases: tuple[tuple[str, ...], ...] = (),
) -> NativeIndexedTwoHopResult:
    """Opt-in E0: root -> typed intermediary -> target, without execution.

    Reuses the existing canonical source graph and index. Every endpoint
    and both join maps must be current, source-pinned, principal-visible,
    and explicitly typed. No unknown input, mixed-record join, inferred
    alias, unapproved parameterized root or model-driven path is allowed.
    """
    if type(k) is not int or k != STRICT_K:
        raise ValueError("G5 two-hop strict fixed K5 required")
    if allowed_target_routes is not None and (
        type(allowed_target_routes) is not frozenset
        or len(allowed_target_routes) > (
            MAX_OWNER_RANKABLE_PATHS if _paper_rank_policy is not None
            else MAX_RESEARCH_RANKABLE_PATHS
        )
        or any(
            type(route) is not str or not 1 <= len(route) <= 320
            for route in allowed_target_routes
        )
    ):
        raise ValueError("G5 two-hop invalid bounded target route prefilter")
    if type(query) is not str or len(query.encode("utf-8")) > 512:
        raise ValueError("G5 two-hop invalid bounded query")
    if not isinstance(group, NativeDeclaredFieldGroup):
        raise ValueError("G5 two-hop host FieldGroup required")
    if not isinstance(principal, PrincipalContext):
        raise PolicyViolationError("G5 two-hop explicit principal required")
    try:
        demand = NativeDeclaredFieldGroup.model_validate(
            group.model_dump(mode="python"), strict=True,
        )
        actor = PrincipalContext.model_validate(
            principal.model_dump(mode="python"), strict=True,
        )
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError("G5 two-hop invalid current declarations") from exc
    if _alias_key(query) not in {_alias_key(a) for a in demand.aliases}:
        raise ValueError("G5 two-hop query lacks approved semantic edge")
    self.field_index._assert_source(router)
    owner_rank: PaperNativeRankPolicy | None = None
    original_owner_rank: str | None = None
    if _paper_rank_policy is not None:
        try:
            original_owner_rank = _paper_rank_policy.model_dump_json()
            owner_rank = PaperNativeRankPolicy.model_validate(
                _paper_rank_policy.model_dump(mode="python"), strict=True,
            )
        except Exception:
            raise PolicyViolationError("G5 two-hop invalid owner Rank policy") from None
        if owner_rank.snapshot_id != self.field_index.snapshot_id or not (
            set(owner_rank.route_domains) | set(owner_rank.route_priorities)
            | set(owner_rank.web_route_ids)
        ) <= self.field_index.route_locations.keys():
            raise PolicyViolationError("G5 two-hop owner Rank source mismatch")
    if router.authorization_policy is None:
        raise PolicyViolationError("G5 two-hop explicit authorization policy required")
    witness = router._retrieval_authority_witness()
    original_policy = (
        router.authorization_policy.default_effect,
        repr(router.authorization_policy.rules),
        repr(router.authorization_policy.data_rules),
    )
    source_pass = _NativeSourcePass(self.field_index, router)
    permitted = router._authorization_predicate(actor)
    if permitted is None:
        raise PolicyViolationError("G5 two-hop explicit authorization required")
    availability = router._source_availability_predicate()

    def authorized(route: str) -> tuple[ToolSpec, EndpointSpec] | None:
        where = self.field_index.route_locations.get(route)
        pinned = self.field_index.route_fingerprints.get(route)
        if where is None or pinned is None:
            raise PolicyViolationError("G5 two-hop original route missing")
        tool, endpoint, fingerprint = source_pass.get(*where)
        if (fingerprint, endpoint.fingerprint) != pinned:
            raise PolicyViolationError("G5 two-hop original source changed")
        if (
            not tool.source_type or not tool.license
            or endpoint.read_only is not True or endpoint.destructive is True
            or not permitted(tool, endpoint)
        ):
            return None
        if availability is not None and not bool(
            source_pass.available(tool, endpoint, availability),
        ):
            return None
        scoped = router._data_scope_endpoint_view(actor, tool, endpoint)
        return (tool, scoped) if scoped is not None else None

    def bind(
        source_tool: ToolSpec,
        source: EndpointSpec,
        consumer: EndpointSpec,
    ) -> tuple[tuple[str, str], ...] | None:
        inputs = _native_required_inputs(consumer)
        if inputs is None:
            return None
        found_bindings: list[tuple[str, str]] = []
        for parameter, required in inputs:
            field = _root_field(source, required)
            if (
                field is None or field.name in {
                    name for _, name in found_bindings
                }
            ):
                return None
            found_bindings.append((parameter, field.name))
        result = tuple(found_bindings)
        if len(result) > 1 and not _flat_same_record_source_contract(
            source_tool.endpoint(source.name), source,
            tuple(field for _, field in result),
        ):
            return None
        return result

    def root_inputs(
        route: str, tool: ToolSpec, endpoint: EndpointSpec,
    ) -> tuple[str, ...] | None:
        if _root_envelope_empty(endpoint):
            return ()
        if route not in self.approved_host_roots:
            return None
        return _host_source_input_names(tool.endpoint(endpoint.name))

    wanted = [
        set(self.field_index.postings.get(field.semantic_id, ()))
        for field in demand.required_fields
    ]
    targets = set.intersection(*wanted) if wanted else set()
    targets.intersection_update(self.edge_consumer_routes)
    if allowed_target_routes is not None:
        targets.intersection_update(allowed_target_routes)
    qualified: list[NativeIndexedTwoHopCandidate] = []

    # Query the indexed predecessor lists only. This does not enumerate
    # the full registered catalog or grant any source execution access.
    try:
        for target_id in sorted(targets):
            target = authorized(target_id)
            if target is None:
                continue
            target_tool, target_ep = target
            if (
                demand.source_type is not None
                and target_tool.source_type != demand.source_type
                or demand.license is not None
                and target_tool.license != demand.license
                or not _complete_fields(
                    target_ep.output_fields, demand.required_fields,
                )
            ):
                continue
            names = tuple(sorted({
                field.name for field in target_ep.output_fields
                if any(
                    _complete_fields([field], (required,))
                    for required in demand.required_fields
                )
            }))
            for middle_id in self.graph.predecessors(target_id):
                middle = authorized(middle_id)
                if middle is None or middle_id == target_id:
                    continue
                middle_tool, middle_ep = middle
                if owner_rank is not None and (
                    demand.source_type is not None
                    and middle_tool.source_type != demand.source_type
                    or demand.license is not None
                    and middle_tool.license != demand.license
                ):
                    continue
                # An intermediary must genuinely consume source inputs
                # and produce the typed identifier needed by the target.
                if _native_required_inputs(middle_ep) is None:
                    continue
                second = bind(middle_tool, middle_ep, target_ep)
                if second is None:
                    continue
                for root_id in self.graph.predecessors(middle_id):
                    if len({root_id, middle_id, target_id}) != 3:
                        continue
                    root = authorized(root_id)
                    if root is None:
                        continue
                    root_tool, root_ep = root
                    if owner_rank is not None and (
                        demand.source_type is not None
                        and root_tool.source_type != demand.source_type
                        or demand.license is not None
                        and root_tool.license != demand.license
                    ):
                        continue
                    external_inputs = root_inputs(root_id, root_tool, root_ep)
                    if external_inputs is None:
                        continue
                    first = bind(root_tool, root_ep, middle_ep)
                    if first is None:
                        continue
                    qualified.append(NativeIndexedTwoHopCandidate(
                        route_ids=(root_id, middle_id, target_id),
                        route_fingerprints=(
                            self.field_index.route_fingerprints[root_id],
                            self.field_index.route_fingerprints[middle_id],
                            self.field_index.route_fingerprints[target_id],
                        ),
                        root_to_intermediate=first,
                        intermediate_to_target=second,
                        target_output_fields=names,
                        source_root_parameters=external_inputs,
                        visible_field_counts=(
                            len(root_ep.output_fields),
                            len(middle_ep.output_fields),
                            len(target_ep.output_fields),
                        ) if owner_rank is not None else None,
                    ))
                    if len(qualified) > (
                        MAX_OWNER_RANKABLE_PATHS if owner_rank is not None
                        else MAX_RESEARCH_RANKABLE_PATHS
                    ):
                        if owner_rank is not None:
                            return NativeIndexedTwoHopResult(
                                "budget_unsatisfied",
                                self.field_index.snapshot_id,
                                self.field_index.registry_version, k, 0, (),
                            )
                        raise PolicyViolationError(
                            "G5 two-hop source expansion exceeds E0 limit"
                        )
        # Every previously qualified route is re-read AFTER all health
        # callbacks, even if >K would return a count-only abstention.
        source_pass.reset()
        for candidate in qualified:
            root_id, middle_id, target_id = candidate.route_ids
            reread = tuple(authorized(route) for route in candidate.route_ids)
            if any(source is None for source in reread):
                raise PolicyViolationError("G5 two-hop route withdrawn")
            root_current, middle_current, target_current = reread
            assert root_current is not None
            assert middle_current is not None
            assert target_current is not None
            root_tool, root_ep = root_current
            middle_tool, middle_ep = middle_current
            target_tool, target_ep = target_current
            if (
                root_inputs(root_id, root_tool, root_ep)
                != candidate.source_root_parameters
                or _native_required_inputs(middle_ep) is None
                or bind(root_tool, root_ep, middle_ep)
                != candidate.root_to_intermediate
                or bind(middle_tool, middle_ep, target_ep)
                != candidate.intermediate_to_target
                or demand.source_type is not None
                and target_tool.source_type != demand.source_type
                or demand.license is not None
                and target_tool.license != demand.license
                or not _complete_fields(
                    target_ep.output_fields, demand.required_fields,
                )
            ):
                raise PolicyViolationError("G5 two-hop binding or scope withdrawn")
            latest_names = tuple(sorted({
                field.name for field in target_ep.output_fields
                if any(
                    _complete_fields([field], (required,))
                    for required in demand.required_fields
                )
            }))
            if latest_names != candidate.target_output_fields:
                raise PolicyViolationError("G5 two-hop output scope changed")
            if owner_rank is not None and candidate.visible_field_counts != (
                len(root_ep.output_fields),
                len(middle_ep.output_fields),
                len(target_ep.output_fields),
            ):
                raise PolicyViolationError("G5 two-hop visible breadth changed")
    except Exception:
        # Provider/host callbacks may throw messages containing private
        # source fields; only generic failure reaches an external agent.
        raise PolicyViolationError(
            "G5 two-hop source eligibility changed during lookup"
        ) from None

    self.field_index._assert_source(router)
    router._check_retrieval_authority_witness(witness)
    policy = router.authorization_policy
    if policy is None or (
        policy.default_effect, repr(policy.rules), repr(policy.data_rules),
    ) != original_policy:
        raise PolicyViolationError(
            "G5 two-hop authorization policy changed during lookup"
        )
    if original_owner_rank is not None:
        try:
            if (
                _paper_rank_policy is None
                or _paper_rank_policy.model_dump_json() != original_owner_rank
            ):
                raise PolicyViolationError("G5 two-hop Rank owner declaration changed")
        except Exception:
            raise PolicyViolationError(
                "G5 two-hop Rank owner declaration changed"
            ) from None
    count = len(qualified)
    if owner_rank is not None:
        offsets = rank_authorized_paper_graph_two_hop(
            tuple(qualified), concept_aliases=_paper_rank_aliases,
            policy=owner_rank, k=k,
        )
        return NativeIndexedTwoHopResult(
            "ranked_unverified" if count > k
            else "complete" if count else "no_proven_hit",
            self.field_index.snapshot_id,
            self.field_index.registry_version,
            k, count, tuple(qualified[i] for i in offsets),
            deterministic_paper_ranked=bool(count),
        )
    return NativeIndexedTwoHopResult(
        "over_k_unranked" if count > k else
        "complete" if count else "no_proven_hit",
        self.field_index.snapshot_id,
        self.field_index.registry_version,
        k,
        count,
        tuple(qualified) if count <= k else (),
    )
