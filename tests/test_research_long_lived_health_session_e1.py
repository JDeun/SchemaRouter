"""Longitudinal no-network proof: ONE provider-bound router across episodes."""
from __future__ import annotations

import asyncio
import json

import httpx
import pytest

from schemarouter import PrincipalContext
from scripts.research_live_health_model_menu_e1 import GEO, WEATHER
from scripts.research_long_lived_health_session_e1 import (
    LongLivedOpenMeteoHealthSessionE1,
)

ACTOR = PrincipalContext(subject="e1-host", roles=("reader",))
QUERY = "Public current weather in Seoul"


def _transport(state: dict[str, bool], counts: dict[str, int]):
    def handle(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/v1/search":
            counts["geo"] += 1
            if not state["geo_up"]:
                raise httpx.ConnectTimeout("PRIVATE_LOCATION_CANARY", request=request)
            return httpx.Response(200, json={"results": [{
                "id": 1835848, "country_code": "KR",
                "latitude": 37.56, "longitude": 126.98,
            }]})
        if request.url.path == "/v1/forecast":
            counts["weather"] += 1
            if not state["weather_up"]:
                raise httpx.ConnectTimeout("PRIVATE_WEATHER_CANARY", request=request)
            return httpx.Response(200, json={
                "current": {
                    "time": "2026-10-20T12:00",
                    "temperature_2m": 18.0,
                },
                "current_units": {"temperature_2m": "°C"},
            })
        raise AssertionError("unknown host-only route")
    return handle


async def _run(session: LongLivedOpenMeteoHealthSessionE1):
    return await session.get_current_weather(
        query=QUERY, city="Seoul", language="en", country="KR",
        principal=ACTOR,
    )


@pytest.mark.asyncio
async def test_one_router_persists_health_across_success_outage_and_recovery():
    state = {"geo_up": True, "weather_up": True,
             "geo_probe": True, "weather_probe": True}
    count = {"geo": 0, "weather": 0}

    async def probe_geo() -> bool:
        return state["geo_probe"]

    async def probe_weather() -> bool:
        return state["weather_probe"]

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(_transport(state, count)),
    ) as client:
        session = LongLivedOpenMeteoHealthSessionE1(
            client, trusted_health_probes={
                GEO: probe_geo, WEATHER: probe_weather,
            },
            probe_interval_seconds=5,
        )
        router_identity = id(session.router)
        async with session:
            first = await _run(session)
            assert first["status"] == "success"
            assert first["successful_native_calls"] == 2
            assert first["model_selected_routes"] is False
            assert first["health_monitor_running"] is True
            assert count == {"geo": 1, "weather": 1}
            assert id(session.router) == router_identity

            state["geo_probe"] = False
            state["geo_up"] = False
            await session.router.check_health_once()
            down = await _run(session)
            assert down["status"] == "temporary_unavailable"
            assert down["successful_native_calls"] == 0
            assert down["initial_model_visible_routes"] == 0
            assert count == {"geo": 1, "weather": 1}
            assert id(session.router) == router_identity

            state["geo_up"] = True
            state["geo_probe"] = True
            await session.router.check_health_once()
            recovered = await _run(session)
            assert recovered["status"] == "success"
            assert recovered["successful_native_calls"] == 2
            assert count == {"geo": 2, "weather": 2}
            assert id(session.router) == router_identity

            # Forecast outage is a separate endpoint; geocoding may still
            # execute, but forecast MUST be omitted at dependent disclosure.
            state["weather_probe"] = False
            state["weather_up"] = False
            await session.router.check_health_once()
            dependent_down = await _run(session)
            assert dependent_down["status"] == "temporary_unavailable"
            assert dependent_down["successful_native_calls"] == 1
            assert dependent_down["dependent_model_visible_routes"] == 0
            assert count == {"geo": 3, "weather": 2}

            state["weather_probe"] = True
            state["weather_up"] = True
            await session.router.check_health_once()
            last = await _run(session)
            assert last["status"] == "success"
            assert count == {"geo": 4, "weather": 3}
            for row in (first, down, recovered, dependent_down, last):
                encoded = json.dumps(row, sort_keys=True)
                assert "PRIVATE_" not in encoded
                assert "Seoul" not in encoded
                assert "37.56" not in encoded
                assert row["real_provider_success_qualified"] is False
                assert row["independent_e2_qualified"] is False
        assert session.router.health_monitor.running is False
        assert client.is_closed is False


@pytest.mark.asyncio
async def test_passive_transport_failure_is_remembered_between_host_requests():
    state = {"geo_up": True, "weather_up": True}
    count = {"geo": 0, "weather": 0}

    async def always_probes_true() -> bool:
        return True

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(_transport(state, count)),
    ) as client:
        session = LongLivedOpenMeteoHealthSessionE1(
            client, trusted_health_probes={
                GEO: always_probes_true, WEATHER: always_probes_true,
            }, probe_interval_seconds=5,
        )
        async with session:
            state["geo_up"] = False
            first = await _run(session)
            assert first["status"] == "temporary_unavailable"
            assert first["successful_native_calls"] == 0
            assert count["geo"] == 1
            hidden = await _run(session)
            assert hidden["status"] == "temporary_unavailable"
            assert count["geo"] == 1  # no re-execution while cooldown
            state["geo_up"] = True
            await session.router.check_health_once()
            assert (await _run(session))["status"] == "success"
            assert count == {"geo": 2, "weather": 1}


@pytest.mark.asyncio
async def test_no_host_approved_probes_never_turn_unknown_into_healthy():
    count = {"geo": 0, "weather": 0}
    state = {"geo_up": True, "weather_up": True}
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(_transport(state, count)),
    ) as client:
        session = LongLivedOpenMeteoHealthSessionE1(
            client, trusted_health_probes={},
        )
        async with session:
            for _ in range(3):
                result = await _run(session)
                assert result["status"] == "temporary_unavailable"
                assert result["successful_native_calls"] == 0
                assert result["initial_model_visible_routes"] == 0
            assert count == {"geo": 0, "weather": 0}


@pytest.mark.asyncio
async def test_finite_probe_window_recovers_after_active_monitor_observes_health():
    state = {"geo_up": True, "weather_up": True}
    count = {"geo": 0, "weather": 0}
    fresh = asyncio.Event()
    probe_ok = {"value": False}

    async def geo_probe() -> bool:
        if probe_ok["value"]:
            fresh.set()
            return True
        return False

    async def weather_probe() -> bool:
        return True

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(_transport(state, count)),
    ) as client:
        session = LongLivedOpenMeteoHealthSessionE1(
            client, trusted_health_probes={
                GEO: geo_probe, WEATHER: weather_probe,
            }, probe_interval_seconds=0.01,
        )
        async with session:
            assert (await _run(session))["status"] == "temporary_unavailable"
            probe_ok["value"] = True
            await asyncio.wait_for(fresh.wait(), timeout=1)
            for _ in range(20):
                if (await _run(session))["status"] == "success":
                    break
                await asyncio.sleep(0.01)
            assert count["geo"] == 1
            assert count["weather"] == 1


@pytest.mark.asyncio
async def test_invalid_or_closed_session_cannot_make_host_calls():
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda _: httpx.Response(500)),
    ) as client:
        session = LongLivedOpenMeteoHealthSessionE1(
            client, trusted_health_probes={},
        )
        with pytest.raises(RuntimeError):
            await _run(session)
        async with session:
            with pytest.raises(ValueError, match="trusted bounded host"):
                await session.get_current_weather(
                    query=QUERY, city="S", language="en", country="KR",
                    principal=ACTOR,
                )
        with pytest.raises(RuntimeError):
            await _run(session)
