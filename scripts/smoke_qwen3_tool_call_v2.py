"""Pre-benchmark B1 v2 multi-turn/determinism smoke for the pinned Qwen model."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.evaluate_agent_utility_phase_b_qwen import (  # noqa: E402
    SYSTEM_PROMPT,
    LocalQwenAgent,
    _parse_tool_calls,
    _runtime_identity,
    _tool_response_message,
)

TOOLS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "contact__lookup",
            "description": (
                "Look up one contact by name and return the contact email address."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "contact name",
                    }
                },
                "required": ["name"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "mail__send",
            "description": "Send one exact message to an email recipient.",
            "parameters": {
                "type": "object",
                "properties": {
                    "recipient": {
                        "type": "string",
                        "description": "recipient email address",
                    },
                    "message": {
                        "type": "string",
                        "description": "message text",
                    },
                },
                "required": ["recipient", "message"],
                "additionalProperties": False,
            },
        },
    },
]

USER_QUERY = (
    "Look up the contact Alex, then send the exact message "
    "'Smoke complete.' to the email address returned by the lookup."
)
OBSERVED_EMAIL = "alex.smoke@example.org"


def _generate_checked(
    agent: LocalQwenAgent,
    messages: list[dict[str, str]],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    generated = agent.generate(messages, TOOLS)
    if generated["context_overflow"]:
        raise SystemExit("unexpected context overflow in B1 v2 smoke")
    calls = _parse_tool_calls(str(generated["text"]))
    if len(calls) != 1:
        raise SystemExit(
            "B1 v2 smoke requires exactly one tool call per assistant turn; "
            f"got {len(calls)}"
        )
    return generated, calls


def main() -> None:
    agent = LocalQwenAgent()
    initial_messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": USER_QUERY},
    ]

    first_a, calls_a = _generate_checked(agent, initial_messages)
    first_b, calls_b = _generate_checked(agent, initial_messages)

    if first_a["text"] != first_b["text"] or calls_a != calls_b:
        raise SystemExit(
            "greedy B1 v2 smoke was not deterministic for an identical prompt"
        )

    first = calls_a[0]
    if first["name"] != "contact__lookup":
        raise SystemExit(f"unexpected first tool: {first['name']!r}")
    name = first["arguments"].get("name")
    if not isinstance(name, str) or name.strip().casefold() != "alex":
        raise SystemExit(f"unexpected first arguments: {first['arguments']!r}")

    observation = {
        "status": "ok",
        "name": "Alex",
        "email": OBSERVED_EMAIL,
    }
    second_messages = [
        *initial_messages,
        {"role": "assistant", "content": str(first_a["text"])},
        {
            "role": "user",
            "content": _tool_response_message([observation]),
        },
    ]

    second_a, second_calls_a = _generate_checked(agent, second_messages)
    second_b, second_calls_b = _generate_checked(agent, second_messages)
    if second_a["text"] != second_b["text"] or second_calls_a != second_calls_b:
        raise SystemExit(
            "greedy B1 v2 smoke was not deterministic after the tool observation"
        )

    second = second_calls_a[0]
    if second["name"] != "mail__send":
        raise SystemExit(f"unexpected second tool: {second['name']!r}")
    if second["arguments"].get("recipient") != OBSERVED_EMAIL:
        raise SystemExit(
            "dependent second call did not use the observed email: "
            f"{second['arguments']!r}"
        )
    if second["arguments"].get("message") != "Smoke complete.":
        raise SystemExit(
            "dependent second call changed the explicit message: "
            f"{second['arguments']!r}"
        )

    print(
        json.dumps(
            {
                "runtime": _runtime_identity(),
                "model_context_limit": agent.context_limit,
                "first_call": first,
                "second_call": second,
                "initial_input_tokens": first_a["input_tokens"],
                "initial_tool_tokens": first_a["tool_tokens"],
                "second_input_tokens": second_a["input_tokens"],
                "second_tool_tokens": second_a["tool_tokens"],
                "deterministic_initial": True,
                "deterministic_after_observation": True,
                "context_overflow": False,
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
