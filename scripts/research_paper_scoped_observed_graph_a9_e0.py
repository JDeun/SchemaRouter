"""A9 E0 opt-in scoped one-shot Understand → native observed G5 execution.

This composes the existing principal-scoped model callback and the *existing*
registered SchemaRouter executor. It does not synthesize answers, replace the
fixed5 agent loop or assert provider-authenticated task success.
"""

from __future__ import annotations

from typing import Any

from schemarouter import PolicyViolationError
from schemarouter.concept_retrieval import NativeConceptCatalog
from schemarouter.native_graph_index import NativeSchemaGraphIndex
from schemarouter.paper_native_rank import PaperNativeRankPolicy
from schemarouter.paper_consumer_execution import (
    PaperUnderstoodExecutedGraph,
    observe_and_execute_paper_understood_graph,
)
from schemarouter.paper_understood_direct_plan import PaperIntentRegistry
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


async def run_paper_scoped_named_graph_a9_e0(
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
    rank_policy: PaperNativeRankPolicy | None = None,
    allow_unnamed_graph_discovery: bool = False,
) -> tuple[Decision, PaperUnderstoodExecutedGraph | None]:
    """Execute an exact source-approved 1-/2-hop named graph, if available.

    A missing host-owned root input is deferred without any tool I/O. Every
    intermediate node must be within the host's **original captured** route
    inventory. `offer` with a result means only local observations succeeded;
    it is not an answer-quality verdict or evidence of independent E2.
    """
    if not isinstance(view, AuthorizedAgentToolSurface):
        raise ValueError("captured principal-scoped source view required")
    if not isinstance(index, NativeSchemaGraphIndex):
        raise ValueError("pinned original G5 index required")
    if rank_policy is not None and not isinstance(rank_policy, PaperNativeRankPolicy):
        raise ValueError("reviewed paper A9 owner Rank required")
    if (
        type(allow_unnamed_graph_discovery) is not bool
        or allow_unnamed_graph_discovery and rank_policy is None
    ):
        raise ValueError("paper A9 unnamed G5 needs host-approved owner Rank")
    try:
        original_rank = (
            rank_policy.model_dump_json() if rank_policy is not None else None
        )
        if rank_policy is not None and (
            rank_policy.snapshot_id != index.field_index.snapshot_id
            or not (
                set(rank_policy.route_domains)
                | set(rank_policy.route_priorities)
                | set(rank_policy.web_route_ids)
            ) <= index.field_index.route_locations.keys()
        ):
            raise ValueError("Rank snapshot or annotations not current")
    except Exception:
        raise PolicyViolationError("paper A9 owner Rank preflight failed") from None

    def check_rank() -> None:
        try:
            if (
                rank_policy.model_dump_json() if rank_policy is not None else None
            ) != original_rank:
                raise ValueError("owner mutation")
        except Exception:
            raise PolicyViolationError("paper A9 owner Rank changed") from None

    check_rank()
    view.assert_source_unchanged()
    understood = await analyze_paper_understanding_scoped(
        model,
        view=view, intent_registry=intent_registry, catalog=catalog,
        model_visible_intent_ids=model_visible_intent_ids,
        model_visible_concept_ids=model_visible_concept_ids,
    )
    view.assert_source_unchanged()
    check_rank()
    if understood is None:
        return "abstain", None
    plan = compile_paper_understood_graph_plan(
        view.router, understood, principal=view._principal, catalog=catalog,
        intent_registry=intent_registry, index=index,
        host_source_arguments=host_source_arguments,
        rank_policy=rank_policy,
        allow_unnamed_graph_discovery=allow_unnamed_graph_discovery,
    )
    view.assert_source_unchanged()
    check_rank()
    approved_inputs = host_source_arguments
    if (
        review_model_root_arguments is not None
        and host_source_arguments is None
        and plan.status in ("requires_arguments", "requires_observation")
        and plan.calls
        and plan.calls[0].call.missing_required_arguments
    ):
        reviewed = await review_paper_root_model_arguments_e0(
            review_model_root_arguments,
            view=view, understanding=understood, plan=plan, index=index,
            catalog=catalog, intent_registry=intent_registry,
        )
        if reviewed is not None:
            approved_inputs = reviewed
            plan = compile_paper_understood_graph_plan(
                view.router, understood, principal=view._principal,
                catalog=catalog, intent_registry=intent_registry, index=index,
                host_source_arguments=approved_inputs,
                rank_policy=rank_policy,
                allow_unnamed_graph_discovery=allow_unnamed_graph_discovery,
            )
            view.assert_source_unchanged()
            check_rank()
    if plan.executable_authority:
        raise PolicyViolationError("paper named graph is not an execution grant")
    if plan.status != "requires_observation":
        return decision_from_plan_status(plan.status), None
    if (
        not 2 <= len(plan.calls) <= 3
        or not plan.bindings
        or not {call.route_id for call in plan.calls}
        <= set(view.visible_route_ids)
    ):
        # An original principal-authorized route that was not captured for
        # the single scoped Understand request is still NOT available to
        # this model/agent episode; never expose its name or execute it.
        return "abstain", None
    if plan.calls[0].call.missing_required_arguments:
        return "request_arguments", None
    receipt = await observe_and_execute_paper_understood_graph(
        view.router, understood, principal=view._principal, catalog=catalog,
        intent_registry=intent_registry, index=index,
        host_source_arguments=approved_inputs, rank_policy=rank_policy,
        allow_unnamed_graph_discovery=allow_unnamed_graph_discovery,
    )
    view.assert_source_unchanged()
    check_rank()
    if receipt.executable_authority or receipt.independent_e2:
        raise PolicyViolationError("paper observed graph cannot assert E2 authority")
    return "offer", receipt
