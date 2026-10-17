"""Opt-in Qwen-Agent Nous *history* encoding after a validated host call.

This is an E0 transport-only adapter, not a parser, route selector, invoker,
authorization delegate or production API. See upstream-pinned #1513 contract.
"""
from __future__ import annotations

import json
import math
import re
from typing import Any

MAX_PUBLIC_HISTORY_BYTES = 4096
_FORBIDDEN = ("<tool_call", "</tool_call", "<tool_response", "</tool_response", "<|")


def append_authorized_nous_user_history_e0(
    messages: list[dict[str, Any]],
    *,
    authorized_route_ids: tuple[str, ...],
    executed_route_id: str,
    validated_arguments: dict[str, Any],
    public_observation: dict[str, Any],
) -> None:
    """Append source-aligned assistant call + user result, with NO host authority.

    Caller must provide an actually executed and projected host result; this
    module cannot execute or authenticate a provider and cannot create a grant.
    """
    if (
        type(messages) is not list
        or type(authorized_route_ids) is not tuple
        or not authorized_route_ids
        or any(type(x) is not str for x in authorized_route_ids)
        or type(executed_route_id) is not str
        or executed_route_id not in authorized_route_ids
        or re.fullmatch(r"[a-z][a-z0-9_]*\.[a-z][a-z0-9_]*", executed_route_id) is None
        or type(validated_arguments) is not dict
        or any(type(k) is not str for k in validated_arguments)
        or any(
            type(v) not in (str, int, float, bool)
            or (type(v) is float and not math.isfinite(v))
            for v in validated_arguments.values()
        )
        or type(public_observation) is not dict
        or public_observation.get("status") != "ok"
    ):
        raise ValueError("unverifiable upstream Nous history input")

    proposal = {
        "name": executed_route_id.replace(".", "__", 1),
        "arguments": validated_arguments,
    }
    try:
        call_json = json.dumps(
            proposal, ensure_ascii=False, sort_keys=True, allow_nan=False,
        )
        result_json = json.dumps(
            public_observation, ensure_ascii=False, sort_keys=True,
            allow_nan=False,
        )
    except (TypeError, ValueError, OverflowError, RecursionError) as exc:
        raise ValueError("unserializable trusted host history") from exc
    if (
        len(call_json.encode("utf-8")) > MAX_PUBLIC_HISTORY_BYTES
        or len(result_json.encode("utf-8")) > MAX_PUBLIC_HISTORY_BYTES
        or any(mark in call_json or mark in result_json for mark in _FORBIDDEN)
        or '"secret"' in result_json
    ):
        raise ValueError("unsafe or oversized model-facing history")

    # Qwen-Agent's pinned NousFnCallPrompt preprocesses an assistant
    # FunctionCall and a FUNCTION result into assistant <tool_call> and
    # USER <tool_response> messages. Do not replay the raw EOS model text.
    messages.extend([
        {"role": "assistant", "content": "<tool_call>\n" + call_json + "\n</tool_call>"},
        {"role": "user", "content": "<tool_response>\n" + result_json + "\n</tool_response>"},
    ])
