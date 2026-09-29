"""Two-turn structured tool-calling viability smoke for #444.

This script never imports or reads B1/B2 benchmark rows. It talks only to a local
OpenAI-compatible llama-server using the synthetic tool contract frozen in
benchmarks/agent-utility-b2-gemma4-viability.json.
"""

from __future__ import annotations

import argparse
import json
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
PROTOCOL_PATH = ROOT / "benchmarks" / "agent-utility-b2-gemma4-viability.json"


def _request(url: str, payload: dict[str, Any], timeout: float) -> dict[str, Any]:
    body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(
            f"server returned HTTP {error.code}: {detail}"
        ) from error


def _arguments(call: dict[str, Any]) -> dict[str, Any]:
    function = call.get("function")
    if not isinstance(function, dict):
        raise RuntimeError(f"missing structured function object: {call!r}")
    raw = function.get("arguments")
    if isinstance(raw, dict):
        return raw
    if not isinstance(raw, str):
        raise RuntimeError(f"tool arguments are not structured/JSON text: {raw!r}")
    parsed = json.loads(raw)
    if not isinstance(parsed, dict):
        raise RuntimeError(f"tool arguments did not decode to an object: {parsed!r}")
    return parsed


def _single_tool_call(response: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    choices = response.get("choices")
    if not isinstance(choices, list) or len(choices) != 1:
        raise RuntimeError(f"expected one response choice: {response!r}")
    message = choices[0].get("message")
    if not isinstance(message, dict):
        raise RuntimeError(f"missing assistant message: {response!r}")
    calls = message.get("tool_calls")
    if not isinstance(calls, list) or len(calls) != 1:
        raise RuntimeError(
            "expected exactly one structured tool call; "
            f"received {calls!r}"
        )
    call = calls[0]
    if not isinstance(call, dict):
        raise RuntimeError(f"tool call must be an object: {call!r}")
    return message, call


def _tools(protocol: dict[str, Any]) -> list[dict[str, Any]]:
    descriptions = {
        "lookup_record": "Look up one record by identifier.",
        "send_message": "Send a message to a recipient.",
    }
    return [
        {
            "type": "function",
            "function": {
                "name": tool["name"],
                "description": descriptions[tool["name"]],
                "parameters": tool["parameters"],
            },
        }
        for tool in protocol["tools"]
    ]


def _payload(
    protocol: dict[str, Any],
    messages: list[dict[str, Any]],
) -> dict[str, Any]:
    generation = protocol["generation"]
    return {
        "model": "gemma-4-E2B-it-Q4_0.gguf",
        "messages": messages,
        "tools": _tools(protocol),
        "tool_choice": generation["tool_choice"],
        "parallel_tool_calls": generation["parallel_tool_calls"],
        "temperature": generation["temperature"],
        "top_p": generation["top_p"],
        "seed": generation["seed"],
        "max_tokens": generation["max_tokens_per_turn"],
        "stream": False,
    }


def run(base_url: str, timeout: float) -> dict[str, Any]:
    protocol = json.loads(PROTOCOL_PATH.read_text(encoding="utf-8"))
    url = base_url.rstrip("/") + "/v1/chat/completions"
    user_message = {
        "role": "user",
        "content": protocol["task"]["user_request"],
    }

    initial_results: list[dict[str, Any]] = []
    first_message: dict[str, Any] | None = None
    first_call: dict[str, Any] | None = None

    for repetition in range(2):
        started = time.perf_counter()
        response = _request(
            url,
            _payload(protocol, [user_message]),
            timeout,
        )
        latency = time.perf_counter() - started
        message, call = _single_tool_call(response)
        function = call["function"]
        name = function.get("name")
        args = _arguments(call)
        if name != "lookup_record":
            raise RuntimeError(
                f"initial repetition {repetition} selected {name!r}, "
                "expected 'lookup_record'"
            )
        if args != {"record_id": "R-7"}:
            raise RuntimeError(
                f"initial repetition {repetition} arguments drifted: {args!r}"
            )
        initial_results.append(
            {
                "repetition": repetition,
                "latency_seconds": latency,
                "tool_name": name,
                "arguments": args,
            }
        )
        if repetition == 0:
            first_message = message
            first_call = call

    assert first_message is not None
    assert first_call is not None

    call_id = first_call.get("id")
    if not isinstance(call_id, str) or not call_id:
        raise RuntimeError(f"first structured tool call has no id: {first_call!r}")

    lookup_observation = protocol["task"]["lookup_observation"]
    continuation_messages = [
        user_message,
        first_message,
        {
            "role": "tool",
            "tool_call_id": call_id,
            "name": "lookup_record",
            "content": json.dumps(lookup_observation, separators=(",", ":")),
        },
    ]

    started = time.perf_counter()
    second_response = _request(
        url,
        _payload(protocol, continuation_messages),
        timeout,
    )
    second_latency = time.perf_counter() - started
    _, second_call = _single_tool_call(second_response)
    second_name = second_call["function"].get("name")
    second_args = _arguments(second_call)

    if second_name != "send_message":
        raise RuntimeError(
            f"dependent second turn selected {second_name!r}, "
            "expected 'send_message'"
        )
    if second_args.get("recipient") != "alice@example.org":
        raise RuntimeError(
            f"dependent recipient drifted: {second_args!r}"
        )
    message_text = second_args.get("message")
    if not isinstance(message_text, str) or "alpha" not in message_text:
        raise RuntimeError(
            "dependent second call did not use the lookup observation: "
            f"{second_args!r}"
        )

    return {
        "schema_version": 1,
        "issue": 444,
        "status": "pass",
        "protocol": str(PROTOCOL_PATH.relative_to(ROOT)),
        "initial_repetitions": initial_results,
        "dependent_second_turn": {
            "latency_seconds": second_latency,
            "tool_name": second_name,
            "arguments": second_args,
        },
        "benchmark_rows_consumed": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--base-url",
        default="http://127.0.0.1:8080",
    )
    parser.add_argument("--timeout", type=float, default=180.0)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    result = run(args.base_url, args.timeout)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
