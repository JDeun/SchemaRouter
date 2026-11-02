"""Project verified paper direct plans onto the existing fixed-K agent menu.

This opt-in adapter only returns source-visible route IDs. It never invokes
tools, turns untrusted model parameters into arguments, or flattens typed DAGs.
"""
from __future__ import annotations

from schemarouter import PolicyViolationError
from schemarouter.paper_typed_tool_plan import PaperTypedToolPlan
from scripts.research_authorized_agent_tool_surface import AuthorizedAgentToolSurface
from scripts.research_authorized_fixed5_decision_bridge import _visible_fingerprints


def paper_plan_fixed5_menu(
    view: AuthorizedAgentToolSurface,
    plan: PaperTypedToolPlan | None,
) -> list[str]:
    if not isinstance(view, AuthorizedAgentToolSurface):
        raise ValueError("principal-scoped view required")
    view.assert_source_unchanged()
    if plan is None:
        return []
    if not isinstance(plan, PaperTypedToolPlan):
        raise ValueError("typed source plan required")
    if (
        plan.executable_authority
        or plan.requested_k != 5
        or plan.registry_version != view.witness[1]
    ):
        raise PolicyViolationError("plan does not match fixed-K authority")
    if plan.status in {
        "no_proven_hit", "over_k_unranked", "budget_unsatisfied",
        "ambiguous_paths", "requires_observation",
    }:
        if plan.status == "requires_observation":
            if not plan.calls or not plan.bindings:
                raise PolicyViolationError("incomplete graph plan")
        elif plan.calls or plan.bindings:
            raise PolicyViolationError("abstaining plan disclosed routes")
        view.assert_source_unchanged()
        return []
    if plan.status not in {"ready", "requires_arguments"} or plan.bindings:
        raise PolicyViolationError("not a direct plan")
    routes = [call.route_id for call in plan.calls]
    if (
        not routes or len(routes) > 5 or len(set(routes)) != len(routes)
        or not set(routes).issubset(view.visible_route_ids)
    ):
        raise PolicyViolationError("routes outside authorized source menu")
    pinned = _visible_fingerprints(view)
    if any(
        (call.call.tool_fingerprint, call.call.schema_fingerprint)
        != pinned[call.route_id]
        for call in plan.calls
    ):
        raise PolicyViolationError("route fingerprint mismatch")
    view.tool_definitions(routes, k=5)
    view.assert_source_unchanged()
    return routes
