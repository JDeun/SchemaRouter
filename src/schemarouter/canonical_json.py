from __future__ import annotations

import hashlib
import json
import math
from typing import Any


def _validate_canonical_json_value(value: Any, *, path: str = "$") -> None:
    """Validate the intentionally narrow value domain used by digest surfaces."""

    if value is None or isinstance(value, (str, bool, int)):
        return
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError(f"canonical JSON rejects non-finite float at {path}")
        return
    if isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            _validate_canonical_json_value(item, path=f"{path}[{index}]")
        return
    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str):
                raise TypeError(
                    f"canonical JSON object keys must be strings at {path}"
                )
            _validate_canonical_json_value(item, path=f"{path}.{key}")
        return
    raise TypeError(
        f"canonical JSON does not support {type(value).__name__} at {path}"
    )


def canonical_json_bytes(
    value: Any,
    *,
    ensure_ascii: bool = True,
) -> bytes:
    """Return the stable JSON byte representation used for reproducibility digests.

    Supported values are JSON scalars, objects with string keys, and list/tuple
    containers recursively composed from those values. The representation keeps
    the project's historical digest contract: sorted object keys, compact
    separators, ASCII escaping, UTF-8 bytes, and no non-finite floats.

    ``ensure_ascii=False`` is reserved for domain formats whose historical
    identity explicitly used UTF-8 characters instead of JSON escape sequences.
    """

    _validate_canonical_json_value(value)
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=ensure_ascii,
        allow_nan=False,
    ).encode("utf-8")


def canonical_json_text(
    value: Any,
    *,
    ensure_ascii: bool = True,
) -> str:
    """Return the canonical JSON representation as text."""

    return canonical_json_bytes(value, ensure_ascii=ensure_ascii).decode("utf-8")


def canonical_json_sha256(
    value: Any,
    *,
    ensure_ascii: bool = True,
) -> str:
    """Return a SHA-256 hex digest over :func:`canonical_json_bytes`."""

    return hashlib.sha256(
        canonical_json_bytes(value, ensure_ascii=ensure_ascii)
    ).hexdigest()
