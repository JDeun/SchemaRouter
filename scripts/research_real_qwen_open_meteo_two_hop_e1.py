"""Real pinned local Qwen selects TWO actual Open-Meteo tool calls (E1 DEV).

Research-only: shared strict Qwen tool parser, checked principal-scoped native
tool definitions and existing SchemaRouter planning/execution. No new executor.
These exposed host-authored EN/KO/JA requests are NOT independent E2 gold.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import platform
import subprocess
import time
from pathlib import Path
from typing import Any

import httpx

from schemarouter import PolicyViolationError, PrincipalContext
from scripts.agent_utility_v7_dev_agent import MODEL_NAME, MODEL_REVISION
from scripts.research_authorized_agent_tool_surface import (
    capture_authorized_agent_tool_surface,
)
from scripts.research_open_meteo_live_two_hop_e1 import CASES, build_live_router
from scripts.research_qwen_nous_user_transcript_e0 import (
    append_authorized_nous_user_history_e0,
)
from scripts.research_real_qwen_bound_two_step_e0 import (
    _parse_strict_model_json,
    parse_one_model_action,
)
from scripts.research_scoped_host_invocation import execute_scoped_host_call

ROOT = Path(__file__).resolve().parents[1]
ROUTES = ("open_meteo_geocoding.search", "open_meteo_weather.current")
MAX_TURNS = 4
PRINCIPAL = PrincipalContext(subject="e1-public-open-meteo-reader", roles=("reader",))
SYSTEM = (
    "You are a research agent. Make exactly one listed tool call at a time and "
    "wait for each result. For a city's weather, first resolve its coordinates, "
    "then pass the exact returned latitude and longitude to the weather tool. "
    "Never invent coordinates or weather data. Do not add unsupported keys. "
    "When complete, respond ONLY as a JSON object with exactly these keys: "
    "temperature_2m (number), unit (string), observed_at (string). "
    "Use the units and observation timestamp shown by the weather result. "
    "If you cannot complete the task, reply exactly REQUEST_MORE_TOOLS."
)
# Explicitly author-visible DEV cases. Do not claim language-detection accuracy.
USER_REQUESTS = {
    "en": (
        "What is the current Celsius temperature for Seoul, South Korea? "
        "The city's source search name is Seoul, country_code KR and language en. "
        "Use the geolocation result and then check the actual current weather."
    ),
    "ko": (
        "대한민국 서울특별시의 현재 섭씨 기온을 알려 주세요. "
        "지명 검색 이름은 서울특별시, country_code KR, language ko입니다. "
        "실제 위치 조회에서 반환한 좌표로 현재 날씨를 다시 조회하세요."
    ),
    "ja": (
        "日本の東京都の現在の摂氏気温を教えてください。 "
        "地点検索の名前は東京都、country_code JP、language jaです。 "
        "位置検索で返された座標で、実際の現在の天気を確認してください。"
    ),
}


def _matches_weather_final(text: str, actual: dict[str, Any]) -> bool:
    try:
        raw = _parse_strict_model_json(text.strip())
    except (TypeError, ValueError, OverflowError):
        return False
    return (
        type(raw) is dict
        and set(raw) == {"temperature_2m", "unit", "observed_at"}
        and type(raw["temperature_2m"]) in (int, float)
        and raw["temperature_2m"] == actual["temperature_2m"]
        and type(raw["unit"]) is str
        and raw["unit"] == actual["temperature_unit"] == "°C"
        and type(raw["observed_at"]) is str
        and raw["observed_at"] == actual["time"]
    )


def _binding_matches(
    route: str, arguments: dict[str, Any], *,
    language: str, city: str, country: str,
    validated_location: dict[str, Any] | None,
) -> bool:
    if route == ROUTES[0]:
        return (
            validated_location is None
            and set(arguments) == {"name", "language", "country_code"}
            and all(type(v) is str for v in arguments.values())
            and arguments == {
                "name": city, "language": language, "country_code": country,
            }
        )
    if route == ROUTES[1] and validated_location is not None:
        return (
            set(arguments) == {"latitude", "longitude"}
            and all(type(v) in (int, float) for v in arguments.values())
            and arguments["latitude"] == validated_location["latitude"]
            and arguments["longitude"] == validated_location["longitude"]
        )
    return False


async def evaluate_one(
    agent: Any, client: httpx.AsyncClient, *,
    language: str, city: str, country: str,
) -> dict[str, Any]:
    """Never convert a denied/incomplete model action into a successful call."""
    if (
        (language, city, country) not in CASES
        or language not in USER_REQUESTS
        or not callable(getattr(agent, "generate", None))
    ):
        raise ValueError("unregistered source task or model")
    router, geocode, weather = build_live_router(client)
    query = USER_REQUESTS[language]
    messages = [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": query},
    ]
    actual_location: dict[str, Any] | None = None
    actual_weather: dict[str, Any] | None = None
    attempted = 0
    completed = 0
    turns = 0
    correctly_ended = False
    reason = "turn_limit"
    total_model_ms = 0.0

    for _ in range(MAX_TURNS):
        turns += 1
        # Fresh source authority and freshness check EACH generation.
        view = capture_authorized_agent_tool_surface(
            router, query, principal=PRINCIPAL,
        )
        if set(view.visible_route_ids) != set(ROUTES):
            raise PolicyViolationError("public source visibility unexpectedly changed")
        definitions = view.tool_definitions(list(ROUTES), k=2)
        generated = agent.generate(messages, definitions)
        view.assert_source_unchanged()
        if (
            type(generated) is not dict
            or type(generated.get("text")) is not str
            or type(generated.get("context_overflow")) is not bool
            or type(generated.get("latency_ms")) not in (int, float)
        ):
            raise ValueError("invalid model generation envelope")
        total_model_ms += float(generated["latency_ms"])
        if generated["context_overflow"]:
            reason = "context_overflow"
            break
        try:
            kind, payload = parse_one_model_action(generated["text"])
        except (ValueError, TypeError, OverflowError):
            reason = "malformed_model_tool_call"
            break
        if kind == "final":
            reason = "completed_final" if completed == 2 else "premature_final"
            if completed == 2 and actual_weather is not None:
                correctly_ended = _matches_weather_final(payload, actual_weather)
                if not correctly_ended:
                    reason = "incorrect_final_value_or_format"
            break

        attempted += 1
        route, arguments = payload["route"], payload["arguments"]
        if completed >= len(ROUTES) or route != ROUTES[completed]:
            reason = "unregistered_or_wrong_order_route"
            break
        if not _binding_matches(
            route, arguments,
            language=language, city=city, country=country,
            validated_location=actual_location,
        ):
            # Crucial: a model cannot invent coordinates, change city, or
            # reuse another principal/provider observation as valid state.
            reason = "wrong_arguments_or_unobserved_state"
            break

        try:
            # This is the ALREADY EXISTING trusted planner, auth gate,
            # read-only RegistryExecutor and output projection.
            observation = await execute_scoped_host_call(
                view, selected_route_ids=list(ROUTES),
                route_id=route, arguments=arguments,
            )
        except (PolicyViolationError, ValueError, RuntimeError):
            reason = "host_or_native_source_denied"
            break
        if (
            type(observation) is not dict
            or observation.get("status") != "ok"
        ):
            reason = "non_ok_native_observation"
            break

        completed += 1
        if route == ROUTES[0]:
            # The provider adapter independently checks the original
            # location ID. SchemaRouter correctly omits identifier-only
            # fields from projected agent observations. Never insist that
            # an internal source identity be disclosed to the model.
            if (
                type(observation.get("latitude")) not in (int, float)
                or type(observation.get("longitude")) not in (int, float)
            ):
                # Country is validated against the trusted original JSON by
                # the geocoding adapter *before* Router.execute. The planner
                # can legitimately project country_code away, so never
                # require it to reappear in the model-visible observation.
                reason = "invalid_first_source_observation"
                break
            actual_location = observation
        else:
            if (
                type(observation.get("temperature_2m")) not in (int, float)
                or type(observation.get("temperature_unit")) is not str
                or type(observation.get("time")) is not str
            ):
                reason = "invalid_second_source_observation"
                break
            actual_weather = observation

        # Shared upstream-pinned Qwen Nous history encoder. It will accept
        # only validated public observations, not raw provider replies.
        append_authorized_nous_user_history_e0(
            messages, authorized_route_ids=tuple(view.visible_route_ids),
            executed_route_id=route,
            validated_arguments=arguments,
            public_observation=observation,
        )

    if completed != geocode.calls + weather.calls:
        raise ValueError("native provider calls differ from successful host observations")
    if geocode.calls > 1 or weather.calls > 1:
        raise ValueError("unexpected repeated native provider requests")
    return {
        "language": language,
        "model_turns": turns,
        "attempted_model_calls": attempted,
        "real_geocoding_calls": geocode.calls,
        "real_forecast_calls": weather.calls,
        "model_generated_first_step_complete": completed >= 1,
        "model_generated_two_step_complete": completed == 2,
        "strict_final_answer_correct": correctly_ended,
        "full_task_complete": completed == 2 and correctly_ended,
        "termination_reason": reason,
        "model_generation_ms": round(total_model_ms, 1),
        "original_provider_e1": True,
        "independent_e2_qualified": False,
    }


async def evaluate(
    agent: Any, client: httpx.AsyncClient,
) -> dict[str, Any]:
    started = time.perf_counter()
    outcomes = [
        await evaluate_one(agent, client, language=lang, city=city, country=country)
        for lang, city, country in CASES
    ]
    return {
        "study": "REAL_QWEN_NATIVE_OPEN_METEO_TWO_STEP_E1_DEV",
        "case_count": len(outcomes),
        "outcomes": outcomes,
        "total_real_source_calls": sum(
            x["real_geocoding_calls"] + x["real_forecast_calls"] for x in outcomes
        ),
        "model_generated_full_task_successes": sum(
            x["full_task_complete"] for x in outcomes
        ),
        "duration_seconds": round(time.perf_counter() - started, 2),
        "model_id": MODEL_NAME,
        "model_revision": MODEL_REVISION,
        "scripted_host_route_order_scoring": True,
        "strict_source_observation_argument_binding": True,
        "source_is_live_public_api": True,
        "original_provider_benchmark_gold": False,
        "independently_authored_private_e2": False,
        "calibrated_no_fit": False,
        "product_default_changed": False,
        "release_qualified": False,
    }


async def real_cpu_run() -> dict[str, Any]:
    from scripts.agent_utility_v7_dev_agent import LocalQwenAgent

    agent = LocalQwenAgent()
    async with httpx.AsyncClient(
        timeout=httpx.Timeout(20.0), follow_redirects=False,
    ) as client:
        result = await evaluate(agent, client)
    result["actual_pinned_model_inference"] = True
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    source = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True,
        capture_output=True, timeout=10, check=True,
    ).stdout.strip()
    result = asyncio.run(real_cpu_run())
    result["source_revision"] = source
    result["hardware"] = platform.platform()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    print(json.dumps({
        "study": result["study"],
        "total_real_source_calls": result["total_real_source_calls"],
        "model_generated_full_task_successes": result["model_generated_full_task_successes"],
        "by_language": {
            row["language"]: {
                "real_geocoding_calls": row["real_geocoding_calls"],
                "real_forecast_calls": row["real_forecast_calls"],
                "full_task_complete": row["full_task_complete"],
                "termination_reason": row["termination_reason"],
            }
            for row in result["outcomes"]
        },
        "independently_authored_private_e2": False,
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
