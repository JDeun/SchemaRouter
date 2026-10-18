"""E1 research: derive callable tool menu from original native required inputs.

Not a planner, model ranker, permission grant, or provider invocation.
Caller supplies only trusted host request parameters and *executed*,
principal-projected prior observations; never future/expected task gold.
"""
from __future__ import annotations

import math
from typing import Any

from schemarouter import PolicyViolationError
from scripts.research_authorized_agent_tool_surface import (
    AuthorizedAgentToolSurface,
)


def _safe_values(values: dict[str, Any]) -> bool:
    return (
        type(values) is dict and len(values) <= 32
        and all(
            type(k) is str and k.isidentifier() and
            type(v) in (str, int, float, bool) and
            (type(v) is not float or math.isfinite(v))
            for k, v in values.items()
        )
    )


def source_ready_visible_routes(
    view: AuthorizedAgentToolSurface,
    *,
    host_request_inputs: dict[str, Any],
    prior_public_observation: dict[str, Any] | None,
    executed_route_ids: tuple[str, ...],
) -> tuple[str, ...]:
    """Filter ONLY existing authorized native tool IDs by required input presence.

    The caller MUST have validated the actual provider observation and
    projected data scope before handing it here. This never supplies or
    guesses argument values, never acquires new tool permissions, and never
    reads unobserved original provider/private source fields.
    """
    if not isinstance(view, AuthorizedAgentToolSurface):
        raise PolicyViolationError("an authenticated source tool view is required")
    if (
        not _safe_values(host_request_inputs)
        or prior_public_observation is not None
        and (not _safe_values(prior_public_observation)
             or prior_public_observation.get("status") != "ok")
        or type(executed_route_ids) is not tuple
        or len(executed_route_ids) > 8
        or len(set(executed_route_ids)) != len(executed_route_ids)
        or any(type(x) is not str for x in executed_route_ids)
    ):
        raise ValueError("untrusted current native input/observation state")
    view.assert_source_unchanged()
    visible = tuple(view.visible_route_ids)
    if not set(executed_route_ids).issubset(visible):
        raise PolicyViolationError("executed route absent from current authority")
    available = set(host_request_inputs)
    if prior_public_observation is not None:
        available.update(prior_public_observation)
        available.discard("status")
    ready: list[str] = []
    for route in visible:
        if route in executed_route_ids:
            continue
        tool_key, separator, ep_name = route.rpartition(".")
        if not separator or not tool_key or not ep_name:
            raise PolicyViolationError("invalid original registered route identity")
        tool = view.router.registry.get(tool_key)
        endpoint = tool.endpoint(ep_name)
        if f"{tool.key}.{endpoint.name}" != route:
            raise PolicyViolationError("native endpoint identity mismatch")
        if endpoint.read_only is not True or endpoint.destructive is True:
            continue
        if endpoint.auth_requirements:
            # Presence of trusted parameters is not a credential.
            continue
        if all(
            parameter.name in available
            for parameter in endpoint.parameters
            if parameter.required
        ):
            ready.append(route)
    view.assert_source_unchanged()
    return tuple(ready)
