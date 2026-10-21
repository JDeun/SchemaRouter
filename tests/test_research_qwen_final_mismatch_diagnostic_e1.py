"""Trust only the strict source oracle; categorize failure without source values."""
from __future__ import annotations

import json

import httpx
import pytest

from scripts.research_real_qwen_open_meteo_two_hop_e1 import (
    _matches_weather_final,
    _weather_final_failure_kind,
    evaluate_one,
)

WEATHER = {
    "temperature_2m": 16.5,
    "temperature_unit": "°C",
    "time": "2026-10-18T10:00",
}
FINAL = {
    "temperature_2m": 16.5,
    "unit": "°C",
    "observed_at": "2026-10-18T10:00",
}


@pytest.mark.parametrize("text,reason", (
    (json.dumps(FINAL), None),
    ('{"temperature_2m": 16.5,', "invalid_json"),
    ('{"temperature_2m": NaN, "unit":"°C","observed_at":"2026-10-18T10:00"}',
     "invalid_json"),
    ('{"temperature_2m":16.5,"temperature_2m":17.5,"unit":"°C",'
     '"observed_at":"2026-10-18T10:00"}', "invalid_json"),
    (json.dumps({"temperature_2m": 16.5}), "invalid_shape"),
    (json.dumps({"temperature_2m": "16.5", "unit": "°C",
                 "observed_at": "2026-10-18T10:00"}), "invalid_types"),
    (json.dumps({**FINAL, "temperature_2m": 15.5}), "temperature_mismatch"),
    (json.dumps({**FINAL, "unit": "C"}), "unit_mismatch"),
    (json.dumps({**FINAL, "observed_at": "2026-10-18T11:00"}),
     "timestamp_mismatch"),
    (json.dumps({**FINAL, "unit": "C", "temperature_2m": 15.5}),
     "multiple_source_fields"),
))
def test_original_strict_final_validation_and_bounded_failure_kind(text, reason):
    verdict = _matches_weather_final(text, WEATHER)
    assert verdict == (reason is None)
    assert _weather_final_failure_kind(text, WEATHER) == reason
    if reason is not None:
        assert "16.5" not in reason
        assert "2026" not in reason
        assert "latitude" not in reason


def _call(route, args):
    return "<tool_call>\n" + json.dumps({
        "name": route.replace(".", "__", 1), "arguments": args,
    }) + "\n</tool_call>"


class Agent:
    def __init__(self, final):
        self.outputs = [
            _call("open_meteo_geocoding.search", {
                "name": "Seoul", "language": "en", "country_code": "KR",
            }),
            _call("open_meteo_weather.current", {
                "latitude": 37.56, "longitude": 126.98,
            }),
            final,
        ]
        self.i = 0

    def generate(self, messages, tools):
        del messages, tools
        output = self.outputs[self.i]
        self.i += 1
        return {"text": output, "latency_ms": 0.0, "context_overflow": False}


def _original_provider(request):
    if request.url.path == "/v1/search":
        return httpx.Response(200, json={"results": [{
            "id": 1835848, "country_code": "KR",
            "latitude": 37.56, "longitude": 126.98,
        }]})
    if request.url.path == "/v1/forecast":
        return httpx.Response(200, json={
            "current": {
                "time": WEATHER["time"], "temperature_2m": WEATHER["temperature_2m"],
            },
            "current_units": {"temperature_2m": WEATHER["temperature_unit"]},
        })
    raise AssertionError("unapproved provider path")


@pytest.mark.asyncio
@pytest.mark.parametrize("bad_json,expected", (
    (json.dumps({**FINAL, "observed_at": "2026-10-18T11:00"}),
     "timestamp_mismatch"),
    (json.dumps({**FINAL, "temperature_2m": 12.3}),
     "temperature_mismatch"),
))
async def test_actual_native_two_step_never_promotes_wrong_final(bad_json, expected):
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(_original_provider),
    ) as client:
        result = await evaluate_one(
            Agent(bad_json), client, language="en",
            city="Seoul", country="KR",
        )
    assert result["real_geocoding_calls"] == 1
    assert result["real_forecast_calls"] == 1
    assert result["full_task_complete"] is False
    assert result["termination_reason"] == "incorrect_final_value_or_format"
    assert result["trusted_final_validation_failure_kind"] == expected
    assert "16.5" not in json.dumps(result)
    assert "126.98" not in json.dumps(result)
