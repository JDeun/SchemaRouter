"""No-network controls for explicit capped real-provider observation E1."""
from __future__ import annotations

import json

import httpx
import pytest

from scripts.research_long_lived_real_open_meteo_e1 import (
    CappedOpenMeteoTransport,
    observe_real_source_once,
)


def _good(request: httpx.Request) -> httpx.Response:
    if request.url.path == "/v1/search":
        return httpx.Response(200, json={"results": [{
            "id": 1835848, "country_code": "KR"
            if request.url.params.get("countryCode") == "KR" else "JP",
            "latitude": 37.56, "longitude": 126.98,
        }]})
    if request.url.path == "/v1/forecast":
        return httpx.Response(200, json={
            "current": {"time": "2026-10-20T12:00", "temperature_2m": 18},
            "current_units": {"temperature_2m": "°C"},
        })
    raise AssertionError("disallowed request unexpectedly got to underlying HTTP transport")


@pytest.mark.asyncio
async def test_explicit_six_read_only_provider_gets_same_router_three_languages():
    output = await observe_real_source_once(
        acknowledged_readonly_business_requests=True,
        transport_factory=lambda: httpx.MockTransport(_good),
    )
    assert output["languages"] == ["en", "ko", "ja"]
    assert output["shared_router_across_episodes"] is True
    assert output["total_provider_http_get_attempts"] == 6
    assert output["provider_requests_by_source"] == {
        "geocoding": 3, "forecast": 3,
    }
    assert all(
        row["status"] == "success" and row["native_calls_successful"] == 2
        for row in output["results"].values()
    )
    assert output["health_probes_are_simulated"] is True
    assert output["per_endpoint_health_independently_verified"] is False
    assert output["external_provider_success_qualified"] is False
    assert output["independent_e2_qualified"] is False
    assert output["llm_generations"] == 0
    assert output["model_selected_routes"] is False
    assert output["observation_transport"] == "injected_test_transport"
    assert output["transport_timeout_attempts"] == 0
    assert output["host_deadline_episodes"] == 0
    assert output["temporary_unavailable_episodes"] == 0
    assert output["observed_two_hop_success_episodes"] == 3
    assert output["fallbacks_attempted"] == 0
    assert set(output["simulated_probe_attempts_by_route"]) == {
        "geocoding", "forecast",
    }
    assert all(
        count >= 1 for count in output["simulated_probe_attempts_by_route"].values()
    )
    assert all(
        row["initial_model_visible_routes"] == 1
        and row["dependent_model_visible_routes"] == 1
        for row in output["results"].values()
    )
    assert output["production_default_changed"] is False
    trace = json.dumps(output, ensure_ascii=False)
    assert "Seoul" not in trace
    assert "Tokyo" not in trace
    assert "37.56" not in trace
    assert "temperature_2m" not in trace


@pytest.mark.asyncio
async def test_first_geocoder_transport_timeout_blocks_following_model_menus():
    attempts = {"count": 0}

    def fail_first_geocode(request: httpx.Request) -> httpx.Response:
        attempts["count"] += 1
        if request.url.path == "/v1/search":
            raise httpx.ConnectTimeout("PRIVATE_NETWORK_URL_CANARY", request=request)
        return _good(request)

    result = await observe_real_source_once(
        acknowledged_readonly_business_requests=True,
        transport_factory=lambda: httpx.MockTransport(fail_first_geocode),
    )
    assert result["total_provider_http_get_attempts"] == 1
    assert result["provider_requests_by_source"] == {
        "geocoding": 1, "forecast": 0,
    }
    assert result["results"]["en"]["status"] == "temporary_unavailable"
    assert result["results"]["ko"]["status"] == "temporary_unavailable"
    assert result["results"]["ja"]["status"] == "temporary_unavailable"
    assert all(
        row["native_calls_successful"] == 0
        for row in result["results"].values()
    )
    assert attempts["count"] == 1
    assert result["transport_timeout_attempts"] == 1
    assert result["temporary_unavailable_episodes"] == 3
    assert result["observed_two_hop_success_episodes"] == 0
    assert result["fallbacks_attempted"] == 0
    assert "PRIVATE_" not in json.dumps(result)


@pytest.mark.asyncio
async def test_live_provider_gets_require_explicit_user_or_operator_acknowledgement():
    requests = {"count": 0}

    def explode(request: httpx.Request) -> httpx.Response:
        requests["count"] += 1
        raise AssertionError("not approved")

    with pytest.raises(ValueError, match="operator acknowledgement"):
        await observe_real_source_once(
            acknowledged_readonly_business_requests=False,
            transport_factory=lambda: httpx.MockTransport(explode),
        )
    assert requests["count"] == 0


@pytest.mark.asyncio
async def test_unsupported_external_host_post_or_redirect_is_rejected():
    submitted = {"count": 0}

    def raw_backend(request: httpx.Request) -> httpx.Response:
        submitted["count"] += 1
        return httpx.Response(200)

    transport = CappedOpenMeteoTransport(
        httpx.MockTransport(raw_backend), max_requests=2,
    )
    for method, url in (
        ("POST", "https://api.open-meteo.com/v1/forecast"),
        ("GET", "https://unexpected.example.org/v1/search"),
        ("GET", "http://geocoding-api.open-meteo.com/v1/search"),
        ("GET", "https://api.open-meteo.com/admin"),
        ("GET", "https://api.open-meteo.com:8443/v1/forecast"),
    ):
        with pytest.raises(RuntimeError, match="disallowed"):
            await transport.handle_async_request(httpx.Request(method, url))
    assert submitted["count"] == 0
    assert transport.total_requests == 0
    await transport.aclose()


@pytest.mark.asyncio
async def test_provider_request_cap_is_hard_stop_before_delegate():
    counter = {"requests": 0}

    def under(request: httpx.Request) -> httpx.Response:
        counter["requests"] += 1
        return httpx.Response(200)

    transport = CappedOpenMeteoTransport(
        httpx.MockTransport(under), max_requests=1,
    )
    req = httpx.Request(
        "GET",
        "https://geocoding-api.open-meteo.com/v1/search"
        "?name=Seoul&language=en&countryCode=KR&count=10&format=json",
    )
    await transport.handle_async_request(req)
    with pytest.raises(RuntimeError, match="budget exhausted"):
        await transport.handle_async_request(req)
    assert transport.total_requests == counter["requests"] == 1
    assert transport.transport_timeout_attempts == 0
    await transport.aclose()


@pytest.mark.asyncio
async def test_no_unknown_or_duplicate_query_or_embedded_credentials_forwarded():
    counter = {"sent": 0}

    def delegate(request: httpx.Request) -> httpx.Response:
        counter["sent"] += 1
        return httpx.Response(200)

    transport = CappedOpenMeteoTransport(
        httpx.MockTransport(delegate), max_requests=3,
    )
    base = (
        "https://geocoding-api.open-meteo.com/v1/search?"
        "name=Seoul&language=en&countryCode=KR&count=10&format=json"
    )
    bad = (
        base + "&apikey=PRIVATE_API_KEY_CANARY",
        base + "&name=OtherCity",
        base.replace("https://", "https://user:secret@"),
        base.replace("&language=en", ""),
    )
    for url in bad:
        with pytest.raises(RuntimeError, match="disallowed"):
            await transport.handle_async_request(httpx.Request("GET", url))
    assert counter["sent"] == 0
    assert transport.total_requests == 0
    await transport.aclose()


@pytest.mark.parametrize("invalid", (0, -1, 7, True, 1.5))
def test_invalid_provider_request_budget_is_rejected(invalid):
    with pytest.raises(ValueError, match="maximum live GET"):
        CappedOpenMeteoTransport(
            httpx.MockTransport(_good), max_requests=invalid,
        )


@pytest.mark.asyncio
async def test_invalid_observation_deadline_rejected_without_gets():
    for budget in (0, -1, 25, True):
        with pytest.raises(ValueError, match="bounded observation"):
            await observe_real_source_once(
                acknowledged_readonly_business_requests=True,
                transport_factory=lambda: httpx.MockTransport(_good),
                max_request_seconds=budget,
            )
