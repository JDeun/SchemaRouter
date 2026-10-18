"""Deterministic *model-stub* checks for actual bound-provider agent path.

These are E0 synthetic transport tests and MUST NOT be reported as real
Qwen/model or original public-provider API success.
"""
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
    _binding_matches,
    _matches_weather_final,
    evaluate_one,
)
from scripts.research_scoped_host_invocation import execute_scoped_host_call

LAT = 37.56
LON = 126.98
CITY = "Seoul"
LANGUAGE = "en"
COUNTRY = "KR"


def _call(route: str, arguments: dict[str, Any]) -> str:
    return "<tool_call>\n" + json.dumps({
        "name": route.replace(".", "__", 1),
        "arguments": arguments,
    }) + "\n</tool_call>"


FIRST = _call("open_meteo_geocoding.search", {
    "name": CITY, "country_code": COUNTRY, "language": LANGUAGE,
})
SECOND = _call("open_meteo_weather.current", {
    "latitude": LAT, "longitude": LON,
})
FINAL = json.dumps({
    "temperature_2m": 16.5,
    "unit": "°C",
    "observed_at": "2026-10-18T10:00",
})


class ScriptedAgent:
    def __init__(self, text: list[str]) -> None:
        self.text = text
        self.calls = 0
        self.history_roles: list[list[str]] = []

    def generate(
        self, messages: list[dict[str, str]], tools: list[dict[str, Any]],
    ) -> dict[str, Any]:
        self.history_roles.append([row["role"] for row in messages])
        assert len(tools) == 2
        assert {x["name"] for x in tools} == {
            "open_meteo_geocoding__search", "open_meteo_weather__current",
        }
        position = self.calls
        self.calls += 1
        return {
            "text": self.text[min(position, len(self.text) - 1)],
            "input_tokens": 64,
            "tool_tokens": 25,
            "output_tokens": 30,
            "latency_ms": 0.0,
            "context_overflow": False,
        }


def _fixture_transport(
    seen: list[str], *, correct_country: bool = True,
) -> httpx.MockTransport:
    def handle(request: httpx.Request) -> httpx.Response:
        seen.append(request.url.path)
        if request.url.path == "/v1/search":
            assert request.url.host == "geocoding-api.open-meteo.com"
            assert dict(request.url.params)["name"] == "Seoul"
            return httpx.Response(200, json={"results": [{
                "id": 1835848,
                "country_code": COUNTRY if correct_country else "JP",
                "latitude": LAT, "longitude": LON,
            }]})
        if request.url.path == "/v1/forecast":
            assert request.url.host == "api.open-meteo.com"
            assert float(request.url.params["latitude"]) == LAT
            assert float(request.url.params["longitude"]) == LON
            return httpx.Response(200, json={
                "current": {
                    "time": "2026-10-18T10:00",
                    "temperature_2m": 16.5,
                },
                "current_units": {"temperature_2m": "°C"},
            })
        raise AssertionError("unregistered external source")

    return httpx.MockTransport(handle)


@pytest.mark.asyncio
async def test_source_validated_model_selected_two_hop_and_exact_final() -> None:
    seen: list[str] = []
    agent = ScriptedAgent([FIRST, SECOND, FINAL])
    async with httpx.AsyncClient(transport=_fixture_transport(seen)) as client:
        row = await evaluate_one(
            agent, client, language=LANGUAGE, city=CITY, country=COUNTRY,
        )
    assert seen == ["/v1/search", "/v1/forecast"]
    assert row["attempted_model_calls"] == 2
    assert row["real_geocoding_calls"] == 1
    assert row["real_forecast_calls"] == 1
    assert row["real_geocoding_http_attempts"] == 1
    assert row["real_forecast_http_attempts"] == 1
    assert row["host_exception_family"] is None
    assert row["model_generated_two_step_complete"] is True
    assert row["strict_final_answer_correct"] is True
    assert row["full_task_complete"] is True
    assert row["independent_e2_qualified"] is False
    assert agent.history_roles[-1] == [
        "system", "user", "assistant", "user", "assistant", "user",
    ]
    # Output is sanitized: no source coordinates, model answers or prompts.
    encoded = json.dumps(row)
    assert "1835848" not in encoded
    assert "37.56" not in encoded
    assert "16.5" not in encoded


@pytest.mark.asyncio
async def test_premature_model_final_causes_no_provider_call() -> None:
    seen: list[str] = []
    async with httpx.AsyncClient(transport=_fixture_transport(seen)) as client:
        row = await evaluate_one(
            ScriptedAgent([FINAL]), client,
            language=LANGUAGE, city=CITY, country=COUNTRY,
        )
    assert not seen
    assert row["termination_reason"] == "premature_final"
    assert row["full_task_complete"] is False


@pytest.mark.asyncio
async def test_wrong_model_coordinates_fail_before_second_live_invocation() -> None:
    seen: list[str] = []
    agent = ScriptedAgent([
        FIRST, _call("open_meteo_weather.current", {
            "latitude": LAT + 0.5, "longitude": LON,
        }),
    ])
    async with httpx.AsyncClient(transport=_fixture_transport(seen)) as client:
        row = await evaluate_one(
            agent, client, language=LANGUAGE, city=CITY, country=COUNTRY,
        )
    assert seen == ["/v1/search"]
    assert row["real_forecast_calls"] == 0
    assert row["real_geocoding_http_attempts"] == 1
    assert row["real_forecast_http_attempts"] == 0
    assert row["termination_reason"] == "wrong_arguments_or_unobserved_state"
    assert row["full_task_complete"] is False


@pytest.mark.asyncio
async def test_model_wrong_city_fails_without_provider_request() -> None:
    seen: list[str] = []
    bad = _call("open_meteo_geocoding.search", {
        "name": "Paris", "language": LANGUAGE, "country_code": COUNTRY,
    })
    async with httpx.AsyncClient(transport=_fixture_transport(seen)) as client:
        row = await evaluate_one(
            ScriptedAgent([bad]), client,
            language=LANGUAGE, city=CITY, country=COUNTRY,
        )
    assert not seen and row["real_geocoding_calls"] == 0
    assert row["termination_reason"] == "wrong_arguments_or_unobserved_state"


@pytest.mark.asyncio
async def test_model_wrong_tool_order_denied_before_network() -> None:
    seen: list[str] = []
    async with httpx.AsyncClient(transport=_fixture_transport(seen)) as client:
        row = await evaluate_one(
            ScriptedAgent([SECOND]), client,
            language=LANGUAGE, city=CITY, country=COUNTRY,
        )
    assert not seen
    assert row["termination_reason"] == "unregistered_or_wrong_order_route"
    assert row["full_task_complete"] is False


@pytest.mark.asyncio
async def test_provider_wrong_country_does_not_trigger_weather_call() -> None:
    seen: list[str] = []
    async with httpx.AsyncClient(
        transport=_fixture_transport(seen, correct_country=False),
    ) as client:
        row = await evaluate_one(
            ScriptedAgent([FIRST]), client,
            language=LANGUAGE, city=CITY, country=COUNTRY,
        )
    assert seen == ["/v1/search"]
    assert row["model_generated_two_step_complete"] is False
    assert row["full_task_complete"] is False
    assert row["termination_reason"] == "host_or_native_source_denied"
    assert row["host_exception_family"] == "scoped_boundary_denial"
    assert row["host_failure_after_http_attempt"] is True
    assert row["trusted_failure_stage"] == "geocode_geocoding_payload_rejected"
    assert row["real_geocoding_http_attempts"] == 1
    assert row["real_geocoding_calls"] == 0
    assert row["real_forecast_http_attempts"] == 0
    # Previously misreported as zero external requests despite one HTTPS GET.
    assert len(seen) == row["real_geocoding_http_attempts"]


@pytest.mark.asyncio
async def test_model_correct_tools_wrong_final_is_not_task_success() -> None:
    seen: list[str] = []
    bad_final = json.dumps({
        "temperature_2m": 15.0,
        "unit": "°C",
        "observed_at": "2026-10-18T10:00",
    })
    async with httpx.AsyncClient(transport=_fixture_transport(seen)) as client:
        row = await evaluate_one(
            ScriptedAgent([FIRST, SECOND, bad_final]), client,
            language=LANGUAGE, city=CITY, country=COUNTRY,
        )
    assert row["model_generated_two_step_complete"] is True
    assert row["full_task_complete"] is False
    assert row["termination_reason"] == "incorrect_final_value_or_format"


@pytest.mark.asyncio
async def test_host_required_fields_cannot_request_unregistered_or_wrong_shape() -> None:
    seen: list[str] = []
    async with httpx.AsyncClient(transport=_fixture_transport(seen)) as client:
        router, _, _ = build_live_router(client)
        view = capture_authorized_agent_tool_surface(
            router, USER_REQUESTS["en"], principal=PRINCIPAL,
        )
        for wrong in (("not_a_public_field",), ["latitude", "longitude"]):
            with pytest.raises(
                PolicyViolationError, match="scoped host invocation denied",
            ):
                await execute_scoped_host_call(
                    view, selected_route_ids=[
                        "open_meteo_geocoding.search", "open_meteo_weather.current",
                    ],
                    route_id="open_meteo_geocoding.search",
                    arguments={"name": CITY, "language": LANGUAGE,
                               "country_code": COUNTRY},
                    host_required_output_fields=wrong,
                )
        assert not seen


def test_truthful_final_and_exact_second_hop_argument_binding() -> None:
    actual = {"temperature_2m": 16.5, "temperature_unit": "°C",
              "time": "2026-10-18T10:00"}
    assert _matches_weather_final(FINAL, actual)
    assert not _matches_weather_final(FINAL + " extra", actual)
    assert not _matches_weather_final(
        '{"temperature_2m":16.5,"temperature_2m":16.5,'
        '"unit":"°C","observed_at":"2026-10-18T10:00"}', actual,
    )
    assert _binding_matches(
        "open_meteo_weather.current",
        {"latitude": LAT, "longitude": LON},
        language=LANGUAGE, city=CITY, country=COUNTRY,
        validated_location={"latitude": LAT, "longitude": LON},
    )
    assert not _binding_matches(
        "open_meteo_weather.current",
        {"latitude": LAT, "longitude": LON},
        language=LANGUAGE, city=CITY, country=COUNTRY,
        validated_location=None,
    )


@pytest.mark.asyncio
async def test_transport_error_is_host_classified_without_private_error_text() -> None:
    seen = []

    def broken(request: httpx.Request) -> httpx.Response:
        seen.append(request.url.path)
        raise httpx.ConnectError("PRIVATE_PROVIDER_CANARY", request=request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(broken)) as client:
        row = await evaluate_one(
            ScriptedAgent([FIRST]), client,
            language=LANGUAGE, city=CITY, country=COUNTRY,
        )
    assert seen == ["/v1/search"]
    assert row["termination_reason"] == "host_or_native_source_denied"
    assert row["trusted_failure_stage"] == "geocode_http_transport_failure"
    assert row["host_exception_family"] == "scoped_boundary_denial"
    assert row["host_failure_after_http_attempt"] is True
    assert row["real_geocoding_http_attempts"] == 1
    assert row["real_geocoding_calls"] == 0
    assert row["full_task_complete"] is False
    assert "PRIVATE_PROVIDER_CANARY" not in json.dumps(row)


@pytest.mark.asyncio
async def test_host_pre_http_denial_is_not_mislabeled_source_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from scripts import research_real_qwen_open_meteo_two_hop_e1 as module

    async def deny_host(*_args: Any, **_kwargs: Any) -> dict:
        raise PolicyViolationError("PRIVATE_POLICY_CANARY")

    monkeypatch.setattr(module, "execute_scoped_host_call", deny_host)
    seen: list[str] = []
    async with httpx.AsyncClient(transport=_fixture_transport(seen)) as client:
        row = await evaluate_one(
            ScriptedAgent([FIRST]), client,
            language=LANGUAGE, city=CITY, country=COUNTRY,
        )
    assert seen == []
    assert row["trusted_failure_stage"] == "host_boundary_without_new_http"
    assert row["host_failure_after_http_attempt"] is False
    assert row["real_geocoding_http_attempts"] == 0
    assert row["real_geocoding_calls"] == 0
    assert row["full_task_complete"] is False
    assert "PRIVATE_POLICY_CANARY" not in json.dumps(row)
