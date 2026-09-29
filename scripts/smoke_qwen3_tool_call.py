"""Non-benchmark two-turn mechanical tool-call smoke for pinned B1 Qwen."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.evaluate_agent_utility_phase_b_qwen import (  # noqa: E402
    LocalQwenAgent,
    _parse_tool_calls,
    _runtime_identity,
    _tool_response_message,
)

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "lookup__value",
            "description": "Look up one deterministic numeric value by key.",
            "parameters": {
                "type": "object",
                "properties": {
                    "key": {
                        "type": "string",
                        "description": "lookup key",
                    }
                },
                "required": ["key"],
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

SYSTEM = (
    "Use the provided tools. Never invent a tool. "
    "Execute at most one tool call per assistant turn. "
    "When a later tool depends on an earlier result, wait for the tool "
    "observation before issuing the dependent call."
)

QUERY = (
    "First look up the value for key alpha. After you receive that value, "
    "add 1 to it with the calculator. Do not answer before both tool calls."
)

OBSERVATION = {
    "status": "ok",
    "key": "alpha",
    "value": 41,
}


def _single_trajectory(agent: LocalQwenAgent) -> dict[str, Any]:
    messages = [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": QUERY},
    ]

    first_generated = agent.generate(messages, TOOLS)
    if first_generated["context_overflow"]:
        raise SystemExit("unexpected context overflow on smoke turn 1")
    first_text = str(first_generated["text"])
    first_calls = _parse_tool_calls(first_text)
    if len(first_calls) != 1:
        raise SystemExit(
            f"expected exactly one first-turn tool call, got {first_calls!r}"
        )
    first = first_calls[0]
    if first["name"] != "lookup__value":
        raise SystemExit(f"unexpected first smoke tool: {first['name']!r}")
    key = first["arguments"].get("key")
    if not isinstance(key, str) or key.casefold() != "alpha":
        raise SystemExit(
            f"unexpected first smoke arguments: {first['arguments']!r}"
        )

    messages.append({"role": "assistant", "content": first_text})
    messages.append(
        {
            "role": "user",
            "content": _tool_response_message([OBSERVATION]),
        }
    )

    second_generated = agent.generate(messages, TOOLS)
    if second_generated["context_overflow"]:
        raise SystemExit("unexpected context overflow on smoke turn 2")
    second_text = str(second_generated["text"])
    second_calls = _parse_tool_calls(second_text)
    if len(second_calls) != 1:
        raise SystemExit(
            f"expected exactly one dependent tool call, got {second_calls!r}"
        )
    second = second_calls[0]
    if second["name"] != "calculator__add":
        raise SystemExit(f"unexpected second smoke tool: {second['name']!r}")

    a = second["arguments"].get("a")
    b = second["arguments"].get("b")
    if not isinstance(a, (int, float)) or isinstance(a, bool):
        raise SystemExit(f"invalid dependent a argument: {a!r}")
    if not isinstance(b, (int, float)) or isinstance(b, bool):
        raise SystemExit(f"invalid dependent b argument: {b!r}")
    if float(a) != 41.0 or float(b) != 1.0:
        raise SystemExit(
            f"dependent smoke ignored observation: {second['arguments']!r}"
        )

    return {
        "first_text": first_text,
        "second_text": second_text,
        "first_call": first,
        "second_call": second,
        "turn1": {
            "input_tokens": first_generated["input_tokens"],
            "tool_tokens": first_generated["tool_tokens"],
            "output_tokens": first_generated["output_tokens"],
            "latency_ms": first_generated["latency_ms"],
        },
        "turn2": {
            "input_tokens": second_generated["input_tokens"],
            "tool_tokens": second_generated["tool_tokens"],
            "output_tokens": second_generated["output_tokens"],
            "latency_ms": second_generated["latency_ms"],
        },
    }


def main() -> None:
    agent = LocalQwenAgent()
    first = _single_trajectory(agent)
    second = _single_trajectory(agent)

    if first["first_text"] != second["first_text"]:
        raise SystemExit("first-turn greedy output is not deterministic")
    if first["second_text"] != second["second_text"]:
        raise SystemExit("second-turn greedy output is not deterministic")

    print(
        json.dumps(
            {
                "runtime": _runtime_identity(),
                "model_context_limit": agent.context_limit,
                "deterministic_repeat": True,
                "dependent_second_tool_call_after_observation": True,
                "first_call": first["first_call"],
                "second_call": first["second_call"],
                "turn1": first["turn1"],
                "turn2": first["turn2"],
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
