from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import scripts.smoke_gemma4_b2_tool_call as smoke


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


def test_gemma4_viability_client_requires_observation_dependent_second_call(
    tmp_path: Path,
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

    seen_payloads: list[dict[str, Any]] = []

    def fake_request(
        url: str,
        payload: dict[str, Any],
        timeout: float,
    ) -> dict[str, Any]:
        assert url.endswith("/v1/chat/completions")
        assert timeout == 1.0
        seen_payloads.append(payload)
        return next(responses)

    monkeypatch.setattr(smoke, "_request", fake_request)
    result = smoke.run("http://localhost:8080", 1.0)

    assert result["status"] == "pass"
    assert result["benchmark_rows_consumed"] is False
    assert [
        row["tool_name"]
        for row in result["initial_repetitions"]
    ] == ["lookup_record", "lookup_record"]
    assert result["dependent_second_turn"]["tool_name"] == "send_message"
    assert len(seen_payloads) == 3
    assert len(seen_payloads[0]["messages"]) == 1
    assert len(seen_payloads[1]["messages"]) == 1
    assert len(seen_payloads[2]["messages"]) == 3
    assert seen_payloads[2]["messages"][-1]["role"] == "tool"
    assert seen_payloads[2]["messages"][-1]["content"] == '{"title":"alpha"}'


def test_gemma4_viability_protocol_does_not_reference_benchmark_rows() -> None:
    protocol = json.loads(
        (
            smoke.ROOT
            / "benchmarks"
            / "agent-utility-b2-gemma4-viability.json"
        ).read_text(encoding="utf-8")
    )

    assert protocol["issue"] == 444
    assert protocol["parent_issue"] == 423
    assert protocol["benchmark_rows_consumed"] is False
    assert protocol["status"] == "frozen_before_viability_inference"
    assert protocol["failure_policy"]["no_B2_task_or_catalog_exposure"] is True
    assert protocol["model"]["sha256"] == (
        "31d3a3c630d4e71a7416498c42660dd3805066948acaec76a47e1ffac7010132"
    )
