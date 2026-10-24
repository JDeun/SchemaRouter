"""Opt-in original-paper P2: real producer execution, deferred typed consumers.

Only the original, source-attested root is invoked, exactly once, by the
ordinary SchemaRouter executor. This does not execute consumers or grant a
caller-supplied observation/provider identity any special authority.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from typing import TYPE_CHECKING, Any

from .authorization import PrincipalContext
from .concept_retrieval import (
    NativeConceptCatalog,
    resolve_native_concepts,
)
from .errors import PolicyViolationError, SchemaValidationError
from .field_group_retrieval import NativeDeclaredFieldGroup
from .models import ExecutionPlan, ToolResult
from .native_graph_index import NativeIndexedGraphCandidate, NativeSchemaGraphIndex
from .native_graph_observation import _materialize_original_observed_edge
from .paper_field_retrieval import retrieve_paper_field_coverage
from .paper_typed_tool_plan import (
    PaperPlanCall,
    PaperTypedToolPlan,
    _check_current_call_scopes,
    compile_paper_typed_tool_plan,
)
from .runs import ExecutionBudget, RunConfig

if TYPE_CHECKING:
    from .runtime import SchemaRouter


@dataclass(frozen=True, slots=True)
class PaperObservedBinding:
    """Actual executor root result + source-typed *non-executable* leaf receipt."""

    producer: ToolResult
    plan: PaperTypedToolPlan
    producer_via_registered_executor: bool = True
    provider_provenance_verified: bool = False
    executable_authority: bool = False
    independent_e2: bool = False


async def observe_and_bind_paper_plan(
    router: SchemaRouter,
    query: str,
    *,
    principal: PrincipalContext,
    catalog: NativeConceptCatalog,
    index: NativeSchemaGraphIndex,
    host_source_arguments: dict[str, dict[str, Any]] | None = None,
    alternative_index: int = 0,
    k: int = 5,
) -> PaperObservedBinding:
    """Execute one approved producer and validate typed original-ID leaf inputs.

    The source result is acquired inside this routine from the configured
    executor, *not* from caller-supplied `ToolResult` data. Consumer calls
    remain unexecuted; the returned `ready` status means only that their
    typed shapes now have concrete, validated arguments. Use of this API
    never constitutes publisher-authenticated or independently graded E2.
    """
    original = compile_paper_typed_tool_plan(
        router, query, principal=principal, catalog=catalog, index=index,
        host_source_arguments=host_source_arguments,
        alternative_index=alternative_index, k=k,
    )
    if (
        not 2 <= len(original.calls) <= k
        or len(original.bindings) < len(original.calls) - 1
        or original.status != "requires_observation"
        or any(binding.producer_call_index != 0 for binding in original.bindings)
        or {binding.consumer_call_index for binding in original.bindings}
        != set(range(1, len(original.calls)))
    ):
        raise PolicyViolationError("paper observed binding requires one original root")

    source = original.calls[0].call
    if source.missing_required_arguments or not source.executable:
        raise SchemaValidationError("paper producer requires explicit host source inputs")

    selected = retrieve_paper_field_coverage(
        router, query, principal=principal, catalog=catalog, index=index, k=k,
    )
    if (
        selected.status != "complete"
        or alternative_index >= len(selected.alternatives)
        or tuple(route.route_id for route in selected.alternatives[alternative_index].routes)
        != tuple(item.route_id for item in original.calls)
    ):
        raise PolicyViolationError("original paper field proof changed before execution")

    group = resolve_native_concepts(query, catalog=catalog).field_group
    routes = selected.alternatives[alternative_index].routes
    root_route_id = routes[0].route_id
    # A P1 fork may be fully proven under K5 while each UNFILTERED one-hop
    # subset exceeds K5 due to other source-ID owners. Preflight only the
    # already source-attested original edges, using G5's private fork-arm
    # source/target filters and ALL its normal typed/policy/scope checks.
    pinned_leaves: list[tuple[NativeDeclaredFieldGroup, NativeIndexedGraphCandidate]] = []
    for receipt in routes[1:]:
        demanded = tuple(
            field for field in group.required_fields
            if field.semantic_id in receipt.covered_semantic_ids
        )
        if not demanded:
            raise PolicyViolationError("paper leaf lacks source-attested output intent")
        subset = NativeDeclaredFieldGroup(
            aliases=group.aliases, required_fields=demanded,
            source_type=group.source_type, license=group.license,
        )
        binding_pairs = tuple(
            (parameter, field)
            for parameter, producer, field in receipt.input_bindings
            if producer == root_route_id
        )
        candidate = _pin_source_attested_paper_edge(
            index, router, query, group=subset, principal=principal,
            root_route_id=root_route_id,
            consumer_route_id=receipt.route_id,
            bindings=binding_pairs, k=k,
        )
        pinned_leaves.append((subset, candidate))

    source_plan = ExecutionPlan(
        query=query, registry_version=original.registry_version,
        calls=[source.model_copy(deep=True)],
    )
    # No silent invocation of a dependent consumer, retries, remote extras,
    # provider fallback or unbounded second tool step.
    results = await router.execute(source_plan, config=RunConfig(
        principal=principal,
        budget=ExecutionBudget(
            max_tool_calls=1, max_attempts=1, max_remote_attempts=1,
        ),
    ))
    if (
        len(results) != 1 or not isinstance(results[0], ToolResult)
        or (results[0].tool, results[0].endpoint)
        != (source.tool, source.endpoint)
    ):
        raise SchemaValidationError("paper original producer did not return one result")
    observation = results[0]

    # Reprove original source policy, scoped fields, original root identity
    # and caller host parameter contracts AFTER observed I/O.
    after = compile_paper_typed_tool_plan(
        router, query, principal=principal, catalog=catalog, index=index,
        host_source_arguments=host_source_arguments,
        alternative_index=alternative_index, k=k,
    )
    if after != original:
        raise PolicyViolationError("paper source eligibility changed after observation")

    bound: list[PaperPlanCall] = [original.calls[0]]
    for i, (subset, candidate) in enumerate(pinned_leaves, start=1):
        if _pin_source_attested_paper_edge(
            index, router, query, group=subset, principal=principal,
            root_route_id=candidate.producer_route_id,
            consumer_route_id=candidate.consumer_route_id,
            bindings=candidate.parameter_bindings, k=k,
        ) != candidate:
            raise PolicyViolationError("paper original edge changed during observation")
        values = _materialize_original_observed_edge(
            index, router, candidate, observation,
        )
        if _pin_source_attested_paper_edge(
            index, router, query, group=subset, principal=principal,
            root_route_id=candidate.producer_route_id,
            consumer_route_id=candidate.consumer_route_id,
            bindings=candidate.parameter_bindings, k=k,
        ) != candidate:
            raise PolicyViolationError("paper original edge changed during binding")
        typed = original.calls[i].call.model_copy(deep=True, update={
            "arguments": values.arguments,
            "missing_required_arguments": [],
        })
        bound.append(replace(original.calls[i], call=typed))

    # Do not let an observation from a now-revoked root publish populated
    # consumer calls. Reapply the SAME current executor data-scope preflight.
    _check_current_call_scopes(router, principal, bound)
    if compile_paper_typed_tool_plan(
        router, query, principal=principal, catalog=catalog, index=index,
        host_source_arguments=host_source_arguments,
        alternative_index=alternative_index, k=k,
    ) != original:
        raise PolicyViolationError("paper source eligibility changed during binding")

    return PaperObservedBinding(
        producer=observation,
        plan=replace(original, status="ready", calls=tuple(bound)),
    )


def _pin_source_attested_paper_edge(
    index: NativeSchemaGraphIndex,
    router: SchemaRouter,
    query: str,
    *,
    group: NativeDeclaredFieldGroup,
    principal: PrincipalContext,
    root_route_id: str,
    consumer_route_id: str,
    bindings: tuple[tuple[str, str], ...],
    k: int,
) -> NativeIndexedGraphCandidate:
    """Reprove ONE P1-selected original edge, not an unrelated public K5 menu."""
    if not bindings:
        raise PolicyViolationError("paper leaf lacks exact original bindings")
    # This private mode is safe ONLY after the full P1 required-field proof
    # pinned these exact route identities. It performs G5's normal source,
    # authorization, scope, fingerprint and health validations, and no
    # candidate/over-K count is ever exposed to the public response.
    current = index._lookup_native_paths(
        router, query, group=group, principal=principal, k=k,
        _fork_arm_internal=True,
        _fork_root_filter=frozenset({root_route_id}),
        _fork_target_filter=frozenset({consumer_route_id}),
    )
    found = tuple(
        candidate for candidate in current.candidates
        if candidate.producer_route_id == root_route_id
        and candidate.consumer_route_id == consumer_route_id
        and candidate.parameter_bindings == bindings
    ) if current.status in ("complete", "internal_fork_arm") else ()
    if len(found) != 1 or len(current.candidates) != 1:
        raise PolicyViolationError("paper leaf lacks unique current source-typed edge")
    return found[0]
