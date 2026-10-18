"""E1 state-ready native schema menus; mock agents are NOT model evidence."""
from __future__ import annotations

import json
from typing import Any

import httpx
import pytest

from schemarouter import PolicyViolationError
from scripts.research_authorized_agent_tool_surface import (
    capture_authorized_agent_tool_surface,
)
from scripts.research_open_meteo_live_two_hop_e1 import build_live_router
from scripts.research_real_qwen_open_meteo_two_hop_e1 import (
    PRINCIPAL,
    USER_REQUESTS,
    evaluate_one,
)
from scripts.research_source_ready_native_tool_menu_e1 import (
    source_ready_visible_routes,
)

CITY, LANG, COUNTRY = "Seoul", "en", "KR"
LAT, LON = 37.56, 126.98
GEO, WEATHER = "open_meteo_geocoding.search", "open_meteo_weather.current"


def _model_call(route: str, args: dict[str, Any]) -> str:
    return "<tool_call>\n" + json.dumps({
        "name": route.replace(".", "__", 1),
        "arguments": args,
    }) + "\n</tool_call>"


GEO_CALL = _model_call(
    GEO, {"name": CITY, "country_code": COUNTRY, "language": LANG},
)
WEATHER_CALL = _model_call(WEATHER, {"latitude": LAT, "longitude": LON})
FINAL = json.dumps({
    "temperature_2m": 16.5, "unit": "°C",
    "observed_at": "2026-10-18T10:00",
})


class SpyAgent:
    def __init__(self, outputs: list[str]) -> None:
        self.outputs = outputs
        self.menus: list[tuple[str, ...]] = []
        self.calls = 0

    def generate(
        self, messages: list[dict[str, str]],
        tools: list[dict[str, Any]],
    ) -> dict[str, Any]:
        self.menus.append(tuple(x["name"] for x in tools))
        index = self.calls
        self.calls += 1
        return {
            "text": self.outputs[min(index, len(self.outputs) - 1)],
            "context_overflow": False, "latency_ms": 0.0,
        }


def _transport(seen: list[str]) -> httpx.MockTransport:
    def handler(req: httpx.Request) -> httpx.Response:
        seen.append(req.url.path)
        if req.url.path == "/v1/search":
            return httpx.Response(200, json={"results": [{
                "id": 1835848, "country_code": "KR",
                "latitude": LAT, "longitude": LON,
            }]})
        if req.url.path == "/v1/forecast":
            assert float(req.url.params["latitude"]) == LAT
            assert float(req.url.params["longitude"]) == LON
            return httpx.Response(200, json={
                "current": {"time": "2026-10-18T10:00", "temperature_2m": 16.5},
                "current_units": {"temperature_2m": "°C"},
            })
        raise AssertionError("unexpected source URL")

    return httpx.MockTransport(handler)


@pytest.mark.asyncio
async def test_source_ready_real_native_contracts_only_current_input_available():
    seen: list[str] = []
    async with httpx.AsyncClient(transport=_transport(seen)) as client:
        router, _, _ = build_live_router(client)
        view = capture_authorized_agent_tool_surface(
            router, USER_REQUESTS[LANG], principal=PRINCIPAL,
        )
        host = {"name": CITY, "language": LANG, "country_code": COUNTRY}
        assert source_ready_visible_routes(
            view, host_request_inputs=host,
            prior_public_observation=None, executed_route_ids=(),
        ) == (GEO,)
        assert source_ready_visible_routes(
            view, host_request_inputs=host,
            prior_public_observation={
                "status": "ok", "latitude": LAT, "longitude": LON,
            }, executed_route_ids=(GEO,),
        ) == (WEATHER,)
        assert source_ready_visible_routes(
            view, host_request_inputs=host,
            prior_public_observation={"status": "ok", "latitude": LAT},
            executed_route_ids=(GEO,),
        ) == ()
        assert source_ready_visible_routes(
            view, host_request_inputs=host,
            prior_public_observation={
                "status": "ok", "latitude": LAT, "longitude": LON,
            }, executed_route_ids=(GEO, WEATHER),
        ) == ()
        assert not seen


@pytest.mark.asyncio
async def test_complete_true_two_step_model_proposals_and_strict_source_final():
    calls: list[str] = []
    agent = SpyAgent([GEO_CALL, WEATHER_CALL, FINAL])
    async with httpx.AsyncClient(transport=_transport(calls)) as client:
        row = await evaluate_one(
            agent, client, language=LANG, city=CITY,
            country=COUNTRY, menu_mode="state_ready",
        )
    assert calls == ["/v1/search", "/v1/forecast"]
    assert agent.menus == [
        ("open_meteo_geocoding__search",),
        ("open_meteo_weather__current",),
        (),
    ]
    assert row["full_task_complete"] is True
    assert row["real_geocoding_calls"] == 1
    assert row["real_forecast_calls"] == 1
    assert row["independent_e2_qualified"] is False


@pytest.mark.asyncio
async def test_wrong_future_tool_cannot_execute_when_not_currently_offered():
    calls: list[str] = []
    agent = SpyAgent([WEATHER_CALL])
    async with httpx.AsyncClient(transport=_transport(calls)) as client:
        result = await evaluate_one(
            agent, client, language=LANG, city=CITY,
            country=COUNTRY, menu_mode="state_ready",
        )
    assert result["full_task_complete"] is False
    assert result["real_geocoding_http_attempts"] == 0
    assert result["real_forecast_http_attempts"] == 0
    assert calls == []
    assert agent.menus == [("open_meteo_geocoding__search",)]


@pytest.mark.asyncio
async def test_premature_final_is_not_host_rescued_or_scored_success():
    calls: list[str] = []
    agent = SpyAgent([GEO_CALL, FINAL])
    async with httpx.AsyncClient(transport=_transport(calls)) as client:
        row = await evaluate_one(
            agent, client, language=LANG, city=CITY,
            country=COUNTRY, menu_mode="state_ready",
        )
    assert calls == ["/v1/search"]
    assert row["termination_reason"] == "premature_final"
    assert row["full_task_complete"] is False
    assert row["real_forecast_calls"] == 0


@pytest.mark.asyncio
async def test_default_original_two_tool_menu_unchanged():
    calls: list[str] = []
    agent = SpyAgent([GEO_CALL, WEATHER_CALL, FINAL])
    async with httpx.AsyncClient(transport=_transport(calls)) as client:
        row = await evaluate_one(
            agent, client, language=LANG, city=CITY, country=COUNTRY,
        )
    assert calls == ["/v1/search", "/v1/forecast"]
    assert row["full_task_complete"] is True
    assert agent.menus == [
        ("open_meteo_geocoding__search", "open_meteo_weather__current"),
    ] * 3


@pytest.mark.asyncio
async def test_untrusted_source_state_or_wrong_authority_fails_closed():
    async with httpx.AsyncClient(transport=_transport([])) as client:
        router, _, _ = build_live_router(client)
        view = capture_authorized_agent_tool_surface(
            router, USER_REQUESTS[LANG], principal=PRINCIPAL,
        )
        for bad in (
            {"status": "failed", "latitude": LAT, "longitude": LON},
            {"status": "ok", "latitude": float("nan"), "longitude": LON},
            {"status": "ok", "private": {"token": "canary"}},
        ):
            with pytest.raises(ValueError, match="untrusted"):
                source_ready_visible_routes(
                    view, host_request_inputs={
                        "name": CITY, "country_code": COUNTRY, "language": LANG,
                    },
                    prior_public_observation=bad, executed_route_ids=(GEO,),
                )
        with pytest.raises(PolicyViolationError, match="executed route absent"):
            source_ready_visible_routes(
                view, host_request_inputs={"name": CITY},
                prior_public_observation=None,
                executed_route_ids=("hidden.operation",),
            )
