"""#1618: deterministic no-network actual model-visible health integration."""
from __future__ import annotations

import asyncio

import httpx
import pytest

from schemarouter import (
    AuthorizationPolicy,
    AuthorizationRule,
    DataScopeRule,
    PolicyViolationError,
    PrincipalContext,
)
from scripts.research_live_health_model_menu_e1 import (
    GEO,
    WEATHER,
    build_health_aware_router,
    capture_health_scoped_model_menu,
    execute_health_scoped_host_call,
)

ACTOR = PrincipalContext(subject="health-e1-reader", roles=("reader",))
HOST = {"name": "Seoul", "language": "en", "country_code": "KR"}
QUERY = "Current weather in Seoul from the original source"


def _transport(request: httpx.Request) -> httpx.Response:
    if request.url.path == "/v1/search":
        return httpx.Response(200, json={"results": [{
            "id": 1835848, "country_code": "KR",
            "latitude": 37.56, "longitude": 126.98,
        }]})
    if request.url.path == "/v1/forecast":
        return httpx.Response(200, json={
            "current": {"time": "2026-10-20T12:00", "temperature_2m": 18.0},
            "current_units": {"temperature_2m": "°C"},
        })
    raise AssertionError("unknown external host path")


def _menu(router, *, observation=None, executed=()):
    return capture_health_scoped_model_menu(
        router, QUERY, principal=ACTOR,
        host_request_inputs=HOST,
        prior_public_observation=observation,
        executed_route_ids=executed,
    )


@pytest.mark.asyncio
async def test_no_probe_is_unknown_and_is_not_advertised_to_model():
    async with httpx.AsyncClient(transport=httpx.MockTransport(_transport)) as client:
        router = build_health_aware_router(client, trusted_health_probes={})
        assert router.health_monitor.running is False
        menu = _menu(router)
        assert menu.status == "temporary_unavailable"
        assert menu.definitions == ()
        assert menu.route_ids == ()
        assert router.unavailable_access_paths() == ()
        await router.aclose()


@pytest.mark.asyncio
async def test_real_scoped_tool_model_menu_cooldown_then_probe_recovery():
    state = {"geo": True, "weather": True, "fail_geo": False}

    async def geocode_probe() -> bool:
        return state["geo"]

    async def forecast_probe() -> bool:
        return state["weather"]

    def transport(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/v1/search" and state["fail_geo"]:
            raise httpx.ConnectTimeout("PRIVATE_CONNECT_CANARY", request=request)
        return _transport(request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(transport)) as client:
        router = build_health_aware_router(
            client, trusted_health_probes={
                GEO: geocode_probe,
                WEATHER: forecast_probe,
            },
        )
        assert router.health_monitor.running is False
        await router.check_health_once()
        first = _menu(router)
        assert first.route_ids == (GEO,)
        assert [item["name"] for item in first.definitions] == [
            "open_meteo_geocoding__search",
        ]

        # A real, trusted *scoped host executor* call experiences a transport
        # timeout, which becomes executor-managed cooldown, not model policy.
        state["fail_geo"] = True
        with pytest.raises(PolicyViolationError):
            await execute_health_scoped_host_call(
                first,
                route_id=GEO, arguments=HOST,
                host_required_output_fields=("latitude", "longitude"),
            )
        assert ("open_meteo_geocoding", "search") in router.unavailable_access_paths()
        with pytest.raises(PolicyViolationError, match="availability changed"):
            first.assert_current()

        # Even a stale model-emitted proposal must not reuse the old
        # presentation receipt once the provider enters cooldown.
        with pytest.raises(PolicyViolationError, match="availability changed"):
            await execute_health_scoped_host_call(
                first, route_id=GEO, arguments=HOST,
                host_required_output_fields=("latitude", "longitude"),
            )

        second = _menu(router)
        assert second.route_ids == ()
        assert second.definitions == ()
        assert second.status == "temporary_unavailable"
        assert ("open_meteo_weather", "current") not in router.unavailable_access_paths()

        # Probe succeeds again: original source is eligible for the NEXT
        # model disclosure, without touching schema, input gold or policy.
        state["fail_geo"] = False
        await router.check_health_once()
        third = _menu(router)
        assert third.route_ids == (GEO,)
        assert third.status == "ready"
        assert router.unavailable_access_paths() == ()

        observation = await execute_health_scoped_host_call(
            third,
            route_id=GEO, arguments=HOST,
            host_required_output_fields=("latitude", "longitude"),
        )
        assert observation["status"] == "ok"
        followup = _menu(
            router, observation=observation, executed=(GEO,),
        )
        assert followup.route_ids == (WEATHER,)
        weather_obs = await execute_health_scoped_host_call(
            followup,
            route_id=WEATHER, arguments={
                "latitude": observation["latitude"],
                "longitude": observation["longitude"],
            },
            host_required_output_fields=(
                "time", "temperature_2m", "temperature_unit",
            ),
        )
        assert weather_obs["status"] == "ok"
        await router.aclose()


@pytest.mark.asyncio
async def test_passive_cooldown_expiry_does_not_reuse_pre_failure_health_receipt():
    """Strict model menu requires a new successful probe after transport failure."""
    failing = {"yes": True}
    async def probe() -> bool:
        return True

    def transport(request: httpx.Request) -> httpx.Response:
        if failing["yes"]:
            raise httpx.ConnectTimeout("PRIVATE_TIMEOUT", request=request)
        return _transport(request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(transport)) as client:
        router = build_health_aware_router(
            client, trusted_health_probes={GEO: probe},
        )
        router.executor.unavailable_cooldown_seconds = 0.01
        await router.check_health_once()
        menu = _menu(router)
        assert menu.route_ids == (GEO,)
        with pytest.raises(PolicyViolationError):
            await execute_health_scoped_host_call(
                menu, route_id=GEO, arguments=HOST,
                host_required_output_fields=("latitude", "longitude"),
            )
        assert _menu(router).route_ids == ()
        failing["yes"] = False
        await asyncio.sleep(0.025)
        assert router.unavailable_access_paths() == ()
        # Core passive retry eligibility returns after cooldown; the STRICT
        # model presentation still requires a NEW healthy probe receipt.
        assert _menu(router).route_ids == ()
        assert _menu(router).status == "temporary_unavailable"
        await router.check_health_once()
        assert _menu(router).route_ids == (GEO,)
        await router.aclose()


@pytest.mark.asyncio
async def test_unhealthy_forecast_only_and_strict_unknown_recovery():
    state = {"geo": True, "forecast": False}

    async def geo_probe():
        return state["geo"]

    async def weather_probe():
        return state["forecast"]

    async with httpx.AsyncClient(transport=httpx.MockTransport(_transport)) as client:
        router = build_health_aware_router(
            client, trusted_health_probes={
                GEO: geo_probe, WEATHER: weather_probe,
            },
        )
        await router.check_health_once()
        assert _menu(router).route_ids == (GEO,)
        assert ("open_meteo_weather", "current") in router.unavailable_access_paths()
        state["forecast"] = True
        await router.check_health_once()
        assert ("open_meteo_weather", "current") not in router.unavailable_access_paths()
        await router.aclose()


@pytest.mark.asyncio
async def test_not_every_http_failure_creates_health_cooldown():
    cases = (401, 404, 422)
    for status in cases:
        def transport(
            request: httpx.Request, *, status_code: int = status,
        ) -> httpx.Response:
            return httpx.Response(
                status_code, json={"error": "PRIVATE_CREDENTIAL_CANARY"},
            )

        async with httpx.AsyncClient(transport=httpx.MockTransport(transport)) as client:
            router = build_health_aware_router(
                client, trusted_health_probes={GEO: lambda: True},
            )
            await router.check_health_once()
            menu = _menu(router)
            with pytest.raises(PolicyViolationError):
                await execute_health_scoped_host_call(
                    menu,
                    route_id=GEO, arguments=HOST,
                    host_required_output_fields=("latitude", "longitude"),
                )
            assert router.unavailable_access_paths() == ()
            assert _menu(router).route_ids == (GEO,)
            await router.aclose()


@pytest.mark.asyncio
@pytest.mark.parametrize("http_status", (429, 500, 503))
async def test_only_trusted_transient_status_marks_path_temporarily_unavailable(
    http_status,
):
    async def probe() -> bool:
        return True

    async with httpx.AsyncClient(transport=httpx.MockTransport(
        lambda request: httpx.Response(http_status, json={"error": "unavailable"}),
    )) as client:
        router = build_health_aware_router(
            client, trusted_health_probes={GEO: probe},
        )
        await router.check_health_once()
        menu = _menu(router)
        with pytest.raises(PolicyViolationError):
            await execute_health_scoped_host_call(
                menu,
                route_id=GEO, arguments=HOST,
                host_required_output_fields=("latitude", "longitude"),
            )
        assert _menu(router).status == "temporary_unavailable"
        assert ("open_meteo_geocoding", "search") in router.unavailable_access_paths()
        await router.aclose()


@pytest.mark.asyncio
async def test_newer_healthy_background_probe_does_not_abort_valid_model_tool_receipt():
    """Inference may outlast a healthy heartbeat; no spurious availability veto."""
    updates = {"count": 0}

    async def probe() -> bool:
        updates["count"] += 1
        return True

    async with httpx.AsyncClient(transport=httpx.MockTransport(_transport)) as client:
        router = build_health_aware_router(
            client, trusted_health_probes={GEO: probe},
        )
        await router.check_health_once()
        first = _menu(router)
        assert first.route_ids == (GEO,)
        old_stamp = dict(first.checked_at)[GEO]
        # Simulate model inference lasting beyond the watchdog interval.
        await asyncio.sleep(0.01)
        await router.check_health_once()
        assert updates["count"] == 2
        assert dict(_menu(router).checked_at)[GEO] > old_stamp
        # The old source/authorization/selected-route ID is still valid:
        # only another successful heartbeat occurred.
        first.assert_current()
        observation = await execute_health_scoped_host_call(
            first, route_id=GEO, arguments=HOST,
            host_required_output_fields=("latitude", "longitude"),
        )
        assert observation["status"] == "ok"
        await router.aclose()


@pytest.mark.asyncio
async def test_old_tool_menu_is_invalid_after_probe_replacement_even_if_new_probe_healthy():
    async with httpx.AsyncClient(transport=httpx.MockTransport(_transport)) as client:
        router = build_health_aware_router(
            client, trusted_health_probes={GEO: lambda: True},
        )
        await router.check_health_once()
        first = _menu(router)
        before = tuple(first.probe_identities)
        assert first.route_ids == (GEO,)
        await asyncio.sleep(0.01)
        router.register_health_probe(
            "open_meteo_geocoding", "search", lambda: True,
        )
        await router.check_health_once()
        second = _menu(router)
        assert second.route_ids == (GEO,)
        assert second.probe_identities != before
        with pytest.raises(PolicyViolationError, match="availability changed"):
            first.assert_current()
        with pytest.raises(PolicyViolationError, match="availability changed"):
            await execute_health_scoped_host_call(
                first, route_id=GEO, arguments=HOST,
            )
        await router.aclose()


@pytest.mark.asyncio
async def test_old_menu_rejected_after_unhealthy_then_healthy_same_probe():
    state = {"ok": True}

    async def probe() -> bool:
        return state["ok"]

    async with httpx.AsyncClient(transport=httpx.MockTransport(_transport)) as client:
        router = build_health_aware_router(
            client, trusted_health_probes={GEO: probe},
        )
        await router.check_health_once()
        before = _menu(router)
        state["ok"] = False
        await router.check_health_once()
        assert _menu(router).route_ids == ()
        state["ok"] = True
        await router.check_health_once()
        now = _menu(router)
        assert now.route_ids == (GEO,)
        assert now.probe_identities != before.probe_identities
        with pytest.raises(PolicyViolationError, match="availability changed"):
            before.assert_current()
        await router.aclose()


@pytest.mark.asyncio
async def test_health_changes_during_model_window_abort_old_menu():
    state = {"ok": True}

    async def probe() -> bool:
        return state["ok"]

    async with httpx.AsyncClient(transport=httpx.MockTransport(_transport)) as client:
        router = build_health_aware_router(
            client, trusted_health_probes={GEO: probe},
        )
        await router.check_health_once()
        before = _menu(router)
        assert before.route_ids == (GEO,)

        state["ok"] = False
        await router.check_health_once()
        with pytest.raises(PolicyViolationError, match="availability changed"):
            before.assert_current()
        assert _menu(router).route_ids == ()
        await router.aclose()


@pytest.mark.asyncio
async def test_background_monitor_reopens_after_health_recovers_without_model():
    available = asyncio.Event()
    recovered = asyncio.Event()

    async def probe() -> bool:
        if available.is_set():
            recovered.set()
            return True
        return False

    async with httpx.AsyncClient(transport=httpx.MockTransport(_transport)) as client:
        router = build_health_aware_router(
            client, trusted_health_probes={GEO: probe},
        )
        await router.start_health_monitor(
            interval_seconds=0.01, probe_timeout_seconds=0.1,
            max_concurrency=1,
        )
        try:
            await asyncio.sleep(0.035)
            assert _menu(router).status == "temporary_unavailable"
            available.set()
            await asyncio.wait_for(recovered.wait(), timeout=1)
            for _ in range(20):
                if _menu(router).route_ids == (GEO,):
                    break
                await asyncio.sleep(0.01)
            assert _menu(router).route_ids == (GEO,)
        finally:
            await router.aclose()
        assert router.health_monitor.running is False


@pytest.mark.asyncio
async def test_hidden_field_scoped_cooldown_does_not_reveal_private_route():
    async with httpx.AsyncClient(transport=httpx.MockTransport(_transport)) as client:
        router = build_health_aware_router(
            client, trusted_health_probes={GEO: lambda: True},
        )
        policy = AuthorizationPolicy(
            default_effect="deny",
            rules=(AuthorizationRule(
                effect="allow", operation=GEO, roles_any=("reader",),
            ),),
            data_rules=(DataScopeRule(
                operation=GEO, roles_any=("reader",),
                visible_fields=(),
            ),),
        )
        router.authorization_policy = policy
        router.executor.authorization_policy = policy
        await router.check_health_once()
        router.mark_access_unavailable("open_meteo_geocoding", "search")
        # The role alone is allowed; all actual output fields are hidden.
        # A scoped caller cannot infer an otherwise private cooled-down
        # capability from a different public disposition.
        hidden = _menu(router)
        assert hidden.route_ids == ()
        assert hidden.definitions == ()
        assert hidden.status == "inputs_missing"
        await router.aclose()


@pytest.mark.asyncio
async def test_source_schema_change_never_uses_old_healthy_model_menu():
    async with httpx.AsyncClient(transport=httpx.MockTransport(_transport)) as client:
        router = build_health_aware_router(
            client, trusted_health_probes={GEO: lambda: True},
        )
        await router.check_health_once()
        menu = _menu(router)
        old = router.registry.get("open_meteo_geocoding")
        new = old.model_copy(deep=True)
        new.description = "changed schema description"
        router.add_tool(new, replace=True)
        with pytest.raises(PolicyViolationError):
            menu.assert_current()
        assert _menu(router).route_ids == ()
        await router.aclose()


def test_refuse_to_register_unknown_or_mutating_health_routes():
    with pytest.raises(ValueError, match="trusted read-only"):
        build_health_aware_router(
            httpx.AsyncClient(), trusted_health_probes={
                "hidden.admin_write": lambda: True,
            },
        )
