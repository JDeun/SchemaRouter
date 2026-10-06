"""Bounded loading helpers for persisted and trusted configuration documents."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .storage import (
    PersistedDocumentLimits,
    _PersistedDocumentLimitError,
    _resolve_persisted_document_limits,
    _validate_persisted_document_size,
    _validate_persisted_json_document,
)


class DocumentLimitError(ValueError):
    """A persisted/configuration document exceeded its resource budget."""


def _coerce_bounded_text(
    value: str | bytes,
    *,
    limits: PersistedDocumentLimits,
    label: str,
) -> str:
    if isinstance(value, bytes):
        encoded_bytes = len(value)
        try:
            _validate_persisted_document_size(encoded_bytes, limits=limits)
        except _PersistedDocumentLimitError as exc:
            raise DocumentLimitError(
                f"{label} exceeds the configured byte limit"
            ) from exc
        try:
            return value.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ValueError(f"{label} must be UTF-8 text") from exc

    if not isinstance(value, str):
        raise TypeError(f"{label} must be str or bytes")
    try:
        encoded_bytes = len(value.encode("utf-8"))
    except UnicodeEncodeError as exc:
        raise ValueError(f"{label} must be valid UTF-8 text") from exc
    try:
        _validate_persisted_document_size(encoded_bytes, limits=limits)
    except _PersistedDocumentLimitError as exc:
        raise DocumentLimitError(
            f"{label} exceeds the configured byte limit"
        ) from exc
    return value


def _validate_document_structure(
    value: Any,
    *,
    limits: PersistedDocumentLimits,
    label: str,
) -> None:
    nodes = 0
    active_collections: set[int] = set()

    def walk(current: Any, depth: int) -> None:
        nonlocal nodes
        nodes += 1
        if nodes > limits.max_nodes:
            raise DocumentLimitError(
                f"{label} exceeds the configured node limit"
            )
        if depth > limits.max_depth:
            raise DocumentLimitError(
                f"{label} exceeds the configured depth limit"
            )

        if isinstance(current, dict):
            if len(current) > limits.max_map_items:
                raise DocumentLimitError(
                    f"{label} exceeds the configured map cardinality limit"
                )
            identity = id(current)
            if identity in active_collections:
                raise DocumentLimitError(f"{label} contains a cyclic mapping")
            active_collections.add(identity)
            try:
                for key, item in current.items():
                    walk(key, depth + 1)
                    walk(item, depth + 1)
            finally:
                active_collections.remove(identity)
            return

        if isinstance(current, (list, tuple, set, frozenset)):
            if len(current) > limits.max_list_items:
                raise DocumentLimitError(
                    f"{label} exceeds the configured list cardinality limit"
                )
            identity = id(current)
            if identity in active_collections:
                raise DocumentLimitError(f"{label} contains a cyclic sequence")
            active_collections.add(identity)
            try:
                for item in current:
                    walk(item, depth + 1)
            finally:
                active_collections.remove(identity)

    walk(value, 1)


def load_bounded_json(
    value: str | bytes,
    *,
    limits: PersistedDocumentLimits | None = None,
    label: str = "JSON document",
) -> Any:
    resolved = _resolve_persisted_document_limits(limits)
    text = _coerce_bounded_text(value, limits=resolved, label=label)
    try:
        _validate_persisted_json_document(text, limits=resolved)
    except _PersistedDocumentLimitError as exc:
        raise DocumentLimitError(
            f"{label} exceeds configured structural limits"
        ) from exc
    try:
        raw = json.loads(text)
    except RecursionError as exc:
        raise DocumentLimitError(
            f"{label} exceeds the parser recursion budget"
        ) from exc
    _validate_document_structure(raw, limits=resolved, label=label)
    return raw


def _validate_yaml_events(
    text: str,
    *,
    limits: PersistedDocumentLimits,
    label: str,
    yaml: Any,
) -> None:
    nodes = 0
    depth = 0
    aliases = 0
    anchors = 0
    try:
        events = yaml.parse(text, Loader=yaml.SafeLoader)
        for event in events:
            if isinstance(event, yaml.events.AliasEvent):
                aliases += 1
                nodes += 1
                if aliases > limits.max_aliases:
                    raise DocumentLimitError(
                        f"{label} exceeds the configured YAML alias limit"
                    )
                if nodes > limits.max_nodes:
                    raise DocumentLimitError(
                        f"{label} exceeds the configured node limit"
                    )
                continue

            anchor = getattr(event, "anchor", None)
            if anchor is not None:
                anchors += 1
                if anchors > limits.max_anchors:
                    raise DocumentLimitError(
                        f"{label} exceeds the configured YAML anchor limit"
                    )

            if isinstance(
                event,
                (yaml.events.MappingStartEvent, yaml.events.SequenceStartEvent),
            ):
                nodes += 1
                depth += 1
                if nodes > limits.max_nodes:
                    raise DocumentLimitError(
                        f"{label} exceeds the configured node limit"
                    )
                if depth > limits.max_depth:
                    raise DocumentLimitError(
                        f"{label} exceeds the configured depth limit"
                    )
            elif isinstance(
                event,
                (yaml.events.MappingEndEvent, yaml.events.SequenceEndEvent),
            ):
                depth = max(0, depth - 1)
            elif isinstance(event, yaml.events.ScalarEvent):
                nodes += 1
                if nodes > limits.max_nodes:
                    raise DocumentLimitError(
                        f"{label} exceeds the configured node limit"
                    )
    except RecursionError as exc:
        raise DocumentLimitError(
            f"{label} exceeds the YAML parser recursion budget"
        ) from exc
    except DocumentLimitError:
        raise
    except yaml.YAMLError as exc:
        raise ValueError(f"{label} is not valid YAML") from exc


def load_bounded_yaml(
    value: str | bytes,
    *,
    limits: PersistedDocumentLimits | None = None,
    label: str = "YAML document",
) -> Any:
    resolved = _resolve_persisted_document_limits(limits)
    text = _coerce_bounded_text(value, limits=resolved, label=label)
    try:
        import yaml
    except ImportError as exc:
        raise RuntimeError(
            "YAML loading requires the optional PyYAML package"
        ) from exc

    _validate_yaml_events(text, limits=resolved, label=label, yaml=yaml)
    try:
        raw = yaml.safe_load(text)
    except RecursionError as exc:
        raise DocumentLimitError(
            f"{label} exceeds the YAML construction recursion budget"
        ) from exc
    except yaml.YAMLError as exc:
        raise ValueError(f"{label} is not valid YAML") from exc
    _validate_document_structure(raw, limits=resolved, label=label)
    return raw


def validate_bounded_structure(
    value: Any,
    *,
    limits: PersistedDocumentLimits | None = None,
    label: str = "configuration document",
) -> None:
    resolved = _resolve_persisted_document_limits(limits)
    _validate_document_structure(value, limits=resolved, label=label)


def read_bounded_text(
    path: str | Path,
    *,
    limits: PersistedDocumentLimits | None = None,
    label: str = "document",
) -> str:
    resolved = _resolve_persisted_document_limits(limits)
    source = Path(path)
    try:
        encoded_bytes = source.stat().st_size
    except OSError:
        raise
    try:
        _validate_persisted_document_size(encoded_bytes, limits=resolved)
    except _PersistedDocumentLimitError as exc:
        raise DocumentLimitError(
            f"{label} exceeds the configured byte limit"
        ) from exc

    with source.open("rb") as handle:
        payload = handle.read(resolved.max_bytes + 1)
    if len(payload) > resolved.max_bytes:
        raise DocumentLimitError(
            f"{label} exceeds the configured byte limit"
        )
    try:
        return payload.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError(f"{label} must be UTF-8 text") from exc
