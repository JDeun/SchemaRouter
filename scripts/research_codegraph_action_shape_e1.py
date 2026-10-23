"""Opt-in, post-generation structural labels for Qwen E1; no raw output egress.

This is a classifier, never a parser, schema repairer, retry policy or
execution authority. The existing strict model-action parser and original
native executor decide every real action exactly as before.
"""
from __future__ import annotations

import math
import re
from typing import Any

from scripts.research_real_qwen_bound_two_step_e0 import (
    TOOL_CALL,
    _parse_strict_model_json,
    _strip_one_chatml_marker,
)

# Labels are the entire allowable public surface: no names, arguments,
# model text, prompts, private observations, route IDs or parser exceptions.
CATEGORIES = frozenset({
    "invalid_output_type",
    "invalid_bounded_text",
    "chatml_wrapped_action",
    "multiple_tool_calls",
    "partial_tool_call",
    "bare_json_tool_action",
    "invalid_json",
    "duplicate_json_key",
    "non_object_payload",
    "invalid_tool_envelope",
    "arguments_not_object",
    "non_scalar_arguments",
    "invalid_tool_name",
    "unoffered_tool_name",
    "valid_schema_request_shape",
    "valid_native_tool_call_shape",
    "final_before_schema",
    "final_after_schema",
    "final_after_native",
    "bare_final_json",
})


def _constant(_text: str) -> None:
    raise ValueError("nonfinite value")


def _object_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    obj: dict[str, Any] = {}
    for key, value in pairs:
        if key in obj:
            raise KeyError("duplicate key")
        obj[key] = value
    return obj


def _load_untrusted_json(text: str) -> Any:
    # Never include the parser's exception in the output; even exception
    # text can expose a snippet of untrusted model content.
    import json

    return json.loads(
        text, object_pairs_hook=_object_pairs, parse_constant=_constant,
    )


def structural_action_label(
    text: Any,
    *,
    offered_names: tuple[str, ...],
    after_schema: bool = False,
    native_calls: int = 0,
) -> str:
    """Classify one emitted model turn, without authorizing or changing it.

    Only static labels are returned. Even if an untrusted response contains
    private source data, all such bytes remain inside this call.
    """
    if type(text) is not str:
        return "invalid_output_type"
    if (
        type(after_schema) is not bool
        or type(native_calls) is not int or not 0 <= native_calls <= 8
        or type(offered_names) is not tuple
        or any(type(name) is not str for name in offered_names)
    ):
        raise ValueError("invalid private diagnostic controls")
    try:
        raw = _strip_one_chatml_marker(text)
    except ValueError:
        return "invalid_bounded_text"

    if "<|im_start|>" in raw or "<|im_sep|>" in raw or "<|im_end|>" in raw:
        return "chatml_wrapped_action"
    opens = raw.count("<tool_call>")
    closes = raw.count("</tool_call>")
    if opens > 1 or closes > 1:
        return "multiple_tool_calls"
    if (opens, closes) in ((1, 0), (0, 1)):
        return "partial_tool_call"
    match = TOOL_CALL.fullmatch(raw)
    if match is None:
        if "<tool_call" in raw or "</tool_call>" in raw:
            return "partial_tool_call"
        try:
            bare = _load_untrusted_json(raw)
        except (TypeError, ValueError, KeyError):
            bare = None
        if type(bare) is dict:
            if "name" in bare and "arguments" in bare:
                return "bare_json_tool_action"
            return "bare_final_json"
        if native_calls:
            return "final_after_native"
        if after_schema:
            return "final_after_schema"
        return "final_before_schema"

    try:
        payload = _load_untrusted_json(match.group(1))
    except KeyError:
        return "duplicate_json_key"
    except (ValueError, TypeError):
        return "invalid_json"

    if type(payload) is not dict:
        return "non_object_payload"
    if set(payload) != {"name", "arguments"}:
        return "invalid_tool_envelope"
    name = payload["name"]
    args = payload["arguments"]
    if type(name) is not str or not re.fullmatch(
        r"[a-z][a-z0-9_]*__[a-z][a-z0-9_]*", name,
    ):
        return "invalid_tool_name"
    if type(args) is not dict:
        return "arguments_not_object"

    if name == "research__request_scoped_source_schema":
        values = args.get("route_ids")
        if (
            set(args) == {"route_ids"}
            and type(values) is list
            and 1 <= len(values) <= 5
            and all(type(x) is str for x in values)
            and len(set(values)) == len(values)
        ):
            return (
                "valid_schema_request_shape" if name in offered_names
                else "unoffered_tool_name"
            )
        return "non_scalar_arguments"

    if any(
        type(key) is not str or type(value) not in (str, int, float, bool)
        or type(value) is float and not math.isfinite(value)
        for key, value in args.items()
    ):
        return "non_scalar_arguments"
    if name not in offered_names:
        return "unoffered_tool_name"
    return "valid_native_tool_call_shape"
