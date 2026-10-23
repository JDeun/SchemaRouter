"""Privacy-safe structural diagnostics for failed local CodeGraph E1 model actions.

Never save model text, tool names, argument values, sources, schema definitions
or credentials. The original parsers and execution authority are unchanged:
these labels are retrospective observations, not parse recovery.
"""
from __future__ import annotations

import re
from typing import Any

from scripts.research_real_qwen_bound_two_step_e0 import (
    MAX_MODEL_BYTES,
    TOOL_CALL,
    _parse_strict_model_json,
    _strip_one_chatml_marker,
)

# Explicit bounded, low-cardinality output only. Every label is hardcoded.
CATEGORIES = frozenset({
    "invalid_envelope_type",
    "output_over_limit",
    "unterminated_or_multiple_tool_wrapper",
    "invalid_tool_json",
    "non_object_tool_payload",
    "invalid_tool_envelope",
    "complex_native_arguments",
    "rejected_canonical_tool_call",
    "unwrapped_tool_json",
    "unsupported_tool_markup",
    "plain_final_without_source",
})


def classify_rejected_action_shape(raw: Any) -> str:
    """Safely categorize a *failed* model response, without relaxing parsing.

    When original strict native grammar rejects a call or a terminal appears
    before source completion, classify only its structural shape. Never
    include arbitrary substrings or values from the model in public evidence.
    """
    if type(raw) is not str:
        return "invalid_envelope_type"
    if len(raw.encode("utf-8")) > MAX_MODEL_BYTES:
        return "output_over_limit"
    try:
        bounded = _strip_one_chatml_marker(raw)
    except ValueError:
        return "output_over_limit"
    match = TOOL_CALL.fullmatch(bounded)
    if match is not None:
        try:
            value = _parse_strict_model_json(match.group(1))
        except (TypeError, ValueError, OverflowError):
            return "invalid_tool_json"
        if type(value) is not dict:
            return "non_object_tool_payload"
        if (
            set(value) != {"name", "arguments"}
            or type(value.get("name")) is not str
            or type(value.get("arguments")) is not dict
        ):
            return "invalid_tool_envelope"
        if any(
            type(key) is not str or type(item) not in (str, int, float, bool)
            for key, item in value["arguments"].items()
        ):
            return "complex_native_arguments"
        return "rejected_canonical_tool_call"
    if "<tool_call" in bounded or "</tool_call>" in bounded:
        return "unterminated_or_multiple_tool_wrapper"
    # Qwen can emit function-shaped JSON without its mandatory native wrapper.
    # Do not 'repair' it: strictly classified for future controlled studies.
    try:
        decoded = _parse_strict_model_json(bounded)
    except (TypeError, ValueError, OverflowError):
        decoded = None
    if type(decoded) is dict and (
        {"name", "arguments"} <= set(decoded)
        or "tool_calls" in decoded
        or "function_call" in decoded
    ):
        return "unwrapped_tool_json"
    if re.search(r"<\|(?:tool_call|channel|im_start)[^>]*>", bounded):
        return "unsupported_tool_markup"
    return "plain_final_without_source"
