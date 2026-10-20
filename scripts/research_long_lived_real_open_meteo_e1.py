"""Opt-in, bounded live Open-Meteo GET observation with one E1 router.

This is REAL business-endpoint source execution, but host health probes are
explicit SIMULATED test callbacks. It is NOT verified provider liveness,
continuous real watchdog qualification, Qwen routing or independent E2.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import time
from collections import Counter
from collections.abc import Callable
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
    ("geocoding-api.open-meteo.com", "/v1/search"),
    ("api.open-meteo.com", "/v1/forecast"),
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
    ) -> None:
        if not isinstance(delegate, httpx.AsyncBaseTransport):
            raise ValueError("approved async transport required")
        if type(max_requests) is not int or not 1 <= max_requests <= 6:
            raise ValueError("fixed maximum live GET budget must be 1-6")
        self._delegate = delegate
        self._maximum = max_requests
        self._total = 0
        self._per_host: Counter[str] = Counter()

    @property
    def total_requests(self) -> int:
        return self._total

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
        ):
            raise RuntimeError("disallowed fixed read-only provider request")
        if self._total >= self._maximum:
            raise RuntimeError("fixed provider observation budget exhausted")
        self._total += 1
        self._per_host[request.url.host] += 1
        return await self._delegate.handle_async_request(request)

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
    started = time.perf_counter()
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
                GEO: lambda: True,
                WEATHER: lambda: True,
            },
            probe_interval_seconds=60,
            probe_timeout_seconds=2,
            max_probe_age_seconds=60,
        )
        async with session:
            identity = id(session.router)
            for lang, city, country in _CASES:
                try:
                    async with asyncio.timeout(float(max_request_seconds)):
                        row = await session.get_current_weather(
                            query=USER_REQUESTS[lang],
                            city=city, language=lang, country=country,
                            principal=PRINCIPAL,
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
