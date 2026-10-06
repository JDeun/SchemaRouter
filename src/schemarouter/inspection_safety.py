from __future__ import annotations

import re
from copy import deepcopy
from typing import Any

_REDACTED = "<redacted>"
_SCHEMA_VALUE_KEYS_TO_OMIT = frozenset(
    {
        "const",
        "default",
        "example",
        "examples",
    }
)
_STRUCTURAL_NAME_MAP_KEYS = frozenset(
    {
        "defs",
        "definitions",
        "dependentschemas",
        "patternproperties",
        "properties",
    }
)
_SENSITIVE_KEY_NAMES = frozenset(
    {
        "accesstoken",
        "apikey",
        "authorization",
        "authtoken",
        "bearertoken",
        "clientsecret",
        "cookie",
        "password",
        "passwd",
        "privatekey",
        "refreshtoken",
        "secret",
        "setcookie",
        "token",
    }
)
_SENSITIVE_KEY_SUFFIXES = (
    "accesstoken",
    "apikey",
    "authorization",
    "clientsecret",
    "cookie",
    "password",
    "passwd",
    "privatekey",
    "refreshtoken",
    "setcookie",
)
_AUTHORIZATION_VALUE_RE = re.compile(r"(?i)\b(?:bearer|basic)\s+[^\s,;]+")
_CREDENTIAL_ASSIGNMENT_RE = re.compile(
    r"(?i)(?:^|[?&;,\s])"
    r"(?:access[_-]?token|api[_-]?key|authorization|client[_-]?secret|cookie|"
    r"password|passwd|private[_-]?key|refresh[_-]?token|secret|token)"
    r"\s*[:=]\s*[^\s,;]+"
)
_URL_USERINFO_RE = re.compile(r"(?i)\b[a-z][a-z0-9+.-]*://[^\s/@]*@[^\s/]+")
_MAX_INSPECTION_SCHEMA_DEPTH = 64
_MAX_INSPECTION_SCHEMA_NODES = 20_000


def _normalize_key(value: object) -> str:
    return "".join(character for character in str(value).casefold() if character.isalnum())


def _looks_sensitive_key(value: object) -> bool:
    normalized = _normalize_key(value)
    if normalized in _SENSITIVE_KEY_NAMES:
        return True
    return any(
        normalized.endswith(suffix) and len(normalized) > len(suffix)
        for suffix in _SENSITIVE_KEY_SUFFIXES
    )


def _looks_sensitive_string(value: str) -> bool:
    candidate = value.strip()
    if not candidate:
        return False
    return bool(
        _AUTHORIZATION_VALUE_RE.search(candidate)
        or _CREDENTIAL_ASSIGNMENT_RE.search(candidate)
        or _URL_USERINFO_RE.search(candidate)
    )


def _safe_schema_value(
    value: Any,
    *,
    depth: int,
    ancestors: frozenset[int],
    visited_nodes: list[int],
) -> Any:
    visited_nodes[0] += 1
    if (
        depth > _MAX_INSPECTION_SCHEMA_DEPTH
        or visited_nodes[0] > _MAX_INSPECTION_SCHEMA_NODES
    ):
        return _REDACTED

    if isinstance(value, str):
        return _REDACTED if _looks_sensitive_string(value) else value

    if isinstance(value, dict):
        marker = id(value)
        if marker in ancestors:
            return _REDACTED
        next_ancestors = ancestors | {marker}
        result: dict[str, Any] = {}
        for raw_key, item in value.items():
            key = str(raw_key)
            folded = key.casefold()
            if folded in _SCHEMA_VALUE_KEYS_TO_OMIT:
                continue

            normalized_key = _normalize_key(key)
            if normalized_key in _STRUCTURAL_NAME_MAP_KEYS and isinstance(item, dict):
                result[key] = {
                    str(name): _safe_schema_value(
                        child,
                        depth=depth + 2,
                        ancestors=next_ancestors | {id(item)},
                        visited_nodes=visited_nodes,
                    )
                    for name, child in item.items()
                }
                continue

            if _looks_sensitive_key(key):
                result[key] = _REDACTED
                continue

            result[key] = _safe_schema_value(
                item,
                depth=depth + 1,
                ancestors=next_ancestors,
                visited_nodes=visited_nodes,
            )
        return result

    if isinstance(value, (list, tuple)):
        marker = id(value)
        if marker in ancestors:
            return [_REDACTED]
        next_ancestors = ancestors | {marker}
        return [
            _safe_schema_value(
                item,
                depth=depth + 1,
                ancestors=next_ancestors,
                visited_nodes=visited_nodes,
            )
            for item in value
        ]

    return deepcopy(value)


def safe_schema_document(value: Any) -> Any:
    """Return a detached inspection-safe view of schema-like JSON data.

    Structural keys and property/definition names are preserved. Literal annotation values
    commonly used to carry examples/defaults are omitted, while obvious credential-bearing
    extension keys and strings are redacted.
    """

    return _safe_schema_value(
        value,
        depth=0,
        ancestors=frozenset(),
        visited_nodes=[0],
    )
