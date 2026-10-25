"""Opt-in A5 scoped Understand -> typed plan -> existing fixed5 episode.

The trusted host owns model, principal-scoped view, catalog and registry.
This adapter never executes typed plan calls or dependency bindings.
"""
from __future__ import annotations

from typing import Any

from schemarouter.concept_retrieval import NativeConceptCatalog
from schemarouter.native_graph_index import NativeSchemaGraphIndex
from schemarouter.paper_understood_direct_plan import PaperIntentRegistry
from scripts.agent_utility_generated_common import GeneratedEpisodeAgent
from scripts.research_authorized_agent_tool_surface import AuthorizedAgentToolSurface
from scripts.research_paper_fixed5_episode_e0 import run_paper_fixed5_episode_e0
from scripts.research_paper_refusal_eval_e0 import Decision
from scripts.research_paper_scoped_plan_e0 import analyze_and_plan_paper_scoped_e0
from scripts.research_paper_scoped_understand_e0 import PaperScopedModel


async def run_paper_scoped_agent_episode_e0(
    model: PaperScopedModel,
    agent: GeneratedEpisodeAgent,
    *,
    view: AuthorizedAgentToolSurface,
    task: dict[str, Any],
    catalog: NativeConceptCatalog,
    intent_registry: PaperIntentRegistry,
    index: NativeSchemaGraphIndex,
    model_visible_intent_ids: tuple[str, ...],
    model_visible_concept_ids: tuple[str, ...],
) -> tuple[Decision, dict[str, Any]]:
    """Perform one scoped model analysis before the unchanged frozen executor.

    The decision is a research diagnostic. It does not authorize execution,
    and it is not a calibrated no-fit result.
    """
    if not isinstance(view, AuthorizedAgentToolSurface):
        raise ValueError("principal-scoped source view required")
    if type(task) is not dict or task.get("query") != view.original_query:
        raise ValueError("episode task/query mismatch")
    view.assert_source_unchanged()
    decision, plan = await analyze_and_plan_paper_scoped_e0(
        model,
        view=view,
        catalog=catalog,
        intent_registry=intent_registry,
        index=index,
        model_visible_intent_ids=model_visible_intent_ids,
        model_visible_concept_ids=model_visible_concept_ids,
    )
    view.assert_source_unchanged()
    episode = run_paper_fixed5_episode_e0(
        agent, view=view, task=task, plan=plan,
    )
    view.assert_source_unchanged()
    return decision, episode
