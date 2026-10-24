"""Opt-in original-paper P2 producer-to-consumer execution, never default routing.

All values originate from the *internal* registered executor observation. A
publicly constructible PaperObservedBinding is never accepted as authority.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from typing import TYPE_CHECKING, Any

from .authorization import PrincipalContext
from .concept_retrieval import NativeConceptCatalog
from .errors import PolicyViolationError, SchemaValidationError
from .models import ExecutionPlan, ToolResult
from .native_graph_index import NativeSchemaGraphIndex
from .paper_observed_binding import observe_and_bind_paper_plan
from .paper_typed_tool_plan import (
    PaperTypedToolPlan,
    _check_current_call_scopes,
    compile_paper_typed_tool_plan,
)
from .runs import ExecutionBudget, RunConfig

if TYPE_CHECKING:
    from .runtime import SchemaRouter


@dataclass(frozen=True, slots=True)
class PaperExecutedToolSequence:
    """Locally executed original tools; not source-authenticated/E2 evidence."""

    producer: ToolResult
    consumers: tuple[ToolResult, ...]
    plan: PaperTypedToolPlan
    provider_provenance_verified: bool = False
    executable_authority: bool = False
    independent_e2: bool = False


async def observe_and_execute_paper_plan(
    router: SchemaRouter,
    query: str,
    *,
    principal: PrincipalContext,
    catalog: NativeConceptCatalog,
    index: NativeSchemaGraphIndex,
    host_source_arguments: dict[str, dict[str, Any]] | None = None,
    alternative_index: int = 0,
    k: int = 5,
) -> PaperExecutedToolSequence:
    """Run 1 approved producer then its original K5 leaves, serially.

    Each consumer gets a fresh current proof, executor authorization, and an
    independent *one call, one attempt* budget. No bound receipt can be
    injected, no extra consumer invoked, and no partial success is returned.
    """
    initial_claims = principal.model_dump_json()
    pinned_principal = principal.model_copy(deep=True)

    def check_principal() -> None:
        # Caller claims and the executor's own copy must remain the SAME
        # trusted identity as the original observed producer. In particular,
        # mutating a PrincipalContext during an awaited handler cannot turn
        # a tenant-A record identifier into a tenant-B authorized lookup.
        if (
            principal.model_dump_json() != initial_claims
            or pinned_principal.model_dump_json() != initial_claims
        ):
            raise PolicyViolationError("paper consumer principal claims changed")

    observed = await observe_and_bind_paper_plan(
        router, query, principal=pinned_principal, catalog=catalog, index=index,
        host_source_arguments=host_source_arguments,
        alternative_index=alternative_index, k=k,
    )
    check_principal()
    plan = observed.plan
    if (
        plan.status != "ready" or plan.executable_authority
        or len(plan.calls) < 2 or len(plan.calls) > k
        or len(plan.bindings) < len(plan.calls) - 1
    ):
        raise PolicyViolationError("paper consumer execution requires a bound original plan")

    def check_current() -> None:
        check_principal()
        current = compile_paper_typed_tool_plan(
            router, query, principal=pinned_principal, catalog=catalog, index=index,
            host_source_arguments=host_source_arguments,
            alternative_index=alternative_index, k=k,
        )
        if (
            current.status != "requires_observation"
            or current.snapshot_id != plan.snapshot_id
            or current.registry_version != plan.registry_version
            or current.requested_k != plan.requested_k
            or current.bindings != plan.bindings
            or len(current.calls) != len(plan.calls)
            or current.calls[0] != plan.calls[0]
        ):
            raise PolicyViolationError("paper consumer original proof changed")
        for original, bound in zip(current.calls[1:], plan.calls[1:], strict=True):
            if (
                not bound.call.executable
                or replace(bound, call=bound.call.model_copy(deep=True, update={
                    "arguments": original.call.arguments,
                    "missing_required_arguments": original.call.missing_required_arguments,
                })) != original
            ):
                raise PolicyViolationError("paper consumer source typed shape changed")
        _check_current_call_scopes(router, pinned_principal, list(plan.calls))
        check_principal()

    outcomes: list[ToolResult] = []
    for entry in plan.calls[1:]:
        check_current()
        call = entry.call.model_copy(deep=True)
        results = await router.execute(ExecutionPlan(
            query=query, registry_version=plan.registry_version, calls=[call],
        ), config=RunConfig(principal=pinned_principal, budget=ExecutionBudget(
            max_tool_calls=1, max_attempts=1, max_remote_attempts=1,
        )))
        check_principal()
        if (
            len(results) != 1 or not isinstance(results[0], ToolResult)
            or (results[0].tool, results[0].endpoint) != (call.tool, call.endpoint)
        ):
            raise SchemaValidationError("paper consumer returned unexpected tool result")
        # The executor provides presence-only field contracts using each
        # FieldSpec.result_projection_path, including nested/wildcard paths.
        # Checking literal top-level keys would reject legitimate projections
        # such as `status -> details.state`. Empty batches are valid no-match
        # results, not factual field observations.
        data = results[0].data
        records = [data] if isinstance(data, dict) else data
        if (
            not isinstance(records, list)
            or any(not isinstance(record, dict) for record in records)
            or bool(records) and any(
                field not in results[0].field_contracts for field in call.fields
            )
        ):
            raise SchemaValidationError("paper consumer required output field missing")
        check_current()
        outcomes.append(results[0])

    check_principal()
    return PaperExecutedToolSequence(
        producer=observed.producer, consumers=tuple(outcomes), plan=plan,
    )
