"""Deterministic offline two periodic monitor cycles, no live provider call."""
from __future__ import annotations

import json

import httpx
import pytest

from scripts.research_finite_inband_watchdog_recovery_e1 import (
    observe_finite_background_recovery,
)


def _healthy(request: httpx.Request) -> httpx.Response:
    if request.url.host == "geocoding-api.open-meteo.com":
        return httpx.Response(200, json={"results": [{
            "id": 1, "country_code": "KR",
            "latitude": 37.5665, "longitude": 126.978,
        }]})
    if request.url.host == "api.open-meteo.com":
        return httpx.Response(200, json={
            "current": {"time": "2026-10-20T18:00", "temperature_2m": 18.0},
            "current_units": {"temperature_2m": "°C"},
        })
    raise AssertionError("unknown remote provider")


@pytest.mark.asyncio
async def test_background_watchdog_detects_then_recovers_from_canary_timeout():
    received = {"geo": 0}

    def transport(request: httpx.Request) -> httpx.Response:
        if request.url.host == "geocoding-api.open-meteo.com":
            received["geo"] += 1
            if received["geo"] == 1:
                raise httpx.ConnectTimeout(
                    "PRIVATE_PROVIDER_EXCEPTION_CANARY", request=request,
                )
        return _healthy(request)

    report = await observe_finite_background_recovery(
        lambda: httpx.MockTransport(transport),
        operator_approved=True,
        interval_seconds=0.35,
    )
    assert report["observations"] == [
        {
            "health": "unhealthy",
            "visible_geocoder": False,
            "menu_status": "temporary_unavailable",
        },
        {
            "health": "healthy",
            "visible_geocoder": True,
            "menu_status": "ready",
        },
    ]
    assert report["inband_get_attempts"] == 4
    assert report["probe_attempts"] == {"geocoding": 2, "forecast": 2}
    assert received["geo"] == 2
    for key in (
        "external_network_qualified",
        "continuous_production_monitoring_qualified",
        "model_selected_routes",
        "independent_e2_qualified",
        "production_default_changed",
    ):
        assert report[key] is False
    serialized = json.dumps(report)
    assert "PRIVATE_" not in serialized
    assert "Seoul" not in serialized
    assert "37.5665" not in serialized
    assert "https://" not in serialized


@pytest.mark.asyncio
async def test_false_operator_approval_aborts_before_transport_instantiation():
    def no_factory() -> httpx.AsyncBaseTransport:
        raise AssertionError("must not construct transport without approval")

    with pytest.raises(ValueError, match="permission"):
        await observe_finite_background_recovery(
            no_factory, operator_approved=False,
        )


@pytest.mark.asyncio
@pytest.mark.parametrize("bad", (0, -1, True, float("nan"), 5.0))
async def test_invalid_monitor_interval_rejected_before_transport(bad):
    def no_factory() -> httpx.AsyncBaseTransport:
        raise AssertionError("invalid configuration must not reach transport")

    with pytest.raises(ValueError, match="bounded interval"):
        await observe_finite_background_recovery(
            no_factory, operator_approved=True, interval_seconds=bad,
        )
