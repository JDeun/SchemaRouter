"""#1560 E0: bounded typed 2-4 edge source-native graph path evidence.

This uses the EXISTING indexed native graph and canonical field comparators.
It does not invoke source tools, grant execution, or rank alternatives.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

from .authorization import PrincipalContext
from .errors import PolicyViolationError
from .field_group_retrieval import NativeDeclaredFieldGroup, _alias_key, _complete_fields
from .models import EndpointSpec, ToolSpec
from .native_graph_index import (
    MAX_RESEARCH_RANKABLE_PATHS,
    STRICT_K,
    _flat_same_record_source_contract,
    _host_source_input_names,
    _native_required_inputs,
    _root_envelope_empty,
    _root_field,
)

if TYPE_CHECKING:
    from .native_graph_index import NativeSchemaGraphIndex
    from .runtime import SchemaRouter

MAX_BOUNDED_HOPS = 4
MAX_BOUNDED_VISITS = 256


@dataclass(frozen=True, slots=True)
class NativeIndexedPathCandidate:
    """Original immutable metadata evidence, not an execution plan."""

    route_ids: tuple[str, ...]
    route_fingerprints: tuple[tuple[str, str], ...]
    parameter_bindings: tuple[tuple[tuple[str, str], ...], ...]
    target_output_fields: tuple[str, ...]
    source_root_parameters: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class NativeIndexedPathResult:
    status: Literal["complete", "no_proven_hit", "over_k_unranked"]
    index_snapshot_id: str
    registry_version: int
    requested_k: int
    requested_hops: int
    qualified_path_count: int
    candidates: tuple[NativeIndexedPathCandidate, ...]
    independent_quality_evidence: bool = False
    calibrated_no_fit: bool = False
    executable_authority: bool = False


def lookup_bounded_native_paths(
    index: NativeSchemaGraphIndex,
    router: SchemaRouter,
    query: str,
    *,
    group: NativeDeclaredFieldGroup,
    principal: PrincipalContext,
    hops: int = 3,
    k: int = STRICT_K,
) -> NativeIndexedPathResult:
    """Find EXACTLY 2..4 typed edges by backwards indexed traversal.

    A caller controls exploration depth, but a hard cap forbids arbitrary
    deep search. Required output groups must be satisfied at the single
    terminal route; this does not solve multi-branch data fusion.
    """
    if type(hops) is not int or not 2 <= hops <= MAX_BOUNDED_HOPS:
        raise ValueError("G5 bounded paths require exact 2..4 hops")
    if type(k) is not int or k != STRICT_K:
        raise ValueError("G5 bounded paths require fixed K5")
    if type(query) is not str or len(query.encode("utf-8")) > 512:
        raise ValueError("G5 bounded path query is invalid")
    if not isinstance(group, NativeDeclaredFieldGroup):
        raise ValueError("G5 bounded path needs host-declared FieldGroup")
    if not isinstance(principal, PrincipalContext):
        raise PolicyViolationError("G5 bounded path needs trusted principal")
    try:
        demand = NativeDeclaredFieldGroup.model_validate(
            group.model_dump(mode="python"), strict=True,
        )
        actor = PrincipalContext.model_validate(
            principal.model_dump(mode="python"), strict=True,
        )
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError("G5 bounded path invalid declarations") from exc
    if _alias_key(query) not in {_alias_key(a) for a in demand.aliases}:
        raise ValueError("G5 bounded path lacks host-approved query edge")

    index.field_index._assert_source(router)
    if router.authorization_policy is None:
        raise PolicyViolationError("G5 bounded paths require explicit policy")
    witness = router._retrieval_authority_witness()
    policy_snapshot = (
        router.authorization_policy.default_effect,
        repr(router.authorization_policy.rules),
        repr(router.authorization_policy.data_rules),
    )
    permitted = router._authorization_predicate(actor)
    if permitted is None:
        raise PolicyViolationError("G5 bounded paths require explicit authorization")
    availability = router.planner.availability_predicate

    def authorized(route: str) -> tuple[ToolSpec, EndpointSpec] | None:
        where = index.field_index.route_locations.get(route)
        pinned = index.field_index.route_fingerprints.get(route)
        if where is None or pinned is None:
            raise PolicyViolationError("G5 bounded route absent from indexed source")
        tool = router.registry.get(where[0])
        endpoint = tool.endpoint(where[1])
        if (tool.fingerprint, endpoint.fingerprint) != pinned:
            raise PolicyViolationError("G5 bounded route fingerprint drift")
        if (
            not tool.source_type or not tool.license
            or endpoint.read_only is not True or endpoint.destructive is True
            or not permitted(tool, endpoint)
        ):
            return None
        if availability is not None and not bool(availability(tool, endpoint)):
            return None
        scoped = router._data_scope_endpoint_view(actor, tool, endpoint)
        return (tool, scoped) if scoped is not None else None

    def bind(
        producer: tuple[ToolSpec, EndpointSpec],
        consumer: tuple[ToolSpec, EndpointSpec],
    ) -> tuple[tuple[str, str], ...] | None:
        producer_tool, producer_ep = producer
        _consumer_tool, consumer_ep = consumer
        inputs = _native_required_inputs(consumer_ep)
        if inputs is None:
            return None
        selected: list[tuple[str, str]] = []
        for param, required in inputs:
            field = _root_field(producer_ep, required)
            if field is None or any(field.name == old for _, old in selected):
                return None
            selected.append((param, field.name))
        bindings = tuple(selected)
        if len(bindings) > 1 and not _flat_same_record_source_contract(
            producer_tool.endpoint(producer_ep.name),
            producer_ep,
            tuple(producer_field for _, producer_field in bindings),
        ):
            return None
        return bindings

    def starting_inputs(
        route: str, origin: tuple[ToolSpec, EndpointSpec],
    ) -> tuple[str, ...] | None:
        tool, endpoint = origin
        if _root_envelope_empty(endpoint):
            return ()
        if route not in index.approved_host_roots:
            return None
        return _host_source_input_names(tool.endpoint(endpoint.name))

    wanted = [
        set(index.field_index.postings.get(f.semantic_id, ()))
        for f in demand.required_fields
    ]
    targets = set.intersection(*wanted) if wanted else set()
    targets.intersection_update(index.edge_consumer_routes)
    qualified: list[NativeIndexedPathCandidate] = []
    # Bound EVERY candidate authorization probe, including denied/unhealthy
    # posting hits, not merely paths that pass all typed-join filters.
    # Otherwise a dense but ineligible catalog can consume unbounded CPU.
    visits = 0

    try:
        for target_id in sorted(targets):
            visits += 1
            if visits > MAX_BOUNDED_VISITS:
                raise PolicyViolationError(
                    "G5 bounded graph expansion budget exceeded"
                )
            target = authorized(target_id)
            if target is None:
                continue
            tool, endpoint = target
            if (
                demand.source_type is not None
                and tool.source_type != demand.source_type
                or demand.license is not None
                and tool.license != demand.license
                or not _complete_fields(
                    endpoint.output_fields, demand.required_fields,
                )
            ):
                continue
            target_names = tuple(sorted({
                field.name for field in endpoint.output_fields
                if any(
                    _complete_fields([field], (required,))
                    for required in demand.required_fields
                )
            }))
            # Graph predecessors are already canonical typed compatible.
            # Exact-live scope and binding proof additionally prune each edge.
            stack: list[tuple[str, ...]] = [(target_id,)]
            while stack:
                backwards = stack.pop()
                if len(backwards) == hops + 1:
                    routes = tuple(reversed(backwards))
                    current = [authorized(route) for route in routes]
                    if any(item is None for item in current):
                        continue
                    proven = [item for item in current if item is not None]
                    origin = starting_inputs(routes[0], proven[0])
                    if origin is None or any(
                        _native_required_inputs(view[1]) is None
                        for view in proven[1:-1]
                    ):
                        continue
                    bindings = tuple(
                        bind(proven[i], proven[i + 1])
                        for i in range(hops)
                    )
                    if any(item is None for item in bindings):
                        continue
                    valid_bindings = tuple(
                        item for item in bindings if item is not None
                    )
                    last_tool, last_endpoint = proven[-1]
                    if (
                        demand.source_type is not None
                        and last_tool.source_type != demand.source_type
                        or demand.license is not None
                        and last_tool.license != demand.license
                        or not _complete_fields(
                            last_endpoint.output_fields, demand.required_fields,
                        )
                    ):
                        continue
                    qualified.append(NativeIndexedPathCandidate(
                        route_ids=routes,
                        route_fingerprints=tuple(
                            index.field_index.route_fingerprints[route]
                            for route in routes
                        ),
                        parameter_bindings=valid_bindings,
                        target_output_fields=target_names,
                        source_root_parameters=origin,
                    ))
                    if len(qualified) > MAX_RESEARCH_RANKABLE_PATHS:
                        raise PolicyViolationError(
                            "G5 bounded path count exceeds source limit"
                        )
                    continue

                # Deterministic DFS order; never re-enter an identity already
                # in the chain, including source-owned cyclic graph edges.
                consumer = authorized(backwards[-1])
                if consumer is None:
                    continue
                for predecessor in sorted(
                    index.graph.predecessors(backwards[-1]), reverse=True,
                ):
                    if predecessor in backwards:
                        continue
                    visits += 1
                    if visits > MAX_BOUNDED_VISITS:
                        raise PolicyViolationError(
                            "G5 bounded graph expansion budget exceeded"
                        )
                    producer = authorized(predecessor)
                    if producer is None or bind(producer, consumer) is None:
                        continue
                    # An intermediate must have fully source-typed inputs;
                    # the final predecessor must instead be an actual root.
                    is_origin = len(backwards) == hops
                    if is_origin:
                        if starting_inputs(predecessor, producer) is None:
                            continue
                    elif _native_required_inputs(producer[1]) is None:
                        continue
                    stack.append((*backwards, predecessor))

        # The first traversal might change the same live health callable's
        # captured state. Never return a stale earlier path or even its count.
        for candidate in qualified:
            latest = [authorized(route) for route in candidate.route_ids]
            if any(item is None for item in latest):
                raise PolicyViolationError("G5 bounded path revoked")
            verified = [item for item in latest if item is not None]
            if (
                starting_inputs(candidate.route_ids[0], verified[0])
                != candidate.source_root_parameters
                or any(
                    _native_required_inputs(item[1]) is None
                    for item in verified[1:-1]
                )
                or tuple(
                    bind(verified[i], verified[i + 1])
                    for i in range(hops)
                ) != candidate.parameter_bindings
            ):
                raise PolicyViolationError("G5 bounded path binding revoked")
            output_tool, output_ep = verified[-1]
            if (
                demand.source_type is not None
                and output_tool.source_type != demand.source_type
                or demand.license is not None
                and output_tool.license != demand.license
                or not _complete_fields(
                    output_ep.output_fields, demand.required_fields,
                )
            ):
                raise PolicyViolationError("G5 bounded output scope revoked")
            current_names = tuple(sorted({
                field.name for field in output_ep.output_fields
                if any(
                    _complete_fields([field], (required,))
                    for required in demand.required_fields
                )
            }))
            if current_names != candidate.target_output_fields:
                raise PolicyViolationError("G5 bounded projection revoked")
    except Exception:
        raise PolicyViolationError(
            "G5 bounded path eligibility changed during lookup"
        ) from None

    index.field_index._assert_source(router)
    router._check_retrieval_authority_witness(witness)
    current_policy = router.authorization_policy
    if current_policy is None or (
        current_policy.default_effect,
        repr(current_policy.rules),
        repr(current_policy.data_rules),
    ) != policy_snapshot:
        raise PolicyViolationError("G5 bounded path policy changed")
    qualified.sort(key=lambda item: item.route_ids)
    count = len(qualified)
    return NativeIndexedPathResult(
        "over_k_unranked" if count > k else
        "complete" if count else "no_proven_hit",
        index.field_index.snapshot_id,
        index.field_index.registry_version,
        k, hops, count,
        tuple(qualified) if count <= k else (),
    )
