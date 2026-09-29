"""Non-benchmark mechanical tool-call smoke for the pinned B1 Qwen model."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.evaluate_agent_utility_phase_b_qwen import (  # noqa: E402
    LocalQwenAgent,
    _parse_tool_calls,
)

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "weather__current",
            "description": "Get the current weather for one city.",
            "parameters": {
                "type": "object",
                "properties": {
                    "city": {
                        "type": "string",
                        "description": "city name",
                    }
                },
                "required": ["city"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "calculator__add",
            "description": "Add two numbers.",
            "parameters": {
                "type": "object",
                "properties": {
                    "a": {"type": "number"},
                    "b": {"type": "number"},
                },
                "required": ["a", "b"],
                "additionalProperties": False,
            },
        },
    },
]


def main() -> None:
    agent = LocalQwenAgent()
    messages = [
        {
            "role": "system",
            "content": (
                "Use the provided tools. Never invent a tool. "
                "Return a tool call when the user asks for tool data."
            ),
        },
        {
            "role": "user",
            "content": "What is the current weather in Seoul?",
        },
    ]
    generated = agent.generate(messages, TOOLS)
    if generated["context_overflow"]:
        raise SystemExit("unexpected context overflow in synthetic smoke")
    text = str(generated["text"])
    calls = _parse_tool_calls(text)
    if not calls:
        raise SystemExit(
            "pinned generative Qwen did not emit a parseable tool call "
            "on the synthetic smoke"
        )
    first = calls[0]
    if first["name"] != "weather__current":
        raise SystemExit(
            f"unexpected smoke tool: {first['name']!r}"
        )
    city = first["arguments"].get("city")
    if not isinstance(city, str) or "seoul" not in city.casefold():
        raise SystemExit(
            f"unexpected smoke arguments: {first['arguments']!r}"
        )
    print(
        json.dumps(
            {
                "model_context_limit": agent.context_limit,
                "input_tokens": generated["input_tokens"],
                "tool_tokens": generated["tool_tokens"],
                "output_tokens": generated["output_tokens"],
                "latency_ms": generated["latency_ms"],
                "tool_call": first,
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
