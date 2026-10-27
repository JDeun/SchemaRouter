"""Opt-in A5 scoped Understand -> typed plan -> existing fixed5 episode.

The trusted host owns model, principal-scoped view, catalog and registry.
This adapter never executes typed plan calls or dependency bindings.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any

from schemarouter import PolicyViolationError
from schemarouter.concept_retrieval import NativeConceptCatalog
from schemarouter.native_graph_index import NativeSchemaGraphIndex
from schemarouter.paper_understood_direct_plan import PaperIntentRegistry
from scripts.agent_utility_generated_common import GeneratedEpisodeAgent
from scripts.research_authorized_agent_tool_surface import AuthorizedAgentToolSurface
from scripts.research_paper_a5_runtime_source_binding_e0 import (
    build_paper_a5_root_binding_e0,
)
from scripts.research_paper_fixed5_episode_e0 import run_paper_fixed5_episode_e0
from scripts.research_paper_refusal_eval_e0 import Decision
from scripts.research_paper_reviewed_model_arguments_e0 import PaperRootArgumentReviewer
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
    host_source_arguments: dict[str, dict[str, Any]] | None = None,
    review_model_root_arguments: PaperRootArgumentReviewer | None = None,
) -> tuple[Decision, dict[str, Any]]:
    """Perform one scoped model analysis before the unchanged frozen executor.

    The decision is a research diagnostic. It does not authorize execution,
    and it is not a calibrated no-fit result.
    """
    if not isinstance(view, AuthorizedAgentToolSurface):
        raise ValueError("principal-scoped source view required")
    if type(task) is not dict or task.get("query") != view.original_query:
        raise ValueError("episode task/query mismatch")
    original_host_inputs = deepcopy(host_source_arguments)

    def check_host_inputs() -> None:
        if host_source_arguments != original_host_inputs:
            raise PolicyViolationError("paper episode host source inputs changed")

    check_host_inputs()
    view.assert_source_unchanged()
    decision, plan = await analyze_and_plan_paper_scoped_e0(
        model,
        view=view,
        catalog=catalog,
        intent_registry=intent_registry,
        index=index,
        model_visible_intent_ids=model_visible_intent_ids,
        model_visible_concept_ids=model_visible_concept_ids,
        host_source_arguments=host_source_arguments,
        review_model_root_arguments=review_model_root_arguments,
    )
    check_host_inputs()
    view.assert_source_unchanged()
    # A5 previously exposed a `requires_arguments` direct route so its
    # existing agent could request a value. The new explicit host-review
    # branch must NOT fall back to that path after a denied/missing review:
    # the untrusted model could otherwise call an unreviewed route. An empty
    # explicit host mapping is not authorization to bypass this reviewer gate.
    # Keep legacy behavior unchanged when no reviewer was supplied.
    episode_plan = (
        None if review_model_root_arguments is not None
        and decision == "request_arguments" else plan
    )
    # Preserve the legacy A5 episode path exactly when no host ever supplied
    # or reviewed an input; there is nothing for the source binder to grant.
    source_binding = None
    if host_source_arguments is not None or review_model_root_arguments is not None:
        source_binding = build_paper_a5_root_binding_e0(
            view=view, plan=episode_plan, index=index,
            catalog=catalog, intent_registry=intent_registry,
            host_review_or_inputs_supplied=True,
        )
    episode = run_paper_fixed5_episode_e0(
        agent, view=view, task=task, plan=episode_plan,
        scoped_host_call_binding=source_binding,
    )
    view.assert_source_unchanged()
    check_host_inputs()
    return decision, episode
