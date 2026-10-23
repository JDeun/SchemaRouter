"""Research-only strict Qwen native JSON wrapper normalization (NOT default).

Single intervention: if the original model emitted a COMPLETE, strictly
parsed, exact-name, source-offered tool invocation as bare JSON, add the
canonical <tool_call> envelope. Never repair broken JSON or infer route IDs
or arguments. Existing strict parsers and scoped execution remain unchanged.
"""
from __future__ import annotations

import json
import math
from typing import Any

from scripts.research_real_qwen_bound_two_step_e0 import (
    MAX_MODEL_BYTES,
    _parse_strict_model_json,
    _strip_one_chatml_marker,
)

SCHEMA_REQUEST = "research__request_scoped_source_schema"


def strict_native_json_envelope(
    raw: str,
    *,
    offered_tool_names: tuple[str, ...],
) -> tuple[str, bool]:
    """Return an unchanged string unless a complete *offered* call is valid.

    This is not a general-purpose JSON repair or executable tool router. The
    caller still passes the result to the ORIGINAL strict action parser, then
    the ORIGINAL source-authorization and executor checks.
    """
    if type(raw) is not str or type(offered_tool_names) is not tuple:
        raise ValueError("original bounded model text and host tool menu required")
    if len(raw.encode("utf-8")) > MAX_MODEL_BYTES:
        return raw, False
    try:
        text = _strip_one_chatml_marker(raw)
    except ValueError:
        return raw, False
    if "<" in text or ">" in text:
        return raw, False
    try:
        data: Any = _parse_strict_model_json(text)
    except (TypeError, ValueError, OverflowError):
        return raw, False
    if (
        type(data) is not dict
        or set(data) != {"name", "arguments"}
        or type(data["name"]) is not str
        or type(data["arguments"]) is not dict
        or data["name"] not in offered_tool_names
        or any(type(name) is not str for name in offered_tool_names)
        or any(type(key) is not str for key in data["arguments"])
    ):
        return raw, False
    args = data["arguments"]
    if data["name"] == SCHEMA_REQUEST:
        if (
            set(args) != {"route_ids"}
            or type(args["route_ids"]) is not list
            or not 1 <= len(args["route_ids"]) <= 5
            or any(type(route) is not str for route in args["route_ids"])
            or len(set(args["route_ids"])) != len(args["route_ids"])
        ):
            return raw, False
    elif any(
        type(value) not in (str, int, float, bool)
        or type(value) is float and not math.isfinite(value)
        for value in args.values()
    ):
        return raw, False
    # This serializer introduces ONLY an envelope around a host-offered and
    # exact parsed native function. The original parser still makes final call.
    canonical = json.dumps(data, ensure_ascii=False, separators=(",", ":"),
                           sort_keys=True, allow_nan=False)
    return f"<tool_call>{canonical}</tool_call>", True
