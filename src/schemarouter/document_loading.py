from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


DEFAULT_CONFIGURATION_DOCUMENT_MAX_BYTES = 2 * 1024 * 1024
DEFAULT_CONFIGURATION_DOCUMENT_MAX_DEPTH = 64
DEFAULT_CONFIGURATION_DOCUMENT_MAX_NODES = 100_000
DEFAULT_CONFIGURATION_CONTAINER_MAX_ITEMS = 20_000
DEFAULT_CONFIGURATION_YAML_MAX_ALIASES = 128
DEFAULT_CONFIGURATION_YAML_MAX_ANCHORS = 128


@dataclass(frozen=True)
class ConfigurationDocumentLimits:
    """Resource budgets for persisted/configuration JSON and YAML documents."""

    max_bytes: int = DEFAULT_CONFIGURATION_DOCUMENT_MAX_BYTES
    max_depth: int = DEFAULT_CONFIGURATION_DOCUMENT_MAX_DEPTH
    max_nodes: int = DEFAULT_CONFIGURATION_DOCUMENT_MAX_NODES
    max_container_items: int = DEFAULT_CONFIGURATION_CONTAINER_MAX_ITEMS
    max_yaml_aliases: int = DEFAULT_CONFIGURATION_YAML_MAX_ALIASES
    max_yaml_anchors: int = DEFAULT_CONFIGURATION_YAML_MAX_ANCHORS

    def __post_init__(self) -> None:
        for name, value in (
            ("max_bytes", self.max_bytes),
            ("max_depth", self.max_depth),
            ("max_nodes", self.max_nodes),
            ("max_container_items", self.max_container_items),
            ("max_yaml_aliases", self.max_yaml_aliases),
            ("max_yaml_anchors", self.max_yaml_anchors),
        ):
            if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
                raise ValueError(f"{name} must be a positive integer")


class ConfigurationDocumentError(ValueError):
    """Raised when a configuration document cannot be decoded within its budget."""


def _resolve_limits(
    limits: ConfigurationDocumentLimits | None,
) -> ConfigurationDocumentLimits:
    if limits is None:
        return ConfigurationDocumentLimits()
    if not isinstance(limits, ConfigurationDocumentLimits):
        raise TypeError(
            "document_limits must be ConfigurationDocumentLimits or None"
        )
    return limits


def _encoded_size(value: str | bytes) -> int:
    return len(value) if isinstance(value, bytes) else len(value.encode("utf-8"))


def _validate_encoded_size(
    value: str | bytes,
    *,
    limits: ConfigurationDocumentLimits,
) -> None:
    if _encoded_size(value) > limits.max_bytes:
        raise ConfigurationDocumentError(
            "configuration document exceeds the configured byte limit"
        )


def _validate_json_text_budget(
    document: str,
    *,
    limits: ConfigurationDocumentLimits,
) -> None:
    """Bound JSON depth/node work before the recursive decoder runs."""

    depth = 0
    nodes = 0
    index = 0
    length = len(document)
    delimiters = " \t\r\n,]}:"

    while index < length:
        char = document[index]

        if char in " \t\r\n,:":
            index += 1
            continue

        if char == '"':
            nodes += 1
            if nodes > limits.max_nodes:
                raise ConfigurationDocumentError(
                    "configuration document exceeds the configured node limit"
                )
            index += 1
            while index < length:
                current = document[index]
                if current == "\\":
                    index += 2
                    continue
                index += 1
                if current == '"':
                    break
            continue

        if char in "[{":
            nodes += 1
            if nodes > limits.max_nodes:
                raise ConfigurationDocumentError(
                    "configuration document exceeds the configured node limit"
                )
            depth += 1
            if depth > limits.max_depth:
                raise ConfigurationDocumentError(
                    "configuration document exceeds the configured depth limit"
                )
            index += 1
            continue

        if char in "]}":
            if depth > 0:
                depth -= 1
            index += 1
            continue

        nodes += 1
        if nodes > limits.max_nodes:
            raise ConfigurationDocumentError(
                "configuration document exceeds the configured node limit"
            )
        index += 1
        while index < length and document[index] not in delimiters:
            index += 1


def _validate_loaded_structure(
    value: Any,
    *,
    limits: ConfigurationDocumentLimits,
) -> None:
    stack: list[tuple[bool, Any, int]] = [(False, value, 0)]
    active_containers: set[int] = set()
    nodes = 0

    while stack:
        leaving, current, depth = stack.pop()
        if leaving:
            active_containers.discard(id(current))
            continue

        nodes += 1
        if nodes > limits.max_nodes:
            raise ConfigurationDocumentError(
                "configuration document exceeds the configured node limit"
            )
        if depth > limits.max_depth:
            raise ConfigurationDocumentError(
                "configuration document exceeds the configured depth limit"
            )

        if isinstance(current, dict):
            identity = id(current)
            if identity in active_containers:
                raise ConfigurationDocumentError(
                    "cyclic configuration documents are not permitted"
                )
            if len(current) > limits.max_container_items:
                raise ConfigurationDocumentError(
                    "configuration mapping exceeds the configured item limit"
                )
            active_containers.add(identity)
            stack.append((True, current, depth))
            for key, child in reversed(tuple(current.items())):
                stack.append((False, child, depth + 1))
                stack.append((False, key, depth + 1))
            continue

        if isinstance(current, (list, tuple)):
            identity = id(current)
            if identity in active_containers:
                raise ConfigurationDocumentError(
                    "cyclic configuration documents are not permitted"
                )
            if len(current) > limits.max_container_items:
                raise ConfigurationDocumentError(
                    "configuration sequence exceeds the configured item limit"
                )
            active_containers.add(identity)
            stack.append((True, current, depth))
            for child in reversed(current):
                stack.append((False, child, depth + 1))


def load_bounded_json(
    value: str | bytes,
    *,
    limits: ConfigurationDocumentLimits | None = None,
) -> Any:
    effective_limits = _resolve_limits(limits)
    if not isinstance(value, (str, bytes)):
        raise TypeError("JSON configuration document must be str or bytes")

    _validate_encoded_size(value, limits=effective_limits)
    try:
        document = value.decode("utf-8") if isinstance(value, bytes) else value
    except UnicodeDecodeError as exc:
        raise ConfigurationDocumentError(
            "configuration document is not valid UTF-8"
        ) from exc

    _validate_json_text_budget(document, limits=effective_limits)
    try:
        loaded = json.loads(document)
    except (json.JSONDecodeError, ValueError, RecursionError) as exc:
        raise ConfigurationDocumentError(
            "configuration document is not valid JSON"
        ) from exc
    _validate_loaded_structure(loaded, limits=effective_limits)
    return loaded


def _validate_yaml_event_budget(
    value: str | bytes,
    *,
    limits: ConfigurationDocumentLimits,
) -> None:
    try:
        import yaml
        from yaml.events import (
            AliasEvent,
            MappingEndEvent,
            MappingStartEvent,
            ScalarEvent,
            SequenceEndEvent,
            SequenceStartEvent,
        )
    except ImportError as exc:
        raise RuntimeError(
            "YAML configuration loading requires the optional PyYAML package"
        ) from exc

    depth = 0
    nodes = 0
    aliases = 0
    anchors = 0

    try:
        events = yaml.parse(value, Loader=yaml.SafeLoader)
        for event in events:
            if isinstance(event, AliasEvent):
                aliases += 1
                nodes += 1
                if aliases > limits.max_yaml_aliases:
                    raise ConfigurationDocumentError(
                        "YAML configuration exceeds the configured alias limit"
                    )
            elif isinstance(
                event,
                (MappingStartEvent, SequenceStartEvent),
            ):
                nodes += 1
                depth += 1
                if depth > limits.max_depth:
                    raise ConfigurationDocumentError(
                        "configuration document exceeds the configured depth limit"
                    )
            elif isinstance(event, (MappingEndEvent, SequenceEndEvent)):
                if depth > 0:
                    depth -= 1
            elif isinstance(event, ScalarEvent):
                nodes += 1

            if getattr(event, "anchor", None) is not None:
                anchors += 1
                if anchors > limits.max_yaml_anchors:
                    raise ConfigurationDocumentError(
                        "YAML configuration exceeds the configured anchor limit"
                    )

            if nodes > limits.max_nodes:
                raise ConfigurationDocumentError(
                    "configuration document exceeds the configured node limit"
                )
    except ConfigurationDocumentError:
        raise
    except (yaml.YAMLError, ValueError, RecursionError) as exc:
        raise ConfigurationDocumentError(
            "configuration document is not valid YAML"
        ) from exc


def load_bounded_yaml(
    value: str | bytes,
    *,
    limits: ConfigurationDocumentLimits | None = None,
) -> Any:
    effective_limits = _resolve_limits(limits)
    if not isinstance(value, (str, bytes)):
        raise TypeError("YAML configuration document must be str or bytes")

    _validate_encoded_size(value, limits=effective_limits)
    _validate_yaml_event_budget(value, limits=effective_limits)

    try:
        import yaml
    except ImportError as exc:
        raise RuntimeError(
            "YAML configuration loading requires the optional PyYAML package"
        ) from exc

    try:
        loaded = yaml.safe_load(value)
    except (yaml.YAMLError, ValueError, RecursionError) as exc:
        raise ConfigurationDocumentError(
            "configuration document is not valid YAML"
        ) from exc
    _validate_loaded_structure(loaded, limits=effective_limits)
    return loaded


def read_bounded_text_file(
    path: str | Path,
    *,
    limits: ConfigurationDocumentLimits | None = None,
) -> str:
    effective_limits = _resolve_limits(limits)
    source = Path(path)

    try:
        size = source.stat().st_size
    except OSError as exc:
        raise ConfigurationDocumentError(
            f"cannot read configuration document: {source}"
        ) from exc
    if size > effective_limits.max_bytes:
        raise ConfigurationDocumentError(
            "configuration document exceeds the configured byte limit"
        )

    try:
        with source.open("rb") as handle:
            payload = handle.read(effective_limits.max_bytes + 1)
    except OSError as exc:
        raise ConfigurationDocumentError(
            f"cannot read configuration document: {source}"
        ) from exc

    if len(payload) > effective_limits.max_bytes:
        raise ConfigurationDocumentError(
            "configuration document exceeds the configured byte limit"
        )
    try:
        return payload.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ConfigurationDocumentError(
            "configuration document is not valid UTF-8"
        ) from exc
