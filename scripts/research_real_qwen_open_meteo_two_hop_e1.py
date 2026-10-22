"""Real pinned local Qwen selects TWO actual Open-Meteo tool calls (E1 DEV).

Research-only: shared strict Qwen tool parser, checked principal-scoped native
tool definitions and existing SchemaRouter planning/execution. No new executor.
These exposed host-authored EN/KO/JA requests are NOT independent E2 gold.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import platform
import subprocess
import time
from pathlib import Path
from typing import Any

import httpx

from schemarouter import (
    NativeConceptCatalog,
    NativeDeclaredConcept,
    NativeSchemaGraphIndex,
    NativeSchemaPostingIndex,
    PolicyViolationError,
    PrincipalContext,
)
from schemarouter.capability_contracts import CapabilityFieldContract
from scripts.agent_utility_v7_dev_agent import MODEL_NAME, MODEL_REVISION
from scripts.research_authorized_agent_tool_surface import (
    capture_authorized_agent_tool_surface,
)
from scripts.research_authorized_concept_fixed5_agent_bridge import (
    AuthorizedConceptGraphFixed5Selector,
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
from scripts.research_source_ready_native_tool_menu_e1 import (
    source_ready_visible_routes,
)

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

G5_COMPARISON_ARMS = ("all_visible", "lexical_k5", "concept_graph_optin")


def documented_open_meteo_e1_catalog() -> NativeConceptCatalog:
    """Exposed E1 intent labels, independent from actual provider answer values.

    These aliases are declared by the research host, not inferred by an LLM.
    This catalog is qualified only for the non-commercial public API fixture.
    """
    return NativeConceptCatalog(concepts=(NativeDeclaredConcept(
        concept_id="open_meteo_current_temperature",
        aliases=(
            "current Celsius temperature", "현재 섭씨 기온", "現在の摂氏気温",
        ),
        required_fields=(CapabilityFieldContract(
            semantic_id="open_meteo.temperature_2m",
            json_schema={"type": "number"},
        ),),
        source_type="public_rest",
        license="Open-Meteo Free API / Non-Commercial / CC BY 4.0 data",
    ),))


def _native_source_receipt(router: Any) -> tuple[Any, ...]:
    """Source-identity receipt for paired arms; never exports private data."""
    policy = router.authorization_policy
    return (
        router.registry.version,
        tuple(sorted((tool.key, tool.fingerprint) for tool in router.registry.tools())),
        None if policy is None else (
            policy.default_effect, repr(policy.rules), repr(policy.data_rules),
        ),
    )


def _qualified_g5_selector(
    router: Any, query: str, *,
    catalog: NativeConceptCatalog | None,
    approved_host_roots: frozenset[str],
) -> AuthorizedConceptGraphFixed5Selector | None:
    """Fail closed until independently host-reviewed native source intake exists.

    Open-Meteo's current E1 schemas have no explicit G5 policy/license,
    typed scalar semantic IDs or authorized host roots; there is no fallback
    where the evaluator invents these from its own task gold.
    """
    if (
        router.authorization_policy is None
        or not isinstance(catalog, NativeConceptCatalog)
        or type(approved_host_roots) is not frozenset
        or any(type(root) is not str for root in approved_host_roots)
        or any(
            not tool.source_type or not tool.license
            for tool in router.registry.tools()
        )
    ):
        return None
    try:
        index = NativeSchemaGraphIndex.build(
            NativeSchemaPostingIndex.build(router.registry),
            approved_host_roots=approved_host_roots,
        )
        view = capture_authorized_agent_tool_surface(
            router, query, principal=PRINCIPAL,
        )
        selector = AuthorizedConceptGraphFixed5Selector(view, catalog, index)
        # All original provider operations must be selected with an actual
        # fully proved join; an output-only direct route is not enough.
        selected = selector(query, view.visible_route_ids)
        if tuple(selected) != ROUTES or selector.last_status != "complete":
            return None
        return selector
    except (PolicyViolationError, ValueError, TypeError):
        return None


def _blocked_g5_case(language: str) -> dict[str, Any]:
    """No denominators or percentages: this is not an agent failure."""
    return {
        "status": "BLOCKED_SOURCE_SEMANTICS",
        "condition": "concept_graph_optin",
        "language": language,
        "requested_k": 5,
        "model_turns": 0,
        "real_geocoding_http_attempts": 0,
        "real_forecast_http_attempts": 0,
        "real_geocoding_calls": 0,
        "real_forecast_calls": 0,
        "full_task_complete": None,
        "original_provider_e1": False,
        "independent_e2_qualified": False,
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


def _weather_final_failure_kind(
    model_final: str, actual: dict[str, Any],
) -> str | None:
    """Sanitized original-source final failure only; NEVER raw values.

    This is diagnostic evidence, not a correctness adjustment, model
    response repair, schema coercion or inference of new provider values.
    The independent strict `_matches_weather_final` remains the sole
    source-grounded correctness oracle.
    """
    try:
        answer = _parse_strict_model_json(model_final.strip())
    except (TypeError, ValueError, OverflowError):
        return "invalid_json"
    if type(answer) is not dict or set(answer) != {
        "temperature_2m", "unit", "observed_at",
    }:
        return "invalid_shape"
    if (
        type(answer["temperature_2m"]) not in (int, float)
        or type(answer["unit"]) is not str
        or type(answer["observed_at"]) is not str
    ):
        return "invalid_types"
    mismatches = (
        answer["temperature_2m"] != actual["temperature_2m"],
        answer["unit"] != actual["temperature_unit"] or answer["unit"] != "°C",
        answer["observed_at"] != actual["time"],
    )
    if sum(mismatches) > 1:
        return "multiple_source_fields"
    if mismatches[0]:
        return "temperature_mismatch"
    if mismatches[1]:
        return "unit_mismatch"
    if mismatches[2]:
        return "timestamp_mismatch"
    return None


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
    menu_mode: str = "all_visible",
    transport_retry_budget: int = 0,
    evidence_reprompt_budget: int = 0,
    host_concept_catalog: NativeConceptCatalog | None = None,
    approved_host_roots: frozenset[str] = frozenset(),
    documented_noncommercial_e1: bool = False,
    _private_source_observations: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Never convert a denied/incomplete model action into a successful call.

    A research-only bounded reminder may ask the model to continue *after*
    trusted geocoding, but cannot invoke any native source by itself.
    """
    if (
        (language, city, country) not in CASES
        or language not in USER_REQUESTS
        or not callable(getattr(agent, "generate", None))
        or menu_mode not in (*G5_COMPARISON_ARMS, "state_ready")
        or type(transport_retry_budget) is not int
        or transport_retry_budget not in (0, 1)
        or type(evidence_reprompt_budget) is not int
        or evidence_reprompt_budget not in (0, 1)
    ):
        raise ValueError("unregistered source task or model")
    router, geocode, weather = build_live_router(
        client, transport_retry_budget=transport_retry_budget,
        **({"documented_noncommercial_e1": True} if documented_noncommercial_e1 else {}),
    )
    query = USER_REQUESTS[language]
    graph_selector = None
    if menu_mode == "concept_graph_optin":
        graph_selector = _qualified_g5_selector(
            router, query, catalog=host_concept_catalog,
            approved_host_roots=approved_host_roots,
        )
        if graph_selector is None:
            return _blocked_g5_case(language)
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
    final_failure_kind: str | None = None
    reason = "turn_limit"
    host_exception_family: str | None = None
    host_failure_after_http_attempt: bool | None = None
    trusted_failure_stage: str | None = None
    trusted_transport_error_kind: str | None = None
    total_model_ms = 0.0
    executed_routes: list[str] = []
    evidence_reprompts = 0

    for _ in range(MAX_TURNS):
        turns += 1
        # Fresh source authority and freshness check EACH generation.
        view = capture_authorized_agent_tool_surface(
            router, query, principal=PRINCIPAL,
        )
        if set(view.visible_route_ids) != set(ROUTES):
            raise PolicyViolationError("public source visibility unexpectedly changed")
        # Experimental source readiness: only expose original authorized
        # read-only endpoints whose required native inputs actually exist
        # in owner-supplied request context or validated public state.
        # The default arm retains the exact original tool menu.
        if menu_mode == "concept_graph_optin":
            # The same owner/graph contract is rechecked at *every* turn;
            # source-ready is an additional host-input/observed-state gate.
            if graph_selector is None:
                raise PolicyViolationError("G5 scoped selector unexpectedly unavailable")
            chosen = graph_selector(query, view.visible_route_ids)
            if tuple(chosen) != ROUTES:
                raise PolicyViolationError("G5 route contract changed mid-episode")
            ready = source_ready_visible_routes(
                view,
                host_request_inputs={
                    "name": city, "language": language, "country_code": country,
                },
                prior_public_observation=actual_location,
                executed_route_ids=tuple(executed_routes),
            )
            offered = tuple(route for route in chosen if route in ready)
        elif menu_mode == "state_ready":
            offered = source_ready_visible_routes(
                view,
                host_request_inputs={
                    "name": city, "language": language, "country_code": country,
                },
                prior_public_observation=actual_location,
                executed_route_ids=tuple(executed_routes),
            )
        elif menu_mode == "lexical_k5":
            ranked = router.retrieve_authorized(query, principal=PRINCIPAL, k=5)
            offered = tuple(c.route_id for c in ranked.candidates
                            if c.route_id in view.visible_route_ids)
        else:
            offered = ROUTES
        # Fixed5 arms retain their K=5 contract even though this particular
        # original public provider has only two registered source routes.
        disclosure_k = 5 if menu_mode in (
            "concept_graph_optin", "lexical_k5",
        ) else 2
        definitions = view.tool_definitions(list(offered), k=disclosure_k) if offered else []
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
            # Optional E0-only recovery from an observed model failure:
            # geocoding is complete, but the REQUIRED weather source has
            # not been called. The host cannot call it on the model's behalf,
            # invent coordinates, or treat the unfinished final as correct.
            # One fixed, trusted reminder consumes an existing model turn;
            # the model must still select a valid native operation/arguments.
            if (
                evidence_reprompt_budget == 1
                and evidence_reprompts == 0
                and completed == 1
                and actual_location is not None
                and actual_weather is None
                and turns < MAX_TURNS
            ):
                evidence_reprompts += 1
                messages.append({
                    "role": "user",
                    "content": (
                        "The required current-weather source has not been "
                        "called yet. Do not answer or invent a temperature. "
                        "Use the listed current-weather tool with the exact "
                        "latitude and longitude already returned by the "
                        "verified location tool. Then answer only from the "
                        "verified weather observation."
                    ),
                })
                continue
            reason = "completed_final" if completed == 2 else "premature_final"
            if completed == 2 and actual_weather is not None:
                correctly_ended = _matches_weather_final(payload, actual_weather)
                if not correctly_ended:
                    final_failure_kind = _weather_final_failure_kind(
                        payload, actual_weather,
                    )
                    if final_failure_kind is None:
                        raise ValueError("inconsistent strict source final diagnosis")
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

        before_http = geocode.http_attempts + weather.http_attempts
        before_verified = geocode.calls + weather.calls
        try:
            # This is the ALREADY EXISTING trusted planner, auth gate,
            # read-only RegistryExecutor and output projection.
            observation = await execute_scoped_host_call(
                view, selected_route_ids=list(offered),
                route_id=route, arguments=arguments,
                host_required_output_fields=(
                    ("latitude", "longitude") if route == ROUTES[0]
                    else ("time", "temperature_2m", "temperature_unit")
                ),
            )
        except (PolicyViolationError, ValueError, RuntimeError) as exc:
            # Only the bounded exception FAMILY is public. No provider body,
            # URL, host exception message, coordinates or security details.
            # The scoped host wraps provider, planner AND authorization
            # exceptions as PolicyViolationError; the class does NOT reveal
            # the root cause or prove a real policy breach.
            host_exception_family = (
                "scoped_boundary_denial" if isinstance(exc, PolicyViolationError)
                else "value_error" if isinstance(exc, ValueError)
                else "runtime_error"
            )
            after_http = geocode.http_attempts + weather.http_attempts
            after_verified = geocode.calls + weather.calls
            host_failure_after_http_attempt = after_http > after_verified
            # Host-owned public fixed-source diagnostic only. No raw HTTP
            # body, coordinates, provider exception, route secret or policy.
            if any(
                inv.last_failure_stage is not None
                and inv.last_failure_stage not in inv.FAILURE_STAGES
                for inv in (geocode, weather)
            ):
                raise ValueError("invalid trusted source failure-stage receipt") from None
            source_stages = [
                f"geocode_{geocode.last_failure_stage}"
                if geocode.last_failure_stage is not None else None,
                f"forecast_{weather.last_failure_stage}"
                if weather.last_failure_stage is not None else None,
            ]
            source_stages = [stage for stage in source_stages if stage is not None]
            if len(source_stages) > 1:
                raise ValueError("ambiguous simultaneous trusted source failures") from None
            if source_stages:
                trusted_failure_stage = source_stages[0]
                transport_kinds = [
                    inv.last_transport_error_kind
                    for inv in (geocode, weather)
                    if inv.last_transport_error_kind is not None
                ]
                if len(transport_kinds) > 1:
                    raise ValueError("ambiguous original source transport failures") from None
                trusted_transport_error_kind = (
                    transport_kinds[0] if transport_kinds else None
                )
            elif after_http == before_http:
                trusted_failure_stage = "host_boundary_without_new_http"
            elif after_verified > before_verified:
                trusted_failure_stage = "host_boundary_after_validated_source"
            else:
                trusted_failure_stage = "unclassified_after_http_attempt"
            reason = "host_or_native_source_denied"
            break
        if (
            type(observation) is not dict
            or observation.get("status") != "ok"
        ):
            reason = "non_ok_native_observation"
            break

        completed += 1
        executed_routes.append(route)
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
                # Presence-only source projection telemetry, not values.
                lat = int(type(observation.get("latitude")) in (int, float))
                lon = int(type(observation.get("longitude")) in (int, float))
                reason = f"invalid_first_source_observation_lat{lat}_lon{lon}"
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

    # A provider can verify a response, then the host may still reject
    # projection/policy before publishing its observation to the model.
    # This is one FAILED agent step, not a model-completed step and not an
    # invalid aggregate. Never allow a concealed multi-call surplus.
    verified = geocode.calls + weather.calls
    if (
        completed > verified
        or verified - completed > 1
        or (verified != completed and reason != "host_or_native_source_denied")
    ):
        raise ValueError("native provider verification/host observation mismatch")
    if (
        not 0 <= geocode.calls <= geocode.http_attempts <= 1 + transport_retry_budget
        or not 0 <= weather.calls <= weather.http_attempts <= 1 + transport_retry_budget
        or (weather.http_attempts and geocode.calls != 1)
    ):
        raise ValueError("inconsistent attempted vs validated native source calls")
    result = {
        "language": language,
        "model_turns": turns,
        "attempted_model_calls": attempted,
        # `*_calls` are historic counters for *validated responses*.
        # HTTP can have been attempted even when source data is rejected.
        "real_geocoding_calls": geocode.calls,
        "real_forecast_calls": weather.calls,
        "real_geocoding_http_attempts": geocode.http_attempts,
        "real_forecast_http_attempts": weather.http_attempts,
        "host_exception_family": host_exception_family,
        "host_failure_after_http_attempt": host_failure_after_http_attempt,
        "trusted_failure_stage": trusted_failure_stage,
        "trusted_transport_error_kind": trusted_transport_error_kind,
        "model_generated_first_step_complete": completed >= 1,
        "model_generated_two_step_complete": completed == 2,
        "strict_final_answer_correct": correctly_ended,
        "trusted_final_validation_failure_kind": final_failure_kind,
        "full_task_complete": completed == 2 and correctly_ended,
        "termination_reason": reason,
        "model_generation_ms": round(total_model_ms, 1),
        "original_provider_e1": True,
        "independent_e2_qualified": False,
    }
    if evidence_reprompt_budget:
        # Deliberately absent in default E1 results: no schema/metric drift.
        # Only a count, never raw prompt, output, coordinates or source text.
        result["host_evidence_reprompts"] = evidence_reprompts
    # Only the in-process paired comparator can inspect original source data
    # for arm-to-arm drift. No source values or hashes enter public metrics.
    if _private_source_observations is not None and actual_weather is not None:
        _private_source_observations.append(dict(actual_weather))
    return result


async def compare_graph_native_e1(
    agent: Any, client: httpx.AsyncClient, *,
    host_concept_catalog: NativeConceptCatalog | None = None,
    approved_host_roots: frozenset[str] = frozenset(),
    documented_noncommercial_e1: bool = False,
) -> dict[str, Any]:
    """Paired original-source E1, *not* a fixture score or independent E2.

    Refuses to make even baseline provider calls when a legitimate common G5
    cohort cannot be established. A blocked arm has no success denominator.
    """
    source_kwargs = ({"documented_noncommercial_e1": True}
                     if documented_noncommercial_e1 else {})
    before, _, _ = build_live_router(client, **source_kwargs)
    after, _, _ = build_live_router(client, **source_kwargs)
    first_receipt = _native_source_receipt(before)
    safe_base: dict[str, Any] = {
        "study": "REAL_QWEN_NATIVE_G5_PAIRED_E1_DEV",
        "arms": G5_COMPARISON_ARMS,
        "requested_k": 5,
        "model_id": MODEL_NAME,
        "model_revision": MODEL_REVISION,
        "independently_authored_private_e2": False,
        "release_qualified": False,
        "task_success_rate": None,
    }
    if first_receipt != _native_source_receipt(after):
        return {**safe_base, "status": "INCOMPARABLE_SOURCE_DRIFT", "outcomes": ()}
    if any(_qualified_g5_selector(
        before, USER_REQUESTS[language], catalog=host_concept_catalog,
        approved_host_roots=approved_host_roots,
    ) is None for language, _, _ in CASES):
        return {**safe_base, "status": "BLOCKED_SOURCE_SEMANTICS", "outcomes": ()}
    if not callable(getattr(agent, "generate", None)):
        return {**safe_base, "status": "BLOCKED_MODEL_RUNTIME", "outcomes": ()}

    outcomes: list[dict[str, Any]] = []
    for position, (language, city, country) in enumerate(CASES):
        # Rotate experiment ordering to limit systematic live-time drift.
        arms = G5_COMPARISON_ARMS[position:] + G5_COMPARISON_ARMS[:position]
        private_weather: list[dict[str, Any]] = []
        for arm in arms:
            current, _, _ = build_live_router(client, **source_kwargs)
            if _native_source_receipt(current) != first_receipt:
                return {**safe_base, "status": "INCOMPARABLE_SOURCE_DRIFT", "outcomes": ()}
            row = await evaluate_one(
                agent, client, language=language, city=city, country=country,
                menu_mode=arm, host_concept_catalog=host_concept_catalog,
                approved_host_roots=approved_host_roots,
                documented_noncommercial_e1=documented_noncommercial_e1,
                _private_source_observations=private_weather,
            )
            current, _, _ = build_live_router(client, **source_kwargs)
            if _native_source_receipt(current) != first_receipt:
                return {**safe_base, "status": "INCOMPARABLE_SOURCE_DRIFT", "outcomes": ()}
            if row.get("status") == "BLOCKED_SOURCE_SEMANTICS":
                return {**safe_base, "status": "BLOCKED_SOURCE_SEMANTICS", "outcomes": ()}
            outcomes.append({"condition": arm, **row})
        if len(private_weather) >= 2 and any(
            observation != private_weather[0] for observation in private_weather[1:]
        ):
            return {**safe_base, "status": "INCOMPARABLE_SOURCE_DRIFT", "outcomes": ()}
    return {
        **safe_base,
        "status": "E1_MEASURED_DEV_NOT_E2",
        "outcomes": outcomes,
        "task_success_rate": {
            arm: sum(row["full_task_complete"] for row in outcomes
                     if row["condition"] == arm) / len(CASES)
            for arm in G5_COMPARISON_ARMS
        },
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
        # Backward-compatible legacy counter: VALIDATED response calls only.
        "total_real_source_calls": sum(
            x["real_geocoding_calls"] + x["real_forecast_calls"] for x in outcomes
        ),
        "total_real_http_attempts": sum(
            x["real_geocoding_http_attempts"] + x["real_forecast_http_attempts"]
            for x in outcomes
        ),
        "legacy_call_counter_measures_validated_responses_only": True,
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


async def real_cpu_graph_compare(
    *, host_concept_catalog: NativeConceptCatalog | None = None,
    approved_host_roots: frozenset[str] = frozenset(),
    documented_noncommercial_e1: bool = False,
) -> dict[str, Any]:
    """Gate external/model effects behind independently attested source intake.

    In this repository's current Open-Meteo E1 source the gate is blocked,
    so no model weights are loaded and no provider requests are attempted.
    """
    async with httpx.AsyncClient(
        timeout=httpx.Timeout(20.0), follow_redirects=False,
    ) as client:
        optin_kwargs = ({"documented_noncommercial_e1": True}
                        if documented_noncommercial_e1 else {})
        preflight = await compare_graph_native_e1(
            None, client, host_concept_catalog=host_concept_catalog,
            approved_host_roots=approved_host_roots,
            **optin_kwargs,
        )
        if preflight["status"] != "BLOCKED_MODEL_RUNTIME":
            return preflight
        # An independently qualified source may proceed ONLY with the pinned
        # model already present locally. Force offline loading so this flag
        # can never trigger a surprising weight download.
        from scripts.agent_utility_v7_dev_agent import LocalQwenAgent

        previous = {
            key: os.environ.get(key)
            for key in ("HF_HUB_OFFLINE", "TRANSFORMERS_OFFLINE")
        }
        try:
            os.environ["HF_HUB_OFFLINE"] = "1"
            os.environ["TRANSFORMERS_OFFLINE"] = "1"
            try:
                agent = LocalQwenAgent()
            except (ImportError, OSError, RuntimeError, ValueError):
                return preflight
        finally:
            for key, value in previous.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value
        return await compare_graph_native_e1(
            agent, client, host_concept_catalog=host_concept_catalog,
            approved_host_roots=approved_host_roots,
            **optin_kwargs,
        )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument(
        "--compare-graph", action="store_true",
        help="run source-native G5 eligibility gate and paired E1 if qualified",
    )
    parser.add_argument(
        "--host-catalog", type=Path,
        help="owner-reviewed NativeConceptCatalog JSON, only for --compare-graph",
    )
    parser.add_argument(
        "--approved-host-root", action="append", default=[],
        help="explicit owner-approved parameterized native root route ID",
    )
    parser.add_argument(
        "--documented-noncommercial-e1", action="store_true",
        help="explicitly select reviewed Open-Meteo free/non-commercial source contracts",
    )
    args = parser.parse_args()
    if not args.compare_graph and (
        args.host_catalog or args.approved_host_root or args.documented_noncommercial_e1
    ):
        parser.error("host source qualifications require --compare-graph")
    if args.documented_noncommercial_e1 and (
        args.host_catalog or args.approved_host_root
    ):
        parser.error("documented E1 contract cannot override its pinned catalog/root")
    catalog = (
        documented_open_meteo_e1_catalog() if args.documented_noncommercial_e1 else
        NativeConceptCatalog.model_validate_json(
            args.host_catalog.read_text(encoding="utf-8"), strict=True,
        ) if args.host_catalog is not None else None
    )
    roots = (frozenset({ROUTES[0]}) if args.documented_noncommercial_e1
             else frozenset(args.approved_host_root))
    source = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True,
        capture_output=True, timeout=10, check=True,
    ).stdout.strip()
    result = asyncio.run(
        real_cpu_graph_compare(
            host_concept_catalog=catalog,
            approved_host_roots=roots,
            documented_noncommercial_e1=args.documented_noncommercial_e1,
        ) if args.compare_graph else real_cpu_run()
    )
    result["source_revision"] = source
    result["hardware"] = platform.platform()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    if args.compare_graph:
        print(json.dumps({
            "study": result["study"], "status": result["status"],
            "task_success_rate": result["task_success_rate"],
            "independently_authored_private_e2": False,
        }, ensure_ascii=False))
    else:
        print(json.dumps({
            "study": result["study"],
            "total_real_source_calls": result["total_real_source_calls"],
            "total_real_http_attempts": result["total_real_http_attempts"],
            "model_generated_full_task_successes": result["model_generated_full_task_successes"],
            "by_language": {
                row["language"]: {
                    "real_geocoding_calls": row["real_geocoding_calls"],
                    "real_forecast_calls": row["real_forecast_calls"],
                    "real_geocoding_http_attempts": row["real_geocoding_http_attempts"],
                    "real_forecast_http_attempts": row["real_forecast_http_attempts"],
                    "host_exception_family": row["host_exception_family"],
                    "full_task_complete": row["full_task_complete"],
                    "termination_reason": row["termination_reason"],
                }
                for row in result["outcomes"]
            },
            "independently_authored_private_e2": False,
        }, ensure_ascii=False))


if __name__ == "__main__":
    main()
