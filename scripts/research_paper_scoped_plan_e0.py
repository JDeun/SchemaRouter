"""E0 bounded model -> current source-proven paper plan, without execution.

The existing agent remains the only tool executor. A graph plan is a
non-executing receipt, not an executable agent tool menu.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any

from schemarouter import PolicyViolationError
from schemarouter.concept_retrieval import NativeConceptCatalog
from schemarouter.native_graph_index import NativeSchemaGraphIndex
from schemarouter.paper_typed_tool_plan import PaperTypedToolPlan
from schemarouter.paper_understood_direct_plan import (
    PaperIntentRegistry,
    compile_paper_understood_direct_plan,
)
from schemarouter.paper_understood_graph_plan import compile_paper_understood_graph_plan
from scripts.research_authorized_agent_tool_surface import AuthorizedAgentToolSurface
from scripts.research_paper_refusal_eval_e0 import Decision, decision_from_plan_status
from scripts.research_paper_reviewed_model_arguments_e0 import (
    PaperRootArgumentReviewer,
    review_paper_root_model_arguments_e0,
)
from scripts.research_paper_scoped_understand_e0 import (
    PaperScopedModel,
    analyze_paper_understanding_scoped,
)


def _source_proves_single_nondependency_input(
    view: AuthorizedAgentToolSurface, plan: PaperTypedToolPlan,
) -> bool:
    """Keep an unproved semantic dependency out of the existing agent menu."""
    if plan.status != "requires_arguments" or len(plan.calls) != 1 or plan.bindings:
        return False
    call = plan.calls[0].call
    endpoint = view.router.registry.get(call.tool).endpoint(call.endpoint)
    required = set(call.missing_required_arguments)
    ordinary = {
        parameter.name for parameter in endpoint.parameters
        if parameter.semantic_id is None
    }
    return bool(required) and required <= ordinary


async def analyze_and_plan_paper_scoped_e0(
    model: PaperScopedModel,
    *,
    view: AuthorizedAgentToolSurface,
    catalog: NativeConceptCatalog,
    intent_registry: PaperIntentRegistry,
    index: NativeSchemaGraphIndex,
    model_visible_intent_ids: tuple[str, ...],
    model_visible_concept_ids: tuple[str, ...],
    host_source_arguments: dict[str, dict[str, Any]] | None = None,
    review_model_root_arguments: PaperRootArgumentReviewer | None = None,
) -> tuple[Decision, PaperTypedToolPlan | None]:
    """Exactly one scoped Understand call followed by a reauthorized plan.

    An empty authorized menu does not call the model. No tool is executed;
    a dependency plan is only a source-bound research receipt.
    """
    if not isinstance(view, AuthorizedAgentToolSurface):
        raise ValueError("current principal-scoped view required")
    if not isinstance(index, NativeSchemaGraphIndex):
        raise ValueError("source-pinned graph index required")
    if host_source_arguments is not None and (
        type(host_source_arguments) is not dict
        or any(type(route) is not str or type(values) is not dict
               for route, values in host_source_arguments.items())
    ):
        raise ValueError("explicit host source arguments required")
    pinned_host_inputs = deepcopy(host_source_arguments)

    def check_host_inputs() -> None:
        if host_source_arguments != pinned_host_inputs:
            raise PolicyViolationError("scoped paper host source arguments changed")

    check_host_inputs()
    view.assert_source_unchanged()
    understanding = await analyze_paper_understanding_scoped(
        model, view=view, intent_registry=intent_registry, catalog=catalog,
        model_visible_intent_ids=model_visible_intent_ids,
        model_visible_concept_ids=model_visible_concept_ids,
    )
    view.assert_source_unchanged()
    check_host_inputs()
    if understanding is None:
        return "abstain", None
    plan = compile_paper_understood_graph_plan(
        view.router, understanding, principal=view._principal,
        catalog=catalog, intent_registry=intent_registry, index=index,
        host_source_arguments=pinned_host_inputs,
    )
    # The graph-only compiler intentionally refuses an unproved dependency.
    # The existing agent may still request a genuinely scalar source input,
    # but a typed identifier dependency must never silently become one.
    if plan.status == "no_proven_hit":
        direct = compile_paper_understood_direct_plan(
            view.router, understanding, principal=view._principal,
            catalog=catalog, intent_registry=intent_registry, index=index,
            host_source_arguments=pinned_host_inputs,
        )
        if _source_proves_single_nondependency_input(view, direct):
            plan = direct
    if (
        review_model_root_arguments is not None
        and host_source_arguments is None
        and plan.status in ("requires_arguments", "requires_observation")
        and plan.calls
        and plan.calls[0].call.missing_required_arguments
    ):
        reviewed = await review_paper_root_model_arguments_e0(
            review_model_root_arguments, view=view, understanding=understanding,
            plan=plan, index=index,
            catalog=catalog, intent_registry=intent_registry,
        )
        if reviewed is not None:
            plan = compile_paper_understood_graph_plan(
                view.router, understanding, principal=view._principal,
                catalog=catalog, intent_registry=intent_registry, index=index,
                host_source_arguments=reviewed,
            )
    # The graph compiler also returns a direct missing-input receipt when
    # understanding did not name a target. Enforce the same A5 disclosure
    # rule on BOTH entry paths; omission of named_tools cannot bypass it.
    if plan.status == "requires_arguments" and not _source_proves_single_nondependency_input(
        view, plan,
    ):
        plan = PaperTypedToolPlan(
            status="no_proven_hit", snapshot_id=plan.snapshot_id,
            registry_version=plan.registry_version, requested_k=plan.requested_k,
        )
    view.assert_source_unchanged()
    check_host_inputs()
    if plan.executable_authority:
        raise PolicyViolationError("paper research plan cannot authorize execution")
    if plan.status == "requires_observation" and not plan.bindings:
        raise PolicyViolationError("dependency plan missing typed bindings")
    if plan.status == "ready" and plan.bindings:
        raise PolicyViolationError("direct plan unexpectedly has dependency bindings")
    # A dependency graph may be valid but its actual first producer still
    # require a host-owned scalar. Observation cannot start until that root
    # input is supplied; report the actionable deferral, not a runnable DAG.
    if (
        plan.status == "requires_observation"
        and plan.calls
        and plan.calls[0].call.missing_required_arguments
    ):
        return "request_arguments", plan
    return decision_from_plan_status(plan.status), plan
