"""E1 generic single completion feedback: mock agent is NOT Qwen evidence."""
from __future__ import annotations

import json
from typing import Any

import httpx
import pytest

from scripts.research_real_qwen_open_meteo_two_hop_e1 import evaluate_one

CITY, LANG, COUNTRY = "Seoul", "en", "KR"
LAT, LON = 37.56, 126.98


def _tool(route: str, args: dict[str, Any]) -> str:
    return "<tool_call>\n" + json.dumps({
        "name": route.replace(".", "__", 1), "arguments": args,
    }) + "\n</tool_call>"


GEO = _tool(
    "open_meteo_geocoding.search",
    {"name": CITY, "language": LANG, "country_code": COUNTRY},
)
WEATHER = _tool(
    "open_meteo_weather.current", {"latitude": LAT, "longitude": LON},
)
FINAL = json.dumps({
    "temperature_2m": 16.5,
    "unit": "°C",
    "observed_at": "2026-10-18T10:00",
})
WRONG = json.dumps({
    "temperature_2m": -25.0, "unit": "°C",
    "observed_at": "2026-10-18T10:00",
})


class Model:
    def __init__(self, outputs: list[str]) -> None:
        self.outputs = outputs
        self.history: list[list[dict[str, Any]]] = []
        self.position = 0

    def generate(self, messages, tools):
        self.history.append([
            dict(x) for x in messages
        ])
        pos = self.position
        self.position += 1
        return {
            "text": self.outputs[min(pos, len(self.outputs) - 1)],
            "latency_ms": 0.0, "context_overflow": False,
        }


def _source(seen: list[str], fail=False):
    def serve(request: httpx.Request) -> httpx.Response:
        seen.append(request.url.path)
        if fail:
            raise httpx.ConnectError("PRIVATE_SOURCE_CANARY", request=request)
        if request.url.path == "/v1/search":
            return httpx.Response(200, json={"results": [{
                "id": 1835848, "country_code": COUNTRY,
                "latitude": LAT, "longitude": LON,
            }]})
        if request.url.path == "/v1/forecast":
            return httpx.Response(200, json={
                "current": {
                    "time": "2026-10-18T10:00", "temperature_2m": 16.5,
                },
                "current_units": {"temperature_2m": "°C"},
            })
        raise AssertionError("not an approved source endpoint")

    return httpx.MockTransport(serve)


async def _evaluate(outputs: list[str], *, feedback=0, fail=False):
    seen: list[str] = []
    model = Model(outputs)
    async with httpx.AsyncClient(transport=_source(seen, fail=fail)) as client:
        result = await evaluate_one(
            model, client, language=LANG, city=CITY, country=COUNTRY,
            menu_mode="state_ready",
            host_completion_feedback_budget=feedback,
        )
    return result, seen, model


@pytest.mark.asyncio
async def test_default_original_premature_final_remains_failed():
    result, seen, model = await _evaluate([GEO, WRONG, WEATHER, FINAL])
    assert seen == ["/v1/search"]
    assert model.position == 2
    assert result["termination_reason"] == "premature_final"
    assert result["generic_completion_feedback_sent"] == 0
    assert result["model_generated_two_step_complete"] is False
    assert result["full_task_complete"] is False


@pytest.mark.asyncio
async def test_one_generic_feedback_requires_model_generated_next_tool_and_final():
    result, seen, model = await _evaluate(
        [GEO, WRONG, WEATHER, FINAL], feedback=1,
    )
    assert seen == ["/v1/search", "/v1/forecast"]
    assert model.position == 4
    assert result["model_generated_two_step_complete"] is True
    assert result["strict_final_answer_correct"] is True
    assert result["full_task_complete"] is True
    assert result["generic_completion_feedback_sent"] == 1
    injected = model.history[2][-1]
    assert injected["role"] == "user"
    for withheld in (
        "open_meteo_weather", "latitude", "longitude", "37.56", "16.5",
        "source-secret", "gold", "expected route",
    ):
        assert withheld not in injected["content"].lower()


@pytest.mark.asyncio
async def test_second_premature_final_still_fails_without_host_call():
    result, seen, model = await _evaluate(
        [GEO, WRONG, WRONG, WEATHER], feedback=1,
    )
    assert seen == ["/v1/search"]
    assert model.position == 3
    assert result["full_task_complete"] is False
    assert result["termination_reason"] == "premature_final"
    assert result["generic_completion_feedback_sent"] == 1


@pytest.mark.asyncio
async def test_one_source_grounded_final_rewrite_requires_model_and_exact_fields():
    result, seen, model = await _evaluate(
        [GEO, WEATHER, WRONG, FINAL], feedback=1,
    )
    assert seen == ["/v1/search", "/v1/forecast"]
    assert model.position == 4
    assert result["generic_completion_feedback_sent"] == 1
    assert result["strict_final_answer_correct"] is True
    assert result["full_task_complete"] is True


@pytest.mark.asyncio
async def test_repeated_wrong_final_is_still_failure():
    result, seen, _ = await _evaluate(
        [GEO, WEATHER, WRONG, WRONG], feedback=1,
    )
    assert seen == ["/v1/search", "/v1/forecast"]
    assert result["generic_completion_feedback_sent"] == 1
    assert result["termination_reason"] == "incorrect_final_value_or_format"
    assert result["full_task_complete"] is False


@pytest.mark.asyncio
async def test_original_provider_denial_has_no_feedback_or_host_success():
    result, seen, _ = await _evaluate(
        [GEO, WRONG, WEATHER], feedback=1, fail=True,
    )
    assert seen == ["/v1/search"]
    assert result["generic_completion_feedback_sent"] == 0
    assert result["full_task_complete"] is False
    assert result["termination_reason"] == "host_or_native_source_denied"
    assert "PRIVATE_SOURCE_CANARY" not in json.dumps(result)


@pytest.mark.asyncio
@pytest.mark.parametrize("value", [2, -1, True, 0.5, None])
async def test_feedback_budget_is_strict_optin_boolean_is_not_one(value):
    agent = Model([GEO])
    async with httpx.AsyncClient(transport=_source([])) as client:
        with pytest.raises(ValueError, match="unregistered source task"):
            await evaluate_one(
                agent, client, language=LANG, city=CITY, country=COUNTRY,
                host_completion_feedback_budget=value,
            )
