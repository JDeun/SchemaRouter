"""Explicitly approved, finite IN-BAND Open-Meteo canary via original routes.

The actual public geocoding/forecast GET endpoints serve as bounded read-only
canaries. This is NOT an independently published health endpoint, a service
uptime guarantee, periodic production monitoring, Qwen routing or E2.
No external request is possible until the operator explicitly opts in.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import time
from collections import Counter
from collections.abc import Callable
from pathlib import Path
from typing import Any

import httpx

from schemarouter import PolicyViolationError
from scripts.research_durable_inband_probe_lease_e1 import DurableInBandProbeLeaseE1
from scripts.research_live_health_model_menu_e1 import (
    GEO,
    WEATHER,
    build_health_aware_router,
    capture_health_scoped_model_menu,
    execute_health_scoped_host_call,
)
from scripts.research_long_lived_real_open_meteo_e1 import (
    CappedOpenMeteoTransport,
)
from scripts.research_open_meteo_live_two_hop_e1 import OpenMeteoBoundInvoker
from scripts.research_real_qwen_open_meteo_two_hop_e1 import (
    PRINCIPAL,
    USER_REQUESTS,
)

_ROUTES = (GEO, WEATHER)
_MAX_GET_ATTEMPTS = 6
# The canary input is fixed by the operator-approved research code, never a
# query supplied by the model or runtime tool discovery.
_GEO_ARGS = {"name": "Seoul", "language": "en", "country_code": "KR"}
_FORECAST_ARGS = {"latitude": 37.5665, "longitude": 126.9780}


class InBandCanaryCallbacksE1:
    """Only one explicitly budgeted source-native callback per route per run.

    A second attempt returns False (fail closed), never a cached Healthy value
    with a fictitious newer timestamp. No rerouting or provider fallback.
    """

    def __init__(
        self, client: httpx.AsyncClient, *,
        approved_public_business_canaries: bool,
        attempts_per_route: int = 1,
    ) -> None:
        if approved_public_business_canaries is not True:
            raise ValueError("explicit operator permission for in-band GET canaries required")
        if type(attempts_per_route) is not int or not 1 <= attempts_per_route <= 2:
            raise ValueError("bounded per-route canary attempt budget required")
        self._invokers = {
            GEO: (OpenMeteoBoundInvoker(client, source="geocode"), "search", _GEO_ARGS),
            WEATHER: (OpenMeteoBoundInvoker(client, source="forecast"), "current", _FORECAST_ARGS),
        }
        self._max = attempts_per_route
        self.counts: Counter[str] = Counter()

    async def _check(self, route: str) -> bool:
        # No LLM/model text, user request, source private payload or third
        # party URL can choose the transport. Original source validates schema.
        if route not in self._invokers:
            return False
        if self.counts[route] >= self._max:
            return False
        self.counts[route] += 1
        invoker, endpoint, args = self._invokers[route]
        try:
            result = await invoker(endpoint, args)
        except (httpx.RequestError, httpx.HTTPStatusError, ValueError, RuntimeError):
            return False
        return type(result) is dict

    async def geocoding(self) -> bool:
        return await self._check(GEO)

    async def forecast(self) -> bool:
        return await self._check(WEATHER)


async def observe_inband_canary_once(
    *,
    approved_public_business_canaries: bool,
    transport_factory: Callable[[], httpx.AsyncBaseTransport] = httpx.AsyncHTTPTransport,
    existing_shared_lease_file: Path | None = None,
) -> dict[str, Any]:
    """One background monitor sweep + (if healthy) one original two-hop task.

    Absolute cap six outbound GET attempts, normally four (two canaries, two
    business requests). A 60s monitor interval prevents aggressive polling.
    Never represent this one-shot as 24/7 monitoring or a provider-health API.
    """
    if approved_public_business_canaries is not True:
        raise ValueError("explicit operator permission for public in-band GETs required")
    lease = (
        DurableInBandProbeLeaseE1(existing_shared_lease_file)
        if existing_shared_lease_file is not None else None
    )
    transport = CappedOpenMeteoTransport(
        transport_factory(), max_requests=_MAX_GET_ATTEMPTS,
    )
    start = time.perf_counter()
    async with httpx.AsyncClient(
        transport=transport,
        timeout=httpx.Timeout(5.0, connect=3.0),
        follow_redirects=False,
    ) as client:
        canaries = InBandCanaryCallbacksE1(
            client, approved_public_business_canaries=True,
        )
        probes = {
            GEO: canaries.geocoding,
            WEATHER: canaries.forecast,
        }
        if lease is not None:
            # Existing, explicit, nonrenewable allowance. The E1 runner
            # must NEVER create a new DB or refresh permission on start.
            probes = {
                GEO: lease.wrap_probe(GEO, canaries.geocoding),
                WEATHER: lease.wrap_probe(WEATHER, canaries.forecast),
            }
        router = build_health_aware_router(
            client,
            trusted_health_probes=probes,
            transport_retry_budget=0,
        )
        status = "probe_bootstrap_timeout"
        successful_native_calls = 0
        try:
            # Do NOT call check_health_once and then start_monitor: the
            # immediately scheduled first background tick would double spend.
            await router.start_health_monitor(
                interval_seconds=60.0,
                probe_timeout_seconds=4.0,
                max_concurrency=2,
            )

            async def await_first_sweep() -> None:
                for _ in range(300):
                    snapshots = {
                        f"{r.tool}.{r.endpoint}": r
                        for r in router.health_snapshots()
                    }
                    if all(
                        key in snapshots and snapshots[key].status != "unknown"
                        for key in _ROUTES
                    ):
                        return
                    await asyncio.sleep(0.02)
                raise TimeoutError("bounded first actual canary sweep unfinished")

            try:
                await asyncio.wait_for(await_first_sweep(), timeout=9.0)
            except TimeoutError:
                status = "probe_bootstrap_timeout"
            else:
                statuses = {
                    f"{r.tool}.{r.endpoint}": r.status
                    for r in router.health_snapshots()
                }
                if all(statuses.get(key) == "healthy" for key in _ROUTES):
                    query = USER_REQUESTS["en"]
                    first = capture_health_scoped_model_menu(
                        router, query, principal=PRINCIPAL,
                        host_request_inputs=dict(_GEO_ARGS),
                        max_probe_age_seconds=30,
                    )
                    if GEO in first.route_ids:
                        try:
                            geo = await execute_health_scoped_host_call(
                                first, route_id=GEO, arguments=dict(_GEO_ARGS),
                                host_required_output_fields=(
                                    "location_id", "latitude", "longitude", "country_code",
                                ),
                            )
                            if geo.get("status") != "ok":
                                raise ValueError("native source projection unavailable")
                            successful_native_calls = 1
                            second = capture_health_scoped_model_menu(
                                router, query, principal=PRINCIPAL,
                                host_request_inputs=dict(_GEO_ARGS),
                                prior_public_observation=geo,
                                executed_route_ids=(GEO,),
                                max_probe_age_seconds=30,
                            )
                            if WEATHER not in second.route_ids:
                                status = "source_now_unavailable"
                            else:
                                weather = await execute_health_scoped_host_call(
                                    second, route_id=WEATHER,
                                    arguments={
                                        "latitude": geo["latitude"],
                                        "longitude": geo["longitude"],
                                    },
                                    host_required_output_fields=(
                                        "time", "temperature_2m", "temperature_unit",
                                    ),
                                )
                                if weather.get("status") != "ok":
                                    raise ValueError("native weather projection unavailable")
                                successful_native_calls = 2
                                status = "success"
                        except (PolicyViolationError, httpx.RequestError,
                                httpx.HTTPStatusError, ValueError, RuntimeError):
                            status = "source_execution_rejected"
                    else:
                        status = "source_now_unavailable"
                else:
                    status = "inband_canary_unhealthy"
        finally:
            await router.aclose()

    counts = transport.counts
    canary_counts = {
        "geocoding": canaries.counts[GEO],
        "forecast": canaries.counts[WEATHER],
    }
    total_canaries = sum(canary_counts.values())
    if total_canaries > 2 or transport.total_requests > _MAX_GET_ATTEMPTS:
        raise RuntimeError("strict in-band canary GET budget invalidated")
    return {
        "schema_version": 1,
        "evidence_tier": "OPERATOR_APPROVED_INBAND_PUBLIC_ENDPOINT_CANARY_E1_NOT_E2",
        "status": status,
        "observed_native_calls_completed": successful_native_calls,
        "actual_https_get_attempts": transport.total_requests,
        "actual_get_attempts_by_endpoint": counts,
        "actual_inband_canary_attempts_by_endpoint": canary_counts,
        "durable_shared_lease_enabled": lease is not None,
        "durable_shared_lease_spent_by_route": (
            lease.public_counts() if lease is not None else {}
        ),
        "canary_uses_actual_business_endpoint": True,
        "independent_dedicated_health_endpoint_verified": False,
        "long_term_availability_verified": False,
        "model_selected_routes": False,
        "model_generations": 0,
        "independent_e2_qualified": False,
        "production_default_changed": False,
        "external_business_requests_maximum": _MAX_GET_ATTEMPTS,
        "elapsed_ms": round((time.perf_counter() - start) * 1000, 3),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--operator-approves-inband-business-gets", action="store_true")
    parser.add_argument("--existing-shared-lease-file", type=Path, default=None)
    args = parser.parse_args()
    outcome = asyncio.run(observe_inband_canary_once(
        approved_public_business_canaries=args.operator_approves_inband_business_gets,
        existing_shared_lease_file=args.existing_shared_lease_file,
    ))
    print(json.dumps(outcome, sort_keys=True, allow_nan=False))


if __name__ == "__main__":
    main()
