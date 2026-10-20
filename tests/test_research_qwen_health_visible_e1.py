"""No-network, no-model checks of Qwen health exposure E1 experiment."""
from __future__ import annotations

import asyncio
import json

import pytest

from scripts.research_qwen_health_visible_e1 import (
    PHASES,
    _safe_generation,
    run_visibility_probe,
)

_ALLOWED_TOOL = (
    '<tool_call>{"name":"open_meteo_geocoding__search",'
    '"arguments":{"name":"Seoul","language":"en","country_code":"KR"}}'
    "</tool_call>"
)
_DENIED_TOOL = (
    '<tool_call>{"name":"open_meteo_weather__current",'
    '"arguments":{"latitude":37.56,"longitude":126.98}}</tool_call>'
)


class ScriptedAgent:
    def __init__(self, text: str):
        self.text = text
        self.exposures: list[tuple[str, ...]] = []

    def generate(self, messages, tools):
        assert len(messages) == 2
        self.exposures.append(tuple(item["name"] for item in tools))
        return {
            "text": self.text,
            "context_overflow": False,
            "latency_ms": 1.0,
            "input_tokens": 20,
            "tool_tokens": len(tools) * 7,
            "output_tokens": 8,
        }


@pytest.mark.asyncio
async def test_actual_model_tool_json_is_one_zero_one_under_host_health():
    agent = ScriptedAgent(_ALLOWED_TOOL)
    r = await run_visibility_probe(agent)
    assert r["evidence_tier"] == "INJECTED_AGENT_NO_REAL_QWEN_E1"
    assert r["languages"] == ["en", "ko", "ja"]
    assert r["phases"] == list(PHASES)
    assert r["shared_router_across_episodes"] is True
    assert r["executed_model_tool_calls"] == 0
    assert r["external_provider_http_requests"] == 0
    assert r["independent_e2_qualified"] is False
    assert r["real_provider_success_qualified"] is False
    assert r["model_task_completion_measured"] is False
    assert r["production_default_changed"] is False
    assert len(agent.exposures) == 9
    for idx in (0, 3, 6):
        assert agent.exposures[idx] == ("open_meteo_geocoding__search",)
        assert agent.exposures[idx + 1] == ()
        assert agent.exposures[idx + 2] == (
            "open_meteo_geocoding__search",
        )
    for lang, rows in r["results"].items():
        assert lang in ("en", "ko", "ja")
        assert set(rows) == set(PHASES)
        assert [rows[p]["exposed_tool_count"] for p in PHASES] == [1, 0, 1]
        assert rows["healthy"]["action_class"] == "attempt_visible_tool"
        assert rows["unavailable"]["action_class"] == "attempt_hidden_or_unknown_tool"
        assert rows["recovered"]["action_class"] == "attempt_visible_tool"
        assert all(row["attempts_executed"] == 0 for row in rows.values())
    payload = json.dumps(r)
    assert "Seoul" not in payload
    assert "latitude" not in payload
    assert "<tool_call>" not in payload
    assert "original_query" not in payload
    assert "actual_provider_response" not in payload


@pytest.mark.asyncio
async def test_agent_cannot_execute_unoffered_weather_route():
    agent = ScriptedAgent(_DENIED_TOOL)
    r = await run_visibility_probe(agent)
    assert all(
        cell["action_class"] == "attempt_hidden_or_unknown_tool"
        for rows in r["results"].values()
        for cell in rows.values()
    )
    assert all(
        row["provider_http_requests"] == 0
        and row["attempts_executed"] == 0
        for rows in r["results"].values()
        for row in rows.values()
    )


@pytest.mark.asyncio
async def test_malformed_model_final_cannot_be_misreported_as_tool_attempt():
    r = await run_visibility_probe(ScriptedAgent("<tool_call>incomplete"))
    assert all(
        cell["action_class"] == "invalid_format"
        for rows in r["results"].values()
        for cell in rows.values()
    )


@pytest.mark.parametrize(("response", "expected"), (
    ("REQUEST_MORE_TOOLS", True),
    ("REQUEST_MORE_TOOLS<|im_end|>", True),
    ("REQUEST_MORE_TOOLS <|im_end|>", False),
    ("Cannot do it.", False),
    ("{\\"reason\\":\\"unsupported\\"}", False),
))
def test_exact_host_refusal_is_not_confused_with_any_terminal(
    response, expected,
):
    result = _safe_generation({
        "text": response, "latency_ms": 1.0,
        "context_overflow": False,
        "input_tokens": 20, "tool_tokens": 0, "output_tokens": 5,
    }, ())
    assert result["action_class"] == "terminal_no_tool"
    assert result["exact_host_refusal_after_allowlisted_eot"] is expected
    assert result["attempts_executed"] == 0
    assert result["provider_http_requests"] == 0


@pytest.mark.asyncio
async def test_incorrect_final_cannot_be_promoted_to_safe_refusal():
    result = await run_visibility_probe(ScriptedAgent("I cannot provide it."))
    assert all(
        row["action_class"] == "terminal_no_tool"
        and row["exact_host_refusal_after_allowlisted_eot"] is False
        for phase in result["results"].values()
        for row in phase.values()
    )


@pytest.mark.parametrize("broken", (
    {"text": "REQUEST_MORE_TOOLS", "latency_ms": float("nan")},
    {"text": "REQUEST_MORE_TOOLS", "latency_ms": -1.0},
    {"text": 5, "latency_ms": 1.0},
))
def test_invalid_model_envelopes_fail_closed(broken):
    with pytest.raises(ValueError, match="invalid actual"):
        _safe_generation(broken, ())


def test_bad_agent_cannot_be_used_as_model():
    with pytest.raises(ValueError, match="generate-compatible"):
        asyncio.run(run_visibility_probe(object()))
