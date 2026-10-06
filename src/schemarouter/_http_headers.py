from __future__ import annotations

import re
from collections.abc import Iterable, Mapping

_HEADER_NAME_RE = re.compile(r"^[!#$%&'*+.^_\x60|~0-9A-Za-z-]+$")

HTTP_CONTROLLED_HEADERS = frozenset(
    {
        "connection",
        "content-length",
        "host",
        "keep-alive",
        "proxy-authenticate",
        "proxy-authorization",
        "te",
        "trailer",
        "transfer-encoding",
        "upgrade",
    }
)


def validate_trusted_headers(
    headers: Mapping[str, str] | None,
    *,
    additional_protected: Iterable[str] = (),
    protected_prefixes: Iterable[str] = (),
    label: str = "trusted_headers",
) -> dict[str, str]:
    """Validate host-controlled HTTP headers before any transport sees them."""

    if headers is None:
        return {}

    protected = set(HTTP_CONTROLLED_HEADERS)
    protected.update(str(name).casefold() for name in additional_protected)
    prefixes = tuple(str(prefix).casefold() for prefix in protected_prefixes)

    result: dict[str, str] = {}
    seen: set[str] = set()
    for name, value in headers.items():
        if not isinstance(name, str) or not name or name != name.strip():
            raise ValueError(f"{label} names must be non-empty trimmed strings")
        if not _HEADER_NAME_RE.fullmatch(name):
            raise ValueError(f"invalid {label} header name: {name!r}")
        if not isinstance(value, str):
            raise ValueError(f"{label} values must be strings")

        normalized = name.casefold()
        if normalized in seen:
            raise ValueError(f"{label} contains case-insensitive duplicate names")
        if normalized in protected or any(
            normalized.startswith(prefix) for prefix in prefixes
        ):
            raise ValueError(
                f"{label} header {name!r} is controlled by the transport"
            )
        if any(ord(char) < 0x20 or ord(char) == 0x7F for char in value):
            raise ValueError(f"{label} values must not contain control characters")

        seen.add(normalized)
        result[name] = value

    return result
