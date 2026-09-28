from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from importlib import metadata
from typing import Any, cast

from .decisions import DecisionBackend

DECISION_BACKEND_ENTRY_POINT_GROUP = "schemarouter.decision_backends"


@dataclass(frozen=True)
class DecisionBackendPluginInfo:
    """Metadata-only description of an installed decision-backend plugin."""

    name: str
    value: str
    distribution: str | None = None
    version: str | None = None


def _decision_backend_entry_points() -> tuple[Any, ...]:
    entry_points = metadata.entry_points()
    if hasattr(entry_points, "select"):
        selected = entry_points.select(group=DECISION_BACKEND_ENTRY_POINT_GROUP)
    else:  # pragma: no cover - compatibility with older importlib.metadata surfaces.
        selected = entry_points.get(DECISION_BACKEND_ENTRY_POINT_GROUP, ())
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


def discover_decision_backend_plugins() -> tuple[DecisionBackendPluginInfo, ...]:
    """Discover installed decision-backend plugins without importing plugin code."""

    plugins: list[DecisionBackendPluginInfo] = []
    for entry_point in _decision_backend_entry_points():
        distribution, version = _distribution_info(entry_point)
        plugins.append(
            DecisionBackendPluginInfo(
                name=str(entry_point.name),
                value=str(entry_point.value),
                distribution=distribution,
                version=version,
            )
        )
    return tuple(sorted(plugins, key=lambda plugin: plugin.name))


def _normalize_config(config: Mapping[str, Any] | None) -> dict[str, Any]:
    if config is None:
        return {}
    if not isinstance(config, Mapping):
        raise TypeError("decision backend plugin config must be a mapping")

    normalized: dict[str, Any] = {}
    for key, value in config.items():
        if not isinstance(key, str) or not key.strip():
            raise TypeError("decision backend plugin config keys must be non-empty strings")
        normalized[key] = value
    return normalized


def _coerce_backend(value: Any, *, config: Mapping[str, Any] | None) -> DecisionBackend:
    candidate = value
    kwargs = _normalize_config(config)

    if isinstance(candidate, type):
        candidate = candidate(**kwargs)
    elif callable(candidate) and not callable(getattr(candidate, "decide", None)):
        candidate = candidate(**kwargs)
    elif kwargs:
        raise TypeError(
            "preconstructed decision backend plugin does not accept configuration"
        )

    decide = getattr(candidate, "decide", None)
    if not callable(decide):
        raise TypeError(
            "decision backend plugin must resolve to an object exposing callable decide()"
        )
    return cast(DecisionBackend, candidate)


def load_decision_backend_plugin(
    name: str,
    *,
    config: Mapping[str, Any] | None = None,
) -> DecisionBackend:
    """Explicitly import and construct one installed decision-backend plugin.

    Loading an entry point executes trusted installed Python code. Discovery never imports
    plugin code; loading requires an exact plugin name so installed plugins are not executed
    implicitly.
    """

    plugin_name = str(name).strip()
    if not plugin_name:
        raise ValueError("decision backend plugin name must be non-empty")

    available: dict[str, list[Any]] = {}
    for entry_point in _decision_backend_entry_points():
        available.setdefault(str(entry_point.name), []).append(entry_point)

    matches = available.get(plugin_name)
    if matches is None:
        raise KeyError(f"unknown decision backend plugin: {plugin_name}")
    if len(matches) != 1:
        raise RuntimeError(
            "ambiguous decision backend plugin name registered by multiple distributions: "
            f"{plugin_name}"
        )

    loaded = matches[0].load()
    return _coerce_backend(loaded, config=config)
