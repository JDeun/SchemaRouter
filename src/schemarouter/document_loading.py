"""Bounded loading helpers for persisted and administrative documents."""

from __future__ import annotations

import dataclasses
import json
import pathlib
import typing

DEFAULT_DOCUMENT_MAX_BYTES = 8 * 1024 * 1024
DEFAULT_DOCUMENT_MAX_DEPTH = 64
DEFAULT_DOCUMENT_MAX_NODES = 100_000
DEFAULT_DOCUMENT_MAX_CONTAINER_ITEMS = 20_000
DEFAULT_DOCUMENT_MAX_STRING_CHARS = 2 * 1024 * 1024
DEFAULT_YAML_MAX_ALIASES = 64
DEFAULT_YAML_MAX_ANCHORS = 64


class DocumentLimitError(ValueError):
    """Raised when a persisted/configuration document exceeds a resource budget."""


@dataclasses.dataclass(frozen=True, slots=True)
class DocumentLimits:
    max_bytes: int = DEFAULT_DOCUMENT_MAX_BYTES
    max_depth: int = DEFAULT_DOCUMENT_MAX_DEPTH
    max_nodes: int = DEFAULT_DOCUMENT_MAX_NODES
    max_container_items: int = DEFAULT_DOCUMENT_MAX_CONTAINER_ITEMS
    max_string_chars: int = DEFAULT_DOCUMENT_MAX_STRING_CHARS
    max_yaml_aliases: int = DEFAULT_YAML_MAX_ALIASES
    max_yaml_anchors: int = DEFAULT_YAML_MAX_ANCHORS

    def __post_init__(self) -> None:
        for name, value in (
            ("max_bytes", self.max_bytes),
            ("max_depth", self.max_depth),
            ("max_nodes", self.max_nodes),
            ("max_container_items", self.max_container_items),
            ("max_string_chars", self.max_string_chars),
            ("max_yaml_aliases", self.max_yaml_aliases),
            ("max_yaml_anchors", self.max_yaml_anchors),
        ):
            if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
                raise ValueError(f"{name} must be a positive integer")


def _resolve_limits(limits: DocumentLimits | None) -> DocumentLimits:
    if limits is None:
        return DocumentLimits()
    if not isinstance(limits, DocumentLimits):
        raise TypeError("document_limits must be DocumentLimits or None")
    return limits


def _encoded_size(value: str | bytes) -> int:
    if isinstance(value, bytes):
        return len(value)
    if isinstance(value, str):
        try:
            return len(value.encode("utf-8"))
        except UnicodeEncodeError as exc:
            raise ValueError("document is not valid UTF-8 text") from exc
    raise TypeError("document must be str or bytes")


def _validate_encoded_size(value: str | bytes, limits: DocumentLimits) -> None:
    size = _encoded_size(value)
    if size > limits.max_bytes:
        raise DocumentLimitError(
            f"document exceeds configured encoded-size limit ({size} > {limits.max_bytes})"
        )


def _validate_json_text_budget(document: str, limits: DocumentLimits) -> None:
    """Bound JSON nesting and lexical node work before recursive decoding."""

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
                raise DocumentLimitError("document node limit exceeded")
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
                raise DocumentLimitError("document node limit exceeded")
            depth += 1
            if depth > limits.max_depth:
                raise DocumentLimitError("document depth limit exceeded")
            index += 1
            continue

        if char in "]}":
            if depth > 0:
                depth -= 1
            index += 1
            continue

        nodes += 1
        if nodes > limits.max_nodes:
            raise DocumentLimitError("document node limit exceeded")
        index += 1
        while index < length and document[index] not in delimiters:
            index += 1


def validate_bounded_structure(
    value: typing.Any,
    *,
    limits: DocumentLimits | None = None,
) -> None:
    effective = _resolve_limits(limits)
    stack: list[tuple[bool, typing.Any, int]] = [(False, value, 0)]
    active_containers: set[int] = set()
    nodes = 0

    while stack:
        leaving, current, depth = stack.pop()
        if leaving:
            active_containers.discard(id(current))
            continue

        nodes += 1
        if nodes > effective.max_nodes:
            raise DocumentLimitError("document node limit exceeded")
        if depth > effective.max_depth:
            raise DocumentLimitError("document depth limit exceeded")

        if isinstance(current, str):
            if len(current) > effective.max_string_chars:
                raise DocumentLimitError("document string length limit exceeded")
            continue

        if isinstance(current, dict):
            identity = id(current)
            if identity in active_containers:
                raise DocumentLimitError("cyclic document containers are not permitted")
            if len(current) > effective.max_container_items:
                raise DocumentLimitError("document object member limit exceeded")
            active_containers.add(identity)
            stack.append((True, current, depth))
            for key, child in reversed(tuple(current.items())):
                stack.append((False, child, depth + 1))
                stack.append((False, key, depth + 1))
            continue

        if isinstance(current, (list, tuple, set)):
            identity = id(current)
            if identity in active_containers:
                raise DocumentLimitError("cyclic document containers are not permitted")
            if len(current) > effective.max_container_items:
                raise DocumentLimitError("document collection item limit exceeded")
            active_containers.add(identity)
            stack.append((True, current, depth))
            for child in reversed(tuple(current)):
                stack.append((False, child, depth + 1))


def load_bounded_json(
    document: str | bytes,
    *,
    limits: DocumentLimits | None = None,
) -> typing.Any:
    effective = _resolve_limits(limits)
    _validate_encoded_size(document, effective)
    try:
        text = document.decode("utf-8") if isinstance(document, bytes) else document
    except UnicodeDecodeError as exc:
        raise ValueError("document is not valid bounded JSON") from exc

    _validate_json_text_budget(text, effective)
    try:
        value = json.loads(text)
    except (json.JSONDecodeError, ValueError, RecursionError) as exc:
        raise ValueError("document is not valid bounded JSON") from exc
    validate_bounded_structure(value, limits=effective)
    return value


def _validate_yaml_event_budget(
    document: str | bytes,
    limits: DocumentLimits,
) -> None:
    try:
        from yaml import SafeLoader, YAMLError, parse
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
            "YAML document loading requires the optional PyYAML package"
        ) from exc

    depth = 0
    nodes = 0
    aliases = 0
    anchors = 0

    try:
        for event in parse(document, Loader=SafeLoader):
            if isinstance(event, AliasEvent):
                aliases += 1
                nodes += 1
                if aliases > limits.max_yaml_aliases:
                    raise DocumentLimitError("YAML alias limit exceeded")
            elif isinstance(event, (MappingStartEvent, SequenceStartEvent)):
                nodes += 1
                depth += 1
                if depth > limits.max_depth:
                    raise DocumentLimitError("document depth limit exceeded")
                if event.anchor is not None:
                    anchors += 1
            elif isinstance(event, (MappingEndEvent, SequenceEndEvent)):
                if depth > 0:
                    depth -= 1
            elif isinstance(event, ScalarEvent):
                nodes += 1
                if len(event.value) > limits.max_string_chars:
                    raise DocumentLimitError("document string length limit exceeded")
                if event.anchor is not None:
                    anchors += 1

            if anchors > limits.max_yaml_anchors:
                raise DocumentLimitError("YAML anchor limit exceeded")
            if nodes > limits.max_nodes:
                raise DocumentLimitError("document node limit exceeded")
    except DocumentLimitError:
        raise
    except (YAMLError, ValueError, RecursionError) as exc:
        raise ValueError("document is not valid bounded YAML") from exc


def load_bounded_yaml(
    document: str | bytes,
    *,
    limits: DocumentLimits | None = None,
) -> typing.Any:
    effective = _resolve_limits(limits)
    _validate_encoded_size(document, effective)
    _validate_yaml_event_budget(document, effective)

    try:
        from yaml import YAMLError, safe_load
    except ImportError as exc:
        raise RuntimeError(
            "YAML document loading requires the optional PyYAML package"
        ) from exc

    try:
        value = safe_load(document)
    except (YAMLError, ValueError, RecursionError) as exc:
        raise ValueError("document is not valid bounded YAML") from exc

    validate_bounded_structure(value, limits=effective)
    return value


def read_bounded_text(
    path: str | pathlib.Path,
    *,
    limits: DocumentLimits | None = None,
) -> str:
    effective = _resolve_limits(limits)
    source = pathlib.Path(path)
    with source.open("rb") as handle:
        payload = handle.read(effective.max_bytes + 1)
    if len(payload) > effective.max_bytes:
        raise DocumentLimitError(
            f"document exceeds configured encoded-size limit "
            f"({len(payload)} > {effective.max_bytes})"
        )
    try:
        return payload.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError("document is not valid UTF-8 text") from exc
