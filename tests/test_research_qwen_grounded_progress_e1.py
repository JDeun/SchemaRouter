"""Stage-aware Qwen prompt is truthful and cannot host-rescue a wrong call."""
from __future__ import annotations

import json
from typing import Any

import httpx
import pytest

from scripts import research_qwen_state_ready_open_meteo_e1 as paired
from scripts.research_real_qwen_open_meteo_two_hop_e1 import (
    SOURCE_PROGRESS_NOTE,
    evaluate_one,
)

CITY, LANGUAGE, COUNTRY = "Seoul", "en", "KR"
LAT, LON = 37.56, 126.98


def _action(route: str, arguments: dict[str, Any]) -> str:
    return "<tool_call>\n" + json.dumps({
        "name": route.replace(".", "__", 1), "arguments": arguments,
    }) + "\n</tool_call>"


GEOCODE = _action("open_meteo_geocoding.search", {
    "name": CITY, "language": LANGUAGE, "country_code": COUNTRY,
})
FORECAST = _action("open_meteo_weather.current", {
    "latitude": LAT, "longitude": LON,
})
FINAL = json.dumps({
    "temperature_2m": 16.5,
    "unit": "°C",
    "observed_at": "2026-10-18T10:00",
})


class Agent:
    def __init__(self, outputs: list[str]) -> None:
        self.outputs = outputs
        self.seen: list[tuple[list[dict[str, str]], tuple[str, ...]]] = []

    def generate(
        self, messages: list[dict[str, str]],
        tools: list[dict[str, Any]],
    ) -> dict[str, Any]:
        self.seen.append((
            [dict(msg) for msg in messages],
            tuple(tool["name"] for tool in tools),
        ))
        text = self.outputs[min(len(self.seen) - 1, len(self.outputs) - 1)]
        return {
            "text": text, "context_overflow": False, "latency_ms": 0.0,
        }


def _transport(requests: list[str], *, geocode_failure=False):
    def respond(req: httpx.Request) -> httpx.Response:
        requests.append(req.url.path)
        if geocode_failure:
            raise httpx.ConnectError("PRIVATE_SOURCE_MESSAGE", request=req)
        if req.url.path == "/v1/search":
            return httpx.Response(200, json={"results": [{
                "id": 1835848, "country_code": "KR",
                "latitude": LAT, "longitude": LON,
            }]})
        if req.url.path == "/v1/forecast":
            return httpx.Response(200, json={
                "current": {
                    "time": "2026-10-18T10:00", "temperature_2m": 16.5,
                },
                "current_units": {"temperature_2m": "°C"},
            })
        raise AssertionError("unexpected original source path")

    return httpx.MockTransport(respond)


@pytest.mark.asyncio
async def test_progress_notice_only_after_actual_authorized_geocode():
    requests: list[str] = []
    agent = Agent([GEOCODE, FORECAST, FINAL])
    async with httpx.AsyncClient(transport=_transport(requests)) as client:
        result = await evaluate_one(
            agent, client, language=LANGUAGE, city=CITY, country=COUNTRY,
            menu_mode="state_ready_progress",
        )
    assert result["full_task_complete"] is True
    assert requests == ["/v1/search", "/v1/forecast"]
    assert len(agent.seen) == 3
    assert agent.seen[0][1] == ("open_meteo_geocoding__search",)
    assert agent.seen[1][1] == ("open_meteo_weather__current",)
    assert agent.seen[2][1] == ()
    assert all(
        SOURCE_PROGRESS_NOTE not in msg["content"]
        for msg in agent.seen[0][0]
    )
    notice_count = [
        sum(msg["content"].count(SOURCE_PROGRESS_NOTE) for msg in messages)
        for messages, _ in agent.seen
    ]
    assert notice_count == [0, 1, 1]


@pytest.mark.asyncio
async def test_premature_final_remains_failed_not_host_repaired():
    requests: list[str] = []
    agent = Agent([GEOCODE, FINAL])
    async with httpx.AsyncClient(transport=_transport(requests)) as client:
        result = await evaluate_one(
            agent, client, language=LANGUAGE, city=CITY, country=COUNTRY,
            menu_mode="state_ready_progress",
        )
    assert result["termination_reason"] == "premature_final"
    assert result["full_task_complete"] is False
    assert result["real_forecast_http_attempts"] == 0
    assert requests == ["/v1/search"]
    assert SOURCE_PROGRESS_NOTE in agent.seen[1][0][-1]["content"]


@pytest.mark.asyncio
async def test_failed_original_http_does_not_publish_progress_notice():
    requests: list[str] = []
    agent = Agent([GEOCODE, FORECAST])
    async with httpx.AsyncClient(
        transport=_transport(requests, geocode_failure=True),
    ) as client:
        result = await evaluate_one(
            agent, client, language=LANGUAGE, city=CITY, country=COUNTRY,
            menu_mode="state_ready_progress", transport_retry_budget=1,
        )
    assert requests == ["/v1/search", "/v1/search"]
    assert len(agent.seen) == 1
    assert result["full_task_complete"] is False
    assert "PRIVATE_SOURCE_MESSAGE" not in json.dumps(result)
    assert all(
        SOURCE_PROGRESS_NOTE not in msg["content"]
        for msg in agent.seen[0][0]
    )


def test_progress_text_has_no_route_or_answer_or_hidden_native_fields():
    lowered = SOURCE_PROGRESS_NOTE.lower()
    for prohibited in (
        "open_meteo", "search", "forecast", "longitude", "latitude",
        "37.56", "126.98", "16.5", "customer_id", "weather.current",
    ):
        assert prohibited not in lowered
    assert "has been verified yet" in lowered


@pytest.mark.asyncio
async def test_same_provider_paired_evaluator_preserves_strict_denominator(
    monkeypatch: pytest.MonkeyPatch,
):
    calls: list[tuple[str, str, int]] = []

    async def fake_evaluate(
        agent, client, *, language, city, country, menu_mode,
        transport_retry_budget,
    ):
        del agent, client, city, country
        calls.append((language, menu_mode, transport_retry_budget))
        return {
            "language": language,
            "independent_e2_qualified": False,
            "full_task_complete": False,
            "strict_final_answer_correct": False,
            "model_generated_two_step_complete": False,
            "real_geocoding_calls": 0,
            "real_forecast_calls": 0,
            "real_geocoding_http_attempts": 0,
            "real_forecast_http_attempts": 0,
            "termination_reason": "premature_final",
            "trusted_failure_stage": None,
            "trusted_transport_error_kind": None,
            "model_turns": 1,
            "model_generation_ms": 0.0,
        }

    monkeypatch.setattr(paired, "evaluate_one", fake_evaluate)
    evidence = "REAL_QWEN_OPEN_METEO_GROUNDED_PROGRESS_E1_EXPOSED_DEV_NOT_E2"
    value = await paired.compare(
        type("AgentLike", (), {"generate": lambda *_a, **_k: None})(),
        object(), transport_retry_budget=1,
        arms=("state_ready", "state_ready_progress"), evidence=evidence,
    )
    assert calls == [
        ("en", "state_ready", 1), ("en", "state_ready_progress", 1),
        ("ko", "state_ready_progress", 1), ("ko", "state_ready", 1),
        ("ja", "state_ready", 1), ("ja", "state_ready_progress", 1),
    ]
    assert value["study"] == evidence
    assert value["shared_host_transport_retry_budget"] == 1
    assert value["independent_e2_qualified"] is False
    assert all(
        x["completed_strict_real_provider_tasks"] == 0
        for x in value["by_arm"].values()
    )
