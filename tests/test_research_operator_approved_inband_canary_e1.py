"""No-network actual-source in-band canary contract and fail-closed policy."""
from __future__ import annotations

import json

import httpx
import pytest

from scripts.research_operator_approved_inband_canary_e1 import (
    GEO,
    InBandCanaryCallbacksE1,
    observe_inband_canary_once,
)


def source_response(request: httpx.Request) -> httpx.Response:
    if request.url.host == "geocoding-api.open-meteo.com":
        assert request.url.path == "/v1/search"
        assert request.url.params["name"] == "Seoul"
        assert request.url.params["countryCode"] == "KR"
        return httpx.Response(200, json={"results": [{
            "id": 1835848, "country_code": "KR",
            "latitude": 37.5665, "longitude": 126.978,
        }]})
    if request.url.host == "api.open-meteo.com":
        assert request.url.path == "/v1/forecast"
        assert request.url.params["current"] == "temperature_2m"
        return httpx.Response(200, json={
            "current": {"time": "2026-10-20T18:00", "temperature_2m": 17.3},
            "current_units": {"temperature_2m": "°C"},
        })
    raise AssertionError("unapproved external source reached")


@pytest.mark.asyncio
async def test_actual_background_monitor_inband_receipts_and_two_native_calls():
    seen = []

    def observe(request: httpx.Request) -> httpx.Response:
        seen.append(request.url.host)
        return source_response(request)

    receipt = await observe_inband_canary_once(
        approved_public_business_canaries=True,
        transport_factory=lambda: httpx.MockTransport(observe),
    )
    assert receipt["status"] == "success"
    assert receipt["observed_native_calls_completed"] == 2
    assert receipt["actual_https_get_attempts"] == 4
    assert receipt["actual_inband_canary_attempts_by_endpoint"] == {
        "geocoding": 1, "forecast": 1,
    }
    assert receipt["actual_get_attempts_by_endpoint"] == {
        "geocoding": 2, "forecast": 2,
    }
    assert sorted(seen) == sorted([
        "geocoding-api.open-meteo.com",
        "api.open-meteo.com",
        "geocoding-api.open-meteo.com",
        "api.open-meteo.com",
    ])
    for key in (
        "independent_dedicated_health_endpoint_verified",
        "long_term_availability_verified",
        "model_selected_routes",
        "independent_e2_qualified",
        "production_default_changed",
    ):
        assert receipt[key] is False
    assert receipt["model_generations"] == 0
    assert receipt["canary_uses_actual_business_endpoint"] is True
    data = json.dumps(receipt, ensure_ascii=False)
    for forbidden in (
        "Seoul", "37.5665", "126.978", "17.3", "results", "PRIVATE",
        "https://",
    ):
        assert forbidden not in data


@pytest.mark.asyncio
async def test_real_canary_timeout_blocks_native_business_calls_without_retry():
    seen = []

    def timeout(request: httpx.Request) -> httpx.Response:
        seen.append(request.url.host)
        if request.url.host == "geocoding-api.open-meteo.com":
            raise httpx.ConnectTimeout("PRIVATE_CANARY_NET_ERROR", request=request)
        return source_response(request)

    receipt = await observe_inband_canary_once(
        approved_public_business_canaries=True,
        transport_factory=lambda: httpx.MockTransport(timeout),
    )
    assert receipt["status"] == "inband_canary_unhealthy"
    assert receipt["observed_native_calls_completed"] == 0
    assert receipt["actual_https_get_attempts"] == 2
    assert receipt["actual_inband_canary_attempts_by_endpoint"] == {
        "geocoding": 1, "forecast": 1,
    }
    assert len(seen) == 2
    assert "PRIVATE_" not in json.dumps(receipt)


@pytest.mark.asyncio
async def test_forecast_canary_500_is_not_interpreted_as_healthy():
    def error(request: httpx.Request) -> httpx.Response:
        if request.url.host == "api.open-meteo.com":
            return httpx.Response(503, json={"reason": "PRIVATE_REMOTE_FAILURE"})
        return source_response(request)

    receipt = await observe_inband_canary_once(
        approved_public_business_canaries=True,
        transport_factory=lambda: httpx.MockTransport(error),
    )
    assert receipt["status"] == "inband_canary_unhealthy"
    assert receipt["observed_native_calls_completed"] == 0
    assert receipt["actual_https_get_attempts"] == 2
    assert "PRIVATE_" not in json.dumps(receipt)


@pytest.mark.asyncio
async def test_malformed_geocoder_canary_response_is_not_healthy():
    def malformed(request: httpx.Request) -> httpx.Response:
        if request.url.host == "geocoding-api.open-meteo.com":
            return httpx.Response(200, json={"results": []})
        return source_response(request)

    receipt = await observe_inband_canary_once(
        approved_public_business_canaries=True,
        transport_factory=lambda: httpx.MockTransport(malformed),
    )
    assert receipt["status"] == "inband_canary_unhealthy"
    assert receipt["observed_native_calls_completed"] == 0


@pytest.mark.asyncio
async def test_no_approval_cannot_create_outbound_requests():
    seen = []

    def response(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return source_response(request)

    with pytest.raises(ValueError, match="permission"):
        await observe_inband_canary_once(
            approved_public_business_canaries=False,
            transport_factory=lambda: httpx.MockTransport(response),
        )
    assert seen == []


@pytest.mark.asyncio
async def test_exhausted_probe_budget_fails_closed_never_recycles_healthy():
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(source_response),
    ) as client:
        probes = InBandCanaryCallbacksE1(
            client, approved_public_business_canaries=True, attempts_per_route=1,
        )
        assert await probes.geocoding() is True
        assert await probes.geocoding() is False
        assert probes.counts[GEO] == 1


@pytest.mark.parametrize("invalid", (0, 3, -1, True, 1.2))
def test_canary_per_route_budget_is_explicit_and_finite(invalid):
    with pytest.raises(ValueError, match="per-route"):
        InBandCanaryCallbacksE1(
            httpx.AsyncClient(transport=httpx.MockTransport(source_response)),
            approved_public_business_canaries=True,
            attempts_per_route=invalid,
        )


@pytest.mark.asyncio
async def test_invalid_canary_approval_rejected_even_with_good_source():
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(source_response),
    ) as client:
        with pytest.raises(ValueError, match="permission"):
            InBandCanaryCallbacksE1(
                client, approved_public_business_canaries=False,
            )
