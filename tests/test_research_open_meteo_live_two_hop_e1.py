"""Offline request/response contracts for live Open-Meteo two-hop harness."""
from __future__ import annotations

import json

import httpx
import pytest

from scripts.research_open_meteo_live_two_hop_e1 import (
    _forecast_response,
    _geocode_response,
    _plan,
    build_live_router,
    run,
)


@pytest.mark.asyncio
async def test_live_api_route_and_second_call_use_actual_first_output() -> None:
    requests: list[tuple[str, dict[str, str]]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        params = dict(request.url.params)
        requests.append((request.url.host or "", params))
        if request.url.host == "geocoding-api.open-meteo.com":
            assert request.url.path == "/v1/search"
            assert params["countryCode"] in ("KR", "JP")
            assert params["count"] == "1"
            country = params["countryCode"]
            latitude, longitude, identifier = (
                (37.56, 126.98, 1835848) if country == "KR"
                else (35.68, 139.69, 1850147)
            )
            return httpx.Response(200, json={"results": [{
                "id": identifier, "country_code": country,
                "latitude": latitude, "longitude": longitude,
            }]})
        if request.url.host == "api.open-meteo.com":
            assert request.url.path == "/v1/forecast"
            assert params["current"] == "temperature_2m"
            assert params["timezone"] == "auto"
            latitude = float(params["latitude"])
            longitude = float(params["longitude"])
            assert (latitude, longitude) in {
                (37.56, 126.98), (35.68, 139.69),
            }
            return httpx.Response(200, json={
                "current": {
                    "time": "2026-10-18T10:00",
                    "temperature_2m": 16.5,
                },
                "current_units": {"temperature_2m": "°C"},
            })
        raise AssertionError("unapproved endpoint reached")

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await run(client)
    assert [case["language_label"] for case in result["cases"]] == [
        "en", "ko", "ja",
    ]
    assert result["source_http_calls"] == {"geocoding": 3, "forecast": 3}
    assert len(requests) == 6
    for i in range(0, 6, 2):
        assert requests[i][0] == "geocoding-api.open-meteo.com"
        assert requests[i + 1][0] == "api.open-meteo.com"
    assert all(x["two_real_source_calls_completed"] for x in result["cases"])
    assert result["real_agent_final_answer_pass"] is False
    assert result["independent_private_e2"] is False
    assert "temperature_2m" not in json.dumps(result)


@pytest.mark.parametrize("response,country", [
    ({"results": []}, "KR"),
    ({"results": [{"id": 123, "country_code": "JP",
                  "latitude": 37.0, "longitude": 127.0}]}, "KR"),
    ({"results": [{"id": 123, "country_code": "KR",
                  "latitude": float("nan"), "longitude": 127.0}]}, "KR"),
    ({"results": [{"id": 123, "country_code": "KR",
                  "latitude": 190.0, "longitude": 127.0}]}, "KR"),
])
def test_live_geocode_invalid_data_fails_closed(
    response: dict, country: str,
) -> None:
    with pytest.raises(ValueError):
        _geocode_response(response, country)


@pytest.mark.parametrize("response", [
    {"current": {"time": "2026-10-18T10:00", "temperature_2m": 14}},
    {"current": {"time": "2026-10-18T10:00", "temperature_2m": 14},
     "current_units": {"temperature_2m": "°F"}},
    {"current": {"time": "2026-10-18T10:00",
                 "temperature_2m": float("inf")},
     "current_units": {"temperature_2m": "°C"}},
])
def test_live_weather_invalid_unit_and_measurement_fail_closed(
    response: dict,
) -> None:
    with pytest.raises(ValueError):
        _forecast_response(response)


@pytest.mark.asyncio
async def test_missing_city_argument_does_not_call_network() -> None:
    def block(_: httpx.Request) -> httpx.Response:
        raise AssertionError("input schema should reject before network")

    async with httpx.AsyncClient(transport=httpx.MockTransport(block)) as client:
        router, geo, weather = build_live_router(client)
        incomplete = _plan(
            router, "weather Seoul",
            tool_name="open_meteo_geocoding",
            endpoint_name="search",
            args={"country_code": "KR"},
            fields=["location_id", "latitude", "longitude", "country_code"],
        )
        with pytest.raises(Exception):
            await router.execute(incomplete)
        assert geo.calls == 0 and weather.calls == 0


@pytest.mark.asyncio
async def test_wrong_source_response_country_blocks_second_live_call() -> None:
    requests = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request.url.host)
        return httpx.Response(200, json={"results": [{
            "id": 1, "country_code": "JP",
            "latitude": 37.0, "longitude": 127.0,
        }]})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        router, geo, weather = build_live_router(client)
        from scripts.research_open_meteo_live_two_hop_e1 import live_task
        with pytest.raises(ValueError, match="wrong country"):
            await live_task(router, "ko", "서울", "KR")
        assert requests == ["geocoding-api.open-meteo.com"]
        assert geo.calls == 0 and weather.calls == 0
