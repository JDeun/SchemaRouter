"""Two *real* public Open-Meteo HTTPS hops through bound SchemaRouter endpoints.

Research E1 provider-live execution smoke (not agent-generated tool routing,
independent E2, or response factuality oracle). Host selects both calls and
trusted city inputs; the second consumes validated first-hop coordinates.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import math
import time
from pathlib import Path
from typing import Any

import httpx

from schemarouter import (
    EndpointSpec,
    ExecutionPlan,
    FieldSpec,
    ParameterSpec,
    SchemaRouter,
    ToolCall,
    ToolSpec,
)

GEOCODE_URL = "https://geocoding-api.open-meteo.com/v1/search"
WEATHER_URL = "https://api.open-meteo.com/v1/forecast"
CASES = (
    ("en", "Seoul", "KR"),
    ("ko", "서울", "KR"),
    ("ja", "東京", "JP"),
)
MAX_RESPONSE_BYTES = 262144


def _finite_number(value: Any, *, minimum: float, maximum: float) -> float:
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ValueError("provider returned invalid coordinate or measurement")
    if not minimum <= value <= maximum:
        raise ValueError("provider numeric value out of source contract")
    return float(value)


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate provider JSON object key")
        result[key] = value
    return result


def _nonfinite(_: str) -> None:
    raise ValueError("provider JSON contains nonfinite value")


def _provider_json(response: httpx.Response) -> dict[str, Any]:
    response.raise_for_status()
    if len(response.content) > MAX_RESPONSE_BYTES:
        raise ValueError("provider response too large")
    try:
        raw = json.loads(
            response.content,
            object_pairs_hook=_unique_object,
            parse_constant=_nonfinite,
        )
    except (TypeError, UnicodeError, ValueError) as exc:
        raise ValueError("provider JSON invalid") from exc
    if type(raw) is not dict:
        raise ValueError("provider response must be object")
    return raw


def _geocode_response(payload: dict[str, Any], country_code: str) -> dict[str, Any]:
    rows = payload.get("results")
    if type(rows) is not list or not rows or type(rows[0]) is not dict:
        raise ValueError("geocoding source returned no verifiable location")
    row = rows[0]
    if row.get("country_code") != country_code:
        raise ValueError("geocoding returned wrong country")
    if type(row.get("id")) is not int or row["id"] <= 0:
        raise ValueError("geocoding location ID invalid")
    return {
        "location_id": row["id"],
        "latitude": _finite_number(
            row.get("latitude"), minimum=-90, maximum=90,
        ),
        "longitude": _finite_number(
            row.get("longitude"), minimum=-180, maximum=180,
        ),
        "country_code": country_code,
    }


def _forecast_response(payload: dict[str, Any]) -> dict[str, Any]:
    current = payload.get("current")
    units = payload.get("current_units")
    if type(current) is not dict or type(units) is not dict:
        raise ValueError("weather source omitted current observation")
    date = current.get("time")
    unit = units.get("temperature_2m")
    if (
        type(date) is not str or not 16 <= len(date) <= 35
        or date[4:5] != "-" or date[7:8] != "-" or "T" not in date
        or unit != "°C"
    ):
        raise ValueError("weather time or unit source contract invalid")
    return {
        "time": date,
        "temperature_2m": _finite_number(
            current.get("temperature_2m"), minimum=-120, maximum=70,
        ),
        "temperature_unit": unit,
    }


class OpenMeteoBoundInvoker:
    """Trusted fixed-host invoker. No caller-controlled host, path or API key."""

    def __init__(self, client: httpx.AsyncClient, *, source: str) -> None:
        if source not in ("geocode", "forecast"):
            raise ValueError("unknown trusted Open-Meteo source")
        self.client = client
        self.source = source
        self.calls = 0

    async def __call__(
        self, endpoint: str, arguments: dict[str, Any],
    ) -> dict[str, Any]:
        if self.source == "geocode" and endpoint == "search":
            country = arguments["country_code"]
            params = {
                "name": arguments["name"],
                "countryCode": country,
                "count": 1,
                "format": "json",
            }
            response = await self.client.get(GEOCODE_URL, params=params)
            result = _geocode_response(_provider_json(response), country)
        elif self.source == "forecast" and endpoint == "current":
            params = {
                "latitude": arguments["latitude"],
                "longitude": arguments["longitude"],
                "current": "temperature_2m",
                "timezone": "auto",
            }
            response = await self.client.get(WEATHER_URL, params=params)
            result = _forecast_response(_provider_json(response))
        else:
            raise ValueError("unregistered trusted Open-Meteo endpoint")
        self.calls += 1
        return result


def _parameter(name: str, schema: dict[str, Any]) -> ParameterSpec:
    return ParameterSpec(name=name, required=True, json_schema=schema)


def _schema(params: dict[str, Any]) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": params,
        "required": list(params),
        "additionalProperties": False,
    }


def build_live_router(
    client: httpx.AsyncClient,
) -> tuple[SchemaRouter, OpenMeteoBoundInvoker, OpenMeteoBoundInvoker]:
    geo = ToolSpec(
        name="open_meteo_geocoding",
        provider="open-meteo", access_mode="host-bound-https",
        source_type="public_rest",
        remote=True,
        description="Resolve a place to WGS84 coordinates",
        endpoints=[EndpointSpec(
            name="search", read_only=True, destructive=False,
            description="Geocode city and explicit country",
            parameters=[
                _parameter("name", {"type": "string", "minLength": 2}),
                _parameter("country_code", {
                    "type": "string", "enum": ["KR", "JP"],
                }),
            ],
            input_schema=_schema({
                "name": {"type": "string", "minLength": 2},
                "country_code": {"type": "string", "enum": ["KR", "JP"]},
            }),
            output_schema=_schema({
                "location_id": {"type": "integer", "minimum": 1},
                "latitude": {"type": "number", "minimum": -90, "maximum": 90},
                "longitude": {"type": "number", "minimum": -180, "maximum": 180},
                "country_code": {"type": "string", "enum": ["KR", "JP"]},
            }),
            output_fields=[
                FieldSpec(name="location_id", identifier=True),
                FieldSpec(name="latitude"),
                FieldSpec(name="longitude"),
                FieldSpec(name="country_code"),
            ],
        )],
    )
    weather = ToolSpec(
        name="open_meteo_weather",
        provider="open-meteo", access_mode="host-bound-https",
        source_type="public_rest", remote=True,
        description="Read observed current weather using source geocoordinates",
        endpoints=[EndpointSpec(
            name="current", read_only=True, destructive=False,
            description="Get Celsius current temperature at WGS84 coordinates",
            parameters=[
                _parameter("latitude", {"type": "number", "minimum": -90, "maximum": 90}),
                _parameter("longitude", {"type": "number", "minimum": -180, "maximum": 180}),
            ],
            input_schema=_schema({
                "latitude": {"type": "number", "minimum": -90, "maximum": 90},
                "longitude": {"type": "number", "minimum": -180, "maximum": 180},
            }),
            output_schema=_schema({
                "time": {"type": "string"},
                "temperature_2m": {"type": "number"},
                "temperature_unit": {"type": "string", "const": "°C"},
            }),
            output_fields=[
                FieldSpec(name="time"),
                FieldSpec(name="temperature_2m"),
                FieldSpec(name="temperature_unit"),
            ],
        )],
    )
    router = SchemaRouter()
    geo_invoker = OpenMeteoBoundInvoker(client, source="geocode")
    weather_invoker = OpenMeteoBoundInvoker(client, source="forecast")
    router.add_bound_tool(geo, geo_invoker)
    router.add_bound_tool(weather, weather_invoker)
    return router, geo_invoker, weather_invoker


def _plan(
    router: SchemaRouter, query: str, *,
    tool_name: str, endpoint_name: str, args: dict[str, Any],
    fields: list[str],
) -> ExecutionPlan:
    tool = router.registry.get(tool_name)
    endpoint = tool.endpoint(endpoint_name)
    return ExecutionPlan(
        query=query, registry_version=router.registry.version,
        calls=[ToolCall(
            tool=tool_name, endpoint=endpoint_name,
            schema_fingerprint=endpoint.fingerprint,
            tool_fingerprint=tool.fingerprint,
            arguments=args,
            fields=fields,
        )],
    )


async def live_task(
    router: SchemaRouter, lang: str, city: str, country: str,
) -> dict[str, Any]:
    """Host-orchestrated two-stage execution, NOT model tool planning."""
    query = f"weather in {city}"  # Not passed as an EN/KO/JA competence result.
    first = _plan(
        router, query, tool_name="open_meteo_geocoding",
        endpoint_name="search", args={"name": city, "country_code": country},
        fields=["location_id", "latitude", "longitude", "country_code"],
    )
    location = (await router.execute(first))[0].data
    if type(location) is not dict or location.get("country_code") != country:
        raise ValueError("geocoding SchemaRouter projection incorrect")
    # Exactly the two *observed projected fields* flow into the next call.
    second = _plan(
        router, query, tool_name="open_meteo_weather",
        endpoint_name="current",
        args={
            "latitude": location["latitude"],
            "longitude": location["longitude"],
        },
        fields=["time", "temperature_2m", "temperature_unit"],
    )
    weather = (await router.execute(second))[0].data
    if (
        type(weather) is not dict
        or type(weather.get("temperature_2m")) not in (int, float)
        or weather.get("temperature_unit") != "°C"
        or type(weather.get("time")) is not str
    ):
        raise ValueError("weather SchemaRouter projection incorrect")
    return {
        "language_label": lang,
        "host_supplied_place": True,
        "geocode_verified_country": True,
        "geocode_observation_to_weather_args": True,
        "current_weather_source_observed": True,
        "two_real_source_calls_completed": True,
        "model_selected_routes": False,
        "native_provider_e2_qualified": False,
    }


async def run(
    client: httpx.AsyncClient,
) -> dict[str, Any]:
    router, geo, weather = build_live_router(client)
    started = time.perf_counter()
    results = []
    for lang, name, country in CASES:
        results.append(await live_task(router, lang, name, country))
    if geo.calls != len(CASES) or weather.calls != len(CASES):
        raise ValueError("did not complete exactly two provider calls per case")
    return {
        "study": "OPEN_METEO_REAL_BOUND_TWO_HOP_PUBLIC_DEV_E1",
        "cases": results,
        "source_http_calls": {"geocoding": geo.calls, "forecast": weather.calls},
        "duration_seconds": round(time.perf_counter() - started, 2),
        "source_hosts": [
            "geocoding-api.open-meteo.com", "api.open-meteo.com",
        ],
        "actual_external_https": True,
        "host_orchestrated_not_agent": True,
        "independent_private_e2": False,
        "tool_choice_accuracy_measured": False,
        "real_agent_final_answer_pass": False,
        "product_defaults_changed": False,
        "release_qualified": False,
    }


async def _main(out: Path) -> None:
    async with httpx.AsyncClient(
        timeout=httpx.Timeout(15.0), follow_redirects=False,
    ) as client:
        report = await run(client)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(report, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({
        "study": report["study"], "source_http_calls": report["source_http_calls"],
        "languages": [row["language_label"] for row in report["cases"]],
        "provider_native_live": True, "independent_private_e2": False,
    }, sort_keys=True))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    asyncio.run(_main(args.out))


if __name__ == "__main__":
    main()
