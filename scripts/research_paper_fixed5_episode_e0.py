"""Run the existing opt-in fixed5 episode with a preverified paper plan.

No second executor, no dependency DAG flattening, no frozen benchmark changes.
The host awaits scoped Understand/plan first, then invokes this sync adapter.
"""
from __future__ import annotations

from typing import Any

from schemarouter import PolicyViolationError
from schemarouter.paper_typed_tool_plan import PaperTypedToolPlan
from scripts.agent_utility_generated_common import (
    EXPERIMENTAL_FIXED5_CONDITION,
    GeneratedEpisodeAgent,
    run_generated_episode,
)
from scripts.research_authorized_agent_tool_surface import AuthorizedAgentToolSurface
from scripts.research_paper_fixed5_menu_e0 import paper_plan_fixed5_menu


def run_paper_fixed5_episode_e0(
    agent: GeneratedEpisodeAgent,
    *,
    view: AuthorizedAgentToolSurface,
    task: dict[str, Any],
    plan: PaperTypedToolPlan | None,
) -> dict[str, Any]:
    """Use only existing frozen executor and principal-scoped model exposure."""
    if not isinstance(view, AuthorizedAgentToolSurface):
        raise ValueError("scoped source view required")
    view.assert_source_unchanged()
    if type(task) is not dict or task.get("query") != view.original_query:
        raise ValueError("episode query must match captured scoped source")
    # Verify the receipt BEFORE the original agent sees any route.
    routes = paper_plan_fixed5_menu(view, plan)
    pinned_routes = tuple(routes)

    def select(query: str, source_ids: tuple[str, ...]) -> list[str]:
        view.assert_source_unchanged()
        if query != view.original_query or source_ids != view.visible_route_ids:
            raise PolicyViolationError("paper episode selector source drift")
        # Repeat receipt validation after any asynchronous model callback.
        current = paper_plan_fixed5_menu(view, plan)
        if tuple(current) != pinned_routes:
            raise PolicyViolationError("paper episode route drift")
        return current

    view.assert_source_unchanged()
    return run_generated_episode(
        agent, view.router.registry, task, EXPERIMENTAL_FIXED5_CONDITION,
        experimental_candidate_selector=select,
        experimental_agent_tool_surface=view,
        experimental_host_empty_menu_terminal=True,
    )
