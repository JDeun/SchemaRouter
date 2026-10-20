"""Opt-in long-lived Open-Meteo E1 host reference, health-aware across tasks.

The caller owns the HTTP client AND trusted read-only probe callbacks.
No guessed live health endpoint, no Qwen model, no source gold, no E2, no
provider claims from deterministic tests. Host-orchestrated native two-hop
read-only path through the canonical planner/RegistryExecutor.
"""
from __future__ import annotations

import time
from collections.abc import Mapping
from typing import Any

import httpx

from schemarouter import PolicyViolationError, PrincipalContext
from schemarouter.health import HealthProbe
from scripts.research_live_health_model_menu_e1 import (
    GEO,
    WEATHER,
    build_health_aware_router,
    capture_health_scoped_model_menu,
    execute_health_scoped_host_call,
)

_ALLOWED_STATES = frozenset({
    "success", "inputs_missing", "temporary_unavailable",
    "execution_failure", "invalid_source_observation",
})


class LongLivedOpenMeteoHealthSessionE1:
    """One shared router, original bound invokers, probe lifecycle and cooldown.

    This is a *host-selected* read-only two-hop source integration witness,
    not a model-selected routing benchmark. No output contains source values.
    """

    def __init__(
        self,
        client: httpx.AsyncClient,
        *,
        trusted_health_probes: Mapping[str, HealthProbe],
        probe_interval_seconds: float = 5.0,
        probe_timeout_seconds: float = 2.0,
        max_probe_age_seconds: float = 60.0,
    ) -> None:
        if (
            type(probe_interval_seconds) not in (int, float)
            or isinstance(probe_interval_seconds, bool)
            or not 0.01 <= probe_interval_seconds <= 60
            or type(probe_timeout_seconds) not in (int, float)
            or isinstance(probe_timeout_seconds, bool)
            or not 0.01 <= probe_timeout_seconds <= 10
            or type(max_probe_age_seconds) not in (int, float)
            or isinstance(max_probe_age_seconds, bool)
            or not 0.1 <= max_probe_age_seconds <= 3600
        ):
            raise ValueError("bounded explicit probe timing required")
        self.router = build_health_aware_router(
            client, trusted_health_probes=trusted_health_probes,
        )
        self._interval = float(probe_interval_seconds)
        self._timeout = float(probe_timeout_seconds)
        self._age = float(max_probe_age_seconds)
        self._started = False
        self._closed = False

    async def __aenter__(self) -> LongLivedOpenMeteoHealthSessionE1:
        if self._started or self._closed:
            raise RuntimeError("health session is already running or closed")
        # Boot with explicit host probes; otherwise tool status is UNKNOWN.
        await self.router.check_health_once()
        await self.router.start_health_monitor(
            interval_seconds=self._interval,
            probe_timeout_seconds=self._timeout,
            max_concurrency=2,
        )
        self._started = True
        return self

    async def __aexit__(
        self, exc_type: type[BaseException] | None,
        exc: BaseException | None, traceback: Any | None,
    ) -> bool:
        del exc_type, exc, traceback
        self._closed = True
        await self.router.aclose()
        # HTTP transport lifecycle still belongs to the host caller.
        return False

    def _menu(
        self, query: str, principal: PrincipalContext,
        inputs: dict[str, Any], *, observed: dict[str, Any] | None = None,
        executed: tuple[str, ...] = (),
    ):
        return capture_health_scoped_model_menu(
            self.router, query, principal=principal,
            host_request_inputs=inputs,
            prior_public_observation=observed,
            executed_route_ids=executed,
            max_probe_age_seconds=self._age,
        )

    def _result(
        self, stage: str, started: float, completed: int,
        first_count: int, second_count: int = 0,
    ) -> dict[str, Any]:
        if stage not in _ALLOWED_STATES:
            raise ValueError("unknown safe operational stage")
        return {
            "status": stage,
            "successful_native_calls": completed,
            "initial_model_visible_routes": first_count,
            "dependent_model_visible_routes": second_count,
            "elapsed_ms": round((time.perf_counter() - started) * 1000, 3),
            "real_provider_success_qualified": False,
            "independent_e2_qualified": False,
            "model_selected_routes": False,
            "health_monitor_running": self.router.health_monitor.running,
        }

    async def get_current_weather(
        self, *, query: str, city: str, language: str,
        country: str, principal: PrincipalContext,
    ) -> dict[str, Any]:
        """Run two native source calls; only aggregate sanitized receipt escapes."""
        if not self._started or self._closed:
            raise RuntimeError("long-lived health session must be active")
        if (
            type(query) is not str or not query.strip()
            or type(city) is not str or not 2 <= len(city) <= 80
            or language not in ("en", "ko", "ja")
            or country not in ("KR", "JP")
            or not isinstance(principal, PrincipalContext)
        ):
            raise ValueError("trusted bounded host request required")
        start = time.perf_counter()
        inputs: dict[str, Any] = {
            "name": city, "language": language, "country_code": country,
        }
        first = self._menu(query, principal, inputs)
        if GEO not in first.route_ids:
            return self._result(first.status, start, 0, len(first.route_ids))
        try:
            location = await execute_health_scoped_host_call(
                first, route_id=GEO, arguments=inputs,
                host_required_output_fields=(
                    "location_id", "latitude", "longitude", "country_code",
                ),
            )
        except PolicyViolationError:
            refreshed = self._menu(query, principal, inputs)
            stage = (
                "temporary_unavailable"
                if refreshed.status == "temporary_unavailable"
                else "execution_failure"
            )
            return self._result(stage, start, 0, len(first.route_ids))

        if (
            location.get("status") != "ok"
            or location.get("country_code") != country
            or type(location.get("latitude")) not in (int, float)
            or type(location.get("longitude")) not in (int, float)
        ):
            return self._result(
                "invalid_source_observation", start, 1, len(first.route_ids),
            )
        second = self._menu(
            query, principal, inputs, observed=location, executed=(GEO,),
        )
        if WEATHER not in second.route_ids:
            return self._result(
                second.status, start, 1, len(first.route_ids),
                len(second.route_ids),
            )
        try:
            observation = await execute_health_scoped_host_call(
                second, route_id=WEATHER,
                arguments={
                    "latitude": location["latitude"],
                    "longitude": location["longitude"],
                },
                host_required_output_fields=(
                    "time", "temperature_2m", "temperature_unit",
                ),
            )
        except PolicyViolationError:
            refreshed = self._menu(
                query, principal, inputs, observed=location, executed=(GEO,),
            )
            stage = (
                "temporary_unavailable"
                if refreshed.status == "temporary_unavailable"
                else "execution_failure"
            )
            return self._result(
                stage, start, 1, len(first.route_ids), len(second.route_ids),
            )
        if (
            observation.get("status") != "ok"
            or observation.get("temperature_unit") != "°C"
            or type(observation.get("temperature_2m")) not in (int, float)
            or type(observation.get("time")) is not str
        ):
            return self._result(
                "invalid_source_observation", start, 2,
                len(first.route_ids), len(second.route_ids),
            )
        return self._result(
            "success", start, 2,
            len(first.route_ids), len(second.route_ids),
        )
