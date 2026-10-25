"""E0 bounded model -> current source-proven paper plan, without execution.

The existing agent remains the only tool executor. A graph plan is a
non-executing receipt, not an executable agent tool menu.
"""
from __future__ import annotations

from schemarouter import PolicyViolationError
from schemarouter.concept_retrieval import NativeConceptCatalog
from schemarouter.native_graph_index import NativeSchemaGraphIndex
from schemarouter.paper_typed_tool_plan import PaperTypedToolPlan
from schemarouter.paper_understood_direct_plan import PaperIntentRegistry
from schemarouter.paper_understood_graph_plan import compile_paper_understood_graph_plan
from scripts.research_authorized_agent_tool_surface import AuthorizedAgentToolSurface
from scripts.research_paper_refusal_eval_e0 import Decision, decision_from_plan_status
from scripts.research_paper_scoped_understand_e0 import (
    PaperScopedModel,
    analyze_paper_understanding_scoped,
)


async def analyze_and_plan_paper_scoped_e0(
    model: PaperScopedModel,
    *,
    view: AuthorizedAgentToolSurface,
    catalog: NativeConceptCatalog,
    intent_registry: PaperIntentRegistry,
    index: NativeSchemaGraphIndex,
    model_visible_intent_ids: tuple[str, ...],
    model_visible_concept_ids: tuple[str, ...],
) -> tuple[Decision, PaperTypedToolPlan | None]:
    """Exactly one scoped Understand call followed by a reauthorized plan.

    An empty authorized menu does not call the model. No tool is executed;
    a dependency plan is only a source-bound research receipt.
    """
    if not isinstance(view, AuthorizedAgentToolSurface):
        raise ValueError("current principal-scoped view required")
    if not isinstance(index, NativeSchemaGraphIndex):
        raise ValueError("source-pinned graph index required")
    view.assert_source_unchanged()
    understanding = await analyze_paper_understanding_scoped(
        model, view=view, intent_registry=intent_registry, catalog=catalog,
        model_visible_intent_ids=model_visible_intent_ids,
        model_visible_concept_ids=model_visible_concept_ids,
    )
    view.assert_source_unchanged()
    if understanding is None:
        return "abstain", None
    plan = compile_paper_understood_graph_plan(
        view.router, understanding, principal=view._principal,
        catalog=catalog, intent_registry=intent_registry, index=index,
    )
    view.assert_source_unchanged()
    if plan.executable_authority:
        raise PolicyViolationError("paper research plan cannot authorize execution")
    if plan.status == "requires_observation" and not plan.bindings:
        raise PolicyViolationError("dependency plan missing typed bindings")
    if plan.status == "ready" and plan.bindings:
        raise PolicyViolationError("direct plan unexpectedly has dependency bindings")
    return decision_from_plan_status(plan.status), plan
