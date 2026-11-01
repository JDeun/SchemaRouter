"""CrewAI-compatible bounded tool filter composition.

The callback matches CrewAI's ToolFilterContext, tool -> bool convention.
Selection is query-scoped; authorization is always re-evaluated by the caller.
No execution permissions are granted by this module.
"""
from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from typing import Any


def compose_bounded_filter(
    selected_names: Iterable[str],
    *,
    native_filter: Callable[[Any, dict[str, Any]], bool],
) -> Callable[[Any, dict[str, Any]], bool]:
    """Intersect a query-scoped shortlist with the existing CrewAI policy.

    A fresh callback must be constructed for each query, avoiding stale shortlist
    reuse across requests. A missing or malformed tool name fails closed.
    """
    allowed = frozenset(selected_names)
    if not all(isinstance(name, str) and name for name in allowed):
        raise ValueError("selected names must be nonempty strings")

    def filter_tool(context: Any, tool: dict[str, Any]) -> bool:
        name = tool.get("name")
        if not isinstance(name, str) or name not in allowed:
            return False
        return bool(native_filter(context, tool))

    return filter_tool


def select_names(
    query: str,
    tools: list[Mapping[str, object]],
    *,
    selector: Callable[[str, list[Mapping[str, object]]], Iterable[str]],
    limit: int = 8,
) -> frozenset[str]:
    """Validate retrieval output against the current visible catalog."""
    if limit <= 0:
        raise ValueError("limit must be positive")
    current = {
        str(tool["name"])
        for tool in tools
        if isinstance(tool.get("name"), str) and tool["name"]
    }
    names = list(selector(query, tools))
    if len(names) > limit or len(names) != len(set(names)):
        raise ValueError("selector returned excessive or duplicate tools")
    if not all(isinstance(name, str) and name in current for name in names):
        raise ValueError("selector returned a tool outside current catalog")
    return frozenset(names)
