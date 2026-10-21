"""Opt-in, bounded live Open-Meteo GET observation with one E1 router.

This is REAL business-endpoint source execution, but host health probes are
explicit SIMULATED test callbacks. It is NOT verified provider liveness,
continuous real watchdog qualification, Qwen routing or independent E2.
"""
from __future__ import annotations

import argparse
import asyncio
import inspect
import json
import time
from collections import Counter
from collections.abc import Awaitable, Callable
from typing import Any

import httpx

from scripts.research_live_health_model_menu_e1 import GEO, WEATHER
from scripts.research_long_lived_health_session_e1 import (
    LongLivedOpenMeteoHealthSessionE1,
)
from scripts.research_real_qwen_open_meteo_two_hop_e1 import (
    PRINCIPAL,
    USER_REQUESTS,
)

_ALLOWED = {
    ("geocoding-api.open-meteo.com", "/v1/search"): frozenset({
        "name", "language", "countryCode", "count", "format",
    }),
    ("api.open-meteo.com", "/v1/forecast"): frozenset({
        "latitude", "longitude", "current", "timezone",
    }),
}
_CASES = (
    ("en", "Seoul", "KR"),
    ("ko", "Seoul", "KR"),
    ("ja", "Tokyo", "JP"),
)
_STATUSES = {
    "success", "inputs_missing", "temporary_unavailable",
    "execution_failure", "invalid_source_observation", "host_deadline",
}


class CappedOpenMeteoTransport(httpx.AsyncBaseTransport):
    """Exactly named public GETs only; no HTTP redirects, secrets or retry."""

    def __init__(
        self, delegate: httpx.AsyncBaseTransport, *, max_requests: int = 6,
        source_admission_check: Callable[[], bool | Awaitable[bool]] | None = None,
    ) -> None:
        if not isinstance(delegate, httpx.AsyncBaseTransport):
            raise ValueError("approved async transport required")
        if type(max_requests) is not int or not 1 <= max_requests <= 6:
            raise ValueError("fixed maximum live GET budget must be 1-6")
        if source_admission_check is not None and not callable(source_admission_check):
            raise ValueError("trusted bounded source admission callback required")
        self._delegate = delegate
        self._source_admission_check = source_admission_check
        self._maximum = max_requests
        self._total = 0
        self._per_host: Counter[str] = Counter()
        self._transport_timeouts = 0

    @property
    def total_requests(self) -> int:
        return self._total

    @property
    def transport_timeout_attempts(self) -> int:
        return self._transport_timeouts

    @property
    def counts(self) -> dict[str, int]:
        return {
            "geocoding": self._per_host["geocoding-api.open-meteo.com"],
            "forecast": self._per_host["api.open-meteo.com"],
        }

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        # Never allow arbitrary destinations/redirects, mutations or unbounded
        # additional third-party business requests.
        if (
            request.method != "GET"
            or request.url.scheme != "https"
            or (request.url.host, request.url.path) not in _ALLOWED
            or request.url.port not in (None, 443)
            or bool(request.url.username)
            or bool(request.url.password)
        ):
            raise RuntimeError("disallowed fixed read-only provider request")
        expected_params = _ALLOWED[(request.url.host, request.url.path)]
        actual_params = list(request.url.params.multi_items())
        if (
            len(actual_params) != len(expected_params)
            or {name for name, _ in actual_params} != expected_params
        ):
            raise RuntimeError("disallowed provider query parameter set")
        if self._total >= self._maximum:
            raise RuntimeError("fixed provider observation budget exhausted")
        # The optional E1 lease gate is checked AFTER the fixed source
        # allowlist and IMMEDIATELY BEFORE delegation, narrowing a race
        # with another process revoking the original operator allowance.
        # This is not atomic with a remote HTTP request: cancellation may
        # still land immediately after this check or while GET is in flight.
        if self._source_admission_check is not None:
            try:
                admitted = self._source_admission_check()
                if inspect.isawaitable(admitted):
                    admitted = await admitted
                if admitted is not True:
                    raise RuntimeError("source request approval unavailable")
            except Exception:
                # Do not leak private paths, source args or provider details.
                raise RuntimeError("source request approval unavailable") from None
        self._total += 1
        self._per_host[request.url.host] += 1
        try:
            return await self._delegate.handle_async_request(request)
        except httpx.TimeoutException:
            # Count only observed transport attempts; no raw URL, error or
            # provider payload can enter the public receipt.
            self._transport_timeouts += 1
            raise

    async def aclose(self) -> None:
        await self._delegate.aclose()


async def observe_real_source_once(
    *,
    acknowledged_readonly_business_requests: bool,
    transport_factory: Callable[[], httpx.AsyncBaseTransport] = httpx.AsyncHTTPTransport,
    max_request_seconds: float = 12.0,
) -> dict[str, Any]:
    """Bounded one-process/three-language actual source trial, no model.

    The host's probe callbacks are intentionally synthetic True; we are
    **not** claiming actual health validation by them. Actual provider GET
    outcome is observed independently via the original E1 executor.
    """
    if acknowledged_readonly_business_requests is not True:
        raise ValueError("explicit operator acknowledgement of public GET budget required")
    if type(max_request_seconds) not in (int, float) or not 2 <= max_request_seconds <= 20:
        raise ValueError("bounded observation time required")
    guarded_transport = CappedOpenMeteoTransport(transport_factory())
    reports: dict[str, dict[str, Any]] = {}
    simulated_probe_attempts: Counter[str] = Counter()
    started = time.perf_counter()

    async def simulated_geo_probe() -> bool:
        simulated_probe_attempts["geocoding"] += 1
        # Once the real source transport has failed, an unverified synthetic
        # "healthy" callback must not re-admit a further business GET.
        return guarded_transport.transport_timeout_attempts == 0

    async def simulated_forecast_probe() -> bool:
        simulated_probe_attempts["forecast"] += 1
        return guarded_transport.transport_timeout_attempts == 0
    async with httpx.AsyncClient(
        transport=guarded_transport,
        timeout=httpx.Timeout(6.0, connect=3.0),
        follow_redirects=False,
    ) as client:
        session = LongLivedOpenMeteoHealthSessionE1(
            client,
            # SIMULATED menu gate to isolate actual endpoint execution.
            # Never market these callbacks as independently validated health.
            trusted_health_probes={
                GEO: simulated_geo_probe,
                WEATHER: simulated_forecast_probe,
            },
            probe_interval_seconds=60,
            probe_timeout_seconds=2,
            max_probe_age_seconds=60,
        )
        async with session:
            identity = id(session.router)
            for lang, city, country in _CASES:
                try:
                    row = await asyncio.wait_for(
                        session.get_current_weather(
                            query=USER_REQUESTS[lang],
                            city=city, language=lang, country=country,
                            principal=PRINCIPAL,
                        ),
                        timeout=float(max_request_seconds),
                    )
                except TimeoutError:
                    row = {"status": "host_deadline", "successful_native_calls": 0}
                status = row.get("status")
                if status not in _STATUSES:
                    raise ValueError("unrecognized sanitized source outcome")
                if id(session.router) != identity:
                    raise RuntimeError("live source runner unexpectedly replaced router")
                reports[lang] = {
                    "status": status,
                    "native_calls_successful": row["successful_native_calls"],
                    "initial_model_visible_routes": row.get(
                        "initial_model_visible_routes", 0,
                    ),
                    "dependent_model_visible_routes": row.get(
                        "dependent_model_visible_routes", 0,
                    ),
                }
            if not session.router.health_monitor.running:
                raise RuntimeError("host never started existing monitor")
    out = {
        "evidence_tier": "LIVE_OPEN_METEO_BUSINESS_GETS_SIMULATED_HEALTH_E1_NOT_E2",
        "schema_version": 1,
        "languages": [x[0] for x in _CASES],
        "results": reports,
        "shared_router_across_episodes": True,
        "health_probes_are_simulated": True,
        "per_endpoint_health_independently_verified": False,
        "total_provider_http_get_attempts": guarded_transport.total_requests,
        "provider_requests_by_source": guarded_transport.counts,
        "business_get_budget": 6,
        "observation_transport": (
            "real_http" if transport_factory is httpx.AsyncHTTPTransport
            else "injected_test_transport"
        ),
        "simulated_probe_attempts_by_route": {
            "geocoding": simulated_probe_attempts["geocoding"],
            "forecast": simulated_probe_attempts["forecast"],
        },
        "transport_timeout_attempts": guarded_transport.transport_timeout_attempts,
        "host_deadline_episodes": sum(
            item["status"] == "host_deadline" for item in reports.values()
        ),
        "temporary_unavailable_episodes": sum(
            item["status"] == "temporary_unavailable" for item in reports.values()
        ),
        "observed_two_hop_success_episodes": sum(
            item["status"] == "success" and item["native_calls_successful"] == 2
            for item in reports.values()
        ),
        "fallbacks_attempted": 0,
        "external_provider_success_qualified": False,
        "independent_e2_qualified": False,
        "model_selected_routes": False,
        "llm_generations": 0,
        "production_default_changed": False,
        "elapsed_ms": round((time.perf_counter() - started) * 1000, 3),
    }
    if out["total_provider_http_get_attempts"] > 6:
        raise RuntimeError("provider GET budget exceeded")
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--acknowledge-readonly-business-gets", action="store_true")
    args = parser.parse_args()
    summary = asyncio.run(observe_real_source_once(
        acknowledged_readonly_business_requests=args.acknowledge_readonly_business_gets,
    ))
    print(json.dumps(summary, sort_keys=True, allow_nan=False))


if __name__ == "__main__":
    main()
