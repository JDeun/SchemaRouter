"""Isolated Qwen tool-history wire-format contrast, no executor or model changes.

Hugging Face's model-agnostic chat-template guidance represents an assistant
tool call as structured tool_calls and a later tool-role JSON response, whereas
the frozen SchemaRouter E0 pilot manually replays XML plus a trailing Qwen
end-of-turn marker and then XML-wraps each tool response.

This module only controls serialized CONVERSATION HISTORY after an already
authorized real host call. It must never fabricate a call, authorize a tool,
edit a provider result, reveal gold or change the model's next-turn parser.
"""
from __future__ import annotations

import json
from typing import Any

ALLOWED_TRANSCRIPTS = ("raw", "strip-eos", "structured")
EOS_MARKERS = ("<|im_end|>", "<|endoftext|>")


def append_bound_tool_transcript_e0(
    messages: list[dict[str, Any]],
    *,
    mode: str,
    raw_generated_text: str,
    route_id: str,
    arguments: dict[str, Any],
    public_observation: dict[str, Any],
) -> None:
    """Append previously *executed* host result in one of three E0 formats.

    The caller has already checked route and arguments against the principal
    source and executed the call. No model proposal is executed here.
    """
    if mode not in ALLOWED_TRANSCRIPTS or type(mode) is not str:
        raise ValueError("invalid preregistered E0 transcript mode")
    if (
        type(messages) is not list or type(raw_generated_text) is not str
        or type(route_id) is not str or route_id.count(".") != 1
        or type(arguments) is not dict or type(public_observation) is not dict
        or public_observation.get("status") != "ok"
        or any(type(k) is not str for k in arguments)
    ):
        raise ValueError("malformed model history append request")
    try:
        serialized = json.dumps(
            public_observation, ensure_ascii=False, sort_keys=True,
            allow_nan=False, separators=(",", ":"),
        )
        # Defensive preflight: structured tool_calls are rendered by the
        # tokenizer; never provide non-serializable or non-finite arguments.
        json.dumps(arguments, allow_nan=False)
    except (TypeError, ValueError, OverflowError, RecursionError) as exc:
        raise ValueError("unverifiable host transcript payload") from exc
    if len(serialized.encode("utf-8")) > 4096:
        raise ValueError("public observation exceeds bounded transcript size")
    if mode == "structured":
        messages.append({
            "role": "assistant",
            "content": "",
            "tool_calls": [{
                "type": "function",
                "function": {
                    "name": route_id.replace(".", "__", 1),
                    "arguments": dict(arguments),
                },
            }],
        })
        # Apply the tokenizer's native tool-role wrapping. Do not manually
        # add an extra <tool_response> wrapper around a role='tool' message.
        messages.append({"role": "tool", "content": serialized})
        return
    if mode == "strip-eos":
        text = raw_generated_text
        for marker in EOS_MARKERS:
            if text.endswith(marker):
                text = text[:-len(marker)]
                break
    else:
        text = raw_generated_text
    messages.append({"role": "assistant", "content": text})
    messages.append({
        "role": "tool",
        "content": "<tool_response>\n" + serialized + "\n</tool_response>",
    })
