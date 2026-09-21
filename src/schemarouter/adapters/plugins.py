from __future__ import annotations

from collections.abc import Collection
from dataclasses import dataclass
from importlib import metadata
from typing import Any, cast

from .base import AdapterRegistry, SourceAdapter

ADAPTER_ENTRY_POINT_GROUP = "schemarouter.adapters"


@dataclass(frozen=True)
class AdapterPluginInfo:
    """Metadata-only description of an installed adapter plugin."""

    name: str
    value: str
    distribution: str | None = None
    version: str | None = None


def _adapter_entry_points() -> tuple[Any, ...]:
    entry_points = metadata.entry_points()
    if hasattr(entry_points, "select"):
        selected = entry_points.select(group=ADAPTER_ENTRY_POINT_GROUP)
    else:  # pragma: no cover - compatibility with older importlib.metadata surfaces.
        selected = entry_points.get(ADAPTER_ENTRY_POINT_GROUP, ())
    return tuple(selected)


def _distribution_info(entry_point: Any) -> tuple[str | None, str | None]:
    distribution = getattr(entry_point, "dist", None)
    if distribution is None:
        return None, None
    name = None
    try:
        name = distribution.metadata.get("Name")
    except Exception:  # pragma: no cover - third-party metadata can be incomplete.
        name = None
    version = getattr(distribution, "version", None)
    return (
        str(name) if name is not None else None,
        str(version) if version is not None else None,
    )


def discover_adapter_plugins() -> tuple[AdapterPluginInfo, ...]:
    """Discover installed adapter entry points without importing plugin code."""
    plugins: list[AdapterPluginInfo] = []
    for entry_point in _adapter_entry_points():
        distribution, version = _distribution_info(entry_point)
        plugins.append(
            AdapterPluginInfo(
                name=str(entry_point.name),
                value=str(entry_point.value),
                distribution=distribution,
                version=version,
            )
        )
    return tuple(sorted(plugins, key=lambda plugin: plugin.name))


def _coerce_adapter(value: Any) -> SourceAdapter:
    candidate = value
    if isinstance(candidate, type):
        candidate = candidate()
    elif not hasattr(candidate, "kind") and callable(candidate):
        candidate = candidate()

    kind = getattr(candidate, "kind", None)
    priority = getattr(candidate, "priority", None)
    loader = getattr(candidate, "load", None)
    if not isinstance(kind, str) or not kind.strip() or kind.strip().lower() == "auto":
        raise TypeError("adapter plugin must expose a non-empty kind other than 'auto'")
    if isinstance(priority, bool) or not isinstance(priority, int):
        raise TypeError("adapter plugin must expose an integer priority")
    if not callable(loader):
        raise TypeError("adapter plugin must expose an async-compatible load method")
    return cast(SourceAdapter, candidate)


def load_adapter_plugins(
    registry: AdapterRegistry,
    *,
    allowlist: Collection[str],
    replace: bool = False,
) -> tuple[str, ...]:
    """Import and register only explicitly allowlisted adapter entry points.

    Loading an entry point executes trusted installed Python code. An empty allowlist is rejected
    so callers cannot accidentally turn plugin discovery into arbitrary auto-import.
    """
    requested = {str(name).strip() for name in allowlist if str(name).strip()}
    if not requested:
        raise ValueError("adapter plugin loading requires a non-empty explicit allowlist")

    available: dict[str, list[Any]] = {}
    for entry_point in _adapter_entry_points():
        available.setdefault(str(entry_point.name), []).append(entry_point)

    missing = sorted(requested - set(available))
    if missing:
        raise KeyError("unknown adapter plugin(s): " + ", ".join(missing))

    ambiguous = sorted(name for name in requested if len(available[name]) != 1)
    if ambiguous:
        raise RuntimeError(
            "ambiguous adapter plugin name(s) registered by multiple distributions: "
            + ", ".join(ambiguous)
        )

    staged: list[SourceAdapter] = []
    staged_kinds: list[str] = []
    for name in sorted(requested):
        entry_point = available[name][0]
        adapter = _coerce_adapter(entry_point.load())
        staged.append(adapter)
        staged_kinds.append(str(adapter.kind).strip().lower())

    if len(staged_kinds) != len(set(staged_kinds)):
        raise ValueError("allowlisted adapter plugins resolved to duplicate adapter kinds")

    if not replace:
        collisions = sorted(set(staged_kinds) & set(registry.kinds()))
        if collisions:
            raise ValueError(
                "adapter plugin kind(s) already registered: " + ", ".join(collisions)
            )

    for adapter in staged:
        registry.register(adapter, replace=replace)
    return tuple(staged_kinds)
