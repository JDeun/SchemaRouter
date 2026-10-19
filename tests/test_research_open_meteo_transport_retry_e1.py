"""Read-only Open-Meteo transport retry E1: no actual model/provider evidence."""
from __future__ import annotations

import json

import httpx
import pytest

from scripts.research_real_qwen_open_meteo_two_hop_e1 import evaluate_one

CITY, LANGUAGE, COUNTRY = "Seoul", "en", "KR"
LAT, LON = 37.56, 126.98


def _call(route: str, arguments: dict) -> str:
    return "<tool_call>\n" + json.dumps({
        "name": route.replace(".", "__", 1), "arguments": arguments,
    }) + "\n</tool_call>"


GEO = _call("open_meteo_geocoding.search", {
    "name": CITY, "language": LANGUAGE, "country_code": COUNTRY,
})
WEATHER = _call("open_meteo_weather.current", {
    "latitude": LAT, "longitude": LON,
})
FINAL = json.dumps({
    "temperature_2m": 16.5,
    "unit": "°C",
    "observed_at": "2026-10-18T10:00",
})


class Agent:
    def __init__(self) -> None:
        self.index = 0

    def generate(self, messages, tools):
        outputs = [GEO, WEATHER, FINAL]
        result = outputs[self.index]
        self.index += 1
        return {"text": result, "latency_ms": 0.0, "context_overflow": False}


def _provider(
    requested: list[str], *, fail_geocode_once=False,
    fail_all=False, wrong_country=False, invalid_payload=False,
):
    def respond(request: httpx.Request) -> httpx.Response:
        requested.append(request.url.path)
        if fail_all or fail_geocode_once and len(requested) == 1:
            raise httpx.ConnectError("PRIVATE_CONNECT_FAILURE_CANARY", request=request)
        if request.url.path == "/v1/search":
            return httpx.Response(200, json={
                "results": [{
                    "id": 1835848,
                    "country_code": "JP" if wrong_country else "KR",
                    "latitude": LAT, "longitude": LON,
                }] if not invalid_payload else [],
            })
        if request.url.path == "/v1/forecast":
            return httpx.Response(200, json={
                "current": {
                    "time": "2026-10-18T10:00", "temperature_2m": 16.5,
                },
                "current_units": {"temperature_2m": "°C"},
            })
        raise AssertionError("unexpected provider route")

    return httpx.MockTransport(respond)


@pytest.mark.asyncio
async def test_one_failed_get_then_real_validated_retry_completes_strict_two_hop():
    requested: list[str] = []
    async with httpx.AsyncClient(
        transport=_provider(requested, fail_geocode_once=True),
        follow_redirects=False,
    ) as client:
        row = await evaluate_one(
            Agent(), client, language=LANGUAGE, city=CITY, country=COUNTRY,
            menu_mode="state_ready", transport_retry_budget=1,
        )
    assert requested == ["/v1/search", "/v1/search", "/v1/forecast"]
    assert row["real_geocoding_http_attempts"] == 2
    assert row["real_forecast_http_attempts"] == 1
    assert row["real_geocoding_calls"] == 1
    assert row["real_forecast_calls"] == 1
    assert row["strict_final_answer_correct"] is True
    assert row["full_task_complete"] is True
    assert row["independent_e2_qualified"] is False


@pytest.mark.asyncio
async def test_default_no_retry_and_failure_remains_failed():
    requested: list[str] = []
    async with httpx.AsyncClient(
        transport=_provider(requested, fail_geocode_once=True),
    ) as client:
        row = await evaluate_one(
            Agent(), client, language=LANGUAGE, city=CITY, country=COUNTRY,
        )
    assert requested == ["/v1/search"]
    assert row["real_geocoding_http_attempts"] == 1
    assert row["real_geocoding_calls"] == 0
    assert row["full_task_complete"] is False
    assert row["trusted_failure_stage"] == "geocode_http_transport_failure"
    assert "PRIVATE_CONNECT_FAILURE_CANARY" not in json.dumps(row)


@pytest.mark.asyncio
async def test_no_false_source_validation_when_both_transport_attempts_fail():
    requested: list[str] = []
    async with httpx.AsyncClient(
        transport=_provider(requested, fail_all=True),
    ) as client:
        row = await evaluate_one(
            Agent(), client, language=LANGUAGE, city=CITY, country=COUNTRY,
            transport_retry_budget=1,
        )
    assert requested == ["/v1/search", "/v1/search"]
    assert row["real_geocoding_http_attempts"] == 2
    assert row["real_geocoding_calls"] == 0
    assert row["model_generated_first_step_complete"] is False
    assert row["full_task_complete"] is False
    assert row["termination_reason"] == "host_or_native_source_denied"
    assert "PRIVATE_CONNECT_FAILURE_CANARY" not in json.dumps(row)


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["wrong_country", "invalid_payload"])
async def test_invalid_responded_json_or_country_does_not_trigger_transport_retry(kind):
    requested: list[str] = []
    async with httpx.AsyncClient(
        transport=_provider(requested, **{kind: True}),
    ) as client:
        row = await evaluate_one(
            Agent(), client, language=LANGUAGE, city=CITY, country=COUNTRY,
            transport_retry_budget=1,
        )
    assert requested == ["/v1/search"]
    assert row["real_geocoding_http_attempts"] == 1
    assert row["real_geocoding_calls"] == 0
    assert row["real_forecast_http_attempts"] == 0
    assert row["full_task_complete"] is False


@pytest.mark.asyncio
@pytest.mark.parametrize("invalid", [-1, 2, True, 0.0, None])
async def test_only_exact_integer_zero_or_one_read_retry_budget(invalid):
    async with httpx.AsyncClient(transport=_provider([])) as client:
        with pytest.raises(ValueError, match="unregistered source task"):
            await evaluate_one(
                Agent(), client, language=LANGUAGE, city=CITY, country=COUNTRY,
                transport_retry_budget=invalid,
            )


@pytest.mark.asyncio
@pytest.mark.parametrize("error_type,expected", (
    (httpx.ConnectTimeout, "connect_timeout"),
    (httpx.ReadTimeout, "read_timeout"),
    (httpx.PoolTimeout, "pool_timeout"),
    (httpx.ConnectError, "connect_error"),
    (httpx.ReadError, "read_error"),
    (httpx.RemoteProtocolError, "remote_protocol_error"),
))
async def test_original_transport_exception_class_is_safe_coarse_diagnostic(
    error_type, expected,
):
    requests: list[str] = []

    def fail(req: httpx.Request) -> httpx.Response:
        requests.append(req.url.path)
        raise error_type("PRIVATE_URL_TOKEN_COORDINATE_CANARY", request=req)

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(fail), follow_redirects=False,
    ) as client:
        row = await evaluate_one(
            Agent(), client, language=LANGUAGE, city=CITY, country=COUNTRY,
            transport_retry_budget=1,
        )
    assert requests == ["/v1/search", "/v1/search"]
    assert row["trusted_failure_stage"] == "geocode_http_transport_failure"
    assert row["trusted_transport_error_kind"] == expected
    assert row["full_task_complete"] is False
    assert row["real_geocoding_http_attempts"] == 2
    assert "PRIVATE_URL_TOKEN_COORDINATE_CANARY" not in json.dumps(row)


@pytest.mark.asyncio
async def test_transient_failure_kind_clears_on_actual_verified_source_success():
    requests: list[str] = []
    async with httpx.AsyncClient(
        transport=_provider(requests, fail_geocode_once=True),
    ) as client:
        row = await evaluate_one(
            Agent(), client, language=LANGUAGE, city=CITY, country=COUNTRY,
            transport_retry_budget=1,
        )
    assert row["full_task_complete"] is True
    assert row["trusted_failure_stage"] is None
    assert row["trusted_transport_error_kind"] is None
