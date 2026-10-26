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
from schemarouter.paper_consumer_execution import (
    PaperUnderstoodExecutedGraph,
    observe_and_execute_paper_understood_graph,
)
from schemarouter.paper_understood_direct_plan import PaperIntentRegistry
from schemarouter.paper_understood_graph_plan import compile_paper_understood_graph_plan
from scripts.research_authorized_agent_tool_surface import AuthorizedAgentToolSurface
from scripts.research_paper_refusal_eval_e0 import Decision, decision_from_plan_status
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
    view.assert_source_unchanged()
    understood = await analyze_paper_understanding_scoped(
        model,
        view=view, intent_registry=intent_registry, catalog=catalog,
        model_visible_intent_ids=model_visible_intent_ids,
        model_visible_concept_ids=model_visible_concept_ids,
    )
    view.assert_source_unchanged()
    if understood is None:
        return "abstain", None
    plan = compile_paper_understood_graph_plan(
        view.router, understood, principal=view._principal, catalog=catalog,
        intent_registry=intent_registry, index=index,
        host_source_arguments=host_source_arguments,
    )
    view.assert_source_unchanged()
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
        host_source_arguments=host_source_arguments,
    )
    view.assert_source_unchanged()
    if receipt.executable_authority or receipt.independent_e2:
        raise PolicyViolationError("paper observed graph cannot assert E2 authority")
    return "offer", receipt
