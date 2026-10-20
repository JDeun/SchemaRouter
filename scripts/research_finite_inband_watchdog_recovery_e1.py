"""Offline E1: existing background health monitor checks outage then recovery.

Uses injected HTTPX transport ONLY. No default network client is offered,
no model-selected tool execution, no provider uptime or E2 claim.
"""
from __future__ import annotations

import asyncio
import time
from collections.abc import Callable

import httpx

from scripts.research_live_health_model_menu_e1 import (
    GEO,
    WEATHER,
    build_health_aware_router,
    capture_health_scoped_model_menu,
)
from scripts.research_long_lived_real_open_meteo_e1 import CappedOpenMeteoTransport
from scripts.research_operator_approved_inband_canary_e1 import InBandCanaryCallbacksE1
from scripts.research_real_qwen_open_meteo_two_hop_e1 import PRINCIPAL, USER_REQUESTS


async def observe_finite_background_recovery(
    transport_factory: Callable[[], httpx.AsyncBaseTransport],
    *,
    operator_approved: bool,
    interval_seconds: float = 0.35,
) -> dict[str, object]:
    if operator_approved is not True:
        raise ValueError("explicit operator permission required")
    if type(interval_seconds) not in (float, int) or not 0.15 <= interval_seconds <= 3:
        raise ValueError("bounded interval required")
    transport = CappedOpenMeteoTransport(transport_factory(), max_requests=6)
    async with httpx.AsyncClient(transport=transport, follow_redirects=False) as client:
        probes = InBandCanaryCallbacksE1(
            client, approved_public_business_canaries=True, attempts_per_route=2,
        )
        router = build_health_aware_router(
            client, trusted_health_probes={GEO: probes.geocoding, WEATHER: probes.forecast},
        )
        observations = []
        started = time.perf_counter()
        try:
            await router.start_health_monitor(
                interval_seconds=float(interval_seconds),
                probe_timeout_seconds=2,
                max_concurrency=2,
            )
            for desired in ("unhealthy", "healthy"):
                async def await_status(desired_status: str) -> None:
                    while True:
                        snapshots = {
                            f"{s.tool}.{s.endpoint}": s for s in router.health_snapshots()
                        }
                        if (
                            snapshots.get(GEO) is not None
                            and snapshots[GEO].status == desired_status
                            and snapshots.get(WEATHER) is not None
                            and snapshots[WEATHER].status == "healthy"
                        ):
                            return
                        await asyncio.sleep(0.01)
                await asyncio.wait_for(await_status(desired), timeout=4.0)
                menu = capture_health_scoped_model_menu(
                    router, USER_REQUESTS["en"], principal=PRINCIPAL,
                    host_request_inputs={"name": "Seoul", "language": "en", "country_code": "KR"},
                )
                observations.append({
                    "health": desired,
                    "visible_geocoder": GEO in menu.route_ids,
                    "menu_status": menu.status,
                })
        finally:
            await router.aclose()
    if (
        probes.counts[GEO] > 2 or probes.counts[WEATHER] > 2
        or transport.total_requests > 6
    ):
        raise ValueError("canary request cap exceeded")
    return {
        "observations": observations,
        "inband_get_attempts": transport.total_requests,
        "probe_attempts": {
            "geocoding": probes.counts[GEO], "forecast": probes.counts[WEATHER],
        },
        "elapsed_ms": round((time.perf_counter() - started) * 1000, 3),
        "external_network_qualified": False,
        "continuous_production_monitoring_qualified": False,
        "model_selected_routes": False,
        "independent_e2_qualified": False,
        "production_default_changed": False,
    }
