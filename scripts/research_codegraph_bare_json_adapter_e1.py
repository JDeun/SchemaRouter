"""E1-only opt-in: one strict bare JSON native call, no other model repair.

The canonical parser remains unmodified. Accept only a JSON object naming
exactly one *already exposed* original native tool with scalar arguments,
then reparse via the original strict tool-call grammar. A malformed JSON,
duplicate-key, multi-call, new route or unauthorized native execution is
NEVER corrected or auto-executed. This is not a product API.
"""
from __future__ import annotations

from typing import Any

from scripts.research_codegraph_action_shape_e1 import structural_action_label
from scripts.research_real_qwen_bound_two_step_e0 import (
    _parse_strict_model_json,
    _strip_one_chatml_marker,
    parse_one_model_action,
)


def parse_native_action_optin(
    text: str, *,
    offered_names: tuple[str, ...],
    accept_bare_json_native: bool = False,
) -> tuple[str, Any, bool]:
    """Return (canonical_kind, canonical_payload, was_normalized).

    All accepted calls still pass through canonical strict JSON parsing,
    source authorization, exact offered-route checks, argument binding and
    original read-only executor by the calling E1 harness.
    """
    if type(accept_bare_json_native) is not bool:
        raise ValueError("bare native experiment must use an explicit boolean")
    if (
        type(offered_names) is not tuple
        or any(type(name) is not str for name in offered_names)
    ):
        raise ValueError("trusted original offered tool names required")
    kind, value = parse_one_model_action(text)
    if not accept_bare_json_native or kind != "final":
        return kind, value, False
    if structural_action_label(
        text, offered_names=offered_names,
    ) != "bare_json_tool_action":
        return kind, value, False

    raw = _strip_one_chatml_marker(text)
    candidate = _parse_strict_model_json(raw)
    if (
        type(candidate) is not dict
        or set(candidate) != {"name", "arguments"}
        or type(candidate["name"]) is not str
        or candidate["name"] == "research__request_scoped_source_schema"
        or candidate["name"] not in offered_names
    ):
        # A JSON final answer never becomes an unknown or model-invented
        # executable route. Authorization cannot be inferred from its text.
        return kind, value, False

    # Reject wrong grammar, duplicate keys, bad scalar types and nonfinite
    # values in the *original* strict parser, not an alternate validator.
    new_kind, new_value = parse_one_model_action(
        "<tool_call>" + raw + "</tool_call>",
    )
    if new_kind != "tool":
        raise ValueError("strict native action grammar not preserved")
    return new_kind, new_value, True
