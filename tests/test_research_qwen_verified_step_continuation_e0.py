"""E0 synthetic-only regression for one verified-geocode early-final reminder.

All HTTPX calls use MockTransport. No actual Open-Meteo/provider GETs, Qwen,
independent agent E2, or production routing claim in this test module.
"""
from __future__ import annotations

import json
from typing import Any

import httpx
import pytest

from scripts.research_real_qwen_open_meteo_two_hop_e1 import evaluate_one

LAT = 37.56
LON = 126.98
WEATHER = {"temperature_2m": 16.5, "unit": "°C", "observed_at": "2026-10-18T10:00"}


def _call(route: str, arguments: dict[str, Any]) -> str:
    return "<tool_call>\n" + json.dumps({
        "name": route.replace(".", "__", 1), "arguments": arguments,
    }) + "\n</tool_call>"


GEO = _call("open_meteo_geocoding.search", {
    "name": "Seoul", "language": "en", "country_code": "KR",
})
FORECAST = _call("open_meteo_weather.current", {
    "latitude": LAT, "longitude": LON,
})
FORGED_FORECAST = _call("open_meteo_weather.current", {
    "latitude": LAT + 0.5, "longitude": LON,
})
FINAL = json.dumps(WEATHER)
EARLY = '{"temperature_2m":999,"unit":"°C","observed_at":"invented"}'


class Scripted:
    def __init__(self, outputs: list[str]) -> None:
        self.outputs = outputs
        self.calls = 0
        self.messages: list[list[dict[str, str]]] = []
        self.menus: list[set[str]] = []

    def generate(
        self, messages: list[dict[str, str]], tools: list[dict[str, Any]],
    ) -> dict[str, Any]:
        self.messages.append([dict(message) for message in messages])
        self.menus.append({tool["name"] for tool in tools})
        index = self.calls
        self.calls += 1
        if index >= len(self.outputs):
            raise AssertionError("unexpected extra Qwen call")
        return {
            "text": self.outputs[index],
            "latency_ms": 0.0,
            "context_overflow": False,
        }


def _transport(seen: list[str]) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.url.path)
        if request.url.path == "/v1/search":
            assert request.url.host == "geocoding-api.open-meteo.com"
            return httpx.Response(200, json={"results": [{
                "id": 1835848, "country_code": "KR",
                "latitude": LAT, "longitude": LON,
            }]})
        if request.url.path == "/v1/forecast":
            assert request.url.host == "api.open-meteo.com"
            assert float(request.url.params["latitude"]) == LAT
            assert float(request.url.params["longitude"]) == LON
            return httpx.Response(200, json={
                "current": {
                    "time": "2026-10-18T10:00", "temperature_2m": 16.5,
                },
                "current_units": {"temperature_2m": "°C"},
            })
        raise AssertionError("unsupported provider endpoint")

    return httpx.MockTransport(handler)


async def _run(
    agent: Scripted, seen: list[str], *, budget: int = 0,
    mode: str = "state_ready",
) -> dict[str, Any]:
    async with httpx.AsyncClient(transport=_transport(seen)) as client:
        return await evaluate_one(
            agent, client, language="en", city="Seoul", country="KR",
            menu_mode=mode, evidence_reprompt_budget=budget,
        )


@pytest.mark.asyncio
async def test_original_default_exits_after_unverified_early_final_unchanged():
    seen: list[str] = []
    agent = Scripted([GEO, EARLY])
    row = await _run(agent, seen)
    assert row["termination_reason"] == "premature_final"
    assert row["model_turns"] == 2
    assert row["real_geocoding_calls"] == 1
    assert row["real_forecast_calls"] == 0
    assert "host_evidence_reprompts" not in row
    assert not row["full_task_complete"]
    assert seen == ["/v1/search"]


@pytest.mark.asyncio
async def test_opt_in_reminds_once_but_model_itself_must_make_valid_second_call():
    seen: list[str] = []
    agent = Scripted([GEO, EARLY, FORECAST, FINAL])
    row = await _run(agent, seen, budget=1)
    assert row["full_task_complete"] is True
    assert row["strict_final_answer_correct"] is True
    assert row["termination_reason"] == "completed_final"
    assert row["model_turns"] == 4
    assert row["host_evidence_reprompts"] == 1
    assert row["attempted_model_calls"] == 2
    assert row["real_geocoding_calls"] == row["real_forecast_calls"] == 1
    assert seen == ["/v1/search", "/v1/forecast"]
    assert agent.menus[2] == {"open_meteo_weather__current"}
    assert any(
        message["role"] == "user" and "has not been called yet" in message["content"]
        for message in agent.messages[2]
    )
    # Diagnostic telemetry MUST NOT publish actual source values, gold or text.
    encoded = json.dumps(row, ensure_ascii=False)
    assert "37.56" not in encoded
    assert "16.5" not in encoded
    assert "1835848" not in encoded
    assert "invented" not in encoded
    assert not row["independent_e2_qualified"]


@pytest.mark.asyncio
async def test_second_premature_final_exhausts_budget_without_external_forecast():
    seen: list[str] = []
    row = await _run(Scripted([GEO, EARLY, EARLY]), seen, budget=1)
    assert row["termination_reason"] == "premature_final"
    assert row["host_evidence_reprompts"] == 1
    assert row["attempted_model_calls"] == 1
    assert row["model_turns"] == 3
    assert not row["full_task_complete"]
    assert seen == ["/v1/search"]


@pytest.mark.asyncio
async def test_never_reprompt_or_call_provider_when_no_geocode_was_observed():
    seen: list[str] = []
    row = await _run(Scripted([EARLY]), seen, budget=1)
    assert row["termination_reason"] == "premature_final"
    assert row["host_evidence_reprompts"] == 0
    assert not seen


@pytest.mark.asyncio
async def test_reprompt_cannot_authorize_forged_coordinates_or_tool_order():
    seen: list[str] = []
    row = await _run(
        Scripted([GEO, EARLY, FORGED_FORECAST]), seen, budget=1,
        mode="all_visible",
    )
    assert row["termination_reason"] == "wrong_arguments_or_unobserved_state"
    assert row["host_evidence_reprompts"] == 1
    assert row["real_forecast_http_attempts"] == 0
    assert seen == ["/v1/search"]
    assert not row["full_task_complete"]


@pytest.mark.asyncio
async def test_opt_in_does_not_convert_invalid_post_forecast_final_to_success():
    seen: list[str] = []
    row = await _run(Scripted([GEO, EARLY, FORECAST, EARLY]), seen, budget=1)
    assert row["termination_reason"] == "incorrect_final_value_or_format"
    assert row["model_generated_two_step_complete"]
    assert row["strict_final_answer_correct"] is False
    assert row["host_evidence_reprompts"] == 1
    assert seen == ["/v1/search", "/v1/forecast"]


@pytest.mark.asyncio
@pytest.mark.parametrize("bad", (-1, 2, True, 1.0, "1", None))
async def test_invalid_opt_in_budget_fails_before_any_source_request(bad):
    seen: list[str] = []
    async with httpx.AsyncClient(transport=_transport(seen)) as client:
        with pytest.raises(ValueError, match="unregistered source task or model"):
            await evaluate_one(
                Scripted([GEO]), client,
                language="en", city="Seoul", country="KR",
                evidence_reprompt_budget=bad,
            )
    assert not seen
