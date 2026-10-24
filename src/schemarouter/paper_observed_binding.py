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
from .native_graph_index import NativeSchemaGraphIndex
from .native_graph_observation import materialize_native_observed_arguments
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

    group = resolve_native_concepts(query, catalog=catalog).field_group
    routes = selected.alternatives[alternative_index].routes
    root_route_id = routes[0].route_id
    bound: list[PaperPlanCall] = [original.calls[0]]
    for i, receipt in enumerate(routes[1:], start=1):
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
        matches = index.lookup(
            router, query, group=subset, principal=principal, k=k,
        )
        binding_pairs = tuple(
            (parameter, field)
            for parameter, producer, field in receipt.input_bindings
            if producer == root_route_id
        )
        candidates = tuple(
            candidate for candidate in matches.candidates
            if candidate.producer_route_id == root_route_id
            and candidate.consumer_route_id == receipt.route_id
            and candidate.parameter_bindings == binding_pairs
        ) if matches.status == "complete" else ()
        if len(candidates) != 1 or not binding_pairs:
            raise PolicyViolationError("paper leaf has no unique current typed edge")
        values = materialize_native_observed_arguments(
            index, router, query=query, group=subset,
            principal=principal, candidate=candidates[0], observation=observation,
        )
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
