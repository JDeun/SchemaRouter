from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import scripts.smoke_llama32_b2_tool_call as smoke  # noqa: E402


def _response(
    *,
    call_id: str,
    name: str,
    arguments: dict[str, Any],
) -> dict[str, Any]:
    return {
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        {
                            "id": call_id,
                            "type": "function",
                            "function": {
                                "name": name,
                                "arguments": json.dumps(arguments),
                            },
                        }
                    ],
                }
            }
        ]
    }


def test_llama32_viability_client_enforces_dependency(
    monkeypatch,
) -> None:
    responses = iter(
        [
            _response(
                call_id="lookup0001",
                name="lookup_record",
                arguments={"record_id": "R-7"},
            ),
            _response(
                call_id="lookup0002",
                name="lookup_record",
                arguments={"record_id": "R-7"},
            ),
            _response(
                call_id="send00001",
                name="send_message",
                arguments={
                    "recipient": "alice@example.org",
                    "message": "alpha",
                },
            ),
        ]
    )
    seen: list[dict[str, Any]] = []

    def fake_request(
        url: str,
        payload: dict[str, Any],
        timeout: float,
    ) -> dict[str, Any]:
        assert url.endswith("/v1/chat/completions")
        assert timeout == 1.0
        seen.append(payload)
        return next(responses)

    monkeypatch.setattr(smoke, "_request", fake_request)
    trace: list[dict[str, Any]] = []
    result = smoke.run("http://localhost:8080", 1.0, trace)

    assert result["status"] == "pass"
    assert result["benchmark_rows_consumed"] is False
    assert len(trace) == 3
    assert [
        row["tool_name"]
        for row in result["initial_repetitions"]
    ] == ["lookup_record", "lookup_record"]
    assert result["dependent_second_turn"]["tool_name"] == "send_message"
    assert len(seen[2]["messages"]) == 3
    assert seen[2]["messages"][-1]["role"] == "tool"
    assert seen[2]["messages"][-1]["content"] == '{"title":"alpha"}'


def test_llama32_viability_protocol_is_non_benchmark_and_exact_pinned() -> None:
    protocol = json.loads(
        (
            ROOT
            / "benchmarks"
            / "agent-utility-b2-llama32-viability.json"
        ).read_text(encoding="utf-8")
    )

    assert protocol["issue"] == 447
    assert protocol["parent_issue"] == 423
    assert protocol["benchmark_rows_consumed"] is False
    assert protocol["status"] == "frozen_before_viability_inference"
    assert protocol["model"]["quantized_repo_revision"] == (
        "54651d07cdbbd900b46c652cbf6672c935a22236"
    )
    assert protocol["model"]["sha256"] == (
        "6c1a2b41161032677be168d354123594c0e6e67d2b9227c84f296ad037c728ff"
    )
    assert protocol["runtime"]["tool_call_handler_expectation"] == (
        "native_llama_3_2"
    )
    assert protocol["observability"]["raw_response_trace_required"] is True
