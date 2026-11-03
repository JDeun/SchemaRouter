"""Compose independently source-proven concept groups without merging their authority."""
from __future__ import annotations

from collections.abc import Callable
from copy import deepcopy
from dataclasses import replace
from typing import TYPE_CHECKING, Any

from .authorization import PrincipalContext
from .concept_retrieval import (
    NativeConceptCatalog,
    NativeDeclaredConcept,
    _merged_concept_constraints,
    _merged_concept_fields,
)
from .errors import PolicyViolationError
from .host_field_contract import _policy_contents_digest
from .models import PlanCoverage, SemanticFieldRequirement
from .native_graph_index import NativeSchemaGraphIndex
from .paper_field_retrieval import PaperFieldRoute
from .paper_native_rank import PaperNativeRankPolicy
from .paper_typed_tool_plan import (
    PaperPlanBinding,
    PaperTypedToolPlan,
    _check_current_call_scopes,
    _compile_one_route,
)
from .paper_understood_direct_plan import (
    PaperIntentDeclaration,
    PaperIntentRegistry,
    PaperUnderstanding,
)

if TYPE_CHECKING:
    from .runtime import SchemaRouter


def _compile_understood_concept_plan(
    router: SchemaRouter,
    understanding: PaperUnderstanding,
    *,
    principal: PrincipalContext,
    catalog: NativeConceptCatalog,
    intent_registry: PaperIntentRegistry,
    index: NativeSchemaGraphIndex,
    k: int,
    host_source_arguments: dict[str, dict[str, Any]] | None,
    rank_policy: PaperNativeRankPolicy | None,
    approved: PaperUnderstanding,
    intent: PaperIntentDeclaration,
    concepts: tuple[NativeDeclaredConcept, ...],
    compile_one: Callable[..., PaperTypedToolPlan],
    compile_group: Callable[..., PaperTypedToolPlan],
    graph_options: dict[str, Any] | None = None,
) -> PaperTypedToolPlan:
    witness = router._retrieval_authority_witness()
    index.field_index._assert_source(router)
    if router.authorization_policy is None:
        raise PolicyViolationError("paper concept plan requires source policy")
    policy_digest = _policy_contents_digest(router.authorization_policy)
    owner_objects = (understanding, catalog, intent_registry, principal, rank_policy)
    owner_witness = tuple(obj.model_dump_json() if obj is not None else None
                          for obj in owner_objects)
    host_inputs = deepcopy(host_source_arguments or {})

    def verify_current() -> None:
        index.field_index._assert_source(router)
        router._check_retrieval_authority_witness(witness)
        if (
            router.authorization_policy is None
            or _policy_contents_digest(router.authorization_policy) != policy_digest
            or tuple(obj.model_dump_json() if obj is not None else None
                     for obj in owner_objects) != owner_witness
            or (host_source_arguments or {}) != host_inputs
        ):
            raise PolicyViolationError("paper concept owner or source authority changed")

    def prove_groups() -> tuple[PaperTypedToolPlan, ...]:
        plans = []
        for concept in concepts:
            # Narrow only the internal proof. The outer receipt retains EVERY owner demand.
            single_intent = PaperIntentRegistry(intents=(intent.model_copy(update={
                "required_concept_ids": (concept.concept_id,),
            }),))
            single = approved.model_copy(update={
                "concept_ids": (concept.concept_id,), "unresolved_concepts": (),
            })
            kwargs = dict(
                principal=principal, catalog=catalog, intent_registry=single_intent,
                index=index, k=k, rank_policy=rank_policy, **(graph_options or {}),
            )
            plan = compile_one(router, single, **kwargs)
            routes = {call.route_id for call in plan.calls}
            inputs = {route: values for route, values in host_inputs.items() if route in routes}
            if inputs:
                plan = compile_one(router, single, host_source_arguments=inputs, **kwargs)
            plans.append(plan)
        verify_current()
        return tuple(plans)

    def coverage(covered: set[str]) -> PlanCoverage:
        required, present, missing = [], [], []
        for concept in concepts:
            for field in sorted(concept.required_fields, key=lambda field: field.semantic_id):
                requirement = SemanticFieldRequirement(
                    semantic_id=field.semantic_id,
                    qualifiers=[
                        f"concept_id={concept.concept_id}",
                        *([f"source_type={concept.source_type}"]
                          if concept.source_type is not None else []),
                        *([f"license={concept.license}"] if concept.license is not None else []),
                        *(f"{key}={value}" for key, value in sorted(field.qualifiers.items())),
                    ],
                )
                required.append(requirement)
                (present if concept.concept_id in covered else missing).append(requirement)
        for proposal in approved.unresolved_concepts:
            unresolved = SemanticFieldRequirement(
                semantic_id="unresolved", qualifiers=[f"query_concept={proposal}"],
            )
            required.append(unresolved)
            missing.append(unresolved)
        return PlanCoverage(required=required, covered=present, uncovered=missing,
                            complete=not missing)

    # Preserve the original complete-field AND and its owner Rank before
    # independently ranking smaller concepts with potentially different menus.
    # A single native group holds eight semantics; larger valid concept unions
    # retain their per-concept proof instead of widening that source contract.
    group_fields = _merged_concept_fields(concepts)
    if (group_fields is not None and 1 <= len(group_fields) <= 8
            and _merged_concept_constraints(concepts) is not None):
        kwargs = dict(principal=principal, catalog=catalog, intent_registry=intent_registry,
                      index=index, k=k, rank_policy=rank_policy, **(graph_options or {}))
        try:
            group = compile_group(router, approved, **kwargs)
            verify_current()
        except Exception:
            raise PolicyViolationError("paper concept source eligibility changed") from None
        if group.status != "no_proven_hit":
            if not host_inputs.keys() <= {item.route_id for item in group.calls}:
                raise ValueError("host concept arguments name an unproved source route")
            if host_inputs:
                try:
                    group = compile_group(
                        router, approved, host_source_arguments=host_inputs, **kwargs,
                    )
                    verify_current()
                except Exception:
                    raise PolicyViolationError("paper concept source eligibility changed") from None
            group = replace(group, calls=tuple(
                replace(item, call=item.call.model_copy(update={
                    "fields": [field.name for field in item.fields_meta],
                })) for item in group.calls
            ))
            covered = {concept.concept_id for concept in concepts} if group.calls else set()
            report = coverage(covered)
            return replace(group, coverage=report,
                           status="no_proven_hit" if group.calls and not report.complete
                           else group.status)

    return _merge_understood_plans(
        router, principal=principal, index=index, k=k,
        host_source_arguments=host_source_arguments, prove_groups=prove_groups,
        verify_current=verify_current,
        coverage=lambda covered: coverage({concepts[position].concept_id for position in covered}),
    )


def _merge_understood_plans(
    router: SchemaRouter,
    *,
    principal: PrincipalContext,
    index: NativeSchemaGraphIndex,
    k: int,
    host_source_arguments: dict[str, dict[str, Any]] | None,
    prove_groups: Callable[[], tuple[PaperTypedToolPlan, ...]],
    verify_current: Callable[[], None],
    coverage: Callable[[set[int]], PlanCoverage],
) -> PaperTypedToolPlan:
    """Union bounded source proofs, retaining each independent requirement position."""
    witness = router._retrieval_authority_witness()
    host_inputs = deepcopy(host_source_arguments or {})
    try:
        first = prove_groups()
    except Exception:
        raise PolicyViolationError("paper concept source eligibility changed") from None

    def empty(status: str) -> PaperTypedToolPlan:
        try:
            if prove_groups() != first:
                raise PolicyViolationError("paper concept source proof changed")
            verify_current()
        except Exception:
            raise PolicyViolationError("paper concept source eligibility changed") from None
        return PaperTypedToolPlan(
            status=status, snapshot_id=index.field_index.snapshot_id,  # type: ignore[arg-type]
            registry_version=witness[1], requested_k=k, coverage=coverage(set()),
        )

    proved_routes = {call.route_id for plan in first for call in plan.calls}
    if not host_inputs.keys() <= proved_routes:
        raise ValueError("host concept arguments name an unproved source route")
    for status in ("budget_unsatisfied", "over_k_unranked", "ambiguous_paths"):
        if any(plan.status == status for plan in first):
            return empty(status)
    if len(proved_routes) > k:
        return empty("budget_unsatisfied")

    receipts: dict[str, PaperFieldRoute] = {}
    for plan in first:
        for position, call in enumerate(plan.calls):
            tool_fingerprint = call.call.tool_fingerprint
            if tool_fingerprint is None:
                raise PolicyViolationError("paper concept source fingerprint missing")
            bindings = tuple(sorted(
                (edge.parameter, plan.calls[edge.producer_call_index].route_id,
                 edge.producer_field)
                for edge in plan.bindings if edge.consumer_call_index == position
            ))
            route = PaperFieldRoute(
                route_id=call.route_id, tool_fingerprint=tool_fingerprint,
                endpoint_fingerprint=call.call.schema_fingerprint,
                output_fields=tuple(call.call.fields), covered_semantic_ids=(),
                input_bindings=bindings,
            )
            previous = receipts.get(route.route_id)
            if previous is not None:
                if (
                    previous.tool_fingerprint != route.tool_fingerprint
                    or previous.endpoint_fingerprint != route.endpoint_fingerprint
                ):
                    raise PolicyViolationError("paper concept source fingerprint changed")
                if previous.input_bindings != route.input_bindings:
                    return empty("ambiguous_paths")
                route = PaperFieldRoute(
                    route_id=route.route_id, tool_fingerprint=route.tool_fingerprint,
                    endpoint_fingerprint=route.endpoint_fingerprint,
                    output_fields=tuple(dict.fromkeys(
                        (*previous.output_fields, *route.output_fields),
                    )), covered_semantic_ids=(), input_bindings=bindings,
                )
            receipts[route.route_id] = route

    try:
        for route_id, receipt in receipts.items():
            tool_key, endpoint_name = index.field_index.route_locations[route_id]
            endpoint = router.registry.get(tool_key).endpoint(endpoint_name)
            names = tuple(field.name for field in endpoint.output_fields
                          if field.name in receipt.output_fields)
            if set(names) != set(receipt.output_fields):
                raise PolicyViolationError("paper concept source fields changed")
            # Concept order must not change the original source field declaration order.
            receipts[route_id] = PaperFieldRoute(
                route_id=route_id, tool_fingerprint=receipt.tool_fingerprint,
                endpoint_fingerprint=receipt.endpoint_fingerprint,
                output_fields=names, covered_semantic_ids=(), input_bindings=receipt.input_bindings,
            )
    except Exception:
        raise PolicyViolationError("paper concept source eligibility changed") from None

    ordered: list[str] = []
    remaining = dict(receipts)
    while remaining:
        ready = next((route for route, receipt in remaining.items()
                      if all(producer in ordered for _, producer, _ in receipt.input_bindings)),
                     None)
        if ready is None:
            return empty("ambiguous_paths")
        ordered.append(ready)
        del remaining[ready]

    def materialize():
        permitted = router._authorization_predicate(principal)
        if permitted is None:
            raise PolicyViolationError("paper concept plan lost source policy")
        positions = {route: position for position, route in enumerate(ordered)}
        edges: list[PaperPlanBinding] = []
        calls = tuple(_compile_one_route(
            router, principal, index, receipts[route], position, positions, receipts,
            edges, permitted, host_inputs.get(route),
        ) for position, route in enumerate(ordered))
        _check_current_call_scopes(router, principal, list(calls))
        return calls, tuple(edges)

    try:
        calls, bindings = materialize()
        if prove_groups() != first or materialize() != (calls, bindings):
            raise PolicyViolationError("paper concept source proof changed")
        _check_current_call_scopes(router, principal, list(calls))
        verify_current()
    except Exception:
        raise PolicyViolationError("paper concept source eligibility changed") from None
    covered = {
        position for position, plan in enumerate(first)
        if plan.calls and plan.status in {"ready", "requires_arguments", "requires_observation"}
    }
    report = coverage(covered)
    status = (
        "no_proven_hit" if not report.complete else
        "requires_observation" if bindings else
        "requires_arguments" if any(call.call.missing_required_arguments for call in calls)
        else "ready"
    )
    return PaperTypedToolPlan(
        status=status, snapshot_id=index.field_index.snapshot_id,
        registry_version=witness[1], requested_k=k, calls=calls, bindings=bindings,
        ranked_unverified=any(plan.ranked_unverified for plan in first), coverage=report,
    )
