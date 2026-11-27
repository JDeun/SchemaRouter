"""Checkout-only historical A9 understood-graph producer-to-consumer execution.

All values originate from the internal registered executor observation.
Algorithm 1 does not discover or execute producer-to-consumer dependency DAGs.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, replace
from typing import TYPE_CHECKING, Any

from schemarouter.authorization import PrincipalContext
from schemarouter.concept_retrieval import NativeConceptCatalog
from schemarouter.errors import PolicyViolationError, SchemaValidationError
from schemarouter.models import ExecutionPlan, ToolResult
from schemarouter.native_graph_index import NativeIndexedGraphCandidate, NativeSchemaGraphIndex
from schemarouter.paper_typed_tool_plan import (
    PaperTypedToolPlan,
    _check_current_call_scopes,
)
from schemarouter.paper_understood_direct_plan import PaperIntentRegistry, PaperUnderstanding
from schemarouter.runs import ExecutionBudget, RunConfig
from scripts.research_legacy_direct_rank import PaperNativeRankPolicy
from scripts.research_legacy_graph_observation import _materialize_original_observed_edge
from scripts.research_legacy_paper_graph_plan import compile_paper_understood_graph_plan

if TYPE_CHECKING:
    from schemarouter.runtime import SchemaRouter


@dataclass(frozen=True, slots=True)
class PaperUnderstoodExecutedGraph:
    """Executed source-proven named DAG, with no provider/E2 authority claim."""

    results: tuple[ToolResult, ...]
    plan: PaperTypedToolPlan
    provider_provenance_verified: bool = False
    executable_authority: bool = False
    independent_e2: bool = False


def _original_named_plan_edge(
    plan: PaperTypedToolPlan, producer_index: int,
) -> NativeIndexedGraphCandidate:
    """Make the existing scalar checker input from an already-proven full DAG.

    The caller MUST prove the exact original 1-/2-hop G5 plan before AND
    after using this shape. It never authorizes a standalone new graph edge.
    """
    consumer_index = producer_index + 1
    producer, consumer = plan.calls[producer_index:consumer_index + 1]
    bindings = tuple(
        (b.parameter, b.producer_field) for b in plan.bindings
        if b.consumer_call_index == consumer_index
        and b.producer_call_index == producer_index
    )
    if (
        not bindings
        or len(bindings) != len({b.parameter for b in plan.bindings
                                if b.consumer_call_index == consumer_index})
        or len(bindings) != len({b.parameter for b in plan.bindings
                                if b.consumer_call_index == consumer_index
                                and b.producer_call_index == producer_index})
        or any(b.producer_call_index != producer_index
               for b in plan.bindings if b.consumer_call_index == consumer_index)
        or not producer.call.tool_fingerprint
        or not producer.call.schema_fingerprint
        or not consumer.call.tool_fingerprint
        or not consumer.call.schema_fingerprint
    ):
        raise PolicyViolationError("paper named graph has incomplete consecutive bindings")
    return NativeIndexedGraphCandidate(
        producer_route_id=producer.route_id,
        consumer_route_id=consumer.route_id,
        producer_tool_fingerprint=producer.call.tool_fingerprint,
        producer_endpoint_fingerprint=producer.call.schema_fingerprint,
        consumer_tool_fingerprint=consumer.call.tool_fingerprint,
        consumer_endpoint_fingerprint=consumer.call.schema_fingerprint,
        producer_identifier_field=bindings[0][1] if len(bindings) == 1 else None,
        consumer_required_parameter=bindings[0][0] if len(bindings) == 1 else None,
        consumer_output_fields=tuple(consumer.call.fields),
        parameter_bindings=bindings,
    )


async def observe_and_execute_paper_understood_graph(
    router: SchemaRouter,
    understanding: PaperUnderstanding,
    *,
    principal: PrincipalContext,
    catalog: NativeConceptCatalog,
    intent_registry: PaperIntentRegistry,
    index: NativeSchemaGraphIndex,
    host_source_arguments: dict[str, dict[str, Any]] | None = None,
    k: int = 5,
    max_hops: int = 2,
    rank_policy: PaperNativeRankPolicy | None = None,
    allow_unnamed_graph_discovery: bool = False,
) -> PaperUnderstoodExecutedGraph:
    """Explicit E0 1-/2-hop named G5 DAG using the registered executor only.

    Model hints choose a currently permitted target but NEVER provide inputs.
    A producer's actual projected scalar is validated by the existing native
    observer before the independently authorized next tool runs. No partial
    receipt is published when any step fails or the source proof changes.
    """
    intent_id = understanding.intent_id
    if intent_id is None:
        raise ValueError("paper named graph requires a registered intent")
    if (
        rank_policy is not None
        and not isinstance(rank_policy, PaperNativeRankPolicy)
    ):
        raise ValueError("A9 owner-reviewed Rank policy required")
    if (
        type(allow_unnamed_graph_discovery) is not bool
        or allow_unnamed_graph_discovery and rank_policy is None
    ):
        raise ValueError("A9 unnamed G5 execution requires host-approved owner Rank")
    try:
        initial_rank_policy = (
            rank_policy.model_dump_json() if rank_policy is not None else None
        )
        owner_claims = (
            principal.model_dump_json(), understanding.model_dump_json(),
            catalog.model_dump_json(), intent_registry.model_dump_json(),
        )
    except Exception:
        raise PolicyViolationError("A9 owner source declarations invalid") from None
    host_snapshot = deepcopy(host_source_arguments)
    pinned_principal = principal.model_copy(deep=True)

    def check_owner() -> None:
        try:
            changed = (
                (
                    principal.model_dump_json(), understanding.model_dump_json(),
                    catalog.model_dump_json(), intent_registry.model_dump_json(),
                ) != owner_claims
                or pinned_principal.model_dump_json() != owner_claims[0]
                or host_source_arguments != host_snapshot
                or (
                    rank_policy.model_dump_json() if rank_policy is not None else None
                ) != initial_rank_policy
            )
        except Exception:
            raise PolicyViolationError(
                "paper named graph owner source declarations changed"
            ) from None
        if changed:
            raise PolicyViolationError(
                "paper named graph principal or source declarations changed"
            )

    check_owner()
    original = compile_paper_understood_graph_plan(
        router, understanding, principal=pinned_principal, catalog=catalog,
        intent_registry=intent_registry, index=index, k=k, max_hops=max_hops,
        host_source_arguments=host_snapshot, rank_policy=rank_policy,
        allow_unnamed_graph_discovery=allow_unnamed_graph_discovery,
    )
    if (
        original.status != "requires_observation"
        or original.executable_authority
        or len(original.calls) not in (2, 3)
        or len(original.calls) > k
        or original.calls[0].call.missing_required_arguments
        or not original.calls[0].call.executable
        or {b.consumer_call_index for b in original.bindings}
        != set(range(1, len(original.calls)))
    ):
        raise PolicyViolationError("paper named graph requires approved runnable root")

    # A full named G5 result proves *both* edges. Deriving a fresh public
    # one-hop path from the middle would incorrectly reject valid typed
    # intermediaries that are not independently approved host roots.
    edges = tuple(
        _original_named_plan_edge(original, position)
        for position in range(len(original.calls) - 1)
    )

    def check_current(bound: list[Any]) -> None:
        check_owner()
        current = compile_paper_understood_graph_plan(
            router, understanding, principal=pinned_principal, catalog=catalog,
            intent_registry=intent_registry, index=index, k=k, max_hops=max_hops,
            host_source_arguments=host_snapshot, rank_policy=rank_policy,
            allow_unnamed_graph_discovery=allow_unnamed_graph_discovery,
        )
        if current != original:
            raise PolicyViolationError("paper named graph original G5 proof changed")
        # Only original producer observations may fill later calls. The
        # current source plan is the exact typed/scoped call shape for all
        # unbound parameters; the bound differences are solely concrete args.
        for position, entry in enumerate(bound):
            source_entry = original.calls[position]
            if (
                not entry.call.executable
                or replace(entry, call=entry.call.model_copy(deep=True, update={
                    "arguments": source_entry.call.arguments,
                    "missing_required_arguments": source_entry.call.missing_required_arguments,
                })) != source_entry
            ):
                raise PolicyViolationError("paper named graph bound call shape changed")
        _check_current_call_scopes(router, pinned_principal, bound)
        check_owner()

    bound = [original.calls[0]]
    observations: list[ToolResult] = []
    for position in range(len(original.calls)):
        check_current(bound)
        actual = bound[position].call.model_copy(deep=True)
        if not actual.executable or actual.missing_required_arguments:
            raise SchemaValidationError("paper named graph tool input is incomplete")
        results = await router.execute(ExecutionPlan(
            query=intent_id,
            registry_version=original.registry_version,
            calls=[actual],
        ), config=RunConfig(
            principal=pinned_principal,
            budget=ExecutionBudget(
                max_tool_calls=1, max_attempts=1, max_remote_attempts=1,
            ),
        ))
        check_current(bound)
        if (
            len(results) != 1 or not isinstance(results[0], ToolResult)
            or (results[0].tool, results[0].endpoint)
            != (actual.tool, actual.endpoint)
        ):
            raise SchemaValidationError("paper named graph returned unexpected tool result")
        observed = results[0]
        records = [observed.data] if isinstance(observed.data, dict) else observed.data
        if (
            not isinstance(records, list)
            or any(not isinstance(record, dict) for record in records)
            or bool(records) and any(
                field not in observed.field_contracts for field in actual.fields
            )
        ):
            raise SchemaValidationError("paper named graph required output field missing")
        if position < len(edges):
            values = _materialize_original_observed_edge(
                index, router, edges[position], observed,
            )
            # A JSON `string` schema can permit "", but an empty observed
            # identifier must not trigger a dependent read in the named DAG.
            if any(type(value) is str and not value
                   for value in values.arguments.values()):
                raise SchemaValidationError("paper named graph observed empty identifier")
            check_current(bound)
            later = original.calls[position + 1]
            bound_call = later.call.model_copy(deep=True, update={
                "arguments": values.arguments,
                "missing_required_arguments": [],
            })
            bound.append(replace(later, call=bound_call))
            check_current(bound)
        observations.append(observed)

    check_current(bound)
    return PaperUnderstoodExecutedGraph(
        results=tuple(observations),
        plan=replace(original, status="ready", calls=tuple(bound)),
    )
