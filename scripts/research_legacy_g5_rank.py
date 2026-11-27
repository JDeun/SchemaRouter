"""Historical G5 authorized callback ranking, source-checkout only.

This archives the pre-retirement source-proven one-hop lookup and all
post-callback checks. The installed graph never imports this comparator.
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, replace
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
    NativeSchemaGraphIndex,
    _flat_same_record_source_contract,
    _host_source_input_names,
    _native_required_inputs,
    _root_field,
)
from schemarouter.native_semantic_index import _NativeSourcePass
from scripts.research_legacy_direct_rank import PaperNativeRankPolicy
from scripts.research_legacy_graph_rank import (
    MAX_OWNER_RANKABLE_PATHS,
    rank_authorized_paper_graph_one_hop,
)

if TYPE_CHECKING:
    from schemarouter.runtime import SchemaRouter


@dataclass(frozen=True, slots=True)
class NativeIndexedGraphResult:
    status: Literal[
        "complete", "no_proven_hit", "over_k_unranked",
        "ranked_unverified", "ranker_abstained_unverified",
        "internal_fork_arm", "budget_unsatisfied",
    ]
    index_snapshot_id: str
    registry_version: int
    requested_k: int
    qualified_path_count: int
    candidates: tuple[NativeIndexedGraphCandidate, ...]
    independent_quality_evidence: bool = False
    calibrated_no_fit: bool = False
    executable_authority: bool = False
    experimental_ranked: bool = False
    deterministic_paper_ranked: bool = False


def research_lookup_graph(
    self: NativeSchemaGraphIndex,
    router: SchemaRouter,
    query: str,
    *,
    group: NativeDeclaredFieldGroup,
    principal: PrincipalContext,
    k: int = STRICT_K,
    allowed_target_routes: frozenset[str] | None = None,
    _research_ranker: Callable[
        [str, tuple[NativeIndexedGraphCandidate, ...], int],
        tuple[int, ...],
    ] | None = None,
    _paper_rank_policy: PaperNativeRankPolicy | None = None,
    _paper_rank_aliases: tuple[tuple[str, ...], ...] = (),
    _fork_arm_internal: bool = False,
    _fork_root_filter: frozenset[str] | None = None,
    _fork_target_filter: frozenset[str] | None = None,
) -> NativeIndexedGraphResult:
    """Discover source-proven typed paths; default remains unranked at >K.

    An explicitly supplied host-owned E0 callback sees only FULLY
    current-authorized and field-scoped graph candidate evidence. Its
    tuple of offered candidate offsets is untrusted and checked after
    the callback, as is current authority. This is NOT a production
    ranking policy, no-fit classifier, or grant of execution authority.
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
    if _research_ranker is not None and not callable(_research_ranker):
        raise ValueError("G5 experimental ranker must be callable")
    if _paper_rank_policy is not None and (
        not isinstance(_paper_rank_policy, PaperNativeRankPolicy)
        or _research_ranker is not None
        or _fork_arm_internal
    ):
        raise ValueError("G5 owner Rank must be exclusive and source-reviewed")
    if type(_fork_arm_internal) is not bool or (
        _fork_arm_internal and _research_ranker is not None
    ):
        raise ValueError("G5 internal fork arm forbids external ranking")
    if _fork_root_filter is not None and (
        not _fork_arm_internal
        or type(_fork_root_filter) is not frozenset
        or any(type(route) is not str for route in _fork_root_filter)
    ):
        raise ValueError("G5 root prefilter requires private typed fork mode")
    if _fork_target_filter is not None and (
        not _fork_arm_internal
        or type(_fork_target_filter) is not frozenset
        or any(type(route) is not str for route in _fork_target_filter)
    ):
        raise ValueError("G5 consumer prefilter requires private typed fork mode")
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
    if _fork_target_filter is not None:
        # Candidate-only optimization; current authorization is NEVER
        # inferred from route IDs supplied to the private collector.
        targets.intersection_update(_fork_target_filter)

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
        # Source-graph-only optimization, NOT an authorization grant.
        # Skip routes whose typed indexed producers cannot be part of a
        # two-field common-root fork; authorization remains downstream.
        if _fork_root_filter is not None and not any(
            root in _fork_root_filter
            for root in self.graph.predecessors(target_id)
        ):
            continue
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
            if (_fork_root_filter is not None
                    and root_id not in _fork_root_filter):
                continue
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
            # The default (unranked) K5 path needs the same binding proof
            # already required after an optional research ranker.
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
        # Source-private composition mode: authorize and recheck each
        # one-hop witness exactly as in ordinary G5, but do NOT apply
        # final public K to each arm before proving the shared root.
        # Never expose >K arms from ordinary lookup or return >32 arms.
        if _fork_arm_internal:
            if len(found) > MAX_RESEARCH_RANKABLE_PATHS:
                return NativeIndexedGraphResult(
                    "over_k_unranked", self.field_index.snapshot_id,
                    self.field_index.registry_version, k, len(found), (),
                )
            return NativeIndexedGraphResult(
                "internal_fork_arm", self.field_index.snapshot_id,
                self.field_index.registry_version, k, len(found), tuple(found),
            )
        if (
            _research_ranker is None
            or len(found) > MAX_RESEARCH_RANKABLE_PATHS
        ):
            return NativeIndexedGraphResult(
                "over_k_unranked", self.field_index.snapshot_id,
                self.field_index.registry_version, k, len(found), (),
            )
        # All structural, policy, data-scope, visibility, availability
        # and source checks have already completed, BEFORE disclosure.
        # The research callback is UNTRUSTED. Even frozen dataclasses
        # can be mutated with object.__setattr__. Send detached copies:
        # selected outputs must always be drawn from the original
        # source-verified `found` snapshot, never objects the backend held.
        offered = tuple(replace(candidate) for candidate in found)
        chosen = _research_ranker(query, offered, k)
        self.field_index._assert_source(router)
        router._check_retrieval_authority_witness(witness)
        current_policy = router.authorization_policy
        if current_policy is None or (
            current_policy.default_effect,
            repr(current_policy.rules),
            repr(current_policy.data_rules),
        ) != original_policy:
            raise PolicyViolationError(
                "G5 authorization rules changed during research ranking"
            )
        if (
            type(chosen) is not tuple
            or len(chosen) not in (0, k)
            or any(type(offset) is not int
                   or not 0 <= offset < len(found) for offset in chosen)
            or len(set(chosen)) != len(chosen)
        ):
            raise PolicyViolationError(
                "G5 research ranker returned forged, partial or duplicate offsets"
            )
        # A caller-owned availability callable can change state without
        # changing its object identity (or registry/policy version) while
        # the untrusted research ranker runs. Recheck ALL at-most-32
        # originally qualified paths, not only the chosen K, because
        # qualified_path_count is also published to the caller.
        # These checks never grant access or invoke source tools.
        source_pass.reset()
        try:
            for candidate in found:
                current_root = authorized(candidate.producer_route_id)
                current_target = authorized(candidate.consumer_route_id)
                if current_root is None or current_target is None:
                    raise PolicyViolationError(
                        "G5 source eligibility changed during research ranking"
                    )
                source_tool, source_endpoint = current_root
                _target_tool, target_endpoint = current_target
                if not _complete_fields(
                    target_endpoint.output_fields, demand.required_fields,
                ):
                    raise PolicyViolationError(
                        "G5 visible field contract changed during research ranking"
                    )
                current_inputs = _native_required_inputs(target_endpoint)
                if (
                    current_inputs is None
                    or len(current_inputs) != len(candidate.parameter_bindings)
                    or any(
                        required_name != bound_name
                        or (field := _root_field(source_endpoint, contract))
                        is None or field.name != bound_field
                        for (required_name, contract), (bound_name, bound_field)
                        in zip(
                            current_inputs, candidate.parameter_bindings,
                            strict=True,
                        )
                    )
                ):
                    raise PolicyViolationError(
                        "G5 source binding changed during research ranking"
                    )
                if len(candidate.parameter_bindings) > 1 and not (
                    _flat_same_record_source_contract(
                        source_tool.endpoint(source_endpoint.name),
                        source_endpoint,
                        tuple(field for _, field in candidate.parameter_bindings),
                    )
                ):
                    raise PolicyViolationError(
                        "G5 source record contract changed during research ranking"
                    )
                public_names = tuple(sorted({
                    field.name for field in target_endpoint.output_fields
                    if any(
                        _complete_fields([field], (required,))
                        for required in demand.required_fields
                    )
                }))
                if public_names != candidate.consumer_output_fields:
                    raise PolicyViolationError(
                        "G5 source projection changed during research ranking"
                    )
        except Exception:
            # Source/host callbacks may contain private route/field text
            # in an exception. Never expose it through this optional API.
            raise PolicyViolationError(
                "G5 authorized graph changed during research ranking"
            ) from None
        self.field_index._assert_source(router)
        router._check_retrieval_authority_witness(witness)
        return NativeIndexedGraphResult(
            "ranked_unverified" if chosen
            else "ranker_abstained_unverified",
            self.field_index.snapshot_id,
            self.field_index.registry_version, k, len(found),
            tuple(found[offset] for offset in chosen),
            experimental_ranked=True,
        )
    return NativeIndexedGraphResult(
        "complete" if found else "no_proven_hit",
        self.field_index.snapshot_id,
        self.field_index.registry_version, k, len(found), tuple(found),
    )
